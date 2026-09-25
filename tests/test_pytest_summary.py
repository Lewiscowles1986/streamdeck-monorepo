# test_pytest_summary.py — the CI reporting script (scripts/pytest-summary.py).
#
# This script decides what a red CI run TELLS you: it turns JUnit XML +
# pytest stdout into ::error/::warning annotations and a Markdown job
# summary. A bug here doesn't fail the build — it misreports it, which is
# worse (a wrong annotation sends someone to the wrong file). The cases below
# are the ones that actually bit during development:
#
#   * '%' in a message must be escaped in the workflow payload but NOT in the
#     Markdown table (leaking %25 into the summary is a visible defect);
#   * the same warning at N call sites is ONE problem, not N banners;
#   * a multi-line warning's text lives AFTER the header line, so a naive
#     parse yields an empty annotation body;
#   * warnings raised inside .venv are a dependency's business, not ours.

from __future__ import annotations

import importlib.util
import textwrap
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "pytest_summary", Path(__file__).resolve().parents[1] / "scripts" / "pytest-summary.py"
)
assert _SPEC and _SPEC.loader
ps = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ps)


@pytest.fixture()
def summary_file(tmp_path, monkeypatch):
    """Point the script's summary sink at a temp file."""
    path = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(path))
    return path


def _junit(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "junit.xml"
    path.write_text(textwrap.dedent(body))
    return path


def _log(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "pytest.log"
    path.write_text(textwrap.dedent(body))
    return path


# ---------------------------------------------------------------
# 1. Failures -> ::error annotations
# ---------------------------------------------------------------
def test_failure_becomes_an_annotation_with_file_and_line(tmp_path, capsys, summary_file):
    xml = _junit(
        tmp_path,
        f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <testsuites><testsuite name="pytest" errors="0" failures="1" skipped="0" tests="1">
        <testcase classname="test_mod" name="test_thing" file="{tmp_path}/test_mod.py">
        <failure message="AssertionError: nope">def test_thing():
            x = 1
        &gt;       assert x == 2
        E       AssertionError: nope
        /repo/tests/test_mod.py:31: AssertionError</failure>
        </testcase></testsuite></testsuites>
        """,
    )
    assert ps.main([str(xml)]) == 0
    out = capsys.readouterr().out
    assert "::error " in out
    assert "line=31" in out
    assert "title=pytest: test_mod::test_thing" in out
    # The assertion detail (the 'E' line), not the traceback noise.
    assert "AssertionError: nope" in out


def test_percent_is_escaped_in_the_command_but_not_the_summary(
    tmp_path, capsys, summary_file
):
    """'%' must be %25 in the workflow command (the runner reads a bare '%'
    as an encoded newline) and must stay a literal '%' in Markdown."""
    xml = _junit(
        tmp_path,
        """\
        <?xml version="1.0" encoding="utf-8"?>
        <testsuites><testsuite name="pytest" errors="0" failures="1" skipped="0" tests="1">
        <testcase classname="m" name="t" file="/repo/tests/t.py">
        <failure message="boom">E       RuntimeError: 100% broken
        /repo/tests/t.py:9: RuntimeError</failure>
        </testcase></testsuite></testsuites>
        """,
    )
    ps.main([str(xml)])
    assert "%25 broken" in capsys.readouterr().out
    assert "100% broken" in summary_file.read_text()


def test_missing_or_corrupt_xml_still_exits_zero(tmp_path, capsys, summary_file):
    missing = ps.main([str(tmp_path / "nope.xml")])
    assert missing == 0, "a reporting step must never fail the build"
    assert "could not parse" not in capsys.readouterr().out

    bad = tmp_path / "bad.xml"
    bad.write_text("<not-xml")
    assert ps.main([str(bad)]) == 0
    assert "could not parse" in capsys.readouterr().out


# ---------------------------------------------------------------
# 2. Warnings -> ::warning annotations (parsed from stdout, not XML)
# ---------------------------------------------------------------
def test_warnings_are_deduped_by_message_across_call_sites(tmp_path, capsys, summary_file):
    """The same deprecation at 3 places is ONE problem: one annotation with a
    '+N more' count, one summary row — not three identical banners."""
    log = _log(
        tmp_path,
        """\
        =============================== warnings summary ===============================
        streamdeck/app.py:409
          /repo/streamdeck/app.py:409: DeprecationWarning: on_event is deprecated
          /repo/streamdeck/app.py:219: DeprecationWarning: on_event is deprecated
          /repo/streamdeck/app.py:239: DeprecationWarning: on_event is deprecated
        -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
        3 warnings in 1.00s
        """,
    )
    ps.main([str(_junit(tmp_path, "<testsuites/>")), "--pytest-log", str(log)])
    out = capsys.readouterr().out
    assert out.count("::warning ") == 1, "identical warnings must collapse to one"
    assert "(+2 more)" in out
    assert "3 distinct warning" not in out  # 1 distinct warning, 3 sites
    assert "| 3 |" in summary_file.read_text()


def test_multiline_warning_takes_its_continuation_line(tmp_path, capsys, summary_file):
    """Rich/click style warnings put the text on the lines AFTER the header;
    a naive parse leaves the annotation body empty."""
    # A real repo path, so the annotation resolves to a repo-relative file.
    real = Path(__file__).resolve().parents[1] / "streamdeck" / "app.py"
    log = _log(
        tmp_path,
        f"""\
        =============================== warnings summary ===============================
        streamdeck/app.py:409
          {real}:409: DeprecationWarning:
                    on_event is deprecated, use lifespan event handlers instead.

                    Read more about it in the
                    [FastAPI docs](https://fastapi.tiangolo.com/advanced/events/).

        -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
        """,
    )
    ps.main([str(_junit(tmp_path, "<testsuites/>")), "--pytest-log", str(log)])
    out = capsys.readouterr().out
    assert "on_event is deprecated, use lifespan event handlers instead." in out
    assert "::warning file=streamdeck/app.py,line=409" in out


def test_warnings_from_dependencies_are_ignored(tmp_path, capsys, summary_file):
    """A warning inside .venv/site-packages is the dependency's problem."""
    log = _log(
        tmp_path,
        """\
        =============================== warnings summary ===============================
        .venv/lib/python3.12/site-packages/fastapi/applications.py:4681
          /repo/.venv/lib/python3.12/site-packages/fastapi/applications.py:4681: DeprecationWarning: their problem
        -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
        """,
    )
    ps.main([str(_junit(tmp_path, "<testsuites/>")), "--pytest-log", str(log)])
    assert "their problem" not in capsys.readouterr().out
    assert "warning" not in summary_file.read_text().lower()


# ---------------------------------------------------------------
# 3. The summary itself
# ---------------------------------------------------------------
def test_green_run_says_passed_and_keeps_the_tally(tmp_path, summary_file):
    log = _log(tmp_path, "179 passed, 5 deselected, 50 warnings in 7.13s\n")
    ps.main([str(_junit(tmp_path, "<testsuites/>")), "--pytest-log", str(log)])
    text = summary_file.read_text()
    assert "all tests passed" in text
    assert "179 passed, 5 deselected" in text


def test_repo_paths_are_relativised_and_others_are_left_alone(tmp_path):
    """Annotations are useful only if the path resolves in this repo."""
    inside = Path(ps.__file__).resolve()  # scripts/pytest-summary.py
    assert ps._repo_relative(str(inside)) == "scripts/pytest-summary.py"
    assert ps._repo_relative("/etc/hosts") == "/etc/hosts"
