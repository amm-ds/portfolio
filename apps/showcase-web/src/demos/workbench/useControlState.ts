import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Scenario } from "../types";

export type ControlValues<V extends string | number = string | number> = Record<string, V>;

export interface ControlState<V extends string | number = string | number> {
  controls: ControlValues<V>;
  setControl: (key: string, value: V) => void;
  /** The scenario whose controls all match the current values, else null. */
  activeScenario: string | null;
  applyScenario: (name: string) => void;
  /** Restores defaults and clears the URL query string. */
  reset: () => void;
}

function readQuery(): URLSearchParams {
  return new URLSearchParams(window.location.search);
}

/**
 * Owns a demo workbench's control state — numbers for the churn sandbox's
 * sliders, strings for the forecast workbench's series/model selections.
 * Values serialize to URL query params (`?fn_ratio=5&threshold=0.15`) via
 * `history.replaceState`, so a workbench state is shareable; on mount the
 * query string overrides the defaults (values are coerced to the default's
 * type — numbers must parse finite, non-numeric entries are ignored).
 */
export function useControlState<V extends string | number>(
  defaults: Record<string, V>,
  scenarios: Scenario[],
): ControlState<V> {
  const defaultsKey = JSON.stringify(defaults);
  const scenariosKey = JSON.stringify(scenarios);

  const [controls, setControls] = useState<ControlValues<V>>(() => {
    const fromQuery: ControlValues<V> = {};
    for (const [key, raw] of readQuery()) {
      if (!(key in defaults) || raw.trim() === "") continue;
      if (typeof defaults[key] === "number") {
        const value = Number(raw);
        if (Number.isFinite(value)) fromQuery[key] = value as V;
      } else {
        fromQuery[key] = raw as V;
      }
    }
    return { ...defaults, ...fromQuery };
  });

  // State restored from the query string is a one-shot mount override; drop
  // any keys that stop being part of the defaults.
  useEffect(() => {
    setControls((prev) => {
      const next: ControlValues<V> = {};
      for (const [key, value] of Object.entries(prev)) {
        if (key in defaults) next[key] = value;
      }
      return { ...defaults, ...next };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultsKey, scenariosKey]);

  const writeQuery = useCallback(
    (next: ControlValues<V>) => {
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
  const pendingRef = useRef<ControlValues<V> | null>(null);
  const timerRef = useRef(0);
  const writeQueryThrottled = useCallback(
    (next: ControlValues<V>) => {
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
    (key: string, value: V) => {
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
        ([key, value]) => controls[key] === value,
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
        const next: ControlValues<V> = { ...prev };
        for (const [key, value] of Object.entries(scenario.controls)) {
          // Booleans never apply; a value must match its default's type.
          if (typeof value === "boolean" || !(key in defaults)) continue;
          if (typeof value !== typeof defaults[key]) continue;
          next[key] = value as V;
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
    writeQueryThrottled({ ...defaults });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultsKey, writeQueryThrottled]);

  return { controls, setControl, activeScenario, applyScenario, reset };
}
