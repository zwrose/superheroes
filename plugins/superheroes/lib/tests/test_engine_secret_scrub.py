import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import engine_adapter  # Task 5/6

_SECRET = "ghp_EXAMPLEfakenotarealtoken000000000"

def test_external_review_finding_freetext_is_scrubbed_at_the_adapter_boundary():
    stdout = json.dumps({"findings": [{
        "file": "a.py", "line": 3, "title": "leak", "severity": "Critical",
        "body": f"token found: {_SECRET}", "suggestion": f"rotate {_SECRET}",
    }]})
    parsed = engine_adapter.parse_result("codex", "review", stdout)
    assert parsed["ok"] is True
    blob = json.dumps(parsed["findings"])
    assert _SECRET not in blob, "the raw secret must never survive parse_result (adapter scrub boundary)"

def test_external_review_finding_evidence_and_title_are_scrubbed_too():
    # FIX 1: the adapter boundary scrubs EVERY free-text field in a finding, not just body/
    # suggestion — spine reviewer findings also carry free text in evidence/title.
    stdout = json.dumps({"findings": [{
        "file": "a.py", "line": 3, "severity": "Critical",
        "title": f"leaked token {_SECRET} in header",
        "evidence": f"log line: Authorization: Bearer {_SECRET}",
    }]})
    parsed = engine_adapter.parse_result("codex", "review", stdout)
    assert parsed["ok"] is True
    blob = json.dumps(parsed["findings"])
    assert _SECRET not in blob, "a secret in evidence/title must be scrubbed (adapter boundary)"
    f = parsed["findings"][0]
    assert "[REDACTED]" in f["title"]
    assert "[REDACTED]" in f["evidence"]
    # structural keys pass through unscrubbed/untouched.
    assert f["file"] == "a.py" and f["line"] == 3 and f["severity"] == "Critical"


def test_external_build_evidence_carries_no_freetext():
    stdout = json.dumps({"ok": True, "signal": "ok",
                         "evidence": {"testFailed": False, "testPassed": True},
                         "leaked": f"secret {_SECRET}"})
    parsed = engine_adapter.parse_result("codex", "build", stdout)
    assert parsed["ok"] is True
    assert set(parsed["evidence"].keys()) <= {"testFailed", "testPassed"}
    assert _SECRET not in json.dumps(parsed["evidence"])


def test_salvage_from_artifact_scrubs_secret_in_prose_excerpt():
    # axis: secret containment on salvage excerpt and structured findings
    prose = (
        "Review notes with leaked credential %s in the narrative.\n"
        "- src/a.ts:1 token visible\n- src/b.ts:2 rotate immediately"
    ) % _SECRET
    prose = prose + "\n" + ("padding " * 40)
    salvage = engine_adapter.salvage_from_artifact(prose, "")
    assert _SECRET not in salvage["excerpt"]
    assert "[REDACTED]" in salvage["excerpt"]
    assert _SECRET not in json.dumps(salvage["findings"])


def test_salvage_from_artifact_scrubs_nested_secret_in_structured_findings():
    # axis: that every string leaving salvage is scrubbed — keys, structural values, all fields.
    stdout = json.dumps({"findings": [{
        "file": "a.py", "line": 3, "severity": "Critical", "title": "leak",
        "evidence": {"raw": "token %s in nested field" % _SECRET},
    }]})
    salvage = engine_adapter.salvage_from_artifact(stdout, "")
    assert salvage["structured"] is True
    blob = json.dumps(salvage["findings"])
    assert _SECRET not in blob
    assert "[REDACTED]" in salvage["findings"][0]["evidence"]["raw"]


def test_scrub_salvage_block_scrubs_nested_keys_structural_values_and_other_fields():
    # axis: that every string leaving salvage is scrubbed — keys, structural values, all fields.
    secret_key = "note %s here" % _SECRET
    salvage_in = {
        secret_key: "value under secret key",
        "excerpt": "prose with %s" % _SECRET,
        "summary": "top-level field %s" % _SECRET,
        "findings": [{
            "file": "path with %s embedded" % _SECRET,
            "line": 1,
            "id": "finding id %s" % _SECRET,
            "dimension": "security note %s" % _SECRET,
            "body": "body %s" % _SECRET,
        }],
        "count": 3,
        "optional": None,
    }
    out = engine_adapter.scrub_salvage_block(salvage_in)
    blob = json.dumps(out)
    assert _SECRET not in blob
    assert secret_key not in out
    assert "[REDACTED]" in out["excerpt"]
    assert "[REDACTED]" in out["summary"]
    assert any("[REDACTED]" in k for k in out if isinstance(k, str))
    finding = out["findings"][0]
    assert "[REDACTED]" in finding["file"]
    assert "[REDACTED]" in finding["id"]
    assert "[REDACTED]" in finding["dimension"]
    assert out["count"] == 3
    assert out["optional"] is None
