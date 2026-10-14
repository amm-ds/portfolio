import type { HTMLAttributes, ReactNode } from "react";

/**
 * Shared surface card: dark background, border, 3px accent left border,
 * rounded corners, padding. `accent` picks the left-border color.
 */
export function Card({
  accent = "accent",
  className = "",
  children,
  ...rest
}: {
  accent?: "accent" | "secondary" | "danger";
  children: ReactNode;
} & HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`accent-card card-${accent} ${className}`.trim()} {...rest}>
      {children}
    </div>
  );
}
