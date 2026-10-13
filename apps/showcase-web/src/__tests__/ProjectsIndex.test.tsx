import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectsIndex } from "../pages/ProjectsIndex";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ProjectsIndex", () => {
  it("renders the project grid sorted by order", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse([
          {
            id: "02-demand-forecasting",
            title: "Demand Forecasting",
            domain: "time series",
            techniques: ["LightGBM"],
            data: "retail",
            status: "working",
            order: 2,
          },
          {
            id: "01-rag-agent",
            title: "RAG Agent",
            domain: "NLP",
            techniques: ["RAG"],
            data: "docs",
            status: "flagship",
            order: 1,
          },
        ]),
      ),
    );
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("RAG Agent")).toBeInTheDocument());
    const titles = [...document.querySelectorAll(".project-card h3")].map(
      (el) => el.textContent,
    );
    expect(titles).toEqual(["RAG Agent", "Demand Forecasting"]);
    expect(screen.getByText("[flagship]")).toBeInTheDocument();
    // live-demo banner links to the RAG chat
    const demo = screen.getByRole("link", { name: /RAG demo/i });
    expect(demo.getAttribute("href")).toBe("/chat");
  });

  it("shows an error state when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    render(
      <MemoryRouter>
        <ProjectsIndex />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/could not load/i)).toBeInTheDocument());
  });
});
