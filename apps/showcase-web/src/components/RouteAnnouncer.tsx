import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

/**
 * Announces client-side route changes to assistive tech. On every location
 * change it moves focus to the routed <main id="main"> (so keyboard/screen
 * reader users land on the new content instead of staying on the nav) and
 * mirrors document.title into a visually-hidden aria-live region.
 *
 * The initial mount is deliberately excluded (wave R1, external evaluation):
 * moving focus to main on first load made the first Tab jump to the hero CTA,
 * bypassing the skip link, brand/primary navigation and theme controls. Focus
 * moves only after an actual client-side navigation; hash behavior and the
 * announcement are unchanged.
 */
export function RouteAnnouncer() {
  const { pathname, hash } = useLocation();
  const [announcement, setAnnouncement] = useState("");
  const isFirstRender = useRef(true);

  useEffect(() => {
    let observer: MutationObserver | undefined;
    // Skip focus management on the initial mount — the browser's own focus
    // order (skip link first) must stand on a fresh load.
    const skipFocus = isFirstRender.current;
    isFirstRender.current = false;
    if (hash) {
      // A lazy route may still be showing its skeleton when this effect runs.
      // Wait for the anchored content to mount instead of resetting to top.
      let targetId = hash.slice(1);
      try {
        targetId = decodeURIComponent(targetId);
      } catch {
        // Keep the literal fragment if it contains an invalid escape sequence.
      }
      const scrollToTarget = () => {
        const target = document.getElementById(targetId);
        if (!target) return false;
        target.scrollIntoView();
        return true;
      };
      if (!scrollToTarget()) {
        observer = new MutationObserver(() => {
          if (scrollToTarget()) observer?.disconnect();
        });
        observer.observe(document.getElementById("main") ?? document.body, {
          childList: true,
          subtree: true,
        });
      }
    } else if (!skipFocus) {
      // Reset navigation before moving focus. Without preventScroll, focusing
      // main scrolls its top behind the taller wrapped nav on mobile.
      window.scrollTo(0, 0);
    }
    if (!skipFocus) {
      document.getElementById("main")?.focus({ preventScroll: true });
    }
    // Read the title in a macrotask: this component sits above the routed
    // tree, so its passive effect can flush before usePageMeta has set
    // document.title for the new route.
    const timer = window.setTimeout(() => setAnnouncement(document.title), 0);
    return () => {
      observer?.disconnect();
      window.clearTimeout(timer);
    };
  }, [pathname, hash]);

  return (
    <div aria-live="polite" role="status" className="visually-hidden">
      {announcement}
    </div>
  );
}
