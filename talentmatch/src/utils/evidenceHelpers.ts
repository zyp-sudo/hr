// ─── Source platform mapping ────────────────────────────────────

const SOURCE_PLATFORM_MAP: Array<{ prefix: string; name: string }> = [
  { prefix: "src-boss", name: "BOSS直聘" },
  { prefix: "src-lagou", name: "拉勾招聘" },
  { prefix: "src-51job", name: "前程无忧" },
  { prefix: "src-zhilian", name: "智联招聘" },
  { prefix: "src-liepin", name: "猎聘" },
  { prefix: "src-seed", name: "项目初始资料" },
  { prefix: "src-mkt", name: "市场招聘数据" },
];

// ─── Role display names ─────────────────────────────────────────

const ROLE_DISPLAY_NAMES: Record<string, string> = {
  "java-developer": "Java开发工程师",
  "frontend-developer": "前端开发工程师",
  "data-scientist": "数据科学家",
};

export const AVAILABLE_ROLES: Array<{ id: string; name: string }> = [
  { id: "java-developer", name: "Java开发工程师" },
  { id: "frontend-developer", name: "前端开发工程师" },
  { id: "data-scientist", name: "数据科学家" },
];

// ─── Review status mapping ──────────────────────────────────────

const REVIEW_STATUS_MAP: Record<string, string> = {
  auto: "已自动核验",
  needs_review: "建议人工确认",
  approved: "已确认",
  pending: "待确认",
};

// ─── Public helpers ─────────────────────────────────────────────

/** Convert raw confidence (0-1) to HR-readable support level. */
export function getSupportLevel(confidence: number): string {
  if (confidence >= 0.8) return "较高";
  if (confidence >= 0.5) return "中等";
  return "较低";
}

/** Map a source ID like "src-boss-001" to a Chinese platform name. */
export function getSourcePlatform(id: string): string {
  if (!id) return "其他招聘渠道";
  for (const { prefix, name } of SOURCE_PLATFORM_MAP) {
    if (id.toLowerCase().startsWith(prefix)) return name;
  }
  return "其他招聘渠道";
}

/** Group and count source IDs by platform name. */
export function groupSourcePlatforms(
  ids: string[],
): Array<{ name: string; count: number }> {
  if (!ids?.length) return [];
  const m = new Map<string, number>();
  for (const id of ids) {
    const n = getSourcePlatform(id);
    m.set(n, (m.get(n) || 0) + 1);
  }
  return Array.from(m.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count);
}

/** Get Chinese display name for a role_id. */
export function getRoleDisplayName(roleId: string): string {
  return ROLE_DISPLAY_NAMES[roleId] || roleId;
}

/** Map internal review_status to Chinese label. */
export function getReviewStatusLabel(status: string): string {
  return REVIEW_STATUS_MAP[status] || status;
}

/** Convert technical error messages to HR-friendly text. */
export function getUserFriendlyError(err: unknown): string {
  if (err instanceof Error) {
    const msg = err.message;
    // Strip technical prefixes
    if (msg.includes("ValidationError")) {
      return "暂时无法完成岗位要求核验，请稍后重试。";
    }
    if (msg.includes("HTTP 500") || msg.includes("HTTP 502") || msg.includes("HTTP 503")) {
      return "服务暂时不可用，请稍后重试。";
    }
    if (msg.includes("HTTP 4")) {
      return "请求参数有误，请检查填写内容后重试。";
    }
    if (msg.includes("Failed to fetch") || msg.includes("NetworkError")) {
      return "网络连接失败，请检查网络后重试。";
    }
    // Return cleaned message — strip stack traces and technical identifiers
    const cleaned = msg
      .replace(/EvidenceGenerateResponse/gi, "")
      .replace(/RagGenerateResponse/gi, "")
      .replace(/ValidationError/gi, "")
      .replace(/at\s+.*$/gm, "")
      .trim();
    return cleaned || "暂时无法完成岗位要求核验，请稍后重试。";
  }
  return "暂时无法完成岗位要求核验，请稍后重试。";
}

/** Format a date for display in Chinese locale. */
export function formatEvidenceTime(date: Date): string {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}
