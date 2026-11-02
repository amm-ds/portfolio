import { STATIC_DEMO_REGISTRY } from "./staticRegistry";
import type { DemoRegistryEntry } from "../api";

/** Offline fallback for the projects-page demos block, rendered only when the
 * demo registry endpoint (`GET /demos`) is unreachable. Derived from the
 * generated registry snapshot (scripts/gen_static_registry.py), so it cannot
 * drift from the published demos; the live list still comes from the registry.
 * Carries the same display fields as the live registry entries so fallback
 * cards render the shared layout with identical copy. */
export interface Demo {
  id: string;
  title: string;
  line: string;
  /** Target route once live; undefined while the demo is a placeholder. */
  href?: string;
  /** One-line domain descriptor, e.g. "plan operations". */
  group?: string;
  /** Linked experiment id — its four card tags tag the demo card. */
  project?: string;
  /** Headline metric (label/value/ci) shown as the card's brief result. */
  hero?: DemoRegistryEntry["hero"] | null;
}

export const DEMOS: Demo[] = [...STATIC_DEMO_REGISTRY]
  .sort((a, b) => a.id.localeCompare(b.id))
  .map((d) => ({
    id: d.id,
    title: d.title,
    line: d.hook,
    href: d.href,
    group: d.group,
    project: d.project,
    hero: d.hero,
  }));

export const DEMOS_INTRO = "play with the live systems behind the experiments";

/** Demo cards never show numbers — the experiments own the metrics — but the
 * registry hooks name datasets ("M5") and bands ("80%"). Each published demo
 * therefore carries a digit-free display line for the card's "what it does"
 * block; unknown demo ids fall back to the registry hook with digits and
 * digit-words stripped. */
export const DEMO_DOES: Record<string, string> = {
  "churn-sandbox":
    "Move the alarm threshold and the missed-churner cost — watch the optimal cutoff and the saved budget change on a real churn model.",
  "forecast-workbench":
    "Pick a committed store-product series from the public demand track, compare the seasonal naive, AutoETS, gradient-boosted and pooled ensemble candidates on the scored-once test origins, and slide the horizon — curves, prediction band and per-series error respond.",
};

/** Digit-free "what it does" line for a demo card. */
export function demoDoes(data: { id: string; hook: string }): string {
  return (
    DEMO_DOES[data.id] ??
    data.hook
      .replace(/[0-9０-９]+(?:\.[0-9]+)?%?/g, "")
      .replace(/\s{2,}/g, " ")
      .trim()
  );
}
