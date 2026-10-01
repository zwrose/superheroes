"""#1554: the calibrated implementation engine decides the implementer's write argv.

Invariant: the implementer seat resolved from the project's calibration, run through the chain
the workhorse dispatch-mechanics supervised-write block runs, yields the sandboxed claude write
argv for `claude` (also the default when unset or invalid) and the unchanged cursor argv for
`cursor`."""
import json

import pytest

import engine_adapter as EA
import engine_pref
import model_registry

_SANDBOX = {
    "writeRoots": ["/work/wt", "/work/main/.git/worktrees/wt", "/work/main/.git"],
    "denyWrite": ["/work/main/.git/hooks", "/work/main/.git/config",
                  "/work/main/.git/worktrees/wt/config.worktree"],
    "uvCacheDir": None,
}


def _routed_argv(prefs, tiers):
    rows = engine_pref.dispatch_calibration_rows(prefs, tiers)
    row = next(r for r in rows if r["role"] == "implementer")
    resolved = model_registry.resolve_dispatch("implementer", row["engine"], row["model"])
    seat = {"vendor": row["engine"], "model": resolved["model_id"], "effort": resolved["effort"]}
    opts = {"cwd": "/work/wt", "claudeWriteSandbox": dict(_SANDBOX)}
    result = EA.build_argv_result(seat, "build", opts)
    return row["engine"], resolved["model_id"], result["argv"]


_CLAUDE_CASES = [
    pytest.param({}, {}, id="absent"),
    pytest.param({"implementation": "claude"}, {"implementer": "sonnet"}, id="explicit-claude"),
    pytest.param({"implementation": "bogus"}, {}, id="invalid-value"),
]


@pytest.mark.parametrize("prefs,tiers", _CLAUDE_CASES)
def test_claude_calibration_routes_to_sandboxed_write_argv(prefs, tiers):
    engine, model_id, argv = _routed_argv(prefs, tiers)
    assert engine == "claude"
    assert model_id == "sonnet-5.5"
    for flag in ("--restricted", "--tools", "--strict-mcp-config", "--settings"):
        assert flag in argv, (flag, argv)
    assert argv[argv.index("--model") + 1] == "sonnet"
    settings = json.loads(argv[argv.index("--settings") + 1])
    assert settings["sandbox"]["enabled"] is True
    assert settings["sandbox"]["network"]["allowedDomains"] == []


def test_cursor_calibration_keeps_the_cursor_argv():
    engine, model_id, argv = _routed_argv(
        {"implementation": "cursor"}, {"implementer": "sonnet"})
    assert engine == "cursor"
    assert model_id == "composer-2.5"
    assert argv[0] == "cursor-agent"
    assert "composer-2.5" in argv
    assert "--settings" not in argv
