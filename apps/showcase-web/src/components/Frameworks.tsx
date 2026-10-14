import { useState } from "react";

export interface Framework {
  name: string;
  url: string;
  /** simpleicons slug; absent → render the letter tile directly. */
  slug?: string;
  letters: string;
}

export const FRAMEWORKS: Framework[] = [
  { name: "pydantic", url: "https://pydantic.dev", slug: "pydantic", letters: "Pd" },
  { name: "pydantic-ai", url: "https://ai.pydantic.dev", letters: "PA" },
  { name: "scikit-learn", url: "https://scikit-learn.org", slug: "scikitlearn", letters: "Sk" },
  { name: "PyTorch", url: "https://pytorch.org", slug: "pytorch", letters: "Pt" },
  { name: "Polars", url: "https://pola.rs", slug: "polars", letters: "Pl" },
  { name: "Plotly", url: "https://plotly.com", slug: "plotly", letters: "Py" },
  { name: "DVC", url: "https://dvc.org", slug: "dvc", letters: "Dv" },
  { name: "uv", url: "https://docs.astral.sh/uv", slug: "uv", letters: "uv" },
  { name: "FastAPI", url: "https://fastapi.tiangolo.com", slug: "fastapi", letters: "Fa" },
  { name: "React", url: "https://react.dev", slug: "react", letters: "Re" },
  { name: "TypeScript", url: "https://typescriptlang.org", slug: "typescript", letters: "Ts" },
  { name: "Optuna", url: "https://optuna.org", slug: "optuna", letters: "Op" },
  { name: "Hugging Face", url: "https://huggingface.co", slug: "huggingface", letters: "Hf" },
];

/** One framework logo tile; degrades to a mono initial-letter tile if the CDN image fails. */
export function FrameworkTile({ fw }: { fw: Framework }) {
  const [imgFailed, setImgFailed] = useState(false);
  return (
    <a
      className="framework-tile"
      href={fw.url}
      target="_blank"
      rel="noreferrer"
      title={fw.name}
      aria-label={fw.name}
    >
      {fw.slug && !imgFailed ? (
        <img
          src={`https://cdn.simpleicons.org/${fw.slug}`}
          alt=""
          loading="lazy"
          onError={() => setImgFailed(true)}
        />
      ) : (
        <span className="framework-letters">{fw.letters}</span>
      )}
      <span className="framework-name">{fw.name}</span>
    </a>
  );
}

/** Deployment providers — same tile pattern as frameworks. */
export const PROVIDERS: Framework[] = [
  { name: "AWS", url: "https://aws.amazon.com", slug: "amazonaws", letters: "Aw" },
  { name: "Microsoft Azure", url: "https://azure.microsoft.com", slug: "microsoftazure", letters: "Az" },
  { name: "Google Cloud", url: "https://cloud.google.com", slug: "googlecloud", letters: "Gc" },
  { name: "Docker", url: "https://docker.com", slug: "docker", letters: "Dk" },
];
