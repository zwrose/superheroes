"""The three v2 dispatch-wiring guards (WO-5), all FAIL-CLOSED:

1. Wired-consumer guard — the new model_tier roles `implementer`/`pilot` each have a named
   consumer (the workhorse charter dispatches them), so an orphaned dispatch knob fails CI.
2. §11 config-key drift guard — every enginePreferences key the workhorse charter + preflight +
   configure prose CITE exists in engine_pref.ENGINE_PREF_KEYS (the schema home), and a retired
   key (`planAuthor`) can never re-appear in the calibration prose.
3. Observability wiring — the workhorse charter REQUIRES recording engine+model per dispatch (§7)
   and a PR dispatch-provenance section (§11); removing either fails CI.

Fail-closed means: a guard that cannot find what it is looking for RAISES, it never silently
passes. The §11 extractor in particular asserts its own found-set is non-empty before comparing
it against the schema, so an extractor that regresses to matching nothing cannot vacuously pass.
"""
import json
import os
import re
import importlib.util
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, ".."))
PLUGIN = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, LIB)
import engine_pref
import model_tier
import model_tier_overrides


def _read(rel):
    """rel is relative to the plugin dir, e.g. 'skills/workhorse/SKILL.md'."""
    with open(os.path.join(PLUGIN, rel), encoding="utf-8") as fh:
        return fh.read()


WORKHORSE = "skills/workhorse/SKILL.md"
PREFLIGHT = "skills/configure/reference/preflight.md"
CONFIG_DOCS = ("skills/configure/SKILL.md", "skills/configure/reference/set-up.md",
               "skills/configure/reference/view-and-tune.md")
SURFACE = (WORKHORSE, PREFLIGHT) + CONFIG_DOCS
V2_DISPATCH_ROLES = ("implementer", "pilot")   # the model_tier roles #472 adds


def extract_engine_pref_keys(text):
    """Extract every enginePreferences key CITED in `text` — the §11 drift-guard extractor.

    Union of three patterns:
      - brace form:  enginePreferences: {reviewer, implementation, briefCheck, pilot}
      - dotted form: enginePreferences.codexModels
      - json form:   a ```json fenced block that mentions "enginePreferences" is `json.loads`-ed;
                      when it parses and `enginePreferences` is a dict, ALL of its TOP-LEVEL keys
                      are cited (nested values like "effort": {"review": "high"} are naturally
                      excluded — they aren't top-level). A block that PARSES but whose
                      "enginePreferences" value isn't itself a dict falls back to a defensive scan
                      of quoted keys intersected with the known engine-pref key set, so an
                      atypically-shaped-but-valid example never false-fails. A block that CITES
                      "enginePreferences" and does NOT parse as JSON at all is fail-CLOSED: it
                      RAISES (AssertionError) rather than falling back — a malformed config example
                      is itself a doc defect, and silently intersecting-with-known would let a
                      drifted key hiding in the unparseable prose escape the guard undetected.

    `text` must be a str — a non-str input is a caller bug, not a "nothing cited" result, so this
    raises (AssertionError) rather than silently returning an empty set.
    """
    assert isinstance(text, str), "extract_engine_pref_keys requires str input, got %r" % (type(text),)
    found = set()

    for group in re.findall(r"enginePreferences[^\n{]*\{([^}]*)\}", text):
        for token in group.split(","):
            token = token.strip().strip('"').strip("'")
            token = token.split(":", 1)[0].strip()
            if re.match(r"^[A-Za-z][A-Za-z]*$", token):
                found.add(token)

    for token in re.findall(r"enginePreferences\.([A-Za-z]+)", text):
        found.add(token)

    # A drifted TOP-LEVEL enginePreferences key that appears only inside a ```json example must
    # still be caught (TR-2): json.loads the block and take every top-level key of its
    # "enginePreferences" object directly, rather than merely intersecting quoted tokens against
    # the already-known key set (which can never surface an UNKNOWN drifted key). Nested keys
    # (e.g. "effort"'s nested "review") are naturally excluded — they aren't top-level.
    known = set(engine_pref.ENGINE_PREF_KEYS)
    for block in re.findall(r"```json(.*?)```", text, re.S):
        if "enginePreferences" not in block:
            continue
        try:
            obj = json.loads(block)
        except ValueError:
            # Fail CLOSED: a block that cites "enginePreferences" but is not valid JSON is itself
            # a doc defect. Falling back to the intersect-with-known scan here would let a
            # drifted key hiding in the malformed text silently escape the guard — so this raises
            # instead of papering over it.
            raise AssertionError(
                'a ```json block cites "enginePreferences" but does not parse as valid JSON — '
                "fix the example (or remove the citation); a malformed config example must break "
                "CI, not silently drop drift"
            )
        prefs_obj = obj.get("enginePreferences") if isinstance(obj, dict) else None
        if isinstance(prefs_obj, dict):
            found.update(prefs_obj.keys())
        else:
            # Parsed fine, but "enginePreferences" isn't itself a dict (or the top-level obj
            # isn't a dict) — fall back to the defensive intersect-with-known scan so a
            # legitimately atypical example never false-fails the drift guard.
            for token in re.findall(r'"([A-Za-z]+)"\s*:', block):
                if token in known:
                    found.add(token)

    return found


def test_extract_engine_pref_keys_raises_on_malformed_json_block():
    # Fix D: a ```json block that CITES "enginePreferences" but does not parse as JSON must
    # RAISE, never silently fall back to the intersect-with-known scan (which would let a
    # drifted key hiding in the malformed text escape the guard undetected).
    text = (
        "```json\n"
        "{\n"
        '  "enginePreferences": {\n'
        '    "reviewer": "codex",\n'
        "  }\n"
        "}\n"
        "```\n"
    )
    with pytest.raises(AssertionError):
        extract_engine_pref_keys(text)


def test_extract_engine_pref_keys_raises_on_unquoted_malformed_json_block():
    # Fix 2: the json-branch trigger must catch UNQUOTED enginePreferences too — a malformed
    # ```json fence that writes the key unquoted (and split across lines so the brace-form
    # extractor also misses it) must not silently escape the fail-closed drift guard.
    text = (
        "```json\n"
        "{\n"
        "  enginePreferences: {\n"
        '    "reviewer": "codex",\n'
        "  }\n"
        "}\n"
        "```\n"
    )
    with pytest.raises(AssertionError):
        extract_engine_pref_keys(text)


def test_extract_engine_pref_keys_well_formed_json_block_still_contributes_keys():
    # Sanity twin of the malformed-raises test: a WELL-FORMED block keeps contributing its
    # top-level enginePreferences keys exactly as before.
    text = (
        "```json\n"
        "{\n"
        '  "enginePreferences": {"reviewer": "codex", "pilot": "cursor"}\n'
        "}\n"
        "```\n"
    )
    assert extract_engine_pref_keys(text) == {"reviewer", "pilot"}


def test_extract_engine_pref_keys_over_real_surface_never_raises():
    # Fix D precondition: every ```json block currently in SURFACE that mentions
    # "enginePreferences" must parse cleanly, else the new fail-closed raise would break CI on
    # this repo's own docs. Pins the verified-clean state as a regression guard.
    all_text = "\n".join(_read(f) for f in SURFACE)
    extract_engine_pref_keys(all_text)   # must not raise


# --- Guard 1: wired-consumer ------------------------------------------------------------------

def test_v2_roles_in_schema():
    for role in V2_DISPATCH_ROLES:
        assert role in model_tier.DEFAULT_TIERS, (
            f"{role!r} is missing from model_tier.DEFAULT_TIERS — the v2 role has no schema entry"
        )
        assert role in model_tier_overrides.KNOWN_ROLES, (
            f"{role!r} is missing from model_tier_overrides.KNOWN_ROLES — the v2 role is not "
            "owner-tunable"
        )
        assert model_tier.DEFAULT_TIERS[role] == "sonnet", (
            f"{role!r} default tier is {model_tier.DEFAULT_TIERS[role]!r}, expected 'sonnet' "
            "(the owner-ratified v2 default)"
        )


def test_v2_roles_have_a_wired_consumer():
    workhorse_text = _read(WORKHORSE)
    for role in V2_DISPATCH_ROLES:
        # `pilot` must not be satisfiable by the incidental "test-pilot" hero mentions — a
        # negative lookbehind excludes a "test-" prefix immediately before the word. `implementer`
        # has no such incidental collision, so it keeps the plain word-boundary pattern.
        pattern = (r"(?<!test-)\bpilot\b" if role == "pilot"
                   else r"\b" + re.escape(role) + r"\b")
        assert re.search(pattern, workhorse_text), (
            f"orphaned dispatch role {role!r}: no wired consumer found in {WORKHORSE} — a "
            "model_tier role with no charter consumer is dead config"
        )


def test_brief_check_engine_key_wired():
    assert "briefCheck" in engine_pref.ENGINE_ROLE_KEYS
    assert "pilot" in engine_pref.ENGINE_ROLE_KEYS
    workhorse_text = _read(WORKHORSE)
    assert re.search(r"brief[- ]?check", workhorse_text, re.I), (
        f"{WORKHORSE} never references the brief-check reviewer — the briefCheck engine key "
        "would be orphaned"
    )


# --- Guard 2: §11 config-key drift ------------------------------------------------------------

def test_no_retired_engine_key_in_calibration_prose():
    for k in engine_pref.RETIRED_ENGINE_KEYS:
        pattern = r"\b" + re.escape(k) + r"\b"
        for f in SURFACE:
            text = _read(f)
            assert re.search(pattern, text) is None, (
                f"retired enginePreferences key {k!r} is still cited in {f} — it must never "
                "re-appear as a live config knob (plan authoring was retired in #479)"
            )


def test_cited_enginePreferences_keys_are_in_schema():
    all_text = "\n".join(_read(f) for f in SURFACE)
    found = extract_engine_pref_keys(all_text)
    # Fail-closed: an extractor that matches nothing must RAISE, never pass vacuously.
    assert found, (
        "the §11 extractor found NO enginePreferences keys across SURFACE — refusing to pass "
        "vacuously (either the extractor regressed or the prose stopped citing the schema)"
    )
    assert "briefCheck" in found, (
        "the §11 extractor did not find the known v2 key 'briefCheck' in any SURFACE file — "
        "the extractor is broken or the key is undocumented"
    )
    unknown = found - set(engine_pref.ENGINE_PREF_KEYS)
    assert not unknown, (
        f"SURFACE cites enginePreferences key(s) not in engine_pref.ENGINE_PREF_KEYS: "
        f"{sorted(unknown)} — schema drift"
    )


def test_engine_role_keys_are_documented():
    docs_text = [(f, _read(f)) for f in CONFIG_DOCS]
    for key in engine_pref.ENGINE_ROLE_KEYS:
        assert any(key in text for _, text in docs_text), (
            f"enginePreferences role key {key!r} is not documented in any of {CONFIG_DOCS} — a "
            "schema key with no owner-facing documentation"
        )


# --- Guard 3: observability wiring ------------------------------------------------------------

def test_workhorse_requires_dispatch_provenance():
    text = _read(WORKHORSE)
    missing = []
    if "engine + model in every work order" not in text:
        missing.append("engine + model in every work order")
    if "dispatch provenance" not in text:
        missing.append("dispatch provenance")
    assert not missing, (
        f"{WORKHORSE} is missing required observability wiring phrase(s): {missing}"
    )
