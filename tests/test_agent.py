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

import threading
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


# ---------------------------------------------------------------
# R5: detached-mode zombie reaping (round-4 deferral). A detached child
# that exits while the agent stays up must be reaped (os.waitpid) by a
# daemon thread — fire-and-forget for the CALLER, buried for the OS.
# ---------------------------------------------------------------
def test_detached_child_is_reaped_via_waitpid(monkeypatch):
    """The executor schedules os.waitpid(pid, 0) for the detached child.
    wait_fn is an injectable seam (defaults to os.waitpid); the test
    injects a recorder and asserts the reaper called it with the child's
    real pid."""
    reaped: list[int] = []

    def recording_wait(pid, flags):
        reaped.append(pid)
        return (pid, 0)

    monkeypatch.setattr(agent.os, "waitpid", recording_wait)

    result = agent.execute(
        {
            "type": "command",
            "executable": "/usr/bin/true",
            "mode": "detached",
        }
    )
    assert result["status"] == "detached"
    pid = result["pid"]

    # The reaper thread runs concurrently; give it a moment.
    deadline = time.monotonic() + 3.0
    while pid not in reaped and time.monotonic() < deadline:
        time.sleep(0.01)
    assert pid in reaped, "detached child was never reaped (waitpid not called)"


def test_detached_reaper_waits_for_child_exit(monkeypatch):
    """The reaper must block on the child (waitpid semantics), i.e. reap
    AFTER the child exits — with /bin/true that is immediate, but the
    wait_fn must have been given the blocking (pid, 0) arguments."""
    calls: list[tuple[int, int]] = []

    def recording_wait(pid, flags):
        calls.append((pid, flags))
        return (pid, 0)

    monkeypatch.setattr(agent.os, "waitpid", recording_wait)
    result = agent.execute(
        {"type": "command", "executable": "/usr/bin/true", "mode": "detached"}
    )
    pid = result["pid"]
    deadline = time.monotonic() + 3.0
    while not calls and time.monotonic() < deadline:
        time.sleep(0.01)
    assert calls, "reaper never invoked wait_fn"
    assert calls[0] == (pid, 0), f"wait_fn called with {calls[0]}, want (pid, 0)"


def test_detached_reaper_failure_never_breaks_execute(monkeypatch):
    """If the reaper machinery itself fails (waitpid raising, e.g. the
    child was already reaped elsewhere), execute() must still return the
    clean detached result — reaping is best-effort."""

    def exploding_wait(pid, flags):
        raise ChildProcessError("no such child")

    monkeypatch.setattr(agent.os, "waitpid", exploding_wait)
    result = agent.execute(
        {"type": "command", "executable": "/usr/bin/true", "mode": "detached"}
    )
    assert result["status"] == "detached", result
    assert isinstance(result.get("pid"), int)


def test_detached_reaper_is_a_daemon_thread(monkeypatch):
    """The reaper must be a daemon thread (must not hold the agent process
    open) and must be started per detached child."""
    started: list[threading.Thread] = []
    real_thread = threading.Thread

    def spy_thread(*args, **kwargs):
        t = real_thread(*args, **kwargs)
        started.append(t)
        return t

    monkeypatch.setattr(agent.os, "waitpid", lambda pid, flags: (pid, 0))
    monkeypatch.setattr(threading, "Thread", spy_thread)

    result = agent.execute(
        {"type": "command", "executable": "/usr/bin/true", "mode": "detached"}
    )
    assert result["status"] == "detached"
    reapers = [t for t in started if t.daemon]
    assert reapers, "no daemon reaper thread was started"


# ---------------------------------------------------------------
# R7 (P18): multi-step sequences. A sequence executes on the agent like
# a command; each step is itself a full action (a command or another
# nested sequence). Aggregation semantics (documented in parity.md):
#   - "done"    — every step succeeded
#   - "partial" — some steps failed (continue-on-error, the default)
#   - "failed"  — ALL steps failed, or stopOnError aborted on a failure
# Crash-safety: garbage sequences (non-dict steps, steps as a string,
# missing steps key) return structured error results, never a raise.
# ---------------------------------------------------------------
def test_sequence_happy_path_two_echo_steps():
    result = agent.execute(
        {
            "type": "sequence",
            "steps": [
                {"type": "command", "executable": "/bin/echo", "arguments": "one"},
                {"type": "command", "executable": "/bin/echo", "arguments": "two"},
            ],
        }
    )
    assert result["type"] == "sequence"
    assert result["status"] == "done"
    assert len(result["steps"]) == 2
    assert result["steps"][0]["returncode"] == 0
    assert result["steps"][1]["returncode"] == 0


def test_sequence_continues_on_error_by_default():
    """Default is fire-all-steps: a failing step does not abort the run;
    the aggregate reports "partial" and later steps still execute."""
    result = agent.execute(
        {
            "type": "sequence",
            "steps": [
                {"type": "command", "executable": "/usr/bin/false"},
                {"type": "command", "executable": "/bin/echo", "arguments": "still-ran"},
            ],
        }
    )
    assert result["status"] == "partial"
    assert len(result["steps"]) == 2
    assert result["steps"][0]["status"] == "failed"
    assert result["steps"][1]["status"] == "done"
    assert result["steps"][1]["stdout"].strip() == "still-ran"


def test_sequence_all_failed_reports_failed():
    """Every step failing aggregates to "failed" (distinct from "partial")."""
    result = agent.execute(
        {
            "type": "sequence",
            "steps": [
                {"type": "command", "executable": "/usr/bin/false"},
                {"type": "command", "executable": "/usr/bin/false"},
            ],
        }
    )
    assert result["status"] == "failed"


def test_sequence_stop_on_error_skips_remaining_steps(tmp_path):
    """stopOnError aborts remaining steps on the first failure; the failed
    step is reported, the rest as skipped, and later steps never ran."""
    marker = tmp_path / "stop-on-error-marker"
    result = agent.execute(
        {
            "type": "sequence",
            "stopOnError": True,
            "steps": [
                {"type": "command", "executable": "/usr/bin/false"},
                {"type": "command", "executable": "/usr/bin/touch", "arguments": str(marker)},
            ],
        }
    )
    assert result["status"] == "failed"
    assert len(result["steps"]) == 2
    assert result["steps"][0]["status"] == "failed"
    assert result["steps"][1]["status"] == "skipped"
    assert not marker.exists(), "stopOnError must never run steps after the failure"


def test_sequence_delay_ms_sleeps_before_step():
    started = time.monotonic()
    result = agent.execute(
        {
            "type": "sequence",
            "steps": [
                {
                    "type": "command",
                    "executable": "/bin/echo",
                    "arguments": "after-delay",
                    "delayMs": 200,
                }
            ],
        }
    )
    elapsed = time.monotonic() - started
    assert elapsed >= 0.2, f"delayMs not respected (took {elapsed:.3f}s)"
    assert result["status"] == "done"


def test_sequence_delay_ms_is_clamped_to_60s(monkeypatch):
    """A corrupt/huge delayMs must clamp to 60s — never park the agent
    for hours. The test injects a sleep recorder and asserts no single
    sleep exceeded the cap (and does not actually sleep)."""
    slept: list[float] = []

    def spy_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(agent.time, "sleep", spy_sleep)
    agent.execute(
        {
            "type": "sequence",
            "steps": [
                {"type": "command", "executable": "/bin/echo", "delayMs": 99999999}
            ],
        }
    )
    assert slept, "a positive delayMs must sleep before the step"
    assert max(slept) <= 60.0, f"delayMs not clamped (slept {max(slept)})"


def test_as_delay_ms_sanitizer():
    """Unit teeth for the clamp: non-numeric → 0, negatives → 0, huge → cap."""
    assert agent._as_delay_ms(99999999) == 60000
    assert agent._as_delay_ms("not-a-number") == 0
    assert agent._as_delay_ms(-5) == 0
    assert agent._as_delay_ms(250) == 250
    assert agent._as_delay_ms(None) == 0


def test_sequence_nested_depth_2_works():
    result = agent.execute(
        {
            "type": "sequence",
            "steps": [
                {
                    "type": "sequence",
                    "steps": [
                        {"type": "command", "executable": "/bin/echo", "arguments": "nested"}
                    ],
                }
            ],
        }
    )
    assert result["status"] == "done"
    inner = result["steps"][0]
    assert inner["status"] == "done"
    assert inner["steps"][0]["stdout"].strip() == "nested"


def test_sequence_nesting_capped_at_depth_4():
    """Nesting deeper than 4 yields an error result for the deep step —
    never a crash and never runaway recursion."""
    # Five levels of sequences: depth 5 is one past the cap.
    deep = agent.execute(
        {
            "type": "sequence",
            "steps": [
                {
                    "type": "sequence",
                    "steps": [
                        {
                            "type": "sequence",
                            "steps": [
                                {
                                    "type": "sequence",
                                    "steps": [
                                        {
                                            "type": "sequence",
                                            "steps": [
                                                {
                                                    "type": "command",
                                                    "executable": "/bin/echo",
                                                    "arguments": "too-deep",
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
    # The innermost sequence (depth 5) must error out; the error bubbles up
    # as a failed step at every enclosing level.
    assert deep["status"] == "failed"
    level2 = deep["steps"][0]
    assert level2["status"] == "failed"
    assert level2["steps"][0]["status"] == "failed"


def test_sequence_garbage_shapes_never_raise():
    """The polling loop feeds arbitrary JSON; every garbage sequence shape
    must return a structured result, never an exception."""
    garbage_sequences = [
        {},  # no type at all
        {"type": "sequence"},  # missing steps key
        {"type": "sequence", "steps": "not-a-list"},
        {"type": "sequence", "steps": 42},
        {"type": "sequence", "steps": {"a": 1}},  # dict instead of list
        {"type": "sequence", "steps": [42]},  # non-dict step
        {"type": "sequence", "steps": [None]},
        {"type": "sequence", "steps": ["just-a-string"]},
        {"type": "sequence", "steps": [{"type": 99}]},  # corrupt step type
        {"type": "sequence", "steps": [{"no": "type"}]},  # step without type
        {"type": "sequence", "steps": [{"type": "command"}]},  # no executable
        {"type": "sequence", "steps": ["not-a-list"]},
    ]
    for action in garbage_sequences:
        result = agent.execute(action)  # must not raise
        assert isinstance(result, dict), f"unstructured result for {action!r}"
        assert "status" in result, f"result missing status for {action!r}"


def test_expand_template_vars_recurses_into_sequence_steps():
    """expand_template_vars must expand fields inside sequence steps with
    the same button context (it recurses dicts and lists)."""
    ctx = {"button_index": 5, "config_name": "Seq Cfg"}
    action = {
        "type": "sequence",
        "steps": [
            {
                "type": "command",
                "executable": "echo",
                "arguments": "btn={{button_index}} cfg={{config_name}}",
            }
        ],
    }
    expanded = agent.expand_template_vars(action, ctx)
    assert expanded["steps"][0]["arguments"] == "btn=5 cfg=Seq Cfg"


def test_sequence_template_expansion_inside_steps(tmp_path):
    """End-to-end template expansion: {{button_index}} inside a step's
    arguments expands with the button context before the step runs."""
    result = agent.execute(
        {
            "type": "sequence",
            "steps": [
                {
                    "type": "command",
                    "executable": "/bin/echo",
                    "arguments": "btn={{button_index}}",
                }
            ],
        },
        context={"button_index": 9},
    )
    assert result["status"] == "done"
    assert result["steps"][0]["stdout"].strip() == "btn=9"


# ---------------------------------------------------------------
# R7 judge fixes: detached steps are SUCCESSFUL launches, not failures.
# _execute_detached reports status "detached" (the process was started —
# the fire-and-forget contract); aggregation must treat that as a
# non-failure, or (a) stopOnError aborts remaining steps after a
# successful detached launch, and (b) detached+done aggregates to
# "partial" although nothing failed.
# ---------------------------------------------------------------
def test_sequence_stop_on_error_does_not_abort_after_detached_step():
    """A detached step IS a successful launch; stopOnError must not abort
    after one — abort is for FAILURES only."""
    result = agent.execute(
        {
            "type": "sequence",
            "stopOnError": True,
            "steps": [
                {"type": "command", "executable": "/usr/bin/true", "mode": "detached"},
                {"type": "command", "executable": "/bin/echo", "arguments": "ran"},
            ],
        }
    )
    assert len(result["steps"]) == 2
    assert result["steps"][0]["status"] == "detached"
    assert result["steps"][1]["status"] == "done", (
        "stopOnError must not skip steps after a successful detached launch"
    )


def test_sequence_detached_plus_done_aggregates_to_done():
    """detached + done with zero failures must aggregate to "done" —
    "partial" is reserved for sequences where some step FAILED."""
    result = agent.execute(
        {
            "type": "sequence",
            "steps": [
                {"type": "command", "executable": "/usr/bin/true", "mode": "detached"},
                {"type": "command", "executable": "/bin/echo", "arguments": "hi"},
            ],
        }
    )
    assert result["status"] == "done"


def test_sequence_cyclic_self_reference_hits_depth_cap():
    """A cyclic sequence (a step list containing the enclosing action
    object itself) must terminate at the depth cap with structured
    failures — never an infinite loop or a RecursionError escaping."""
    cyclic: dict = {"type": "sequence", "steps": []}
    cyclic["steps"].append(cyclic)  # shared self-referencing dict
    result = agent.execute(cyclic)
    assert result["status"] == "failed"
    # Each enclosing level wraps the inner result in its own "steps" list;
    # the cap fires at depth 5, i.e. four levels down. Walking the chain
    # must terminate (bounded structure, no runaway nesting).
    node = result
    levels = 0
    while "steps" in node:
        node = node["steps"][0]
        levels += 1
        assert levels <= 10, "cyclic nesting produced runaway structure"
    assert levels == 4, f"expected cap at 4 wrapped levels, got {levels}"
    assert node["status"] == "failed"
    assert "nesting deeper" in node["error"]
