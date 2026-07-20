import { Lock, ArrowRight } from "lucide-react";

interface PreviewOverlayProps {
  total: number;
  shown: number;
  onLoginClick: () => void;
}

/**
 * Renders a blurry "登录后查看完整数据" overlay below preview content.
 *
 * Usage: place it at the bottom of a data section when the user is not logged in.
 * It shows how many records are hidden and a prominent login CTA.
 */
export default function PreviewOverlay({ total, shown, onLoginClick }: PreviewOverlayProps) {
  const hidden = Math.max(0, total - shown);
  if (hidden <= 0) return null;

  return (
    <div className="preview-overlay">
      <div className="preview-overlay-bg" />
      <div className="preview-overlay-content">
        <div className="preview-overlay-icon">
          <Lock size={28} />
        </div>
        <h3>登录后查看完整数据</h3>
        <p>
          当前仅展示前 <strong>{shown}</strong> 条预览数据，
          还有 <strong>{hidden}</strong> 条数据需要登录后查看
        </p>
        <button className="preview-overlay-btn" onClick={onLoginClick}>
          <span>立即登录查看全部</span>
          <ArrowRight size={18} />
        </button>
      </div>
    </div>
  );
}
