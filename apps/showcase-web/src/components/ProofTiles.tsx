import { useEffect, useState } from "react";
import { getDemoRegistry } from "../api";
import type { DemoRegistryEntry, HeroMetric } from "../demos/types";
import { AVAILABILITY } from "../config";

/** Static snapshot of the demo registry, used when `GET /demos` is
 * unreachable. Another workstream maintains `src/lib/staticRegistry.ts`;
 * when that module (or its export) is not there yet we fall back to this
 * inline minimal copy, kept in sync with the published manifests. */
const INLINE_REGISTRY: DemoRegistryEntry[] = [
  {
    id: "forecast-workbench",
    title: "demand forecast workbench",
    hook: "Pick a store-product series from the committed M5 track and compare the seasonal naive, AutoETS, LightGBM and the pooled ensemble on the scored-once test origins.",
    group: "plan operations",
    href: "/demos/forecast-workbench",
    project: "02-demand-forecasting",
    status: "live",
    hero: {
      label: "pooled test WAPE, ensemble vs seasonal-naive floor (600 series, 2 scored origins)",
      value: "0.498 vs 0.603",
      ci: "paired bootstrap CI [−0.115, −0.095] on the −0.105 gap; 89.3% per-series win rate",
    },
  },
  {
    id: "churn-sandbox",
    title: "churn threshold sandbox",
    hook: "Move the alarm threshold and the missed-churner cost — watch the optimal cutoff and the saved budget change on a real churn model.",
    group: "retain customers",
    href: "/demos/churn-sandbox",
    project: "05-ml-pipeline-churn",
    status: "live",
    hero: {
      label: "decision cost per 1,400 customers",
      value: "$601 vs $1,035 naive",
      ci: "paired bootstrap CI [−485, −343]",
    },
  },
];

/** Resolve the static snapshot defensively: the sibling workstream may name
 * the export `STATIC_REGISTRY`, `staticRegistry`, or default-export it — and
 * the module itself may not exist yet (import.meta.glob matches nothing
 * instead of failing the build). Anything unusable falls back to the inline
 * minimal copy above. */
function resolveStaticRegistry(): DemoRegistryEntry[] {
  const modules = import.meta.glob("../lib/staticRegistry*", { eager: true }) as Record<
    string,
    unknown
  >;
  const mod = Object.values(modules)[0] as Record<string, unknown> | undefined;
  const candidate = mod?.STATIC_REGISTRY ?? mod?.staticRegistry ?? mod?.default;
  return Array.isArray(candidate) && candidate.length > 0
    ? (candidate as DemoRegistryEntry[])
    : INLINE_REGISTRY;
}

/** Cut a hero field at the em-dash when it runs long; the CI line keeps only
 * its first clause (the CI statement itself). */
function shorten(text: string): string {
  const cut = text.split(" — ")[0]!.split("; ")[0]!;
  return cut.trim();
}

/** Merge the demo registry's hero metrics with a config-sourced tile so the
 * strip always shows three proof points. */
function buildTiles(entries: DemoRegistryEntry[] | null): { label: string; value: string; ci: string }[] {
  const source = entries ?? resolveStaticRegistry();
  const tiles = source
    .map((e) => e.hero)
    .filter((h): h is HeroMetric => h !== null && h.value !== "")
    .map((h) => ({ label: shorten(h.label), value: h.value, ci: h.ci ? shorten(h.ci) : "" }));
  while (tiles.length < 3 && !tiles.some((t) => t.label === "availability")) {
    tiles.push({
      label: "availability",
      value: AVAILABILITY.status,
      ci: `typical reply within ${AVAILABILITY.replyHours}h`,
    });
  }
  return tiles.slice(0, 3);
}

/** Three proof tiles: measured results from the demo registry (live, with a
 * static fallback) plus one availability tile from site config. */
export function ProofTiles() {
  const [entries, setEntries] = useState<DemoRegistryEntry[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDemoRegistry()
      .then((list) => !cancelled && setEntries(list))
      .catch(() => !cancelled && setEntries(null));
    return () => {
      cancelled = true;
    };
  }, []);

  const tiles = buildTiles(entries);
  return (
    <div className="proof-tiles go-grid" data-testid="proof-tiles">
      {tiles.map((t) => (
        <div key={t.label} className="proof-tile accent-card">
          <p className="proof-label">{t.label}</p>
          <p className="proof-value">{t.value}</p>
          {t.ci && <p className="proof-ci">{t.ci}</p>}
        </div>
      ))}
    </div>
  );
}
