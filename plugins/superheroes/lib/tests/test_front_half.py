import json as _json
import os as _os

import front_half as fh


# --- Task 2: gate_for_terminal ---

def test_clean_terminal_maps_to_passed():
    assert fh.gate_for_terminal("clean") == "passed"


def test_clean_with_skips_maps_to_passed():
    assert fh.gate_for_terminal("clean-with-skips") == "passed"


def test_cannot_certify_maps_to_changes_requested():
    assert fh.gate_for_terminal("cannot-certify") == "changes-requested"


def test_halted_maps_to_changes_requested():
    assert fh.gate_for_terminal("halted") == "changes-requested"


def test_unknown_terminal_fails_closed_to_changes_requested():
    assert fh.gate_for_terminal("continue") == "changes-requested"
    assert fh.gate_for_terminal("banana") == "changes-requested"
    assert fh.gate_for_terminal(None) == "changes-requested"


# --- Task 3: is_usable_draft ---

_GOOD = (
    "---\n"
    "docType: plan\n"
    "gates: {review: pending}\n"
    "---\n"
    "# Title — Plan\n\n"
    "## Overview\nReal overview text.\n\n"
    "## Goals & non-goals\nReal goals.\n"
)


def test_usable_when_signal_matches_and_content_complete():
    assert fh.is_usable_draft(_GOOD, "h1", "h1",
                              required_sections=("Overview", "Goals & non-goals")) is True


def test_not_usable_when_signal_missing():
    assert fh.is_usable_draft(_GOOD, "", "h1") is False
    assert fh.is_usable_draft(_GOOD, None, "h1") is False
    assert fh.is_usable_draft(_GOOD, "h1", "") is False     # no expected signal (e.g. unhashable doc)
    assert fh.is_usable_draft(_GOOD, "h1", None) is False


def test_not_usable_when_signal_stale_mismatch():
    # Run N's signal "h1" against Run N+1's content hash "h2" -> stale -> re-produce.
    assert fh.is_usable_draft(_GOOD, "h1", "h2") is False


def test_not_usable_when_required_section_missing():
    assert fh.is_usable_draft(_GOOD, "h1", "h1",
                              required_sections=("Overview", "Architecture")) is False


def test_not_usable_when_required_section_empty():
    txt = _GOOD + "\n## Architecture\n\n## Risks\nx\n"  # Architecture heading present but empty
    assert fh.is_usable_draft(txt, "h1", "h1", required_sections=("Architecture",)) is False


def test_not_usable_when_placeholder_token_present():
    # every _PLACEHOLDER alternate must be caught (a finished doc carries none of them).
    for token in ("TBD", "{{frontmatter}}", "<!-- AUTHOR GUIDANCE x -->", "similar to Task 3"):
        txt = _GOOD.replace("Real overview text.", token)
        assert fh.is_usable_draft(txt, "h1", "h1", required_sections=("Overview",)) is False, token


def test_not_usable_when_no_frontmatter_or_empty_body():
    assert fh.is_usable_draft("# Title\nbody", "h1", "h1") is False  # no frontmatter
    assert fh.is_usable_draft("---\nx: 1\n---\n   \n", "h1", "h1") is False  # empty body
    assert fh.is_usable_draft("", "h1", "h1") is False


# --- Task 4: render_run_outcome ---

def test_render_embeds_loop_readout_and_lists_phases():
    out = fh.render_run_outcome({
        "completed_phases": ["plan", "review-plan"],
        "docs": {"plan": "docs/.../plan.md"},
        "phase_records": [
            {"phase": "review-plan",
             "record": {"schemaVersion": 1, "terminal": "clean", "fixes": [], "deferred": [], "drops": []}},
        ],
        "readout_record_ok": True,
    })
    assert "plan, review-plan" in out
    assert "Review loop — clean" in out            # loop_readout.render output, embedded
    assert "docs/.../plan.md" in out


def test_render_dedupes_notify_by_phase_and_identity():
    out = fh.render_run_outcome({
        "completed_phases": ["plan"],
        "notify": [
            {"phase": "plan", "identity": "x", "message": "went with X"},
            {"phase": "plan", "identity": "x", "message": "went with X"},  # dup across re-produce
            {"phase": "plan", "identity": "y", "message": "went with Y"},
        ],
    })
    assert out.count("went with X") == 1
    assert "went with Y" in out


def test_render_keeps_distinct_unidentified_notify():
    # two NOTIFYs with no identity but different messages must both survive (no (phase, None) collision)
    out = fh.render_run_outcome({
        "completed_phases": ["plan"],
        "notify": [
            {"phase": "plan", "message": "default A"},
            {"phase": "plan", "message": "default B"},
        ],
    })
    assert "default A" in out and "default B" in out


def test_render_flags_undelivered_durable_readout():
    out = fh.render_run_outcome({"completed_phases": [], "readout_record_ok": False})
    assert "durable readout record could not be written" in out


def test_render_never_raises_on_garbage():
    assert isinstance(fh.render_run_outcome(None), str)
    assert isinstance(fh.render_run_outcome({"phase_records": [{"phase": "p", "record": None}]}), str)


# --- Task 5: merge_findings / record_deferred / append_notify ---

def _write(p, obj):
    _os.makedirs(_os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        _json.dump(obj, f)


def test_merge_findings_compiles_round_findings(tmp_path):
    run_dir = str(tmp_path)
    rd = _os.path.join(run_dir, "round-1")
    _write(_os.path.join(rd, "findings-code.json"),
           [{"severity": "Important", "file": "plan.md", "line": 1, "title": "x", "dimension": "Code"}])
    _write(_os.path.join(rd, "findings-test.json"), [])
    n = fh.merge_findings(run_dir, 1, ["code", "test"])
    assert n >= 1
    with open(_os.path.join(rd, "merged.json"), encoding="utf-8") as f:
        merged = _json.load(f)
    assert isinstance(merged, list) and len(merged) >= 1


def test_record_deferred_appends_identity_severity(tmp_path):
    run_dir = str(tmp_path)
    fh.record_deferred({"deferred": [{"identity": "plan.md::x", "severity": "Minor"}]}, run_dir)
    fh.record_deferred({"deferred": [{"identity": "plan.md::y", "severity": "Nit"}]}, run_dir)
    with open(_os.path.join(run_dir, "deferred-set.json"), encoding="utf-8") as f:
        ds = _json.load(f)
    assert ds == {"plan.md::x": "Minor", "plan.md::y": "Nit"}


def test_record_deferred_tolerates_empty_report(tmp_path):
    run_dir = str(tmp_path)
    assert fh.record_deferred({}, run_dir) == 0
    assert fh.record_deferred(None, run_dir) == 0


def test_append_notify_accumulates(tmp_path):
    ledger = _os.path.join(str(tmp_path), "notify.json")
    fh.append_notify(ledger, [{"phase": "plan", "identity": "x", "message": "went with X"}])
    fh.append_notify(ledger, [{"phase": "tasks", "identity": "y", "message": "went with Y"}])
    with open(ledger, encoding="utf-8") as f:
        data = _json.load(f)
    assert [d["message"] for d in data] == ["went with X", "went with Y"]


def test_append_notify_tolerates_empty(tmp_path):
    ledger = _os.path.join(str(tmp_path), "notify.json")
    assert fh.append_notify(ledger, []) == 0
    assert fh.append_notify(ledger, None) == 0
