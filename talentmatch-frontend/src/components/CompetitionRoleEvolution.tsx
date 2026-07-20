import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  AlertTriangle, ArrowRight, Check, ChevronDown,
  Clock3, Info, Lightbulb, ListChecks, RefreshCw, Search,
  FileText, SearchIcon, TrendingDown
} from "lucide-react";
import {
  validateRoleVersionsResponse, validateRoleDiffResponse, ValidationError,
  type ValidatedRoleVersionItem, type ValidatedRoleVersionsResponse,
  type ValidatedRoleDiffResponse, type ValidatedDiffSkillItem,
} from "../utils/competitionValidators";
import RolePicker from "./RolePicker";
import { AVAILABLE_ROLES } from "../utils/evidenceHelpers";

// ─── Constants ───────────────────────────────────────────────────

const API_BASE = "/api/platform/storage/api/competition";

const LEVEL_ORDER = ["beginner", "intermediate", "advanced", "expert"] as const;

const LEVEL_ZH: Record<string, string> = {
  beginner: "入门", intermediate: "熟练", advanced: "高级", expert: "专家级",
};

const SOURCE_PLATFORM_MAP: Array<{ prefix: string; name: string }> = [
  { prefix: "src-boss", name: "BOSS直聘" },
  { prefix: "src-lagou", name: "拉勾招聘" },
  { prefix: "src-51job", name: "前程无忧" },
  { prefix: "src-zhilian", name: "智联招聘" },
  { prefix: "src-liepin", name: "猎聘" },
  { prefix: "src-seed", name: "项目初始资料" },
  { prefix: "src-mkt", name: "市场招聘数据" },
];

type ChangeCategory = "new" | "upgraded" | "downgraded" | "removed" | "adjusted";
type DetailCategory = ChangeCategory | "unchanged";
type EvolutionViewMode = "loading" | "empty" | "snapshot" | "comparison" | "error";
type SnapshotFilter = "all" | string; // "all" | level string

interface ClassifiedChange {
  item: ValidatedDiffSkillItem;
  category: ChangeCategory;
  oldLevel: string | null;
  newLevel: string | null;
}

interface SuggestionItem {
  id: string;
  icon: React.ReactNode;
  text: string;
}

const CARD_DEFS: Array<{ key: DetailCategory; label: string; cssMod: string }> = [
  { key: "new",        label: "新增要求", cssMod: "new" },
  { key: "upgraded",   label: "要求提高", cssMod: "upgraded" },
  { key: "downgraded", label: "要求降低", cssMod: "downgraded" },
  { key: "removed",    label: "不再强调", cssMod: "removed" },
  { key: "adjusted",   label: "其他调整", cssMod: "adjusted" },
  { key: "unchanged",  label: "保持不变", cssMod: "unchanged" },
];

const SNAPSHOT_LEVEL_DEFS: Array<{ key: SnapshotFilter; label: string; cssMod: string }> = [
  { key: "all",    label: "全部能力", cssMod: "new" },
  { key: "expert",     label: "专家级",   cssMod: "expert" },
  { key: "advanced",   label: "高级",     cssMod: "upgraded" },
  { key: "intermediate", label: "熟练",   cssMod: "downgraded" },
  { key: "beginner",   label: "入门",     cssMod: "new" },
];

const SNAPSHOT_LEVEL_CSS: Record<string, string> = {
  expert: "snapshot-expert",
  advanced: "snapshot-advanced",
  intermediate: "snapshot-intermediate",
  beginner: "snapshot-beginner",
};

// ─── Helpers ─────────────────────────────────────────────────────

function formatVersionDate(ts: string): string {
  try { const d = new Date(ts); if (isNaN(d.getTime())) return ts;
    const y = d.getFullYear(); const m = d.getMonth() + 1; const day = d.getDate();
    return ts.includes("T") ? `${y}年${m}月${day}日` : `${y}年${m}月`;
  } catch { return ts; }
}
function translateSkillLevel(level: string | null): string {
  if (!level) return "未注明";
  return LEVEL_ZH[level.toLowerCase()] || level;
}
function getLevelRank(level: string | null): number {
  if (!level) return -1;
  return LEVEL_ORDER.indexOf(level.toLowerCase() as typeof LEVEL_ORDER[number]);
}
function getSourcePlatform(id: string): string {
  if (!id) return "其他招聘渠道";
  for (const { prefix, name } of SOURCE_PLATFORM_MAP) {
    if (id.toLowerCase().startsWith(prefix)) return name;
  }
  return "其他招聘渠道";
}
function groupSourcePlatforms(ids: string[]): Array<{ name: string; count: number }> {
  if (!ids?.length) return [];
  const m = new Map<string, number>();
  for (const id of ids) { const n = getSourcePlatform(id); m.set(n, (m.get(n) || 0) + 1); }
  return Array.from(m.entries()).map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count);
}
function classifyModifiedSkill(
  name: string, fromSkills: ValidatedRoleVersionItem["skills"],
  toSkills: ValidatedRoleVersionItem["skills"], newLevel: string | null,
): { category: "upgraded" | "downgraded" | "adjusted"; oldLevel: string | null } {
  const old = fromSkills.find(s => s.name === name);
  const oldLevel = old?.level ?? null;
  const oR = getLevelRank(oldLevel); const nR = getLevelRank(newLevel);
  if (oR >= 0 && nR >= 0) { if (nR > oR) return { category: "upgraded", oldLevel }; if (nR < oR) return { category: "downgraded", oldLevel }; }
  return { category: "adjusted", oldLevel };
}
function getDefaultReason(category: ChangeCategory): string {
  switch (category) {
    case "new": return "新的岗位需求中开始出现该能力。";
    case "upgraded": return "企业对该能力的要求有所提高。";
    case "downgraded": return "企业对该能力的要求有所降低。";
    case "removed": return "近期岗位需求中较少强调该能力。";
    case "adjusted": return "该能力的岗位要求发生了调整。";
  }
}
function snapshotSkillDescription(level: string | null): string {
  switch ((level || "").toLowerCase()) {
    case "expert": return "该岗位的核心能力，需要具备深入实践经验。";
    case "advanced": return "该岗位的重要能力，需要能够独立完成相关工作。";
    case "intermediate": return "该岗位的常用能力，需要具备实际使用经验。";
    case "beginner": return "了解基础概念，并能在指导下完成相关工作。";
    default: return "";
  }
}

// ─── Shared Sub-Components ───────────────────────────────────────

function SourcePlatforms({ ids }: { ids: string[] }) {
  const groups = useMemo(() => groupSourcePlatforms(ids), [ids]);
  if (groups.length === 0) return <span className="comp-evolution__no-source">暂无来源信息</span>;
  return <span className="comp-evolution__sources">参考来源：{groups.map((g, i) => <span key={g.name}>{i > 0 && "、"}{g.name}{g.count > 1 ? `（${g.count}条）` : ""}</span>)}</span>;
}

// ── useClickOutside (still needed for VersionPicker & AdvicePopover) ──

function useClickOutside<E extends HTMLElement = HTMLElement>(
  onOutside: () => void, enabled: boolean,
) {
  const ref = useRef<E | null>(null);
  const cbRef = useRef(onOutside); cbRef.current = onOutside;
  useEffect(() => {
    if (!enabled) return;
    const h = (e: MouseEvent | TouchEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) cbRef.current();
    };
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") cbRef.current(); };
    document.addEventListener("mousedown", h); document.addEventListener("touchstart", h);
    document.addEventListener("keydown", k);
    return () => {
      document.removeEventListener("mousedown", h); document.removeEventListener("touchstart", h);
      document.removeEventListener("keydown", k);
    };
  }, [enabled]);
  return ref;
}

// ── VersionPicker ────────────────────────────────────────────────

function VersionPicker({ versions, selectedIdx, onChange, label, disabledAfter, disabledBefore, readonly }: {
  versions: ValidatedRoleVersionItem[]; selectedIdx: number | null; onChange: (idx: number | null) => void;
  label: string; disabledAfter?: number; disabledBefore?: number; readonly?: boolean;
}) {
  const [open, setOpen] = useState(false); const [focusIdx, setFocusIdx] = useState(-1);
  const outerRef = useClickOutside<HTMLDivElement>(() => setOpen(false), open);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const selected = selectedIdx != null ? versions[selectedIdx] : null;
  const isDisabled = (i: number) => (disabledAfter != null && i >= disabledAfter) || (disabledBefore != null && i <= disabledBefore);
  const close = () => { setOpen(false); setFocusIdx(-1); triggerRef.current?.focus(); };
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") { e.preventDefault(); close(); return; }
    if (e.key === "ArrowDown") { e.preventDefault(); setFocusIdx(i => Math.min(i + 1, versions.length - 1)); return; }
    if (e.key === "ArrowUp") { e.preventDefault(); setFocusIdx(i => Math.max(i - 1, -1)); return; }
    if (e.key === "Enter") { e.preventDefault(); const idx = focusIdx >= 0 ? focusIdx : 0; if (idx < versions.length && !isDisabled(idx)) { onChange(idx); close(); } }
  };
  const triggerLabel = selected ? formatVersionDate(selected.timestamp) : "选择时间…";
  return (
    <div className="comp-evo-picker" ref={outerRef}>
      <label className="comp-evo-picker__label">{label}</label>
      <button ref={triggerRef} type="button" disabled={readonly}
        className={`comp-evo-picker__trigger${open ? " comp-evo-picker__trigger--open" : ""}`}
        onClick={(e) => { e.stopPropagation(); if (!readonly) { open ? close() : setOpen(true); } }}
        aria-haspopup="listbox" aria-expanded={open} aria-label={label}>
        <span className="comp-evo-picker__trigger-text">{triggerLabel}</span>
        {selectedIdx === versions.length - 1 && <span className="comp-evo-picker__latest-tag">最新</span>}
        {readonly && <span className="comp-evo-picker__latest-tag comp-evo-picker__latest-tag--hint">仅有一份记录</span>}
        {!readonly && <ChevronDown style={{ width: 14, flex: "none", transition: "transform .2s", transform: open ? "rotate(180deg)" : "rotate(0deg)" }} />}
      </button>
      {open && !readonly && (
        <div className="comp-evo-picker__menu" role="listbox" onKeyDown={onKeyDown} onClick={(e) => e.stopPropagation()}>
          <div className="comp-evo-picker__list">
            {versions.map((v, i) => { const d = isDisabled(i); const sel = i === selectedIdx; return (
              <div key={v.version_id} role="option" aria-selected={sel} aria-disabled={d || undefined}
                className={`comp-evo-picker__option${sel ? " comp-evo-picker__option--selected" : ""}${i === focusIdx ? " comp-evo-picker__option--focused" : ""}${d ? " comp-evo-picker__option--disabled" : ""}`}
                onClick={(e) => { e.stopPropagation(); if (!d) { onChange(i); close(); } }} onMouseEnter={() => { if (!d) setFocusIdx(i); }}>
                <span className="comp-evo-picker__option-name">{formatVersionDate(v.timestamp)}</span>
                {i === versions.length - 1 && <span className="comp-evo-picker__latest-tag">最新</span>}{sel && <Check style={{ width: 14, flex: "none" }} />}
              </div>
            ); })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── RecruitmentAdvicePopover ─────────────────────────────────────

const SUGGESTION_ICONS: Record<string, React.ReactNode> = {
  new: <FileText style={{ width: 14, flex: "none" }} />,
  upgraded: <SearchIcon style={{ width: 14, flex: "none" }} />,
  removed: <TrendingDown style={{ width: 14, flex: "none" }} />,
  snapshot: <ListChecks style={{ width: 14, flex: "none" }} />,
  snapshot_verify: <SearchIcon style={{ width: 14, flex: "none" }} />,
  snapshot_limited: <Info style={{ width: 14, flex: "none" }} />,
};

function RecruitmentAdvicePopover({ suggestions, disclaimer, totalSuggestions }: {
  suggestions: SuggestionItem[]; disclaimer: string; totalSuggestions: number;
}) {
  const [open, setOpen] = useState(false);
  const ref = useClickOutside<HTMLDivElement>(() => setOpen(false), open);
  return (
    <div className="comp-evo-advice" ref={ref}>
      <button type="button" className="comp-evo-advice__btn"
        onClick={(e) => { e.stopPropagation(); setOpen(o => !o); }}
        aria-label={`招聘建议${totalSuggestions > 0 ? `（${totalSuggestions}条）` : ""}`} aria-expanded={open}>
        <Lightbulb style={{ width: 16 }} /><span>招聘建议</span>
        {totalSuggestions > 0 && <span className="comp-evo-advice__badge">{totalSuggestions}</span>}
      </button>
      {open && (
        <div className="comp-evo-advice__popover" onClick={(e) => e.stopPropagation()}>
          <div className="comp-evo-advice__popover-head"><h3>招聘建议</h3><p>{disclaimer}</p></div>
          {totalSuggestions === 0 ? (
            <p className="comp-evo-advice__empty">该岗位要求整体稳定，暂时无需调整招聘标准。</p>
          ) : (
            <ul className="comp-evo-advice__list">
              {suggestions.map(s => <li key={s.id} className="comp-evo-advice__item"><span className="comp-evo-advice__item-icon">{s.icon}</span><span>{s.text}</span></li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

// ── EvolutionFilterCard ─────────────────────────────────────────

function EvolutionFilterCard({ roleId, onRoleChange, sortedVersions, fromIdx, toIdx, onFromChange, onToChange, loading, onRefresh, diffLoading, viewMode }: {
  roleId: string; onRoleChange: (id: string) => void; sortedVersions: ValidatedRoleVersionItem[];
  fromIdx: number | null; toIdx: number | null; onFromChange: (idx: number | null) => void;
  onToChange: (idx: number | null) => void; loading: boolean; onRefresh: () => void;
  diffLoading: boolean; viewMode: EvolutionViewMode;
}) {
  const isSnapshot = viewMode === "snapshot";
  return (
    <div className="comp-evo-filter-card">
      <div className="comp-evo-filter-card__main">
        <div className="comp-evo-filter-card__role">
          <RolePicker roles={AVAILABLE_ROLES} selectedId={roleId} onSelect={onRoleChange} />
        </div>
        {isSnapshot ? (
          <div className="comp-evo-filter-card__time">
            <VersionPicker versions={sortedVersions} selectedIdx={toIdx} onChange={() => {}} label="当前记录" readonly />
          </div>
        ) : (
          <>
            <div className="comp-evo-filter-card__time">
              <VersionPicker versions={sortedVersions} selectedIdx={fromIdx} onChange={onFromChange} label="开始时间" disabledAfter={toIdx ?? undefined} />
            </div>
            <ArrowRight style={{ width: 16, color: "var(--ent-text-muted, #8e8999)", flex: "none", marginTop: 20, alignSelf: "flex-start" }} aria-hidden="true" />
            <div className="comp-evo-filter-card__time">
              <VersionPicker versions={sortedVersions} selectedIdx={toIdx} onChange={onToChange} label="结束时间" disabledBefore={fromIdx ?? undefined} />
            </div>
          </>
        )}
      </div>
      <button className="comp-evo-filter-card__refresh" onClick={onRefresh} disabled={loading || diffLoading} aria-label="刷新数据" type="button">
        <RefreshCw className={loading || diffLoading ? "spin" : ""} style={{ width: 13 }} />刷新数据
      </button>
    </div>
  );
}

// ── Comparison view (multi-version) ─────────────────────────────

const CATEGORY_TAG: Record<string, { label: string; cssMod: string }> = {
  new: { label: "新增要求", cssMod: "new" }, upgraded: { label: "要求提高", cssMod: "upgraded" },
  downgraded: { label: "要求降低", cssMod: "downgraded" }, removed: { label: "不再强调", cssMod: "removed" },
  adjusted: { label: "其他调整", cssMod: "adjusted" },
};

function ChangeDetailItem({ change }: { change: ClassifiedChange }) {
  const { item, category, oldLevel, newLevel } = change;
  const tag = CATEGORY_TAG[category];
  const reason = item.reason || getDefaultReason(category);
  let levelText = "";
  if (category === "new") levelText = `当前要求：${translateSkillLevel(newLevel)}`;
  else if (category === "removed") levelText = `此前要求：${translateSkillLevel(oldLevel)}`;
  else if (category === "upgraded" || category === "downgraded") levelText = `${translateSkillLevel(oldLevel)} → ${translateSkillLevel(newLevel)}`;
  else if (oldLevel && newLevel && oldLevel !== newLevel) levelText = `${translateSkillLevel(oldLevel)} → ${translateSkillLevel(newLevel)}`;
  else levelText = `当前要求：${translateSkillLevel(newLevel || oldLevel)}`;
  return (
    <div className="comp-evo-detail-item">
      <div className="comp-evo-detail-item__head"><span className="comp-evo-detail-item__name">{item.name}</span><span className={`comp-evolution__tag comp-evolution__tag--${tag.cssMod}`}>{tag.label}</span></div>
      {levelText && <p className="comp-evo-detail-item__level">{levelText}</p>}
      <p className="comp-evo-detail-item__reason">变化说明：{reason}</p>
      <div className="comp-evo-detail-item__source"><SourcePlatforms ids={item.source_ids} /></div>
    </div>
  );
}
function UnchangedDetailList({ items }: { items: ValidatedDiffSkillItem[] }) {
  if (items.length === 0) return <div className="comp-evo-detail-empty">当前没有此类变化。</div>;
  return <div className="comp-evo-unchanged-grid">{items.map(item => <div key={item.name} className="comp-evo-unchanged-grid__item"><span className="comp-evo-unchanged-grid__name">{item.name}</span><span className="comp-evo-unchanged-grid__level">{translateSkillLevel(item.level)}</span></div>)}</div>;
}

function EvolutionSummaryPanel({ classified, unchangedItems, fromDate, toDate }: {
  classified: ClassifiedChange[]; unchangedItems: ValidatedDiffSkillItem[]; fromDate: string; toDate: string;
}) {
  const defaultCat = useMemo((): DetailCategory => {
    for (const def of CARD_DEFS) { if (def.key === "unchanged") continue; if (classified.filter(c => c.category === def.key).length > 0) return def.key as DetailCategory; }
    return "unchanged";
  }, [classified]);
  const [active, setActive] = useState<DetailCategory>(defaultCat);
  useEffect(() => { setActive(defaultCat); }, [defaultCat]);
  const counts: Record<DetailCategory, number> = useMemo(() => ({
    new: classified.filter(c => c.category === "new").length, upgraded: classified.filter(c => c.category === "upgraded").length,
    downgraded: classified.filter(c => c.category === "downgraded").length, removed: classified.filter(c => c.category === "removed").length,
    adjusted: classified.filter(c => c.category === "adjusted").length, unchanged: unchangedItems.length,
  }), [classified, unchangedItems]);
  const total = classified.length;
  const activeLabel = CARD_DEFS.find(d => d.key === active)!.label;
  const activeCount = counts[active];
  const detailContent = useMemo(() => {
    if (active === "unchanged") return <UnchangedDetailList items={unchangedItems} />;
    const items = classified.filter(c => c.category === active);
    if (items.length === 0) return <div className="comp-evo-detail-empty">当前没有此类变化。</div>;
    return <div className="comp-evo-detail-list">{items.map(c => <ChangeDetailItem key={c.item.name} change={c} />)}</div>;
  }, [active, classified, unchangedItems]);
  return (
    <div className="comp-evo-panel">
      <p className="comp-evo-panel__heading">从<span className="comp-evo-panel__date">{fromDate}</span>到<span className="comp-evo-panel__date">{toDate}</span>，该岗位共有 <strong>{total}</strong> 项能力要求发生变化。</p>
      <div className="comp-evo-panel__cards">
        {CARD_DEFS.map(def => (
          <button key={def.key} type="button" className={`comp-evo-card comp-evo-card--${def.cssMod}${active === def.key ? " comp-evo-card--active" : ""}`}
            onClick={() => setActive(def.key)} aria-pressed={active === def.key} aria-label={`${def.label}：${counts[def.key]}项`}>
            <span className="comp-evo-card__count">{counts[def.key]}</span><span className="comp-evo-card__label">{def.label}</span>
          </button>
        ))}
      </div>
      <div className="comp-evo-panel__detail"><div className="comp-evo-panel__detail-head">当前查看：{activeLabel}（{activeCount}项）</div>{detailContent}</div>
    </div>
  );
}

// ── RoleSnapshotView (single-version) ──────────────────────────

function SnapshotSkillItem({ skill }: { skill: ValidatedDiffSkillItem }) {
  const levelZh = translateSkillLevel(skill.level);
  const desc = snapshotSkillDescription(skill.level);
  return (
    <div className="comp-evo-detail-item">
      <div className="comp-evo-detail-item__head">
        <span className="comp-evo-detail-item__name">{skill.name}</span>
        <span className={`comp-evolution__tag comp-evolution__tag--${SNAPSHOT_LEVEL_CSS[skill.level?.toLowerCase() || ""] || "adjusted"}`}>{levelZh}</span>
      </div>
      {desc && <p className="comp-evo-detail-item__reason">{desc}</p>}
      <div className="comp-evo-detail-item__source"><SourcePlatforms ids={skill.source_ids} /></div>
    </div>
  );
}

function ResponsibilitiesSection({ items }: { items: string[] }) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? items : items.slice(0, 4);
  if (items.length === 0) return null;
  return (
    <div className="comp-evo-responsibilities">
      <h3 className="comp-evo-responsibilities__title"><ListChecks style={{ width: 16 }} />该岗位主要负责</h3>
      <ul className="comp-evo-responsibilities__list">{visible.map((r, i) => <li key={i}>{r}</li>)}</ul>
      {items.length > 4 && (
        <button type="button" className="comp-evo-responsibilities__toggle" onClick={() => setExpanded(o => !o)}>
          {expanded ? "收起" : `展开全部（共${items.length}条）`}
        </button>
      )}
    </div>
  );
}

function RoleSnapshotView({ version, roleName }: { version: ValidatedRoleVersionItem; roleName: string }) {
  const skills: ValidatedDiffSkillItem[] = useMemo(() =>
    (version.skills || []).map(s => ({ name: s.name, level: s.level, source_ids: s.source_ids || [], reason: null })),
  [version]);

  const levelCounts = useMemo(() => {
    const c: Record<string, number> = { expert: 0, advanced: 0, intermediate: 0, beginner: 0, unlabeled: 0 };
    for (const s of skills) {
      const l = (s.level || "").toLowerCase();
      if (l && c[l] !== undefined) c[l]++;
      else c.unlabeled++;
    }
    return c;
  }, [skills]);

  const totalSkills = skills.length;
  const date = formatVersionDate(version.timestamp);

  // Snapshot summary cards
  const summaryDefs = [
    { key: "all", label: "全部能力", count: totalSkills, cssMod: "new" },
    { key: "expert", label: "专家级", count: levelCounts.expert, cssMod: "expert" },
    { key: "advanced", label: "高级", count: levelCounts.advanced, cssMod: "upgraded" },
    { key: "intermediate", label: "熟练", count: levelCounts.intermediate, cssMod: "downgraded" },
    { key: "beginner", label: "入门", count: levelCounts.beginner, cssMod: "new" },
  ];

  const defaultFilter: SnapshotFilter = useMemo(() => {
    for (const def of summaryDefs) { if (def.key === "all") continue; if (def.count > 0) return def.key; }
    return "all";
  }, [levelCounts]);
  const [filter, setFilter] = useState<SnapshotFilter>(defaultFilter);
  useEffect(() => { setFilter(defaultFilter); }, [defaultFilter]);

  const filteredSkills = useMemo(() => {
    if (filter === "all") return skills;
    return skills.filter(s => (s.level || "").toLowerCase() === filter);
  }, [skills, filter]);

  const filterLabel = summaryDefs.find(d => d.key === filter)!.label;

  return (
    <div className="comp-evo-panel">
      {/* Context header */}
      <p className="comp-evo-panel__heading">
        <span className="comp-evo-panel__date">{roleName}</span> · 当前能力画像
      </p>
      <div className="comp-evo-snapshot-info">
        <Info style={{ width: 14, flex: "none" }} />
        <span>当前只有一份岗位记录，暂时无法查看时间变化。后续新增岗位数据后，系统将自动生成能力变化分析。</span>
      </div>

      {/* Skill level summary cards */}
      <div className="comp-evo-panel__cards">
        {summaryDefs.map(def => (
          <button key={def.key} type="button"
            className={`comp-evo-card comp-evo-card--${def.cssMod}${filter === def.key ? " comp-evo-card--active" : ""}`}
            onClick={() => setFilter(def.key)} aria-pressed={filter === def.key}
            aria-label={`${def.label}：${def.count}项`}>
            <span className="comp-evo-card__count">{def.count}</span>
            <span className="comp-evo-card__label">{def.label}</span>
          </button>
        ))}
      </div>

      {/* Filtered skill list */}
      <div className="comp-evo-panel__detail">
        <div className="comp-evo-panel__detail-head">当前查看：{filterLabel}（{filteredSkills.length}项）</div>
        {filteredSkills.length === 0 ? (
          <div className="comp-evo-detail-empty">当前没有此类能力。</div>
        ) : (
          <div className="comp-evo-detail-list">
            {filteredSkills.map(s => <SnapshotSkillItem key={s.name} skill={s} />)}
          </div>
        )}
      </div>

      {/* Responsibilities */}
      <ResponsibilitiesSection items={version.responsibilities || []} />

      {/* Source info */}
      <div className="comp-evo-snapshot-meta">
        <Clock3 style={{ width: 13 }} />记录时间：{date}
        {version.source && ` · 数据来源：${version.source}`}
      </div>
    </div>
  );
}

// ── EmptyRoleView ────────────────────────────────────────────────

function EmptyRoleView({ roleName, onRefresh, onSwitchRole }: { roleName: string; onRefresh: () => void; onSwitchRole?: () => void }) {
  return (
    <div className="comp-evo-panel" style={{ textAlign: "center", padding: "48px 24px" }}>
      <Info style={{ width: 36, height: 36, color: "#9ca3af", marginBottom: 14 }} />
      <h3 style={{ margin: "0 0 8px", color: "#1a1a2e", fontSize: 18, fontWeight: 700 }}>暂无岗位能力数据</h3>
      <p style={{ margin: "0 auto 20px", color: "#777", fontSize: 13, lineHeight: 1.7, maxWidth: 420 }}>
        {roleName}目前还没有可用于分析的能力记录。数据收录后将在这里展示岗位能力画像和变化趋势。
      </p>
      <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
        <button className="comp-evo-filter-card__refresh" onClick={onRefresh} type="button" style={{ marginTop: 0 }}>
          <RefreshCw style={{ width: 13 }} />刷新数据
        </button>
      </div>
    </div>
  );
}

// ─── Main Component ─────────────────────────────────────────────

type Props = {
  embedded?: boolean;
  roleId?: string;
  onRoleChange?: (id: string) => void;
};

export default function CompetitionRoleEvolution({
  embedded = false,
  roleId: externalRoleId,
  onRoleChange: externalOnRoleChange,
}: Props = {}) {
  const [internalRoleId, setInternalRoleId] = useState("java-developer");
  const roleId = externalRoleId ?? internalRoleId;
  const setRoleId = externalOnRoleChange ?? setInternalRoleId;
  const currentRoleIdRef = useRef(roleId);
  useEffect(() => { currentRoleIdRef.current = roleId; }, [roleId]);

  const [versionsData, setVersionsData] = useState<ValidatedRoleVersionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const versionsAbortRef = useRef<AbortController | null>(null);

  const [fromIdx, setFromIdx] = useState<number | null>(null);
  const [toIdx, setToIdx] = useState<number | null>(null);

  const [diff, setDiff] = useState<ValidatedRoleDiffResponse | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [diffError, setDiffError] = useState("");
  const [selectionError, setSelectionError] = useState("");
  const diffAbortRef = useRef<AbortController | null>(null);

  // ── Names ──
  const selectedRoleName = useMemo(() => AVAILABLE_ROLES.find(r => r.id === roleId)?.name || roleId, [roleId]);
  const loadedRoleName = useMemo(() => {
    if (versionsData && versionsData.role_id === roleId) return versionsData.name;
    return selectedRoleName;
  }, [versionsData, roleId, selectedRoleName]);

  // ── handleRoleChange ──
  const handleRoleChange = useCallback((newRoleId: string) => {
    if (newRoleId === currentRoleIdRef.current) return;
    diffAbortRef.current?.abort(); versionsAbortRef.current?.abort();
    setRoleId(newRoleId); setVersionsData(null); setFromIdx(null); setToIdx(null);
    setDiff(null); setError(""); setDiffError(""); setSelectionError(""); setDiffLoading(false); setLoading(true);
  }, []);

  // ── handleRefresh ──
  const handleRefresh = useCallback(() => {
    versionsAbortRef.current?.abort(); diffAbortRef.current?.abort();
    setLoading(true); setError(""); setDiff(null); setDiffError(""); setFromIdx(null); setToIdx(null); setSelectionError("");
  }, []);

  // ── Load versions ──
  useEffect(() => {
    versionsAbortRef.current?.abort();
    const ac = new AbortController(); versionsAbortRef.current = ac; const { signal } = ac;
    const requestedRoleId = currentRoleIdRef.current;
    setLoading(true); setError(""); setDiff(null); setDiffError(""); setFromIdx(null); setToIdx(null); setSelectionError("");
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/roles/${encodeURIComponent(requestedRoleId)}/versions`, { signal });
        if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(body.detail || `服务返回 HTTP ${res.status}`); }
        const validated = await validateRoleVersionsResponse(res);
        if (signal.aborted) return;
        if (currentRoleIdRef.current !== requestedRoleId) return;
        if (validated.role_id !== requestedRoleId) {
          console.error(`[Evolution] versions role_id mismatch: got "${validated.role_id}", expected "${requestedRoleId}"`);
          setError(`岗位 "${selectedRoleName}" 的历史数据加载异常，请稍后重试。`);
          setVersionsData(null); setLoading(false); return;
        }
        setVersionsData(validated); setLoading(false); setError("");
      } catch (e: unknown) {
        if (signal.aborted) return;
        if (currentRoleIdRef.current !== requestedRoleId) return;
        console.error("[Evolution] loadVersions error:", e);
        setError(e instanceof Error ? e.message : "无法加载岗位版本数据");
        setVersionsData(null); setLoading(false);
      }
    })();
    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roleId]);

  // ── Sorted versions ──
  const sortedVersions = useMemo(() => {
    if (!versionsData?.versions) return [];
    return [...versionsData.versions].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  }, [versionsData]);

  // ── Auto-select ──
  useEffect(() => {
    if (sortedVersions.length >= 2) { setFromIdx(sortedVersions.length - 2); setToIdx(sortedVersions.length - 1); }
    else if (sortedVersions.length === 1) { setFromIdx(null); setToIdx(0); }
    else { setFromIdx(null); setToIdx(null); }
  }, [sortedVersions]);
  const fromVersion = fromIdx != null ? sortedVersions[fromIdx] : null;
  const toVersion = toIdx != null ? sortedVersions[toIdx] : null;

  // ── View mode (derived from sortedVersions) ──
  const viewMode: EvolutionViewMode = loading
    ? "loading"
    : error
      ? "error"
      : sortedVersions.length === 0
        ? "empty"
        : sortedVersions.length === 1
          ? "snapshot"
          : "comparison";

  // ── Auto-run diff (only when 2+ versions) ──
  useEffect(() => {
    if (sortedVersions.length < 2) { setDiff(null); return; }
    if (loading) return;
    if (!versionsData || versionsData.role_id !== currentRoleIdRef.current) return;
    if (!fromVersion || !toVersion) { setDiff(null); return; }
    const requestedRoleId = currentRoleIdRef.current;
    if (fromVersion.version_id === toVersion.version_id) { setSelectionError("开始时间需要早于结束时间。"); setDiff(null); return; }
    diffAbortRef.current?.abort();
    const ac = new AbortController(); diffAbortRef.current = ac; const { signal } = ac;
    setSelectionError(""); setDiffLoading(true); setDiffError("");
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/roles/${encodeURIComponent(requestedRoleId)}/diff?from_version=${encodeURIComponent(fromVersion.version_id)}&to_version=${encodeURIComponent(toVersion.version_id)}`, { signal });
        if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(body.detail || `服务返回 HTTP ${res.status}`); }
        const v = await validateRoleDiffResponse(res);
        if (signal.aborted) return;
        if (currentRoleIdRef.current !== requestedRoleId) return;
        if (v.role_id !== requestedRoleId) { setDiffError(`岗位 "${selectedRoleName}" 的变化数据加载异常，请稍后重试。`); setDiff(null); setDiffLoading(false); return; }
        setDiff(v); setDiffLoading(false);
      } catch (e: unknown) {
        if (signal.aborted) return;
        if (currentRoleIdRef.current !== requestedRoleId) return;
        console.error("[Evolution] diff error:", e);
        setDiffError(e instanceof Error ? e.message : "数据加载失败"); setDiff(null); setDiffLoading(false);
      }
    })();
    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roleId, loading, versionsData?.role_id, sortedVersions.length, fromVersion?.version_id, toVersion?.version_id]);

  // ── Cleanup ──
  useEffect(() => { return () => { versionsAbortRef.current?.abort(); diffAbortRef.current?.abort(); }; }, []);

  // ── Comparison derivations ──
  const classifiedChanges = useMemo((): ClassifiedChange[] => {
    if (!diff || !fromVersion || !toVersion || diff.role_id !== currentRoleIdRef.current) return [];
    const r: ClassifiedChange[] = [];
    for (const item of diff.added) r.push({ item, category: "new", oldLevel: null, newLevel: item.level });
    for (const item of diff.removed) r.push({ item, category: "removed", oldLevel: item.level, newLevel: null });
    for (const item of diff.modified) { const { category, oldLevel } = classifyModifiedSkill(item.name, fromVersion.skills || [], toVersion.skills || [], item.level); r.push({ item, category, oldLevel, newLevel: item.level }); }
    return r;
  }, [diff, fromVersion, toVersion]);
  const unchangedItems = useMemo((): ValidatedDiffSkillItem[] => {
    if (!diff || !toVersion || diff.role_id !== currentRoleIdRef.current) return [];
    const changed = new Set([...diff.added.map(s => s.name), ...diff.removed.map(s => s.name), ...diff.modified.map(s => s.name)]);
    return (toVersion.skills || []).filter(s => !changed.has(s.name)).map(s => ({ name: s.name, level: s.level, source_ids: s.source_ids || [], reason: null }));
  }, [diff, toVersion]);
  const hasAnyChange = diff && diff.role_id === currentRoleIdRef.current && (diff.added.length + diff.removed.length + diff.modified.length) > 0;

  const compareSuggestions: SuggestionItem[] = useMemo(() => {
    const newS = classifiedChanges.filter(c => c.category === "new").map(c => c.item.name);
    const upgS = classifiedChanges.filter(c => c.category === "upgraded").map(c => c.item.name);
    const remS = classifiedChanges.filter(c => c.category === "removed").map(c => c.item.name);
    const r: SuggestionItem[] = [];
    const f = (a: string[], n: number) => a.slice(0, 3).join("、") + (a.length > 3 ? `等${a.length}项` : "");
    if (newS.length) r.push({ id: "new", icon: SUGGESTION_ICONS.new, text: `建议更新职位描述，补充：${f(newS, newS.length)}。` });
    if (upgS.length) r.push({ id: "upgraded", icon: SUGGESTION_ICONS.upgraded, text: `建议在简历筛选和面试中重点考察：${f(upgS, upgS.length)}。` });
    if (remS.length) r.push({ id: "removed", icon: SUGGESTION_ICONS.removed, text: `以下能力的重要性有所下降，可考虑降低筛选权重：${f(remS, remS.length)}。` });
    return r;
  }, [classifiedChanges]);

  const snapshotSuggestions: SuggestionItem[] = useMemo(() => [
    { id: "snapshot_list", icon: SUGGESTION_ICONS.snapshot, text: "建议在职位描述中清晰列出核心能力及对应要求程度。" },
    { id: "snapshot_verify", icon: SUGGESTION_ICONS.snapshot_verify, text: "建议在简历筛选和面试中重点验证专家级和高级能力。" },
    { id: "snapshot_limited", icon: SUGGESTION_ICONS.snapshot_limited, text: "当前历史数据较少，建议结合实际业务需求确认招聘标准。" },
  ], []);

  // Choose suggestions based on mode
  const effectiveSuggestions = viewMode === "snapshot" ? snapshotSuggestions : compareSuggestions;
  const effectiveTotalSuggestions = effectiveSuggestions.length;
  const adviceDisclaimer = viewMode === "snapshot"
    ? "根据当前岗位能力画像生成，仅供招聘决策参考。"
    : (hasAnyChange ? "根据所选时间范围内的岗位能力变化生成，仅供招聘决策参考。" : "当前时间范围内无变化，暂无建议。");

  // ── Render ──
  return (
    <div className="comp-evolution">
      {/* Header — only show when NOT embedded in workspace */}
      {!embedded && (
        <div className="comp-evolution__header">
          <div className="comp-evolution__header-text">
            <h1 className="comp-evolution__title">岗位能力变化</h1>
            <p className="comp-evolution__subtitle">了解岗位要求在不同时间发生的变化，及时调整招聘标准和职位描述。</p>
          </div>
          <RecruitmentAdvicePopover suggestions={effectiveSuggestions} disclaimer={adviceDisclaimer} totalSuggestions={effectiveTotalSuggestions} />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="comp-error-banner"><AlertTriangle /><div><b>数据加载失败</b><span>{error}</span></div><button className="ghost-action" onClick={handleRefresh} aria-label="重新加载">重试</button></div>
      )}

      {/* Filter card — always rendered */}
      <EvolutionFilterCard roleId={roleId} onRoleChange={handleRoleChange}
        sortedVersions={sortedVersions} fromIdx={fromIdx} toIdx={toIdx}
        onFromChange={(idx) => { setFromIdx(idx); setSelectionError(""); }}
        onToChange={(idx) => { setToIdx(idx); setSelectionError(""); }}
        loading={loading} onRefresh={handleRefresh} diffLoading={diffLoading} viewMode={viewMode} />

      {/* ─── Mode: Loading ─── */}
      {viewMode === "loading" && (
        <div className="comp-evolution__skeleton">
          <div className="comp-evolution__skeleton-cards"><div className="comp-evolution__skeleton-card" /><div className="comp-evolution__skeleton-card" /><div className="comp-evolution__skeleton-card" /></div>
          <div className="comp-evolution__skeleton-list"><div className="comp-evolution__skeleton-item" /><div className="comp-evolution__skeleton-item" /></div>
          <p className="comp-evolution__skeleton-text">正在分析{selectedRoleName}的能力要求……</p>
        </div>
      )}

      {/* ─── Mode: Empty ─── */}
      {viewMode === "empty" && <EmptyRoleView roleName={selectedRoleName} onRefresh={handleRefresh} />}

      {/* ─── Mode: Snapshot ─── */}
      {viewMode === "snapshot" && toVersion && (
        <RoleSnapshotView version={toVersion} roleName={loadedRoleName} />
      )}

      {/* ─── Mode: Comparison ─── */}
      {viewMode === "comparison" && (
        <>
          {selectionError && <span className="comp-evolution__select-error">{selectionError}</span>}
          {diffError && <div className="comp-error-banner"><AlertTriangle /><div><b>数据加载失败</b><span>{diffError}</span></div><button className="ghost-action" onClick={handleRefresh} aria-label="重新加载">重新加载</button></div>}
          {diffLoading && (
            <div className="comp-evolution__skeleton">
              <div className="comp-evolution__skeleton-cards"><div className="comp-evolution__skeleton-card" /><div className="comp-evolution__skeleton-card" /><div className="comp-evolution__skeleton-card" /></div>
              <p className="comp-evolution__skeleton-text">正在分析{selectedRoleName}的能力变化……</p>
            </div>
          )}
          {!diffLoading && !diff && !diffError && (
            <div className="comp-evolution__skeleton">
              <div className="comp-evolution__skeleton-cards"><div className="comp-evolution__skeleton-card" /><div className="comp-evolution__skeleton-card" /><div className="comp-evolution__skeleton-card" /></div>
              <p className="comp-evolution__skeleton-text">正在分析{selectedRoleName}的能力变化……</p>
            </div>
          )}
          {!diffLoading && diff && diff.role_id === currentRoleIdRef.current && (
            hasAnyChange ? (
              <EvolutionSummaryPanel classified={classifiedChanges} unchangedItems={unchangedItems}
                fromDate={fromVersion ? formatVersionDate(fromVersion.timestamp) : ""}
                toDate={toVersion ? formatVersionDate(toVersion.timestamp) : ""} />
            ) : (
              <div className="comp-empty" style={{ minHeight: 100, border: "none" }}>
                <Check style={{ width: 32, height: 32, color: "#4ade80" }} />
                <h3>岗位要求整体稳定</h3>
                <p>所选时间范围内没有发现明显的能力要求变化。</p>
              </div>
            )
          )}
        </>
      )}
    </div>
  );
}
