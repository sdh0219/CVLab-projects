import { AtlasGraphEdge, AtlasGraphNode } from "./atlasData";

export type AdjacencyItem = {
  nodeId: string;
  edge: AtlasGraphEdge;
};

export type GraphPoint = {
  x: number;
  y: number;
  ring: number;
  clusterId?: string;
};

export type GraphViewState = {
  enabled: boolean;
  rotationX: number;
  rotationY: number;
  perspective: number;
  scale: number;
  centerX: number;
  centerY: number;
};

export type ProjectableGraphPoint = {
  x: number;
  y: number;
  z?: number;
};

export type ProjectedGraphPoint = GraphPoint & {
  rawX: number;
  rawY: number;
  z: number;
  screenX: number;
  screenY: number;
  screenScale: number;
  depth: number;
  opacity: number;
  labelOpacity: number;
  shadowOpacity: number;
};

export type GraphEdgeEndpoint = {
  source: string;
  target: string;
};

export type GraphLayoutMode = "core" | "expanded" | "full" | "screenshot";

export type GraphLayoutOptions = {
  canvasWidth?: number;
  canvasHeight?: number;
  selectedNodeId?: string | null;
  oneHopNodeIds?: Set<string>;
  twoHopNodeIds?: Set<string>;
  mode?: GraphLayoutMode;
};

export type GraphClusterRegion = {
  id: string;
  label: string;
  types: string[];
  centerX: number;
  centerY: number;
  radiusX: number;
  radiusY: number;
  titleOffsetX?: number;
  titleOffsetY?: number;
  tint?: string;
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
  "分布式AI地震预警",
  "数字孪生城市地震风险模拟",
];

const TYPE_PRIORITY = [
  "DisasterType",
  "AITech",
  "Scenario",
  "Task",
  "Dataset",
  "Model",
  "Case",
  "Event",
  "Policy",
  "Standard",
  "Organization",
  "Metric",
  "ImpactProduct",
  "Limitation",
  "Document",
  "Evidence",
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
  "HAS_METRIC",
  "HAS_IMPACT",
  "HAS_PARAMETER",
  "EVALUATED_BY",
  "PUBLISHED_BY",
  "MEASURED_BY",
  "DERIVES_FROM",
  "SUPPORTED_BY",
];

const KEY_NODE_TYPES = new Set(["AITech", "Task", "Dataset", "Model", "Case", "Event", "ImpactProduct"]);
const KEY_RELATION_TYPES = new Set(["VALIDATED_IN", "SOLVES", "DEPENDS_ON", "USES_MODEL", "SERVES_STAGE", "HAS_METRIC", "HAS_IMPACT", "HAS_PARAMETER"]);

const SEMANTIC_Z_BY_TYPE: Record<string, number> = {
  Evidence: -180,
  Document: -180,
  Policy: -120,
  Standard: -120,
  Limitation: -80,
  Case: -40,
  Event: -40,
  Dataset: 0,
  ImpactProduct: 20,
  Metric: 20,
  Model: 60,
  Task: 80,
  Scenario: 80,
  AITech: 120,
};

function degreesToRadians(value: number): number {
  return (value * Math.PI) / 180;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function zDepthForType(type: string | undefined): number {
  return SEMANTIC_Z_BY_TYPE[type ?? ""] ?? 0;
}

export function project3DNode(point: ProjectableGraphPoint, viewState: GraphViewState): ProjectedGraphPoint {
  const sourceX = Number.isFinite(point.x) ? point.x : viewState.centerX;
  const sourceY = Number.isFinite(point.y) ? point.y : viewState.centerY;
  const sourceZ = Number.isFinite(point.z) ? point.z ?? 0 : 0;
  const safePerspective = clamp(Number.isFinite(viewState.perspective) ? viewState.perspective : 1000, 900, 1200);
  const safeScale = clamp(Number.isFinite(viewState.scale) ? viewState.scale : 1, 0.7, 1.35);

  if (!viewState.enabled) {
    return {
      x: sourceX,
      y: sourceY,
      ring: 0,
      rawX: sourceX,
      rawY: sourceY,
      z: sourceZ,
      screenX: sourceX,
      screenY: sourceY,
      screenScale: safeScale,
      depth: sourceZ,
      opacity: 1,
      labelOpacity: 1,
      shadowOpacity: 0.18,
    };
  }

  const rotationX = degreesToRadians(clamp(viewState.rotationX, -45, 45));
  const rotationY = degreesToRadians(clamp(viewState.rotationY, -60, 60));
  const centeredX = (sourceX - viewState.centerX) * safeScale;
  const centeredY = (sourceY - viewState.centerY) * safeScale;
  const centeredZ = sourceZ * safeScale;

  const yRotatedX = centeredX * Math.cos(rotationY) + centeredZ * Math.sin(rotationY);
  const yRotatedZ = -centeredX * Math.sin(rotationY) + centeredZ * Math.cos(rotationY);

  const xRotatedY = centeredY * Math.cos(rotationX) - yRotatedZ * Math.sin(rotationX);
  const xRotatedZ = centeredY * Math.sin(rotationX) + yRotatedZ * Math.cos(rotationX);

  const projectedScale = clamp(safePerspective / Math.max(120, safePerspective - xRotatedZ), 0.7, 1.38);
  const normalizedDepth = clamp((xRotatedZ + 280) / 560, 0, 1);
  const screenX = viewState.centerX + yRotatedX * projectedScale;
  const screenY = viewState.centerY + xRotatedY * projectedScale;

  return {
    x: screenX,
    y: screenY,
    ring: 0,
    rawX: sourceX,
    rawY: sourceY,
    z: sourceZ,
    screenX,
    screenY,
    screenScale: projectedScale,
    depth: xRotatedZ,
    opacity: clamp(0.25 + normalizedDepth * 0.75, 0.25, 1),
    labelOpacity: clamp(0.18 + normalizedDepth * 0.75, 0.18, 1),
    shadowOpacity: clamp(0.05 + normalizedDepth * 0.35, 0.05, 0.4),
  };
}

export const GRAPH_CLUSTER_REGIONS: GraphClusterRegion[] = [
  { id: "case", label: "真实案例", types: ["Case", "Event"], centerX: 0.18, centerY: 0.22, radiusX: 0.16, radiusY: 0.13, titleOffsetX: -0.12, titleOffsetY: -0.13, tint: "#f5f3ff" },
  { id: "dataset", label: "数据条件", types: ["Dataset", "Metric", "ImpactProduct"], centerX: 0.19, centerY: 0.58, radiusX: 0.17, radiusY: 0.17, titleOffsetX: -0.14, titleOffsetY: -0.17, tint: "#e0f2fe" },
  { id: "model", label: "模型方法", types: ["Model"], centerX: 0.46, centerY: 0.20, radiusX: 0.18, radiusY: 0.14, titleOffsetX: -0.14, titleOffsetY: -0.13, tint: "#eff6ff" },
  { id: "aitech", label: "AI 技术", types: ["AITech"], centerX: 0.44, centerY: 0.48, radiusX: 0.25, radiusY: 0.21, titleOffsetX: -0.20, titleOffsetY: -0.22, tint: "#dbeafe" },
  { id: "task-scenario", label: "任务场景", types: ["Task", "Scenario"], centerX: 0.73, centerY: 0.43, radiusX: 0.22, radiusY: 0.22, titleOffsetX: 0.04, titleOffsetY: -0.23, tint: "#e0f2fe" },
  { id: "policy", label: "政策标准", types: ["Policy", "Standard", "Organization"], centerX: 0.80, centerY: 0.18, radiusX: 0.15, radiusY: 0.11, titleOffsetX: -0.08, titleOffsetY: -0.12, tint: "#f1f5f9" },
  { id: "limitation", label: "技术限制", types: ["Limitation"], centerX: 0.51, centerY: 0.78, radiusX: 0.20, radiusY: 0.12, titleOffsetX: -0.16, titleOffsetY: -0.12, tint: "#fee2e2" },
  { id: "disaster", label: "灾害背景", types: ["DisasterType"], centerX: 0.08, centerY: 0.12, radiusX: 0.08, radiusY: 0.07, titleOffsetX: -0.04, titleOffsetY: -0.08, tint: "#f8fafc" },
  { id: "evidence", label: "证据来源", types: ["Document", "Evidence"], centerX: 0.82, centerY: 0.72, radiusX: 0.14, radiusY: 0.13, titleOffsetX: -0.10, titleOffsetY: -0.14, tint: "#f8fafc" },
];

const TYPE_LAYOUT_AREAS: Record<string, { clusterId: string; centerX: number; centerY: number; radiusX: number; radiusY: number }> = {
  AITech: { clusterId: "aitech", centerX: 0.44, centerY: 0.48, radiusX: 0.25, radiusY: 0.21 },
  Model: { clusterId: "model", centerX: 0.46, centerY: 0.20, radiusX: 0.18, radiusY: 0.14 },
  Dataset: { clusterId: "dataset", centerX: 0.19, centerY: 0.58, radiusX: 0.17, radiusY: 0.17 },
  Metric: { clusterId: "dataset", centerX: 0.24, centerY: 0.68, radiusX: 0.12, radiusY: 0.10 },
  ImpactProduct: { clusterId: "dataset", centerX: 0.13, centerY: 0.70, radiusX: 0.12, radiusY: 0.10 },
  Task: { clusterId: "task-scenario", centerX: 0.72, centerY: 0.47, radiusX: 0.18, radiusY: 0.16 },
  Scenario: { clusterId: "task-scenario", centerX: 0.78, centerY: 0.31, radiusX: 0.14, radiusY: 0.12 },
  Case: { clusterId: "case", centerX: 0.18, centerY: 0.22, radiusX: 0.16, radiusY: 0.13 },
  Event: { clusterId: "case", centerX: 0.25, centerY: 0.28, radiusX: 0.12, radiusY: 0.10 },
  Policy: { clusterId: "policy", centerX: 0.80, centerY: 0.18, radiusX: 0.15, radiusY: 0.11 },
  Standard: { clusterId: "policy", centerX: 0.88, centerY: 0.25, radiusX: 0.11, radiusY: 0.09 },
  Organization: { clusterId: "policy", centerX: 0.72, centerY: 0.14, radiusX: 0.11, radiusY: 0.08 },
  Limitation: { clusterId: "limitation", centerX: 0.51, centerY: 0.78, radiusX: 0.20, radiusY: 0.12 },
  DisasterType: { clusterId: "disaster", centerX: 0.08, centerY: 0.12, radiusX: 0.08, radiusY: 0.07 },
  Document: { clusterId: "evidence", centerX: 0.82, centerY: 0.72, radiusX: 0.14, radiusY: 0.13 },
  Evidence: { clusterId: "evidence", centerX: 0.88, centerY: 0.80, radiusX: 0.10, radiusY: 0.08 },
  Unknown: { clusterId: "aitech", centerX: 0.50, centerY: 0.50, radiusX: 0.12, radiusY: 0.10 },
};

const INITIAL_SUPPORT_LIMITS: Record<string, number> = {
  Model: 3,
  Dataset: 3,
  Task: 4,
  Scenario: 2,
  Case: 3,
  Event: 2,
  ImpactProduct: 2,
  Metric: 2,
  Limitation: 2,
  Policy: 2,
  Standard: 2,
};

export const DEFAULT_RELATION_FILTERS = [
  "VALIDATED_IN",
  "SOLVES",
  "DEPENDS_ON",
  "USES_MODEL",
  "SERVES_STAGE",
  "LIMITED_BY",
  "REQUIRED_BY",
  "HAS_METRIC",
  "HAS_IMPACT",
  "HAS_PARAMETER",
  "EVALUATED_BY",
  "PUBLISHED_BY",
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

function defaultFocusCandidate(node: AtlasGraphNode): boolean {
  return node.type === "AITech" && node.relationCount > 0 && !/GraphRAG/i.test(node.label);
}

function nodeImportance(node: AtlasGraphNode, adjacency: Map<string, AdjacencyItem[]>): number {
  return getNodeDegree(node.id, adjacency) * 6 + node.evidenceCount * 3 + node.relationCount + (node.score ?? 0);
}

function compareNodesByImportance(
  adjacency: Map<string, AdjacencyItem[]>,
  selectedNodeId: string | null | undefined,
): (a: AtlasGraphNode, b: AtlasGraphNode) => number {
  return (a, b) => {
    const aGraphRag = /GraphRAG/i.test(a.label);
    const bGraphRag = /GraphRAG/i.test(b.label);
    if (a.id === selectedNodeId && b.id !== selectedNodeId && !aGraphRag) return -1;
    if (b.id === selectedNodeId && a.id !== selectedNodeId && !bGraphRag) return 1;
    const ai = nodeImportance(a, adjacency) - (aGraphRag ? 10000 : 0);
    const bi = nodeImportance(b, adjacency) - (bGraphRag ? 10000 : 0);
    if (ai !== bi) return bi - ai;
    if (typeRank(a.type) !== typeRank(b.type)) return typeRank(a.type) - typeRank(b.type);
    return a.label.localeCompare(b.label, "zh-Hans-CN");
  };
}

export function getClusterRegionForType(type: string | undefined): GraphClusterRegion | undefined {
  return GRAPH_CLUSTER_REGIONS.find((region) => region.types.includes(type ?? ""));
}

export function clusterLabelForType(type: string | undefined): string {
  return getClusterRegionForType(type)?.label ?? "其他分区";
}

export function getClusterRegionRect(
  region: GraphClusterRegion,
  canvasWidth: number,
  canvasHeight: number,
): { x: number; y: number; width: number; height: number } {
  const cx = region.centerX * canvasWidth;
  const cy = region.centerY * canvasHeight;
  const rx = region.radiusX * canvasWidth;
  const ry = region.radiusY * canvasHeight;
  return {
    x: cx - rx,
    y: cy - ry,
    width: rx * 2,
    height: ry * 2,
  };
}

export function getClusterAura(
  region: GraphClusterRegion,
  canvasWidth: number,
  canvasHeight: number,
): { cx: number; cy: number; rx: number; ry: number; titleX: number; titleY: number; tint: string } {
  const cx = region.centerX * canvasWidth;
  const cy = region.centerY * canvasHeight;
  const rx = region.radiusX * canvasWidth;
  const ry = region.radiusY * canvasHeight;
  return {
    cx,
    cy,
    rx,
    ry,
    titleX: cx + (region.titleOffsetX ?? -region.radiusX * 0.72) * canvasWidth,
    titleY: cy + (region.titleOffsetY ?? -region.radiusY * 0.72) * canvasHeight,
    tint: region.tint ?? "#eff6ff",
  };
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
    if (exact && defaultFocusCandidate(exact)) return exact.id;
  }

  const rankedTech = [...nodes]
    .filter(defaultFocusCandidate)
    .sort(compareNodesByImportance(adjacency, null));
  return rankedTech[0]?.id ?? nodes[0]?.id ?? null;
}

export function getInitialNodeIds(nodes: AtlasGraphNode[], edges: AtlasGraphEdge[]): Set<string> {
  const adjacency = buildAdjacency(nodes, edges);
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const byLabel = new Map(nodes.map((node) => [node.label, node]));
  const selected = new Set<string>();

  for (const label of PREFERRED_LABELS) {
    const exact = byLabel.get(label);
    if (exact && defaultFocusCandidate(exact) && selected.size < 9) selected.add(exact.id);
  }

  const rankedTech = [...nodes]
    .filter(defaultFocusCandidate)
    .sort(compareNodesByImportance(adjacency, null));

  for (const node of rankedTech) {
    if (selected.size >= 9) break;
    selected.add(node.id);
  }

  const focusId = getDefaultSelectedNodeId(nodes, edges);
  if (focusId) selected.add(focusId);

  const selectedTechIds = [...selected].filter((nodeId) => nodeById.get(nodeId)?.type === "AITech");
  const supportCounts = new Map<string, number>();
  const supportingNeighbors = selectedTechIds
    .flatMap((nodeId) => adjacency.get(nodeId) ?? [])
    .filter((item) => Object.hasOwn(INITIAL_SUPPORT_LIMITS, nodeById.get(item.nodeId)?.type ?? ""))
    .filter((item) => item.edge.relationType !== "APPLIES_TO");

  for (const item of rankAdjacencyItems(supportingNeighbors, nodeById)) {
    const node = nodeById.get(item.nodeId);
    if (!node) continue;
    const limit = INITIAL_SUPPORT_LIMITS[node.type] ?? 0;
    const current = supportCounts.get(node.type) ?? 0;
    if (current >= limit) continue;
    selected.add(node.id);
    supportCounts.set(node.type, current + 1);
  }

  for (const [type, limit] of Object.entries(INITIAL_SUPPORT_LIMITS)) {
    const current = supportCounts.get(type) ?? 0;
    if (current >= limit) continue;
    const fillNodes = nodes
      .filter((node) => node.type === type)
      .sort(compareNodesByImportance(adjacency, null))
      .slice(0, limit - current);
    fillNodes.forEach((node) => selected.add(node.id));
  }

  if (!selected.size) {
    [...nodes]
      .filter((node) => node.type !== "DisasterType")
      .sort(compareNodesByImportance(adjacency, null))
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

function layoutAreaForType(type: string, canvasWidth: number, canvasHeight: number, mode: GraphLayoutMode) {
  const area = TYPE_LAYOUT_AREAS[type] ?? TYPE_LAYOUT_AREAS.Unknown;
  const expansion = mode === "full" ? 1.2 : mode === "expanded" ? 1.12 : 1;
  return {
    clusterId: area.clusterId,
    cx: area.centerX * canvasWidth,
    cy: area.centerY * canvasHeight,
    rx: area.radiusX * canvasWidth * expansion,
    ry: area.radiusY * canvasHeight * expansion,
  };
}

function buildLooseClusterSlots(
  count: number,
  radiusX: number,
  radiusY: number,
  type: string,
): Array<{ x: number; y: number }> {
  if (count <= 0) return [];
  const spacingScale = type === "AITech" ? 1.3 : ["Task", "Scenario"].includes(type) ? 1.18 : 1.08;
  const usableWidth = radiusX * 2 * spacingScale;
  const usableHeight = radiusY * 2 * spacingScale;
  const aspect = Math.max(0.75, usableWidth / Math.max(usableHeight, 1));
  const columns = Math.max(1, Math.ceil(Math.sqrt(count * aspect)));
  const rows = Math.max(1, Math.ceil(count / columns));
  const cellWidth = usableWidth / (columns + 0.9);
  const cellHeight = usableHeight / (rows + 0.95);
  const typeOffset = typeRank(type) * 17;
  const slots: Array<{ x: number; y: number; distance: number }> = [];

  for (let row = 0; row < rows; row += 1) {
    for (let column = 0; column < columns; column += 1) {
      const stagger = rows > 1 && row % 2 === 1 ? cellWidth * 0.22 : 0;
      const jitterX = Math.sin((row + 1) * 12.9898 + (column + 1) * 78.233 + typeOffset) * 9;
      const jitterY = Math.cos((row + 1) * 39.3467 + (column + 1) * 11.135 + typeOffset) * 8;
      let x = -usableWidth / 2 + cellWidth * (column + 0.75) + stagger + jitterX;
      let y = -usableHeight / 2 + cellHeight * (row + 0.8) + jitterY;
      const normalized = Math.sqrt((x * x) / Math.max(radiusX * radiusX, 1) + (y * y) / Math.max(radiusY * radiusY, 1));
      if (normalized > 0.98) {
        x /= normalized / 0.98;
        y /= normalized / 0.98;
      }
      const distance = Math.hypot(x, y);
      slots.push({ x, y, distance });
    }
  }

  return slots
    .sort((a, b) => a.distance - b.distance || a.y - b.y || a.x - b.x)
    .slice(0, count)
    .map(({ x, y }) => ({ x, y }));
}

function avoidCanvasCenter(x: number, y: number, canvasWidth: number, canvasHeight: number): { x: number; y: number } {
  const centerX = canvasWidth / 2;
  const centerY = canvasHeight * 0.4875;
  const dx = x - centerX;
  const dy = y - centerY;
  const distance = Math.hypot(dx, dy);
  const minDistance = 108;
  if (distance >= minDistance) return { x, y };
  const unitX = distance > 1 ? dx / distance : -0.86;
  const unitY = distance > 1 ? dy / distance : -0.5;
  return {
    x: centerX + unitX * minDistance,
    y: centerY + unitY * minDistance,
  };
}

function interpolatePoint(
  point: { x: number; y: number },
  target: { x: number; y: number },
  amount: number,
): { x: number; y: number } {
  return {
    x: point.x + (target.x - point.x) * amount,
    y: point.y + (target.y - point.y) * amount,
  };
}

export function computeSoftClusterLayout(
  nodes: AtlasGraphNode[],
  edges: GraphEdgeEndpoint[],
  options: GraphLayoutOptions = {},
): Map<string, GraphPoint> {
  const points = new Map<string, GraphPoint>();
  if (!nodes.length) return points;

  const canvasWidth = options.canvasWidth ?? 1160;
  const canvasHeight = options.canvasHeight ?? 800;
  const mode = options.mode ?? "core";
  const visibleIds = new Set(nodes.map((node) => node.id));
  const layoutAdjacency = new Map<string, Set<string>>();
  nodes.forEach((node) => layoutAdjacency.set(node.id, new Set()));
  edges
    .filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target))
    .forEach((edge) => {
      layoutAdjacency.get(edge.source)?.add(edge.target);
      layoutAdjacency.get(edge.target)?.add(edge.source);
    });

  const adjacencyForRank = new Map<string, AdjacencyItem[]>();
  nodes.forEach((node) => {
    adjacencyForRank.set(
      node.id,
      [...(layoutAdjacency.get(node.id) ?? [])].map((neighborId) => ({
        nodeId: neighborId,
        edge: {
          id: `${node.id}-${neighborId}`,
          source: node.id,
          target: neighborId,
          relationType: "RELATED_TO",
          label: "RELATED_TO",
          evidenceText: "",
          docId: "",
          chunkId: "",
          sourceName: "",
          reviewStatus: "",
        },
      })),
    );
  });

  const grouped = new Map<string, AtlasGraphNode[]>();
  nodes.forEach((node) => {
    const list = grouped.get(node.type) ?? [];
    list.push(node);
    grouped.set(node.type, list);
  });

  for (const [type, typedNodes] of [...grouped.entries()].sort(([a], [b]) => typeRank(a) - typeRank(b))) {
    const area = layoutAreaForType(type, canvasWidth, canvasHeight, mode);
    const slots = buildLooseClusterSlots(typedNodes.length, area.rx, area.ry, type);
    const sortedNodes = [...typedNodes].sort(compareNodesByImportance(adjacencyForRank, options.selectedNodeId));

    sortedNodes.forEach((node, index) => {
      const slot = slots[index] ?? { x: 0, y: 0 };
      const candidate = avoidCanvasCenter(area.cx + slot.x, area.cy + slot.y, canvasWidth, canvasHeight);
      points.set(node.id, {
        x: clamp(candidate.x, 36, canvasWidth - 36),
        y: clamp(candidate.y, 42, canvasHeight - 54),
        ring: typeRank(node.type),
        clusterId: area.clusterId,
      });
    });
  }

  const selectedPoint = options.selectedNodeId ? points.get(options.selectedNodeId) : undefined;
  if (selectedPoint) {
    nodes.forEach((node) => {
      if (node.id === options.selectedNodeId) return;
      const point = points.get(node.id);
      if (!point) return;
      const attraction = options.oneHopNodeIds?.has(node.id)
        ? 0.25
        : options.twoHopNodeIds?.has(node.id)
          ? 0.12
          : 0;
      if (!attraction) return;
      const next = interpolatePoint(point, selectedPoint, attraction);
      points.set(node.id, {
        ...point,
        x: clamp(next.x, 36, canvasWidth - 36),
        y: clamp(next.y, 42, canvasHeight - 54),
      });
    });
  }

  return points;
}

export function computeClusterLayout(
  nodes: AtlasGraphNode[],
  edges: GraphEdgeEndpoint[],
  options: GraphLayoutOptions = {},
): Map<string, GraphPoint> {
  return computeSoftClusterLayout(nodes, edges, options);
}

export function computeGraphLayout(
  nodes: AtlasGraphNode[],
  edges: GraphEdgeEndpoint[],
  selectedNodeId: string | null,
): Map<string, GraphPoint> {
  return computeSoftClusterLayout(nodes, edges, { selectedNodeId });
}
