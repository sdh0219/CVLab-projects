"use client";

import { useEffect, useMemo, useRef, useState, type MouseEvent, type WheelEvent } from "react";
import {
  AtlasGraphEdge,
  AtlasGraphNode,
  NormalizedAtlasGraph,
  compactText,
  displayValue,
  normalizeAtlasData,
} from "../lib/atlasData";
import {
  AdjacencyItem,
  AggregatedGraphEdge,
  GRAPH_CLUSTER_REGIONS,
  ProjectedGraphPoint,
  aggregateEdges,
  buildAdjacency,
  clusterLabelForType,
  computeSoftClusterLayout,
  getClusterAura,
  getDefaultRelationTypes,
  getDefaultSelectedNodeId,
  getFilteredVisibleEdges,
  getInitialNodeIds,
  getNodeDegree,
  project3DNode,
  rankAdjacencyItems,
  zDepthForType,
} from "../lib/graphUtils";

type ExpandableGraphProps = {
  snapshot: unknown | null;
};

type TypeVisual = {
  label: string;
  fill: string;
  stroke: string;
  tint: string;
};

type GraphMode = "core" | "expanded" | "full";
type LabelMode = "compact" | "full";
type FocusDepth = 0 | 1 | 2;
type GraphViewMode = "3d" | "2d";

type NeighborhoodSets = {
  nodeIds: Set<string>;
  oneHopNodeIds: Set<string>;
  twoHopNodeIds: Set<string>;
};

type NeighborListItem = {
  node: AtlasGraphNode;
  relationTypes: string[];
  rawEdgeCount: number;
  evidenceCount: number;
  viaNode?: AtlasGraphNode;
};

const TYPE_VISUALS: Record<string, TypeVisual> = {
  Document: { label: "文档", fill: "#64748B", stroke: "#475569", tint: "#F8FAFC" },
  Evidence: { label: "证据", fill: "#94A3B8", stroke: "#64748B", tint: "#F8FAFC" },
  DisasterType: { label: "灾害类型", fill: "#0B1F4D", stroke: "#1D4ED8", tint: "#DBEAFE" },
  AITech: { label: "AI技术", fill: "#1D4ED8", stroke: "#2563EB", tint: "#DBEAFE" },
  Scenario: { label: "应用场景", fill: "#2563EB", stroke: "#3B82F6", tint: "#EFF6FF" },
  Task: { label: "任务", fill: "#0369A1", stroke: "#0284C7", tint: "#E0F2FE" },
  Dataset: { label: "数据集", fill: "#0EA5E9", stroke: "#0284C7", tint: "#E0F2FE" },
  Model: { label: "模型", fill: "#60A5FA", stroke: "#3B82F6", tint: "#EFF6FF" },
  Case: { label: "案例", fill: "#7C3AED", stroke: "#7C3AED", tint: "#F3E8FF" },
  Event: { label: "事件", fill: "#8B5CF6", stroke: "#7C3AED", tint: "#F3E8FF" },
  Policy: { label: "政策标准", fill: "#475569", stroke: "#64748B", tint: "#F1F5F9" },
  Standard: { label: "标准", fill: "#64748B", stroke: "#475569", tint: "#F1F5F9" },
  Organization: { label: "机构", fill: "#334155", stroke: "#475569", tint: "#F8FAFC" },
  Metric: { label: "指标", fill: "#0284C7", stroke: "#0369A1", tint: "#E0F2FE" },
  ImpactProduct: { label: "影响产品", fill: "#0F766E", stroke: "#0F766E", tint: "#ECFDF5" },
  Limitation: { label: "限制", fill: "#DC2626", stroke: "#DC2626", tint: "#FEF2F2" },
  Unknown: { label: "未知", fill: "#64748B", stroke: "#64748B", tint: "#F1F5F9" },
};

const REPORT_CANVAS_EDGE_LIMIT = 30;
const EXPLORE_CANVAS_EDGE_LIMIT = 90;
const FULL_CANVAS_EDGE_LIMIT = 360;
const FOCUSED_KEY_EDGE_LIMIT = 5;
const KEY_EDGE_RELATION_PRIORITY = ["VALIDATED_IN", "SOLVES", "DEPENDS_ON", "USES_MODEL", "SERVES_STAGE"];
const EVIDENCE_TEXT_LIMIT = 120;
const DEFAULT_ROTATION_X = 18;
const DEFAULT_ROTATION_Y = -22;
const DEFAULT_PERSPECTIVE = 1000;
const CANVAS_WIDTH = 1160;
const CANVAS_HEIGHT = 800;
const CANVAS_CENTER_X = 580;
const CANVAS_CENTER_Y = 390;
const MANUAL_LABEL_SPLITS: Record<string, string[]> = {
  地震证据图谱GraphRAG: ["地震证据图谱", "GraphRAG"],
  生命线震损风险传播GNN: ["生命线震损风险", "传播GNN"],
  震后建筑损毁识别: ["震后建筑损毁", "识别"],
};
const RELATION_LABELS: Record<string, string> = {
  APPLIES_TO: "适用于",
  SERVES_STAGE: "服务阶段",
  SOLVES: "解决任务",
  DEPENDS_ON: "依赖数据",
  USES_MODEL: "采用模型",
  VALIDATED_IN: "案例验证",
  LIMITED_BY: "受限于",
  REQUIRED_BY: "政策要求",
  SUPPORTED_BY: "证据支持",
  DERIVES_FROM: "来源于",
  MEASURED_BY: "由指标度量",
  EVALUATED_BY: "由对象评估",
  PUBLISHED_BY: "由机构发布",
  HAS_METRIC: "具有指标",
  HAS_PARAMETER: "具有参数",
  HAS_IMPACT: "产生影响",
};

function relationTypeLabel(type: string): string {
  return RELATION_LABELS[type] ? `${type}（${RELATION_LABELS[type]}）` : type;
}

function reviewStatusLabel(value: string | undefined): string {
  const text = value?.trim().toLowerCase();
  if (!text || text === "unknown" || text === "null" || text === "undefined") return "暂无记录";
  if (text === "pending") return "待复核";
  if (text === "approved" || text === "passed") return "已通过";
  if (text === "rejected" || text === "failed") return "已拒绝";
  if (text === "rule") return "规则抽取";
  if (text === "hybrid") return "混合抽取";
  if (text === "llm") return "大模型抽取";
  return value ?? "暂无记录";
}

function edgeRelationRank(edge: AggregatedGraphEdge, allowAppliesTo: boolean): number {
  const ranks = edge.relationTypes.map((type) => {
    if (type === "APPLIES_TO") return allowAppliesTo ? 8 : 98;
    const index = KEY_EDGE_RELATION_PRIORITY.indexOf(type);
    return index === -1 ? 50 : index;
  });
  return Math.min(...ranks, 99);
}

function sortFocusedEdges(edges: AggregatedGraphEdge[], allowAppliesTo: boolean): AggregatedGraphEdge[] {
  return [...edges].sort((a, b) => {
    const ar = edgeRelationRank(a, allowAppliesTo);
    const br = edgeRelationRank(b, allowAppliesTo);
    if (ar !== br) return ar - br;
    if (a.evidenceCount !== b.evidenceCount) return b.evidenceCount - a.evidenceCount;
    if ((a.confidenceMax ?? 0) !== (b.confidenceMax ?? 0)) return (b.confidenceMax ?? 0) - (a.confidenceMax ?? 0);
    return b.rawEdgeCount - a.rawEdgeCount;
  });
}

function getFocusedKeyEdges(edges: AggregatedGraphEdge[], selectedNodeId: string | null, limit = FOCUSED_KEY_EDGE_LIMIT): AggregatedGraphEdge[] {
  if (!selectedNodeId) return [];
  const incident = edges.filter((edge) => edge.source === selectedNodeId || edge.target === selectedNodeId);
  const hasNonAppliesTo = incident.some((edge) => edge.relationTypes.some((type) => type !== "APPLIES_TO"));
  const pool = hasNonAppliesTo ? incident.filter((edge) => edge.relationTypes.some((type) => type !== "APPLIES_TO")) : incident;
  return sortFocusedEdges(pool, !hasNonAppliesTo).slice(0, limit);
}

function edgePeerLabel(edge: AggregatedGraphEdge, nodeId: string, graph: NormalizedAtlasGraph): string {
  const peerId = edge.source === nodeId ? edge.target : edge.source;
  return graph.nodeById.get(peerId)?.label ?? peerId;
}

function visualFor(type: string): TypeVisual {
  return TYPE_VISUALS[type] ?? { label: type || "未知", fill: "#3B82F6", stroke: "#1D4ED8", tint: "#EFF6FF" };
}

function confidenceLabel(value: number | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "未提供";
  return value.toFixed(2);
}

function coreLabel(label: string): string {
  if (/GraphRAG/i.test(label)) return "GraphRAG";
  if (/GNN/i.test(label)) return "GNN";
  if (/LSTM/i.test(label)) return "LSTM";
  const clean = label.replace(/地震|震后|灾害|智能|关键|技术|模型|数据|评估|识别/g, "").trim();
  return compactText(clean || label, 4).replace("…", "");
}

function splitCaption(label: string, mode: LabelMode): string[] {
  if (MANUAL_LABEL_SPLITS[label]) return MANUAL_LABEL_SPLITS[label].slice(0, 2);
  if (/GraphRAG/i.test(label)) {
    const prefix = label.replace(/GraphRAG/gi, "").trim();
    return [compactText(prefix, 10), "GraphRAG"];
  }
  if (/GNN/i.test(label) && label.length > 10) {
    const prefix = label.replace(/GNN/gi, "").trim();
    return [compactText(prefix, 8), `${compactText(prefix.slice(8), 4)}GNN`.replace(/^GNN$/, "GNN")].filter(Boolean).slice(0, 2);
  }
  const limit = mode === "compact" ? 18 : 22;
  const text = compactText(label, limit);
  if (text.length <= 9) return [text];
  return [text.slice(0, 9), compactText(text.slice(9), 9)];
}

function nodeRadius(node: AtlasGraphNode, selected: boolean, linked: boolean): number {
  if (selected) return node.type === "DisasterType" ? 34 : 31;
  if (node.type === "DisasterType") return 30;
  if (node.type === "AITech") return linked ? 27 : 25;
  if (["Scenario", "Task", "Dataset", "Model"].includes(node.type)) return linked ? 25 : 23;
  return linked ? 23 : 21;
}

function clampViewValue(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, Number.isFinite(value) ? value : 0));
}

function projectedNodeRadius(node: AtlasGraphNode, selected: boolean, linked: boolean, point: ProjectedGraphPoint, is3DView: boolean): number {
  const base = nodeRadius(node, selected, linked);
  if (!is3DView) return base;
  const depthScale = 0.86 + point.opacity * 0.22;
  return Math.max(14, base * point.screenScale * depthScale);
}

function displayAngle(value: number): string {
  return `${Math.round(value)}°`;
}

function edgePath(
  edge: { id: string },
  source: { x: number; y: number },
  target: { x: number; y: number },
  sourceRadius: number,
  targetRadius: number,
): string {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const length = Math.sqrt(dx * dx + dy * dy) || 1;
  const x1 = source.x + (dx / length) * (sourceRadius + 6);
  const y1 = source.y + (dy / length) * (sourceRadius + 6);
  const x2 = target.x - (dx / length) * (targetRadius + 8);
  const y2 = target.y - (dy / length) * (targetRadius + 8);
  const hash = [...edge.id].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  const bendIndex = (hash % 7) - 3 || 2;
  const bend = bendIndex * Math.min(18, Math.max(7, length * 0.026));
  const midX = (x1 + x2) / 2 - (dy / length) * bend;
  const midY = (y1 + y2) / 2 + (dx / length) * bend;
  return `M ${x1} ${y1} Q ${midX} ${midY} ${x2} ${y2}`;
}

function sortAggregatedEdges(edges: AggregatedGraphEdge[], selectedNodeId: string | null): AggregatedGraphEdge[] {
  return [...edges].sort((a, b) => {
    const aSelected = selectedNodeId && (a.source === selectedNodeId || a.target === selectedNodeId) ? 1 : 0;
    const bSelected = selectedNodeId && (b.source === selectedNodeId || b.target === selectedNodeId) ? 1 : 0;
    if (aSelected !== bSelected) return bSelected - aSelected;
    if (a.evidenceCount !== b.evidenceCount) return b.evidenceCount - a.evidenceCount;
    if ((a.confidenceMax ?? 0) !== (b.confidenceMax ?? 0)) return (b.confidenceMax ?? 0) - (a.confidenceMax ?? 0);
    return b.rawEdgeCount - a.rawEdgeCount;
  });
}

function aggregatedEdgeLabel(edge: AggregatedGraphEdge): string {
  const primary = relationTypeLabel(edge.primaryRelationType);
  if (edge.relationTypes.length <= 1) {
    return edge.rawEdgeCount > 1 ? `${primary} ×${edge.rawEdgeCount}` : primary;
  }
  return `${primary} 等 ${edge.relationTypes.length} 类`;
}

function relationSummary(nodeId: string | null, edges: AtlasGraphEdge[]): Array<{ type: string; count: number }> {
  if (!nodeId) return [];
  const counts = new Map<string, number>();
  edges.forEach((edge) => {
    if (edge.source === nodeId || edge.target === nodeId) counts.set(edge.relationType, (counts.get(edge.relationType) ?? 0) + 1);
  });
  return [...counts.entries()]
    .map(([type, count]) => ({ type, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 6);
}

function uniqueNeighborItems(items: AdjacencyItem[]): AdjacencyItem[] {
  const seen = new Set<string>();
  const unique: AdjacencyItem[] = [];
  for (const item of items) {
    if (seen.has(item.nodeId)) continue;
    seen.add(item.nodeId);
    unique.push(item);
  }
  return unique;
}

function rawEdgeAllowed(
  edge: AtlasGraphEdge,
  graph: NormalizedAtlasGraph,
  relationFilters: Set<string>,
  typeFilters: Set<string>,
  evidenceOnly: boolean,
): boolean {
  if (!relationFilters.has(edge.relationType)) return false;
  const sourceType = graph.nodeById.get(edge.source)?.type ?? "Unknown";
  const targetType = graph.nodeById.get(edge.target)?.type ?? "Unknown";
  if (!typeFilters.has(sourceType) || !typeFilters.has(targetType)) return false;
  if (evidenceOnly && !edge.evidenceText && !edge.docId) return false;
  return true;
}

function collectNeighborhood(
  nodeId: string | null,
  graph: NormalizedAtlasGraph,
  relationFilters: Set<string>,
  typeFilters: Set<string>,
  evidenceOnly: boolean,
  depth: FocusDepth,
): NeighborhoodSets {
  const empty = { nodeIds: new Set<string>(), oneHopNodeIds: new Set<string>(), twoHopNodeIds: new Set<string>() };
  if (!nodeId || !graph.nodeById.has(nodeId)) return empty;

  const neighborMap = new Map<string, Set<string>>();
  graph.edges
    .filter((edge) => rawEdgeAllowed(edge, graph, relationFilters, typeFilters, evidenceOnly))
    .forEach((edge) => {
      const sourceSet = neighborMap.get(edge.source) ?? new Set<string>();
      sourceSet.add(edge.target);
      neighborMap.set(edge.source, sourceSet);
      const targetSet = neighborMap.get(edge.target) ?? new Set<string>();
      targetSet.add(edge.source);
      neighborMap.set(edge.target, targetSet);
    });

  const nodeIds = new Set<string>([nodeId]);
  const oneHopNodeIds = depth >= 1 ? new Set(neighborMap.get(nodeId) ?? []) : new Set<string>();
  oneHopNodeIds.forEach((id) => nodeIds.add(id));

  const twoHopNodeIds = new Set<string>();
  if (depth >= 2) {
    oneHopNodeIds.forEach((oneHopId) => {
      for (const nextId of neighborMap.get(oneHopId) ?? []) {
        if (nextId === nodeId || oneHopNodeIds.has(nextId)) continue;
        twoHopNodeIds.add(nextId);
        nodeIds.add(nextId);
      }
    });
  }

  return { nodeIds, oneHopNodeIds, twoHopNodeIds };
}

function edgeTouchesNodeSet(edge: AggregatedGraphEdge, nodeIds: Set<string>): boolean {
  return nodeIds.has(edge.source) && nodeIds.has(edge.target);
}

function StatusBadge({ value }: { value: string }) {
  const text = reviewStatusLabel(value);
  return <span className={`status-badge ${text === "待复核" ? "pending" : ""}`}>{text}</span>;
}

function DetailMetric({ label, value }: { label: string; value: string | number | undefined }) {
  return (
    <div className="detail-metric">
      <span>{label}</span>
      <strong>{displayValue(value)}</strong>
    </div>
  );
}

function FilterPanel({
  title,
  values,
  selected,
  open,
  onToggleOpen,
  formatValue = (value: string) => value,
}: {
  title: string;
  values: string[];
  selected: Set<string>;
  open: boolean;
  onToggleOpen: () => void;
  formatValue?: (value: string) => string;
}) {
  const selectedLabel = values.filter((value) => selected.has(value)).slice(0, 2).map(formatValue).join("、");
  return (
    <div className="filter-panel">
      <button className={open ? "filter-summary-button active" : "filter-summary-button"} onClick={onToggleOpen} type="button">
        <span>{title}</span>
        <strong>{selected.size}/{values.length}</strong>
        {selectedLabel ? <em>{selectedLabel}{selected.size > 2 ? " 等" : ""}</em> : null}
      </button>
    </div>
  );
}

function FilterDrawer({
  title,
  values,
  selected,
  formatValue,
  onToggleValue,
  onSelectAll,
  onClearAll,
  onClose,
}: {
  title: string;
  values: string[];
  selected: Set<string>;
  formatValue: (value: string) => string;
  onToggleValue: (value: string) => void;
  onSelectAll: () => void;
  onClearAll: () => void;
  onClose: () => void;
}) {
  return (
    <div className="filter-drawer" role="region" aria-label={`${title}筛选面板`}>
      <div className="filter-drawer-head">
        <strong>{title}</strong>
        <span>当前选择 {selected.size}/{values.length}</span>
      </div>
      <div className="filter-chip-grid filter-drawer-grid">
        {values.map((value) => (
          <button className={selected.has(value) ? "selected" : ""} key={value} onClick={() => onToggleValue(value)} type="button">
            {formatValue(value)}
          </button>
        ))}
      </div>
      <div className="filter-mini-actions filter-drawer-actions">
        <button onClick={onSelectAll} type="button">全部选择</button>
        <button onClick={onClearAll} type="button">全部清除</button>
        <button onClick={onClose} type="button">应用筛选</button>
        <button onClick={onClose} type="button">关闭筛选</button>
      </div>
    </div>
  );
}

function RawRelationList({ edge, graph }: { edge: AggregatedGraphEdge; graph: NormalizedAtlasGraph }) {
  const shown = edge.rawEdges.slice(0, 10);
  return (
    <div className="raw-relation-list">
      {shown.map((rawEdge) => {
        const source = graph.nodeById.get(rawEdge.source);
        const target = graph.nodeById.get(rawEdge.target);
        return (
          <article key={rawEdge.id}>
            <strong>{source?.label ?? rawEdge.source} → {relationTypeLabel(rawEdge.relationType)} → {target?.label ?? rawEdge.target}</strong>
            <span>
              {confidenceLabel(rawEdge.confidence)} · {rawEdge.docId || "未提供 doc_id"} · {rawEdge.chunkId || "未提供 chunk_id"} · {reviewStatusLabel(rawEdge.reviewStatus)}
            </span>
            <em>{rawEdge.sourceName || "未提供来源名称"}</em>
            <p>{rawEdge.evidenceText ? compactText(rawEdge.evidenceText, 120) : "当前原始关系未提供证据片段"}</p>
          </article>
        );
      })}
      {edge.rawEdgeCount > shown.length ? <p className="raw-relation-more">当前聚合边包含 {edge.rawEdgeCount} 条原始关系，已展示前 {shown.length} 条。</p> : null}
    </div>
  );
}

function SidePanel({
  graph,
  selectedNode,
  selectedEdge,
  adjacency,
  aggregatedVisibleEdges,
  focusRelationEdges,
  oneHopItems,
  twoHopItems,
  focusDepth,
  visibleNodeIds,
  screenshotMode,
  viewMode,
  rotationX,
  rotationY,
  onExpandOne,
  onExpandMore,
  onCollapse,
  onReset,
  onSelectNeighbor,
}: {
  graph: NormalizedAtlasGraph;
  selectedNode: AtlasGraphNode | null;
  selectedEdge: AggregatedGraphEdge | null;
  adjacency: Map<string, AdjacencyItem[]>;
  aggregatedVisibleEdges: AggregatedGraphEdge[];
  focusRelationEdges: AggregatedGraphEdge[];
  oneHopItems: NeighborListItem[];
  twoHopItems: NeighborListItem[];
  focusDepth: FocusDepth;
  visibleNodeIds: Set<string>;
  screenshotMode: boolean;
  viewMode: GraphViewMode;
  rotationX: number;
  rotationY: number;
  onExpandOne: () => void;
  onExpandMore: () => void;
  onCollapse: () => void;
  onReset: () => void;
  onSelectNeighbor: (nodeId: string) => void;
}) {
  const evidenceRef = useRef<HTMLElement>(null);
  const [expandedEvidenceIds, setExpandedEvidenceIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (screenshotMode) evidenceRef.current?.scrollIntoView({ block: "nearest" });
  }, [screenshotMode, selectedNode?.id, selectedEdge?.id]);

  if (!selectedNode && !selectedEdge) {
    return (
      <aside className="graph-side-panel showcase-side-panel">
        <section className="detail-section empty-state-card">
          <span className="eyebrow">当前选择</span>
          <h3>点击图谱中的任意节点或聚合边</h3>
          <p>可查看实体类型、聚合关系、原始关系、来源文档和可展开邻居节点。</p>
        </section>
      </aside>
    );
  }

  const sourceNode = selectedEdge ? graph.nodeById.get(selectedEdge.source) : null;
  const targetNode = selectedEdge ? graph.nodeById.get(selectedEdge.target) : null;
  const node = selectedNode ?? sourceNode ?? null;
  const rankedNeighbors = node ? uniqueNeighborItems(rankAdjacencyItems(adjacency.get(node.id) ?? [], graph.nodeById)) : [];
  const nonAppliesNeighbors = rankedNeighbors.filter((item) => item.edge.relationType !== "APPLIES_TO");
  const hiddenNeighborCount = rankedNeighbors.filter((item) => !visibleNodeIds.has(item.nodeId)).length;
  const incidentAggregatedEdges = node ? aggregatedVisibleEdges.filter((edge) => edge.source === node.id || edge.target === node.id) : [];
  const rawIncidentEdges = node ? graph.edges.filter((edge) => edge.source === node.id || edge.target === node.id) : [];
  const evidenceEdges = selectedEdge
    ? selectedEdge.rawEdges
    : node
      ? (nonAppliesNeighbors.length ? nonAppliesNeighbors : rankedNeighbors).map((item) => item.edge)
      : [];
  const evidenceSnippets = evidenceEdges.filter((edge) => edge.evidenceText || edge.docId).slice(0, 3);

  return (
    <aside className="graph-side-panel showcase-side-panel">
      <section className="detail-section selection-card">
        <span className="eyebrow">当前图谱对象</span>
        <h3>{selectedEdge ? aggregatedEdgeLabel(selectedEdge) : node?.label}</h3>
        {selectedEdge ? (
          <>
            <div className="selection-badges">
              <span className="node-type-pill edge-type-pill">{selectedEdge.isBidirectional ? "双向关系" : "单向关系"}</span>
              <StatusBadge value={selectedEdge.reviewStatuses.map(reviewStatusLabel).join(" / ") || "暂无记录"} />
            </div>
            <div className="detail-metric-grid edge-metric-grid">
              <DetailMetric label="起点" value={sourceNode?.label ?? selectedEdge.source} />
              <DetailMetric label="终点" value={targetNode?.label ?? selectedEdge.target} />
              <DetailMetric label="原始关系" value={selectedEdge.rawEdgeCount} />
              <DetailMetric label="主关系" value={relationTypeLabel(selectedEdge.primaryRelationType)} />
              <DetailMetric label="证据数" value={selectedEdge.evidenceCount} />
              <DetailMetric label="最大置信度" value={confidenceLabel(selectedEdge.confidenceMax)} />
              <DetailMetric label="平均置信度" value={confidenceLabel(selectedEdge.confidenceAvg)} />
              <DetailMetric label="来源文档" value={selectedEdge.docIds.length} />
            </div>
            <div className="relation-count-grid">
              {selectedEdge.relationTypes.map((type) => <span key={type}>{relationTypeLabel(type)}</span>)}
            </div>
          </>
        ) : node ? (
          <>
            <div className="selection-badges">
              <span className="node-type-pill" style={{ borderColor: visualFor(node.type).stroke, color: visualFor(node.type).stroke }}>
                {visualFor(node.type).label}
              </span>
              <StatusBadge value={node.reviewStatus} />
            </div>
            <div className="detail-metric-grid">
              <DetailMetric label="聚合边" value={incidentAggregatedEdges.length} />
              <DetailMetric label="原始关系" value={rawIncidentEdges.length} />
              <DetailMetric label="证据边" value={rawIncidentEdges.filter((edge) => edge.evidenceText || edge.docId).length} />
              <DetailMetric label="社区编号" value={node.community || "未分配"} />
              <DetailMetric label="所属簇团" value={clusterLabelForType(node.type)} />
            </div>
          </>
        ) : null}
      </section>

      <section className="detail-section action-card">
        <span className="eyebrow">操作</span>
        <div className="side-action-grid">
          <button disabled={!node} onClick={onExpandOne} type="button">展开一跳</button>
          <button disabled={!node} onClick={onExpandMore} type="button">展开两跳</button>
          <button disabled={!node} onClick={onCollapse} type="button">收起到当前节点</button>
          <button onClick={onReset} type="button">重置视图</button>
        </div>
        {hiddenNeighborCount ? <p className="hidden-neighbor-note">还有 {hiddenNeighborCount} 个相关节点未展开。</p> : null}
      </section>

      <section className="detail-section view-state-card">
        <span className="eyebrow">视角说明</span>
        <div className="view-state-grid">
          <div><span>当前视图</span><strong>{viewMode === "3d" ? "立体视图" : "平面视图"}</strong></div>
          <div><span>当前角度</span><strong>X {displayAngle(rotationX)} / Y {displayAngle(rotationY)}</strong></div>
        </div>
        <p>前层：AI 技术与任务；中层：模型与数据；后层：证据、政策与限制。</p>
      </section>

      {node ? (
        <section className="detail-section relation-summary-card">
          <span className="eyebrow">关系摘要</span>
          <div className="relation-count-grid">
            {relationSummary(node.id, graph.edges).map((item) => (
              <span key={item.type}>{relationTypeLabel(item.type)} {item.count}</span>
            ))}
          </div>
        </section>
      ) : null}

      {node && focusRelationEdges.length ? (
        <section className="detail-section focused-edge-card">
          <span className="eyebrow">全部相关关系</span>
          <div className="focused-edge-list">
            {focusRelationEdges.map((edge) => (
              <article key={edge.id}>
                <strong>{relationTypeLabel(edge.primaryRelationType)}</strong>
                <span>{edgePeerLabel(edge, node.id, graph)}</span>
                <em>{edge.rawEdgeCount} 条原始关系 · {edge.evidenceCount} 条证据</em>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {selectedEdge ? (
        <section className="detail-section raw-relations-card">
          <span className="eyebrow">原始关系</span>
          <h3>原始关系列表</h3>
          <RawRelationList edge={selectedEdge} graph={graph} />
        </section>
      ) : null}

      {node ? (
        <section className="detail-section compact-card">
          <span className="eyebrow">已关联节点</span>
          <h3>一跳关联节点：{oneHopItems.length} 个</h3>
          <div className="neighbor-list compact-neighbor-list expanded-neighbor-list">
            {oneHopItems.map((item) => {
              return (
                <button key={item.node.id} onClick={() => onSelectNeighbor(item.node.id)} type="button">
                  <strong>{item.node.label}</strong>
                  <span>{visualFor(item.node.type).label} · {item.relationTypes.map(relationTypeLabel).join("、")}</span>
                  <em>{item.rawEdgeCount} 条原始关系 · {item.evidenceCount ? "有证据" : "待补证"}</em>
                </button>
              );
            })}
            {!oneHopItems.length ? <p>当前筛选条件下暂无一跳关联节点。</p> : null}
          </div>
          {focusDepth >= 2 ? (
            <>
              <h3>二跳扩展节点：{twoHopItems.length} 个</h3>
              <div className="neighbor-list compact-neighbor-list expanded-neighbor-list">
                {twoHopItems.map((item) => (
                  <button key={item.node.id} onClick={() => onSelectNeighbor(item.node.id)} type="button">
                    <strong>{item.node.label}</strong>
                    <span>{visualFor(item.node.type).label} · 经由 {item.viaNode?.label ?? "一跳节点"}</span>
                    <em>{item.relationTypes.map(relationTypeLabel).join("、")} · {item.evidenceCount ? "有证据" : "待补证"}</em>
                  </button>
                ))}
                {!twoHopItems.length ? <p>当前筛选条件下暂无二跳扩展节点。</p> : null}
              </div>
            </>
          ) : null}
        </section>
      ) : null}

      <section className="detail-section evidence-detail" ref={evidenceRef}>
        <span className="eyebrow">证据片段</span>
        <div className="evidence-stack">
          {evidenceSnippets.length ? evidenceSnippets.map((edge) => {
            const fullText = edge.evidenceText || "当前边未提供证据片段";
            const expanded = expandedEvidenceIds.has(edge.id);
            const needsToggle = fullText.length > EVIDENCE_TEXT_LIMIT;
            return (
              <article className="evidence-card" key={edge.id}>
                <dl>
                  <div><dt>关系类型</dt><dd>{relationTypeLabel(edge.relationType)}</dd></div>
                  <div><dt>来源</dt><dd>{edge.sourceName || edge.docId || "未提供来源"}</dd></div>
                  <div><dt>置信度</dt><dd>{confidenceLabel(edge.confidence)}</dd></div>
                  <div><dt>复核状态</dt><dd>{reviewStatusLabel(edge.reviewStatus)}</dd></div>
                </dl>
                <p><strong>证据片段：</strong>{expanded || !needsToggle ? fullText : compactText(fullText, EVIDENCE_TEXT_LIMIT)}</p>
                {needsToggle ? (
                  <button onClick={() => setExpandedEvidenceIds((previous) => {
                    const next = new Set(previous);
                    if (next.has(edge.id)) next.delete(edge.id);
                    else next.add(edge.id);
                    return next;
                  })} type="button">
                    {expanded ? "收起" : "展开"}
                  </button>
                ) : null}
              </article>
            );
          }) : <p>当前选择暂未提供可展示证据片段。</p>}
        </div>
      </section>
    </aside>
  );
}

function ExpandableGraphWorkspace({ graph }: { graph: NormalizedAtlasGraph }) {
  const initialNodeIds = useMemo(() => getInitialNodeIds(graph.nodes, graph.edges), [graph.nodes, graph.edges]);
  const defaultSelectedNodeId = useMemo(() => getDefaultSelectedNodeId(graph.nodes, graph.edges), [graph.nodes, graph.edges]);
  const defaultRelationFilterValues = useMemo(() => getDefaultRelationTypes(graph.relationTypes), [graph.relationTypes]);
  const adjacency = useMemo(() => buildAdjacency(graph.nodes, graph.edges), [graph.nodes, graph.edges]);
  const defaultFocusNodeId = defaultSelectedNodeId ?? [...initialNodeIds][0] ?? graph.nodes[0]?.id ?? null;
  const initialVisibleNodeIds = useMemo(() => {
    const next = new Set(initialNodeIds);
    if (defaultFocusNodeId) {
      collectNeighborhood(
        defaultFocusNodeId,
        graph,
        new Set(defaultRelationFilterValues),
        new Set(graph.entityTypes),
        false,
        1,
      ).nodeIds.forEach((nodeId) => next.add(nodeId));
    }
    return next;
  }, [defaultFocusNodeId, defaultRelationFilterValues, graph, initialNodeIds]);
  const [visibleNodeIds, setVisibleNodeIds] = useState<Set<string>>(() => initialVisibleNodeIds);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(() => defaultFocusNodeId);
  const [focusNodeId, setFocusNodeId] = useState<string | null>(() => defaultFocusNodeId);
  const [focusDepth, setFocusDepth] = useState<FocusDepth>(1);
  const [neighborhoodOnly, setNeighborhoodOnly] = useState(false);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [relationFilters, setRelationFilters] = useState<Set<string>>(() => new Set(defaultRelationFilterValues));
  const [typeFilters, setTypeFilters] = useState<Set<string>>(() => new Set(graph.entityTypes));
  const [searchKeyword, setSearchKeyword] = useState("");
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const [evidenceOnly, setEvidenceOnly] = useState(false);
  const [showEdgeLabels, setShowEdgeLabels] = useState(false);
  const [labelMode, setLabelMode] = useState<LabelMode>("compact");
  const [graphMode, setGraphMode] = useState<GraphMode>("core");
  const [screenshotMode, setScreenshotMode] = useState(false);
  const [relationFilterOpen, setRelationFilterOpen] = useState(false);
  const [typeFilterOpen, setTypeFilterOpen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [viewMode, setViewMode] = useState<GraphViewMode>("3d");
  const [rotationX, setRotationX] = useState(DEFAULT_ROTATION_X);
  const [rotationY, setRotationY] = useState(DEFAULT_ROTATION_Y);
  const [autoRotate, setAutoRotate] = useState(false);
  const [isDraggingView, setIsDraggingView] = useState(false);
  const autoRotateDirectionRef = useRef(1);
  const dragStartRef = useRef({ active: false, x: 0, y: 0, rotationX: DEFAULT_ROTATION_X, rotationY: DEFAULT_ROTATION_Y });
  const dragMovedRef = useRef(false);

  const selectedNode = selectedNodeId ? graph.nodeById.get(selectedNodeId) ?? null : null;

  useEffect(() => {
    if (!autoRotate || viewMode !== "3d") return undefined;
    const timer = window.setInterval(() => {
      setRotationY((value) => {
        const next = value + autoRotateDirectionRef.current * 0.25;
        if (next > 55 || next < -55) {
          autoRotateDirectionRef.current *= -1;
          return clampViewValue(next, -55, 55);
        }
        return next;
      });
    }, 120);
    return () => window.clearInterval(timer);
  }, [autoRotate, viewMode]);

  const neighborhood = useMemo(
    () => collectNeighborhood(focusNodeId, graph, relationFilters, typeFilters, evidenceOnly, focusDepth),
    [evidenceOnly, focusDepth, focusNodeId, graph, relationFilters, typeFilters],
  );

  const effectiveVisibleNodeIds = useMemo(() => {
    if ((neighborhoodOnly || screenshotMode) && focusNodeId) return neighborhood.nodeIds;
    return visibleNodeIds;
  }, [focusNodeId, neighborhood.nodeIds, neighborhoodOnly, screenshotMode, visibleNodeIds]);

  const visibleNodes = useMemo(
    () => graph.nodes.filter((node) => effectiveVisibleNodeIds.has(node.id) && typeFilters.has(node.type)),
    [effectiveVisibleNodeIds, graph.nodes, typeFilters],
  );

  const visibleEdges = useMemo(
    () => getFilteredVisibleEdges(graph.edges, effectiveVisibleNodeIds, graph.nodeById, relationFilters, typeFilters, evidenceOnly),
    [effectiveVisibleNodeIds, evidenceOnly, graph.edges, graph.nodeById, relationFilters, typeFilters],
  );

  const aggregatedVisibleEdges = useMemo(() => aggregateEdges(visibleEdges), [visibleEdges]);
  const selectedEdge = selectedEdgeId ? aggregatedVisibleEdges.find((edge) => edge.id === selectedEdgeId) ?? null : null;

  const oneHopEdgeIds = useMemo(() => {
    if (!focusNodeId) return new Set<string>();
    return new Set(
      aggregatedVisibleEdges
        .filter((edge) => (edge.source === focusNodeId && neighborhood.oneHopNodeIds.has(edge.target)) || (edge.target === focusNodeId && neighborhood.oneHopNodeIds.has(edge.source)))
        .map((edge) => edge.id),
    );
  }, [aggregatedVisibleEdges, focusNodeId, neighborhood.oneHopNodeIds]);

  const twoHopEdgeIds = useMemo(() => {
    if (!focusNodeId || focusDepth < 2) return new Set<string>();
    return new Set(
      aggregatedVisibleEdges
        .filter((edge) => edgeTouchesNodeSet(edge, neighborhood.nodeIds) && !oneHopEdgeIds.has(edge.id))
        .map((edge) => edge.id),
    );
  }, [aggregatedVisibleEdges, focusDepth, focusNodeId, neighborhood.nodeIds, oneHopEdgeIds]);

  const focusEdgeIds = useMemo(() => new Set([...oneHopEdgeIds, ...twoHopEdgeIds]), [oneHopEdgeIds, twoHopEdgeIds]);

  const focusRelationEdges = useMemo(
    () => sortAggregatedEdges(aggregatedVisibleEdges.filter((edge) => focusEdgeIds.has(edge.id)), focusNodeId),
    [aggregatedVisibleEdges, focusEdgeIds, focusNodeId],
  );

  const canvasEdges = useMemo(() => {
    const sorted = sortAggregatedEdges(aggregatedVisibleEdges, selectedNodeId);
    if (neighborhoodOnly || screenshotMode) return focusRelationEdges;

    const limit = graphMode === "full" ? FULL_CANVAS_EDGE_LIMIT : graphMode === "expanded" ? EXPLORE_CANVAS_EDGE_LIMIT : REPORT_CANVAS_EDGE_LIMIT;
    const merged = new Map<string, AggregatedGraphEdge>();
    focusRelationEdges.forEach((edge) => merged.set(edge.id, edge));
    for (const edge of sorted) {
      if (merged.size >= Math.max(limit, focusRelationEdges.length)) break;
      merged.set(edge.id, edge);
    }
    return [...merged.values()];
  }, [aggregatedVisibleEdges, focusRelationEdges, graphMode, neighborhoodOnly, screenshotMode, selectedNodeId]);

  const layout = useMemo(
    () => computeSoftClusterLayout(visibleNodes, canvasEdges, {
      canvasWidth: CANVAS_WIDTH,
      canvasHeight: CANVAS_HEIGHT,
      selectedNodeId,
      oneHopNodeIds: neighborhood.oneHopNodeIds,
      twoHopNodeIds: neighborhood.twoHopNodeIds,
      mode: screenshotMode ? "screenshot" : graphMode,
    }),
    [canvasEdges, graphMode, neighborhood.oneHopNodeIds, neighborhood.twoHopNodeIds, screenshotMode, selectedNodeId, visibleNodes],
  );

  const is3DView = viewMode === "3d";
  const viewLabel = is3DView ? "立体视图" : "平面视图";
  const layoutLabel = is3DView ? "单画布软分区立体网络" : "单画布软分区网络布局";
  const projectedLayout = useMemo(() => {
    const next = new Map<string, ProjectedGraphPoint>();
    visibleNodes.forEach((node) => {
      const point = layout.get(node.id);
      if (!point) return;
      const projected = project3DNode(
        { x: point.x, y: point.y, z: zDepthForType(node.type) },
        {
          enabled: is3DView,
          rotationX,
          rotationY,
          perspective: DEFAULT_PERSPECTIVE,
          scale: 1,
          centerX: CANVAS_CENTER_X,
          centerY: CANVAS_CENTER_Y,
        },
      );
      next.set(node.id, { ...projected, ring: point.ring, clusterId: point.clusterId });
    });
    return next;
  }, [is3DView, layout, rotationX, rotationY, visibleNodes]);

  const visibleClusterAuras = useMemo(() => {
    const visibleTypes = new Set(visibleNodes.map((node) => node.type));
    return GRAPH_CLUSTER_REGIONS.filter((region) => region.types.some((type) => visibleTypes.has(type)));
  }, [visibleNodes]);

  const searchResults = useMemo(() => {
    const keyword = searchKeyword.trim().toLowerCase();
    if (!keyword) return [];
    return graph.nodes
      .filter((node) => `${node.label} ${node.id} ${node.type}`.toLowerCase().includes(keyword))
      .sort((a, b) => getNodeDegree(b.id, adjacency) - getNodeDegree(a.id, adjacency))
      .slice(0, 8);
  }, [adjacency, graph.nodes, searchKeyword]);

  const focusedKeyEdges = useMemo(() => getFocusedKeyEdges(focusRelationEdges, focusNodeId), [focusNodeId, focusRelationEdges]);
  const keyEdgeIds = useMemo(() => new Set(focusedKeyEdges.map((edge) => edge.id)), [focusedKeyEdges]);

  const edgeRenderItems = useMemo(() => {
    return canvasEdges
      .map((edge) => {
        const source = projectedLayout.get(edge.source);
        const target = projectedLayout.get(edge.target);
        const sourceNode = graph.nodeById.get(edge.source);
        const targetNode = graph.nodeById.get(edge.target);
        if (!source || !target || !sourceNode || !targetNode) return null;

        const selected = edge.id === selectedEdgeId;
        const oneHopEdge = oneHopEdgeIds.has(edge.id);
        const twoHopEdge = twoHopEdgeIds.has(edge.id);
        const incident = focusEdgeIds.has(edge.id);
        const hovered = edge.id === hoveredEdgeId;
        const keyEdge = keyEdgeIds.has(edge.id);
        const unrelated = Boolean(focusNodeId && !incident && !selected);
        const sourceLinked = neighborhood.oneHopNodeIds.has(sourceNode.id) || neighborhood.twoHopNodeIds.has(sourceNode.id);
        const targetLinked = neighborhood.oneHopNodeIds.has(targetNode.id) || neighborhood.twoHopNodeIds.has(targetNode.id);
        const sourceRadius = projectedNodeRadius(sourceNode, sourceNode.id === selectedNodeId, sourceLinked, source, is3DView);
        const targetRadius = projectedNodeRadius(targetNode, targetNode.id === selectedNodeId, targetLinked, target, is3DView);
        const depthOpacity = clampViewValue(0.12 + ((source.opacity + target.opacity) / 2) * 0.72, 0.08, 0.9);
        const opacity = selected || hovered
          ? 1
          : keyEdge
            ? 0.9
            : incident
              ? Math.max(0.38, depthOpacity)
              : unrelated
                ? Math.min(0.12, depthOpacity * 0.32)
                : depthOpacity * 0.52;
        const strokeWidth = selected
          ? 4.5
          : hovered
            ? 3.5
            : keyEdge
              ? 3
              : incident
                ? 1.7
                : is3DView
                  ? 0.9 + ((source.screenScale + target.screenScale) / 2 - 0.7) * 0.8
                  : 1.1;
        return {
          edge,
          source,
          target,
          sourceNode,
          targetNode,
          sourceRadius,
          targetRadius,
          selected,
          oneHopEdge,
          twoHopEdge,
          incident,
          hovered,
          keyEdge,
          unrelated,
          opacity,
          strokeWidth,
          depth: (source.depth + target.depth) / 2,
          drawRank: selected ? 5 : hovered ? 4 : keyEdge ? 3 : incident ? 2 : 1,
        };
      })
      .filter((item): item is NonNullable<typeof item> => Boolean(item))
      .sort((a, b) => a.depth - b.depth || a.drawRank - b.drawRank);
  }, [
    canvasEdges,
    focusEdgeIds,
    focusNodeId,
    graph.nodeById,
    hoveredEdgeId,
    is3DView,
    keyEdgeIds,
    neighborhood.oneHopNodeIds,
    neighborhood.twoHopNodeIds,
    oneHopEdgeIds,
    projectedLayout,
    selectedEdgeId,
    selectedNodeId,
    twoHopEdgeIds,
  ]);

  const nodeRenderItems = useMemo(() => {
    return visibleNodes
      .map((node) => {
        const point = projectedLayout.get(node.id);
        if (!point) return null;
        const selected = node.id === selectedNodeId;
        const oneHop = neighborhood.oneHopNodeIds.has(node.id);
        const twoHop = neighborhood.twoHopNodeIds.has(node.id);
        const linked = oneHop || twoHop;
        const unrelated = Boolean(focusNodeId && node.id !== focusNodeId && !linked);
        const hovered = hoveredNodeId === node.id;
        const radius = projectedNodeRadius(node, selected, linked, point, is3DView);
        const circleOpacity = selected || hovered
          ? 1
          : linked
            ? Math.max(0.78, point.opacity)
            : unrelated
              ? Math.max(0.18, point.opacity * 0.46)
              : point.opacity;
        const labelOpacity = selected || hovered || linked ? 1 : unrelated ? Math.max(0.12, point.labelOpacity * 0.42) : point.labelOpacity;
        return {
          node,
          point,
          selected,
          oneHop,
          twoHop,
          linked,
          unrelated,
          hovered,
          radius,
          circleOpacity,
          labelOpacity,
          drawRank: selected ? 5 : hovered ? 4 : linked ? 3 : 1,
        };
      })
      .filter((item): item is NonNullable<typeof item> => Boolean(item))
      .sort((a, b) => a.point.depth - b.point.depth || a.drawRank - b.drawRank);
  }, [
    focusNodeId,
    hoveredNodeId,
    is3DView,
    neighborhood.oneHopNodeIds,
    neighborhood.twoHopNodeIds,
    projectedLayout,
    selectedNodeId,
    visibleNodes,
  ]);

  const oneHopItems = useMemo<NeighborListItem[]>(() => {
    if (!focusNodeId) return [];
    return [...neighborhood.oneHopNodeIds]
      .map((nodeId) => {
        const node = graph.nodeById.get(nodeId);
        if (!node) return null;
        const edges = aggregatedVisibleEdges.filter((edge) => (edge.source === focusNodeId && edge.target === nodeId) || (edge.target === focusNodeId && edge.source === nodeId));
        return {
          node,
          relationTypes: [...new Set(edges.flatMap((edge) => edge.relationTypes))],
          rawEdgeCount: edges.reduce((sum, edge) => sum + edge.rawEdgeCount, 0),
          evidenceCount: edges.reduce((sum, edge) => sum + edge.evidenceCount, 0),
        };
      })
      .filter((item): item is NeighborListItem => Boolean(item))
      .sort((a, b) => b.rawEdgeCount - a.rawEdgeCount || a.node.label.localeCompare(b.node.label, "zh-Hans-CN"));
  }, [aggregatedVisibleEdges, focusNodeId, graph.nodeById, neighborhood.oneHopNodeIds]);

  const twoHopItems = useMemo<NeighborListItem[]>(() => {
    if (!focusNodeId || focusDepth < 2) return [];
    return [...neighborhood.twoHopNodeIds]
      .map((nodeId) => {
        const node = graph.nodeById.get(nodeId);
        if (!node) return null;
        const edges = aggregatedVisibleEdges.filter((edge) => {
          const sourceOneHop = neighborhood.oneHopNodeIds.has(edge.source) && edge.target === nodeId;
          const targetOneHop = neighborhood.oneHopNodeIds.has(edge.target) && edge.source === nodeId;
          return sourceOneHop || targetOneHop;
        });
        const viaId = edges[0] ? (edges[0].source === nodeId ? edges[0].target : edges[0].source) : undefined;
        return {
          node,
          viaNode: viaId ? graph.nodeById.get(viaId) : undefined,
          relationTypes: [...new Set(edges.flatMap((edge) => edge.relationTypes))],
          rawEdgeCount: edges.reduce((sum, edge) => sum + edge.rawEdgeCount, 0),
          evidenceCount: edges.reduce((sum, edge) => sum + edge.evidenceCount, 0),
        };
      })
      .filter((item): item is NeighborListItem => Boolean(item))
      .sort((a, b) => b.rawEdgeCount - a.rawEdgeCount || a.node.label.localeCompare(b.node.label, "zh-Hans-CN"));
  }, [aggregatedVisibleEdges, focusDepth, focusNodeId, graph.nodeById, neighborhood.oneHopNodeIds, neighborhood.twoHopNodeIds]);


  function toggleSetValue(setter: (updater: (previous: Set<string>) => Set<string>) => void, value: string) {
    setter((previous) => {
      const next = new Set(previous);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  function closeFilters() {
    setRelationFilterOpen(false);
    setTypeFilterOpen(false);
  }

  function neighborhoodNodeIds(nodeId: string, depth: FocusDepth): Set<string> {
    return collectNeighborhood(nodeId, graph, relationFilters, typeFilters, evidenceOnly, depth).nodeIds;
  }

  function focusNeighborhood(nodeId: string, depth: 1 | 2 = 1, options: { nextMode?: GraphMode; screenshot?: boolean; only?: boolean } = {}) {
    const next = new Set(visibleNodeIds);
    neighborhoodNodeIds(nodeId, depth).forEach((id) => next.add(id));
    setVisibleNodeIds(next);
    setSelectedNodeId(nodeId);
    setFocusNodeId(nodeId);
    setFocusDepth(depth);
    setSelectedEdgeId(null);
    setGraphMode(options.nextMode ?? "expanded");
    setScreenshotMode(Boolean(options.screenshot));
    setNeighborhoodOnly(Boolean(options.only));
    closeFilters();
  }

  function expandNode(nodeId: string, depth: 1 | 2 = 1) {
    focusNeighborhood(nodeId, depth, { nextMode: "expanded", only: neighborhoodOnly });
  }

  function applyReportMode() {
    const initial = getInitialNodeIds(graph.nodes, graph.edges);
    const focusId = getDefaultSelectedNodeId(graph.nodes, graph.edges) ?? [...initial][0] ?? graph.nodes[0]?.id ?? null;
    const next = new Set(initial);
    if (focusId) collectNeighborhood(focusId, graph, new Set(getDefaultRelationTypes(graph.relationTypes)), new Set(graph.entityTypes), false, 1).nodeIds.forEach((id) => next.add(id));
    setVisibleNodeIds(next);
    setSelectedNodeId(focusId);
    setFocusNodeId(focusId);
    setFocusDepth(1);
    setSelectedEdgeId(null);
    setEvidenceOnly(false);
    setShowEdgeLabels(false);
    setRelationFilters(new Set(getDefaultRelationTypes(graph.relationTypes)));
    setTypeFilters(new Set(graph.entityTypes));
    setGraphMode("core");
    setZoom(0.96);
    setScreenshotMode(false);
    setNeighborhoodOnly(false);
    closeFilters();
  }

  function applyExploreMode() {
    setSelectedEdgeId(null);
    setGraphMode("expanded");
    setZoom(1);
    setScreenshotMode(false);
    if (selectedNodeId && focusDepth === 0) focusNeighborhood(selectedNodeId, 1, { nextMode: "expanded", only: neighborhoodOnly });
    closeFilters();
  }

  function resetGraph() {
    applyReportMode();
  }

  function showAllGraph() {
    setVisibleNodeIds(new Set(graph.nodes.map((node) => node.id)));
    setSelectedEdgeId(null);
    setGraphMode("full");
    setShowEdgeLabels(false);
    setZoom(0.82);
    setScreenshotMode(false);
    setNeighborhoodOnly(false);
    closeFilters();
  }

  function collapseCurrent() {
    if (!selectedNodeId) return;
    focusNeighborhood(selectedNodeId, 1, { nextMode: "expanded", only: neighborhoodOnly });
  }

  function selectSearchResult(nodeId: string) {
    setSearchKeyword("");
    focusNeighborhood(nodeId, 1, { nextMode: "expanded", only: neighborhoodOnly });
  }

  function toggleNeighborhoodOnly() {
    const focusId = selectedNodeId ?? defaultSelectedNodeId ?? graph.nodes[0]?.id ?? null;
    if (!focusId) return;
    if (neighborhoodOnly) {
      setNeighborhoodOnly(false);
      setScreenshotMode(false);
      return;
    }
    focusNeighborhood(focusId, focusDepth || 1, { nextMode: graphMode === "full" ? "expanded" : graphMode, only: true });
  }

  function toggleScreenshotMode() {
    if (screenshotMode) {
      applyReportMode();
      return;
    }
    const focusId = selectedNodeId ?? defaultSelectedNodeId ?? [...initialNodeIds][0] ?? graph.nodes[0]?.id ?? null;
    if (!focusId) return;
    closeFilters();
    setEvidenceOnly(false);
    setShowEdgeLabels(false);
    setZoom(1.04);
    focusNeighborhood(focusId, 2, { nextMode: "core", screenshot: true, only: true });
  }

  function enable3DView() {
    setViewMode("3d");
    setRotationX(DEFAULT_ROTATION_X);
    setRotationY(DEFAULT_ROTATION_Y);
  }

  function enableFlatView() {
    setViewMode("2d");
    setAutoRotate(false);
  }

  function rotateView(deltaX: number, deltaY: number) {
    setViewMode("3d");
    setAutoRotate(false);
    setRotationX((value) => clampViewValue(value + deltaX, -45, 45));
    setRotationY((value) => clampViewValue(value + deltaY, -60, 60));
  }

  function resetViewAngle() {
    setViewMode("3d");
    setAutoRotate(false);
    setRotationX(DEFAULT_ROTATION_X);
    setRotationY(DEFAULT_ROTATION_Y);
    setZoom(1);
  }

  function toggleAutoRotate() {
    setViewMode("3d");
    setAutoRotate((value) => !value);
  }

  function handleCanvasMouseDown(event: MouseEvent<SVGSVGElement>) {
    if (event.button !== 0) return;
    dragStartRef.current = {
      active: true,
      x: event.clientX,
      y: event.clientY,
      rotationX,
      rotationY,
    };
    dragMovedRef.current = false;
    setAutoRotate(false);
  }

  function handleCanvasMouseMove(event: MouseEvent<SVGSVGElement>) {
    const drag = dragStartRef.current;
    if (!drag.active) return;
    const deltaX = event.clientX - drag.x;
    const deltaY = event.clientY - drag.y;
    if (Math.hypot(deltaX, deltaY) > 5) {
      dragMovedRef.current = true;
      setIsDraggingView(true);
      setViewMode("3d");
      setRotationY(clampViewValue(drag.rotationY + deltaX * 0.18, -60, 60));
      setRotationX(clampViewValue(drag.rotationX - deltaY * 0.12, -45, 45));
    }
  }

  function stopCanvasDrag() {
    dragStartRef.current.active = false;
    setIsDraggingView(false);
  }

  function handleCanvasWheel(event: WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    const nextDelta = event.deltaY > 0 ? -0.05 : 0.05;
    setZoom((value) => clampViewValue(value + nextDelta, 0.72, 1.34));
  }

  const modeLabel = screenshotMode ? "汇报截图模式" : graphMode === "core" ? "汇报模式" : graphMode === "expanded" ? "探索模式" : "全量模式";
  const neighborhoodLabel = focusDepth === 2 ? "两跳" : focusDepth === 1 ? "一跳" : "未展开";
  const relatedNodeCount = neighborhood.oneHopNodeIds.size + neighborhood.twoHopNodeIds.size;
  const unrelatedStatus = neighborhoodOnly || screenshotMode ? "已隐藏" : "已弱化";
  const activeFilter = relationFilterOpen ? "relation" : typeFilterOpen ? "type" : null;

  return (
    <section className={`panel interactive-graph-shell refined-graph-shell ${graphMode === "core" ? "report-mode" : graphMode === "expanded" ? "explore-mode" : "full-mode dense-mode"} ${screenshotMode ? "screenshot-mode" : ""} ${neighborhoodOnly ? "neighborhood-only" : ""} ${is3DView ? "three-d-mode" : "flat-view-mode"} ${isDraggingView ? "dragging-view" : ""} focus-depth-${focusDepth}`}>
      <div className="panel-title graph-title-row refined-title-row">
        <div>
          <span className="eyebrow">交互式 GraphRAG 图谱</span>
          <h2>地震灾害 AI 关键技术图谱汇报视图</h2>
          <p>{screenshotMode ? "当前为汇报截图模式：已隐藏弱关系和边标签。" : "点击节点可展开其相关技术、模型、数据、任务、案例与证据边。立体视图通过前后层级区分 AI 技术、模型数据、案例政策和证据来源，可拖拽旋转查看图谱结构。"}</p>
        </div>
        <div className="graph-live-stats compact-stats">
          <span>当前模式</span><strong>{modeLabel}</strong>
          <span>布局方式</span><strong>{layoutLabel}</strong>
          <span>视图</span><strong>{viewLabel}</strong>
          <span>旋转角度</span><strong>X {displayAngle(rotationX)} / Y {displayAngle(rotationY)}</strong>
          <span>当前邻域</span><strong>{neighborhoodLabel}</strong>
          <span>已关联节点</span><strong>{relatedNodeCount}</strong>
          <span>聚合关系</span><strong>{focusRelationEdges.length || aggregatedVisibleEdges.length}</strong>
          <span>原始关系</span><strong>{visibleEdges.length}</strong>
          <span>无关节点</span><strong>{unrelatedStatus}</strong>
        </div>
      </div>

      <div className="compact-control-zone">
        <div className="control-row primary-control-row">
          <div className="graph-search compact-search">
            <label htmlFor="graph-search-input">搜索节点</label>
            <input
              id="graph-search-input"
              onChange={(event) => setSearchKeyword(event.target.value)}
              placeholder="搜索技术、模型、任务或案例"
              value={searchKeyword}
            />
            {searchResults.length ? (
              <div className="search-results refined-search-results">
                {searchResults.map((node) => (
                  <button key={node.id} onClick={() => selectSearchResult(node.id)} type="button">
                    <strong>{node.label}</strong>
                    <span>{visualFor(node.type).label}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          <div className="graph-actions compact-actions">
            <button className={graphMode === "core" ? "active" : ""} onClick={applyReportMode} type="button">汇报模式</button>
            <button className={graphMode === "expanded" ? "active" : ""} onClick={applyExploreMode} type="button">探索模式</button>
            <button className={graphMode === "full" ? "active" : ""} onClick={showAllGraph} type="button">全量模式</button>
            <button className={screenshotMode ? "active screenshot-action" : "screenshot-action"} onClick={toggleScreenshotMode} type="button">汇报截图模式</button>
            <button disabled={!selectedNodeId} onClick={() => selectedNodeId && expandNode(selectedNodeId, 1)} type="button">展开一跳</button>
            <button disabled={!selectedNodeId} onClick={() => selectedNodeId && expandNode(selectedNodeId, 2)} type="button">展开两跳</button>
            <button disabled={!selectedNodeId} onClick={collapseCurrent} type="button">收起到当前节点</button>
            <button onClick={resetGraph} type="button">重置视图</button>
            <button className={neighborhoodOnly ? "active" : ""} disabled={!selectedNodeId} onClick={toggleNeighborhoodOnly} type="button">只看当前邻域</button>
            <button onClick={() => setZoom((value) => Math.min(1.25, value + 0.08))} type="button">放大</button>
            <button onClick={() => setZoom((value) => Math.max(0.78, value - 0.08))} type="button">缩小</button>
            <button onClick={() => setZoom(1)} type="button">适应画布</button>
          </div>
        </div>

        <div className="control-row view-control-row">
          <span className="view-control-label">视角控制</span>
          <button className={is3DView ? "toggle-button active" : "toggle-button"} onClick={enable3DView} type="button">立体视图</button>
          <button className={!is3DView ? "toggle-button active" : "toggle-button"} onClick={enableFlatView} type="button">平面视图</button>
          <button onClick={() => rotateView(0, -15)} type="button">左旋</button>
          <button onClick={() => rotateView(0, 15)} type="button">右旋</button>
          <button onClick={() => rotateView(10, 0)} type="button">上俯</button>
          <button onClick={() => rotateView(-10, 0)} type="button">下仰</button>
          <button onClick={resetViewAngle} type="button">重置视角</button>
          <button className={autoRotate ? "toggle-button active" : "toggle-button"} onClick={toggleAutoRotate} type="button">自动旋转</button>
        </div>

        <div className="control-row secondary-control-row">
          <FilterPanel
            onToggleOpen={() => { setRelationFilterOpen((value) => !value); setTypeFilterOpen(false); }}
            open={relationFilterOpen}
            selected={relationFilters}
            title="关系类型"
            values={graph.relationTypes}
            formatValue={relationTypeLabel}
          />
          <FilterPanel
            onToggleOpen={() => { setTypeFilterOpen((value) => !value); setRelationFilterOpen(false); }}
            open={typeFilterOpen}
            selected={typeFilters}
            title="实体类型"
            values={graph.entityTypes}
            formatValue={(value) => visualFor(value).label}
          />
          <button className={evidenceOnly ? "toggle-button active" : "toggle-button"} onClick={() => setEvidenceOnly((value) => !value)} type="button">只看证据链</button>
          <button className={showEdgeLabels ? "toggle-button active" : "toggle-button"} onClick={() => setShowEdgeLabels((value) => !value)} type="button">显示关系标签</button>
          <button className="toggle-button" onClick={() => setLabelMode((value) => (value === "compact" ? "full" : "compact"))} type="button">
            标签{labelMode === "compact" ? "简洁" : "完整"}
          </button>
        </div>
        {activeFilter ? (
          <FilterDrawer
            formatValue={activeFilter === "relation" ? relationTypeLabel : (value) => visualFor(value).label}
            onClearAll={() => activeFilter === "relation" ? setRelationFilters(new Set()) : setTypeFilters(new Set())}
            onClose={closeFilters}
            onSelectAll={() => activeFilter === "relation" ? setRelationFilters(new Set(graph.relationTypes)) : setTypeFilters(new Set(graph.entityTypes))}
            onToggleValue={(value) => activeFilter === "relation" ? toggleSetValue(setRelationFilters, value) : toggleSetValue(setTypeFilters, value)}
            selected={activeFilter === "relation" ? relationFilters : typeFilters}
            title={activeFilter === "relation" ? "关系类型" : "实体类型"}
            values={activeFilter === "relation" ? graph.relationTypes : graph.entityTypes}
          />
        ) : null}
      </div>

      {screenshotMode ? (
        <div className="screenshot-mode-banner">当前为汇报截图模式：已隐藏弱关系和边标签。</div>
      ) : null}
      {graphMode === "full" ? (
        <div className="dense-mode-banner">当前为全量图谱模式，已启用单画布软分区布局与边聚合以降低视觉密度。</div>
      ) : null}

      <div className="interactive-graph-grid refined-graph-grid">
        <div className="graph-canvas-card refined-canvas-card">
          <div className="graph-canvas-meta refined-canvas-meta">
            <span>{modeLabel}</span>
            <span>布局方式：{layoutLabel}</span>
            <span>视图：{viewLabel}</span>
            <span>旋转角度：X {displayAngle(rotationX)} / Y {displayAngle(rotationY)}</span>
            <span>当前邻域：{neighborhoodLabel}</span>
            <span>已关联节点 {relatedNodeCount}</span>
            <span>聚合关系 {focusRelationEdges.length}/{aggregatedVisibleEdges.length}</span>
            <span>关键边 {keyEdgeIds.size}</span>
            <span>边标签 {showEdgeLabels ? "开启" : "关闭"}</span>
            <span>无关节点 {unrelatedStatus}</span>
          </div>
          <svg
            className={`expandable-graph-svg refined-graph-svg ${is3DView ? "three-d-graph-svg" : "flat-graph-svg"}`}
            onClick={() => {
              if (dragMovedRef.current) {
                dragMovedRef.current = false;
                return;
              }
              setSelectedEdgeId(null);
              closeFilters();
            }}
            onMouseDown={handleCanvasMouseDown}
            onMouseLeave={stopCanvasDrag}
            onMouseMove={handleCanvasMouseMove}
            onMouseUp={stopCanvasDrag}
            onWheel={handleCanvasWheel}
            role="img"
            viewBox={`0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`}
            aria-label="可展开地震灾害AI关键技术图谱"
          >
            <defs>
              <marker id="atlas-arrow-blue" markerHeight="5" markerWidth="5" orient="auto" refX="4" refY="2.5" viewBox="0 0 5 5">
                <path d="M0,0 L5,2.5 L0,5 Z" fill="#2563EB" />
              </marker>
              <marker id="atlas-arrow-red" markerHeight="6" markerWidth="6" orient="auto" refX="5" refY="3" viewBox="0 0 6 6">
                <path d="M0,0 L6,3 L0,6 Z" fill="#DC2626" />
              </marker>
            </defs>
            <g className="graph-zoom-layer" transform={`translate(${CANVAS_CENTER_X} ${CANVAS_CENTER_Y}) scale(${zoom}) translate(${-CANVAS_CENTER_X} ${-CANVAS_CENTER_Y})`}>
              <g className="cluster-aura-layer" aria-hidden="true">
                {visibleClusterAuras.map((region) => {
                  const aura = getClusterAura(region, CANVAS_WIDTH, CANVAS_HEIGHT);
                  return (
                    <g className={`cluster-aura cluster-aura-${region.id}`} key={region.id}>
                      <ellipse cx={aura.cx} cy={aura.cy} fill={aura.tint} rx={aura.rx} ry={aura.ry} />
                      <text x={aura.titleX} y={aura.titleY}>{region.label}</text>
                    </g>
                  );
                })}
              </g>
              <g className="atlas-edges refined-edges aggregated-edges">
                {edgeRenderItems.map((item) => {
                  const path = edgePath(item.edge, item.source, item.target, item.sourceRadius, item.targetRadius);
                  const background = item.unrelated;
                  const showLabel = !screenshotMode && (item.selected || item.hovered || showEdgeLabels || (item.keyEdge && item.oneHopEdge));
                  const midX = (item.source.x + item.target.x) / 2;
                  const midY = (item.source.y + item.target.y) / 2;
                  const label = aggregatedEdgeLabel(item.edge);
                  const labelWidth = Math.max(76, label.length * 7 + 18);
                  const showCountBadge = item.selected || item.hovered;
                  return (
                    <g key={item.edge.id} className={`${item.selected ? "selected-aggregate-edge" : ""} ${item.incident ? "incident-aggregate-edge" : ""} ${item.oneHopEdge ? "one-hop-aggregate-edge" : ""} ${item.twoHopEdge ? "two-hop-aggregate-edge" : ""} ${item.keyEdge ? "key-aggregate-edge" : ""} ${background ? "background-aggregate-edge" : ""}`}>
                      <path
                        className={`${item.selected ? "selected" : ""} ${item.incident ? "incident" : ""} ${item.oneHopEdge ? "focus-one-hop" : ""} ${item.twoHopEdge ? "focus-two-hop" : ""} ${item.keyEdge ? "key" : ""} ${background ? "background unrelated" : ""} ${item.hovered ? "hovered" : ""}`}
                        d={path}
                        markerEnd={item.selected ? "url(#atlas-arrow-red)" : item.keyEdge || item.hovered || item.oneHopEdge ? "url(#atlas-arrow-blue)" : undefined}
                        onClick={(event) => {
                          event.stopPropagation();
                          setSelectedEdgeId(item.edge.id);
                        }}
                        onMouseEnter={() => setHoveredEdgeId(item.edge.id)}
                        onMouseLeave={() => setHoveredEdgeId(null)}
                        style={{ opacity: item.opacity, strokeWidth: item.strokeWidth }}
                      />
                      {showLabel ? (
                        <g className={`edge-label-badge ${item.selected ? "selected" : ""}`} opacity={Math.max(0.42, item.opacity)} transform={`translate(${midX} ${midY - 11})`}>
                          <rect height="20" rx="6" width={labelWidth} x={-labelWidth / 2} y="-13" />
                          <text y="1">{label}</text>
                        </g>
                      ) : null}
                      {showCountBadge ? (
                        <g className={`edge-count-badge ${item.selected ? "selected" : ""}`} transform={`translate(${midX} ${midY + 13})`}>
                          <circle r="12" />
                          <text y="4">×{item.edge.rawEdgeCount}</text>
                        </g>
                      ) : null}
                    </g>
                  );
                })}
              </g>
              <g className="atlas-nodes refined-nodes">
                {nodeRenderItems.map((item) => {
                  const { node, point, selected, oneHop, twoHop, linked, unrelated, hovered, radius, circleOpacity, labelOpacity } = item;
                  const visual = visualFor(node.type);
                  const captionLines = splitCaption(node.label, labelMode);
                  const depthShadowY = Math.max(4, radius * 0.42);
                  const depthShadowRx = Math.max(8, radius * 0.78);
                  const depthShadowRy = Math.max(3, radius * 0.22);
                  return (
                    <g
                      key={node.id}
                      className={`atlas-node refined-node ${selected ? "selected" : ""} ${linked ? "linked" : ""} ${oneHop ? "focus-one-hop" : ""} ${twoHop ? "focus-two-hop" : ""} ${unrelated ? "unrelated" : ""} ${hovered ? "hovered" : ""}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        if (dragMovedRef.current) {
                          dragMovedRef.current = false;
                          return;
                        }
                        expandNode(node.id, 1);
                      }}
                      onMouseEnter={() => setHoveredNodeId(node.id)}
                      onMouseLeave={() => setHoveredNodeId(null)}
                      role="button"
                      tabIndex={0}
                      transform={`translate(${point.x} ${point.y})`}
                    >
                      <title>{`${node.label} · ${visualFor(node.type).label} · Z ${zDepthForType(node.type)} · 关联 ${getNodeDegree(node.id, adjacency)}`}</title>
                      {is3DView ? (
                        <ellipse
                          className="node-depth-shadow"
                          cx="0"
                          cy={depthShadowY}
                          opacity={point.shadowOpacity}
                          rx={depthShadowRx}
                          ry={depthShadowRy}
                        />
                      ) : null}
                      <circle
                        fill={visual.fill}
                        opacity={circleOpacity}
                        r={radius}
                        stroke={visual.stroke}
                        style={is3DView ? { filter: `drop-shadow(0 ${Math.max(2, point.screenScale * 4)}px ${Math.max(4, point.screenScale * 8)}px rgba(15, 23, 42, ${point.shadowOpacity}))` } : undefined}
                      />
                      <text className="node-core-label" opacity={Math.max(0.5, labelOpacity)} y="4">{coreLabel(node.label)}</text>
                      <text className="node-caption" opacity={labelOpacity} y={radius + 18}>
                        {captionLines.map((line, index) => (
                          <tspan key={`${node.id}-${line}-${index}`} x="0" y={radius + 18 + index * 13}>{line}</tspan>
                        ))}
                      </text>
                    </g>
                  );
                })}
              </g>
            </g>
          </svg>
        </div>

        <SidePanel
          adjacency={adjacency}
          aggregatedVisibleEdges={aggregatedVisibleEdges}
          focusDepth={focusDepth}
          focusRelationEdges={focusRelationEdges}
          graph={graph}
          oneHopItems={oneHopItems}
          onCollapse={collapseCurrent}
          onExpandMore={() => selectedNodeId && expandNode(selectedNodeId, 2)}
          onExpandOne={() => selectedNodeId && expandNode(selectedNodeId, 1)}
          onReset={resetGraph}
          onSelectNeighbor={(nodeId) => focusNeighborhood(nodeId, 1, { nextMode: "expanded", only: neighborhoodOnly })}
          selectedEdge={selectedEdge}
          selectedNode={selectedNode}
          twoHopItems={twoHopItems}
          visibleNodeIds={effectiveVisibleNodeIds}
          screenshotMode={screenshotMode}
          viewMode={viewMode}
          rotationX={rotationX}
          rotationY={rotationY}
        />
      </div>
    </section>
  );
}

export default function ExpandableGraph({ snapshot }: ExpandableGraphProps) {
  const [fallbackGraph, setFallbackGraph] = useState<unknown | null>(null);

  useEffect(() => {
    let alive = true;
    fetch("/atlas/graph_visualization.json", { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`graph_visualization ${response.status}`);
        return response.json() as Promise<unknown>;
      })
      .then((data) => {
        if (alive) setFallbackGraph(data);
      })
      .catch(() => {
        if (alive) setFallbackGraph(null);
      });
    return () => {
      alive = false;
    };
  }, []);

  const graph = useMemo(() => normalizeAtlasData(snapshot, fallbackGraph), [snapshot, fallbackGraph]);
  const graphKey = `${graph.nodes.length}:${graph.edges.length}:${graph.relationTypes.join("|")}:${graph.entityTypes.join("|")}`;

  if (!graph.nodes.length) {
    return (
      <section className="panel interactive-graph-shell refined-graph-shell">
        <div className="panel-title">
          <span className="eyebrow">交互图谱</span>
          <h2>交互图谱数据未就绪</h2>
          <p>页面已加载，但当前快照未提供可绘制的节点与边。请先运行前端发布命令生成完整快照。</p>
        </div>
      </section>
    );
  }

  return <ExpandableGraphWorkspace key={graphKey} graph={graph} />;
}










