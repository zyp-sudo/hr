import { useState, useEffect, useCallback, useRef } from "react";
import { AlertTriangle, Clock3, Filter, Info, Maximize2, RefreshCw, RotateCcw } from "lucide-react";
import {
  validatePanoramaResponse, ValidationError,
  type ValidatedPanoramaResponse, type ValidatedPanoramaNode, type ValidatedPanoramaEdge,
} from "../utils/competitionValidators";

const API = "/api/platform/storage/api/competition/panorama";

function timeText(date: Date) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(date);
}

const NODE_COLORS: Record<string, string> = { role: "#9bf2e9", skill: "#4ade80", capability: "#ffaf40" };
const NODE_BG: Record<string, string> = { role: "rgba(155,242,233,.12)", skill: "rgba(74,222,128,.10)", capability: "rgba(255,175,64,.10)" };
const RELATION_LABELS: Record<string, string> = { requires: "需要", demonstrates: "体现", related_to: "相关" };

/** Per-type visual dimensions (viewBox units). */
const NODE_DIMS: Record<string, { w: number; h: number }> = {
  role: { w: 9, h: 4.5 },
  skill: { w: 7.5, h: 3.6 },
  capability: { w: 8, h: 4 },
};
const NODE_DIMS_DEFAULT = { w: 7, h: 3.5 };

const MAX_LABEL_CHARS = 6;

interface LayoutNode extends ValidatedPanoramaNode { x: number; y: number; }

function layoutNodes(validNodes: ValidatedPanoramaNode[]): LayoutNode[] {
  if (!validNodes || validNodes.length === 0) return [];
  const groups: Record<string, ValidatedPanoramaNode[]> = {};
  for (const n of validNodes) {
    const t = n.type || "skill";
    if (!groups[t]) groups[t] = [];
    groups[t].push(n);
  }
  const typeOrder: Record<string, number> = { role: 0, skill: 1, capability: 2 };
  const typeKeys = Object.keys(groups).sort((a, b) => (typeOrder[a] ?? 1) - (typeOrder[b] ?? 1));

  // Layout centres tuned to keep larger nodes from overlapping
  const layoutDef: Record<string, { cx: number; cy: number; rx: number; ry: number }> = {
    role: { cx: 16, cy: 50, rx: 6, ry: 26 },
    skill: { cx: 48, cy: 50, rx: 20, ry: 36 },
    capability: { cx: 81, cy: 50, rx: 13, ry: 30 },
  };

  const result: LayoutNode[] = [];
  typeKeys.forEach((type) => {
    const def = layoutDef[type] || layoutDef.skill;
    const group = groups[type];
    const count = group.length;
    group.forEach((node, i) => {
      const angle = (i / Math.max(1, count)) * Math.PI * 2 - Math.PI / 2;
      result.push({
        ...node,
        x: def.cx + Math.cos(angle) * def.rx,
        y: def.cy + Math.sin(angle) * def.ry,
      });
    });
  });
  return result;
}

export default function RoleCapabilityGraph() {
  const [data, setData] = useState<ValidatedPanoramaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedNode, setSelectedNode] = useState<ValidatedPanoramaNode | null>(null);
  const [highlightNodeId, setHighlightNodeId] = useState<string | null>(null);
  const [stack, setStack] = useState("all");
  const [level, setLevel] = useState("all");
  const [version, setVersion] = useState("all");
  const [updated, setUpdated] = useState("");
  const [filteredEdgeCount, setFilteredEdgeCount] = useState(0);
  const svgRef = useRef<SVGSVGElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (stack !== "all") params.set("stack", stack);
      if (level !== "all") params.set("level", level);
      if (version !== "all") params.set("version", version);
      const url = params.toString() ? `${API}?${params.toString()}` : API;
      const res = await fetch(url);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `服务返回 HTTP ${res.status}`);
      }
      const validated = await validatePanoramaResponse(res) as ValidatedPanoramaResponse & { _filteredEdges?: number };
      setData(validated);
      setFilteredEdgeCount(validated._filteredEdges || 0);
      setUpdated(timeText(new Date()));
      setSelectedNode(null);
      setHighlightNodeId(null);
    } catch (e: any) {
      setError(e.name === "ValidationError" ? e.message : (e.message || "无法加载岗位能力图谱数据"));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [stack, level, version]);

  useEffect(() => { load(); }, [load]);

  const meta = data?.meta;
  const stacks: string[] = meta?.stacks || [];
  const levels: string[] = meta?.levels || [];
  const versions: string[] = meta?.versions || [];
  const rawNodes: ValidatedPanoramaNode[] = data?.nodes || [];
  const rawEdges: ValidatedPanoramaEdge[] = data?.edges || [];

  const nodes: LayoutNode[] = layoutNodes(rawNodes);
  const nodeMap = new Map(nodes.map(n => [n.id, n]));

  const validEdges = rawEdges.filter(e => nodeMap.has(e.source) && nodeMap.has(e.target));
  const skippedEdgeCount = rawEdges.length - validEdges.length + filteredEdgeCount;

  const adjacency = new Map<string, Set<string>>();
  for (const e of validEdges) {
    if (!adjacency.has(e.source)) adjacency.set(e.source, new Set());
    if (!adjacency.has(e.target)) adjacency.set(e.target, new Set());
    adjacency.get(e.source)!.add(e.target);
    adjacency.get(e.target)!.add(e.source);
  }

  const highlightSet = highlightNodeId ? (adjacency.get(highlightNodeId) || new Set()) : new Set<string>();
  const connectedEdgeKeys = highlightNodeId
    ? new Set(validEdges.filter(e => e.source === highlightNodeId || e.target === highlightNodeId).map(e => `${e.source}-${e.target}-${e.relation}`))
    : new Set<string>();

  /** Edge centre: connect from node visual centre to target visual centre. */
  const edgeCentre = (node: LayoutNode) => {
    const dim = NODE_DIMS[node.type] || NODE_DIMS_DEFAULT;
    return { cx: node.x + dim.w / 2, cy: node.y + dim.h / 2 };
  };

  const resetView = () => { setSelectedNode(null); setHighlightNodeId(null); };
  const selectNode = (node: ValidatedPanoramaNode) => {
    if (selectedNode?.id === node.id) { setSelectedNode(null); setHighlightNodeId(null); }
    else { setSelectedNode(node); setHighlightNodeId(node.id); }
  };
  const nodeTypeLabel = (type: string) => type === "role" ? "岗位" : type === "skill" ? "技能" : "能力维度";

  const truncateLabel = (label: string) =>
    (label || "").length > MAX_LABEL_CHARS ? label.slice(0, MAX_LABEL_CHARS) + "…" : label;

  const hasGraph = nodes.length > 0;

  return (
    <div className="rcg">
      <div className="rcg__filters">
        <div className="rcg__filter-group">
          <Filter style={{ width: 18 }} />
          <label><span>技术栈</span><select value={stack} onChange={e => setStack(e.target.value)} aria-label="技术栈筛选"><option value="all">全部</option>{stacks.map(s => <option key={s} value={s}>{s}</option>)}</select></label>
          <label><span>级别</span><select value={level} onChange={e => setLevel(e.target.value)} aria-label="级别筛选"><option value="all">全部</option>{levels.map(l => <option key={l} value={l}>{l}</option>)}</select></label>
          <label><span>版本</span><select value={version} onChange={e => setVersion(e.target.value)} aria-label="版本筛选"><option value="all">全部</option>{versions.map(v => <option key={v} value={v}>{v}</option>)}</select></label>
        </div>
        <div className="rcg__actions">
          <span><Clock3 style={{ width: 14 }} />{updated || "等待数据"}</span>
          <button className="ghost-action spring-hover" onClick={load} disabled={loading} aria-label="刷新图谱"><RefreshCw className={loading ? "spin" : ""} />{loading ? "加载中" : "刷新"}</button>
          {highlightNodeId && <button className="ghost-action" onClick={resetView} aria-label="重置视图"><RotateCcw style={{ width: 14 }} /> 重置视图</button>}
        </div>
      </div>

      {error && (<div className="comp-error-banner"><AlertTriangle /><div><b>数据加载失败</b><span>{error}</span></div><button className="ghost-action" onClick={load} aria-label="重试">重试</button></div>)}
      {loading && (<div className="comp-empty"><RefreshCw className="spin" /><h3>加载图谱数据中…</h3><p>正在从后端获取岗位能力图谱。</p></div>)}
      {!loading && !error && !hasGraph && (
        <div className="comp-empty"><Info /><h3>暂无图谱数据</h3><p>后端图谱服务可能尚未启动，或当前筛选条件下无数据。请尝试调整筛选条件或稍后重试。</p><button className="ghost-action" onClick={load} style={{ marginTop: 12 }}>重新加载</button></div>
      )}

      {hasGraph && (
        <div className="rcg__main">
          <div className="rcg__canvas">
            {skippedEdgeCount > 0 && (
              <div style={{ position: "absolute", top: 6, right: 10, fontSize: 10, color: "#facc15", zIndex: 5 }}>已过滤 {skippedEdgeCount} 条非法边</div>
            )}
            <svg ref={svgRef} viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet" className="rcg__svg" aria-label="岗位能力图谱">
              {/* ── Edges drawn first so they sit behind nodes ── */}
              {validEdges.map((e) => {
                const sn = nodeMap.get(e.source), tn = nodeMap.get(e.target);
                if (!sn || !tn) return null;
                const sc = edgeCentre(sn), tc = edgeCentre(tn);
                const edgeKey = `${e.source}-${e.target}-${e.relation}`;
                const isConnected = connectedEdgeKeys.has(edgeKey);
                const hasHighlight = highlightNodeId !== null;
                const relLabel = RELATION_LABELS[e.relation] || e.relation;
                return (
                  <g key={edgeKey} opacity={hasHighlight && !isConnected ? 0.15 : 1}>
                    <title>{`${sn.label} → ${tn.label} (${relLabel})`}</title>
                    <line
                      x1={sc.cx} y1={sc.cy} x2={tc.cx} y2={tc.cy}
                      stroke={isConnected ? "rgba(155,242,233,.55)" : "rgba(255,255,255,.10)"}
                      strokeWidth={isConnected ? 0.45 : 0.14}
                    />
                  </g>
                );
              })}
              {/* ── Nodes ── */}
              {nodes.map(node => {
                const dim = NODE_DIMS[node.type] || NODE_DIMS_DEFAULT;
                const color = NODE_COLORS[node.type] || "#94a3b8";
                const bg = NODE_BG[node.type] || "rgba(148,163,184,.08)";
                const isSelected = selectedNode?.id === node.id;
                const isAdjacent = highlightSet.has(node.id);
                const isDimmed = highlightNodeId !== null && !isSelected && !isAdjacent;
                const labelText = isSelected ? node.label : truncateLabel(node.label);
                const typeLabel = nodeTypeLabel(node.type);
                return (
                  <g
                    key={node.id}
                    className="rcg-node"
                    role="button"
                    tabIndex={0}
                    aria-label={`${typeLabel}: ${node.label}`}
                    aria-pressed={isSelected}
                    opacity={isDimmed ? 0.3 : 1}
                    onClick={() => selectNode(node)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectNode(node); } }}
                    style={{ cursor: "pointer", outline: "none" }}
                  >
                    <title>{`${typeLabel}: ${node.label}`}</title>
                    <rect
                      x={node.x} y={node.y} width={dim.w} height={dim.h} rx={0.8}
                      fill={isSelected ? color : isAdjacent ? bg : "rgba(20,20,31,.85)"}
                      stroke={color}
                      strokeWidth={isSelected ? 0.35 : isAdjacent ? 0.22 : 0.12}
                    />
                    <text
                      x={node.x + dim.w / 2}
                      y={node.y + dim.h / 2 + 0.55}
                      textAnchor="middle"
                      fill={isSelected ? "#fff" : isAdjacent ? color : "rgba(255,255,255,.50)"}
                      fontSize={isSelected ? 1.7 : 1.3}
                      fontWeight={isSelected ? 700 : isAdjacent ? 600 : 400}
                      style={{ pointerEvents: "none", userSelect: "none" }}
                    >
                      {labelText}
                    </text>
                  </g>
                );
              })}
            </svg>
            <div className="rcg__canvas-legend">
              <span style={{ fontSize: 10, color: "#6e6a78", marginBottom: 4 }}>图例</span>
              {(["role", "skill", "capability"] as const).map(type => (
                <span key={type} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10, color: "#918b99" }}>
                  <i style={{ width: 8, height: 8, borderRadius: 2, background: NODE_COLORS[type] }} />
                  {nodeTypeLabel(type)}
                </span>
              ))}
              <span style={{ fontSize: 9, color: "#555", marginTop: 2 }}>点击节点查看详情</span>
            </div>
          </div>

          <div className="rcg__detail">
            {selectedNode ? (
              <div className="rcg__node-info">
                <div className="rcg__node-header">
                  <span className="rcg__node-type" style={{ color: NODE_COLORS[selectedNode.type] || "#94a3b8" }}>
                    {nodeTypeLabel(selectedNode.type)}
                  </span>
                  <h3>{selectedNode.label}</h3>
                </div>
                <div className="rcg__node-stats">
                  <div className="rcg__stat"><span>类型</span><b>{nodeTypeLabel(selectedNode.type)}</b></div>
                  <div className="rcg__stat"><span>来源证据</span><b>{(selectedNode.source_ids || []).length} 条</b></div>
                  {selectedNode.stack && <div className="rcg__stat"><span>技术栈</span><b>{selectedNode.stack}</b></div>}
                  {selectedNode.level && <div className="rcg__stat"><span>级别</span><b>{selectedNode.level}</b></div>}
                  {selectedNode.version && <div className="rcg__stat"><span>版本</span><b>{selectedNode.version}</b></div>}
                </div>
                {(selectedNode.source_ids || []).length > 0 && (
                  <div className="rcg__node-sources">
                    <span>来源 ID</span>
                    <div className="rcg__source-list">
                      {(selectedNode.source_ids || []).map(id => <code key={id} className="rcg__source-code">{id}</code>)}
                    </div>
                  </div>
                )}
                <div className="rcg__node-related">
                  <span>关联关系 ({adjacency.get(selectedNode.id)?.size || 0})</span>
                  <div className="rcg__related-list">
                    {validEdges
                      .filter(e => e.source === selectedNode.id || e.target === selectedNode.id)
                      .slice(0, 12)
                      .map(e => {
                        const otherId = e.source === selectedNode.id ? e.target : e.source;
                        const otherNode = nodeMap.get(otherId);
                        return (
                          <button
                            key={`${e.source}-${e.target}-${e.relation}`}
                            className="rcg__related-chip"
                            onClick={() => { const t = nodeMap.get(otherId); if (t) { setSelectedNode(t); setHighlightNodeId(t.id); } }}
                            aria-label={`查看 ${otherNode?.label || otherId}`}
                          >
                            {RELATION_LABELS[e.relation] || e.relation}: {otherNode?.label || otherId}
                          </button>
                        );
                      })}
                  </div>
                </div>
              </div>
            ) : (
              <div className="rcg__empty-detail">
                <Maximize2 style={{ width: 34, height: 34 }} />
                <h3>岗位能力图谱</h3>
                <p>点击图谱中的节点查看岗位与技能点的来源证据和关联关系。</p>
                <div className="rcg__legend">
                  <span className="rcg__legend-label">节点类型</span>
                  <div className="rcg__legend-items">
                    <span><i style={{ background: NODE_COLORS.role }} /> 岗位</span>
                    <span><i style={{ background: NODE_COLORS.skill }} /> 技能</span>
                    <span><i style={{ background: NODE_COLORS.capability }} /> 能力维度</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
