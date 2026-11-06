import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { About } from "../pages/About";
import { AgentChatArticle } from "../pages/AgentChatArticle";
import { Contact } from "../pages/Contact";
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
    expect(indexHrefs()).toEqual(["#how-i-work", "#experience"]);
    expect(document.getElementById("how-i-work")).not.toBeNull();
    expect(document.getElementById("experience")).not.toBeNull();
  });

  it("indexes inquiry, the free call, and engagement start", () => {
    render(<MemoryRouter><Contact /></MemoryRouter>);
    expect(indexHrefs()).toEqual(["#inquiry", "#free-call", "#engagement-start"]);
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
    expect(document.querySelector('img[src="/apps/agent-chat-memory.png"]')).not.toBeNull();
    expect(document.querySelectorAll(".app-spec-card")).toHaveLength(4);
    expect(document.querySelectorAll("pre.code-block")).toHaveLength(5);
    expect(screen.getAllByText("In plain terms")).toHaveLength(8);
    const video = document.querySelector("video")!;
    expect(video).toHaveAttribute("controls");
    expect(video).toHaveAttribute("preload", "metadata");
    expect(video.querySelector('source[src="/apps/agent-chat-demo.webm"]')).not.toBeNull();
    expect(screen.getByText(/13-case suite/)).toBeInTheDocument();
    expect(screen.getByText(/single-agent chassis/)).toBeInTheDocument();
  });
});
