import { useEffect, useRef, useState, type MutableRefObject } from "react";

export interface MeasuredSize {
  w: number;
  h: number;
}

/**
 * Container-measured sizing for SVG panels: observes the wrapper with a
 * ResizeObserver and reports its content box, so a viewBox +
 * preserveAspectRatio="none" svg fills the panel at any viewport. Returns
 * `null` until the first measurement (callers keep a static fallback size)
 * and stays `null` where ResizeObserver is unavailable (jsdom).
 */
export function useMeasuredSize<T extends HTMLElement>(): {
  ref: MutableRefObject<T | null>;
  size: MeasuredSize | null;
} {
  const ref = useRef<T | null>(null);
  const [size, setSize] = useState<MeasuredSize | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      try {
        const r = entries[0]?.contentRect;
        if (!r || r.width <= 0 || r.height <= 0) return;
        const next: MeasuredSize = { w: Math.round(r.width), h: Math.round(r.height) };
        // Bail on identical sizes: Safari re-fires the observer during scroll
        // (scrollbar overlay shifts the content box) and an unconditional
        // setState storms renders into an error boundary. The 2px hysteresis
        // also breaks sub-pixel oscillation loops (300.4 -> 300 vs 300.6 ->
        // 301 ping-ponging re-renders and growing flex parents on real
        // devices).
        setSize((prev) =>
          prev && Math.abs(prev.w - next.w) < 2 && Math.abs(prev.h - next.h) < 2
            ? prev
            : next,
        );
      } catch {
        // never let an observer callback reach the error boundary
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return { ref, size };
}
