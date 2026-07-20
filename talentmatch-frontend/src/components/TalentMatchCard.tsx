import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { motion, AnimatePresence } from "motion/react";

/* ================================================================
   ScoreDisplay — 核心数据 + 百分号（%）的特殊视觉放大特效
   ================================================================ */
export function ScoreDisplay({
  value,
  suffix = "%",
  label,
  size = "lg",
}: {
  value: number | string;
  suffix?: string;
  label?: string;
  size?: "lg" | "md";
}) {
  const numStr = typeof value === "number" ? value.toFixed(1) : value;
  const fontSize = size === "lg" ? 30 : 24;

  return (
    <div className="flex flex-col items-start gap-1">
      {label && (
        <span
          className="block font-normal tracking-wide select-none"
          style={{
            fontSize: 12,
            color: "rgba(255,255,255,0.50)",
            fontFamily: `"SF Pro Display", "PingFang SC", "Noto Sans SC", sans-serif`,
            WebkitFontSmoothing: "antialiased",
            MozOsxFontSmoothing: "grayscale",
          }}
        >
          {label}
        </span>
      )}
      <div
        className="flex items-baseline select-none"
        style={{
          fontFamily: `"SF Pro Rounded", "JetBrains Mono", monospace`,
          fontVariantNumeric: "tabular-nums",
          WebkitFontSmoothing: "antialiased",
          MozOsxFontSmoothing: "grayscale",
        }}
      >
        {/* 主数字 */}
        <span
          style={{
            fontSize,
            fontWeight: 800,
            lineHeight: 1,
            color: "rgba(255,255,255,0.95)",
            letterSpacing: "-0.02em",
          }}
        >
          {numStr}
        </span>
        {/* 百分号（%）特效微调 */}
        <span
          style={{
            fontSize: fontSize * 0.55,
            fontWeight: 300,
            lineHeight: 1,
            color: "rgba(6,182,212,0.80)",
            transform: "translateY(-42%)",
            marginLeft: 1,
            WebkitFontSmoothing: "antialiased",
            MozOsxFontSmoothing: "grayscale",
          }}
        >
          {suffix}
        </span>
      </div>
    </div>
  );
}

/* ================================================================
   StardustCanvas — 鼠标排斥星尘液态物理粒子系统
   ================================================================ */

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  ox: number; // 原始位置（弹簧锚点）
  oy: number;
  radius: number;
  alpha: number;
  hue: number;
}

function useStardustCanvas(
  canvasRef: RefObject<HTMLCanvasElement | null>,
  containerRef: RefObject<HTMLDivElement | null>,
  active: boolean,
) {
  const particlesRef = useRef<Particle[]>([]);
  const mouseRef = useRef({ x: -9999, y: -9999, inside: false });
  const rafRef = useRef<number>(0);
  const dimsRef = useRef({ w: 0, h: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // ── Resize ──
    const resize = () => {
      const rect = container.getBoundingClientRect();
      const w = rect.width;
      const h = rect.height;
      dimsRef.current = { w, h };
      canvas.width = w * devicePixelRatio;
      canvas.height = h * devicePixelRatio;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
    };

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(container);

    // ── Init particles ──
    const { w, h } = dimsRef.current;
    const count = Math.min(75, Math.floor((w * h) / 3800));
    particlesRef.current = Array.from({ length: count }, () => {
      const x = Math.random() * w;
      const y = Math.random() * h;
      return {
        x,
        y,
        vx: 0,
        vy: 0,
        ox: x,
        oy: y,
        radius: 1.0 + Math.random() * 2.2,
        alpha: 0.25 + Math.random() * 0.55,
        hue: 210 + Math.random() * 60, // cyan-purple range
      };
    });

    // ── Mouse ──
    const onMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      mouseRef.current = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
        inside: true,
      };
    };
    const onLeave = () => {
      mouseRef.current = { x: -9999, y: -9999, inside: false };
    };
    container.addEventListener("mousemove", onMove, { passive: true });
    container.addEventListener("mouseleave", onLeave);
    // Also listen on document to catch moves outside the card
    document.addEventListener("mousemove", (e) => {
      const rect = container.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const inside = mx >= -80 && mx <= rect.width + 80 && my >= -80 && my <= rect.height + 80;
      if (inside) {
        mouseRef.current = { x: mx, y: my, inside: true };
      } else if (mouseRef.current.inside) {
        mouseRef.current.inside = false;
      }
    });

    // ── Animation loop ──
    const REPEL_RADIUS = 130;
    const REPEL_FORCE = 1.8;
    const DAMPING = 0.92;
    const SPRING = 0.018;

    const animate = () => {
      const { w, h } = dimsRef.current;
      const mouse = mouseRef.current;
      const particles = particlesRef.current;

      ctx.clearRect(0, 0, w, h);

      for (const p of particles) {
        // Spring force toward origin
        const dxHome = p.ox - p.x;
        const dyHome = p.oy - p.y;
        p.vx += dxHome * SPRING;
        p.vy += dyHome * SPRING;

        // Mouse repulsion
        if (mouse.inside) {
          const dx = p.x - mouse.x;
          const dy = p.y - mouse.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < REPEL_RADIUS && dist > 0.1) {
            const force = ((REPEL_RADIUS - dist) / REPEL_RADIUS) * REPEL_FORCE;
            p.vx += (dx / dist) * force;
            p.vy += (dy / dist) * force;
          }
        }

        // Integrate
        p.vx *= DAMPING;
        p.vy *= DAMPING;
        p.x += p.vx;
        p.y += p.vy;

        // Draw
        const a = active ? p.alpha : p.alpha * 0.3;
        if (a < 0.02) continue;

        // Outer glow
        const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.radius * 2.8);
        gradient.addColorStop(0, `hsla(${p.hue}, 70%, 75%, ${a * 0.9})`);
        gradient.addColorStop(0.4, `hsla(${p.hue}, 60%, 68%, ${a * 0.35})`);
        gradient.addColorStop(1, "transparent");
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius * 2.8, 0, Math.PI * 2);
        ctx.fill();

        // Core dot
        ctx.fillStyle = `hsla(${p.hue}, 55%, 82%, ${a})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fill();
      }

      rafRef.current = requestAnimationFrame(animate);
    };

    rafRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
      container.removeEventListener("mousemove", onMove);
      container.removeEventListener("mouseleave", onLeave);
    };
  }, [active]);

  return mouseRef;
}

/* ================================================================
   TalentMatchCard — 主卡片组件
   ================================================================ */

interface TalentMatchCardProps {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  /** 卡片标题（如候选人姓名） */
  candidateName?: string;
  /** 小标题/二级标题（如 "匹配分析"） */
  subtitle?: string;
  /** 是否可展开 */
  expandable?: boolean;
  /** 展开后的额外内容 */
  expandedContent?: ReactNode;
  /** 默认是否展开 */
  defaultExpanded?: boolean;
  /** 综合匹配分数 */
  overallScore?: number;
  /** 匹配等级文本 */
  matchLevel?: string;
  /** 点击事件 */
  onClick?: () => void;
}

export default function TalentMatchCard({
  children,
  className = "",
  style,
  candidateName,
  subtitle,
  expandable = false,
  expandedContent,
  defaultExpanded = false,
  overallScore,
  matchLevel,
  onClick,
}: TalentMatchCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [sweepActive, setSweepActive] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useStardustCanvas(canvasRef, containerRef, true);

  const handleExpand = useCallback(() => {
    if (!expandable) return;
    setExpanded((prev) => !prev);
    if (!expanded) {
      setSweepActive(true);
      setTimeout(() => setSweepActive(false), 800);
    }
  }, [expandable, expanded]);

  const handleKeyDown = useCallback(
    (e: ReactKeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleExpand();
      }
    },
    [handleExpand],
  );

  return (
    <div
      ref={containerRef}
      className={`talent-match-card ${className}`}
      style={{
        position: "relative",
        borderRadius: 20,
        overflow: "hidden",
        isolation: "isolate",
        cursor: expandable ? "pointer" : "default",
        ...style,
      }}
      onClick={onClick}
      role={expandable ? "button" : undefined}
      tabIndex={expandable ? 0 : undefined}
      aria-expanded={expandable ? expanded : undefined}
      onKeyDown={expandable ? handleKeyDown : undefined}
    >
      {/* ── Layer 0: Canvas 星尘液态物理粒子 ── */}
      <canvas
        ref={canvasRef}
        style={{
          position: "absolute",
          inset: 0,
          zIndex: 0,
          pointerEvents: "none",
          borderRadius: 20,
        }}
      />

      {/* ── Layer 1: 3D 液态玻璃外壳 ── */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          zIndex: 1,
          borderRadius: 20,
          background: `
            linear-gradient(160deg,
              rgba(30, 28, 48, 0.72) 0%,
              rgba(20, 18, 36, 0.80) 40%,
              rgba(14, 12, 28, 0.88) 100%
            )
          `,
          backdropFilter: "blur(30px) saturate(180%)",
          WebkitBackdropFilter: "blur(30px) saturate(180%)",
          border: "1px solid rgba(255,255,255,0.08)",
          boxShadow: `
            inset 0 1px 0 rgba(255,255,255,0.06),
            0 20px 60px rgba(0,0,0,0.35),
            0 0 80px rgba(91,66,243,0.04)
          `,
        }}
      />

      {/* ── Layer 2: 边缘缓慢游走的紫青渐变流光 ── */}
      <div
        style={{
          position: "absolute",
          inset: -2,
          zIndex: 0,
          borderRadius: 22,
          padding: 2,
          background: `
            conic-gradient(
              from 0deg,
              rgba(124,92,255,0.5),
              rgba(0,221,235,0.4),
              rgba(124,92,255,0.5),
              rgba(175,64,255,0.4),
              rgba(0,221,235,0.5),
              rgba(124,92,255,0.5)
            )
          `,
          filter: "blur(8px)",
          opacity: 0.55,
          animation: "talentCardBorderRotate 8s linear infinite",
          mask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
          WebkitMask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
          maskComposite: "exclude",
          WebkitMaskComposite: "xor",
        }}
      />

      {/* ── Layer 3: 展开时强流光从上至下扫过边框 ── */}
      <AnimatePresence>
        {sweepActive && (
          <motion.div
            initial={{ top: "-100%" }}
            animate={{ top: "120%" }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.65, ease: [0.16, 1, 0.3, 1] }}
            style={{
              position: "absolute",
              left: -4,
              right: -4,
              height: "60%",
              zIndex: 2,
              pointerEvents: "none",
              borderRadius: 22,
              background: `
                linear-gradient(
                  180deg,
                  transparent 0%,
                  rgba(0,221,235,0.25) 30%,
                  rgba(175,64,255,0.35) 50%,
                  rgba(124,92,255,0.25) 70%,
                  transparent 100%
                )
              `,
              filter: "blur(12px)",
            }}
          />
        )}
      </AnimatePresence>

      {/* ── Layer 4: 内容区域 ── */}
      <div
        style={{
          position: "relative",
          zIndex: 10,
          padding: "28px 30px",
          display: "flex",
          flexDirection: "column",
          gap: 20,
        }}
      >
        {/* ── 卡片头部：候选人姓名 + 综合评分 ── */}
        {(candidateName || overallScore !== undefined) && (
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              gap: 16,
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {candidateName && (
                <h2
                  style={{
                    margin: 0,
                    fontSize: 22,
                    fontWeight: 700,
                    lineHeight: 1.2,
                    color: "rgba(255,255,255,0.95)",
                    fontFamily: `"SF Pro Display", "PingFang SC", "Noto Sans SC", sans-serif`,
                    letterSpacing: "-0.01em",
                    WebkitFontSmoothing: "antialiased",
                    MozOsxFontSmoothing: "grayscale",
                  }}
                >
                  {candidateName}
                </h2>
              )}
              {subtitle && (
                <h3
                  style={{
                    margin: 0,
                    fontSize: 15,
                    fontWeight: 600,
                    lineHeight: 1.3,
                    color: "rgba(255,255,255,0.90)",
                    fontFamily: `"SF Pro Display", "PingFang SC", "Noto Sans SC", sans-serif`,
                    letterSpacing: "0.01em",
                    WebkitFontSmoothing: "antialiased",
                    MozOsxFontSmoothing: "grayscale",
                  }}
                >
                  {subtitle}
                </h3>
              )}
            </div>
            {overallScore !== undefined && (
              <ScoreDisplay value={overallScore} label={matchLevel} size="lg" />
            )}
          </div>
        )}

        {/* ── 主要内容（children）以 Fade-in + Slide-up 呈现 ── */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay: 0.08 }}
          style={{ display: "flex", flexDirection: "column", gap: 16 }}
        >
          {children}
        </motion.div>

        {/* ── 展开/收起按钮 ── */}
        {expandable && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleExpand();
            }}
            style={{
              alignSelf: "center",
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.10)",
              borderRadius: 999,
              color: "rgba(255,255,255,0.65)",
              padding: "7px 20px",
              fontSize: 13,
              fontWeight: 500,
              cursor: "pointer",
              fontFamily: `"SF Pro Display", "PingFang SC", "Noto Sans SC", sans-serif`,
              WebkitFontSmoothing: "antialiased",
              MozOsxFontSmoothing: "grayscale",
              transition: "all 0.3s cubic-bezier(0.16,1,0.3,1)",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "rgba(124,92,255,0.12)";
              e.currentTarget.style.borderColor = "rgba(124,92,255,0.35)";
              e.currentTarget.style.color = "rgba(255,255,255,0.90)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "rgba(255,255,255,0.04)";
              e.currentTarget.style.borderColor = "rgba(255,255,255,0.10)";
              e.currentTarget.style.color = "rgba(255,255,255,0.65)";
            }}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{
                transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
                transition: "transform 0.35s cubic-bezier(0.16,1,0.3,1)",
              }}
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
            {expanded ? "收起详情" : "展开详情"}
          </button>
        )}

        {/* ── 展开内容 ── */}
        <AnimatePresence initial={false}>
          {expanded && expandedContent && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
              style={{ overflow: "hidden" }}
            >
              <motion.div
                initial={{ y: 16, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: 12, opacity: 0 }}
                transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1], delay: 0.05 }}
                style={{
                  paddingTop: 8,
                  borderTop: "1px solid rgba(255,255,255,0.06)",
                }}
              >
                {expandedContent}
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── 注入关键帧动画 ── */}
      <style>{`
        @keyframes talentCardBorderRotate {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

/* ================================================================
   MatchMetricBar — 匹配度进度条（带百分号特效）
   ================================================================ */
export function MatchMetricBar({
  label,
  value,
  tone = "purple",
}: {
  label: string;
  value: number;
  tone?: "purple" | "mint" | "cyan";
}) {
  const gradients: Record<string, string> = {
    purple: "linear-gradient(90deg, #947dff, #5b42f3)",
    mint: "linear-gradient(90deg, #00ddeb, #9bf2e9)",
    cyan: "linear-gradient(90deg, #06b6d4, #67e8f9)",
  };

  return (
    <div style={{ marginBottom: 20 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: 10,
        }}
      >
        <span
          style={{
            fontSize: 13,
            fontWeight: 400,
            color: "rgba(255,255,255,0.65)",
            fontFamily: `"SF Pro Display", "PingFang SC", "Noto Sans SC", sans-serif`,
            WebkitFontSmoothing: "antialiased",
            MozOsxFontSmoothing: "grayscale",
          }}
        >
          {label}
        </span>
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            fontFamily: `"SF Pro Rounded", "JetBrains Mono", monospace`,
            fontVariantNumeric: "tabular-nums",
            WebkitFontSmoothing: "antialiased",
          }}
        >
          <span
            style={{
              fontSize: 18,
              fontWeight: 700,
              color: "rgba(255,255,255,0.90)",
            }}
          >
            {value}
          </span>
          <span
            style={{
              fontSize: 10,
              fontWeight: 300,
              color: "rgba(6,182,212,0.80)",
              transform: "translateY(-50%)",
              marginLeft: 1,
            }}
          >
            %
          </span>
        </div>
      </div>
      <div
        style={{
          height: 10,
          borderRadius: 999,
          background: "rgba(255,255,255,0.05)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${Math.min(100, Math.max(0, value))}%`,
            borderRadius: 999,
            background: gradients[tone] || gradients.purple,
            transition: "width 0.8s cubic-bezier(0.16,1,0.3,1)",
            boxShadow: `0 0 12px rgba(124,92,255,0.25)`,
          }}
        />
      </div>
    </div>
  );
}

/* ================================================================
   AIRecommendation — AI 核心推荐评语
   ================================================================ */
export function AIRecommendation({ text }: { text: string }) {
  return (
    <div
      style={{
        padding: "16px 18px",
        borderRadius: 12,
        background:
          "linear-gradient(135deg, rgba(0,221,235,0.06), rgba(175,64,255,0.06))",
        border: "1px solid rgba(0,221,235,0.12)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 10,
        }}
      >
        {/* Sparkle icon */}
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="rgba(0,221,235,0.8)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z" />
          <path d="M19 15l.75 2.25L22 18l-2.25.75L19 21l-.75-2.25L16 18l2.25-.75z" />
        </svg>
        <span
          style={{
            fontSize: 14,
            fontWeight: 600,
            color: "rgba(255,255,255,0.90)",
            fontFamily: `"SF Pro Display", "PingFang SC", "Noto Sans SC", sans-serif`,
            WebkitFontSmoothing: "antialiased",
            MozOsxFontSmoothing: "grayscale",
          }}
        >
          AI 核心推荐评语
        </span>
      </div>
      <p
        style={{
          margin: 0,
          fontSize: 13,
          fontWeight: 400,
          lineHeight: 1.7,
          color: "rgba(255,255,255,0.65)",
          fontFamily: `"SF Pro Display", "PingFang SC", "Noto Sans SC", sans-serif`,
          WebkitFontSmoothing: "antialiased",
          MozOsxFontSmoothing: "grayscale",
        }}
      >
        {text}
      </p>
    </div>
  );
}
