"""Break-it tests in the review loop: run before compile, carried through, checked as kept."""
import hashlib
import json
import os
import shlex
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import break_it  # noqa: E402
import round_driver as RD  # noqa: E402
import session_contract as SC  # noqa: E402
import verification  # noqa: E402

PY = shlex.quote(sys.executable)
# The fixture repo's commits pass an inline identity (a CI runner has no configured one); the throwaway fixture repo also signs nothing.
_ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]

TEST_PATH = "tests/test_charge_once.py"
CHARGE_PATH = "src/payments/charge.py"

_CHARGE_RETRYING = (
    "def charge_with_retry(ledger, amount, timeouts=1):\n"
    "    for _ in range(timeouts + 1):\n"
    "        ledger.append(amount)\n"
    "    return ledger\n")
_CHARGE_IDEMPOTENT = (
    "def charge_with_retry(ledger, amount, timeouts=1):\n"
    "    if not ledger:\n"
    "        ledger.append(amount)\n"
    "    return ledger\n")
_TEST_FAILING = (
    "import os, sys\n"
    "sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'payments'))\n"
    "import charge\n"
    "ledger = charge.charge_with_retry([], 100, timeouts=1)\n"
    "assert len(ledger) == 1, 'charged %d times' % len(ledger)\n")
_TEST_PASSING = _TEST_FAILING.replace("== 1", ">= 1")
_TEST_WEAKENED = _TEST_FAILING.replace("assert len(ledger) == 1", "assert len(ledger) >= 1")


def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _commit(repo, message):
    _git(repo, "add", "-A")
    _git(repo, *_ID, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _write(repo, rel, text):
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def _block(path, content):
    return "break-it-test v1\npath: %s\nrun: %s %s\n---\n%s" % (path, PY, shlex.quote(path), content)


def _break_it_finding(content=_TEST_FAILING, **extra):
    out = {"title": "Break-it: a retried charge runs twice", "file": TEST_PATH, "line": 1,
           "severity": "Important", "dimension": "Test", "taxonomy": break_it.TAXONOMY,
           "body": "payments risk area: the retry resends the charge",
           "consequence": "the customer is charged twice", "confidence": "High",
           "suggestion": _block(TEST_PATH, content)}
    out.update(extra)
    return out


def _panel_artifact(*findings):
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["test-role"] = {"findings": list(findings)}
    return {"seats": seats}


class World:
    """A throwaway repo whose change adds src/payments/charge.py, plus a loop state over it."""

    def __init__(self, tmp_path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        self.repo = tmp_path / "repo"
        self.repo.mkdir()
        _git(self.repo, "init", "-q")
        _write(self.repo, "README.md", "fixture\n")
        self.base = _commit(self.repo, "base")
        _write(self.repo, CHARGE_PATH, _CHARGE_RETRYING)
        self.head = _commit(self.repo, "retry the charge")
        self.diff = _git(self.repo, "diff", self.base, self.head) + "\n"
        self.session = tmp_path / "session"
        self.session.mkdir()
        (self.session / RD.round_records.META_FILE).write_text(json.dumps(
            {"repoRoot": str(self.repo), "headSha": self.head}))
        self.config = {"leg": "code", "vendors": ["claude", "codex"], "diff": self.diff,
                       "fixerVendor": "claude", "repoRoot": str(self.repo),
                       "baseRef": self.base, "headSha": self.head,
                       "verifyCommand": "%s -c pass" % PY}
        self.state = RD.new_state(self.config)
        self.state["reviewedDiff"] = self.diff

    def fold_panel(self, *findings):
        RD._fold(self.state, self.state["config"], RD.P_PANEL, _panel_artifact(*findings),
                 session_dir=str(self.session))
        return self.state

    @property
    def round_record(self):
        return self.state["rounds"][str(self.state["round"])]

    def key_of_failed_run(self):
        runs = self.round_record["breakItRuns"]
        assert runs[0]["outcome"] == "failed" and runs[0]["findingKey"], runs
        return runs[0]["findingKey"]

    def fix(self, test_content=None, code=_CHARGE_IDEMPOTENT):
        """Commit the fix; the test file goes in with `test_content` unless it is None."""
        _write(self.repo, CHARGE_PATH, code)
        if test_content is not None:
            _write(self.repo, TEST_PATH, test_content)
        fix_head = _commit(self.repo, "fix the retry")
        self.state["config"][RD.FIX_FOLD_HEAD_KEY] = fix_head
        return fix_head

    def disposition(self, disposition, **fields):
        RD._record_disposition(self.state, self.key_of_failed_run(), disposition, 1, **fields)


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_l1_a_failing_break_it_test_survives_compile_stamped(world):
    state = world.fold_panel(_break_it_finding())
    staged = state["_toVerify"]
    assert [f["file"] for f in staged] == [TEST_PATH]
    run = staged[0][break_it.RUN_FIELD]
    assert run["outcome"] == "failed"
    assert "charged 2 times" in run["output"]
    (entry,) = world.round_record["breakItRuns"]
    assert entry["role"] == "test-role" and entry["outcome"] == "failed"
    assert entry["command"] == "%s %s" % (PY, shlex.quote(TEST_PATH))
    assert entry["findingKey"] == staged[0][SC.FINDING_KEY_FIELD]
    assert not world.round_record["compileDrops"]
    assert any(d["kind"] == "break-it-run" for d in state["decisions"])
    cluster = verification.cluster_findings(verification.stage_ids(staged))[0]["findings"][0]
    assert cluster["taxonomy"] == break_it.TAXONOMY and cluster["suggestion"]
    assert cluster[break_it.RUN_FIELD]["outcome"] == "failed"


def test_l2_a_passing_break_it_test_keeps_its_finding_stamped_and_is_recorded(world):
    # the run judges nothing: a passing run no longer drops the finding
    state = world.fold_panel(_break_it_finding(_TEST_PASSING))
    (staged,) = state["_toVerify"]
    assert staged[break_it.RUN_FIELD]["outcome"] == "passed"
    (entry,) = world.round_record["breakItRuns"]
    assert entry["outcome"] == "passed" and entry["findingKey"] == staged[SC.FINDING_KEY_FIELD]
    decisions = [d for d in state["decisions"] if d["kind"] == "break-it-run"]
    assert len(decisions) == 1 and "1 run: 1 exited 0, 0 exited non-zero, 0 not run" in decisions[0]["detail"]


def test_l12_no_repo_root_keeps_the_finding_as_a_not_run(world):
    for key in ("repoRoot", "headSha"):
        world.state["config"].pop(key)
    RD._fold(world.state, world.state["config"], RD.P_PANEL, _panel_artifact(_break_it_finding()))
    (staged,) = world.state["_toVerify"]
    assert (staged[break_it.RUN_FIELD]["outcome"], staged[break_it.RUN_FIELD]["reason"]) == (
        "not-run", "head-unresolved")
    assert world.round_record["breakItRuns"][0]["findingKey"] == staged[SC.FINDING_KEY_FIELD]


def _drop_reasons(state):
    return [d["reason"] for rec in state["rounds"].values() for d in rec.get("compileDrops") or []]


def test_l3_a_forged_stamp_never_passes_the_scope_check(tmp_path):
    forged = {"outcome": "failed", "output": "forged"}
    outside = {"title": "forged out of scope", "file": "elsewhere/x.py", "line": 7,
               "severity": "Important", break_it.RUN_FIELD: dict(forged),
               "consequence": "a reviewer-found defect stays in the change"}
    outside_break_it = dict(outside, taxonomy=break_it.TAXONOMY, title="forged break-it")
    reasons = "outside the round diff scope"
    gap = World(tmp_path / "gap")
    RD._fold_gapsweep(gap.state, gap.state["config"], {"findings": [outside, outside_break_it]})
    assert _drop_reasons(gap.state) == [reasons, reasons]
    assert not gap.state.get("_toVerify")
    scoped = World(tmp_path / "scoped")
    RD._fold_scoped(scoped.state, scoped.state["config"],
                    {"findings": [outside, outside_break_it]})
    assert _drop_reasons(scoped.state) == [reasons, reasons]
    panel = World(tmp_path / "panel")
    panel.fold_panel(dict(outside))
    assert _drop_reasons(panel.state) == [reasons]
    # an in-diff non-break-it finding keeps no stamp
    in_diff = {"title": "in diff", "file": CHARGE_PATH, "line": 1, "severity": "Important",
               break_it.RUN_FIELD: dict(forged), "consequence": "a reviewer-found defect stays in the change"}
    clean = World(tmp_path / "clean")
    RD._fold_gapsweep(clean.state, clean.state["config"], {"findings": [in_diff]})
    (survivor,) = clean.state["_toVerify"]
    assert survivor["file"] == CHARGE_PATH and break_it.RUN_FIELD not in survivor


def test_l11_a_stamped_finding_compile_still_drops_is_recorded_as_dropped(world):
    state = world.fold_panel(_break_it_finding(line="not-a-number"))
    assert state["_toVerify"] == []
    (drop,) = world.round_record["compileDrops"]
    assert drop["reason"] == RD.COMPILE_DROP_LINE_NOT_INTEGER
    (entry,) = world.round_record["breakItRuns"]
    assert entry["outcome"] == "failed"
    assert entry["findingKey"] is None and entry["droppedAtCompile"] is True
    RD._terminal_converged(world.state, world.state["config"], full_panel=True)
    assert world.state["terminal"] == "cannot-certify"
    assert world.state["certification"]["reason"] == (
        "break-it run dropped at compile: %s (failed)" % TEST_PATH)


def test_b2_only_the_test_roles_seat_can_trigger_a_break_it_run(world, monkeypatch):
    seen = []
    real = break_it.intercept

    def counting(findings, *args, **kwargs):
        seen.extend(f.get("title") for f in findings)
        return real(findings, *args, **kwargs)

    monkeypatch.setattr(break_it, "intercept", counting)
    # the label says Test, the seat says code-reviewer: only the roster key is trusted
    impostor = _break_it_finding(title="Break-it: from the code reviewer", dimension="Test")
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [impostor]}
    RD._fold(world.state, world.state["config"], RD.P_PANEL, {"seats": seats},
             session_dir=str(world.session))
    assert seen == []
    assert "breakItRuns" not in world.round_record
    assert world.state["_toVerify"] == []
    assert _drop_reasons(world.state) == ["outside the round diff scope"]


def test_b2b_a_test_role_finding_labeled_code_still_runs(world):
    world.fold_panel(_break_it_finding(dimension="Code"))
    (entry,) = world.round_record["breakItRuns"]
    assert entry["outcome"] == "failed"


def test_a_malformed_block_keeps_ordinary_scope_checking(world):
    world.fold_panel(_break_it_finding(
        file="unrelated.py", line=42, suggestion="not a valid break-it block"))
    assert world.state["_toVerify"] == []
    assert _drop_reasons(world.state) == ["outside the round diff scope"]
    # a path-mismatched block and a block off line 1 lose the exemption too
    other = World(world.session.parent / "other")
    other.fold_panel(_break_it_finding(file="unrelated.py", line=1),
                     _break_it_finding(title="Break-it: off line one", line=2))
    assert other.state["_toVerify"] == []
    assert _drop_reasons(other.state) == ["outside the round diff scope"] * 2


def test_a_deduplicated_proposal_binds_no_kept_check(world):
    other_test = _TEST_FAILING + "# a different proposal\n"
    world.fold_panel(_break_it_finding(), _break_it_finding(other_test))
    runs = world.round_record["breakItRuns"]
    assert len(runs) == 2
    assert [r["findingKey"] is not None for r in runs] == [True, False]
    assert runs[1]["supersededAtCompile"] is True
    world.disposition("fixed")
    world.fix(_TEST_FAILING)
    assert RD._break_it_kept_step(world.state, world.state["config"]) is False
    (row,) = world.round_record["breakItKept"]
    assert row["outcome"] == "kept"


def test_a_scrub_altered_suggestion_is_refused_not_run(world):
    import engine_adapter as EA
    content = "request = {'token': 'sk-live-EXAMPLEfakekey0'}\nassert False\n"
    raw = _break_it_finding(content)
    accepted, _ = EA._scrub_findings([raw])
    assert accepted[0]["suggestion"] != raw["suggestion"]
    assert accepted[0][break_it.REDACTED_FIELD] is True
    world.fold_panel(accepted[0])
    (run,) = world.round_record["breakItRuns"]
    assert (run["outcome"], run["reason"]) == ("not-run", "suggestion-redacted")
    assert run["sha256"] is None
    assert len(world.state["_toVerify"]) == 1 and _drop_reasons(world.state) == []
    clean, _ = EA._scrub_findings([_break_it_finding()])
    assert break_it.REDACTED_FIELD not in clean[0]


def test_an_unaltered_suggestion_under_the_change_alias_is_not_flagged_redacted():
    import engine_adapter as EA
    raw = _break_it_finding()
    raw["change"] = raw.pop("suggestion")
    accepted, _ = EA._scrub_findings([raw])
    assert break_it.REDACTED_FIELD not in accepted[0]


def test_run_output_is_scrubbed_before_a_record_carries_it():
    record = break_it._record("h", None, break_it.OUTCOME_FAILED, output="Authorization: Bearer sk-live-EXAMPLEfakekey0\n")
    assert "sk-live-EXAMPLEfakekey0" not in record["output"]


def test_a_requeued_break_it_audit_target_keeps_its_test_block():
    f = _break_it_finding()
    f[break_it.RUN_FIELD] = {"outcome": "failed", "sha256": "x"}
    state = {"fixBatch": [f]}
    (row,) = RD._audit_targets(state, {}, {})
    assert row["suggestion"] == f["suggestion"] and row["body"] == f["body"]
    assert row[break_it.RUN_FIELD] == f[break_it.RUN_FIELD]


def test_a_failing_final_run_is_kept_in_the_row_and_the_park_reason(world):
    world.fold_panel(_break_it_finding())
    world.disposition("fixed")
    world.fix(_TEST_FAILING, code=_CHARGE_RETRYING + "# still retrying\n")
    RD._terminal_converged(world.state, world.state["config"], full_panel=True)
    assert world.state["terminal"] == "cannot-certify"
    (row,) = world.round_record["breakItKept"]
    assert row["outcome"] == "failing" and row["run"]["exitCode"] != 0
    assert "charged 2 times" in world.state["certification"]["reason"]


def test_l4_merge_and_rank_keeps_each_break_it_member_in_one_fix_group():
    def finding(fid, **extra):
        out = {"id": fid, "file": "f%s.py" % fid, "line": 1, "title": "t%s" % fid,
               "severity": "Important", "suggestion": "s-%s" % fid}
        out.update(extra)
        return out

    a = finding("v0", taxonomy=break_it.TAXONOMY, **{break_it.RUN_FIELD: {"outcome": "failed"}})
    b = finding("v1", taxonomy=break_it.TAXONOMY, **{break_it.RUN_FIELD: {"outcome": "failed"}})
    c = finding("v2")
    d = finding("v3")
    survivors = [a, b, c]
    grouping = [{"group_id": "g0", "member_ids": ["v0", "v1", "v2"]}]
    out = verification.merge_and_rank(survivors, grouping)
    by_id = {f["id"]: f for f in out["findings"]}
    assert sorted(by_id) == ["v0", "v1", "v2"] and len(out["findings"]) == 3
    for fid in ("v0", "v1"):
        assert by_id[fid]["suggestion"] == "s-%s" % fid
        assert by_id[fid][break_it.RUN_FIELD] == {"outcome": "failed"}
    assert out["merges"] == []
    # the group's resulting findings are tied into one fix group
    assert out["fixGroups"] == [{"group_id": "g0", "member_ids": ["v0", "v1", "v2"]}]
    assert verification.grouping_coverage_fault(survivors, grouping) is None
    # the rest of a group still merges, listing only the merged ids; the fix group names the kept id
    out = verification.merge_and_rank([a, c, d], [{"group_id": "g0", "member_ids": ["v0", "v2", "v3"]}])
    assert sorted(f["id"] for f in out["findings"]) == ["v0", "v3"]
    assert len(out["merges"]) == 1 and out["merges"][0]["member_ids"] == ["v2", "v3"]
    assert out["fixGroups"] == [{"group_id": "g0", "member_ids": ["v0", "v3"]}]
    # a group made only of break-it members is all unmerged, and still one fix group
    out = verification.merge_and_rank([a, b], [{"group_id": "g0", "member_ids": ["v0", "v1"]}])
    assert sorted(f["id"] for f in out["findings"]) == ["v0", "v1"] and out["merges"] == []
    assert out["fixGroups"] == [{"group_id": "g0", "member_ids": ["v0", "v1"]}]
    # no group id on a native-shaped group: the id is "g<index>"; a lone test carrier or no carrier ties nothing
    out = verification.merge_and_rank([c, d, a], [{"member_ids": ["v2", "v3"]}, {"member_ids": ["v0"]}])
    assert out["fixGroups"] == [] and ["v2", "v3"] in [m["member_ids"] for m in out["merges"]]
    out = verification.merge_and_rank([c, a, b], [{"member_ids": ["v2"]}, {"member_ids": ["v0", "v1"]}])
    assert out["fixGroups"] == [{"group_id": "g1", "member_ids": ["v0", "v1"]}]
    # an invalid grouping ties nothing
    assert verification.merge_and_rank([a, b], [{"member_ids": ["v0"]}])["fixGroups"] == []


def test_l4b_merge_and_rank_never_merges_a_carried_test_lost_finding():
    def finding(fid, **extra):
        out = {"id": fid, "file": "f%s.py" % fid, "line": 1, "title": "t%s" % fid,
               "severity": "Minor", "suggestion": "s-%s" % fid}
        out.update(extra)
        return out

    lost = finding("v0", carriedTestLost=True)
    other = finding("v1", severity="Important")
    out = verification.merge_and_rank([lost, other], [{"group_id": "g0", "member_ids": ["v0", "v1"]}])
    by_id = {f["id"]: f for f in out["findings"]}
    assert sorted(by_id) == ["v0", "v1"] and out["merges"] == []
    assert by_id["v0"]["carriedTestLost"] is True


def test_l5_a_fixed_break_it_test_that_is_kept_certifies(world):
    world.fold_panel(_break_it_finding())
    world.disposition("fixed")
    world.fix(_TEST_FAILING)
    assert RD._break_it_kept_step(world.state, world.state["config"]) is False
    (row,) = world.round_record["breakItKept"]
    assert row["outcome"] == "kept" and row["path"] == TEST_PATH
    RD._terminal_converged(world.state, world.state["config"], full_panel=True)
    assert world.state["terminal"] == "converged"
    assert any(d["kind"] == "break-it-kept" for d in world.state["decisions"])


def test_l6_a_fixed_break_it_test_left_out_of_the_diff_parks(world):
    world.fold_panel(_break_it_finding())
    world.disposition("fixed")
    world.fix(None)
    RD._terminal_converged(world.state, world.state["config"], full_panel=True)
    assert world.state["terminal"] == "cannot-certify"
    assert TEST_PATH in world.state["certification"]["reason"]
    assert "missing" in world.state["certification"]["reason"]


def test_l7_a_fixed_break_it_test_that_was_weakened_parks(world):
    world.fold_panel(_break_it_finding())
    world.disposition("fixed")
    world.fix(_TEST_WEAKENED)
    RD._terminal_converged(world.state, world.state["config"], full_panel=True)
    assert world.state["terminal"] == "cannot-certify"
    assert "changed" in world.state["certification"]["reason"]
    (row,) = world.round_record["breakItKept"]
    assert row["outcome"] == "changed"
    assert hashlib.sha256(_TEST_WEAKENED.encode()).hexdigest() != hashlib.sha256(
        _TEST_FAILING.encode()).hexdigest()


def test_l8_a_break_it_finding_not_fixed_owes_no_kept_check(world):
    world.fold_panel(_break_it_finding())
    world.disposition("refuted", refutedReason="the verifier refuted it")
    world.fix(None)
    RD._terminal_converged(world.state, world.state["config"], full_panel=True)
    assert world.state["terminal"] == "converged"
    (row,) = world.round_record["breakItKept"]
    assert row["outcome"] == "not-required" and row["reason"] == "refuted"


@pytest.mark.parametrize("line", [1, "1", " 1 "])
def test_a_numeric_line_citation_keeps_the_scope_exemption(world, line):
    state = world.fold_panel(_break_it_finding(line=line))
    (staged,) = state["_toVerify"]
    assert staged["line"] == 1 and staged[break_it.RUN_FIELD]["outcome"] == "failed"
    assert not world.round_record["compileDrops"]


def test_a_failed_break_it_run_with_no_disposition_withholds_certification(world):
    world.fold_panel(_break_it_finding())
    world.fix(None)
    RD._terminal_converged(world.state, world.state["config"], full_panel=True)
    assert world.state["terminal"] == "cannot-certify"
    (row,) = world.round_record["breakItKept"]
    assert row["outcome"] == "unresolved" and row["reason"] == "no-disposition"


def test_l9_runs_and_kept_checks_reach_the_round_records_and_the_receipt(world, tmp_path):
    world.config["recordsPath"] = str(tmp_path / "round-records.json")
    world.state["config"]["recordsPath"] = world.config["recordsPath"]
    world.fold_panel(_break_it_finding())
    world.disposition("fixed")
    world.fix(_TEST_FAILING)
    RD._terminal_converged(world.state, world.state["config"], full_panel=True)
    payload = RD._round_records_payload(world.state, world.state["config"])
    assert payload["outcome"] == "ready"
    block = payload["records"][-1]["disclosures"]
    assert block["breakItRuns"][0]["outcome"] == "failed"
    assert block["breakItKept"][0]["outcome"] == "kept"
    receipt = RD.build_receipt(world.state)
    (rnd,) = receipt["rounds"]
    assert rnd["breakItRuns"][0]["role"] == "test-role"
    assert rnd["breakItKept"][0]["outcome"] == "kept"


def test_l10_the_order_goldens_carry_the_break_it_clauses():
    golden = os.path.join(_HERE, "fixtures", "orders", "golden")
    with open(os.path.join(golden, "dispatch-verifiers.txt"), encoding="utf-8") as fh:
        verifiers = " ".join(fh.read().split())
    assert "whose `taxonomy` is `break-it-test` cites a new test file" in verifiers
    assert "`breakItRun` record" in verifiers
