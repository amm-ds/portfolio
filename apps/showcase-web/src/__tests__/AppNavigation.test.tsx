import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { readStylesCss } from "./helpers/css";
import { About } from "../pages/About";
import { AgentChatArticle } from "../pages/AgentChatArticle";
import { Contact } from "../pages/Contact";
import { DocumentIntelligenceArticle } from "../pages/DocumentIntelligenceArticle";
import { Glossary } from "../pages/Glossary";
import { Services } from "../pages/Services";

function indexHrefs(): string[] {
  return [...screen.getByRole("navigation", { name: "On this page" }).querySelectorAll("a")].map(
    (anchor) => anchor.getAttribute("href") ?? "",
  );
}

afterEach(cleanup);

describe("shared page indexes", () => {
  it("indexes every services section", () => {
    render(<MemoryRouter><Services /></MemoryRouter>);
    expect(indexHrefs()).toEqual([
      "#offerings",
      "#frameworks",
      "#cloud-deployment",
      "#process",
      "#engagement-models",
    ]);
    for (const id of ["offerings", "frameworks", "cloud-deployment", "process", "engagement-models"]) {
      expect(document.getElementById(id)).not.toBeNull();
    }
  });

  it("indexes the about sections", () => {
    render(<MemoryRouter><About /></MemoryRouter>);
    expect(indexHrefs()).toEqual(["#how-i-work", "#ai-disclosure", "#experience"]);
    expect(document.getElementById("how-i-work")).not.toBeNull();
    expect(document.getElementById("ai-disclosure")).not.toBeNull();
    expect(document.getElementById("experience")).not.toBeNull();
  });

  it("indexes inquiry, the free call, and engagement start", () => {
    render(<MemoryRouter><Contact /></MemoryRouter>);
    expect(indexHrefs()).toEqual(["#direct", "#inquiry", "#free-call", "#engagement-start"]);
    expect(document.getElementById("direct")).not.toBeNull();
    expect(document.getElementById("inquiry")).not.toBeNull();
    expect(document.getElementById("free-call")).not.toBeNull();
    expect(document.getElementById("engagement-start")).not.toBeNull();
  });

  it("indexes both glossary groups", () => {
    render(<MemoryRouter><Glossary /></MemoryRouter>);
    expect(indexHrefs()).toEqual(["#core-keywords", "#experiment-specific"]);
    expect(document.getElementById("core-keywords")).not.toBeNull();
    expect(document.getElementById("experiment-specific")).not.toBeNull();
  });
});

describe("AgentChatArticle", () => {
  it("presents architecture, screenshots, evaluation, specs, and adaptation guidance", () => {
    render(<MemoryRouter><AgentChatArticle /></MemoryRouter>);

    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "Chatbot agent — production template",
    );
    expect(screen.getByRole("navigation", { name: "App article sections" }).querySelectorAll("a")).toHaveLength(8);
    expect(screen.getByRole("heading", { name: /Architecture$/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Evaluation$/ })).toBeInTheDocument();
    expect(document.querySelectorAll(".app-screenshot img")).toHaveLength(3);
    expect(document.querySelector('img[src="/apps/agent-chat-memory-v3.png"]')).not.toBeNull();
    expect(document.querySelectorAll(".app-spec-card")).toHaveLength(4);
    expect(document.querySelectorAll("pre.code-block")).toHaveLength(5);
    expect(screen.getAllByText("tl;dr")).toHaveLength(8);
    const video = document.querySelector("video")!;
    expect(video).toHaveAttribute("controls");
    expect(video).toHaveAttribute("preload", "metadata");
    expect(video).toHaveAttribute("poster", "/apps/agent-chat-ui-v3.png");
    expect(video.querySelector('source[src="/apps/agent-chat-demo.webm"]')).not.toBeNull();
    expect(video.querySelector('source[src="/apps/agent-chat-demo.mp4"]')).not.toBeNull();
    expect(screen.getByText(/16-case suite/)).toBeInTheDocument();
    expect(screen.getByText(/last 10 user turns/)).toBeInTheDocument();
    expect(document.body.textContent).toContain("sessionStorage");
    expect(document.body.textContent).toContain("preferred_cloud");
    expect(screen.getByText(/authenticated principal/)).toBeInTheDocument();
    expect(screen.getByText(/single-agent chassis/)).toBeInTheDocument();
    expect(document.body.textContent).toContain("108/108 assertions passed in each of three repetitions.");
    expect(document.body.textContent).toContain("UseThreadExecutor");
    expect(document.body.textContent).toContain("reports liveness plus the configured provider");
    expect(document.body.textContent).toContain("content exclusion");
    expect(screen.getByRole("link", { name: "native deferred tools" })).toHaveAttribute(
      "href",
      "https://ai.pydantic.dev/deferred-tools/",
    );
    expect(screen.getByRole("link", { name: "observability guidance" })).toHaveAttribute(
      "href",
      "https://ai.pydantic.dev/observability/",
    );
  });

  it("styles code as padded terminal cards and keeps spec text and images contained", () => {
    const css = readStylesCss();
    expect(css.match(/\.code-block \{\n  display: block;[\s\S]*?\n\}/)![0]).toContain("padding: 1rem 1.25rem;");
    expect(css.match(/\.app-spec-card \{[\s\S]*?\n\}/)![0]).toContain("padding: 1.25rem 1.4rem;");
    expect(css.match(/\.app-screenshot img \{[\s\S]*?\n\}/)![0]).toContain("height: 440px;");
    expect(css.match(/\.app-screenshot img \{[\s\S]*?\n\}/)![0]).toContain("object-fit: contain;");
    expect(css.match(/\.detail-header \.chips \.chip \{[\s\S]*?\n\}/)![0]).toContain(
      "color: var(--chip-blue-text);",
    );
    expect(css.match(/\.detail-header \.domain \{[\s\S]*?\n\}/)![0]).toContain("color: var(--accent-bright);");
  });
});

describe("DocumentIntelligenceArticle", () => {
  it("presents the application, evidence boundary, evaluation, and specs", () => {
    render(<MemoryRouter><DocumentIntelligenceArticle /></MemoryRouter>);

    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "AI Document Intelligence Workbench",
    );
    expect(screen.getByRole("navigation", { name: "App article sections" }).querySelectorAll("a")).toHaveLength(8);
    expect(screen.getByRole("heading", { name: /Evidence & performance$/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Evaluation$/ })).toBeInTheDocument();
    expect(document.querySelectorAll(".app-screenshot img")).toHaveLength(2);
    expect(document.querySelector('img[src="/apps/document-intelligence-summary.png"]')).not.toBeNull();
    expect(document.querySelector('img[src="/apps/document-intelligence-qa.png"]')).not.toBeNull();
    expect(document.querySelector('link[rel="canonical"]')).toHaveAttribute(
      "href",
      "https://alejandromerida.dev/apps/document-intelligence",
    );
    expect(document.title).toContain("AI Document Intelligence Workbench");
    expect(document.querySelectorAll(".app-spec-card")).toHaveLength(4);
    expect(document.querySelectorAll("pre.code-block")).toHaveLength(4);
    expect(screen.getAllByText("tl;dr")).toHaveLength(8);
    expect(document.body.textContent).toContain("page-level scorecards");
    expect(document.body.textContent).toContain("per-page misses");
    expect(document.body.textContent).toContain("Offline fixtures verify the application path");
  });
});
