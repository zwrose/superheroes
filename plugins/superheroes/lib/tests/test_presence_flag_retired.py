"""Census detector: owner-presence flag retired and provisional defaults disclosed (#1136).

Mechanical receipt for the issue DoD row requiring zero INTERACTIVE / ask-mode drift across
skills/, rubric/, reference/, lib/, and eval/. Each guarded element is independent — partial
drift that fixes one site while another silently decides without disclosing must still go red.

Deliberately out of scope (not bugs to "fix" here):
- lib/acceptance_rereview.py, lib/engine_authz.py, lib/engine_dispatch.py,
  lib/engine_adapter.py, lib/preflight_probe.py — "interactive" names a CLI invocation mode
  (-p/--print), not owner presence.
- lib/tests/test_discovery_doctrine.py — AskUserQuestion references are discovery's prohibition.
- rubric/covenant.md "parks and asks" — a park is the sanctioned hand-back.
"""
import os
import re
import subprocess

import pytest

import mode_registry as mr

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))

_CENSUS_ROOTS = [
    os.path.join(_PLUGIN_ROOT, "skills"),
    os.path.join(_PLUGIN_ROOT, "rubric"),
    os.path.join(_PLUGIN_ROOT, "reference"),
    os.path.join(_PLUGIN_ROOT, "lib"),
    os.path.join(_PLUGIN_ROOT, "eval"),
]

_SKILLS_ROOT = os.path.join(_PLUGIN_ROOT, "skills")
_REFERENCE_ROOT = os.path.join(_PLUGIN_ROOT, "reference")

_INTERACTIVE_PATTERNS = [
    re.compile(r"\$INTERACTIVE"),
    re.compile(r"(?<![\w-])INTERACTIVE(?![\w-])"),
    re.compile(r"^\s*INTERACTIVE=", re.MULTILINE),
]

# Files that necessarily name the retired literal to detect it — excluded from the census walk.
_CENSUS_SELF_PATHS = {
    os.path.normpath(os.path.join(_PLUGIN_ROOT, "lib/tests/test_presence_flag_retired.py")),
    os.path.normpath(os.path.join(_PLUGIN_ROOT, "lib/tests/test_review_only_headless.py")),
}

_BOOTSTRAP_SURFACES = [
    "skills/audit-debt/SKILL.md",
    "skills/review-spec/SKILL.md",
    "skills/review-init/SKILL.md",
    "skills/review-code/reference/setup.md",
    "skills/test-pilot-init/SKILL.md",
]

# Cross-doc literal-agreement pin: carrier noun is the only per-surface variable.
_DISCLOSURE_CARRIER_BY_SURFACE = {
    "skills/audit-debt/SKILL.md": "audit report",
    "skills/review-spec/SKILL.md": "terminal summary artifact",
    "skills/review-init/SKILL.md": "profile provenance block",
    "skills/review-code/reference/setup.md": "dispatch summary",
    "skills/test-pilot-init/SKILL.md": "profile provenance block",
}

# Byte-for-byte pins from shipped FIX-B prose (multi-line where the skill wraps the sentence).
_DISCLOSURE_PIN_BY_SURFACE = {
    "skills/audit-debt/SKILL.md": (
        "**Disclosure (provisional storage).** When `.provisional` is `true`, write into the "
        "**audit report**: the storage location taken, that it is a provisional default rather "
        "than an owner choice, and that `/superheroes:configure` changes it."
    ),
    "skills/review-spec/SKILL.md": (
        "**Disclosure (provisional storage).** When `.provisional` is `true`, write into the "
        "**terminal summary artifact**: the storage location taken, that it is a provisional "
        "default rather than an owner choice, and that `/superheroes:configure` changes it."
    ),
    "skills/review-init/SKILL.md": (
        "**Disclosure (provisional storage).** When `.provisional` is\n"
        "`true`, write into the **profile provenance block**: the storage location taken, that "
        "it is a\n"
        "provisional default rather than an owner choice, and that `/superheroes:configure` "
        "changes it."
    ),
    "skills/review-code/reference/setup.md": (
        "**Disclosure (provisional storage).** When `.provisional` is `true`, write into the "
        "**dispatch summary**: the storage location taken, that it is a provisional default "
        "rather than an owner choice, and that `/superheroes:configure` changes it."
    ),
    "skills/test-pilot-init/SKILL.md": (
        "**Disclosure (provisional storage).** When `.provisional` is\n"
        "`true`, write into the **profile provenance block**: the storage location taken, that "
        "it is a\n"
        "provisional default rather than an owner choice, and that `/superheroes:configure` "
        "changes it."
    ),
}

_DECIDE_MODE_DIRECT_PATTERN = re.compile(r"mode_registry\.decide_mode\(")

# Retired presence-premise spellings — byte-literal census with cardinality floor zero outside
# the explicit allowlist (in-class pinned literals; no meaning guard).
_PREMISE_LITERALS = ("no human", "nobody to answer", "headless run")

_PREMISE_LITERAL_ALLOWLIST = {
    # no human
    ("skills/review-code/SKILL.md", 361, "no human"): (
        "terminal report names why the ask-set stayed undecided — outcome disclosure, not a "
        "presence branch"
    ),
    # headless run
    ("skills/review-spec/reference/spec-detail.md", 16, "headless run"): (
        "bootstrap table row names provisional profile outcome without detecting presence"
    ),
    ("skills/review-code/reference/auto-fix-loop.md", 762, "headless run"): (
        "bootstrap table row names provisional profile outcome without detecting presence"
    ),
    ("skills/configure/reference/set-up.md", 48, "headless run"): (
        "configure records provisional core when owner did not answer — not a storage branch"
    ),
    ("skills/configure/reference/fix.md", 79, "headless run"): (
        "FR-17 records un-applied owner-choice fix — not a presence-detection branch"
    ),
    ("skills/configure/SKILL.md", 73, "headless run"): (
        "FR-14 table row: headless never flips storage — owner-choice fix recorded un-applied"
    ),
    ("skills/audit-debt/reference/sweep-detail.md", 42, "headless run"): (
        "bootstrap table row names provisional profile outcome without detecting presence"
    ),
    ("skills/audit-debt/SKILL.md", 116, "headless run"): (
        "inline bootstrap names provisional profile from defaults — not a presence branch"
    ),
    ("lib/engine_authz.py", 102, "headless run"): (
        "engine comment: CLI -p/--print invocation mode, not owner presence"
    ),
    ("lib/engine_adapter.py", 252, "headless run"): (
        "engine comment: CLI -p/--print invocation mode, not owner presence"
    ),
    ("lib/engine_adapter.py", 253, "headless run"): (
        "engine comment: CLI trust gate for non-interactive engine, not owner presence"
    ),
}


def _bootstrap_disclosure_window(text):
    """Pin bounding extractor: fenced bash block around decide-location plus following prose."""
    dl_idx = text.find("decide-location")
    if dl_idx < 0:
        return None
    search_start = max(0, dl_idx - 4000)
    region = text[search_start:dl_idx]
    bash_open = region.rfind("```bash")
    if bash_open < 0:
        bash_open = region.rfind("```")
    if bash_open < 0:
        return None
    window_start = search_start + bash_open
    bash_close = text.find("```", dl_idx)
    if bash_close < 0:
        return None
    window_end = bash_close + 3
    prose_lines = []
    started = False
    for line in text[window_end:].splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("```") or re.match(r"^#{1,6}\s", stripped):
            break
        if not stripped:
            if started:
                break
            continue
        started = True
        prose_lines.append(line)
    return text[window_start:window_end] + "".join(prose_lines)


def _read_plugin_rel(rel):
    path = os.path.join(_PLUGIN_ROOT, rel)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _walk_text_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
        for name in filenames:
            yield os.path.join(dirpath, name)


def _init_repo(d, remote=None):
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)
    if remote:
        subprocess.run(["git", "-C", str(d), "remote", "add", "origin", remote], check=True)


def _premise_literal_hits(literal):
    """Case-insensitive substring search; returns (rel, lineno, matched_substring) tuples."""
    hits = []
    needle = literal.casefold()
    for root in _CENSUS_ROOTS:
        for path in _walk_text_files(root):
            if os.path.normpath(path) in _CENSUS_SELF_PATHS:
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except (UnicodeDecodeError, OSError):
                continue
            rel = os.path.relpath(path, _PLUGIN_ROOT)
            for lineno, line in enumerate(text.splitlines(), 1):
                folded = line.casefold()
                start = 0
                while True:
                    idx = folded.find(needle, start)
                    if idx < 0:
                        break
                    hits.append((rel, lineno, literal))
                    start = idx + len(needle)
    return hits


# axis: zero INTERACTIVE / $INTERACTIVE / INTERACTIVE= anywhere under the census trees — every hit
# reported, not just the first. Not other spellings of "interactive".
def test_no_interactive_presence_flag_in_census_trees():
    """#1136 census: the retired presence flag must not survive anywhere under skills/lib/eval."""
    hits = []
    for root in _CENSUS_ROOTS:
        for path in _walk_text_files(root):
            if os.path.normpath(path) in _CENSUS_SELF_PATHS:
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except (UnicodeDecodeError, OSError):
                continue
            rel = os.path.relpath(path, _PLUGIN_ROOT)
            for lineno, line in enumerate(text.splitlines(), 1):
                for pat in _INTERACTIVE_PATTERNS:
                    if pat.search(line):
                        hits.append(f"{rel}:{lineno}: {line.strip()}")
    assert not hits, (
        "#1136 retired detecting owner presence — INTERACTIVE or $INTERACTIVE still present. "
        "Every hit:\n" + "\n".join(hits)
    )


# axis: no skill surface passes --interactive to decide-location — the old CLI flag must not
# return. Not other store.py subcommands.
def test_no_decide_location_interactive_flag_on_skill_surfaces():
    """Store CLI must not receive the retired --interactive flag from skills/reference."""
    hits = []
    for root in (_SKILLS_ROOT, _REFERENCE_ROOT):
        for path in _walk_text_files(root):
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except (UnicodeDecodeError, OSError):
                continue
            if "decide-location --interactive" in text:
                rel = os.path.relpath(path, _PLUGIN_ROOT)
                for lineno, line in enumerate(text.splitlines(), 1):
                    if "decide-location --interactive" in line:
                        hits.append(f"{rel}:{lineno}: {line.strip()}")
    assert not hits, (
        "a skill surface still passes decide-location --interactive — the flag is retired (#1136). "
        "Every hit:\n" + "\n".join(hits)
    )


# axis: no surface under skills/ calls mode_registry.decide_mode( directly — storage goes through CLI.
def test_no_direct_decide_mode_calls_in_skills():
    """#1136: skills must not bypass decide-location by calling mode_registry.decide_mode(."""
    hits = []
    for path in _walk_text_files(_SKILLS_ROOT):
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (UnicodeDecodeError, OSError):
            continue
        if not _DECIDE_MODE_DIRECT_PATTERN.search(text):
            continue
        rel = os.path.relpath(path, _PLUGIN_ROOT)
        for lineno, line in enumerate(text.splitlines(), 1):
            if _DECIDE_MODE_DIRECT_PATTERN.search(line):
                hits.append(f"{rel}:{lineno}: {line.strip()}")
    assert not hits, (
        "a skill surface still calls mode_registry.decide_mode( directly — use decide-location "
        "JSON instead (#1136). Every hit:\n" + "\n".join(hits)
    )


@pytest.mark.parametrize("literal", _PREMISE_LITERALS)
# axis: retired presence-premise spellings — cardinality floor zero outside explicit allowlist.
def test_retired_presence_premise_literals_census(literal):
    """#1136: premise spellings that detected owner presence must not survive unallowlisted."""
    hits = []
    for rel, lineno, matched in _premise_literal_hits(literal):
        if (rel, lineno, matched) not in _PREMISE_LITERAL_ALLOWLIST:
            hits.append(f"{rel}:{lineno}: {_read_plugin_rel(rel).splitlines()[lineno - 1].strip()}")
    assert not hits, (
        "retired presence-premise literal %r found outside the explicit allowlist (#1136). "
        "Every hit:\n" + "\n".join(hits)
    )


# axis: ask is unreachable from decide_mode — env override, recorded, backfilled, and greenfield
# inputs never return mode=ask. Not decide-location CLI wiring.
def test_decide_mode_never_returns_ask(tmp_path, monkeypatch):
    """Census home: decide_mode must never return ask across its input cross-product."""
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    monkeypatch.setattr(mr, "_hero_global_root", lambda n: str(tmp_path / ("g_" + n)))

    def _assert_no_ask(d):
        assert d["mode"] in (mr.IN_REPO, mr.GLOBAL)
        assert d["mode"] != "ask"

    _assert_no_ask(mr.decide_mode(str(tmp_path), mr.IN_REPO, root=root))
    _assert_no_ask(mr.decide_mode(str(tmp_path), mr.GLOBAL, root=root))
    _assert_no_ask(mr.decide_mode(str(tmp_path), "bogus", root=root))

    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _assert_no_ask(mr.decide_mode(str(tmp_path), None, root=root))

    repo2 = tmp_path / "repo2"
    repo2.mkdir()
    _init_repo(repo2)
    (repo2 / ".claude").mkdir()
    (repo2 / ".claude" / "review-profile.md").write_text("x")
    _assert_no_ask(mr.decide_mode(str(repo2), None, root=root))

    repo3 = tmp_path / "repo3"
    repo3.mkdir()
    _init_repo(repo3)
    _assert_no_ask(mr.decide_mode(str(repo3), None, root=root))


# axis: cardinality floor — exactly five bootstrap surfaces carry the disclosure pin.
def test_bootstrap_disclosure_pin_cardinality_floor():
    """#1136: a surface silently dropping out of the disclosure census must go red."""
    assert len(_BOOTSTRAP_SURFACES) == 5
    assert set(_BOOTSTRAP_SURFACES) == set(_DISCLOSURE_PIN_BY_SURFACE)
    assert set(_DISCLOSURE_CARRIER_BY_SURFACE) == set(_BOOTSTRAP_SURFACES)


@pytest.mark.parametrize("surface_rel", _BOOTSTRAP_SURFACES)
# axis: each converted bootstrap carries the byte-pinned disclosure sentence in its home window.
def test_bootstrap_surface_reads_provisional_and_discloses(surface_rel):
    """A site that takes the storage default without the pinned disclosure sentence decides silently."""
    text = _read_plugin_rel(surface_rel)
    assert "decide-location" in text, (
        "%s no longer calls decide-location — if bootstrap moved, re-point this detector (#1136)"
        % surface_rel
    )
    assert re.search(r"jq\s+-r\s+['\"]\.provisional['\"]", text), (
        "%s does not read `.provisional` from decide-location JSON — provisional defaults cannot "
        "be disclosed mechanically (#1136)" % surface_rel
    )
    window = _bootstrap_disclosure_window(text)
    assert window is not None, (
        "%s has no fenced bootstrap block around decide-location — if bootstrap moved, "
        "re-point this detector (#1136)" % surface_rel
    )
    pin = _DISCLOSURE_PIN_BY_SURFACE[surface_rel]
    assert pin in window, (
        "%s is missing the byte-pinned disclosure sentence for carrier %r in the bootstrap window "
        "— a default would be taken silently (#1136)" % (
            surface_rel, _DISCLOSURE_CARRIER_BY_SURFACE[surface_rel])
    )
