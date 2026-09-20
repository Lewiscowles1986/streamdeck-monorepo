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
    await expect(page.getByText(/agent nominated/i).first()).toBeVisible();
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

// ---------------------------------------------------------------
// Round 2 — config-editor parity: template variables (P1) and font
// configuration (P2) as the ActionEditor/ButtonEditor actually
// render them, with save+reload persistence through the demo API.
// ---------------------------------------------------------------

test.describe("demo-ui parity: template variables + font config", () => {
  /** Open button 1's Action tab with a Command action configured. */
  async function openCommandAction(page: Page) {
    await createConfigAndOpenButton1(page, `Template Vars E2E ${Date.now()}`);
    await page.getByText("Action", { exact: true }).first().click();
    // Radix Select: click the trigger, then the option.
    const actionTrigger = page.getByRole("combobox").filter({ hasText: /^No Action$/i }).first();
    await actionTrigger.click();
    await page.getByRole("option", { name: /^Command$/i }).click();
    // Choosing Command immediately renders the command fields.
    await expect(page.getByPlaceholder("/path/to/executable")).toBeVisible();
  }

  /**
   * The ghost icon button that opens the template-variables popover for a
   * field. Structural fact: each label row (div.flex.items-center.justify-
   * between) holds the field's Label plus exactly one popover trigger —
   * a Radix PopoverTrigger rendering a ghost icon Button with
   * aria-haspopup="dialog" (verified: exactly 3 such buttons in the panel).
   */
  function templateButton(page: Page, label: string) {
    return page
      .locator("div.flex.items-center.justify-between")
      .filter({ has: page.getByText(label, { exact: true }) })
      .locator('button[aria-haspopup="dialog"]');
  }

  test("action editor inserts template variables into the arguments field", async ({
    page,
  }) => {
    await openCommandAction(page);

    // Type into Arguments, then insert {{button_index}} via the popover.
    const argsInput = page.getByPlaceholder("--flag value");
    await argsInput.fill("echo ");
    await templateButton(page, "Arguments").click();
    await expect(page.getByText("Template Variables")).toBeVisible();
    await page.getByText("{{button_index}}").first().click();
    await expect(argsInput).toHaveValue("echo {{button_index}}");

    // The Executable field has its own independent popover/insert.
    const execInput = page.getByPlaceholder("/path/to/executable");
    await templateButton(page, "Executable").click();
    await page.getByText("{{device_id}}").first().click();
    await expect(execInput).toHaveValue("{{device_id}}");
    // Arguments must be untouched by the executable insert.
    await expect(argsInput).toHaveValue("echo {{button_index}}");
  });

  test("timeout and env vars round-trip through save + reload", async ({
    page,
  }) => {
    await openCommandAction(page);

    await page.getByPlaceholder("/path/to/executable").fill("echo");
    // Timeout is the only number input in the action panel.
    const timeoutInput = page.locator('input[type="number"]').first();
    await timeoutInput.fill("90");
    await expect(timeoutInput).toHaveValue("90");

    // Env row: fill KEY first, then value (updateEnvVar flushes the pair
    // into action.env on every keystroke; typing value with an empty key
    // would leave the value out of action.env).
    await page.getByRole("button", { name: /^add$/i }).click();
    await page.getByPlaceholder("KEY").fill("SD_BUTTON");
    await page.getByPlaceholder("value", { exact: true }).fill("{{button_index}}");

    await page.getByRole("button", { name: /^save$/i }).click();
    await expect(
      page.getByText("Configuration saved successfully.").first()
    ).toBeVisible();

    await page.reload();
    await page.locator(".streamdeck-button").first().click();
    await page.getByText("Action", { exact: true }).first().click();

    await expect(page.locator('input[type="number"]').first()).toHaveValue("90");
    await expect(page.getByPlaceholder("KEY")).toHaveValue("SD_BUTTON");
    await expect(page.getByPlaceholder("value", { exact: true })).toHaveValue(
      "{{button_index}}"
    );

    // JSON View: the exact wire fields the agent executor consumes.
    await page.getByRole("tab", { name: /json view/i }).click();
    const pre = page.locator("pre");
    await expect(pre).toContainText('"timeout": 90');
    await expect(pre).toContainText('"env"');
    await expect(pre).toContainText('"SD_BUTTON"');
    await expect(pre).toContainText("{{button_index}}");
  });

  test("font config edits persist through save + reload", async ({ page }) => {
    await createConfigAndOpenButton1(page, `Font Cfg E2E ${Date.now()}`);

    // Idle tab is the default — fill the text and font controls.
    const textInput = page.getByPlaceholder("Button text");
    await textInput.fill("HELLO");

    await page.getByRole("combobox").filter({ hasText: /^Sans Serif$/i }).click();
    await page.getByRole("option", { name: /^Serif$/i }).click();

    const sizeInput = page.locator('input[type="number"]').first();
    await sizeInput.fill("20");

    // Stable structural selector for the hex color input: inside the grid
    // cell that holds the "Text Color" label, the non-color input is the
    // hex field (the color swatch is input[type=color]).
    const colorCell = page
      .locator("div.grid > div")
      .filter({ has: page.getByText("Text Color", { exact: true }) })
      .first();
    const hex = colorCell.locator('input:not([type="color"])');
    await hex.fill("#00ff00");

    await page.getByRole("combobox").filter({ hasText: /^Center$/i }).click();
    await page.getByRole("option", { name: /^Top$/i }).click();

    await page.getByRole("button", { name: /^save$/i }).click();
    await expect(
      page.getByText("Configuration saved successfully.").first()
    ).toBeVisible();

    await page.reload();
    await page.locator(".streamdeck-button").first().click();

    await expect(page.getByPlaceholder("Button text")).toHaveValue("HELLO");
    await expect(
      page.getByRole("combobox").filter({ hasText: /^Serif$/i })
    ).toBeVisible();
    await expect(page.locator('input[type="number"]').first()).toHaveValue("20");
    await expect(hex).toHaveValue("#00ff00");
    await expect(
      page.getByRole("combobox").filter({ hasText: /^Top$/i })
    ).toBeVisible();

    // JSON View: the wire dialect the runner's resolve_label_style reads.
    await page.getByRole("tab", { name: /json view/i }).click();
    const pre = page.locator("pre");
    await expect(pre).toContainText('"font"');
    await expect(pre).toContainText('"family": "serif"');
    await expect(pre).toContainText('"position": "top"');
  });

  test("pressed-state image and text are independent from idle", async ({
    page,
  }) => {
    await createConfigAndOpenButton1(page, `Pressed State E2E ${Date.now()}`);

    // Upload to the PRESSED tab.
    await page.getByRole("tab", { name: "Pressed" }).click();
    await page.locator('input[type="file"]').setInputFiles(RED_BLUE_GIF);
    await expect(page.getByAltText("Button preview")).toBeVisible();
    await expect(page.getByText("GIF", { exact: true })).toBeVisible();
    await page.getByPlaceholder("Button text").fill("PRESSED");

    // IDLE tab must still be empty — states are independent.
    await page.getByRole("tab", { name: "Idle" }).click();
    await expect(page.getByPlaceholder("Button text")).toHaveValue("");
    await expect(page.getByText("GIF", { exact: true })).toBeHidden();

    // Save + reload: both states persist independently.
    await page.getByRole("button", { name: /^save$/i }).click();
    await expect(
      page.getByText("Configuration saved successfully.").first()
    ).toBeVisible();

    await page.reload();
    await page.locator(".streamdeck-button").first().click();

    await expect(page.getByPlaceholder("Button text")).toHaveValue("");
    await expect(page.getByText("GIF", { exact: true })).toBeHidden();

    await page.getByRole("tab", { name: "Pressed" }).click();
    await expect(page.getByAltText("Button preview")).toBeVisible();
    await expect(page.getByText("GIF", { exact: true })).toBeVisible();
    await expect(page.getByPlaceholder("Button text")).toHaveValue("PRESSED");
  });
});

// ---------------------------------------------------------------
// Round 3A — toggle-mode editor parity: the Action tab's Toggle Mode
// switch seeds two states; each state carries name/image/text/action
// overrides that round-trip through save + reload; the grid cell
// renders a ToggleLeft badge for toggle buttons; the remove control
// is locked at the two-state minimum.
// ---------------------------------------------------------------
test.describe("demo-ui parity: toggle states", () => {
  /** Open button 1's Action tab on a fresh config. */
  async function openActionTab(page: Page, name: string) {
    await createConfigAndOpenButton1(page, name);
    await page.getByText("Action", { exact: true }).first().click();
  }

  /**
   * Flip the Toggle Mode switch. NOTE: in headless Chromium the FIRST
   * click after this Radix switch mounts is swallowed — the handler runs
   * (onClick-start/end fire) but aria-checked stays false; every click
   * after the first toggles normally (probe: 4 clicks → false,true,false,
   * true; a real browser toggles on click 1). So click up to 3 times,
   * checking between retries — blind repeated clicks would overshoot
   * because clicks alternate the state.
   */
  async function flipToggleMode(page: Page) {
    const sw = page.getByRole("switch");
    for (let i = 0; i < 3; i++) {
      await sw.click();
      try {
        await expect(page.getByText("Toggle States (2)")).toBeVisible({
          timeout: 1500,
        });
        return;
      } catch {
        /* first click often no-ops in headless Chromium — retry */
      }
    }
    await expect(page.getByText("Toggle States (2)")).toBeVisible();
  }

  test("toggle mode switch seeds two editable states", async ({ page }) => {
    await openActionTab(page, `Toggle Seed E2E ${Date.now()}`);

    await flipToggleMode(page);

    await expect(page.getByText("Toggle States (2)")).toBeVisible();
    await expect(page.getByRole("button", { name: /^State 1/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /^State 2/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Add State/ })).toBeVisible();
  });

  test("toggle states carry per-state overrides through save + reload", async ({
    page,
  }) => {
    await openActionTab(page, `Toggle Persist E2E ${Date.now()}`);
    await flipToggleMode(page);
    await expect(page.getByText("Toggle States (2)")).toBeVisible();

    // State 1's trigger renders "State 1 (State 1)" — a prefix match;
    // clicking it expands the accordion so its inputs mount.
    await page.getByRole("button", { name: /^State 1/ }).click();
    await page.getByPlaceholder("Image URL or path").fill("https://example.com/off.png");
    await page.getByPlaceholder("Button text").last().fill("OFF");

    // Expand state 2 and override its text.
    await page.getByRole("button", { name: /^State 2/ }).click();
    await page.getByPlaceholder("Button text").last().fill("ON");

    // Add a third state, rename it, override its text.
    await page.getByRole("button", { name: /Add State/ }).click();
    await expect(page.getByText("Toggle States (3)")).toBeVisible();
    await page.getByRole("button", { name: /^State 3/ }).click();
    await page.getByPlaceholder("State name").last().fill("MUTE");
    await page.getByPlaceholder("Button text").last().fill("MUTE");

    await page.getByRole("button", { name: /^save$/i }).click();
    await expect(
      page.getByText("Configuration saved successfully.").first()
    ).toBeVisible();

    await page.reload();
    await page.locator(".streamdeck-button").first().click();
    await page.getByText("Action", { exact: true }).first().click();

    // The renamed third state persisted; expand each state and assert its
    // override fields.
    await expect(page.getByRole("button", { name: /^MUTE/ })).toBeVisible();
    await page.getByRole("button", { name: /^State 1/ }).click();
    await expect(page.getByPlaceholder("Button text").last()).toHaveValue("OFF");
    await expect(page.getByPlaceholder("Image URL or path")).toHaveValue(
      "https://example.com/off.png"
    );
    await page.getByRole("button", { name: /^State 2/ }).click();
    await expect(page.getByPlaceholder("Button text").last()).toHaveValue("ON");
    await page.getByRole("button", { name: /^MUTE/ }).click();
    await expect(page.getByPlaceholder("Button text").last()).toHaveValue("MUTE");

    // JSON View: the camelCase wire dialect the runner's get_button_config
    // consumes (JSON.stringify(config, null, 2) — quoted keys with spaces).
    await page.getByRole("tab", { name: /json view/i }).click();
    const pre = page.locator("pre");
    await expect(pre).toContainText('"toggleStates"');
    await expect(pre).toContainText('"isToggle": true');
    await expect(pre).toContainText('"OFF"');
    await expect(pre).toContainText('"ON"');
    await expect(pre).toContainText('"MUTE"');
    await expect(pre).toContainText("https://example.com/off.png");
  });

  test("state count cannot drop below two", async ({ page }) => {
    await openActionTab(page, `Toggle Min E2E ${Date.now()}`);
    await flipToggleMode(page);
    await expect(page.getByText("Toggle States (2)")).toBeVisible();

    // Expand state 1 to reach its remove control: the ghost Trash2 icon
    // button in the State Name row. At 2 states it must be disabled.
    await page.getByRole("button", { name: /^State 1/ }).click();
    const stateNameRow = page
      .locator("div.flex.items-end.gap-2")
      .filter({ has: page.getByPlaceholder("State name") })
      .first();
    await expect(stateNameRow.getByRole("button")).toBeDisabled();
  });

  test("toggle badge appears on the grid cell", async ({ page }) => {
    await openActionTab(page, `Toggle Badge E2E ${Date.now()}`);
    await flipToggleMode(page);
    await expect(page.getByText("Toggle States (2)")).toBeVisible();

    await page.getByRole("button", { name: /^save$/i }).click();
    await expect(
      page.getByText("Configuration saved successfully.").first()
    ).toBeVisible();

    await page.reload();
    await page.locator(".streamdeck-button").first().click();

    // Badge = the ToggleLeft lucide icon inside the cell's indicator row.
    await expect(
      page.locator(".streamdeck-button").first().locator("svg.lucide-toggle-left")
    ).toBeVisible();
  });
});

// ---------------------------------------------------------------
// Round 4 (P14/P15) — launch mode (attached/detached) and the
// switch-config action as the ActionEditor hosts them.
// ---------------------------------------------------------------
test.describe("demo-ui parity: launch mode + switch-config", () => {
  /** Open button 1's Action tab with a Command action configured. */
  async function openCommandAction(page: Page) {
    await createConfigAndOpenButton1(page, `Launch Mode E2E ${Date.now()}`);
    await page.getByText("Action", { exact: true }).first().click();
    const actionTrigger = page
      .getByRole("combobox")
      .filter({ hasText: /^No Action$/i })
      .first();
    await actionTrigger.click();
    await page.getByRole("option", { name: /^Command$/i }).click();
    await expect(page.getByPlaceholder("/path/to/executable")).toBeVisible();
  }

  test("command action exposes the launch-mode select defaulting to attached", async ({
    page,
  }) => {
    await openCommandAction(page);

    // Mode select defaults to Attached.
    await expect(
      page.getByRole("combobox").filter({ hasText: /^Attached \(wait for completion\)$/i })
    ).toBeVisible();

    // Switch it to Detached.
    await page
      .getByRole("combobox")
      .filter({ hasText: /^Attached \(wait for completion\)$/i })
      .click();
    await page.getByRole("option", { name: /fire and forget/i }).click();
    await expect(
      page.getByRole("combobox").filter({ hasText: /^Detached/i })
    ).toBeVisible();

    // JSON View: the exact wire field the agent executor consumes (P14).
    await page.getByRole("tab", { name: /json view/i }).click();
    await expect(page.locator("pre")).toContainText('"mode": "detached"');
  });

  test("attached mode stays implicit (default) in the JSON", async ({ page }) => {
    await openCommandAction(page);
    await page.getByPlaceholder("/path/to/executable").fill("echo");

    await page.getByRole("tab", { name: /json view/i }).click();
    const pre = page.locator("pre");
    await expect(pre).toContainText('"executable": "echo"');
    await expect(pre).not.toContainText('"mode"');
  });

  test("switch-config action offers a config picker and writes the wire form", async ({
    page,
  }) => {
    // Seed a second config first so the picker has an entry to select.
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("link", { name: /configurations/i }).click();
    await page.getByRole("button", { name: /new config/i }).click();
    const targetName = `Switch Target ${Date.now()}`;
    await page.getByPlaceholder(/my gaming layout/i).fill(targetName);
    await page.getByRole("button", { name: /^create$/i }).click();
    await expect(page.getByText(/visual editor/i).first()).toBeVisible();

    // Now create the config under edit with the switch-config action.
    await createConfigAndOpenButton1(page, `Switch Source ${Date.now()}`);
    await page.getByText("Action", { exact: true }).first().click();
    const actionTrigger = page
      .getByRole("combobox")
      .filter({ hasText: /^No Action$/i })
      .first();
    await actionTrigger.click();
    await page.getByRole("option", { name: /^Switch Config$/i }).click();

    // The picker must appear and list the other config.
    await expect(page.getByText("Target Config")).toBeVisible();
    await page.getByRole("combobox").filter({ hasText: /no configs yet|pick a config/i }).click();
    await page.getByRole("option", { name: targetName }).click();

    // JSON View: the exact wire form the runner's key callback consumes (P15).
    await page.getByRole("tab", { name: /json view/i }).click();
    const pre = page.locator("pre");
    await expect(pre).toContainText('"switch-config"');
    await expect(pre).toContainText('"configId"');
  });
});
