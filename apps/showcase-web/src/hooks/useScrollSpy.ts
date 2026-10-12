import { useEffect, useState } from "react";

/**
 * Scroll-spy: returns the id (from `ids`, in document order) whose section is
 * currently most in view. Falls back to null where IntersectionObserver is
 * unavailable (e.g. jsdom).
 */
export function useScrollSpy(ids: string[]): string | null {
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined" || ids.length === 0) return;
    const ratios = new Map<string, number>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const id = entry.target.id;
          if (entry.isIntersecting) ratios.set(id, entry.intersectionRatio);
          else ratios.delete(id);
        }
        let best: string | null = null;
        let bestRatio = 0;
        for (const id of ids) {
          const r = ratios.get(id);
          if (r !== undefined && r >= bestRatio) {
            best = id;
            bestRatio = r;
          }
        }
        if (best !== null) setActive(best);
      },
      { rootMargin: "-20% 0px -70% 0px", threshold: [0, 0.25, 0.5, 1] },
    );
    for (const id of ids) {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, [ids]);

  return active;
}
