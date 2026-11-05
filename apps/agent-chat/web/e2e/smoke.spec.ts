import { expect, test } from "playwright/test";

// Smoke: the shell renders and one scripted mock run completes end to end.
test("mock run completes with approval", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("agent-chat")).toBeVisible();

  await page.getByLabel("message").fill("why did p99 spike?");
  await page.getByRole("button", { name: "send" }).click();

  await expect(page.locator(".tool-name", { hasText: "search_docs" })).toBeVisible();
  await expect(page.getByRole("group", { name: "approval: restart_service" })).toBeVisible();
  await page.getByRole("button", { name: "approve" }).click();

  await expect(page.getByText(/Restarted the api service/)).toBeVisible();
});
