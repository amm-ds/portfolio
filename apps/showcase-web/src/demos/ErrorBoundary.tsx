import { Component, type ReactNode } from "react";

interface State {
  hasError: boolean;
}

/**
 * Last-resort guard for demo pages: a render crash inside a demo shows the
 * fallback card instead of unmounting the whole app (white/blue screen).
 */
export class DemoErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    console.error("demo crashed", error);
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="state-box error demo-error" role="alert">
        <p>This demo hit an unexpected error.</p>
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
