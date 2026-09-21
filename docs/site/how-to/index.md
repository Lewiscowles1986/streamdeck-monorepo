# How-to guides

Task-oriented pages. Each one solves a specific problem with numbered steps
and a verification at the end. If you're still learning the stack, start with
the [tutorials](../tutorials/index.md) instead.

## Working with buttons

- **[Upload an animated GIF button](animated-gif-button.md)** — put a GIF on
  a key (data URI pipeline, GIF badge, shared decode).
- **[Pause and resume an animation](pause-animation.md)** — hold a frame with
  `pause`/`play`/`toggle-animation` actions and the `animation` config block.

## Running commands

- **[Run commands attached vs detached](attached-detached-commands.md)** —
  wait-and-report vs fire-and-forget (`mode` semantics, `timeout`).
- **[Build a multi-step sequence](multi-step-sequences.md)** — `steps`,
  `stopOnError`, per-step `delayMs`, and the nesting cap.

## Organizing configs

- **[Switch configs from a button](switch-config-button.md)** — the
  `switch-config` action, with a picker in the UI.
- **[Set up automatic switching with triggers](automatic-switching-triggers.md)** —
  the config `triggers` block, end to end from the UI.

## Computers and agents

- **[Nominate an agent computer](nominate-agents.md)** — register a machine
  with `streamdeck agent` and point a device at it.

## Developer workflows

- **[Use shell completion and input autocomplete](completion.md)** — CLI
  completion (typer) and the UI's `CommandInput` suggestions.
- **[Run the test suites](run-tests.md)** — pytest, the four Playwright
  projects, and mutation-verification practice.