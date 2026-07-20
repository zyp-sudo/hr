import { useState, useEffect, useCallback, useRef } from "react";
import {
  AlertTriangle, Check, ChevronDown, ChevronUp, Clock3,
  Edit3, RefreshCw, Search, ThumbsDown, ThumbsUp, TrendingUp, X
} from "lucide-react";
import type { ReviewEditPayload, ReviewRecord } from "../types";
import {
  validateDiscoveriesResponse,
  ValidationError,
  type ValidatedDiscoveryItem,
} from "../utils/competitionValidators";
import JobSectionHeader from "./JobSectionHeader";
import AddJobButton from "./AddJobButton";

const API_BASE = "/api/platform/storage/api/competition";

function timeText(date: Date) {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(date);
}

function getSourceName(id: string): string {
  if (id === "manual-entry") return "人工录入";
  if (id.startsWith("src-boss-")) return "BOSS直聘";
  if (id.startsWith("src-lagou-")) return "拉勾招聘";
  if (id.startsWith("src-51job-")) return "前程无忧";
  if (id.startsWith("src-zhilian-")) return "智联招聘";
  if (id.startsWith("src-liepin-")) return "猎聘";
  return "其他招聘渠道";
}

/** Parse FastAPI 422 validation error into a readable Chinese message.
 *  Handles both the custom exception handler format ({errors:[...]}) and
 *  route-raised HTTPException (detail as string or string array). */
function parseValidationError(detail: unknown, errors?: unknown): string {
  // FastAPI custom validation_exception_handler returns {errors: [...]}
  if (Array.isArray(errors) && errors.length > 0) {
    const messages = (errors as any[]).map((e: any) => {
      const loc = (e.loc || []).slice(1).join(" > ");
      const msg = String(e.msg || "输入无效").replace(/^Value error, /, "");
      return loc ? `${loc}: ${msg}` : msg;
    });
    if (messages.length) return messages.join("；");
  }
  // Route-raised HTTPException: detail is a Chinese string
  if (typeof detail === "string" && detail !== "Request validation failed") return detail;
  // Route-raised: detail is an array of strings
  if (Array.isArray(detail)) {
    const messages = detail.map((e: any) => {
      if (typeof e === "string") return e;
      const loc = (e.loc || []).slice(1).join(" > ");
      const msg = String(e.msg || e || "输入无效").replace(/^Value error, /, "");
      return loc ? `${loc}: ${msg}` : msg;
    });
    return messages.length ? messages.join("；") : "输入校验失败";
  }
  return "输入校验失败，请检查填写内容";
}

function SourceIdsDisplay({ ids }: { ids: string[] }) {
  const [expanded, setExpanded] = useState(false);
  if (!ids || ids.length === 0) return <span style={{ color: "#667085", fontSize: 12 }}>暂无来源信息</span>;

  // Group by platform name, count per platform
  const grouped = new Map<string, number>();
  for (const id of ids) {
    const name = getSourceName(id);
    grouped.set(name, (grouped.get(name) || 0) + 1);
  }
  const entries = Array.from(grouped.entries());
  const visible = expanded ? entries : entries.slice(0, 5);

  return (
    <div className="comp-source-platforms">
      {visible.map(([name, count]) => (
        <span key={name} className="comp-source-platforms__tag">
          {name}
          <em>{count}条</em>
        </span>
      ))}
      {entries.length > 5 && (
        <button className="comp-source-toggle" onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}>
          {expanded ? <><ChevronUp style={{ width: 14 }} /> 收起来源</>
            : <><ChevronDown style={{ width: 14 }} /> 展开来源（共 {entries.length} 个平台）</>}
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

  // AbortController to cancel stale in-flight load requests
  const loadAbortRef = useRef<AbortController | null>(null);
  // Request sequence counter to drop stale responses
  const loadSeqRef = useRef(0);

  /* ── Add discovery dialog state ── */
  const [adding, setAdding] = useState(false);
  const [addSubmitting, setAddSubmitting] = useState(false);
  const [addError, setAddError] = useState("");
  const [addForm, setAddForm] = useState({
    name: "",
    responsibilities: "",
    required_skills: "",
    bonus_skills: "",
    application_scenarios: "",
    source_note: "人工录入",
  });
  const addNameRef = useRef<HTMLInputElement>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  };

  /** Reset and open the add-dialog. */
  const openAddDialog = () => {
    setAddForm({
      name: "",
      responsibilities: "",
      required_skills: "",
      bonus_skills: "",
      application_scenarios: "",
      source_note: "人工录入",
    });
    setAddError("");
    setAdding(true);
    setTimeout(() => addNameRef.current?.focus(), 80);
  };

  /** Parse validation error and keep user's form content. */
  const handleAddError = (res: Response, errBody: any): string => {
    if (res.status === 409) {
      return errBody.detail || `岗位已存在，请勿重复添加`;
    }
    if (res.status === 422) {
      return parseValidationError(errBody.detail, errBody.errors);
    }
    return errBody.detail || `创建失败 (HTTP ${res.status})`;
  };

  /** Submit a new discovery record. */
  const submitAdd = async () => {
    // ── Client-side validation ──
    const name = addForm.name.trim();
    if (!name) { setAddError("岗位名称不能为空"); addNameRef.current?.focus(); return; }
    if (name.length > 200) { setAddError("岗位名称不能超过 200 个字符"); addNameRef.current?.focus(); return; }

    const responsibilities = addForm.responsibilities
      .split("\n")
      .map(s => s.trim())
      .filter(Boolean);
    if (responsibilities.length === 0) { setAddError("岗位职责至少需要填写一条（每行一条）"); return; }

    const parseSkills = (raw: string): string[] => {
      return [...new Set(
        raw.split(/[,，、\n]/)
          .map(s => s.trim())
          .filter(s => s.length > 0 && s.length <= 80)
      )];
    };
    const required_skills = parseSkills(addForm.required_skills);
    const bonus_skills = parseSkills(addForm.bonus_skills);
    const application_scenarios = addForm.application_scenarios
      .split(/[,，、\n]/)
      .map(s => s.trim())
      .filter(Boolean);

    setAddSubmitting(true);
    setAddError("");

    try {
      const res = await fetch(`${API_BASE}/discoveries`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          responsibilities,
          required_skills,
          bonus_skills,
          application_scenarios,
          source_note: addForm.source_note.trim() || "人工录入",
        }),
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(handleAddError(res, errBody));
      }

      // Success
      setAdding(false);
      showToast(`「${name}」已添加，状态为待审核`);
      // Deterministically reload with pending filter — pass explicit status
      // to avoid the race between setFilter("pending") and load().
      await load("pending");
      // Ensure filter UI matches
      setFilter("pending");
    } catch (e: any) {
      setAddError(e.message || "创建失败，请稍后重试");
    } finally {
      setAddSubmitting(false);
    }
  };

  /**
   * Load discoveries.  When `explicitStatus` is provided it is used
   * directly; otherwise the current `filter` state is used.  This removes
   * the race between setFilter() and load() after creation.
   *
   * Uses AbortController + sequence counter so only the most recent
   * request's result is applied.
   */
  const load = useCallback(async (explicitStatus?: string) => {
    // Abort any in-flight load
    loadAbortRef.current?.abort();
    const controller = new AbortController();
    loadAbortRef.current = controller;
    const seq = ++loadSeqRef.current;

    setLoading(true);
    setError("");
    try {
      const status = explicitStatus ?? filter;
      const params = status !== "all" ? `?status=${status}` : "";
      const res = await fetch(`${API_BASE}/discoveries${params}`, {
        signal: controller.signal,
      });

      // Drop stale response
      if (seq !== loadSeqRef.current) return;

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `服务返回 HTTP ${res.status}`);
      }
      const validated = await validateDiscoveriesResponse(res);
      // Double-check we're still the latest request
      if (seq !== loadSeqRef.current) return;

      setItems(validated.items);
      setUpdated(timeText(new Date()));
      if (selected) {
        const refreshed = validated.items.find(i => i.id === selected.id);
        if (refreshed) setSelected(refreshed);
      }
    } catch (e: any) {
      if (controller.signal.aborted) return;
      setError(e.name === "ValidationError" ? e.message : (e.message || "无法加载新岗位发现数据"));
      setItems([]);
    } finally {
      if (seq === loadSeqRef.current) {
        setLoading(false);
      }
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
  return (
    <div className="comp-discovery">
      {toast && (
        <div className="comp-toast">
          <Check style={{ width: 16, color: "#4ade80" }} /><span>{toast}</span>
          <button onClick={() => setToast("")} aria-label="关闭提示"><X style={{ width: 14 }} /></button>
        </div>
      )}

      <JobSectionHeader eyebrow="JOB DISCOVERY" title="新岗位发现" />

      <div className="page-actions" style={{ marginBottom: 16 }}>
        <span><Clock3 style={{ width: 14, verticalAlign: "middle", marginRight: 4 }} />{updated || "等待数据"}</span>
        <button className="ghost-action spring-hover" onClick={() => load()} disabled={loading} aria-label="刷新数据"><RefreshCw className={loading ? "spin" : ""} />{loading ? "加载中" : "刷新"}</button>
        <AddJobButton onClick={openAddDialog} />
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
          <button className="ghost-action" onClick={() => load()} aria-label="重试加载">重试</button>
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
          {items.length === 0 && <button className="ghost-action" onClick={() => load()} style={{ marginTop: 12 }}>重新加载</button>}
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
        <div className="discovery-dialog-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget){setSelected(null);setEditOpen(false);setReviewsOpen(false)}}} onKeyDown={e=>{if(e.key==="Escape"){setSelected(null);setEditOpen(false);setReviewsOpen(false)}}}>
          <div className="discovery-dialog" role="dialog" aria-modal="true" aria-labelledby="discovery-dialog-title">
            <div className="comp-detail__header">
              <div>
                <span className={`comp-status comp-status--${selected.review_status}`}>{statusLabel(selected.review_status)}</span>
                <h2 id="discovery-dialog-title">{selected.name}</h2>
                <p className="comp-detail__meta">
                  增长率 {Math.round(selected.growth_rate * 100)}% · {selected.source_ids.length} 个来源
                  {selected.reviewed_at ? ` · 审核于 ${timeText(new Date(selected.reviewed_at))}` : ""}
                  {selected.created_at ? ` · 创建于 ${timeText(new Date(selected.created_at))}` : ""}
                </p>
              </div>
              <button className="comp-detail__close" onClick={()=>{setSelected(null);setEditOpen(false);setReviewsOpen(false)}} aria-label="关闭详情"><X/></button>
            </div>
            {editOpen?(
              <div className="comp-edit-form">
                <label className="comp-field"><span>岗位名称</span><input value={editForm.name!==undefined?(editForm.name??""):selected.name} onChange={e=>setEditForm(f=>({...f,name:e.target.value}))} aria-label="编辑岗位名称"/></label>
                <label className="comp-field"><span>岗位职责（一行一条）</span><textarea value={editForm.responsibilities!==undefined?(editForm.responsibilities||[]).join("\n"):(selected.responsibilities||[]).join("\n")} onChange={e=>setEditForm(f=>({...f,responsibilities:e.target.value.split("\n").filter(Boolean)}))} aria-label="编辑岗位职责"/></label>
                <label className="comp-field"><span>必备技能（JSON 格式）</span><textarea value={editForm.required_skills!==undefined?JSON.stringify(editForm.required_skills,null,2):JSON.stringify(selected.required_skills,null,2)} onChange={e=>{try{setEditForm(f=>({...f,required_skills:JSON.parse(e.target.value)}))}catch{/* ignore */}}} aria-label="编辑必备技能"/></label>
                <label className="comp-field"><span>加分技能（JSON 格式）</span><textarea value={editForm.bonus_skills!==undefined?JSON.stringify(editForm.bonus_skills,null,2):JSON.stringify(selected.bonus_skills,null,2)} onChange={e=>{try{setEditForm(f=>({...f,bonus_skills:JSON.parse(e.target.value)}))}catch{/* ignore */}}} aria-label="编辑加分技能"/></label>
                <div className="comp-edit-actions">
                  <button className="ghost-action" onClick={()=>{setEditOpen(false);setActionError("")}} disabled={submitting}>取消</button>
                  <button className="primary small-primary" onClick={saveEdit} disabled={submitting}>{submitting?"保存中…":"保存修改"}</button>
                </div>
              </div>
            ):(
              <>
                <section className="comp-detail__section"><h3>岗位职责</h3>{(selected.responsibilities||[]).length>0?<ul>{selected.responsibilities.map((r,i)=><li key={i}>{r}</li>)}</ul>:<p style={{color:"#667085",fontSize:12}}>暂无职责描述</p>}</section>
                <section className="comp-detail__section"><h3>必备技能</h3><div className="comp-skill-tags">{selected.required_skills.length?selected.required_skills.map(s=><i key={s.name} className="comp-tag--required" title={`等级: ${s.level||"未指定"} | 来源: ${(s.source_ids||[]).join(", ")}`}>{s.name}{s.level?` (${s.level})`:""}</i>):<span style={{color:"#667085",fontSize:12}}>无</span>}</div></section>
                <section className="comp-detail__section"><h3>加分技能</h3><div className="comp-skill-tags">{selected.bonus_skills.length?selected.bonus_skills.map(s=><i key={s.name} className="comp-tag--bonus" title={`来源: ${(s.source_ids||[]).join(", ")}`}>{s.name}</i>):<span style={{color:"#667085",fontSize:12}}>无</span>}</div></section>
                {selected.application_scenarios.length>0&&<section className="comp-detail__section"><h3>应用场景</h3><div className="comp-skill-tags">{selected.application_scenarios.map(s=><i key={s} className="comp-tag--scenario">{s}</i>)}</div></section>}
                <section className="comp-detail__section"><h3>来源证据</h3><SourceIdsDisplay ids={selected.source_ids}/>{selected.source_count>0&&<p style={{color:"#667085",fontSize:11,marginTop:8}}>共 {selected.source_count} 条数据支持</p>}{selected.source_note&&<p style={{color:"#667085",fontSize:11,marginTop:4}}>来源说明：{selected.source_note}</p>}</section>
                <section className="comp-detail__section">
                  <button className="comp-review-toggle" onClick={()=>{setReviewsOpen(!reviewsOpen);if(!reviewsOpen&&reviews.length===0)loadReviews(selected.id)}} aria-label={reviewsOpen?"收起审核历史":"展开审核历史"}>
                    <Clock3 style={{width:14}}/><span>审核历史</span>{reviewsLoading?<span style={{color:"#667085",fontSize:11}}>加载中…</span>:<span style={{color:"#667085",fontSize:11}}>{reviews.length} 条记录</span>}{reviewsOpen?<ChevronUp style={{width:14}}/>:<ChevronDown style={{width:14}}/>}
                  </button>
                  {reviewsOpen&&(
                    <div className="comp-review-timeline">
                      {reviewsLoading?<p style={{color:"#667085",fontSize:12,textAlign:"center",padding:16}}>加载审核历史中…</p>
                        :reviews.length===0?<p style={{color:"#667085",fontSize:12,textAlign:"center",padding:16}}>暂无审核记录</p>
                          :reviews.map(r=>(
                            <div key={r.review_id} className="comp-review-item">
                              <div className="comp-review-item__dot"/>
                              <div className="comp-review-item__content">
                                <div className="comp-review-item__head">
                                  <span className={`comp-status comp-status--${r.status}`}>{statusLabel(r.status)}</span>
                                  <span className="comp-review-item__editor">{r.editor}</span>
                                  <time className="comp-review-item__time">{timeText(new Date(r.created_at))}</time>
                                </div>
                                {r.comment&&<p className="comp-review-item__comment">{r.comment}</p>}
                                {r.edits&&Object.keys(r.edits).length>0&&<div className="comp-review-item__edits"><span>修改内容：</span><code>{JSON.stringify(r.edits,null,2).slice(0,300)}</code></div>}
                              </div>
                            </div>
                          ))}
                    </div>
                  )}
                </section>
                <div className="comp-detail__actions">
                  {selected.review_status==="pending"&&(<>
                    <button className="comp-action-btn comp-action-btn--approve" onClick={()=>submitReview(selected.id,"approved")} disabled={submitting} aria-label="批准"><ThumbsUp style={{width:16}}/>{submitting?"处理中…":"批准"}</button>
                    <button className="comp-action-btn comp-action-btn--reject" onClick={()=>submitReview(selected.id,"rejected")} disabled={submitting} aria-label="驳回"><ThumbsDown style={{width:16}}/>{submitting?"处理中…":"驳回"}</button>
                  </>)}
                  <button className="ghost-action" onClick={()=>{setEditForm({});setEditOpen(true)}} disabled={submitting} aria-label="编辑"><Edit3 style={{width:14}}/>编辑</button>
                  {selected.review_status!=="pending"&&<button className="ghost-action" onClick={()=>submitReview(selected.id,"pending")} disabled={submitting} aria-label="重置为待审核">重置为待审核</button>}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ═══════ Add Discovery Dialog ═══════ */}
      {adding && (
        <div
          className="discovery-dialog-backdrop"
          onMouseDown={e => { if (e.target === e.currentTarget && !addSubmitting) setAdding(false); }}
          onKeyDown={e => { if (e.key === "Escape" && !addSubmitting) setAdding(false); }}
        >
          <div className="discovery-dialog" role="dialog" aria-modal="true" aria-labelledby="add-discovery-title">
            <div className="comp-detail__header">
              <div>
                <h2 id="add-discovery-title">添加新岗位</h2>
                <p className="comp-detail__meta">手动录入新岗位发现记录，提交后将进入待审核列表。</p>
              </div>
              <button
                className="comp-detail__close"
                onClick={() => setAdding(false)}
                disabled={addSubmitting}
                aria-label="关闭"
              >
                <X />
              </button>
            </div>

            {addError && (
              <div className="comp-error-banner" style={{ margin: "0 28px 16px" }}>
                <AlertTriangle /><div><span>{addError}</span></div>
                <button className="ghost-action" onClick={() => setAddError("")} aria-label="关闭错误"><X /></button>
              </div>
            )}

            <div className="comp-edit-form">
              <label className="comp-field">
                <span>岗位名称 <em style={{ color: "#dc2626", fontStyle: "normal" }}>*</em></span>
                <input
                  ref={addNameRef}
                  value={addForm.name}
                  onChange={e => setAddForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="例如：AI 提示工程师"
                  maxLength={200}
                  aria-label="岗位名称（必填）"
                />
              </label>

              <label className="comp-field">
                <span>岗位职责 <em style={{ color: "#dc2626", fontStyle: "normal" }}>*</em></span>
                <textarea
                  value={addForm.responsibilities}
                  onChange={e => setAddForm(f => ({ ...f, responsibilities: e.target.value }))}
                  placeholder={"每行一条职责，例如：\n设计并优化 AI 提示词模板\n分析用户意图并迭代提示策略"}
                  rows={4}
                  aria-label="岗位职责（必填，每行一条）"
                />
              </label>

              <label className="comp-field">
                <span>必备技能</span>
                <input
                  value={addForm.required_skills}
                  onChange={e => setAddForm(f => ({ ...f, required_skills: e.target.value }))}
                  placeholder="使用逗号、顿号或空格分隔，例如：Python, LLM, Prompt Engineering"
                  aria-label="必备技能"
                />
              </label>

              <label className="comp-field">
                <span>加分技能</span>
                <input
                  value={addForm.bonus_skills}
                  onChange={e => setAddForm(f => ({ ...f, bonus_skills: e.target.value }))}
                  placeholder="使用逗号、顿号或空格分隔，例如：RAG, LangChain"
                  aria-label="加分技能"
                />
              </label>

              <label className="comp-field">
                <span>应用场景</span>
                <input
                  value={addForm.application_scenarios}
                  onChange={e => setAddForm(f => ({ ...f, application_scenarios: e.target.value }))}
                  placeholder="使用逗号、顿号或空格分隔，例如：智能客服, 内容生成"
                  aria-label="应用场景"
                />
              </label>

              <label className="comp-field">
                <span>来源说明</span>
                <input
                  value={addForm.source_note}
                  onChange={e => setAddForm(f => ({ ...f, source_note: e.target.value }))}
                  placeholder="人工录入"
                  maxLength={200}
                  aria-label="来源说明"
                />
              </label>

              <div className="comp-edit-actions">
                <button
                  className="ghost-action"
                  onClick={() => setAdding(false)}
                  disabled={addSubmitting}
                >
                  取消
                </button>
                <button
                  className="primary small-primary"
                  onClick={submitAdd}
                  disabled={addSubmitting}
                >
                  {addSubmitting ? "提交中…" : "提交"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
