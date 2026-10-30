import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Scenario } from "../types";

export type ControlValues = Record<string, number>;

export interface ControlState {
  controls: ControlValues;
  setControl: (key: string, value: number) => void;
  /** The scenario whose controls all match the current values, else null. */
  activeScenario: string | null;
  applyScenario: (name: string) => void;
  /** Restores defaults and clears the URL query string. */
  reset: () => void;
  /** Absolute URL encoding the current control values (for a copy button). */
  shareUrl: string;
}

function readQuery(): URLSearchParams {
  return new URLSearchParams(window.location.search);
}

/**
 * Owns a demo's numeric control state. Values serialize to URL query params
 * (`?fn_ratio=5&threshold=0.15`) via `history.replaceState`, so a workbench
 * state is shareable; on mount the query string overrides the defaults (values
 * are coerced to numbers, non-numeric entries ignored).
 */
export function useControlState(
  defaults: Record<string, number>,
  scenarios: Scenario[],
): ControlState {
  const defaultsKey = JSON.stringify(defaults);
  const scenariosKey = JSON.stringify(scenarios);

  const [controls, setControls] = useState<ControlValues>(() => {
    const fromQuery: ControlValues = {};
    for (const [key, raw] of readQuery()) {
      const value = Number(raw);
      if (key in defaults && raw.trim() !== "" && Number.isFinite(value)) {
        fromQuery[key] = value;
      }
    }
    return { ...defaults, ...fromQuery };
  });

  // State restored from the query string is a one-shot mount override; drop
  // any keys that stop being part of the defaults.
  useEffect(() => {
    setControls((prev) => {
      const next: ControlValues = {};
      for (const [key, value] of Object.entries(prev)) {
        if (key in defaults) next[key] = value;
      }
      return { ...defaults, ...next };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultsKey, scenariosKey]);

  const writeQuery = useCallback(
    (next: ControlValues) => {
      try {
        const params = readQuery();
        for (const [key, value] of Object.entries(next)) {
          if (value !== defaults[key]) params.set(key, String(value));
          else params.delete(key);
        }
        const qs = params.toString();
        const url = window.location.pathname + (qs ? `?${qs}` : "") + window.location.hash;
        window.history.replaceState(null, "", url);
      } catch {
        // URL state is a nicety, never a crash: Safari can throw on history
        // churn (e.g. replaceState during a drag) — state still works.
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [defaultsKey],
  );

  // Coalesce URL writes: drags fire setControl per pointermove, and Safari is
  // strict about replaceState churn. State updates immediately; the query
  // string follows at most every 300ms and once more on the trailing edge.
  const pendingRef = useRef<ControlValues | null>(null);
  const timerRef = useRef(0);
  const writeQueryThrottled = useCallback(
    (next: ControlValues) => {
      pendingRef.current = next;
      if (timerRef.current) return;
      writeQuery(next);
      timerRef.current = window.setTimeout(() => {
        timerRef.current = 0;
        if (pendingRef.current) writeQuery(pendingRef.current);
      }, 300);
    },
    [writeQuery],
  );
  useEffect(() => () => window.clearTimeout(timerRef.current), []);

  // Drop the control keys on unmount so a later mount (or another demo) does
  // not inherit a previous session's params.
  useEffect(() => {
    return () => {
      const params = readQuery();
      for (const key of Object.keys(defaults)) params.delete(key);
      const qs = params.toString();
      const url = window.location.pathname + (qs ? `?${qs}` : "") + window.location.hash;
      window.history.replaceState(null, "", url);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultsKey]);

  const setControl = useCallback(
    (key: string, value: number) => {
      setControls((prev) => {
        const next = { ...prev, [key]: value };
        writeQueryThrottled(next);
        return next;
      });
    },
    [writeQueryThrottled],
  );

  const activeScenario = useMemo(() => {
    for (const scenario of scenarios) {
      const matches = Object.entries(scenario.controls).every(
        ([key, value]) => typeof value === "number" && controls[key] === value,
      );
      if (matches) return scenario.name;
    }
    return null;
  }, [controls, scenariosKey, scenarios]); // eslint-disable-line react-hooks/exhaustive-deps

  const applyScenario = useCallback(
    (name: string) => {
      const scenario = scenarios.find((s) => s.name === name);
      if (!scenario) return;
      setControls((prev) => {
        const next: ControlValues = { ...prev };
        for (const [key, value] of Object.entries(scenario.controls)) {
          if (key in defaults && typeof value === "number") next[key] = value;
        }
        writeQueryThrottled(next);
        return next;
      });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [scenariosKey, defaultsKey, writeQueryThrottled],
  );

  const reset = useCallback(() => {
    setControls({ ...defaults });
    writeQueryThrottled(defaults);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultsKey, writeQueryThrottled]);

  const shareUrl = useMemo(() => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(controls)) {
      if (value !== defaults[key]) params.set(key, String(value));
    }
    const qs = params.toString();
    return window.location.origin + window.location.pathname + (qs ? `?${qs}` : "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [controls, defaultsKey]);

  return { controls, setControl, activeScenario, applyScenario, reset, shareUrl };
}
