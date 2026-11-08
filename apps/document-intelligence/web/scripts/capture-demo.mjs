import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const output = path.resolve(process.argv[2] ?? path.join(webRoot, "artifacts"));
const api = process.env.DOCUMENT_INTELLIGENCE_API_URL ?? "http://127.0.0.1:8001";
const ui = process.env.DOCUMENT_INTELLIGENCE_UI_URL ?? "http://127.0.0.1:4323";
const headers = {
  "X-Dev-Tenant": process.env.DOCUMENT_INTELLIGENCE_DEV_TENANT ?? "demo",
  "X-Dev-Actor": process.env.DOCUMENT_INTELLIGENCE_DEV_ACTOR ?? "developer",
};

await mkdir(output, { recursive: true });
const pdf = await readFile(path.join(webRoot, "public", "fixtures", "cv.pdf"));
const form = new FormData();
form.append("file", new Blob([pdf], { type: "application/pdf" }), "cv.pdf");
const upload = await fetch(`${api}/documents`, { method: "POST", headers, body: form });
if (!upload.ok) throw new Error(`Fixture upload failed: ${upload.status} ${await upload.text()}`);
const { document } = await upload.json();

let ready = false;
for (let attempt = 0; attempt < 60; attempt += 1) {
  const response = await fetch(`${api}/documents/${document.id}/analysis`, { headers });
  if (!response.ok) throw new Error(`Analysis polling failed: ${response.status}`);
  const current = await response.json();
  if (current.document.status === "completed") {
    ready = true;
    break;
  }
  if (current.document.status === "failed") throw new Error("Fixture analysis failed");
  await new Promise((resolve) => setTimeout(resolve, 1000));
}
if (!ready) throw new Error("Fixture analysis did not complete");

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({
    viewport: { width: 1920, height: 1400 },
    deviceScaleFactor: 1,
    colorScheme: "dark",
  });
  await page.goto(ui, { waitUntil: "networkidle" });
  const card = page.locator(".document-card").filter({ hasText: "cv.pdf" }).first();
  await card.click();
  await page.locator(".pdf-page canvas").first().waitFor();
  await page.locator(".page-summary-text").first().waitFor();
  await page.locator(".citation-chip .button").first().click();
  await page.locator(".evidence-highlight").first().waitFor();
  await page.screenshot({
    path: path.join(output, "document-intelligence-summary.png"),
    fullPage: true,
  });

  await page.getByRole("tab", { name: "Conversation", exact: true }).click();
  await page.getByLabel(/Ask about page/, { exact: false }).fill("Which programming and API skills are listed?");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await page.locator(".chat-bubble--assistant").first().waitFor();
  await page.screenshot({
    path: path.join(output, "document-intelligence-qa.png"),
    fullPage: true,
  });
  console.log(JSON.stringify({ document_id: document.id, summary: true, qa: true, output }));
} finally {
  await browser.close();
}
