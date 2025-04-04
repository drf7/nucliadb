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
from unittest import mock

import pytest

from nucliadb.search.predict import AnswerStatusCode
from nucliadb.search.search.chat.query import (
    _parse_answer_status_code,
    chat,
    get_find_results,
)
from nucliadb_models.search import (
    ChatOptions,
    ChatRequest,
    KnowledgeboxFindResults,
    NucliaDBClientType,
    SearchOptions,
)


@pytest.fixture()
def predict():
    predict = mock.AsyncMock()
    with mock.patch(
        "nucliadb.search.search.chat.query.get_predict", return_value=predict
    ):
        yield predict


async def test_chat_does_not_call_predict_if_no_find_results(
    predict,
):
    find_results = KnowledgeboxFindResults(
        total=0, min_score=0.7, resources={}, facets=[]
    )
    chat_request = ChatRequest(query="query")

    with mock.patch(
        "nucliadb.search.search.chat.query.get_find_results", return_value=find_results
    ):
        await chat(
            "kbid",
            chat_request,
            "user_id",
            NucliaDBClientType.API,
            "origin",
        )

    predict.chat_query.assert_not_called()


@pytest.mark.parametrize(
    "chunk,status_code,error",
    [
        (b"", None, True),
        (b"errorcodeisnotpresetn", None, True),
        (b"0", AnswerStatusCode.SUCCESS, False),
        (b"-1", AnswerStatusCode.ERROR, False),
        (b"-2", AnswerStatusCode.NO_CONTEXT, False),
        (b"foo.0", AnswerStatusCode.SUCCESS, False),
        (b"bar.-1", AnswerStatusCode.ERROR, False),
        (b"baz.-2", AnswerStatusCode.NO_CONTEXT, False),
    ],
)
def test_parse_status_code(chunk, status_code, error):
    if error:
        with pytest.raises(ValueError):
            _parse_answer_status_code(chunk)
    else:
        assert _parse_answer_status_code(chunk) == status_code


@pytest.mark.parametrize(
    "chat_features,find_features",
    [
        (
            None,  # default value will be used
            [SearchOptions.VECTOR, SearchOptions.PARAGRAPH, SearchOptions.RELATIONS],
        ),
        (
            [ChatOptions.PARAGRAPHS, ChatOptions.VECTORS, ChatOptions.RELATIONS],
            [SearchOptions.PARAGRAPH, SearchOptions.VECTOR, SearchOptions.RELATIONS],
        ),
        (
            [ChatOptions.PARAGRAPHS, ChatOptions.VECTORS],
            [
                SearchOptions.PARAGRAPH,
                SearchOptions.VECTOR,
            ],
        ),
        (
            [ChatOptions.VECTORS],
            [
                SearchOptions.VECTOR,
            ],
        ),
        (
            [ChatOptions.PARAGRAPHS],
            [
                SearchOptions.PARAGRAPH,
            ],
        ),
    ],
)
async def test_get_find_results_vector_search_is_optional(
    predict, chat_features, find_features
):
    find_results = KnowledgeboxFindResults(
        total=0, min_score=0.7, resources={}, facets=[]
    )

    chat_request = ChatRequest(query="query")
    if chat_features is not None:
        chat_request.features = chat_features

    with mock.patch(
        "nucliadb.search.search.chat.query.find", return_value=(find_results, False)
    ) as find_mock:
        await get_find_results(
            kbid="kbid",
            query="query",
            chat_request=chat_request,
            ndb_client=NucliaDBClientType.API,
            user="user_id",
            origin="origin",
        )
        find_request = find_mock.call_args[0][1]
        assert set(find_request.features) == set(find_features)
