"""#396 review (architecture-003): the final-review verify gate's three duration bounds must stay
strictly ordered — gate --timeout < the courier's Bash-tool floor < the perl-alarm ceiling — so
verify_gate.py always raises TimeoutExpired and atomically writes its distinct `result: "timeout"`
BEFORE any outer bound hard-kills the process. The three constants live in three files/languages:

- gate --timeout  → review_panel_shell.js  `VERIFY_TIMEOUT_SECONDS` (seconds)
- Bash floor      → hooks/bash_timeout.py    `DEFAULT_TIMEOUT_MS`     (milliseconds)
- perl alarm      → review_panel_shell.js  `VERIFY_ALARM_SECONDS`   (seconds)

The round-1 fix chose 570 precisely to sit below the 600s Bash floor; nothing but this test ties the
three homes together, so a later change to any one (bash_timeout.py:24 explicitly contemplates the
floor moving) could silently invert the ordering and reintroduce the #396 race. This drift guard makes
the invariant mechanical, following the repo's SSOT/drift-guard convention (CONVENTIONS §11).
"""
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_PLUGIN = os.path.dirname(_LIB)
_SHELL_JS = os.path.join(_LIB, "review_panel_shell.js")
_BUNDLE_JS = os.path.join(_LIB, "showrunner.bundle.js")
_BASH_HOOK = os.path.join(_PLUGIN, "hooks", "bash_timeout.py")


def _js_const(path, name):
    src = open(path, encoding="utf-8").read()
    # Anchor on the `const` keyword so a doc-comment mention of the name can never shadow the real
    # declaration (test-review Nit): the parse must bind to the assignment, not incidental prose.
    m = re.search(r"\bconst\s+%s\s*=\s*(\d+)\b" % re.escape(name), src)
    assert m, "could not find JS const %s in %s" % (name, path)
    return int(m.group(1))


def _py_const(path, name):
    src = open(path, encoding="utf-8").read()
    m = re.search(r"^%s\s*=\s*(\d+)\b" % re.escape(name), src, re.MULTILINE)
    assert m, "could not find Python const %s in %s" % (name, path)
    return int(m.group(1))


def test_verify_timeout_bounds_are_strictly_ordered():
    gate_s = _js_const(_SHELL_JS, "VERIFY_TIMEOUT_SECONDS")
    alarm_s = _js_const(_SHELL_JS, "VERIFY_ALARM_SECONDS")
    floor_ms = _py_const(_BASH_HOOK, "DEFAULT_TIMEOUT_MS")
    # Compare in milliseconds so the cross-unit boundary is explicit.
    gate_ms, alarm_ms = gate_s * 1000, alarm_s * 1000
    assert gate_ms < floor_ms, (
        "verify gate --timeout (%dms) must be STRICTLY BELOW the courier Bash floor (%dms) so "
        "verify_gate.py classifies+writes its timeout result before the Bash kill (#396)" % (gate_ms, floor_ms))
    assert floor_ms < alarm_ms, (
        "the perl-alarm ceiling (%dms) must sit ABOVE the Bash floor (%dms) so it is the outermost "
        "backstop only (#396)" % (alarm_ms, floor_ms))


def test_bundle_verify_constants_match_source():
    # The bundle is a generated mirror; pin the two constants so a stale bundle can't ship a different
    # ordering than the source this test just verified.
    for name in ("VERIFY_TIMEOUT_SECONDS", "VERIFY_ALARM_SECONDS"):
        assert _js_const(_SHELL_JS, name) == _js_const(_BUNDLE_JS, name), (
            "%s drifted between review_panel_shell.js and showrunner.bundle.js — regenerate the bundle" % name)
