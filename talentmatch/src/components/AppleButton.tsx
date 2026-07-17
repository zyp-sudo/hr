import React, { useRef, useState } from "react";
import { motion, useMotionValue, useSpring } from "motion/react";

interface AppleButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  variant?: "primary" | "secondary" | "success" | "danger" | "ghost";
  glowColor?: string;
  magnetic?: boolean;
}

export const AppleButton: React.FC<AppleButtonProps> = ({
  children,
  variant = "primary",
  glowColor = "rgba(124, 92, 255, 0.4)",
  magnetic = true,
  className = "",
  ...props
}) => {
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [isHovered, setIsHovered] = useState(false);

  // Motion values for magnetic effect
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  // Smooth springs for translation
  const springX = useSpring(x, { stiffness: 120, damping: 12 });
  const springY = useSpring(y, { stiffness: 120, damping: 12 });

  const handleMouseMove = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (!magnetic || !buttonRef.current) return;
    const rect = buttonRef.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    // Calculate distance from center, with a maximum offset of 10px
    const offsetX = (e.clientX - centerX) * 0.15;
    const offsetY = (e.clientY - centerY) * 0.15;

    x.set(offsetX);
    y.set(offsetY);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    x.set(0);
    y.set(0);
  };

  // Setup classes based on variant
  let variantClasses = "";
  switch (variant) {
    case "primary":
      // Rich gradient background, premium purple text alignment
      variantClasses = "bg-gradient-to-r from-[#7C5CFF] to-[#947dff] text-white shadow-lg shadow-primary/20 border border-primary/20";
      break;
    case "secondary":
      variantClasses = "bg-[#1f1f24]/80 backdrop-blur-md border border-outline-variant/50 text-[#c9c4d8] hover:text-white hover:border-[#7C5CFF]/60";
      break;
    case "success":
      variantClasses = "bg-gradient-to-r from-[#7fd5cd] to-[#9bf2e9] text-[#003733] font-bold shadow-lg shadow-[#7fd5cd]/10 border border-[#7fd5cd]/30";
      break;
    case "danger":
      variantClasses = "bg-gradient-to-r from-[#ffb4ab] to-[#ffdad6] text-[#690005] font-bold border border-error/30";
      break;
    case "ghost":
      variantClasses = "text-on-surface-variant hover:text-white hover:bg-surface-variant/30";
      break;
  }

  return (
    <motion.button
      ref={buttonRef}
      style={{
        x: springX,
        y: springY,
      }}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.96 }}
      transition={{ type: "spring", stiffness: 450, damping: 14 }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className={`relative px-5 py-3 rounded-lg font-medium select-none overflow-hidden cursor-pointer transition-colors duration-200 flex items-center justify-center gap-2 ${variantClasses} ${className}`}
      {...(props as any)}
    >
      {/* Glossy reflection/sweep effect */}
      <motion.div
        className="absolute inset-y-0 w-20 bg-gradient-to-r from-transparent via-white/20 to-transparent pointer-events-none"
        style={{
          skewX: -25,
          left: "-100%",
        }}
        animate={
          isHovered
            ? { left: "200%" }
            : { left: "-100%" }
        }
        transition={{
          repeat: Infinity,
          repeatDelay: 2.5,
          duration: 1.2,
          ease: "easeInOut",
        }}
      />

      {/* Button Content */}
      <span className="relative z-10 flex items-center gap-2">{children}</span>
    </motion.button>
  );
};
