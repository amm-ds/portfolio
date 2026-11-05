import { readFileSync } from "node:fs";

export function readStylesCss(): string {
  const manifest = readFileSync("src/styles.css", "utf8");
  return manifest
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/^@import "\.\/(styles\/.+\.css)";$/);
      if (!match) throw new Error(`Unexpected CSS manifest line: ${line}`);
      return readFileSync(`src/${match[1]}`, "utf8");
    })
    .join("");
}
