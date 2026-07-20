import { useState, useEffect, useCallback, useMemo } from "react";
import {
  AlertTriangle, CheckCircle2, ChevronDown, ChevronUp,
  Clock, Plus, Search, Trash2, FileSearch, RefreshCw, XCircle,
} from "lucide-react";
import {
  validateRagAuditResponse, validateRagGenerateResponse,
  type ValidatedRagAuditResponse,
  type ValidatedRagGenerateResponse,
  type ValidatedEvidenceClaim,
} from "../utils/competitionValidators";
import RolePicker from "./RolePicker";
import {
  AVAILABLE_ROLES,
  getSupportLevel,
  groupSourcePlatforms,
  getRoleDisplayName,
  getReviewStatusLabel,
  getUserFriendlyError,
  formatEvidenceTime,
} from "../utils/evidenceHelpers";

const API_BASE = "/api/platform/storage/api/competition/rag";

// ─── Constants ───────────────────────────────────────────────────

const MAX_CLAIMS = 50;
const MAX_CLAIM_LENGTH = 2000;

// ─── ClaimInputs ─────────────────────────────────────────────────

function ClaimInputs({
  claims,
  onChange,
  disabled,
}: {
  claims: string[];
  onChange: (claims: string[]) => void;
  disabled: boolean;
}) {
  const add = useCallback(() => {
    if (claims.length >= MAX_CLAIMS) return;
    onChange([...claims, ""]);
  }, [claims, onChange]);

  const remove = useCallback(
    (idx: number) => {
      const next = claims.filter((_, i) => i !== idx);
      onChange(next.length === 0 ? [""] : next);
    },
    [claims, onChange],
  );

  const update = useCallback(
    (idx: number, value: string) => {
      const next = [...claims];
      next[idx] = value.slice(0, MAX_CLAIM_LENGTH);
      onChange(next);
    },
    [claims, onChange],
  );

  const onKeyDown = useCallback(
    (idx: number, e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        if (claims.length < MAX_CLAIMS) {
          const next = [...claims];
          next.splice(idx + 1, 0, "");
          onChange(next);
        }
      }
    },
    [claims, onChange],
  );

  return (
    <div className="comp-evidence__claims-input">
      <label className="comp-evidence__label">需要核验的岗位要求</label>
      <div className="comp-evidence__claims-list-input">
        {claims.map((c, i) => (
          <div key={i} className="comp-evidence__claim-input-row">
            <input
              type="text"
              value={c}
              onChange={(e) => update(i, e.target.value)}
              onKeyDown={(e) => onKeyDown(i, e)}
              placeholder="请输入需要核验的岗位要求"
              disabled={disabled}
              maxLength={MAX_CLAIM_LENGTH}
              aria-label={`岗位要求 ${i + 1}`}
            />
            <button
              type="button"
              className="comp-evidence__claim-remove"
              onClick={() => remove(i)}
              disabled={disabled || claims.length <= 1}
              aria-label={`删除第 ${i + 1} 条要求`}
            >
              <Trash2 style={{ width: 14 }} />
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        className="comp-evidence__claim-add"
        onClick={add}
        disabled={disabled || claims.length >= MAX_CLAIMS}
      >
        <Plus style={{ width: 14 }} />
        添加一条要求
      </button>
      {claims.length >= MAX_CLAIMS && (
        <p className="comp-evidence__hint">已达到最大条数限制（{MAX_CLAIMS}条）</p>
      )}
    </div>
  );
}

// ─── SourcePlatforms ──────────────────────────────────────────────

function SourcePlatforms({ ids }: { ids: string[] }) {
  const groups = useMemo(() => groupSourcePlatforms(ids), [ids]);
  if (groups.length === 0)
    return <span className="comp-evidence__no-source">暂未找到可展示的来源</span>;
  return (
    <span className="comp-evidence__sources">
      参考来源：
      {groups.map((g, i) => (
        <span key={g.name}>
          {i > 0 && "、"}
          {g.name}
          {g.count > 1 ? `（${g.count}条）` : ""}
        </span>
      ))}
    </span>
  );
}

// ─── SupportedClaimCard ──────────────────────────────────────────

function SupportedClaimCard({ claim }: { claim: ValidatedEvidenceClaim }) {
  const level = getSupportLevel(claim.confidence);
  const levelClass =
    level === "较高"
      ? "comp-evidence__support--high"
      : level === "中等"
        ? "comp-evidence__support--mid"
        : "comp-evidence__support--low";

  return (
    <div className="comp-evidence__claim-card comp-evidence__claim-card--supported">
      <div className="comp-evidence__claim-card-head">
        <CheckCircle2 style={{ width: 16, color: "#059669" }} />
        <span className="comp-evidence__claim-text">{claim.text}</span>
      </div>
      <div className="comp-evidence__claim-card-meta">
        <span className={`comp-evidence__support-level ${levelClass}`}>
          数据支持程度：{level}
          <span className="comp-evidence__support-pct">
            （{Math.round(claim.confidence * 100)}%）
          </span>
        </span>
        <SourcePlatforms ids={claim.source_ids} />
      </div>
      <p className="comp-evidence__claim-note">
        在现有招聘数据中找到了相关要求。
      </p>
    </div>
  );
}

// ─── UnsupportedClaimCard ────────────────────────────────────────

function UnsupportedClaimCard({ claim }: { claim: ValidatedEvidenceClaim }) {
  const needsReview = claim.needs_review;
  return (
    <div
      className={`comp-evidence__claim-card ${needsReview ? "comp-evidence__claim-card--needs-review" : "comp-evidence__claim-card--unsupported"}`}
    >
      <div className="comp-evidence__claim-card-head">
        {needsReview ? (
          <AlertTriangle style={{ width: 16, color: "#d97706" }} />
        ) : (
          <XCircle style={{ width: 16, color: "#6b7280" }} />
        )}
        <span className="comp-evidence__claim-text">{claim.text}</span>
      </div>
      <p className="comp-evidence__claim-note">
        {needsReview
          ? "现有数据支持有限，建议招聘负责人进一步确认。"
          : "暂未找到足够的招聘数据支持，建议结合实际业务需要人工确认。"}
      </p>
    </div>
  );
}

// ─── VerificationResult ──────────────────────────────────────────

function VerificationResult({
  result,
}: {
  result: ValidatedRagGenerateResponse;
}) {
  const supportedClaims = result.claims.filter((c) => c.supported);
  const unsupportedClaims = [
    ...result.claims.filter((c) => !c.supported),
    ...result.blocked_claims,
  ];
  const needsReviewCount = unsupportedClaims.filter((c) => c.needs_review).length;
  const totalClaims =
    result.claims.length + result.blocked_claims.length;

  return (
    <div className="comp-evidence__result">
      {/* Header */}
      <div className="comp-evidence__result-header">
        <h3 className="comp-evidence__result-title">核验结果</h3>
        <p className="comp-evidence__result-summary">
          本次核验 {totalClaims} 项要求
        </p>
      </div>

      {/* Stats */}
      <div className="comp-evidence__result-stats">
        <div className="comp-evidence__stat comp-evidence__stat--supported">
          <span className="comp-evidence__stat-count">{supportedClaims.length}</span>
          <span className="comp-evidence__stat-label">有数据支持</span>
        </div>
        <div className="comp-evidence__stat comp-evidence__stat--unsupported">
          <span className="comp-evidence__stat-count">
            {unsupportedClaims.length - needsReviewCount}
          </span>
          <span className="comp-evidence__stat-label">依据不足</span>
        </div>
        {needsReviewCount > 0 && (
          <div className="comp-evidence__stat comp-evidence__stat--needs-review">
            <span className="comp-evidence__stat-count">{needsReviewCount}</span>
            <span className="comp-evidence__stat-label">建议人工确认</span>
          </div>
        )}
      </div>

      {/* Supported claims */}
      {supportedClaims.length > 0 && (
        <div className="comp-evidence__result-section">
          <h4 className="comp-evidence__result-section-title comp-evidence__result-section-title--supported">
            <CheckCircle2 style={{ width: 16 }} />
            有数据支持的要求
          </h4>
          <div className="comp-evidence__claims-grid">
            {supportedClaims.map((c, i) => (
              <SupportedClaimCard key={i} claim={c} />
            ))}
          </div>
        </div>
      )}

      {/* Unsupported claims */}
      {unsupportedClaims.length > 0 && (
        <div className="comp-evidence__result-section">
          <h4 className="comp-evidence__result-section-title comp-evidence__result-section-title--unsupported">
            <AlertTriangle style={{ width: 16 }} />
            依据不足的要求
          </h4>
          <div className="comp-evidence__claims-grid">
            {unsupportedClaims.map((c, i) => (
              <UnsupportedClaimCard key={i} claim={c} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── VerificationHistory ─────────────────────────────────────────

function VerificationHistory({
  data,
  loading,
  error,
  onRetry,
  selectedRoleId,
}: {
  data: ValidatedRagAuditResponse | null;
  loading: boolean;
  error: string;
  onRetry: () => void;
  selectedRoleId: string;
}) {
  const [open, setOpen] = useState(false);

  // Extract role_id from request_summary if available
  const getEntryRoleName = (
    entry: ValidatedRagAuditResponse["items"][number],
  ): string => {
    const summary = entry.request_summary as Record<string, unknown> | undefined;
    if (summary?.role_id && typeof summary.role_id === "string") {
      return getRoleDisplayName(summary.role_id);
    }
    return getRoleDisplayName(selectedRoleId);
  };

  const getEntryClaimCount = (
    entry: ValidatedRagAuditResponse["items"][number],
  ): number => {
    const summary = entry.request_summary as Record<string, unknown> | undefined;
    if (summary?.candidate_claims && Array.isArray(summary.candidate_claims)) {
      return summary.candidate_claims.length;
    }
    return 0;
  };

  const getEntryStats = (
    entry: ValidatedRagAuditResponse["items"][number],
  ): { supported: number; unsupported: number; needsReview: boolean } => {
    const results = entry.results as Record<string, unknown> | undefined;
    const claims = (results?.claims as Array<Record<string, unknown>>) || [];
    const blocked = (results?.blocked_claims as Array<Record<string, unknown>>) || [];
    const all = [...claims, ...blocked];
    const supported = all.filter((c) => c.supported).length;
    const unsupported = all.length - supported;
    const needsReview = all.some((c) => c.needs_review);
    return { supported, unsupported, needsReview };
  };

  return (
    <div className="comp-evidence__section">
      <button
        className="comp-review-toggle"
        onClick={() => {
          setOpen(!open);
          if (!open && !data && !loading) onRetry();
        }}
        aria-label={open ? "收起历史核验记录" : "展开历史核验记录"}
      >
        <Clock style={{ width: 16 }} />
        <span>历史核验记录</span>
        <span style={{ color: "#777180", fontSize: 11 }}>
          {open ? `${data?.total || 0} 条` : "点击展开"}
        </span>
        {open ? (
          <ChevronUp style={{ width: 14 }} />
        ) : (
          <ChevronDown style={{ width: 14 }} />
        )}
      </button>

      {open && (
        <div className="comp-evidence__audit">
          {error && (
            <div className="comp-error-banner">
              <AlertTriangle />
              <div>
                <b>加载失败</b>
                <span>{error}</span>
              </div>
              <button
                className="ghost-action"
                onClick={onRetry}
                aria-label="重试"
              >
                重试
              </button>
            </div>
          )}

          {loading ? (
            <p className="comp-evidence__loading-text">
              加载历史记录中…
            </p>
          ) : !data || data.items.length === 0 ? (
            <div
              className="comp-empty"
              style={{ minHeight: 120, border: "none" }}
            >
              <Search style={{ width: 32, height: 32 }} />
              <h3>暂无历史核验记录</h3>
              <p>
                完成第一次岗位要求核验后，记录会显示在这里。
              </p>
            </div>
          ) : (
            <div className="comp-evidence__audit-list">
              {data.items.map((entry) => {
                const { supported, unsupported, needsReview } =
                  getEntryStats(entry);
                return (
                  <div key={entry.audit_id} className="comp-evidence__audit-item">
                    <div className="comp-evidence__audit-head">
                      <span className="comp-evidence__audit-role">
                        {getEntryRoleName(entry)}
                      </span>
                      <span
                        className={`comp-status ${needsReview ? "comp-status--pending" : "comp-status--approved"}`}
                      >
                        {getReviewStatusLabel(entry.review_status)}
                      </span>
                      <time>{formatEvidenceTime(new Date(entry.timestamp))}</time>
                    </div>
                    <div className="comp-evidence__audit-detail">
                      <span>核验要求：{getEntryClaimCount(entry)} 条</span>
                      <span>有数据支持：{supported} 条</span>
                      <span>依据不足：{unsupported} 条</span>
                      {needsReview && <span>需要人工确认</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────

type Props = {
  embedded?: boolean;
  roleId?: string;
  onRoleChange?: (id: string) => void;
};

export default function CompetitionEvidence({
  embedded = false,
  roleId: externalRoleId,
  onRoleChange: externalOnRoleChange,
}: Props = {}) {
  // ── Form state ──
  const [internalRoleId, setInternalRoleId] = useState("java-developer");
  const roleId = externalRoleId ?? internalRoleId;
  const setRoleId = externalOnRoleChange ?? setInternalRoleId;
  const [question, setQuestion] = useState("");
  const [claims, setClaims] = useState<string[]>([""]);

  // ── Generate state ──
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState("");
  const [genResult, setGenResult] =
    useState<ValidatedRagGenerateResponse | null>(null);

  // ── Audit state ──
  const [auditData, setAuditData] =
    useState<ValidatedRagAuditResponse | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState("");

  // ── Load audit ──
  const loadAudit = useCallback(async () => {
    setAuditLoading(true);
    setAuditError("");
    try {
      const res = await fetch(`${API_BASE}/audit?limit=50`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `服务返回 HTTP ${res.status}`);
      }
      const validated = await validateRagAuditResponse(res);
      setAuditData(validated);
    } catch (e: unknown) {
      setAuditError(getUserFriendlyError(e));
      setAuditData(null);
    } finally {
      setAuditLoading(false);
    }
  }, []);

  // ── Generate ──
  const handleGenerate = async () => {
    const validClaims = claims.map((s) => s.trim()).filter(Boolean);
    if (!roleId.trim() || !question.trim() || validClaims.length === 0) {
      setGenError("请选择岗位，并至少填写一条需要核验的要求。");
      return;
    }
    if (validClaims.length > MAX_CLAIMS) {
      setGenError(`岗位要求不能超过 ${MAX_CLAIMS} 条。`);
      return;
    }
    setGenError("");
    setGenerating(true);
    setGenResult(null);
    try {
      const res = await fetch(`${API_BASE}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role_id: roleId,
          question,
          candidate_claims: validClaims,
        }),
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || `服务返回 HTTP ${res.status}`);
      }
      const validated = await validateRagGenerateResponse(res);
      setGenResult(validated);
      // Refresh audit after successful generation
      loadAudit();
    } catch (e: unknown) {
      setGenError(getUserFriendlyError(e));
    } finally {
      setGenerating(false);
    }
  };

  // Determine if form is valid for submission
  const canSubmit =
    roleId.trim() !== "" &&
    question.trim() !== "" &&
    claims.some((c) => c.trim() !== "") &&
    !generating;

  return (
    <div className="comp-evidence">
      {/* ── Page header — only when NOT embedded ── */}
      {!embedded && (
        <div className="comp-evidence__header">
          <h1 className="comp-evidence__title">岗位要求核验</h1>
          <p className="comp-evidence__subtitle">
            检查职位要求是否有招聘数据支持，减少不合理或缺少依据的招聘要求。
          </p>
        </div>
      )}

      {/* ── Form card ── */}
      <div className="comp-evidence__form-card">
        {/* Role picker */}
        <RolePicker
          roles={AVAILABLE_ROLES}
          selectedId={roleId}
          onSelect={setRoleId}
        />

        {/* Question */}
        <label className="comp-evidence__label" htmlFor="evidence-question">
          想确认什么？
        </label>
        <input
          id="evidence-question"
          type="text"
          className="comp-evidence__input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="例如：该岗位需要哪些核心技术能力？"
          disabled={generating}
          aria-label="想确认什么"
        />
        <p className="comp-evidence__field-hint">
          系统将围绕这个问题核验下方的岗位要求。
        </p>

        {/* Claims input */}
        <ClaimInputs claims={claims} onChange={setClaims} disabled={generating} />

        {/* Error */}
        {genError && (
          <div className="comp-evidence__error">
            <AlertTriangle style={{ width: 16, flex: "none" }} />
            <div>
              <b>核验失败</b>
              <span>{genError}</span>
            </div>
          </div>
        )}

        {/* Submit button */}
        <button
          className="comp-evidence__submit"
          onClick={handleGenerate}
          disabled={!canSubmit}
          aria-label={generating ? "正在核验" : "开始核验"}
        >
          <FileSearch style={{ width: 16 }} />
          {generating ? "正在核验…" : "开始核验"}
        </button>
      </div>

      {/* ── Result ── */}
      {genResult && <VerificationResult result={genResult} />}

      {/* ── History ── */}
      <VerificationHistory
        data={auditData}
        loading={auditLoading}
        error={auditError}
        onRetry={loadAudit}
        selectedRoleId={roleId}
      />
    </div>
  );
}
