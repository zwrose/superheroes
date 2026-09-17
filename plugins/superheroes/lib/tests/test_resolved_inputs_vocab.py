import importlib.util
import os
import shutil
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import dispatch_outcome
import resolved_inputs_vocab as riv
import seat_bundle


def _load_engine_dispatch():
    spec = importlib.util.spec_from_file_location(
        "engine_dispatch", os.path.join(_LIB, "engine_dispatch.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ED = _load_engine_dispatch()

_SV = importlib.util.spec_from_file_location(
    "sanitized_view", os.path.join(_LIB, "sanitized_view.py"),
)
_SV_MOD = importlib.util.module_from_spec(_SV)
_SV.loader.exec_module(_SV_MOD)


@pytest.fixture(autouse=True)
def _pin_temp_base_to_tmp_path(tmp_path, monkeypatch):
    base = str(tmp_path / "sanitized-temp-base")
    os.makedirs(base, exist_ok=True)
    monkeypatch.setattr(_SV_MOD.tempfile, "gettempdir", lambda: base)
    monkeypatch.setattr(ED.tempfile, "gettempdir", lambda: base)
    journal_root = str(tmp_path / "dispatch-journal-root")
    os.makedirs(journal_root, exist_ok=True)
    monkeypatch.setenv(ED.JOURNAL_ROOT_ENV, journal_root)
    yield

_EXPECTED_ENTRY_REFUSAL_REASONS = frozenset({
    "allowlist-malformed",
    "allowlist-raised",
    "allowlist-refused",
    "effort-invalid",
    "effort-key-absent",
    "effort-token-conflict",
    "expected-result-kind-invalid",
    seat_bundle.ENTRY_REASON_UNDECLARED,
    "internal-error",
    "invalid-model-effort",
    "legacy-seat-args",
    "max-wait-out-of-range",
    "mode-invalid",
    "mode-role-mismatch",
    "model-ambiguous",
    "model-invalid",
    "model-key-absent",
    "model-required",
    "seat-extra-keys",
    "role-key-absent",
    "role-null",
    "run-kind-role-mismatch",
    "run-kind-unclassified",
    "seat-empty",
    "seat-not-object",
    "seat-token-dropped",
    "seat-unparseable",
    "token-unresolvable",
    "undispatchable-vendor",
    "unknown-dispatch-kwargs",
    "unknown-model",
    "unknown-role",
    "unknown-vendor",
    "unknown-verb",
    "vendor-hint-mismatch",
    "vendor-invalid",
    "verb-role-mismatch",
})

_EXPECTED_DISPATCH_OUTCOME_REASONS = frozenset({
    dispatch_outcome.REASON_FORFEITED,
    dispatch_outcome.REASON_VACUOUS,
    dispatch_outcome.REASON_FORFEIT_ENGAGED_ARTIFACT,
    dispatch_outcome.REASON_UNRUNNABLE,
    dispatch_outcome.REASON_RUNNING,
})


def _valid_prompt(tmp_path, content="Review this code.\n"):
    p = tmp_path / "prompt.txt"
    p.write_text(content, encoding="utf-8")
    return str(p)


def _repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir(exist_ok=True)
    (root / ".git").write_text("gitdir: /fake/worktree\n", encoding="utf-8")
    return str(root)


class FakeRunner:
    def __init__(self, responses):
        self.responses = list(responses)

    def __call__(self, argv, prompt_bytes, timeout, progress_cb, cwd):
        if not self.responses:
            return ("", False, 0, "")
        return self.responses.pop(0)


def _fake_build_view(tmp_path):
    counter = {"n": 0}

    def build_view(repo_real, *, diff_base=None, pr_body_path=None, session_dir=None):
        counter["n"] += 1
        view_base = _SV_MOD.tempfile.gettempdir()
        view_dir = os.path.join(
            view_base,
            _SV_MOD.SANITIZED_VIEW_DIR_PREFIX + str(counter["n"]),
        )
        os.makedirs(view_dir, exist_ok=True)
        repo = os.path.realpath(repo_real)
        for name in os.listdir(repo):
            src = os.path.join(repo, name)
            dst = os.path.join(view_dir, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        return {
            "path": view_dir,
            "strategy": "git-archive-export",
            "stripped": [],
            "strippedCount": 0,
            "headSha": "abc123fake",
            "sourceDirty": False,
            "buildSeconds": 0.01,
            "bytes": 1,
            "fileCount": 1,
        }

    return build_view


def _codex_seat():
    return {"vendor": "codex", "model": "gpt-5.6-sol", "effort": "high", "role": "reviewer"}


def _opened_resolved_inputs(run_dir):
    records, _ = ED._journal_read(run_dir)
    opened = next(r for r in records if r.get("kind") == "run-opened")
    snapshot = opened.get("resolvedInputs")
    assert isinstance(snapshot, dict)
    return snapshot


def _source_marker_values(snapshot):
    return {key: value for key, value in snapshot.items() if key.endswith("Source")}


def test_put_resolved_refuses_undeclared_marker():
    snapshot = {}
    with pytest.raises(riv.UndeclaredSourceMarker) as exc_info:
        ED._put_resolved(snapshot, "engine", "codex", "not-a-marker")
    msg = str(exc_info.value)
    assert "not-a-marker" in msg
    assert "accepted:" in msg
    for marker in riv.SOURCE_MARKERS:
        assert marker in msg


def test_put_resolved_accepts_every_source_marker():
    for marker in riv.SOURCE_MARKERS:
        snapshot = {}
        ED._put_resolved(snapshot, "probe", "value", marker)
        assert snapshot["probeSource"] == marker


def test_undeclared_marker_refusal_does_not_expand_entry_refusal_reasons():
    assert seat_bundle.ENTRY_REFUSAL_REASONS == _EXPECTED_ENTRY_REFUSAL_REASONS


def test_undeclared_marker_refusal_does_not_expand_dispatch_outcome_reasons():
    assert dispatch_outcome.ALL_REASONS == _EXPECTED_DISPATCH_OUTCOME_REASONS


def test_live_dispatch_snapshot_source_markers_are_declared(tmp_path):
    repo_root = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    ED.dispatch_review(
        seat=_codex_seat(),
        prompt_path=_valid_prompt(tmp_path),
        repo_root=repo_root,
        run_engine=FakeRunner([]),
        build_view=_fake_build_view(tmp_path),
        run_dir=run_dir,
        max_wait=0,
        order_id="order-1",
    )
    snapshot = _opened_resolved_inputs(run_dir)
    for key, value in _source_marker_values(snapshot).items():
        assert value in riv.SOURCE_MARKERS, "%s=%r" % (key, value)
