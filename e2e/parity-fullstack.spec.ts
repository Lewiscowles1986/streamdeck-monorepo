import path from "node:path";

import { test, expect, type Page } from "@playwright/test";

/**
 * Full-stack parity specs — the real API's dialect as seen by the UI.
 * Locks the frontend half of docs/parity.md against the backend,
 * including the animated-GIF path persisting data URIs end-to-end
 * through PUT /config/{id} and GET /config/{id}.
 */

test.describe("full-stack parity", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
  });

  test("device card renders a label for the human-name device type", async ({ page }) => {
    // The dummy API returns types like "Stream Deck Original" (human names).
    // The card must show a readable label, never a blank/undefined one.
    const subtitle = page
      .getByText(/stream deck/i)
      .filter({ hasText: /^Stream Deck/ })
      .first();
    await expect(subtitle).toBeVisible();
  });

  test("agents page works against the real API (empty state)", async ({ page }) => {
    await page.getByRole("link", { name: /agents/i }).click();
    // Fresh DB: either the empty state or a registered agent is acceptable,
    // but the page must render its heading either way.
    await expect(page.getByText(/agents/i).first()).toBeVisible();
  });

  test("deleting a config clears the assignment on the device card", async ({ page }) => {
    const configName = `Parity ${Date.now()}`;
    // Create a config.
    await page.getByRole("link", { name: /configurations/i }).click();
    await page.getByRole("button", { name: /new config/i }).click();
    await page.getByPlaceholder(/my gaming layout/i).fill(configName);
    await page.getByRole("button", { name: /^create$/i }).click();
    await expect(page.getByText(configName).first()).toBeVisible();

    // Assign it to the first device.
    await page.getByRole("link", { name: /devices/i }).click();
    await page.getByRole("button", { name: /assign/i }).first().click();
    await page.getByRole("dialog").getByRole("combobox").click();
    await page.getByRole("option", { name: configName }).click();
    await page.getByRole("dialog").getByRole("button", { name: /^assign$/i }).click();
    await expect(page.getByText(/config assigned/i)).toBeVisible();

    // Delete the config.
    await page.getByRole("link", { name: /configurations/i }).click();
    const card = page.locator(".group", { hasText: configName }).first();
    await card.getByRole("button", { name: /config actions/i }).click(); // ⋮ menu
    await page.getByRole("menuitem", { name: /delete/i }).click();

    // Back to devices: the card must show "None assigned" (P4 regression).
    await page.getByRole("link", { name: /devices/i }).click();
    await expect(page.getByText(/none assigned/i).first()).toBeVisible();
  });
});

// ---------------------------------------------------------------
// Animated GIF over the real API: upload in the UI, save with PUT
// /config/{id}, survive a reload, and round-trip the data URI
// through GET /config/{id} — the format the runner decodes per frame.
// ---------------------------------------------------------------
const RED_BLUE_GIF = path.resolve(__dirname, "assets", "red-blue.gif");

async function createConfigAndOpenButton1(page: Page, name: string) {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.getByRole("link", { name: /configurations/i }).click();
  await page.getByRole("button", { name: /new config/i }).click();
  await page.getByPlaceholder(/my gaming layout/i).fill(name);
  await page.getByRole("button", { name: /^create$/i }).click();
  await expect(page.getByText(/visual editor/i).first()).toBeVisible();
  await page.locator(".streamdeck-button").first().click();
}

test.describe("full-stack parity: animated GIF over the real API", () => {
  test("uploaded GIF persists through save, reload, and the real API", async ({
    page,
  }) => {
    const configName = `GIF API E2E ${Date.now()}`;
    await createConfigAndOpenButton1(page, configName);
    await page.locator('input[type="file"]').setInputFiles(RED_BLUE_GIF);
    await expect(page.getByAltText("Button preview")).toBeVisible();
    await expect(page.getByText("GIF", { exact: true })).toBeVisible();

    // The toast fires only in onSuccess — i.e. after PUT /config/{id}
    // has committed. Waiting for it (instead of the disabled state, which
    // is also true while pending) removes the reload/write race. .first()
    // because the aria-live viewport span wraps the same text.
    await page.getByRole("button", { name: /^save$/i }).click();
    await expect(
      page.getByText("Configuration saved successfully.").first()
    ).toBeVisible();

    await page.reload();
    await page.locator(".streamdeck-button").first().click();
    await expect(page.getByAltText("Button preview")).toBeVisible();
    await expect(page.getByText("GIF", { exact: true })).toBeVisible();

    // Round-trip: the saved body must carry the data URI the runner consumes.
    // NOTE: page.request is scoped to baseURL (:8081, the SPA server whose
    // catch-all returns index.html) — the API lives on :8000, so use the
    // absolute URL.
    const configId = page.url().split("/").filter(Boolean).pop();
    expect(configId, "URL must end in the config id").toBeTruthy();
    const response = await page.request.get(`http://localhost:8000/config/${configId}`);
    expect(response.ok()).toBeTruthy();
    const body = await response.text();
    expect(body).toContain("data:image/gif;base64,");
    expect(body).toContain(`"name":"${configName}"`);
  });
});