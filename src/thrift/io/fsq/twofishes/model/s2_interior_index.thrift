namespace java io.fsq.twofishes.model.gen

include "io/fsq/twofishes/types.thrift"

struct ThriftS2InteriorIndex {
  1: optional types.ThriftObjectId id (wire_name="_id")
  2: optional list<i64> cellIds
} (
  primary_key="id"
  mongo_collection="s2_interior_index"
  mongo_identifier="geocoder"
)
