import type { ReactNode } from "react";
import type { DocumentStatus } from "../api/types";
import { useTheme } from "../theme/useTheme";

export function StatusBadge({ status }: { status: DocumentStatus | string }) {
  return <span className={`status-badge status-badge--${status}`}>{status.replaceAll("_", " ")}</span>;
}

export function Alert({
  tone,
  children,
  onDismiss,
}: {
  tone: "error" | "success";
  children: ReactNode;
  onDismiss?: () => void;
}) {
  return (
    <div className={`alert alert--${tone}`} role={tone === "error" ? "alert" : "status"}>
      <span className="alert__marker" aria-hidden="true">
        {tone === "error" ? "!" : "✓"}
      </span>
      <div className="alert__body">{children}</div>
      {onDismiss ? (
        <button type="button" className="icon-button" onClick={onDismiss} aria-label="Dismiss message">
          ×
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="empty-state">
      <span className="empty-state__prompt" aria-hidden="true">
        &gt;_
      </span>
      <h3>{title}</h3>
      <div>{children}</div>
    </div>
  );
}

export function LoadingState({ label }: { label: string }) {
  return (
    <div className="loading-state" role="status">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  return (
    <div className="theme-switcher" role="group" aria-label="Display theme">
      <button
        type="button"
        className={`theme-switcher__option ${theme === "dark" ? "is-active" : ""}`}
        aria-pressed={theme === "dark"}
        onClick={() => setTheme("dark")}
      >
        <span aria-hidden="true">☾</span>
        dark
      </button>
      <button
        type="button"
        className={`theme-switcher__option ${theme === "light" ? "is-active" : ""}`}
        aria-pressed={theme === "light"}
        onClick={() => setTheme("light")}
      >
        <span aria-hidden="true">☼</span>
        light
      </button>
    </div>
  );
}

export function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}
