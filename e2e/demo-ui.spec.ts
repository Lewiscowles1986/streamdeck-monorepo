import { test, expect } from "@playwright/test";

/**
 * UI-only E2E suite — runs against the DEMO build served statically.
 * No backend, no device, no network: the whole app is exercised through the
 * in-browser mock. This is the "mindshare" guarantee: the UI works anywhere.
 */

test.describe("offline demo (no server)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    // Demo build defaults to demo mode; dismiss any onboarding if present.
    await page.waitForLoadState("networkidle");
  });

  test("dashboard shows demo devices without a server", async ({ page }) => {
    await expect(page.getByText("Stream Deck XL (demo)")).toBeVisible();
    await expect(page.getByText(/demo/i).first()).toBeVisible();
  });

  test("demo banner explains offline mode", async ({ page }) => {
    const banner = page.getByText(/demo mode/i).first();
    await expect(banner).toBeVisible();
  });

  test("create a config and open the editor", async ({ page }) => {
    await page.getByRole("link", { name: /configurations/i }).click();
    await page.getByRole("button", { name: /new config/i }).click();
    await page.getByPlaceholder(/my gaming layout/i).fill("E2E Test Layout");
    await page.getByRole("button", { name: /^create$/i }).click();

    // Navigates into the editor for the new config
    await expect(page.getByText("E2E Test Layout").first()).toBeVisible();
  });

  test("configs persist across reloads (localStorage)", async ({ page }) => {
    await page.getByRole("link", { name: /configurations/i }).click();
    const name = `Persist ${Date.now()}`;
    await page.getByRole("button", { name: /new config/i }).click();
    await page.getByPlaceholder(/my gaming layout/i).fill(name);
    await page.getByRole("button", { name: /^create$/i }).click();
    await page.waitForTimeout(300);

    await page.reload();
    await page.getByRole("link", { name: /configurations/i }).click();
    await expect(page.getByText(name).first()).toBeVisible();
  });

  test("exit demo shows the connect screen path", async ({ page }) => {
    await page.getByRole("button", { name: /exit demo/i }).click();
    // Without a server the UI should surface its not-connected state
    await expect(
      page.getByText(/not connected|unable to connect/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });
});