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

# Bite-proof records are receipts, not consumed surfaces: they are categorically outside every
# content census, exactly as detector self-paths are. A proof must be free to quote the literal
# it proves — a census that polices its own evidence re-fires on every new proof.
# Standing advisor ruling, 2026-08-25 (#1136).
_CENSUS_EXCLUDED_DIRS = (
    os.path.normpath(os.path.join(_PLUGIN_ROOT, "lib/tests/bite_proofs")),
)


def _census_excluded(path):
    """Files the census must not read: detector self-paths and bite-proof receipts."""
    norm = os.path.normpath(path)
    if norm in _CENSUS_SELF_PATHS:
        return True
    return any(
        norm.startswith(d + os.sep) for d in _CENSUS_EXCLUDED_DIRS
    )


_DECIDE_LOCATION_INVOCATION = re.compile(r"decide-location\)")

# Conversation-driven surfaces disclose in the run transcript, not a durable file artifact (R-2).
_CONVERSATION_DRIVEN_DISCLOSURE_SURFACES = frozenset({
    "skills/configure/reference/set-up.md",
})

# Cross-doc literal-agreement pin: carrier noun is the only per-surface variable.
_DISCLOSURE_CARRIER_BY_SURFACE = {
    "skills/audit-debt/SKILL.md": "audit report",
    "skills/review-spec/SKILL.md": "receipt",
    "skills/review-init/SKILL.md": "review-crew layer body",
    "skills/review-code/reference/setup.md": "dispatch summary",
    "skills/test-pilot-init/SKILL.md": "test-pilot layer body",
    "skills/configure/reference/set-up.md": "set-up output",
}

# Byte-for-byte pins from shipped prose (multi-line where the skill wraps the sentence).
_DISCLOSURE_PIN_BY_SURFACE = {
    "skills/audit-debt/SKILL.md": (
        "**Storage location (`decide-location`).** `decide-location` returns JSON: `.mode` is "
        "`in-repo` or `global` (`ask` no longer exists); `.source` is where the decision came from: "
        "`env` (environment override `REVIEW_CREW_STORAGE` for this run only; never recorded), "
        "`registry` (a mode the owner recorded; authoritative), `backfilled` (a mode inferred from "
        "consistent existing evidence and then recorded), `provisional` (nothing recorded and no "
        "consistent evidence; the lib's default, re-taken next run); `.provisional` is `true` when "
        "the mode was not owner-recorded. **Default:** the returned `.mode` (recorded when "
        "configured, else the lib's provisional default). Bootstrap blocks never record — an "
        "unrecorded mode is re-taken next run. **Disclosure.** Write into the **audit report** "
        "(`$SESSION_DIR/report.md`): the storage mode taken, its source, whether it is provisional, "
        "and that `/superheroes:configure` changes it. When `.provisional` is `true`, also state "
        "that it is a provisional default rather than an owner choice and will be re-taken on the "
        "next run when not recorded. **Follow-up:** `/superheroes:configure`.\n"
    ),
    "skills/review-spec/SKILL.md": (
        "**Storage location.** `decide-location` JSON: `.mode` (`in-repo`|`global`; `ask` gone), "
        "`.source`\n"
        "(`env` — `REVIEW_CREW_STORAGE` override this run, never recorded; `registry` — "
        "owner-recorded; `backfilled` — inferred then recorded; `provisional` — lib default, "
        "re-taken next run), `.provisional` (`true` when not owner-recorded). **Default:**\n"
        "returned `.mode`. Bootstrap blocks never record — unrecorded modes re-taken next run.\n"
        "**Disclosure.** Write into `$SESSION_DIR/receipt.md` (assembled in §6): mode, source, "
        "provisional\n"
        "status, and `/superheroes:configure` follow-up; when `.provisional` is `true`, note it is "
        "a\n"
        "provisional default and will be re-taken next run when not recorded.\n"
    ),
    "skills/review-init/SKILL.md": (
        "**Storage location (`decide-location`).** `decide-location` returns JSON: `.mode` is "
        "`in-repo` or\n"
        "`global` (`ask` no longer exists); `.source` is where the decision came from: `env` "
        "(environment\n"
        "override `REVIEW_CREW_STORAGE` for this run only; never recorded), `registry` (a mode the "
        "owner\n"
        "recorded; authoritative), `backfilled` (a mode inferred from consistent existing evidence "
        "and then\n"
        "recorded), `provisional` (nothing recorded and no consistent evidence; the lib's default, "
        "re-taken\n"
        "next run); `.provisional` is `true` when the mode was not owner-recorded. **Default:**\n"
        "the returned `.mode` (recorded when configured, else the lib's provisional default). "
        "Bootstrap\n"
        "blocks never record — an unrecorded mode is re-taken next run. **Disclosure.** Write into "
        "the\n"
        "**review-crew layer body** (`$REVIEW_LAYER_BODY`, written through `core_md.py write-layer` "
        "in Step\n"
        "4b — a `## Setup disclosures` section, not the generated provenance block): the storage "
        "mode\n"
        "taken, its source, whether it is provisional, and that `/superheroes:configure` changes "
        "it. When\n"
        "`.provisional` is `true`, also state that it is a provisional default rather than an "
        "owner choice\n"
        "and will be re-taken on the next run when not recorded. **Follow-up:** "
        "`/superheroes:configure`.\n"
        "The minted `$PROFILE` is the path Step 4 writes to.\n"
    ),
    "skills/review-code/reference/setup.md": (
        "**Storage location (`decide-location`).** `decide-location` returns JSON: `.mode` is "
        "`in-repo` or `global` (`ask` no longer exists); `.source` is where the decision came from: "
        "`env` (environment override `REVIEW_CREW_STORAGE` for this run only; never recorded), "
        "`registry` (a mode the owner recorded; authoritative), `backfilled` (a mode inferred from "
        "consistent existing evidence and then recorded), `provisional` (nothing recorded and no "
        "consistent evidence; the lib's default, re-taken next run); `.provisional` is `true` when "
        "the mode was not owner-recorded. **Default:** the returned `.mode` (recorded when "
        "configured, else the lib's provisional default). Bootstrap blocks never record — an "
        "unrecorded mode is re-taken next run. **Disclosure.** Write into `$SESSION_DIR/meta.json` "
        "when that file is written (`storageMode`, `storageSource`, `storageProvisional` from "
        "`$LOC`, `$SOURCE`, `$PROVISIONAL`) — the durable session record review-code's setup path "
        "owns — and repeat the same facts in the **dispatch summary** for visibility. When "
        "`.provisional` is `true`, also state that it is a provisional default rather than an "
        "owner choice and will be re-taken on the next run when not recorded, and that "
        "`/superheroes:configure` changes it. **Follow-up:** `/superheroes:configure`.\n"
    ),
    "skills/test-pilot-init/SKILL.md": (
        "**Storage location (`decide-location`).** `decide-location` returns JSON: `.mode` is "
        "`in-repo` or\n"
        "`global` (`ask` no longer exists); `.source` is where the decision came from: `env` "
        "(environment\n"
        "override `TEST_PILOT_STORAGE` for this run only; never recorded), `registry` (a mode the "
        "owner\n"
        "recorded; authoritative), `backfilled` (a mode inferred from consistent existing evidence "
        "and then\n"
        "recorded), `provisional` (nothing recorded and no consistent evidence; the lib's default, "
        "re-taken\n"
        "next run); `.provisional` is `true` when the mode was not owner-recorded. **Default:**\n"
        "the returned `.mode` (recorded when configured, else the lib's provisional default). "
        "Bootstrap\n"
        "blocks never record — an unrecorded mode is re-taken next run. **Disclosure.** Write into "
        "the\n"
        "**test-pilot layer body** (the markdown piped to `core_md.py write-layer --hero "
        "test-pilot` in\n"
        "Step 6 — a `## Setup disclosures` section, not the generated provenance block): the "
        "storage mode\n"
        "taken, its source, whether it is provisional, and that `/superheroes:configure` changes "
        "it. When\n"
        "`.provisional` is `true`, also state that it is a provisional default rather than an "
        "owner choice\n"
        "and will be re-taken on the next run when not recorded. **Follow-up:** "
        "`/superheroes:configure`.\n"
    ),
    "skills/configure/reference/set-up.md": (
        "**Default:** recorded mode when one exists, else provisional `global` (out-of-repo). An\n"
        "already-decided mode is reported, not re-asked. **Disclosure:** when `$PROVISIONAL` is "
        "`true`, state\n"
        "in the set-up output which storage mode was taken, that it is provisional, and that\n"
        "`/superheroes:configure` changes it. **Follow-up:** the owner changes storage mode via\n"
        "`/superheroes:configure` (view-and-tune §3 for a flip after set-up).\n"
    ),
}

# Byte pins for bootstrap safety guards inside each surface's decide-location window.
_NONZERO_EXIT_GUARD = 'decide-location) || {'
_USABLE_VALUE_GUARD = '[ -n "$LOC" ] && [ -n "$PROVISIONAL" ]'
_RECONCILE_MODE_PATTERN = re.compile(r"reconcile\s+--mode")

_DECIDE_MODE_DIRECT_PATTERN = re.compile(r"mode_registry\.decide_mode\(")

# Retired presence-premise spellings — byte-literal census with cardinality floor zero (#1144).
_PREMISE_LITERALS = ("no human", "nobody to answer", "headless run")


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


def _discover_decide_location_surfaces():
    """Walk skills/ for decide-location CLI invocations — census is derived, not hand-maintained."""
    surfaces = set()
    for path in _walk_text_files(_SKILLS_ROOT):
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (UnicodeDecodeError, OSError):
            continue
        if "DEC=$(python" not in text or not _DECIDE_LOCATION_INVOCATION.search(text):
            continue
        surfaces.add(os.path.relpath(path, _PLUGIN_ROOT))
    return frozenset(surfaces)


_BOOTSTRAP_SURFACES = sorted(_discover_decide_location_surfaces())


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
            if _census_excluded(path):
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
            if _census_excluded(path):
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
# axis: retired presence-premise spellings — cardinality floor zero unconditionally (#1144).
def test_retired_presence_premise_literals_census(literal):
    """#1136/#1144: premise spellings that detected owner presence must not survive.

    Floor is zero with no allowlist — an allowlist whose entries are prose rationales does not
    terminate by construction. Expected red on seven formerly-allowlisted lines until other WOs
    reword them (#1144).
    """
    hits = []
    for rel, lineno, matched in _premise_literal_hits(literal):
        line_text = _read_plugin_rel(rel).splitlines()[lineno - 1].strip()
        hits.append(f"{rel}:{lineno}: {line_text}")
    assert not hits, (
        "retired presence-premise literal %r found (#1136/#1144 zero floor). "
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


# axis: derived decide-location census equals the disclosure-pin map in both directions.
def test_bootstrap_disclosure_pin_cardinality_floor():
    """#1136: a surface silently dropping out of the disclosure census must go red."""
    discovered = set(_discover_decide_location_surfaces())
    pin_surfaces = set(_DISCLOSURE_PIN_BY_SURFACE)
    carrier_surfaces = set(_DISCLOSURE_CARRIER_BY_SURFACE)
    missing_pins = discovered - pin_surfaces
    stale_pins = pin_surfaces - discovered
    assert not missing_pins, (
        "decide-location call site(s) lack a disclosure pin — add to _DISCLOSURE_PIN_BY_SURFACE "
        "(#1136). Missing:\n" + "\n".join(sorted(missing_pins))
    )
    assert not stale_pins, (
        "disclosure pin(s) left behind for surface(s) that no longer call decide-location — "
        "remove stale pin (#1136). Stale:\n" + "\n".join(sorted(stale_pins))
    )
    assert carrier_surfaces == discovered, (
        "disclosure carrier map must match the derived decide-location census (#1136). "
        "discovered=%r carriers=%r" % (sorted(discovered), sorted(carrier_surfaces))
    )


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
    carrier = _DISCLOSURE_CARRIER_BY_SURFACE[surface_rel]
    assert pin in window, (
        "%s is missing the byte-pinned disclosure sentence for carrier %r in the bootstrap window "
        "— a default would be taken silently (#1136)" % (surface_rel, carrier)
    )
    # R-2: configure's owner invocation is the hearing-from-the-owner event — carrier is the run's
    # set-up output, not a durable file artifact; do not demand a file path pin here.
    if surface_rel not in _CONVERSATION_DRIVEN_DISCLOSURE_SURFACES:
        assert "$SESSION_DIR" in pin or "layer body" in pin or "receipt.md" in pin, (
            "%s disclosure pin must name a durable carrier artifact (#1136)" % surface_rel
        )


@pytest.mark.parametrize("surface_rel", _BOOTSTRAP_SURFACES)
# axis: bootstrap safety guards — non-zero exit, usable JSON fields, no reconcile --mode (R-1).
def test_bootstrap_surface_safety_guards(surface_rel):
    """Bootstrap must halt on decide-location failure and must not reconcile during bootstrap."""
    text = _read_plugin_rel(surface_rel)
    window = _bootstrap_disclosure_window(text)
    assert window is not None, (
        "%s has no fenced bootstrap block around decide-location (#1136)" % surface_rel
    )
    bash_close = window.find("```", 3)
    assert bash_close > 0, "%s bootstrap window has no fenced bash block (#1136)" % surface_rel
    bash_block = window[:bash_close + 3]
    assert _NONZERO_EXIT_GUARD in bash_block, (
        "%s bootstrap is missing the non-zero-exit guard on decide-location (#1136)" % surface_rel
    )
    assert _USABLE_VALUE_GUARD in bash_block, (
        "%s bootstrap is missing the usable-value guard on LOC/PROVISIONAL (#1136)" % surface_rel
    )
    assert not _RECONCILE_MODE_PATTERN.search(bash_block), (
        "%s bootstrap still contains reconcile --mode — bootstrap reconciliation is retired "
        "(#1136)" % surface_rel
    )
