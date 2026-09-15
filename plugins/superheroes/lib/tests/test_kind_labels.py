"""Fake-based units for kind_labels.py. No real gh or network — every gh call is faked."""
import json
import subprocess
from types import SimpleNamespace

import pytest

import kind_labels as kl


REPO = "owner/example"


def _labels_json(names):
    return json.dumps(
        [{"name": n, "color": "000000", "description": "x"} for n in names]
    )


def _make_run(handlers):
    calls = []
    queues = {}
    for key, value in handlers.items():
        if isinstance(value, list):
            queues[key] = list(value)
        else:
            queues[key] = [value]

    def _run(argv, **kwargs):
        calls.append(list(argv))
        key = tuple(argv)
        if key not in queues or not queues[key]:
            raise AssertionError("unexpected gh argv: %r" % argv)
        handler = queues[key].pop(0)
        if isinstance(handler, Exception):
            raise handler
        return handler

    return _run, calls


def _auth_ok():
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def _list_ok(names):
    return SimpleNamespace(returncode=0, stdout=_labels_json(names), stderr="")


def _create_ok():
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def _auth_argv():
    return kl._gh_auth_argv()


def _list_argv(repo=REPO):
    return kl._gh_label_list_argv(repo)


def _create_argv(name, repo=REPO):
    label = kl._label_by_name(name)
    return kl._gh_label_create_argv(repo, label)


# --- report success ------------------------------------------------------------

def test_report_both_present():
    run, calls = _make_run(
        {
            tuple(_auth_argv()): _auth_ok(),
            tuple(_list_argv()): _list_ok(list(kl.KIND_LABEL_NAMES)),
        }
    )
    result = kl.ensure_kind_labels(REPO, run=run)
    assert result["ok"] is True
    assert result["present"] == list(kl.KIND_LABEL_NAMES)
    assert result["missing"] == []
    assert result["created"] == []
    assert result["reason"] is None
    assert not any("create" in c for c in calls)


def test_report_one_present():
    run, _calls = _make_run(
        {
            tuple(_auth_argv()): _auth_ok(),
            tuple(_list_argv()): _list_ok(["kind:machinery"]),
        }
    )
    result = kl.ensure_kind_labels(REPO, run=run)
    assert result["ok"] is True
    assert result["present"] == ["kind:machinery"]
    assert result["missing"] == ["kind:product"]


# axis: report never invokes gh label create
def test_report_never_calls_create():
    run, calls = _make_run(
        {
            tuple(_auth_argv()): _auth_ok(),
            tuple(_list_argv()): _list_ok([]),
        }
    )
    kl.ensure_kind_labels(REPO, run=run)
    assert all("create" not in argv for argv in calls)


# --- apply ---------------------------------------------------------------------

def test_apply_creates_only_missing_labels():
    # axis: apply skips labels already present and creates only the missing one
    run, calls = _make_run(
        {
            tuple(_auth_argv()): _auth_ok(),
            tuple(_list_argv()): [
                _list_ok(["kind:machinery"]),
                _list_ok(list(kl.KIND_LABEL_NAMES)),
            ],
            tuple(_create_argv("kind:product")): _create_ok(),
        }
    )
    result = kl.ensure_kind_labels(REPO, apply=True, run=run)
    assert result["ok"] is True
    assert result["created"] == ["kind:product"]
    assert result["present"] == list(kl.KIND_LABEL_NAMES)
    assert result["missing"] == []
    create_calls = [c for c in calls if "create" in c]
    assert len(create_calls) == 1
    assert create_calls[0] == _create_argv("kind:product")


def test_apply_creates_both_when_missing():
    handlers = {
        tuple(_auth_argv()): _auth_ok(),
        tuple(_list_argv()): [
            _list_ok([]),
            _list_ok(list(kl.KIND_LABEL_NAMES)),
        ],
        tuple(_create_argv("kind:machinery")): _create_ok(),
        tuple(_create_argv("kind:product")): _create_ok(),
    }
    run, _calls = _make_run(handlers)
    result = kl.ensure_kind_labels(REPO, apply=True, run=run)
    assert result["ok"] is True
    assert set(result["created"]) == set(kl.KIND_LABEL_NAMES)


def test_apply_first_create_failure_still_attempts_second():
    # axis: one create failure does not skip the second label
    run, calls = _make_run(
        {
            tuple(_auth_argv()): _auth_ok(),
            tuple(_list_argv()): [
                _list_ok([]),
                _list_ok(["kind:product"]),
            ],
            tuple(_create_argv("kind:machinery")): SimpleNamespace(
                returncode=1, stdout="", stderr="permission denied"
            ),
            tuple(_create_argv("kind:product")): _create_ok(),
        }
    )
    result = kl.ensure_kind_labels(REPO, apply=True, run=run)
    assert result["ok"] is False
    assert "kind:machinery" in result["reason"]
    assert result["created"] == ["kind:product"]
    create_calls = [c for c in calls if "create" in c]
    assert len(create_calls) == 2


# axis: every gh call passes explicit --repo on the argv the helper builds
def test_gh_calls_pass_explicit_repo():
    run, calls = _make_run(
        {
            tuple(_auth_argv()): _auth_ok(),
            tuple(_list_argv()): _list_ok(list(kl.KIND_LABEL_NAMES)),
        }
    )
    kl.ensure_kind_labels(REPO, run=run)
    for argv in calls:
        if argv[0:2] == ["gh", "auth"]:
            continue
        assert "--repo" in argv
        assert argv[argv.index("--repo") + 1] == REPO


# --- fail-closed edges ---------------------------------------------------------

def test_edge_gh_not_on_path(monkeypatch):
    monkeypatch.setattr(kl.shutil, "which", lambda _name: None)
    result = kl.ensure_kind_labels(REPO, run=lambda *a, **k: None)
    assert result["ok"] is False
    assert result["reason"] == "gh not on PATH"


def test_edge_gh_not_authenticated():
    run, _calls = _make_run(
        {
            tuple(_auth_argv()): SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="You are not logged into any GitHub hosts",
            ),
        }
    )
    result = kl.ensure_kind_labels(REPO, run=run)
    assert result["ok"] is False
    assert "logged" in result["reason"].lower()


def test_edge_repo_does_not_resolve():
    run, _calls = _make_run(
        {
            tuple(_auth_argv()): _auth_ok(),
            tuple(_list_argv()): SimpleNamespace(
                returncode=1,
                stdout="",
                stderr=(
                    "GraphQL: Could not resolve to a Repository with the name "
                    "'owner/definitely-not-a-repo'. (repository)"
                ),
            ),
        }
    )
    result = kl.ensure_kind_labels(REPO, run=run)
    assert result["ok"] is False
    assert "Could not resolve to a Repository" in result["reason"]


def test_edge_label_list_json_not_list():
    run, _calls = _make_run(
        {
            tuple(_auth_argv()): _auth_ok(),
            tuple(_list_argv()): SimpleNamespace(
                returncode=0, stdout='{"name":"kind:machinery"}', stderr=""
            ),
        }
    )
    result = kl.ensure_kind_labels(REPO, run=run)
    assert result["ok"] is False
    assert "not a list" in result["reason"]


def test_edge_label_list_entry_not_object():
    run, _calls = _make_run(
        {
            tuple(_auth_argv()): _auth_ok(),
            tuple(_list_argv()): SimpleNamespace(
                returncode=0, stdout='["kind:machinery"]', stderr=""
            ),
        }
    )
    result = kl.ensure_kind_labels(REPO, run=run)
    assert result["ok"] is False
    assert "not an object" in result["reason"]


def test_edge_label_list_entry_missing_name():
    run, _calls = _make_run(
        {
            tuple(_auth_argv()): _auth_ok(),
            tuple(_list_argv()): SimpleNamespace(
                returncode=0, stdout='[{"color":"5319E7"}]', stderr=""
            ),
        }
    )
    result = kl.ensure_kind_labels(REPO, run=run)
    assert result["ok"] is False
    assert "no name" in result["reason"]


def test_edge_label_list_not_json():
    run, _calls = _make_run(
        {
            tuple(_auth_argv()): _auth_ok(),
            tuple(_list_argv()): SimpleNamespace(
                returncode=0, stdout="not json at all", stderr=""
            ),
        }
    )
    result = kl.ensure_kind_labels(REPO, run=run)
    assert result["ok"] is False
    assert "not JSON" in result["reason"]


def test_edge_label_already_exists_not_error_on_apply():
    run, _calls = _make_run(
        {
            tuple(_auth_argv()): _auth_ok(),
            tuple(_list_argv()): [
                _list_ok(["kind:machinery"]),
                _list_ok(list(kl.KIND_LABEL_NAMES)),
            ],
            tuple(_create_argv("kind:product")): SimpleNamespace(
                returncode=1,
                stdout="",
                stderr=(
                    'label with name "kind:product" already exists; '
                    "use `--force` to update its color and description"
                ),
            ),
        }
    )
    result = kl.ensure_kind_labels(REPO, apply=True, run=run)
    assert result["ok"] is True
    assert result["created"] == []
    assert "kind:product" in result["present"]


def test_edge_gh_call_hangs():
    run, _calls = _make_run(
        {
            tuple(_auth_argv()): subprocess.TimeoutExpired(cmd="gh", timeout=120),
        }
    )
    result = kl.ensure_kind_labels(REPO, run=run)
    assert result["ok"] is False
    assert "timed out" in result["reason"]


def test_edge_report_cannot_write():
    run, calls = _make_run(
        {
            tuple(_auth_argv()): _auth_ok(),
            tuple(_list_argv()): _list_ok([]),
        }
    )
    kl.ensure_kind_labels(REPO, apply=False, run=run)
    assert all("create" not in argv for argv in calls)


# --- module constants ----------------------------------------------------------

def test_closed_enumeration_only_two_labels():
    assert len(kl.KIND_LABELS) == 2
    assert kl.KIND_LABEL_NAMES == ("kind:machinery", "kind:product")


def test_label_metadata_matches_contract():
    machinery = kl._label_by_name("kind:machinery")
    product = kl._label_by_name("kind:product")
    assert machinery["color"] == "5319E7"
    assert product["color"] == "0E8A16"


# --- CLI -----------------------------------------------------------------------

def test_main_report_exit_zero(capsys, monkeypatch):
    def _fake(repo, apply=False):
        return {
            "ok": True,
            "repo": repo,
            "present": list(kl.KIND_LABEL_NAMES),
            "missing": [],
            "created": [],
            "reason": None,
        }

    monkeypatch.setattr(kl, "ensure_kind_labels", _fake)
    rc = kl.main(["--repo", REPO])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 0
    assert payload["ok"] is True
    assert set(payload) >= {"ok", "repo", "present", "missing", "created", "reason"}


def test_main_failure_exit_nonzero(capsys, monkeypatch):
    monkeypatch.setattr(
        kl,
        "ensure_kind_labels",
        lambda repo, apply=False: {
            "ok": False,
            "repo": repo,
            "present": [],
            "missing": list(kl.KIND_LABEL_NAMES),
            "created": [],
            "reason": "boom",
        },
    )
    rc = kl.main(["--repo", REPO])
    assert rc == 1
