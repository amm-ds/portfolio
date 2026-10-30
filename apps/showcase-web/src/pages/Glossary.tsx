import glossary from "../lib/glossary.json";
import { Terminal } from "../components/Terminal";
import { usePageMeta } from "../seo";

/**
 * Plain-language glossary of the evaluation terms used across the case
 * studies. Terms prose auto-links to (`/glossary#<slug>`) point here; each
 * entry keeps its definition under 25 words plus one concrete example.
 */
export function Glossary() {
  usePageMeta({
    title: "Glossary",
    description:
      "Plain-language definitions — with examples — for the evaluation terms used across the case studies: baselines, holdouts, WAPE, MASE, uplift, and more.",
    canonical: "/glossary",
  });

  return (
    <div className="glossary-page">
      <h1>Glossary</h1>
      <p>
        The evaluation terms the case studies use, defined in plain language.
        Terms are linked from story prose at their first occurrence.
      </p>
      <Terminal title="glossary — plain-language definitions">
        <dl className="glossary-list">
          {glossary.map((entry) => (
            <div className="glossary-entry" key={entry.slug}>
              <dt id={entry.slug} className="glossary-term-name">
                {entry.term}
              </dt>
              <dd className="glossary-def">
                <p>{entry.definition}</p>
                <p className="glossary-example">
                  <span className="glossary-example-label">example:</span> {entry.example}
                </p>
              </dd>
            </div>
          ))}
        </dl>
      </Terminal>
    </div>
  );
}
