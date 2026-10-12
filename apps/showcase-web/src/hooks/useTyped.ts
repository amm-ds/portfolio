import { useEffect, useState } from "react";

export interface TypedScriptLine {
  cmd: string;
  output?: string;
}

export interface TypedScriptState {
  /** Fully typed lines (cmd + output). */
  lines: TypedScriptLine[];
  /** The partially typed command currently being typed ("" between lines). */
  currentCmd: string;
  done: boolean;
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

const DEFAULT_CPS = 30;

/**
 * Types a short command script character by character, revealing each line's
 * output once its command completes. Honors prefers-reduced-motion by
 * returning the final state immediately.
 */
export function useTypedScript(script: TypedScriptLine[], cps: number = DEFAULT_CPS): TypedScriptState {
  const reduced = prefersReducedMotion();
  const [state, setState] = useState<TypedScriptState>(() =>
    reduced
      ? { lines: script, currentCmd: "", done: true }
      : { lines: [], currentCmd: "", done: false },
  );

  useEffect(() => {
    if (reduced) return;
    let cancelled = false;
    let lineIndex = 0;
    let charCount = 0;
    let timer = 0;

    const tick = () => {
      if (cancelled) return;
      const line = script[lineIndex];
      if (line === undefined) {
        setState((s) => ({ ...s, done: true }));
        return;
      }
      charCount += 1;
      if (charCount <= line.cmd.length) {
        const slice = line.cmd.slice(0, charCount);
        setState((s) => ({ ...s, currentCmd: slice }));
        timer = window.setTimeout(tick, 1000 / cps);
      } else {
        const isLast = lineIndex === script.length - 1;
        setState((s) => ({
          lines: [...s.lines, line],
          currentCmd: "",
          done: isLast,
        }));
        lineIndex += 1;
        charCount = 0;
        timer = window.setTimeout(tick, 350);
      }
    };

    timer = window.setTimeout(tick, 400);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // The script is a static constant at every call site; typing params fixed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return state;
}
