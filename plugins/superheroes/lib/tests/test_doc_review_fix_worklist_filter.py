"""#397 FR-4/FR-5: the DOC-REVIEW fix-worklist filter — non-blocking findings are excluded
from compose_fix_context's fixer worklist on the doc legs, and the routed_forward payload
composition scrubs text+identity. This does NOT drive the workhorse BUILD phase: FR-5's
build-side guarantee is structural — routed_forward journal events have zero readers in any
build-instruction composition path (verified by grep at the #431 spec-vet), so there is no
behavioral seam to test there."""
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
    """Mirror of journalTasksRoutedFindings' Python courier composition (kept in sync by the
    production-path smoke in showrunner_tasks_routed_smoke.js, which drives the real embedded
    script): identity is computed from a SCRUBBED copy of title/summary — mirroring
    review_handoff._scrubbed_label — never from the raw finding."""
    title_raw = finding.get("title") or ""
    summary_raw = finding.get("summary") or ""
    ident_f = {"file": finding.get("file")}
    if title_raw:
        ident_f["title"] = readout.scrub(title_raw)[0]
    elif summary_raw:
        ident_f["summary"] = readout.scrub(summary_raw)[0]
    else:
        ident_f["title"] = ""
    ident = finding_identity.finding_identity(ident_f)
    text = readout.scrub(summary_raw or title_raw)[0]
    section = finding.get("docSection") or finding.get("section") or ""
    return {"doc": "tasks", "identity": ident, "section": section, "text": text}


def test_routed_tasks_finding_absent_from_doc_fix_worklist(tmp_path):
    records_path = _write_records(tmp_path, [{"round": 1, "findings": [
        {"file": "tasks.md", "title": "task 3 mis-specifies the clock", "severity": "Important"},
        {"file": "tasks.md", "title": "nit: rename local var", "severity": "Minor"},
    ], "dimensions": {}}])
    out = str(tmp_path / "worklist.json")
    rlp.compose_fix_context(records_path, None, None, "code", 1, FULL_ROSTER, out, doc_mode=True)
    titles = [f["title"] for f in json.loads(open(out).read())["findings"]]
    # routed forward, never in the DOC-REVIEW fixer worklist (the build's contract stays the
    # tasks doc alone — routed_forward events have no build-side reader, structurally)
    assert "nit: rename local var" not in titles
    assert "task 3 mis-specifies the clock" in titles  # blocking tasks finding IS in the worklist


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
    # identity is journal payload too (journal.append writes payload as-is) — the secret must
    # not survive there either: it is computed from the scrubbed copy, never the raw title
    assert "abcdef0123456789" not in payload["identity"]
    assert payload["identity"].startswith("tasks.md::")
