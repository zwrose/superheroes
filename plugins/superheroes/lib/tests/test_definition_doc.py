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
_MODULE_PATH = os.path.join(_REPO_ROOT, "plugins/superheroes/lib/definition_doc.py")


def _load(rel_path, mod_name):
    path = os.path.join(_REPO_ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DD = _load("plugins/superheroes/lib/definition_doc.py", "architect_definition_doc")

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


# --- #25: quick discovery's orphan tasks doc (null parent, opt-in) ---------

def test_tasks_orphan_frontmatter_allows_null_parent():
    # Quick discovery authors a tasks doc with no plan/spec ancestor — it IS the root input
    # artifact, so a null parent is correct (schema-valid) exactly as a spec's is.
    fm = DD.frontmatter("tasks", "tasks-x-bbb222", size="small", allow_orphan=True,
                        created="2026-06-14", updated="2026-06-14")
    jsonschema.validate(fm, SCHEMA)
    assert fm["parent"] is None


def test_tasks_orphan_is_opt_in_only():
    # Without allow_orphan a parent-less tasks doc still fails closed (the full path is unchanged),
    # and allow_orphan never loosens spec/plan nor a tasks doc that WAS given a parent.
    with pytest.raises(ValueError):
        DD.frontmatter("tasks", "tasks-x-bbb222", size="small")
    with pytest.raises(ValueError):
        DD.frontmatter("plan", "plan-x-aaa111", size="small", allow_orphan=True)
    with pytest.raises(ValueError):  # tasks given a spec parent is still rejected
        DD.frontmatter("tasks", "tasks-x-bbb222", size="small", allow_orphan=True,
                       parent={"workItem": WI, "docType": "spec"})


def test_tasks_orphan_content_hash_is_present_and_deterministic(tmp_path):
    # §6.3 content-hash (the deterministic build-branch key) requires the `parent` stable field to
    # be PRESENT — a null parent renders + reads back as the literal "null" (present, not missing),
    # so the hash never raises and is stable across reads (a stable quick-route build branch).
    import identifiers
    fm = DD.frontmatter("tasks", "tasks-x-bbb222", size="small", allow_orphan=True,
                        created="2026-06-14", updated="2026-06-14")
    p = tmp_path / "tasks.md"
    p.write_text(DD.render_frontmatter(fm) + "\n# t\n### Task 1: go\n", encoding="utf-8")
    fm1, body1 = DD.read_frontmatter(str(p))
    fm2, body2 = DD.read_frontmatter(str(p))
    assert fm1.get("parent") == "null"  # present as the literal, not absent
    assert identifiers.content_hash(fm1, body1) == identifiers.content_hash(fm2, body2)


def test_cli_frontmatter_orphan_tasks_renders_null_parent(capsys):
    rc, out = _run_main(["frontmatter", "--doc", "tasks", "--work-item", "tasks-x-bbb222",
                         "--size", "small", "--orphan",
                         "--created", "2026-06-14", "--updated", "2026-06-14"], capsys)
    assert rc == 0
    parsed = _parse_frontmatter(out)
    jsonschema.validate(parsed, SCHEMA)
    assert parsed["parent"] is None and parsed["docType"] == "tasks"


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


def test_cli_path_and_dir(tmp_path):
    # spec present in-repo → spec-anchored resolution returns the in-repo layout deterministically
    d = os.path.join(str(tmp_path), "docs", "superheroes", WI)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "spec.md"), "w").write("x")
    out = subprocess.run([sys.executable, _MODULE_PATH, "path", "--work-item", WI,
                          "--doc", "plan", "--root", str(tmp_path)],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == os.path.join(d, "plan.md")
    dout = subprocess.run([sys.executable, _MODULE_PATH, "dir", "--work-item", WI,
                           "--root", str(tmp_path)], capture_output=True, text=True)
    assert dout.returncode == 0, dout.stderr
    assert dout.stdout.strip() == d


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


def _set_gate_file(path, review, run_id="test-run"):
    text = open(path, encoding="utf-8").read()
    return DD.set_gate(path, review, expected_hash=DD.content_hash(text), run_id=run_id)


def test_set_gate_passed_derives_approved_and_revalidates(tmp_path):
    p = _write_spec(tmp_path)
    assert _set_gate_file(p, "passed") == {"ok": True, "review": "passed", "status": "approved", "runId": "test-run"}
    assert DD.read_gate(p) == "passed"
    parsed = _parse_frontmatter(open(p, encoding="utf-8").read())
    jsonschema.validate(parsed, SCHEMA)  # still schema-valid after the in-place edit
    assert parsed["gates"] == {"review": "passed"} and parsed["status"] == "approved"


def test_set_gate_changes_requested_derives_in_review(tmp_path):
    p = _write_spec(tmp_path)
    _set_gate_file(p, "changes-requested")
    parsed = _parse_frontmatter(open(p, encoding="utf-8").read())
    assert parsed["gates"]["review"] == "changes-requested" and parsed["status"] == "in-review"


def test_set_gate_rejects_non_review_state(tmp_path):
    with pytest.raises(ValueError):  # 'approved' is a status, not a review state
        _set_gate_file(_write_spec(tmp_path), "approved")


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
    spec_path = d / "spec.md"
    spec_path.write_text(DD.render_frontmatter(fm) + "\n# t\n", encoding="utf-8")
    spec_hash = DD.content_hash(spec_path.read_text(encoding="utf-8"))
    rc = DD.main(["definition_doc.py", "set-gate", "--doc", "spec", "--work-item", WI,
                  "--review", "passed", "--root", str(tmp_path),
                  "--expected-hash", spec_hash, "--run-id", "cli-test"])
    assert rc == 0
    capsys.readouterr()
    rc = DD.main(["definition_doc.py", "read-gate", "--doc", "spec", "--work-item", WI,
                  "--root", str(tmp_path)])
    assert rc == 0 and capsys.readouterr().out.strip() == "passed"


@pytest.mark.parametrize("doc_type,wi,parent", [
    ("plan", "plan-x-aaa111", WI),
    ("tasks", "tasks-x-bbb222", {"workItem": "plan-x-aaa111", "docType": "plan"}),
])
def test_cli_set_then_read_gate_for_autonomous_doctypes(tmp_path, capsys, doc_type, wi, parent):
    # Plan and Tasks are autonomous: each self-certifies its OWN gate (no owner authority,
    # unlike spec) so the next phase doesn't deadlock. That drives `set-gate --doc plan` /
    # `--doc tasks` — prove the gate CLI is doc-type-agnostic, not spec-only, and that it
    # round-trips to passed + derives an approved, schema-valid frontmatter.
    fm = DD.frontmatter(doc_type, wi, size="small", parent=parent,
                        created="2026-06-14", updated="2026-06-14")
    d = tmp_path / "docs" / "superheroes" / wi
    d.mkdir(parents=True)
    (d / "spec.md").write_text("x")
    doc_file = d / (doc_type + ".md")
    doc_file.write_text(DD.render_frontmatter(fm) + "\n# t\n", encoding="utf-8")
    doc_hash = DD.content_hash(doc_file.read_text(encoding="utf-8"))
    rc = DD.main(["definition_doc.py", "set-gate", "--doc", doc_type, "--work-item", wi,
                  "--review", "passed", "--root", str(tmp_path),
                  "--expected-hash", doc_hash, "--run-id", "cli-test"])
    assert rc == 0
    capsys.readouterr()
    rc = DD.main(["definition_doc.py", "read-gate", "--doc", doc_type, "--work-item", wi,
                  "--root", str(tmp_path)])
    assert rc == 0 and capsys.readouterr().out.strip() == "passed"
    parsed = _parse_frontmatter((d / (doc_type + ".md")).read_text(encoding="utf-8"))
    jsonschema.validate(parsed, SCHEMA)
    assert parsed["gates"]["review"] == "passed" and parsed["status"] == "approved"


def test_work_item_dir_honors_location():
    assert DD.work_item_dir(WI, root="/r", location="docs/specs") == "/r/docs/specs/" + WI
    assert DD.doc_path(WI, "spec", root="/r", location="docs/specs") == "/r/docs/specs/%s/spec.md" % WI
    # default unchanged (existing callers)
    assert DD.work_item_dir(WI, root="/r") == "/r/docs/superheroes/" + WI


# --- resolve_work_item_dir (mode-aware, spec-anchored) ---------------------

def _stub_mode(monkeypatch, mode, store):
    import mode_registry, architect_config
    monkeypatch.setattr(mode_registry, "resolve",
                        lambda cwd, root=None: {"mode": mode})
    monkeypatch.setattr(mode_registry, "project_store_dir",
                        lambda cwd, root=None: store)
    monkeypatch.setattr(architect_config, "read_policy",
                        lambda cwd, root=None: None)


def test_resolve_new_workitem_global_goes_to_store(tmp_path, monkeypatch):
    store = str(tmp_path / "store")
    _stub_mode(monkeypatch, "global", store)
    d = DD.resolve_work_item_dir(WI, root=str(tmp_path), cwd=str(tmp_path))
    assert d == os.path.join(store, "docs", WI)


def test_resolve_new_workitem_inrepo_uses_location(tmp_path, monkeypatch):
    store = str(tmp_path / "store")
    _stub_mode(monkeypatch, "in-repo", store)
    d = DD.resolve_work_item_dir(WI, root=str(tmp_path), cwd=str(tmp_path))
    assert d == os.path.join(str(tmp_path), "docs", "superheroes", WI)


def test_resolve_anchors_on_existing_spec(tmp_path, monkeypatch):
    # spec already exists in-repo; recorded mode says global → still resolves in-repo.
    store = str(tmp_path / "store")
    _stub_mode(monkeypatch, "global", store)
    inrepo = os.path.join(str(tmp_path), "docs", "superheroes", WI)
    os.makedirs(inrepo, exist_ok=True)
    open(os.path.join(inrepo, "spec.md"), "w").write("x")
    d = DD.resolve_work_item_dir(WI, root=str(tmp_path), cwd=str(tmp_path))
    assert d == inrepo


def test_resolve_propagates_unknown_schema(tmp_path, monkeypatch):
    import mode_registry
    def boom(cwd, root=None):
        raise mode_registry.UnknownSchemaVersion("newer")
    monkeypatch.setattr(mode_registry, "resolve", boom)
    with pytest.raises(mode_registry.UnknownSchemaVersion):
        DD.resolve_work_item_dir(WI, root=str(tmp_path), cwd=str(tmp_path))


import json as _json


def _git_repo(path):
    subprocess.run(["git", "init", "-q", path], check=True)
    subprocess.run(["git", "-C", path, "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", path, "config", "user.name", "t"], check=True)


def _resolve_write(tmp, doc="spec", store=None):
    args = [sys.executable, _MODULE_PATH, "resolve-write", "--work-item", WI,
            "--doc", doc, "--root", str(tmp), "--cwd", str(tmp)]
    env = dict(os.environ)
    return subprocess.run(args, capture_output=True, text=True, env=env)


def test_resolve_write_prints_path_inrepo(tmp_path):
    # A fresh repo with an in-repo spec anchors in-repo; the verb prints the .md path, exit 0.
    d = os.path.join(str(tmp_path), "docs", "superheroes", WI)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "spec.md"), "w").write("x")
    out = _resolve_write(tmp_path)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().endswith(os.path.join(WI, "spec.md"))


def test_resolve_write_halts_on_unknown_schema(tmp_path):
    # UFR-7: a NEWER registry schemaVersion is undeterminable → exit 1, no guessed write,
    # an owner-facing message. Drop a newer-schema registry into the project store that
    # mode_registry.resolve will read.
    _git_repo(str(tmp_path))
    import sys as _sys
    _sys.path.insert(0, os.path.join(_REPO_ROOT, "plugins/superheroes/lib"))
    import mode_registry as _mr
    store = _mr.project_store_dir(str(tmp_path))
    os.makedirs(store, exist_ok=True)
    with open(os.path.join(store, "registry.json"), "w") as fh:
        _json.dump({"schemaVersion": 999, "storageMode": "global",
                    "remoteKey": None, "createdAt": "t"}, fh)
    out = _resolve_write(tmp_path)
    assert out.returncode == 1
    assert "could not be determined" in out.stderr


def test_default_location_matches_architect_config():
    import architect_config
    assert DD.DEFAULT_LOCATION == architect_config.DEFAULT_LOCATION


def test_resolve_write_path_inrepo_returns_md(tmp_path):
    d = os.path.join(str(tmp_path), "docs", "superheroes", WI)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "spec.md"), "w").write("x")  # anchor in-repo
    got = DD.resolve_write_path(WI, "spec", root=str(tmp_path), cwd=str(tmp_path))
    assert got == os.path.join(d, "spec.md")
    assert os.path.isdir(d)


def test_resolve_write_path_raises_ignore_coverage(tmp_path, monkeypatch):
    import architect_config
    d = os.path.join(str(tmp_path), "docs", "superheroes", WI)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "spec.md"), "w").write("x")  # anchor in-repo
    monkeypatch.setattr(architect_config, "read_policy",
                        lambda cwd, root=None: {"location": "docs/superheroes",
                                                "visibility": architect_config.GITIGNORED,
                                                "confirmed": True})
    monkeypatch.setattr(architect_config, "ensure_ignored", lambda repo, loc: False)
    with pytest.raises(DD.IgnoreCoverageError):
        DD.resolve_write_path(WI, "spec", root=str(tmp_path), cwd=str(tmp_path))


def test_resolve_write_refuses_gitignored_but_tracked(tmp_path):
    # UFR-8: a gitignored policy whose location is already tracked cannot be kept local →
    # refuse the write (exit 1, no exposed doc).
    repo = str(tmp_path)
    _git_repo(repo)
    loc = os.path.join(repo, "docs", "superheroes")
    os.makedirs(loc, exist_ok=True)
    open(os.path.join(loc, "tracked.md"), "w").write("x")
    subprocess.run(["git", "-C", repo, "add", "docs/superheroes/tracked.md"], check=True)
    import sys as _sys
    _sys.path.insert(0, os.path.join(_REPO_ROOT, "plugins/superheroes/lib"))
    import mode_registry as _mr, architect_config as _ac
    # record an in-repo mode + a gitignored policy for this location
    store = _mr.project_store_dir(repo)
    os.makedirs(store, exist_ok=True)
    with open(os.path.join(store, "registry.json"), "w") as fh:
        _json.dump({"schemaVersion": 1, "storageMode": "in-repo",
                    "remoteKey": None, "createdAt": "t"}, fh)
    _ac.write_policy(repo, {"location": "docs/superheroes",
                            "visibility": "gitignored", "confirmed": True})
    out = _resolve_write(tmp_path)
    assert out.returncode == 1
    assert "refusing to write" in out.stderr
