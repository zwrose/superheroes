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
