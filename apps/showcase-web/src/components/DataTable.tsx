import type { ReactNode } from "react";

/**
 * Shared table pattern: mono accent-tinted header row, 1px borders, surface
 * background, and a horizontal-scroll wrapper on narrow screens. Pass a
 * modifier className (e.g. "metrics-table") for per-use tweaks.
 */
export function DataTable({ className = "", children }: { className?: string; children: ReactNode }) {
  return (
    <div className={`table-scroll data-table ${className}`.trim()}>
      <table>{children}</table>
    </div>
  );
}
