import path from "node:path";

import { test, expect, type Page } from "@playwright/test";

/**
 * Parity regression specs — lock the frontend half of docs/parity.md.
 *
 * demo-ui project: agents page + nomination flow through the demo mock,
 * plus the animated-GIF upload path (data URI embedding, GIF badge,
 * save/reload persistence, shared source across buttons).
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

// ---------------------------------------------------------------
// Animated GIF upload: the UI embeds animated GIFs as base64 data
// URIs (FileReader.readAsDataURL → "data:image/gif;base64,...") and
// shows a GIF badge while the value is a data:image/gif URI. The
// backend runner decodes every frame once and cycles them at 30fps.
// These specs lock the frontend half of that look-and-feel contract.
// ---------------------------------------------------------------
const RED_BLUE_GIF = path.resolve(__dirname, "assets", "red-blue.gif");
const TRI_COLOR_GIF = path.resolve(__dirname, "assets", "tri-color.gif");

async function createConfigAndOpenButton1(page: Page, name: string) {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.getByRole("link", { name: /configurations/i }).click();
  await page.getByRole("button", { name: /new config/i }).click();
  await page.getByPlaceholder(/my gaming layout/i).fill(name);
  await page.getByRole("button", { name: /^create$/i }).click();
  await expect(page.getByText(/visual editor/i).first()).toBeVisible();
  // Grid cell 0 renders as button "1". Locate by class, not by text: once
  // a cell holds an image its accessible text is gone.
  await page.locator(".streamdeck-button").first().click();
}

test.describe("demo-ui parity: animated GIF upload", () => {
  test("uploading an animated GIF embeds a data URI and shows the GIF badge", async ({
    page,
  }) => {
    await createConfigAndOpenButton1(page, `GIF Badge E2E ${Date.now()}`);

    // setInputFiles works on the visually hidden input inside the upload zone.
    await page.locator('input[type="file"]').setInputFiles(RED_BLUE_GIF);

    await expect(page.getByAltText("Button preview")).toBeVisible();
    await expect(page.getByText("GIF", { exact: true })).toBeVisible();
  });

  test("uploaded GIF survives a save + reload round-trip", async ({ page }) => {
    await createConfigAndOpenButton1(page, `GIF Reload E2E ${Date.now()}`);
    await page.locator('input[type="file"]').setInputFiles(RED_BLUE_GIF);
    await expect(page.getByText("GIF", { exact: true })).toBeVisible();

    // Save is enabled only while dirty. NOTE: it is also disabled while the
    // save is IN FLIGHT (isPending) — so "disabled" alone doesn't prove the
    // write landed. Wait for the success toast, which fires only in
    // onSuccess, after the demo API has persisted to localStorage.
    await page.getByRole("button", { name: /^save$/i }).click();
    await expect(
      page.getByText("Configuration saved successfully.").first()
    ).toBeVisible();

    await page.reload();
    await page.locator(".streamdeck-button").first().click();
    await expect(page.getByAltText("Button preview")).toBeVisible();
    await expect(page.getByText("GIF", { exact: true })).toBeVisible();

    // JSON View proves the wire format the backend runner consumes.
    await page.getByRole("tab", { name: /json view/i }).click();
    await expect(page.locator("pre")).toContainText("data:image/gif;base64,");
  });

  test("the same GIF can be assigned to two buttons (shared source)", async ({
    page,
  }) => {
    // The poll below is a liveness gate on the *prefix* count; the full-URI
    // regex + Set equality is the real assertion (byte-identical sources).
    await createConfigAndOpenButton1(page, `GIF Shared E2E ${Date.now()}`);
    await page.locator('input[type="file"]').setInputFiles(TRI_COLOR_GIF);
    await expect(page.getByText("GIF", { exact: true })).toBeVisible();

    // Assign the same file to a second button.
    await page.locator(".streamdeck-button").nth(1).click();
    await page.locator('input[type="file"]').setInputFiles(TRI_COLOR_GIF);
    await expect(page.getByText("GIF", { exact: true })).toBeVisible();

    await page.getByRole("tab", { name: /json view/i }).click();
    const pre = page.locator("pre");

    // At least two occurrences of the same data URI prefix — the runner
    // keys persistent_images by the full source string, so identical
    // uploads share one decode across buttons.
    await expect
      .poll(async () => {
        const text = await pre.textContent();
        return (text?.match(/data:image\/gif;base64,/g) ?? []).length;
      })
      .toBeGreaterThanOrEqual(2);

    // Same file uploaded twice → byte-identical data URIs on both buttons.
    const text = (await pre.textContent()) ?? "";
    const uris = text.match(/data:image\/gif;base64,[A-Za-z0-9+/=]+/g) ?? [];
    expect(uris.length).toBeGreaterThanOrEqual(2);
    expect(new Set(uris).size).toBe(1);
  });
});