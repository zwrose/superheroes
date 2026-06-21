# new file: test_mode_reconcile.py
import json, os, subprocess
import mode_registry as mr
import mode_reconcile as rc


def _init_repo(d):
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)


def test_disagreement_yields_one_signal(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / ".claude").mkdir(); (tmp_path / ".claude" / "review-profile.md").write_text("p")
    g = str(tmp_path / "tp"); entry = os.path.join(g, "entries", "e1"); os.makedirs(entry)
    open(os.path.join(entry, "profile.md"), "w").write("p")
    import store_core as sc
    sc.write_pointer(g, sc.derive_identifiers(str(tmp_path))["gitdir_hash"], "e1")
    monkeypatch.setattr(mr, "_hero_global_root", lambda n: g if n == "test-pilot" else str(tmp_path/"x"))
    sigs = rc.gather_signals(str(tmp_path), root=str(tmp_path / "store"))
    assert len(sigs) == 1 and sigs[0]["type"] == "disagreement"


def test_fr10_disagreement_identity_ignores_none_heroes(tmp_path, monkeypatch):
    # FIX 5 / FR-10: a future hero appearing as "none" must NOT change the disagreement
    # identity (else a dismissed nudge would re-surface). The identity over the 2 present
    # heroes plus a none-hero must equal the identity over just the 2 present heroes.
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    two = {"review-crew": mr.IN_REPO, "test-pilot": mr.GLOBAL}
    three = {"review-crew": mr.IN_REPO, "test-pilot": mr.GLOBAL, "future-hero": "none"}

    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: dict(three))
    sigs_three = rc.gather_signals(str(tmp_path), root=root)
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: dict(two))
    sigs_two = rc.gather_signals(str(tmp_path), root=root)

    dis_three = [s for s in sigs_three if s["type"] == "disagreement"]
    dis_two = [s for s in sigs_two if s["type"] == "disagreement"]
    assert len(dis_three) == 1 and len(dis_two) == 1
    assert dis_three[0]["identity"] == dis_two[0]["identity"]


def test_coalesce_one_prompt_with_count_and_ack_suppresses(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    # greenfield → one provisional-mode signal
    p = rc.coalesce(str(tmp_path), root=root)
    assert p is not None and p["count"] == 1
    assert isinstance(p["message"], str) and p["message"]
    rc.ack_signal(str(tmp_path), p["items"][0]["identity"], root=root)
    assert rc.coalesce(str(tmp_path), root=root) is None  # acked → suppressed until it changes


def test_reconcile_records_chosen_mode_and_disagreement_becomes_migration_pending(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / ".claude").mkdir(); (tmp_path / ".claude" / "review-profile.md").write_text("p")  # review-crew in-repo
    g = str(tmp_path / "tp"); entry = os.path.join(g, "entries", "e1"); os.makedirs(entry)
    open(os.path.join(entry, "profile.md"), "w").write("p")
    import store_core as sc
    sc.write_pointer(g, sc.derive_identifiers(str(tmp_path))["gitdir_hash"], "e1")            # test-pilot global
    monkeypatch.setattr(mr, "_hero_global_root", lambda n: g if n == "test-pilot" else str(tmp_path/"x"))
    root = str(tmp_path / "store")
    out = rc.reconcile(str(tmp_path), chosen_mode=mr.IN_REPO, root=root)
    assert out["action"] == "recorded"
    assert mr.read_registry(str(tmp_path), root=root)["storageMode"] == mr.IN_REPO  # recorded now
    # the out-of-place test-pilot global calibration is untouched → a migration-pending signal remains (move = I6)
    assert any(s["type"] == "migration-pending" for s in rc.gather_signals(str(tmp_path), root=root))


def test_reconcile_backfills_consistent_in_repo_evidence(tmp_path, monkeypatch):
    # FIX test-003: no-chosen-mode BACKFILL branch — consistent in-repo evidence, no registry.
    _init_repo(tmp_path)
    (tmp_path / ".claude").mkdir(); (tmp_path / ".claude" / "review-profile.md").write_text("x")
    root = str(tmp_path / "store")
    monkeypatch.setattr(mr, "_hero_global_root", lambda n: str(tmp_path / ("g_" + n)))
    out = rc.reconcile(str(tmp_path), root=root)
    assert out["action"] == "backfilled"
    assert mr.read_registry(str(tmp_path), root=root)["storageMode"] == mr.IN_REPO


def test_reconcile_noop_when_consistent(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.GLOBAL, None, root=root)
    assert rc.reconcile(str(tmp_path), root=root)["action"] == "noop"


def test_cli_resolve_emits_json(tmp_path, capsys):
    _init_repo(tmp_path)
    rc.main(["resolve", "--cwd", str(tmp_path), "--root", str(tmp_path / "store")])
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == mr.GLOBAL and out["source"] == "provisional"
