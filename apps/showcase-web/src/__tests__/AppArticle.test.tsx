import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AppArticleSection } from "../components/AppArticle";

describe("AppArticleSection", () => {
  it("renders the numbered section title with a real space (H2)", () => {
    render(
      <AppArticleSection
        id="sec-eval"
        index={7}
        title="Evaluation"
        subtitle="graded against the committed report"
        takeaway="all graders pass"
      >
        <p>body</p>
      </AppArticleSection>,
    );
    const heading = screen.getByRole("heading", { level: 2 });
    expect(heading.textContent).toBe("07 Evaluation");
    // the space must be a text node, not just CSS margin
    expect(heading.textContent).toContain("07 ");
  });

  it("keeps the subtitle on the muted class hook (H3)", () => {
    render(
      <AppArticleSection
        id="sec-eval"
        index={7}
        title="Evaluation"
        subtitle="graded against the committed report"
        takeaway="all graders pass"
      >
        <p>body</p>
      </AppArticleSection>,
    );
    expect(screen.getByText("graded against the committed report").className).toBe(
      "section-subtitle",
    );
  });
});
