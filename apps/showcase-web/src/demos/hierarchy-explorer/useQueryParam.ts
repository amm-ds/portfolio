import { useState } from "react";

/** One string control serialized to the URL query (`?group=&node=&origin=`),
 * mirroring the forecast workbench's pattern (panels/common.tsx) and its
 * write-and-cleanup behavior: the fallback value is dropped from the query. */
export function useQueryParam<T extends string>(
  key: string,
  allowed: readonly T[],
  fallback: T,
): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    const q = new URLSearchParams(window.location.search).get(key);
    return (allowed as readonly string[]).includes(q ?? "") ? (q as T) : fallback;
  });
  const set = (v: T) => {
    setValue(v);
    try {
      const params = new URLSearchParams(window.location.search);
      if (v === fallback) params.delete(key);
      else params.set(key, v);
      const qs = params.toString();
      window.history.replaceState(
        null,
        "",
        window.location.pathname + (qs ? `?${qs}` : "") + window.location.hash,
      );
    } catch {
      // URL state is a nicety, never a crash
    }
  };
  return [value, set];
}
