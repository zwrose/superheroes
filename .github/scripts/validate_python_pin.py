#!/usr/bin/env python3
"""UFR-8: one Python pin in `.python-version`; homes must not name other interpreters."""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from collections import namedtuple
from typing import Iterable, List, Optional, Sequence

Violation = namedtuple("Violation", ("rule", "path", "line", "detail"))

_DEFAULT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Declared homes (validate_python_pin.py excludes itself — never scan the guard).
_EXPLICIT_HOMES = (
    "requirements-dev.txt",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "RELEASING.md",
    "README.md",
    "conftest.py",
    "source_guard.py",
    "pytest.ini",
    ".github/pull_request_template.md",
    "eval/README.md",
    "eval/skills/README.md",
    "plugins/superheroes/eval/README.md",
    "docs/superheroes/KEEP-OR-RETIRE.md",
    "plugins/superheroes/lib/dispatch_entry_doc.py",
    "plugins/superheroes/skills/workhorse/reference/dispatch-entry.md",
    "plugins/superheroes/lib/tests/test_round_certification_fixture_generator_drift.py",
)
_SELF_SCRIPT = ".github/scripts/validate_python_pin.py"

_PIN_LINE_RE = re.compile(r"^3\.\d+(\.\d+)?$")

_ABS_INTERPRETER_RE = re.compile(
    r"(?<![\w.$-])(?:~)?/(?:[\w.+-]+/)+python(?:\d+(?:\.\d+)*)?(?![\w.-])"
)

_VERSION_PATTERNS: Sequence[tuple[re.Pattern[str], Optional[str]]] = (
    (re.compile(r"python-version\s*:\s*[\"']?(\d+(?:\.\d+)+)", re.I), None),
    (re.compile(r"\bpython(\d+(?:\.\d+)+)\b", re.I), None),
    (re.compile(r"\bpython[\s*_`]+v?(\d+\.\d+(?:\.\d+)?)", re.I), None),
    (re.compile(r"\bpy3(\d{1,2})\b", re.I), "3."),
    (re.compile(r"--python[=\s]+[\"']?(\d+(?:\.\d+)*)", re.I), None),
    (re.compile(r"\bUV_PYTHON\s*[=:]\s*[\"']?(\d+(?:\.\d+)*)", re.I), None),
    (re.compile(r"\bcpython-(\d+\.\d+(?:\.\d+)?)", re.I), None),
)

_WORKFLOW_PY_VERSION_LINE_RE = re.compile(r"^\s*-?\s*python-version\s*:", re.I)

_RUN_PYTHON_BEFORE_RE = re.compile(
    r"(?<![\w/.-])(?:python[\d.]*|pip3?)(?![\w-])|\buv\s+pip\b",
    re.I,
)

_SETUP_PYTHON_USES = "actions/setup-python"

_BARE_INTERPRETER_CMD_RE = re.compile(
    r"(?:"
    r"(?:(?:^|[\n\r])\s*(?:[-*+]\s+)?)"
    r"|`"
    r"|(?:\$\s+)"
    r"|(?:&&\s+)"
    r"|(?:;\s+)"
    r"|(?:\|\s+)"
    r"|(?:\(\s*)"
    r")"
    r"(?!scripts/pinned-python\b)"
    r"(?:python\d*(?:\.\d+)*|pip3?)\b(?=\s)"
)

_PIN_HOME_WALK_SKIP = frozenset({".git", "node_modules", ".venv", "venv"})


def _rel(root: str, path: str) -> str:
    return os.path.relpath(path, root).replace(os.sep, "/")


def _versions_agree(pin: str, found: str) -> bool:
    p_parts = pin.split(".")
    f_parts = found.split(".")
    n = min(len(p_parts), len(f_parts))
    return all(int(p_parts[i]) == int(f_parts[i]) for i in range(n))


def _read_pin(root: str, violations: List[Violation]) -> Optional[str]:
    pin_path = os.path.join(root, ".python-version")
    rel_pin = ".python-version"
    if not os.path.isfile(pin_path):
        violations.append(Violation("pin-missing", rel_pin, None, "missing pin file"))
        return None
    try:
        raw = open(pin_path, encoding="utf-8").read()
    except OSError as exc:
        violations.append(
            Violation("home-unreadable", rel_pin, None, "cannot read pin: %s" % exc)
        )
        return None
    lines = [ln.strip() for ln in raw.splitlines()]
    non_empty = [ln for ln in lines if ln]
    if len(non_empty) != 1 or not _PIN_LINE_RE.match(non_empty[0]):
        violations.append(
            Violation(
                "pin-malformed",
                rel_pin,
                None,
                "expected exactly one version line matching 3.N or 3.N.P",
            )
        )
        return None
    return non_empty[0]


def _check_pin_home_duplicates(root: str, violations: List[Violation]) -> None:
    root_pin = os.path.normpath(os.path.join(root, ".python-version"))
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _PIN_HOME_WALK_SKIP]
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = _rel(root, full)
            if name == ".python-versions":
                violations.append(
                    Violation(
                        "pin-home-duplicate",
                        rel,
                        None,
                        "competing Python pin home",
                    )
                )
            elif name == ".python-version" and os.path.normpath(full) != root_pin:
                violations.append(
                    Violation(
                        "pin-home-duplicate",
                        rel,
                        None,
                        "nested .python-version competes with root pin",
                    )
                )


def _iter_homes(root: str, violations: List[Violation]) -> List[tuple[str, bool]]:
    """Return (repo-relative path, is_workflow) for every home file to scan."""
    homes: List[tuple[str, bool]] = []

    for rel in _EXPLICIT_HOMES:
        if not os.path.isfile(os.path.join(root, rel)):
            violations.append(
                Violation("home-missing", rel, None, "declared home does not exist")
            )
        else:
            homes.append((rel, False))

    wf_patterns = (
        os.path.join(root, ".github", "workflows", "*.yml"),
        os.path.join(root, ".github", "workflows", "*.yaml"),
    )
    wf_files: List[str] = []
    for pattern in wf_patterns:
        wf_files.extend(glob.glob(pattern))
    wf_files = sorted(set(wf_files))
    if not wf_files:
        violations.append(
            Violation(
                "home-missing",
                ".github/workflows",
                None,
                "workflow glob matched no files",
            )
        )
    else:
        for path in wf_files:
            homes.append((_rel(root, path), True))

    script_py = sorted(
        p
        for p in glob.glob(os.path.join(root, ".github", "scripts", "*.py"))
        if _rel(root, p) != _SELF_SCRIPT
    )
    if not script_py:
        violations.append(
            Violation(
                "home-missing",
                ".github/scripts/*.py",
                None,
                "script glob matched no files",
            )
        )
    else:
        for path in script_py:
            homes.append((_rel(root, path), False))

    script_files = sorted(
        p
        for p in glob.glob(os.path.join(root, "scripts", "*"))
        if os.path.isfile(p)
    )
    if not script_files:
        violations.append(
            Violation(
                "home-missing",
                "scripts/*",
                None,
                "scripts glob matched no files",
            )
        )
    else:
        for path in script_files:
            homes.append((_rel(root, path), False))

    return homes


def _scan_line_rules(
    pin: str,
    rel: str,
    text: str,
    violations: List[Violation],
    workflow_only: bool,
) -> None:
    for line_no, line in enumerate(text.splitlines(), start=1):
        if _ABS_INTERPRETER_RE.search(line):
            violations.append(
                Violation(
                    "absolute-interpreter-path",
                    rel,
                    line_no,
                    "absolute interpreter path",
                )
            )
        for pattern, prefix in _VERSION_PATTERNS:
            for match in pattern.finditer(line):
                ver = match.group(1)
                if prefix is not None:
                    ver = prefix + ver
                if not _versions_agree(pin, ver):
                    violations.append(
                        Violation(
                            "version-literal-mismatch",
                            rel,
                            line_no,
                            "version %s disagrees with pin %s" % (ver, pin),
                        )
                    )
        if workflow_only and _WORKFLOW_PY_VERSION_LINE_RE.match(line):
            violations.append(
                Violation(
                    "workflow-python-version-literal",
                    rel,
                    line_no,
                    "workflow must use python-version-file, not python-version",
                )
            )
        if not workflow_only and _BARE_INTERPRETER_CMD_RE.search(line):
            violations.append(
                Violation(
                    "bare-interpreter-command",
                    rel,
                    line_no,
                    "bare ambient python or pip command",
                )
            )


def _job_default_run_shell(job: dict, workflow_defaults_shell: Optional[str]) -> Optional[str]:
    defaults = job.get("defaults")
    if isinstance(defaults, dict):
        run = defaults.get("run")
        if isinstance(run, dict):
            shell = run.get("shell")
            if isinstance(shell, str):
                return shell
    return workflow_defaults_shell


def _workflow_default_run_shell(doc: dict) -> Optional[str]:
    defaults = doc.get("defaults")
    if not isinstance(defaults, dict):
        return None
    run = defaults.get("run")
    if not isinstance(run, dict):
        return None
    shell = run.get("shell")
    return shell if isinstance(shell, str) else None


def _step_runs_python(step: dict, job_default_shell: Optional[str]) -> bool:
    if not isinstance(step, dict):
        return False
    shell = step.get("shell")
    if isinstance(shell, str) and shell.strip().lower().startswith("python"):
        return True
    run = step.get("run")
    if not isinstance(run, str):
        return False
    if job_default_shell and job_default_shell.strip().lower().startswith("python"):
        return True
    return bool(_RUN_PYTHON_BEFORE_RE.search(run))


def _uses_action(step: dict, action: str) -> bool:
    uses = step.get("uses")
    if not isinstance(uses, str):
        return False
    base = uses.split("@", 1)[0]
    return base == action


def _check_workflow_structure(
    pin: str, rel: str, text: str, violations: List[Violation]
) -> None:
    try:
        import yaml
    except ImportError:
        violations.append(
            Violation("yaml-unavailable", rel, None, "PyYAML is not installed")
        )
        return

    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        violations.append(
            Violation("workflow-unparseable", rel, None, "YAML parse error: %s" % exc)
        )
        return

    if doc is not None and not isinstance(doc, dict):
        violations.append(
            Violation("workflow-unparseable", rel, None, "top level is not a mapping")
        )
        return

    if not doc:
        return

    workflow_default_shell = _workflow_default_run_shell(doc)

    jobs = doc.get("jobs")
    if jobs is None:
        return
    if not isinstance(jobs, dict):
        violations.append(
            Violation("workflow-unparseable", rel, None, "jobs is not a mapping")
        )
        return

    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps")
        if steps is None:
            continue
        if not isinstance(steps, list):
            continue
        job_default_shell = _job_default_run_shell(job, workflow_default_shell)
        _check_job_steps(rel, steps, violations, job_default_shell)


def _check_job_steps(
    rel: str,
    steps: list,
    violations: List[Violation],
    job_default_shell: Optional[str] = None,
) -> None:
    pinned_index: Optional[int] = None
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        if _uses_action(step, _SETUP_PYTHON_USES):
            with_block = step.get("with")
            if not isinstance(with_block, dict):
                violations.append(
                    Violation(
                        "workflow-setup-python-unpinned",
                        rel,
                        None,
                        "setup-python missing python-version-file: .python-version",
                    )
                )
            elif with_block.get("python-version-file") != ".python-version":
                violations.append(
                    Violation(
                        "workflow-setup-python-unpinned",
                        rel,
                        None,
                        "setup-python python-version-file must be .python-version",
                    )
                )
            else:
                if pinned_index is None:
                    pinned_index = idx

    for idx, step in enumerate(steps):
        if not _step_runs_python(step, job_default_shell):
            continue
        if pinned_index is None or idx < pinned_index:
            violations.append(
                Violation(
                    "workflow-python-before-setup",
                    rel,
                    None,
                    "Python runs before pinned setup-python in job",
                )
            )


def check(root: str) -> List[Violation]:
    # Axis: the pin's disagreement — a home that names an interpreter path, a version other than the pin, or a workflow Python not read from .python-version — exits 1 with the rule token; never a clean exit on an unreadable or missing home.
    violations: List[Violation] = []
    try:
        import yaml  # noqa: F401
    except ImportError:
        violations.append(
            Violation("yaml-unavailable", ".", None, "PyYAML is not installed")
        )
        return violations

    pin = _read_pin(root, violations)
    _check_pin_home_duplicates(root, violations)
    homes = _iter_homes(root, violations)
    if pin is None:
        return violations

    for rel, is_workflow in homes:
        abs_path = os.path.join(root, rel)
        try:
            text = open(abs_path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError) as exc:
            violations.append(
                Violation("home-unreadable", rel, None, "cannot read: %s" % exc)
            )
            continue
        _scan_line_rules(pin, rel, text, violations, is_workflow)
        if is_workflow:
            _check_workflow_structure(pin, rel, text, violations)

    seen: set[tuple] = set()
    unique: List[Violation] = []
    for v in violations:
        key = (v.rule, v.path, v.line, v.detail)
        if key in seen:
            continue
        seen.add(key)
        unique.append(v)
    return unique


def _format_violation(v: Violation) -> str:
    loc = v.path
    if v.line is not None:
        loc = "%s:%s" % (v.path, v.line)
    return "validate_python_pin: %s: %s: %s" % (v.rule, loc, v.detail)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="validate single Python pin (UFR-8)")
    parser.add_argument(
        "--root",
        default=_DEFAULT_ROOT,
        help="repository root (default: two levels above this script)",
    )
    parser.add_argument(
        "--require-running-pin",
        action="store_true",
        help="also require the running interpreter major.minor to match the pin",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    root = os.path.abspath(args.root)

    violations = check(root)
    if not violations and args.require_running_pin:
        pin_path = os.path.join(root, ".python-version")
        pin_line = (
            open(pin_path, encoding="utf-8").read().strip().splitlines()[0].strip()
        )
        running = "%d.%d" % sys.version_info[:2]
        if not _versions_agree(pin_line, running):
            violations.append(
                Violation(
                    "running-interpreter-mismatch",
                    ".python-version",
                    None,
                    "running interpreter %s disagrees with pin %s"
                    % (running, pin_line),
                )
            )
    if violations:
        for v in violations:
            print(_format_violation(v))
        print(
            "validate_python_pin: FAIL (%d violation(s))"
            % len(violations)
        )
        return 1

    pin_path = os.path.join(root, ".python-version")
    pin_line = open(pin_path, encoding="utf-8").read().strip().splitlines()[0].strip()
    _scratch: List[Violation] = []
    homes_checked = len(_iter_homes(root, _scratch))
    print(
        "validate_python_pin: ok (pin %s, %d homes checked)"
        % (pin_line, homes_checked)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
