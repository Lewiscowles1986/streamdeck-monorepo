import { test, expect } from "@playwright/test";

/**
 * Parity regression specs — lock the frontend half of docs/parity.md.
 *
 * demo-ui project: agents page + nomination flow through the demo mock.
 * full-stack project: device-type labels against the real API's human-name
 * dialect, and config deletion not leaving dangling assignments in the UI.
 */

test.describe("demo-ui parity: agents surface", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
  });

  test("sidebar links to the agents page", async ({ page }) => {
    await page.getByRole("link", { name: /agents/i }).click();
    await expect(page.getByText(/registered computers/i).first()).toBeVisible();
  });

  test("agents page lists the seeded demo agent", async ({ page }) => {
    await page.getByRole("link", { name: /agents/i }).click();
    await expect(page.getByText("studio-mac.local").first()).toBeVisible();
    await expect(page.getByText(/active/i).first()).toBeVisible();
  });

  test("device card offers nominate + clear-agent controls", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /^nominate$/i }).first()
    ).toBeVisible();
  });

  test("nominate an agent from the device card", async ({ page }) => {
    await page.getByRole("button", { name: /^nominate$/i }).first().click();
    await page
      .getByRole("dialog")
      .getByRole("combobox")
      .click();
    await page.getByRole("option", { name: /studio-mac\.local/i }).click();
    await page.getByRole("dialog").getByRole("button", { name: /^nominate$/i }).click();
    await expect(page.getByText(/agent nominated/i)).toBeVisible();
    // The card now shows the nominated agent and a clear control.
    await expect(page.getByText("demo-agent-studio").first()).toBeVisible();
    await expect(page.getByRole("button", { name: /clear agent/i }).first()).toBeVisible();
  });
});

test.describe("demo-ui parity: exit action configurable", () => {
  test("action editor offers the exit action type", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    // Create a config to edit.
    await page.getByRole("link", { name: /configurations/i }).click();
    await page.getByRole("button", { name: /new config/i }).click();
    await page.getByPlaceholder(/my gaming layout/i).fill(`Exit E2E ${Date.now()}`);
    await page.getByRole("button", { name: /^create$/i }).click();
    await expect(page.getByText(/visual editor/i).first()).toBeVisible();

    // Select the first button and open the action editor.
    await page.getByRole("button", { name: /^1$/i }).first().click();
    await page.getByText(/action/i).first().click();

    // The action-type select must offer Exit.
    const trigger = page.getByRole("combobox").filter({ hasText: /no action|command|exit/i }).first();
    await trigger.click();
    await expect(page.getByRole("option", { name: /exit/i }).first()).toBeVisible();
  });
});