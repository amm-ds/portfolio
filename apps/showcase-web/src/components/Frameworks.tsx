import { useState } from "react";

export interface Framework {
  name: string;
  url: string;
  /** Local SVG under /logos (self-hosted, see public/logos/README.md);
   *  absent → render the letter tile directly. */
  logo?: string;
  /** Icon backdrop: colored brand icons sit on a light chip; white-only marks
   * (pydantic-ai) need the dark chip to stay visible. */
  logoBg?: "light" | "dark";
  letters: string;
}

export const FRAMEWORKS: Framework[] = [
  { name: "pydantic", url: "https://pydantic.dev", logo: "/logos/pydantic.svg", letters: "Pd" },
  { name: "pydantic-ai", url: "https://ai.pydantic.dev", logo: "/logos/pydantic-ai.svg", logoBg: "dark", letters: "PA" },
  { name: "Ollama", url: "https://ollama.com", logo: "/logos/ollama.svg", letters: "Ol" },
  { name: "scikit-learn", url: "https://scikit-learn.org", logo: "/logos/scikitlearn.svg", letters: "Sk" },
  { name: "PyTorch", url: "https://pytorch.org", logo: "/logos/pytorch.svg", letters: "Pt" },
  { name: "Polars", url: "https://pola.rs", logo: "/logos/polars.svg", letters: "Pl" },
  { name: "DuckDB", url: "https://duckdb.org", logo: "/logos/duckdb.svg", letters: "Db" },
  { name: "Plotly", url: "https://plotly.com", logo: "/logos/plotly.svg", letters: "Py" },
  { name: "DVC", url: "https://dvc.org", logo: "/logos/dvc.svg", letters: "Dv" },
  { name: "uv", url: "https://docs.astral.sh/uv", logo: "/logos/uv.svg", letters: "uv" },
  { name: "FastAPI", url: "https://fastapi.tiangolo.com", logo: "/logos/fastapi.svg", letters: "Fa" },
  { name: "React", url: "https://react.dev", logo: "/logos/react.svg", letters: "Re" },
  { name: "TypeScript", url: "https://typescriptlang.org", logo: "/logos/typescript.svg", letters: "Ts" },
  { name: "Optuna", url: "https://optuna.org", logo: "/logos/optuna.svg", letters: "Op" },
  { name: "RAGAS", url: "https://ragas.io", logo: "/logos/ragas.svg", letters: "Ra" },
  { name: "pydantic-evals", url: "https://ai.pydantic.dev/evals/", letters: "Pe" },
  { name: "Hugging Face", url: "https://huggingface.co", logo: "/logos/huggingface.svg", letters: "Hf" },
];

/** One framework logo tile; degrades to a mono initial-letter tile if the image fails. */
export function FrameworkTile({ fw }: { fw: Framework }) {
  const [imgFailed, setImgFailed] = useState(false);
  const src = fw.logo ?? null;
  return (
    <a
      className="framework-tile"
      href={fw.url}
      target="_blank"
      rel="noreferrer"
      title={fw.name}
      aria-label={fw.name}
    >
      {src && !imgFailed ? (
        <span
          className={`framework-icon${fw.logoBg === "dark" ? " framework-icon--dark" : ""}`}
        >
          <img
            src={src}
            alt={`${fw.name} logo`}
            width={18}
            height={18}
            loading="lazy"
            onError={() => setImgFailed(true)}
          />
        </span>
      ) : (
        <span className="framework-letters">{fw.letters}</span>
      )}
      <span className="framework-name">{fw.name}</span>
    </a>
  );
}

/** Deployment providers — same tile pattern as frameworks. Every icon is
 * served from a self-hosted SVG under /logos (see public/logos/README.md):
 * the production CSP blocks third-party CDNs, and the Simple Icons copies
 * are CC0-licensed, so nothing hotlinks brand art anymore. AWS and Azure
 * keep their local copies because their brand icons were removed from Simple
 * Icons (no CC0 source); RAGAS / pydantic-ai never had entries. */
export const PROVIDERS: Framework[] = [
  { name: "AWS", url: "https://aws.amazon.com", logo: "/logos/aws.svg", logoBg: "dark", letters: "Aw" },
  { name: "Microsoft Azure", url: "https://azure.microsoft.com", logo: "/logos/azure.svg", letters: "Az" },
  { name: "Google Cloud", url: "https://cloud.google.com", logo: "/logos/googlecloud.svg", letters: "Gc" },
  { name: "Docker", url: "https://docker.com", logo: "/logos/docker.svg", letters: "Dk" },
];
