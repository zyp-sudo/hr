import { useState } from "react";
import type { Interview, InterviewTag, InterviewCandidate } from "../../types/interview";
import { STATUS_LABELS, CONTACT_STATUS_LABELS } from "../../types/interview";
import { X, Edit2, Trash2, Phone, Mail, FileText, Star, Pin, CalendarDays, Clock3, MapPin, Video, UserRound, Tag, CheckCircle2, AlertCircle, Copy, ExternalLink } from "lucide-react";

interface Props {
  interview: Interview;
  tags: InterviewTag[];
  candidate?: InterviewCandidate | null;
  favorites: string[];
  onEdit: () => void;
  onDelete: () => void;
  onClose: () => void;
  onToggleFavorite: (candidateId: string) => void;
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

export default function InterviewDetail({ interview, tags, candidate, favorites, onEdit, onDelete, onClose, onToggleFavorite, onTogglePin, onStatusChange }: Props) {
  const [showResume, setShowResume] = useState(false);
  const [copied, setCopied] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);

  const copyText = (text: string, label: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(label);
      setTimeout(() => setCopied(""), 2000);
    });
  };

  const interviewTags = tags.filter((t) => (interview.tagIds || []).includes(t.id));
  const isFavorite = candidate ? favorites.includes(candidate.id) : false;

  const timeStr = (iso: string) => {
    try {
      return new Date(iso).toLocaleString("zh-CN", {
        year: "numeric", month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit", hour12: false,
      });
    } catch { return iso; }
  };

  const selectedTag = (interview.tagIds || [])[0];

  return (
    <div className="iv-detail">
      <div className="iv-detail__head">
        <div>
          <span className="iv-detail__status" style={{ borderColor: statusColors[interview.status], color: statusColors[interview.status] }}>
            {STATUS_LABELS[interview.status as keyof typeof STATUS_LABELS] || interview.status}
          </span>
          <h2>{interview.title || `${interview.candidateName} · ${interview.jobTitle}`}</h2>
          <p>{interview.candidateName} · {interview.jobTitle}</p>
        </div>
        <button onClick={onClose} aria-label="关闭"><X /></button>
      </div>

      <div className="iv-detail__body">
        {/* ── Time & Format ── */}
        <section className="iv-detail__section">
          <h3>面试信息</h3>
          <div className="iv-detail__info-grid">
            <div className="iv-detail__info-item"><CalendarDays /> <span>开始</span> <b>{timeStr(interview.startsAt)}</b></div>
            <div className="iv-detail__info-item"><CalendarDays /> <span>结束</span> <b>{timeStr(interview.endsAt)}</b></div>
            <div className="iv-detail__info-item"><Clock3 /> <span>时区</span> <b>{interview.timezone}</b></div>
            <div className="iv-detail__info-item"><span>形式</span> <b>{interview.customFormat || interview.format}</b></div>
            <div className="iv-detail__info-item"><span>轮次</span> <b>{interview.customRound || interview.round}</b></div>
            <div className="iv-detail__info-item"><span>优先级</span> <b style={{ color: interview.priority === "紧急" ? "#f87171" : interview.priority === "重要" ? "#facc15" : "#9bf2e9" }}>{interview.customPriority || interview.priority}</b></div>
          </div>
        </section>

        {/* ── Interviewers ── */}
        <section className="iv-detail__section">
          <h3>面试官</h3>
          <div className="iv-detail__interviewers">
            {(interview.interviewers || []).map((name, i) => (
              <span key={i} className="iv-detail__interviewer"><UserRound /> {name}</span>
            ))}
          </div>
        </section>

        {/* ── Location & Meeting ── */}
        {(interview.location || interview.meetingUrl) && (
          <section className="iv-detail__section">
            <h3>地点与链接</h3>
            {interview.location && <div className="iv-detail__info-item"><MapPin /> <b>{interview.location}</b></div>}
            {interview.meetingUrl && (
              <a href={interview.meetingUrl} target="_blank" rel="noreferrer" className="iv-detail__link">
                <Video /> {interview.meetingUrl} <ExternalLink />
              </a>
            )}
          </section>
        )}

        {/* ── Tags ── */}
        <section className="iv-detail__section">
          <h3>标签</h3>
          <div className="iv-detail__tags">
            {interviewTags.length ? interviewTags.map((t) => (
              <span key={t.id} className="iv-detail__tag" style={{ borderColor: t.color, background: `${t.color}22` }}>
                <span style={{ background: t.color }} />{t.name}
              </span>
            )) : <span className="iv-detail__empty">暂无标签</span>}
          </div>
        </section>

        {/* ── Candidate contact ── */}
        <section className="iv-detail__section">
          <h3>候选人信息</h3>
          <div className="iv-detail__candidate">
            <div className="iv-detail__candidate-name">
              <span className="iv-detail__candidate-avatar">{(interview.candidateName || "匿").slice(0, 1)}</span>
              <div>
                <b>{interview.candidateName || "匿名候选人"}</b>
                <small>{candidate?.stage || "—"}{candidate?.education ? ` · ${candidate.education}` : ""}{candidate?.experienceYears ? ` · ${candidate.experienceYears}年` : ""}</small>
              </div>
            </div>
            <div className="iv-detail__contacts">
              {candidate?.phone ? (
                <div className="iv-detail__contact-row">
                  <Phone /> <span>{candidate.phone}</span>
                  <a href={`tel:${candidate.phone}`} className="iv-detail__contact-btn" title="拨号">拨打</a>
                  <button className="iv-detail__contact-btn" onClick={() => copyText(candidate.phone!, "电话")} title="复制">
                    {copied === "电话" ? <CheckCircle2 /> : <Copy />}
                  </button>
                </div>
              ) : (
                <div className="iv-detail__contact-row iv-detail__contact-row--empty"><Phone /> <span>未填写电话</span></div>
              )}
              {candidate?.email ? (
                <div className="iv-detail__contact-row">
                  <Mail /> <span>{candidate.email}</span>
                  <a href={`mailto:${candidate.email}`} className="iv-detail__contact-btn" title="发送邮件">邮件</a>
                  <button className="iv-detail__contact-btn" onClick={() => copyText(candidate.email!, "邮箱")} title="复制">
                    {copied === "邮箱" ? <CheckCircle2 /> : <Copy />}
                  </button>
                </div>
              ) : (
                <div className="iv-detail__contact-row iv-detail__contact-row--empty"><Mail /> <span>未填写邮箱</span></div>
              )}
            </div>
            <div className="iv-detail__candidate-actions">
              <button onClick={() => onToggleFavorite(interview.candidateId)} className={isFavorite ? "active" : ""}>
                <Star fill={isFavorite ? "currentColor" : "none"} /> {isFavorite ? "已关注" : "关注候选人"}
              </button>
              {candidate?.profileText && (
                <button onClick={() => setShowResume(!showResume)}>
                  <FileText /> {showResume ? "收起简历" : "查看简历"}
                </button>
              )}
              <button onClick={() => onTogglePin(interview.id)}>
                <Pin fill={interview.isPinned ? "currentColor" : "none"} /> {interview.isPinned ? "取消置顶" : "置顶"}
              </button>
            </div>
            {showResume && candidate?.profileText && (
              <div className="iv-detail__resume">
                <h4>简历正文</h4>
                {(candidate.skills || []).length > 0 && (
                  <div className="iv-detail__skills">
                    {(candidate.skills || []).map((s) => <span key={s} className="iv-detail__skill">{s}</span>)}
                  </div>
                )}
                <pre>{candidate.profileText}</pre>
              </div>
            )}
            {(!candidate?.profileText) && (
              <p className="iv-detail__empty">暂无简历正文</p>
            )}
          </div>
        </section>

        {/* ── Contact status ── */}
        <section className="iv-detail__section">
          <h3>联系状态</h3>
          <span className="iv-detail__contact-status">
            {CONTACT_STATUS_LABELS[interview.contactStatus as keyof typeof CONTACT_STATUS_LABELS] || interview.contactStatus}
          </span>
        </section>

        {/* ── Focus areas ── */}
        {(interview.focusAreas || []).length > 0 && (
          <section className="iv-detail__section">
            <h3>面试重点</h3>
            <div className="iv-detail__chips">
              {(interview.focusAreas || []).map((f, i) => <span key={i} className="iv-detail__chip">{f}</span>)}
            </div>
          </section>
        )}

        {/* ── Questions ── */}
        {(interview.questions || []).length > 0 && (
          <section className="iv-detail__section">
            <h3>面试问题</h3>
            <ol className="iv-detail__questions">
              {(interview.questions || []).map((q, i) => <li key={i}>{q}</li>)}
            </ol>
          </section>
        )}

        {/* ── Internal notes ── */}
        {interview.internalNotes && (
          <section className="iv-detail__section">
            <h3>内部备注</h3>
            <p className="iv-detail__notes">{interview.internalNotes}</p>
          </section>
        )}

        {/* ── Candidate notes ── */}
        {interview.candidateNotes && (
          <section className="iv-detail__section">
            <h3>候选人备注</h3>
            <p className="iv-detail__notes">{interview.candidateNotes}</p>
          </section>
        )}
      </div>

      {/* ── Actions ── */}
      <div className="iv-detail__footer">
        <select
          value={interview.status}
          onChange={(e) => onStatusChange(interview.id, e.target.value)}
          className="iv-detail__status-select"
        >
          {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <div className="iv-detail__footer-actions">
          {confirmDelete ? (
            <>
              <span className="iv-detail__delete-confirm">确认删除？</span>
              <button className="iv-btn iv-btn--danger" onClick={() => { onDelete(); setConfirmDelete(false); }}>确认</button>
              <button className="iv-btn iv-btn--ghost" onClick={() => setConfirmDelete(false)}>取消</button>
            </>
          ) : (
            <>
              <button className="iv-btn iv-btn--ghost" onClick={() => setConfirmDelete(true)}><Trash2 /> 删除</button>
              <button className="iv-btn iv-btn--primary" onClick={onEdit}><Edit2 /> 编辑</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
