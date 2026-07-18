import { useState } from "react";
import type { Interview, InterviewTag, InterviewStatus, ContactStatus } from "../../types/interview";
import { INTERVIEW_FORMATS, INTERVIEW_ROUNDS, INTERVIEW_PRIORITIES, CONTACT_STATUS_LABELS, STATUS_LABELS } from "../../types/interview";
import { Plus, X, Save, Loader2 } from "lucide-react";

interface Props {
  interview?: Interview | null;
  candidates: Array<{ id: string; name: string }>;
  jobs: Array<{ id: string; name: string }>;
  tags: InterviewTag[];
  onSave: (data: Partial<Interview>) => Promise<void>;
  onClose: () => void;
  onTagCreate: (name: string, color: string) => Promise<InterviewTag>;
}

interface FormData {
  candidateId: string;
  jobId: string;
  title: string;
  startsAt: string;
  endsAt: string;
  timezone: string;
  format: string;
  customFormat: string;
  location: string;
  meetingUrl: string;
  interviewersText: string;
  round: string;
  customRound: string;
  status: InterviewStatus;
  priority: string;
  customPriority: string;
  tagIds: string[];
  focusAreasText: string;
  questionsText: string;
  internalNotes: string;
  candidateNotes: string;
  contactStatus: ContactStatus;
  reminderMinutes: number;
  isPinned: boolean;
}

function toLocalDatetime(iso: string): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch {
    return "";
  }
}

export default function InterviewEditor({ interview, candidates, jobs, tags, onSave, onClose, onTagCreate }: Props) {
  const isEdit = Boolean(interview);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showNewTag, setShowNewTag] = useState(false);
  const [newTagName, setNewTagName] = useState("");
  const [newTagColor, setNewTagColor] = useState("#6366f1");

  const [form, setForm] = useState<FormData>(() => ({
    candidateId: interview?.candidateId || candidates[0]?.id || "",
    jobId: interview?.jobId || jobs[0]?.id || "",
    title: interview?.title || "",
    startsAt: toLocalDatetime(interview?.startsAt || ""),
    endsAt: toLocalDatetime(interview?.endsAt || ""),
    timezone: interview?.timezone || "Asia/Shanghai",
    format: interview?.format || "视频",
    customFormat: interview?.customFormat || "",
    location: interview?.location || "",
    meetingUrl: interview?.meetingUrl || "",
    interviewersText: (interview?.interviewers || []).join("、"),
    round: interview?.round || "初试",
    customRound: interview?.customRound || "",
    status: (interview?.status as InterviewStatus) || "scheduled",
    priority: interview?.priority || "普通",
    customPriority: interview?.customPriority || "",
    tagIds: interview?.tagIds || [],
    focusAreasText: (interview?.focusAreas || []).join("、"),
    questionsText: (interview?.questions || []).join("\n"),
    internalNotes: interview?.internalNotes || "",
    candidateNotes: interview?.candidateNotes || "",
    contactStatus: (interview?.contactStatus as ContactStatus) || "not_contacted",
    reminderMinutes: interview?.reminderMinutes ?? 30,
    isPinned: interview?.isPinned || false,
  }));

  const set = (patch: Partial<FormData>) => {
    setForm((f) => ({ ...f, ...patch }));
    setErrors({});
  };

  const toggleTag = (tagId: string) => {
    setForm((f) => ({
      ...f,
      tagIds: f.tagIds.includes(tagId) ? f.tagIds.filter((id) => id !== tagId) : [...f.tagIds, tagId],
    }));
  };

  const createTag = async () => {
    const name = newTagName.trim();
    if (!name) return;
    try {
      await onTagCreate(name, newTagColor);
      setNewTagName("");
      setNewTagColor("#6366f1");
      setShowNewTag(false);
    } catch {
      // handled by parent
    }
  };

  const validate = (): boolean => {
    const e: Record<string, string> = {};
    if (!form.candidateId) e.candidateId = "请选择候选人";
    if (!form.startsAt) e.startsAt = "请设置开始时间";
    if (!form.endsAt) e.endsAt = "请设置结束时间";
    if (form.startsAt && form.endsAt && new Date(form.endsAt) <= new Date(form.startsAt)) e.endsAt = "结束时间必须晚于开始时间";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const submit = async () => {
    if (!validate()) return;
    setSaving(true);
    try {
      const data: Partial<Interview> = {
        candidateId: form.candidateId,
        jobId: form.jobId,
        title: form.title,
        startsAt: new Date(form.startsAt).toISOString(),
        endsAt: new Date(form.endsAt).toISOString(),
        timezone: form.timezone,
        format: form.format === "自定义" ? form.customFormat : form.format,
        customFormat: form.customFormat,
        location: form.location,
        meetingUrl: form.meetingUrl,
        interviewers: form.interviewersText.split(/[,，、]/).map((s) => s.trim()).filter(Boolean),
        round: form.round === "自定义" ? form.customRound : form.round,
        customRound: form.customRound,
        status: form.status,
        priority: form.priority === "自定义" ? form.customPriority : form.priority,
        customPriority: form.customPriority,
        tagIds: form.tagIds,
        focusAreas: form.focusAreasText.split(/[,，、]/).map((s) => s.trim()).filter(Boolean),
        questions: form.questionsText.split("\n").map((s) => s.trim()).filter(Boolean),
        internalNotes: form.internalNotes,
        candidateNotes: form.candidateNotes,
        contactStatus: form.contactStatus,
        reminderMinutes: form.reminderMinutes,
        isPinned: form.isPinned,
      };
      await onSave(data);
    } finally {
      setSaving(false);
    }
  };

function LabeledField({ label, children, error }: { label: string; children: React.ReactNode; error?: string }) {
  return (
    <label className="iv-editor__field">
      <span>{label}</span>
      {children}
      {error && <small className="iv-editor__error">{error}</small>}
    </label>
  );
}

  return (
    <div className="iv-editor">
      <div className="iv-editor__head">
        <h2>{isEdit ? "编辑面试" : "新建面试"}</h2>
        <button onClick={onClose} disabled={saving} aria-label="关闭"><X /></button>
      </div>

      <div className="iv-editor__body">
        {/* ── Basic info ── */}
        <LabeledField label="候选人" error={errors.candidateId}>
          <select value={form.candidateId} onChange={(e) => set({ candidateId: e.target.value })}>
            <option value="">请选择候选人</option>
            {candidates.map((c) => <option key={c.id} value={c.id}>{c.name || "匿名候选人"}</option>)}
          </select>
        </LabeledField>

        <LabeledField label="目标岗位">
          <select value={form.jobId} onChange={(e) => set({ jobId: e.target.value })}>
            <option value="">请选择岗位</option>
            {jobs.map((j) => <option key={j.id} value={j.id}>{j.name}</option>)}
          </select>
        </LabeledField>

        <LabeledField label="面试标题">
          <input value={form.title} onChange={(e) => set({ title: e.target.value })} placeholder="自动生成，也可自定义" />
        </LabeledField>

        {/* ── Time ── */}
        <div className="iv-editor__row">
          <LabeledField label="开始时间" error={errors.startsAt}>
            <input type="datetime-local" value={form.startsAt} onChange={(e) => set({ startsAt: e.target.value })} />
          </LabeledField>
          <LabeledField label="结束时间" error={errors.endsAt}>
            <input type="datetime-local" value={form.endsAt} onChange={(e) => set({ endsAt: e.target.value })} />
          </LabeledField>
        </div>

        <div className="iv-editor__row">
          <LabeledField label="时区">
            <select value={form.timezone} onChange={(e) => set({ timezone: e.target.value })}>
              <option value="Asia/Shanghai">Asia/Shanghai (UTC+8)</option>
              <option value="Asia/Tokyo">Asia/Tokyo (UTC+9)</option>
              <option value="America/New_York">America/New_York (UTC-5)</option>
              <option value="America/Los_Angeles">America/Los_Angeles (UTC-8)</option>
              <option value="Europe/London">Europe/London (UTC+0)</option>
            </select>
          </LabeledField>
          <LabeledField label="提醒">
            <select value={String(form.reminderMinutes)} onChange={(e) => set({ reminderMinutes: Number(e.target.value) })}>
              <option value="0">不提醒</option>
              <option value="15">15 分钟前</option>
              <option value="30">30 分钟前</option>
              <option value="60">1 小时前</option>
              <option value="1440">1 天前</option>
            </select>
          </LabeledField>
        </div>

        {/* ── Format ── */}
        <div className="iv-editor__row">
          <LabeledField label="面试形式">
            <div className="iv-editor__combo">
              <select value={form.format} onChange={(e) => set({ format: e.target.value })} style={{ flex: 1 }}>
                {INTERVIEW_FORMATS.map((f) => <option key={f} value={f}>{f}</option>)}
                <option value="自定义">自定义</option>
              </select>
              {form.format === "自定义" && (
                <input value={form.customFormat} onChange={(e) => set({ customFormat: e.target.value })} placeholder="自定义形式" style={{ flex: 2 }} />
              )}
            </div>
          </LabeledField>
          <LabeledField label="面试轮次">
            <div className="iv-editor__combo">
              <select value={form.round} onChange={(e) => set({ round: e.target.value })} style={{ flex: 1 }}>
                {INTERVIEW_ROUNDS.map((r) => <option key={r} value={r}>{r}</option>)}
                <option value="自定义">自定义</option>
              </select>
              {form.round === "自定义" && (
                <input value={form.customRound} onChange={(e) => set({ customRound: e.target.value })} placeholder="自定义轮次" style={{ flex: 2 }} />
              )}
            </div>
          </LabeledField>
        </div>

        {/* ── Location & Meeting ── */}
        <div className="iv-editor__row">
          <LabeledField label="面试地点">
            <input value={form.location} onChange={(e) => set({ location: e.target.value })} placeholder="会议室或地址" />
          </LabeledField>
          <LabeledField label="视频会议链接">
            <input value={form.meetingUrl} onChange={(e) => set({ meetingUrl: e.target.value })} placeholder="会议链接（视频面试时填写）" />
          </LabeledField>
        </div>

        {/* ── Interviewers ── */}
        <LabeledField label="面试官">
          <input value={form.interviewersText} onChange={(e) => set({ interviewersText: e.target.value })} placeholder="多个面试官用逗号或顿号分隔" />
        </LabeledField>

        {/* ── Status & Priority ── */}
        <div className="iv-editor__row">
          <LabeledField label="状态">
            <select value={form.status} onChange={(e) => set({ status: e.target.value as InterviewStatus })}>
              {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </LabeledField>
          <LabeledField label="优先级">
            <div className="iv-editor__combo">
              <select value={form.priority} onChange={(e) => set({ priority: e.target.value })} style={{ flex: 1 }}>
                {INTERVIEW_PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
                <option value="自定义">自定义</option>
              </select>
              {form.priority === "自定义" && (
                <input value={form.customPriority} onChange={(e) => set({ customPriority: e.target.value })} placeholder="自定义优先级" style={{ flex: 2 }} />
              )}
            </div>
          </LabeledField>
        </div>

        {/* ── Tags ── */}
        <div className="iv-editor__field">
          <span>标签</span>
          <div className="iv-editor__tags">
            {tags.map((t) => (
              <button
                key={t.id}
                className={`iv-tag-chip ${form.tagIds.includes(t.id) ? "iv-tag-chip--active" : ""}`}
                style={{ borderColor: form.tagIds.includes(t.id) ? t.color : undefined, background: form.tagIds.includes(t.id) ? `${t.color}22` : undefined }}
                onClick={() => toggleTag(t.id)}
                type="button"
              >
                <span className="iv-tag-chip__dot" style={{ background: t.color }} />
                {t.name}
              </button>
            ))}
            <button className="iv-tag-chip iv-tag-chip--add" onClick={() => setShowNewTag(!showNewTag)} type="button">
              <Plus /> 新增
            </button>
          </div>
          {showNewTag && (
            <div className="iv-editor__new-tag">
              <input value={newTagName} onChange={(e) => setNewTagName(e.target.value)} placeholder="标签名称" onKeyDown={(e) => { if (e.key === "Enter") createTag(); }} />
              <input type="color" value={newTagColor} onChange={(e) => setNewTagColor(e.target.value)} />
              <button onClick={createTag} disabled={!newTagName.trim()} type="button">创建</button>
            </div>
          )}
        </div>

        {/* ── Contact status ── */}
        <LabeledField label="联系状态">
          <select value={form.contactStatus} onChange={(e) => set({ contactStatus: e.target.value as ContactStatus })}>
            {Object.entries(CONTACT_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </LabeledField>

        {/* ── Focus areas ── */}
        <LabeledField label="面试重点">
          <input value={form.focusAreasText} onChange={(e) => set({ focusAreasText: e.target.value })} placeholder="多个重点用逗号或顿号分隔" />
        </LabeledField>

        {/* ── Questions ── */}
        <LabeledField label="面试问题">
          <textarea rows={3} value={form.questionsText} onChange={(e) => set({ questionsText: e.target.value })} placeholder="每行一个问题" />
        </LabeledField>

        {/* ── Notes ── */}
        <LabeledField label="内部备注">
          <textarea rows={2} value={form.internalNotes} onChange={(e) => set({ internalNotes: e.target.value })} placeholder="仅招聘团队可见" />
        </LabeledField>
        <LabeledField label="候选人备注">
          <textarea rows={2} value={form.candidateNotes} onChange={(e) => set({ candidateNotes: e.target.value })} placeholder="对候选人可见的备注" />
        </LabeledField>

        {/* ── Pin ── */}
        <label className="iv-editor__checkbox">
          <input type="checkbox" checked={form.isPinned} onChange={(e) => set({ isPinned: e.target.checked })} />
          <span>置顶此面试</span>
        </label>
      </div>

      <div className="iv-editor__footer">
        <button className="iv-btn iv-btn--ghost" onClick={onClose} disabled={saving}>取消</button>
        <button className="iv-btn iv-btn--primary" onClick={submit} disabled={saving}>
          {saving ? <><Loader2 className="spin-icon" /> 保存中…</> : <><Save /> {isEdit ? "保存修改" : "创建面试"}</>}
        </button>
      </div>
    </div>
  );
}
