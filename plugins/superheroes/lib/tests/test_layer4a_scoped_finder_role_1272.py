import importlib.util
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
_MOD = os.path.join(_LIB, "dispatch_guard.py")


def _load(name, filename):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


MR = _load("model_registry", "model_registry.py")
DG = _load("dispatch_guard", "dispatch_guard.py")
SB = _load("seat_bundle", "seat_bundle.py")
ED = _load("engine_dispatch", "engine_dispatch.py")

_ROLE = "scoped-finder"


def _guard_check(seat):
    proc = subprocess.run(
        [sys.executable, _MOD, "check", "--seat", json.dumps(seat)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc


def test_edge1_codex_scoped_finder_guard_check():
    proc = _guard_check(
        {
            "vendor": "codex",
            "model": "gpt-5.6-sol",
            "effort": "xhigh",
            "role": _ROLE,
        }
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["model_id"] == "gpt-5.6-sol"
    assert payload["effort"] == "xhigh"


def test_edge2_cursor_scoped_finder_guard_check():
    proc = _guard_check(
        {
            "vendor": "cursor",
            "model": "cursor-grok-4.6",
            "effort": "xhigh",
            "role": _ROLE,
        }
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["model_id"] == "cursor-grok-4.6"
    assert payload["effort"] == "xhigh"


def test_edge2_claude_scoped_finder_guard_check():
    proc = _guard_check(
        {
            "vendor": "claude",
            "model": "opus",
            "effort": "xhigh",
            "role": _ROLE,
        }
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["model_id"] == "opus-5"
    assert payload["effort"] == "xhigh"
    assert payload["dispatch_token"] == "opus"


def test_edge3_reviewer_cell_refused_under_scoped_finder():
    result = DG.validate(_ROLE, "codex", "gpt-5.6-terra")
    assert result["ok"] is False
    assert "gpt-5.6-terra" in result["reason"]


def test_edge4_standalone_role_flag_refused(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("review\n", encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    seat = json.dumps(
        {
            "vendor": "codex",
            "model": "gpt-5.6-sol",
            "effort": "xhigh",
            "role": _ROLE,
        }
    )
    argv = [
        "dispatch-review",
        "--role",
        _ROLE,
        "--seat",
        seat,
        "--prompt-path",
        str(prompt),
        "--repo-root",
        str(repo),
        "--run-dir",
        str(run_dir),
    ]
    assert SB.scan_dropped_flags(argv) == ["--role"]
    assert ED.main(argv) == 1
    result = json.loads(capsys.readouterr().out.strip())
    assert result["entryReason"] == "legacy-seat-args"


def test_edge5_not_on_model_tier_or_owner_tunable_surfaces():
    assert _ROLE not in MR.model_tier_roles()
    owner_tunable = tuple(
        role for role, meta in MR._ROLE_META.items() if meta.get("owner_tunable")
    )
    assert _ROLE not in owner_tunable


@pytest.mark.parametrize("vendor", MR.vendors())
def test_t_same_scoped_finder_matches_reviewer_deep_cells(vendor):
    assert MR.matrix_config(_ROLE, vendor) == MR.matrix_config("reviewer-deep", vendor)


def test_t_parse_template_documented_codex_bundle():
    seat = json.dumps(
        {
            "vendor": "codex",
            "model": "gpt-5.6-sol",
            "effort": "xhigh",
            "role": _ROLE,
        }
    )
    resolved = SB.resolve_entry(seat, verb="dispatch-review")
    assert resolved["ok"] is True
    assert resolved["vendor"] == "codex"
    assert resolved["model"] == "gpt-5.6-sol"
    assert resolved["effort"] == "xhigh"
    assert resolved["role"] == _ROLE
