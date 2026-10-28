import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getDemoRegistry } from "../api";
import type { DemoRegistryEntry } from "../demos/types";
import { DEMOS } from "../lib/demos";

const FEATURED_IDS = ["forecast-workbench", "churn-sandbox"];

function staticFeatured(): DemoRegistryEntry[] {
  return DEMOS.filter((d) => FEATURED_IDS.includes(d.id)).map((d) => ({
    id: d.id,
    title: d.title,
    hook: d.line,
    group: "",
    href: d.href ?? "",
    project: "",
    status: d.status,
    hero: null,
  }));
}

/** Two featured demo cards (forecast workbench + churn sandbox) from the live
 * registry, falling back to the static list when the API is unreachable.
 * Each card links straight into its demo. */
export function FeaturedDemos() {
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

  const source = entries ?? staticFeatured();
  const featured = FEATURED_IDS.map(
    (id) => source.find((e) => e.id === id) ?? staticFeatured().find((e) => e.id === id)!,
  ).filter((e) => e.href !== "");

  return (
    <section aria-label="Featured demos">
      <h2 className="section-title">featured demos</h2>
      <div className="go-grid">
        {featured.map((d) => (
          <Link key={d.id} to={d.href} className="go-card accent-card">
            <h3>$ {d.title} →</h3>
            <p>{d.hook}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
