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

// ---------------------------------------------------------------
// Round 2 — command actions with template variables over the real
// API: the queue payload the agent executes must round-trip
// executable/arguments/timeout verbatim through PUT/GET /config/{id}.
// ---------------------------------------------------------------
test.describe("full-stack parity: command actions over the real API", () => {
  test("command action with template variables round-trips through the real API", async ({
    page,
  }) => {
    const configName = `Command API E2E ${Date.now()}`;
    await createConfigAndOpenButton1(page, configName);

    await page.getByText("Action", { exact: true }).first().click();
    // Radix Select: trigger shows the current value ("No Action").
    await page
      .getByRole("combobox")
      .filter({ hasText: /^No Action$/i })
      .first()
      .click();
    await page.getByRole("option", { name: /^Command$/i }).click();

    await page.getByPlaceholder("/path/to/executable").fill("/usr/bin/env");
    await page.getByPlaceholder("--flag value").fill("echo {{button_index}}");
    // Timeout is the only number input in the action panel.
    await page.locator('input[type="number"]').first().fill("42");

    await page.getByRole("button", { name: /^save$/i }).click();
    await expect(
      page.getByText("Configuration saved successfully.").first()
    ).toBeVisible();

    // Round-trip through the real API — same absolute-URL pattern as the
    // GIF spec (page.request is scoped to :8081, the API lives on :8000).
    // Structural assertion via response.json(): does not depend on FastAPI's
    // compact separators, and toMatchObject pins the nested action fields.
    const configId = page.url().split("/").filter(Boolean).pop();
    expect(configId, "URL must end in the config id").toBeTruthy();
    const response = await page.request.get(`http://localhost:8000/config/${configId}`);
    expect(response.ok()).toBeTruthy();
    const config = await response.json();
    const commandAction = Object.values(config.buttons)
      .map((b) => (b as { action?: { type?: string } }).action)
      .find((a) => a?.type === "command");
    expect(commandAction).toMatchObject({
      executable: "/usr/bin/env",
      arguments: "echo {{button_index}}",
      timeout: 42,
    });
  });
});

// ---------------------------------------------------------------
// Round 3A — device config assignment over the real API: the config
// the UI saved is assigned to a device via PUT /device/{id}/config/
// {configId}, and the runner-facing GET /device/{id}/config returns
// that config plus a device whose currentConfigId points at it.
// ---------------------------------------------------------------
test.describe("full-stack parity: device config assignment", () => {
  test("device config assignment round-trips through the real API", async ({
    page,
  }) => {
    const configName = `Assign API E2E ${Date.now()}`;
    await createConfigAndOpenButton1(page, configName);

    // Give the config one distinctive button so the round-trip check is
    // not just about the name.
    await page.getByPlaceholder("Button text").fill("HELLO");
    await page.getByRole("button", { name: /^save$/i }).click();
    await expect(
      page.getByText("Configuration saved successfully.").first()
    ).toBeVisible();

    // Structural round-trip — no compact-JSON string matching (round-2
    // critic lesson): the API lives on :8000, page.request is scoped to :8081.
    const configId = page.url().split("/").filter(Boolean).pop();
    expect(configId, "URL must end in the config id").toBeTruthy();

    const devicesResponse = await page.request.get("http://localhost:8000/devices");
    expect(devicesResponse.ok()).toBeTruthy();
    const devices = await devicesResponse.json();
    const device = devices.find((d: { connected?: boolean }) => d.connected) ?? devices[0];
    expect(device, "at least one device must exist").toBeTruthy();

    const assignResponse = await page.request.put(
      `http://localhost:8000/device/${device.id}/config/${configId}`
    );
    expect(assignResponse.ok()).toBeTruthy();

    const assignedResponse = await page.request.get(
      `http://localhost:8000/device/${device.id}/config`
    );
    expect(assignedResponse.ok()).toBeTruthy();
    const assigned = await assignedResponse.json();

    // Structural assertions: the assigned config is this config, and the
    // device's currentConfigId points at it.
    expect(assigned.config).toMatchObject({
      id: configId,
      name: configName,
      buttons: expect.arrayContaining([
        expect.objectContaining({ index: 0, idle: expect.objectContaining({ text: "HELLO" }) }),
      ]),
    });
    expect(assigned.device).toMatchObject({
      id: device.id,
      currentConfigId: configId,
    });
  });
});

// ---------------------------------------------------------------
// Round 4 (P15) — switch-config action over the real API: two configs
// created via the API, the button action set to Switch Config targeting
// config B through the UI picker, and the saved wire form asserted
// structurally through GET /config/{id}.
// ---------------------------------------------------------------
test.describe("full-stack parity: switch-config action", () => {
  test("switch-config action round-trips the target config id through the real API", async ({
    page,
    request,
  }) => {
    // 1. Create config B (the switch TARGET) directly via the API.
    const targetName = `Switch Target API ${Date.now()}`;
    const createB = await request.post("http://localhost:8000/config", {
      data: { name: targetName, deviceType: "stream-deck-xl", buttons: [] },
    });
    expect(createB.ok()).toBeTruthy();
    const configB = await createB.json();
    expect(configB.id).toBeTruthy();

    // 2. Create config A in the UI and set button 1's action to Switch
    //    Config targeting B via the picker.
    const configName = `Switch Source API ${Date.now()}`;
    await createConfigAndOpenButton1(page, configName);
    await page.getByText("Action", { exact: true }).first().click();
    await page
      .getByRole("combobox")
      .filter({ hasText: /^No Action$/i })
      .first()
      .click();
    await page.getByRole("option", { name: /^Switch Config$/i }).click();

    await expect(page.getByText("Target Config")).toBeVisible();
    await page
      .getByRole("combobox")
      .filter({ hasText: /no configs yet|pick a config/i })
      .click();
    await page.getByRole("option", { name: targetName }).click();

    await page.getByRole("button", { name: /^save$/i }).click();
    await expect(
      page.getByText("Configuration saved successfully.").first()
    ).toBeVisible();

    // 3. Structural round-trip through the real API: the nested action is
    //    a switch-config pointing at config B's id.
    const configId = page.url().split("/").filter(Boolean).pop();
    expect(configId, "URL must end in the config id").toBeTruthy();
    const response = await request.get(`http://localhost:8000/config/${configId}`);
    expect(response.ok()).toBeTruthy();
    const saved = await response.json();
    const switchAction = Object.values(saved.buttons)
      .map((b) => (b as { action?: { type?: string } }).action)
      .find((a) => a?.type === "switch-config");
    expect(switchAction).toMatchObject({ configId: configB.id });

    // 4. The runner's fetch endpoint serves config B by id (what
    //    fetch_config_by_id consumes at press time).
    const fetchedB = await request.get(`http://localhost:8000/config/${configB.id}`);
    expect(fetchedB.ok()).toBeTruthy();
    expect((await fetchedB.json()).name).toBe(targetName);
  });

  test("command action with detached mode round-trips through the real API", async ({
    page,
    request,
  }) => {
    const configName = `Detached API ${Date.now()}`;
    await createConfigAndOpenButton1(page, configName);

    await page.getByText("Action", { exact: true }).first().click();
    await page
      .getByRole("combobox")
      .filter({ hasText: /^No Action$/i })
      .first()
      .click();
    await page.getByRole("option", { name: /^Command$/i }).click();
    await page.getByPlaceholder("/path/to/executable").fill("/usr/bin/open");

    // Mode select: default Attached → switch to Detached.
    await page
      .getByRole("combobox")
      .filter({ hasText: /^Attached \(wait for completion\)$/i })
      .click();
    await page.getByRole("option", { name: /fire and forget/i }).click();

    await page.getByRole("button", { name: /^save$/i }).click();
    await expect(
      page.getByText("Configuration saved successfully.").first()
    ).toBeVisible();

    const configId = page.url().split("/").filter(Boolean).pop();
    const response = await request.get(`http://localhost:8000/config/${configId}`);
    expect(response.ok()).toBeTruthy();
    const config = await response.json();
    const commandAction = Object.values(config.buttons)
      .map((b) => (b as { action?: { type?: string } }).action)
      .find((a) => a?.type === "command");
    expect(commandAction).toMatchObject({
      executable: "/usr/bin/open",
      mode: "detached",
    });
  });
});

// ---------------------------------------------------------------
// Round 5 (P16) — triggers through the REAL API: the UI writes
// config.triggers via the Automatic Switching editor, PUT /config/{id}
// persists the JSON blob, and GET /config/{id} returns it structurally —
// the same wire the runner's TriggerWatcher consumes.
// ---------------------------------------------------------------
test.describe("full-stack parity: automatic switching triggers", () => {
  test("triggers round-trip through the real API (PUT + GET /config/{id})", async ({
    page,
    request,
  }) => {
    const configName = `Triggers API ${Date.now()}`;
    await createConfigAndOpenButton1(page, configName);

    await page.getByTestId("triggers-toggle").click();
    await page.getByTestId("triggers-apps").fill("Slack");
    await page.getByTestId("triggers-ssid").fill("HomeWifi");

    await page.getByRole("button", { name: /^save$/i }).click();
    await expect(
      page.getByText("Configuration saved successfully.").first()
    ).toBeVisible();

    // Structural round-trip through the real API: triggers survive as a
    // schema-less JSON blob with the exact wire shape the evaluator reads.
    const configId = page.url().split("/").filter(Boolean).pop();
    expect(configId, "URL must end in the config id").toBeTruthy();
    const response = await request.get(`http://localhost:8000/config/${configId}`);
    expect(response.ok()).toBeTruthy();
    const saved = await response.json();
    expect(saved.triggers).toEqual({
      app: ["Slack"],
      network: { ssid: "HomeWifi" },
    });

    // And the whole-row PUT replace semantics: a body WITHOUT triggers
    // clears the block (matching buttons/name/deviceType behavior).
    const put = await request.put(`http://localhost:8000/config/${configId}`, {
      data: {
        name: saved.name,
        deviceType: saved.deviceType,
        buttons: saved.buttons,
      },
    });
    expect(put.ok()).toBeTruthy();
    const cleared = await put.json();
    expect(cleared.triggers ?? null).toBeNull();
  });
});

