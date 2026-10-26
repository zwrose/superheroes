"""The spec delivery lifecycle (CONVENTIONS §3.1, issue #2182).

A spec freezes when its work is delivered: `delivered`, `deliveryReceipt` and `livesIn` are
recorded together, and a later ruling that changes delivered behavior adds a `supersededInPart`
entry. These tests pin the validator, the writers, the anchor check, the doctrine's one shared
sentence, and every committed spec in this repository.
"""
import glob
import importlib.util
import json
import os
import subprocess
import sys

import jsonschema
import pytest
import yaml

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_PLUGIN_ROOT = os.path.join(_REPO_ROOT, "plugins", "superheroes")
_MODULE_PATH = os.path.join(_PLUGIN_ROOT, "lib", "definition_doc.py")

_spec = importlib.util.spec_from_file_location("lifecycle_definition_doc", _MODULE_PATH)
DD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(DD)

with open(os.path.join(_REPO_ROOT, "eval/lib/schemas/definition-doc.schema.json"),
          encoding="utf-8") as _fh:
    SCHEMA = json.load(_fh)

RECEIPT = "https://github.com/example/repo/pull/1#issuecomment-1"
BASE = (
    "---\n"
    "superheroes: doc\n"
    "schemaVersion: 1\n"
    "docType: spec\n"
    "workItem: sample-spec-abc123\n"
    "issue: null\n"
    "size: small\n"
    "status: %s\n"
    "%s"
    "gates: {review: %s}\n"
    'producedBy: "the-architect@0.1.0"\n'
    'created: "2026-01-01"\n'
    'updated: "2026-01-02"\n'
    "%s"
    "---\n"
    "# Sample\n\n## UFR-1\n\n## FR-6\n\n## Amendments\n\n_No amendments since the last full approval._\n"
)


def _doc(extra="", approved=True):
    if approved:
        return BASE % ("approved", 'approved: "2026-01-02"\n', "passed", extra)
    return BASE % ("draft", "", "pending", extra)


DELIVERED = ('delivered: "2026-02-01"\n'
             'deliveryReceipt: "%s"\n'
             'livesIn: ["plugins/superheroes/lib/definition_doc.py"]\n' % RECEIPT)


def _superseded(sections=("UFR-1", "FR-6"), date="2026-03-01", ruling="owner's ruling 9 a"):
    return "supersededInPart: %s\n" % json.dumps(
        [{"date": date, "sections": list(sections), "ruling": ruling}])


def _schema_ok(text):
    lines = text.split("\n")
    fm = yaml.safe_load("\n".join(lines[1:lines.index("---", 1)]))
    try:
        jsonschema.validate(fm, SCHEMA, format_checker=jsonschema.FormatChecker())
    except jsonschema.ValidationError:
        return False
    return True


# --- the validator: one row per rule, the library and the schema agreeing ----------------

VALID = [
    ("not-delivered", _doc()),
    ("delivered", _doc(DELIVERED)),
    ("delivered-and-superseded", _doc(DELIVERED + _superseded())),
]

INVALID = [
    ("delivered-without-date", _doc(DELIVERED.replace('delivered: "2026-02-01"\n', ""))),
    ("delivered-without-pointer", _doc(DELIVERED.replace(
        'livesIn: ["plugins/superheroes/lib/definition_doc.py"]\n', ""))),
    ("delivered-empty-pointer", _doc(DELIVERED.replace(
        '["plugins/superheroes/lib/definition_doc.py"]', "[]"))),
    ("delivered-without-receipt", _doc(DELIVERED.replace('deliveryReceipt: "%s"\n' % RECEIPT, ""))),
    ("delivered-not-approved", _doc(DELIVERED, approved=False)),
    ("delivered-bad-date", _doc(DELIVERED.replace("2026-02-01", "2026-2-1"))),
    ("superseded-without-delivery", _doc(_superseded())),
    ("superseded-without-sections", _doc(DELIVERED + _superseded(sections=()))),
    ("superseded-without-ruling", _doc(DELIVERED + _superseded(ruling=""))),
    ("superseded-bad-date", _doc(DELIVERED + _superseded(date="March"))),
    ("superseded-empty-list", _doc(DELIVERED + "supersededInPart: []\n")),
    ("superseded-blank-ruling", _doc(DELIVERED + _superseded(ruling="  "))),
    ("superseded-section-sign-only", _doc(DELIVERED + _superseded(sections=("§",)))),
    ("superseded-blank-section", _doc(DELIVERED + _superseded(sections=(" ",)))),
    ("delivered-blank-pointer", _doc(DELIVERED.replace(
        '["plugins/superheroes/lib/definition_doc.py"]', '[" "]'))),
]


@pytest.mark.parametrize("name,text", VALID, ids=[v[0] for v in VALID])
def test_valid_lifecycle_passes_library_and_schema(name, text):
    assert DD.lifecycle_errors(text) == []
    assert _schema_ok(text)


@pytest.mark.parametrize("name,text", INVALID, ids=[v[0] for v in INVALID])
def test_invalid_lifecycle_fails_library_and_schema(name, text):
    assert DD.lifecycle_errors(text), name
    assert not _schema_ok(text), name


def test_library_only_rules():
    # Ordering and JSON-shape rules the schema cannot see; each is its own refusal.
    assert DD.lifecycle_errors(_doc(DELIVERED.replace(
        '["plugins/superheroes/lib/definition_doc.py"]', '[" § FR-6"]')))
    assert DD.lifecycle_errors(_doc(DELIVERED.replace("2026-02-01", "2025-12-31")))
    assert DD.lifecycle_errors(_doc(DELIVERED + _superseded(date="2026-01-15")))
    assert DD.lifecycle_errors(_doc(DELIVERED.replace('"2026-02-01"', "2026-02-01 x")))
    assert DD.lifecycle_errors(_doc(DELIVERED + 'delivered: "2026-02-02"\n'))


@pytest.mark.parametrize("section", ["FR6", "FR-60", "R-6", "Purpose"])
def test_superseded_section_must_occur_in_the_body(section):
    # A typo the body never names would leave the real section's anchor uncovered.
    errors = DD.lifecycle_errors(_doc(DELIVERED + _superseded(sections=("FR-6", section))))
    assert any("does not contain" in e and repr(section) in e for e in errors), errors
    assert DD.lifecycle_errors(_doc(DELIVERED + _superseded(sections=("§ fr-6",)))) == []


@pytest.mark.parametrize("spelling", ['"supersededInPart": ', "supersededInPart : ",
                                      "'supersededInPart': "])
def test_noncanonical_key_spelling_is_refused_not_skipped(spelling):
    # YAML reads each of these as the key, so a line scan that skipped it would let the anchor
    # check miss a recorded supersession.
    line = _superseded().replace("supersededInPart: ", spelling)
    text = _doc(DELIVERED + line)
    assert any("non-canonical spelling" in e for e in DD.lifecycle_errors(text))
    with pytest.raises(ValueError):
        DD.superseding_ruling(text, "FR-6")


def test_lives_in_must_exist_under_root(tmp_path):
    text = _doc(DELIVERED)
    assert DD.lifecycle_errors(text, root=_REPO_ROOT) == []
    assert any("does not exist" in e for e in DD.lifecycle_errors(text, root=str(tmp_path)))


def test_lives_in_must_stay_under_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (tmp_path / "outside.md").write_text("x", encoding="utf-8")
    for escape in ("../outside.md", str(tmp_path / "outside.md")):
        text = _doc(DELIVERED.replace("plugins/superheroes/lib/definition_doc.py", escape))
        assert any("outside the repository" in e
                   for e in DD.lifecycle_errors(text, root=str(root))), escape


# --- the anchor check ----------------------------------------------------------------------

@pytest.mark.parametrize("section,covered", [
    ("FR-6", True), ("§ FR-6", True), ("fr-6", True), ("Part A · setup (FR-6)", True),
    ("UFR-1", True), ("FR-60", False), ("UFR-6", False), ("FR-1", False), ("Purpose", False),
])
def test_superseding_ruling_covers_named_sections_only(section, covered):
    entry = DD.superseding_ruling(_doc(DELIVERED + _superseded()), section)
    assert (entry is not None) is covered
    if covered:
        assert entry["ruling"] == "owner's ruling 9 a"


def test_superseding_ruling_names_the_latest_covering_ruling():
    entries = [
        {"date": "2026-04-01", "sections": ["FR-6"], "ruling": "newest"},
        {"date": "2026-03-01", "sections": ["FR-6", "UFR-1"], "ruling": "older"},
        {"date": "2026-04-01", "sections": ["UFR-1"], "ruling": "same day, written later"},
        {"date": "2026-03-15", "sections": ["UFR-1"], "ruling": "middle"},
    ]
    text = _doc(DELIVERED + "supersededInPart: %s\n" % json.dumps(entries))
    assert DD.superseding_ruling(text, "FR-6")["ruling"] == "newest"
    assert DD.superseding_ruling(text, "UFR-1")["ruling"] == "same day, written later"


def test_superseding_ruling_fails_closed_on_invalid_fields():
    with pytest.raises(ValueError):
        DD.superseding_ruling(_doc(_superseded()), "FR-6")
    assert DD.superseding_ruling(_doc(DELIVERED), "FR-6") is None


def _cli(*args):
    return subprocess.run([sys.executable, "-B", _MODULE_PATH, *args],
                          capture_output=True, text=True)


def test_cli_anchor_superseded_names_the_ruling(tmp_path):
    p = tmp_path / "spec.md"
    p.write_text(_doc(DELIVERED + _superseded()), encoding="utf-8")
    out = _cli("anchor-superseded", "--path", str(p), "--section", "FR-6")
    assert out.returncode == 0
    result = json.loads(out.stdout)
    assert result["covered"] is True and result["entry"]["ruling"] == "owner's ruling 9 a"
    p.write_text(_doc(_superseded()), encoding="utf-8")
    out = _cli("anchor-superseded", "--path", str(p), "--section", "FR-6")
    assert out.returncode == 1 and json.loads(out.stdout)["reason"] == "lifecycle-invalid"


# --- the writers ---------------------------------------------------------------------------

def test_mark_delivered_then_superseded_round_trips(tmp_path):
    p = tmp_path / "spec.md"
    p.write_text(_doc(), encoding="utf-8")
    assert DD.add_superseded(str(p), "2026-03-01", ["FR-6"], "r")["reason"] == "not-delivered"
    r = DD.mark_delivered(str(p), "2026-02-01", RECEIPT, ["lib/x.py"])
    assert r["ok"] is True
    assert DD.mark_delivered(str(p), "2026-02-01", RECEIPT, ["lib/x.py"])["reason"] == \
        "already-delivered"
    assert DD.add_superseded(str(p), "2026-03-01", ["FR-6"], "ruling one")["ok"] is True
    assert DD.add_superseded(str(p), "2026-03-02", ["UFR-1"], "ruling two")["ok"] is True
    text = p.read_text(encoding="utf-8")
    assert DD.lifecycle_errors(text) == [] and _schema_ok(text)
    assert DD.superseding_ruling(text, "UFR-1")["ruling"] == "ruling two"
    assert text.endswith(_doc().split("---\n", 2)[2])   # the body is untouched


@pytest.mark.parametrize("doc,args", [
    (_doc(approved=False), ("2026-02-01", RECEIPT, ["lib/x.py"])),
    (_doc(), ("2026-02-01", "not a link", ["x"])),
    (_doc(), ("2026-02-01", RECEIPT, [])),
    (_doc(), ("2025-12-31", RECEIPT, ["x"])),
    (_doc(), ("2026-2-1", RECEIPT, ["x"])),
], ids=["not-approved", "receipt-not-a-link", "no-pointer", "before-approval", "bad-date"])
def test_mark_delivered_refuses_what_lifecycle_check_rejects(tmp_path, doc, args):
    p = tmp_path / "spec.md"
    p.write_text(doc, encoding="utf-8")
    before = p.read_bytes()
    r = DD.mark_delivered(str(p), *args)
    assert r["reason"] == "lifecycle-invalid" and r["errors"]
    assert p.read_bytes() == before


@pytest.mark.parametrize("args", [
    ("2026-01-15", ["FR-6"], "r"), ("March", ["FR-6"], "r"), ("2026-03-01", [], "r"),
    ("2026-03-01", ["FR6"], "r"), ("2026-03-01", ["FR-6"], " "),
], ids=["predates-delivery", "bad-date", "no-sections", "section-not-in-body", "blank-ruling"])
def test_mark_superseded_refuses_what_lifecycle_check_rejects(tmp_path, args):
    p = tmp_path / "spec.md"
    p.write_text(_doc(DELIVERED + _superseded()), encoding="utf-8")
    before = p.read_bytes()
    r = DD.add_superseded(str(p), *args)
    assert r["reason"] == "lifecycle-invalid" and r["errors"]
    assert p.read_bytes() == before


def test_cli_writers_check_lives_in_under_root(tmp_path):
    # The CLI writer and `lifecycle-check --root` reject the same missing pointer.
    p = tmp_path / "spec.md"
    p.write_text(_doc(), encoding="utf-8")
    before = p.read_bytes()
    out = _cli("mark-delivered", "--path", str(p), "--date", "2026-02-01", "--receipt", RECEIPT,
               "--lives-in", "no/such/file.md", "--root", _REPO_ROOT)
    assert out.returncode == 1 and json.loads(out.stdout)["reason"] == "lifecycle-invalid"
    assert p.read_bytes() == before
    out = _cli("mark-delivered", "--path", str(p), "--date", "2026-02-01", "--receipt", RECEIPT,
               "--lives-in", "plugins/superheroes/lib/definition_doc.py § Lifecycle",
               "--root", _REPO_ROOT)
    assert out.returncode == 0, out.stdout
    out = _cli("mark-superseded", "--path", str(p), "--date", "2026-03-01",
               "--section", "FR-6", "--ruling", "owner's ruling 9 a", "--root", _REPO_ROOT)
    assert out.returncode == 0, out.stdout
    assert _cli("lifecycle-check", "--path", str(p), "--root", _REPO_ROOT).returncode == 0


def test_set_gate_refuses_a_delivered_spec(tmp_path):
    p = tmp_path / "spec.md"
    p.write_text(_doc(DELIVERED), encoding="utf-8")
    before = p.read_bytes()
    r = DD.set_gate(str(p), "pending", expected_hash="current", run_id="r1")
    assert r == {"ok": False, "reason": "delivered-spec-frozen"}
    assert p.read_bytes() == before


def test_set_gate_refuses_a_delivered_specs_reapproval_cycle(tmp_path):
    # passed -> changes-requested -> passed would re-date `approved` past `delivered` and leave
    # the spec invalid with no sanctioned repair; every step of the cycle is refused.
    p = tmp_path / "spec.md"
    p.write_text(_doc(DELIVERED), encoding="utf-8")
    before = p.read_bytes()
    for review in ("changes-requested", "passed"):
        r = DD.set_gate(str(p), review, expected_hash="current", run_id="r1")
        assert r == {"ok": False, "reason": "delivered-spec-frozen"}, review
        assert p.read_bytes() == before
    assert DD.lifecycle_errors(p.read_text(encoding="utf-8")) == []


# --- the committed specs ---------------------------------------------------------------------

def test_every_committed_spec_lifecycle_is_valid():
    paths = sorted(glob.glob(os.path.join(_REPO_ROOT, "docs/superheroes/*/spec.md")))
    assert paths
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            assert DD.lifecycle_errors(fh.read(), path, root=_REPO_ROOT) == [], path


def test_cloud_builders_spec_is_delivered_and_superseded_in_part():
    path = os.path.join(_REPO_ROOT, "docs/superheroes/cloud-builders-66a2e8/spec.md")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    for section in ("UFR-1", "FR-6"):
        assert "392 a" in DD.superseding_ruling(text, section)["ruling"]
    assert DD.superseding_ruling(text, "FR-1") is None


# --- the doctrine: one sentence, three homes ---------------------------------------------------

LIFECYCLE_SENTENCE = (
    "A spec is amended in place while it is approved and its work is building, freezes when the "
    "owner accepts its delivery, and after that takes only superseded-in-part lines: a later "
    "owner ruling that changes delivered behavior is marked on the spec, never amended into its "
    "body."
)
AMENDMENTS_SCOPE = "This path covers a spec that is approved and not yet delivered"


def _read(rel):
    with open(os.path.join(_PLUGIN_ROOT, rel), encoding="utf-8") as fh:
        return " ".join(fh.read().split())


@pytest.mark.parametrize("rel", [
    "skills/architect-spec/reference/spec-content.md",
    "skills/showrunner/reference/closure.md",
    "skills/showrunner/reference/issue-contract.md",
])
def test_lifecycle_sentence_is_said_in_the_same_words(rel):
    assert LIFECYCLE_SENTENCE in _read(rel)


def test_amendments_are_scoped_to_before_delivery():
    assert AMENDMENTS_SCOPE in _read("skills/showrunner/reference/amendments.md")


def test_conventions_states_the_lifecycle_fields():
    with open(os.path.join(_REPO_ROOT, "CONVENTIONS.md"), encoding="utf-8") as fh:
        text = fh.read()
    section = text[text.index("### 3.1 Shared frontmatter"):text.index("### 3.2 Body")]
    for field in DD.LIFECYCLE_FIELDS:
        assert field in section, field


@pytest.mark.parametrize("rel,verb", [
    ("skills/showrunner/reference/closure.md", "mark-delivered"),
    ("skills/architect-spec/reference/spec-content.md", "mark-superseded"),
    ("skills/showrunner/reference/amendments.md", "mark-superseded"),
    ("TRANSITION.md", "mark-delivered"),
    ("TRANSITION.md", "mark-superseded"),
])
def test_doctrine_names_the_writer_verbs(rel, verb):
    text = _read(rel)
    assert verb in text
    assert "a hand edit of the front matter" not in text and "by hand, and checks" not in text
