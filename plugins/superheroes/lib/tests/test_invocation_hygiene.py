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

# ``python3`` followed by whitespace must be ``python3`` then optional whitespace and ``-B``.
_MISSING_B = re.compile(r"python3\s+(?!\s*-B\b)")
# E3: incomplete invocation at end of line (must fail, not crash); not a shebang.
_PYTHON3_EOL = re.compile(r"python3\s*$")
_SHEBANG_PYTHON3 = re.compile(r"^#!/usr/bin/(?:env )?python3\s*$")

_PLUGIN_MD_ROOTS = (
    "skills",
    "reference",
    "agents",
    "hosts",
    "rubric",
    "templates",
)


def _plugin_md_paths():
    paths = []
    for root in _PLUGIN_MD_ROOTS:
        base = os.path.join(PLUGIN, root)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirs, files in os.walk(base):
            for name in files:
                if name.endswith(".md"):
                    paths.append(os.path.relpath(os.path.join(dirpath, name), PLUGIN))
    return sorted(paths)


def _violations_in_text(rel_path, text):
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.rstrip("\n")
        if _SHEBANG_PYTHON3.match(stripped):
            continue
        if _PYTHON3_EOL.search(stripped):
            hits.append("%s:%d: %s" % (rel_path, lineno, stripped))
            continue
        for _ in _MISSING_B.finditer(line):
            hits.append("%s:%d: %s" % (rel_path, lineno, stripped))
            break
    return hits


def test_matcher_accepts_python3_b_with_one_space():
    assert not _violations_in_text("x.md", "python3 -B foo.py")


def test_matcher_accepts_python3_b_with_two_spaces():
    assert not _violations_in_text("x.md", "python3  -B foo.py")


def test_matcher_flags_bare_python3_invocation():
    hits = _violations_in_text("x.md", "python3 foo.py")
    assert len(hits) == 1


def test_matcher_flags_python3_c_invocation():
    hits = _violations_in_text("x.md", 'python3 -c "print(1)"')
    assert len(hits) == 1


def test_matcher_flags_python3_at_end_of_line():
    hits = _violations_in_text("x.md", "ROOT=1\npython3\n  foo.py")
    assert any("python3" in h for h in hits)


def test_matcher_ignores_env_python3_shebang():
    text = "#!/usr/bin/env python3\npython3 -B run.py\n"
    assert not _violations_in_text("x.md", text)


def test_matcher_ignores_bin_python3_shebang():
    assert not _violations_in_text("x.md", "#!/usr/bin/python3\n")


def test_skill_python3_invocations_use_bytecode_free_flag():
    """Every ``python3`` invocation in plugin ``.md`` files includes ``-B``."""
    md_paths = _plugin_md_paths()
    assert md_paths, (
        "expected at least one .md under plugin md roots (wrong PLUGIN path?)"
    )
    invocation_count = 0
    violations = []
    for rel in md_paths:
        path = os.path.join(PLUGIN, rel)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        invocation_count += len(re.findall(r"python3\s+", text))
        violations.extend(_violations_in_text(rel, text))
    assert invocation_count > 0, (
        "plugin md roots: expected at least one python3 invocation (census drift?)"
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
