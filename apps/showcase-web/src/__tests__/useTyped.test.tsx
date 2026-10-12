import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useTypedScript } from "../hooks/useTyped";

function Probe({ script }: { script: { cmd: string; output?: string }[] }) {
  const { lines, currentCmd, done } = useTypedScript(script, 50);
  return (
    <div>
      {lines.map((l, i) => (
        <p key={i} data-testid={`line-${i}`}>
          {l.cmd}|{l.output ?? ""}
        </p>
      ))}
      <p data-testid="current">{currentCmd}</p>
      <p data-testid="done">{String(done)}</p>
    </div>
  );
}

const SCRIPT = [
  { cmd: "whoami", output: "data scientist" },
  { cmd: "dvc repro", output: "all green" },
];

function mockMatchMedia(matches: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      matches,
      media: "",
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("useTypedScript", () => {
  it("renders the full script instantly under prefers-reduced-motion", () => {
    mockMatchMedia(true);
    render(<Probe script={SCRIPT} />);
    expect(screen.getByTestId("line-0").textContent).toBe("whoami|data scientist");
    expect(screen.getByTestId("line-1").textContent).toBe("dvc repro|all green");
    expect(screen.getByTestId("done").textContent).toBe("true");
    expect(screen.getByTestId("current").textContent).toBe("");
  });

  it("types character by character when motion is allowed", () => {
    mockMatchMedia(false);
    vi.useFakeTimers();
    render(<Probe script={SCRIPT} />);
    expect(screen.queryByTestId("line-0")).toBeNull();

    const advance = (ms: number) => {
      act(() => {
        vi.advanceTimersByTime(ms);
      });
    };

    advance(400); // start delay → first tick types 1 char
    expect(screen.getByTestId("current").textContent).toBe("w");

    advance(20 * 5); // chars 2..6 → full "whoami"
    expect(screen.getByTestId("current").textContent).toBe("whoami");

    advance(20); // tick past the end → commit line
    expect(screen.getByTestId("line-0").textContent).toBe("whoami|data scientist");
    expect(screen.getByTestId("done").textContent).toBe("false");

    advance(350); // pause, then line 2 starts typing
    expect(screen.getByTestId("current").textContent).toBe("d");

    advance(20 * 9); // finish "dvc repro"
    advance(20); // commit
    expect(screen.getByTestId("line-1").textContent).toBe("dvc repro|all green");
    expect(screen.getByTestId("done").textContent).toBe("true");
  });
});
