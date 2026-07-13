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
