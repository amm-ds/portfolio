import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

/**
 * Announces client-side route changes to assistive tech. On every pathname
 * change it moves focus to the routed <main id="main"> (so keyboard/screen
 * reader users land on the new content instead of staying on the nav) and
 * mirrors document.title into a visually-hidden aria-live region.
 */
export function RouteAnnouncer() {
  const { pathname } = useLocation();
  const [announcement, setAnnouncement] = useState("");

  useEffect(() => {
    // Reset navigation before moving focus. Without preventScroll, focusing
    // main scrolls its top behind the taller wrapped nav on mobile.
    window.scrollTo(0, 0);
    document.getElementById("main")?.focus({ preventScroll: true });
    // Read the title in a macrotask: this component sits above the routed
    // tree, so its passive effect can flush before usePageMeta has set
    // document.title for the new route.
    const timer = window.setTimeout(() => setAnnouncement(document.title), 0);
    return () => window.clearTimeout(timer);
  }, [pathname]);

  return (
    <div aria-live="polite" role="status" className="visually-hidden">
      {announcement}
    </div>
  );
}
