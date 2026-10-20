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
    id: "churn-sandbox",
    title: "churn threshold sandbox",
    line: "Move the alarm threshold and the false-alarm cost — watch the optimal cutoff and the saved budget change on a real churn model.",
    status: "live",
    href: "/demos/churn-sandbox",
  },
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
    id: "uplift-policy",
    title: "uplift policy simulator",
    line: "Compare targeting policies against mail-everyone on the Hillstrom outcome data.",
    status: "coming soon",
  },
];

export const DEMOS_INTRO = "play with the live systems behind the experiments";

/** Project id → live demo route, for the "try the live demo" link on a
 *  project detail page. Add an entry here when a demo goes live. */
export const DEMO_LINKS: Record<string, string> = {
  "05-ml-pipeline-churn": "/demos/churn-sandbox",
};
