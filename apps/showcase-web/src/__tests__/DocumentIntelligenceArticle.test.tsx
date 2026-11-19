import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { DocumentIntelligenceArticle } from "../pages/DocumentIntelligenceArticle";

describe("DocumentIntelligenceArticle committed-result table (H4)", () => {
  it("renders the live-result table through the shared markdown table path", () => {
    render(
      <MemoryRouter>
        <DocumentIntelligenceArticle />
      </MemoryRouter>,
    );
    // the committed table content is present…
    expect(screen.getByText("0.677 / 0.500")).toBeInTheDocument();
    // …inside the shared table chrome, not a raw prose <table>
    const cell = screen.getByText("0.677 / 0.500");
    const table = cell.closest("table");
    expect(table).not.toBeNull();
    expect(table!.className).toBe("data-table");
    expect(table!.parentElement!.className).toBe("table-scroll");
  });
});
