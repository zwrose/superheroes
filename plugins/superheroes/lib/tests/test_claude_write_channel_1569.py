"""#1569: the claude write channel allows the demonstrated command families by targeted rule.

Invariant: the settings always carry the same eleven `Bash(<family>:*)` allow rules, never a blanket
`Bash` allow, whatever the sandbox dict holds; the argv stays the sandboxed shape.

The rule literals are spelled out as strings on purpose: a test that reaches them through the
module constant stays green under any value (rubric/bite-proof.md).

Detector axes (bite-proof):
- test_settings_allow_is_the_eleven_targeted_rules — rule list: exactly the eleven rules, in order
- test_allow_never_blanket — scope: no rule is a blanket or a non-family shape
- test_allow_rule_shape_admits_three_shapes_and_refuses_blankets — shape regex: three shapes in, blankets out
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

# The three admitted allow-rule shapes (#2275); the family token carries no paren, `*`, `=` or space.
_ALLOW_RULE_SHAPE = re.compile(
    r"^Bash\((?:[^()*=\s]+:\*|\*=\* [^()*=\s]+ \*|\*=\* [^()*=\s]+)\)$"
)


def _permissions(sandbox):
    return json.loads(EA.claude_write_sandbox_settings(sandbox))["permissions"]


def test_settings_allow_is_the_eleven_targeted_rules():
    # axis: rule list — exactly the eleven prefix rules then their two assignment-prefixed
    # forms each (#2275), in order, with the deny list unchanged
    assert _permissions(_SANDBOX) == {
        "allow": ["Bash(python:*)", "Bash(python3:*)", "Bash(pytest:*)",
                  "Bash(scripts/pinned-python:*)", "Bash(echo:*)",
                  "Bash(npm:*)", "Bash(npx:*)", "Bash(node:*)", "Bash(pnpm:*)",
                  "Bash(yarn:*)", "Bash(ps:*)",
                  "Bash(*=* python *)", "Bash(*=* python3 *)", "Bash(*=* pytest *)",
                  "Bash(*=* scripts/pinned-python *)", "Bash(*=* echo *)",
                  "Bash(*=* npm *)", "Bash(*=* npx *)", "Bash(*=* node *)",
                  "Bash(*=* pnpm *)", "Bash(*=* yarn *)", "Bash(*=* ps *)",
                  "Bash(*=* python)", "Bash(*=* python3)", "Bash(*=* pytest)",
                  "Bash(*=* scripts/pinned-python)", "Bash(*=* echo)",
                  "Bash(*=* npm)", "Bash(*=* npx)", "Bash(*=* node)",
                  "Bash(*=* pnpm)", "Bash(*=* yarn)", "Bash(*=* ps)"],
        "deny": ["WebFetch", "WebSearch"],
    }


def test_allow_never_blanket():
    # axis: scope — every rule is one of the three admitted shapes `Bash(f:*)`, `Bash(*=* f *)`,
    # `Bash(*=* f)` for a single family token f; none is a bare or wildcard Bash allow
    allow = _permissions(_SANDBOX)["allow"]
    assert allow
    for rule in allow:
        assert rule not in ("Bash", "Bash(*)"), rule
        assert _ALLOW_RULE_SHAPE.match(rule), rule


def test_allow_rule_shape_admits_three_shapes_and_refuses_blankets():
    # axis: shape regex — admits exactly the three family shapes; every blanket or wildcard-family
    # spelling is refused
    for rule in ("Bash(npx:*)", "Bash(*=* npx *)", "Bash(*=* scripts/pinned-python)"):
        assert _ALLOW_RULE_SHAPE.match(rule), rule
    for rule in ("Bash", "Bash(*)", "Bash(*=* *)", "Bash(*=* *  *)", "Bash(* npx *)",
                 "Bash(*=* np*x *)", "Bash(*:*)", "Bash(*=* npx :*)"):
        assert not _ALLOW_RULE_SHAPE.match(rule), rule


def test_allow_unconditional_on_sandbox_keys():
    # axis: unconditional — the permissions block does not vary with uvCacheDir or any access option
    base = _permissions(_SANDBOX)
    assert _permissions(dict(_SANDBOX, uvCacheDir="/cache/uv")) == base
    assert _permissions(dict(_SANDBOX, uvCacheDir="/cache/uv", access=dict(_ALL_ACCESS))) == base


def test_argv_stays_sandboxed_and_carries_rules():
    # axis: argv — the built argv keeps the sandboxed shape and its settings carry the eleven rules
    res = _write_argv()
    assert res["reason"] is None
    _assert_sandboxed_shape(res["argv"])
    assert _settings_of(res["argv"])["permissions"]["allow"] == [
        "Bash(python:*)", "Bash(python3:*)", "Bash(pytest:*)",
        "Bash(scripts/pinned-python:*)", "Bash(echo:*)",
        "Bash(npm:*)", "Bash(npx:*)", "Bash(node:*)", "Bash(pnpm:*)",
        "Bash(yarn:*)", "Bash(ps:*)",
        "Bash(*=* python *)", "Bash(*=* python3 *)", "Bash(*=* pytest *)",
        "Bash(*=* scripts/pinned-python *)", "Bash(*=* echo *)",
        "Bash(*=* npm *)", "Bash(*=* npx *)", "Bash(*=* node *)",
        "Bash(*=* pnpm *)", "Bash(*=* yarn *)", "Bash(*=* ps *)",
        "Bash(*=* python)", "Bash(*=* python3)", "Bash(*=* pytest)",
        "Bash(*=* scripts/pinned-python)", "Bash(*=* echo)",
        "Bash(*=* npm)", "Bash(*=* npx)", "Bash(*=* node)",
        "Bash(*=* pnpm)", "Bash(*=* yarn)", "Bash(*=* ps)",
    ]
