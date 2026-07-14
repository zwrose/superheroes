# plugins/superheroes/lib/tests/test_core_md.py
"""Conformance: shared core.md calibration brain (CONVENTIONS §2.1/§2.2/§4.2/§4.4)."""
import importlib.util
import json
import os
import sys

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


_REVIEW_PROFILE = """<!-- review-profile · managed by review-crew · schema 1 -->
schema: 1
status: stable

## Project
node app

## Threat model
multi-tenant

## Verify
command: npm test

## Scope exclusions
- none

## Focus hints
- security: authz

## Canonical patterns
- auth: src/auth.ts:10

## Conventions
See CLAUDE.md.
"""

_TEST_PILOT_PROFILE = """# test-pilot profile — app

<!-- provenance: plugin-version=0.2.0 profile-version=1 status=stable created=2026-06-26 updated=2026-06-26 -->

## App launch
- Dev command: `npm run dev`

## Auth strategy
test-user credentials

## Seed surfaces
- DB: env DB_URL

## Browser tool order
chrome-devtools

## Machine-readable config

```json test-pilot-config
{"schemaVersion": 1, "baseUrl": "http://localhost:3000"}
```
"""


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
    # and migrate_on_read() both refuse to rewrite a behind record; confirm() must too.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _write_core(repo, CM.SCHEMA_VERSION + 1, status="provisional")  # newer schema, provisional
    core_p = os.path.join(repo, ".claude", "superheroes", "core.md")
    before = open(core_p).read()
    res = CM.confirm(repo, root=store, now="2026-06-28")
    assert res["action"] == "behind"
    assert open(core_p).read() == before  # file untouched — not downgraded, not re-rendered


def test_classify_standard_review_profile():
    assert CM.classify(_REVIEW_PROFILE, "review-crew") == "standard"


def test_classify_standard_test_pilot_profile():
    assert CM.classify(_TEST_PILOT_PROFILE, "test-pilot") == "standard"


def test_classify_ambiguous_when_shared_fact_unlocatable():
    # FR-9: the verify command sits under a heading the system does not recognize → ambiguous.
    hand_edited = _REVIEW_PROFILE.replace("## Verify", "## How we check")
    assert CM.classify(hand_edited, "review-crew") == "ambiguous"


def test_split_review_profile_routes_shared_and_layer():
    core_facts, layer = CM.split_profile(_REVIEW_PROFILE, "review-crew")
    assert core_facts["verifyCommand"] == "npm test"
    assert core_facts["threatModel"] == "multi-tenant"
    assert "src/auth.ts:10" in core_facts["patterns"]
    # hero sections land in the layer, shared ones do not
    assert "## Scope exclusions" in layer
    assert "## Focus hints" in layer
    assert "## Threat model" not in layer
    assert "## Verify" not in layer


def test_split_test_pilot_carries_machine_block_verbatim():
    core_facts, layer = CM.split_profile(_TEST_PILOT_PROFILE, "test-pilot")
    # the hero machine block survives byte-for-byte in the layer
    assert "```json test-pilot-config" in layer
    assert '"baseUrl": "http://localhost:3000"' in layer
    assert "## App launch" in layer
    assert "## Auth strategy" in layer


def test_split_preserves_unrecognized_section_verbatim():
    extra = _REVIEW_PROFILE + "\n## Weird custom section\n\nkeep me exactly\n"
    _core, layer = CM.split_profile(extra, "review-crew")
    assert "## Weird custom section" in layer
    assert "keep me exactly" in layer


def _hero_layer_path(repo, hero):
    return os.path.join(repo, ".claude", "superheroes", hero + ".md")


def _legacy_review_path(repo):
    d = os.path.join(repo, ".claude")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "review-profile.md")


def _seed_legacy_global_profile(repo, hero_root):
    """Seed a legacy review-profile.md in the review-crew global store (not unified layer)."""
    import store_core as sc
    ident = sc.derive_identifiers(repo)
    eid = ident["gitdir_hash"]
    entry = os.path.join(hero_root, "entries", eid)
    os.makedirs(entry, exist_ok=True)
    if not os.path.exists(os.path.join(entry, "keys.json")):
        sc.write_keys_json(entry, ident)
    sc.write_pointer(hero_root, ident["gitdir_hash"], eid)
    if ident["remote_hash"]:
        sc.write_pointer(hero_root, ident["remote_hash"], eid)
    return os.path.join(entry, "review-profile.md")


def test_migrate_global_standard_splits_and_retires_legacy(tmp_path):
    # Global mode (no repo root override / nongit): write core.md + layer, remove legacy.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE)
    res = CM.migrate_on_read(repo, "review-crew", root=store)
    assert res["action"] == "migrated"
    # core.md exists and carries the shared facts
    got = CM.read(repo, root=store)
    assert got is not None and got["verifyCommand"] == "npm test"
    # the hero layer exists and carries hero content
    layer = open(_hero_layer_path(repo, "review-crew")).read()
    assert "## Scope exclusions" in layer
    # legacy removed (retired only after both new files exist)
    assert not os.path.exists(legacy)


def test_migrate_noop_when_no_legacy(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    assert CM.migrate_on_read(repo, "review-crew", root=store)["action"] == "noop"


def test_migrate_ambiguous_no_write(tmp_path):
    # FR-9: ambiguous profile → no write, legacy untouched, action ambiguous.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE.replace("## Verify", "## How we check"))
    res = CM.migrate_on_read(repo, "review-crew", root=store)
    assert res["action"] == "ambiguous"
    assert CM.read(repo, root=store) is None
    assert os.path.exists(legacy)  # untouched


def test_migrate_noop_when_core_already_present(tmp_path):
    # A usable core.md already exists → do not re-migrate even if a legacy file lingers absent.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _write_core(repo, CM.SCHEMA_VERSION)  # from Task 3 helper
    assert CM.migrate_on_read(repo, "review-crew", root=store)["action"] == "noop"


def test_migrate_global_mode_legacy_profile_is_found_and_migrated(tmp_path, monkeypatch):
    # FR-8: a GLOBAL-mode legacy profile lives under review-crew's own store (NOT in the repo)
    # — _legacy_path must resolve it via the hero resolver, so global-mode migration is reachable.
    repo = str(tmp_path / "repo")
    os.makedirs(repo, exist_ok=True)
    store = str(tmp_path / "store")
    hero_root = str(tmp_path / "review_store")  # review-crew's own global store root
    # seed a global review-crew profile (hermetic: point review_store.store_root at hero_root)
    import review_store
    monkeypatch.setattr(review_store, "store_root", lambda: hero_root)
    prof_path = _seed_legacy_global_profile(repo, hero_root)
    open(prof_path, "w").write(_REVIEW_PROFILE)
    # _legacy_path resolves the global profile path (NOT the in-repo .claude/review-profile.md)
    legacy = CM._legacy_path(repo, "review-crew")
    assert legacy == prof_path
    assert os.path.isfile(legacy)
    res = CM.migrate_on_read(repo, "review-crew", root=store)
    assert res["action"] == "migrated"
    assert CM.read(repo, root=store)["verifyCommand"] == "npm test"
    assert not os.path.exists(legacy)  # global legacy retired


import subprocess


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


def _git_repo(tmp_path):
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    return repo


def _force_in_repo(repo, store):
    import mode_registry as mr
    mr.write_registry(repo, mr.IN_REPO, None, root=store)


def test_migrate_in_repo_commits_only_calibration_paths(tmp_path):
    repo = _git_repo(tmp_path)
    store = str(tmp_path / "store")
    _force_in_repo(repo, store)
    # a tracked, committed legacy profile (git commit --only records no deletion for an untracked one)
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE)
    _git(repo, "add", ".claude/review-profile.md")
    _git(repo, "commit", "-q", "-m", "seed legacy")
    # an unrelated staged change + an unrelated working-tree change must NOT be swept
    open(os.path.join(repo, "unrelated.txt"), "w").write("staged change")
    _git(repo, "add", "unrelated.txt")
    open(os.path.join(repo, "other.txt"), "w").write("worktree change")
    # ALSO stage an edit to a NAMED calibration path (the legacy profile): `git commit --only`
    # must commit the migrator's working-tree state (its DELETION), never this staged content.
    open(legacy, "a").write("\n<!-- staged-but-uncommitted edit to a named path -->\n")
    _git(repo, "add", ".claude/review-profile.md")

    res = CM.migrate_on_read(repo, "review-crew", root=store)
    assert res["action"] == "migrated"

    # the migration commit names ONLY the calibration paths
    changed = _git(repo, "show", "--name-status", "--format=", "HEAD").stdout.split()
    names = set(changed)
    assert ".claude/superheroes/core.md" in names
    assert ".claude/superheroes/review-crew.md" in names
    assert ".claude/review-profile.md" in names  # deletion recorded
    assert "unrelated.txt" not in names
    assert "other.txt" not in names
    # the unrelated change is still staged (not committed)
    assert "unrelated.txt" in _git(repo, "diff", "--cached", "--name-only").stdout
    # --only ignored the staged modify and recorded the legacy DELETION (not a modification)
    legacy_line = [l for l in _git(repo, "show", "--name-status", "--format=", "HEAD").stdout.splitlines()
                   if "review-profile.md" in l]
    assert legacy_line and legacy_line[0].split()[0] == "D"


def test_migrate_in_repo_records_legacy_deletion(tmp_path):
    repo = _git_repo(tmp_path)
    store = str(tmp_path / "store")
    _force_in_repo(repo, store)
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE)
    _git(repo, "add", ".claude/review-profile.md")
    _git(repo, "commit", "-q", "-m", "seed legacy")
    CM.migrate_on_read(repo, "review-crew", root=store)
    status = _git(repo, "show", "--name-status", "--format=", "HEAD").stdout
    assert "D\t.claude/review-profile.md" in status or "D .claude/review-profile.md" in status


def test_resume_both_files_present_completes_retirement(tmp_path):
    # UFR-5/FR-11: a prior run wrote both new files but a still-present legacy lingers →
    # on re-entry, do NOT re-split; complete retirement (unlink legacy) and report completed.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE)
    # pre-place both new files (as a prior interrupted run would have)
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    CM_facts = {"verifyCommand": "npm test", "stackTags": [], "threatModel": "x", "patterns": ""}
    open(os.path.join(d, "core.md"), "w").write(
        CM.render_core(CM_facts, "provisional", "2026-06-26", "2026-06-26"))
    open(os.path.join(d, "review-crew.md"), "w").write(
        CM._render_layer("## Scope exclusions\n- none\n", "review-crew", "provisional", "2026-06-26"))
    res = CM.migrate_on_read(repo, "review-crew", root=store)
    assert res["action"] == "completed"
    assert not os.path.exists(legacy)  # retired
    # and a subsequent read is a plain noop
    assert CM.migrate_on_read(repo, "review-crew", root=store)["action"] == "noop"


def test_migrate_in_repo_with_out_of_repo_legacy_commits_and_records(tmp_path, monkeypatch):
    # #121 Part E: IN_REPO registry but the legacy lives in review-crew's GLOBAL store (out-of-repo,
    # a realistic mixed state). The commit must land core+layer (not fail on an out-of-repo
    # pathspec) and report `migrated` HONESTLY — never a false `migrated` with calibration left
    # staged-but-uncommitted in the developer's index.
    repo = _git_repo(tmp_path)
    store = str(tmp_path / "store")
    _force_in_repo(repo, store)
    open(os.path.join(repo, "README"), "w").write("x\n")  # give the repo a HEAD
    _git(repo, "add", "README")
    _git(repo, "commit", "-q", "-m", "init")
    hero_root = str(tmp_path / "review_store")
    import review_store
    monkeypatch.setattr(review_store, "store_root", lambda: hero_root)
    prof_path = _seed_legacy_global_profile(repo, hero_root)
    open(prof_path, "w").write(_REVIEW_PROFILE)
    legacy = CM._legacy_path(repo, "review-crew")
    assert legacy == prof_path  # out-of-repo (global hero store)
    res = CM.migrate_on_read(repo, "review-crew", root=store)
    assert res["action"] == "migrated"
    # the migration commit actually landed core+layer in HEAD
    names = set(_git(repo, "show", "--name-status", "--format=", "HEAD").stdout.split())
    assert ".claude/superheroes/core.md" in names
    assert ".claude/superheroes/review-crew.md" in names
    # out-of-repo legacy retired (plain unlink, not a git pathspec)
    assert not os.path.exists(prof_path)
    # NO false success: nothing left staged-but-uncommitted
    staged = _git(repo, "diff", "--cached", "--name-only").stdout
    assert ".claude/superheroes" not in staged


def test_resume_empty_placeholder_rescues_rich_legacy(tmp_path):
    # Part D / #121 (DATA LOSS): the destination core + layer exist only as EMPTY placeholders
    # (a botched/interrupted set-up) while a RICH legacy still holds the only copy of the real
    # threat model + patterns. The RESUME branch must NOT retire the legacy and keep the empty
    # core — it re-derives losslessly from the legacy, THEN retires it.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE)  # rich: verify npm test, threat multi-tenant, patterns
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    empty = {"verifyCommand": "", "stackTags": [], "threatModel": "", "patterns": ""}
    open(os.path.join(d, "core.md"), "w").write(
        CM.render_core(empty, "provisional", "2026-06-26", "2026-06-26"))
    open(os.path.join(d, "review-crew.md"), "w").write(
        CM._render_layer("", "review-crew", "provisional", "2026-06-26"))  # empty body
    res = CM.migrate_on_read(repo, "review-crew", root=store)
    # the rich content was rescued into the destination — not lost
    got = CM.read(repo, root=store)
    assert got is not None
    assert got["verifyCommand"] == "npm test"
    assert "multi-tenant" in got["threatModel"]
    layer = open(_hero_layer_path(repo, "review-crew")).read()
    assert "## Scope exclusions" in layer
    # legacy retired only AFTER its content was secured
    assert not os.path.exists(legacy)
    assert res["action"] in ("migrated", "completed")


def test_resume_empty_placeholder_refuses_to_destroy_ambiguous_legacy(tmp_path):
    # Part D / #121: an ambiguous (non-auto-derivable) legacy must NEVER be silently deleted over
    # an empty placeholder — surface it for hand-reconcile, legacy preserved.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE.replace("## Verify", "## How we check"))  # ambiguous
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    empty = {"verifyCommand": "", "stackTags": [], "threatModel": "", "patterns": ""}
    open(os.path.join(d, "core.md"), "w").write(
        CM.render_core(empty, "provisional", "2026-06-26", "2026-06-26"))
    open(os.path.join(d, "review-crew.md"), "w").write(
        CM._render_layer("", "review-crew", "provisional", "2026-06-26"))
    res = CM.migrate_on_read(repo, "review-crew", root=store)
    assert res["action"] == "ambiguous"
    assert os.path.exists(legacy)  # NOT destroyed


def test_resume_core_present_layer_absent_rederives(tmp_path):
    # UFR-5: a crash between (1) and (2) left core.md but no layer → re-derive the split from
    # the still-present legacy profile (never lose the layer).
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE)
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "core.md"), "w").write(
        CM.render_core({"verifyCommand": "npm test", "stackTags": [], "threatModel": "x",
                        "patterns": ""}, "provisional", "2026-06-26", "2026-06-26"))
    # layer is ABSENT
    assert not os.path.exists(_hero_layer_path(repo, "review-crew"))
    res = CM.migrate_on_read(repo, "review-crew", root=store)
    assert res["action"] in ("migrated", "completed")
    layer = open(_hero_layer_path(repo, "review-crew")).read()
    assert "## Scope exclusions" in layer  # re-derived, not lost
    assert not os.path.exists(legacy)


def test_kill_after_core_before_layer_leaves_legacy_recoverable(tmp_path, monkeypatch):
    # UFR-5: crash after core.md write, before layer write → legacy still present (recoverable).
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE)
    real_write = CM.store_core.atomic_write

    def _boom(path, text, *a, **k):
        # Target the LAYER write specifically (store setup + core.md succeed; the layer fails)
        # — key on the path, not a fragile call counter (meta.json/registry.json are written
        # first by store setup + the mode backfill, so a "first call = core.md" assumption is
        # wrong). This still exercises the exact core→layer crash boundary the test intends.
        if path.endswith("review-crew.md"):
            raise OSError("killed before layer")
        return real_write(path, text, *a, **k)

    monkeypatch.setattr(CM.store_core, "atomic_write", _boom)
    res = CM.migrate_on_read(repo, "review-crew", root=store)
    assert res["action"] == "deferred"
    assert os.path.exists(legacy)  # legacy never removed → fully recoverable


def test_unlink_failure_defers_legacy_preserved(tmp_path, monkeypatch):
    # UFR-5: the unlink step (3) fails → deferred, legacy still present, no half-state.
    # (Ordering is write→write→unlink→commit, so this is the unlink boundary, not a
    # "post-commit" one — there is no kill-after-commit-before-unlink window.)
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE)
    monkeypatch.setattr(CM.os, "unlink", lambda p: (_ for _ in ()).throw(OSError("unlink failed")))
    res = CM.migrate_on_read(repo, "review-crew", root=store)
    assert res["action"] == "deferred"
    assert os.path.exists(legacy)


def test_inrepo_fresh_migrate_commit_failure_defers_then_retry_records(tmp_path, monkeypatch):
    # FR-8/UFR-4/UFR-5 (round-2 review-tasks finding): an in-repo fresh migration whose COMMIT
    # fails must NOT be left silently uncommitted — it returns `deferred` + a
    # calibration-not-saved marker, and the NEXT read RETRIES the outstanding commit until
    # `_migration_recorded` confirms it landed.
    repo = _git_repo(tmp_path)
    store = str(tmp_path / "store")
    _force_in_repo(repo, store)
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE)
    _git(repo, "add", ".claude/review-profile.md")
    _git(repo, "commit", "-q", "-m", "seed legacy")
    core_p = os.path.join(repo, ".claude", "superheroes", "core.md")
    real_run_git = CM.store_core.run_git

    def _fail_commit(repo_root, *a):
        if a and a[0] == "commit":
            return None  # simulate a nonzero git exit on commit only
        return real_run_git(repo_root, *a)

    monkeypatch.setattr(CM.store_core, "run_git", _fail_commit)
    r1 = CM.migrate_on_read(repo, "review-crew", root=store)
    assert r1["action"] == "deferred"                      # commit failed → NOT a silent success
    assert os.path.isfile(core_p) and not os.path.exists(legacy)  # split landed on disk
    pending = CM._pending_path(repo, store)
    assert os.path.isfile(pending)                         # calibration-not-saved marker set
    # retry with git working → the outstanding commit is recorded and the marker cleared
    monkeypatch.setattr(CM.store_core, "run_git", real_run_git)
    r2 = CM.migrate_on_read(repo, "review-crew", root=store)
    assert r2["action"] in ("completed", "migrated")
    assert CM._migration_recorded(repo, core_p, legacy)
    assert not os.path.isfile(pending)


def test_migrate_deferred_when_lock_contended(tmp_path, monkeypatch):
    # UFR-4: contended lock → deferred, legacy untouched, no raise.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE)
    from contextlib import contextmanager

    @contextmanager
    def _contended(cwd, root=None):
        yield False

    monkeypatch.setattr(CM.mode_registry, "config_lock", _contended)
    res = CM.migrate_on_read(repo, "review-crew", root=store)
    assert res["action"] == "deferred"
    assert os.path.exists(legacy)


def test_resume_completed_branch_git_failure_yields_deferred(tmp_path, monkeypatch):
    # UFR-4: in the `completed` (retire-only) branch, a FORCED git failure must yield
    # `deferred`, NOT a false `completed` — run_git returns None on any nonzero exit.
    repo = _git_repo(tmp_path)
    store = str(tmp_path / "store")
    _force_in_repo(repo, store)  # in-repo so the retirement commit path runs
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE)
    _git(repo, "add", ".claude/review-profile.md")
    _git(repo, "commit", "-q", "-m", "seed legacy")
    # pre-place both new files (a prior interrupted run) so the resume rule takes the
    # `completed` branch and tries to record the legacy deletion.
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "core.md"), "w").write(
        CM.render_core({"verifyCommand": "npm test", "stackTags": [], "threatModel": "x",
                        "patterns": ""}, "provisional", "2026-06-26", "2026-06-26"))
    open(os.path.join(d, "review-crew.md"), "w").write(
        CM._render_layer("## Scope exclusions\n- none\n", "review-crew", "provisional", "2026-06-26"))
    # force ONLY the retirement commit to fail; delegate every other git call to the real one
    real_run_git = CM.store_core.run_git

    def _fail_commit(repo_root, *a):
        if a and a[0] == "commit":
            return None  # simulate a nonzero git exit
        return real_run_git(repo_root, *a)

    monkeypatch.setattr(CM.store_core, "run_git", _fail_commit)
    res = CM.migrate_on_read(repo, "review-crew", root=store)
    assert res["action"] == "deferred"  # NOT "completed"


def test_resolve_shared_migrates_then_reads(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE)
    got = CM.resolve_shared(repo, root=store)
    assert got is not None and got["verifyCommand"] == "npm test"
    assert not os.path.exists(legacy)  # migration fired


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


def test_cli_migrate_runs(tmp_path, capsys):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE)
    rc = CM.main(["migrate", "--cwd", repo, "--root", store, "--hero", "review-crew"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["action"] == "migrated"


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


def test_content_completeness_review_profile_roundtrip(tmp_path):
    # Loss-free guarantee (justifies removing the legacy file): every shared fact lands in
    # core.md; every recognized hero section survives in the layer; an unrecognized section
    # survives verbatim.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    legacy = _legacy_review_path(repo)
    profile = _REVIEW_PROFILE + "\n## Weird custom\n\nverbatim please\n"
    open(legacy, "w").write(profile)
    assert CM.migrate_on_read(repo, "review-crew", root=store)["action"] == "migrated"
    core = CM.read(repo, root=store)
    assert core["verifyCommand"] == "npm test"
    assert core["threatModel"] == "multi-tenant"
    assert "src/auth.ts:10" in core["patterns"]
    layer = open(_hero_layer_path(repo, "review-crew")).read()
    assert "## Scope exclusions" in layer
    assert "## Focus hints" in layer
    assert "## Weird custom" in layer and "verbatim please" in layer


def test_content_completeness_test_pilot_machine_block_byte_identical(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    d = os.path.join(repo, ".claude", "test-pilot")
    os.makedirs(d, exist_ok=True)
    legacy = os.path.join(d, "profile.md")
    open(legacy, "w").write(_TEST_PILOT_PROFILE)
    assert CM.migrate_on_read(repo, "test-pilot", root=store)["action"] == "migrated"
    layer = open(_hero_layer_path(repo, "test-pilot")).read()
    assert "```json test-pilot-config" in layer
    assert '"baseUrl": "http://localhost:3000"' in layer


def test_fr11_edited_layer_survives_reread(tmp_path):
    # FR-11: a layer hand-edited AFTER migration is not overwritten on the next read.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE)
    CM.migrate_on_read(repo, "review-crew", root=store)
    layer_p = _hero_layer_path(repo, "review-crew")
    edited = open(layer_p).read() + "\n## My hand edit\n\nkeep this\n"
    open(layer_p, "w").write(edited)
    # next read: noop (both files present, legacy gone) → layer untouched
    assert CM.migrate_on_read(repo, "review-crew", root=store)["action"] == "noop"
    assert open(layer_p).read() == edited


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


def test_migrate_unknown_hero_is_noop(tmp_path):
    # code-002: an unknown hero has no legacy profile → noop, never a TypeError from a None
    # pathspec reaching _migration_recorded/run_git.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    assert CM.migrate_on_read(repo, "bogus-hero", root=store)["action"] == "noop"


def test_relocate_file_copies_then_unlinks_atomically(tmp_path):
    src = tmp_path / "a.txt"; src.write_text("hello")
    dst = tmp_path / "sub" / "b.txt"
    CM.relocate_file(str(src), str(dst))
    assert dst.read_text() == "hello" and not src.exists()


def test_resume_placeholder_with_out_of_repo_legacy_rescues_and_commits(tmp_path, monkeypatch):
    # #121 Part F: IN_REPO registry, EMPTY placeholder core+layer, and a RICH legacy in the GLOBAL
    # (out-of-repo) store. The RESUME branch must rescue the content (Part D) AND commit it without
    # passing the out-of-repo legacy to git (Part E) — the rich global profile is never destroyed
    # over a placeholder, and the migration is recorded, not left dirty.
    repo = _git_repo(tmp_path)
    store = str(tmp_path / "store")
    _force_in_repo(repo, store)
    open(os.path.join(repo, "README"), "w").write("x\n")
    _git(repo, "add", "README")
    _git(repo, "commit", "-q", "-m", "init")
    hero_root = str(tmp_path / "review_store")
    import review_store
    monkeypatch.setattr(review_store, "store_root", lambda: hero_root)
    prof_path = _seed_legacy_global_profile(repo, hero_root)
    open(prof_path, "w").write(_REVIEW_PROFILE)
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    empty = {"verifyCommand": "", "stackTags": [], "threatModel": "", "patterns": ""}
    open(os.path.join(d, "core.md"), "w").write(
        CM.render_core(empty, "provisional", "2026-06-26", "2026-06-26"))
    open(os.path.join(d, "review-crew.md"), "w").write(
        CM._render_layer("", "review-crew", "provisional", "2026-06-26"))
    CM.migrate_on_read(repo, "review-crew", root=store)
    got = CM.read(repo, root=store)
    assert got["verifyCommand"] == "npm test"          # rescued, not lost
    assert "multi-tenant" in got["threatModel"]
    assert "## Scope exclusions" in open(_hero_layer_path(repo, "review-crew")).read()
    assert not os.path.exists(prof_path)               # rich global legacy retired safely
    names = set(_git(repo, "show", "--name-status", "--format=", "HEAD").stdout.split())
    assert ".claude/superheroes/core.md" in names      # committed, not left dirty
    assert ".claude/superheroes" not in _git(repo, "diff", "--cached", "--name-only").stdout


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


def test_resume_ambiguous_over_placeholder_marks_pending(tmp_path):
    # /code-review #9: refusing to retire an ambiguous legacy over a placeholder must drop a
    # calibration-pending marker so mode_reconcile surfaces it for hand-reconcile.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE.replace("## Verify", "## How we check"))  # ambiguous
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    empty = {"verifyCommand": "", "stackTags": [], "threatModel": "", "patterns": ""}
    open(os.path.join(d, "core.md"), "w").write(
        CM.render_core(empty, "provisional", "2026-06-26", "2026-06-26"))
    open(os.path.join(d, "review-crew.md"), "w").write(
        CM._render_layer("", "review-crew", "provisional", "2026-06-26"))
    res = CM.migrate_on_read(repo, "review-crew", root=store)
    assert res["action"] == "ambiguous"
    assert os.path.exists(legacy)                       # preserved
    assert os.path.isfile(CM._pending_path(repo, store))  # surfaced as calibration-not-saved


def test_resume_rescue_preserves_confirmed_status_and_created(tmp_path):
    # /code-review #10: rescuing an empty placeholder must NOT downgrade a confirmed status or
    # reset the created date.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    legacy = _legacy_review_path(repo)
    open(legacy, "w").write(_REVIEW_PROFILE)
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    empty = {"verifyCommand": "", "stackTags": [], "threatModel": "", "patterns": ""}
    open(os.path.join(d, "core.md"), "w").write(
        CM.render_core(empty, "confirmed", "2026-06-01", "2026-06-01"))
    open(os.path.join(d, "review-crew.md"), "w").write(
        CM._render_layer("", "review-crew", "confirmed", "2026-06-01"))
    CM.migrate_on_read(repo, "review-crew", root=store)
    got = CM.read(repo, root=store)
    assert got["verifyCommand"] == "npm test"   # rescued
    assert got["status"] == "confirmed"          # NOT downgraded
    assert got["created"] == "2026-06-01"        # preserved


# ---------------------------------------------------------------------------
# #428 — migrate_on_read committed a pure DELETION of the tracked calibration
# LAYER (.claude/superheroes/test-pilot.md) with no replacement, losing a
# migrated project's calibration. Two-part defense: (1) the migration commit
# never records a deletion of core/layer; (2) _legacy_path never returns the
# unified layer as a "legacy" migration source (the trigger).
# ---------------------------------------------------------------------------

_TP_LAYER_BODY = (
    "## App launch\n\nnpm run dev\n\n"
    "## Machine-readable config\n\n"
    "```json test-pilot-config\n"
    '{"schemaVersion": 1, "baseUrl": "http://localhost:3000"}\n'
    "```\n"
)


def _write_migrated_test_pilot(repo, *, status="confirmed", stamp="2026-07-01"):
    """A MIGRATED test-pilot project: core.md + the unified test-pilot.md layer (with the
    test-pilot-config block store.resolve() keys on), NO legacy profile.md. Returns the layer path."""
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    core_facts = {"verifyCommand": "npm test", "stackTags": ["node"],
                  "threatModel": "xss", "patterns": "hooks"}
    open(os.path.join(d, "core.md"), "w").write(
        CM.render_core(core_facts, status, stamp, stamp))
    layer_p = os.path.join(d, "test-pilot.md")
    open(layer_p, "w").write(CM._render_layer(_TP_LAYER_BODY, "test-pilot", status, stamp))
    return layer_p


def test_migrated_layer_is_never_a_legacy_migration_source(tmp_path, monkeypatch):
    # #428 direction 2 (trigger): a migrated project's unified layer must NEVER be treated as a
    # legacy profile. store.resolve() returns profileSource=="layer" with the layer in `profile`;
    # _legacy_path must NOT hand that back (its #123 contract: "never the unified layer").
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    monkeypatch.setenv("TEST_PILOT_STORE_ROOT", str(tmp_path / "tp_store"))
    layer_p = _write_migrated_test_pilot(repo)
    # sanity: store.resolve DOES surface the layer (that overload is correct for the engine)
    import store as tp_store
    res = tp_store.resolve(repo, tp_store.store_root())
    assert res["profileSource"] == "layer"
    assert os.path.realpath(res["profile"]) == os.path.realpath(layer_p)
    # but _legacy_path must not return the layer — it returns the (non-existent) legacy path,
    # so resolve_shared's `os.path.isfile(legacy)` gate is False and migration never fires.
    legacy = CM._legacy_path(repo, "test-pilot")
    assert os.path.realpath(legacy) != os.path.realpath(layer_p)
    assert not os.path.isfile(legacy)


def test_migrate_migrated_test_pilot_is_noop_never_deletes_layer(tmp_path, monkeypatch):
    # #428 THE reproducer: an in-repo worktree cut from a migrated main (core.md + tracked
    # test-pilot.md layer, NO legacy profile.md). migrate_on_read must be a NOOP — it must NOT
    # unlink the layer, and must NOT commit a deletion of it.
    repo = _git_repo(tmp_path)
    store = str(tmp_path / "store")
    _force_in_repo(repo, store)
    monkeypatch.setenv("TEST_PILOT_STORE_ROOT", str(tmp_path / "tp_store"))
    layer_p = _write_migrated_test_pilot(repo)
    _git(repo, "add", ".claude/superheroes/core.md", ".claude/superheroes/test-pilot.md")
    _git(repo, "commit", "-q", "-m", "migrate (prior run)")
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()

    res = CM.migrate_on_read(repo, "test-pilot", root=store)

    assert res["action"] == "noop"
    # the layer is still on disk AND still tracked — no destructive deletion
    assert os.path.isfile(layer_p)
    assert _git(repo, "ls-files", "--", ".claude/superheroes/test-pilot.md").stdout.strip()
    # HEAD did not advance with a phantom "migrate" deletion commit
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    # idempotent: a second read is still a clean noop, layer intact
    assert CM.migrate_on_read(repo, "test-pilot", root=store)["action"] == "noop"
    assert os.path.isfile(layer_p)
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head_before


def test_migrate_belt_refuses_when_legacy_is_the_layer(tmp_path, monkeypatch):
    # #428 direction 1 (belt, independent of the trigger fix): even if a resolver regressed and
    # handed the LAYER path back as "legacy", migrate_on_read must refuse — a calibration
    # core/layer is never its own legacy. No unlink, no deletion commit.
    repo = _git_repo(tmp_path)
    store = str(tmp_path / "store")
    _force_in_repo(repo, store)
    layer_p = _write_migrated_test_pilot(repo)
    _git(repo, "add", ".claude/superheroes/core.md", ".claude/superheroes/test-pilot.md")
    _git(repo, "commit", "-q", "-m", "migrate (prior run)")
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    # simulate the regression: _legacy_path returns the layer itself
    monkeypatch.setattr(CM, "_legacy_path", lambda cwd, hero: layer_p)

    res = CM.migrate_on_read(repo, "test-pilot", root=store)

    assert res["action"] == "noop"
    assert os.path.isfile(layer_p)  # NOT unlinked
    assert _git(repo, "ls-files", "--", ".claude/superheroes/test-pilot.md").stdout.strip()
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head_before


def test_commit_pathspec_excludes_absent_calibration_paths(tmp_path):
    # #428 direction 1 (unit): the migration commit pathspec / add-set must include core/layer
    # ONLY when present+non-empty. An ABSENT (tracked-but-missing) layer must never have its
    # DELETION staged/committed by the migration — and a present-but-EMPTY one is equally not
    # a calibration ADD (the >0 boundary).
    repo = _git_repo(tmp_path)
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d)
    core_p = os.path.join(d, "core.md")
    layer_p = os.path.join(d, "test-pilot.md")
    open(core_p, "w").write(CM.render_core(
        {"verifyCommand": "npm test", "stackTags": [], "threatModel": "x", "patterns": ""},
        "provisional", "2026-07-01", "2026-07-01"))
    # layer_p is ABSENT
    present = CM._present_calibration_paths(core_p, layer_p)
    assert core_p in present
    assert layer_p not in present
    # present-but-ZERO-BYTE is not "populated" either (kills the >0 → >=0 mutant)
    open(layer_p, "w").close()
    assert layer_p not in CM._present_calibration_paths(core_p, layer_p)
    os.unlink(layer_p)
    # a distinct TRACKED in-repo legacy deletion is still recorded; an absent layer is not
    legacy = os.path.join(repo, ".claude", "test-pilot", "profile.md")
    os.makedirs(os.path.dirname(legacy))
    open(legacy, "w").write("# legacy\n")
    _git(repo, "add", ".claude/test-pilot/profile.md")
    _git(repo, "commit", "-q", "-m", "seed legacy")
    spec = CM._commit_pathspec(repo, core_p, layer_p, legacy)
    assert core_p in spec
    assert layer_p not in spec        # absent → never a deletion in the pathspec
    assert legacy in spec             # distinct tracked in-repo legacy deletion still recorded


def test_commit_pathspec_excludes_phantom_untracked_legacy(tmp_path):
    # #428 review (code round 1): _legacy_path returns an in-repo ANCHORED path even when no
    # legacy ever existed. A never-tracked pathspec entry makes `git commit --only` abort the
    # WHOLE commit ("did not match any files"), so core/layer would never land. The pathspec
    # must include the legacy only when it is genuinely tracked.
    repo = _git_repo(tmp_path)
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d)
    core_p = os.path.join(d, "core.md")
    layer_p = os.path.join(d, "test-pilot.md")
    open(core_p, "w").write("x\n")
    open(layer_p, "w").write("y\n")
    phantom = os.path.join(repo, ".claude", "test-pilot", "profile.md")  # never created/tracked
    spec = CM._commit_pathspec(repo, core_p, layer_p, phantom)
    assert phantom not in spec
    assert spec == [core_p, layer_p]


def test_resume_outstanding_commit_with_no_legacy_ever_lands(tmp_path, monkeypatch):
    # #428 review (code round 1, integration): in-repo core+layer written on disk but never
    # committed, and NO legacy profile ever existed. The outstanding-commit resume must land
    # the split — with the phantom anchored legacy in the pathspec the whole commit aborted
    # and every read deferred forever.
    repo = _git_repo(tmp_path)
    store = str(tmp_path / "store")
    _force_in_repo(repo, store)
    monkeypatch.setenv("TEST_PILOT_STORE_ROOT", str(tmp_path / "tp_store"))
    _git(repo, "commit", "-q", "--allow-empty", "-m", "init")
    layer_p = _write_migrated_test_pilot(repo)  # writes core.md + layer, commits nothing

    res = CM.migrate_on_read(repo, "test-pilot", root=store)

    assert res["action"] == "completed"
    assert _git(repo, "ls-files", "--", ".claude/superheroes/core.md").stdout.strip()
    assert _git(repo, "ls-files", "--", ".claude/superheroes/test-pilot.md").stdout.strip()
    assert os.path.isfile(layer_p)
    assert not os.path.isfile(CM._pending_path(repo, store))


def test_record_migration_commit_nothing_to_add_refuses(tmp_path):
    # #428 direction 1 (unit lock on the belt): with NEITHER core nor layer present+populated
    # there is nothing legitimate to record — _record_migration_commit must refuse (deferred +
    # calibration-not-saved marker), never commit a purely destructive migration.
    repo = _git_repo(tmp_path)
    store = str(tmp_path / "store")
    _force_in_repo(repo, store)
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d)
    core_p = os.path.join(d, "core.md")         # ABSENT
    layer_p = os.path.join(d, "test-pilot.md")  # ABSENT
    legacy = os.path.join(repo, ".claude", "test-pilot", "profile.md")
    os.makedirs(os.path.dirname(legacy))
    open(legacy, "w").write("# legacy\n")
    _git(repo, "add", ".claude/test-pilot/profile.md")
    _git(repo, "commit", "-q", "-m", "seed legacy")
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()

    res = CM._record_migration_commit(repo, repo, "test-pilot", core_p, layer_p, legacy, store)

    assert res == {"action": "deferred"}
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head_before  # no commit landed
    assert _git(repo, "ls-files", "--", ".claude/test-pilot/profile.md").stdout.strip()  # not retired
    marker = json.load(open(CM._pending_path(repo, store)))
    assert marker["detail"]["reason"] == "migrate-nothing-to-add"


def test_migration_recorded_requires_present_layer_tracked(tmp_path, monkeypatch):
    # #428 review (premortem round 1): the convergence predicate must not be layer-blind. A
    # commit that landed core.md + legacy retirement but DROPPED the layer must read as NOT
    # recorded (so the next read retries and heals), while an absent layer imposes no
    # requirement (a deliberately deleted layer must not retry forever).
    repo = _git_repo(tmp_path)
    store = str(tmp_path / "store")
    _force_in_repo(repo, store)
    monkeypatch.setenv("TEST_PILOT_STORE_ROOT", str(tmp_path / "tp_store"))
    layer_p = _write_migrated_test_pilot(repo)
    core_p = os.path.join(repo, ".claude", "superheroes", "core.md")
    legacy = os.path.join(repo, ".claude", "test-pilot", "profile.md")  # never existed
    # core committed, layer present+populated but UNTRACKED → not recorded
    _git(repo, "add", ".claude/superheroes/core.md")
    _git(repo, "commit", "-q", "-m", "core only")
    assert CM._migration_recorded(repo, core_p, legacy, layer_p=layer_p) is False
    # the next read HEALS it: the outstanding-commit resume commits the dropped layer
    res = CM.migrate_on_read(repo, "test-pilot", root=store)
    assert res["action"] == "completed"
    assert _git(repo, "ls-files", "--", ".claude/superheroes/test-pilot.md").stdout.strip()
    assert CM._migration_recorded(repo, core_p, legacy, layer_p=layer_p) is True
    # an ABSENT layer imposes no tracked requirement (recorded stays true after a deliberate,
    # committed retirement of the layer)
    _git(repo, "rm", "-q", ".claude/superheroes/test-pilot.md")
    _git(repo, "commit", "-q", "-m", "retire layer on purpose")
    assert CM._migration_recorded(repo, core_p, legacy, layer_p=layer_p) is True


def test_commit_pathspec_never_records_legacy_that_is_the_layer(tmp_path):
    # #428 direction 1 (unit): if `legacy` coincides with core_p/layer_p, it must NOT be appended
    # as a deletion (a core/layer is never its own legacy).
    repo = _git_repo(tmp_path)
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d)
    core_p = os.path.join(d, "core.md")
    layer_p = os.path.join(d, "test-pilot.md")
    open(core_p, "w").write("x\n")
    open(layer_p, "w").write("y\n")
    spec = CM._commit_pathspec(repo, core_p, layer_p, layer_p)  # legacy == layer
    assert spec.count(layer_p) == 1  # present once as the ADD, never doubled as a deletion


def test_store_create_does_not_mint_legacy_profile_md(tmp_path):
    # #428 direction 2 corollary: store.create() must not materialize a legacy profile.md on disk
    # (it returns the path but never writes the file). Locks the non-minting invariant so a future
    # change can't reintroduce the migrate_on_read trigger.
    import store as tp_store
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    subprocess.run(["git", "init", "-q", repo], check=True, capture_output=True)
    root = str(tmp_path / "store")
    c = tp_store.create(repo, "in-repo", root)
    assert c["profileSource"] == "profile-md"  # genuinely un-migrated: legacy scaffold target
    assert c["profile"].endswith(os.path.join(".claude", "test-pilot", "profile.md"))
    assert not os.path.exists(c["profile"])  # path returned, file NOT minted


def test_migrate_real_test_pilot_legacy_still_migrates_and_commits(tmp_path, monkeypatch):
    # #428 must NOT break the legitimate migration: a REAL in-repo legacy profile.md (tracked, no
    # prior core/layer) still splits into core.md + test-pilot.md, commits them, and records the
    # legacy DELETION.
    repo = _git_repo(tmp_path)
    store = str(tmp_path / "store")
    _force_in_repo(repo, store)
    monkeypatch.setenv("TEST_PILOT_STORE_ROOT", str(tmp_path / "tp_store"))
    legacy_dir = os.path.join(repo, ".claude", "test-pilot")
    os.makedirs(legacy_dir)
    legacy = os.path.join(legacy_dir, "profile.md")
    open(legacy, "w").write(
        "<!-- test-pilot -->\n\n## App launch\n\nnpm run dev\n\n"
        "## Machine-readable config\n\n```json test-pilot-config\n"
        '{"schemaVersion": 1, "baseUrl": "http://localhost:3000"}\n```\n')
    _git(repo, "add", ".claude/test-pilot/profile.md")
    _git(repo, "commit", "-q", "-m", "seed legacy test-pilot profile")

    # _legacy_path returns the REAL legacy (anchored in-repo), not the layer
    assert os.path.realpath(CM._legacy_path(repo, "test-pilot")) == os.path.realpath(legacy)
    res = CM.migrate_on_read(repo, "test-pilot", root=store)
    assert res["action"] == "migrated"
    # core.md + layer written and committed; legacy deletion recorded
    names = set(_git(repo, "show", "--name-status", "--format=", "HEAD").stdout.split())
    assert ".claude/superheroes/core.md" in names
    assert ".claude/superheroes/test-pilot.md" in names
    # the legacy profile.md's removal is recorded (git may report it as a delete or, since it
    # shares the config block with the layer, as a rename — either way it is no longer tracked)
    assert not _git(repo, "ls-files", "--", ".claude/test-pilot/profile.md").stdout.strip()
    assert not os.path.exists(legacy)
    # and the layer carries the test-pilot-config block (real calibration, not an empty deletion)
    assert "test-pilot-config" in open(os.path.join(repo, ".claude", "superheroes", "test-pilot.md")).read()
