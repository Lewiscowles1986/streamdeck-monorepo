# test_agent.py — the agent executor (Feature 1, R4: launch modes +
# crash-safety). The agent is the process that actually runs button
# commands; these tests pin:
#
#   - "attached" mode (default): subprocess.run + wait + capture + report,
#     exactly the pre-existing behavior, now explicitly named.
#   - "detached" mode: the executor starts the process WITHOUT waiting
#     (Popen, start_new_session=True so it survives the agent), reports
#     status "detached" with a pid, and never blocks on the child.
#   - crash-safety: NO exception may escape execute() — arbitrary garbage
#     actions (missing executable, nonexistent cwd, non-dict env, timeout
#     that isn't a number, corrupt type) must come back as structured
#     failed results, because execute() is called from the agent's polling
#     loop and a single raising action must never kill the loop.
#
# The user's mandate: "focus on trying not to crash our server no matter
# what happens" — hence the garbage-input matrix at the bottom.

from __future__ import annotations

import time

import pytest

from streamdeck import agent


# ---------------------------------------------------------------
# Attached mode (default): current behavior, locked by name.
# ---------------------------------------------------------------
def test_attached_mode_is_the_default_and_captures_output(tmp_path):
    result = agent.execute(
        {"type": "command", "executable": "/bin/echo", "arguments": "hi"}
    )
    assert result["status"] == "done"
    assert result["returncode"] == 0
    assert result["stdout"].strip() == "hi"


def test_attached_mode_explicit():
    result = agent.execute(
        {
            "type": "command",
            "executable": "/bin/echo",
            "arguments": "explicit",
            "mode": "attached",
        }
    )
    assert result["status"] == "done"
    assert result["stdout"].strip() == "explicit"


def test_attached_mode_reports_failure_status_on_nonzero_exit():
    # /usr/bin/false exits 1 (a naive `sh -c exit 3` would split into
    # ["-c", "exit", "3"] and exit 0 — the arguments field is whitespace-
    # split, so use a command whose exit code needs no quoting).
    result = agent.execute(
        {"type": "command", "executable": "/usr/bin/false"}
    )
    assert result["status"] == "failed"
    assert result["returncode"] == 1


def test_attached_mode_timeout_enforced():
    """P8 timeout must kill the command: sleep 5 with timeout 1 must come
    back well under the full sleep. Current executor converts the
    TimeoutExpired into a failed result whose message reads "timed out
    after 1 seconds" — pinned here."""
    started = time.monotonic()
    result = agent.execute(
        {
            "type": "command",
            "executable": "/bin/sleep",
            "arguments": "5",
            "timeout": 1,
        }
    )
    elapsed = time.monotonic() - started
    assert elapsed < 3.0, f"timeout not enforced (took {elapsed:.1f}s)"
    assert result["status"] == "failed"
    assert "timed out" in str(result.get("error", "")).lower()


# ---------------------------------------------------------------
# Detached mode: fire-and-forget, process survives the executor.
# ---------------------------------------------------------------
def test_detached_mode_returns_promptly_with_pid_and_process_lands_file(tmp_path, monkeypatch):
    """Detached = Popen without waiting. The marker file proves the child
    actually started and outlives the execute() call."""
    marker = tmp_path / "sd-detached-test"
    action = {
        "type": "command",
        "executable": "/usr/bin/touch",
        "arguments": str(marker),
        "mode": "detached",
    }

    started = time.monotonic()
    result = agent.execute(action)
    elapsed = time.monotonic() - started

    assert result["status"] == "detached"
    assert isinstance(result.get("pid"), int)
    assert result["pid"] > 0
    # A detached start must not block on the child (touch would take
    # milliseconds anyway; the bound guards against a run()-style wait).
    assert elapsed < 2.0, f"detached execute blocked for {elapsed:.1f}s"

    # The file must EVENTUALLY exist (poll up to ~3s) — the process really
    # ran, asynchronously.
    deadline = time.monotonic() + 3.0
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert marker.exists(), "detached process never ran (marker file missing)"


def test_detached_mode_uses_start_new_session(monkeypatch):
    """The child must be disowned from the executor's process group so it
    survives the agent stopping (the whole point of detached mode)."""
    captured: dict = {}

    class FakePopen:
        def __init__(self, argv, *args, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            self.pid = 4242

        def poll(self):
            return None  # still running

    monkeypatch.setattr("streamdeck.agent.subprocess.Popen", FakePopen)
    result = agent.execute(
        {
            "type": "command",
            "executable": "/usr/bin/some-long-runner",
            "mode": "detached",
        }
    )
    assert result["status"] == "detached"
    assert result["pid"] == 4242
    assert captured["kwargs"].get("start_new_session") is True


# ---------------------------------------------------------------
# Crash-safety: no input may raise out of execute().
# ---------------------------------------------------------------
def test_missing_executable_is_a_failed_result_not_a_raise():
    result = agent.execute(
        {"type": "command", "executable": "/nonexistent/binary"}
    )
    assert result["status"] == "failed"
    assert result.get("error")


def test_nonexistent_cwd_is_ignored_not_fatal():
    """Hardening choice (documented): a cwd that isn't an existing directory
    is IGNORED (the command runs in the executor's cwd) rather than raising
    FileNotFoundError — the executor must not crash on bad cwd fields."""
    result = agent.execute(
        {
            "type": "command",
            "executable": "/bin/echo",
            "arguments": "hi",
            "cwd": "/nonexistent/cwd/dir",
        }
    )
    assert result["status"] == "done"
    assert result["stdout"].strip() == "hi"


def test_cwd_pointing_at_a_file_is_ignored_not_fatal(tmp_path):
    cwd_file = tmp_path / "not-a-dir.txt"
    cwd_file.write_text("x", encoding="utf-8")
    result = agent.execute(
        {
            "type": "command",
            "executable": "/bin/echo",
            "arguments": "hi",
            "cwd": str(cwd_file),
        }
    )
    assert result["status"] == "done"


def test_corrupt_env_is_sanitized_not_fatal():
    result = agent.execute(
        {
            "type": "command",
            "executable": "/bin/echo",
            "arguments": "hi",
            "env": "not-a-dict",
        }
    )
    # The executor must either sanitize the env and run (done) or report a
    # clean failure — either way it must NOT raise and must be structured.
    assert result["status"] in ("done", "failed")


def test_corrupt_timeout_falls_back_instead_of_raising():
    result = agent.execute(
        {
            "type": "command",
            "executable": "/bin/echo",
            "arguments": "hi",
            "timeout": "not-a-number",
        }
    )
    assert result["status"] == "done"
    assert result["stdout"].strip() == "hi"


def test_garbage_action_shapes_never_raise():
    """The polling loop feeds arbitrary JSON into execute(); every one of
    these must return a structured result, never an exception."""
    garbage_actions = [
        {},  # no type at all
        None,  # not even a dict
        {"type": 42},  # non-string type
        {"type": "command"},  # no executable
        {"type": "command", "executable": 123},  # non-string executable
        {"type": "command", "executable": ["list"]},  # list executable
        {"type": "command", "executable": "/bin/echo", "arguments": 99},
        {"type": "command", "executable": "/bin/echo", "timeout": ["x"]},
        {"type": "command", "executable": "/bin/echo", "mode": 7},
        "just-a-string",  # action that isn't a dict at all
    ]
    for action in garbage_actions:
        result = agent.execute(action)  # must not raise
        assert isinstance(result, dict), f"unstructured result for {action!r}"
        assert "status" in result, f"result missing status for {action!r}"


def test_execute_never_raises_for_any_action(monkeypatch):
    """Belt-and-braces: even if an internal helper explodes (simulated by
    monkeypatching expand_template_vars to raise), execute() must return a
    structured failed result — the agent loop must survive arbitrary
    garbage actions."""
    import streamdeck.agent as agent_module

    def explode(action, context=None):
        raise RuntimeError("simulated internal explosion")

    monkeypatch.setattr(agent_module, "expand_template_vars", explode)
    result = agent_module.execute(
        {"type": "command", "executable": "/bin/echo", "arguments": "hi"}
    )
    assert result["status"] == "failed"
    assert result.get("error")

def test_env_reaches_the_subprocess():
    """Teeth for _as_env: an action's env must actually reach the child
    process (not just survive the wire payload). /usr/bin/env with no
    command prints its environment — so the var set via the env field
    must appear in the captured stdout."""
    result = agent.execute(
        {
            "type": "command",
            "executable": "/usr/bin/env",
            "env": {"SD_R4_TEETH": "env-flows"},
        }
    )
    assert result["status"] == "done"
    assert "SD_R4_TEETH=env-flows" in result["stdout"], (
        "the action env field must be merged into the subprocess env"
    )
