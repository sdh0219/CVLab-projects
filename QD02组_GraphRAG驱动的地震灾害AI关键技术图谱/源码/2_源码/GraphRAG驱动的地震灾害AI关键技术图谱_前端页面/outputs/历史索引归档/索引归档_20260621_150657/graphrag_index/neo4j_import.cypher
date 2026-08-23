// Neo4j 导入脚本：从 outputs/graphrag_index 导入地震灾害知识图谱
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.entity_id IS UNIQUE;

LOAD CSV WITH HEADERS FROM 'file:///graph_nodes.csv' AS row
MERGE (n:Entity {entity_id: row.entity_id})
SET n.name = row.name,
    n.entity_type = row.entity_type,
    n.description = row.description,
    n.community_id = row.community_id,
    n.review_status = row.review_status;

LOAD CSV WITH HEADERS FROM 'file:///graph_edges_neo4j.csv' AS row
MATCH (s:Entity {entity_id: row.source_id})
MATCH (t:Entity {entity_id: row.target_id})
MERGE (s)-[r:RELATED {relation_id: row.relation_id}]->(t)
SET r.relation_type = row.relation_type,
    r.confidence = toFloat(row.confidence),
    r.doc_id = row.doc_id,
    r.chunk_id = row.chunk_id,
    r.evidence_text = row.evidence_text,
    r.review_status = row.review_status;
