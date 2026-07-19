"""Unit tests for lib/owner_authority.py — the minimal owner-authority classifier (#482).

Covers the enumerated command set (lifted verbatim from the retired enforcer), the tri-state
calibration probe (calibrated / uncalibrated / indeterminate), the strictly-read-only guarantee,
and the classify() decision (ask only for an owner-authority command on a calibrated OR
indeterminate project; allow otherwise).
"""
import os

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
