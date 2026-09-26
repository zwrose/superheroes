"""CONVENTIONS §15 heartbeat contract drift guard.

Module constants in heartbeat.py are authoritative; prose copies in CONVENTIONS §15
and the workhorse/showrunner charters must stay pinned to them.
"""
import os
import re

import heartbeat as hb
import wave_watch as ww

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
    _assert_bound_fragment(
        section,
        "CONVENTIONS.md §15",
        "`wave_watch.LIVENESS_QUIET_WINDOW_SECONDS` = **%d** seconds"
        % ww.LIVENESS_QUIET_WINDOW_SECONDS,
    )


def test_wave_watch_doc_states_the_quiet_window():
    doc = _read_plugin("skills/showrunner/reference/wave-watch.md")
    _assert_bound_fragment(
        doc,
        "reference/wave-watch.md",
        "`LIVENESS_QUIET_WINDOW_SECONDS`, **%d s**" % ww.LIVENESS_QUIET_WINDOW_SECONDS,
    )


def test_wave_watch_doc_pins_the_loop_wire_contract():
    doc = _read_plugin("skills/showrunner/reference/wave-watch.md")
    _assert_tokens_present(
        doc, "reference/wave-watch.md",
        ["`%s`" % ww.RESULT_KEY_PASSED_OVER,
         "`%s`" % ww.RESULT_KEY_PASSED_OVER_COUNT,
         "`%s`" % ww.RESULT_KEY_LIVE_LOOP],
    )


def test_workhorse_charter_matches_heartbeat_constants():
    text = _read_plugin("skills/workhorse/SKILL.md")
    tokens = [
        hb.LAUNCH_ID_ENV,
        "CONVENTIONS §15",
        "blocked",
    ] + sorted(hb.TERMINAL_STATES)
    _assert_tokens_present(text, "skills/workhorse/SKILL.md", tokens)


def test_showrunner_charter_matches_heartbeat_constants():
    text = _read_plugin("skills/showrunner/SKILL.md")
    m = re.search(
        r"\*\*Scheduled liveness sweep.*?(?=\n\s*\*\*Wave-preflight)",
        text,
        re.DOTALL,
    )
    assert m, "showrunner duty-9 liveness sweep paragraph not found"
    duty = m.group(0)
    tokens = (
        sorted(hb.SWEEP_CLASSES)
        + [
            "lib/heartbeat.py",
            "lib/wave_watch.py",
            "sweep",
            "run",
            "--repo-root",
            "--batch",
            "record-outcome",
            "lane-stale",
            "LIVENESS_QUIET_WINDOW_SECONDS",
        ]
    )
    _assert_tokens_present(duty, "skills/showrunner/SKILL.md duty-9", tokens)


def test_resume_row_two_names_the_liveness_rule():
    text = _read_plugin("skills/showrunner-resume/SKILL.md")
    row_start = "| **2. re-arm** |"
    idx = text.find(row_start)
    assert idx != -1, "showrunner-resume row 2 not found"
    line_end = text.find("\n", idx)
    row = text[idx:line_end]
    assert "LIVENESS_QUIET_WINDOW_SECONDS" in row
    assert "`fresh`" not in row
    assert "staleAfterSeconds" not in row


_RETIRED_TOKENS = (
    "staleAfterSeconds",
    "stale-after",
    "DEFAULT_STALE_AFTER",
    "STALE_AFTER_MEASUREMENT",
    "staleSuppressed",
    "stale-suppressed-transcript-fresh",
    "`fresh`",
    "heartbeat promise",
)

_CENSUS_ALLOWLIST = frozenset({
    ("plugins/superheroes/lib/heartbeat.py", "stale-after"),
    ("plugins/superheroes/lib/heartbeat.py", "staleAfterSeconds"),
})

_CENSUS_TEXT_SUFFIXES = (
    ".py", ".md", ".json", ".sh", ".txt", ".yml", ".yaml", ".toml",
)


def test_no_reader_or_builder_keeps_the_retired_promise():
    offenders = []
    files = []
    for dirpath, dirnames, filenames in os.walk(_PLUGIN):
        parts = dirpath.split(os.sep)
        if "tests" in parts:
            dirnames.clear()
            continue
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name == "CHANGELOG.md":
                continue
            if not any(name.endswith(suffix) for suffix in _CENSUS_TEXT_SUFFIXES):
                continue
            files.append(os.path.join(dirpath, name))
    conv = os.path.join(_REPO_ROOT, "CONVENTIONS.md")
    if os.path.isfile(conv):
        files.append(conv)

    for path in files:
        try:
            rel = os.path.relpath(path, _REPO_ROOT)
        except ValueError:
            rel = path
        with open(path, encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, start=1):
                for token in _RETIRED_TOKENS:
                    if token not in line:
                        continue
                    if (rel, token) in _CENSUS_ALLOWLIST:
                        continue
                    offenders.append("%s:%d:%s" % (rel, lineno, token))
    assert not offenders, "retired promise token(s) found:\n" + "\n".join(sorted(offenders))
