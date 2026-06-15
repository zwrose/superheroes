"""Conformance: the-architect's definition-doc helper obeys the band contracts.

This is the-architect's slice of the Phase-1 conformance track (eval/gate.md):
the frontmatter it emits MUST validate against the band's definition-doc schema,
the work-item slug it mints MUST match §6.1, and the in-repo location MUST be the
§3.3 layout. If the-architect ever drifts from the shared contract, this fails.

Critically, we parse `render_frontmatter`'s output with a REAL YAML parser and
re-validate it against the schema — the renderer is hand-rolled, so substring
checks alone could not prove the emitted bytes round-trip to a schema-valid dict.

jsonschema and pyyaml are hard dependencies (CI installs them) — no importorskip,
so a missing dep fails loudly rather than silently skipping (the eval convention).
"""
import importlib.util
import json
import os
import re
import subprocess
import sys

import jsonschema
import pytest
import yaml

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_MODULE_PATH = os.path.join(_REPO_ROOT, "plugins/the-architect/lib/definition_doc.py")


def _load(rel_path, mod_name):
    path = os.path.join(_REPO_ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DD = _load("plugins/the-architect/lib/definition_doc.py", "architect_definition_doc")

with open(os.path.join(_REPO_ROOT, "eval/lib/schemas/definition-doc.schema.json"), encoding="utf-8") as _fh:
    SCHEMA = json.load(_fh)

WORKITEM_RE = re.compile(SCHEMA["properties"]["workItem"]["pattern"])
WI = "add-dark-mode-toggle-50c082"


def _parse_frontmatter(block):
    """Extract the frontmatter between the `---` fences and parse it as a real
    frontmatter reader would — proving the rendered block is valid YAML."""
    lines = block.split("\n")
    assert lines[0] == "---", "frontmatter must open with ---"
    end = lines.index("---", 1)
    return yaml.safe_load("\n".join(lines[1:end]))


# --- mint + locate ---------------------------------------------------------

def test_mint_matches_band_golden():
    # Same (title, nonce) the band reference pins — proves the vendored
    # identifiers flow through mint_work_item unchanged.
    assert DD.mint_work_item("Add Dark Mode Toggle", "fixed-nonce-v1") == WI


def test_mint_matches_schema_pattern():
    for title in ["Add Dark Mode Toggle", "café menu", "!!!", "x" * 100]:
        slug = DD.mint_work_item(title, "n")
        assert WORKITEM_RE.match(slug), slug


def test_mint_random_nonce_is_valid_and_varies():
    a = DD.mint_work_item("Same Title")
    b = DD.mint_work_item("Same Title")
    assert WORKITEM_RE.match(a) and WORKITEM_RE.match(b)
    assert a != b  # fresh random nonce disambiguates same-titled items


def test_location_is_in_repo_layout():
    assert DD.work_item_dir(WI, root="/r") == "/r/docs/superheroes/" + WI
    assert DD.doc_path(WI, "spec", root="/r") == "/r/docs/superheroes/%s/spec.md" % WI
    assert DD.doc_path(WI, "tasks", root="/r") == "/r/docs/superheroes/%s/tasks.md" % WI


def test_doc_path_rejects_unknown_doctype():
    with pytest.raises(ValueError):
        DD.doc_path("x-abc123", "design")


# --- frontmatter dict (§3.1) ----------------------------------------------

def test_spec_frontmatter_validates():
    fm = DD.frontmatter("spec", WI, size="medium", created="2026-06-14", updated="2026-06-14")
    jsonschema.validate(fm, SCHEMA)
    assert fm["parent"] is None
    assert fm["producedBy"] == DD.produced_by()
    assert fm["producedBy"].startswith("the-architect@")


def test_plan_and_tasks_frontmatter_validate():
    plan = DD.frontmatter("plan", "plan-x-aaa111", size="small", parent=WI,
                          created="2026-06-14", updated="2026-06-14")
    jsonschema.validate(plan, SCHEMA)
    assert plan["parent"] == {"workItem": WI, "docType": "spec"}

    tasks = DD.frontmatter("tasks", "tasks-x-bbb222", size="large",
                           parent={"workItem": "plan-x-aaa111", "docType": "plan"},
                           created="2026-06-14", updated="2026-06-14")
    jsonschema.validate(tasks, SCHEMA)
    assert tasks["parent"]["docType"] == "plan"


def test_frontmatter_enforces_parent_invariant():
    with pytest.raises(ValueError):  # spec must not have a parent
        DD.frontmatter("spec", WI, size="small", parent="something-abc123")
    with pytest.raises(ValueError):  # plan must have a parent
        DD.frontmatter("plan", "plan-x-aaa111", size="small")
    with pytest.raises(ValueError):  # tasks parent must be a plan, not a spec
        DD.frontmatter("tasks", "tasks-x-bbb222", size="small",
                       parent={"workItem": WI, "docType": "spec"})


def test_frontmatter_with_issue_validates():
    fm = DD.frontmatter("spec", WI, size="medium", issue=42,
                        created="2026-06-14", updated="2026-06-14")
    jsonschema.validate(fm, SCHEMA)
    assert fm["issue"] == 42


# --- render: parse with a REAL YAML reader and re-validate -----------------

ROUNDTRIP_CASES = [
    ("spec", WI, dict(size="medium")),                                  # null parent, null issue
    ("spec", WI, dict(size="small", issue=42)),                         # issue set (stays int)
    ("plan", "plan-x-aaa111", dict(size="small", parent=WI)),           # parent flow-mapping
    ("tasks", "tasks-x-bbb222",
     dict(size="large", parent={"workItem": "plan-x-aaa111", "docType": "plan"})),
]


@pytest.mark.parametrize("doc_type,work_item,kw", ROUNDTRIP_CASES)
def test_render_roundtrips_to_schema_valid_dict(doc_type, work_item, kw):
    fm = DD.frontmatter(doc_type, work_item, created="2026-06-14", updated="2026-06-14", **kw)
    parsed = _parse_frontmatter(DD.render_frontmatter(fm))
    # The rendered block is valid YAML AND validates against the band schema...
    jsonschema.validate(parsed, SCHEMA)
    # ...and round-trips losslessly with NO type coercion (e.g. dates stay strings,
    # issue stays an int) — the guard the substring tests can't give.
    assert parsed == fm


def test_render_quotes_dates_so_yaml_keeps_them_as_strings():
    fm = DD.frontmatter("spec", WI, size="medium", created="2026-06-14", updated="2026-06-14")
    parsed = _parse_frontmatter(DD.render_frontmatter(fm))
    assert isinstance(parsed["created"], str) and parsed["created"] == "2026-06-14"
    assert isinstance(parsed["updated"], str)
    out = DD.render_frontmatter(fm)
    assert 'created: "2026-06-14"' in out and 'producedBy: "the-architect@' in out


# --- CLI (the surface the skills actually drive) ---------------------------

def _run_main(argv, capsys):
    rc = DD.main(["definition_doc.py", *argv])
    return rc, capsys.readouterr().out


def test_cli_mint(capsys):
    rc, out = _run_main(["mint", "--title", "Add Dark Mode Toggle", "--nonce", "fixed-nonce-v1"], capsys)
    assert rc == 0 and out.strip() == WI


def test_cli_path_and_dir(capsys):
    rc, out = _run_main(["path", "--work-item", WI, "--doc", "spec", "--root", "/r"], capsys)
    assert rc == 0 and out.strip() == "/r/docs/superheroes/%s/spec.md" % WI
    rc, out = _run_main(["dir", "--work-item", WI, "--root", "/r"], capsys)
    assert rc == 0 and out.strip() == "/r/docs/superheroes/" + WI


def test_cli_frontmatter_roundtrips(capsys):
    rc, out = _run_main(["frontmatter", "--doc", "spec", "--work-item", WI, "--size", "medium",
                         "--created", "2026-06-14", "--updated", "2026-06-14"], capsys)
    assert rc == 0
    parsed = _parse_frontmatter(out)
    jsonschema.validate(parsed, SCHEMA)
    assert parsed["docType"] == "spec" and parsed["workItem"] == WI


def test_cli_frontmatter_plan_wires_parent(capsys):
    # --parent-item must wire through to the `parent=` kwarg (the flag→kwarg glue).
    rc, out = _run_main(["frontmatter", "--doc", "plan", "--work-item", "plan-x-aaa111",
                         "--size", "small", "--parent-item", WI,
                         "--created", "2026-06-14", "--updated", "2026-06-14"], capsys)
    assert rc == 0
    parsed = _parse_frontmatter(out)
    assert parsed["parent"] == {"workItem": WI, "docType": "spec"}


def test_cli_invalid_combo_exits_nonzero_via_script():
    # The __main__ guard maps a ValueError (plan without a parent) to exit 1 + stderr.
    proc = subprocess.run(
        [sys.executable, _MODULE_PATH, "frontmatter", "--doc", "plan",
         "--work-item", "plan-x-aaa111", "--size", "small"],
        capture_output=True, text=True)
    assert proc.returncode == 1
    assert "definition_doc error" in proc.stderr


# --- review gate (set/read) ------------------------------------------------

def _write_spec(tmp_path):
    fm = DD.frontmatter("spec", WI, size="medium", created="2026-06-14", updated="2026-06-14")
    p = tmp_path / "spec.md"
    # include a body line that looks gate-ish, to prove frontmatter-scoping
    p.write_text(DD.render_frontmatter(fm) + "\n# Title\n\nWe will discuss gates: and review: here.\n",
                 encoding="utf-8")
    return str(p)


def test_read_gate_default_is_pending(tmp_path):
    assert DD.read_gate(_write_spec(tmp_path)) == "pending"


def test_set_gate_passed_derives_approved_and_revalidates(tmp_path):
    p = _write_spec(tmp_path)
    assert DD.set_gate(p, "passed") == {"review": "passed", "status": "approved"}
    assert DD.read_gate(p) == "passed"
    parsed = _parse_frontmatter(open(p, encoding="utf-8").read())
    jsonschema.validate(parsed, SCHEMA)  # still schema-valid after the in-place edit
    assert parsed["gates"] == {"review": "passed"} and parsed["status"] == "approved"


def test_set_gate_changes_requested_derives_in_review(tmp_path):
    p = _write_spec(tmp_path)
    DD.set_gate(p, "changes-requested")
    parsed = _parse_frontmatter(open(p, encoding="utf-8").read())
    assert parsed["gates"]["review"] == "changes-requested" and parsed["status"] == "in-review"


def test_set_gate_rejects_non_review_state(tmp_path):
    with pytest.raises(ValueError):  # 'approved' is a status, not a review state
        DD.set_gate(_write_spec(tmp_path), "approved")


def test_read_gate_fails_closed_without_frontmatter(tmp_path):
    p = tmp_path / "bad.md"
    p.write_text("# no frontmatter\n", encoding="utf-8")
    with pytest.raises(ValueError):
        DD.read_gate(str(p))


def test_cli_set_then_read_gate(tmp_path, capsys):
    # round-trip through the CLI surface the skills actually drive
    fm = DD.frontmatter("spec", WI, size="small", created="2026-06-14", updated="2026-06-14")
    d = tmp_path / "docs" / "superheroes" / WI
    d.mkdir(parents=True)
    (d / "spec.md").write_text(DD.render_frontmatter(fm) + "\n# t\n", encoding="utf-8")
    rc = DD.main(["definition_doc.py", "set-gate", "--doc", "spec", "--work-item", WI,
                  "--review", "passed", "--root", str(tmp_path)])
    assert rc == 0
    capsys.readouterr()
    rc = DD.main(["definition_doc.py", "read-gate", "--doc", "spec", "--work-item", WI,
                  "--root", str(tmp_path)])
    assert rc == 0 and capsys.readouterr().out.strip() == "passed"
