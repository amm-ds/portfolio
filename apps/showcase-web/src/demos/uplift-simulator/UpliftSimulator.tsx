import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { LineChart, type LineMarker } from "../charts/LineChart";
import { useMeasuredSize } from "../charts/useMeasuredSize";
import type { DemoManifest, UpliftPayload } from "../types";
import { DemoWorkbench, KpiTile, Notice, useControlState } from "../workbench";
import {
  crossoverCost,
  incrementalAt,
  mailEveryoneAt,
  nearestIndex,
  peakFractionAt,
  policyProfitAt,
  profitAt,
  winnerAt,
} from "./kpis";
import { fetchManifest, fetchUpliftPayload } from "./payload";

const C_TEAL = "#2dd4bf";
const C_PINK = "#f472b6";
const C_AMBER = "#fbbf24";
const C_GRAY = "#64748b";

/** Shared plot padding for charts that overlay SVG children computed from a
 * container measurement (the frontier's mail-everyone labels). */
const PAD = { l: 56, r: 18, t: 16, b: 32 };

/** Compact money readout: 47.3k → "$47.3k". */
function fmtMoney(v: number): string {
  return `$${(v / 1000).toFixed(1)}k`;
}

/** Axis money format: 47000 → "$47k". */
function fmtMoneyAxis(v: number): string {
  return `$${Math.round(v / 1000)}k`;
}

function fmtPct(v: number): string {
  return `${Math.round(v * 100)}%`;
}

/** Minimal manifest so the workbench renders before/if the manifest fetch fails. */
const FALLBACK_MANIFEST: DemoManifest = {
  id: "uplift-simulator",
  title: "uplift policy simulator",
  hook: "Move the send cost and the targeting budget — watch when personalized targeting beats mailing everyone, and which email each customer should get.",
  project: "10-uplift-experimentation",
  group: "spend marketing budget",
  skills: ["causal inference", "uplift modeling", "experimentation"],
  modes: ["browser"],
  hero: {
    label: "best-arm profit @25% vs random",
    value: "$35.5k vs $16.6k",
    ci: "paired bootstrap, 95%",
  },
  scenarios: [
    { name: "base", controls: { cost: 0.05, budget: 0.25 } },
    { name: "break-even-discovery", controls: { cost: 0.31, budget: 0.5 } },
    { name: "high-cost", controls: { cost: 0.5, budget: 0.35 } },
  ],
  live_endpoints: [],
  payload: { path: "reports/demo_payload.json", schema_version: 1, required_keys: [] },
};

/** Card with the shared figure-card chrome (chart region + commentary band). */
function Figure({ comment, children }: { comment: ReactNode; children: ReactNode }) {
  return (
    <div className="figure-card">
      {children}
      <footer className="figure-card-band">
        <p className="figure-comment">{comment}</p>
      </footer>
    </div>
  );
}

// --- profit frontier panel --------------------------------------------------------

function FrontierPanel({
  payload,
  cost,
  budget,
  onBudget,
}: {
  payload: UpliftPayload;
  cost: number;
  budget: number;
  onBudget: (fraction: number) => void;
}) {
  const grid = payload.profit_grid;
  const costIdx = nearestIndex(grid.costs, cost);
  const fracIdx = nearestIndex(grid.fractions, budget);
  const latticeCost = grid.costs[costIdx];
  const fraction = grid.fractions[fracIdx];

  const best = grid.policies.best_arm.profit[costIdx] ?? [];
  const ciHi = grid.policies.best_arm.ci?.hi[costIdx] ?? best;
  const ciLo = grid.policies.best_arm.ci?.lo[costIdx] ?? best;
  const single = grid.policies.single_arm.profit[costIdx] ?? [];
  const random = grid.policies.random.profit[costIdx] ?? [];
  const meMens = mailEveryoneAt(payload.scalars.mail_everyone_profit.mens, latticeCost);
  const meWomens = mailEveryoneAt(payload.scalars.mail_everyone_profit.womens, latticeCost);

  const series = [
    { name: "best arm", color: C_TEAL, values: best },
    // transparent CI boundary series so the chart's band fill has edges
    { name: "ci hi", color: "transparent", values: ciHi },
    { name: "ci lo", color: "transparent", values: ciLo },
    { name: "single arm (mens)", color: C_AMBER, values: single },
    { name: "random", color: C_GRAY, dashed: true, values: random },
    {
      name: "mail everyone mens",
      color: C_PINK,
      dashed: true,
      values: grid.fractions.map(() => meMens),
    },
    {
      name: "mail everyone womens",
      color: C_GRAY,
      dashed: true,
      values: grid.fractions.map(() => meWomens),
    },
  ];

  // The mail-everyone lines are flat, so the y ceiling is stable across drags;
  // pin it (chart default would do the same) and reuse it for label coords.
  const yMax = Math.max(...series.flatMap((s) => s.values), 1) * 1.08;

  // label coordinates must match the chart's own scale: measure the same box
  // the chart measures and apply the same padding/yMax
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 720;
  const H = size?.h ?? 280;
  const plotH = H - PAD.t - PAD.b;
  const yFor = (v: number) => PAD.t + plotH - (v / yMax) * plotH;

  const bestProfit = profitAt(grid, costIdx, fracIdx);
  const winner = winnerAt(bestProfit, meMens);
  const delta = bestProfit - meMens;

  return (
    <Figure
      comment={
        <>
          Profit = incremental conversions × revenue − emails × send cost, model-estimated on the
          committed scores; the dashed horizontals are the mail-everyone baselines at the current
          cost — drag the cursor to set the targeting budget.
        </>
      }
    >
      <div className="demo-readouts">
        <span className="chip demo-readout">cost ${latticeCost.toFixed(2)}/email</span>
        <span className="chip demo-readout">budget {fmtPct(fraction)}</span>
        <span className="chip demo-readout">best arm {fmtMoney(bestProfit)}</span>
        <span className={`chip demo-readout ${winner === "best_arm" ? "good" : "bad"}`}>
          {winner === "best_arm"
            ? `best-arm targeting +${fmtMoney(delta)}`
            : `mail everyone mens +${fmtMoney(-delta)}`}
        </span>
      </div>
      <div className="demo-chart" ref={ref}>
        <LineChart
          x={grid.fractions}
          series={series}
          pad={PAD}
          yMax={yMax}
          cursor={fracIdx}
          onCursorChange={(idx) => onBudget(grid.fractions[idx])}
          band={{ between: [1, 2], color: C_TEAL, opacity: 0.15 }}
          formatX={fmtPct}
          formatY={fmtMoneyAxis}
          ariaLabel="campaign profit over targeted fraction"
        >
          <text
            x={W - PAD.r - 4}
            y={yFor(meMens) - 5}
            textAnchor="end"
            className="demo-axis-label"
            style={{ fill: C_PINK }}
          >
            mail everyone · mens {fmtMoney(meMens)}
          </text>
          <text
            x={W - PAD.r - 4}
            y={yFor(meWomens) - 5}
            textAnchor="end"
            className="demo-axis-label"
            style={{ fill: C_GRAY }}
          >
            mail everyone · womens {fmtMoney(meWomens)}
          </text>
        </LineChart>
      </div>
      <p className="demo-hint">drag the chart to move the targeting budget</p>
    </Figure>
  );
}

// --- qini curves panel --------------------------------------------------------------

/** "(95% CI spans zero: ranking not established)" for arms whose coefficient
 * interval crosses 0 — the honest read of a weak ranking. */
function ciCaveat(lo: number, hi: number): string {
  return lo < 0 && hi > 0 ? " (95% CI spans zero: ranking not established)" : "";
}

function QiniPanel({ payload }: { payload: UpliftPayload }) {
  const qm = payload.qini_points.mens;
  const qw = payload.qini_points.womens;
  const fr = qm.fractions;
  // random baseline is a straight line to the best-arm full-send total
  // (payload note); resampling a line onto the shared grid is exact.
  const randomLine = fr.map((f) => f * payload.scalars.incremental_conversions_full_send_best_arm);
  return (
    <Figure
      comment={
        <>
          Empirical Qini curves on the randomized arm-vs-control pairs — mens qini{" "}
          {qm.qini_coefficient.toFixed(2)}
          {ciCaveat(qm.qini_ci[0], qm.qini_ci[1])}, womens{" "}
          {qw.qini_coefficient.toFixed(2)}
          {ciCaveat(qw.qini_ci[0], qw.qini_ci[1])}; dashed is the model-estimated random line to
          the best-arm full-send total.
        </>
      }
    >
      <div className="demo-chart">
        <LineChart
          x={fr}
          series={[
            { name: "mens", color: C_TEAL, values: qm.incremental },
            { name: "womens", color: C_PINK, values: qw.incremental },
            { name: "random", color: C_GRAY, dashed: true, values: randomLine },
          ]}
          formatX={fmtPct}
          ariaLabel="empirical qini curve per arm"
        />
      </div>
      <p className="demo-hint">incremental conversions captured vs fraction targeted</p>
    </Figure>
  );
}

// --- cost sensitivity panel -----------------------------------------------------------

function CostPanel({
  payload,
  cost,
  budget,
}: {
  payload: UpliftPayload;
  cost: number;
  budget: number;
}) {
  const grid = payload.profit_grid;
  const costIdx = nearestIndex(grid.costs, cost);
  const budgetIdx = nearestIndex(grid.fractions, budget);
  const bestCol = grid.costs.map((_, c) => policyProfitAt(grid, "best_arm", c, budgetIdx));
  const randCol = grid.costs.map((_, c) => policyProfitAt(grid, "random", c, budgetIdx));
  const meCol = grid.costs.map((c) => mailEveryoneAt(payload.scalars.mail_everyone_profit.mens, c));
  const crossIdx = crossoverCost(grid, budgetIdx, meCol);

  const markers: LineMarker[] = [
    { xIndex: costIdx, label: `$${grid.costs[costIdx].toFixed(2)}`, style: "dashed" },
  ];
  if (crossIdx !== null) markers.push({ xIndex: crossIdx, style: "star" });

  return (
    <Figure
      comment={
        <>
          Profit vs send cost at {fmtPct(grid.fractions[budgetIdx])} targeting — the star marks the
          crossover where best-arm targeting overtakes mailing everyone; the dashed marker is the
          current cost.
        </>
      }
    >
      <div className="demo-chart">
        <LineChart
          x={grid.costs}
          series={[
            { name: "best arm", color: C_TEAL, values: bestCol },
            { name: "random", color: C_GRAY, dashed: true, values: randCol },
            { name: "mail everyone mens", color: C_PINK, dashed: true, values: meCol },
          ]}
          markers={markers}
          formatX={(v) => `$${v.toFixed(2)}`}
          formatY={fmtMoneyAxis}
          ariaLabel="campaign profit over send cost at the targeting budget"
        />
      </div>
      <p className="demo-hint">total campaign profit vs cost per email</p>
    </Figure>
  );
}

// --- recommended-arm mix panel ---------------------------------------------------------

const SEGMENT_KEYS = ["Mens E-Mail", "Womens E-Mail", "No E-Mail"] as const;
const SEGMENT_COLORS: Record<(typeof SEGMENT_KEYS)[number], string> = {
  "Mens E-Mail": C_TEAL,
  "Womens E-Mail": C_PINK,
  "No E-Mail": C_GRAY,
};

function ArmMixPanel({ payload }: { payload: UpliftPayload }) {
  // container-measured like the churn panels: the bars fill the whole box
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 360;
  const H = size?.h ?? 180;

  const shares = SEGMENT_KEYS.map((name) => ({
    label: name,
    value: payload.scalars.recommended_arm_shares[name === "Mens E-Mail" ? "mens" : name === "Womens E-Mail" ? "womens" : "none"],
    color: SEGMENT_COLORS[name],
  }));
  const conv = SEGMENT_KEYS.map((name) => ({
    label: name,
    value: payload.segments[name].conversion_rate,
    color: SEGMENT_COLORS[name],
  }));
  // static maxima (never 1.0): both bar groups keep a stable scale
  const shareMax = Math.max(...shares.map((s) => s.value), 0.01);
  const convMax = Math.max(...conv.map((s) => s.value), 0.001);

  const pad = 12;
  const labelW = Math.min(104, W * 0.34);
  const valueW = 46;
  const barX = pad + labelW + 6;
  const barW = Math.max(W - barX - valueW - pad - 10, 0);
  const rowH = H / (shares.length + conv.length);

  const rows = [
    ...shares.map((s) => ({ ...s, frac: s.value / shareMax, text: fmtPct(s.value) })),
    ...conv.map((s) => ({ ...s, frac: s.value / convMax, text: `${(s.value * 100).toFixed(2)}%` })),
  ];

  return (
    <Figure
      comment={
        <>
          Arm assignment from the per-customer uplift scores — {fmtPct(shares[0].value)} get the
          men's creative, {fmtPct(shares[1].value)} the women's, {fmtPct(shares[2].value)} no
          email; the lower bars are each segment's observed conversion rate in the experiment.
        </>
      }
    >
      <div ref={ref} className="wb-panel-viz">
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          role="img"
          aria-label="recommended arm shares and segment conversion rates"
        >
          {rows.map((r, i) => {
            const cy = rowH * i + rowH / 2;
            const isConv = i >= shares.length;
            return (
              <g key={`${r.label}-${i}`}>
                <text x={pad} y={cy + 3} className="demo-axis-label">
                  {isConv ? `${r.label} conv.` : r.label}
                </text>
                <rect
                  x={barX}
                  y={cy - 7}
                  width={barW}
                  height={14}
                  fill="var(--bg)"
                  stroke="var(--border)"
                />
                <rect
                  x={barX}
                  y={cy - 7}
                  width={Math.max(r.frac * barW, 0)}
                  height={14}
                  fill={r.color}
                  opacity={0.85}
                />
                <text x={W - pad} y={cy + 3} textAnchor="end" className="demo-axis-label">
                  {r.text}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </Figure>
  );
}

// --- notice tiles -----------------------------------------------------------------------

/** Crossover tile: names the winner vs mail-everyone-mens at the current cost. */
function CrossoverText({
  costLabel,
  bestProfit,
  meMens,
}: {
  costLabel: string;
  bestProfit: number;
  meMens: number;
}) {
  const delta = bestProfit - meMens;
  if (delta >= 0) {
    return (
      <>
        At <strong>{costLabel}</strong>, best-arm targeting beats mailing everyone by{" "}
        <strong>{fmtMoney(delta)}</strong> at this budget
      </>
    );
  }
  return (
    <>
      At <strong>{costLabel}</strong>, mailing everyone wins — targeting can't pay for itself at
      this budget
    </>
  );
}

/** Peak tile: where the frontier tops out at the current cost. */
function PeakText({ costLabel, peak }: { costLabel: string; peak: number }) {
  return (
    <>
      The profit peak at <strong>{costLabel}</strong> sits near{" "}
      <strong>{Math.round(peak * 100)}%</strong> targeting
    </>
  );
}

// --- demo ------------------------------------------------------------------------------

export default function UpliftSimulator() {
  const [manifest, setManifest] = useState<DemoManifest | null>(null);
  const [payload, setPayload] = useState<UpliftPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchManifest("uplift-simulator")
      .then((m) => !cancelled && setManifest(m))
      .catch(() => {
        /* payload fetch below reports the real error */
      });
    fetchUpliftPayload("uplift-simulator")
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
  return <UpliftSimulatorWorkbench manifest={manifest ?? FALLBACK_MANIFEST} payload={payload} />;
}

/** Workbench body once the payload (and manifest, or fallback) is in hand. */
function UpliftSimulatorWorkbench({
  manifest,
  payload,
}: {
  manifest: DemoManifest;
  payload: UpliftPayload;
}) {
  const state = useControlState({ cost: 0.05, budget: 0.25 }, manifest.scenarios);
  const { controls, setControl } = state;
  const cost = controls.cost ?? 0.05;
  const budget = controls.budget ?? 0.25;

  const grid = payload.profit_grid;
  const costIdx = nearestIndex(grid.costs, cost);
  const fracIdx = nearestIndex(grid.fractions, budget);
  const latticeCost = grid.costs[costIdx];
  const fraction = grid.fractions[fracIdx];
  const costLabel = `$${latticeCost.toFixed(2)}/email`;

  const bestProfit = profitAt(grid, costIdx, fracIdx);
  const randProfit = policyProfitAt(grid, "random", costIdx, fracIdx);
  const meMens = mailEveryoneAt(payload.scalars.mail_everyone_profit.mens, latticeCost);
  const inc = incrementalAt(
    bestProfit,
    fraction,
    latticeCost,
    payload.n_customers,
    payload.scalars.revenue_per_conversion,
  );
  const be = payload.scalars.break_even;

  return (
    <DemoWorkbench
      manifest={manifest}
      state={state}
      controls={
        <>
          <div className="wb-control-group wb-group-slider">
            <label className="wb-rail-title" htmlFor="send-cost">
              Cost per email
            </label>
            <div className="demo-control">
              <div className="wb-slider-row">
                <input
                  id="send-cost"
                  type="range"
                  className="wb-slider"
                  min={0.01}
                  max={0.5}
                  step={0.01}
                  value={latticeCost}
                  style={
                    {
                      "--fill": `${((latticeCost - 0.01) / 0.49) * 100}%`,
                    } as CSSProperties
                  }
                  onChange={(e) => setControl("cost", Number(e.target.value))}
                />
                <span className="chip wb-value-badge">${latticeCost.toFixed(2)}</span>
              </div>
            </div>
          </div>
          <div className="wb-control-group">
            <span className="wb-rail-title">Targeting budget</span>
            <div className="demo-control">
              <p className="demo-hint">
                Drag the pink cursor on the frontier — the budget chip, the KPIs and both notice
                tiles follow. Scenario presets load via the URL (?cost=&budget=).
              </p>
            </div>
          </div>
        </>
      }
      canvas={
        <FrontierPanel
          payload={payload}
          cost={cost}
          budget={budget}
          onBudget={(f) => setControl("budget", f)}
        />
      }
      kpis={
        <>
          <KpiTile
            label="profit at budget"
            value={fmtMoney(bestProfit)}
            sub={`vs random +${fmtMoney(bestProfit - randProfit)} · 95% CI band`}
          />
          <KpiTile
            label="incremental conversions"
            value={String(Math.round(inc))}
            sub={`model-estimated · revenue $${payload.scalars.revenue_per_conversion}/conversion`}
          />
          <KpiTile
            label="break-even"
            value={`$${be.multi_arm_best_arm.cost_per_email.toFixed(2)}`}
            sub={`committed two-arm $${be.two_arm_committed.cost_per_email.toFixed(2)} · best-arm $${be.multi_arm_best_arm.cost_per_email.toFixed(2)}`}
          />
          <KpiTile
            label="customers targeted"
            value={Math.round(payload.n_customers * fraction).toLocaleString("en-US")}
            sub={`of ${payload.n_customers.toLocaleString("en-US")} scored customers`}
          />
        </>
      }
      notice={
        <>
          <Notice>
            <CrossoverText costLabel={costLabel} bestProfit={bestProfit} meMens={meMens} />
          </Notice>
          <Notice>
            <PeakText costLabel={costLabel} peak={peakFractionAt(grid, costIdx)} />
          </Notice>
        </>
      }
      secondary={
        <>
          <div className="wb-secondary-panel">
            <h3 className="wb-rail-title">qini curves per arm</h3>
            <QiniPanel payload={payload} />
          </div>
          <div className="wb-secondary-panel">
            <h3 className="wb-rail-title">cost sensitivity at budget</h3>
            <CostPanel payload={payload} cost={cost} budget={budget} />
          </div>
          <div className="wb-secondary-panel">
            <h3 className="wb-rail-title">recommended-arm mix</h3>
            <ArmMixPanel payload={payload} />
          </div>
        </>
      }
      evidence={
        <>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">models used</h4>
            <p className="wb-evidence-line">
              Two per-arm T-learners score every customer for the men's and women's creative; the
              best-arm policy assigns the higher predicted uplift, no e-mail when both are
              negative — {payload.n_customers.toLocaleString("en-US")} committed cross-fitted
              scores.
            </p>
            <p className="wb-evidence-line">
              Frontier CIs are a paired row bootstrap ({payload.profit_grid.n_boot} reps,
              percentile 95%, one shared resample per replication) over the cost × fraction
              lattice.
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">metrics results</h4>
            <p className="wb-evidence-line wb-metric-tags">
              <span className="wb-tag">
                qini mens {payload.scalars.per_arm_qini.mens.qini_coefficient.toFixed(2)}
              </span>
              <span className="wb-tag">
                qini womens {payload.scalars.per_arm_qini.womens.qini_coefficient.toFixed(2)}
              </span>
              <span className="wb-tag">
                break-even ${be.multi_arm_best_arm.cost_per_email.toFixed(2)}
              </span>
            </p>
            <p className="wb-evidence-line wb-metric-tags">
              <span className="wb-tag">arm mens {fmtPct(payload.scalars.recommended_arm_shares.mens)}</span>
              <span className="wb-tag">
                arm womens {fmtPct(payload.scalars.recommended_arm_shares.womens)}
              </span>
              <span className="wb-tag">arm none {fmtPct(payload.scalars.recommended_arm_shares.none)}</span>
            </p>
          </div>
        </>
      }
      about={
        <>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">what this shows</h4>
            <p className="wb-evidence-line">
              The profit frontier trades reach against send cost as the targeting budget moves —
              the best fraction to target shifts with the <strong>cost per email</strong>, and the
              dashed mail-everyone lines mark the no-modeling alternative at the same cost.
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">the experiment</h4>
            <p className="wb-evidence-line">
              A randomized multi-arm e-mail experiment (men's vs women's creative vs no e-mail);
              the target is to maximize campaign profit{" "}
              <span className="wb-tag">
                conversions × ${payload.scalars.revenue_per_conversion} − emails × cost
              </span>{" "}
              over {payload.n_customers.toLocaleString("en-US")} customers.
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">honest caveats</h4>
            <p className="wb-evidence-line">{payload.scalars.model_estimated_note}</p>
            <p className="wb-evidence-line">
              Policy-level profit is model-estimated, so the frontier CIs are bootstrap spreads of
              a model read, not observed counterfactuals.
            </p>
          </div>
        </>
      }
    />
  );
}
