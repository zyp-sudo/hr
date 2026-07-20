import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, ArrowLeft, RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
  onNavigateHome?: () => void;
  pageName?: string;
}

interface State {
  hasError: boolean;
  errorMessage: string;
}

export default class CompetitionErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, errorMessage: "" };
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      errorMessage: error.message || "未知运行时错误",
    };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(
      `[CompetitionErrorBoundary] ${this.props.pageName || "页面"} 渲染崩溃:`,
      error,
      info.componentStack,
    );
  }

  handleReload = () => {
    this.setState({ hasError: false, errorMessage: "" });
  };

  handleGoHome = () => {
    this.setState({ hasError: false, errorMessage: "" });
    this.props.onNavigateHome?.();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="comp-empty" style={{ minHeight: 360, gap: 14 }}>
          <AlertTriangle style={{ width: 42, height: 42, color: "#f87171" }} />
          <h3>页面加载失败</h3>
          <p style={{ maxWidth: 480 }}>
            当前页面渲染时发生错误：
            <code style={{ display: "block", marginTop: 8, padding: "8px 12px", borderRadius: 6, background: "rgba(0,0,0,.2)", color: "#f87171", fontSize: 12, wordBreak: "break-all" }}>
              {this.state.errorMessage}
            </code>
          </p>
          <p style={{ color: "#6e6a78", fontSize: 12, maxWidth: 480 }}>
            这通常是因为后端接口返回了不符合预期的数据结构。
            请确认 8080 后端已重启并加载最新路由。
          </p>
          <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
            <button
              className="comp-action-btn"
              onClick={this.handleReload}
              aria-label="重新加载当前页面"
            >
              <RefreshCw style={{ width: 16 }} /> 重新加载当前页面
            </button>
            <button
              className="comp-action-btn"
              onClick={this.handleGoHome}
              aria-label="返回功能总览"
            >
              <ArrowLeft style={{ width: 16 }} /> 返回功能总览
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
