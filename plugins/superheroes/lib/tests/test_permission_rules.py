import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import permission_rules as pr


def test_real_worktree_interpreter_confined(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    wt = root / "abc123"
    wt.mkdir(parents=True)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    assert pr.worktree_confined("python3 -c 'print(1)'", str(wt)) is True


def test_root_itself_is_not_a_strict_descendant(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    root.mkdir(parents=True)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    assert pr.worktree_confined("python3 -c 'x'", str(root)) is False


def test_parent_hop_earns_nothing(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    (root / "wt").mkdir(parents=True)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    # cwd escapes the root via `..` — realpath resolves it OUT of the root
    escaped = os.path.join(str(root), "wt", "..", "..")
    assert pr.worktree_confined("python3 -c 'x'", escaped) is False


def test_symlink_into_root_is_resolved_and_confined(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    (root / "real").mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(root / "real")
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    # a symlink whose realpath IS under root -> confined
    assert pr.worktree_confined("python3 -c 'x'", str(link)) is True


def test_symlink_lookalike_outside_root_earns_nothing(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    root.mkdir(parents=True)
    outside = tmp_path / "evil"
    outside.mkdir()
    link = root.parent / ".superheroes-worktrees-evil"   # name-prefix lookalike, not a descendant
    link.symlink_to(outside)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    assert pr.worktree_confined("python3 -c 'x'", str(link)) is False


def test_non_interpreter_command_not_confined(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    wt = root / "abc"; wt.mkdir(parents=True)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    assert pr.worktree_confined("gh pr merge 1", str(wt)) is False


def test_missing_or_bad_cwd_not_confined(monkeypatch, tmp_path):
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(tmp_path / ".superheroes-worktrees"))
    assert pr.worktree_confined("python3 -c 'x'", None) is False
    assert pr.worktree_confined("python3 -c 'x'", "") is False


# --- Task 2: Rules store paths + provenance-checked read (FR-6 substrate, UFR-9) ---

import json


def _write_rules(root, cwd, entries, monkeypatch):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    d = os.path.join(root, "projects", "KEY", "permission")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "rules.json"), "w") as f:
        json.dump({"rules": entries}, f)
    return d


def test_store_dir_is_config_keyed(monkeypatch, tmp_path):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    got = pr._store_dir("/some/cwd", root=str(tmp_path))
    assert got == os.path.join(str(tmp_path), "projects", "KEY", "permission")


def test_rules_reads_provenance_valid_only(monkeypatch, tmp_path):
    _write_rules(str(tmp_path), "/cwd", [
        {"family": "test-run", "pattern": "pytest", "provenance": {"source": "configure", "at": "2026-07-05T00:00:00Z"}},
        {"family": "sneaky", "pattern": "gh pr merge", "provenance": None},   # untraceable -> ignored
        {"family": "sneaky2", "pattern": "rm -rf"},                            # no provenance key -> ignored
    ], monkeypatch)
    got = pr.rules("/cwd", root=str(tmp_path))
    fams = [r["family"] for r in got]
    assert fams == ["test-run"]


def test_rules_missing_store_is_empty(monkeypatch, tmp_path):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "NONE")
    assert pr.rules("/cwd", root=str(tmp_path)) == []


def test_rules_corrupt_store_is_empty_not_raise(monkeypatch, tmp_path):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    d = os.path.join(str(tmp_path), "projects", "KEY", "permission"); os.makedirs(d)
    with open(os.path.join(d, "rules.json"), "w") as f:
        f.write("{ this is not json")
    assert pr.rules("/cwd", root=str(tmp_path)) == []   # UFR-2 fail-safe: corrupt -> empty -> prompt


# --- Task 3: freeze_run_rules / frozen_rules / record_composed + lazy reap (FR-8, UFR-9) ---


def test_freeze_snapshots_current_rules(monkeypatch, tmp_path):
    _write_rules(str(tmp_path), "/cwd", [
        {"family": "test-run", "pattern": "pytest", "provenance": {"source": "configure", "at": "2026-07-05T00:00:00Z"}},
    ], monkeypatch)
    pr.freeze_run_rules("RUN1", "/cwd", root=str(tmp_path))
    frozen = pr.frozen_rules("RUN1", "/cwd", root=str(tmp_path))
    assert [r["family"] for r in frozen["rules"]] == ["test-run"]
    assert frozen["composed"] == []


def test_frozen_read_ignores_live_edit(monkeypatch, tmp_path):
    _write_rules(str(tmp_path), "/cwd", [
        {"family": "test-run", "pattern": "pytest", "provenance": {"source": "configure", "at": "2026-07-05T00:00:00Z"}},
    ], monkeypatch)
    pr.freeze_run_rules("RUN2", "/cwd", root=str(tmp_path))
    _write_rules(str(tmp_path), "/cwd", [
        {"family": "test-run", "pattern": "pytest", "provenance": {"source": "configure", "at": "x"}},
        {"family": "broad", "pattern": "gh pr merge", "provenance": {"source": "configure", "at": "y"}},  # mid-run edit
    ], monkeypatch)
    frozen = pr.frozen_rules("RUN2", "/cwd", root=str(tmp_path))
    assert [r["family"] for r in frozen["rules"]] == ["test-run"]   # UFR-9: edit invisible to the run


def test_record_composed_is_exact(monkeypatch, tmp_path):
    _write_rules(str(tmp_path), "/cwd", [], monkeypatch)
    pr.freeze_run_rules("RUN3", "/cwd", root=str(tmp_path))
    pr.record_composed("RUN3", "gh pr create --draft --title X", "/cwd", root=str(tmp_path))
    frozen = pr.frozen_rules("RUN3", "/cwd", root=str(tmp_path))
    assert pr._hash("gh pr create --draft --title X") in frozen["composed"]
    assert pr._hash("gh pr create --draft --title Y") not in frozen["composed"]


def test_reap_deletes_stale_keeps_recent(monkeypatch, tmp_path):
    import time
    _write_rules(str(tmp_path), "/cwd", [], monkeypatch)
    d = os.path.join(str(tmp_path), "projects", "KEY", "permission", "runs")
    os.makedirs(d, exist_ok=True)
    stale = os.path.join(d, "OLD.json"); open(stale, "w").write("{}")
    old = time.time() - 40 * 86400
    os.utime(stale, (old, old))
    monkeypatch.setattr(pr, "_run_is_live", lambda rid, cwd, root: False)  # no live lease
    pr.freeze_run_rules("NEW", "/cwd", root=str(tmp_path))
    assert not os.path.exists(stale)                 # stale + no lease -> reaped
    assert os.path.exists(os.path.join(d, "NEW.json"))


# --- Task 4: evaluate — the pure allowance decision (FR-5/6/8, UFR-1, UFR-2) ---


def test_evaluate_routine_family_allows(monkeypatch, tmp_path):
    _write_rules(str(tmp_path), "/cwd", [
        {"family": "test-run", "pattern": r"\bpytest\b", "provenance": {"source": "configure", "at": "z"}},
    ], monkeypatch)
    pr.freeze_run_rules("R", "/cwd", root=str(tmp_path))
    assert pr.evaluate("python3 -m pytest -q", "/cwd", "R", root=str(tmp_path))[0] == "allow"


def test_evaluate_composed_exact_allows_only_exact(monkeypatch, tmp_path):
    _write_rules(str(tmp_path), "/cwd", [], monkeypatch)
    pr.freeze_run_rules("R", "/cwd", root=str(tmp_path))
    pr.record_composed("R", "gh pr create --draft", "/cwd", root=str(tmp_path))
    assert pr.evaluate("gh pr create --draft", "/cwd", "R", root=str(tmp_path))[0] == "allow"
    assert pr.evaluate("gh pr create --draft ", "/cwd", "R", root=str(tmp_path))[0] == "fall"  # 1-char diff


def test_evaluate_gated_command_never_allowed_even_with_matching_rule(monkeypatch, tmp_path):
    # A malicious/overbroad rule that would match a floor command must NOT allow it (UFR-1).
    _write_rules(str(tmp_path), "/cwd", [
        {"family": "bad", "pattern": r"gh pr merge", "provenance": {"source": "configure", "at": "z"}},
    ], monkeypatch)
    pr.freeze_run_rules("R", "/cwd", root=str(tmp_path))
    assert pr.evaluate("gh pr merge 1", "/cwd", "R", root=str(tmp_path))[0] == "fall"


def test_evaluate_no_match_falls_through(monkeypatch, tmp_path):
    _write_rules(str(tmp_path), "/cwd", [], monkeypatch)
    pr.freeze_run_rules("R", "/cwd", root=str(tmp_path))
    assert pr.evaluate("curl http://evil", "/cwd", "R", root=str(tmp_path))[0] == "fall"


def test_evaluate_any_error_falls_through(monkeypatch, tmp_path):
    monkeypatch.setattr(pr, "frozen_rules", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert pr.evaluate("python3 -m pytest", "/cwd", "R", root=str(tmp_path))[0] == "fall"  # UFR-2


# --- Task 13: configure front door — set_rule / remove_rule provenance-stamped CRUD (FR-9, UFR-9) ---


def test_set_rule_stamps_provenance(monkeypatch, tmp_path):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    pr.set_rule("/cwd", {"family": "test-run", "pattern": r"\bpytest\b"}, root=str(tmp_path))
    got = pr.rules("/cwd", root=str(tmp_path))
    assert got[0]["family"] == "test-run"
    assert got[0]["provenance"]["source"] == "configure"   # front-door stamp -> evaluate honors it


def test_remove_rule(monkeypatch, tmp_path):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    pr.set_rule("/cwd", {"family": "a", "pattern": "x"}, root=str(tmp_path))
    pr.set_rule("/cwd", {"family": "b", "pattern": "y"}, root=str(tmp_path))
    pr.remove_rule("/cwd", "a", root=str(tmp_path))
    assert [r["family"] for r in pr.rules("/cwd", root=str(tmp_path))] == ["b"]


# --- Task 14: seed the initial rules.json families + audit.json from the FR-7 audit (FR-6, FR-7) ---


def test_seed_families_cover_routine_exclude_floor(monkeypatch, tmp_path):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    pr.seed_default_rules("/cwd", root=str(tmp_path))
    fams = {r["family"] for r in pr.rules("/cwd", root=str(tmp_path))}
    assert {"test-run", "validators", "worktree-vcs", "draft-pr"} <= fams
    # the owner-role floor set must NOT be auto-allowed by any seeded rule
    for cmd in ["gh pr merge 1", "gh release create v1", "git push --force",
                "gh workflow run ci.yml", "git push origin main"]:
        pr.freeze_run_rules("R", "/cwd", root=str(tmp_path))
        assert pr.evaluate(cmd, "/cwd", "R", root=str(tmp_path))[0] == "fall"


def test_seed_rules_are_provenance_stamped(monkeypatch, tmp_path):
    # Every seeded rule must carry the configure provenance stamp so `rules()` (which filters
    # on _provenance_ok) surfaces it — an unstamped seed would be invisible to evaluate.
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    pr.seed_default_rules("/cwd", root=str(tmp_path))
    for r in pr.rules("/cwd", root=str(tmp_path)):
        assert r["provenance"]["source"] == "configure"


def test_seed_routine_families_allow_their_commands(monkeypatch, tmp_path):
    # The seeded routine families must actually allow the routine commands they name.
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    pr.seed_default_rules("/cwd", root=str(tmp_path))
    pr.freeze_run_rules("R", "/cwd", root=str(tmp_path))
    for cmd in [
        "python3 -m pytest -q",
        "python3 .github/scripts/validate_marketplace.py",
        "git commit -m 'x'",
        "gh pr create --draft --title X",
        "gh pr ready 12",
    ]:
        assert pr.evaluate(cmd, "/cwd", "R", root=str(tmp_path))[0] == "allow", cmd
    # base-branch change is NOT in the draft-pr family — normal prompt path
    assert pr.evaluate("gh pr edit 12 --base develop", "/cwd", "R", root=str(tmp_path))[0] == "fall"


def test_seed_audit_traces_every_family(monkeypatch, tmp_path):
    # FR-7: an out-of-repo audit.json lists the prompt-provoking commands observed in a run,
    # and every seeded routine family maps to at least one audit entry.
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    pr.seed_default_rules("/cwd", root=str(tmp_path))
    audit = pr.audit("/cwd", root=str(tmp_path))
    assert isinstance(audit, list) and audit
    # each entry names a command + a disposition (a rule/family id or "keep prompting")
    for entry in audit:
        assert entry.get("command")
        assert entry.get("disposition")
    audited_families = {e.get("disposition") for e in audit}
    for fam in ("test-run", "validators", "worktree-vcs", "draft-pr"):
        assert fam in audited_families, fam
