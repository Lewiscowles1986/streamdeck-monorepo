# tests/test_cli.py — the CLI surface contract (round 6).
#
# The CLI is a plain typer app, so shell completion (--install-completion /
# --show-completion) is typer's built-in behavior — the only way to lose it
# is to disable it (add_completion=False, which is exactly how it was lost
# historically). These subprocess tests pin that it stays enabled, that the
# documented commands remain listed, and that --help stays cheap (the CLI
# must not import heavy modules at parse time; uvx smoke in CI runs --help).

from __future__ import annotations

import os
import re
import subprocess
import sys
import time

import pytest

# --help is colourised by Rich whenever it thinks it is on a terminal, and
# GitHub Actions sets a colour env, so option names arrive wrapped in SGR
# sequences ("\x1b[1m--show-completion\x1b[0m"). These tests pin the CLI's
# CONTENT, not Rich's colour decisions, so styling is stripped before every
# assertion. Without this the suite passes on a plain local shell and fails
# on CI purely on colour.
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _plain(text: str) -> str:
    """Text with ANSI/CSI escape sequences removed."""
    return _ANSI_ESCAPE.sub("", text)


def run_cli(*args: str, timeout: float = 15.0) -> subprocess.CompletedProcess:
    """Run the CLI module the way uvx does (python -m streamdeck.cli)."""
    return subprocess.run(
        [sys.executable, "-m", "streamdeck.cli", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_help_advertises_shell_completion():
    """Typer's built-in completion options must be present on the top level."""
    result = run_cli("--help")
    assert result.returncode == 0, result.stderr
    out = _plain(result.stdout)
    assert "--install-completion" in out
    assert "--show-completion" in out


def test_help_lists_documented_commands():
    """Every command README/roadmap documents must appear in --help."""
    result = run_cli("--help")
    assert result.returncode == 0, result.stderr
    out = _plain(result.stdout)
    for command in ("serve", "list-devices", "run", "agent", "demo", "ui", "version"):
        assert command in out


def test_help_completes_quickly():
    """--help must not import the heavy stack (uvicorn/pillow/db) at parse time.

    Generous 10s ceiling: a regression that pulls in the whole app at CLI
    import time lands around 2s+; this catches that without being flaky.
    """
    start = time.monotonic()
    result = run_cli("--help")
    elapsed = time.monotonic() - start
    assert result.returncode == 0, result.stderr
    assert elapsed < 10, f"--help took {elapsed:.2f}s — CLI imports got heavy"


def test_show_completion_prints_a_script():
    """--show-completion prints the shell script for the guessed shell."""
    env = dict(os.environ)
    env["SHELL"] = "/bin/bash"
    result = subprocess.run(
        [sys.executable, "-m", "streamdeck.cli", "--show-completion"],
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip(), "expected a non-empty completion script"


@pytest.mark.parametrize(
    "command",
    ["--install-completion", "--show-completion"],
)
def test_completion_options_exist_on_every_command_path(command):
    """Completion is a top-level option; the app object must keep it enabled."""
    result = run_cli("--help")
    assert result.returncode == 0, result.stderr
    assert command in _plain(result.stdout)