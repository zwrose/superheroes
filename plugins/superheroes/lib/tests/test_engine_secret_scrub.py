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


_ANT_KEY_A = "sk-ant-api03-" + ("A" * 40)
_ANT_KEY_B = "sk-ant-api03-" + ("B" * 40)
_ANT_KEY_C = "sk-ant-api03-" + ("C" * 40)


def test_scrub_salvage_block_two_secret_keys_both_values_survive():
    # axis: scrubbed-key collision preserves every entry — not injective key scrub.
    blk = {_ANT_KEY_A: "v1", _ANT_KEY_B: "v2"}
    out = engine_adapter.scrub_salvage_block(blk)
    assert set(out.values()) == {"v1", "v2"}
    assert len(out) == 2
    assert _ANT_KEY_A not in out and _ANT_KEY_B not in out
    assert _SECRET not in json.dumps(out)


def test_scrub_salvage_block_three_secret_keys_all_values_survive():
    # axis: scrubbed-key collision preserves every entry — not injective key scrub.
    blk = {_ANT_KEY_A: "v1", _ANT_KEY_B: "v2", _ANT_KEY_C: "v3"}
    out = engine_adapter.scrub_salvage_block(blk)
    assert set(out.values()) == {"v1", "v2", "v3"}
    assert len(out) == 3


def test_scrub_salvage_block_nested_secret_key_collision_preserves_entries():
    # axis: scrubbed-key collision preserves every entry — not injective key scrub.
    nested = {_ANT_KEY_A: "inner1", _ANT_KEY_B: "inner2"}
    out = engine_adapter.scrub_salvage_block({"wrapper": nested})
    inner = out["wrapper"]
    assert set(inner.values()) == {"inner1", "inner2"}
    assert len(inner) == 2


def test_scrub_salvage_block_no_collision_keys_byte_identical():
    # axis: scrubbed-key collision preserves every entry — not injective key scrub.
    blk = {"safe_key": "val", "other": "data", 42: "int_val", ("t",): "tuple_val"}
    out = engine_adapter.scrub_salvage_block(blk)
    assert out["safe_key"] == "val"
    assert out["other"] == "data"
    assert out[42] == "int_val"
    assert out[("t",)] == "tuple_val"
    assert set(out.keys()) == set(blk.keys())


def test_scrub_salvage_block_literal_redacted_key_survives_collision():
    # axis: scrubbed-key collision preserves every entry — not injective key scrub.
    blk = {"[REDACTED]": "literal", _ANT_KEY_A: "secret_val"}
    out = engine_adapter.scrub_salvage_block(blk)
    assert out["[REDACTED]"] == "literal"
    assert "secret_val" in out.values()
    assert len(out) == 2
