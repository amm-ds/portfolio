import { Component, type ReactNode } from "react";

interface State {
  hasError: boolean;
  detail: string;
}

function describe(error: unknown): string {
  if (error instanceof Error) return `${error.name}: ${error.message}`;
  return String(error);
}

/**
 * Last-resort guard for demo pages: a render crash inside a demo shows the
 * fallback card instead of unmounting the whole app (white/blue screen). The
 * error is stored (console + localStorage) so an un reproduced browser crash
 * can be reported with its exact message.
 */
export class DemoErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { hasError: false, detail: "" };

  static getDerivedStateFromError(): Partial<State> {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    const detail = describe(error);
    console.error("demo crashed", error);
    try {
      localStorage.setItem("demo-crash", `${detail}\n${new Date().toISOString()}`);
    } catch {
      // storage unavailable (private mode) — the visible detail still helps
    }
    this.setState({ detail });
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="state-box error demo-error" role="alert">
        <p>This demo hit an unexpected error.</p>
        {this.state.detail && (
          <p className="demo-error-detail">
            <code>{this.state.detail}</code>
          </p>
        )}
        <div className="demo-error-actions">
          <button type="button" onClick={() => window.location.reload()}>
            try again
          </button>
          <a href="/projects#demos">back to demos</a>
        </div>
      </div>
    );
  }
}
