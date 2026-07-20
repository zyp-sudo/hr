import { Plus } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";

type AddJobButtonProps = {
  /** Button size variant — "default" for toolbar (40px), "large" for hero (46px). */
  size?: "default" | "large";
} & Pick<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "onClick" | "className" | "disabled" | "aria-label"
>;

/**
 * Shared "添加新岗位" button used across the homepage hero, job management
 * toolbar, and competition discovery header.  All three locations delegate to
 * this single component so visual language, text, and animation never drift
 * apart.
 */
export default function AddJobButton({
  size = "default",
  className,
  disabled,
  onClick,
  ...rest
}: AddJobButtonProps) {
  const ariaLabel = rest["aria-label"] ?? "添加新岗位";

  return (
    <button
      className={`add-job-button add-job-button--${size}${className ? ` ${className}` : ""}`}
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      type="button"
    >
      <Plus size={16} aria-hidden="true" />
      <span>添加新岗位</span>
    </button>
  );
}
