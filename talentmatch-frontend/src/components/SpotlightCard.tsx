import React, { useState } from "react";
import { motion, useMotionValue, useSpring } from "motion/react";

interface SpotlightCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  glowColor?: string;
  borderColor?: string;
  hoverGlowOpacity?: number;
}

export const SpotlightCard: React.FC<SpotlightCardProps> = ({
  children,
  glowColor = "rgba(124, 92, 255, 0.15)",
  borderColor = "rgba(147, 142, 161, 0.15)",
  hoverGlowOpacity = 0.35,
  className = "",
  style: _style,
  ...rest
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  const springX = useSpring(mouseX, { stiffness: 150, damping: 20 });
  const springY = useSpring(mouseY, { stiffness: 150, damping: 20 });

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    mouseX.set(x);
    mouseY.set(y);
  };

  const props = { style: _style, ...rest } as any;

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => setIsHovered(false)}
      className={`relative rounded-xl bg-[#1f1f24]/30 backdrop-blur-xl border border-outline-variant/20 overflow-hidden shadow-2xl transition-all duration-300 ${className}`}
      style={{
        borderColor: isHovered ? "rgba(124, 92, 255, 0.3)" : borderColor,
        ..._style,
      }}
      {...props}
    >
      {/* Spotlight follow glow */}
      <motion.div
        className="absolute pointer-events-none rounded-full"
        style={{
          width: 320,
          height: 320,
          top: -160,
          left: -160,
          x: springX,
          y: springY,
          background: `radial-gradient(circle, ${glowColor} 0%, transparent 70%)`,
          opacity: isHovered ? hoverGlowOpacity : 0,
        }}
        transition={{ duration: 0.3 }}
      />

      {/* Subtle pulsing rotating neon-gradient light for card borders */}
      {isHovered && (
        <div className="absolute inset-0 p-[1px] rounded-xl bg-gradient-to-tr from-[#7C5CFF]/30 via-[#9bf2e9]/20 to-[#7C5CFF]/30 pointer-events-none -z-10" />
      )}

      {/* Content wrapper */}
      <div className="relative z-10 w-full h-full p-6 md:p-8 flex flex-col">
        {children}
      </div>
    </motion.div>
  );
};
