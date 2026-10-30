"""#2275: leading `NAME=value` assignments run in the claude write sandbox.

Invariant (I1): for every command family in the one family list, the settings' allow rules carry
exactly the prefix rule `Bash(f:*)` plus the two assignment-prefixed rules `Bash(*=* f *)` and
`Bash(*=* f)`, and no other rule.

The family and rule literals are spelled out as strings on purpose: a test that reaches them through
the module constant stays green under any value (rubric/bite-proof.md).

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo_b_env_prefix_2275.md

Detector axes (bite-proof):
- test_every_family_carries_both_assignment_rules — census: three rules per family, no extras, no duplicates
- test_weekly_eats_shape_matches_a_new_rule — reach: the field shape matches a rule of the new settings
- test_bare_family_with_assignment_matches_a_new_rule — reach: an assignment before a bare family matches
- test_pinned_python_with_assignment_matches_a_new_rule — reach: the pinned-python shape matches
- test_weekly_eats_shape_matches_no_old_rule — break-it: today's eleven prefix rules refuse the shape
- test_assignment_before_a_non_family_command_matches_no_rule — tightness: other commands stay refused
- test_equals_before_a_family_word_is_a_known_match — residual: `touch x=1 npx f` matches, pinned
"""
import fnmatch
import json

# The 1554 suite's harness (and, through it, the write-dispatch suite's autouse fixture).
from test_claude_write_sandbox_1554 import (  # noqa: F401
    EA,
    _SANDBOX,
    _pin_temp_base_to_tmp_path,
)

_FAMILIES = (
    "python", "python3", "pytest", "scripts/pinned-python", "echo",
    "npm", "npx", "node", "pnpm", "yarn", "ps",
)

# The allow rules before #2275: the eleven prefix rules only.
_PRE_2275_RULES = (
    "Bash(python:*)", "Bash(python3:*)", "Bash(pytest:*)",
    "Bash(scripts/pinned-python:*)", "Bash(echo:*)",
    "Bash(npm:*)", "Bash(npx:*)", "Bash(node:*)", "Bash(pnpm:*)",
    "Bash(yarn:*)", "Bash(ps:*)",
)

_WEEKLY_EATS = (
    "MONGODB_URI=mongodb://localhost:27017/weekly-eats-test SKIP_DB_SETUP=true "
    "npx --no-install vitest run --reporter=dot"
)


def _allow():
    return json.loads(EA.claude_write_sandbox_settings(_SANDBOX))["permissions"]["allow"]


def _rule_matches(rule, command):
    """Emulate Claude Code's Bash permission matcher as measured on 2.1.314 (the far side's contract).

    `Bash(p:*)` is a prefix rule: it matches when the command equals `p` or starts with `p + " "`.
    Any other `Bash(x)` rule is a glob: `*` matches any run of characters, spaces included. Measured
    live: `Bash(*=* npx *)` and `Bash(*=* npx)` ran `A=1 B=2 npx --version`, while `Bash(*=* npx:*)`
    (a `:*` suffix after a leading `*`) did not match anything."""
    assert rule.startswith("Bash(") and rule.endswith(")"), rule
    body = rule[len("Bash("):-1]
    if body.endswith(":*"):
        prefix = body[:-2]
        return command == prefix or command.startswith(prefix + " ")
    return fnmatch.fnmatchcase(command, body)


def _matching(rules, command):
    return [rule for rule in rules if _rule_matches(rule, command)]


def test_every_family_carries_both_assignment_rules():
    # axis: census — each family has its prefix rule and both assignment rules; 3 per family, no extras
    allow = _allow()
    assert tuple(EA.CLAUDE_WRITE_BASH_FAMILIES) == _FAMILIES
    for family in _FAMILIES:
        assert f"Bash({family}:*)" in allow, family
        assert f"Bash(*=* {family} *)" in allow, family
        assert f"Bash(*=* {family})" in allow, family
    assert len(allow) == 3 * len(_FAMILIES)
    assert len(set(allow)) == len(allow)


def test_weekly_eats_shape_matches_a_new_rule():
    # axis: reach — the field shape (leading assignments before npx with arguments) matches a rule
    assert _matching(_allow(), _WEEKLY_EATS)


def test_bare_family_with_assignment_matches_a_new_rule():
    # axis: reach — an assignment before a family name with no arguments matches a rule
    assert _matching(_allow(), "SBX_PROBE=one npx")


def test_pinned_python_with_assignment_matches_a_new_rule():
    # axis: reach — an assignment before the pinned python wrapper matches a rule
    assert _matching(_allow(), "PYTHONDONTWRITEBYTECODE=1 scripts/pinned-python -B -m pytest x -q")


def test_weekly_eats_shape_matches_no_old_rule():
    # axis: break-it — the pre-#2275 rules refuse the field shape, so the old refusal reads red
    assert _matching(_PRE_2275_RULES, _WEEKLY_EATS) == []


def test_assignment_before_a_non_family_command_matches_no_rule():
    # axis: tightness — a leading assignment before a command outside the families stays refused
    allow = _allow()
    for command in ("SBX_PROBE=two touch f", "FOO=1 rm -rf x", "FOO=1 curl example.com"):
        assert _matching(allow, command) == [], command


def test_equals_before_a_family_word_is_a_known_match():
    # axis: residual — an `=` anywhere before a family name also matches; pinned so a change shows
    assert _matching(_allow(), "touch x=1 npx f")
