import type { ReactNode } from "react";
import { useTheme } from "../theme/useTheme";

export function StatusBadge({ status }: { status: string }) {
  return <span className={`status-badge status-badge--${status}`}>{status}</span>;
}

export function Alert({ children, onDismiss }: { children: ReactNode; onDismiss: () => void }) {
  return (
    <div className="alert" role="alert">
      <span aria-hidden="true">!</span>
      <div><strong>Request failed.</strong> {children}</div>
      <button type="button" className="icon-button" onClick={onDismiss} aria-label="Dismiss error">×</button>
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="empty-state">
      <span aria-hidden="true">&gt;_</span>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  return (
    <div className="theme-switcher" role="group" aria-label="Display theme">
      {(["dark", "light"] as const).map((option) => (
        <button
          type="button"
          key={option}
          className={theme === option ? "is-active" : ""}
          aria-pressed={theme === option}
          onClick={() => setTheme(option)}
        >
          {option}
        </button>
      ))}
    </div>
  );
}

export function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}
