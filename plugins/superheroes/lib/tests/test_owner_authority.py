"""Unit tests for lib/owner_authority.py — the minimal owner-authority classifier (#482).

Covers the enumerated command set (lifted verbatim from the retired enforcer), the tri-state
calibration probe (calibrated / uncalibrated / indeterminate), the strictly-read-only guarantee,
the owner-calibrated allowlist (#947), and the classify() decision (ask only for an
owner-authority command on a calibrated OR indeterminate project unless allowlisted; allow
otherwise).
"""
import json
import os
import stat

import pytest

import mode_registry
import owner_authority as oa


# --- owner_authority_action: the enumerated set --------------------------------

@pytest.mark.parametrize("command,action", [
    ("gh pr merge 42 --squash", "merge-pr"),
    ("gh api -X PUT repos/o/r/pulls/42/merge", "merge-api"),
    ("gh api graphql -f query='mutation { mergePullRequest(input: {}) }'", "merge-graphql"),
    ("gh release create v1.0.0", "release"),
    ("gh workflow run deploy.yml", "run-workflow"),
    ("gh workflow enable ci.yml", "run-workflow"),
    ("gh workflow disable ci.yml", "run-workflow"),
    ("git push --force origin main", "force-push"),
    ("git push -f origin feature", "force-push"),
    ("git push --force-with-lease origin feature", "force-push"),
    ("git push origin main", "push-to-default"),
    ("git push origin HEAD:main", "push-to-default"),
    ("git push origin feature-branch:main", "push-to-default"),
    ("git push origin master", "push-to-default"),
    ("git push origin refs/heads/main", "push-to-default"),
])
def test_owner_authority_action_recognises_each_shape(command, action):
    assert oa.owner_authority_action(command) == action


@pytest.mark.parametrize("command", [
    "git push origin my-branch",
    "git push -u origin superheroes/x-abc123",
    "git commit -m wip",
    "gh pr create --draft",
    "gh pr ready 42",
    "gh pr checks 42",
    "npm run build",
    # compound-with-later-main regressions: the push targets a feature branch, `main` only
    # appears after a `;` / `&&` (a separate later command), so the push regex must NOT fire.
    "git push -u origin superheroes/x && git checkout main",
    "git push origin superheroes/x ; echo on main",
    # branches merely PREFIXED with `main` are not the default branch → must NOT gate.
    "git push origin main-feature",
    "git push origin mainline",
])
def test_owner_authority_action_none_for_ordinary(command):
    assert oa.owner_authority_action(command) is None


def test_owner_authority_action_none_for_non_string():
    assert oa.owner_authority_action(None) is None
    assert oa.owner_authority_action(123) is None
    assert oa.owner_authority_action(["gh", "pr", "merge"]) is None


# --- classify: ask on every gated shape under a calibrated cwd -----------------

_GATED = [
    "gh pr merge 42 --squash",
    "gh api -X PUT repos/o/r/pulls/42/merge",
    "gh api graphql -f query='mutation { mergePullRequest(input: {}) }'",
    "gh release create v1.0.0",
    "gh workflow run deploy.yml",
    "git push --force origin main",
    "git push origin main",
    "git push origin HEAD:main",
    "git push origin feature-branch:main",
    "git push origin master",
    "git push origin refs/heads/main",
]

_SAFE = [
    "git push origin my-branch",
    "git push -u origin superheroes/x-abc123",
    "git commit -m wip",
    "gh pr create --draft",
    "gh pr ready 42",
    "gh pr checks 42",
    "npm run build",
    "git push -u origin superheroes/x && git checkout main",
    "git push origin superheroes/x ; echo on main",
]


@pytest.mark.parametrize("command", _GATED)
def test_classify_asks_on_gated_when_calibrated(command, monkeypatch):
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    decision, reason = oa.classify(command, "/somewhere")
    assert decision == "ask"
    assert reason  # non-empty human-readable reason


@pytest.mark.parametrize("command", _SAFE)
def test_classify_allows_safe_when_calibrated(command, monkeypatch):
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    assert oa.classify(command, "/somewhere") == ("allow", "")


def test_classify_allows_non_gated_regardless_of_calibration():
    # A non-owner-authority command short-circuits: the probe is never even consulted, so a
    # probe that would raise still yields allow.
    def _boom(cwd):
        raise RuntimeError("probe must not be reached for a non-gated command")

    orig = oa.calibration_state
    oa.calibration_state = _boom
    try:
        assert oa.classify("git commit -m wip", "/somewhere") == ("allow", "")
    finally:
        oa.calibration_state = orig


def test_classify_uncalibrated_allows_even_gated(monkeypatch):
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "uncalibrated")
    assert oa.classify("gh pr merge 42 --squash", "/somewhere") == ("allow", "")


def test_classify_indeterminate_asks_gated(monkeypatch):
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "indeterminate")
    decision, _ = oa.classify("gh pr merge 42 --squash", "/somewhere")
    assert decision == "ask"


# --- calibration_state: tri-state ----------------------------------------------

def test_calibration_state_registry_present_is_calibrated(monkeypatch, tmp_path):
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo"})
    assert oa.calibration_state(str(tmp_path)) == "calibrated"


def test_calibration_state_hero_evidence_present_is_calibrated(monkeypatch, tmp_path):
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)
    monkeypatch.setattr(mode_registry, "registry_path",
                        lambda cwd, root=None: str(tmp_path / "no-such-registry.json"))
    monkeypatch.setattr(mode_registry, "hero_evidence",
                        lambda cwd, root=None, hero_roots=None: {"review-crew": "global"})
    assert oa.calibration_state(str(tmp_path)) == "calibrated"


def test_calibration_state_no_registry_no_evidence_is_uncalibrated(monkeypatch, tmp_path):
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)
    monkeypatch.setattr(mode_registry, "registry_path",
                        lambda cwd, root=None: str(tmp_path / "no-such-registry.json"))
    monkeypatch.setattr(mode_registry, "hero_evidence",
                        lambda cwd, root=None, hero_roots=None: {"review-crew": "none"})
    assert oa.calibration_state(str(tmp_path)) == "uncalibrated"


def test_calibration_state_registry_file_present_but_corrupt_is_indeterminate(monkeypatch, tmp_path):
    # read_registry returns None (corrupt), but the registry FILE exists → indeterminate,
    # distinct from a plain absence (uncalibrated).
    reg = tmp_path / "registry.json"
    reg.write_text("{ this is not valid json")
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)
    monkeypatch.setattr(mode_registry, "registry_path", lambda cwd, root=None: str(reg))
    # hero_evidence must NOT be consulted once a corrupt file is detected.
    monkeypatch.setattr(mode_registry, "hero_evidence",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("hero_evidence must not run when file exists")))
    assert oa.calibration_state(str(tmp_path)) == "indeterminate"


def test_calibration_state_dangling_symlink_is_indeterminate(monkeypatch, tmp_path):
    # A DANGLING symlink at the registry path: os.path.exists would follow it, find nothing, and
    # report "absent" → falling through to hero-evidence and possibly dropping the floor to
    # uncalibrated. os.lstat succeeds on the link itself → present → indeterminate (fail-closed).
    link_path = tmp_path / "registry.json"
    os.symlink(tmp_path / "nonexistent-target", link_path)
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)
    monkeypatch.setattr(mode_registry, "registry_path", lambda cwd, root=None: str(link_path))
    # hero_evidence must NOT be consulted once the (dangling) file link is detected.
    monkeypatch.setattr(mode_registry, "hero_evidence",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("hero_evidence must not run when link is present")))
    assert oa.calibration_state(str(tmp_path)) == "indeterminate"


def test_calibration_state_import_failure_is_indeterminate(monkeypatch, tmp_path):
    import builtins
    real_import = builtins.__import__

    def _fake(name, *a, **k):
        if name == "mode_registry":
            raise ImportError("simulated")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _fake)
    assert oa.calibration_state(str(tmp_path)) == "indeterminate"


def test_calibration_state_read_registry_raises_is_indeterminate(monkeypatch, tmp_path):
    def _raise(cwd, root=None):
        raise mode_registry.UnknownSchemaVersion("newer schema")

    monkeypatch.setattr(mode_registry, "read_registry", _raise)
    assert oa.calibration_state(str(tmp_path)) == "indeterminate"


def test_calibration_state_read_registry_generic_error_is_indeterminate(monkeypatch, tmp_path):
    def _raise(cwd, root=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(mode_registry, "read_registry", _raise)
    assert oa.calibration_state(str(tmp_path)) == "indeterminate"


def test_calibration_state_registry_path_error_is_indeterminate(monkeypatch, tmp_path):
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)

    def _raise(cwd, root=None):
        raise RuntimeError("path boom")

    monkeypatch.setattr(mode_registry, "registry_path", _raise)
    assert oa.calibration_state(str(tmp_path)) == "indeterminate"


def test_calibration_state_evidence_error_is_indeterminate(monkeypatch, tmp_path):
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)
    monkeypatch.setattr(mode_registry, "registry_path",
                        lambda cwd, root=None: str(tmp_path / "no-such-registry.json"))

    def _raise(*a, **k):
        raise RuntimeError("evidence boom")

    monkeypatch.setattr(mode_registry, "hero_evidence", _raise)
    assert oa.calibration_state(str(tmp_path)) == "indeterminate"


def test_calibration_state_never_calls_resolve(monkeypatch, tmp_path):
    # A probe must be strictly read-only: resolve() and write_registry() can backfill-WRITE the
    # registry and must never be reached from calibration_state.
    def _tripwire(*a, **k):
        raise AssertionError("write-capable registry path must not be called from the probe")

    monkeypatch.setattr(mode_registry, "resolve", _tripwire)
    monkeypatch.setattr(mode_registry, "write_registry", _tripwire)
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo"})
    assert oa.calibration_state(str(tmp_path)) == "calibrated"


# --- calibrated-path integration: a real on-disk registry (no subprocess) ------

def test_calibration_state_reads_a_real_registry(tmp_path, monkeypatch):
    # Pin the store root to tmp (the autouse conftest fixture already env-pins it, but be
    # explicit), write a valid registry via the real write_registry, then probe it read-only.
    root = str(tmp_path / "store")
    cwd = str(tmp_path)
    rec = mode_registry.write_registry(cwd, mode_registry.IN_REPO, None, root=root)
    assert rec is not None, "precondition: registry write landed"
    # calibration_state calls read_registry(cwd) with no root, so route reads through the same
    # pinned store root the write used.
    orig_read = mode_registry.read_registry
    orig_path = mode_registry.registry_path
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda c, r=None: orig_read(c, root=root))
    monkeypatch.setattr(mode_registry, "registry_path",
                        lambda c, r=None: orig_path(c, root=root))
    assert oa.calibration_state(cwd) == "calibrated"


# --- allowlist helpers ---------------------------------------------------------

def _pin_allow_store(tmp_path, monkeypatch, store_name="allow-store"):
    store = str(tmp_path / store_name)
    monkeypatch.setattr(mode_registry, "project_store_dir",
                        lambda cwd, root=None: store)
    return store


def _write_allow_at(store, content):
    os.makedirs(store, exist_ok=True)
    path = os.path.join(store, oa.ALLOW_FILENAME)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(content, fh)
    return path


_VALID_ENTRY = {"action": "run-workflow", "workflow": "deploy.yml"}


# --- workflow_run_dispatch: accepts ------------------------------------------------
# Bites on: workflow_run_dispatch returns workflow+ref when flags are limited to
# inputs (-f/-F/--field) or valueless --json — never repo scope-changing flags.

@pytest.mark.parametrize("command,expected", [
    ("gh workflow run deploy.yml", {"workflow": "deploy.yml", "ref": None}),
    ("gh workflow run 'Preview seed'", {"workflow": "Preview seed", "ref": None}),
    ('gh workflow run "Preview seed"', {"workflow": "Preview seed", "ref": None}),
    ("gh workflow run ci.yml", {"workflow": "ci.yml", "ref": None}),
    ("gh workflow run -f k=v deploy.yml", {"workflow": "deploy.yml", "ref": None}),
    ("gh workflow run -F k=v deploy.yml", {"workflow": "deploy.yml", "ref": None}),
    ("gh workflow run --field=k=v deploy.yml", {"workflow": "deploy.yml", "ref": None}),
    ("gh workflow run --json deploy.yml", {"workflow": "deploy.yml", "ref": None}),
    ("gh workflow run -- deploy.yml", {"workflow": "deploy.yml", "ref": None}),
    ("gh workflow run --ref main deploy.yml", {"workflow": "deploy.yml", "ref": "main"}),
    ("gh workflow run --ref=main deploy.yml", {"workflow": "deploy.yml", "ref": "main"}),
    ("gh workflow run -r main deploy.yml", {"workflow": "deploy.yml", "ref": "main"}),
    ("gh workflow run deploy.yml --ref main", {"workflow": "deploy.yml", "ref": "main"}),
    ("gh workflow run deploy.yml --ref=main", {"workflow": "deploy.yml", "ref": "main"}),
])
def test_workflow_run_dispatch_accepts(command, expected):
    assert oa.workflow_run_dispatch(command) == expected


# --- workflow_run_dispatch: refuses ------------------------------------------------
# Bites on: workflow_run_dispatch returns None for shell-expandable text, repo
# scope-changing flags, malformed commands, and any dispatch that does not name exactly one workflow.

@pytest.mark.parametrize("command", [
    "gh workflow run $VAR",
    'gh workflow run "$VAR"',
    "gh workflow run ${VAR}",
    "gh workflow run $(cmd)",
    "gh workflow run `cmd`",
    "gh workflow run $'ansi'",
    "gh workflow run *",
    "gh workflow run ?",
    "gh workflow run [abc]",
    "gh workflow run {a,b}",
    "gh workflow run ~",
    "gh workflow run \\x",
    "gh workflow run X; rm -rf /",
    "gh workflow run X && echo hi",
    "gh workflow run X || echo hi",
    "gh workflow run X | cat",
    "gh workflow run X > /tmp/out",
    "gh workflow run X < /tmp/in",
    "gh workflow run X\nY",
    "gh workflow run unclosed'",
    "FOO=bar gh workflow run X",
    "/usr/bin/gh workflow run X",
    "gh workflow enable ci.yml",
    "gh workflow disable ci.yml",
    "gh workflow run --zzz X deploy.yml",
    "gh workflow run -rmain deploy.yml",
    "gh workflow run - deploy.yml",
    "gh workflow run deploy.yml --ref",
    "gh workflow run --json=x deploy.yml",
    "gh workflow run",
    "gh workflow run a b",
    "gh workflow run ''",
    "gh workflow run deploy.yml\n",
    "gh workflow run deploy.yml \n",
    "gh workflow run deploy.yml\r",
    "gh workflow run deploy.yml\r\n",
    None,
    "x" * 4097,
    # scope-changing repo flags — never pre-authorized regardless of allow file
    "gh workflow run -R o/r deploy.yml",
    "gh workflow run --repo o/r deploy.yml",
    "gh workflow run --repo=o/r deploy.yml",
    "gh workflow run deploy.yml -R o/r",
    "gh workflow run deploy.yml --repo o/r",
    "gh workflow run deploy.yml --repo=o/r",
    # ref flag edge cases — refuse
    "gh workflow run --ref= deploy.yml",
    "gh workflow run --ref a --ref b deploy.yml",
    # --ref consumes main as its value, leaving zero positionals (distinct from empty/missing value)
    "gh workflow run --ref main",
    "gh workflow run --ref=main$ deploy.yml",
])
def test_workflow_run_dispatch_refuses(command):
    assert oa.workflow_run_dispatch(command) is None


# --- read_allow_file: fail direction (§A) --------------------------------------
# Bites on: read_allow_file yields no entries for absent, unreadable, malformed, or
# wrong-schema files — a weakened guard must not honour hostile content.

@pytest.mark.parametrize("setup", [
    "absent",
    "unreadable",
    "is_dir",
    "dangling_symlink",
    "bad_json",
    "top_array",
    "top_string",
    "top_number",
    "top_null",
    "schema_missing",
    "schema_true",
    "schema_false",
    "schema_1_0",
    "schema_str_1",
    "schema_null",
    "schema_0",
    "schema_3",
    "allow_missing",
    "allow_dict",
    "exception_on_path",
])
def test_read_allow_file_fail_direction_yields_no_entries(setup, tmp_path, monkeypatch):
    # Each case carries a valid allow entry so a weakened schema guard would yield entries != [].
    store = _pin_allow_store(tmp_path, monkeypatch)
    path = os.path.join(store, oa.ALLOW_FILENAME)

    if setup == "absent":
        # No file — cannot carry a valid entry by construction.
        os.makedirs(store, exist_ok=True)
    elif setup == "unreadable":
        os.makedirs(store, exist_ok=True)
        path_obj = tmp_path / "allow-store" / oa.ALLOW_FILENAME
        path_obj.write_text(json.dumps({"schemaVersion": 1, "allow": [_VALID_ENTRY]}))
        path_obj.chmod(0)
        if os.access(path, os.R_OK):
            pytest.skip("chmod 000 did not make file unreadable for this user")
    elif setup == "is_dir":
        # Path is a directory — cannot carry a valid entry by construction.
        os.makedirs(path, exist_ok=True)
    elif setup == "dangling_symlink":
        # Unreadable path — cannot carry a valid entry by construction.
        os.makedirs(store, exist_ok=True)
        os.symlink(tmp_path / "no-target", path)
    elif setup == "bad_json":
        # Invalid JSON — cannot carry a valid entry by construction.
        os.makedirs(store, exist_ok=True)
        with open(path, "w") as fh:
            fh.write("{ not json")
    elif setup == "top_array":
        _write_allow_at(store, [_VALID_ENTRY])
    elif setup == "top_string":
        _write_allow_at(store, "hello")
    elif setup == "top_number":
        _write_allow_at(store, 1)
    elif setup == "top_null":
        os.makedirs(store, exist_ok=True)
        with open(path, "w") as fh:
            fh.write("null")
    elif setup == "schema_missing":
        _write_allow_at(store, {"allow": [_VALID_ENTRY]})
    elif setup == "schema_true":
        _write_allow_at(store, {"schemaVersion": True, "allow": [_VALID_ENTRY]})
    elif setup == "schema_false":
        _write_allow_at(store, {"schemaVersion": False, "allow": [_VALID_ENTRY]})
    elif setup == "schema_1_0":
        _write_allow_at(store, {"schemaVersion": 1.0, "allow": [_VALID_ENTRY]})
    elif setup == "schema_str_1":
        _write_allow_at(store, {"schemaVersion": "1", "allow": [_VALID_ENTRY]})
    elif setup == "schema_null":
        _write_allow_at(store, {"schemaVersion": None, "allow": [_VALID_ENTRY]})
    elif setup == "schema_0":
        _write_allow_at(store, {"schemaVersion": 0, "allow": [_VALID_ENTRY]})
    elif setup == "schema_3":
        _write_allow_at(store, {"schemaVersion": 3, "allow": [_VALID_ENTRY]})
    elif setup == "allow_missing":
        # No allow key — cannot carry a valid entry by construction.
        _write_allow_at(store, {"schemaVersion": 1})
    elif setup == "allow_dict":
        # allow is a dict, not a list — cannot carry a valid entry by construction.
        _write_allow_at(store, {"schemaVersion": 1, "allow": {}})
    elif setup == "exception_on_path":
        # Path resolution fails — cannot carry a valid entry by construction.
        def _boom(cwd, root=None):
            raise OSError("simulated path failure")
        monkeypatch.setattr(oa, "allow_file_path", _boom)

    entries, notes = oa.read_allow_file(str(tmp_path))
    assert entries == []
    if setup == "unreadable":
        path_obj.chmod(stat.S_IWUSR | stat.S_IRUSR)


# --- read_allow_file: notes ------------------------------------------------------
# Bites on: rejected-file notes name the defect; structural/malformed entries are
# dropped with the correct note kind; absent files produce no rejection note.

@pytest.mark.parametrize("setup,defect_fragment", [
    ("unreadable", "unreadable"),
    ("bad_json", "invalid JSON"),
    ("top_array", "top level is not an object"),
    ("schema_3", "bad schemaVersion"),
    ("allow_dict", "allow is not a list"),
    ("exception_on_path", "path resolution failed"),
])
def test_read_allow_file_rejected_file_note(setup, defect_fragment, tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    path = os.path.join(store, oa.ALLOW_FILENAME)

    if setup == "unreadable":
        os.makedirs(store, exist_ok=True)
        path_obj = tmp_path / "allow-store" / oa.ALLOW_FILENAME
        path_obj.write_text(json.dumps({"schemaVersion": 1, "allow": [_VALID_ENTRY]}))
        path_obj.chmod(0)
        if os.access(path, os.R_OK):
            pytest.skip("chmod 000 did not make file unreadable for this user")
    elif setup == "bad_json":
        os.makedirs(store, exist_ok=True)
        with open(path, "w") as fh:
            fh.write("{ not json")
    elif setup == "top_array":
        _write_allow_at(store, [_VALID_ENTRY])
    elif setup == "schema_3":
        _write_allow_at(store, {"schemaVersion": 3, "allow": [_VALID_ENTRY]})
    elif setup == "allow_dict":
        _write_allow_at(store, {"schemaVersion": 1, "allow": {}})
    elif setup == "exception_on_path":
        def _boom(cwd, root=None):
            raise OSError("simulated path failure")
        monkeypatch.setattr(oa, "allow_file_path", _boom)

    entries, notes = oa.read_allow_file(str(tmp_path))
    assert entries == []
    rejected = [n for n in notes if n[0] == "rejected-file"]
    assert len(rejected) == 1
    assert defect_fragment in rejected[0][2]

    if setup == "unreadable":
        path_obj.chmod(stat.S_IWUSR | stat.S_IRUSR)


def test_read_allow_file_absent_produces_no_rejection_note(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    os.makedirs(store, exist_ok=True)
    entries, notes = oa.read_allow_file(str(tmp_path))
    assert entries == []
    assert not any(kind == "rejected-file" for kind, _, _ in notes)


def test_read_allow_file_empty_allow_list_valid_no_rejection_note(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 1, "allow": []})
    entries, notes = oa.read_allow_file(str(tmp_path))
    assert entries == []
    assert not any(kind == "rejected-file" for kind, _, _ in notes)


def test_read_allow_file_empty_file_rejected(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    os.makedirs(store, exist_ok=True)
    path = os.path.join(store, oa.ALLOW_FILENAME)
    with open(path, "w") as fh:
        fh.write("")
    entries, notes = oa.read_allow_file(str(tmp_path))
    assert entries == []
    assert any(kind == "rejected-file" for kind, _, _ in notes)


def test_read_allow_file_notes_structural_exclusions(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    allow = [{"action": a, "workflow": "x"} for a in oa.NEVER_ALLOWLISTABLE]
    _write_allow_at(store, {"schemaVersion": 1, "allow": allow})
    entries, notes = oa.read_allow_file(str(tmp_path))
    assert entries == []
    assert len(notes) == len(oa.NEVER_ALLOWLISTABLE)
    assert all(kind == "structural" for kind, _, _ in notes)


def test_read_allow_file_notes_not_allowlistable(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 1,
                            "allow": [{"action": "push-to-default", "workflow": "main"}]})
    entries, notes = oa.read_allow_file(str(tmp_path))
    assert entries == []
    assert notes == [("not-allowlistable", "push-to-default",
                      "ignored not-allowlistable action 'push-to-default'")]


def test_read_allow_file_notes_malformed(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 1, "allow": ["garbage", None, 42]})
    entries, notes = oa.read_allow_file(str(tmp_path))
    assert entries == []
    assert len(notes) == 3
    assert all(kind == "malformed" for kind, _, _ in notes)


def test_read_allow_file_valid_entry(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 1,
                            "allow": [{"action": "run-workflow", "workflow": "Preview seed"}]})
    entries, notes = oa.read_allow_file(str(tmp_path))
    assert entries == [{"action": "run-workflow", "workflow": "Preview seed"}]
    assert notes == []


def test_read_allow_file_mixed_valid_invalid(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 1, "allow": [
        {"action": "merge-pr", "workflow": "x"},
        {"action": "run-workflow", "workflow": "good"},
        "bad",
    ]})
    entries, notes = oa.read_allow_file(str(tmp_path))
    assert entries == [{"action": "run-workflow", "workflow": "good"}]
    assert len(notes) == 2


def test_read_allow_file_does_not_create_missing_store(tmp_path, monkeypatch):
    missing = str(tmp_path / "no-such-store")
    assert not os.path.exists(missing)
    monkeypatch.setattr(mode_registry, "project_store_dir",
                        lambda cwd, root=None: missing)
    entries, notes = oa.read_allow_file(str(tmp_path))
    assert entries == []
    assert notes == []
    assert not os.path.exists(missing)


def test_read_allow_file_does_not_modify_existing_store(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    content = {"schemaVersion": 1,
               "allow": [{"action": "run-workflow", "workflow": "deploy.yml"}]}
    path = _write_allow_at(store, content)
    before_bytes = open(path, "rb").read()
    before_mtime = os.stat(path).st_mtime_ns
    before_mode = os.stat(path).st_mode
    before_listing = sorted(os.listdir(store))

    entries, notes = oa.read_allow_file(str(tmp_path))

    assert entries == [{"action": "run-workflow", "workflow": "deploy.yml"}]
    assert notes == []
    assert open(path, "rb").read() == before_bytes
    assert os.stat(path).st_mtime_ns == before_mtime
    assert os.stat(path).st_mode == before_mode
    assert sorted(os.listdir(store)) == before_listing


# --- allowlisted -----------------------------------------------------------------
# Bites on: allowlisted honours exact action+workflow pairs only — near-misses and
# structural exclusions must not reach silence.

def test_allowlisted_exact_match():
    entries = [{"action": "run-workflow", "workflow": "Preview seed"}]
    cmd = "gh workflow run 'Preview seed'"
    assert oa.allowlisted(cmd, "run-workflow", entries) is True


@pytest.mark.parametrize("workflow,quoted", [
    ("preview seed", "'preview seed'"),
    ("Preview seed ", "'Preview seed '"),
    ("Preview seed.yml", "'Preview seed.yml'"),
    ("Preview", "Preview"),
    ("Preview seed extra", "'Preview seed extra'"),
])
def test_allowlisted_near_miss(workflow, quoted):
    entries = [{"action": "run-workflow", "workflow": "Preview seed"}]
    cmd = "gh workflow run %s" % quoted
    assert oa.workflow_run_dispatch(cmd) == {"workflow": workflow, "ref": None}
    assert oa.allowlisted(cmd, "run-workflow", entries) is False


def test_allowlisted_different_action():
    entries = [{"action": "run-workflow", "workflow": "deploy.yml"}]
    assert oa.allowlisted("gh pr merge 1", "merge-pr", entries) is False


def test_allowlisted_glob_entry_does_not_match():
    entries = [{"action": "run-workflow", "workflow": "*"}]
    assert oa.allowlisted("gh workflow run deploy.yml", "run-workflow", entries) is False


# --- classify: allowlist end-to-end --------------------------------------------
# Bites on: classify consults the allow file only when calibrated; indeterminate
# never reads it; rejected-file notes surface in stderr and the ask reason.

def test_classify_calibrated_allowlisted_dispatch_allows(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 1,
                            "allow": [{"action": "run-workflow", "workflow": "deploy.yml"}]})
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    assert oa.classify("gh workflow run deploy.yml", str(tmp_path)) == ("allow", "")


def test_classify_calibrated_non_allowlisted_dispatch_asks(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 1,
                            "allow": [{"action": "run-workflow", "workflow": "other.yml"}]})
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    decision, reason = oa.classify("gh workflow run deploy.yml", str(tmp_path))
    assert decision == "ask"
    assert "owner-authority action 'run-workflow'" in reason


def test_classify_calibrated_allowlisted_but_enable_asks(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 1,
                            "allow": [{"action": "run-workflow", "workflow": "ci.yml"}]})
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    decision, _ = oa.classify("gh workflow enable ci.yml", str(tmp_path))
    assert decision == "ask"


def test_classify_indeterminate_does_not_read_allow_file(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 1,
                            "allow": [{"action": "run-workflow", "workflow": "deploy.yml"}]})
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "indeterminate")

    def _tripwire(*a, **k):
        raise AssertionError("read_allow_file must not be called when indeterminate")

    monkeypatch.setattr(oa, "read_allow_file", _tripwire)
    decision, _ = oa.classify("gh workflow run deploy.yml", str(tmp_path))
    assert decision == "ask"


def test_classify_indeterminate_ignores_matching_allow_file(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 1,
                            "allow": [{"action": "run-workflow", "workflow": "deploy.yml"}]})
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "indeterminate")
    decision, _ = oa.classify("gh workflow run deploy.yml", str(tmp_path))
    assert decision == "ask"


def test_classify_uncalibrated_allows_even_with_matching_file(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 1,
                            "allow": [{"action": "run-workflow", "workflow": "deploy.yml"}]})
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "uncalibrated")
    assert oa.classify("gh workflow run deploy.yml", str(tmp_path)) == ("allow", "")


def test_classify_hostile_merge_pr_file_does_not_silence_pr_merge(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 1,
                            "allow": [{"action": "merge-pr", "workflow": "x"}]})
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    decision, reason = oa.classify("gh pr merge 42 --squash", str(tmp_path))
    assert decision == "ask"
    assert "merge-pr" in reason
    assert "can never be allowlisted" in reason


def test_classify_workflow_dispatch_ask_reason_has_doc_pointer(tmp_path, monkeypatch):
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    _, reason = oa.classify("gh workflow run deploy.yml", str(tmp_path))
    assert "reference/owner-authority-allowlist.md" in reason


def test_classify_pr_merge_ask_reason_has_no_doc_pointer(tmp_path, monkeypatch):
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    _, reason = oa.classify("gh pr merge 42 --squash", str(tmp_path))
    assert "reference/owner-authority-allowlist.md" not in reason


@pytest.mark.parametrize("command", _GATED)
def test_classify_gated_still_asks_without_allow_file(command, monkeypatch):
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    decision, _ = oa.classify(command, "/somewhere")
    assert decision == "ask"


def test_classify_rejected_file_note_in_reason(tmp_path, monkeypatch, capsys):
    store = _pin_allow_store(tmp_path, monkeypatch)
    os.makedirs(store, exist_ok=True)
    path = os.path.join(store, oa.ALLOW_FILENAME)
    with open(path, "w") as fh:
        fh.write("{ not json")
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    decision, reason = oa.classify("gh workflow run deploy.yml", str(tmp_path))
    assert decision == "ask"
    assert "rejected (invalid JSON)" in reason
    captured = capsys.readouterr()
    assert "invalid JSON" in captured.err


def test_classify_writes_structural_note_to_stderr(tmp_path, monkeypatch, capsys):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 1,
                            "allow": [{"action": "merge-pr", "workflow": "x"}]})
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    oa.classify("gh pr merge 42 --squash", str(tmp_path))
    captured = capsys.readouterr()
    assert "structurally-excluded" in captured.err


def test_classify_workflow_target_none_still_asks_despite_matching_entry(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 1,
                            "allow": [{"action": "run-workflow", "workflow": "main"}]})
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    decision, _ = oa.classify("gh workflow run --repo=o/r", str(tmp_path))
    assert decision == "ask"


# --- invariant: repo-flag census -------------------------------------------------
# Every _REPO_FLAGS member refuses parse in both spellings and both positions.

@pytest.mark.parametrize("flag", sorted(oa._REPO_FLAGS))
def test_repo_flags_refuse_parse_census(flag):
    workflow = "deploy.yml"
    spaced_before = "gh workflow run %s o/r %s" % (flag, workflow)
    spaced_after = "gh workflow run %s %s o/r" % (workflow, flag)
    eq_before = "gh workflow run %s=o/r %s" % (flag, workflow)
    eq_after = "gh workflow run %s %s=o/r" % (workflow, flag)
    for cmd in (spaced_before, spaced_after, eq_before, eq_after):
        assert oa.workflow_run_dispatch(cmd) is None, cmd


# --- invariant: ref-flag census --------------------------------------------------
# Every _REF_FLAGS member never matches bare-name entry but matches opted-in v2 entry.

_V2_REF_ENTRY = [
    {"action": "run-workflow", "workflow": "Preview seed", "allows_refs": True},
]
_BARE_ENTRY = [{"action": "run-workflow", "workflow": "Preview seed"}]


@pytest.mark.parametrize("flag", sorted(oa._REF_FLAGS))
def test_ref_flags_never_match_bare_name_census(flag):
    workflow = "Preview seed"
    for cmd in (
        'gh workflow run "%s" %s main' % (workflow, flag),
        'gh workflow run "%s" %s=main' % (workflow, flag),
    ):
        assert oa.allowlisted(cmd, "run-workflow", _BARE_ENTRY) is False, cmd


@pytest.mark.parametrize("flag", sorted(oa._REF_FLAGS))
def test_ref_flags_match_opted_in_v2_census(flag):
    workflow = "Preview seed"
    for cmd in (
        'gh workflow run "%s" %s main' % (workflow, flag),
        'gh workflow run "%s" %s=main' % (workflow, flag),
    ):
        assert oa.allowlisted(cmd, "run-workflow", _V2_REF_ENTRY) is True, cmd


# --- invariant: branch-preview acceptance pair -----------------------------------
_BRANCH_PREVIEW_CMD = 'gh workflow run "Preview seed" --ref my-feature-branch'
_V2_ALLOW_FILE = {
    "schemaVersion": 2,
    "allow": [
        {"action": "run-workflow", "workflow": "Preview seed", "ref": "any"},
    ],
}


def test_branch_preview_refuses_without_v2_grant(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 1,
                            "allow": [{"action": "run-workflow", "workflow": "Preview seed"}]})
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    decision, _ = oa.classify(_BRANCH_PREVIEW_CMD, str(tmp_path))
    assert decision == "ask"


def test_branch_preview_allows_with_v2_grant(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, _V2_ALLOW_FILE)
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    assert oa.classify(_BRANCH_PREVIEW_CMD, str(tmp_path)) == ("allow", "")


_V2_BARE_ALLOW_FILE = {
    "schemaVersion": 2,
    "allow": [{"action": "run-workflow", "workflow": "Preview seed"}],
}
_BARE_DISPATCH = 'gh workflow run "Preview seed"'


def test_classify_v2_bare_entry_allows_bare_dispatch(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, _V2_BARE_ALLOW_FILE)
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    assert oa.classify(_BARE_DISPATCH, str(tmp_path)) == ("allow", "")


@pytest.mark.parametrize("flag", sorted(oa._REF_FLAGS))
def test_classify_v2_bare_entry_refuses_ref_dispatch(flag, tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, _V2_BARE_ALLOW_FILE)
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    workflow = "Preview seed"
    for cmd in (
        'gh workflow run "%s" %s main' % (workflow, flag),
        'gh workflow run "%s" %s=main' % (workflow, flag),
    ):
        decision, _ = oa.classify(cmd, str(tmp_path))
        assert decision == "ask", cmd


@pytest.mark.parametrize("flag", sorted(oa._REF_FLAGS))
def test_classify_v2_ref_any_allows_ref_dispatch(flag, tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, _V2_ALLOW_FILE)
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    workflow = "Preview seed"
    for cmd in (
        'gh workflow run "%s" %s main' % (workflow, flag),
        'gh workflow run "%s" %s=main' % (workflow, flag),
    ):
        assert oa.classify(cmd, str(tmp_path)) == ("allow", ""), cmd


def test_classify_ref_dispatch_without_grant_still_asks(tmp_path, monkeypatch):
    _pin_allow_store(tmp_path, monkeypatch)
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    decision, _ = oa.classify(_BRANCH_PREVIEW_CMD, str(tmp_path))
    assert decision == "ask"


# --- fail-closed edges (enumerated) ----------------------------------------------

def test_edge_ref_flag_missing_value_refuses():
    assert oa.workflow_run_dispatch("gh workflow run deploy.yml --ref") is None


def test_edge_repeated_ref_flag_refuses():
    assert oa.workflow_run_dispatch("gh workflow run --ref a --ref b deploy.yml") is None


def test_edge_empty_ref_eq_form_refuses():
    assert oa.workflow_run_dispatch("gh workflow run --ref= deploy.yml") is None


def test_edge_ref_command_against_bare_name_entry_no_match():
    cmd = 'gh workflow run "Preview seed" --ref main'
    entries = [{"action": "run-workflow", "workflow": "Preview seed"}]
    assert oa.allowlisted(cmd, "run-workflow", entries) is False


@pytest.mark.parametrize("bad_ref", ["main", "feat/*", ""])
def test_edge_v2_entry_bad_ref_dropped_at_read(tmp_path, monkeypatch, bad_ref):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 2, "allow": [
        {"action": "run-workflow", "workflow": "deploy.yml", "ref": bad_ref},
    ]})
    entries, notes = oa.read_allow_file(str(tmp_path))
    assert entries == []
    assert any("invalid ref" in text for _, _, text in notes)


def test_edge_v1_ref_key_dropped_not_bare_grant(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 1, "allow": [
        {"action": "run-workflow", "workflow": "deploy.yml", "ref": "any"},
    ]})
    entries, notes = oa.read_allow_file(str(tmp_path))
    assert entries == []
    assert any(
        text == (
            "ignored entry with ref key under schemaVersion 1 — "
            "bump owner-authority-allow.json to schemaVersion 2"
        )
        for _, _, text in notes
    )
    cmd = "gh workflow run deploy.yml"
    assert oa.allowlisted(cmd, "run-workflow", entries) is False


@pytest.mark.parametrize("bad_ref", [True, 1, None, [], {}])
def test_edge_v2_ref_wrong_type_dropped(tmp_path, monkeypatch, bad_ref):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 2, "allow": [
        {"action": "run-workflow", "workflow": "deploy.yml", "ref": bad_ref},
    ]})
    entries, notes = oa.read_allow_file(str(tmp_path))
    assert entries == []
    assert any("invalid ref" in text for _, _, text in notes)


def test_edge_shell_expandable_in_ref_refuses():
    assert oa.workflow_run_dispatch('gh workflow run deploy.yml --ref=$BRANCH') is None


def test_edge_zero_positionals_refuses():
    assert oa.workflow_run_dispatch("gh workflow run") is None


def test_edge_multiple_positionals_refuses():
    assert oa.workflow_run_dispatch("gh workflow run a b") is None


def test_edge_enable_never_allowlistable(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 2, "allow": [
        {"action": "run-workflow", "workflow": "ci.yml", "ref": "any"},
    ]})
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    decision, _ = oa.classify("gh workflow enable ci.yml", str(tmp_path))
    assert decision == "ask"


def test_edge_structural_excluded_with_ref_still_ignored(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 2, "allow": [
        {"action": "merge-pr", "workflow": "x", "ref": "any"},
    ]})
    entries, notes = oa.read_allow_file(str(tmp_path))
    assert entries == []
    assert any(kind == "structural" for kind, _, _ in notes)


def test_read_allow_file_v2_valid_ref_any_entry(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": 2, "allow": [
        {"action": "run-workflow", "workflow": "Preview seed", "ref": "any"},
    ]})
    entries, notes = oa.read_allow_file(str(tmp_path))
    assert entries == [{"action": "run-workflow", "workflow": "Preview seed",
                        "allows_refs": True}]
    assert notes == []


def test_v2_entry_covers_bare_dispatch(tmp_path, monkeypatch):
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, _V2_ALLOW_FILE)
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    assert oa.classify('gh workflow run "Preview seed"', str(tmp_path)) == ("allow", "")


@pytest.mark.parametrize("schema_version", [1, 2])
def test_classify_file_supplied_allows_refs_never_authorizes_ref_dispatch(
        schema_version, tmp_path, monkeypatch):
    """allows_refs in file input is never honored — only derived from validated ref sentinel."""
    store = _pin_allow_store(tmp_path, monkeypatch)
    _write_allow_at(store, {"schemaVersion": schema_version, "allow": [
        {"action": "run-workflow", "workflow": "Preview seed", "allows_refs": True},
    ]})
    monkeypatch.setattr(oa, "calibration_state", lambda cwd: "calibrated")
    cmd = 'gh workflow run "Preview seed" --ref my-feature-branch'
    decision, _ = oa.classify(cmd, str(tmp_path))
    assert decision == "ask", cmd
