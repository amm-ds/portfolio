import { useEffect, useRef, useState } from "react";
import { MERMAID_THEME } from "./mermaid-theme";

export { MERMAID_THEME };

let initialized = false;
let diagramCounter = 0;
// mermaid.render mutates shared temp DOM internally and is not safely
// reentrant: concurrent renders (multiple diagrams on one page) throw
// intermittently in Safari. Serialize every render through this queue.
let renderQueue: Promise<unknown> = Promise.resolve();

function renderQueued(id: string, code: string): Promise<{ svg: string }> {
  const run = async (): Promise<{ svg: string }> => {
    const mermaid = (await import("mermaid")).default;
    if (!initialized) {
      mermaid.initialize(MERMAID_THEME);
      initialized = true;
    }
    return mermaid.render(id, code);
  };
  const result = renderQueue.then(run, run);
  renderQueue = result.catch(() => undefined);
  return result;
}

// Tiny synchronous SHA-1 (FIPS 180-1) so the pre-rendered SVG path lookup
// matches scripts/render-diagrams.mjs (node:crypto) without async crypto.
function sha1Hex(input: string): string {
  const bytes = new TextEncoder().encode(input);
  const bitLen = bytes.length * 8;
  const padded = new Uint8Array(((bytes.length + 8) >> 6 << 6) + 64);
  padded.set(bytes);
  padded[bytes.length] = 0x80;
  const view = new DataView(padded.buffer);
  view.setUint32(padded.length - 4, bitLen >>> 0);
  view.setUint32(padded.length - 8, Math.floor(bitLen / 0x100000000));

  let h0 = 0x67452301, h1 = 0xefcdab89, h2 = 0x98badcfe, h3 = 0x10325476, h4 = 0xc3d2e1f0;
  const w = new Uint32Array(80);
  for (let block = 0; block < padded.length; block += 64) {
    for (let t = 0; t < 16; t += 1) w[t] = view.getUint32(block + t * 4);
    for (let t = 16; t < 80; t += 1) w[t] = (w[t - 3] ^ w[t - 8] ^ w[t - 14] ^ w[t - 16]) >>> 0, w[t] = (w[t] << 1) | (w[t] >>> 31);
    let a = h0, b = h1, c = h2, d = h3, e = h4;
    for (let t = 0; t < 80; t += 1) {
      let f: number, k: number;
      if (t < 20) { f = (b & c) | (~b & d); k = 0x5a827999; }
      else if (t < 40) { f = b ^ c ^ d; k = 0x6ed9eba1; }
      else if (t < 60) { f = (b & c) | (b & d) | (c & d); k = 0x8f1bbcdc; }
      else { f = b ^ c ^ d; k = 0xca62c1d6; }
      const temp = (((a << 5) | (a >>> 27)) + f + e + k + w[t]) >>> 0;
      e = d; d = c; c = (b << 30) | (b >>> 2); b = a; a = temp;
    }
    h0 = (h0 + a) >>> 0; h1 = (h1 + b) >>> 0; h2 = (h2 + c) >>> 0; h3 = (h3 + d) >>> 0; h4 = (h4 + e) >>> 0;
  }
  return [h0, h1, h2, h3, h4].map((h) => h.toString(16).padStart(8, "0")).join("");
}

/**
 * Lazy-rendered mermaid diagram. Prefers a pre-rendered static SVG served at
 * /diagrams/<sha1(code)>.svg (Safari-proof); on 404/miss it falls back to the
 * queued runtime renderer, and parse/render failures fall back to a styled
 * <pre> of the source — the page never crashes on a bad diagram.
 */
export function MermaidDiagram({ code }: { code: string }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      // Pre-rendered SVG path: static file hashed by the exact source the
      // runtime renderer would receive. Any non-200 (or fetch error, e.g.
      // relative URL in tests) falls through to runtime rendering.
      try {
        const res = await fetch(`/diagrams/${sha1Hex(code)}.svg`);
        if (res.ok) {
          const svg = await res.text();
          if (cancelled || !hostRef.current) return;
          hostRef.current.innerHTML = svg;
          setReady(true);
          return;
        }
      } catch {
        // fall through to runtime render
      }
      // one retry before falling back: transient failures (observer timing,
      // chunk still warming) should not dump raw source on the page
      for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
          const { svg } = await renderQueued(`mmd-${diagramCounter++}`, code);
          if (cancelled || !hostRef.current) return;
          hostRef.current.innerHTML = svg;
          setReady(true);
          return;
        } catch {
          if (cancelled) return;
        }
      }
      if (!cancelled) setFailed(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [code]);

  if (failed) {
    return (
      <pre className="code-block mermaid-fallback">
        <code>{code}</code>
      </pre>
    );
  }

  return (
    <div className="mermaid-wrap">
      {!ready && (
        <div className="frame-skeleton" aria-hidden="true">
          <span>rendering diagram…</span>
        </div>
      )}
      <div ref={hostRef} className="mermaid-host" data-testid="mermaid-host" />
    </div>
  );
}
