import { Card } from "../components/Card";
import { FRAMEWORKS } from "../components/Frameworks";
import { CONTACT_EMAIL, SITE_NAME } from "../config";
import { usePageMeta } from "../seo";

/** Concrete working practices, distilled from the repository's engineering
 * playbook (docs/engineering-playbook.md) — each one enforced by tooling, not
 * by goodwill. */
const PRACTICES = [
  {
    title: "reproducible pipelines",
    text: "Every result rebuilds from a clean state with dvc repro — no notebook ghosts, no \"works on my machine\".",
  },
  {
    title: "pinned data with checksums",
    text: "Dataset cards pin source, license, checksum and snapshot date. Raw data never enters git; DVC tracks the rest.",
  },
  {
    title: "honest baselines",
    text: "Every model is scored against a named naive baseline — seasonal-naive, majority, random — and the delta is stated, not implied.",
  },
  {
    title: "scored-once evaluation",
    text: "Evaluation runs in CI against a pinned holdout. A model that was never evaluated cannot ship; a metric that changed is flagged.",
  },
  {
    title: "drift & data-quality gates",
    text: "Data-quality checks halt pipelines loudly — non-zero exit plus a persisted report — instead of quietly degrading downstream numbers.",
  },
  {
    title: "tested code",
    text: "pytest plus hypothesis property tests on every validator, with coverage gates. A bug fix without a regression test is not a fix.",
  },
  {
    title: "typed contracts",
    text: "Pydantic models at every cross-module boundary and mypy strict in the shared libraries — config is a schema, not a guess.",
  },
  {
    title: "honest limits",
    text: "Every evaluation report states what the case study does not establish, including the conditions under which the conclusions break.",
  },
];

export function About() {
  usePageMeta({
    title: "About",
    description:
      "Independent ML/AI consultant — who does the work, the engineering practices behind every case study (reproducible pipelines, pinned data, scored-once evaluation, honest limits), and the stack.",
    canonical: "/about",
  });

  return (
    <>
      <section className="services-hero">
        <p className="kicker">&gt; about</p>
        <h1>Independent ML/AI consultant</h1>
        <p>
          I design, build and evaluate ML systems end to end, and I keep the code, metrics
          and case studies public and auditable — the same working standards run through
          every engagement.
        </p>
        <p>
          The public experiments on this site are the sample: real datasets, measured
          baselines, published pipelines, and limits stated in every report. Reach me at{" "}
          <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
        </p>
      </section>

      <h2 className="section-title">how the work is done</h2>
      <p className="section-intro">
        Eight practices from the repository's engineering playbook — enforced by tooling,
        not by goodwill.
      </p>
      <div className="practices-grid">
        {PRACTICES.map((p, i) => (
          <Card key={p.title} className="practice-card">
            <h3>
              <span className="practice-num">{String(i + 1).padStart(2, "0")}</span>{" "}
              {p.title}
            </h3>
            <p>{p.text}</p>
          </Card>
        ))}
      </div>

      <h2 className="section-title">stack</h2>
      <p className="section-intro">
        Chosen for reproducibility and longevity — the same stack the case studies run on.
      </p>
      <div className="chips about-stack">
        {FRAMEWORKS.map((f) => (
          <span key={f.name} className="chip">
            {f.name}
          </span>
        ))}
      </div>

      <p className="license-line">© 2026 {SITE_NAME} · MIT licensed</p>
    </>
  );
}
