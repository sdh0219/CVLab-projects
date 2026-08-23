// Put CSV files in Neo4j import directory before running.
CREATE CONSTRAINT atlas_entity_id IF NOT EXISTS FOR (n:AtlasEntity) REQUIRE n.entity_id IS UNIQUE;

LOAD CSV WITH HEADERS FROM 'file:///graph_nodes.csv' AS row
MERGE (n:AtlasEntity {entity_id: row.`entity_id:ID`})
SET n.name = row.name,
    n.entity_type = row.entity_type,
    n.aliases = row.aliases,
    n.relation_count = toInteger(row.`relation_count:int`),
    n.evidence_count = toInteger(row.`evidence_count:int`),
    n.community_id = row.community_id,
    n.expert_status = row.expert_status;

LOAD CSV WITH HEADERS FROM 'file:///graph_edges_neo4j.csv' AS row
MATCH (s:AtlasEntity {entity_id: row.`:START_ID`})
MATCH (t:AtlasEntity {entity_id: row.`:END_ID`})
CALL apoc.create.relationship(s, row.`:TYPE`, {
  relation_id: row.relation_id,
  doc_id: row.doc_id,
  chunk_id: row.chunk_id,
  confidence: toFloat(row.`confidence:float`),
  evidence_text: row.evidence_text,
  expert_status: row.expert_status
}, t) YIELD rel
RETURN count(rel);
