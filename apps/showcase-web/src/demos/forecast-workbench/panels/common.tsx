import { useState, type ReactNode } from "react";

/** One string control serialized to the URL query (`?series=&origin=&model=`),
 * mirroring useControlState's write-and-cleanup pattern for the numeric ones. */
export function useQueryParam<T extends string>(
  key: string,
  allowed: readonly T[],
  fallback: T,
): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    const q = new URLSearchParams(window.location.search).get(key);
    return (allowed as readonly string[]).includes(q ?? "") ? (q as T) : fallback;
  });
  const set = (v: T) => {
    setValue(v);
    try {
      const params = new URLSearchParams(window.location.search);
      if (v === fallback) params.delete(key);
      else params.set(key, v);
      const qs = params.toString();
      window.history.replaceState(
        null,
        "",
        window.location.pathname + (qs ? `?${qs}` : "") + window.location.hash,
      );
    } catch {
      // URL state is a nicety, never a crash
    }
  };
  return [value, set];
}

/** Card with the shared figure-card chrome (chart region + commentary band). */
export function Figure({ comment, children }: { comment: ReactNode; children: ReactNode }) {
  return (
    <div className="figure-card">
      {children}
      <footer className="figure-card-band">
        <p className="figure-comment">{comment}</p>
      </footer>
    </div>
  );
}

/** Tiny inline sparkline for picker rows (drawn from the SELECTED ORIGIN's
 * as-of history, so a row previews exactly what the explorer would show). */
export function Sparkline({ values, color }: { values: number[]; color: string }) {
  const W = 64;
  const H = 20;
  const max = Math.max(...values, 1);
  const pts = values
    .map(
      (v, i) =>
        `${((i / Math.max(1, values.length - 1)) * W).toFixed(1)},${(
          H -
          (Math.max(0, v) / max) * (H - 2) -
          1
        ).toFixed(1)}`,
    )
    .join(" ");
  return (
    <svg width={W} height={H} className="wb-spark" aria-hidden="true">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}
