/** Interactive demo placeholders for the projects page (demos block). Rendered as
 * non-interactive cards above the experiments rows; swap `href` in later and mark
 * `status: "live"` — the layout reads from this list, so demos drop in
 * without page changes. */
export interface Demo {
  id: string;
  title: string;
  line: string;
  status: "coming soon" | "live";
  /** Target route once live; undefined while the demo is a placeholder. */
  href?: string;
}

export const DEMOS: Demo[] = [
  {
    id: "tape-forecast",
    title: "btc orderflow lab",
    line: "Replay a $3.5B liquidation flush on the BTC tape — volume candles, CVD, volume profile — and see ML beat GARCH at volatility forecasting, with honest numbers where it doesn't.",
    status: "live",
    href: "/demos/tape-forecast/",
  },
  {
    id: "rag-ask",
    title: "RAG ask-a-question",
    line: "Query the retrieval corpus and watch the agent verify claims against sources.",
    status: "coming soon",
  },
  {
    id: "churn-threshold",
    title: "churn threshold sandbox",
    line: "Move the campaign cutoff and see cost per retained customer update live.",
    status: "coming soon",
  },
  {
    id: "uplift-policy",
    title: "uplift policy simulator",
    line: "Compare targeting policies against mail-everyone on the Hillstrom outcome data.",
    status: "coming soon",
  },
];

export const DEMOS_INTRO = "play with the live systems behind the experiments";
