/** Structured validation error for API responses whose shape doesn't match the contract. */
export class ValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ValidationError";
  }
}

/** Safely parse JSON and validate it's an object. */
function safeJson(res: Response): Promise<unknown> {
  return res.json().catch(() => {
    throw new ValidationError("后端返回的不是合法 JSON，请确认 8080 后端已重启并加载最新路由。");
  });
}

function ensureArray(v: unknown, label: string): unknown[] {
  if (Array.isArray(v)) return v;
  throw new ValidationError(`岗位数据接口返回结构不正确 (${label} 不是数组)，请确认 8080 后端已重启并加载最新路由。`);
}

function ensureString(v: unknown, label: string): string {
  if (typeof v === "string") return v;
  throw new ValidationError(`岗位数据接口返回结构不正确 (${label} 不是字符串)，请确认 8080 后端已重启并加载最新路由。`);
}

function ensureNumber(v: unknown, label: string): number {
  if (typeof v === "number" && !Number.isNaN(v)) return v;
  throw new ValidationError(`岗位数据接口返回结构不正确 (${label} 不是数字)，请确认 8080 后端已重启并加载最新路由。`);
}

function ensureBoolean(v: unknown, label: string): boolean {
  if (typeof v === "boolean") return v;
  throw new ValidationError(`岗位数据接口返回结构不正确 (${label} 不是布尔值)，请确认 8080 后端已重启并加载最新路由。`);
}

// ────────────────────────────────────────────────────────────────
// DiscoveriesResponse
// ────────────────────────────────────────────────────────────────

export interface ValidatedDiscoveryItem {
  id: string;
  name: string;
  confidence: number;
  growth_rate: number;
  source_count: number;
  responsibilities: string[];
  required_skills: ValidatedSkillItem[];
  bonus_skills: ValidatedBonusSkillItem[];
  application_scenarios: string[];
  source_ids: string[];
  review_status: string;
  reviewed_at: string | null;
  source_note?: string | null;
  created_at?: string | null;
}

export interface ValidatedSkillItem {
  name: string;
  level: string | null;
  source_ids: string[];
}

export interface ValidatedBonusSkillItem {
  name: string;
  source_ids: string[];
}

function validateSkillItem(raw: unknown): ValidatedSkillItem {
  const o = raw as Record<string, unknown> | null;
  if (!o || typeof o !== "object") throw new ValidationError("SkillItem 结构异常");
  return {
    name: ensureString(o.name, "skill.name"),
    level: o.level != null ? ensureString(o.level, "skill.level") : null,
    source_ids: Array.isArray(o.source_ids) ? o.source_ids.map(String) : [],
  };
}

function validateBonusSkillItem(raw: unknown): ValidatedBonusSkillItem {
  const o = raw as Record<string, unknown> | null;
  if (!o || typeof o !== "object") throw new ValidationError("BonusSkillItem 结构异常");
  return {
    name: ensureString(o.name, "bonus_skill.name"),
    source_ids: Array.isArray(o.source_ids) ? o.source_ids.map(String) : [],
  };
}

function validateDiscoveryItem(raw: unknown): ValidatedDiscoveryItem {
  const o = raw as Record<string, unknown> | null;
  if (!o || typeof o !== "object") throw new ValidationError("DiscoveryItem 结构异常");
  return {
    id: ensureString(o.id, "discovery.id"),
    name: ensureString(o.name, "discovery.name"),
    confidence: ensureNumber(o.confidence, "discovery.confidence"),
    growth_rate: ensureNumber(o.growth_rate, "discovery.growth_rate"),
    source_count: ensureNumber(o.source_count, "discovery.source_count"),
    responsibilities: Array.isArray(o.responsibilities) ? o.responsibilities.map(String) : [],
    required_skills: ensureArray(o.required_skills, "discoveries.items[*].required_skills").map(validateSkillItem),
    bonus_skills: ensureArray(o.bonus_skills, "discoveries.items[*].bonus_skills").map(validateBonusSkillItem),
    application_scenarios: Array.isArray(o.application_scenarios) ? o.application_scenarios.map(String) : [],
    source_ids: Array.isArray(o.source_ids) ? o.source_ids.map(String) : [],
    review_status: ensureString(o.review_status, "discovery.review_status"),
    reviewed_at: o.reviewed_at != null ? ensureString(o.reviewed_at, "discovery.reviewed_at") : null,
    source_note: o.source_note != null ? String(o.source_note) : undefined,
    created_at: o.created_at != null ? String(o.created_at) : undefined,
  };
}

export interface ValidatedDiscoveriesResponse {
  total: number;
  items: ValidatedDiscoveryItem[];
}

export async function validateDiscoveriesResponse(res: Response): Promise<ValidatedDiscoveriesResponse> {
  const raw = await safeJson(res);
  const o = raw as Record<string, unknown> | null;
  if (!o || typeof o !== "object") throw new ValidationError("discoveries 接口返回不是对象");
  if (!Array.isArray(o.items)) throw new ValidationError("discoveries.items 不是数组");
  return {
    total: typeof o.total === "number" ? o.total : (o.items as unknown[]).length,
    items: (o.items as unknown[]).map(validateDiscoveryItem),
  };
}

// ────────────────────────────────────────────────────────────────
// RoleVersionsResponse
// ────────────────────────────────────────────────────────────────

export interface ValidatedRoleVersionItem {
  version_id: string;
  timestamp: string;
  source: string;
  responsibilities: string[];
  skills: ValidatedSkillItem[];
  source_ids: string[];
}

export interface ValidatedRoleVersionsResponse {
  role_id: string;
  name: string;
  current_version: string;
  versions: ValidatedRoleVersionItem[];
}

export async function validateRoleVersionsResponse(res: Response): Promise<ValidatedRoleVersionsResponse> {
  const raw = await safeJson(res);
  const o = raw as Record<string, unknown> | null;
  if (!o || typeof o !== "object") throw new ValidationError("roles/versions 接口返回不是对象");
  const versionsRaw = ensureArray(o.versions, "versions.versions");
  const versions: ValidatedRoleVersionItem[] = versionsRaw.map((v: unknown) => {
    const rv = v as Record<string, unknown> | null;
    if (!rv || typeof rv !== "object") throw new ValidationError("RoleVersionItem 结构异常");
    return {
      version_id: ensureString(rv.version_id, "version.version_id"),
      timestamp: ensureString(rv.timestamp, "version.timestamp"),
      source: typeof rv.source === "string" ? rv.source : "多源采集",
      responsibilities: Array.isArray(rv.responsibilities) ? rv.responsibilities.map(String) : [],
      skills: Array.isArray(rv.skills) ? rv.skills.map(validateSkillItem) : [],
      source_ids: Array.isArray(rv.source_ids) ? rv.source_ids.map(String) : [],
    };
  });
  return {
    role_id: ensureString(o.role_id || "", "versions.role_id"),
    name: ensureString(o.name || "", "versions.name"),
    current_version: ensureString(o.current_version || "", "versions.current_version"),
    versions,
  };
}

// ────────────────────────────────────────────────────────────────
// RoleDiffResponse
// ────────────────────────────────────────────────────────────────

export interface ValidatedDiffSkillItem {
  name: string;
  level: string | null;
  source_ids: string[];
  reason: string | null;
}

export interface ValidatedRoleDiffResponse {
  role_id: string;
  from_version: string;
  to_version: string;
  added: ValidatedDiffSkillItem[];
  removed: ValidatedDiffSkillItem[];
  modified: ValidatedDiffSkillItem[];
}

function validateDiffSkillItem(raw: unknown): ValidatedDiffSkillItem {
  const o = raw as Record<string, unknown> | null;
  if (!o || typeof o !== "object") throw new ValidationError("DiffSkillItem 结构异常");
  return {
    name: ensureString(o.name, "diff_skill.name"),
    level: o.level != null ? ensureString(o.level, "diff_skill.level") : null,
    source_ids: Array.isArray(o.source_ids) ? o.source_ids.map(String) : [],
    reason: o.reason != null ? ensureString(o.reason, "diff_skill.reason") : null,
  };
}

export async function validateRoleDiffResponse(res: Response): Promise<ValidatedRoleDiffResponse> {
  const raw = await safeJson(res);
  const o = raw as Record<string, unknown> | null;
  if (!o || typeof o !== "object") throw new ValidationError("roles/diff 接口返回不是对象");
  return {
    role_id: ensureString(o.role_id || "", "diff.role_id"),
    from_version: ensureString(o.from_version || "", "diff.from_version"),
    to_version: ensureString(o.to_version || "", "diff.to_version"),
    added: ensureArray(o.added, "diff.added").map(validateDiffSkillItem),
    removed: ensureArray(o.removed, "diff.removed").map(validateDiffSkillItem),
    modified: ensureArray(o.modified, "diff.modified").map(validateDiffSkillItem),
  };
}

// ────────────────────────────────────────────────────────────────
// PanoramaResponse
// ────────────────────────────────────────────────────────────────

export interface ValidatedPanoramaNode {
  id: string;
  type: string;
  label: string;
  stack: string | null;
  level: string | null;
  version: string | null;
  source_ids: string[];
  x?: number;
  y?: number;
}

export interface ValidatedPanoramaEdge {
  source: string;
  target: string;
  relation: string;
  source_ids: string[];
}

export interface ValidatedPanoramaResponse {
  meta: { stacks: string[]; levels: string[]; versions: string[] };
  nodes: ValidatedPanoramaNode[];
  edges: ValidatedPanoramaEdge[];
}

export async function validatePanoramaResponse(res: Response): Promise<ValidatedPanoramaResponse> {
  const raw = await safeJson(res);
  const o = raw as Record<string, unknown> | null;
  if (!o || typeof o !== "object") throw new ValidationError("图谱接口返回不是对象，请确认后端已重启并加载最新路由。");

  const metaRaw = (o.meta as Record<string, unknown>) || {};
  const nodesRaw = ensureArray(o.nodes, "panorama.nodes");
  const edgesRaw = ensureArray(o.edges, "panorama.edges");

  const nodes: ValidatedPanoramaNode[] = nodesRaw.map((n: unknown) => {
    const rn = n as Record<string, unknown> | null;
    if (!rn || typeof rn !== "object") throw new ValidationError("PanoramaNode 结构异常");
    return {
      id: ensureString(rn.id, "panorama_node.id"),
      type: ensureString(rn.type, "panorama_node.type"),
      label: ensureString(rn.label, "panorama_node.label"),
      stack: rn.stack != null ? ensureString(rn.stack, "panorama_node.stack") : null,
      level: rn.level != null ? ensureString(rn.level, "panorama_node.level") : null,
      version: rn.version != null ? ensureString(rn.version, "panorama_node.version") : null,
      source_ids: Array.isArray(rn.source_ids) ? rn.source_ids.map(String) : [],
    };
  });

  const validEdges: ValidatedPanoramaEdge[] = [];
  const filteredEdgeCount = { skipped: 0 };
  edgesRaw.forEach((e: unknown, i: number) => {
    const re = e as Record<string, unknown> | null;
    if (!re || typeof re !== "object") { filteredEdgeCount.skipped++; return; }
    try {
      validEdges.push({
        source: ensureString(re.source, `edge[${i}].source`),
        target: ensureString(re.target, `edge[${i}].target`),
        relation: ensureString(re.relation, `edge[${i}].relation`),
        source_ids: Array.isArray(re.source_ids) ? re.source_ids.map(String) : [],
      });
    } catch { filteredEdgeCount.skipped++; }
  });

  return {
    meta: {
      stacks: Array.isArray(metaRaw.stacks) ? metaRaw.stacks.map(String) : [],
      levels: Array.isArray(metaRaw.levels) ? metaRaw.levels.map(String) : [],
      versions: Array.isArray(metaRaw.versions) ? metaRaw.versions.map(String) : [],
    },
    nodes,
    edges: validEdges,
    _filteredEdges: filteredEdgeCount.skipped,
  } as ValidatedPanoramaResponse & { _filteredEdges: number };
}

// ────────────────────────────────────────────────────────────────
// RagHealthResponse
// ────────────────────────────────────────────────────────────────

export interface ValidatedRagHealthResponse {
  status: string;
  sources_loaded: string[];
  competencies_indexed: number;
  roles_indexed: number;
  alias_entries: number;
  milvus_wired: boolean;
  neo4j_wired: boolean;
  audit_path: string;
}

export async function validateRagHealthResponse(res: Response): Promise<ValidatedRagHealthResponse> {
  const raw = await safeJson(res);
  const o = raw as Record<string, unknown> | null;
  if (!o || typeof o !== "object") throw new ValidationError("rag/health 接口返回不是对象");
  return {
    status: ensureString(o.status, "health.status"),
    sources_loaded: Array.isArray(o.sources_loaded) ? o.sources_loaded.map(String) : [],
    competencies_indexed: ensureNumber(o.competencies_indexed, "health.competencies_indexed"),
    roles_indexed: ensureNumber(o.roles_indexed, "health.roles_indexed"),
    alias_entries: ensureNumber(o.alias_entries, "health.alias_entries"),
    milvus_wired: ensureBoolean(o.milvus_wired, "health.milvus_wired"),
    neo4j_wired: ensureBoolean(o.neo4j_wired, "health.neo4j_wired"),
    audit_path: ensureString(o.audit_path, "health.audit_path"),
  };
}

// ────────────────────────────────────────────────────────────────
// RagAuditResponse
// ────────────────────────────────────────────────────────────────

export interface ValidatedAuditEntry {
  audit_id: string;
  timestamp: string;
  mode: string;
  request_summary: Record<string, unknown>;
  sources_used: string[];
  results: Record<string, unknown>;
  review_status: string;
}

export interface ValidatedRagAuditResponse {
  total: number;
  items: ValidatedAuditEntry[];
}

export async function validateRagAuditResponse(res: Response): Promise<ValidatedRagAuditResponse> {
  const raw = await safeJson(res);
  const o = raw as Record<string, unknown> | null;
  if (!o || typeof o !== "object") throw new ValidationError("rag/audit 接口返回不是对象");
  const items = ensureArray(o.items, "audit.items");
  return {
    total: ensureNumber(o.total, "audit.total"),
    items: items.map((entry: unknown) => {
      const e = entry as Record<string, unknown> | null;
      if (!e || typeof e !== "object") throw new ValidationError("AuditEntry 结构异常");
      return {
        audit_id: ensureString(e.audit_id, "audit.audit_id"),
        timestamp: ensureString(e.timestamp, "audit.timestamp"),
        mode: ensureString(e.mode, "audit.mode"),
        request_summary: (e.request_summary as Record<string, unknown>) || {},
        sources_used: Array.isArray(e.sources_used) ? e.sources_used.map(String) : [],
        results: (e.results as Record<string, unknown>) || {},
        review_status: ensureString(e.review_status, "audit.review_status"),
      };
    }),
  };
}

// ────────────────────────────────────────────────────────────────
// RagGenerateResponse
// ────────────────────────────────────────────────────────────────

export interface ValidatedEvidenceClaim {
  text: string;
  source_ids: string[];
  supported: boolean;
  confidence: number;
  needs_review: boolean;
}

export interface ValidatedRagGenerateResponse {
  answer: string;
  claims: ValidatedEvidenceClaim[];
  blocked_claims: ValidatedEvidenceClaim[];
  confidence: number;
  audit_id: string;
  mode: string;
}

function validateClaim(raw: unknown): ValidatedEvidenceClaim {
  const o = raw as Record<string, unknown> | null;
  if (!o || typeof o !== "object") throw new ValidationError("EvidenceClaim 结构异常");
  return {
    text: ensureString(o.text, "claim.text"),
    source_ids: Array.isArray(o.source_ids) ? o.source_ids.map(String) : [],
    supported: typeof o.supported === "boolean" ? o.supported : false,
    confidence: typeof o.confidence === "number" ? o.confidence : 0,
    needs_review: typeof o.needs_review === "boolean" ? o.needs_review : false,
  };
}

export async function validateRagGenerateResponse(res: Response): Promise<ValidatedRagGenerateResponse> {
  const raw = await safeJson(res);
  const o = raw as Record<string, unknown> | null;
  if (!o || typeof o !== "object") throw new ValidationError("rag/generate 接口返回不是对象");
  return {
    answer: ensureString(o.answer, "generate.answer"),
    claims: ensureArray(o.claims, "generate.claims").map(validateClaim),
    blocked_claims: ensureArray(o.blocked_claims, "generate.blocked_claims").map(validateClaim),
    confidence: ensureNumber(o.confidence, "generate.confidence"),
    audit_id: ensureString(o.audit_id, "generate.audit_id"),
    mode: ensureString(o.mode, "generate.mode"),
  };
}
