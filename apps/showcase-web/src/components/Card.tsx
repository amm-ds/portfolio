import type { HTMLAttributes, ReactNode } from "react";

/**
 * Shared surface card: dark background, border, 3px accent left border,
 * rounded corners, padding.
 */
export function Card({
  className = "",
  children,
  ...rest
}: {
  children: ReactNode;
} & HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`accent-card ${className}`.trim()} {...rest}>
      {children}
    </div>
  );
}
