/* eslint-disable jsx-a11y/no-noninteractive-tabindex -- Focusable table regions allow keyboard scrolling. */
import type { ReactNode } from "react";

/**
 * Shared table pattern: mono accent-tinted header row, 1px borders, surface
 * background, and a horizontal-scroll wrapper on narrow screens. Pass a
 * modifier className (e.g. "metrics-table") for per-use tweaks. The wrapper is
 * focusable and named so keyboard users can scroll it (axe scrollable-region-focusable).
 */
export function DataTable({
  className = "",
  ariaLabel,
  children,
}: {
  className?: string;
  ariaLabel: string;
  children: ReactNode;
}) {
  return (
    <div
      className={`table-scroll data-table ${className}`.trim()}
      role="region"
      aria-label={ariaLabel}
      tabIndex={0}
    >
      <table>{children}</table>
    </div>
  );
}
