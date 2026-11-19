import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AGENT_EVAL_SUMMARY } from "../lib/agentChatEvalSummary";
import { AgentChatArticle } from "../pages/AgentChatArticle";

describe("AgentChatArticle eval summary table (H5)", () => {
  it("renders a summary whose totals match the committed report", () => {
    render(
      <MemoryRouter>
        <AgentChatArticle />
      </MemoryRouter>,
    );
    const summary = AGENT_EVAL_SUMMARY;
    expect(summary.totalPassed).toBe(108);
    expect(summary.totalAssertions).toBe(108);
    expect(summary.executions).toBe(48);
    // per-kind rows come from the generated module and add up to the totals
    const kinds = summary.byKind.map((k) => k.kind).join(",");
    expect(kinds).toBe("answer,refuse,tool_choice");
    expect(summary.byKind.reduce((n, k) => n + k.assertions, 0)).toBe(108);
    // the rendered table carries the shared chrome and the totals row
    const total = screen.getByText(
      `total (${summary.cases} cases × ${summary.repetitions} repetitions)`,
    );
    const table = total.closest("table");
    expect(table).not.toBeNull();
    // DataTable carries the shared chrome on its wrapper div
    expect(table!.className).toBe("");
    expect(table!.parentElement!.className).toBe("table-scroll data-table");
    expect(table!.textContent).toContain("63");
    expect(table!.textContent).toContain("108/108");
  });
});
