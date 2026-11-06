import { mkdir } from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "../../../..");
const require = createRequire(path.join(repoRoot, "apps", "showcase-web", "package.json"));
const { chromium } = require("playwright");
const outDir = path.join(repoRoot, "artifacts", "agent-chat-e2e");
const publicDir = path.join(repoRoot, "apps", "showcase-web", "public", "apps");
await mkdir(outDir, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1600, height: 1000 },
  deviceScaleFactor: 2,
  recordVideo: { dir: outDir, size: { width: 1600, height: 1000 } },
});
const page = await context.newPage();
page.setDefaultTimeout(30_000);
page.on("console", (message) => {
  if (message.type() === "error") console.error(`browser: ${message.text()}`);
});
page.on("pageerror", (error) => console.error(`page error: ${error.message}`));
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
  await page.waitForFunction(
    () => /\d[\d,]* tok · \d+ req/.test(
      document.querySelector(".composer-meter-text")?.textContent ?? "",
    ),
    { timeout },
  );
  await page.waitForTimeout(800);
}

async function ask(message, timeout = 600_000) {
  await send(message);
  await waitDone(timeout);
}

try {
  await page.goto("http://127.0.0.1:4322", { waitUntil: "networkidle", timeout: 60_000 });
  await ask("What is 2+2? Answer briefly.");
  await page.screenshot({ path: path.join(publicDir, "agent-chat-ui.png") });

  await send('Send a message to the team saying "Deployment succeeded".');
  const approve = page.getByRole("button", { name: /^approve$/i });
  await approve.waitFor({ timeout: 600_000 });
  await page.screenshot({ path: path.join(publicDir, "agent-chat-approval.png") });
  await approve.click();
  await waitDone();

  await page.locator(".btn-new").click();
  await ask("Remember that my preferred cloud is GCP.");
  await page.locator(".btn-new").click();
  await ask("What is my preferred cloud?");
  await page.screenshot({ path: path.join(publicDir, "agent-chat-memory.png") });
} finally {
  await context.close();
  await browser.close();
}

console.log(`recording and screenshots written under ${outDir} and ${publicDir}`);
