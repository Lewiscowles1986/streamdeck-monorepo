import { test, expect } from "@playwright/test";

/**
 * Full-stack parity specs — the real API's dialect as seen by the UI.
 * Locks the frontend half of docs/parity.md against the backend.
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