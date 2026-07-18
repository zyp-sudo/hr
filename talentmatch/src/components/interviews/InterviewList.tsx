import type { Interview, InterviewTag } from "../../types/interview";
import { STATUS_LABELS } from "../../types/interview";
import { Star, Pin, CalendarDays, UserRound, ChevronRight, MapPin } from "lucide-react";

interface Props {
  interviews: Interview[];
  tags: InterviewTag[];
  favorites: string[];
  onSelect: (interview: Interview) => void;
  onTogglePin: (id: string) => void;
  onStatusChange: (id: string, status: string) => void;
}

const statusColors: Record<string, string> = {
  pending: "#facc15",
  scheduled: "#60a5fa",
  in_progress: "#4ade80",
  completed: "#9bf2e9",
  cancelled: "#f87171",
};

export default function InterviewList({ interviews, tags, favorites, onSelect, onTogglePin, onStatusChange }: Props) {
  if (!interviews.length) {
    return (
      <div className="iv-list iv-list--empty">
        <CalendarDays />
        <h3>暂无面试记录</h3>
        <p>点击右上角「新建面试」按钮，创建第一条面试安排。</p>
      </div>
    );
  }

  const timeStr = (iso: string) => {
    try {
      const d = new Date(iso);
      const today = new Date();
      const isToday = d.toDateString() === today.toDateString();
      const time = d.toLocaleString("zh-CN", {
        month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit", hour12: false,
      });
      return isToday ? `今天 ${time.slice(6)}` : time;
    } catch { return iso; }
  };

  return (
    <div className="iv-list">
      <div className="iv-list__header">
        <span className="iv-list__header-cell iv-list__header-cell--pin" />
        <span className="iv-list__header-cell iv-list__header-cell--time">时间</span>
        <span className="iv-list__header-cell iv-list__header-cell--candidate">候选人</span>
        <span className="iv-list__header-cell iv-list__header-cell--job">岗位</span>
        <span className="iv-list__header-cell iv-list__header-cell--interviewers">面试官</span>
        <span className="iv-list__header-cell iv-list__header-cell--status">状态</span>
        <span className="iv-list__header-cell iv-list__header-cell--tags">标签</span>
        <span className="iv-list__header-cell iv-list__header-cell--actions" />
      </div>
      {interviews.map((iv) => {
        const ivTags = tags.filter((t) => (iv.tagIds || []).includes(t.id));
        const isFav = favorites.includes(iv.candidateId);
        return (
          <div
            key={iv.id}
            className={`iv-list__row ${iv.isPinned ? "iv-list__row--pinned" : ""}`}
            onClick={() => onSelect(iv)}
          >
            {/* Pin */}
            <span className="iv-list__cell iv-list__cell--pin">
              <button
                onClick={(e) => { e.stopPropagation(); onTogglePin(iv.id); }}
                className={`iv-list__pin-btn ${iv.isPinned ? "active" : ""}`}
                title={iv.isPinned ? "取消置顶" : "置顶"}
              >
                <Pin fill={iv.isPinned ? "currentColor" : "none"} />
              </button>
            </span>

            {/* Time */}
            <span className="iv-list__cell iv-list__cell--time">
              <CalendarDays />
              <span>
                <b>{timeStr(iv.startsAt)}</b>
                <small>{iv.customRound || iv.round}</small>
              </span>
            </span>

            {/* Candidate */}
            <span className="iv-list__cell iv-list__cell--candidate">
              <span className="iv-list__candidate-avatar">{(iv.candidateName || "匿").slice(0, 1)}</span>
              <span>
                <b>{iv.candidateName}{isFav && <Star fill="currentColor" className="iv-list__fav-star" />}</b>
                {iv.location && <small><MapPin /> {iv.location}</small>}
              </span>
            </span>

            {/* Job */}
            <span className="iv-list__cell iv-list__cell--job">
              <span>{iv.jobTitle}</span>
            </span>

            {/* Interviewers */}
            <span className="iv-list__cell iv-list__cell--interviewers">
              <UserRound />
              <span>{(iv.interviewers || []).join("、") || "—"}</span>
            </span>

            {/* Status */}
            <span className="iv-list__cell iv-list__cell--status" onClick={(e) => e.stopPropagation()}>
              <select
                value={iv.status}
                onChange={(e) => onStatusChange(iv.id, e.target.value)}
                style={{ borderColor: statusColors[iv.status] || "#666", color: statusColors[iv.status] || "#ccc" }}
                className="iv-list__status-select"
              >
                {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </span>

            {/* Tags */}
            <span className="iv-list__cell iv-list__cell--tags">
              {ivTags.slice(0, 3).map((t) => (
                <span key={t.id} className="iv-list__tag" style={{ borderColor: t.color, background: `${t.color}22` }}>
                  {t.name}
                </span>
              ))}
              {ivTags.length > 3 && <span className="iv-list__tag-more">+{ivTags.length - 3}</span>}
            </span>

            {/* Actions */}
            <span className="iv-list__cell iv-list__cell--actions">
              <ChevronRight />
            </span>
          </div>
        );
      })}
    </div>
  );
}
