# new file: test_mode_registry.py
import json, os, subprocess
import pytest
import mode_registry as mr


def _write_raw(cwd, root, obj):
    d = mr.ensure_project_store(cwd, root=root)
    mr_store_core = __import__("store_core")
    mr_store_core.atomic_write(os.path.join(d, "registry.json"), json.dumps(obj))


def _init_repo(d, remote=None):
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)
    if remote:
        subprocess.run(["git", "-C", str(d), "remote", "add", "origin", remote], check=True)


def test_config_key_prefers_remote_and_is_16hex(tmp_path):
    _init_repo(tmp_path, "git@github.com:org/repo.git")
    k = mr.config_key(str(tmp_path))
    assert len(k) == 16 and all(c in "0123456789abcdef" for c in k)


def test_config_key_falls_back_to_common_dir_when_no_remote(tmp_path):
    _init_repo(tmp_path)
    import store_core as sc
    assert mr.config_key(str(tmp_path)) == sc.derive_identifiers(str(tmp_path))["gitdir_hash"]


def test_ensure_project_store_creates_git_and_meta(tmp_path):
    _init_repo(tmp_path)
    d = mr.ensure_project_store(str(tmp_path), root=str(tmp_path / "store"))
    assert d is not None
    assert os.path.isdir(os.path.join(d, ".git"))
    assert json.load(open(os.path.join(d, "meta.json")))["schemaVersion"] == mr.SCHEMA_VERSION


def test_ensure_project_store_is_idempotent(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    a = mr.ensure_project_store(str(tmp_path), root=root)
    b = mr.ensure_project_store(str(tmp_path), root=root)
    assert a == b  # same dir, no error on second touch


def test_config_lock_is_nonblocking_and_exclusive(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.ensure_project_store(str(tmp_path), root=root)
    with mr.config_lock(str(tmp_path), root=root) as got1:
        assert got1 is True
        with mr.config_lock(str(tmp_path), root=root) as got2:
            assert got2 is False        # held by the outer context — never blocks
    with mr.config_lock(str(tmp_path), root=root) as got3:
        assert got3 is True             # released after the outer context closed


def test_write_then_read_roundtrips(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    rec = mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root, now="2026-06-21T00:00:00Z")
    assert rec["storageMode"] == mr.IN_REPO and rec["schemaVersion"] == 1
    assert mr.read_registry(str(tmp_path), root=root)["storageMode"] == mr.IN_REPO


def test_read_unknown_newer_version_fails_closed(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    _write_raw(str(tmp_path), root, {"schemaVersion": 999, "storageMode": "in-repo"})
    with pytest.raises(mr.UnknownSchemaVersion):
        mr.read_registry(str(tmp_path), root=root)


def test_read_semantically_invalid_is_treated_as_absent(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    _write_raw(str(tmp_path), root, {"schemaVersion": 1, "storageMode": "bogus"})
    assert mr.read_registry(str(tmp_path), root=root) is None


def test_read_float_schema_version_is_corrupt_not_accepted(tmp_path):
    # FIX 1: a non-int schemaVersion (float 2.0) must NOT bypass the fail-closed guard;
    # it is a corrupt record → absent (None), neither raised nor accepted.
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    _write_raw(str(tmp_path), root, {"schemaVersion": 2.0, "storageMode": "in-repo",
                                     "remoteKey": None, "createdAt": "2026-06-21T00:00:00Z"})
    assert mr.read_registry(str(tmp_path), root=root) is None


def test_read_string_schema_version_is_corrupt_not_accepted(tmp_path):
    # FIX 1: a string schemaVersion ("2") is corrupt → absent.
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    _write_raw(str(tmp_path), root, {"schemaVersion": "2", "storageMode": "in-repo",
                                     "remoteKey": None, "createdAt": "2026-06-21T00:00:00Z"})
    assert mr.read_registry(str(tmp_path), root=root) is None


def test_read_bool_schema_version_is_corrupt_not_accepted(tmp_path):
    # FIX test-002: a bool schemaVersion (True) must NOT be accepted as schemaVersion 1 —
    # pins the isinstance(ver, bool) guard in read_registry.
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    _write_raw(str(tmp_path), root, {"schemaVersion": True, "storageMode": "in-repo",
                                     "remoteKey": None, "createdAt": "2026-06-21T00:00:00Z"})
    assert mr.read_registry(str(tmp_path), root=root) is None


def test_read_missing_schema_version_is_corrupt_not_accepted(tmp_path):
    # FIX 1: an absent schemaVersion (storageMode otherwise valid) is corrupt → absent.
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    _write_raw(str(tmp_path), root, {"storageMode": "in-repo",
                                     "remoteKey": None, "createdAt": "2026-06-21T00:00:00Z"})
    assert mr.read_registry(str(tmp_path), root=root) is None


def test_read_non_string_remote_key_is_corrupt(tmp_path):
    # FIX 2: a v1 record with a non-string remoteKey (42) is malformed → absent.
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    _write_raw(str(tmp_path), root, {"schemaVersion": 1, "storageMode": "in-repo",
                                     "remoteKey": 42, "createdAt": "2026-06-21T00:00:00Z"})
    assert mr.read_registry(str(tmp_path), root=root) is None


def test_read_empty_or_missing_created_at_is_corrupt(tmp_path):
    # FIX 2: an empty createdAt (and a missing one) is malformed → absent.
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    _write_raw(str(tmp_path), root, {"schemaVersion": 1, "storageMode": "in-repo",
                                     "remoteKey": "rk", "createdAt": ""})
    assert mr.read_registry(str(tmp_path), root=root) is None
    _write_raw(str(tmp_path), root, {"schemaVersion": 1, "storageMode": "in-repo",
                                     "remoteKey": "rk"})  # createdAt missing entirely
    assert mr.read_registry(str(tmp_path), root=root) is None


def test_write_refuses_to_change_sticky_mode(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.GLOBAL, None, root=root)
    assert mr.write_registry(str(tmp_path), mr.IN_REPO, None, root=root) is None   # refused
    assert mr.read_registry(str(tmp_path), root=root)["storageMode"] == mr.GLOBAL  # preserved
    # explicit migration is allowed
    assert mr.write_registry(str(tmp_path), mr.IN_REPO, None, root=root, allow_migration=True)["storageMode"] == mr.IN_REPO


def test_evidence_in_repo_anchored_at_repo_root(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "review-profile.md").write_text("x")
    locs = mr.hero_evidence(str(tmp_path), hero_roots={"review-crew": str(tmp_path/"g1"),
                                                       "test-pilot": str(tmp_path/"g2")})
    assert locs["review-crew"] == mr.IN_REPO and locs["test-pilot"] == "none"


def test_verdict_present_only_and_disagree_needs_two():
    assert mr.evidence_verdict({"review-crew": mr.IN_REPO, "test-pilot": "none"}) == mr.IN_REPO
    assert mr.evidence_verdict({"review-crew": "none", "test-pilot": "none"}) == "none"
    assert mr.evidence_verdict({"review-crew": mr.IN_REPO, "test-pilot": mr.GLOBAL}) == "disagree"


def test_evidence_global_via_pointer_is_read_only(tmp_path):
    import store_core as sc
    _init_repo(tmp_path)
    g = str(tmp_path / "review-crew-global")
    entry = os.path.join(g, "entries", "e1"); os.makedirs(entry)
    open(os.path.join(entry, "review-profile.md"), "w").write("p")
    sc.write_pointer(g, sc.derive_identifiers(str(tmp_path))["gitdir_hash"], "e1")
    locs = mr.hero_evidence(str(tmp_path), hero_roots={"review-crew": g, "test-pilot": str(tmp_path/"g2")})
    assert locs["review-crew"] == mr.GLOBAL
    assert not os.path.exists(os.path.join(entry, "keys.json"))  # probe healed nothing


def test_resolve_registry_present_is_authoritative(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.GLOBAL, None, root=root)
    r = mr.resolve(str(tmp_path), root=root)
    assert r["mode"] == mr.GLOBAL and r["authoritative"] is True and r["source"] == "registry"


def test_resolve_greenfield_is_provisional_global_without_writing(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    r = mr.resolve(str(tmp_path), root=root)
    assert r["mode"] == mr.GLOBAL and r["authoritative"] is False and r["source"] == "provisional"
    assert mr.read_registry(str(tmp_path), root=root) is None  # pure read wrote nothing


def test_resolve_backfills_from_consistent_evidence(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / ".claude").mkdir(); (tmp_path / ".claude" / "review-profile.md").write_text("x")
    root = str(tmp_path / "store")
    monkeypatch.setattr(mr, "_hero_global_root", lambda n: str(tmp_path / ("g_" + n)))
    r = mr.resolve(str(tmp_path), root=root)
    assert r["mode"] == mr.IN_REPO and r["authoritative"] is True and r["source"] == "backfilled"
    assert mr.read_registry(str(tmp_path), root=root)["storageMode"] == mr.IN_REPO  # synthesized


def test_resolve_backfill_on_wedged_store_reports_non_authoritative(tmp_path, monkeypatch):
    # FIX 3: consistent in-repo evidence but a wedged store (write cannot land) must report
    # authoritative=False, not masquerade as authoritative. The resolved mode + source stay.
    _init_repo(tmp_path)
    (tmp_path / ".claude").mkdir(); (tmp_path / ".claude" / "review-profile.md").write_text("x")
    root = str(tmp_path / "store")
    monkeypatch.setattr(mr, "_hero_global_root", lambda n: str(tmp_path / ("g_" + n)))
    monkeypatch.setattr(mr, "ensure_project_store", lambda *a, **k: None)  # write_registry → None
    r = mr.resolve(str(tmp_path), root=root)
    assert r["authoritative"] is False
    assert r["mode"] == mr.IN_REPO
    assert r["source"] == "backfilled"


def test_resolve_artifact_reads_follow_the_artifact(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, None, root=root)  # recorded mode = in-repo
    only_global = tmp_path / "g.txt"; only_global.write_text("here")
    in_repo = tmp_path / "i.txt"  # does not exist
    assert mr.resolve_artifact(str(tmp_path), str(in_repo), str(only_global), root=root) == str(only_global)
    # a NEW artifact (neither exists) follows the recorded mode (in-repo)
    new_in = tmp_path / "new_i.txt"; new_g = tmp_path / "new_g.txt"
    assert mr.resolve_artifact(str(tmp_path), str(new_in), str(new_g), root=root) == str(new_in)


def test_ufr7_interrupted_write_leaves_record_absent_not_torn(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.ensure_project_store(str(tmp_path), root=root)
    import store_core as sc
    def boom(path, text, **kw):
        raise OSError("simulated mid-write abort")
    monkeypatch.setattr(sc, "atomic_write", boom)
    try:
        mr.write_registry(str(tmp_path), mr.IN_REPO, None, root=root)
    except OSError:
        pass
    assert not os.path.exists(mr.registry_path(str(tmp_path), root))  # absent, never half-written


def test_ufr3_corrupt_registry_repaired_from_consistent_evidence(tmp_path, monkeypatch):
    # UFR-3 repair clause composed end-to-end: a corrupt on-disk record + consistent evidence
    # → the resolver treats the record as absent and repairs it from the evidence.
    _init_repo(tmp_path)
    (tmp_path / ".claude").mkdir(); (tmp_path / ".claude" / "review-profile.md").write_text("x")  # consistent in-repo evidence
    monkeypatch.setattr(mr, "_hero_global_root", lambda n: str(tmp_path / ("g_" + n)))
    root = str(tmp_path / "store")
    d = mr.ensure_project_store(str(tmp_path), root=root)
    import store_core as sc
    sc.atomic_write(os.path.join(d, "registry.json"),
                    json.dumps({"schemaVersion": 1, "storageMode": "bogus"}))  # parseable but invalid → corrupt
    r = mr.resolve(str(tmp_path), root=root)
    assert r["mode"] == mr.IN_REPO and r["source"] == "backfilled"            # repaired, not trusted
    assert mr.read_registry(str(tmp_path), root=root)["storageMode"] == mr.IN_REPO


def test_ufr8_chosen_but_unrecorded_reasks_and_keeps_calibration(tmp_path, monkeypatch):
    import mode_reconcile as rc
    import store_core as sc
    _init_repo(tmp_path)
    (tmp_path / ".claude").mkdir(); (tmp_path / ".claude" / "review-profile.md").write_text("keep")  # review-crew in-repo
    g = str(tmp_path / "tp"); entry = os.path.join(g, "entries", "e1"); os.makedirs(entry)
    open(os.path.join(entry, "profile.md"), "w").write("tpkeep")
    sc.write_pointer(g, sc.derive_identifiers(str(tmp_path))["gitdir_hash"], "e1")  # test-pilot global → genuinely ambiguous
    monkeypatch.setattr(mr, "_hero_global_root", lambda n: g if n == "test-pilot" else str(tmp_path / "x"))
    root = str(tmp_path / "store")
    monkeypatch.setattr(mr, "write_registry", lambda *a, **k: None)  # the owner's choice never lands durably
    out = rc.reconcile(str(tmp_path), chosen_mode=mr.IN_REPO, root=root)
    assert out["action"] == "deferred"
    assert out["written"] is False
    assert mr.read_registry(str(tmp_path), root=root) is None                  # no unrecorded mode acted on
    assert (tmp_path / ".claude" / "review-profile.md").read_text() == "keep"   # calibration intact
    assert open(os.path.join(entry, "profile.md")).read() == "tpkeep"           # other calibration intact
    # the choice was not recorded → the owner is asked again (the disagreement still surfaces)
    assert any(s["type"] == "disagreement" for s in rc.gather_signals(str(tmp_path), root=root))


def test_nf6_second_writer_skips_and_one_valid_record_lands(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.ensure_project_store(str(tmp_path), root=root)
    with mr.config_lock(str(tmp_path), root=root) as got:
        assert got is True
        assert mr.write_registry(str(tmp_path), mr.GLOBAL, None, root=root) is None  # contended → skip, no block
    assert mr.read_registry(str(tmp_path), root=root) is None         # the skipped write left no torn/partial record
    rec = mr.write_registry(str(tmp_path), mr.GLOBAL, None, root=root)  # lock free now → the write lands
    assert rec["storageMode"] == mr.GLOBAL                             # exactly one valid record (UFR-6 positive clause)
    assert mr.read_registry(str(tmp_path), root=root)["storageMode"] == mr.GLOBAL


def test_nf6_concurrent_store_creation_converges(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    a = mr.ensure_project_store(str(tmp_path), root=root)
    b = mr.ensure_project_store(str(tmp_path), root=root)  # second "worktree" first-touch
    assert a == b and os.path.isdir(os.path.join(a, ".git"))


def test_nf6_holder_death_releases_lock_and_next_resolve_backfills(tmp_path, monkeypatch):
    # The flock-over-file_lock win (UFR-7 "the next resolution finishes the work"): a holder
    # that DIES leaves no stuck lock — the OS releases it — so the next resolve backfills.
    import sys, time
    _init_repo(tmp_path)
    (tmp_path / ".claude").mkdir(); (tmp_path / ".claude" / "review-profile.md").write_text("x")  # consistent in-repo evidence
    monkeypatch.setattr(mr, "_hero_global_root", lambda n: str(tmp_path / ("g_" + n)))
    root = str(tmp_path / "store")
    mr.ensure_project_store(str(tmp_path), root=root)
    lock = os.path.join(mr.project_store_dir(str(tmp_path), root), "config.lock")
    held = lock + ".held"
    child = subprocess.Popen([sys.executable, "-c",
        "import fcntl,os,time;"
        f"fd=os.open({lock!r},os.O_CREAT|os.O_RDWR,0o644);fcntl.flock(fd,fcntl.LOCK_EX);"
        f"open({held!r},'w').close();time.sleep(30)"])
    try:
        deadline = time.time() + 30
        while not os.path.exists(held) and time.time() < deadline:
            exit_code = child.poll()
            if exit_code is not None:  # child exited before signaling → fail fast, not a hang
                raise AssertionError(
                    f"child exited (returncode={exit_code}) before signaling flock acquisition "
                    f"(pid={child.pid})")
            time.sleep(0.02)
        assert os.path.exists(held), f"child did not signal flock acquisition within deadline (pid={child.pid})"
        with mr.config_lock(str(tmp_path), root=root) as got:
            assert got is False, "config_lock should report contended while the live child holds the flock"
    finally:
        child.kill(); child.wait()             # holder DIES → OS releases the flock
    # the dead holder left no stuck lock (unlike file_lock's TTL): the next resolve acquires
    # the freed flock and backfills — the recovery file_lock could not give until its TTL.
    r = mr.resolve(str(tmp_path), root=root)
    assert r["mode"] == mr.IN_REPO and r["authoritative"] is True
    assert mr.read_registry(str(tmp_path), root=root)["storageMode"] == mr.IN_REPO


def test_nf1_config_key_deterministic_golden_for_remote(tmp_path):
    # NF1: a pinned golden literal (not re-derived through the funcs under test) catches
    # any determinism/truncation drift in the remote-keyed config key.
    _init_repo(tmp_path); subprocess.run(["git", "-C", str(tmp_path), "remote", "add",
                                          "origin", "git@github.com:o/r.git"], check=True)
    assert mr.config_key(str(tmp_path)) == "6d5c8a7b6c8ca477"


def test_evidence_agrees_with_hero_resolve_for_repo_root_cwd(tmp_path, monkeypatch):
    # Scope is deliberately a repo-root cwd: the probe anchors in-repo at the repo root while
    # review_store anchors at cwd, so they intentionally diverge for a sub-dir cwd (the probe is
    # the more-correct anchor; I2 aligns the heroes onto it — see plan "reads-follow-the-artifact").
    import review_store, store as tp
    _init_repo(tmp_path)
    rc_root = str(tmp_path / "rc"); tp_root = str(tmp_path / "tp")
    # review-crew in-repo; test-pilot global
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "review-profile.md").write_text("p")
    open(tp.create(str(tmp_path), "global", tp_root)["profile"], "w").write("p")  # seed test-pilot global profile
    monkeypatch.setattr(review_store, "store_root", lambda: rc_root)
    monkeypatch.setattr(tp, "store_root", lambda: tp_root)
    locs = mr.hero_evidence(str(tmp_path))
    assert locs["review-crew"] == review_store.resolve(str(tmp_path), "profile", rc_root)["location"]
    assert locs["test-pilot"] == tp.resolve(str(tmp_path), tp_root)["location"]


def test_decide_mode_env_wins_without_touching_registry(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    assert mr.decide_mode(str(tmp_path), mr.IN_REPO, True, root=root) == mr.IN_REPO
    assert mr.decide_mode(str(tmp_path), mr.GLOBAL, False, root=root) == mr.GLOBAL
    assert mr.decide_mode(str(tmp_path), "bogus", True, root=root) == "ask"  # invalid env falls through
    assert mr.read_registry(str(tmp_path), root=root) is None  # env path records nothing


def test_decide_mode_recorded_mode_is_returned_not_asked(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, None, root=root)
    # FR-4 / the #35 fix: a recorded mode is returned even when interactive — never "ask".
    assert mr.decide_mode(str(tmp_path), None, True, root=root) == mr.IN_REPO


def test_decide_mode_backfilled_mode_is_returned(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "review-profile.md").write_text("x")
    monkeypatch.setattr(mr, "_hero_global_root", lambda n: str(tmp_path / ("g_" + n)))
    root = str(tmp_path / "store")
    assert mr.decide_mode(str(tmp_path), None, True, root=root) == mr.IN_REPO  # FR-6 (in-repo side)


def test_decide_mode_backfills_global_evidence(tmp_path, monkeypatch):
    # The plan's named "in-repo THEN global" regression: consistent GLOBAL evidence backfills
    # global — kills a mutant that hardcodes IN_REPO on the backfill branch (FR-6, global side).
    import store_core as sc
    _init_repo(tmp_path)
    g = str(tmp_path / "g_review-crew")
    entry = os.path.join(g, "entries", "e1"); os.makedirs(entry)
    open(os.path.join(entry, "review-profile.md"), "w").write("p")
    sc.write_pointer(g, sc.derive_identifiers(str(tmp_path))["gitdir_hash"], "e1")
    monkeypatch.setattr(mr, "_hero_global_root",
                        lambda n: g if n == "review-crew" else str(tmp_path / ("x_" + n)))
    root = str(tmp_path / "store")
    assert mr.decide_mode(str(tmp_path), None, True, root=root) == mr.GLOBAL


def test_decide_mode_greenfield_interactive_asks(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    assert mr.decide_mode(str(tmp_path), None, True, root=root) == "ask"


def test_decide_mode_greenfield_headless_is_provisional_global_unrecorded(tmp_path):
    # UFR-5: headless greenfield → provisional global, never frozen as authoritative.
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    assert mr.decide_mode(str(tmp_path), None, False, root=root) == mr.GLOBAL
    assert mr.read_registry(str(tmp_path), root=root) is None  # not recorded


def test_decide_mode_propagates_unknown_schema_version(tmp_path):
    # UFR-2: a newer registry fails closed THROUGH decide_mode — not swallowed.
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    _write_raw(str(tmp_path), root, {"schemaVersion": 999, "storageMode": "in-repo"})
    with pytest.raises(mr.UnknownSchemaVersion):
        mr.decide_mode(str(tmp_path), None, True, root=root)


def test_config_lock_at_keys_on_an_arbitrary_store_dir(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    import store_core as sc
    gh = sc.derive_identifiers(str(tmp_path))["gitdir_hash"]
    common_dir = os.path.join(root, "projects", gh)
    with mr.config_lock_at(common_dir) as got1:
        assert got1 is True
        with mr.config_lock_at(common_dir) as got2:
            assert got2 is False     # same dir -> mutually exclusive, non-blocking
    with mr.config_lock_at(common_dir) as got3:
        assert got3 is True          # released after the context closed


def _seed_hero_in_repo(repo):
    p = os.path.join(str(repo), ".claude", "review-profile.md")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write("profile\n")


def _pin_hero_globals(monkeypatch, tmp_path):
    monkeypatch.setattr(mr, "_hero_global_root", lambda name: str(tmp_path / "heroglobal"))


def test_resolve_defers_backfill_write_while_rebind_marker_present(tmp_path, monkeypatch):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    _pin_hero_globals(monkeypatch, tmp_path)
    _seed_hero_in_repo(tmp_path)
    import store_core as sc
    gh = sc.derive_identifiers(str(tmp_path))["gitdir_hash"]
    cdir = os.path.join(root, "projects", gh); os.makedirs(cdir, exist_ok=True)
    sc.atomic_write(os.path.join(cdir, "migration-journal.json"),
                    json.dumps({"kind": "rebind", "phase": "copying"}))
    r = mr.resolve(str(tmp_path), root=root)
    assert r["authoritative"] is False
    rk = sc.derive_identifiers(str(tmp_path))["remote_hash"]
    assert not os.path.isfile(os.path.join(root, "projects", rk, "registry.json"))


def test_resolve_backfills_when_no_rebind_marker(tmp_path, monkeypatch):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    _pin_hero_globals(monkeypatch, tmp_path)
    _seed_hero_in_repo(tmp_path)
    r = mr.resolve(str(tmp_path), root=root)
    assert r["source"] == "backfilled" and r["authoritative"] is True


def test_resolve_artifact_prefers_recorded_mode_when_both_exist(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.GLOBAL, "rk", root=root)
    in_repo = tmp_path / "in.txt"; in_repo.write_text("old")
    glob = tmp_path / "g.txt"; glob.write_text("new")
    assert mr.resolve_artifact(str(tmp_path), str(in_repo), str(glob), root=root) == str(glob)
