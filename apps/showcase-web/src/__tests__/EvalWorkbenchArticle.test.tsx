import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { EvalWorkbenchArticle } from "../pages/EvalWorkbenchArticle";

describe("EvalWorkbenchArticle", () => {
  it("renders the five-section article, architecture, screenshot, and honest limits", () => {
    render(<MemoryRouter><EvalWorkbenchArticle /></MemoryRouter>);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Eval Workbench");
    expect(screen.getByRole("navigation", { name: "App article sections" }).querySelectorAll("a")).toHaveLength(5);
    expect(screen.getByRole("heading", { name: /Architecture$/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Evaluation$/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Results$/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Conclusions$/ })).toBeInTheDocument();
    expect(document.querySelector('img[src="/apps/eval-workbench.png"]')).not.toBeNull();
    expect(screen.getAllByText("tl;dr")).toHaveLength(5);
    expect(document.body.textContent).toContain("not live model-quality evidence");
    expect(document.body.textContent).toContain("No weighted overall score");
    expect(document.querySelector('link[rel="canonical"]')).toHaveAttribute(
      "href",
      "https://alejandromerida.dev/apps/eval-workbench",
    );
  });
});
