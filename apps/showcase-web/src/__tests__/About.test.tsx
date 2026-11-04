import { readFileSync } from "node:fs";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { About } from "../pages/About";
import { PHONE_UNLOCK_KEY } from "../components/ChannelCards";
import { AVAILABILITY, CONTACT_EMAIL, LINKEDIN_URL, REPO_URL, SITE_NAME } from "../config";

beforeEach(() => {
  // the vitest jsdom environment ships no localStorage — stub one with the
  // phone flag preset; page-level tests exercise the channel row unlocked,
  // the locked-state flow itself is covered by ChannelCards.test.tsx
  const store: Record<string, string> = { [PHONE_UNLOCK_KEY]: "1" };
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => (key in store ? store[key] : null),
    setItem: (key: string, value: string) => {
      store[key] = String(value);
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      for (const key of Object.keys(store)) delete store[key];
    },
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderAbout() {
  return render(
    <MemoryRouter>
      <About />
    </MemoryRouter>,
  );
}

describe("About page", () => {
  it("opens with the consultant's name, positioning and contact channel cards", () => {
    renderAbout();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "Alejandro Mérida Maroto",
    );
    expect(screen.getByText("> about")).toBeInTheDocument();
    expect(screen.getByText("Independent ML/AI consultant — Barcelona.")).toBeInTheDocument();
    // the home-hero positioning sentence
    expect(
      screen.getByText(/I design, build and evaluate ML systems end to end, and I keep the code, metrics/),
    ).toBeInTheDocument();
    // contact facts render as channel cards (the contact page's pattern)
    const cards = [...document.querySelectorAll(".channel-card")];
    expect(cards).toHaveLength(4);
    const tel = screen.getByRole("link", { name: /\+34 670 881 697/ });
    expect(tel.getAttribute("href")).toBe("tel:+34670881697");
    expect(tel.classList.contains("channel-card")).toBe(true);
    expect(screen.getByRole("link", { name: new RegExp(CONTACT_EMAIL, "i") })).toHaveAttribute(
      "href",
      expect.stringContaining(`mailto:${CONTACT_EMAIL}?`),
    );
    const github = screen.getByRole("link", { name: /github\.com/i });
    // unified with the Contact page: the card points at the profile
    expect(github.getAttribute("href")).toBe("https://github.com/amm-ds");
    expect(github.getAttribute("href")).not.toBe(REPO_URL);
    expect(github.getAttribute("rel")).toContain("noopener");
    const linkedin = screen.getByRole("link", { name: /linkedin/i });
    expect(linkedin.getAttribute("href")).toBe(LINKEDIN_URL);
    // the old inline contact list is gone; languages & timezone render as the
    // two shared fact cards (with the phone unlocked via the localStorage flag)
    expect(document.querySelector(".about-contact")).toBeNull();
    expect(document.querySelector(".facts-grid")).not.toBeNull();
    expect(document.querySelector(".languages-card")).not.toBeNull();
    expect(document.querySelector(".timezone-card")).not.toBeNull();
    expect(screen.getByText("🇬🇧 English")).toBeInTheDocument();
    expect(screen.getByText("🇪🇸 Spanish")).toBeInTheDocument();
    expect(screen.getByText("Catalan")).toBeInTheDocument();
    // Catalan carries the drawn Senyera, not a country emoji
    expect(document.querySelector(".languages-card .flag-senyera")).not.toBeNull();
    expect(screen.getByText(/Europe\/Madrid \(CET, UTC\+1\)/)).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(`within ${AVAILABILITY.replyHours}h on business days`)),
    ).toBeInTheDocument();
  });

  it("renders the four channel cards with inline SVG logos, one row", () => {
    renderAbout();
    const grid = document.querySelector(".channel-grid--4")!;
    expect(grid).not.toBeNull();
    expect(grid.classList.contains("channel-grid")).toBe(true);
    const cards = [...grid.querySelectorAll(".channel-card")];
    expect(cards).toHaveLength(4);
    const names = cards.map((c) => c.querySelector(".channel-name")!.textContent);
    expect(names).toEqual(["Phone", "Email", "GitHub", "LinkedIn"]);
    for (const card of cards) {
      expect(card.tagName).toBe("A");
      expect(card.querySelector("svg")).not.toBeNull();
      expect(card.querySelector("svg path")).not.toBeNull();
      expect(card.querySelector(".channel-address")!.textContent!.length).toBeGreaterThan(0);
    }
    // external cards open in a new tab safely; phone/email stay in-page
    expect(cards[0].getAttribute("target")).toBeNull();
    expect(cards[1].getAttribute("target")).toBeNull();
    expect(cards[2].getAttribute("target")).toBe("_blank");
    expect(cards[3].getAttribute("target")).toBe("_blank");
    // the CSS carries the 4-column row from 640px up, single column below
    const css = readFileSync("src/styles.css", "utf8");
    const fourCol = css.match(
      /@media \(min-width: 640px\) \{\s*\.channel-grid--4 \{[\s\S]*?\n  \}/,
    )![0];
    expect(fourCol).toContain("grid-template-columns: repeat(4, minmax(0, 1fr));");
    // channel cards reuse the contact page's card styles untouched
    expect(css.match(/\.channel-card \{[\s\S]*?\n\}/)![0]).toContain("display: flex;");
  });

  it("renders six experience stops as a vertical timeline with periods and 2–3 bullets each", () => {
    renderAbout();
    const items = document.querySelectorAll(".timeline-item");
    expect(items).toHaveLength(6);
    const titles = [...document.querySelectorAll(".timeline-item h3")].map(
      (el) => el.textContent,
    );
    expect(titles).toEqual([
      "Lead ML/AI engineer — pharmaceutical AI (remote)",
      "Senior data scientist — network telemetry (ISP data)",
      "Senior data scientist — manufacturing analytics",
      "Senior data scientist — e-commerce retail",
      "Data scientist & engineer",
      "Data scientist — venture studio",
    ]);
    // periods, newest first, in accent mono
    const dates = [...document.querySelectorAll(".timeline-period")].map((el) => el.textContent);
    expect(dates).toEqual([
      "2025 — now",
      "2024 — 2025",
      "2023 — 2024",
      "2022 — 2023",
      "2021 — 2022",
      "2019 — 2021",
    ]);
    // each stop carries 2–3 achievement bullets
    for (const item of items) {
      const bullets = item.querySelectorAll("ul li").length;
      expect(bullets).toBeGreaterThanOrEqual(2);
      expect(bullets).toBeLessThanOrEqual(3);
    }
    // scope notes from the profile survive
    expect(screen.getByText(/100k\+ products with hierarchical models/i)).toBeInTheDocument();
    expect(screen.getByText(/30\+ interviews/i)).toBeInTheDocument();
    // generic industry descriptors only — no company names anywhere on the page
    expect(screen.queryByText(/vanti|kognic|dera|pecan|letgo|olx|king/i)).toBeNull();
  });

  it("connects the timeline with the site's dot/line language, left-aligned with the line through the dot centers", () => {
    const css = readFileSync("src/styles.css", "utf8");
    // last rem value of a shorthand (the list writes `padding: 0 0 0 1.5rem;`)
    const rem = (rule: string, prop: string) =>
      Number(
        rule.match(
          prop === "padding"
            ? /padding:[^;]*?(-?[0-9.]+)rem;/
            : new RegExp(`${prop}: (-?[0-9.]+)rem;`),
        )![1],
      );
    // a connecting line down the list…
    const lineRule = css.match(/\.timeline::before \{[\s\S]*?\n\}/)![0];
    expect(lineRule).toContain("width: 1px;");
    expect(lineRule).toContain("background: var(--border);");
    // …and an accent dot per stop
    const dotRule = css.match(/\.timeline-item::before \{[\s\S]*?\n\}/)![0];
    expect(dotRule).toContain("border-radius: 50%;");
    expect(dotRule).toContain("background: var(--accent);");
    // vertical layout, single column, width-constrained but LEFT-aligned with
    // the page text (no auto margins)
    const timelineRule = css.match(/\.timeline \{[\s\S]*?\n\}/)![0];
    expect(timelineRule).toContain("max-width: 720px;");
    expect(timelineRule).toContain("margin: 1.75rem 0 0;");
    expect(timelineRule).not.toContain("margin: 1.75rem auto 0;");
    expect(timelineRule).toContain("padding: 0 0 0 1.5rem;");
    // the line passes through the dots' centers: its left offset equals the
    // list padding + dot left edge + half the dot width, and its top/bottom
    // offsets equal the dot top + half the dot height (first/last dot center)
    const padLeft = rem(timelineRule, "padding");
    const dotLeft = rem(dotRule, "left");
    const dotWidth = rem(dotRule, "width");
    const dotTop = rem(dotRule, "top");
    const dotHeight = rem(dotRule, "height");
    expect(rem(lineRule, "left")).toBeCloseTo(padLeft + dotLeft + dotWidth / 2, 5);
    expect(rem(lineRule, "top")).toBeCloseTo(dotTop + dotHeight / 2, 5);
    expect(rem(lineRule, "bottom")).toBeCloseTo(dotTop + dotHeight / 2, 5);
  });

  it("has no education section — no block, no heading, no styles", () => {
    renderAbout();
    expect(document.querySelector(".education-card")).toBeNull();
    expect(screen.queryByRole("heading", { name: /education/i })).toBeNull();
    expect(screen.queryByText(/Master in Big Data|Business & IT|financial markets|MITx/i)).toBeNull();
    const css = readFileSync("src/styles.css", "utf8");
    expect(css).not.toContain(".education-card");
  });

  it("opens 'how I work' as nine client-facing practice cards with the services card geometry", () => {
    renderAbout();
    const cards = document.querySelectorAll(".practice-card");
    expect(cards).toHaveLength(9);
    const text = document.querySelector(".practices-grid")!.textContent!;
    for (const practice of [
      "full repository handover",
      "measured against your baseline",
      "decisions from holdout evidence",
      "performance budgets stated & met",
      "documentation & handover walkthrough",
      "honest limits in every report",
      "monitoring & drift response",
      "structured revision rounds",
      "results quality & performance first",
    ]) {
      expect(text).toContain(practice);
    }
    // the retired portfolio-experiment cards are gone
    expect(text).not.toContain("small, reversible changes");
    expect(text).not.toContain("pinned data with checksums");
    expect(text).not.toContain("public by default");
    expect(text).not.toContain("plain-language reporting");
    // client-facing framing: what the client receives, not internal plumbing
    expect(screen.getByText(/Nine practices shape every engagement/i)).toBeInTheDocument();
    // importance cards, not a narrative strip
    expect(document.querySelectorAll(".practices-grid")).toHaveLength(1);
    expect(document.querySelector(".practices-strip")).toBeNull();
    // "how I work" is the FIRST section right after the profile intro
    const firstTitle = document.querySelector(".section-title")!;
    expect(firstTitle.textContent).toBe("how I work");
    // and it precedes the experience timeline
    const hero = document.querySelector(".services-hero")!;
    const practices = document.querySelector(".practices-grid")!;
    const timeline = document.querySelector(".timeline")!;
    expect(
      hero.compareDocumentPosition(practices) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      practices.compareDocumentPosition(timeline) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("has no stack/frameworks section (Projects owns that) and no license line", () => {
    renderAbout();
    expect(document.querySelector(".about-stack")).toBeNull();
    expect(document.querySelector(".license-line")).toBeNull();
    expect(screen.queryByText(/© 2026/)).toBeNull();
    expect(screen.queryByText(/MIT licensed/i)).toBeNull();
    expect(screen.queryByRole("heading", { name: /^stack$/i })).toBeNull();
    // no framework chip vocabulary on the page
    expect(screen.queryByText("pydantic-ai")).toBeNull();
    expect(screen.queryByText("FastAPI")).toBeNull();
  });

  it("gives the practice cards the services card geometry (bigger padding)", () => {
    const css = readFileSync("src/styles.css", "utf8");
    const practiceRule = css.match(/\.practice-card \{[\s\S]*?\n\}/)![0];
    expect(practiceRule).toContain("padding: 1.6rem 1.75rem;");
    const offeringRule = css.match(/\.offering-card \{[\s\S]*?\n\}/)![0];
    expect(offeringRule).toContain("padding: 1.6rem 1.75rem;");
  });

  it("sets document title and meta description", () => {
    renderAbout();
    expect(document.title).toBe(`About · ${SITE_NAME}`);
    expect(
      document.head
        .querySelector<HTMLElement>('meta[name="description"]')
        ?.getAttribute("content"),
    ).toMatch(/Alejandro Mérida Maroto/);
  });
});
