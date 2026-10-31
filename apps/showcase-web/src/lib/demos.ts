import { STATIC_DEMO_REGISTRY } from "./staticRegistry";

/** Offline fallback for the projects-page demos block, rendered only when the
 * demo registry endpoint (`GET /demos`) is unreachable. Derived from the
 * generated registry snapshot (scripts/gen_static_registry.py), so it cannot
 * drift from the published demos; the live list still comes from the registry. */
export interface Demo {
  id: string;
  title: string;
  line: string;
  /** Target route once live; undefined while the demo is a placeholder. */
  href?: string;
}

export const DEMOS: Demo[] = [...STATIC_DEMO_REGISTRY]
  .sort((a, b) => a.id.localeCompare(b.id))
  .map((d) => ({
    id: d.id,
    title: d.title,
    line: d.hook,
    href: d.href,
  }));

export const DEMOS_INTRO = "play with the live systems behind the experiments";
