export interface JobProfile { id: string; title: string; description: string; requirements: string[] }
export interface AssessmentResult {
  id?: string; createdAt?: string; candidateName?: string; jobId?: string; jobTitle?: string;
  score: number; matchLevel: string;
  radar: { technical: number; experience: number; collaboration: number; education: number; softSkills: number };
  experienceMatch: { relevance: number; alignment: number };
  skillGaps: string[]; highlights: string[];
}

/** UI-facing assessment shape used by the draggable candidate cards. */
export interface AssessmentViewModel {
  score: number;
  level: string;
  industry: number;
  title: number;
  gaps: string[];
  strengths: string[];
  radar: number[];
}

/* ── Competition types (aligned with backend snake_case schemas) ── */

export interface SkillItem {
  name: string;
  level?: "beginner" | "intermediate" | "advanced" | "expert" | null;
  source_ids: string[];
}

export interface BonusSkillItem {
  name: string;
  source_ids: string[];
}

export interface DiscoveryItem {
  id: string;
  name: string;
  confidence: number;        // 0~1 from backend; display ×100
  growth_rate: number;        // 0~1 from backend; display ×100
  source_count: number;
  responsibilities: string[];
  required_skills: SkillItem[];
  bonus_skills: BonusSkillItem[];
  application_scenarios: string[];
  source_ids: string[];
  review_status: "pending" | "approved" | "rejected";
  reviewed_at: string | null;
}

export interface ReviewEditPayload {
  name?: string | null;
  responsibilities?: string[] | null;
  required_skills?: SkillItem[] | null;
  bonus_skills?: BonusSkillItem[] | null;
}

export interface ReviewRequest {
  status: "approved" | "rejected" | "pending";
  editor: string;
  edits?: ReviewEditPayload | null;
  comment?: string | null;
}

export interface ReviewRecord {
  review_id: string;
  discovery_id: string;
  status: string;
  editor: string;
  edits?: Record<string, unknown> | null;
  comment?: string | null;
  created_at: string;
}

export interface RoleVersionItem {
  version_id: string;
  timestamp: string;
  source: string;
  responsibilities: string[];
  skills: SkillItem[];
  source_ids: string[];
}

export interface RoleVersionsResponse {
  role_id: string;
  name: string;
  current_version: string;
  versions: RoleVersionItem[];
}

export interface DiffSkillItem {
  name: string;
  level?: string | null;
  source_ids: string[];
  reason?: string | null;
}

export interface RoleDiffResponse {
  role_id: string;
  from_version: string;
  to_version: string;
  added: DiffSkillItem[];
  removed: DiffSkillItem[];
  modified: DiffSkillItem[];
}

export interface PanoramaMeta {
  stacks?: string[];
  levels?: string[];
  versions?: string[];
  [key: string]: unknown;
}

export interface PanoramaNode {
  id: string;
  type: "role" | "skill" | "capability";
  label: string;
  stack?: string | null;
  level?: string | null;
  version?: string | null;
  source_ids: string[];
  // layout helpers (client-side only)
  x?: number;
  y?: number;
}

export interface PanoramaEdge {
  source: string;
  target: string;
  relation: "requires" | "demonstrates" | "related_to";
  source_ids: string[];
}

export interface PanoramaResponse {
  meta: PanoramaMeta;
  nodes: PanoramaNode[];
  edges: PanoramaEdge[];
}

/* ── Company Agent types (aligned with backend schemas) ── */

export interface CompanyAgentHealth {
  enabled: boolean;
  configured: boolean;
  status: string;
  provider: string;
  endpoint_configured: boolean;
}

export interface CompanyAgentDimension {
  name: string;
  score: number;
}

export interface CompanyAgentEvidence {
  type: string;
  description: string;
}

export interface CompanyAgentResult {
  status: "success" | "disabled" | "failed";
  request_id: string;
  trace_id?: string | null;
  agent_score?: number | null;
  recommendation?: string | null;
  summary?: string | null;
  strengths: string[];
  risks: string[];
  skill_gaps: string[];
  dimensions: CompanyAgentDimension[];
  evidence: CompanyAgentEvidence[];
  provider: string;
  model?: string | null;
  latency_ms: number;
  evaluated_at: string;
}
