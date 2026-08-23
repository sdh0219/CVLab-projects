import { AtlasGraphEdge, AtlasGraphNode } from "./atlasData";

export type AdjacencyItem = {
  nodeId: string;
  edge: AtlasGraphEdge;
};

export type GraphPoint = {
  x: number;
  y: number;
  ring: number;
};

export type GraphEdgeEndpoint = {
  source: string;
  target: string;
};

export type AggregatedGraphEdge = GraphEdgeEndpoint & {
  id: string;
  pairKey: string;
  relationTypes: string[];
  primaryRelationType: string;
  rawEdges: AtlasGraphEdge[];
  rawEdgeCount: number;
  confidenceMax?: number;
  confidenceAvg?: number;
  hasEvidence: boolean;
  evidenceCount: number;
  docIds: string[];
  reviewStatuses: string[];
  isBidirectional: boolean;
};

const PREFERRED_LABELS = [
  "地震早期预警",
  "震后建筑损毁识别",
  "遥感震损智能解译",
  "地震应急辅助决策",
  "震后救援调度优化",
  "生命线震损风险传播GNN",
  "地震证据图谱GraphRAG",
  "地震风险时空预测",
  "震后灾情快速评估",
];

const TYPE_PRIORITY = [
  "DisasterType",
  "AITech",
  "Scenario",
  "Task",
  "Dataset",
  "Model",
  "Case",
  "Policy",
  "Limitation",
];

const EXPANSION_RELATION_PRIORITY = [
  "VALIDATED_IN",
  "SOLVES",
  "DEPENDS_ON",
  "USES_MODEL",
  "SERVES_STAGE",
  "APPLIES_TO",
  "LIMITED_BY",
  "REQUIRED_BY",
];

const KEY_NODE_TYPES = new Set(["AITech", "Task", "Dataset", "Model", "Case"]);
const KEY_RELATION_TYPES = new Set(["VALIDATED_IN", "SOLVES", "DEPENDS_ON", "USES_MODEL", "SERVES_STAGE"]);

export const DEFAULT_RELATION_FILTERS = [
  "VALIDATED_IN",
  "SOLVES",
  "DEPENDS_ON",
  "USES_MODEL",
  "SERVES_STAGE",
  "LIMITED_BY",
  "REQUIRED_BY",
];

export function getDefaultRelationTypes(relationTypes: string[]): string[] {
  const defaults = relationTypes.filter((type) => DEFAULT_RELATION_FILTERS.includes(type));
  return defaults.length ? defaults : relationTypes.filter((type) => type !== "APPLIES_TO");
}

export function buildAdjacency(nodes: AtlasGraphNode[], edges: AtlasGraphEdge[]): Map<string, AdjacencyItem[]> {
  const adjacency = new Map<string, AdjacencyItem[]>();
  nodes.forEach((node) => adjacency.set(node.id, []));
  edges.forEach((edge) => {
    adjacency.get(edge.source)?.push({ nodeId: edge.target, edge });
    adjacency.get(edge.target)?.push({ nodeId: edge.source, edge });
  });
  return adjacency;
}

export function getNodeDegree(nodeId: string, adjacency: Map<string, AdjacencyItem[]>): number {
  return adjacency.get(nodeId)?.length ?? 0;
}

function typeRank(type: string): number {
  const index = TYPE_PRIORITY.indexOf(type);
  return index === -1 ? 99 : index;
}

function relationRank(type: string): number {
  const index = EXPANSION_RELATION_PRIORITY.indexOf(type);
  return index === -1 ? 99 : index;
}

function uniqueSortedByPriority(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))].sort((a, b) => {
    const ar = relationRank(a);
    const br = relationRank(b);
    if (ar !== br) return ar - br;
    return a.localeCompare(b, "zh-Hans-CN");
  });
}

export function aggregateEdges(edges: AtlasGraphEdge[]): AggregatedGraphEdge[] {
  const groups = new Map<string, AtlasGraphEdge[]>();

  edges.forEach((edge) => {
    const pairKey = [edge.source, edge.target].sort().join("__");
    const group = groups.get(pairKey) ?? [];
    group.push(edge);
    groups.set(pairKey, group);
  });

  return [...groups.entries()].map(([pairKey, rawEdges]) => {
    const first = rawEdges[0];
    const relationTypes = uniqueSortedByPriority(rawEdges.map((edge) => edge.relationType));
    const confidences = rawEdges
      .map((edge) => edge.confidence)
      .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
    const confidenceMax = confidences.length ? Math.max(...confidences) : undefined;
    const confidenceAvg = confidences.length
      ? confidences.reduce((sum, value) => sum + value, 0) / confidences.length
      : undefined;
    const evidenceEdges = rawEdges.filter((edge) => edge.evidenceText || edge.docId);
    const directions = new Set(rawEdges.map((edge) => `${edge.source}->${edge.target}`));

    return {
      id: `agg-${pairKey}`,
      source: first.source,
      target: first.target,
      pairKey,
      relationTypes,
      primaryRelationType: relationTypes[0] ?? "RELATED_TO",
      rawEdges,
      rawEdgeCount: rawEdges.length,
      confidenceMax,
      confidenceAvg,
      hasEvidence: evidenceEdges.length > 0,
      evidenceCount: evidenceEdges.length,
      docIds: [...new Set(rawEdges.map((edge) => edge.docId).filter(Boolean))],
      reviewStatuses: [...new Set(rawEdges.map((edge) => edge.reviewStatus).filter(Boolean))],
      isBidirectional: directions.size > 1,
    };
  });
}

export function isKeyAggregatedEdge(
  edge: AggregatedGraphEdge,
  selectedNodeId: string | null,
  selectedEdgeId: string | null,
  nodeById: Map<string, AtlasGraphNode>,
): boolean {
  if (edge.id === selectedEdgeId) return true;
  if (selectedNodeId && (edge.source === selectedNodeId || edge.target === selectedNodeId) && KEY_RELATION_TYPES.has(edge.primaryRelationType)) return true;
  if (edge.primaryRelationType !== "APPLIES_TO" && KEY_RELATION_TYPES.has(edge.primaryRelationType)) return true;
  if (edge.evidenceCount > 0 && (edge.confidenceMax ?? 0) >= 0.72) return true;
  const sourceType = nodeById.get(edge.source)?.type ?? "";
  const targetType = nodeById.get(edge.target)?.type ?? "";
  return KEY_NODE_TYPES.has(sourceType) && KEY_NODE_TYPES.has(targetType);
}

export function rankAdjacencyItems(
  items: AdjacencyItem[],
  nodeById: Map<string, AtlasGraphNode>,
): AdjacencyItem[] {
  return [...items].sort((a, b) => {
    const aEvidence = a.edge.evidenceText ? 1 : 0;
    const bEvidence = b.edge.evidenceText ? 1 : 0;
    if (aEvidence !== bEvidence) return bEvidence - aEvidence;

    const aConfidence = a.edge.confidence ?? 0;
    const bConfidence = b.edge.confidence ?? 0;
    if (aConfidence !== bConfidence) return bConfidence - aConfidence;

    const aRelation = relationRank(a.edge.relationType);
    const bRelation = relationRank(b.edge.relationType);
    if (aRelation !== bRelation) return aRelation - bRelation;

    const aType = nodeById.get(a.nodeId)?.type ?? "";
    const bType = nodeById.get(b.nodeId)?.type ?? "";
    if (typeRank(aType) !== typeRank(bType)) return typeRank(aType) - typeRank(bType);

    return (nodeById.get(a.nodeId)?.label ?? a.nodeId).localeCompare(
      nodeById.get(b.nodeId)?.label ?? b.nodeId,
      "zh-Hans-CN",
    );
  });
}

export function getDefaultSelectedNodeId(nodes: AtlasGraphNode[], edges: AtlasGraphEdge[]): string | null {
  const adjacency = buildAdjacency(nodes, edges);
  const byLabel = new Map(nodes.map((node) => [node.label, node]));

  for (const label of PREFERRED_LABELS) {
    const exact = byLabel.get(label);
    if (exact?.type === "AITech") return exact.id;
  }

  const rankedTech = [...nodes]
    .filter((node) => node.type === "AITech")
    .sort((a, b) => getNodeDegree(b.id, adjacency) - getNodeDegree(a.id, adjacency));
  return rankedTech[0]?.id ?? nodes[0]?.id ?? null;
}

export function getInitialNodeIds(nodes: AtlasGraphNode[], edges: AtlasGraphEdge[]): Set<string> {
  const adjacency = buildAdjacency(nodes, edges);
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const byLabel = new Map(nodes.map((node) => [node.label, node]));
  const selected = new Set<string>();

  for (const label of PREFERRED_LABELS) {
    const exact = byLabel.get(label);
    if (exact?.type === "AITech" && selected.size < 7) selected.add(exact.id);
  }

  const rankedTech = [...nodes]
    .filter((node) => node.type === "AITech")
    .sort((a, b) => getNodeDegree(b.id, adjacency) - getNodeDegree(a.id, adjacency));

  for (const node of rankedTech) {
    if (selected.size >= 7) break;
    selected.add(node.id);
  }

  const focusId = getDefaultSelectedNodeId(nodes, edges);
  if (focusId) selected.add(focusId);

  const supportingTypes = new Set(["Task", "Dataset", "Model", "Case"]);
  const supportingNeighbors = [...selected]
    .flatMap((nodeId) => adjacency.get(nodeId) ?? [])
    .filter((item) => supportingTypes.has(nodeById.get(item.nodeId)?.type ?? ""))
    .filter((item) => item.edge.relationType !== "APPLIES_TO");

  rankAdjacencyItems(supportingNeighbors, nodeById)
    .slice(0, 8)
    .forEach((item) => selected.add(item.nodeId));

  if (!selected.size) {
    [...nodes]
      .sort((a, b) => getNodeDegree(b.id, adjacency) - getNodeDegree(a.id, adjacency))
      .slice(0, 8)
      .forEach((node) => selected.add(node.id));
  }

  return selected;
}

export function expandNodeIds(
  nodeId: string,
  visibleNodeIds: Set<string>,
  adjacency: Map<string, AdjacencyItem[]>,
  nodeById: Map<string, AtlasGraphNode>,
  depth: 1 | 2 = 1,
  limitPerNode = 8,
  maxAdded = depth === 2 ? 20 : 8,
): Set<string> {
  const next = new Set(visibleNodeIds);
  let added = 0;
  let frontier = [nodeId];
  next.add(nodeId);

  for (let layer = 0; layer < depth; layer += 1) {
    const nextFrontier: string[] = [];
    for (const current of frontier) {
      const ranked = rankAdjacencyItems(adjacency.get(current) ?? [], nodeById).slice(0, limitPerNode);
      for (const item of ranked) {
        if (!next.has(item.nodeId)) {
          next.add(item.nodeId);
          nextFrontier.push(item.nodeId);
          added += 1;
          if (added >= maxAdded) return next;
        }
      }
    }
    frontier = nextFrontier;
    if (!frontier.length) break;
  }

  return next;
}

export function collapseToNodeIds(
  nodeId: string,
  adjacency: Map<string, AdjacencyItem[]>,
  nodeById: Map<string, AtlasGraphNode>,
): Set<string> {
  return expandNodeIds(nodeId, new Set([nodeId]), adjacency, nodeById, 1, 8, 8);
}

export function getRelationTypesForNode(nodeId: string, adjacency: Map<string, AdjacencyItem[]>): string[] {
  return [...new Set((adjacency.get(nodeId) ?? []).map((item) => item.edge.relationType))].sort((a, b) => relationRank(a) - relationRank(b));
}

export function getFilteredVisibleEdges(
  edges: AtlasGraphEdge[],
  visibleNodeIds: Set<string>,
  nodeById: Map<string, AtlasGraphNode>,
  relationFilters: Set<string>,
  typeFilters: Set<string>,
  evidenceOnly: boolean,
): AtlasGraphEdge[] {
  if (!relationFilters.size || !typeFilters.size) return [];
  return edges.filter((edge) => {
    if (!visibleNodeIds.has(edge.source) || !visibleNodeIds.has(edge.target)) return false;
    if (!relationFilters.has(edge.relationType)) return false;
    const sourceType = nodeById.get(edge.source)?.type ?? "Unknown";
    const targetType = nodeById.get(edge.target)?.type ?? "Unknown";
    if (!typeFilters.has(sourceType) || !typeFilters.has(targetType)) return false;
    if (evidenceOnly && !edge.evidenceText && !edge.docId) return false;
    return true;
  });
}

export function computeGraphLayout(
  nodes: AtlasGraphNode[],
  edges: GraphEdgeEndpoint[],
  selectedNodeId: string | null,
): Map<string, GraphPoint> {
  const points = new Map<string, GraphPoint>();
  if (!nodes.length) return points;

  const centerX = 550;
  const centerY = 360;
  const selected = selectedNodeId && nodes.some((node) => node.id === selectedNodeId) ? selectedNodeId : nodes[0].id;
  const visibleIds = new Set(nodes.map((node) => node.id));
  const layoutAdjacency = new Map<string, Set<string>>();
  nodes.forEach((node) => layoutAdjacency.set(node.id, new Set()));
  edges
    .filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target))
    .forEach((edge) => {
      layoutAdjacency.get(edge.source)?.add(edge.target);
      layoutAdjacency.get(edge.target)?.add(edge.source);
    });
  const distance = new Map<string, number>([[selected, 0]]);
  const queue = [selected];

  while (queue.length) {
    const current = queue.shift();
    if (!current) break;
    const currentDistance = distance.get(current) ?? 0;
    for (const neighborId of layoutAdjacency.get(current) ?? []) {
      if (!distance.has(neighborId)) {
        distance.set(neighborId, currentDistance + 1);
        queue.push(neighborId);
      }
    }
  }

  const rings = new Map<number, AtlasGraphNode[]>();
  nodes.forEach((node) => {
    const ring = node.id === selected ? 0 : Math.min(distance.get(node.id) ?? 3, 3);
    const list = rings.get(ring) ?? [];
    list.push(node);
    rings.set(ring, list);
  });

  points.set(selected, { x: centerX, y: centerY, ring: 0 });

  const typeAngles: Record<string, number> = {
    Model: -Math.PI / 2,
    Dataset: (Math.PI * 3) / 4,
    Task: 0,
    Case: Math.PI,
    Limitation: Math.PI / 2,
    Policy: Math.PI / 4,
    DisasterType: Math.PI / 2,
    Scenario: -Math.PI / 5,
  };

  for (const [ring, ringNodes] of [...rings.entries()].sort(([a], [b]) => a - b)) {
    if (ring === 0) continue;
    const count = ringNodes.length;
    const radiusX = Math.min(535, 260 + ring * 132 + Math.max(0, count - 10) * 4.4);
    const radiusY = Math.min(330, 165 + ring * 88 + Math.max(0, count - 10) * 2.4);
    const grouped = new Map<string, AtlasGraphNode[]>();
    ringNodes
      .sort((a, b) => typeRank(a.type) - typeRank(b.type) || a.label.localeCompare(b.label, "zh-Hans-CN"))
      .forEach((node) => {
        const list = grouped.get(node.type) ?? [];
        list.push(node);
        grouped.set(node.type, list);
      });

    if ([...grouped.keys()].length === 1 && grouped.has("AITech")) {
      ringNodes.forEach((node, index) => {
        const angle = -Math.PI / 2 + (Math.PI * 2 * index) / Math.max(1, count);
        points.set(node.id, {
          x: centerX + Math.cos(angle) * radiusX,
          y: centerY + Math.sin(angle) * radiusY,
          ring,
        });
      });
      continue;
    }

    for (const [type, typedNodes] of grouped.entries()) {
      const baseAngle = type === "AITech" ? -Math.PI / 2 : typeAngles[type] ?? ((typeRank(type) / 9) * Math.PI * 2 - Math.PI / 2);
      const spread = type === "AITech" ? Math.PI * 1.4 : Math.min(0.86, 0.22 * Math.max(1, typedNodes.length - 1));
      typedNodes.forEach((node, index) => {
        const offset = typedNodes.length === 1 ? 0 : -spread / 2 + (spread * index) / (typedNodes.length - 1);
        const angle = baseAngle + offset + ring * 0.08;
        points.set(node.id, {
          x: centerX + Math.cos(angle) * radiusX,
          y: centerY + Math.sin(angle) * radiusY,
          ring,
        });
      });
    }
  }

  return points;
}
