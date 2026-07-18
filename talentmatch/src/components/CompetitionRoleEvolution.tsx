import { useState, useEffect, useCallback } from "react";
import {
  AlertTriangle, ArrowRight, Check, Clock3, GitCompareArrows, Info, Minus,
  RefreshCw, RotateCcw
} from "lucide-react";
import {
  validateRoleVersionsResponse, validateRoleDiffResponse, ValidationError,
  type ValidatedRoleVersionItem, type ValidatedRoleVersionsResponse,
  type ValidatedRoleDiffResponse, type ValidatedDiffSkillItem,
} from "../utils/competitionValidators";

const API_BASE = "/api/platform/storage/api/competition";

const AVAILABLE_ROLES: Array<{ id: string; name: string }> = [
  { id: "java-developer", name: "Java开发工程师" },
  { id: "frontend-developer", name: "前端开发工程师" },
  { id: "data-scientist", name: "数据科学家" },
];

function timeText(date: Date) {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(date);
}

function SourceIdsDisplay({ ids }: { ids: string[]; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  if (!ids || ids.length === 0) return <span style={{ color: "#6e6a78", fontSize: 11 }}>—</span>;
  const visible = open ? ids : ids.slice(0, 2);
  return (
    <span style={{ fontSize: 11 }}>
      {visible.join(", ")}
      {ids.length > 2 && !open && <button className="comp-link-btn" onClick={() => setOpen(true)}> …共{ids.length}个</button>}
      {open && ids.length > 2 && <button className="comp-link-btn" onClick={() => setOpen(false)}> 收起</button>}
    </span>
  );
}

export default function CompetitionRoleEvolution() {
  const [versionsData, setVersionsData] = useState<ValidatedRoleVersionsResponse | null>(null);
  const [roleId, setRoleId] = useState("java-developer");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [fromVersionId, setFromVersionId] = useState<string | null>(null);
  const [toVersionId, setToVersionId] = useState<string | null>(null);
  const [diff, setDiff] = useState<ValidatedRoleDiffResponse | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [diffError, setDiffError] = useState("");
  const [selectionError, setSelectionError] = useState("");

  const loadVersions = useCallback(async () => {
    setLoading(true);
    setError("");
    setDiff(null); setDiffError(""); setFromVersionId(null); setToVersionId(null); setSelectionError("");
    try {
      const res = await fetch(`${API_BASE}/roles/${encodeURIComponent(roleId)}/versions`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `服务返回 HTTP ${res.status}`);
      }
      const validated = await validateRoleVersionsResponse(res);
      setVersionsData(validated);
    } catch (e: any) {
      setError(e.name === "ValidationError" ? e.message : (e.message || "无法加载岗位版本数据"));
      setVersionsData(null);
    } finally {
      setLoading(false);
    }
  }, [roleId]);

  useEffect(() => { loadVersions(); }, [loadVersions]);

  const runDiff = useCallback(async (fromV: string, toV: string) => {
    if (fromV === toV) { setSelectionError("不能选择相同的版本进行对比"); return; }
    setSelectionError("");
    setDiffLoading(true);
    setDiffError("");
    try {
      const res = await fetch(`${API_BASE}/roles/${encodeURIComponent(roleId)}/diff?from_version=${encodeURIComponent(fromV)}&to_version=${encodeURIComponent(toV)}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `服务返回 HTTP ${res.status}`);
      }
      const validated = await validateRoleDiffResponse(res);
      setDiff(validated);
    } catch (e: any) {
      setDiffError(e.name === "ValidationError" ? e.message : (e.message || "Diff 加载失败"));
      setDiff(null);
    } finally {
      setDiffLoading(false);
    }
  }, [roleId]);

  const resetSelection = () => {
    setFromVersionId(null); setToVersionId(null); setDiff(null); setDiffError(""); setSelectionError("");
  };

  const versions: ValidatedRoleVersionItem[] = versionsData?.versions || [];
  const currentRole = AVAILABLE_ROLES.find(r => r.id === roleId);
  const roleName = versionsData?.name || currentRole?.name || roleId;
  const fromVersion = versions.find(v => v.version_id === fromVersionId) || null;
  const toVersion = versions.find(v => v.version_id === toVersionId) || null;

  const getUnchangedItems = (): ValidatedDiffSkillItem[] => {
    if (!diff || !fromVersion || !toVersion) return [];
    const addedNames = new Set(diff.added.map(s => s.name));
    const removedNames = new Set(diff.removed.map(s => s.name));
    const modifiedNames = new Set(diff.modified.map(s => s.name));
    return (toVersion.skills || [])
      .filter(s => !addedNames.has(s.name) && !removedNames.has(s.name) && !modifiedNames.has(s.name))
      .map(s => ({ name: s.name, level: s.level, source_ids: s.source_ids || [], reason: null }));
  };

  const unchangedItems = getUnchangedItems();
  const hasVersions = versions.length > 0;

  return (
    <div className="comp-evolution">
      <div className="comp-evolution__role-bar">
        <span className="comp-evolution__role-label">选择岗位</span>
        <select value={roleId} onChange={e => setRoleId(e.target.value)} className="comp-evolution__role-select" aria-label="选择岗位">
          {AVAILABLE_ROLES.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
        <button className="ghost-action spring-hover" onClick={loadVersions} disabled={loading} aria-label="刷新版本数据">
          <RefreshCw className={loading ? "spin" : ""} />{loading ? "加载中" : "刷新"}
        </button>
      </div>

      {error && (
        <div className="comp-error-banner">
          <AlertTriangle /><div><b>数据加载失败</b><span>{error}</span></div>
          <button className="ghost-action" onClick={loadVersions} aria-label="重试">重试</button>
        </div>
      )}

      {loading && (
        <div className="comp-empty"><RefreshCw className="spin" /><h3>加载版本数据中…</h3><p>正在从后端获取岗位历史版本信息。</p></div>
      )}

      {!loading && !error && !hasVersions && (
        <div className="comp-empty">
          <Info /><h3>暂无版本数据</h3>
          <p>后端 competition 服务可能尚未启动，或该岗位的能力数据尚未收录。</p>
          <button className="ghost-action" onClick={loadVersions} style={{ marginTop: 12 }}>重新加载</button>
        </div>
      )}

      {!loading && !error && hasVersions && (
        <>
          <div className="comp-evolution__timeline">
            <div className="comp-evolution__timeline-label">历史版本（点击选择两个版本进行对比）</div>
            <div className="comp-evolution__timeline-track">
              {versions.map(v => {
                const isFrom = v.version_id === fromVersionId;
                const isTo = v.version_id === toVersionId;
                return (
                  <button key={v.version_id}
                    className={`comp-version-chip ${isFrom ? "comp-version-chip--from" : ""} ${isTo ? "comp-version-chip--to" : ""}`}
                    onClick={() => {
                      if (!fromVersionId) { setFromVersionId(v.version_id); }
                      else if (!toVersionId && v.version_id !== fromVersionId) { setToVersionId(v.version_id); }
                      else { setFromVersionId(v.version_id); setToVersionId(null); setDiff(null); setDiffError(""); setSelectionError(""); }
                    }}
                    aria-label={`版本 ${v.version_id}`}>
                    <span className="comp-version-chip__num">{isFrom && <span className="comp-version-chip__badge">A</span>}{isTo && <span className="comp-version-chip__badge">B</span>}{v.version_id}</span>
                    <span className="comp-version-chip__date">{timeText(new Date(v.timestamp))}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="comp-compare-bar">
            <div className="comp-compare-bar__selects">
              <div className="comp-compare-bar__field">
                <span>基准版本 (A)</span>
                <select value={fromVersionId || ""} onChange={e => { setFromVersionId(e.target.value || null); setDiff(null); setSelectionError(""); }} className="comp-evolution__role-select" aria-label="选择基准版本">
                  <option value="">选择版本…</option>
                  {versions.map(v => <option key={v.version_id} value={v.version_id} disabled={v.version_id === toVersionId}>{v.version_id} — {timeText(new Date(v.timestamp))}</option>)}
                </select>
              </div>
              <ArrowRight style={{ width: 20, color: "#6e6a78", flex: "none", marginTop: 16 }} />
              <div className="comp-compare-bar__field">
                <span>对比版本 (B)</span>
                <select value={toVersionId || ""} onChange={e => { setToVersionId(e.target.value || null); setDiff(null); setSelectionError(""); }} className="comp-evolution__role-select" aria-label="选择对比版本">
                  <option value="">选择版本…</option>
                  {versions.map(v => <option key={v.version_id} value={v.version_id} disabled={v.version_id === fromVersionId}>{v.version_id} — {timeText(new Date(v.timestamp))}</option>)}
                </select>
              </div>
            </div>
            <div className="comp-compare-bar__actions">
              {selectionError && <span className="comp-compare-bar__error">{selectionError}</span>}
              <button className="comp-action-btn" onClick={() => fromVersionId && toVersionId && runDiff(fromVersionId, toVersionId)} disabled={!fromVersionId || !toVersionId || diffLoading} aria-label="执行版本对比"><GitCompareArrows style={{ width: 16 }} />{diffLoading ? "对比中…" : "执行对比"}</button>
              {(fromVersionId || toVersionId) && <button className="ghost-action" onClick={resetSelection} aria-label="重置选择"><RotateCcw style={{ width: 14 }} /> 重置</button>}
            </div>
          </div>

          {diffError && (
            <div className="comp-error-banner"><AlertTriangle /><div><b>版本对比失败</b><span>{diffError}</span></div><button className="ghost-action" onClick={() => fromVersionId && toVersionId && runDiff(fromVersionId, toVersionId)} aria-label="重试对比">重试</button></div>
          )}

          {diffLoading && (
            <div className="comp-empty" style={{ minHeight: 120 }}><RefreshCw className="spin" /><h3>正在对比版本差异…</h3><p>正在计算 {fromVersionId} → {toVersionId} 的能力变化。</p></div>
          )}

          {diff && !diffLoading && (
            <div className="comp-diff-panel">
              <div className="comp-diff-panel__head">
                <h3><GitCompareArrows style={{ width: 18 }} /> 版本对比：{diff.from_version} → {diff.to_version}</h3>
                <span>{diff.added.length + diff.removed.length + diff.modified.length} 项变化{unchangedItems.length > 0 && ` · ${unchangedItems.length} 项未变`}</span>
              </div>
              {diff.added.length === 0 && diff.removed.length === 0 && diff.modified.length === 0 ? (
                <div className="comp-empty" style={{ minHeight: 100, border: "none" }}><Check style={{ width: 32, height: 32, color: "#4ade80" }} /><h3>两个版本之间无差异</h3><p>{diff.from_version} 和 {diff.to_version} 的能力项完全相同。</p></div>
              ) : (
                <div className="comp-diff-grid">
                  {(["added", "removed", "modified"] as const).map(kind => {
                    const items = diff[kind];
                    if (!items || items.length === 0) return null;
                    const icon = kind === "added" ? "+" : kind === "removed" ? "−" : "~";
                    const label = kind === "added" ? "新增技能" : kind === "removed" ? "删除技能" : "修改技能";
                    return (
                      <div key={kind} className={`comp-diff-col comp-diff-col--${kind}`}>
                        <div className="comp-diff-col__head"><span className="comp-diff-col__icon">{icon}</span><span>{label}</span><em>{items.length}</em></div>
                        {items.map((item) => (
                          <div key={item.name} className="comp-diff-item">
                            <b>{item.name}</b>
                            {item.level && <span className="comp-diff-item__level">{item.level}</span>}
                            <SourceIdsDisplay ids={item.source_ids} />
                            {item.reason && <small className="comp-diff-item__reason">原因：{item.reason}</small>}
                          </div>
                        ))}
                      </div>
                    );
                  })}
                </div>
              )}
              {unchangedItems.length > 0 && (
                <div className="comp-diff-unchanged">
                  <div className="comp-diff-unchanged__head"><Minus style={{ width: 14 }} /><span>未变化技能</span><em>{unchangedItems.length}</em></div>
                  <div className="comp-diff-unchanged__list">
                    {unchangedItems.map(item => <span key={item.name} className="comp-diff-unchanged__chip">{item.name}{item.level ? ` (${item.level})` : ""}</span>)}
                  </div>
                </div>
              )}
            </div>
          )}

          {fromVersion && !diff && !diffLoading && (
            <div className="comp-evolution__detail">
              <div className="comp-evolution__detail-head">
                <div><h2>{roleName} · {fromVersion.version_id}</h2><p className="comp-evolution__detail-meta"><Clock3 style={{ width: 14 }} /> {timeText(new Date(fromVersion.timestamp))} · 数据来源：{fromVersion.source || "多源采集"}</p></div>
              </div>
              <div className="comp-capability-table">
                <div className="comp-capability-table__head" style={{ gridTemplateColumns: "2fr 1fr 1fr" }}><span>技能名称</span><span>等级</span><span>来源证据</span></div>
                {(fromVersion.skills || []).map(skill => (
                  <div key={skill.name} className="comp-capability-row" style={{ gridTemplateColumns: "2fr 1fr 1fr" }}>
                    <span className="comp-capability-row__name">{skill.name}</span>
                    <span className="comp-capability-row__category">{skill.level || "--"}</span>
                    <span className="comp-capability-row__reason"><SourceIdsDisplay ids={skill.source_ids || []} /></span>
                  </div>
                ))}
              </div>
              {(fromVersion.responsibilities || []).length > 0 && (
                <section className="comp-detail__section" style={{ marginTop: 20 }}><h3>岗位职责</h3><ul>{fromVersion.responsibilities.map((r, i) => <li key={i}>{r}</li>)}</ul></section>
              )}
              <p style={{ color: "#6e6a78", fontSize: 11, marginTop: 16 }}>选择两个版本并点击"执行对比"查看能力变化。</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
