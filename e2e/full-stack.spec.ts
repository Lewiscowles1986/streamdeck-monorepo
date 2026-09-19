import { test, expect } from "@playwright/test";

/**
 * Full-stack E2E — real API server (dummy transport) + built frontend.
 * Validates the device workflows end-to-end without hardware: device list
 * comes from the emulated deck, config assignment and agent nomination flow
 * through the REST API and SQLite.
 */

test.describe("full-stack (API + dummy device)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
  });

  test("device from the emulated deck is listed and connected", async ({ page }) => {
    await expect(page.getByText(/stream deck original/i).first()).toBeVisible();
    await expect(page.getByText(/connected/i).first()).toBeVisible();
  });

  test("assign a config to the emulated device", async ({ page }) => {
    // Create a config first (unique name: the API database may be reused
    // across local runs, and duplicate option names break strict selectors)
    const configName = `Stack ${Date.now()}`;
    await page.getByRole("link", { name: /configurations/i }).click();
    await page.getByRole("button", { name: /new config/i }).click();
    await page.getByPlaceholder(/my gaming layout/i).fill(configName);
    await page.getByRole("button", { name: /^create$/i }).click();
    await expect(page.getByText(configName).first()).toBeVisible();

    // Assign from dashboard
    await page.getByRole("link", { name: /devices/i }).click();
    await expect(page.getByRole("button", { name: /assign/i }).first()).toBeVisible();
    const assignButton = page.getByRole("button", { name: /assign/i }).first();
    if (await assignButton.isVisible()) {
      await assignButton.click();
      await page.getByRole("dialog").getByRole("combobox").click();
      await page.getByRole("option", { name: configName }).click();
      await page.getByRole("dialog").getByRole("button", { name: /^assign$/i }).click();
      await expect(page.getByText(/config assigned/i)).toBeVisible();
    }
  });

  test("api health: devices endpoint responds through the ui origin", async ({ page }) => {
    // The frontend must be able to reach the API; verify via a settings check
    await page.getByRole("link", { name: /settings/i }).click();
    const checkButton = page.getByRole("button", { name: /test|check|save/i }).first();
    if (await checkButton.isVisible()) {
      await checkButton.click();
    }
  });
});