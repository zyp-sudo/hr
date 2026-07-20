import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Bot,
  Check,
  Clock,
  Loader2,
  RefreshCw,
  Sparkles,
  XCircle,
} from "lucide-react";
import type { CompanyAgentHealth, CompanyAgentResult } from "../types";
import {
  evaluateWithAgent,
  fetchAgentHealth,
  type EvaluateResult,
  type HealthCheckResult,
} from "../utils/companyAgent";

/* ── Props ─────────────────────────────────────────────────────────── */

interface Props {
  candidateName: string;
  resumeText: string;
  jobId: string;
  jobTitle: string;
  jobDescription?: string;
  requiredSkills?: string[];
  localScore: number;
  localDimensions?: Record<string, number>;
}

/* ── Panel state machine ──────────────────────────────────────────────
 *
 *  checking    — health request is in-flight (not yet resolved)
 *  disabled    — health returned; enabled=false or configured=false
 *  unavailable — health request failed (network, non-JSON, HTML, etc.)
 *  ready       — enabled=true, configured=true, ready to evaluate
 *  loading     — evaluating
 *  success     — agent returned a valid score
 *  failed      — agent call returned failed / validation error
 * ──────────────────────────────────────────────────────────────────── */

type PanelState =
  | "checking"
  | "disabled"
  | "unavailable"
  | "ready"
  | "loading"
  | "success"
  | "failed";

/* ── Component ──────────────────────────────────────────────────────── */

export default function CompanyAgentPanel({
  candidateName,
  resumeText,
  jobId,
  jobTitle,
  jobDescription,
  requiredSkills,
  localScore,
  localDimensions,
}: Props) {
  const [state, setState] = useState<PanelState>("checking");
  const [health, setHealth] = useState<CompanyAgentHealth | null>(null);
  const [result, setResult] = useState<CompanyAgentResult | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  // ── health check on mount ──────────────────────────────────────────

  useEffect(() => {
    let cancelled = false;
    setState("checking");

    fetchAgentHealth().then((h: HealthCheckResult) => {
      if (cancelled) return;

      if (h.state === "unavailable") {
        setState("unavailable");
        setHealth(null);
        setErrorMsg(h.reason);
        return;
      }

      // h.state === "ok"
      setHealth(h.health);
      if (!h.health.enabled || !h.health.configured) {
        setState("disabled");
      } else {
        setState("ready");
      }
    });

    return () => {
      cancelled = true;
    };
  }, [candidateName, jobId, jobTitle]);

  // ── evaluate ───────────────────────────────────────────────────────

  const evaluate = useCallback(async () => {
    if (!resumeText || resumeText.trim().length < 30) return;
    setState("loading");
    setErrorMsg("");
    setResult(null);

    const res: EvaluateResult = await evaluateWithAgent({
      candidateName,
      resumeText,
      jobId,
      jobTitle,
      jobDescription,
      requiredSkills,
      localScore,
      localDimensions,
    });

    if (res.status === "disabled") {
      setState("disabled");
      return;
    }

    if (res.status === "failed") {
      setState("failed");
      setErrorMsg(res.summary);
      return;
    }

    // res.status === "success"
    setResult(res.data);
    setState("success");
  }, [
    candidateName,
    resumeText,
    jobId,
    jobTitle,
    jobDescription,
    requiredSkills,
    localScore,
    localDimensions,
  ]);

  // ── auto-evaluate when ready ────────────────────────────────────────

  useEffect(() => {
    if (state === "ready" && resumeText && resumeText.trim().length >= 30) {
      evaluate();
    }
  }, [state, resumeText, jobId, jobTitle]);

  /* ═══════════════════════════════════════════════════════════════════
     RENDER: checking
     ═══════════════════════════════════════════════════════════════════ */

  if (state === "checking") {
    return (
      <div className="company-agent-panel company-agent-panel--disabled">
        <div className="company-agent-panel__head">
          <Sparkles className="company-agent-panel__icon" />
          <span>智能体增强评分</span>
          <span className="company-agent-badge company-agent-badge--muted">
            <Loader2 className="spin-icon" style={{ width: 12 }} />
            {" "}检查中
          </span>
        </div>
        <div className="company-agent-row">
          <span className="company-agent-row__label">本地评分</span>
          <span className="company-agent-row__value">{localScore} 分</span>
        </div>
        <div className="company-agent-row">
          <span className="company-agent-row__label">智能体评分</span>
          <span className="company-agent-row__value--muted">—</span>
        </div>
        <div className="company-agent-note">
          <span>正在检查公司智能体服务状态…</span>
        </div>
      </div>
    );
  }

  /* ═══════════════════════════════════════════════════════════════════
     RENDER: disabled (configured=false or enabled=false)
     ═══════════════════════════════════════════════════════════════════ */

  if (state === "disabled") {
    return (
      <div className="company-agent-panel company-agent-panel--disabled">
        <div className="company-agent-panel__head">
          <Sparkles className="company-agent-panel__icon" />
          <span>智能体增强评分</span>
          <span className="company-agent-badge company-agent-badge--muted">
            待接入
          </span>
        </div>
        <div className="company-agent-row">
          <span className="company-agent-row__label">当前评分模式</span>
          <span className="company-agent-row__value--muted">基础规则</span>
        </div>
        <div className="company-agent-row">
          <span className="company-agent-row__label">智能体增强</span>
          <span className="company-agent-row__value--muted">未接入</span>
        </div>
        <div className="company-agent-row">
          <span className="company-agent-row__label">本地评分</span>
          <span className="company-agent-row__value">{localScore} 分</span>
        </div>
        <div className="company-agent-row">
          <span className="company-agent-row__label">智能体评分</span>
          <span className="company-agent-row__value--muted">—</span>
        </div>
        <div className="company-agent-note">
          <AlertTriangle />
          <span>
            公司智能体尚未接入。本地规则评分正常运作，智能体增强评分功能将在接入后自动启用。
          </span>
        </div>
      </div>
    );
  }

  /* ═══════════════════════════════════════════════════════════════════
     RENDER: unavailable (health check failed — network, HTML, etc.)
     ═══════════════════════════════════════════════════════════════════ */

  if (state === "unavailable") {
    return (
      <div className="company-agent-panel company-agent-panel--disabled">
        <div className="company-agent-panel__head">
          <Sparkles className="company-agent-panel__icon" />
          <span>智能体增强评分</span>
          <span className="company-agent-badge company-agent-badge--muted">
            服务不可用
          </span>
        </div>
        <div className="company-agent-row">
          <span className="company-agent-row__label">本地评分</span>
          <span className="company-agent-row__value">{localScore} 分</span>
        </div>
        <div className="company-agent-row">
          <span className="company-agent-row__label">智能体评分</span>
          <span className="company-agent-row__value--muted">—</span>
        </div>
        {errorMsg && (
          <div className="company-agent-error-msg">
            <AlertTriangle />
            <span>{errorMsg}</span>
          </div>
        )}
        <button
          className="company-agent-retry-btn"
          onClick={() => {
            setState("checking");
            fetchAgentHealth().then((h: HealthCheckResult) => {
              if (h.state === "unavailable") {
                setState("unavailable");
                setHealth(null);
                setErrorMsg(h.reason);
              } else {
                setHealth(h.health);
                setState(
                  h.health.enabled && h.health.configured ? "ready" : "disabled",
                );
              }
            });
          }}
        >
          <RefreshCw /> 重新检查
        </button>
        <div className="company-agent-note">
          <span>智能体服务暂时不可用，仅展示本地规则评分。</span>
        </div>
      </div>
    );
  }

  /* ═══════════════════════════════════════════════════════════════════
     RENDER: loading
     ═══════════════════════════════════════════════════════════════════ */

  if (state === "loading") {
    return (
      <div className="company-agent-panel company-agent-panel--loading">
        <div className="company-agent-panel__head">
          <Sparkles className="company-agent-panel__icon" />
          <span>智能体增强评分</span>
          <span className="company-agent-badge company-agent-badge--active">
            <Loader2 className="spin-icon" />
            正在评分
          </span>
        </div>
        <div className="company-agent-row">
          <span className="company-agent-row__label">本地评分</span>
          <span className="company-agent-row__value">{localScore} 分</span>
        </div>
        <div className="company-agent-row">
          <span className="company-agent-row__label">智能体评分</span>
          <span className="company-agent-row__value--muted">
            <Loader2 className="spin-icon" style={{ width: 13 }} /> 评估中…
          </span>
        </div>
        <div className="company-agent-loading-bar">
          <div className="company-agent-loading-bar__track" />
        </div>
      </div>
    );
  }

  /* ═══════════════════════════════════════════════════════════════════
     RENDER: failed
     ═══════════════════════════════════════════════════════════════════ */

  if (state === "failed") {
    return (
      <div className="company-agent-panel company-agent-panel--failed">
        <div className="company-agent-panel__head">
          <Sparkles className="company-agent-panel__icon" />
          <span>智能体增强评分</span>
          <span className="company-agent-badge company-agent-badge--error">
            <XCircle />
            评分失败
          </span>
        </div>
        <div className="company-agent-row">
          <span className="company-agent-row__label">本地评分</span>
          <span className="company-agent-row__value">{localScore} 分</span>
        </div>
        <div className="company-agent-row">
          <span className="company-agent-row__label">智能体评分</span>
          <span className="company-agent-row__value--muted">—</span>
        </div>
        {errorMsg && (
          <div className="company-agent-error-msg">
            <AlertTriangle />
            <span>{errorMsg}</span>
          </div>
        )}
        <button className="company-agent-retry-btn" onClick={evaluate}>
          <RefreshCw /> 重新评估
        </button>
        <div className="company-agent-note">
          <span>本次失败不影响本地规则评分。可稍后重试。</span>
        </div>
      </div>
    );
  }

  /* ═══════════════════════════════════════════════════════════════════
     RENDER: success
     ═══════════════════════════════════════════════════════════════════ */

  if (state === "success" && result) {
    return (
      <div className="company-agent-panel company-agent-panel--success">
        <div className="company-agent-panel__head">
          <Sparkles className="company-agent-panel__icon" />
          <span>智能体增强评分</span>
          <span className="company-agent-badge company-agent-badge--success">
            <Bot />
            公司智能体评分
          </span>
        </div>

        <div className="company-agent-score-grid">
          <div className="company-agent-score-card company-agent-score-card--local">
            <div className="company-agent-score-card__label">本地规则评分</div>
            <div className="company-agent-score-card__value">{localScore}</div>
            <div className="company-agent-score-card__unit">分</div>
          </div>
          <div className="company-agent-score-card company-agent-score-card--agent">
            <div className="company-agent-score-card__label">
              <Sparkles /> 智能体评分
            </div>
            <div className="company-agent-score-card__value">
              {result.agent_score ?? "—"}
            </div>
            <div className="company-agent-score-card__unit">分</div>
          </div>
        </div>

        {result.recommendation && (
          <div className="company-agent-recommendation">
            <div className="company-agent-recommendation__label">推荐结论</div>
            <div className="company-agent-recommendation__text">
              {result.recommendation}
            </div>
          </div>
        )}

        {result.summary && (
          <div className="company-agent-summary">
            <div className="company-agent-summary__label">评估摘要</div>
            <p>{result.summary}</p>
          </div>
        )}

        {result.strengths.length > 0 && (
          <div className="company-agent-list-section">
            <div className="company-agent-list-section__label">核心优势</div>
            <ul>
              {result.strengths.map((s, i) => (
                <li key={i}>
                  <Check /> {s}
                </li>
              ))}
            </ul>
          </div>
        )}

        {(result.risks.length > 0 || result.skill_gaps.length > 0) && (
          <div className="company-agent-list-section">
            <div className="company-agent-list-section__label">
              风险与能力缺口
            </div>
            {result.risks.length > 0 && (
              <ul className="company-agent-list--risks">
                {result.risks.map((r, i) => (
                  <li key={i}>
                    <AlertTriangle /> {r}
                  </li>
                ))}
              </ul>
            )}
            {result.skill_gaps.length > 0 && (
              <div className="company-agent-tags">
                {result.skill_gaps.map((g) => (
                  <span key={g} className="company-agent-tag company-agent-tag--gap">
                    {g}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {result.evidence.length > 0 && (
          <div className="company-agent-list-section">
            <div className="company-agent-list-section__label">评分依据</div>
            <ul className="company-agent-list--evidence">
              {result.evidence.map((e, i) => (
                <li key={i}>
                  <span className="company-agent-evidence-type">{e.type}</span>
                  <span>{e.description}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="company-agent-meta">
          <span>
            <Clock /> {result.latency_ms}ms
          </span>
          {result.model && <span>模型：{result.model}</span>}
          <span className="company-agent-badge company-agent-badge--agent">
            公司智能体评分
          </span>
        </div>
      </div>
    );
  }

  /* ═══════════════════════════════════════════════════════════════════
     RENDER: ready (shouldn't happen long — auto-evaluates)
     ═══════════════════════════════════════════════════════════════════ */

  return (
    <div className="company-agent-panel company-agent-panel--disabled">
      <div className="company-agent-panel__head">
        <Sparkles className="company-agent-panel__icon" />
        <span>智能体增强评分</span>
        <span className="company-agent-badge company-agent-badge--muted">
          就绪
        </span>
      </div>
      <div className="company-agent-row">
        <span className="company-agent-row__label">本地评分</span>
        <span className="company-agent-row__value">{localScore} 分</span>
      </div>
      <div className="company-agent-row">
        <span className="company-agent-row__label">智能体评分</span>
        <span className="company-agent-row__value--muted">—</span>
      </div>
      <div className="company-agent-note">
        <span>智能体服务已就绪，请上传简历后自动评估。</span>
      </div>
    </div>
  );
}
