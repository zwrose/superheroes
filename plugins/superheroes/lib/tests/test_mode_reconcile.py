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


def test_coalesce_one_prompt_with_count_and_ack_suppresses(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    # greenfield → one provisional-mode signal
    p = rc.coalesce(str(tmp_path), root=root)
    assert p is not None and p["count"] == 1
    rc.ack_signal(str(tmp_path), p["items"][0]["identity"], root=root)
    assert rc.coalesce(str(tmp_path), root=root) is None  # acked → suppressed until it changes
