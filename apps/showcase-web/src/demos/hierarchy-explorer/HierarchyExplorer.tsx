import { useEffect, useState } from "react";
import type { DemoManifest, HierarchyPayload } from "../types";
import { DemoWorkbench, KpiTile, Notice, useControlState } from "../workbench";
import { HierarchyChart, VARIANT_SHORT } from "./HierarchyChart";
import {
  coherencePair,
  fmtDay,
  groupNodes,
  groupTotalRmae,
  isBottom,
  maeByVariant,
  nodeLabel,
  nodeLeaf,
  nodeOrigin,
  nodePathLabel,
  originDates,
} from "./kpis";
import { fetchHierarchyPayload, fetchManifest } from "./payload";
import { useQueryParam } from "./useQueryParam";

/** Minimal manifest so the explorer renders before/if the manifest fetch fails
 * (mirrors projects/02-demand-forecasting/demos/hierarchy-explorer.yaml). */
const FALLBACK_MANIFEST: DemoManifest = {
  id: "hierarchy-explorer",
  title: "hierarchy explorer",
  hook: "Pick a node in the Labour or TourismSmall hierarchy, pick one of the committed rolling origins, and slide across the horizon — the raw global LightGBM drifts away from its children while MinT reconciliation snaps the curves back into an exactly-coherent tree, total down to every bottom series.",
  project: "02-demand-forecasting",
  group: "plan operations",
  skills: ["hierarchical time series", "forecast reconciliation", "MinT"],
  modes: ["browser"],
  hero: {
    label: "total-level rmae, lgbm_global+MinT vs seasonal naive (committed wave-23a hierarchical track)",
    value: "Labour 0.297, TourismSmall 0.869 — MinT repairs the incoherent ML base forecast on both hierarchies",
    ci: "per-level rmae and coherence are copied verbatim from the committed reports_hier/metrics.json; the payload build re-runs the scoring and drift-guards every carried scalar at 1e-9 before writing",
  },
  scenarios: [
    { name: "base", controls: { group: "Labour", node: "['Total']", origin: "2019-04-01" } },
    {
      name: "reconciled-gap",
      controls: { group: "Labour", node: "['New South Wales']", origin: "2019-04-01" },
    },
    { name: "tourism", controls: { group: "TourismSmall", node: "nsw-hol", origin: "2005-12-31" } },
  ],
  live_endpoints: [],
  payload: {
    path: "reports/hier_demo_payload.json",
    schema_version: 1,
    required_keys: ["demo", "project", "groups", "catalog", "evaluation_metadata"],
  },
};

/** Presentation order — Labour carries the flagship story (raw total-level
 * rmae 1.03 → 0.297 under MinT). */
const GROUP_ORDER = ["Labour", "TourismSmall"];

export default function HierarchyExplorer() {
  const [manifest, setManifest] = useState<DemoManifest | null>(null);
  const [payload, setPayload] = useState<HierarchyPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchManifest("hierarchy-explorer")
      .then((m) => !cancelled && setManifest(m))
      .catch(() => {
        /* payload fetch below reports the real error */
      });
    fetchHierarchyPayload("hierarchy-explorer")
      .then((p) => !cancelled && setPayload(p))
      .catch(() => !cancelled && setError("could not load the demo payload — is the API running?"));
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return <div className="state-box error">{error}</div>;
  }
  if (payload === null) {
    return <p className="loading">loading demo…</p>;
  }
  return <Explorer manifest={manifest ?? FALLBACK_MANIFEST} payload={payload} />;
}

/** Explorer body once the payload (and manifest, or fallback) is in hand. */
function Explorer({ manifest, payload }: { manifest: DemoManifest; payload: HierarchyPayload }) {
  const state = useControlState({}, manifest.scenarios);
  const groups = GROUP_ORDER.filter((g) => payload.groups[g] !== undefined);

  // --- selection: group / node / origin, all URL-serialized string controls
  const [groupName, setGroupName] = useQueryParam("group", groups, groups[0]);
  const nodes = groupNodes(payload, groupName);
  const allNodeIds = payload.catalog.map((n) => n.node);
  const [nodeRaw, setNodeRaw] = useQueryParam("node", allNodeIds, nodes[0]?.node ?? "");
  const node = nodes.find((n) => n.node === nodeRaw) ?? nodes[0];

  const dates = originDates(payload, groupName);
  const [originRaw, setOriginRaw] = useQueryParam(
    "origin",
    dates,
    dates[dates.length - 1] ?? "",
  );
  const originDate = dates.includes(originRaw) ? originRaw : dates[dates.length - 1];
  const origin = nodeOrigin(node, originDate);

  const group = payload.groups[groupName];
  const horizon = group?.horizon ?? origin?.actuals.dates.length ?? 0;
  const bottom = isBottom(node);
  const mae = maeByVariant(origin);
  const coh = group ? coherencePair(group) : null;
  const totalRmae = group ? groupTotalRmae(group) : null;

  const rawMaeStr = mae.lgbm_global !== null ? mae.lgbm_global.toFixed(1) : "n/a";
  const mintMaeStr =
    mae["lgbm_global+mint_shrink"] !== null ? mae["lgbm_global+mint_shrink"].toFixed(1) : "n/a";
  const mintBeatsRaw =
    mae.lgbm_global !== null && mae["lgbm_global+mint_shrink"] !== null
      ? mae["lgbm_global+mint_shrink"]! <= mae.lgbm_global!
      : null;

  return (
    <DemoWorkbench
      manifest={manifest}
      state={state}
      controls={
        <>
          <div className="wb-control-group wb-group-presets">
            <span className="wb-rail-title" id="hier-group-label">
              Group
            </span>
            <div className="demo-control">
              <div className="demo-presets" role="group" aria-labelledby="hier-group-label">
                {groups.map((g) => (
                  <button
                    key={g}
                    type="button"
                    className={`chip demo-preset ${g === groupName ? "active" : ""}`}
                    aria-pressed={g === groupName}
                    onClick={() => setGroupName(g)}
                  >
                    {g}
                  </button>
                ))}
              </div>
              <p className="demo-hint">
                {group?.freq === "MS" ? "monthly" : "quarterly"} · season{" "}
                {group?.season_length} · horizon {horizon}
              </p>
            </div>
          </div>
          <div className="wb-control-group wb-group-picker">
            <span className="wb-rail-title" id="hier-node-label">
              Node
            </span>
            <div className="demo-control">
              <ul className="wb-series-list" aria-label="Node list" style={{ maxHeight: 240 }}>
                {nodes.map((n) => (
                  <li key={n.node}>
                    <button
                      type="button"
                      className={`wb-series-row ${n.node === node.node ? "active" : ""}`}
                      aria-pressed={n.node === node.node}
                      title={nodePathLabel(n.node)}
                      onClick={() => setNodeRaw(n.node)}
                    >
                      <span className="chip wb-series-class">{n.level}</span>
                      <span className="wb-series-label">{nodeLabel(n)}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <p className="demo-hint">
                {node.children_count} {node.children_count === 1 ? "child" : "children"} — pick a
                parent to see reconciliation move the curve
              </p>
            </div>
          </div>
          <div className="wb-control-group wb-group-presets">
            <span className="wb-rail-title" id="hier-origin-label">
              Origin
            </span>
            <div className="demo-control">
              <div className="demo-presets" role="group" aria-labelledby="hier-origin-label">
                {dates.map((d) => (
                  <button
                    key={d}
                    type="button"
                    className={`chip demo-preset ${d === originDate ? "active" : ""}`}
                    aria-pressed={d === originDate}
                    onClick={() => setOriginRaw(d)}
                  >
                    {fmtDay(d)}
                    {d === dates[dates.length - 1] && " · latest"}
                  </button>
                ))}
              </div>
              <p className="demo-hint">committed rolling origins — history ends at the origin</p>
            </div>
          </div>
        </>
      }
      canvas={<HierarchyChart node={node} origin={origin} horizon={horizon} />}
      kpis={
        <>
          <KpiTile
            label="Horizon MAE — MinT vs raw"
            value={`${mintMaeStr} vs ${rawMaeStr}`}
            sub={`${VARIANT_SHORT["lgbm_global+mint_shrink"]} vs ${VARIANT_SHORT.lgbm_global} · ${nodeLeaf(node.node)} · h = 1…${horizon}`}
            tone={mintBeatsRaw === null ? "neutral" : mintBeatsRaw ? "good" : "bad"}
          />
          <KpiTile
            label="Horizon MAE — other variants"
            value={`${mae.seasonal_naive !== null ? mae.seasonal_naive.toFixed(1) : "n/a"} · ${mae.auto_ets !== null ? mae.auto_ets.toFixed(1) : "n/a"} · ${mae["lgbm_global+bottom_up"] !== null ? mae["lgbm_global+bottom_up"].toFixed(1) : "n/a"}`}
            sub="seasonal naive · auto ets · lgbm global + BottomUp — same origin, computed client-side"
          />
          {bottom ? (
            <KpiTile
              label="Coherence — bottom leaves"
              value="unchanged"
              sub="BottomUp leaves the bottom series unchanged — MinT nudges a leaf only slightly (shrunk covariance)"
            />
          ) : (
            <KpiTile
              label="Coherence — MinT vs raw"
              value={coh ? `${coh.mint.toFixed(3)} vs ${coh.raw.toFixed(3)}` : "n/a"}
              sub={`mean |parent − Σchildren| share of the horizon forecasts · ${groupName} (group mean)`}
              tone={coh && coh.mint < coh.raw ? "good" : "neutral"}
            />
          )}
          <KpiTile
            label="Total rmae (committed)"
            value={totalRmae !== null ? `rmae ${totalRmae.toFixed(3)}` : "n/a"}
            sub={`lgbm_global+MinT vs seasonal naive at the total level · ${groupName} · wave-23a committed`}
            tone={totalRmae !== null && totalRmae < 1 ? "good" : "neutral"}
          />
        </>
      }
      notice={
        <Notice>
          {bottom ? (
            <>
              Bottom series: the BottomUp curve coincides with the raw global curve here and
              MinT moves it only slightly — a leaf has no children to disagree with, so
              reconciliation has almost nothing to re-anchor.
            </>
          ) : (
            <>
              At this node the raw global model forecasts on its own, off its{" "}
              <strong>{node.children_count} children</strong> — horizon MAE{" "}
              <strong>{mintMaeStr} (MinT) vs {rawMaeStr} (raw)</strong> against what
              materialized, while the committed group-mean incoherence of the raw curve is{" "}
              <strong>{coh ? coh.raw.toFixed(3) : "n/a"}</strong> vs exactly 0 after MinT.
            </>
          )}
        </Notice>
      }
      evidence={
        <>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">the reconciliation story</h4>
            <p className="wb-evidence-line">
              A global boosted model pools every series in the hierarchy and forecasts each
              node independently — fast and accurate at the leaves, but it never sees the
              aggregation constraints: its total can drift away from the sum of its own
              children. That is <strong>incoherence</strong> — planning against a total that
              is not the sum of its parts.
            </p>
            <p className="wb-evidence-line">
              <code className="wb-tag">BottomUp</code> rebuilds every aggregate from the
              bottom forecasts — exactly coherent, but it throws away whatever signal the
              aggregate level carries. <code className="wb-tag">MinT shrink</code> keeps the
              base forecasts and re-anchors them with one linear pass: the adjustment uses
              the residual covariance between levels, shrunk toward a diagonal — coherent by
              construction, and closer to the truth where the aggregates really do know
              something the leaves don't.
            </p>
            <p className="wb-evidence-line">
              BottomUp leaves the bottom series exactly unchanged, and MinT barely moves
              them (a few percent at most in this payload) — the curves visibly move only
              at parents, which is exactly where this explorer lets you watch them move.
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">committed headline numbers</h4>
            {groups.map((g) => (
              <p className="wb-evidence-line" key={g}>
                <strong>{g}</strong> — {payload.groups[g].headline.claim}
              </p>
            ))}
            <p className="wb-evidence-line wb-metric-tags">
              {groups.map((g) => {
                const blk = payload.groups[g];
                const rawTotal = blk.per_level["lgbm_global"]?.["total"]?.rmae;
                const mintTotal = blk.per_level["lgbm_global+mint_shrink"]?.["total"]?.rmae;
                const rawCoh = blk.coherence["lgbm_global"];
                return (
                  <span key={g} className="wb-tag">
                    {g}: total rmae {rawTotal?.toFixed(3)} → {mintTotal?.toFixed(3)} (MinT) ·
                    raw incoherence {rawCoh?.toFixed(3)} → 0.000
                  </span>
                );
              })}
            </p>
            <p className="wb-evidence-line">
              The cost of incoherence is visible in the committed per-level rmae: the raw
              global model posts total-level rmae above 1 (worse than the seasonal naive)
              on Labour, while the MinT-reconciled curve repairs it to 0.297 — and on
              TourismSmall the reconciliation closes a 0.102 mean incoherence share to
              exactly zero without giving back bottom-level accuracy.
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">protocol</h4>
            <p className="wb-evidence-line wb-metric-tags">
              <span className="wb-tag">{payload.evaluation_metadata.protocol}</span>
              <span className="wb-tag">
                source {payload.evaluation_metadata.source}
              </span>
              {groups.map((g) => (
                <span key={g} className="wb-tag">
                  {g}: {payload.evaluation_metadata.origins[g].n} rolling origins,{" "}
                  {payload.evaluation_metadata.origins[g].catalog_origins.length} in the
                  catalog
                </span>
              ))}
              <span className="wb-tag">5 curve variants committed</span>
            </p>
            <p className="wb-evidence-line">
              Every carried scalar is copied from the committed{" "}
              <code className="wb-tag">reports_hier/metrics.json</code> and drift-guarded at
              1e-9 when the payload is rebuilt; the experiment write-up lives at{" "}
              <a href="/projects/02-demand-forecasting">/projects/02-demand-forecasting</a>.
            </p>
          </div>
        </>
      }
      about={
        <>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">what this shows</h4>
            <p className="wb-evidence-line">
              The explorer replays committed rolling-origin forecasts — nothing refits. The
              solid white line is the bounded history window (two seasons) ending at the
              origin period; right of the dashed origin marker everything was still unknown.
              The five curves are the committed variants over the horizon: two raw learners,
              the raw global LightGBM, and its two reconciled forms. <strong>MAE</strong>{" "}
              tiles average |curve − actual| over the whole horizon at the selected node ×
              origin — computed client-side from the payload, not quoted. <strong>rmae</strong>{" "}
              is pooled MAE ÷ the seasonal-naive MAE at the same level;{" "}
              <strong>coherence</strong> is the mean share of the horizon where a parent
              disagrees with the sum of its children (0 = exactly coherent).
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">how to read the gap</h4>
            <p className="wb-evidence-line">
              Pick a parent node and compare the teal raw curve against the amber BottomUp
              and pink MinT curves: the raw curve is the boosted model's own opinion of that
              node, the reconciled curves are re-anchored to its children. Where the raw
              curve sits closer to the ghost actuals, the aggregate carried real signal; where
              the reconciled curves do, the raw model was drifting off its own hierarchy. At
              bottom nodes the BottomUp curve coincides with the raw one and MinT sits
              almost on top — a leaf has no children to disagree with.
            </p>
          </div>
        </>
      }
    />
  );
}
