"""Caller-contract builders and dispatch-CLI census (#WO-3)."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cli_contract as cc  # noqa: E402


def _load(name: str, filename: str):
    path = os.path.join(_LIB, filename)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ED = _load("engine_dispatch", "engine_dispatch.py")
DG = _load("dispatch_guard", "dispatch_guard.py")
SM = _load("seat_map", "seat_map.py")
RD = _load("round_driver", "round_driver.py")
MR = _load("model_registry", "model_registry.py")

_CENSUS_MODULES = (
    ("engine_dispatch", ED.build_parser()),
    ("dispatch_guard", DG.build_parser()),
    ("seat_map", SM.build_parser()),
    ("round_driver", RD.build_parser()),
)


def _git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    (repo / "f.txt").write_text("x", encoding="utf-8")
    subprocess.run(
        ["git", "add", "f.txt"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return str(repo)


def test_dispatch_cli_argument_census():
    """Every caller-supplied dispatch argument declares a contract."""
    for module_name, parser in _CENSUS_MODULES:
        missing = cc.census_undeclared(parser)
        assert missing == [], (
            f"{module_name} has undeclared caller-supplied arguments: {missing}"
        )
        unvalidated = cc.census_unvalidated(parser)
        assert unvalidated == [], (
            f"{module_name} has declared-but-unvalidated caller-supplied arguments: {unvalidated}"
        )


def test_dispatch_review_run_dir_symlink_refused_through_cli(tmp_path, capsys):
    real_dir = tmp_path / "real-run"
    real_dir.mkdir()
    symlink = tmp_path / "run-link"
    symlink.symlink_to(real_dir)
    repo = _git_repo(tmp_path)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("review this", encoding="utf-8")
    rc = ED.main([
        "dispatch-review",
        "--engine", "cursor",
        "--effort", "high",
        "--prompt-path", str(prompt),
        "--repo-root", str(repo),
        "--run-dir", str(symlink),
    ])
    assert rc == 0
    result = json.loads(capsys.readouterr().out.strip())
    assert result["ok"] is False
    assert result["detail"] == "run-dir-is-symlink"


def test_role_rejects_valid_vendor_name():
    with pytest.raises(SystemExit):
        DG.build_parser().parse_args(
            ["check", "--role", "claude", "--vendor", "cursor"]
        )


def test_model_slot_rejects_valid_role_name():
    with pytest.raises(SystemExit):
        DG.build_parser().parse_args(
            [
                "check",
                "--role",
                "implementer",
                "--vendor",
                "cursor",
                "--model",
                "reviewer",
            ]
        )


def test_model_slot_accepts_unknown_registry_model():
    args = DG.build_parser().parse_args(
        [
            "check",
            "--role",
            "implementer",
            "--vendor",
            "cursor",
            "--model",
            "__totally-unknown-model-token__",
        ]
    )
    assert args.model == "__totally-unknown-model-token__"


def test_dispatch_review_repo_root_omitted_refused_at_argparse(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("review me", encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        ED.build_parser().parse_args(
            [
                "dispatch-review",
                "--engine",
                "codex",
                "--effort",
                "high",
                "--prompt-path",
                str(prompt),
            ]
        )
    assert excinfo.value.code == 2


def test_dispatch_review_repo_root_not_a_git_repo_refused_at_argparse(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("review me", encoding="utf-8")
    bare = tmp_path / "bare"
    bare.mkdir()
    with pytest.raises(SystemExit):
        ED.build_parser().parse_args(
            [
                "dispatch-review",
                "--engine",
                "codex",
                "--effort",
                "high",
                "--prompt-path",
                str(prompt),
                "--repo-root",
                str(bare),
            ]
        )


def test_dispatch_write_run_dir_creatable_when_parent_exists(tmp_path):
    parent = tmp_path / "runs"
    parent.mkdir()
    run_dir = parent / "new-run"
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("write me", encoding="utf-8")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    args = ED.build_parser().parse_args(
        [
            "dispatch-write",
            "--engine",
            "cursor",
            "--prompt-path",
            str(prompt),
            "--cwd",
            str(cwd),
            "--run-dir",
            str(run_dir),
        ]
    )
    assert args.run_dir == str(run_dir)
    assert not run_dir.exists()


def test_dispatch_write_run_dir_refused_when_parent_missing(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("write me", encoding="utf-8")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    run_dir = tmp_path / "missing" / "parent" / "run"
    with pytest.raises(SystemExit):
        ED.build_parser().parse_args(
            [
                "dispatch-write",
                "--engine",
                "cursor",
                "--prompt-path",
                str(prompt),
                "--cwd",
                str(cwd),
                "--run-dir",
                str(run_dir),
            ]
        )


def test_run_dir_existing_file_refused(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("write me", encoding="utf-8")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir", encoding="utf-8")
    with pytest.raises(SystemExit):
        ED.build_parser().parse_args(
            [
                "dispatch-write",
                "--engine",
                "cursor",
                "--prompt-path",
                str(prompt),
                "--cwd",
                str(cwd),
                "--run-dir",
                str(blocker),
            ]
        )


def test_contract_builders_expose_metadata():
    for name in (
        "role",
        "vendor",
        "effort",
        "model_not_a_role",
        "existing_directory",
        "creatable_path",
        "repo_root",
        "free_text",
        "integer",
    ):
        fn = getattr(cc, name)
        assert getattr(fn, cc.CLI_CONTRACT_ATTR, None) == name.replace("_", "-")


def test_effort_union_covers_registry_vendor_efforts():
    union = set()
    for vendor in MR.vendors():
        union.update(MR.effort_enum(vendor))
    for effort_value in union:
        assert cc.effort(effort_value) == effort_value


def test_vendor_rejects_unknown_value():
    with pytest.raises(argparse.ArgumentTypeError, match="unknown vendor"):
        cc.vendor("__not-a-registered-vendor__")


def test_effort_rejects_unknown_value():
    with pytest.raises(argparse.ArgumentTypeError, match="unknown effort"):
        cc.effort("__not-a-registered-effort__")


def test_census_reads_contract_from_parser_not_hand_list():
  # axis: a parser built through build_parser() carries declarations on its actions.
    parser = ED.build_parser()
    contracts = {
        (path, action.dest): cc.contract_for_action(action)
        for path, action in cc.iter_caller_supplied_actions(parser)
    }
    assert contracts[("dispatch-write",), "run_dir"] == "creatable-path"
    assert contracts[("dispatch-review",), "repo_root"] == "repo-root"
    assert contracts[("dispatch-review",), "model"] == "model-not-a-role"
    assert contracts[("dispatch-review",), "mode"] == "choices:review,brief-check"


def test_census_red_when_argument_lacks_contract():
    parser = ED.build_parser()
    sub = None
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            sub = action
            break
    assert sub is not None
    write = sub.choices["dispatch-write"]
    write.add_argument("--undeclared-bite-proof-arg", default=None)
    missing = cc.census_undeclared(parser)
    assert any(
        dest == "undeclared_bite_proof_arg" for _path, _opts, dest in missing
    )


def test_census_red_when_argument_declared_but_unvalidated():
    """Bite-axis: declared contract with no validator must fail census_unvalidated."""
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    probe = sub.add_parser("probe")
    action = probe.add_argument("--declared-only-arg", default=None)
    setattr(action, cc.ACTION_CONTRACT_ATTR, "unmapped-contract-token")
    unvalidated = cc.census_unvalidated(parser)
    assert any(
        dest == "declared_only_arg" for _path, _opts, dest, contract in unvalidated
    )
    assert any(
        contract == "unmapped-contract-token"
        for _path, _opts, _dest, contract in unvalidated
    )


def test_boolean_flag_contract_validated_on_round_driver_parser():
    contracts = {
        (path, action.dest): cc.contract_for_action(action)
        for path, action in cc.iter_caller_supplied_actions(RD.build_parser())
    }
    assert contracts[("record-result",), "supersede"] == "boolean-flag"
    assert contracts[("advance",), "break_lock"] == "boolean-flag"
    action = next(
        action for path, action in cc.iter_caller_supplied_actions(RD.build_parser())
        if path == ("advance",) and action.dest == "break_lock"
    )
    assert cc.contract_is_validated(action) is True
