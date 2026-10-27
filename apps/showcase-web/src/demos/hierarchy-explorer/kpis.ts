import type {
  HierGroupBlock,
  HierNode,
  HierOrigin,
  HierVariant,
  HierarchyPayload,
} from "../types";

// --- node identity ------------------------------------------------------------

/** Split a node id into its path segments. Labour ids are stringified path
 * lists ("['Males', 'New South Wales']"); TourismSmall ids are plain slugs
 * ("nsw-hol"). Anything unparseable falls back to the raw id. */
export function nodeSegments(nodeId: string): string[] {
  const m = /^\[(.*)\]$/.exec(nodeId.trim());
  if (!m) return [nodeId];
  const inner = m[1].trim();
  if (inner === "") return [nodeId];
  // split a python-repr list on `', '` boundaries that are not inside quotes
  const parts: string[] = [];
  let cur = "";
  let inQ = false;
  for (let i = 0; i < inner.length; i++) {
    const ch = inner[i];
    if (ch === "'") {
      inQ = !inQ;
      continue;
    }
    if (ch === "," && !inQ) {
      parts.push(cur.trim());
      cur = "";
      continue;
    }
    cur += ch;
  }
  parts.push(cur.trim());
  return parts.length > 0 && parts.every((p) => p !== "") ? parts : [nodeId];
}

/** The leaf segment of a node id — its short display name. */
export function nodeLeaf(nodeId: string): string {
  const segs = nodeSegments(nodeId);
  return segs[segs.length - 1];
}

/** A node's full path as display text ("Males · New South Wales"). */
export function nodePathLabel(nodeId: string): string {
  return nodeSegments(nodeId).join(" · ");
}

/** Selector row label: level badge + leaf, e.g. "Country/Region · New South Wales". */
export function nodeLabel(node: HierNode): string {
  return `${node.level} · ${nodeLeaf(node.node)}`;
}

/** The 6 catalog nodes of one group, in committed order (total first). */
export function groupNodes(payload: HierarchyPayload, group: string): HierNode[] {
  return payload.catalog.filter((n) => n.group === group);
}

/** Bottom nodes carry no children — reconciliation cannot move them. */
export function isBottom(node: HierNode): boolean {
  return node.children_count === 0 || node.level === "bottom";
}

// --- origin + curve accessors ---------------------------------------------------

/** Safe accessor: a node's origin block for one of the committed origin dates. */
export function nodeOrigin(node: HierNode, originDate: string): HierOrigin | null {
  return node.origins?.find((o) => o.origin === originDate) ?? null;
}

/** The committed origin dates for a group (ascending, identical on every node). */
export function originDates(payload: HierarchyPayload, group: string): string[] {
  return payload.evaluation_metadata.origins[group]?.catalog_origins ?? [];
}

/** The drawn x-axis: history (ends at the origin period) + the horizon
 * actuals — contiguous by construction (monthly / quarterly periods). */
export function axisFor(origin: HierOrigin | null): string[] {
  if (!origin) return [];
  return [...origin.history.dates, ...origin.actuals.dates];
}

/** Map (dates, values) onto the drawn axis; periods outside the series are
 * NaN so the shared chart splits them into separate line runs. */
export function valuesOnAxis(
  axis: string[],
  dates: string[],
  vals: number[],
): number[] {
  const idx = new Map(axis.map((d, i) => [d, i]));
  const out = Array<number>(axis.length).fill(NaN);
  for (let i = 0; i < dates.length; i++) {
    const j = idx.get(dates[i]);
    if (j !== undefined) out[j] = vals[i];
  }
  return out;
}

/** Horizon MAE of one variant's curve against the origin's actuals; null when
 * the lengths disagree or the window is empty (never fabricated). */
export function horizonMae(curve: number[] | null | undefined, actuals: number[]): number | null {
  if (!curve || curve.length === 0 || curve.length !== actuals.length) return null;
  let sum = 0;
  for (let i = 0; i < curve.length; i++) {
    const e = Math.abs(curve[i] - actuals[i]);
    if (!Number.isFinite(e)) return null;
    sum += e;
  }
  return sum / curve.length;
}

/** Per-variant horizon MAE at one origin, computed client-side from the curves. */
export function maeByVariant(
  origin: HierOrigin | null,
): Record<HierVariant, number | null> {
  const out = {} as Record<HierVariant, number | null>;
  const variants: HierVariant[] = [
    "seasonal_naive",
    "auto_ets",
    "lgbm_global",
    "lgbm_global+bottom_up",
    "lgbm_global+mint_shrink",
  ];
  for (const v of variants) {
    out[v] = origin ? horizonMae(origin.models[v]?.y_pred, origin.actuals.y) : null;
  }
  return out;
}

// --- committed blocks ------------------------------------------------------------

/** Group-mean incoherence share of the raw global model vs the MinT-reconciled
 * curve — the coherence KPI pair (reconciled is exactly 0 by construction). */
export function coherencePair(group: HierGroupBlock): {
  raw: number;
  mint: number;
} | null {
  const raw = group.coherence?.["lgbm_global"];
  const mint = group.coherence?.["lgbm_global+mint_shrink"];
  if (raw === undefined || mint === undefined) return null;
  return { raw, mint };
}

/** Committed total-level rmae of the headline variant (lgbm_global+MinT) vs
 * the seasonal-naive base — the group-level KPI tile. */
export function groupTotalRmae(group: HierGroupBlock): number | null {
  return group.headline?.total?.rmae ?? null;
}

// --- calendar --------------------------------------------------------------------

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/** "2019-02-01" → local Date (midnight, no TZ shift). */
export function parseDay(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** "2019-02-01" → "Feb 1". */
export function fmtDay(iso: string): string {
  const d = parseDay(iso);
  return `${MONTHS[d.getMonth()]} ${d.getDate()}`;
}
