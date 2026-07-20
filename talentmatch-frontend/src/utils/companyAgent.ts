import type { CompanyAgentHealth, CompanyAgentResult } from "../types";

const BASE = "/api/platform/storage/api/company-agent";

/* ── Runtime validation helpers ───────────────────────────────────────── */

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isString(v: unknown): v is string {
  return typeof v === "string";
}

function isStringArray(v: unknown): v is string[] {
  return Array.isArray(v) && v.every((x) => typeof x === "string");
}

function isBoolean(v: unknown): v is boolean {
  return typeof v === "boolean";
}

function isNumberOrNull(v: unknown): v is number | null {
  return v === null || (typeof v === "number" && Number.isFinite(v));
}

function isAgentScore(v: unknown): v is number | null {
  if (v === null) return true;
  return typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= 100;
}

/* ── Structured health result ─────────────────────────────────────────── */

export type HealthCheckResult =
  | { state: "ok"; health: CompanyAgentHealth }
  | { state: "unavailable"; reason: string };

/**
 * Check whether the company agent is reachable.
 *
 * Returns a discriminated union:
 * - ``{state: "ok", health}`` — healthy, with validated shape
 * - ``{state: "unavailable", reason}`` — network error, HTML response,
 *   non-JSON, HTTP error, or invalid shape
 *
 * Never throws.
 */
export async function fetchAgentHealth(): Promise<HealthCheckResult> {
  let resp: Response;
  try {
    resp = await fetch(`${BASE}/health`);
  } catch (err) {
    return {
      state: "unavailable",
      reason: err instanceof Error ? err.message : "网络请求失败",
    };
  }

  /* ── Guard: HTML response (e.g. Express fallback index.html) ── */
  const contentType = (resp.headers.get("content-type") || "").toLowerCase();
  if (contentType.includes("text/html")) {
    return {
      state: "unavailable",
      reason: "服务器返回 HTML，请检查代理路径是否正确",
    };
  }

  if (!resp.ok) {
    return {
      state: "unavailable",
      reason: `HTTP ${resp.status} ${resp.statusText}`.trim(),
    };
  }

  let data: unknown;
  try {
    data = await resp.json();
  } catch {
    return {
      state: "unavailable",
      reason: "health 响应不是合法 JSON",
    };
  }

  if (!isRecord(data)) {
    return {
      state: "unavailable",
      reason: "health 响应不是 JSON 对象",
    };
  }

  if (!isBoolean(data.enabled) || !isBoolean(data.configured)) {
    return {
      state: "unavailable",
      reason: "health 响应缺少 enabled/configured 布尔字段",
    };
  }

  return {
    state: "ok",
    health: {
      enabled: data.enabled,
      configured: data.configured,
      status: isString(data.status) ? data.status : "unknown",
      provider: isString(data.provider) ? data.provider : "unknown",
      endpoint_configured: isBoolean(data.endpoint_configured)
        ? data.endpoint_configured
        : false,
    },
  };
}

/* ── Evaluate result union ────────────────────────────────────────────── */

export type EvaluateResult =
  | { status: "success"; data: CompanyAgentResult }
  | { status: "disabled" }
  | { status: "failed"; summary: string };

const EMPTY_FAILED: CompanyAgentResult = {
  status: "failed",
  request_id: "",
  provider: "http",
  strengths: [],
  risks: [],
  skill_gaps: [],
  dimensions: [],
  evidence: [],
  latency_ms: 0,
  evaluated_at: new Date().toISOString(),
  summary: "",
};

/**
 * Request an agent-enhanced score.
 *
 * Returns a discriminated union — never throws, never returns
 * the raw ``data as CompanyAgentResult`` cast without validation.
 */
export async function evaluateWithAgent(payload: {
  candidateName: string;
  resumeText: string;
  jobId: string;
  jobTitle: string;
  jobDescription?: string;
  requiredSkills?: string[];
  localScore: number;
  localDimensions?: Record<string, number>;
}): Promise<EvaluateResult> {
  const requestId = crypto.randomUUID();

  let resp: Response;
  try {
    resp = await fetch(`${BASE}/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        candidate_name: payload.candidateName,
        resume_text: payload.resumeText,
        job_id: payload.jobId,
        job_title: payload.jobTitle,
        job_description: payload.jobDescription || "",
        required_skills: payload.requiredSkills || [],
        local_score: payload.localScore,
        local_dimensions: payload.localDimensions || {},
        request_id: requestId,
      }),
    });
  } catch (err) {
    return {
      status: "failed",
      summary: err instanceof Error ? err.message : "网络请求失败",
    };
  }

  /* ── Guard: HTML response ── */
  const contentType = (resp.headers.get("content-type") || "").toLowerCase();
  if (contentType.includes("text/html")) {
    return {
      status: "failed",
      summary: `服务器返回 HTML (HTTP ${resp.status})，请检查代理路径`,
    };
  }

  let data: unknown;
  try {
    data = await resp.json();
  } catch {
    return {
      status: "failed",
      summary: `服务器返回非 JSON 响应 (HTTP ${resp.status})`,
    };
  }

  if (!isRecord(data)) {
    return {
      status: "failed",
      summary: "响应不是 JSON 对象",
    };
  }

  /* ── Validate status field ── */
  const status = data.status;
  if (
    status !== "success" &&
    status !== "disabled" &&
    status !== "failed"
  ) {
    return {
      status: "failed",
      summary: `非法 status 值: ${String(status)}`,
    };
  }

  if (status === "disabled") {
    return { status: "disabled" };
  }

  if (status === "failed") {
    return {
      status: "failed",
      summary: isString(data.summary)
        ? data.summary
        : (isString(data.detail) ? data.detail : `评估失败`),
    };
  }

  /* ── status === "success": validate all fields ── */
  if (!isAgentScore(data.agent_score)) {
    return {
      status: "failed",
      summary: `agent_score 必须为 null 或 0–100 数字，收到: ${String(data.agent_score)}`,
    };
  }

  const strengths = isStringArray(data.strengths) ? data.strengths : [];
  const risks = isStringArray(data.risks) ? data.risks : [];
  const skill_gaps = isStringArray(data.skill_gaps)
    ? data.skill_gaps
    : [];

  /* ── Validate dimensions ── */
  let dimensions: CompanyAgentResult["dimensions"] = [];
  if (Array.isArray(data.dimensions)) {
    dimensions = data.dimensions
      .filter(
        (d: unknown): d is { name: string; score: number } =>
          isRecord(d) &&
          isString(d.name) &&
          typeof d.score === "number" &&
          Number.isFinite(d.score) &&
          d.score >= 0 &&
          d.score <= 100,
      )
      .map((d) => ({ name: d.name, score: d.score }));
  }

  /* ── Validate evidence ── */
  let evidence: CompanyAgentResult["evidence"] = [];
  if (Array.isArray(data.evidence)) {
    evidence = data.evidence
      .filter(
        (e: unknown): e is { type: string; description: string } =>
          isRecord(e) && isString(e.type) && isString(e.description),
      )
      .map((e) => ({ type: e.type, description: e.description }));
  }

  return {
    status: "success",
    data: {
      status: "success",
      request_id: isString(data.request_id) ? data.request_id : requestId,
      trace_id: isString(data.trace_id) ? data.trace_id : null,
      agent_score: data.agent_score as number | null,
      recommendation: isString(data.recommendation)
        ? data.recommendation
        : null,
      summary: isString(data.summary) ? data.summary : null,
      strengths,
      risks,
      skill_gaps,
      dimensions,
      evidence,
      provider: isString(data.provider) ? data.provider : "http",
      model: isString(data.model) ? data.model : null,
      latency_ms:
        typeof data.latency_ms === "number" && Number.isFinite(data.latency_ms)
          ? data.latency_ms
          : 0,
      evaluated_at: isString(data.evaluated_at)
        ? data.evaluated_at
        : new Date().toISOString(),
    },
  };
}
