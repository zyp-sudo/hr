import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Interview, InterviewTag, InterviewFilters, InterviewStatus, InterviewViewMode, InterviewCandidate } from "../types/interview";
import { STATUS_LABELS } from "../types/interview";
import InterviewCalendar from "../components/interviews/InterviewCalendar";
import InterviewList from "../components/interviews/InterviewList";
import InterviewEditor from "../components/interviews/InterviewEditor";
import InterviewDetail from "../components/interviews/InterviewDetail";
import InterviewFiltersBar from "../components/interviews/InterviewFilters";
import { Plus, RefreshCw, CalendarDays, Clock3, CheckCircle2, XCircle, Pin, AlertCircle, Star, LayoutList, Kanban, Columns3 } from "lucide-react";

interface Props {
  isLoggedIn: boolean;
  onNavigate?: (page: string) => void;
  onFocusInterviewId?: () => string | undefined;
}

export default function InterviewManagement({ isLoggedIn, onNavigate }: Props) {
  // ── Data state ──
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [tags, setTags] = useState<InterviewTag[]>([]);
  const [candidates, setCandidates] = useState<InterviewCandidate[]>([]);
  const [favorites, setFavorites] = useState<string[]>([]);
  const [jobs, setJobs] = useState<Array<{ id: string; name: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState("");

  // ── UI state ──
  const [filters, setFilters] = useState<InterviewFilters>({
    search: "", status: "", round: "", priority: "", tagId: "",
    dateFrom: "", dateTo: "", isPinned: false, onlyFavorites: false, view: "list",
  });
  const [selectedInterview, setSelectedInterview] = useState<Interview | null>(null);
  const [editingInterview, setEditingInterview] = useState<Interview | null>(null);
  const [showEditor, setShowEditor] = useState(false);
  const [newDate, setNewDate] = useState<Date | null>(null);
  const [saving, setSaving] = useState(false);

  const notify = (msg: string) => { setToast(msg); setTimeout(() => setToast(""), 3000); };

  // ── Load data ──
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ivRes, tagRes, hrRes] = await Promise.all([
        fetch("/api/hr/interviews?pageSize=200").then((r) => r.json()),
        fetch("/api/hr/interview-tags").then((r) => r.json()),
        fetch("/api/hr/state").then((r) => r.json()),
      ]);
      setInterviews(ivRes.items || []);
      setTags(tagRes.items || []);
      setCandidates(hrRes.candidates || []);
      setFavorites(hrRes.favorites || []);
      setJobs((hrRes.jobs || []).concat([
        { id: "backend", name: "高级后端工程师" },
        { id: "ai", name: "AI 算法工程师" },
        { id: "frontend", name: "资深前端工程师" },
        { id: "product", name: "高级产品经理" },
      ]));
    } catch {
      notify("数据加载失败，请检查后端服务");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ── Deep-link from notification ──
  useEffect(() => {
    const focusId = sessionStorage.getItem("talentmatch-focus-interview");
    if (focusId && interviews.length > 0) {
      const iv = interviews.find((x) => x.id === focusId);
      if (iv) {
        setSelectedInterview(iv);
        sessionStorage.removeItem("talentmatch-focus-interview");
      }
    }
  }, [interviews]);

  // ── Derived data ──
  const filteredInterviews = useMemo(() => {
    let list = [...interviews];
    const f = filters;
    if (f.search) {
      const s = f.search.toLowerCase();
      list = list.filter((iv) =>
        `${iv.candidateName}${iv.jobTitle}${(iv.interviewers || []).join(" ")}${iv.title}`.toLowerCase().includes(s)
      );
    }
    if (f.status) list = list.filter((iv) => iv.status === f.status);
    if (f.round) list = list.filter((iv) => iv.round === f.round || iv.customRound === f.round);
    if (f.priority) list = list.filter((iv) => iv.priority === f.priority || iv.customPriority === f.priority);
    if (f.tagId) list = list.filter((iv) => (iv.tagIds || []).includes(f.tagId));
    if (f.dateFrom) list = list.filter((iv) => new Date(iv.startsAt) >= new Date(f.dateFrom));
    if (f.dateTo) list = list.filter((iv) => new Date(iv.startsAt) <= new Date(f.dateTo));
    if (f.isPinned) list = list.filter((iv) => Boolean(iv.isPinned));
    if (f.onlyFavorites) list = list.filter((iv) => favorites.includes(iv.candidateId));
    // Pinned first
    list.sort((a, b) => (b.isPinned ? 1 : 0) - (a.isPinned ? 1 : 0));
    return list;
  }, [interviews, filters, favorites]);

  const availableRounds = useMemo(() => {
    const set = new Set<string>();
    interviews.forEach((iv) => { if (iv.round) set.add(iv.customRound || iv.round); });
    return Array.from(set).sort();
  }, [interviews]);

  const stats = useMemo(() => {
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const todayEnd = new Date(todayStart.getTime() + 86400000);
    const weekEnd = new Date(todayStart.getTime() + 7 * 86400000);

    const today = interviews.filter((iv) => {
      try { const d = new Date(iv.startsAt); return d >= todayStart && d < todayEnd; } catch { return false; }
    }).length;

    const thisWeek = interviews.filter((iv) => {
      try { const d = new Date(iv.startsAt); return d >= todayStart && d < weekEnd; } catch { return false; }
    }).length;

    const pending = interviews.filter((iv) => iv.status === "pending").length;
    const scheduled = interviews.filter((iv) => iv.status === "scheduled").length;
    const completed = interviews.filter((iv) => iv.status === "completed").length;
    const cancelled = interviews.filter((iv) => iv.status === "cancelled").length;
    const pinned = interviews.filter((iv) => iv.isPinned).length;
    const upcoming = interviews.filter((iv) => iv.status === "scheduled" || iv.status === "in_progress").length;

    return { today, thisWeek, pending, scheduled, completed, cancelled, pinned, upcoming };
  }, [interviews]);

  // ── Actions ──
  const handleSave = async (data: Partial<Interview>) => {
    if (saving) return;
    setSaving(true);
    try {
      const isEdit = Boolean(editingInterview);
      const url = isEdit ? `/api/hr/interviews/${editingInterview!.id}` : "/api/hr/interviews";
      const method = isEdit ? "PATCH" : "POST";
      const res = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || "保存失败");
      }
      notify(isEdit ? "面试已更新" : "面试已创建");
      setShowEditor(false);
      setEditingInterview(null);
      setNewDate(null);
      await load();
    } catch (e) {
      notify(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      const res = await fetch(`/api/hr/interviews/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("删除失败");
      notify("面试已删除");
      setSelectedInterview(null);
      await load();
    } catch (e) {
      notify(e instanceof Error ? e.message : "删除失败");
    }
  };

  const handleStatusChange = async (id: string, status: string) => {
    try {
      await fetch(`/api/hr/interviews/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      await load();
      // Update selected interview if open
      if (selectedInterview?.id === id) {
        setSelectedInterview((prev) => prev ? { ...prev, status: status as InterviewStatus } : null);
      }
    } catch {
      notify("状态更新失败");
    }
  };

  const handleTogglePin = async (id: string) => {
    const iv = interviews.find((x) => x.id === id);
    if (!iv) return;
    try {
      await fetch(`/api/hr/interviews/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ isPinned: !iv.isPinned }),
      });
      await load();
    } catch {
      notify("操作失败");
    }
  };

  const handleToggleFavorite = async (candidateId: string) => {
    const isFav = favorites.includes(candidateId);
    try {
      await fetch(`/api/hr/favorites/${candidateId}`, { method: isFav ? "DELETE" : "PUT" });
      setFavorites((prev) => isFav ? prev.filter((id) => id !== candidateId) : [candidateId, ...prev]);
      notify(isFav ? "已取消关注" : "已添加关注");
    } catch {
      notify("操作失败");
    }
  };

  const handleTagCreate = async (name: string, color: string): Promise<InterviewTag> => {
    const res = await fetch("/api/hr/interview-tags", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, color }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error);
    }
    const tag = await res.json();
    setTags((prev) => [...prev, tag]);
    return tag;
  };

  const openCreate = (date?: Date) => {
    setEditingInterview(null);
    setNewDate(date || null);
    setShowEditor(true);
  };

  const openEdit = () => {
    if (!selectedInterview) return;
    setEditingInterview(selectedInterview);
    setShowEditor(true);
  };

  // ── Kanban view ──
  const kanbanColumns = useMemo(() => {
    const statuses: InterviewStatus[] = ["pending", "scheduled", "in_progress", "completed", "cancelled"];
    return statuses.map((status) => ({
      status,
      label: STATUS_LABELS[status],
      items: filteredInterviews.filter((iv) => iv.status === status),
      color: { pending: "#facc15", scheduled: "#60a5fa", in_progress: "#4ade80", completed: "#9bf2e9", cancelled: "#f87171" }[status],
    }));
  }, [filteredInterviews]);

  const candidateForInterview = (iv: Interview) => candidates.find((c) => c.id === iv.candidateId) || null;

  if (!isLoggedIn) {
    return (
      <main className="platform-main">
        <div className="iv-empty-state">
          <div className="iv-empty-state__icon"><CalendarDays /></div>
          <h2>面试管理</h2>
          <p>请先登录后查看和管理面试安排。</p>
        </div>
      </main>
    );
  }

  return (
    <main className="platform-main iv-management">
      {/* ── Page header ── */}
      <div className="page-heading">
        <div>
          <span className="slide-in-left" style={{ "--i": 0 } as React.CSSProperties}>INTERVIEW MANAGEMENT</span>
          <h2 className="slide-in-left" style={{ "--i": 1 } as React.CSSProperties}>面试管理</h2>
          <p className="slide-in-left" style={{ "--i": 2 } as React.CSSProperties}>集中管理面试安排、候选人跟进、面试状态与标签，支持日历、列表和看板视图。</p>
        </div>
        <div className="page-actions">
          <button className="ghost-action spring-hover" onClick={load} disabled={loading}>
            <RefreshCw className={loading ? "spin" : ""} /> {loading ? "加载中…" : "刷新"}
          </button>
          <button className="primary small-primary" onClick={() => openCreate()}>
            <Plus /> 新建面试
          </button>
        </div>
      </div>

      {/* ── Stats ── */}
      <section className="iv-stats">
        <div className="iv-stat"><CalendarDays /><span>今日面试</span><b>{stats.today}</b></div>
        <div className="iv-stat"><CalendarDays /><span>本周面试</span><b>{stats.thisWeek}</b></div>
        <div className="iv-stat" style={{ color: "#facc15" }}><AlertCircle /><span>待安排</span><b>{stats.pending}</b></div>
        <div className="iv-stat" style={{ color: "#60a5fa" }}><Clock3 /><span>已安排</span><b>{stats.scheduled}</b></div>
        <div className="iv-stat" style={{ color: "#9bf2e9" }}><CheckCircle2 /><span>已完成</span><b>{stats.completed}</b></div>
        <div className="iv-stat" style={{ color: "#f87171" }}><XCircle /><span>已取消</span><b>{stats.cancelled}</b></div>
        <div className="iv-stat" style={{ color: "#f59e0b" }}><Pin /><span>置顶</span><b>{stats.pinned}</b></div>
        <div className="iv-stat" style={{ color: "#4ade80" }}><AlertCircle /><span>即将开始</span><b>{stats.upcoming}</b></div>
      </section>

      {/* ── Filters ── */}
      <InterviewFiltersBar
        filters={filters}
        onChange={(patch) => setFilters((f) => ({ ...f, ...patch }))}
        tags={tags}
        rounds={availableRounds}
        availableStatuses={["pending", "scheduled", "in_progress", "completed", "cancelled"]}
      />

      {/* ── View switcher (quick buttons) ── */}
      <div className="iv-view-switcher">
        {(["list", "calendar", "kanban"] as InterviewViewMode[]).map((v) => (
          <button
            key={v}
            className={filters.view === v ? "active" : ""}
            onClick={() => setFilters((f) => ({ ...f, view: v }))}
          >
            {v === "calendar" ? <CalendarDays /> : v === "kanban" ? <Columns3 /> : <LayoutList />}
            {v === "calendar" ? "日历" : v === "kanban" ? "看板" : "列表"}
          </button>
        ))}
      </div>

      {/* ── Views ── */}
      <section className="iv-content">
        {loading && interviews.length === 0 ? (
          <div className="iv-empty-state"><RefreshCw className="spin" /><p>加载中…</p></div>
        ) : (
          <>
            {filters.view === "calendar" && (
              <InterviewCalendar
                interviews={filteredInterviews}
                tags={tags}
                onSelect={(iv) => setSelectedInterview(iv)}
                onCreate={(date) => openCreate(date)}
              />
            )}

            {filters.view === "list" && (
              <InterviewList
                interviews={filteredInterviews}
                tags={tags}
                favorites={favorites}
                onSelect={(iv) => setSelectedInterview(iv)}
                onTogglePin={handleTogglePin}
                onStatusChange={handleStatusChange}
              />
            )}

            {filters.view === "kanban" && (
              <div className="iv-kanban">
                {kanbanColumns.map((col) => (
                  <div key={col.status} className="iv-kanban__col">
                    <div className="iv-kanban__col-head" style={{ borderColor: col.color }}>
                      <span className="iv-kanban__col-dot" style={{ background: col.color }} />
                      <b>{col.label}</b>
                      <em>{col.items.length}</em>
                    </div>
                    <div className="iv-kanban__col-body">
                      {col.items.map((iv) => {
                        const ivTags = tags.filter((t) => (iv.tagIds || []).includes(t.id));
                        const isFav = favorites.includes(iv.candidateId);
                        return (
                          <button
                            key={iv.id}
                            className={`iv-kanban__card ${iv.isPinned ? "iv-kanban__card--pinned" : ""}`}
                            onClick={() => setSelectedInterview(iv)}
                          >
                            <div className="iv-kanban__card-head">
                              <span className="iv-kanban__card-avatar">{(iv.candidateName || "匿").slice(0, 1)}</span>
                              <span>
                                <b>{iv.candidateName}{isFav && <Star fill="currentColor" className="iv-list__fav-star" />}</b>
                                <small>{iv.jobTitle}</small>
                              </span>
                              {iv.isPinned && <Pin className="iv-kanban__card-pin" />}
                            </div>
                            <div className="iv-kanban__card-time">
                              {new Date(iv.startsAt).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false })}
                            </div>
                            <div className="iv-kanban__card-interviewers">
                              {(iv.interviewers || []).join("、") || "—"}
                            </div>
                            {ivTags.length > 0 && (
                              <div className="iv-kanban__card-tags">
                                {ivTags.slice(0, 2).map((t) => (
                                  <span key={t.id} style={{ color: t.color }}>{t.name}</span>
                                ))}
                              </div>
                            )}
                          </button>
                        );
                      })}
                      {!col.items.length && <p className="iv-kanban__col-empty">暂无</p>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </section>

      {/* ── Detail drawer ── */}
      {selectedInterview && (
        <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setSelectedInterview(null); }}>
          <div className="dialog iv-detail-dialog">
            <InterviewDetail
              interview={selectedInterview}
              tags={tags}
              candidate={candidateForInterview(selectedInterview)}
              favorites={favorites}
              onEdit={openEdit}
              onDelete={() => handleDelete(selectedInterview.id)}
              onClose={() => setSelectedInterview(null)}
              onToggleFavorite={handleToggleFavorite}
              onTogglePin={handleTogglePin}
              onStatusChange={handleStatusChange}
            />
          </div>
        </div>
      )}

      {/* ── Editor modal ── */}
      {showEditor && (
        <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) { setShowEditor(false); setEditingInterview(null); } }}>
          <div className="dialog iv-editor-dialog">
            <InterviewEditor
              interview={editingInterview}
              candidates={candidates.map((c) => ({ id: c.id, name: c.name }))}
              jobs={jobs}
              tags={tags}
              onSave={handleSave}
              onClose={() => { setShowEditor(false); setEditingInterview(null); }}
              onTagCreate={handleTagCreate}
            />
          </div>
        </div>
      )}

      {/* ── Toast ── */}
      {toast && (
        <div className="toast"><span>{toast}</span><button onClick={() => setToast("")}><XCircle /></button></div>
      )}
    </main>
  );
}
