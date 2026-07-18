import { useState, useEffect, useCallback } from "react";
import {
  AlertTriangle, Check, ChevronDown, ChevronUp, Clock3, Copy,
  Edit3, RefreshCw, Search, ThumbsDown, ThumbsUp, TrendingUp, X
} from "lucide-react";
import type { ReviewEditPayload, ReviewRecord } from "../types";
import {
  validateDiscoveriesResponse,
  ValidationError,
  type ValidatedDiscoveryItem,
} from "../utils/competitionValidators";

const API_BASE = "/api/platform/storage/api/competition";

function timeText(date: Date) {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(date);
}

function SourceIdsDisplay({ ids }: { ids: string[] }) {
  const [expanded, setExpanded] = useState(false);
  if (!ids || ids.length === 0) return <span style={{ color: "#777180", fontSize: 12 }}>无来源记录</span>;
  const visible = expanded ? ids : ids.slice(0, 3);
  return (
    <div className="comp-sources">
      {visible.map(id => (
        <div key={id} className="comp-source-item">
          <div className="comp-source-item__row">
            <code className="comp-source-item__code">{id}</code>
            <button
              className="comp-source-item__copy"
              onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(id).catch(() => {}); }}
              aria-label={`复制来源ID: ${id}`}
            >
              <Copy style={{ width: 13, height: 13 }} />
            </button>
          </div>
        </div>
      ))}
      {ids.length > 3 && (
        <button className="comp-source-toggle" onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}>
          {expanded ? <><ChevronUp style={{ width: 14 }} /> 收起（共 {ids.length} 个来源）</>
            : <><ChevronDown style={{ width: 14 }} /> 查看全部 {ids.length} 个来源</>}
        </button>
      )}
    </div>
  );
}

export default function CompetitionDiscovery() {
  const [items, setItems] = useState<ValidatedDiscoveryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<"all" | "pending" | "approved" | "rejected">("pending");
  const [selected, setSelected] = useState<ValidatedDiscoveryItem | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState<ReviewEditPayload>({});
  const [updated, setUpdated] = useState("");
  const [actionError, setActionError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [reviews, setReviews] = useState<ReviewRecord[]>([]);
  const [reviewsLoading, setReviewsLoading] = useState(false);
  const [reviewsOpen, setReviewsOpen] = useState(false);
  const [toast, setToast] = useState("");

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = filter !== "all" ? `?status=${filter}` : "";
      const res = await fetch(`${API_BASE}/discoveries${params}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `服务返回 HTTP ${res.status}`);
      }
      const validated = await validateDiscoveriesResponse(res);
      setItems(validated.items);
      setUpdated(timeText(new Date()));
      if (selected) {
        const refreshed = validated.items.find(i => i.id === selected.id);
        if (refreshed) setSelected(refreshed);
      }
    } catch (e: any) {
      setError(e.name === "ValidationError" ? e.message : (e.message || "无法加载新岗位发现数据"));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const loadReviews = useCallback(async (discoveryId: string) => {
    setReviewsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/discoveries/${encodeURIComponent(discoveryId)}/reviews`);
      if (!res.ok) throw new Error(`服务返回 ${res.status}`);
      const data: ReviewRecord[] = await res.json();
      if (!Array.isArray(data)) throw new Error("审核历史返回结构不正确");
      setReviews(data);
    } catch {
      setReviews([]);
    } finally {
      setReviewsLoading(false);
    }
  }, []);

  const handleSelect = (item: ValidatedDiscoveryItem) => {
    setSelected(item);
    setEditOpen(false);
    setActionError("");
    setReviewsOpen(false);
    loadReviews(item.id);
  };

  const submitReview = async (
    id: string, status: "approved" | "rejected" | "pending",
    edits?: ReviewEditPayload, comment?: string,
  ) => {
    setActionError("");
    setSubmitting(true);
    try {
      const body: Record<string, unknown> = { status, editor: "competition-ui" };
      if (edits) body.edits = edits;
      if (comment) body.comment = comment;
      const res = await fetch(`${API_BASE}/discoveries/${encodeURIComponent(id)}/review`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || `审核失败 (${res.status})`);
      }
      await load();
      if (selected?.id === id) await loadReviews(id);
      setEditOpen(false);
      showToast(`操作成功：${status === "approved" ? "已批准" : status === "rejected" ? "已驳回" : "已重置"}`);
    } catch (e: any) {
      setActionError(e.message || "审核操作失败");
    } finally {
      setSubmitting(false);
    }
  };

  const saveEdit = async () => {
    if (!selected) return;
    setActionError("");
    const edits: ReviewEditPayload = {};
    if (editForm.name !== undefined) edits.name = editForm.name;
    if (editForm.responsibilities !== undefined) edits.responsibilities = editForm.responsibilities;
    if (editForm.required_skills !== undefined) edits.required_skills = editForm.required_skills;
    if (editForm.bonus_skills !== undefined) edits.bonus_skills = editForm.bonus_skills;
    await submitReview(selected.id, selected.review_status as "approved" | "rejected" | "pending", edits, "人工编辑修改");
  };

  const filtered = filter === "all" ? items : items.filter(i => i.review_status === filter);
  const statusLabel = (s: string) => s === "approved" ? "已批准" : s === "rejected" ? "已驳回" : "待审核";
  const pendingCount = items.filter(i => i.review_status === "pending").length;
  const approvedCount = items.filter(i => i.review_status === "approved").length;

  return (
    <div className="comp-discovery">
      {toast && (
        <div className="comp-toast">
          <Check style={{ width: 16, color: "#4ade80" }} /><span>{toast}</span>
          <button onClick={() => setToast("")} aria-label="关闭提示"><X style={{ width: 14 }} /></button>
        </div>
      )}

      <div className="comp-stats">
        <div className="comp-stat"><span className="comp-stat__label">发现岗位</span><b className="comp-stat__value">{error ? "不可用" : items.length}</b><small>{error ? "接口异常" : `${pendingCount} 条待审核 · ${approvedCount} 条已批准`}</small></div>
        <div className="comp-stat"><span className="comp-stat__label">平均置信度</span><b className="comp-stat__value mint">{error ? "--" : `${items.length ? Math.round(items.reduce((s, i) => s + i.confidence * 100, 0) / items.length) : 0}%`}</b><small>{error ? "接口异常" : "基于多源交叉验证"}</small></div>
        <div className="comp-stat"><span className="comp-stat__label">数据来源</span><b className="comp-stat__value">{error ? "不可用" : new Set(items.flatMap(i => i.source_ids)).size}</b><small>{error ? "接口异常" : "个独立渠道"}</small></div>
        <div className="comp-stat"><span className="comp-stat__label">更新时间</span><b className="comp-stat__value" style={{ fontSize: 14 }}>{error ? "--" : (updated || "--")}</b><small>{error ? "接口异常" : "最近同步"}</small></div>
      </div>

      <div className="page-actions" style={{ marginBottom: 16 }}>
        <span><Clock3 style={{ width: 14, verticalAlign: "middle", marginRight: 4 }} />{updated || "等待数据"}</span>
        <button className="ghost-action spring-hover" onClick={load} disabled={loading} aria-label="刷新数据"><RefreshCw className={loading ? "spin" : ""} />{loading ? "加载中" : "刷新"}</button>
        <div className="comp-filter-group">
          {(["all", "pending", "approved", "rejected"] as const).map(k => (
            <button key={k} className={filter === k ? "active" : ""} onClick={() => setFilter(k)} aria-label={`筛选: ${k === "all" ? "全部" : statusLabel(k)}`}>
              {k === "all" ? "全部" : statusLabel(k)}
              {k !== "all" && <span className="comp-filter-count">{items.filter(i => i.review_status === k).length}</span>}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="comp-error-banner">
          <AlertTriangle /><div><b>数据加载失败</b><span>{error}</span></div>
          <button className="ghost-action" onClick={load} aria-label="重试加载">重试</button>
        </div>
      )}
      {actionError && (
        <div className="comp-error-banner">
          <AlertTriangle /><div><b>操作失败</b><span>{actionError}</span></div>
          <button className="ghost-action" onClick={() => setActionError("")} aria-label="关闭错误"><X /></button>
        </div>
      )}
      {loading && (
        <div className="comp-discovery-list">
          {[1, 2, 3].map(i => (
            <div key={i} className="comp-discovery-card comp-skeleton">
              <div className="comp-skeleton__line w60" /><div className="comp-skeleton__line w80" /><div className="comp-skeleton__line w100" /><div className="comp-skeleton__line w40" />
            </div>
          ))}
        </div>
      )}
      {!loading && !error && filtered.length === 0 && (
        <div className="comp-empty">
          <Search /><h3>{items.length === 0 ? "暂无新岗位发现数据" : "当前筛选条件下无数据"}</h3>
          <p>{items.length === 0 ? "后端 competition 服务可能尚未启动或采集任务还在进行中。" : "尝试切换筛选条件查看其他状态的岗位。"}</p>
          {items.length === 0 && <button className="ghost-action" onClick={load} style={{ marginTop: 12 }}>重新加载</button>}
        </div>
      )}
      {!loading && filtered.length > 0 && (
        <div className="comp-discovery-list">
          {filtered.map(item => (
            <button key={item.id} className={`comp-discovery-card spring-hover ${selected?.id === item.id ? "comp-discovery-card--selected" : ""}`} onClick={() => handleSelect(item)} aria-label={`岗位: ${item.name}, 状态: ${statusLabel(item.review_status)}`}>
              <div className="comp-discovery-card__head">
                <span className={`comp-status comp-status--${item.review_status}`}>{statusLabel(item.review_status)}</span>
                <span className="comp-discovery-card__confidence">置信度 {Math.round(item.confidence * 100)}%</span>
              </div>
              <h3>{item.name}</h3>
              <p>{(item.responsibilities || []).slice(0, 3).join("；").slice(0, 120)}{(item.responsibilities || []).join("；").length > 120 ? "…" : ""}</p>
              <div className="comp-skill-tags">
                {item.required_skills.slice(0, 4).map(s => <i key={s.name} className="comp-tag--required">{s.name}</i>)}
                {item.bonus_skills.slice(0, 2).map(s => <i key={s.name} className="comp-tag--bonus">{s.name}</i>)}
              </div>
              <div className="comp-discovery-card__footer">
                <span><TrendingUp style={{ width: 13 }} /> 增长率 {Math.round(item.growth_rate * 100)}%</span>
                <span>来源 {item.source_ids.length} 个</span>
              </div>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div className="comp-detail">
          <div className="comp-detail__header">
            <div>
              <span className={`comp-status comp-status--${selected.review_status}`}>{statusLabel(selected.review_status)}</span>
              <h2>{selected.name}</h2>
              <p className="comp-detail__meta">置信度 {Math.round(selected.confidence * 100)}% · 增长率 {Math.round(selected.growth_rate * 100)}% · {selected.source_ids.length} 个来源{selected.reviewed_at ? ` · 审核于 ${timeText(new Date(selected.reviewed_at))}` : ""}</p>
            </div>
            <button className="comp-detail__close" onClick={() => { setSelected(null); setEditOpen(false); setReviewsOpen(false); }} aria-label="关闭详情"><X /></button>
          </div>

          {editOpen ? (
            <div className="comp-edit-form">
              <label className="comp-field"><span>岗位名称</span><input value={editForm.name !== undefined ? (editForm.name ?? "") : selected.name} onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))} aria-label="编辑岗位名称" /></label>
              <label className="comp-field"><span>岗位职责（一行一条）</span><textarea value={editForm.responsibilities !== undefined ? (editForm.responsibilities || []).join("\n") : (selected.responsibilities || []).join("\n")} onChange={e => setEditForm(f => ({ ...f, responsibilities: e.target.value.split("\n").filter(Boolean) }))} aria-label="编辑岗位职责" /></label>
              <label className="comp-field"><span>必备技能（JSON 格式）</span><textarea value={editForm.required_skills !== undefined ? JSON.stringify(editForm.required_skills, null, 2) : JSON.stringify(selected.required_skills, null, 2)} onChange={e => { try { setEditForm(f => ({ ...f, required_skills: JSON.parse(e.target.value) })); } catch { /* ignore */ } }} aria-label="编辑必备技能" /></label>
              <label className="comp-field"><span>加分技能（JSON 格式）</span><textarea value={editForm.bonus_skills !== undefined ? JSON.stringify(editForm.bonus_skills, null, 2) : JSON.stringify(selected.bonus_skills, null, 2)} onChange={e => { try { setEditForm(f => ({ ...f, bonus_skills: JSON.parse(e.target.value) })); } catch { /* ignore */ } }} aria-label="编辑加分技能" /></label>
              <div className="comp-edit-actions">
                <button className="ghost-action" onClick={() => { setEditOpen(false); setActionError(""); }} disabled={submitting}>取消</button>
                <button className="primary small-primary" onClick={saveEdit} disabled={submitting}>{submitting ? "保存中…" : "保存修改"}</button>
              </div>
            </div>
          ) : (
            <>
              <section className="comp-detail__section"><h3>岗位职责</h3>{(selected.responsibilities || []).length > 0 ? <ul>{selected.responsibilities.map((r, i) => <li key={i}>{r}</li>)}</ul> : <p style={{ color: "#777180", fontSize: 12 }}>暂无职责描述</p>}</section>
              <section className="comp-detail__section"><h3>必备技能</h3><div className="comp-skill-tags">{selected.required_skills.length ? selected.required_skills.map(s => <i key={s.name} className="comp-tag--required" title={`等级: ${s.level || "未指定"} | 来源: ${(s.source_ids || []).join(", ")}`}>{s.name}{s.level ? ` (${s.level})` : ""}</i>) : <span style={{ color: "#777180", fontSize: 12 }}>无</span>}</div></section>
              <section className="comp-detail__section"><h3>加分技能</h3><div className="comp-skill-tags">{selected.bonus_skills.length ? selected.bonus_skills.map(s => <i key={s.name} className="comp-tag--bonus" title={`来源: ${(s.source_ids || []).join(", ")}`}>{s.name}</i>) : <span style={{ color: "#777180", fontSize: 12 }}>无</span>}</div></section>
              {selected.application_scenarios.length > 0 && <section className="comp-detail__section"><h3>应用场景</h3><div className="comp-skill-tags">{selected.application_scenarios.map(s => <i key={s} className="comp-tag--scenario">{s}</i>)}</div></section>}
              <section className="comp-detail__section"><h3>来源证据</h3><SourceIdsDisplay ids={selected.source_ids} />{selected.source_count > 0 && <p style={{ color: "#6e6a78", fontSize: 11, marginTop: 8 }}>共 {selected.source_count} 条数据支持</p>}</section>
              <section className="comp-detail__section">
                <button className="comp-review-toggle" onClick={() => { setReviewsOpen(!reviewsOpen); if (!reviewsOpen && reviews.length === 0) loadReviews(selected.id); }} aria-label={reviewsOpen ? "收起审核历史" : "展开审核历史"}>
                  <Clock3 style={{ width: 14 }} /><span>审核历史</span>{reviewsLoading ? <span style={{ color: "#777180", fontSize: 11 }}>加载中…</span> : <span style={{ color: "#777180", fontSize: 11 }}>{reviews.length} 条记录</span>}{reviewsOpen ? <ChevronUp style={{ width: 14 }} /> : <ChevronDown style={{ width: 14 }} />}
                </button>
                {reviewsOpen && (
                  <div className="comp-review-timeline">
                    {reviewsLoading ? <p style={{ color: "#777180", fontSize: 12, textAlign: "center", padding: 16 }}>加载审核历史中…</p>
                      : reviews.length === 0 ? <p style={{ color: "#777180", fontSize: 12, textAlign: "center", padding: 16 }}>暂无审核记录</p>
                        : reviews.map(r => (
                          <div key={r.review_id} className="comp-review-item">
                            <div className="comp-review-item__dot" />
                            <div className="comp-review-item__content">
                              <div className="comp-review-item__head">
                                <span className={`comp-status comp-status--${r.status}`}>{statusLabel(r.status)}</span>
                                <span className="comp-review-item__editor">{r.editor}</span>
                                <time className="comp-review-item__time">{timeText(new Date(r.created_at))}</time>
                              </div>
                              {r.comment && <p className="comp-review-item__comment">{r.comment}</p>}
                              {r.edits && Object.keys(r.edits).length > 0 && <div className="comp-review-item__edits"><span>修改内容：</span><code>{JSON.stringify(r.edits, null, 2).slice(0, 300)}</code></div>}
                            </div>
                          </div>
                        ))}
                  </div>
                )}
              </section>
              <div className="comp-detail__actions">
                {selected.review_status === "pending" && (<>
                  <button className="comp-action-btn comp-action-btn--approve" onClick={() => submitReview(selected.id, "approved")} disabled={submitting} aria-label="批准"><ThumbsUp style={{ width: 16 }} /> {submitting ? "处理中…" : "批准"}</button>
                  <button className="comp-action-btn comp-action-btn--reject" onClick={() => submitReview(selected.id, "rejected")} disabled={submitting} aria-label="驳回"><ThumbsDown style={{ width: 16 }} /> {submitting ? "处理中…" : "驳回"}</button>
                </>)}
                <button className="ghost-action" onClick={() => { setEditForm({}); setEditOpen(true); }} disabled={submitting} aria-label="编辑"><Edit3 style={{ width: 14 }} /> 编辑</button>
                {selected.review_status !== "pending" && <button className="ghost-action" onClick={() => submitReview(selected.id, "pending")} disabled={submitting} aria-label="重置为待审核">重置为待审核</button>}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
