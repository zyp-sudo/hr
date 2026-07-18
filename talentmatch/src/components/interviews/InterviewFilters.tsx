import { useCallback, useEffect, useRef, useState } from "react";
import type { InterviewFilters, InterviewViewMode, InterviewStatus } from "../../types/interview";
import { Search, X, Filter, Star, Pin, Clock3 } from "lucide-react";

interface Props {
  filters: InterviewFilters;
  onChange: (patch: Partial<InterviewFilters>) => void;
  tags: Array<{ id: string; name: string; color: string }>;
  rounds: string[];
  availableStatuses: InterviewStatus[];
}

export default function InterviewFilters({ filters, onChange, tags, rounds, availableStatuses }: Props) {
  const [expanded, setExpanded] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  const hasActiveFilters = filters.search || filters.status || filters.round || filters.priority || filters.tagId || filters.dateFrom || filters.dateTo || filters.isPinned || filters.onlyFavorites;

  const clearAll = () => onChange({ search: "", status: "", round: "", priority: "", tagId: "", dateFrom: "", dateTo: "", isPinned: false, onlyFavorites: false });

  return (
    <div className="iv-filters">
      {/* ── Search bar (always visible) ── */}
      <div className="iv-filters__search">
        <Search />
        <input
          ref={searchRef}
          value={filters.search}
          onChange={(e) => onChange({ search: e.target.value })}
          placeholder="搜索候选人、岗位、面试官..."
        />
        {filters.search && (
          <button onClick={() => onChange({ search: "" })} className="iv-filters__clear-btn" aria-label="清空搜索">
            <X />
          </button>
        )}
      </div>

      {/* ── Quick toggles ── */}
      <div className="iv-filters__toggles">
        <button className={`iv-filters__toggle ${filters.isPinned ? "active" : ""}`} onClick={() => onChange({ isPinned: !filters.isPinned })} title="仅看置顶面试">
          <Pin /> 置顶
        </button>
        <button className={`iv-filters__toggle ${filters.onlyFavorites ? "active" : ""}`} onClick={() => onChange({ onlyFavorites: !filters.onlyFavorites })} title="仅看关注候选人">
          <Star /> 关注
        </button>
        <button className={`iv-filters__toggle ${expanded ? "active" : ""}`} onClick={() => setExpanded(!expanded)} title="展开筛选">
          <Filter /> 筛选 {hasActiveFilters && <i className="iv-filters__dot" />}
        </button>
        {hasActiveFilters && (
          <button className="iv-filters__toggle iv-filters__toggle--clear" onClick={clearAll}>
            清空
          </button>
        )}
      </div>

      {/* ── Expanded filters ── */}
      {expanded && (
        <div className="iv-filters__expanded">
          <div className="iv-filters__row">
            {/* Status */}
            <label>
              <span>状态</span>
              <select value={filters.status} onChange={(e) => onChange({ status: e.target.value as InterviewStatus | "" })}>
                <option value="">全部</option>
                {availableStatuses.map((s) => (
                  <option key={s} value={s}>{statusLabel(s)}</option>
                ))}
              </select>
            </label>

            {/* Round */}
            <label>
              <span>面试轮次</span>
              <select value={filters.round} onChange={(e) => onChange({ round: e.target.value })}>
                <option value="">全部</option>
                {rounds.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </label>

            {/* Priority */}
            <label>
              <span>优先级</span>
              <select value={filters.priority} onChange={(e) => onChange({ priority: e.target.value })}>
                <option value="">全部</option>
                <option value="普通">普通</option>
                <option value="重要">重要</option>
                <option value="紧急">紧急</option>
              </select>
            </label>

            {/* Tag */}
            <label>
              <span>标签</span>
              <select value={filters.tagId} onChange={(e) => onChange({ tagId: e.target.value })}>
                <option value="">全部</option>
                {tags.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="iv-filters__row">
            {/* Date range */}
            <label>
              <span>开始日期</span>
              <input type="date" value={filters.dateFrom} onChange={(e) => onChange({ dateFrom: e.target.value })} />
            </label>
            <label>
              <span>结束日期</span>
              <input type="date" value={filters.dateTo} onChange={(e) => onChange({ dateTo: e.target.value })} />
            </label>
            <label>
              <span>视图</span>
              <select value={filters.view} onChange={(e) => onChange({ view: e.target.value as InterviewViewMode })}>
                <option value="calendar">日历视图</option>
                <option value="list">列表视图</option>
                <option value="kanban">看板视图</option>
              </select>
            </label>
          </div>
        </div>
      )}
    </div>
  );
}

function statusLabel(s: InterviewStatus): string {
  const map: Record<InterviewStatus, string> = { pending: "待安排", scheduled: "已安排", in_progress: "进行中", completed: "已完成", cancelled: "已取消" };
  return map[s] || s;
}
