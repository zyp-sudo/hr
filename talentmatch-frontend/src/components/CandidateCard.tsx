import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  GripHorizontal,
  Loader2,
  Menu,
  Sparkles,
  Trash2,
  UserRound,
} from "lucide-react";
import type { AssessmentViewModel } from "../types";

/* ================================================================
   CardData — per-candidate card state
   ================================================================ */
export interface CardData {
  id: string;
  name: string;
  skills: string;
  years: string;
  education: string;
  experience: string;
  resumeText: string;
  x: number; // px from left of workspace
  y: number; // px from top of workspace
  result: AssessmentViewModel | null;
  evaluating: boolean;
}

/* ================================================================
   CandidateCard props
   ================================================================ */
interface CandidateCardProps {
  card: CardData;
  onUpdate: (id: string, patch: Partial<CardData>) => void;
  onDelete: (id: string) => void;
  onEvaluate: (id: string) => void;
  onSelect: (id: string) => void;
  isSelected: boolean;
}

/* ================================================================
   CandidateCard — self-contained draggable candidate input card
   ================================================================ */
export default function CandidateCard({
  card,
  onUpdate,
  onDelete,
  onEvaluate,
  onSelect,
  isSelected,
}: CandidateCardProps) {
  const [expanded, setExpanded] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef({
    active: false,
    offsetX: 0,
    offsetY: 0,
    cardX: 0,
    cardY: 0,
  });
  const [deleting, setDeleting] = useState(false);

  /* ── Generate resume text from quick-fill fields ── */
  const generateResume = useCallback(() => {
    const text = [
      `姓名：${card.name || "未填写"}`,
      `核心技能：${card.skills || "未填写"}`,
      `相关经验：${card.years || "未填写"}年`,
      `学历：${card.education}`,
      `项目/工作经历：${card.experience || "未填写"}`,
    ].join("\n");
    onUpdate(card.id, { resumeText: text });
  }, [card, onUpdate]);

  /* ── Drag: pointerdown on header ── */
  const onHeaderPointerDown = useCallback(
    (e: ReactPointerEvent) => {
      if (!cardRef.current) return;
      e.preventDefault();
      dragRef.current = {
        active: true,
        offsetX: e.clientX - card.x,
        offsetY: e.clientY - card.y,
        cardX: card.x,
        cardY: card.y,
      };
      cardRef.current.setPointerCapture(e.pointerId);
    },
    [card.x, card.y],
  );

  /* ── Drag: pointermove (fires on the card due to capture) ── */
  const onPointerMove = useCallback((e: ReactPointerEvent) => {
    if (!dragRef.current.active) return;
    const el = cardRef.current;
    if (!el) return;
    const newX = e.clientX - dragRef.current.offsetX;
    const newY = e.clientY - dragRef.current.offsetY;
    el.style.left = `${newX}px`;
    el.style.top = `${newY}px`;
  }, []);

  /* ── Drag: pointerup — commit position to parent ── */
  const onPointerUp = useCallback(
    (e: ReactPointerEvent) => {
      if (!dragRef.current.active) return;
      dragRef.current.active = false;
      const el = cardRef.current;
      if (!el) return;
      el.releasePointerCapture(e.pointerId);
      // Read final DOM position back
      const left = parseFloat(el.style.left);
      const top = parseFloat(el.style.top);
      if (!isNaN(left) && !isNaN(top)) {
        // Only emit if position actually changed (avoid noise)
        if (Math.abs(left - card.x) > 1 || Math.abs(top - card.y) > 1) {
          onUpdate(card.id, { x: left, y: top });
        }
      }
    },
    [card, onUpdate],
  );

  /* ── Document-level pointerup safety net ── */
  useEffect(() => {
    const up = () => {
      if (!dragRef.current.active) return;
      dragRef.current.active = false;
      const el = cardRef.current;
      if (!el) return;
      const left = parseFloat(el.style.left);
      const top = parseFloat(el.style.top);
      if (!isNaN(left) && !isNaN(top)) {
        onUpdate(card.id, { x: left, y: top });
      }
    };
    document.addEventListener("pointerup", up);
    return () => document.removeEventListener("pointerup", up);
  }, [card.id, onUpdate]);

  /* ── Keyboard accessibility ── */
  const handleKeyDown = useCallback(
    (e: ReactKeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        setExpanded((v) => !v);
      }
    },
    [],
  );

  /* ── Has the user filled anything in? ── */
  const hasContent =
    card.name || card.skills || card.years || card.experience || card.resumeText;

  /* ── Delete animation ── */
  const handleDelete = useCallback(() => {
    setDeleting(true);
    setTimeout(() => onDelete(card.id), 240);
  }, [card.id, onDelete]);

  return (
    <AnimatePresence>
      {!deleting && (
        <motion.div
          ref={cardRef}
          className={`candidate-card ${expanded ? "candidate-card--expanded" : ""} ${isSelected ? "candidate-card--selected" : ""} ${card.evaluating ? "candidate-card--evaluating" : ""}`}
          style={{ left: `${card.x}px`, top: `${card.y}px` }}
          role="region"
          aria-label={`候选人卡片：${card.name || "未命名"}`}
          initial={{ opacity: 0, scale: 0.88, y: 12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.85, y: 10 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
        >
          {/* ── Header bar (drag handle) ── */}
          <div
            className="candidate-card__header"
            onPointerDown={onHeaderPointerDown}
          >
            <button
              className="candidate-card__grip"
              aria-label="拖拽移动卡片"
              tabIndex={-1}
            >
              <GripHorizontal />
            </button>

            <div className="candidate-card__name">
              {card.evaluating ? (
                <Loader2 className="spin" />
              ) : (
                <UserRound />
              )}
              <input
                className="candidate-card__name-input"
                value={card.name}
                onChange={(e) => onUpdate(card.id, { name: e.target.value })}
                placeholder="候选人姓名"
                aria-label="候选人姓名"
                onClick={(e) => e.stopPropagation()}
                onPointerDown={(e) => e.stopPropagation()}
              />
            </div>

            {/* ── Score badge (when evaluated) ── */}
            {card.result && (
              <span
                className={`candidate-card__badge ${card.result.score >= 80 ? "candidate-card__badge--high" : card.result.score >= 60 ? "candidate-card__badge--mid" : "candidate-card__badge--low"}`}
              >
                {card.result.score}分
              </span>
            )}

            <button
              className="candidate-card__toggle"
              onClick={(e) => {
                e.stopPropagation();
                onSelect(card.id);
                setExpanded((v) => !v);
              }}
              onPointerDown={(e) => e.stopPropagation()}
              aria-label={expanded ? "折叠卡片" : "展开候选人分析"}
              title={expanded ? "折叠" : "展开候选人分析"}
              tabIndex={0}
              onKeyDown={handleKeyDown}
            >
              <Menu />
            </button>
          </div>

          {/* ── Body (collapsible) ── */}
          <AnimatePresence initial={false}>
            {expanded && (
              <motion.div
                className="candidate-card__body"
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              >
                <div className="candidate-card__fields">
                  <label className="candidate-card__field">
                    <span>核心技能</span>
                    <input
                      value={card.skills}
                      onChange={(e) =>
                        onUpdate(card.id, { skills: e.target.value })
                      }
                      placeholder="Java, Python, 产品设计…"
                      onPointerDown={(e) => e.stopPropagation()}
                    />
                  </label>
                  <div className="candidate-card__row">
                    <label className="candidate-card__field">
                      <span>工作年限</span>
                      <input
                        value={card.years}
                        onChange={(e) =>
                          onUpdate(card.id, { years: e.target.value })
                        }
                        placeholder="如 3"
                        onPointerDown={(e) => e.stopPropagation()}
                      />
                    </label>
                    <label className="candidate-card__field">
                      <span>学历</span>
                      <select
                        value={card.education}
                        onChange={(e) =>
                          onUpdate(card.id, { education: e.target.value })
                        }
                        onPointerDown={(e) => e.stopPropagation()}
                      >
                        <option>本科</option>
                        <option>硕士</option>
                        <option>博士</option>
                        <option>专科</option>
                        <option>高中及以下</option>
                      </select>
                    </label>
                  </div>
                  <label className="candidate-card__field">
                    <span>项目/工作经历</span>
                    <textarea
                      value={card.experience}
                      onChange={(e) =>
                        onUpdate(card.id, { experience: e.target.value })
                      }
                      placeholder="简述项目背景、职责、成果…"
                      rows={3}
                      onPointerDown={(e) => e.stopPropagation()}
                    />
                  </label>
                  <label className="candidate-card__field">
                    <span>完整简历文本</span>
                    <textarea
                      value={card.resumeText}
                      onChange={(e) =>
                        onUpdate(card.id, { resumeText: e.target.value })
                      }
                      placeholder="粘贴完整简历，或点击上方「生成评估内容」从快捷字段生成…"
                      rows={5}
                      onPointerDown={(e) => e.stopPropagation()}
                    />
                  </label>
                </div>

                <div className="candidate-card__actions">
                  <button
                    className="candidate-card__generate"
                    onClick={(e) => {
                      e.stopPropagation();
                      generateResume();
                    }}
                  >
                    <Sparkles />
                    生成评估内容
                  </button>
                  <button
                    className="candidate-card__delete"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete();
                    }}
                  >
                    <Trash2 />
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Footer: evaluate button ── */}
          <div className="candidate-card__footer">
            {/* quick summary when collapsed */}
            {!expanded && hasContent && (
              <span className="candidate-card__summary">
                {card.skills && `${card.skills}`}
                {card.years && ` · ${card.years}年`}
                {card.education && card.education !== "本科" && ` · ${card.education}`}
              </span>
            )}
            <button
              className="candidate-card__evaluate"
              onClick={(e) => {
                e.stopPropagation();
                onEvaluate(card.id);
              }}
              disabled={card.evaluating || card.resumeText.length < 30}
            >
              {card.evaluating ? (
                <>
                  <Loader2 className="spin" /> 评估中…
                </>
              ) : (
                <>
                  <Sparkles /> 智能评估
                </>
              )}
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
