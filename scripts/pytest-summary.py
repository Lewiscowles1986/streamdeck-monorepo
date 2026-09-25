#!/usr/bin/env python3
"""Turn a pytest JUnit XML report into GitHub-native reporting.

pytest has no `--reporter github` equivalent, so failures only ever appear as
opaque log text — and on a private repo those logs sit behind a GitHub
sign-in. JUnit XML already carries the test id, the message and the traceback,
so this converts it into the two surfaces GitHub renders richly:

  * ::error annotations  -> inline on the changed files + the Checks tab
  * a job summary        -> the run's summary page, as a Markdown table

Usage (inside a workflow step, after pytest has written the XML):

    .venv/bin/python scripts/pytest-summary.py /tmp/junit.xml \\
        --pytest-log /tmp/pytest.log

Exit status is ALWAYS 0: this is a reporting step and must never mask
pytest's own exit code (the calling step re-exits with that).

Stdlib only — no dependencies, no network.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# A traceback's final frame line: "/abs/path/to/test_x.py:31: AssertionError"
_LOCATION = re.compile(r"^(?P<path>.+?):(?P<line>\d+):\s*(?P<kind>\w+)?\s*$")
# pytest's own closing line: "179 passed, 5 deselected, 50 warnings in 8.17s"
_TALLY = re.compile(r"\b\d+ (?:passed|failed|error|errors|skipped|deselected|warning|warnings)\b")
# A warnings-summary entry body: "  /abs/path/file.py:409: DeprecationWarning: msg"
_WARNING = re.compile(
    r"^\s+(?P<path>/[^\s:]+):(?P<line>\d+): (?P<category>[A-Za-z_][\w.]*): ?(?P<msg>.*)$"
)
# Annotations are capped: 11 identical Pydantic warnings must not become 11
# banners on the Checks tab. Duplicates are collapsed; distinct ones capped.
MAX_WARNING_ANNOTATIONS = 15
_TOTALS = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}


def _repo_relative(path: str) -> str:
    """Annotations render best with a repo-relative path; fall back to as-is."""
    try:
        return str(Path(path).resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return path


def _one_line(text: str) -> str:
    """Collapse to a single line — tracebacks are multi-line."""
    return " ".join(text.split())[:900]


def _command_safe(text: str) -> str:
    """Escape for a workflow-command payload: single-line, and '%' must be
    escaped because the runner reads a bare '%' as an encoded newline.
    Applied only at the `::error`/`::warning` emit sites — the Markdown
    summary must keep the real text."""
    return _one_line(text).replace("%", "%25")


def _first_meaningful_line(failure_text: str) -> str:
    """The most useful single line of a traceback: the assertion, not the noise.

    Prefers pytest's own 'E   ...' detail line (the actual mismatch), falling
    back to the 'message' attribute, then the last non-empty line."""
    for line in failure_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("E "):
            return stripped[2:].strip()
    return ""


def _parse_failures(xml_path: Path) -> tuple[list[dict], dict]:
    """Return (failures, counts) from a pytest JUnit XML file."""
    if not xml_path.is_file():
        return [], {}
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError as exc:  # corrupt XML must not break the build
        print(f"::warning title=pytest-summary::could not parse {xml_path}: {exc}")
        return [], {}

    failures: list[dict] = []
    totals = dict(_TOTALS)

    for suite in root.iter("testsuite"):
        for key in totals:
            totals[key] += int(suite.get(key) or 0)

    for case in root.iter("testcase"):
        problem = case.find("failure")
        if problem is None:
            problem = case.find("error")
        if problem is None:
            continue

        raw = (problem.text or "") or problem.get("message") or ""
        location = {"path": case.get("file") or "", "line": "1"}
        for line in reversed(raw.splitlines()):
            match = _LOCATION.match(line.strip())
            if match and match.group("path"):
                location = {"path": match.group("path"), "line": match.group("line")}
                break

        classname = case.get("classname") or ""
        name = case.get("name") or "unknown"
        detail = (
            _first_meaningful_line(raw)
            or (problem.get("message") or "").splitlines()[0]
            or "failed"
        )
        failures.append(
            {
                "id": f"{classname}::{name}" if classname else name,
                "file": _repo_relative(location["path"]) if location["path"] else "",
                "line": location["line"],
                "detail": _one_line(detail),
            }
        )

    return failures, totals


def _parse_warnings(pytest_log: Path) -> list[dict]:
    """Distinct warnings from pytest's 'warnings summary' section.

    JUnit XML does not carry warnings at all — they only exist in stdout — so
    they are parsed from the log. Two reductions keep this useful rather than
    noisy:

      * a warning inside `.venv/`/`site-packages` is a dependency's business,
        not this repo's, and is dropped;
      * warnings are keyed by MESSAGE, not by (file, line). The same
        `on_event` deprecation reported at eight call sites is ONE problem,
        and eight identical banners on the Checks tab is noise. The first
        location is kept and the count is reported.

    Multi-line warnings (Rich/click style messages put the text on the lines
    AFTER the `Category: ` header) take their first non-blank continuation
    line, otherwise the annotation body would be empty.
    """
    if not pytest_log.is_file():
        return []
    lines = pytest_log.read_text(errors="replace").splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if "warnings summary" in line)
    except StopIteration:
        return []

    grouped: dict[tuple[str, str], dict] = {}
    for index, line in enumerate(lines[start:]):
        match = _WARNING.match(line)
        if not match:
            continue
        path = match.group("path")
        if "/.venv/" in path or "site-packages" in path:
            continue
        message = match.group("msg").strip() or _continuation(lines, start + index)
        if not message:
            continue
        key = (match.group("category"), message)
        if key in grouped:
            grouped[key]["count"] += 1
            continue
        grouped[key] = {
            "file": _repo_relative(path),
            "line": match.group("line"),
            "category": match.group("category"),
            "message": message,
            "count": 1,
        }
    return list(grouped.values())


def _continuation(lines: list[str], header_index: int) -> str:
    """First non-blank line after a warning header (multi-line messages)."""
    for line in lines[header_index + 1 : header_index + 6]:
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _emit_annotations(failures: list[dict]) -> None:
    for failure in failures:
        where = f"file={failure['file']}," if failure["file"] else ""
        title = _command_safe(failure["id"])
        print(
            f"::error {where}line={failure['line']},"
            f"title=pytest: {title}::{_command_safe(failure['detail'])}"
        )


def _emit_warnings(warnings: list[dict]) -> None:
    for warning in warnings[:MAX_WARNING_ANNOTATIONS]:
        where = f"file={warning['file']}," if warning["file"] else ""
        count = f" (+{warning['count'] - 1} more)" if warning["count"] > 1 else ""
        print(
            f"::warning {where}line={warning['line']},"
            f"title=pytest: {_command_safe(warning['category'])}"
            f"::{_command_safe(warning['message'] + count)}"
        )
    hidden = len(warnings) - MAX_WARNING_ANNOTATIONS
    if hidden > 0:
        print(
            f"::notice title=pytest::{hidden} further distinct warning(s) "
            "are listed in the job summary"
        )


def _tally_line(pytest_log: Path) -> str:
    """pytest's closing counts line, e.g. '179 passed, 5 deselected, 50 warnings'."""
    if not pytest_log.is_file():
        return ""
    for line in reversed(pytest_log.read_text(errors="replace").splitlines()):
        if _TALLY.search(line) and ("passed" in line or "failed" in line):
            return line.strip()
    return ""


def _write_summary(
    failures: list[dict],
    warnings: list[dict],
    totals: dict,
    tally: str,
    summary_file: str | None,
) -> None:
    if not summary_file:
        return
    lines: list[str] = []
    if failures:
        lines.append(f"## ❌ pytest — {len(failures)} failed")
    else:
        lines.append("## ✅ pytest — all tests passed")
    lines.append("")
    if tally:
        lines.append(f"`{tally}`")
        lines.append("")
    skipped = totals.get("skipped", 0)
    if skipped:
        lines.append(f"{skipped} skipped.")
        lines.append("")
    if failures:
        lines.append("| Test | Location | Failure |")
        lines.append("| ---- | -------- | ------- |")
        for failure in failures:
            where = f"`{failure['file']}:{failure['line']}`" if failure["file"] else "—"
            # Escape pipes so a message can't break the table.
            detail = failure["detail"].replace("|", "\\|")
            lines.append(f"| `{failure['id']}` | {where} | {detail} |")
        lines.append("")
    if warnings:
        lines.append(f"### ⚠️ {len(warnings)} distinct warning(s)")
        lines.append("")
        lines.append("| Location | Warning | Sites |")
        lines.append("| -------- | ------- | ----- |")
        for warning in warnings:
            where = f"`{warning['file']}:{warning['line']}`" if warning["file"] else "—"
            detail = f"{warning['category']}: {warning['message']}".replace("|", "\\|")
            lines.append(f"| {where} | {detail} | {warning['count']} |")
        lines.append("")
    try:
        with open(summary_file, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except OSError as exc:
        print(f"::warning title=pytest-summary::could not write summary: {exc}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("junit_xml", help="path to pytest's --junit-xml output")
    parser.add_argument(
        "--pytest-log",
        default="",
        help="pytest's captured stdout, for the closing counts line",
    )
    parser.add_argument(
        "--summary-file",
        default=os.environ.get("GITHUB_STEP_SUMMARY", ""),
        help="job summary file (defaults to $GITHUB_STEP_SUMMARY)",
    )
    args = parser.parse_args(argv)

    failures, totals = _parse_failures(Path(args.junit_xml))
    pytest_log = Path(args.pytest_log) if args.pytest_log else None
    warnings = _parse_warnings(pytest_log) if pytest_log else []
    _emit_annotations(failures)
    _emit_warnings(warnings)
    _write_summary(
        failures,
        warnings,
        totals,
        _tally_line(pytest_log) if pytest_log else "",
        args.summary_file,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
