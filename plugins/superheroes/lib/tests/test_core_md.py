# plugins/superheroes/lib/tests/test_core_md.py
"""Conformance: shared core.md calibration brain (CONVENTIONS §2.1/§2.2/§4.2/§4.4)."""
import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_LIB = os.path.join(_REPO_ROOT, "plugins/superheroes/lib")


def _load(name):
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    path = os.path.join(_LIB, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CM = _load("core_md")


def test_render_then_parse_roundtrips():
    facts = {"verifyCommand": "npm test", "stackTags": ["node", "ts"],
             "threatModel": "multi-tenant", "patterns": "- auth: src/auth.ts:10"}
    text = CM.render_core(facts, "confirmed", "2026-06-26", "2026-06-26")
    assert text.startswith("<!-- superheroes-core: schemaVersion=2 status=confirmed "
                           "created=2026-06-26 updated=2026-06-26 -->")
    assert "## Threat model" in text and "## Canonical patterns" in text
    assert "```json superheroes-core" in text
    got = CM.parse_core(text)
    assert got["schemaVersion"] == 2
    assert got["status"] == "confirmed"
    assert got["verifyCommand"] == "npm test"
    assert got["stackTags"] == ["node", "ts"]
    assert got["threatModel"] == "multi-tenant"
    assert got["patterns"] == "- auth: src/auth.ts:10"
    assert got["created"] == "2026-06-26" and got["updated"] == "2026-06-26"


def test_render_parse_engine_preferences_roundtrip_mixed():
    # MIXED: reviewer != implementation (guards a same-engine-only fixture masking a routing bug).
    # Also carries an optional FR-9 effort sub-map — it must survive the round-trip unchanged.
    facts = {"verifyCommand": "npm test", "stackTags": ["node"],
             "threatModel": "x", "patterns": "",
             "enginePreferences": {"reviewer": "codex", "implementation": "cursor",
                                   "effort": {"review": "medium", "fix": "high"}}}
    text = CM.render_core(facts, "confirmed", "2026-06-30", "2026-06-30")
    assert "schemaVersion=2" in text
    got = CM.parse_core(text)
    assert got["schemaVersion"] == 2
    assert got["enginePreferences"] == {"reviewer": "codex", "implementation": "cursor",
                                        "effort": {"review": "medium", "fix": "high"}}


def test_parse_absent_engine_preferences_is_empty_dict():
    facts = {"verifyCommand": "npm test", "stackTags": [], "threatModel": "", "patterns": ""}
    text = CM.render_core(facts, "provisional", "2026-06-30", "2026-06-30")
    assert CM.parse_core(text)["enginePreferences"] == {}


def test_read_current_schema_is_two_with_engine_prefs(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    facts = {"verifyCommand": "npm test", "stackTags": ["node"], "threatModel": "x",
             "patterns": "", "enginePreferences": {"reviewer": "codex", "implementation": "claude"}}
    CM.write(repo, facts, "confirmed", root=store, now="2026-06-30")
    got = CM.read(repo, root=store)
    assert got["schemaVersion"] == 2 and got["behind"] is False
    assert got["enginePreferences"] == {"reviewer": "codex", "implementation": "claude"}


def test_parse_missing_json_block_is_none():
    text = ("<!-- superheroes-core: schemaVersion=1 status=provisional "
            "created=2026-06-26 updated=2026-06-26 -->\n\n## Threat model\n\nsingle-user\n")
    assert CM.parse_core(text) is None


def test_parse_corrupt_json_block_is_none():
    text = ("<!-- superheroes-core: schemaVersion=1 status=provisional "
            "created=2026-06-26 updated=2026-06-26 -->\n\n"
            "```json superheroes-core\n{ not json\n```\n")
    assert CM.parse_core(text) is None


def test_core_path_in_repo_when_file_present(tmp_path):
    repo = str(tmp_path)
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "core.md"), "w").write("x")
    p = CM.core_path(repo, root=str(tmp_path / "store"))
    assert p == os.path.join(repo, ".claude", "superheroes", "core.md")


def test_core_path_global_default_greenfield(tmp_path):
    # No file anywhere + no registry → defaults to the project store config/ path (global).
    store = str(tmp_path / "store")
    p = CM.core_path(str(tmp_path), root=store)
    assert p.endswith(os.path.join("config", "core.md"))
    assert p.startswith(store)


def _write_core(repo, schema_version, status="provisional", verify="npm test"):
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    text = (
        "<!-- superheroes-core: schemaVersion=%d status=%s created=2026-06-26 "
        "updated=2026-06-26 -->\n\n## Threat model\n\nsingle-user\n\n"
        "## Canonical patterns\n\n- x: a.ts:1\n\n"
        "```json superheroes-core\n%s\n```\n"
        % (schema_version, status,
           json.dumps({"schemaVersion": schema_version, "verifyCommand": verify,
                       "stackTags": ["node"]}, indent=2)))
    open(os.path.join(d, "core.md"), "w").write(text)


def test_read_absent_is_none(tmp_path):
    assert CM.read(str(tmp_path), root=str(tmp_path / "store")) is None


def test_read_current_schema(tmp_path):
    repo = str(tmp_path)
    _write_core(repo, CM.SCHEMA_VERSION, status="confirmed")
    got = CM.read(repo, root=str(tmp_path / "store"))
    assert got["verifyCommand"] == "npm test"
    assert got["stackTags"] == ["node"]
    assert got["status"] == "confirmed"
    assert got["behind"] is False
    assert got["schemaVersion"] == CM.SCHEMA_VERSION


def test_read_corrupt_block_is_none(tmp_path):
    repo = str(tmp_path)
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "core.md"), "w").write(
        "<!-- superheroes-core: schemaVersion=1 status=provisional created=2026-06-26 "
        "updated=2026-06-26 -->\n\n```json superheroes-core\n{ broken\n```\n")
    assert CM.read(repo, root=str(tmp_path / "store")) is None


def test_read_older_schema_upgraded_in_memory_no_writeback(tmp_path):
    # UFR-2: an older schemaVersion (0) is upgraded in memory (stamped current); the FILE is
    # untouched. schemaVersion=0 is a valid int → older, NOT corrupt (it never becomes None).
    repo = str(tmp_path)
    _write_core(repo, 0)
    before = open(os.path.join(repo, ".claude", "superheroes", "core.md")).read()
    got = CM.read(repo, root=str(tmp_path / "store"))
    assert got is not None
    assert got["schemaVersion"] == CM.SCHEMA_VERSION  # upgraded in memory
    assert got["behind"] is False
    after = open(os.path.join(repo, ".claude", "superheroes", "core.md")).read()
    assert after == before  # no write-back on read


def test_read_newer_schema_behind_no_downgrade(tmp_path):
    # UFR-3: a newer schemaVersion → known fields + behind=True, file never rewritten.
    repo = str(tmp_path)
    _write_core(repo, CM.SCHEMA_VERSION + 1)
    before = open(os.path.join(repo, ".claude", "superheroes", "core.md")).read()
    got = CM.read(repo, root=str(tmp_path / "store"))
    assert got is not None
    assert got["behind"] is True
    assert got["verifyCommand"] == "npm test"  # still reads the understood field
    after = open(os.path.join(repo, ".claude", "superheroes", "core.md")).read()
    assert after == before


def test_write_new_is_written(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    facts = {"verifyCommand": "npm test", "stackTags": ["node"],
             "threatModel": "single-user", "patterns": "- x: a.ts:1"}
    res = CM.write(repo, facts, "confirmed", root=store, now="2026-06-26")
    assert res["action"] == "written"
    got = CM.read(repo, root=store)
    assert got["verifyCommand"] == "npm test" and got["status"] == "confirmed"


def test_write_refused_on_fable_external_engine_at_create(tmp_path, monkeypatch):
    import model_tier_overrides as mto

    repo = str(tmp_path)
    store = str(tmp_path / "store")
    monkeypatch.setattr(
        mto,
        "effective_tiers",
        lambda profile_path: {"implementer": "fable", "reviewer": "sonnet"},
    )
    monkeypatch.setattr(mto, "resolve_profile_path", lambda cwd, root=None: "/fake/profile.md")
    facts = {
        "verifyCommand": "npm test",
        "stackTags": ["node"],
        "threatModel": "single-user",
        "patterns": "",
        "enginePreferences": {"implementation": "codex"},
    }
    res = CM.write(repo, facts, "confirmed", root=store, now="2026-06-26")
    assert res["action"] == "refused"
    assert res["violations"][0]["reason"] == "fable-on-external-engine"
    assert CM.read(repo, root=store) is None


def test_write_refused_on_fable_external_engine_when_existing_proposes_codex(tmp_path, monkeypatch):
    import model_tier_overrides as mto

    repo = str(tmp_path)
    store = str(tmp_path / "store")
    monkeypatch.setattr(
        mto,
        "effective_tiers",
        lambda profile_path: {"implementer": "fable", "reviewer": "sonnet"},
    )
    monkeypatch.setattr(mto, "resolve_profile_path", lambda cwd, root=None: "/fake/profile.md")
    initial = {
        "verifyCommand": "npm test",
        "stackTags": ["node"],
        "threatModel": "single-user",
        "patterns": "",
        "enginePreferences": {"implementation": "claude"},
    }
    CM.write(repo, initial, "confirmed", root=store, now="2026-06-26")
    res = CM.write(
        repo,
        {
            "verifyCommand": "npm test",
            "stackTags": ["node"],
            "threatModel": "single-user",
            "patterns": "",
            "enginePreferences": {"implementation": "codex"},
        },
        "confirmed",
        root=store,
        now="2026-06-27",
    )
    assert res["action"] == "refused"
    assert res["violations"][0]["reason"] == "fable-on-external-engine"
    assert CM.read(repo, root=store)["enginePreferences"]["implementation"] == "claude"


def test_write_refused_on_dispatch_gate_evaluation_failure(tmp_path, monkeypatch):
    import model_tier_overrides as mto

    repo = str(tmp_path)
    store = str(tmp_path / "store")

    def _boom(profile_path):
        raise RuntimeError("tier read failed")

    monkeypatch.setattr(mto, "effective_tiers", _boom)
    monkeypatch.setattr(mto, "resolve_profile_path", lambda cwd, root=None: "/fake/profile.md")
    facts = {
        "verifyCommand": "npm test",
        "stackTags": ["node"],
        "threatModel": "single-user",
        "patterns": "",
        "enginePreferences": {"implementation": "codex"},
    }
    res = CM.write(repo, facts, "confirmed", root=store, now="2026-06-26")
    assert res["action"] == "refused"
    assert res["violations"][0]["reason"] == "dispatch-gate-evaluation-failed"
    assert CM.read(repo, root=store) is None


def test_write_reuses_when_detected_equal_or_absent(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, {"verifyCommand": "npm test", "stackTags": ["node"],
                    "threatModel": "single-user", "patterns": ""}, "confirmed",
             root=store, now="2026-06-26")
    # second hero detects the SAME verify command and an ABSENT stack → reuse, no proposal
    res = CM.write(repo, {"verifyCommand": "npm test", "stackTags": [],
                          "threatModel": "", "patterns": ""}, "confirmed",
                   root=store, now="2026-06-26")
    assert res["action"] == "reused"
    assert res["proposals"] == []
    assert CM.read(repo, root=store)["verifyCommand"] == "npm test"


def test_write_proposes_on_genuine_difference_not_applied(tmp_path):
    # FR-6: a second hero detecting a DIFFERENT verify command proposes (not clobbers).
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, {"verifyCommand": "npm test", "stackTags": ["node"],
                    "threatModel": "single-user", "patterns": ""}, "confirmed",
             root=store, now="2026-06-26")
    res = CM.write(repo, {"verifyCommand": "pnpm check", "stackTags": ["node"],
                          "threatModel": "single-user", "patterns": ""}, "confirmed",
                   root=store, now="2026-06-26")
    assert res["action"] == "proposed"
    assert any(p["field"] == "verifyCommand" and p["detected"] == "pnpm check"
               and p["recorded"] == "npm test" for p in res["proposals"])
    # NOT applied: core.md still names npm test
    assert CM.read(repo, root=store)["verifyCommand"] == "npm test"


def test_write_deferred_when_lock_contended(tmp_path, monkeypatch):
    # UFR-4: lock contended → deferred, no write, never raises.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    from contextlib import contextmanager

    @contextmanager
    def _contended(cwd, root=None):
        yield False

    monkeypatch.setattr(CM.mode_registry, "config_lock", _contended)
    res = CM.write(repo, {"verifyCommand": "npm test", "stackTags": [],
                          "threatModel": "", "patterns": ""}, "provisional",
                   root=store, now="2026-06-26")
    assert res["action"] == "deferred"
    assert res["record"] is None
    assert CM.read(repo, root=store) is None  # nothing written


def test_write_deferred_when_store_unwritable(tmp_path, monkeypatch):
    # UFR-4: ensure_project_store returns None (store unwritable) → deferred, no raise.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    monkeypatch.setattr(CM.mode_registry, "ensure_project_store", lambda cwd, root=None: None)
    res = CM.write(repo, {"verifyCommand": "npm test", "stackTags": [],
                          "threatModel": "", "patterns": ""}, "provisional",
                   root=store, now="2026-06-26")
    assert res["action"] == "deferred"


def test_write_deferred_marks_pending_then_written_clears_it(tmp_path, monkeypatch):
    # UFR-4 calibration-not-saved marker: a deferred write drops a pending marker; a later
    # successful write clears it.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    from contextlib import contextmanager

    @contextmanager
    def _contended(cwd, root=None):
        yield False

    monkeypatch.setattr(CM.mode_registry, "config_lock", _contended)
    CM.write(repo, {"verifyCommand": "npm test", "stackTags": [], "threatModel": "",
                    "patterns": ""}, "provisional", root=store, now="2026-06-26")
    assert os.path.isfile(CM._pending_path(repo, store))  # marker dropped
    monkeypatch.undo()  # restore the real lock
    res = CM.write(repo, {"verifyCommand": "npm test", "stackTags": [], "threatModel": "",
                          "patterns": ""}, "confirmed", root=store, now="2026-06-26")
    assert res["action"] == "written"
    assert not os.path.exists(CM._pending_path(repo, store))  # cleared on success


_CORE_FACTS = {"verifyCommand": "npm test", "stackTags": ["node"],
               "threatModel": "single-user", "patterns": "- x: a.ts:1"}


def test_confirm_flips_provisional_core_preserving_created(tmp_path):
    # #121 Part A: write() (reuse-not-clobber) cannot flip an existing provisional core; confirm()
    # does — preserving `created`, bumping `updated`, leaving the facts untouched.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, dict(_CORE_FACTS), "provisional", root=store, now="2026-06-26")
    res = CM.confirm(repo, root=store, now="2026-06-28")
    assert res["action"] == "confirmed"
    got = CM.read(repo, root=store)
    assert got["status"] == "confirmed"
    assert got["created"] == "2026-06-26"            # preserved
    assert got["updated"] == "2026-06-28"            # bumped
    assert got["verifyCommand"] == "npm test"        # facts untouched
    assert got["patterns"] == "- x: a.ts:1"
    assert got["threatModel"] == "single-user"


def test_confirm_idempotent_on_already_confirmed(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    res = CM.confirm(repo, root=store, now="2026-06-28")
    assert res["action"] == "noop"
    assert CM.read(repo, root=store)["updated"] == "2026-06-26"  # untouched


def test_confirm_absent_core_is_absent(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    assert CM.confirm(repo, root=store)["action"] == "absent"


def test_confirm_deferred_when_lock_contended_leaves_provisional(tmp_path, monkeypatch):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, dict(_CORE_FACTS), "provisional", root=store, now="2026-06-26")
    from contextlib import contextmanager

    @contextmanager
    def _contended(cwd, root=None):
        yield False

    monkeypatch.setattr(CM.mode_registry, "config_lock", _contended)
    res = CM.confirm(repo, root=store, now="2026-06-28")
    assert res["action"] == "deferred"
    assert CM.read(repo, root=store)["status"] == "provisional"  # unchanged


def test_confirm_layer_flips_status_preserving_body_created_nudge_ack(tmp_path):
    # #121 Part A (layers): a surgical provenance flip — status + updated change; created,
    # nudge-ack, and the body are preserved verbatim (FR-11; never rewrite a hand-edited layer).
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    layer_p = CM._layer_path(repo, "review-crew", store)
    os.makedirs(os.path.dirname(layer_p), exist_ok=True)
    prov = ('<!-- review-crew: schemaVersion=1 status=provisional created=2026-06-20 '
            'updated=2026-06-20 nudge-ack={"rubric-v1":true} -->')
    body = "\n\n## Scope exclusions\n- hand-edited note\n"
    open(layer_p, "w").write(prov + body)
    res = CM.confirm_layer(repo, "review-crew", root=store, now="2026-06-28")
    assert res["action"] == "confirmed"
    out = open(layer_p).read()
    assert "status=confirmed" in out
    assert "created=2026-06-20" in out                  # preserved
    assert "updated=2026-06-28" in out                  # bumped
    assert 'nudge-ack={"rubric-v1":true}' in out        # preserved verbatim
    assert "## Scope exclusions\n- hand-edited note" in out  # body untouched


def test_confirm_layer_idempotent_and_absent(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    assert CM.confirm_layer(repo, "review-crew", root=store)["action"] == "absent"
    layer_p = CM._layer_path(repo, "review-crew", store)
    os.makedirs(os.path.dirname(layer_p), exist_ok=True)
    open(layer_p, "w").write(
        '<!-- review-crew: schemaVersion=1 status=confirmed created=2026-06-20 '
        'updated=2026-06-20 nudge-ack={} -->\n\n## Scope exclusions\n- none\n')
    assert CM.confirm_layer(repo, "review-crew", root=store)["action"] == "noop"


def test_confirm_all_confirms_core_and_present_layers(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, dict(_CORE_FACTS), "provisional", root=store, now="2026-06-26")
    layer_p = CM._layer_path(repo, "review-crew", store)
    os.makedirs(os.path.dirname(layer_p), exist_ok=True)
    open(layer_p, "w").write(
        '<!-- review-crew: schemaVersion=1 status=provisional created=2026-06-20 '
        'updated=2026-06-20 nudge-ack={} -->\n\n## Scope exclusions\n- none\n')
    res = CM.confirm_all(repo, root=store, now="2026-06-28")
    assert res["core"]["action"] == "confirmed"
    assert res["layers"]["review-crew"]["action"] == "confirmed"
    assert CM.read(repo, root=store)["status"] == "confirmed"
    assert "status=confirmed" in open(layer_p).read()


def test_cli_confirm_flips_core(tmp_path, capsys):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, dict(_CORE_FACTS), "provisional", root=store, now="2026-06-26")
    CM.main(["confirm", "--cwd", repo, "--root", store])
    out = json.loads(capsys.readouterr().out)
    assert out["core"]["action"] == "confirmed"
    assert CM.read(repo, root=store)["status"] == "confirmed"


def test_confirm_does_not_downgrade_a_newer_schema_core(tmp_path):
    # #121 Part A / UFR-3: confirm() must NEVER rewrite a forward-schema (behind) core — that
    # would downgrade schemaVersion and drop fields the running version doesn't understand. write()
    # and migrate_on_read() (removed in #724) both refused to rewrite a behind record; confirm()
    # must too.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _write_core(repo, CM.SCHEMA_VERSION + 1, status="provisional")  # newer schema, provisional
    core_p = os.path.join(repo, ".claude", "superheroes", "core.md")
    before = open(core_p).read()
    res = CM.confirm(repo, root=store, now="2026-06-28")
    assert res["action"] == "behind"
    assert open(core_p).read() == before  # file untouched — not downgraded, not re-rendered


# ---------------------------------------------------------------------------
# Issue #724 — legacy profile detection + refusal (migrate_on_read removed)
# ---------------------------------------------------------------------------

def _init_git_repo(repo):
    subprocess.run(["git", "-C", repo, "init", "-q"], check=True)


def _legacy_inrepo_path(repo, hero):
    sub = CM.mode_registry._HERO_LEGACY_INREPO[hero]
    return os.path.join(repo, sub)


def _write_legacy_inrepo(repo, hero, text="legacy profile\n"):
    path = _legacy_inrepo_path(repo, hero)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(text)
    return path


def _seed_global_legacy(tmp_path, repo, hero, monkeypatch, text="legacy profile\n"):
    import store_core as sc
    if hero == "review-crew":
        g = str(tmp_path / "review_global")
        import review_store
        monkeypatch.setattr(review_store, "store_root", lambda: g)
    else:
        g = str(tmp_path / "tp_global")
        monkeypatch.setenv("TEST_PILOT_STORE_ROOT", g)
    ident = sc.derive_identifiers(repo)
    eid = ident["gitdir_hash"]
    entry = os.path.join(g, "entries", eid)
    os.makedirs(entry, exist_ok=True)
    fname = CM.mode_registry._HERO_GLOBAL_FILENAME[hero]
    prof = os.path.join(entry, fname)
    open(prof, "w").write(text)
    sc.write_pointer(g, ident["gitdir_hash"], eid)
    if ident["remote_hash"]:
        sc.write_pointer(g, ident["remote_hash"], eid)
    return prof


def _tree_snapshot(roots):
    snap = {}
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            for name in dirnames:
                p = os.path.join(dirpath, name)
                snap[p] = ("dir", os.path.getmtime(p))
            for name in filenames:
                p = os.path.join(dirpath, name)
                snap[p] = ("file", os.path.getsize(p), os.path.getmtime(p))
    return snap


def test_legacy_profile_refusal_inrepo_review_crew_and_test_pilot(tmp_path):
  # E1: in-repo legacy regular files for both heroes.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _init_git_repo(repo)
    review_path = _write_legacy_inrepo(repo, "review-crew")
    tp_path = _write_legacy_inrepo(repo, "test-pilot")
    refusal = CM.legacy_profile_refusal(repo, root=store)
    assert refusal is not None
    assert refusal["reason"] == CM.LEGACY_PROFILE_REASON
    assert refusal["action"] == "refused"
    assert "review-crew" in refusal["heroes"]
    assert "test-pilot" in refusal["heroes"]
    assert review_path in refusal["paths"]
    assert tp_path in refusal["paths"]
    assert refusal["detail"]["review-crew"] == review_path
    assert refusal["detail"]["test-pilot"] == tp_path


def test_legacy_profile_refusal_global_only(tmp_path, monkeypatch):
  # E1: global legacy regular file when no in-repo copy exists.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _init_git_repo(repo)
    global_path = _seed_global_legacy(tmp_path, repo, "review-crew", monkeypatch)
    refusal = CM.legacy_profile_refusal(repo, root=store)
    assert refusal is not None
    assert refusal["reason"] == CM.LEGACY_PROFILE_REASON
    assert "review-crew" in refusal["heroes"]
    assert global_path in refusal["paths"]


def test_legacy_profile_refusal_dangling_symlink(tmp_path):
  # E2: dangling symlink at a legacy path is a refusal.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    path = _legacy_inrepo_path(repo, "review-crew")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    os.symlink("/no/such/legacy-dangle-724", path)
    refusal = CM.legacy_profile_refusal(repo, root=store)
    assert refusal is not None
    assert "review-crew" in refusal["heroes"]
    assert path in refusal["paths"]


def test_legacy_profile_refusal_directory(tmp_path):
  # E3: directory at a legacy path is a refusal.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    path = _legacy_inrepo_path(repo, "test-pilot")
    os.makedirs(path, exist_ok=True)
    refusal = CM.legacy_profile_refusal(repo, root=store)
    assert refusal is not None
    assert "test-pilot" in refusal["heroes"]
    assert path in refusal["paths"]


def test_legacy_profile_refusal_none_when_no_legacy(tmp_path):
  # E4: no legacy anywhere → None.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    assert CM.legacy_profile_refusal(repo, root=store) is None


def test_legacy_profile_refusal_lstat_permission_error(tmp_path, monkeypatch):
  # E5: os.lstat PermissionError → present-indeterminate refusal with exception text.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    path = _write_legacy_inrepo(repo, "review-crew")
    real_lstat = os.lstat

    def _lstat(p, *a, **k):
        if os.path.abspath(p) == os.path.abspath(path):
            raise PermissionError("access denied for test")
        return real_lstat(p, *a, **k)

    monkeypatch.setattr(os, "lstat", _lstat)
    refusal = CM.legacy_profile_refusal(repo, root=store)
    assert refusal is not None
    assert "review-crew" in refusal["heroes"]
    assert "PermissionError" in refusal["detail"]["review-crew"]


def test_legacy_profile_refusal_global_probe_failure(tmp_path, monkeypatch):
  # E6: global-leg probe failure with no in-repo legacy → refusal, not None.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _init_git_repo(repo)

    def _boom(*a, **k):
        raise RuntimeError("global probe failed")

    monkeypatch.setattr(CM.store_core, "resolve_global", _boom)
    refusal = CM.legacy_profile_refusal(repo, root=store)
    assert refusal is not None
    assert refusal["action"] == "refused"
    assert "review-crew" in refusal["heroes"]
    assert refusal["detail"]["review-crew"].startswith("RuntimeError:")


def test_legacy_profile_refusal_guardian_not_in_roster(tmp_path):
  # E7: guardian (no _HERO_LEGACY_INREPO entry) contributes no candidates.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    assert "guardian" not in CM.mode_registry._HERO_LEGACY_INREPO
    refusal = CM.legacy_profile_refusal(repo, root=store)
    assert refusal is None or "guardian" not in (refusal.get("heroes") or [])


def test_legacy_profile_refusal_inrepo_when_global_none(tmp_path, monkeypatch):
  # E8: resolve_global returns None → in-repo candidate still evaluated.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    path = _write_legacy_inrepo(repo, "review-crew")
    monkeypatch.setattr(CM.store_core, "resolve_global", lambda *a, **k: None)
    refusal = CM.legacy_profile_refusal(repo, root=store)
    assert refusal is not None
    assert path in refusal["paths"]


def test_legacy_profile_refusal_outer_exception_fail_closed(tmp_path, monkeypatch):
  # E9: exception inside the function body → refusal with heroes/paths empty, detail has '*'.
    repo = str(tmp_path)
    store = str(tmp_path / "store")

    class _BoomDict(dict):
        def __iter__(self):
            raise RuntimeError("iteration exploded")

    monkeypatch.setattr(CM.mode_registry, "_HERO_LEGACY_INREPO", _BoomDict())
    refusal = CM.legacy_profile_refusal(repo, root=store)
    assert refusal is not None
    assert refusal["heroes"] == []
    assert refusal["paths"] == []
    assert "*" in refusal["detail"]
    assert "iteration exploded" in refusal["detail"]["*"]


def test_legacy_profile_refusal_writes_nothing(tmp_path):
  # E10: legacy_profile_refusal is detection-only — no store or .claude writes.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _write_legacy_inrepo(repo, "review-crew")
    claude_dir = os.path.join(repo, ".claude")
    before = _tree_snapshot([store, claude_dir])
    CM.legacy_profile_refusal(repo, root=store)
    after = _tree_snapshot([store, claude_dir])
    assert before == after


def test_resolve_shared_prefers_core_over_legacy(tmp_path):
  # E11: parseable core.md + legacy present → shared facts, no refusal action.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _write_core(repo, CM.SCHEMA_VERSION, status="confirmed", verify="pnpm test")
    _write_legacy_inrepo(repo, "review-crew")
    got = CM.resolve_shared(repo, root=store)
    assert got is not None
    assert got["verifyCommand"] == "pnpm test"
    assert "action" not in got


def test_resolve_shared_refusal_core_absent(tmp_path):
  # E12: no core.md, legacy present → refusal with coreMd absent.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _write_legacy_inrepo(repo, "review-crew")
    got = CM.resolve_shared(repo, root=store)
    assert got is not None
    assert got["action"] == "refused"
    assert got["detail"]["coreMd"] == CM.CONFIG_ABSENT


def test_resolve_shared_refusal_core_unreadable(tmp_path):
  # E12: corrupt core.md + legacy present → refusal with coreMd unreadable.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "core.md"), "w").write("not parseable core\n")
    _write_legacy_inrepo(repo, "review-crew")
    got = CM.resolve_shared(repo, root=store)
    assert got is not None
    assert got["action"] == "refused"
    assert got["detail"]["coreMd"] == CM.CONFIG_UNREADABLE


def test_resolve_shared_none_when_neither_present(tmp_path):
  # E13: neither core.md nor legacy → None.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    assert CM.resolve_shared(repo, root=store) is None


def test_core_facts_are_empty_none():
    assert CM.core_facts_are_empty(None) is True


def test_core_facts_are_empty_empty_dict():
    assert CM.core_facts_are_empty({}) is True


def test_core_facts_are_empty_placeholder():
    rec = {
        "schemaVersion": CM.SCHEMA_VERSION,
        "verifyCommand": None,
        "stackTags": [],
        "threatModel": "",
        "patterns": "",
    }
    assert CM.core_facts_are_empty(rec) is True


def test_core_facts_are_empty_whitespace_only_threat_model():
    assert CM.core_facts_are_empty({"threatModel": "  "}) is True


def test_core_facts_are_empty_verify_command_set():
    assert CM.core_facts_are_empty({"verifyCommand": "x"}) is False


def test_core_facts_are_empty_stack_tags_nonempty():
    assert CM.core_facts_are_empty({"stackTags": ["py"]}) is False


def test_core_facts_are_empty_patterns_set():
    assert CM.core_facts_are_empty({"patterns": "p"}) is False


def test_core_facts_are_empty_non_dict_str():
    assert CM.core_facts_are_empty("oops") is True


def test_core_facts_are_empty_non_dict_zero():
    assert CM.core_facts_are_empty(0) is True


def test_core_facts_are_empty_non_dict_list():
    assert CM.core_facts_are_empty([]) is True


def test_core_facts_are_empty_populated():
    rec = {
        "schemaVersion": CM.SCHEMA_VERSION,
        "verifyCommand": "npm test",
        "stackTags": ["node"],
        "threatModel": "multi-tenant",
        "patterns": "- x: a.ts:1",
    }
    assert CM.core_facts_are_empty(rec) is False


def test_resolve_shared_refusal_leaves_no_pending_marker(tmp_path):
    # E14: refusal path leaves no calibration-pending marker. Not asserting config_lock:
    # resolve_shared does acquire the lock once via read()'s mode_registry.resolve backfill
    # (predates #724; base migrate_on_read took the lock and could unlink/commit). The refusal
    # path guarantees no migrate, unlink, commit, or mark_pending.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _init_git_repo(repo)
    legacy_path = _write_legacy_inrepo(repo, "review-crew")
    subprocess.run(["/usr/bin/git", "-C", repo, "add", legacy_path], check=True)
    subprocess.run(["/usr/bin/git", "-C", repo, "commit", "-q", "-m", "track legacy"], check=True)
    head_before = subprocess.check_output(
        ["/usr/bin/git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    legacy_bytes_before = open(legacy_path, "rb").read()
    porcelain_before = subprocess.check_output(
        ["/usr/bin/git", "-C", repo, "status", "--porcelain"], text=True)
    got = CM.resolve_shared(repo, root=store)
    assert got is not None and got["action"] == "refused"
    assert not os.path.exists(CM._pending_path(repo, store))
    assert os.path.isfile(legacy_path)
    assert open(legacy_path, "rb").read() == legacy_bytes_before
    head_after = subprocess.check_output(
        ["/usr/bin/git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    assert head_after == head_before
    porcelain_after = subprocess.check_output(
        ["/usr/bin/git", "-C", repo, "status", "--porcelain"], text=True)
    rel_legacy = os.path.relpath(legacy_path, repo)
    assert rel_legacy not in porcelain_before
    assert rel_legacy not in porcelain_after


_REMOVED_MIGRATION_SYMBOLS = (
    "migrate_on_read", "classify", "split_profile", "_split_sections", "_headings",
    "_migration_recorded", "_record_migration_commit", "_commit_pathspec",
    "_present_calibration_paths", "_legacy_in_repo", "_facts_are_empty", "_in_repo_mode",
    "_same_file", "_legacy_path",
)


def test_migration_symbols_removed():
    for name in _REMOVED_MIGRATION_SYMBOLS:
        assert not hasattr(CM, name)


def test_core_md_cli_has_no_migrate_subcommand(capsys):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), pytest.raises(SystemExit):
        CM.main(["--help"])
    assert "migrate" not in buf.getvalue()


def test_core_md_cli_migrate_rejected(tmp_path):
    with pytest.raises(SystemExit) as exc:
        CM.main(["migrate", "--cwd", str(tmp_path), "--root", str(tmp_path / "store"),
                 "--hero", "review-crew"])
    assert exc.value.code != 0


def test_core_md_source_has_no_git_commit_calls():
    src = open(os.path.join(_LIB, "core_md.py"), encoding="utf-8").read()
    assert not re.search(r'run_git\s*\([^)]*["\']commit["\']', src)


def test_resolve_shared_none_on_bare_greenfield(tmp_path):
    assert CM.resolve_shared(str(tmp_path), root=str(tmp_path / "store")) is None


def test_cli_resolve_emits_expected_shape(tmp_path, capsys):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _write_core(repo, CM.SCHEMA_VERSION, status="confirmed")
    rc = CM.main(["resolve", "--cwd", repo, "--root", store])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert set(out) == {"verifyCommand", "stackTags", "status", "behind"}
    assert out["verifyCommand"] == "npm test"
    assert out["behind"] is False


def test_cli_resolve_greenfield_emits_nulls(tmp_path, capsys):
    rc = CM.main(["resolve", "--cwd", str(tmp_path), "--root", str(tmp_path / "store")])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verifyCommand"] is None and out["status"] is None


def test_cli_write_creates_core_from_stdin(tmp_path, capsys, monkeypatch):
    # FR-5 create path: `write` reads a facts JSON from stdin and writes core.md.
    import io
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    facts = {"verifyCommand": "pnpm check", "stackTags": ["node"],
             "threatModel": "multi-tenant", "patterns": "- x: a.ts:1"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(facts)))
    rc = CM.main(["write", "--cwd", repo, "--root", store, "--status", "confirmed"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["action"] == "written"
    got = CM.read(repo, root=store)
    assert got["verifyCommand"] == "pnpm check" and got["status"] == "confirmed"


def test_cli_write_layer_creates_layer_from_stdin(tmp_path, capsys, monkeypatch):
    # FR-3 create path: `write-layer` reads the hero layer body from stdin and writes the layer.
    import io
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    monkeypatch.setattr("sys.stdin", io.StringIO("## Scope exclusions\n- none\n"))
    rc = CM.main(["write-layer", "--cwd", repo, "--root", store,
                  "--hero", "review-crew", "--status", "provisional"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["action"] == "written"
    layer = open(out["path"]).read()
    assert "## Scope exclusions" in layer
    assert "review-crew: schemaVersion=" in layer  # wrapped in the §2.2 layer provenance line


def test_write_defers_when_core_write_fails(tmp_path, monkeypatch):
    # code-001 fail-open: an OSError writing core.md → `deferred` + a best-effort pending
    # marker, never a propagated exception (the function's "never raise, never block" contract).
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    real = CM.store_core.atomic_write

    def _boom(path, text, *a, **k):
        if path.endswith("core.md"):
            raise OSError("disk full")
        return real(path, text, *a, **k)  # let store setup + the marker write through

    monkeypatch.setattr(CM.store_core, "atomic_write", _boom)
    res = CM.write(repo, {"verifyCommand": "x", "stackTags": [], "threatModel": "t",
                          "patterns": ""}, "provisional", root=store)
    assert res["action"] == "deferred"
    assert os.path.isfile(CM._pending_path(repo, store))  # UFR-4 marker set


def test_relocate_file_copies_then_unlinks_atomically(tmp_path):
    src = tmp_path / "a.txt"; src.write_text("hello")
    dst = tmp_path / "sub" / "b.txt"
    CM.relocate_file(str(src), str(dst))
    assert dst.read_text() == "hello" and not src.exists()


def test_render_layer_always_ends_with_one_newline(tmp_path):
    # #121 Part I: a body without a trailing newline must still yield a file ending in exactly one
    # \n (no "No newline at end of file"); a \n-terminated body is unchanged.
    out = CM._render_layer("## App launch\n- x", "test-pilot", "provisional", "2026-06-26")
    assert out.endswith("- x\n") and not out.endswith("\n\n")
    out2 = CM._render_layer("## Scope exclusions\n- none\n", "review-crew", "provisional", "2026-06-26")
    assert out2.endswith("- none\n")


def test_confirm_layer_rejects_provenance_without_status_field(tmp_path):
    # /code-review #3: a provenance with no status= token must NOT report 'confirmed' (the surgical
    # re.sub would be a no-op) — that was a silent false-success.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    lp = CM._layer_path(repo, "review-crew", store)
    os.makedirs(os.path.dirname(lp), exist_ok=True)
    open(lp, "w").write("<!-- review-crew: schemaVersion=1 created=2026-06-20 nudge-ack={} -->"
                        "\n\n## Scope exclusions\n- none\n")
    res = CM.confirm_layer(repo, "review-crew", root=store, now="2026-06-28")
    assert res["action"] != "confirmed"
    assert "status=confirmed" not in open(lp).read()


def test_confirm_layer_does_not_corrupt_nudge_ack_with_status_token(tmp_path):
    # /code-review #3: the surgical sub must touch only the leading status=/updated= fields, never a
    # status=/updated= substring inside the nudge-ack map.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    lp = CM._layer_path(repo, "review-crew", store)
    os.makedirs(os.path.dirname(lp), exist_ok=True)
    open(lp, "w").write('<!-- review-crew: schemaVersion=1 status=provisional created=2026-06-20 '
                        'updated=2026-06-20 nudge-ack={"k":"status=x"} -->\n\n## Scope exclusions\n- none\n')
    res = CM.confirm_layer(repo, "review-crew", root=store, now="2026-06-28")
    out = open(lp).read()
    assert res["action"] == "confirmed"
    assert 'nudge-ack={"k":"status=x"}' in out  # ack preserved verbatim
    assert "status=confirmed" in out


def test_confirm_layer_reads_under_lock_not_stale(tmp_path, monkeypatch):
    # /code-review #1: confirm_layer must re-read the layer UNDER the lock, so a concurrent write
    # that lands while it waits for the lock is not clobbered by a stale pre-lock read.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    lp = CM._layer_path(repo, "review-crew", store)
    os.makedirs(os.path.dirname(lp), exist_ok=True)
    prov = ('<!-- review-crew: schemaVersion=1 status=provisional created=2026-06-20 '
            'updated=2026-06-20 nudge-ack={} -->\n\n## Scope exclusions\n- %s\n')
    open(lp, "w").write(prov % "OLD")
    from contextlib import contextmanager
    real_lock = CM.mode_registry.config_lock

    @contextmanager
    def _lock_then_mutate(cwd, root=None):
        open(lp, "w").write(prov % "NEW BODY")  # a concurrent write_layer landed first
        with real_lock(cwd, root) as got:
            yield got

    monkeypatch.setattr(CM.mode_registry, "config_lock", _lock_then_mutate)
    CM.confirm_layer(repo, "review-crew", root=store, now="2026-06-28")
    out = open(lp).read()
    assert "NEW BODY" in out and "OLD" not in out  # concurrent body survived
    assert "status=confirmed" in out


def test_confirm_all_does_not_flip_layers_when_core_not_confirmed(tmp_path):
    # /code-review #5: a behind/deferred/absent core must NOT leave layers advertising 'confirmed'
    # over an unconfirmed shared core (no split state).
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _write_core(repo, CM.SCHEMA_VERSION + 1, status="provisional")  # behind core → confirm -> 'behind'
    lp = CM._layer_path(repo, "review-crew", store)
    os.makedirs(os.path.dirname(lp), exist_ok=True)
    open(lp, "w").write('<!-- review-crew: schemaVersion=1 status=provisional created=2026-06-20 '
                        'updated=2026-06-20 nudge-ack={} -->\n\n## Scope exclusions\n- none\n')
    res = CM.confirm_all(repo, root=store, now="2026-06-28")
    assert res["core"]["action"] == "behind"
    assert all(v["action"] != "confirmed" for v in res["layers"].values())
    assert "status=confirmed" not in open(lp).read()


def test_store_create_does_not_mint_legacy_profile_md(tmp_path):
    # #428 direction 2 corollary: store.create() must not materialize a legacy profile.md on disk
    # (it returns the path but never writes the file). Locks the non-minting invariant so a future
    # change can't reintroduce the migrate_on_read trigger (removed in #724).
    import store as tp_store
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    subprocess.run(["git", "init", "-q", repo], check=True, capture_output=True)
    root = str(tmp_path / "store")
    c = tp_store.create(repo, "in-repo", root)
    assert c["profileSource"] == "profile-md"  # genuinely un-migrated: legacy scaffold target
    assert c["profile"].endswith(os.path.join(".claude", "test-pilot", "profile.md"))
    assert not os.path.exists(c["profile"])  # path returned, file NOT minted


def _gate_valid_core_text(prefs=None):
    facts = {
        "verifyCommand": "npm test",
        "stackTags": [],
        "threatModel": "t",
        "patterns": "",
        "enginePreferences": prefs if prefs is not None else {"reviewer": "cursor"},
    }
    return CM.render_core(facts, "confirmed", "2026-01-01", "2026-01-01")


def _gate_core_beside(repo):
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "core.md")


def test_gate_accessor_dangling_in_repo_symlink_global_mode_is_unreadable(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.mode_registry.write_registry(repo, CM.mode_registry.GLOBAL, None, root=store)
    core_p = _gate_core_beside(repo)
    os.symlink("/no/such/target-for-wo676", core_p)
    assert CM.core_path(repo, root=store) != core_p
    cfg = CM.engine_preferences_for_gate(cwd=repo, root=store)
    assert cfg.status == CM.CONFIG_UNREADABLE
    assert core_p in (cfg.detail or "")


def test_gate_edge1_fully_absent_path(tmp_path):
    path = str(tmp_path / "missing" / "core.md")
    cfg = CM._classify_core_md_at_path(path)
    assert cfg.status == CM.CONFIG_ABSENT


def test_gate_edge2_dangling_symlink(tmp_path):
    path = str(tmp_path / "core.md")
    os.symlink("/nonexistent/dangle", path)
    cfg = CM._classify_core_md_at_path(path)
    assert cfg.status == CM.CONFIG_UNREADABLE
    assert path in cfg.detail


def test_gate_edge3_stat_oserror(tmp_path):
    parent = tmp_path / "locked"
    parent.mkdir()
    os.chmod(parent, 0)
    try:
        path = str(parent / "core.md")
        cfg = CM._classify_core_md_at_path(path)
        assert cfg.status == CM.CONFIG_UNREADABLE
        assert path in cfg.detail
    finally:
        os.chmod(parent, 0o755)


def test_gate_edge4_directory_not_file(tmp_path):
    path = str(tmp_path / "core.md")
    os.mkdir(path)
    cfg = CM._classify_core_md_at_path(path)
    assert cfg.status == CM.CONFIG_UNREADABLE


def test_gate_edge5_open_filenotfound_after_stat_is_unreadable_race(tmp_path, monkeypatch):
    path = str(tmp_path / "core.md")
    open(path, "w").write(_gate_valid_core_text())
    real_open = open

    def _open(p, *a, **kw):
        if os.path.abspath(p) == os.path.abspath(path):
            raise FileNotFoundError("raced away")
        return real_open(p, *a, **kw)

    monkeypatch.setattr("builtins.open", _open)
    cfg = CM._classify_core_md_at_path(path)
    assert cfg.status == CM.CONFIG_UNREADABLE
    assert "race" in (cfg.detail or "").lower()


def test_gate_edge6_mode_zero_unreadable(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root reads mode-000 files")
    path = str(tmp_path / "core.md")
    open(path, "w").write(_gate_valid_core_text())
    try:
        os.chmod(path, 0)
        cfg = CM._classify_core_md_at_path(path)
        assert cfg.status == CM.CONFIG_UNREADABLE
    finally:
        os.chmod(path, 0o644)


def test_gate_edge7_corrupt_parse(tmp_path):
    path = str(tmp_path / "core.md")
    open(path, "w").write("not a core document\n")
    cfg = CM._classify_core_md_at_path(path)
    assert cfg.status == CM.CONFIG_UNREADABLE


def test_gate_edge8_ok_empty_prefs_when_key_missing(tmp_path):
    path = str(tmp_path / "core.md")
    text = (
        "<!-- superheroes-core: schemaVersion=2 status=confirmed "
        "created=2026-01-01 updated=2026-01-01 -->\n\n"
        "## Threat model\n\nt\n\n## Canonical patterns\n\n\n"
        "```json superheroes-core\n"
        '{"schemaVersion": 2, "verifyCommand": "x", "stackTags": []}\n'
        "```\n"
    )
    open(path, "w").write(text)
    cfg = CM._classify_core_md_at_path(path)
    assert cfg.status == CM.CONFIG_OK
    assert cfg.prefs == {}


def test_gate_edge9_ok_with_prefs(tmp_path):
    path = str(tmp_path / "core.md")
    open(path, "w").write(_gate_valid_core_text({"reviewer": "cursor"}))
    cfg = CM._classify_core_md_at_path(path)
    assert cfg.status == CM.CONFIG_OK
    assert cfg.prefs == {"reviewer": "cursor"}


def test_gate_edge10_accessor_never_raises(monkeypatch):
    def _boom(cwd, root=None):
        raise RuntimeError("candidates exploded")

    monkeypatch.setattr(CM, "_core_candidates", _boom)
    cfg = CM.engine_preferences_for_gate(cwd="/tmp", root="/tmp/store")
    assert cfg.status == CM.CONFIG_UNREADABLE
    assert "candidates exploded" in cfg.detail


def test_gate_edge11_invalid_utf8(tmp_path):
    path = str(tmp_path / "core.md")
    with open(path, "wb") as fh:
        fh.write(b"<!-- x -->\n\xff\xfe not utf8\n")
    cfg = CM._classify_core_md_at_path(path)
    assert cfg.status == CM.CONFIG_UNREADABLE
    assert "UTF-8" in cfg.detail


def test_read_raises_on_invalid_utf8_write_refuses_via_gate(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    core_p = _gate_core_beside(repo)
    with open(core_p, "wb") as fh:
        fh.write(b"\xff broken\n")
    with pytest.raises(UnicodeDecodeError):
        CM.read(repo, root=store)
    res = CM.write(
        repo,
        {"verifyCommand": "npm test", "stackTags": [], "threatModel": "t", "patterns": ""},
        "confirmed",
        root=store,
        now="2026-01-01",
    )
    assert res["action"] == "refused"
    assert res["violations"][0]["reason"] == CM.GATE_REASON_UNREADABLE


def test_symlink_to_regular_file_is_ok(tmp_path):
    target = tmp_path / "real-core.md"
    target.write_text(_gate_valid_core_text(), encoding="utf-8")
    link = tmp_path / "core.md"
    os.symlink(target, link)
    cfg = CM._classify_core_md_at_path(str(link))
    assert cfg.status == CM.CONFIG_OK


@pytest.mark.parametrize("strategy", ("profile", "cwd"))
def test_gate_resolution_absent(strategy, tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    if strategy == "profile":
        prof = os.path.join(repo, ".claude", "superheroes", "review-crew.md")
        os.makedirs(os.path.dirname(prof), exist_ok=True)
        open(prof, "w").write("## Model tiers\n")
        cfg = CM.engine_preferences_for_gate(profile_path=prof)
    else:
        cfg = CM.engine_preferences_for_gate(cwd=repo, root=store)
    assert cfg.status == CM.CONFIG_ABSENT


@pytest.mark.parametrize("strategy", ("profile", "cwd"))
def test_gate_resolution_ok(strategy, tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    core_p = _gate_core_beside(repo)
    open(core_p, "w").write(_gate_valid_core_text({"reviewer": "codex"}))
    if strategy == "profile":
        prof = os.path.join(os.path.dirname(core_p), "review-crew.md")
        open(prof, "w").write("## Model tiers\n")
        cfg = CM.engine_preferences_for_gate(profile_path=prof)
    else:
        cfg = CM.engine_preferences_for_gate(cwd=repo, root=store)
    assert cfg.status == CM.CONFIG_OK
    assert cfg.prefs.get("reviewer") == "codex"


@pytest.mark.parametrize("strategy", ("profile", "cwd"))
def test_gate_resolution_unreadable_directory(strategy, tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    core_p = _gate_core_beside(repo)
    os.makedirs(core_p)
    if strategy == "profile":
        prof = os.path.join(os.path.dirname(core_p), "review-crew.md")
        open(prof, "w").write("## Model tiers\n")
        cfg = CM.engine_preferences_for_gate(profile_path=prof)
    else:
        cfg = CM.engine_preferences_for_gate(cwd=repo, root=store)
    assert cfg.status == CM.CONFIG_UNREADABLE


def test_write_refused_mode_zero_preserves_bytes(tmp_path, monkeypatch):
    if os.geteuid() == 0:
        pytest.skip("root reads mode-000 files")
    import model_tier_overrides as mto

    repo = str(tmp_path)
    store = str(tmp_path / "store")
    monkeypatch.setattr(
        mto,
        "effective_tiers",
        lambda profile_path: {"reviewer": "sonnet"},
    )
    monkeypatch.setattr(mto, "resolve_profile_path", lambda cwd, root=None: "/fake/profile.md")
    core_p = _gate_core_beside(repo)
    body = _gate_valid_core_text({"implementation": "claude"})
    open(core_p, "w").write(body)
    expected = body.encode("utf-8")
    try:
        os.chmod(core_p, 0)
        res = CM.write(
            repo,
            {
                "verifyCommand": "npm test",
                "stackTags": [],
                "threatModel": "t",
                "patterns": "",
                "enginePreferences": {"implementation": "codex"},
            },
            "confirmed",
            root=store,
            now="2026-01-02",
        )
        assert res["action"] == "refused"
        assert res["violations"][0]["reason"] == CM.GATE_REASON_UNREADABLE
    finally:
        os.chmod(core_p, 0o644)
    with open(core_p, "rb") as fh:
        assert fh.read() == expected


def test_write_refused_dangling_symlink_preserves_link(tmp_path, monkeypatch):
    import model_tier_overrides as mto

    repo = str(tmp_path)
    store = str(tmp_path / "store")
    monkeypatch.setattr(
        mto,
        "effective_tiers",
        lambda profile_path: {"reviewer": "sonnet"},
    )
    monkeypatch.setattr(mto, "resolve_profile_path", lambda cwd, root=None: "/fake/profile.md")
    core_p = _gate_core_beside(repo)
    target = "/nonexistent/wo676-preserve"
    os.symlink(target, core_p)
    res = CM.write(
        repo,
        {"verifyCommand": "npm test", "stackTags": [], "threatModel": "t", "patterns": ""},
        "confirmed",
        root=store,
        now="2026-01-02",
    )
    assert res["action"] == "refused"
    assert res["violations"][0]["reason"] == CM.GATE_REASON_UNREADABLE
    assert os.path.islink(core_p)
    assert os.readlink(core_p) == target


def test_write_absent_still_writes_gate_676(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    res = CM.write(
        repo,
        {"verifyCommand": "npm test", "stackTags": ["node"], "threatModel": "t", "patterns": ""},
        "confirmed",
        root=store,
        now="2026-01-01",
    )
    assert res["action"] == "written"


def test_write_readable_still_reuses_gate_676(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    facts = {"verifyCommand": "npm test", "stackTags": ["node"], "threatModel": "t", "patterns": ""}
    CM.write(repo, facts, "confirmed", root=store, now="2026-01-01")
    res = CM.write(repo, facts, "confirmed", root=store, now="2026-01-02")
    assert res["action"] == "reused"


def test_gate_global_candidate_dangling_symlink_unreadable(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    in_repo, global_path = CM._core_candidates(repo, store)
    assert not os.path.exists(in_repo)
    os.makedirs(os.path.dirname(global_path), exist_ok=True)
    os.symlink("/no/such/global-dangle-wo676", global_path)
    cfg = CM.engine_preferences_for_gate(cwd=repo, root=store)
    assert cfg.status == CM.CONFIG_UNREADABLE
    assert global_path in (cfg.detail or "")


def test_gate_global_candidate_directory_unreadable(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    in_repo, global_path = CM._core_candidates(repo, store)
    os.makedirs(os.path.dirname(global_path), exist_ok=True)
    os.makedirs(global_path)
    cfg = CM.engine_preferences_for_gate(cwd=repo, root=store)
    assert cfg.status == CM.CONFIG_UNREADABLE
    assert global_path in (cfg.detail or "")


def test_gate_global_candidate_mode_zero_unreadable(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root reads mode-000 files")
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    in_repo, global_path = CM._core_candidates(repo, store)
    os.makedirs(os.path.dirname(global_path), exist_ok=True)
    open(global_path, "w").write(_gate_valid_core_text({"reviewer": "global"}))
    try:
        os.chmod(global_path, 0)
        cfg = CM.engine_preferences_for_gate(cwd=repo, root=store)
        assert cfg.status == CM.CONFIG_UNREADABLE
        assert global_path in (cfg.detail or "")
    finally:
        os.chmod(global_path, 0o644)


def test_gate_merge_both_present_in_repo_mode_uses_in_repo(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.mode_registry.write_registry(repo, CM.mode_registry.IN_REPO, None, root=store)
    in_repo, global_path = CM._core_candidates(repo, store)
    os.makedirs(os.path.dirname(in_repo), exist_ok=True)
    os.makedirs(os.path.dirname(global_path), exist_ok=True)
    open(in_repo, "w").write(_gate_valid_core_text({"reviewer": "inrepo"}))
    open(global_path, "w").write(_gate_valid_core_text({"reviewer": "global"}))
    cfg = CM.engine_preferences_for_gate(cwd=repo, root=store)
    assert cfg.status == CM.CONFIG_OK
    assert cfg.prefs.get("reviewer") == "inrepo"


def test_gate_merge_both_present_global_mode_uses_global(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.mode_registry.write_registry(repo, CM.mode_registry.GLOBAL, None, root=store)
    in_repo, global_path = CM._core_candidates(repo, store)
    os.makedirs(os.path.dirname(in_repo), exist_ok=True)
    os.makedirs(os.path.dirname(global_path), exist_ok=True)
    open(in_repo, "w").write(_gate_valid_core_text({"reviewer": "inrepo"}))
    open(global_path, "w").write(_gate_valid_core_text({"reviewer": "global"}))
    cfg = CM.engine_preferences_for_gate(cwd=repo, root=store)
    assert cfg.status == CM.CONFIG_OK
    assert cfg.prefs.get("reviewer") == "global"


def test_gate_merge_mode_selected_unreadable_in_repo(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.mode_registry.write_registry(repo, CM.mode_registry.IN_REPO, None, root=store)
    in_repo, global_path = CM._core_candidates(repo, store)
    os.makedirs(os.path.dirname(in_repo), exist_ok=True)
    os.makedirs(os.path.dirname(global_path), exist_ok=True)
    os.makedirs(in_repo)
    open(global_path, "w").write(_gate_valid_core_text({"reviewer": "global"}))
    cfg = CM.engine_preferences_for_gate(cwd=repo, root=store)
    assert cfg.status == CM.CONFIG_UNREADABLE
    assert in_repo in (cfg.detail or "")


def test_gate_merge_mode_selected_unreadable_global(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.mode_registry.write_registry(repo, CM.mode_registry.GLOBAL, None, root=store)
    in_repo, global_path = CM._core_candidates(repo, store)
    os.makedirs(os.path.dirname(in_repo), exist_ok=True)
    os.makedirs(os.path.dirname(global_path), exist_ok=True)
    open(in_repo, "w").write(_gate_valid_core_text({"reviewer": "inrepo"}))
    os.makedirs(global_path)
    cfg = CM.engine_preferences_for_gate(cwd=repo, root=store)
    assert cfg.status == CM.CONFIG_UNREADABLE
    assert global_path in (cfg.detail or "")


def test_gate_merge_inactive_unreadable_does_not_wedge_in_repo_mode(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.mode_registry.write_registry(repo, CM.mode_registry.IN_REPO, None, root=store)
    in_repo, global_path = CM._core_candidates(repo, store)
    os.makedirs(os.path.dirname(in_repo), exist_ok=True)
    os.makedirs(os.path.dirname(global_path), exist_ok=True)
    open(in_repo, "w").write(_gate_valid_core_text({"reviewer": "inrepo"}))
    os.symlink("/no/such/inactive-global-wo676", global_path)
    cfg = CM.engine_preferences_for_gate(cwd=repo, root=store)
    assert cfg.status == CM.CONFIG_OK
    assert cfg.prefs.get("reviewer") == "inrepo"


def test_gate_merge_inactive_unreadable_does_not_wedge_global_mode(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.mode_registry.write_registry(repo, CM.mode_registry.GLOBAL, None, root=store)
    in_repo, global_path = CM._core_candidates(repo, store)
    os.makedirs(os.path.dirname(in_repo), exist_ok=True)
    os.makedirs(os.path.dirname(global_path), exist_ok=True)
    os.makedirs(in_repo)
    open(global_path, "w").write(_gate_valid_core_text({"reviewer": "global"}))
    cfg = CM.engine_preferences_for_gate(cwd=repo, root=store)
    assert cfg.status == CM.CONFIG_OK
    assert cfg.prefs.get("reviewer") == "global"


def test_gate_accessor_matches_core_path_selection(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.mode_registry.write_registry(repo, CM.mode_registry.IN_REPO, None, root=store)
    in_repo, global_path = CM._core_candidates(repo, store)
    os.makedirs(os.path.dirname(in_repo), exist_ok=True)
    os.makedirs(os.path.dirname(global_path), exist_ok=True)
    open(in_repo, "w").write(_gate_valid_core_text({"reviewer": "inrepo"}))
    open(global_path, "w").write(_gate_valid_core_text({"reviewer": "global"}))
    selected = CM.core_path(repo, root=store)
    cfg = CM.engine_preferences_for_gate(cwd=repo, root=store)
    at_selected = CM._classify_core_md_at_path(selected)
    assert at_selected.status == cfg.status
    assert at_selected.prefs == cfg.prefs


_SHOW_IT_BODY = (
    "**Level:** command\n"
    "**What the owner does:** npm run dev (from repo root)\n"
    "**Notes:** optional"
)


def test_parse_core_returns_show_it_surface_when_section_present():
    facts = dict(_CORE_FACTS, showItSurface=_SHOW_IT_BODY)
    text = CM.render_core(facts, "confirmed", "2026-06-26", "2026-06-26")
    got = CM.parse_core(text)
    assert got["showItSurface"] == _SHOW_IT_BODY


def test_parse_core_and_read_return_empty_show_it_when_section_absent(tmp_path):
    text = CM.render_core(dict(_CORE_FACTS), "confirmed", "2026-06-26", "2026-06-26")
    assert CM.parse_core(text)["showItSurface"] == ""
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    assert CM.read(repo, root=store)["showItSurface"] == ""


def test_render_core_omits_show_it_heading_when_empty():
    facts = dict(_CORE_FACTS)
    text = CM.render_core(facts, "confirmed", "2026-06-26", "2026-06-26")
    assert "## Show-it surface" not in text
    golden = (
        "<!-- superheroes-core: schemaVersion=%d status=confirmed "
        "created=2026-06-26 updated=2026-06-26 -->\n\n"
        "## Threat model\n\nsingle-user\n\n"
        "## Canonical patterns\n\n- x: a.ts:1\n\n"
        "```json superheroes-core\n"
        '{\n  "schemaVersion": %d,\n  "verifyCommand": "npm test",\n'
        '  "stackTags": [\n    "node"\n  ],\n  "enginePreferences": {}\n}\n```\n'
        % (CM.SCHEMA_VERSION, CM.SCHEMA_VERSION)
    )
    assert text == golden
    facts["showItSurface"] = ""
    assert CM.render_core(facts, "confirmed", "2026-06-26", "2026-06-26") == golden


def test_parse_core_hand_authored_show_it_section_ordering():
    text = (
        "<!-- superheroes-core: schemaVersion=%d status=confirmed "
        "created=2026-06-26 updated=2026-06-26 -->\n\n"
        "## Threat model\n\nsingle-user\n\n"
        "## Show-it surface\n\n%s\n\n"
        "## Canonical patterns\n\n- x: a.ts:1\n\n"
        "```json superheroes-core\n"
        '{\n  "schemaVersion": %d,\n  "verifyCommand": "npm test",\n'
        '  "stackTags": ["node"],\n  "enginePreferences": {}\n}\n```\n'
        % (CM.SCHEMA_VERSION, _SHOW_IT_BODY, CM.SCHEMA_VERSION)
    )
    got = CM.parse_core(text)
    assert got["showItSurface"] == _SHOW_IT_BODY
    assert CM._section(text, "Threat model") == "single-user"
    assert CM._section(text, "Canonical patterns") == "- x: a.ts:1"


def test_json_block_has_no_show_it_surface_key():
    facts = dict(_CORE_FACTS, showItSurface=_SHOW_IT_BODY)
    text = CM.render_core(facts, "confirmed", "2026-06-26", "2026-06-26")
    block = json.loads(CM._JSON_BLOCK.search(text).group(1))
    assert "showItSurface" not in block


def test_confirm_preserves_show_it_surface_on_provisional_core(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    facts = dict(_CORE_FACTS, showItSurface=_SHOW_IT_BODY)
    CM.write(repo, facts, "provisional", root=store, now="2026-06-26")
    res = CM.confirm(repo, root=store, now="2026-06-28")
    assert res["action"] == "confirmed"
    got = CM.read(repo, root=store)
    assert got["showItSurface"] == _SHOW_IT_BODY


def test_replace_show_it_surface_section_create_replace_clear_preserves_rest():
    base_facts = dict(_CORE_FACTS)
    text = CM.render_core(base_facts, "confirmed", "2026-06-26", "2026-06-26")
    prov = text[: text.index("## Threat model")]
    threat = CM._section(text, "Threat model")
    patterns = CM._section(text, "Canonical patterns")
    json_part = text[text.index("```json superheroes-core") :]

    created = CM.replace_show_it_surface_section(text, _SHOW_IT_BODY)
    assert prov == created[: created.index("## Threat model")]
    assert CM._section(created, "Threat model") == threat
    assert CM._section(created, "Canonical patterns") == patterns
    assert created.endswith(json_part)
    assert CM._section(created, "Show-it surface") == _SHOW_IT_BODY

    replaced = CM.replace_show_it_surface_section(created, _SHOW_IT_BODY + "\nextra")
    assert CM._section(replaced, "Show-it surface") == _SHOW_IT_BODY + "\nextra"
    assert replaced.endswith(json_part)

    cleared = CM.replace_show_it_surface_section(replaced, "")
    assert "## Show-it surface" not in cleared
    assert cleared == text

    manual = (
        prov
        + threat
        + patterns
        + "## Show-it surface\n\nold body\n\n"
        + "   ## Extra notes\n\nkeep indented heading section\n\n"
        + json_part
    )
    fixed = CM.replace_show_it_surface_section(manual, _SHOW_IT_BODY)
    assert CM._section(fixed, "Show-it surface") == _SHOW_IT_BODY
    assert "keep indented heading section" in fixed
    assert CM._section(fixed, "Extra notes") == "keep indented heading section"

    no_section = prov + threat + patterns + json_part
    assert CM.replace_show_it_surface_section(no_section, "") == no_section


def _write_core_for_show_it_tests(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    return repo, store


def test_write_show_it_surface_written_and_parses(tmp_path):
    repo, store = _write_core_for_show_it_tests(tmp_path)
    res = CM.write_show_it_surface(repo, _SHOW_IT_BODY, root=store)
    assert res["action"] == "written"
    got = CM.read(repo, root=store)
    assert got["showItSurface"] == _SHOW_IT_BODY
    assert CM.parse_core(open(CM.core_path(repo, store)).read()) is not None


def test_write_show_it_surface_succeeds_with_json_word_and_subheading_in_prose(tmp_path):
    repo, store = _write_core_for_show_it_tests(tmp_path)
    body = (
        _SHOW_IT_BODY
        + "\nNotes: deploy emits json artifacts.\n"
        + "### Local setup\n\nextra detail\n"
    )
    res = CM.write_show_it_surface(repo, body, root=store)
    assert res["action"] == "written"
    assert CM.read(repo, root=store)["showItSurface"] == body.strip()


def test_write_show_it_surface_noop_when_unchanged(tmp_path):
    repo, store = _write_core_for_show_it_tests(tmp_path)
    CM.write_show_it_surface(repo, _SHOW_IT_BODY, root=store)
    res = CM.write_show_it_surface(repo, _SHOW_IT_BODY, root=store)
    assert res["action"] == "noop"


def test_write_show_it_surface_clear_returns_none_level(tmp_path):
    repo, store = _write_core_for_show_it_tests(tmp_path)
    CM.write_show_it_surface(repo, _SHOW_IT_BODY, root=store)
    res = CM.write_show_it_surface(repo, "", root=store)
    assert res["action"] == "written"
    assert CM.read(repo, root=store)["showItSurface"] == ""


def test_write_show_it_surface_refused_unparseable_core(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.mode_registry.ensure_project_store(repo, store)
    path = CM.core_path(repo, store)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write("not a core.md\n")
    res = CM.write_show_it_surface(repo, _SHOW_IT_BODY, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.SHOW_IT_REASON_UNPARSEABLE


def test_write_show_it_surface_refused_absent_core(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.mode_registry.ensure_project_store(repo, store)
    res = CM.write_show_it_surface(repo, _SHOW_IT_BODY, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.SHOW_IT_REASON_ABSENT


def test_write_show_it_surface_refused_prose_with_heading(tmp_path):
    repo, store = _write_core_for_show_it_tests(tmp_path)
    bad = _SHOW_IT_BODY + "\n## Threat model\n\ninjected\n"
    res = CM.write_show_it_surface(repo, bad, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.SHOW_IT_REASON_PROSE_FORBIDDEN
    assert CM.read(repo, root=store)["showItSurface"] == ""


def test_write_show_it_surface_refused_prose_with_json_fence(tmp_path):
    repo, store = _write_core_for_show_it_tests(tmp_path)
    bad = "**Level:** command\n```json superheroes-core\n{}\n```\n"
    res = CM.write_show_it_surface(repo, bad, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.SHOW_IT_REASON_PROSE_FORBIDDEN


def test_write_show_it_surface_refused_injected_fence_not_at_line_start(tmp_path):
    """D1: unanchored parse_core + field equality misses int/float respelling in injected block."""
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    facts = dict(_CORE_FACTS, enginePreferences={"timeout": 45})
    CM.write(repo, facts, "confirmed", root=store, now="2026-06-26")
    path = CM.core_path(repo, store)
    before = open(path, encoding="utf-8").read()
    bad = (
        _SHOW_IT_BODY
        + "\nx```json superheroes-core\n"
        + '{\n  "schemaVersion": 2,\n  "verifyCommand": "npm test",\n'
        + '  "stackTags": ["node"],\n  "enginePreferences": {"timeout": 45.0}\n}\n```\n'
    )
    res = CM.write_show_it_surface(repo, bad, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.SHOW_IT_REASON_ROUND_TRIP
    after = open(path, encoding="utf-8").read()
    assert after == before


def test_write_show_it_surface_refused_no_json_fence(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.mode_registry.ensure_project_store(repo, store)
    path = CM.core_path(repo, store)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(
        "<!-- superheroes-core: schemaVersion=2 status=confirmed "
        "created=2026-06-26 updated=2026-06-26 -->\n\n"
        "## Threat model\n\nx\n\n"
    )
    res = CM.write_show_it_surface(repo, _SHOW_IT_BODY, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == CM.SHOW_IT_REASON_UNPARSEABLE


def test_write_show_it_surface_deferred_lock_contended(tmp_path, monkeypatch):
    repo, store = _write_core_for_show_it_tests(tmp_path)
    from contextlib import contextmanager

    @contextmanager
    def _contended(cwd, root=None):
        yield False

    monkeypatch.setattr(CM.mode_registry, "config_lock", _contended)
    res = CM.write_show_it_surface(repo, _SHOW_IT_BODY, root=store)
    assert res["action"] == "deferred"
    assert CM.read(repo, root=store)["showItSurface"] == ""


def test_write_show_it_surface_deferred_store_unwritable(tmp_path, monkeypatch):
    repo, store = _write_core_for_show_it_tests(tmp_path)
    monkeypatch.setattr(CM.mode_registry, "ensure_project_store", lambda cwd, root=None: None)
    res = CM.write_show_it_surface(repo, _SHOW_IT_BODY, root=store)
    assert res["action"] == "deferred"


def test_write_show_it_surface_pending_cleared_only_on_real_write(tmp_path, monkeypatch):
    repo, store = _write_core_for_show_it_tests(tmp_path)
    from contextlib import contextmanager

    @contextmanager
    def _contended(cwd, root=None):
        yield False

    monkeypatch.setattr(CM.mode_registry, "config_lock", _contended)
    res = CM.write_show_it_surface(repo, _SHOW_IT_BODY, root=store)
    assert res["action"] == "deferred"
    assert os.path.isfile(CM._pending_path(repo, store))
    monkeypatch.undo()
    res = CM.write_show_it_surface(repo, _SHOW_IT_BODY, root=store)
    assert res["action"] == "written"
    assert not os.path.isfile(CM._pending_path(repo, store))
    CM.mark_pending(repo, store, detail={"reason": "test"})
    res = CM.write_show_it_surface(repo, _SHOW_IT_BODY, root=store)
    assert res["action"] == "noop"
    assert os.path.isfile(CM._pending_path(repo, store))


def test_write_show_it_surface_behind_refuses(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    facts = dict(_CORE_FACTS)
    text = CM.render_core(facts, "confirmed", "2026-06-26", "2026-06-26")
    text = text.replace(
        '"schemaVersion": %d' % CM.SCHEMA_VERSION,
        '"schemaVersion": %d' % (CM.SCHEMA_VERSION + 1),
        1,
    )
    text = text.replace(
        "schemaVersion=%d" % CM.SCHEMA_VERSION,
        "schemaVersion=%d" % (CM.SCHEMA_VERSION + 1),
        1,
    )
    CM.mode_registry.ensure_project_store(repo, store)
    path = CM.core_path(repo, store)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(text)
    res = CM.write_show_it_surface(repo, _SHOW_IT_BODY, root=store)
    assert res["action"] == "behind"
    assert CM.read(repo, root=store)["showItSurface"] == ""


def test_cli_write_show_it_from_stdin(tmp_path, capsys, monkeypatch):
    import io

    repo, store = _write_core_for_show_it_tests(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(_SHOW_IT_BODY))
    rc = CM.main(["write-show-it", "--cwd", repo, "--root", store])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["action"] == "written"
    assert CM.read(repo, root=store)["showItSurface"] == _SHOW_IT_BODY
