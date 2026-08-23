export const ENTITY_TYPE_ORDER = [
  "Document",
  "Evidence",
  "AITech",
  "Scenario",
  "Model",
  "Dataset",
  "Task",
  "Case",
  "Event",
  "Policy",
  "Standard",
  "Organization",
  "Metric",
  "ImpactProduct",
  "Limitation",
  "DisasterType",
];

export const RELATION_TYPE_ORDER = [
  "APPLIES_TO",
  "SERVES_STAGE",
  "SOLVES",
  "DEPENDS_ON",
  "USES_MODEL",
  "VALIDATED_IN",
  "LIMITED_BY",
  "REQUIRED_BY",
  "SUPPORTED_BY",
  "DERIVES_FROM",
  "MEASURED_BY",
  "EVALUATED_BY",
  "PUBLISHED_BY",
  "HAS_METRIC",
  "HAS_PARAMETER",
  "HAS_IMPACT",
];

export type AtlasSummary = {
  documents?: number;
  chunks?: number;
  entities?: number;
  claims?: number;
  relations?: number;
  communities?: number;
  extractor?: string;
};

export type AtlasGraphNode = {
  id: string;
  label: string;
  name: string;
  type: string;
  community: string;
  description: string;
  evidenceCount: number;
  relationCount: number;
  reviewStatus: string;
  score?: number;
};

export type AtlasGraphEdge = {
  id: string;
  source: string;
  target: string;
  relationType: string;
  label: string;
  confidence?: number;
  evidenceText: string;
  docId: string;
  chunkId: string;
  sourceName: string;
  reviewStatus: string;
};

export type NormalizedAtlasGraph = {
  nodes: AtlasGraphNode[];
  edges: AtlasGraphEdge[];
  nodeById: Map<string, AtlasGraphNode>;
  relationTypes: string[];
  entityTypes: string[];
  summary: AtlasSummary;
};

type LooseRecord = Record<string, unknown>;

type RawGraphArrays = {
  nodes: unknown[];
  edges: unknown[];
};

function isRecord(value: unknown): value is LooseRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function getRecord(value: unknown, key: string): LooseRecord | null {
  if (!isRecord(value)) return null;
  const child = value[key];
  return isRecord(child) ? child : null;
}

function getArray(value: unknown, key: string): unknown[] {
  if (!isRecord(value)) return [];
  const child = value[key];
  return Array.isArray(child) ? child : [];
}

function readGraphArrays(raw: unknown): RawGraphArrays {
  if (!isRecord(raw)) return { nodes: [], edges: [] };

  const graphData = getRecord(raw, "graphData");
  if (graphData) {
    const nodes = getArray(graphData, "nodes");
    const edges = getArray(graphData, "edges").length ? getArray(graphData, "edges") : getArray(graphData, "links");
    if (nodes.length || edges.length) return { nodes, edges };
  }

  const graph = getRecord(raw, "graph");
  if (graph) {
    const nodes = getArray(graph, "nodes");
    const edges = getArray(graph, "edges").length ? getArray(graph, "edges") : getArray(graph, "links");
    if (nodes.length || edges.length) return { nodes, edges };
  }

  const nodes = getArray(raw, "nodes").length ? getArray(raw, "nodes") : getArray(raw, "graphNodes");
  const edges = getArray(raw, "edges").length
    ? getArray(raw, "edges")
    : getArray(raw, "links").length
      ? getArray(raw, "links")
      : getArray(raw, "graphEdges");
  return { nodes, edges };
}

function getValue(record: LooseRecord, keys: string[]): unknown {
  for (const key of keys) {
    const value = record[key];
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return undefined;
}

function toText(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value.trim() || fallback;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return String(value);
  return fallback;
}

function toNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const next = Number(value);
    return Number.isFinite(next) ? next : undefined;
  }
  return undefined;
}

function normalizeEndpoint(value: unknown): string {
  if (isRecord(value)) return toText(getValue(value, ["id", "entity_id", "node_id", "key"]));
  return toText(value);
}

function normalizeNode(raw: unknown): AtlasGraphNode | null {
  if (!isRecord(raw)) return null;
  const id = toText(getValue(raw, ["id", "entity_id", "node_id", "key"]));
  if (!id) return null;
  const label = toText(getValue(raw, ["label", "name", "title"]), id);
  const type = toText(getValue(raw, ["type", "entity_type", "kind", "category"]), "Unknown");
  return {
    id,
    label,
    name: toText(getValue(raw, ["name", "label", "title"]), label),
    type,
    community: toText(getValue(raw, ["community", "community_id", "communityId"]), "未分配"),
    description: toText(getValue(raw, ["description", "summary", "note"]), "当前节点未提供描述。"),
    evidenceCount: toNumber(getValue(raw, ["evidence_count", "evidenceCount", "claims"])) ?? 0,
    relationCount: toNumber(getValue(raw, ["relation_count", "relationCount", "degree"])) ?? 0,
    reviewStatus: toText(getValue(raw, ["review_status", "reviewStatus", "expert_status"]), "pending"),
    score: toNumber(getValue(raw, ["score", "key_tech_score", "weight"])),
  };
}

function normalizeEdge(raw: unknown, index: number): AtlasGraphEdge | null {
  if (!isRecord(raw)) return null;
  const source = normalizeEndpoint(getValue(raw, ["source", "from", "source_id", "sourceId"]));
  const target = normalizeEndpoint(getValue(raw, ["target", "to", "target_id", "targetId"]));
  if (!source || !target) return null;
  const relationType = toText(getValue(raw, ["relation_type", "relation", "type", "label"]), "RELATED_TO");
  const id = toText(getValue(raw, ["id", "relation_id", "edge_id"]), `${source}-${relationType}-${target}-${index}`);
  return {
    id,
    source,
    target,
    relationType,
    label: toText(getValue(raw, ["label", "relation", "relation_type", "type"]), relationType),
    confidence: toNumber(getValue(raw, ["confidence", "score", "weight", "strength"])),
    evidenceText: toText(getValue(raw, ["evidence_text", "evidenceText", "evidence", "claim_text"])),
    docId: toText(getValue(raw, ["doc_id", "docId", "document_id", "documentId"])),
    chunkId: toText(getValue(raw, ["chunk_id", "chunkId", "chunk"])),
    sourceName: toText(getValue(raw, ["source_name", "sourceName", "document_title", "title"])),
    reviewStatus: toText(getValue(raw, ["review_status", "reviewStatus", "expert_status"]), "pending"),
  };
}

function uniqueSorted(values: string[], preferredOrder: string[]): string[] {
  const unique = [...new Set(values.filter(Boolean))];
  return unique.sort((a, b) => {
    const ai = preferredOrder.indexOf(a);
    const bi = preferredOrder.indexOf(b);
    if (ai !== -1 || bi !== -1) return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    return a.localeCompare(b, "zh-Hans-CN");
  });
}

function readStringArray(raw: unknown, key: string): string[] {
  if (!isRecord(raw)) return [];
  const value = raw[key];
  return Array.isArray(value) ? value.map((item) => toText(item)).filter(Boolean) : [];
}

function readSummary(raw: unknown): AtlasSummary {
  const summary = getRecord(raw, "summary");
  if (!summary) return {};
  return {
    documents: toNumber(summary.documents),
    chunks: toNumber(summary.chunks),
    entities: toNumber(summary.entities),
    claims: toNumber(summary.claims),
    relations: toNumber(summary.relations),
    communities: toNumber(summary.communities),
    extractor: toText(summary.extractor),
  };
}

export function normalizeAtlasData(primary: unknown, fallback?: unknown): NormalizedAtlasGraph {
  const primaryGraph = readGraphArrays(primary);
  const fallbackGraph = readGraphArrays(fallback);
  const rawNodes = primaryGraph.nodes.length ? primaryGraph.nodes : fallbackGraph.nodes;
  const rawEdges = primaryGraph.edges.length ? primaryGraph.edges : fallbackGraph.edges;

  const nodeMap = new Map<string, AtlasGraphNode>();
  rawNodes.forEach((rawNode) => {
    const node = normalizeNode(rawNode);
    if (node) nodeMap.set(node.id, node);
  });

  const edges = rawEdges
    .map((rawEdge, index) => normalizeEdge(rawEdge, index))
    .filter((edge): edge is AtlasGraphEdge => Boolean(edge && nodeMap.has(edge.source) && nodeMap.has(edge.target)));

  const relationTypes = uniqueSorted(
    [...readStringArray(primary, "relationTypes"), ...edges.map((edge) => edge.relationType)],
    RELATION_TYPE_ORDER,
  );
  const entityTypes = uniqueSorted(
    [...readStringArray(primary, "entityTypes"), ...[...nodeMap.values()].map((node) => node.type)],
    ENTITY_TYPE_ORDER,
  );

  return {
    nodes: [...nodeMap.values()],
    edges,
    nodeById: nodeMap,
    relationTypes,
    entityTypes,
    summary: readSummary(primary),
  };
}

export function compactText(value: string, maxLength: number): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, Math.max(0, maxLength - 1))}…`;
}

export function displayValue(value: string | number | undefined, fallback = "未提供"): string {
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : fallback;
  if (typeof value === "string" && value.trim()) return value.trim();
  return fallback;
}
