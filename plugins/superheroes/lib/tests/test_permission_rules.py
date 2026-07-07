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


def test_reap_keeps_stale_but_live(monkeypatch, tmp_path):
    # The third reap arm (uncovered before): a stale-mtime run file whose lease IS live must be KEPT
    # (permission_rules._reap_stale's `if _run_is_live(...): continue` guard). A mutation dropping that
    # guard would reap a live run's frozen snapshot — this pins the fail-safe keep-on-live branch.
    import time
    _write_rules(str(tmp_path), "/cwd", [], monkeypatch)
    d = os.path.join(str(tmp_path), "projects", "KEY", "permission", "runs")
    os.makedirs(d, exist_ok=True)
    stale_live = os.path.join(d, "LIVE.json"); open(stale_live, "w").write("{}")
    old = time.time() - 40 * 86400
    os.utime(stale_live, (old, old))
    monkeypatch.setattr(pr, "_run_is_live", lambda rid, cwd, root: True)  # a live lease
    pr.freeze_run_rules("NEW", "/cwd", root=str(tmp_path))
    assert os.path.exists(stale_live)                # stale-mtime BUT live -> kept (the guard branch)
    assert os.path.exists(os.path.join(d, "NEW.json"))


def test_reap_namespaced_stem_keys_liveness_on_generation(monkeypatch, tmp_path):
    # test-002: the PRODUCTION run-file shape is "<work-item>--<generation>.json" (_run_path writes
    # it whenever a work_item is threaded — the enforcer/showrunner path). _reap_stale must key
    # liveness on the stem TAIL past the last "--" (the generation), not the whole stem or the
    # work-item. Pins `rid = name[:-len('.json')].rsplit('--', 1)[-1]`.
    import time
    _write_rules(str(tmp_path), "/cwd", [], monkeypatch)
    d = os.path.join(str(tmp_path), "projects", "KEY", "permission", "runs")
    os.makedirs(d, exist_ok=True)
    old = time.time() - 40 * 86400

    # (a) a namespaced live run file -> kept, and _run_is_live consulted with generation '7'
    kept = os.path.join(d, "wi-a--7.json"); open(kept, "w").write("{}")
    os.utime(kept, (old, old))
    seen = []
    def _live_capture(rid, cwd, root):
        seen.append(rid)
        return True
    monkeypatch.setattr(pr, "_run_is_live", _live_capture)
    pr.freeze_run_rules("NEW", "/cwd", root=str(tmp_path))
    assert "7" in seen, "liveness keyed on the generation (stem tail), not 'wi-a--7' or 'wi-a'"
    assert os.path.exists(kept), "a stale-mtime BUT live namespaced run file is kept"

    # (b) the same namespaced file is REAPED when its lease is not live
    reaped = os.path.join(d, "wi-b--3.json"); open(reaped, "w").write("{}")
    os.utime(reaped, (old, old))
    monkeypatch.setattr(pr, "_run_is_live", lambda rid, cwd, root: False)
    pr.freeze_run_rules("NEW2", "/cwd", root=str(tmp_path))
    assert not os.path.exists(reaped), "a stale + not-live namespaced run file is reaped"


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


def test_evaluate_inert_without_active_run(monkeypatch, tmp_path):
    # FR-3: with NO active run (run_id falsy), evaluate is fully inert — prompting is
    # UNCHANGED. Build a command that WOULD be allowed by EVERY arm (a worktree-confined
    # interpreter cwd, a matching frozen routine rule, AND a byte-exact composed entry), then
    # assert run_id=None still falls through to the prompt.
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    wt_root = tmp_path / ".superheroes-worktrees"
    wt = wt_root / "abc"; wt.mkdir(parents=True)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(wt_root))
    _write_rules(str(tmp_path), "/cwd", [
        {"family": "test-run", "pattern": r"\bpytest\b", "provenance": {"source": "configure", "at": "z"}},
    ], monkeypatch)
    cmd = "python3 -m pytest -q"
    pr.freeze_run_rules("R", "/cwd", root=str(tmp_path))
    pr.record_composed("R", cmd, "/cwd", root=str(tmp_path))
    # sanity: WITH an active run + managed-worktree cwd, every arm would allow this command
    assert pr.evaluate(cmd, str(wt), "R", root=str(tmp_path))[0] == "allow"
    # FR-3: run_id=None -> inert -> fall, even though every arm would otherwise allow
    assert pr.evaluate(cmd, str(wt), None, root=str(tmp_path))[0] == "fall"


def test_evaluate_worktree_vcs_falls_from_repo_root_cwd(monkeypatch, tmp_path):
    # FR-6: a worktree-vcs-family command run from a NON-worktree cwd (a repo root) earns
    # nothing — the family is now cwd-confined to a real managed build worktree.
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    wt_root = tmp_path / ".superheroes-worktrees"; wt_root.mkdir(parents=True)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(wt_root))
    repo_root = tmp_path / "repo"; repo_root.mkdir()
    pr.seed_default_rules("/cwd", root=str(tmp_path))
    pr.freeze_run_rules("R", "/cwd", root=str(tmp_path))
    assert pr.evaluate("git commit -m 'x'", str(repo_root), "R", root=str(tmp_path))[0] == "fall"


def test_evaluate_worktree_vcs_falls_from_pathtrick_cwd(monkeypatch, tmp_path):
    # FR-6/UFR-5: the same path-tricks the interpreter arm rejects apply to worktree-vcs — a
    # name-prefix lookalike sibling of the worktrees root is NOT a descendant, and a `..`
    # parent-hop that resolves out of the root earns nothing.
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    wt_root = tmp_path / ".superheroes-worktrees"; wt_root.mkdir(parents=True)
    outside = tmp_path / "evil"; outside.mkdir()
    link = wt_root.parent / ".superheroes-worktrees-evil"   # lookalike, not a descendant
    link.symlink_to(outside)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(wt_root))
    pr.seed_default_rules("/cwd", root=str(tmp_path))
    pr.freeze_run_rules("R", "/cwd", root=str(tmp_path))
    assert pr.evaluate("git commit -m 'x'", str(link), "R", root=str(tmp_path))[0] == "fall"
    escaped = os.path.join(str(wt_root), "wt", "..", "..")   # parent-hop OUT of the root
    assert pr.evaluate("git status", escaped, "R", root=str(tmp_path))[0] == "fall"


def test_evaluate_worktree_vcs_allows_from_genuine_managed_worktree(monkeypatch, tmp_path):
    # FR-6 (existing behavior preserved): a genuine managed-worktree cwd + frozen rules + a
    # live run -> allow.
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    wt_root = tmp_path / ".superheroes-worktrees"
    wt = wt_root / "abc123"; wt.mkdir(parents=True)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(wt_root))
    pr.seed_default_rules("/cwd", root=str(tmp_path))
    pr.freeze_run_rules("R", "/cwd", root=str(tmp_path))
    assert pr.evaluate("git commit -m 'x'", str(wt), "R", root=str(tmp_path))[0] == "allow"


def test_no_pending_request_state_is_ever_persisted(monkeypatch, tmp_path):
    # Pins UFR-7 (an interruption mid-permission-wait resolves to DENIAL on resume, never
    # allowance or more waiting) and UFR-4 (a late owner response is NOT applied
    # retroactively). Both hold ONLY because the layer is STATELESS-BY-DESIGN: it persists no
    # pending/waiting request record. An interrupted ask therefore leaves NOTHING to resume,
    # and a late response has NOTHING to attach to. This walks the entire store the full
    # lifecycle wrote and asserts no such pending-request structure exists anywhere.
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    store = tmp_path / "store"
    # Full store lifecycle: CRUD, seed, freeze, compose, and both evaluate verdicts.
    pr.set_rule("/cwd", {"family": "test-run", "pattern": r"\bpytest\b"}, root=str(store))
    pr.seed_default_rules("/cwd", root=str(store))                 # writes rules.json + audit.json
    pr.freeze_run_rules("R", "/cwd", root=str(store))             # writes runs/R.json
    pr.record_composed("R", "gh pr create --draft", "/cwd", root=str(store))
    assert pr.evaluate("python3 -m pytest -q", "/cwd", "R", root=str(store))[0] == "allow"  # allow path
    assert pr.evaluate("curl http://evil", "/cwd", "R", root=str(store))[0] == "fall"        # fall path
    perm = os.path.join(str(store), "projects", "KEY", "permission")
    # (1) EXACT file inventory — no stray pending/queue/request file was written.
    inventory = set()
    for dirpath, _dirs, files in os.walk(perm):
        for f in files:
            inventory.add(os.path.relpath(os.path.join(dirpath, f), perm))
    assert inventory == {"rules.json", "audit.json", os.path.join("runs", "R.json")}, inventory
    # (2) No file's bytes carry any pending/waiting/queued request vocabulary.
    banned = ("pending", "waiting", "queued", "await", "resume")
    for rel in inventory:
        text = open(os.path.join(perm, rel)).read().lower()
        for token in banned:
            assert token not in text, "%s leaked pending-request state: %r" % (rel, token)
    # (3) The run snapshot carries ONLY the expected keys — no request/denial/pending field.
    with open(os.path.join(perm, "runs", "R.json")) as f:
        snap = json.load(f)
    assert set(snap.keys()) == {"rules", "composed"}, snap.keys()


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
    # The worktree-vcs family is now cwd-confined (FR-6), so a VCS command only allows from a
    # real managed build worktree. Point _worktrees_root at a managed root and run the git
    # command from a worktree under it; the non-VCS families are cwd-agnostic ("/cwd" is fine).
    wt_root = tmp_path / ".superheroes-worktrees"
    wt = wt_root / "abc123"; wt.mkdir(parents=True)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(wt_root))
    pr.seed_default_rules("/cwd", root=str(tmp_path))
    pr.freeze_run_rules("R", "/cwd", root=str(tmp_path))
    for cmd, cwd in [
        ("python3 -m pytest -q", "/cwd"),
        ("python3 .github/scripts/validate_marketplace.py", "/cwd"),
        ("git commit -m 'x'", str(wt)),                       # worktree-vcs: managed-worktree cwd
        ("gh pr create --draft --title X", "/cwd"),
        ("gh pr ready 12", "/cwd"),
    ]:
        assert pr.evaluate(cmd, cwd, "R", root=str(tmp_path))[0] == "allow", cmd
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
