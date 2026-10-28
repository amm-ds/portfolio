import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Scenario } from "../types";

export type WorkbenchValues = Record<string, string | number>;

export interface WorkbenchState {
  values: WorkbenchValues;
  setValue: (key: string, value: string | number) => void;
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
 * String-tolerant twin of the churn sandbox's `useControlState`: owns a
 * workbench's control values (series id, model list, origin, horizon) and
 * serializes them to URL query params (`?series=…&models=…&origin=…&horizon=28`)
 * via `history.replaceState`, so a workbench state is shareable. On mount the
 * query string overrides defaults (values are coerced to the default's type);
 * non-numeric entries for numeric defaults are ignored.
 */
export function useWorkbenchState(defaults: WorkbenchValues, scenarios: Scenario[]): WorkbenchState {
  const defaultsKey = JSON.stringify(defaults);
  const scenariosKey = JSON.stringify(scenarios);

  const [values, setValues] = useState<WorkbenchValues>(() => {
    const fromQuery: WorkbenchValues = {};
    for (const [key, raw] of readQuery()) {
      if (!(key in defaults) || raw.trim() === "") continue;
      if (typeof defaults[key] === "number") {
        const value = Number(raw);
        if (Number.isFinite(value)) fromQuery[key] = value;
      } else {
        fromQuery[key] = raw;
      }
    }
    return { ...defaults, ...fromQuery };
  });

  // One-shot mount override; drop keys that stop being part of the defaults.
  useEffect(() => {
    setValues((prev) => {
      const next: WorkbenchValues = {};
      for (const [key, value] of Object.entries(prev)) {
        if (key in defaults) next[key] = value;
      }
      return { ...defaults, ...next };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultsKey, scenariosKey]);

  const writeQuery = useCallback(
    (next: WorkbenchValues) => {
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
        // URL state is a nicety, never a crash.
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [defaultsKey],
  );

  const pendingRef = useRef<WorkbenchValues | null>(null);
  const timerRef = useRef(0);
  const writeQueryThrottled = useCallback(
    (next: WorkbenchValues) => {
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

  // Drop the control keys on unmount so another demo does not inherit them.
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

  const setValue = useCallback(
    (key: string, value: string | number) => {
      setValues((prev) => {
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
        ([key, value]) => values[key] === value,
      );
      if (matches) return scenario.name;
    }
    return null;
  }, [values, scenariosKey, scenarios]); // eslint-disable-line react-hooks/exhaustive-deps

  const applyScenario = useCallback(
    (name: string) => {
      const scenario = scenarios.find((s) => s.name === name);
      if (!scenario) return;
      setValues((prev) => {
        const next: WorkbenchValues = { ...prev };
        for (const [key, value] of Object.entries(scenario.controls)) {
          if (typeof value === "boolean" || !(key in defaults)) continue;
          next[key] = value;
        }
        writeQueryThrottled(next);
        return next;
      });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [scenariosKey, defaultsKey, writeQueryThrottled],
  );

  const reset = useCallback(() => {
    setValues({ ...defaults });
    writeQueryThrottled({ ...defaults });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultsKey, writeQueryThrottled]);

  return { values, setValue, activeScenario, applyScenario, reset };
}
