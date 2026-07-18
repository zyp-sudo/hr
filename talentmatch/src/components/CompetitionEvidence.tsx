import { useState, useEffect, useCallback } from "react";
import {
  Activity, AlertTriangle, CheckCircle2, ChevronDown, ChevronUp,
  FileSearch, RefreshCw, Search, Send, ShieldAlert, ShieldCheck, ShieldOff, XCircle
} from "lucide-react";
import {
  validateRagHealthResponse, validateRagAuditResponse, validateRagGenerateResponse,
  ValidationError,
  type ValidatedRagHealthResponse, type ValidatedRagAuditResponse,
  type ValidatedRagGenerateResponse,
} from "../utils/competitionValidators";

const API_BASE = "/api/platform/storage/api/competition/rag";

function timeText(date: Date) {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(date);
}

function StatusBadge({ label, color }: { label: string; color: string }) {
  return <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 13, fontWeight: 600 }}><span style={{ width: 8, height: 8, borderRadius: "50%", background: color }} /> {label}</span>;
}

export default function CompetitionEvidence() {
  // Health
  const [health, setHealth] = useState<ValidatedRagHealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthError, setHealthError] = useState("");

  // Generate
  const [roleId, setRoleId] = useState("java-developer");
  const [question, setQuestion] = useState("");
  const [claimsText, setClaimsText] = useState("");
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState("");
  const [genResult, setGenResult] = useState<ValidatedRagGenerateResponse | null>(null);

  // Audit
  const [auditData, setAuditData] = useState<ValidatedRagAuditResponse | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState("");
  const [auditOpen, setAuditOpen] = useState(false);

  const loadHealth = useCallback(async () => {
    setHealthLoading(true);
    setHealthError("");
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(body.detail || `服务返回 HTTP ${res.status}`); }
      const validated = await validateRagHealthResponse(res);
      setHealth(validated);
    } catch (e: any) {
      setHealthError(e.name === "ValidationError" ? e.message : (e.message || "无法获取证据服务状态"));
      setHealth(null);
    } finally { setHealthLoading(false); }
  }, []);

  const loadAudit = useCallback(async () => {
    setAuditLoading(true);
    setAuditError("");
    try {
      const res = await fetch(`${API_BASE}/audit?limit=50`);
      if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(body.detail || `服务返回 HTTP ${res.status}`); }
      const validated = await validateRagAuditResponse(res);
      setAuditData(validated);
    } catch (e: any) {
      setAuditError(e.name === "ValidationError" ? e.message : (e.message || "无法获取审计记录"));
      setAuditData(null);
    } finally { setAuditLoading(false); }
  }, []);

  useEffect(() => { loadHealth(); }, [loadHealth]);

  const handleGenerate = async () => {
    const claims = claimsText.split("\n").map(s => s.trim()).filter(Boolean);
    if (!roleId.trim() || !question.trim() || claims.length === 0) { setGenError("请填写岗位ID、评估问题和至少一条能力声明"); return; }
    setGenError(""); setGenerating(true); setGenResult(null);
    try {
      const res = await fetch(`${API_BASE}/generate`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role_id: roleId, question, candidate_claims: claims }),
      });
      if (!res.ok) { const errBody = await res.json().catch(() => ({})); throw new Error(errBody.detail || `服务返回 HTTP ${res.status}`); }
      const validated = await validateRagGenerateResponse(res);
      setGenResult(validated);
    } catch (e: any) {
      setGenError(e.name === "ValidationError" ? e.message : (e.message || "证据生成失败"));
    } finally { setGenerating(false); }
  };

  const statusLabel = (s: string) => s === "ok" ? "正常" : s === "degraded" ? "降级" : "不可用";
  const statusColor = (s: string) => s === "ok" ? "#4ade80" : s === "degraded" ? "#facc15" : "#f87171";
  const healthOk = health !== null && !healthError;

  return (
    <div className="comp-evidence">
      {/* ── User-facing description ── */}
      <div className="comp-evidence__intro" style={{marginBottom:20,padding:"14px 18px",borderRadius:10,border:"1px solid rgba(255,255,255,.08)",background:"rgba(0,0,0,.15)"}}>
        <p style={{margin:0,fontSize:13,lineHeight:1.7,color:"rgba(255,255,255,.65)"}}>核查岗位能力声明是否具有数据来源，并拦截缺少来源的内容。</p>
        <p style={{margin:"8px 0 0",fontSize:11,lineHeight:1.6,color:"rgba(255,255,255,.35)"}}>技术说明：轻量确定性证据检索，非生产级 RAG。</p>
      </div>
      {/* ── Health ── */}
      <div className="comp-evidence__section">
        <h3 className="comp-evidence__section-title"><Activity style={{ width: 18 }} /> 证据服务状态</h3>
        {healthLoading ? (
          <div className="comp-evidence__health-bar"><RefreshCw className="spin" style={{ width: 16 }} /><span>正在检测服务状态…</span></div>
        ) : healthError ? (
          <div className="comp-error-banner"><AlertTriangle /><div><b>服务检测失败</b><span>{healthError}</span></div><button className="ghost-action" onClick={loadHealth} aria-label="重试">重试</button></div>
        ) : healthOk ? (
          <div className="comp-evidence__health-grid">
            <div className="comp-evidence__health-card"><span className="comp-evidence__health-dot" style={{ background: statusColor(health.status) }} /><div><b>{statusLabel(health.status)}</b><small>核查能力声明数据来源，拦截无证据内容</small></div></div>
            <div className="comp-evidence__health-card"><b>{health.sources_loaded.length}</b><small>已加载数据源</small></div>
            <div className="comp-evidence__health-card"><b>{health.competencies_indexed}</b><small>能力项索引</small></div>
            <div className="comp-evidence__health-card"><b>{health.roles_indexed}</b><small>岗位索引</small></div>
            <div className="comp-evidence__health-card"><b>{health.alias_entries}</b><small>别名条目</small></div>
            <div className="comp-evidence__health-card">
              <span style={{ display: "flex", alignItems: "center", gap: 4 }}>{health.milvus_wired ? <><ShieldCheck style={{ width: 14, color: "#4ade80" }} /> Milvus 已连接</> : <><ShieldOff style={{ width: 14, color: "#6e6a78" }} /> Milvus 未接入</>}</span>
              <span style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 4 }}>{health.neo4j_wired ? <><ShieldCheck style={{ width: 14, color: "#4ade80" }} /> Neo4j 已连接</> : <><ShieldOff style={{ width: 14, color: "#6e6a78" }} /> Neo4j 未接入</>}</span>
              <small>可选后端</small>
            </div>
          </div>
        ) : null}
      </div>

      {/* ── Generate ── */}
      <div className="comp-evidence__section">
        <h3 className="comp-evidence__section-title"><FileSearch style={{ width: 18 }} /> 证据生成</h3>
        <div className="comp-evidence__form">
          <label className="comp-field"><span>岗位 ID</span><input value={roleId} onChange={e => setRoleId(e.target.value)} placeholder="如 java-developer" aria-label="岗位ID" /></label>
          <label className="comp-field"><span>评估问题</span><input value={question} onChange={e => setQuestion(e.target.value)} placeholder="如：该岗位需要哪些核心技术能力？" aria-label="评估问题" /></label>
          <label className="comp-field"><span>能力声明（一行一条）</span><textarea value={claimsText} onChange={e => setClaimsText(e.target.value)} placeholder={"精通Java开发\n熟悉分布式系统\n具备团队管理经验"} rows={4} aria-label="能力声明" /></label>
          {genError && <div className="comp-error-banner" style={{ marginTop: 8 }}><AlertTriangle /><div><b>生成失败</b><span>{genError}</span></div></div>}
          <button className="primary" onClick={handleGenerate} disabled={generating || !roleId || !question || !claimsText.trim()} aria-label="生成证据" style={{ marginTop: 8 }}><Send style={{ width: 16 }} /> {generating ? "生成中…" : "生成证据"}</button>
        </div>

        {genResult && (
          <div className="comp-evidence__result">
            <div className="comp-evidence__result-head"><h4>生成结果</h4><span>审计 ID: <code>{genResult.audit_id}</code></span><span>模式: {genResult.mode}</span><span>整体置信度: {Math.round(genResult.confidence * 100)}%</span></div>
            <p className="comp-evidence__answer">{genResult.answer}</p>

            {/* Supported claims */}
            {genResult.claims.length > 0 && (
              <div className="comp-evidence__claims">
                <h5><CheckCircle2 style={{ width: 16, color: "#4ade80" }} />有证据支持的声明 ({genResult.claims.length})</h5>
                <div className="comp-evidence__claims-list">
                  {genResult.claims.map((c, i) => (
                    <div key={i} className="comp-evidence__claim comp-evidence__claim--supported">
                      <div className="comp-evidence__claim-head">
                        <span className="comp-evidence__claim-text">{c.text}</span>
                        {c.needs_review && <span className="comp-status comp-status--pending">需人工复核</span>}
                      </div>
                      <div className="comp-evidence__claim-meta">
                        <span>置信度 {Math.round(c.confidence * 100)}%</span>
                        <span>来源 {c.source_ids.length} 条</span>
                        {c.source_ids.length > 0 && <span className="comp-evidence__claim-sources">{c.source_ids.slice(0, 3).join(", ")}{c.source_ids.length > 3 ? ` …共${c.source_ids.length}个` : ""}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Blocked claims */}
            {genResult.blocked_claims.length > 0 && (
              <div className="comp-evidence__claims">
                <h5><XCircle style={{ width: 16, color: "#f87171" }} />无来源被拦截的声明 ({genResult.blocked_claims.length})</h5>
                <div className="comp-evidence__claims-list">
                  {genResult.blocked_claims.map((c, i) => (
                    <div key={i} className="comp-evidence__claim comp-evidence__claim--blocked">
                      <span className="comp-evidence__claim-text">{c.text}</span>
                      <span style={{ color: "#f87171", fontSize: 11 }}>无证据来源，已拦截</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Audit ── */}
      <div className="comp-evidence__section">
        <button className="comp-review-toggle" onClick={() => { setAuditOpen(!auditOpen); if (!auditOpen) loadAudit(); }} aria-label={auditOpen ? "收起审计记录" : "展开审计记录"}>
          <ShieldAlert style={{ width: 16 }} /><span>审计记录</span>
          <span style={{ color: "#777180", fontSize: 11 }}>{auditOpen ? `${auditData?.total || 0} 条` : "点击展开"}</span>
          {auditOpen ? <ChevronUp style={{ width: 14 }} /> : <ChevronDown style={{ width: 14 }} />}
        </button>
        {auditOpen && (
          <div className="comp-evidence__audit">
            {auditError && <div className="comp-error-banner"><AlertTriangle /><div><b>审计记录加载失败</b><span>{auditError}</span></div><button className="ghost-action" onClick={loadAudit} aria-label="重试">重试</button></div>}
            {auditLoading ? <p style={{ color: "#777180", fontSize: 12, textAlign: "center", padding: 16 }}>加载审计记录中…</p>
              : !auditData || auditData.items.length === 0 ? (
                <div className="comp-empty" style={{ minHeight: 120, border: "none" }}><Search /><h3>暂无审计记录</h3><p>还没有执行过证据生成请求，或审计文件尚不存在。</p></div>
              ) : (
                <div className="comp-evidence__audit-list">
                  {auditData.items.map(entry => (
                    <div key={entry.audit_id} className="comp-evidence__audit-item">
                      <div className="comp-evidence__audit-head">
                        <code>{entry.audit_id}</code>
                        <span className="comp-evidence__audit-mode">{entry.mode}</span>
                        <span className={`comp-status comp-status--${entry.review_status === "auto" ? "approved" : "pending"}`}>{entry.review_status}</span>
                        <time>{timeText(new Date(entry.timestamp))}</time>
                      </div>
                      <div className="comp-evidence__audit-detail">
                        <span>来源: {(entry.sources_used || []).join(", ") || "无"}</span>
                        {entry.request_summary && Object.keys(entry.request_summary).length > 0 && <span>请求: {JSON.stringify(entry.request_summary).slice(0, 200)}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
          </div>
        )}
      </div>
    </div>
  );
}
