import { useState } from "react";
import { X, LogIn, Eye, EyeOff, ShieldAlert } from "lucide-react";
import { login, type AuthUser } from "../auth";

interface LoginModalProps {
  open: boolean;
  onClose: () => void;
  onLoginSuccess: (user: AuthUser) => void;
}

/**
 * Login modal with email/password fields.
 * Displays a hint with the 5 built-in test accounts.
 * On success calls onLoginSuccess; on failure shows inline error.
 */
export default function LoginModal({ open, onClose, onLoginSuccess }: LoginModalProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showAccounts, setShowAccounts] = useState(false);

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!email.trim() || !password) {
      setError("请填写邮箱和密码");
      return;
    }
    setLoading(true);
    try {
      const result = await login(email.trim(), password);
      onLoginSuccess(result.user);
      onClose();
    } catch (err: any) {
      setError(err.message || "登录失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  const fillAccount = (acct: { email: string; password: string }) => {
    setEmail(acct.email);
    setPassword(acct.password);
    setShowAccounts(false);
  };

  return (
    <div className="login-overlay" onClick={onClose}>
      <div className="login-modal" onClick={(e) => e.stopPropagation()}>
        {/* Close button */}
        <button className="login-close" onClick={onClose} aria-label="关闭">
          <X size={20} />
        </button>

        {/* Header */}
        <div className="login-header">
          <div className="login-icon-wrap">
            <LogIn size={22} />
          </div>
          <h2>登录 TalentMatch</h2>
          <p>登录后可查看完整岗位数据与人岗匹配结果</p>
        </div>

        {/* Error */}
        {error && (
          <div className="login-error">
            <ShieldAlert size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="login-form">
          <label>
            <span>邮箱</span>
            <input
              type="email"
              placeholder="admin@talentmatch.cn"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoFocus
            />
          </label>
          <label>
            <span>密码</span>
            <div className="login-password-wrap">
              <input
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                className="login-password-toggle"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </label>
          <button
            type="submit"
            className="login-submit"
            disabled={loading}
          >
            {loading ? "登录中…" : "登 录"}
          </button>
        </form>

        {/* Test accounts hint */}
        <div className="login-accounts-hint">
          <button
            className="login-accounts-toggle"
            onClick={() => setShowAccounts(!showAccounts)}
          >
            {showAccounts ? "隐藏" : "查看"}测试账号 →
          </button>
          {showAccounts && (
            <div className="login-accounts-list">
              {[
                { email: "admin@talentmatch.cn", password: "admin123", label: "管理员" },
                { email: "hr_zhang@talentmatch.cn", password: "hr123456", label: "张HR" },
                { email: "hr_li@talentmatch.cn", password: "hr123456", label: "李HR" },
                { email: "iv_wang@talentmatch.cn", password: "iv123456", label: "王面试官" },
                { email: "iv_chen@talentmatch.cn", password: "iv123456", label: "陈面试官" },
              ].map((acct) => (
                <button
                  key={acct.email}
                  className="login-account-chip"
                  onClick={() => fillAccount(acct)}
                >
                  <strong>{acct.label}</strong>
                  <code>{acct.email}</code>
                  <span className="chip-pw">{acct.password}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
