/**
 * Interview Management — shared types
 * All fields are designed for full CRUD persistence via hr_state.json.
 */

// ── Tag ────────────────────────────────────────────────────────────────────
export interface InterviewTag {
  id: string;
  name: string;
  color: string;
  createdAt: string;
}

// ── Interview record ────────────────────────────────────────────────────────
export interface Interview {
  id: string;
  candidateId: string;
  candidateName: string;
  jobId: string;
  jobTitle: string;
  title: string;
  startsAt: string;       // ISO-8601 with offset, e.g. 2026-07-20T14:00:00+08:00
  endsAt: string;
  timezone: string;
  format: string;         // "现场" | "电话" | "视频" | custom value
  customFormat: string;
  location: string;
  meetingUrl: string;
  interviewers: string[];
  round: string;         // "初试" | "技术一面" | "技术二面" | "HR面" | "终面" | custom
  customRound: string;
  status: InterviewStatus;
  priority: string;       // "普通" | "重要" | "紧急" | custom
  customPriority: string;
  tagIds: string[];
  focusAreas: string[];
  questions: string[];
  internalNotes: string;
  candidateNotes: string;
  contactStatus: ContactStatus;
  reminderMinutes: number;
  isPinned: boolean;
  createdAt: string;
  updatedAt: string;

  // legacy compat — normalised on read
  scheduledAt?: string;
  interviewer?: string;
  tags?: string[];
  notes?: string;
}

export type InterviewStatus =
  | "pending"      // 待安排
  | "scheduled"    // 已安排
  | "in_progress"  // 进行中
  | "completed"    // 已完成
  | "cancelled";    // 已取消

export type ContactStatus =
  | "not_contacted"
  | "contacted"
  | "no_response"
  | "confirmed";

// ── Candidate (subset used by interview module) ─────────────────────────────
export interface InterviewCandidate {
  id: string;
  name: string;
  email: string;
  phone: string;
  stage: string;
  skills: string[];
  experienceYears: number;
  education: string;
  profileText: string;
  createdAt: string;
  projectScore?: number;
  collaborationScore?: number;
}

// ── Filters ─────────────────────────────────────────────────────────────────
export interface InterviewFilters {
  search: string;          // candidate name, job title, interviewer
  status: InterviewStatus | "";
  round: string;
  priority: string;
  tagId: string;
  dateFrom: string;
  dateTo: string;
  isPinned: boolean;
  onlyFavorites: boolean;
  view: InterviewViewMode;
}

export type InterviewViewMode = "calendar" | "list" | "kanban";
export type CalendarSubView = "month" | "week" | "day";

// ── Notifications ───────────────────────────────────────────────────────────
export interface AppNotification {
  id: string;
  type: "interview" | "resume";
  title: string;
  detail: string;
  time: string;
  readAt: string | null;
  target: {
    page: "interviews" | "jobs" | "favorites";
    interviewId?: string;
    candidateId?: string;
  };
}

// ── Stats ───────────────────────────────────────────────────────────────────
export interface InterviewStats {
  today: number;
  thisWeek: number;
  pending: number;
  scheduled: number;
  completed: number;
  cancelled: number;
  pinned: number;
  upcoming: number;
}

// ── Kanban columns ──────────────────────────────────────────────────────────
export interface KanbanColumn {
  status: InterviewStatus;
  label: string;
  icon: string;
  color: string;
}

export const KANBAN_COLUMNS: KanbanColumn[] = [
  { status: "pending", label: "待安排", icon: "circle", color: "#facc15" },
  { status: "scheduled", label: "已安排", icon: "calendar", color: "#60a5fa" },
  { status: "in_progress", label: "进行中", icon: "activity", color: "#4ade80" },
  { status: "completed", label: "已完成", icon: "check-circle", color: "#9bf2e9" },
  { status: "cancelled", label: "已取消", icon: "x-circle", color: "#f87171" },
];

// ── Preset options (user can override) ──────────────────────────────────────
export const INTERVIEW_FORMATS = ["现场", "电话", "视频"];
export const INTERVIEW_ROUNDS = ["初试", "技术一面", "技术二面", "HR面", "终面"];
export const INTERVIEW_PRIORITIES = ["普通", "重要", "紧急"];
export const CONTACT_STATUS_LABELS: Record<ContactStatus, string> = {
  not_contacted: "未联系",
  contacted: "已联系",
  no_response: "未响应",
  confirmed: "已确认",
};
export const STATUS_LABELS: Record<InterviewStatus, string> = {
  pending: "待安排",
  scheduled: "已安排",
  in_progress: "进行中",
  completed: "已完成",
  cancelled: "已取消",
};

// ── Status to Chinese mapping (for legacy compat) ───────────────────────────
export const STATUS_CN_TO_EN: Record<string, InterviewStatus> = {
  "待进行": "scheduled",
  "待安排": "pending",
  "已安排": "scheduled",
  "进行中": "in_progress",
  "已完成": "completed",
  "已取消": "cancelled",
};
