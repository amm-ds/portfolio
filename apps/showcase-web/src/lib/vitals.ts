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

interface RouteMeasurements {
  cls: number;
  lcp: number;
  /** Longest event duration for each browser interaction id. */
  interactions: Map<number, number>;
}

const measurements = new Map<string, RouteMeasurements>();
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

function forCurrentRoute(): RouteMeasurements {
  const route = routeKey();
  let current = measurements.get(route);
  if (!current) {
    current = { cls: 0, lcp: 0, interactions: new Map() };
    measurements.set(route, current);
  }
  return current;
}

function buildSha(): string {
  return document.querySelector('meta[name="build-sha"]')?.getAttribute("content") ?? "dev";
}

/** INP's high-percentile value: worst interaction below 50 interactions, then
 * approximately one slower interaction excluded per 50 (p98). */
function interactionToNextPaint(interactions: Map<number, number>): number {
  const durations = [...interactions.values()].sort((a, b) => a - b);
  if (durations.length === 0) return 0;
  const index = durations.length - 1 - Math.floor(durations.length / 50);
  return durations[index];
}

/** Push final values per originating route; no-op when nothing was measured. */
export function flush(): void {
  const vitals: (VitalSample & { route: string; device: string; sha: string })[] = [];
  for (const [route, current] of measurements) {
    const samples: VitalSample[] = [];
    if (current.lcp > 0) samples.push({ metric: "LCP", value: Math.round(current.lcp) });
    const inp = interactionToNextPaint(current.interactions);
    if (inp > 0) samples.push({ metric: "INP", value: Math.round(inp) });
    if (current.cls > 0) samples.push({ metric: "CLS", value: Number(current.cls.toFixed(4)) });
    vitals.push(...samples.map((sample) => ({
      ...sample,
      route,
      device: deviceClass(),
      sha: buildSha(),
    })));
  }
  measurements.clear(); // a later pagehide cannot double-send consumed values
  if (vitals.length === 0) return;
  const payload = JSON.stringify({ vitals });
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
      if (entries.length > 0) forCurrentRoute().lcp = entries[entries.length - 1].startTime;
    });
    lcp.observe({ type: "largest-contentful-paint", buffered: true });
  } catch {
    /* observer type unsupported — skip the metric */
  }

  try {
    const cls = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const shift = entry as PerformanceEntry & { hadRecentInput?: boolean; value?: number };
        if (!shift.hadRecentInput) forCurrentRoute().cls += shift.value ?? 0;
      }
    });
    cls.observe({ type: "layout-shift", buffered: true });
  } catch {
    /* layout-shift unsupported */
  }

  try {
    const inp = new PerformanceObserver((list) => {
      const current = forCurrentRoute();
      for (const entry of list.getEntries()) {
        const timing = entry as PerformanceEntry & { interactionId?: number };
        if (timing.interactionId && timing.interactionId > 0) {
          const previous = current.interactions.get(timing.interactionId) ?? 0;
          current.interactions.set(timing.interactionId, Math.max(previous, timing.duration));
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
