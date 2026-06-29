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
    assert text.startswith("<!-- superheroes-core: schemaVersion=1 status=confirmed "
                           "created=2026-06-26 updated=2026-06-26 -->")
    assert "## Threat model" in text and "## Canonical patterns" in text
    assert "```json superheroes-core" in text
    got = CM.parse_core(text)
    assert got["schemaVersion"] == 1
    assert got["status"] == "confirmed"
    assert got["verifyCommand"] == "npm test"
    assert got["stackTags"] == ["node", "ts"]
    assert got["threatModel"] == "multi-tenant"
    assert got["patterns"] == "- auth: src/auth.ts:10"
    assert got["created"] == "2026-06-26" and got["updated"] == "2026-06-26"


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
    prof_path = review_store.create(repo, "profile", "global", hero_root)  # mints entry + pointers
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
