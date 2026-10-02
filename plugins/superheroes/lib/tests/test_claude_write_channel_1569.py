"""#1569: the claude write channel allows the demonstrated command families by targeted rule.

Invariant: the settings always carry the same five `Bash(<family>:*)` allow rules, never a blanket
`Bash` allow, whatever the sandbox dict holds; the argv stays the sandboxed shape.

The rule literals are spelled out as strings on purpose: a test that reaches them through the
module constant stays green under any value (rubric/bite-proof.md).

Detector axes (bite-proof):
- test_settings_allow_is_the_five_targeted_rules — rule list: exactly the five rules, in order
- test_allow_never_blanket — scope: no rule is a blanket or a non-family shape
- test_allow_unconditional_on_sandbox_keys — unconditional: no sandbox key changes the rules
- test_argv_stays_sandboxed_and_carries_rules — argv: the built argv is sandboxed and carries them
"""
import json
import re

# The 1554 suite's harness (and, through it, the write-dispatch suite's autouse fixture).
from test_claude_write_sandbox_1554 import (  # noqa: F401
    EA,
    _SANDBOX,
    _assert_sandboxed_shape,
    _pin_temp_base_to_tmp_path,
    _settings_of,
    _write_argv,
)

_ALL_ACCESS = {
    "allowedDomains": ["pypi.org"], "localPorts": True,
    "localSocketDirs": ["/tmp/claude-501"], "extraWritePaths": ["/x/cache"],
}


def _permissions(sandbox):
    return json.loads(EA.claude_write_sandbox_settings(sandbox))["permissions"]


def test_settings_allow_is_the_five_targeted_rules():
    # axis: rule list — exactly the five targeted rules, in order, with the deny list unchanged
    assert _permissions(_SANDBOX) == {
        "allow": ["Bash(python:*)", "Bash(python3:*)", "Bash(pytest:*)",
                  "Bash(scripts/pinned-python:*)", "Bash(echo:*)"],
        "deny": ["WebFetch", "WebSearch"],
    }


def test_allow_never_blanket():
    # axis: scope — every rule names one command family; none is a bare or wildcard Bash allow
    allow = _permissions(_SANDBOX)["allow"]
    assert allow
    for rule in allow:
        assert rule not in ("Bash", "Bash(*)"), rule
        assert re.match(r"^Bash\([^()*]+:\*\)$", rule), rule


def test_allow_unconditional_on_sandbox_keys():
    # axis: unconditional — the permissions block does not vary with uvCacheDir or any access option
    base = _permissions(_SANDBOX)
    assert _permissions(dict(_SANDBOX, uvCacheDir="/cache/uv")) == base
    assert _permissions(dict(_SANDBOX, uvCacheDir="/cache/uv", access=dict(_ALL_ACCESS))) == base


def test_argv_stays_sandboxed_and_carries_rules():
    # axis: argv — the built argv keeps the sandboxed shape and its settings carry the five rules
    res = _write_argv()
    assert res["reason"] is None
    _assert_sandboxed_shape(res["argv"])
    assert _settings_of(res["argv"])["permissions"]["allow"] == [
        "Bash(python:*)", "Bash(python3:*)", "Bash(pytest:*)",
        "Bash(scripts/pinned-python:*)", "Bash(echo:*)",
    ]
