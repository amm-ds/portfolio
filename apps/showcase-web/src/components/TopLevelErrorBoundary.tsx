import { Component, type ReactNode } from "react";
import { Link } from "react-router-dom";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

/** Last-resort boundary around the whole app: plain copy, reload + home. */
export class TopLevelErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: unknown): void {
    console.error("Unhandled render error:", error);
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <main className="app-main" style={{ paddingTop: "4rem" }}>
        <div className="state-box">
          <p>Something went wrong.</p>
          <p>
            The page hit an unexpected error.{" "}
            <button type="button" onClick={() => window.location.reload()}>
              Reload the page
            </button>{" "}
            or <Link to="/">go back home</Link>.
          </p>
        </div>
      </main>
    );
  }
}
