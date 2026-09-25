"""Active requirement-line parsing for CI workflow oracle tests."""
from __future__ import annotations

import os
import re


def active_requirements_content(raw: str) -> str:
    """PEP 508 lines only — omit full-line and trailing inline # comments."""
    lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0]
        part = line.strip()
        if part:
            lines.append(part)
    return "\n".join(lines)


def requirement_package_name(line: str) -> str:
    name = re.split(r"[<>=!~\[]", line.strip(), maxsplit=1)[0].strip()
    return name.lower().replace("_", "-")


def active_requirement_names(active_text: str) -> set[str]:
    return {
        requirement_package_name(line)
        for line in active_text.splitlines()
        if line.strip()
    }


def _strip_unquoted_shell_comment(line: str) -> str:
    in_single = in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:i]
    return line


def run_text_for_requirement_scan(run_text: str) -> str:
    """Shell run text with full-line and unquoted inline # comments removed."""
    lines: list[str] = []
    for line in run_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        part = _strip_unquoted_shell_comment(line).rstrip()
        if part.strip():
            lines.append(part)
    return "\n".join(lines)


def expand_requirements(run_text: str, repo_root: str) -> str:
    """Run text plus contents of every requirements file named via -r or --requirement."""
    executable = run_text_for_requirement_scan(run_text)
    expanded = executable
    tokens = executable.split()
    i = 0
    while i < len(tokens):
        if tokens[i] in ("-r", "--requirement") and i + 1 < len(tokens):
            req_rel = tokens[i + 1]
            req_path = (
                req_rel
                if os.path.isabs(req_rel)
                else os.path.join(repo_root, req_rel)
            )
            if not os.path.isfile(req_path):
                raise AssertionError(f"requirements file does not exist: {req_rel}")
            with open(req_path, encoding="utf-8") as fh:
                expanded += "\n" + active_requirements_content(fh.read())
            i += 2
        else:
            i += 1
    return expanded
