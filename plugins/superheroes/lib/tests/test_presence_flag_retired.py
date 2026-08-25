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


@pytest.mark.parametrize("surface_rel", _BOOTSTRAP_SURFACES)
# axis: each converted bootstrap reads .provisional and discloses when true — one surface per case,
# never a joined blob. Not decide-location JSON shape in lib/.
def test_bootstrap_surface_reads_provisional_and_discloses(surface_rel):
    """A site that takes the storage default without disclosing it decides silently (#1136)."""
    text = _read_plugin_rel(surface_rel)
    assert "decide-location" in text, (
        "%s no longer calls decide-location — if bootstrap moved, re-point this detector (#1136)"
        % surface_rel
    )
    assert re.search(r"jq\s+-r\s+['\"]\.provisional['\"]", text), (
        "%s does not read `.provisional` from decide-location JSON — provisional defaults cannot "
        "be disclosed mechanically (#1136)" % surface_rel
    )
    disclosure = (
        re.search(
            r"\*\*Disclosure:\*\*.*provisional",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        or re.search(
            r"When\s+[`\$]?(?:\.provisional|PROVISIONAL).*provisional",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        or re.search(
            r"provisional.*dispatch summary|dispatch summary.*provisional",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    )
    assert disclosure, (
        "%s has no disclosure language keyed to provisional storage — a default would be taken "
        "silently (#1136)" % surface_rel
    )
    assert "/superheroes:configure" in text, (
        "%s does not name /superheroes:configure as the follow-up for provisional storage — "
        "the triad's follow-up pointer is missing (#1136)" % surface_rel
    )
