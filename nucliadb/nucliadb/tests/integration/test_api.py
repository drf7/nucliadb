# Copyright (C) 2021 Bosutech XXI S.L.
#
# nucliadb is offered under the AGPL v3.0 and as commercial software.
# For commercial licensing, contact us at info@nuclia.com.
#
# AGPL:
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
import asyncio

import pytest
from httpx import AsyncClient
from nucliadb_protos.dataset_pb2 import TaskType, TrainSet
from nucliadb_protos.resources_pb2 import (
    Answers,
    ExtractedTextWrapper,
    FieldComputedMetadataWrapper,
    FieldID,
    FieldQuestionAnswerWrapper,
    FieldType,
    FileExtractedData,
    LinkExtractedData,
    Paragraph,
    QuestionAnswer,
)
from nucliadb_protos.train_pb2 import GetSentencesRequest, TrainParagraph
from nucliadb_protos.train_pb2_grpc import TrainStub
from nucliadb_protos.writer_pb2 import BrokerMessage, OpStatusWriter
from nucliadb_protos.writer_pb2_grpc import WriterStub

from nucliadb.tests.utils import broker_resource, inject_message
from nucliadb_protos import resources_pb2 as rpb
from nucliadb_protos import writer_pb2 as wpb


@pytest.mark.asyncio
async def test_kb_creation_with_similarity(
    nucliadb_manager,
    nucliadb_reader,
):
    # Check that by default we get cosine similarity
    resp = await nucliadb_manager.post(
        f"/kbs",
        json={"title": "My KB", "slug": "kb1"},
        timeout=None,
    )
    assert resp.status_code == 201
    kbid = resp.json()["uuid"]
    resp = await nucliadb_manager.get(f"/kb/{kbid}/shards")
    assert resp.status_code == 200
    body = resp.json()
    assert body["similarity"] == "cosine"
    assert body["model"]["similarity_function"] == "cosine"

    # Check that we can define it to dot similarity
    resp = await nucliadb_manager.post(
        f"/kbs",
        json={"title": "My KB with dot similarity", "slug": "dot", "similarity": "dot"},
    )
    assert resp.status_code == 201
    dot_kbid = resp.json()["uuid"]
    resp = await nucliadb_manager.get(f"/kb/{dot_kbid}/shards")
    assert resp.status_code == 200
    body = resp.json()
    assert body["similarity"] == "dot"
    assert body["model"]["similarity_function"] == "dot"


@pytest.mark.asyncio
@pytest.mark.parametrize("knowledgebox", ("EXPERIMENTAL", "STABLE"), indirect=True)
async def test_creation(
    nucliadb_reader: AsyncClient,
    nucliadb_writer: AsyncClient,
    nucliadb_grpc: WriterStub,
    nucliadb_train: TrainStub,
    knowledgebox,
):
    # PUBLIC API
    resp = await nucliadb_reader.get(f"/kb/{knowledgebox}")
    assert resp.status_code == 200

    resp = await nucliadb_writer.post(
        f"/kb/{knowledgebox}/labelset/ls1",
        json={"title": "Labelset 1", "labels": [{"text": "text", "title": "title"}]},
    )
    assert resp.status_code == 200

    resp = await nucliadb_writer.post(
        f"/kb/{knowledgebox}/resources",
        json={
            "title": "My title",
            "slug": "myresource",
            "texts": {"text1": {"body": "My text"}},
        },
    )

    assert resp.status_code == 201
    rid = resp.json()["uuid"]

    # PROCESSING API

    bm = BrokerMessage()
    et = ExtractedTextWrapper()
    fm = FieldComputedMetadataWrapper()
    et.field.field = "text1"
    fm.field.field = "text1"
    et.field.field_type = FieldType.TEXT
    fm.field.field_type = FieldType.TEXT
    et.body.text = "My text"
    fm.metadata.metadata.language = "en"
    p1 = Paragraph()
    p1.start = 0
    p1.end = 7

    fm.metadata.metadata.paragraphs.append(p1)
    bm.extracted_text.append(et)
    bm.field_metadata.append(fm)
    bm.uuid = rid
    bm.kbid = knowledgebox

    async def iterate(value: BrokerMessage):
        yield value

    await nucliadb_grpc.ProcessMessage(iterate(bm))  # type: ignore

    resp = await nucliadb_reader.get(
        f"/kb/{knowledgebox}/resource/{rid}?show=extracted&show=values&extracted=text&extracted=metadata",
    )
    assert resp.status_code == 200
    assert (
        resp.json()["data"]["texts"]["text1"]["extracted"]["metadata"]["metadata"][
            "paragraphs"
        ][0]["end"]
        == 7
    )

    # ADD A LABEL

    resp = await nucliadb_writer.patch(
        f"/kb/{knowledgebox}/resource/{rid}",
        json={
            "fieldmetadata": [
                {
                    "field": {
                        "field": "text1",
                        "field_type": "text",
                    },
                    "paragraphs": [
                        {
                            "key": f"{rid}/t/text1/0-7",
                            "classifications": [{"labelset": "ls1", "label": "label"}],
                        }
                    ],
                }
            ]
        },
    )
    assert resp.status_code == 200

    resp = await nucliadb_reader.get(
        f"/kb/{knowledgebox}/resource/{rid}?show=errors&show=values&show=basic",
        timeout=None,
    )
    assert resp.status_code == 200

    # TRAINING GRPC API
    request = GetSentencesRequest()
    request.kb.uuid = knowledgebox
    request.metadata.labels = True
    request.metadata.text = True
    paragraph: TrainParagraph
    async for paragraph in nucliadb_train.GetParagraphs(request):  # type: ignore
        if paragraph.field.field == "title":
            assert paragraph.metadata.text == "My title"
        else:
            assert paragraph.metadata.text == "My text"
            assert paragraph.metadata.labels.paragraph[0].label == "label"

    # TRAINING REST API
    trainset = TrainSet()
    trainset.batch_size = 20
    trainset.type = TaskType.PARAGRAPH_CLASSIFICATION
    trainset.filter.labels.append("ls1")
    resp = await nucliadb_reader.get(f"/kb/{knowledgebox}/trainset")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["partitions"]) == 1
    partition_id = data["partitions"][0]

    resp = await nucliadb_reader.post(
        f"/kb/{knowledgebox}/trainset/{partition_id}",
        content=trainset.SerializeToString(),
    )
    assert len(resp.content) > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("channel", ("EXPERIMENTAL", "STABLE"))
async def test_can_create_knowledgebox_with_colon_in_slug(
    nucliadb_manager: AsyncClient, channel
):
    resp = await nucliadb_manager.post(
        "/kbs",
        json={"slug": "something:else", "release_channel": channel},
    )
    assert resp.status_code == 201

    resp = await nucliadb_manager.get(f"/kbs")
    assert resp.status_code == 200
    assert resp.json()["kbs"][0]["slug"] == "something:else"


@pytest.mark.asyncio
@pytest.mark.parametrize("knowledgebox", ("EXPERIMENTAL", "STABLE"), indirect=True)
async def test_reprocess_should_set_status_to_pending(
    nucliadb_writer: AsyncClient,
    nucliadb_reader: AsyncClient,
    nucliadb_grpc: WriterStub,
    knowledgebox: str,
):
    """
    - Create a resource with a status PROCESSED
    - Send it to reprocess
    - Check that the status is set to PENDING
    """
    br = broker_resource(knowledgebox)
    br.basic.metadata.status = rpb.Metadata.Status.PROCESSED
    await inject_message(nucliadb_grpc, br)

    resp = await nucliadb_reader.get(f"/kb/{knowledgebox}/resource/{br.uuid}")
    assert resp.status_code == 200
    resp_json = resp.json()
    assert resp_json["metadata"]["status"] == "PROCESSED"

    resp = await nucliadb_writer.post(
        f"/kb/{knowledgebox}/resource/{br.uuid}/reprocess"
    )
    assert resp.status_code == 202

    await asyncio.sleep(1)

    resp = await nucliadb_reader.get(f"/kb/{knowledgebox}/resource/{br.uuid}")
    assert resp.status_code == 200
    resp_json = resp.json()
    assert resp_json["metadata"]["status"] == "PENDING"


@pytest.mark.asyncio
@pytest.mark.parametrize("knowledgebox", ("EXPERIMENTAL", "STABLE"), indirect=True)
async def test_serialize_errors(
    nucliadb_writer: AsyncClient,
    nucliadb_reader: AsyncClient,
    nucliadb_grpc: WriterStub,
    knowledgebox: str,
):
    """
    Test description:

    - Create a bm with errors for every type of field
    - Get the resource and check that error serialization works
    """
    br = broker_resource(knowledgebox)

    # Add an error for every field type
    fields_to_test = [
        (rpb.FieldType.TEXT, "text", "texts"),
        (rpb.FieldType.FILE, "file", "files"),
        (rpb.FieldType.LINK, "link", "links"),
        (rpb.FieldType.KEYWORDSET, "kws", "keywordsets"),
        (rpb.FieldType.LAYOUT, "layout", "layouts"),
        (rpb.FieldType.CONVERSATION, "conversation", "conversations"),
        (rpb.FieldType.DATETIME, "datetime", "datetimes"),
    ]
    for ftype, fid, _ in fields_to_test:
        field = rpb.FieldID(field_type=ftype, field=fid)
        fcmw = FieldComputedMetadataWrapper()
        fcmw.field.CopyFrom(field)
        fcmw.metadata.metadata.language = "es"
        br.field_metadata.append(fcmw)
        error = wpb.Error(
            field=field.field,
            field_type=field.field_type,
            error="Failed",
            code=wpb.Error.ErrorCode.EXTRACT,
        )
        br.errors.append(error)

    await inject_message(nucliadb_grpc, br)

    resp = await nucliadb_reader.get(
        f"/kb/{knowledgebox}/resource/{br.uuid}",
        params=dict(show=["extracted", "errors", "basic"], extracted=["metadata"]),
    )
    assert resp.status_code == 200
    resp_json = resp.json()

    for _, fid, ftypestring in fields_to_test:
        assert resp_json["data"][ftypestring][fid]["error"]["body"] == "Failed"
        assert resp_json["data"][ftypestring][fid]["error"]["code"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("knowledgebox", ("EXPERIMENTAL", "STABLE"), indirect=True)
async def test_entitygroups(
    nucliadb_writer: AsyncClient,
    nucliadb_reader: AsyncClient,
    nucliadb_grpc: WriterStub,
    knowledgebox: str,
):
    entitygroup = {
        "group": "group1",
        "title": "Kitchen",
        "custom": True,
        "color": "blue",
        "entities": {
            "cupboard": {"value": "Cupboard"},
            "fork": {"value": "Fork"},
            "fridge": {"value": "Fridge"},
            "knife": {"value": "Knife"},
            "sink": {"value": "Sink"},
            "spoon": {"value": "Spoon"},
        },
    }
    resp = await nucliadb_writer.post(
        f"/kb/{knowledgebox}/entitiesgroups", json=entitygroup
    )
    assert resp.status_code == 200

    # Entities are not returned by default
    resp = await nucliadb_reader.get(f"/kb/{knowledgebox}/entitiesgroups")
    groups = resp.json()["groups"]
    assert groups["group1"]["entities"] == {}
    assert groups["group1"]["title"] == "Kitchen"
    assert groups["group1"]["color"] == "blue"
    assert groups["group1"]["custom"] is True

    # But they can be included with show_entities=true
    resp = await nucliadb_reader.get(
        f"/kb/{knowledgebox}/entitiesgroups?show_entities=true"
    )
    groups = resp.json()["groups"]
    assert len(groups) == 1
    assert groups["group1"]["entities"] != {}
    assert groups["group1"]["title"] == "Kitchen"
    assert groups["group1"]["color"] == "blue"
    assert groups["group1"]["custom"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("knowledgebox", ("EXPERIMENTAL", "STABLE"), indirect=True)
async def test_extracted_shortened_metadata(
    nucliadb_writer: AsyncClient,
    nucliadb_reader: AsyncClient,
    nucliadb_grpc: WriterStub,
    knowledgebox: str,
):
    """
    Test description:

    - Create a resource with a field containing FieldMetadata with ner, positions and relations.
    - Check that new extracted data option filters them out
    """
    br = broker_resource(knowledgebox)

    field = rpb.FieldID(field_type=rpb.FieldType.TEXT, field="text")
    fcmw = FieldComputedMetadataWrapper()
    fcmw.field.CopyFrom(field)
    fcmw.metadata.metadata.language = "es"

    # Add some relations
    relation = rpb.Relation(relation_label="foo")
    relations = rpb.Relations()
    relations.relations.append(relation)
    fcmw.metadata.metadata.relations.append(relations)
    fcmw.metadata.split_metadata["split"].relations.append(relations)

    # Add some ners
    ner = {"Barcelona": "CITY/Barcelona"}
    fcmw.metadata.metadata.ner.update(ner)
    fcmw.metadata.split_metadata["split"].ner.update(ner)

    # Add some positions
    position = rpb.Position(start=1, end=2)
    fcmw.metadata.metadata.positions["foo"].position.append(position)
    fcmw.metadata.split_metadata["split"].positions["foo"].position.append(position)

    # Add some classification
    classification = rpb.Classification(label="foo", labelset="bar")
    fcmw.metadata.metadata.classifications.append(classification)
    fcmw.metadata.split_metadata["split"].classifications.append(classification)

    br.field_metadata.append(fcmw)

    await inject_message(nucliadb_grpc, br)

    cropped_fields = ["ner", "positions", "relations", "classifications"]

    # Check that when 'shortened_metadata' in extracted param fields are cropped
    resp = await nucliadb_reader.get(
        f"/kb/{knowledgebox}/resource/{br.uuid}/text/text",
        params=dict(show=["extracted"], extracted=["shortened_metadata"]),
    )
    assert resp.status_code == 200
    resp_json = resp.json()
    metadata = resp_json["extracted"]["metadata"]["metadata"]
    split_metadata = resp_json["extracted"]["metadata"]["split_metadata"]["split"]
    for meta in (metadata, split_metadata):
        for cropped_field in cropped_fields:
            assert len(meta[cropped_field]) == 0

    # Check that when 'metadata' in extracted param fields are returned
    for extracted_param in (["metadata"], ["metadata", "shortened_metadata"]):
        resp = await nucliadb_reader.get(
            f"/kb/{knowledgebox}/resource/{br.uuid}/text/text",
            params=dict(show=["extracted"], extracted=extracted_param),
        )
        assert resp.status_code == 200
        resp_json = resp.json()
        metadata = resp_json["extracted"]["metadata"]["metadata"]
        split_metadata = resp_json["extracted"]["metadata"]["split_metadata"]["split"]
        for meta in (metadata, split_metadata):
            for cropped_field in cropped_fields:
                assert len(meta[cropped_field]) > 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field_id,error,knowledgebox",
    [
        ("foobar", False, "EXPERIMENTAL"),
        ("My_Field_1", False, "EXPERIMENTAL"),
        ("With Spaces Not Allowed", True, "EXPERIMENTAL"),
        ("Invalid&Character", True, "EXPERIMENTAL"),
        ("foobar", False, "STABLE"),
        ("My_Field_1", False, "STABLE"),
        ("With Spaces Not Allowed", True, "STABLE"),
        ("Invalid&Character", True, "STABLE"),
    ],
)
async def test_field_ids_are_validated(
    nucliadb_writer: AsyncClient,
    knowledgebox: str,
    field_id,
    error,
):
    payload = {
        "title": "Foo",
        "texts": {
            field_id: {
                "format": "HTML",
                "body": "<p>whatever</p>",
            }
        },
    }
    resp = await nucliadb_writer.post(f"/kb/{knowledgebox}/resources", json=payload)
    if error:
        assert resp.status_code == 422
        body = resp.json()
        assert body["detail"][0]["type"] == "value_error.wrong_field_id"
    else:
        assert resp.status_code == 201


@pytest.mark.asyncio
@pytest.mark.parametrize("knowledgebox", ("EXPERIMENTAL", "STABLE"), indirect=True)
async def test_extra(
    nucliadb_writer: AsyncClient,
    nucliadb_reader: AsyncClient,
    knowledgebox: str,
):
    """
    Test description:
    - Check that limits are applied
    - Check that it is returned only if requested on resource GET
    - Check that it is returned only if requested on search results
    - Check modification
    """
    kbid = knowledgebox
    invalid_extra = {"metadata": {i: f"foo{i}" for i in range(100000)}}
    resp = await nucliadb_writer.post(
        f"/kb/{kbid}/resources",
        json={
            "title": "Foo",
            "extra": invalid_extra,
        },
    )
    assert resp.status_code == 422
    error_detail = resp.json()["detail"][0]
    assert error_detail["loc"] == ["body", "extra"]
    assert error_detail["type"] == "value_error"
    assert (
        error_detail["msg"]
        == "metadata should be less than 400000 bytes when serialized to JSON"
    )
    extra = {
        "metadata": {
            "str": "str",
            "number": 2.0,
            "list": [1.0, 2.0, 3.0],
            "dict": {"foo": "bar"},
        }
    }
    resp = await nucliadb_writer.post(
        f"/kb/{kbid}/resources",
        json={
            "title": "Foo",
            "extra": extra,
        },
        headers={"X-SYNCHRONOUS": "true"},
        timeout=None,
    )
    assert resp.status_code == 201
    rid = resp.json()["uuid"]

    # Check that extra metadata is not returned by default on GET
    resp = await nucliadb_reader.get(f"/kb/{kbid}/resource/{rid}")
    assert resp.status_code == 200
    assert "extra" not in resp.json()

    # Check that extra metadata is returned when requested on GET
    resp = await nucliadb_reader.get(f"/kb/{kbid}/resource/{rid}?show=extra")
    assert resp.status_code == 200
    assert resp.json()["extra"] == extra

    # Check that extra metadata is not returned by default on search
    resp = await nucliadb_reader.get(f"/kb/{kbid}/search?query=foo")
    assert resp.status_code == 200
    resource = resp.json()["resources"][rid]
    assert "extra" not in resource

    # Check that extra metadata is returned when requested on search results
    resp = await nucliadb_reader.get(f"/kb/{kbid}/search?query=foo&show=extra")
    assert resp.status_code == 200
    resource = resp.json()["resources"][rid]
    assert resource["extra"] == extra

    # Check modification of extra metadata
    extra["metadata"].pop("dict")
    resp = await nucliadb_writer.patch(
        f"/kb/{kbid}/resource/{rid}", json={"extra": extra}
    )
    assert resp.status_code == 200

    resp = await nucliadb_reader.get(f"/kb/{kbid}/resource/{rid}?show=extra")
    assert resp.status_code == 200
    assert resp.json()["extra"] == extra


@pytest.mark.asyncio
@pytest.mark.parametrize("knowledgebox", ("EXPERIMENTAL", "STABLE"), indirect=True)
async def test_icon_doesnt_change_after_labeling_resource_sc_5625(
    nucliadb_reader: AsyncClient,
    nucliadb_writer: AsyncClient,
    knowledgebox,
):
    kbid = knowledgebox
    resp = await nucliadb_writer.post(
        f"/kb/{kbid}/resources",
        json={"title": "Foo", "icon": "application/pdf"},
        headers={"X-SYNCHRONOUS": "True"},
        timeout=None,
    )
    assert resp.status_code == 201
    uuid = resp.json()["uuid"]

    resp = await nucliadb_reader.get(f"/kb/{kbid}/resource/{uuid}")
    assert resp.json()["icon"] == "application/pdf"

    # A partial patch should not change the icon
    resp = await nucliadb_writer.patch(
        f"/kb/{kbid}/resource/{uuid}",
        json={
            "usermetadata": {"classifications": [{"labelset": "foo", "label": "bar"}]}
        },
        headers={"X-SYNCHRONOUS": "True"},
        timeout=None,
    )
    assert resp.status_code == 200

    resp = await nucliadb_reader.get(f"/kb/{kbid}/resource/{uuid}")
    assert resp.json()["icon"] == "application/pdf"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "knowledgebox",
    ("STABLE", "EXPERIMENTAL"),
    indirect=True,
)
@pytest.mark.parametrize(
    "slug,valid",
    [
        ("foo", True),
        ("foo-bar", True),  # with dash
        ("foo:bar", True),  # with colon
        ("foo_bar", True),  # with underscore
        ("FooBar", True),  # with capital letters
        ("foo.bar", False),  # with dot
        ("foo/bar", False),  # with slash
    ],
)
async def test_resource_slug_validation(
    nucliadb_writer, nucliadb_reader, knowledgebox, slug, valid
):
    resp = await nucliadb_writer.post(
        f"/kb/{knowledgebox}/resources", json={"slug": slug}
    )
    if valid:
        assert resp.status_code == 201
        resp = await nucliadb_reader.get(f"/kb/{knowledgebox}/slug/{slug}")
        assert resp.status_code == 200
    else:
        assert resp.status_code == 422
        detail = resp.json()["detail"][0]
        assert detail["loc"] == ["body", "slug"]
        assert detail["msg"].startswith(f"Invalid slug: '{slug}'")


@pytest.mark.asyncio
@pytest.mark.parametrize("knowledgebox", ("EXPERIMENTAL", "STABLE"), indirect=True)
async def test_icon_doesnt_change_after_adding_file_field_sc_2388(
    nucliadb_reader: AsyncClient,
    nucliadb_writer: AsyncClient,
    knowledgebox,
):
    kbid = knowledgebox
    resp = await nucliadb_writer.post(
        f"/kb/{kbid}/resources",
        json={
            "title": "Foo",
            "icon": "text/plain",
            "texts": {"text": {"body": "my text"}},
        },
        headers={"X-SYNCHRONOUS": "True"},
        timeout=None,
    )
    assert resp.status_code == 201
    uuid = resp.json()["uuid"]

    resp = await nucliadb_reader.get(f"/kb/{kbid}/resource/{uuid}")
    assert resp.json()["icon"] == "text/plain"

    # A subsequent file upload should not change the icon
    resp = await nucliadb_writer.post(
        f"/kb/{kbid}/resource/{uuid}/file/file/upload",
        content=b"foo" * 200,
        headers={"X-SYNCHRONOUS": "True"},
        timeout=None,
    )
    assert resp.status_code == 201

    resp = await nucliadb_reader.get(f"/kb/{kbid}/resource/{uuid}")
    assert resp.json()["icon"] == "text/plain"


@pytest.mark.asyncio
@pytest.mark.parametrize("knowledgebox", ("EXPERIMENTAL", "STABLE"), indirect=True)
async def test_language_metadata(
    nucliadb_writer,
    nucliadb_reader,
    nucliadb_grpc,
    knowledgebox,
):
    kbid = knowledgebox
    resp = await nucliadb_writer.post(
        f"/kb/{kbid}/resources",
        json={"title": "My resource"},
        headers={"X-SYNCHRONOUS": "True"},
        timeout=None,
    )
    assert resp.status_code == 201
    uuid = resp.json()["uuid"]

    # Detected language in processing should be stored in basic metadata
    bm = BrokerMessage()
    bm.kbid = kbid
    bm.uuid = uuid
    field = FieldID(field_type=FieldType.TEXT, field="text")

    led = LinkExtractedData()
    led.field = field.field
    led.language = "ca"
    bm.link_extracted_data.append(led)

    fed = FileExtractedData()
    fed.field = field.field
    fed.language = "es"
    bm.file_extracted_data.append(fed)

    fcmw = FieldComputedMetadataWrapper()
    fcmw.field.CopyFrom(field)
    fcmw.metadata.metadata.language = "en"
    fcmw.metadata.split_metadata["foo"].language = "it"
    bm.field_metadata.append(fcmw)

    resp = await nucliadb_grpc.ProcessMessage([bm])
    assert resp.status == OpStatusWriter.Status.OK

    resp = await nucliadb_reader.get(
        f"/kb/{kbid}/resource/{uuid}", params={"show": ["basic"]}
    )
    assert resp.status_code == 200
    res = resp.json()
    assert res["metadata"]["language"] == "ca"
    assert set(res["metadata"]["languages"]) == {"ca", "es", "it", "en"}

    resp = await nucliadb_writer.post(
        f"/kb/{kbid}/resources",
        json={"metadata": {"language": "en"}},
        headers={"X-SYNCHRONOUS": "True"},
        timeout=None,
    )
    assert resp.status_code == 201
    uuid = resp.json()["uuid"]

    resp = await nucliadb_reader.get(
        f"/kb/{kbid}/resource/{uuid}", params={"show": ["basic"]}
    )
    assert resp.status_code == 200
    res = resp.json()
    assert res["metadata"]["language"] == "en"
    assert res["metadata"]["languages"] == []

    resp = await nucliadb_writer.patch(
        f"/kb/{kbid}/resource/{uuid}",
        json={"metadata": {"language": "de"}},
        headers={"X-SYNCHRONOUS": "True"},
        timeout=None,
    )
    assert resp.status_code == 200

    resp = await nucliadb_reader.get(
        f"/kb/{kbid}/resource/{uuid}", params={"show": ["basic"]}
    )
    assert resp.status_code == 200
    res = resp.json()
    assert res["metadata"]["language"] == "de"
    assert res["metadata"]["languages"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("knowledgebox", ("EXPERIMENTAL", "STABLE"), indirect=True)
async def test_story_7081(
    nucliadb_reader: AsyncClient,
    nucliadb_writer: AsyncClient,
    knowledgebox,
):
    resp = await nucliadb_writer.post(
        f"/kb/{knowledgebox}/resources",
        json={
            "title": "My title",
            "slug": "myresource",
            "texts": {"text1": {"body": "My text"}},
        },
    )

    assert resp.status_code == 201
    rid = resp.json()["uuid"]

    resp = await nucliadb_writer.patch(
        f"/kb/{knowledgebox}/resource/{rid}",
        json={"origin": {"metadata": {"some": "data"}}},
    )
    assert resp.status_code == 200

    resp = await nucliadb_reader.get(
        f"/kb/{knowledgebox}/resource/{rid}?show=origin",
        timeout=None,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["origin"]["metadata"]["some"] == "data"


@pytest.mark.asyncio
@pytest.mark.parametrize("knowledgebox", ("EXPERIMENTAL", "STABLE"), indirect=True)
async def test_question_answer(
    nucliadb_reader: AsyncClient,
    nucliadb_writer: AsyncClient,
    nucliadb_grpc: WriterStub,
    knowledgebox,
):
    # create a new resource
    resp = await nucliadb_writer.post(
        f"/kb/{knowledgebox}/resources",
        json={
            "title": "My title",
            "slug": "myresource",
            "texts": {"text1": {"body": "My text"}},
        },
    )

    assert resp.status_code == 201
    rid = resp.json()["uuid"]

    # send a broker message with the Q/A
    message = BrokerMessage()
    qaw = FieldQuestionAnswerWrapper()
    qaw.field.field_type = FieldType.TEXT
    qaw.field.field = "text1"

    for i in range(10):
        qa = QuestionAnswer()

        qa.question.text = f"My question {i}"
        qa.question.language = "catalan"
        qa.question.ids_paragraphs.extend([f"id1/{i}", f"id2/{i}"])

        for x in range(2):
            answer = Answers()
            answer.text = f"My answer {i}{x}"
            answer.language = "catalan"
            answer.ids_paragraphs.extend([f"id1/{i}{x}", f"id2/{i}{x}"])
            qa.answers.append(answer)

        qaw.question_answers.question_answer.append(qa)

    message.question_answers.append(qaw)
    message.uuid = rid
    message.kbid = knowledgebox

    async def iterate(value: BrokerMessage):
        yield value

    await nucliadb_grpc.ProcessMessage(iterate(message))  # type: ignore

    resp = await nucliadb_reader.get(
        f"/kb/{knowledgebox}/resource/{rid}?show=extracted&extracted=question_answers",
        timeout=None,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["data"]["texts"]["text1"]["extracted"]["question_answers"][
        "question_answer"
    ][0] == {
        "question": {
            "text": "My question 0",
            "language": "catalan",
            "ids_paragraphs": ["id1/0", "id2/0"],
        },
        "answers": [
            {
                "ids_paragraphs": ["id1/00", "id2/00"],
                "language": "catalan",
                "text": "My answer 00",
            },
            {
                "ids_paragraphs": ["id1/01", "id2/01"],
                "language": "catalan",
                "text": "My answer 01",
            },
        ],
    }
