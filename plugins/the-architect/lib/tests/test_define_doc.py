"""Conformance: the-architect's define-doc helper obeys the band contracts.

This is the-architect's slice of the Phase-1 conformance track (eval/gate.md):
the frontmatter it emits MUST validate against the band's define-doc schema, the
work-item slug it mints MUST match §6.1, and the in-repo location MUST be the
§3.3 layout. If the-architect ever drifts from the shared contract, this fails.

jsonschema is a hard dependency (CI installs it) — no importorskip, so a missing
dep fails loudly rather than silently skipping (the eval-suite convention).
"""
import importlib.util
import json
import os
import re

import jsonschema
import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def _load(rel_path, mod_name):
    path = os.path.join(_REPO_ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DD = _load("plugins/the-architect/lib/define_doc.py", "architect_define_doc")

with open(os.path.join(_REPO_ROOT, "eval/lib/schemas/define-doc.schema.json"), encoding="utf-8") as _fh:
    SCHEMA = json.load(_fh)

WORKITEM_RE = re.compile(SCHEMA["properties"]["workItem"]["pattern"])


# --- mint + locate ---------------------------------------------------------

def test_mint_matches_band_golden():
    # Same (title, nonce) the band reference pins — proves the vendored
    # identifiers flow through mint_work_item unchanged.
    assert DD.mint_work_item("Add Dark Mode Toggle", "fixed-nonce-v1") == "add-dark-mode-toggle-50c082"


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
    slug = "add-dark-mode-toggle-50c082"
    assert DD.work_item_dir(slug, root="/r") == "/r/docs/superheroes/" + slug
    assert DD.doc_path(slug, "spec", root="/r") == "/r/docs/superheroes/%s/spec.md" % slug
    assert DD.doc_path(slug, "tasks", root="/r") == "/r/docs/superheroes/%s/tasks.md" % slug


def test_doc_path_rejects_unknown_doctype():
    with pytest.raises(ValueError):
        DD.doc_path("x-abc123", "design")


# --- frontmatter (§3.1) ----------------------------------------------------

WI = "add-dark-mode-toggle-50c082"


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
    # spec must not have a parent
    with pytest.raises(ValueError):
        DD.frontmatter("spec", WI, size="small", parent="something-abc123")
    # plan must have a parent
    with pytest.raises(ValueError):
        DD.frontmatter("plan", "plan-x-aaa111", size="small")
    # tasks parent must be a plan, not a spec
    with pytest.raises(ValueError):
        DD.frontmatter("tasks", "tasks-x-bbb222", size="small",
                       parent={"workItem": WI, "docType": "spec"})


def test_frontmatter_with_issue_validates():
    fm = DD.frontmatter("spec", WI, size="medium", issue=42,
                        created="2026-06-14", updated="2026-06-14")
    jsonschema.validate(fm, SCHEMA)
    assert fm["issue"] == 42


# --- render ----------------------------------------------------------------

def test_render_is_a_fenced_block_with_quoted_dates():
    fm = DD.frontmatter("spec", WI, size="medium", created="2026-06-14", updated="2026-06-14")
    out = DD.render_frontmatter(fm)
    assert out.startswith("---\n") and out.rstrip().endswith("---")
    assert "superheroes: doc" in out
    assert f"workItem: {WI}" in out
    assert "parent: null" in out
    assert "gates: {review: pending}" in out
    # dates and producedBy are quoted so a YAML reader keeps them as strings
    assert 'created: "2026-06-14"' in out
    assert 'updated: "2026-06-14"' in out
    assert out.count('"the-architect@') == 1


def test_render_plan_parent_is_flow_mapping():
    fm = DD.frontmatter("plan", "plan-x-aaa111", size="small", parent=WI,
                        created="2026-06-14", updated="2026-06-14")
    out = DD.render_frontmatter(fm)
    assert "parent: {workItem: %s, docType: spec}" % WI in out
