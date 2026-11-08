import { mkdir, readdir, stat } from "node:fs/promises";
import { execFile } from "node:child_process";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const runFile = promisify(execFile);
const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "../../../..");
const require = createRequire(path.join(repoRoot, "apps", "showcase-web", "package.json"));
const { chromium } = require("playwright");
const outDir = path.join(repoRoot, "artifacts", "agent-chat-e2e");
const publicDir = path.join(repoRoot, "apps", "showcase-web", "public", "apps");
await mkdir(outDir, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1600, height: 1100 },
  deviceScaleFactor: 2,
  recordVideo: { dir: outDir, size: { width: 1600, height: 1100 } },
});
const page = await context.newPage();
page.setDefaultTimeout(30_000);
await page.emulateMedia({ reducedMotion: "reduce" });
const browserErrors = [];
page.on("console", (message) => {
  if (message.type() === "error") {
    browserErrors.push(message.text());
    console.error(`browser: ${message.text()}`);
  }
});
page.on("pageerror", (error) => {
  browserErrors.push(error.message);
  console.error(`page error: ${error.message}`);
});
page.on("response", (response) => {
  if (response.url().includes("/chat") || response.url().includes("/approvals")) {
    console.log(`${response.request().method()} ${response.url()} -> ${response.status()}`);
  }
});

async function send(message) {
  await page.locator(".composer-input").fill(message);
  await page.locator(".composer-input").press("Enter");
}

async function waitDone(timeout = 600_000) {
  const visibleError = page.locator(".chat-error");
  await Promise.race([
    page.waitForFunction(
      () => document.querySelector(".chat-phase")?.textContent === "idle" &&
        /\d[\d,]* tok · \d+ req/.test(
          document.querySelector(".composer-meter-text")?.textContent ?? "",
        ),
      undefined,
      { timeout },
    ),
    visibleError.waitFor({ state: "visible", timeout }).then(async () => {
      throw new Error(`visible chat error: ${await visibleError.textContent()}`);
    }),
  ]);
  if (browserErrors.length > 0) throw new Error(browserErrors.join("\n"));
  await page.waitForTimeout(800);
}

async function ask(message, timeout = 600_000) {
  await send(message);
  await waitDone(timeout);
  return page.locator(".bubble--assistant .md-p").last().innerText();
}

function assertCompleteCloudFact(text, stage) {
  const normalized = text.trim();
  if (!/preferred cloud/i.test(normalized) || !/GCP/i.test(normalized)) {
    throw new Error(`${stage}: incomplete cloud fact in final answer: ${normalized}`);
  }
  if (/^\s*ed,\s*your preferred cloud/i.test(normalized)) {
    throw new Error(`${stage}: truncated answer suffix: ${normalized}`);
  }
}

async function capture(filename, selector) {
  const target = page.locator(selector).last();
  await target.scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(publicDir, filename) });
}

async function publishLatestVideo() {
  const files = (await readdir(outDir)).filter((name) => name.endsWith(".webm"));
  if (files.length === 0) throw new Error(`no webm recording found in ${outDir}`);
  const newest = await Promise.all(
    files.map(async (name) => ({
      name,
      mtime: (await stat(path.join(outDir, name))).mtimeMs,
    })),
  );
  newest.sort((a, b) => b.mtime - a.mtime);
  const input = path.join(outDir, newest[0].name);
  await runFile("ffmpeg", [
    "-loglevel", "error", "-i", input,
    "-c:v", "libvpx-vp9", "-crf", "36", "-b:v", "0", "-an",
    "-y", path.join(publicDir, "agent-chat-demo.webm"),
  ]);
  await runFile("ffmpeg", [
    "-loglevel", "error", "-i", input,
    "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
    "-an", "-movflags", "+faststart",
    "-y", path.join(publicDir, "agent-chat-demo.mp4"),
  ]);
}

let completed = false;
try {
  await mkdir(publicDir, { recursive: true });
  const webUrl = process.env.AGENT_CHAT_WEB_URL ?? "http://127.0.0.1:4322";
  const expectedProvider = process.env.AGENT_CHAT_EXPECT_PROVIDER ?? "kimi";
  const expectedModel = process.env.AGENT_CHAT_EXPECT_MODEL ?? "k3-256k";
  await page.goto(webUrl, { waitUntil: "networkidle", timeout: 60_000 });
  const badge = await page.locator(".composer-badge").innerText();
  if (!badge.includes(`${expectedModel}@${expectedProvider}`)) {
    throw new Error(`unexpected model identity: ${badge}; wanted ${expectedModel}@${expectedProvider}`);
  }
  // Do not showcase a stale persisted conversation: every flow starts clean.
  await page.locator(".btn-new").click();
  await ask("What is 2+2? Answer briefly.");
  await capture("agent-chat-ui-v3.png", ".bubble");

  await send('Use send_message to post "Deployment succeeded" to the ops channel.');
  const approve = page.getByRole("button", { name: /^approve$/i });
  await approve.waitFor({ timeout: 600_000 });
  await capture("agent-chat-approval-v3.png", ".approval-card");
  await approve.click();
  await waitDone();

  await page.locator(".btn-new").click();
  const acknowledgement = await ask("Remember that my preferred cloud is GCP.");
  assertCompleteCloudFact(acknowledgement, "memory acknowledgement");
  await page.locator(".btn-new").click();
  const recalled = await ask("What is my preferred cloud?");
  assertCompleteCloudFact(recalled, "memory recall");
  await capture("agent-chat-memory-v3.png", ".bubble");
  completed = true;
} finally {
  await context.close();
  if (completed) await publishLatestVideo();
  await browser.close();
  if (browserErrors.length > 0) throw new Error(browserErrors.join("\n"));
}

console.log(`recording and screenshots written under ${outDir} and ${publicDir}`);
