import importlib.util, json, os

LIB = os.path.join(os.path.dirname(__file__), "..")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


DOC = """# Plan

## Architecture

The write path authenticates every request.

## Data flow

Records are append-only.
"""


def test_section_hash_spans_whole_subsection(tmp_path):
    ra = _load("review_acceptance")
    # the "Architecture" span is heading-to-next-heading — the whole subsection, not one line
    h1 = ra.section_hash(DOC, "Architecture")
    edited = DOC.replace("authenticates every request", "authenticates every request (added a note)")
    h2 = ra.section_hash(edited, "Architecture")
    assert h1 != h2                      # an edit anywhere in the subsection invalidates the hash
    assert ra.section_hash(DOC, "Data flow") == ra.section_hash(edited, "Data flow")


def test_unresolved_heading_falls_back_to_whole_doc_hash(tmp_path):
    ra = _load("review_acceptance")
    assert ra.section_hash(DOC, "No Such Heading") == ra.whole_doc_hash(DOC)


def test_record_and_match_unchanged_section(tmp_path):
    ra = _load("review_acceptance")
    ra.record(str(tmp_path), "plan", [
        {"file": "plan.md", "title": "unauth path", "docSection": "Architecture"}], DOC)
    led = json.loads(open(os.path.join(str(tmp_path), "plan-accept.json")).read())
    assert led["accepted"][0]["identity"] == "plan.md::unauth path"
    # unchanged doc -> the section hash still matches (candidate for suppression)
    cands = ra.candidates(str(tmp_path), "plan", DOC)
    assert cands[0]["identity"] == "plan.md::unauth path" and cands[0]["hashMatches"] is True
    # edited section -> no longer a candidate (judged afresh)
    edited = DOC.replace("authenticates", "skips authenticating")
    cands2 = ra.candidates(str(tmp_path), "plan", edited)
    assert cands2[0]["hashMatches"] is False


def test_cross_cutting_finding_keyed_to_whole_doc(tmp_path):
    ra = _load("review_acceptance")
    ra.record(str(tmp_path), "plan", [
        {"file": "plan.md", "title": "structural", "docSection": None}], DOC)
    led = json.loads(open(os.path.join(str(tmp_path), "plan-accept.json")).read())
    assert led["accepted"][0]["docSection"] is None
    assert led["accepted"][0]["contentHash"] == ra.whole_doc_hash(DOC)


def test_record_preserves_still_valid_prior_acceptances(tmp_path):
    """Scoped-review fix (FR-14 durability): a suppressed-then-passed re-review's record()
    must not erase prior acceptances whose concerned content is unchanged — otherwise the
    NEXT review re-asks the settled decision. Changed-content entries are dropped (judged
    afresh, the safe direction)."""
    ra = _load("review_acceptance")
    ra.record(str(tmp_path), "plan", [
        {"file": "plan.md", "title": "unauth path", "docSection": "Architecture"}], DOC)
    # re-review on unchanged content: the accepted finding was suppressed, so this session's
    # terminal open blockers are EMPTY — record must carry the prior entry forward verbatim
    out = ra.record(str(tmp_path), "plan", [], DOC)
    assert out["ok"] and out["count"] == 1
    led = json.loads(open(os.path.join(str(tmp_path), "plan-accept.json")).read())
    assert [e["identity"] for e in led["accepted"]] == ["plan.md::unauth path"]
    # content changed: the carried entry's hash no longer matches -> dropped from the ledger
    edited = DOC.replace("authenticates every request", "skips authentication")
    out2 = ra.record(str(tmp_path), "plan", [], edited)
    assert out2["ok"] and out2["count"] == 0
    led2 = json.loads(open(os.path.join(str(tmp_path), "plan-accept.json")).read())
    assert led2["accepted"] == []


def test_record_union_new_blockers_with_preserved_priors_dedupes_identity(tmp_path):
    ra = _load("review_acceptance")
    ra.record(str(tmp_path), "plan", [
        {"file": "plan.md", "title": "unauth path", "docSection": "Architecture"}], DOC)
    # next park accepts a NEW blocker AND re-lists the same prior one — no duplicate entry
    out = ra.record(str(tmp_path), "plan", [
        {"file": "plan.md", "title": "unauth path", "docSection": "Architecture"},
        {"file": "plan.md", "title": "records lost on retry", "docSection": "Data flow"}], DOC)
    assert out["ok"] and out["count"] == 2
    led = json.loads(open(os.path.join(str(tmp_path), "plan-accept.json")).read())
    assert sorted(e["identity"] for e in led["accepted"]) == [
        "plan.md::records lost on retry", "plan.md::unauth path"]
