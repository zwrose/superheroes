"""Test-only git double for the round driver's post-fix head-diff derivation (#1419 part i).

In production the driver derives the diff a panel reviews from git at the fold head, and a
session that cannot derive parks — there is no fallback. The suite's fixtures, though, fold fixers
with synthetic head-diff strings and usually no pinned base or real repository. This double stands
in for git in those tests: when a fold runs with no explicit derivation seam, "git" answers with
the diff the fixture supplied, recorded at the head the fold's checkout is at (never a declared
one), and a session minted from a config (never through the CLI's Setup binding) records the head
its meta declares, else the one its checkout is at. It lives in test
code only.

Opt out with ``@pytest.mark.real_git_head_diff`` (module-level ``pytestmark`` works too): the
stale-diff, derivation and bite-proof tests run with the double OFF, against real temporary git
repositories.
"""
import hashlib
import os
import subprocess
import sys
import types

MARKER = "real_git_head_diff"
_DOUBLE_ATTR = "_head_diff_double_installed"


def _is_round_driver(module):
    path = getattr(module, "__file__", None) or ""
    return (isinstance(module, types.ModuleType)
            and os.path.basename(path) == "round_driver.py"
            and hasattr(module, "_fold_fixer"))


_SCAN_CACHE = {"key": None, "found": ()}


def round_driver_copies(extra=()):
    """Every loaded copy of round_driver: the imported one and the ones test modules loaded by
    file spec (held in their globals). The scan is cached while the set of loaded modules (and the
    requesting test module) is unchanged, so it does not walk every module for every test."""
    key = (len(sys.modules), tuple(id(m) for m in extra))
    if _SCAN_CACHE["key"] == key:
        return list(_SCAN_CACHE["found"])
    found = {}
    roots = [m for m in list(sys.modules.values()) + list(extra) if m is not None]
    # Test modules load their own copies by file spec, sometimes inside another spec-loaded test
    # module; look one module level down as well.
    root_ids = {id(m) for m in roots}
    nested = [v for m in roots for v in list(getattr(m, "__dict__", {}).values())
              if isinstance(v, types.ModuleType) and id(v) not in root_ids]
    for module in roots + nested:
        if _is_round_driver(module):
            found[id(module)] = module
        for value in list(getattr(module, "__dict__", {}).values()):
            if _is_round_driver(value):
                found[id(value)] = value
    _SCAN_CACHE["key"], _SCAN_CACHE["found"] = key, tuple(found.values())
    return list(found.values())


def _wrap(original, module):
    def fold_fixer(state, config, artifact, changed_subjects_seam=None, session_dir=None,
                   head_diff_seam=None):
        if head_diff_seam is None:
            supplied, _source = module._resolve_head_diff(
                artifact if isinstance(artifact, dict) else {})

            def head_diff_seam(st):
                # Like git, record the pair: the head the checkout is at now, resolved the way the
                # driver's derivation resolves it — never the head a fixture declares (none on the
                # in-process leg, which has no repository).
                if isinstance(supplied, str) and not module._IN_PROCESS_LEG.get():
                    head = _live_fold_head(module, st, session_dir)
                    if head is not None:
                        st["headDiffSha"] = head
                        st["headDiffDigest"] = module.review_diff_digest(supplied)
                return supplied
        return original(state, config, artifact, changed_subjects_seam, session_dir=session_dir,
                        head_diff_seam=head_diff_seam)
    setattr(fold_fixer, _DOUBLE_ATTR, True)
    return fold_fixer


def _live_fold_head(module, state, session_dir):
    """The head the fold's checkout is at now: the driver's own repository resolution and
    hardened lookup with a session directory, else the config's `repoRoot` (or the cwd). A
    declared `headSha` is never read. With a session directory a head git cannot resolve is None
    (the fold then resolves, and refuses, on its own); without one, a stand-in SHA derived from the
    fixture's diff when no repository answers."""
    config = state.get("config") or {}
    if session_dir:
        root = module._resolve_repo_root(session_dir, state)
    else:
        root = config.get("repoRoot") if isinstance(config.get("repoRoot"), str) else os.getcwd()
    head = module._hardened_head(root) if root else None
    if isinstance(head, str) and len(head) in (40, 64):
        return head
    if session_dir:
        return None
    return hashlib.sha1(str(config.get("diff")).encode("utf-8")).hexdigest()


def _checkout_head(config):
    """The HEAD of the checkout a fixture session runs in (its `repoRoot`, else the cwd), or a
    stand-in SHA derived from the fixture's diff when there is no repository."""
    declared = config.get("headSha")
    if isinstance(declared, str) and len(declared) in (40, 64):
        return declared  # the Setup binding refuses unless the declared head is the derived one
    root = config.get("repoRoot") if isinstance(config.get("repoRoot"), str) else os.getcwd()
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                              text=True, timeout=10)
        head = proc.stdout.strip() if proc.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        head = ""
    if len(head) in (40, 64):
        return head
    return hashlib.sha1(str(config.get("diff")).encode("utf-8")).hexdigest()


def _wrap_new_state(original, module):
    def new_state(config=None):
        state = original(config)
        # Like the fresh `next`'s derivation, record the head the round-1 diff was taken at: these
        # fixtures mint sessions from a config, never through the CLI's Setup binding.
        cfg = state.get("config") or {}
        if state.get("reviewedDiffSha") is None and not module._IN_PROCESS_LEG.get():
            state["reviewedDiffSha"] = _checkout_head(cfg)
            if isinstance(cfg.get("diff"), str):
                state["reviewedDiffDigest"] = module.review_diff_digest(cfg["diff"])
        return state
    setattr(new_state, _DOUBLE_ATTR, True)
    return new_state


def _wrap_cmd_next_locked(original, module):
    def cmd_next_locked(session_dir, config_overrides=None):
        # The Setup binding refuses unless meta's recorded head is the derived one, so a fixture
        # that declares `meta.headSha` records exactly that head.
        fresh = not os.path.exists(os.path.join(session_dir, module.STATE_FILE))
        if fresh and isinstance(config_overrides, dict) and "diffHead" not in config_overrides:
            meta_head = module._session_meta(session_dir).get("headSha")
            if isinstance(meta_head, str) and len(meta_head) in (40, 64):
                diff = config_overrides.get("diff")
                config_overrides = dict(config_overrides, diffHead={
                    "sha": meta_head,
                    "digest": module.review_diff_digest(diff) if isinstance(diff, str) else None})
        return original(session_dir, config_overrides)
    setattr(cmd_next_locked, _DOUBLE_ATTR, True)
    return cmd_next_locked


def install(monkeypatch, extra=()):
    """Install the double on every loaded round_driver copy (undone by monkeypatch)."""
    for module in round_driver_copies(extra):
        if getattr(module._fold_fixer, _DOUBLE_ATTR, False):
            continue
        monkeypatch.setattr(module, "_fold_fixer", _wrap(module._fold_fixer, module))
        monkeypatch.setattr(module, "new_state", _wrap_new_state(module.new_state, module))
        monkeypatch.setattr(module, "_cmd_next_locked",
                            _wrap_cmd_next_locked(module._cmd_next_locked, module))


def installed(module):
    return bool(getattr(module._fold_fixer, _DOUBLE_ATTR, False))
