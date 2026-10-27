import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import type { HierVariant, HierarchyPayload } from "../types";
import {
  axisFor,
  coherencePair,
  groupNodes,
  groupTotalRmae,
  horizonMae,
  isBottom,
  maeByVariant,
  nodeLeaf,
  nodeOrigin,
  nodeSegments,
  originDates,
  valuesOnAxis,
} from "./kpis";

/**
 * Contract test against the REAL committed payload
 * (`projects/02-demand-forecasting/reports/hier_demo_payload.json`, built by
 * `demand_forecasting.hier_demo_payload`, schema v1 — the wave-23b
 * hierarchical reconciliation demo: 2 groups × 6 catalog nodes, 3 rolling
 * origins per node, 5 committed curve variants). Walks every node × origin
 * through the kpi helpers and pins the reconciliation invariants (BottomUp
 * leaves bottoms exactly unchanged; reconciled variants are exactly coherent;
 * parents diverge from the raw curve), so a payload drift fails here instead
 * of blanking the demo.
 */
const raw = JSON.parse(
  readFileSync("../../projects/02-demand-forecasting/reports/hier_demo_payload.json", "utf8"),
) as HierarchyPayload;

const VARIANTS: HierVariant[] = [
  "seasonal_naive",
  "auto_ets",
  "lgbm_global",
  "lgbm_global+bottom_up",
  "lgbm_global+mint_shrink",
];
const RECONCILED: HierVariant[] = ["lgbm_global+bottom_up", "lgbm_global+mint_shrink"];

describe("committed hierarchy demo payload contract (schema v1)", () => {
  it("carries the explorer identity and the hierarchical protocol", () => {
    expect(raw.schema_version).toBe(1);
    expect(raw.demo).toBe("hierarchy-explorer");
    expect(raw.project).toBe("02-demand-forecasting");
    expect(raw.evaluation_metadata.protocol).toBe("hierarchical_rolling_v1");
    expect(raw.evaluation_metadata.curve_variants).toEqual(VARIANTS);
    expect(Object.keys(raw.groups).sort()).toEqual(["Labour", "TourismSmall"]);
  });

  it("catalog holds 6 nodes per group across 4 levels, parents before bottoms", () => {
    expect(raw.catalog).toHaveLength(12);
    for (const group of ["Labour", "TourismSmall"]) {
      const nodes = groupNodes(raw, group);
      expect(nodes).toHaveLength(6);
      const levels = new Set(nodes.map((n) => n.level));
      expect(levels).toEqual(new Set(raw.groups[group].levels));
      expect(nodes[0].level).toBe("total");
      expect(nodes[0].parent_path).toEqual([]);
      expect(nodes[0].children_count).toBeGreaterThan(0);
      const bottoms = nodes.filter(isBottom);
      expect(bottoms.length).toBeGreaterThan(0);
      for (const b of bottoms) {
        expect(b.children_count).toBe(0);
        expect(b.children).toEqual([]);
      }
      // every non-total node's parent chain depth matches its level depth
      // (parent_path entries are hierarchy ids — only 6 of the ~91 nodes are
      // carried in the catalog, so intermediate ids need not appear here)
      const depth = (level: string) => raw.groups[group].levels.indexOf(level);
      for (const n of nodes.slice(1)) {
        expect(n.parent_path.length).toBeGreaterThan(0);
        expect(n.parent_path.length).toBe(depth(n.level));
      }
    }
  });

  it("every node carries the same 3 committed origins with a contiguous axis", () => {
    for (const group of ["Labour", "TourismSmall"]) {
      const expected = raw.evaluation_metadata.origins[group].catalog_origins;
      expect(expected).toHaveLength(3);
      expect(originDates(raw, group)).toEqual(expected);
      for (const node of groupNodes(raw, group)) {
        expect(node.origins.map((o) => o.origin)).toEqual(expected);
        for (const o of node.origins) {
          // history ends AT the origin period, actuals start the period after
          expect(o.history.dates[o.history.dates.length - 1]).toBe(o.origin);
          expect(o.actuals.dates[0] > o.origin).toBe(true);
          expect(o.actuals.dates).toHaveLength(raw.groups[group].horizon);
          expect(o.history.dates.length).toBe(raw.groups[group].season_length * 2);
          const axis = axisFor(o);
          expect(axis).toHaveLength(o.history.dates.length + o.actuals.dates.length);
          expect(new Set(axis).size).toBe(axis.length); // no duplicates → contiguous
        }
      }
    }
  });

  it("every origin carries exactly the 5 finite curve variants over the horizon", () => {
    for (const node of raw.catalog) {
      for (const o of node.origins) {
        expect(Object.keys(o.models).sort()).toEqual([...VARIANTS].sort());
        for (const v of VARIANTS) {
          const curve = o.models[v].y_pred;
          expect(curve).toHaveLength(o.actuals.dates.length);
          expect(curve.every((x) => Number.isFinite(x))).toBe(true);
        }
        const mae = maeByVariant(o);
        for (const v of VARIANTS) {
          expect(mae[v]).not.toBeNull();
          expect(Number.isFinite(mae[v]!)).toBe(true);
        }
      }
    }
  });

  it("reconciliation invariants: BottomUp leaves bottoms unchanged, parents move, reconciled coherence is exactly 0", () => {
    for (const node of raw.catalog) {
      for (const o of node.origins) {
        const raw_ = o.models.lgbm_global.y_pred;
        if (isBottom(node)) {
          // BottomUp leaves the bottom series EXACTLY unchanged; MinT nudges
          // slightly (≤ ~6% of the curve scale on the committed payload)
          expect(o.models["lgbm_global+bottom_up"].y_pred).toEqual(raw_);
          const mint = o.models["lgbm_global+mint_shrink"].y_pred;
          const mintMax = Math.max(...mint.map((v, i) => Math.abs(v - raw_[i])));
          const scale = Math.max(1, ...raw_.map(Math.abs), ...mint.map(Math.abs));
          expect(mintMax).toBeLessThan(0.1 * scale);
          // coherence block is absent at bottoms
          expect(o.coherence ?? null).toBeNull();
        } else {
          for (const v of RECONCILED) {
            expect(o.models[v].y_pred).not.toEqual(raw_);
          }
          // per-node coherence: exactly 0 for both reconciled variants
          const coh = o.coherence as Record<HierVariant, number> | null | undefined;
          expect(Object.keys(coh ?? {}).sort()).toEqual([...RECONCILED].sort());
          for (const v of RECONCILED) expect(coh?.[v]).toBe(0);
        }
      }
    }
  });

  it("group blocks carry the committed headline + per-level rmae and the coherence story", () => {
    for (const [name, g] of Object.entries(raw.groups)) {
      expect(g.group).toBe(name);
      expect(g.levels).toHaveLength(4);
      expect(g.per_level["lgbm_global+mint_shrink"]).toBeDefined();
      // the reconciled variants are exactly coherent at the group level; the raw bases are not
      expect(g.coherence["lgbm_global+mint_shrink"]).toBe(0);
      expect(g.coherence["lgbm_global+bottom_up"]).toBe(0);
      expect(g.coherence["lgbm_global"]).toBeGreaterThan(0);
      const coh = coherencePair(g)!;
      expect(coh.raw).toBe(g.coherence["lgbm_global"]);
      expect(coh.mint).toBe(0);
      // headline total-level rmae matches the per_level table for the same variant
      const total = g.per_level["lgbm_global+mint_shrink"].total;
      expect(groupTotalRmae(g)).toBeCloseTo(total.rmae, 12);
      expect(g.headline.total.rmae).toBeCloseTo(total.rmae, 12);
      expect(g.headline.claim).toContain("lgbm_global+mint_shrink");
      expect(g.headline.claim).toContain("rmae");
    }
    // the two committed headline rmae values the fallback manifest quotes
    expect(raw.groups.Labour.headline.total.rmae).toBeCloseTo(0.2969702109027057, 12);
    expect(raw.groups.TourismSmall.headline.total.rmae).toBeCloseTo(0.8686089500307468, 12);
  });

  it("kpi helpers walk every node × origin without throwing", () => {
    let scored = 0;
    for (const group of Object.keys(raw.groups)) {
      for (const node of groupNodes(raw, group)) {
        expect(nodeLeaf(node.node).length).toBeGreaterThan(0);
        for (const date of originDates(raw, group)) {
          const o = nodeOrigin(node, date);
          expect(o).not.toBeNull();
          const axis = axisFor(o);
          const hist = valuesOnAxis(axis, o!.history.dates, o!.history.y);
          const act = valuesOnAxis(axis, o!.actuals.dates, o!.actuals.y);
          expect(hist.filter(Number.isFinite)).toHaveLength(o!.history.dates.length);
          expect(act.filter(Number.isFinite)).toHaveLength(o!.actuals.dates.length);
          expect(horizonMae(o!.models.seasonal_naive.y_pred, o!.actuals.y)).not.toBeNull();
          scored++;
        }
      }
    }
    expect(scored).toBe(12 * 3);
  });

  it("node id parsing handles both id forms", () => {
    expect(nodeSegments("total")).toEqual(["total"]);
    expect(nodeSegments("nsw-hol-city")).toEqual(["nsw-hol-city"]);
    expect(nodeSegments("['Total']")).toEqual(["Total"]);
    expect(nodeSegments("['Males', 'New South Wales']")).toEqual(["Males", "New South Wales"]);
    expect(nodeSegments("['Employed full-time', 'Males', 'New South Wales']")).toEqual([
      "Employed full-time",
      "Males",
      "New South Wales",
    ]);
    expect(nodeLeaf("['Males', 'New South Wales']")).toBe("New South Wales");
  });

  it("stays under the 200 KB demo-payload cap", () => {
    const bytes = readFileSync(
      "../../projects/02-demand-forecasting/reports/hier_demo_payload.json",
    ).byteLength;
    expect(bytes).toBeLessThanOrEqual(200 * 1024);
  });
});
