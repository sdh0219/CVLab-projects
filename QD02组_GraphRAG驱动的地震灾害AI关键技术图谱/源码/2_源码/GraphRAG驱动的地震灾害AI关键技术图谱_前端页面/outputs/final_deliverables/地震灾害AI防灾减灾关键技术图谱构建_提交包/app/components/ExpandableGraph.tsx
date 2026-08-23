"use client";

import { useEffect, useMemo, useState } from "react";
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
  aggregateEdges,
  buildAdjacency,
  collapseToNodeIds,
  computeGraphLayout,
  expandNodeIds,
  getDefaultRelationTypes,
  getDefaultSelectedNodeId,
  getFilteredVisibleEdges,
  getInitialNodeIds,
  getNodeDegree,
  rankAdjacencyItems,
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

const TYPE_VISUALS: Record<string, TypeVisual> = {
  DisasterType: { label: "灾害类型", fill: "#0B1F4D", stroke: "#1D4ED8", tint: "#DBEAFE" },
  AITech: { label: "AI技术", fill: "#1D4ED8", stroke: "#2563EB", tint: "#DBEAFE" },
  Scenario: { label: "应用场景", fill: "#2563EB", stroke: "#3B82F6", tint: "#EFF6FF" },
  Task: { label: "任务", fill: "#0369A1", stroke: "#0284C7", tint: "#E0F2FE" },
  Dataset: { label: "数据集", fill: "#0EA5E9", stroke: "#0284C7", tint: "#E0F2FE" },
  Model: { label: "模型", fill: "#60A5FA", stroke: "#3B82F6", tint: "#EFF6FF" },
  Case: { label: "案例", fill: "#7C3AED", stroke: "#7C3AED", tint: "#F3E8FF" },
  Policy: { label: "政策标准", fill: "#475569", stroke: "#64748B", tint: "#F1F5F9" },
  Limitation: { label: "限制", fill: "#DC2626", stroke: "#DC2626", tint: "#FEF2F2" },
  Unknown: { label: "未知", fill: "#64748B", stroke: "#64748B", tint: "#F1F5F9" },
};

const BASE_CANVAS_EDGE_LIMIT = 140;
const FULL_CANVAS_EDGE_LIMIT = 360;
const FOCUSED_KEY_EDGE_LIMIT = 5;
const REPORT_EDGE_LABEL_LIMIT = 3;
const KEY_EDGE_RELATION_PRIORITY = ["VALIDATED_IN", "SOLVES", "DEPENDS_ON", "USES_MODEL", "SERVES_STAGE"];
const RELATION_LABELS: Record<string, string> = {
  APPLIES_TO: "适用于",
  SERVES_STAGE: "服务阶段",
  SOLVES: "解决任务",
  DEPENDS_ON: "依赖数据",
  USES_MODEL: "采用模型",
  VALIDATED_IN: "案例验证",
  LIMITED_BY: "受限于",
  REQUIRED_BY: "政策要求",
};

function relationTypeLabel(type: string): string {
  return RELATION_LABELS[type] ? `${type}（${RELATION_LABELS[type]}）` : type;
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
  if (/GraphRAG/i.test(label)) {
    const prefix = label.replace(/GraphRAG/gi, "").trim();
    return [compactText(prefix, 10), "GraphRAG"];
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
  const bend = ((hash % 7) - 3) * 8;
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
  if (edge.relationTypes.length <= 1) {
    return edge.rawEdgeCount > 1 ? `${edge.primaryRelationType} ×${edge.rawEdgeCount}` : edge.primaryRelationType;
  }
  return `${edge.primaryRelationType} 等 ${edge.relationTypes.length} 类`;
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

function StatusBadge({ value }: { value: string }) {
  const text = displayValue(value, "待复核");
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
  onToggleValue,
  onSelectAll,
  onClearAll,
  formatValue = (value: string) => value,
}: {
  title: string;
  values: string[];
  selected: Set<string>;
  open: boolean;
  onToggleOpen: () => void;
  onToggleValue: (value: string) => void;
  onSelectAll: () => void;
  onClearAll: () => void;
  formatValue?: (value: string) => string;
}) {
  return (
    <div className="filter-panel">
      <button className="filter-summary-button" onClick={onToggleOpen} type="button">
        <span>{title}</span>
        <strong>{selected.size}/{values.length}</strong>
      </button>
      {open ? (
        <div className="filter-popover">
          <div className="filter-mini-actions">
            <button onClick={onSelectAll} type="button">全部选择</button>
            <button onClick={onClearAll} type="button">全部清除</button>
          </div>
          <div className="filter-chip-grid">
            {values.map((value) => (
              <button className={selected.has(value) ? "selected" : ""} key={value} onClick={() => onToggleValue(value)} type="button">
                {formatValue(value)}
              </button>
            ))}
          </div>
        </div>
      ) : null}
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
              {confidenceLabel(rawEdge.confidence)} · {rawEdge.docId || "未提供 doc_id"} · {rawEdge.chunkId || "未提供 chunk_id"} · {rawEdge.reviewStatus === "pending" ? "待复核" : rawEdge.reviewStatus || "待复核"}
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
  focusedKeyEdges,
  visibleNodeIds,
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
  focusedKeyEdges: AggregatedGraphEdge[];
  visibleNodeIds: Set<string>;
  onExpandOne: () => void;
  onExpandMore: () => void;
  onCollapse: () => void;
  onReset: () => void;
  onSelectNeighbor: (nodeId: string) => void;
}) {
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
  const hiddenNeighborCount = rankedNeighbors.filter((item) => !visibleNodeIds.has(item.nodeId)).length;
  const incidentAggregatedEdges = node ? aggregatedVisibleEdges.filter((edge) => edge.source === node.id || edge.target === node.id) : [];
  const rawIncidentEdges = node ? graph.edges.filter((edge) => edge.source === node.id || edge.target === node.id) : [];
  const evidenceEdges = selectedEdge
    ? selectedEdge.rawEdges
    : node
      ? rankAdjacencyItems(adjacency.get(node.id) ?? [], graph.nodeById).map((item) => item.edge)
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
              <StatusBadge value={selectedEdge.reviewStatuses.map((status) => status === "pending" ? "待复核" : status).join(" / ") || "待复核"} />
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
            </div>
          </>
        ) : null}
      </section>

      <section className="detail-section action-card">
        <span className="eyebrow">操作</span>
        <div className="side-action-grid">
          <button disabled={!node} onClick={onExpandOne} type="button">展开一跳</button>
          <button disabled={!node || !hiddenNeighborCount} onClick={onExpandMore} type="button">展开更多</button>
          <button disabled={!node} onClick={onCollapse} type="button">收起到当前节点</button>
          <button onClick={onReset} type="button">重置视图</button>
        </div>
        {hiddenNeighborCount ? <p className="hidden-neighbor-note">还有 {hiddenNeighborCount} 个相关节点未展开。</p> : null}
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

      {node && focusedKeyEdges.length ? (
        <section className="detail-section focused-edge-card">
          <span className="eyebrow">关键关系前五</span>
          <div className="focused-edge-list">
            {focusedKeyEdges.map((edge) => (
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
          <span className="eyebrow">邻居预览</span>
          <h3>下一步可展开节点</h3>
          <div className="neighbor-list compact-neighbor-list">
            {rankedNeighbors.slice(0, 6).map((item) => {
              const neighbor = graph.nodeById.get(item.nodeId);
              if (!neighbor) return null;
              return (
                <button key={neighbor.id} onClick={() => onSelectNeighbor(neighbor.id)} type="button">
                  <strong>{neighbor.label}</strong>
                  <span>{visualFor(neighbor.type).label} · {relationTypeLabel(item.edge.relationType)}</span>
                  <em>{item.edge.evidenceText || item.edge.docId ? "有证据" : "待补证"}</em>
                </button>
              );
            })}
          </div>
        </section>
      ) : null}

      <section className="detail-section evidence-detail">
        <span className="eyebrow">证据片段</span>
        <div className="evidence-stack">
          {evidenceSnippets.length ? evidenceSnippets.map((edge) => (
            <article key={edge.id}>
              <strong>{relationTypeLabel(edge.relationType)}</strong>
              <span>{edge.sourceName || edge.docId || "未提供来源"} · {confidenceLabel(edge.confidence)} · {edge.reviewStatus === "pending" ? "待复核" : edge.reviewStatus || "待复核"}</span>
              <p>{edge.evidenceText ? compactText(edge.evidenceText, 118) : "当前边未提供证据片段"}</p>
            </article>
          )) : <p>当前选择暂未提供可展示证据片段。</p>}
        </div>
      </section>
    </aside>
  );
}

function ExpandableGraphWorkspace({ graph }: { graph: NormalizedAtlasGraph }) {
  const initialNodeIds = useMemo(() => getInitialNodeIds(graph.nodes, graph.edges), [graph.nodes, graph.edges]);
  const defaultSelectedNodeId = useMemo(() => getDefaultSelectedNodeId(graph.nodes, graph.edges), [graph.nodes, graph.edges]);
  const defaultRelationFilterValues = useMemo(() => getDefaultRelationTypes(graph.relationTypes), [graph.relationTypes]);
  const [visibleNodeIds, setVisibleNodeIds] = useState<Set<string>>(() => initialNodeIds);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(() => defaultSelectedNodeId ?? [...initialNodeIds][0] ?? graph.nodes[0]?.id ?? null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(new Set());
  const [relationFilters, setRelationFilters] = useState<Set<string>>(() => new Set(defaultRelationFilterValues));
  const [typeFilters, setTypeFilters] = useState<Set<string>>(() => new Set(graph.entityTypes));
  const [searchKeyword, setSearchKeyword] = useState("");
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const [evidenceOnly, setEvidenceOnly] = useState(false);
  const [showEdgeLabels, setShowEdgeLabels] = useState(false);
  const [labelMode, setLabelMode] = useState<LabelMode>("compact");
  const [graphMode, setGraphMode] = useState<GraphMode>("core");
  const [relationFilterOpen, setRelationFilterOpen] = useState(false);
  const [typeFilterOpen, setTypeFilterOpen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const adjacency = useMemo(() => buildAdjacency(graph.nodes, graph.edges), [graph.nodes, graph.edges]);

  const selectedNode = selectedNodeId ? graph.nodeById.get(selectedNodeId) ?? null : null;


  const visibleNodes = useMemo(
    () => graph.nodes.filter((node) => visibleNodeIds.has(node.id) && typeFilters.has(node.type)),
    [graph.nodes, typeFilters, visibleNodeIds],
  );

  const visibleEdges = useMemo(
    () => getFilteredVisibleEdges(graph.edges, visibleNodeIds, graph.nodeById, relationFilters, typeFilters, evidenceOnly),
    [evidenceOnly, graph.edges, graph.nodeById, relationFilters, typeFilters, visibleNodeIds],
  );

  const aggregatedVisibleEdges = useMemo(() => aggregateEdges(visibleEdges), [visibleEdges]);
  const selectedEdge = selectedEdgeId ? aggregatedVisibleEdges.find((edge) => edge.id === selectedEdgeId) ?? null : null;

  const canvasEdges = useMemo(
    () => sortAggregatedEdges(aggregatedVisibleEdges, selectedNodeId).slice(0, graphMode === "full" ? FULL_CANVAS_EDGE_LIMIT : BASE_CANVAS_EDGE_LIMIT),
    [aggregatedVisibleEdges, graphMode, selectedNodeId],
  );

  const layout = useMemo(() => computeGraphLayout(visibleNodes, canvasEdges, selectedNodeId), [canvasEdges, selectedNodeId, visibleNodes]);

  const searchResults = useMemo(() => {
    const keyword = searchKeyword.trim().toLowerCase();
    if (!keyword) return [];
    return graph.nodes
      .filter((node) => `${node.label} ${node.id} ${node.type}`.toLowerCase().includes(keyword))
      .sort((a, b) => getNodeDegree(b.id, adjacency) - getNodeDegree(a.id, adjacency))
      .slice(0, 8);
  }, [adjacency, graph.nodes, searchKeyword]);

  const selectedIncidentEdges = useMemo(() => {
    if (!selectedNodeId) return new Set<string>();
    return new Set(aggregatedVisibleEdges.filter((edge) => edge.source === selectedNodeId || edge.target === selectedNodeId).map((edge) => edge.id));
  }, [aggregatedVisibleEdges, selectedNodeId]);

  const focusedKeyEdges = useMemo(() => getFocusedKeyEdges(canvasEdges, selectedNodeId), [canvasEdges, selectedNodeId]);
  const keyEdgeIds = useMemo(() => new Set(focusedKeyEdges.map((edge) => edge.id)), [focusedKeyEdges]);
  const keyLabelEdgeIds = useMemo(() => new Set(focusedKeyEdges.slice(0, REPORT_EDGE_LABEL_LIMIT).map((edge) => edge.id)), [focusedKeyEdges]);


  function toggleSetValue(setter: (updater: (previous: Set<string>) => Set<string>) => void, value: string) {
    setter((previous) => {
      const next = new Set(previous);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  function expandNode(nodeId: string, depth: 1 | 2 = 1) {
    const next = expandNodeIds(nodeId, visibleNodeIds, adjacency, graph.nodeById, depth);
    setVisibleNodeIds(next);
    setSelectedNodeId(nodeId);
    setSelectedEdgeId(null);
    setExpandedNodeIds((previous) => new Set(previous).add(nodeId));
    setGraphMode("expanded");
  }

  function expandMoreForNode(nodeId: string) {
    const ranked = uniqueNeighborItems(rankAdjacencyItems(adjacency.get(nodeId) ?? [], graph.nodeById)).filter((item) => !visibleNodeIds.has(item.nodeId));
    const next = new Set(visibleNodeIds);
    ranked.slice(0, 8).forEach((item) => next.add(item.nodeId));
    setVisibleNodeIds(next);
    setSelectedNodeId(nodeId);
    setSelectedEdgeId(null);
    setExpandedNodeIds((previous) => new Set(previous).add(nodeId));
    setGraphMode("expanded");
  }

  function applyReportMode() {
    const initial = getInitialNodeIds(graph.nodes, graph.edges);
    setVisibleNodeIds(initial);
    setSelectedNodeId(getDefaultSelectedNodeId(graph.nodes, graph.edges) ?? [...initial][0] ?? graph.nodes[0]?.id ?? null);
    setSelectedEdgeId(null);
    setExpandedNodeIds(new Set());
    setEvidenceOnly(false);
    setShowEdgeLabels(false);
    setRelationFilters(new Set(getDefaultRelationTypes(graph.relationTypes)));
    setTypeFilters(new Set(graph.entityTypes));
    setGraphMode("core");
    setZoom(0.96);
  }

  function applyExploreMode() {
    setSelectedEdgeId(null);
    setGraphMode("expanded");
    setZoom(1);
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
  }

  function collapseCurrent() {
    if (!selectedNodeId) return;
    setVisibleNodeIds(collapseToNodeIds(selectedNodeId, adjacency, graph.nodeById));
    setSelectedEdgeId(null);
    setGraphMode("expanded");
  }

  function selectSearchResult(nodeId: string) {
    setSearchKeyword("");
    const next = expandNodeIds(nodeId, new Set(visibleNodeIds).add(nodeId), adjacency, graph.nodeById, 1);
    setVisibleNodeIds(next);
    setSelectedNodeId(nodeId);
    setSelectedEdgeId(null);
    setExpandedNodeIds((previous) => new Set(previous).add(nodeId));
    setGraphMode("expanded");
  }

  const modeLabel = graphMode === "core" ? "汇报模式" : graphMode === "expanded" ? "探索模式" : "全量模式";

  return (
    <section className={`panel interactive-graph-shell refined-graph-shell ${graphMode === "core" ? "report-mode" : graphMode === "expanded" ? "explore-mode" : "full-mode dense-mode"}`}>
      <div className="panel-title graph-title-row refined-title-row">
        <div>
          <span className="eyebrow">交互式 GraphRAG 图谱</span>
          <h2>地震灾害 AI 关键技术图谱汇报视图</h2>
          <p>默认进入汇报模式：隐藏高噪声关系标签，弱化 APPLIES_TO（适用于）背景关系，只突出当前技术节点的少量关键证据链。</p>
        </div>
        <div className="graph-live-stats compact-stats">
          <span>当前模式</span><strong>{modeLabel}</strong>
          <span>可见节点</span><strong>{visibleNodes.length}</strong>
          <span>可视化关系</span><strong>{aggregatedVisibleEdges.length}</strong>
          <span>原始关系</span><strong>{visibleEdges.length}</strong>
          <span>关键边</span><strong>{keyEdgeIds.size}</strong>
          <span>边标签</span><strong>{showEdgeLabels ? "开启" : "关闭"}</strong>
          <span>适用关系</span><strong>{relationFilters.has("APPLIES_TO") ? "显示" : "隐藏"}</strong>
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
            <button disabled={!selectedNodeId} onClick={() => selectedNodeId && expandNode(selectedNodeId, 1)} type="button">展开一跳</button>
            <button disabled={!selectedNodeId} onClick={() => selectedNodeId && expandNode(selectedNodeId, 2)} type="button">展开两跳</button>
            <button disabled={!selectedNodeId} onClick={collapseCurrent} type="button">收起到当前节点</button>
            <button onClick={resetGraph} type="button">重置视图</button>
            <button onClick={() => setZoom((value) => Math.min(1.25, value + 0.08))} type="button">放大</button>
            <button onClick={() => setZoom((value) => Math.max(0.78, value - 0.08))} type="button">缩小</button>
            <button onClick={() => setZoom(1)} type="button">适应画布</button>
          </div>
        </div>

        <div className="control-row secondary-control-row">
          <FilterPanel
            onClearAll={() => setRelationFilters(new Set())}
            onSelectAll={() => setRelationFilters(new Set(graph.relationTypes))}
            onToggleOpen={() => setRelationFilterOpen((value) => !value)}
            onToggleValue={(value) => toggleSetValue(setRelationFilters, value)}
            open={relationFilterOpen}
            selected={relationFilters}
            title="关系类型"
            values={graph.relationTypes}
            formatValue={relationTypeLabel}
          />
          <FilterPanel
            onClearAll={() => setTypeFilters(new Set())}
            onSelectAll={() => setTypeFilters(new Set(graph.entityTypes))}
            onToggleOpen={() => setTypeFilterOpen((value) => !value)}
            onToggleValue={(value) => toggleSetValue(setTypeFilters, value)}
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
      </div>

      {graphMode === "full" ? (
        <div className="dense-mode-banner">当前为全量图谱模式，关系密度较高；已启用边聚合并隐藏普通标签，建议通过筛选器查看局部证据链。</div>
      ) : null}

      <div className="interactive-graph-grid refined-graph-grid">
        <div className="graph-canvas-card refined-canvas-card">
          <div className="graph-canvas-meta refined-canvas-meta">
            <span>{modeLabel}</span>
            <span>聚合边 {canvasEdges.length}/{aggregatedVisibleEdges.length}</span>
            <span>关键边 {keyEdgeIds.size}</span>
            <span>边标签 {showEdgeLabels ? "开启" : "关闭"}</span>
            <span>适用关系 {relationFilters.has("APPLIES_TO") ? "显示" : "隐藏"}</span>
            <span>已展开 {expandedNodeIds.size}</span>
          </div>
          <svg className="expandable-graph-svg refined-graph-svg" onClick={() => setSelectedEdgeId(null)} role="img" viewBox="0 0 1100 760" aria-label="可展开地震灾害AI关键技术图谱">
            <defs>
              <marker id="atlas-arrow-blue" markerHeight="5" markerWidth="5" orient="auto" refX="4" refY="2.5" viewBox="0 0 5 5">
                <path d="M0,0 L5,2.5 L0,5 Z" fill="#2563EB" />
              </marker>
              <marker id="atlas-arrow-red" markerHeight="6" markerWidth="6" orient="auto" refX="5" refY="3" viewBox="0 0 6 6">
                <path d="M0,0 L6,3 L0,6 Z" fill="#DC2626" />
              </marker>
            </defs>
            <g className="graph-zoom-layer" transform={`translate(550 360) scale(${zoom}) translate(-550 -360)`}>
              <g className="atlas-edges refined-edges aggregated-edges">
                {canvasEdges.map((edge) => {
                  const source = layout.get(edge.source);
                  const target = layout.get(edge.target);
                  const sourceNode = graph.nodeById.get(edge.source);
                  const targetNode = graph.nodeById.get(edge.target);
                  if (!source || !target || !sourceNode || !targetNode) return null;
                  const sourceSelected = sourceNode.id === selectedNodeId;
                  const targetSelected = targetNode.id === selectedNodeId;
                  const sourceRadius = nodeRadius(sourceNode, sourceSelected, false);
                  const targetRadius = nodeRadius(targetNode, targetSelected, false);
                  const path = edgePath(edge, source, target, sourceRadius, targetRadius);
                  const selected = edge.id === selectedEdgeId;
                  const incident = selectedIncidentEdges.has(edge.id);
                  const hovered = edge.id === hoveredEdgeId;
                  const keyEdge = keyEdgeIds.has(edge.id);
                  const background = Boolean(selectedNodeId && !incident && !selected);
                  const showLabel = selected || hovered || showEdgeLabels || (graphMode === "core" && keyLabelEdgeIds.has(edge.id));
                  const midX = (source.x + target.x) / 2;
                  const midY = (source.y + target.y) / 2;
                  const label = aggregatedEdgeLabel(edge);
                  const labelWidth = Math.max(76, label.length * 7 + 18);
                  const showCountBadge = selected || hovered;
                  return (
                    <g key={edge.id} className={`${selected ? "selected-aggregate-edge" : ""} ${incident ? "incident-aggregate-edge" : ""} ${keyEdge ? "key-aggregate-edge" : ""} ${background ? "background-aggregate-edge" : ""}`}>
                      <path
                        className={`${selected ? "selected" : ""} ${incident ? "incident" : ""} ${keyEdge ? "key" : ""} ${background ? "background" : ""} ${hovered ? "hovered" : ""}`}
                        d={path}
                        markerEnd={selected ? "url(#atlas-arrow-red)" : keyEdge || hovered ? "url(#atlas-arrow-blue)" : undefined}
                        onClick={(event) => {
                          event.stopPropagation();
                          setSelectedEdgeId(edge.id);
                        }}
                        onMouseEnter={() => setHoveredEdgeId(edge.id)}
                        onMouseLeave={() => setHoveredEdgeId(null)}
                      />
                      {showLabel ? (
                        <g className={`edge-label-badge ${selected ? "selected" : ""}`} transform={`translate(${midX} ${midY - 11})`}>
                          <rect height="20" rx="6" width={labelWidth} x={-labelWidth / 2} y="-13" />
                          <text y="1">{label}</text>
                        </g>
                      ) : null}
                      {showCountBadge ? (
                        <g className={`edge-count-badge ${selected ? "selected" : ""}`} transform={`translate(${midX} ${midY + 13})`}>
                          <circle r="12" />
                          <text y="4">×{edge.rawEdgeCount}</text>
                        </g>
                      ) : null}
                    </g>
                  );
                })}
              </g>
              <g className="atlas-nodes refined-nodes">
                {visibleNodes.map((node) => {
                  const point = layout.get(node.id);
                  if (!point) return null;
                  const selected = node.id === selectedNodeId;
                  const linked = selectedNodeId ? Boolean(adjacency.get(selectedNodeId)?.some((item) => item.nodeId === node.id)) : false;
                  const hovered = hoveredNodeId === node.id;
                  const visual = visualFor(node.type);
                  const radius = nodeRadius(node, selected, linked);
                  const captionLines = splitCaption(node.label, labelMode);
                  return (
                    <g
                      key={node.id}
                      className={`atlas-node refined-node ${selected ? "selected" : ""} ${linked ? "linked" : ""} ${hovered ? "hovered" : ""}`}
                      onClick={(event) => { event.stopPropagation(); expandNode(node.id, 1); }}
                      onMouseEnter={() => setHoveredNodeId(node.id)}
                      onMouseLeave={() => setHoveredNodeId(null)}
                      role="button"
                      tabIndex={0}
                      transform={`translate(${point.x} ${point.y})`}
                    >
                      <title>{`${node.label} · ${visualFor(node.type).label} · 关联 ${getNodeDegree(node.id, adjacency)}`}</title>
                      <circle fill={visual.fill} r={radius} stroke={visual.stroke} />
                      <text className="node-core-label" y="4">{coreLabel(node.label)}</text>
                      <text className="node-caption" y={radius + 18}>
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
          focusedKeyEdges={focusedKeyEdges}
          graph={graph}
          onCollapse={collapseCurrent}
          onExpandMore={() => selectedNodeId && expandMoreForNode(selectedNodeId)}
          onExpandOne={() => selectedNodeId && expandNode(selectedNodeId, 1)}
          onReset={resetGraph}
          onSelectNeighbor={(nodeId) => expandNode(nodeId, 1)}
          selectedEdge={selectedEdge}
          selectedNode={selectedNode}
          visibleNodeIds={visibleNodeIds}
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










