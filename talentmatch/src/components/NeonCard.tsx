import { useState } from "react";
import { motion } from "motion/react";

interface NeonCardProps {
  icon?: string;
  title?: string;
  subtitle?: string;
  className?: string;
}

/**
 * 190×254px 霓虹边框发光卡片
 * 渐变边框 + 双层外光晕 + hover 增强 + 内部深色内容区
 */
export default function NeonCard({
  icon = "⚡",
  title = "Deep Match",
  subtitle = "v3.2.0",
  className = "",
}: NeonCardProps) {
  const [hovered, setHovered] = useState(false);

  return (
    <motion.div
      className={`neon-card ${className}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      whileHover={{ y: -5, scale: 1.03 }}
      transition={{ type: "spring", stiffness: 340, damping: 20 }}
    >
      {/* 外层柔光 (第二层, 范围更大) */}
      <div
        className="neon-card__glow-outer"
        style={{ opacity: hovered ? 0.4 : 0.2 }}
      />

      {/* 内层锐利光晕 (紧跟边框) */}
      <div
        className="neon-card__glow-inner"
        style={{
          opacity: hovered ? 0.9 : 0.5,
          filter: hovered ? "blur(35px)" : "blur(25px)",
        }}
      />

      {/* 卡片内容区 */}
      <div className="neon-card__content">
        {/* 顶部微光反射 */}
        <div className="neon-card__sheen" />

        <motion.span
          className="neon-card__icon"
          animate={{ y: hovered ? -4 : 0 }}
          transition={{ type: "spring", stiffness: 200, damping: 10 }}
        >
          {icon}
        </motion.span>

        <span className="neon-card__title">{title}</span>
        <span className="neon-card__code">{subtitle}</span>
      </div>
    </motion.div>
  );
}
