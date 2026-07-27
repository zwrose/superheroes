"""Bytecode-free plugin invocation drift guard (issue #652 rider 1).

Every plugin-controlled ``python3`` invocation must pass ``-B`` so the versioned
install cache does not accumulate ``__pycache__`` noise that reads as local
modifications during plugin updates. Skill prose and SessionStart/PreToolUse hooks
are the two surfaces that drive the highest traffic.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))

# ``python3`` followed by whitespace must be immediately ``python3 -B``.
_MISSING_B = re.compile(r"python3\s+(?!-B\b)")
# E3: incomplete invocation at end of line (must fail, not crash).
_PYTHON3_EOL = re.compile(r"python3\s*$")


def _skill_md_paths():
    skills_root = os.path.join(PLUGIN, "skills")
    paths = []
    for dirpath, _dirs, files in os.walk(skills_root):
        for name in files:
            if name.endswith(".md"):
                paths.append(os.path.relpath(os.path.join(dirpath, name), PLUGIN))
    return sorted(paths)


def _violations_in_text(rel_path, text):
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.rstrip("\n")
        if _PYTHON3_EOL.search(stripped):
            hits.append("%s:%d: %s" % (rel_path, lineno, stripped))
            continue
        for _ in _MISSING_B.finditer(line):
            hits.append("%s:%d: %s" % (rel_path, lineno, stripped))
            break
    return hits


def test_skill_python3_invocations_use_bytecode_free_flag():
    """Every ``python3`` invocation in skill ``.md`` files includes ``-B``."""
    md_paths = _skill_md_paths()
    assert md_paths, "skills/: expected at least one .md file (wrong PLUGIN path?)"
    invocation_count = 0
    violations = []
    for rel in md_paths:
        path = os.path.join(PLUGIN, rel)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        invocation_count += len(re.findall(r"python3\s+", text))
        violations.extend(_violations_in_text(rel, text))
    assert invocation_count > 0, (
        "skills/: expected at least one python3 invocation (census drift?)"
    )
    assert not violations, (
        "plugin python3 invocations must use -B (issue #652 rider 1); fix:\n"
        + "\n".join(violations)
    )


def test_hooks_json_python3_invocations_use_bytecode_free_flag():
    """SessionStart and PreToolUse hook commands invoke python3 with ``-B``."""
    rel = os.path.join("hooks", "hooks.json")
    path = os.path.join(PLUGIN, rel)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    invocation_count = len(re.findall(r"python3\s+", text))
    assert invocation_count > 0, "hooks/hooks.json: expected python3 hook commands"
    violations = _violations_in_text(rel, text)
    assert not violations, (
        "hooks/hooks.json python3 invocations must use -B (issue #652 rider 1); fix:\n"
        + "\n".join(violations)
    )
