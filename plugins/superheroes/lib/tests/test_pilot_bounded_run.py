"""Tests for pilot_bounded_run.py — structural detector for #866 audit r2-2 (pgid-reuse window)."""
import ast
import inspect
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_bounded_run as pbr  # noqa: E402


def _terminate_function_ast():
    """Parse `_terminate`'s own source (not the whole module) into its `ast.FunctionDef`."""
    source = inspect.getsource(pbr._terminate)
    tree = ast.parse(source)
    func = tree.body[0]
    assert isinstance(func, ast.FunctionDef) and func.name == "_terminate", (
        "inspect.getsource(pbr._terminate) did not parse to a single FunctionDef named "
        "_terminate — got %r" % (ast.dump(tree),)
    )
    return func


def _is_os_killpg_with_signal(node, signal_name):
    """True for an `os.killpg(<pgid>, signal.<signal_name>)` call node, structurally."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr != "killpg":
        return False
    if not (isinstance(node.func.value, ast.Name) and node.func.value.id == "os"):
        return False
    if len(node.args) < 2:
        return False
    sig_arg = node.args[1]
    return (
        isinstance(sig_arg, ast.Attribute)
        and isinstance(sig_arg.value, ast.Name)
        and sig_arg.value.id == "signal"
        and sig_arg.attr == signal_name
    )


def _is_proc_reap_call(node):
    """True for a `proc.wait(...)` or `proc.poll()` call node — either reaps the group leader."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr not in ("wait", "poll"):
        return False
    return isinstance(node.func.value, ast.Name) and node.func.value.id == "proc"


def test_terminate_signals_the_whole_group_before_any_reap():
    # axis: statement ORDER inside `_terminate` — both `os.killpg(..., SIGTERM)` and
    # `os.killpg(..., SIGKILL)` must precede the first `proc.wait(...)`/`proc.poll()` call,
    # wherever in the function body it sits (the calls live inside nested `try` blocks, so this
    # walks the whole subtree via `ast.walk` and orders by `node.lineno` rather than assuming a
    # flat body). #866 audit r2-2: reaping the process-group leader releases its pid, and pgid IS
    # that pid, so a reap between the two signals lets the kernel hand the pid to an unrelated
    # same-UID process group that the second `killpg` would then hit. That consequence is a race
    # — the kernel would have to reuse the exact pid inside a narrow window — which no behavioural
    # test can force to reproduce; a re-run of this batch's own WO-2 bite-proof confirmed exactly
    # that (both containment tests stayed green with the pre-fix order restored). The ORDER of
    # operations is what makes the fix correct, and unlike its consequence, the order is
    # mechanically checkable by inspecting the source — so that is what this test checks.
    func = _terminate_function_ast()
    calls = [node for node in ast.walk(func) if isinstance(node, ast.Call)]

    sigterm_calls = [c for c in calls if _is_os_killpg_with_signal(c, "SIGTERM")]
    sigkill_calls = [c for c in calls if _is_os_killpg_with_signal(c, "SIGKILL")]
    reap_calls = [c for c in calls if _is_proc_reap_call(c)]

    # Non-vacuity: both killpg calls must actually be present, or the ordering check below would
    # trivially pass over a `_terminate` that stopped sending one of the signals altogether.
    assert sigterm_calls, "_terminate no longer calls os.killpg(..., signal.SIGTERM) at all"
    assert sigkill_calls, "_terminate no longer calls os.killpg(..., signal.SIGKILL) at all"
    # Non-vacuity: a reap call must exist too, or "both killpg calls precede the first reap" would
    # be vacuously true for a `_terminate` that never reaps the leader at all — its own defect.
    assert reap_calls, (
        "_terminate has no proc.wait(...)/proc.poll() reaping call at all — the ordering "
        "assertion below would be vacuously satisfied by a function that never reaps"
    )

    first_reap_lineno = min(c.lineno for c in reap_calls)
    last_sigterm_lineno = max(c.lineno for c in sigterm_calls)
    last_sigkill_lineno = max(c.lineno for c in sigkill_calls)

    assert last_sigterm_lineno < first_reap_lineno, (
        "os.killpg(..., signal.SIGTERM) at relative line %d does not precede the first reap "
        "at relative line %d — a reap between the signals can release the leader's pid before "
        "the group is fully signalled (#866 audit r2-2)"
        % (last_sigterm_lineno, first_reap_lineno)
    )
    assert last_sigkill_lineno < first_reap_lineno, (
        "os.killpg(..., signal.SIGKILL) at relative line %d does not precede the first reap "
        "at relative line %d — a reap between the signals can release the leader's pid before "
        "the group is fully signalled (#866 audit r2-2)"
        % (last_sigkill_lineno, first_reap_lineno)
    )
