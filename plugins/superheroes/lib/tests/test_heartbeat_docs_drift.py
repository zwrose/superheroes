"""CONVENTIONS §15 heartbeat contract drift guard.

Module constants in heartbeat.py are authoritative; prose copies in CONVENTIONS §15
and the workhorse/showrunner charters must stay pinned to them.
"""
import os
import re

import heartbeat as hb

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN = os.path.abspath(os.path.join(_HERE, "..", ".."))
_REPO_ROOT = os.path.abspath(os.path.join(_PLUGIN, "..", ".."))


def _read_repo(rel):
    with open(os.path.join(_REPO_ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def _read_plugin(rel):
    with open(os.path.join(_PLUGIN, rel), encoding="utf-8") as fh:
        return fh.read()


def _conventions_section_15():
    text = _read_repo("CONVENTIONS.md")
    m = re.search(r"## 15\. Builder liveness heartbeat.*?(?=\n## 16\.|\Z)", text, re.DOTALL)
    assert m, "CONVENTIONS §15 not found (renumbered or moved?)"
    return m.group(0)


def _assert_tokens_present(text, label, tokens):
    missing = [tok for tok in tokens if tok not in text]
    assert not missing, "%s missing token(s): %r" % (label, missing)


def _assert_bound_fragment(text, label, fragment):
    assert fragment in text, "%s missing bound fragment: %r" % (label, fragment)


def _launch_id_grammar_token():
    return "`%s`" % hb._LAUNCH_ID_RE.pattern


def test_conventions_section_15_matches_heartbeat_constants():
    section = _conventions_section_15()
    tokens = (
        sorted(hb.STATES)
        + sorted(hb.TERMINAL_STATES)
        + sorted(hb.SWEEP_CLASSES)
        + [hb.HEARTBEAT_ROOT_ENV, hb.LAUNCH_ID_ENV, _launch_id_grammar_token()]
    )
    _assert_tokens_present(section, "CONVENTIONS.md §15", tokens)


def _bind_conventions_section_15_measurement(section):
    """Field-bind every STALE_AFTER_MEASUREMENT value stated in CONVENTIONS §15."""
    m = hb.STALE_AFTER_MEASUREMENT
    label = "CONVENTIONS.md §15"
    _assert_bound_fragment(
        section, label,
        "`heartbeat.DEFAULT_STALE_AFTER_SECONDS` = **%d** seconds"
        % hb.DEFAULT_STALE_AFTER_SECONDS,
    )
    _assert_bound_fragment(
        section, label, "floored at %d× the worst" % m["multiplier"],
    )
    _assert_bound_fragment(
        section, label, "(%d s, over" % m["worstBenignGapSeconds"],
    )
    _assert_bound_fragment(
        section, label, "over %d gaps across" % m["gaps"],
    )
    _assert_bound_fragment(
        section, label, "across %d builder lanes" % m["lanes"],
    )
    _assert_bound_fragment(
        section, label, "builder lanes, %d of" % m["benignGaps"],
    )
    # coldThresholdSeconds is not stated in §15 — only in wave-watch.md.


def _bind_wave_watch_measurement_corpus(doc):
    """Field-bind every STALE_AFTER_MEASUREMENT value stated in wave-watch.md."""
    m = hb.STALE_AFTER_MEASUREMENT
    label = "reference/wave-watch.md"
    _assert_bound_fragment(
        doc, label,
        "`DEFAULT_STALE_AFTER_SECONDS`, **%d s**" % hb.DEFAULT_STALE_AFTER_SECONDS,
    )
    _assert_bound_fragment(
        doc, label,
        "**%d× the worst benign inter-stamp gap" % m["multiplier"],
    )
    _assert_bound_fragment(
        doc, label, "host, %d s**" % m["worstBenignGapSeconds"],
    )
    _assert_bound_fragment(
        doc, label, "across **%d** builder lanes" % m["lanes"],
    )
    _assert_bound_fragment(
        doc, label, "pooled **%d** inter-stamp gaps" % m["gaps"],
    )
    _assert_bound_fragment(
        doc, label,
        "**%d** of the %d gaps were benign" % (m["benignGaps"], m["gaps"]),
    )
    _assert_bound_fragment(
        doc, label,
        "colder than **%d** s anywhere inside it" % m["coldThresholdSeconds"],
    )


def test_conventions_section_15_pins_the_measurement_corpus():
    # bite-axis: every measurement field stated in §15 tracks heartbeat.py.
    _bind_conventions_section_15_measurement(_conventions_section_15())


def test_wave_watch_doc_states_the_full_measurement_corpus():
    # bite-axis: every measurement field stated in wave-watch.md tracks heartbeat.py.
    _bind_wave_watch_measurement_corpus(
        _read_plugin("skills/showrunner/reference/wave-watch.md"),
    )


def test_wave_watch_doc_pins_the_suppression_wire_contract():
    # bite-axis: the WIRE NAMES in prose track the module. `staleSuppressed` and the
    # note token are a JSON contract an operator reads out of wave-watch.md; a rename
    # on one side without the other is the silent drift this pins.
    import wave_watch as ww

    # Both sides read the RUNTIME constants — a hardcoded literal here would keep
    # passing after a runtime rename, which is the drift this is supposed to catch.
    # Require the BACKTICKED form so an incidental prose occurrence of a common word
    # (`lane-stale` appears all over this document) cannot satisfy the check.
    doc = _read_plugin("skills/showrunner/reference/wave-watch.md")
    _assert_tokens_present(
        doc, "reference/wave-watch.md",
        ["`%s`" % ww.RESULT_KEY_STALE_SUPPRESSED,
         "`%s`" % ww.NOTE_STALE_SUPPRESSED_TRANSCRIPT_FRESH],
    )


def test_workhorse_charter_matches_heartbeat_constants():
    text = _read_plugin("skills/workhorse/SKILL.md")
    tokens = [
        hb.LAUNCH_ID_ENV,
        "CONVENTIONS §15",
    ] + sorted(hb.TERMINAL_STATES)
    _assert_tokens_present(text, "skills/workhorse/SKILL.md", tokens)


def test_showrunner_charter_matches_heartbeat_constants():
    text = _read_plugin("skills/showrunner/SKILL.md")
    m = re.search(
        r"\*\*Scheduled heartbeat sweep.*?(?=\n\s*\*\*Wave-preflight)",
        text,
        re.DOTALL,
    )
    assert m, "showrunner duty-9 heartbeat sweep paragraph not found"
    duty = m.group(0)
    tokens = (
        sorted(cls for cls in hb.SWEEP_CLASSES if cls != "fresh")
        + ["staleAfterSeconds", "lib/heartbeat.py", "sweep", "--repo-root", "record-outcome"]
    )
    _assert_tokens_present(duty, "skills/showrunner/SKILL.md duty-9", tokens)
