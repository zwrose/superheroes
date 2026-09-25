"""Active requirement-line parsing for CI workflow oracle tests."""
from __future__ import annotations

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
