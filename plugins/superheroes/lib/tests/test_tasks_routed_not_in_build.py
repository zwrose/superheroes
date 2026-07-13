import json
import os
import sys

import finding_identity
import readout
import review_loop_plan as rlp

FULL_ROSTER = ["architecture-reviewer", "code-reviewer", "security-reviewer",
               "test-reviewer", "premortem-reviewer"]

_LIB = os.path.join(os.path.dirname(__file__), "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)


def _write_records(tmp_path, records, name="round-records.json"):
    p = tmp_path / name
    p.write_text(json.dumps(records))
    return str(p)


def _build_routed_forward_payload(finding):
    """Same composition path journalTasksRoutedFindings uses in its Python courier one-liner."""
    ident = finding_identity.finding_identity(finding)
    text = readout.scrub((finding.get("summary") or finding.get("title") or ""))[0]
    section = finding.get("docSection") or finding.get("section") or ""
    return {"doc": "tasks", "identity": ident, "section": section, "text": text}


def test_routed_tasks_finding_absent_from_build_worklist(tmp_path):
    records_path = _write_records(tmp_path, [{"round": 1, "findings": [
        {"file": "tasks.md", "title": "task 3 mis-specifies the clock", "severity": "Important"},
        {"file": "tasks.md", "title": "nit: rename local var", "severity": "Minor"},
    ], "dimensions": {}}])
    out = str(tmp_path / "worklist.json")
    rlp.compose_fix_context(records_path, None, None, "code", 1, FULL_ROSTER, out, doc_mode=True)
    titles = [f["title"] for f in json.loads(open(out).read())["findings"]]
    assert "nit: rename local var" not in titles   # routed forward, never in the build worklist
    assert "task 3 mis-specifies the clock" in titles  # blocking tasks finding IS judged/built


def test_routed_forward_text_is_scrubbed_before_payload():
    # journal.append writes `payload` as-is (no scrub) — the payload-building path must scrub.
    # Bearer-token shape matches an existing pr_comment._SCRUB_PATTERNS pattern.
    finding = {
        "file": "tasks.md",
        "title": "rotate the leaked token: Bearer abcdef0123456789",
        "severity": "Minor",
        "docSection": "Security",
    }
    payload = _build_routed_forward_payload(finding)
    assert "abcdef0123456789" not in payload["text"]
    assert "Bearer [REDACTED]" in payload["text"]
    assert "rotate the leaked token:" in payload["text"]
