# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: nucliadb_protos/replication.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from nucliadb_protos import noderesources_pb2 as nucliadb__protos_dot_noderesources__pb2
try:
  nucliadb__protos_dot_utils__pb2 = nucliadb__protos_dot_noderesources__pb2.nucliadb__protos_dot_utils__pb2
except AttributeError:
  nucliadb__protos_dot_utils__pb2 = nucliadb__protos_dot_noderesources__pb2.nucliadb_protos.utils_pb2

from nucliadb_protos.noderesources_pb2 import *

DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n!nucliadb_protos/replication.proto\x12\x0breplication\x1a#nucliadb_protos/noderesources.proto\"i\n\x1cPrimaryShardReplicationState\x12\x10\n\x08shard_id\x18\x01 \x01(\t\x12\x15\n\rgeneration_id\x18\x02 \x01(\t\x12\x0c\n\x04kbid\x18\x03 \x01(\t\x12\x12\n\nsimilarity\x18\x04 \x01(\t\"I\n\x1eSecondaryShardReplicationState\x12\x10\n\x08shard_id\x18\x01 \x01(\t\x12\x15\n\rgeneration_id\x18\x02 \x01(\t\"\x80\x01\n%SecondaryCheckReplicationStateRequest\x12\x14\n\x0csecondary_id\x18\x01 \x01(\t\x12\x41\n\x0cshard_states\x18\x02 \x03(\x0b\x32+.replication.SecondaryShardReplicationState\"\x95\x01\n$PrimaryCheckReplicationStateResponse\x12?\n\x0cshard_states\x18\x01 \x03(\x0b\x32).replication.PrimaryShardReplicationState\x12\x18\n\x10shards_to_remove\x18\x02 \x03(\t\x12\x12\n\nprimary_id\x18\x03 \x01(\t\"\x1b\n\nSegmentIds\x12\r\n\x05items\x18\x01 \x03(\t\"\xeb\x01\n\x15ReplicateShardRequest\x12\x10\n\x08shard_id\x18\x01 \x01(\t\x12X\n\x14\x65xisting_segment_ids\x18\x02 \x03(\x0b\x32:.replication.ReplicateShardRequest.ExistingSegmentIdsEntry\x12\x12\n\nchunk_size\x18\x03 \x01(\x04\x1aR\n\x17\x45xistingSegmentIdsEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12&\n\x05value\x18\x02 \x01(\x0b\x32\x17.replication.SegmentIds:\x02\x38\x01\"\x89\x01\n\x16ReplicateShardResponse\x12\x15\n\rgeneration_id\x18\x01 \x01(\t\x12\x10\n\x08\x66ilepath\x18\x02 \x01(\t\x12\x0c\n\x04\x64\x61ta\x18\x03 \x01(\x0c\x12\r\n\x05\x63hunk\x18\x04 \x01(\r\x12\x15\n\rread_position\x18\x05 \x01(\x04\x12\x12\n\ntotal_size\x18\x06 \x01(\x04\x32\xbf\x02\n\x12ReplicationService\x12\x80\x01\n\x15\x43heckReplicationState\x12\x32.replication.SecondaryCheckReplicationStateRequest\x1a\x31.replication.PrimaryCheckReplicationStateResponse\"\x00\x12]\n\x0eReplicateShard\x12\".replication.ReplicateShardRequest\x1a#.replication.ReplicateShardResponse\"\x00\x30\x01\x12G\n\x0bGetMetadata\x12\x19.noderesources.EmptyQuery\x1a\x1b.noderesources.NodeMetadata\"\x00P\x00\x62\x06proto3')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'nucliadb_protos.replication_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  _REPLICATESHARDREQUEST_EXISTINGSEGMENTIDSENTRY._options = None
  _REPLICATESHARDREQUEST_EXISTINGSEGMENTIDSENTRY._serialized_options = b'8\001'
  _PRIMARYSHARDREPLICATIONSTATE._serialized_start=87
  _PRIMARYSHARDREPLICATIONSTATE._serialized_end=192
  _SECONDARYSHARDREPLICATIONSTATE._serialized_start=194
  _SECONDARYSHARDREPLICATIONSTATE._serialized_end=267
  _SECONDARYCHECKREPLICATIONSTATEREQUEST._serialized_start=270
  _SECONDARYCHECKREPLICATIONSTATEREQUEST._serialized_end=398
  _PRIMARYCHECKREPLICATIONSTATERESPONSE._serialized_start=401
  _PRIMARYCHECKREPLICATIONSTATERESPONSE._serialized_end=550
  _SEGMENTIDS._serialized_start=552
  _SEGMENTIDS._serialized_end=579
  _REPLICATESHARDREQUEST._serialized_start=582
  _REPLICATESHARDREQUEST._serialized_end=817
  _REPLICATESHARDREQUEST_EXISTINGSEGMENTIDSENTRY._serialized_start=735
  _REPLICATESHARDREQUEST_EXISTINGSEGMENTIDSENTRY._serialized_end=817
  _REPLICATESHARDRESPONSE._serialized_start=820
  _REPLICATESHARDRESPONSE._serialized_end=957
  _REPLICATIONSERVICE._serialized_start=960
  _REPLICATIONSERVICE._serialized_end=1279
# @@protoc_insertion_point(module_scope)
