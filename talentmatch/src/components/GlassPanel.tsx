import { useCallback, useRef, useState, type CSSProperties, type ReactNode, type MouseEvent } from "react";
import { motion } from "motion/react";

interface GlassPanelProps {
  children: ReactNode;
  className?: string;
  /** 是否启用 hover 渐变光环扩散 */
  glowOnHover?: boolean;
  /** 是否启用 click 涟漪扩散 */
  rippleOnClick?: boolean;
  /** 光圈颜色 */
  glowColor?: string;
  /** 自定义内联样式 */
  style?: CSSProperties;
  /** 点击回调 */
  onClick?: (e: MouseEvent<HTMLDivElement>) => void;
}

/**
 * 毛玻璃面板 — 带 hover 渐变光圈扩散 + click 涟漪
 *
 * - hover：渐变彩色光圈从边框向外扩散
 * - click：更大的涟漪
 * - 面板本身为透明毛玻璃材质，能折射/吸收背景光源
 */
export default function GlassPanel({
  children,
  className = "",
  glowOnHover = true,
  rippleOnClick = true,
  glowColor = "rgba(0, 221, 235, 0.5), rgba(175, 64, 255, 0.5), rgba(91, 66, 243, 0.5)",
  style,
  onClick,
}: GlassPanelProps) {
  const [hovered, setHovered] = useState(false);
  const [ripples, setRipples] = useState<Array<{ id: number; x: number; y: number }>>([]);
  const rippleId = useRef(0);

  const handleClick = useCallback(
    (e: MouseEvent<HTMLDivElement>) => {
      onClick?.(e);

      if (!rippleOnClick) return;

      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const id = ++rippleId.current;

      setRipples((prev) => [...prev, { id, x, y }]);
      setTimeout(() => {
        setRipples((prev) => prev.filter((r) => r.id !== id));
      }, 800);
    },
    [onClick, rippleOnClick],
  );

  return (
    <motion.div
      className={`glass-panel-dynamic ${className}`}
      style={style}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={handleClick}
      whileHover={glowOnHover ? { scale: 1.005 } : undefined}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
    >
      {/* ---- Hover 渐变光环扩散层 ---- */}
      {glowOnHover && (
        <div
          className="glass-panel__glow-ring"
          style={{
            opacity: hovered ? 1 : 0,
            background: `conic-gradient(from 0deg, ${glowColor}, transparent 60%, ${glowColor})`,
          }}
        />
      )}

      {/* ---- Hover 第二层更柔的光晕 ---- */}
      {glowOnHover && (
        <div
          className="glass-panel__glow-aura"
          style={{
            opacity: hovered ? 1 : 0,
            background: `radial-gradient(circle, ${glowColor.split(",")[0] || "rgba(0,221,235,0.3)"}, transparent 70%)`,
          }}
        />
      )}

      {/* ---- 光源吸收折射边 (右侧, 面向光源) ---- */}
      <div className="glass-panel__light-absorb" />

      {/* ---- Click 涟漪 ---- */}
      {ripples.map((ripple) => (
        <span
          key={ripple.id}
          className="glass-panel__ripple"
          style={{
            left: ripple.x,
            top: ripple.y,
            borderColor: glowColor.split(",")[0]?.replace("0.5", "0.7") || "rgba(0,221,235,0.7)",
          }}
        />
      ))}

      {/* ---- 内容 ---- */}
      <div className="glass-panel__content">{children}</div>
    </motion.div>
  );
}
