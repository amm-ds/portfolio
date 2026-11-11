/** Privacy-preserving field Web Vitals (evaluation P1-5).
 *
 * Observes LCP, INP and CLS in the browser and sends one beacon to the API's
 * POST /vitals when the page hides. The payload carries nothing but the
 * metric name, value, the route reduced to its first two path segments, the
 * device class and the release build SHA — no cookies, no identifiers, no
 * message content. Same-origin, so the strict CSP needs no exception.
 */

export interface VitalSample {
  metric: "LCP" | "INP" | "CLS";
  value: number;
}

let clsTotal = 0;
let inpMax = 0;
let lcpLast = 0;
let installed = false;

export function deviceClass(): "mobile" | "tablet" | "desktop" {
  const w = window.innerWidth;
  if (w < 640) return "mobile";
  if (w < 1024) return "tablet";
  return "desktop";
}

export function routeKey(pathname: string = window.location.pathname): string {
  const parts = pathname.split("/").filter(Boolean).slice(0, 2);
  return "/" + parts.join("/");
}

function buildSha(): string {
  return document.querySelector('meta[name="build-sha"]')?.getAttribute("content") ?? "dev";
}

/** Push the final values and beacon them; no-op when nothing was measured. */
export function flush(): void {
  const vitals: VitalSample[] = [];
  if (lcpLast > 0) vitals.push({ metric: "LCP", value: Math.round(lcpLast) });
  if (inpMax > 0) vitals.push({ metric: "INP", value: Math.round(inpMax) });
  if (clsTotal > 0) vitals.push({ metric: "CLS", value: Number(clsTotal.toFixed(4)) });
  if (vitals.length === 0) return;
  // consume the accumulators so a later pagehide cannot double-send
  lcpLast = 0;
  inpMax = 0;
  clsTotal = 0;
  const payload = JSON.stringify({
    vitals: vitals.map((v) => ({ ...v, route: routeKey(), device: deviceClass(), sha: buildSha() })),
  });
  const blob = new Blob([payload], { type: "application/json" });
  if (!navigator.sendBeacon("/vitals", blob)) {
    void fetch("/vitals", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: payload,
      keepalive: true,
    }).catch(() => {
      /* field data is best-effort */
    });
  }
}

/** Wire the PerformanceObservers; idempotent. Exported for tests. */
export function installVitals(): void {
  if (installed || typeof PerformanceObserver === "undefined") return;
  installed = true;

  try {
    const lcp = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      if (entries.length > 0) lcpLast = entries[entries.length - 1].startTime;
    });
    lcp.observe({ type: "largest-contentful-paint", buffered: true });
  } catch {
    /* observer type unsupported — skip the metric */
  }

  try {
    const cls = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const shift = entry as PerformanceEntry & { hadRecentInput?: boolean; value?: number };
        if (!shift.hadRecentInput) clsTotal += shift.value ?? 0;
      }
    });
    cls.observe({ type: "layout-shift", buffered: true });
  } catch {
    /* layout-shift unsupported */
  }

  try {
    const inp = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const timing = entry as PerformanceEntry & { interactionId?: number };
        if (timing.interactionId && timing.interactionId > 0) {
          inpMax = Math.max(inpMax, timing.duration);
        }
      }
    });
    inp.observe({ type: "event", durationThreshold: 16, buffered: true } as never);
  } catch {
    /* event-timing unsupported */
  }

  const onHide = () => {
    if (document.visibilityState === "hidden") flush();
  };
  document.addEventListener("visibilitychange", onHide);
  window.addEventListener("pagehide", flush);
}

installVitals();
