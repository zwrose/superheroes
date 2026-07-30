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
    # exactly one storage-mode disagreement signal (the seeded stub review-profile.md also
    # surfaces a legacy-profile-unsupported signal — assert on the disagreement specifically).
    disagreements = [s for s in sigs if s["type"] == "disagreement"]
    assert len(disagreements) == 1


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


def test_reconcile_backfill_deferred_when_write_skipped(tmp_path, monkeypatch):
    # FIX r2-test-deferred: no-chosen-mode BACKFILL-DEFERRED branch (write skipped).
    # Consistent in-repo evidence, no registry, but write_registry returns None (contended/wedged).
    _init_repo(tmp_path)
    (tmp_path / ".claude").mkdir(); (tmp_path / ".claude" / "review-profile.md").write_text("x")
    root = str(tmp_path / "store")
    monkeypatch.setattr(mr, "_hero_global_root", lambda n: str(tmp_path / ("g_" + n)))
    monkeypatch.setattr(mr, "write_registry", lambda *a, **k: None)
    out = rc.reconcile(str(tmp_path), root=root)
    assert out["action"] == "deferred"
    assert out["written"] is False


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


# append to test_mode_reconcile.py — load architect_config + stub read_policy
def test_provisional_policy_emits_signal(tmp_path, monkeypatch):
    import mode_reconcile, mode_registry, architect_config
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo",
                                                "schemaVersion": 1, "remoteKey": None,
                                                "createdAt": "t"})
    monkeypatch.setattr(mode_registry, "hero_evidence", lambda cwd, root=None: {})
    monkeypatch.setattr(architect_config, "read_policy",
                        lambda cwd, root=None: {"location": "docs/superheroes",
                                                "visibility": "committed", "confirmed": False})
    sigs = mode_reconcile.gather_signals(str(tmp_path), root=str(tmp_path / "s"))
    assert any(s["type"] == "doc-policy-provisional" for s in sigs)


def test_confirmed_policy_emits_no_signal(tmp_path, monkeypatch):
    import mode_reconcile, mode_registry, architect_config
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo",
                                                "schemaVersion": 1, "remoteKey": None,
                                                "createdAt": "t"})
    monkeypatch.setattr(mode_registry, "hero_evidence", lambda cwd, root=None: {})
    monkeypatch.setattr(architect_config, "read_policy",
                        lambda cwd, root=None: {"location": "docs/superheroes",
                                                "visibility": "committed", "confirmed": True})
    sigs = mode_reconcile.gather_signals(str(tmp_path), root=str(tmp_path / "s"))
    assert not any(s["type"] == "doc-policy-provisional" for s in sigs)


def test_provisional_identity_is_stable(tmp_path, monkeypatch):
    # Deterministic identity → a dismissed nudge stays dismissed across calls.
    import mode_reconcile, mode_registry, architect_config
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo", "schemaVersion": 1,
                                                "remoteKey": None, "createdAt": "t"})
    monkeypatch.setattr(mode_registry, "hero_evidence", lambda cwd, root=None: {})
    monkeypatch.setattr(architect_config, "read_policy",
                        lambda cwd, root=None: {"location": "docs/superheroes",
                                                "visibility": "committed", "confirmed": False})
    a = [s for s in mode_reconcile.gather_signals(str(tmp_path), root=str(tmp_path / "s"))
         if s["type"] == "doc-policy-provisional"][0]
    b = [s for s in mode_reconcile.gather_signals(str(tmp_path), root=str(tmp_path / "s"))
         if s["type"] == "doc-policy-provisional"][0]
    assert a["identity"] == b["identity"]


def test_provisional_signal_ack_suppresses(tmp_path, monkeypatch):
    # Acking the identity removes it from the coalesced prompt (mirrors the I1 ack test).
    import mode_reconcile, mode_registry, architect_config
    store = str(tmp_path / "s")
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo", "schemaVersion": 1,
                                                "remoteKey": None, "createdAt": "t"})
    monkeypatch.setattr(mode_registry, "hero_evidence", lambda cwd, root=None: {})
    monkeypatch.setattr(architect_config, "read_policy",
                        lambda cwd, root=None: {"location": "docs/superheroes",
                                                "visibility": "committed", "confirmed": False})
    monkeypatch.setattr(mode_registry, "ensure_project_store", lambda cwd, root=None: store)
    sig = [s for s in mode_reconcile.gather_signals(str(tmp_path), root=store)
           if s["type"] == "doc-policy-provisional"][0]
    mode_reconcile.ack_signal(str(tmp_path), sig["identity"], root=store)
    coalesced = mode_reconcile.coalesce(str(tmp_path), root=store)
    assert coalesced is None or all(
        i["identity"] != sig["identity"] for i in coalesced["items"])


# --- core.md drift signals (#81) ---
def _cm():
    """Load core_md INSIDE a test (never at module top level) so an import error can't
    make the whole mode_reconcile suite uncollectable (Fix 7)."""
    import importlib
    import core_md
    return importlib.reload(core_md)


def _write_core_file(repo, schema=1, status="confirmed", corrupt=False):
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    if corrupt:
        body = "```json superheroes-core\n{ broken\n```\n"
    else:
        import json as _j
        body = ("```json superheroes-core\n%s\n```\n"
                % _j.dumps({"schemaVersion": schema, "verifyCommand": "npm test",
                            "stackTags": ["node"]}, indent=2))
    open(os.path.join(d, "core.md"), "w").write(
        "<!-- superheroes-core: schemaVersion=%d status=%s created=2026-06-26 "
        "updated=2026-06-26 -->\n\n## Threat model\n\nx\n\n%s" % (schema, status, body))


def test_core_md_provisional_signal_present_and_ack_suppresses(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    _write_core_file(str(tmp_path), status="provisional")
    sigs = rc.gather_signals(str(tmp_path), root=root)
    prov = [s for s in sigs if s["type"] == "core-md-provisional"]
    assert len(prov) == 1
    rc.ack_signal(str(tmp_path), prov[0]["identity"], root=root)
    coalesced = rc.coalesce(str(tmp_path), root=root)
    assert coalesced is None or all(i["identity"] != prov[0]["identity"] for i in coalesced["items"])


def test_core_md_confirmed_emits_no_provisional_signal(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    _write_core_file(str(tmp_path), status="confirmed")
    sigs = rc.gather_signals(str(tmp_path), root=str(tmp_path / "store"))
    assert not any(s["type"] == "core-md-provisional" for s in sigs)


def test_legacy_profile_unsupported_signal(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    (tmp_path / ".claude").mkdir(exist_ok=True)
    # an ambiguous review profile (verify under an unrecognized heading), no core.md
    (tmp_path / ".claude" / "review-profile.md").write_text(
        "## How we check\ncommand: npm test\n## Threat model\nx\n")
    sigs = rc.gather_signals(str(tmp_path), root=str(tmp_path / "store"))
    assert any(s["type"] == "legacy-profile-unsupported" for s in sigs)


def test_legacy_profile_unsupported_ack_suppresses(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    (tmp_path / ".claude").mkdir(exist_ok=True)
    (tmp_path / ".claude" / "review-profile.md").write_text(
        "## Verify\ncommand: npm test\n## Threat model\nx\n")
    sigs = rc.gather_signals(str(tmp_path), root=root)
    assert any(s["type"] == "legacy-profile-unsupported" for s in sigs)
    # ack-suppresses: re-make it ambiguous, ack the signal, then it must not coalesce.
    (tmp_path / ".claude" / "review-profile.md").write_text(
        "## How we check\ncommand: npm test\n## Threat model\nx\n")
    unsupported = [s for s in rc.gather_signals(str(tmp_path), root=root)
                   if s["type"] == "legacy-profile-unsupported"]
    assert len(unsupported) == 1
    rc.ack_signal(str(tmp_path), unsupported[0]["identity"], root=root)
    coalesced = rc.coalesce(str(tmp_path), root=root)
    assert coalesced is None or all(i["identity"] != unsupported[0]["identity"]
                                    for i in coalesced["items"])


def test_core_md_unreadable_signal_not_on_greenfield(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    # greenfield: no core.md → NO unreadable signal (signal-absent)
    assert not any(s["type"] == "core-md-unreadable"
                   for s in rc.gather_signals(str(tmp_path), root=str(tmp_path / "store")))
    # corrupt core.md present → unreadable signal
    _write_core_file(str(tmp_path), corrupt=True)
    assert any(s["type"] == "core-md-unreadable"
               for s in rc.gather_signals(str(tmp_path), root=str(tmp_path / "store")))


def test_core_md_unreadable_ack_suppresses(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    _write_core_file(str(tmp_path), corrupt=True)
    unr = [s for s in rc.gather_signals(str(tmp_path), root=root)
           if s["type"] == "core-md-unreadable"]
    assert len(unr) == 1
    rc.ack_signal(str(tmp_path), unr[0]["identity"], root=root)
    coalesced = rc.coalesce(str(tmp_path), root=root)
    assert coalesced is None or all(i["identity"] != unr[0]["identity"] for i in coalesced["items"])


def test_hero_behind_signal(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    _write_core_file(str(tmp_path), schema=_cm().SCHEMA_VERSION + 1)
    assert any(s["type"] == "hero-behind"
               for s in rc.gather_signals(str(tmp_path), root=str(tmp_path / "store")))


def test_hero_behind_absent_on_current_and_ack_suppresses(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    # current schema → NO hero-behind (signal-absent)
    _write_core_file(str(tmp_path), schema=_cm().SCHEMA_VERSION)
    assert not any(s["type"] == "hero-behind"
                   for s in rc.gather_signals(str(tmp_path), root=root))
    # newer schema → signal present, then ack suppresses
    _write_core_file(str(tmp_path), schema=_cm().SCHEMA_VERSION + 1)
    behind = [s for s in rc.gather_signals(str(tmp_path), root=root) if s["type"] == "hero-behind"]
    assert len(behind) == 1
    rc.ack_signal(str(tmp_path), behind[0]["identity"], root=root)
    coalesced = rc.coalesce(str(tmp_path), root=root)
    assert coalesced is None or all(i["identity"] != behind[0]["identity"] for i in coalesced["items"])


def test_legacy_profile_unsupported_with_core_present(tmp_path, monkeypatch):
    # E17: parseable core.md + legacy profile still emits exactly one signal for that hero.
    _init_repo(tmp_path)
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    _write_core_file(str(tmp_path), status="confirmed")
    (tmp_path / ".claude").mkdir(exist_ok=True)
    (tmp_path / ".claude" / "review-profile.md").write_text("stray legacy\n")
    sigs = [s for s in rc.gather_signals(str(tmp_path), root=str(tmp_path / "store"))
            if s["type"] == "legacy-profile-unsupported"]
    assert len(sigs) == 1
    assert sigs[0]["detail"]["hero"] == "review-crew"


def test_legacy_profile_one_signal_per_hero(tmp_path):
    # E17: exactly one signal per affected hero — not two, not one for both.
    _init_repo(tmp_path)
    (tmp_path / ".claude").mkdir(exist_ok=True)
    (tmp_path / ".claude" / "review-profile.md").write_text("review legacy\n")
    tp_dir = tmp_path / ".claude" / "test-pilot"
    tp_dir.mkdir(parents=True)
    (tp_dir / "profile.md").write_text("pilot legacy\n")
    sigs = [s for s in rc.gather_signals(str(tmp_path), root=str(tmp_path / "store"))
            if s["type"] == "legacy-profile-unsupported"]
    assert len(sigs) == 2
    heroes = {s["detail"]["hero"] for s in sigs}
    assert heroes == {"review-crew", "test-pilot"}


def test_legacy_profile_signal_when_detection_exception(tmp_path, monkeypatch):
    # E18: when detection records an exception for a hero, the signal is still emitted.
    _init_repo(tmp_path)
    (tmp_path / ".claude").mkdir(exist_ok=True)
    target = str(tmp_path / ".claude" / "review-profile.md")
    open(target, "w").write("legacy\n")
    real_lstat = os.lstat

    def _lstat(path, *a, **k):
        if os.path.abspath(path) == os.path.abspath(target):
            raise PermissionError("denied for test")
        return real_lstat(path, *a, **k)

    monkeypatch.setattr(os, "lstat", _lstat)
    sigs = rc.gather_signals(str(tmp_path), root=str(tmp_path / "store"))
    legacy = [s for s in sigs if s["type"] == "legacy-profile-unsupported"]
    assert len(legacy) == 1
    assert legacy[0]["detail"]["hero"] == "review-crew"
    assert legacy[0]["detail"]["path"] is None
    assert "denied for test" in legacy[0]["detail"]["reason"]


def test_legacy_profile_signal_on_detection_total_failure(tmp_path, monkeypatch):
    import core_md as _cm

    _init_repo(tmp_path)
    monkeypatch.setattr(_cm, "legacy_profile_refusal", lambda *a, **k: {
        "action": "refused",
        "reason": _cm.LEGACY_PROFILE_REASON,
        "heroes": [],
        "paths": [],
        "remedy": _cm.LEGACY_PROFILE_REMEDY,
        "detail": {"*": "RuntimeError: detection exploded"},
    })
    sigs = rc.gather_signals(str(tmp_path), root=str(tmp_path / "store"))
    legacy = [s for s in sigs if s["type"] == "legacy-profile-unsupported"]
    assert len(legacy) == 1
    assert legacy[0]["detail"]["hero"] is None
    assert legacy[0]["detail"]["path"] is None
    assert legacy[0]["detail"]["reason"] == "RuntimeError: detection exploded"


def test_legacy_profile_signal_core_facts_empty(tmp_path, monkeypatch):
    import core_md as _cm

    _init_repo(tmp_path)
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    (tmp_path / ".claude").mkdir(exist_ok=True)
    (tmp_path / ".claude" / "review-profile.md").write_text("stray legacy\n")
    # empty-placeholder core: schemaVersion only, no real facts
    d = os.path.join(str(tmp_path), ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "core.md"), "w").write(
        "<!-- superheroes-core: schemaVersion=2 status=confirmed created=2026-06-26 "
        "updated=2026-06-26 -->\n\n## Threat model\n\n\n\n## Canonical patterns\n\n\n\n"
        "```json superheroes-core\n"
        + json.dumps({"schemaVersion": 2, "verifyCommand": None, "stackTags": []}, indent=2)
        + "\n```\n")
    sigs = [s for s in rc.gather_signals(str(tmp_path), root=str(tmp_path / "store"))
            if s["type"] == _cm.LEGACY_PROFILE_REASON]
    assert len(sigs) == 1
    assert sigs[0]["detail"]["coreFactsEmpty"] is True


def test_legacy_profile_signal_core_facts_populated(tmp_path, monkeypatch):
    import core_md as _cm

    _init_repo(tmp_path)
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    _write_core_file(str(tmp_path), status="confirmed")
    (tmp_path / ".claude").mkdir(exist_ok=True)
    (tmp_path / ".claude" / "review-profile.md").write_text("stray legacy\n")
    sigs = [s for s in rc.gather_signals(str(tmp_path), root=str(tmp_path / "store"))
            if s["type"] == _cm.LEGACY_PROFILE_REASON]
    assert len(sigs) == 1
    assert sigs[0]["detail"]["coreFactsEmpty"] is False


def test_no_legacy_no_legacy_profile_signal(tmp_path):
    _init_repo(tmp_path)
    sigs = rc.gather_signals(str(tmp_path), root=str(tmp_path / "store"))
    assert not any(s["type"] == "legacy-profile-unsupported" for s in sigs)


def test_legacy_profile_unsupported_absent_and_ack_suppresses(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    # core.md present, NO stray legacy → no legacy-profile-unsupported (signal-absent)
    _write_core_file(str(tmp_path), status="confirmed")
    assert not any(s["type"] == "legacy-profile-unsupported"
                   for s in rc.gather_signals(str(tmp_path), root=root))
    # add a stray legacy → signal present, then ack suppresses
    (tmp_path / ".claude").mkdir(exist_ok=True)
    (tmp_path / ".claude" / "review-profile.md").write_text("stray legacy\n")
    unsupported = [s for s in rc.gather_signals(str(tmp_path), root=root)
                   if s["type"] == "legacy-profile-unsupported"]
    assert len(unsupported) == 1
    rc.ack_signal(str(tmp_path), unsupported[0]["identity"], root=root)
    coalesced = rc.coalesce(str(tmp_path), root=root)
    assert coalesced is None or all(i["identity"] != unsupported[0]["identity"]
                                    for i in coalesced["items"])


def test_calibration_not_saved_signal_present_absent_and_ack(tmp_path, monkeypatch):
    # UFR-4: a pending marker in the machine-local project store → calibration-not-saved.
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    # absent: no marker → no signal
    assert not any(s["type"] == "calibration-not-saved"
                   for s in rc.gather_signals(str(tmp_path), root=root))
    # present: drop the marker via core_md.mark_pending (the real producer of it)
    cm = _cm()
    cm.mark_pending(str(tmp_path), root, detail={"hero": "review-crew", "reason": "lock-contended"})
    sigs = rc.gather_signals(str(tmp_path), root=root)
    not_saved = [s for s in sigs if s["type"] == "calibration-not-saved"]
    assert len(not_saved) == 1
    # ack suppresses
    rc.ack_signal(str(tmp_path), not_saved[0]["identity"], root=root)
    coalesced = rc.coalesce(str(tmp_path), root=root)
    assert coalesced is None or all(i["identity"] != not_saved[0]["identity"]
                                    for i in coalesced["items"])
    # a falsey marker ({"pending": false}) is NOT a signal
    import json as _j
    open(cm._pending_path(str(tmp_path), root), "w").write(_j.dumps({"pending": False}))
    assert not any(s["type"] == "calibration-not-saved"
                   for s in rc.gather_signals(str(tmp_path), root=root))


# --- gather_signals core-md-unreadable via engine_preferences_for_gate (#699 rider 8) ---

def _gate_core_fixture(tmp_path, shape, *, registry_mode=None):
    """Seed a repo for accessor-based unreadable-signal tests."""
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    if registry_mode is not None:
        mr.write_registry(str(tmp_path), registry_mode, "rk", root=root)
    cal = os.path.join(str(tmp_path), ".claude", "superheroes")
    os.makedirs(cal, exist_ok=True)
    core_p = os.path.join(cal, "core.md")
    if shape == "dangling":
        os.symlink("/nonexistent/mode-reconcile-dangle-699", core_p)
    elif shape == "directory":
        os.mkdir(core_p)
    elif shape == "corrupt":
        open(core_p, "w").write("not a core document\n")
    elif shape == "provisional":
        _write_core_file(str(tmp_path), status="provisional")
    return str(tmp_path), root, core_p


def test_gather_signals_dangling_symlink_emits_unreadable(tmp_path, monkeypatch):
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    repo, root, core_p = _gate_core_fixture(tmp_path, "dangling")
    # The old os.path.exists rule missed dangling symlinks — exists follows the link target.
    assert os.path.exists(core_p) is False
    sigs = rc.gather_signals(repo, root=root)
    assert any(s["type"] == "core-md-unreadable" for s in sigs)


def test_gather_signals_absent_emits_no_unreadable(tmp_path, monkeypatch):
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    _init_repo(tmp_path)
    sigs = rc.gather_signals(str(tmp_path), root=str(tmp_path / "store"))
    assert not any(s["type"] == "core-md-unreadable" for s in sigs)


def test_gather_signals_corrupt_emits_unreadable(tmp_path, monkeypatch):
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    repo, root, _ = _gate_core_fixture(tmp_path, "corrupt")
    sigs = rc.gather_signals(repo, root=root)
    assert any(s["type"] == "core-md-unreadable" for s in sigs)


def test_gather_signals_provisional_not_unreadable(tmp_path, monkeypatch):
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    repo, root, _ = _gate_core_fixture(tmp_path, "provisional")
    sigs = rc.gather_signals(repo, root=root)
    assert any(s["type"] == "core-md-provisional" for s in sigs)
    assert not any(s["type"] == "core-md-unreadable" for s in sigs)


def test_gather_signals_directory_emits_unreadable(tmp_path, monkeypatch):
    monkeypatch.setattr(mr, "hero_evidence", lambda *a, **k: {})
    repo, root, _ = _gate_core_fixture(tmp_path, "directory")
    sigs = rc.gather_signals(repo, root=root)
    assert any(s["type"] == "core-md-unreadable" for s in sigs)


def test_gather_signals_core_md_import_failure_is_fail_open(tmp_path, monkeypatch):
    import builtins
    import sys

    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    real_import = builtins.__import__
    saved_core_md = sys.modules.pop("core_md", None)
    try:

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "core_md":
                raise ImportError("simulated core_md import failure")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        sigs = rc.gather_signals(str(tmp_path), root=root)
    finally:
        if saved_core_md is not None:
            sys.modules["core_md"] = saved_core_md

    assert not any(s["type"] == "core-md-unreadable" for s in sigs)

