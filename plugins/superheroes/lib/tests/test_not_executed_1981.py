"""A check that did not execute the code under test never dismisses a finding (#1981).

Two seats dismiss: the break-it runner (a run whose output shows a setup failure read `failed`, or
`passed` at exit 0, which `intercept` drops) and the per-finding verifier fold (a REFUTED with a reason
dropped the finding even when the reason only showed that a probe failed to start). Both now read the
check as not executed and keep the finding.

Edges: E1 exit 127 with empty output (T2) · E2 exit 1 with `ERR_MODULE_NOT_FOUND` (T2) · E3 exit 0 with
`ModuleNotFoundError` (T2) · E4 the signature first, then more than the 8192-byte tail of other output,
exit 0 and exit 1 (T2, T3) · E5 a genuine assertion failure stays `failed` (T2) · E6 a genuine pass stays
`passed` (T2) · a verifier REFUTED resting on such a check is kept unverified (T4), a real refutation
still drops (T5), and the round driver records the kept one without a disposition (T6).

Precedence (review round 1, WO-3): `command-not-found` outranks `module-not-found` however the output is
read — a module chunk then a command chunk upgrades the drain latch (T7), and exit 127 beats a latched
module reason (T8: E2 module signature and exit 127, E3 module signature and exit 1 unchanged, E4 an early
`command not found`, more than the tail of other output, then a module signature).

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo_1_1981_not_executed.md
"""
import os
import sys
import threading
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import break_it  # noqa: E402
import test_break_it as BI  # noqa: E402
import test_round_driver as TRD  # noqa: E402
import test_synthesis_seat_1858 as S1858  # noqa: E402
import test_verification as TV  # noqa: E402
import verification as V  # noqa: E402
from test_break_it import repo  # noqa: E402,F401  (fixture, re-exported)

RDT = TRD.RD
_PATH = "tests/test_s.py"
_MODULE_SIGNATURE = "Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'vitest'"


def _run(repo, content):
    return break_it.run_one(str(repo), BI._head(repo), BI._block(_PATH, content))


# T1
@pytest.mark.parametrize("text, code, expected", [
    ("", 127, "command-not-found"),
    ("anything", 127, "command-not-found"),
    ("sh: 1: vitest: command not found", None, "command-not-found"),
    ("Error [ERR_MODULE_NOT_FOUND]: x", None, "module-not-found"),
    ("Error: Cannot find module './x'", 1, "module-not-found"),
    ("Error: Cannot find package 'vitest'", 1, "module-not-found"),
    ("ModuleNotFoundError: x", 1, "module-not-found"),
    ("ImportError: No module named 'x'", 1, "module-not-found"),
    ("sh: vitest: command not found\nCannot find module 'x'", 0, "command-not-found"),
    ("AssertionError: 1 == 2", 1, None),
    ("", 0, None),
    ("", None, None),
    (None, None, None),
    (None, 127, "command-not-found"),
    (b"command not found", 1, None),
    (["command not found"], 0, None),
])
def test_t1_setup_failure_reason_table(text, code, expected):
    assert break_it.setup_failure_reason(text, code) == expected


# T2
@pytest.mark.proc_containment
@pytest.mark.process_listing
def test_t2_e1_exit_127_with_empty_output_is_command_not_found(repo):
    record = _run(repo, "import sys\nsys.exit(127)\n")
    assert (record["outcome"], record["reason"], record["exitCode"]) == ("not-run", "command-not-found", 127)
    assert record["output"] == ""


def test_t2_e2_exit_1_with_module_not_found_is_not_run(repo):
    content = "import sys\nsys.stderr.write(%r + '\\n')\nsys.exit(1)\n" % _MODULE_SIGNATURE
    record = _run(repo, content)
    assert (record["outcome"], record["reason"], record["exitCode"]) == ("not-run", "module-not-found", 1)
    assert "vitest" in record["output"]


def test_t2_e3_exit_0_with_module_not_found_is_not_run_never_passed(repo):
    record = _run(repo, "print(\"ModuleNotFoundError: No module named 'x'\")\n")
    assert (record["outcome"], record["reason"], record["exitCode"]) == ("not-run", "module-not-found", 0)


@pytest.mark.parametrize("code", [0, 1])
def test_t2_e4_an_early_signature_survives_a_long_output(repo, code):
    content = ("import sys\nprint(%r, flush=True)\n"
               "for _ in range(4000):\n    print('y' * 49)\nsys.exit(%d)\n" % (_MODULE_SIGNATURE, code))
    record = _run(repo, content)
    # the premise: the drain's tail kept no trace of the signature, so only the latch can have seen it
    assert "vitest" not in record["output"], record["output"][:200]
    assert len(record["output"].encode()) <= break_it.OUTPUT_TAIL_BYTES + 64
    assert (record["outcome"], record["reason"], record["exitCode"]) == ("not-run", "module-not-found", code)


def test_t2_e5_a_genuine_assertion_failure_stays_failed(repo):
    record = _run(repo, "assert 1 == 2, 'boom-marker'\n")
    assert (record["outcome"], record["reason"], record["exitCode"]) == ("failed", None, 1)


def test_t2_e6_a_genuine_pass_stays_passed(repo):
    record = _run(repo, "assert 1 == 1\n")
    assert (record["outcome"], record["reason"], record["exitCode"]) == ("passed", None, 0)


# T3
def test_t3_intercept_keeps_a_break_it_finding_whose_early_signature_scrolled_off(repo):
    content = ("print(%r, flush=True)\nfor _ in range(4000):\n    print('y' * 49)\n" % _MODULE_SIGNATURE)
    block = BI._wire(_PATH, "%s %s" % (BI.PY, _PATH), content)
    finding = {"title": "Break-it: %s" % _PATH, "file": _PATH, "line": 1, "taxonomy": break_it.TAXONOMY,
               "suggestion": block}
    kept, runs, _, _ = break_it.intercept([finding], str(repo), BI._head(repo))
    assert len(kept) == 1, kept
    run = kept[0][break_it.RUN_FIELD]
    assert (run["outcome"], run["reason"], run["exitCode"]) == ("not-run", "module-not-found", 0)
    assert runs[0]["outcome"] == "not-run"


# T4
_PROBE_REASONS = [
    ("reason", "probe failed: sh: 1: vitest: command not found (exit 127)", "command-not-found"),
    ("reason", "the probe printed " + _MODULE_SIGNATURE, "module-not-found"),
    ("reason", "the recorded probe was not-run: module-not-found", "module-not-found"),
    ("evidence", "ModuleNotFoundError: No module named 'x'", "module-not-found"),
    ("reason", "the probe exited with status 127 before running anything", "command-not-found"),
]


@pytest.mark.parametrize("field, text, token", _PROBE_REASONS)
def test_t4_a_refutation_resting_on_a_check_that_did_not_run_is_kept_unverified(field, text, token):
    findings = TV._stage([TV._f("a.py", "bug", "Important")])
    verdict = {"id": "v0", "verdict": "REFUTED", "reason": "refuted by the probe", "severity": "Nit"}
    verdict[field] = text
    out = V.apply_verdicts(findings, [verdict])
    assert out["drops"] == []
    assert len(out["findings"]) == 1
    kept = out["findings"][0]
    assert kept["verdict"] == "PLAUSIBLE"
    assert kept["severity"] == "Important"
    assert "severityChange" not in kept and out["downgrades"] == []
    assert kept["unverified"] is True
    assert out["unverified"] == ["v0"]
    assert len(out["notExecuted"]) == 1
    entry = out["notExecuted"][0]
    assert entry["reason"].startswith("not-executed: %s: " % token), entry
    assert (entry["id"], entry["file"], entry["title"]) == ("v0", "a.py", "bug")
    assert V.not_executed_reason(verdict) == token


def test_t4_the_kept_finding_keeps_its_identity_key():
    import session_contract
    finding = TV._f("a.py", "bug", "Important")
    out = V.apply_verdicts(TV._stage([finding]), [
        {"id": "v0", "verdict": "REFUTED", "reason": "probe: vitest: command not found"}])
    assert session_contract.finding_identity_key(out["findings"][0]) == session_contract.finding_identity_key(finding)


# T5
def test_t5_a_real_refutation_still_drops():
    findings = TV._stage([TV._f("a.py", "bug", "Critical")])
    verdicts = [{"id": "v0", "verdict": "REFUTED", "reason": "the guard at line 40 already returns early on None"}]
    out = V.apply_verdicts(findings, verdicts)
    assert out["findings"] == []
    assert [d["id"] for d in out["drops"]] == ["v0"]
    assert out["notExecuted"] == []
    assert out["unverified"] == []


# T6
_REAL = {"title": "real bug", "severity": "Important", "file": "f.py", "line": 1,
         "consequence": "a reviewer-found defect stays in the change"}
_UNRUN = {"title": "probe bug", "severity": "Important", "file": "f.py", "line": 2,
          "consequence": "a reviewer-found defect stays in the change"}
_UNRUN_REASON = "probe failed: sh: 1: vitest: command not found (exit 127)"


class _AtSynthesis(Exception):
    """Raised by the responder when the driver offers the synthesis step."""


def _drive(tmp_path):
    """Drive next/submit with two findings: the verifier really refutes one and refutes the other on a probe
    that never started. Halts when synthesis is offered (the survivor reaches it)."""
    session_dir = str(tmp_path)
    base = TRD._responder(round1_findings=[dict(_REAL), dict(_UNRUN)], verdict="CONFIRMED")

    def respond(phase, payload, rnd):
        if phase == RDT.P_SYNTHESIS:
            raise _AtSynthesis()
        art = base(phase, payload, rnd)
        if phase == RDT.P_VERIFIERS:
            verdicts = []
            for cluster in payload.get("clusters", []):
                for finding, fid in zip(cluster["findings"], cluster["ids"]):
                    reason = (_UNRUN_REASON if finding["title"] == _UNRUN["title"]
                              else "the guard at line 40 already returns early on None")
                    verdicts.append({"id": fid, "verdict": "REFUTED", "reason": reason})
            ok, state = RDT.load_state(session_dir)
            art = {"verdicts": verdicts,
                   "verifierVendor": RDT._nonpanel_selection(state, session_dir, phase)[0]}
        return art

    cfg = S1858._cfg()
    cfg.pop("repoRoot")  # the driven session runs in a real checkout
    try:
        TRD._drive_cli(session_dir, TRD._cfg(**cfg), respond)
    except _AtSynthesis:
        pass
    return session_dir


def test_t6_the_round_driver_keeps_a_not_executed_refutation_and_records_it(tmp_path):
    # axis: a REFUTED resting on a check that did not execute is kept unverified, not dropped
    session_dir = _drive(tmp_path)
    ok, state = RDT.load_state(session_dir)
    assert ok, state
    contract = RDT.session_contract
    ledger = {contract.finding_identity_key(e): e for e in state[contract.DISPOSITION_LEDGER_KEY]}
    real_key, unrun_key = contract.finding_identity_key(_REAL), contract.finding_identity_key(_UNRUN)
    assert ledger[real_key]["disposition"] == "refuted", ledger
    assert "disposition" not in ledger.get(unrun_key, {}), ledger
    survivors = [f["title"] for f in state["_verified"]]
    assert survivors == [_UNRUN["title"]], survivors
    assert state["_verified"][0]["unverified"] is True
    kinds = [d["kind"] for d in state["decisions"]]
    assert kinds.count("verifier-refuted") == 1 and kinds.count("verifier-not-executed") == 1, kinds
    decision = next(d for d in state["decisions"] if d["kind"] == "verifier-not-executed")
    assert decision["detail"] == "not-executed: command-not-found: " + _UNRUN_REASON
    verify = state["rounds"]["1"]["verify"]
    assert [n["title"] for n in verify["notExecuted"]] == [_UNRUN["title"]]
    assert [d["title"] for d in verify["drops"]] == [_REAL["title"]]
    passes = state["rounds"]["1"]["verifyPasses"][-1]
    assert (passes["PLAUSIBLE"], passes["REFUTED"], passes["unverified"]) == (1, 1, 1), passes


# T7
_MODULE_CHUNK = b"ModuleNotFoundError: No module named 'x'\n"
_COMMAND_CHUNK = b"sh: 1: vitest: command not found\n"
_PLAIN_CHUNK = b"all quiet on this read\n"


def _drain_two_reads(first, second):
    """Feed ``first`` then ``second`` to a ``_TailDrain`` as two reads it takes separately: the second write
    waits until the drain has latched the first chunk's reason, so a pipe cannot coalesce the two."""
    expected = break_it.setup_failure_reason(first.decode())
    rfd, wfd = os.pipe()
    with os.fdopen(rfd, "rb") as stream, os.fdopen(wfd, "wb", buffering=0) as out:
        drain = break_it._TailDrain(stream)
        drain.start()
        out.write(first)
        deadline = time.monotonic() + 5
        while drain.setup != expected and time.monotonic() < deadline:
            time.sleep(0.01)
        assert drain.setup == expected, drain.setup
        out.write(second)
        out.close()
        drain.join(30)
        assert not drain.is_alive()
    return drain.setup


def test_t7_a_later_command_not_found_read_upgrades_an_earlier_module_latch():
    assert _drain_two_reads(_MODULE_CHUNK, _COMMAND_CHUNK) == "command-not-found"


def test_t7_a_module_read_never_downgrades_an_earlier_command_latch():
    assert _drain_two_reads(_COMMAND_CHUNK, _MODULE_CHUNK) == "command-not-found"


def test_t7_a_signature_free_read_never_clears_a_module_latch():
    assert _drain_two_reads(_MODULE_CHUNK, _PLAIN_CHUNK) == "module-not-found"


# T8
def test_t8_e2_module_signature_with_exit_127_is_command_not_found(repo):
    content = "import sys\nsys.stderr.write(%r + '\\n')\nsys.exit(127)\n" % _MODULE_SIGNATURE
    record = _run(repo, content)
    assert (record["outcome"], record["reason"], record["exitCode"]) == ("not-run", "command-not-found", 127)
    assert "vitest" in record["output"]


def test_t8_e3_module_signature_with_exit_1_stays_module_not_found(repo):
    content = "import sys\nsys.stderr.write(%r + '\\n')\nsys.exit(1)\n" % _MODULE_SIGNATURE
    record = _run(repo, content)
    assert (record["outcome"], record["reason"], record["exitCode"]) == ("not-run", "module-not-found", 1)


def test_t8_e4_an_early_command_not_found_outranks_a_late_module_signature(repo):
    content = ("import sys\nprint('sh: 1: vitest: command not found', flush=True)\n"
               "for _ in range(4000):\n    print('y' * 49)\n"
               "print(%r)\nsys.exit(0)\n" % _MODULE_SIGNATURE)
    record = _run(repo, content)
    # the premise: the tail kept the module signature and no trace of the early command line
    assert "command not found" not in record["output"], record["output"][:200]
    assert "vitest'" in record["output"]
    assert (record["outcome"], record["reason"], record["exitCode"]) == ("not-run", "command-not-found", 0)
