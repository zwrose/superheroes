"""#2393: the kept break-it step reads the session head through ONE resolver (`_session_head`).

The command-line `next` builds a loop config with `repoRoot` and `baseRef` but no `headSha`; the
head lives in the session's `meta.json`. These tests build that shape and prove the kept step is
never headless when `meta.json` records a head, and still withholds when no head is recorded.
"""
import ast
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

PY = shlex.quote(sys.executable)
# pinned condition: every fixture git call ignores the user's and the system's git config and passes its
# commit identity inline; production timing or environment shape the pin makes unobservable: a host whose
# global config rewrites hooks, signing or default branches (the code under test reads the repo with the
# caller's own environment, so this pin covers only the fixture's own commits).
# inherited GIT_* routing (GIT_INDEX_FILE, GIT_DIR, GIT_WORK_TREE...) captured at collection would send a
# fixture's git call to the caller's repository, so none of it is kept; the two pins are the only GIT_* kept
_GIT_ENV = {**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
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

# The chain: every function from which the kept step is reached, plus the step itself. A caller that
# holds a `session_dir` must pass it down every one of these.
CHAIN = frozenset({
    "new_state", "_seed_returning_round", "_after_findings_settled",
    "_resolve_empty_fix_batch_convergence", "_fold_verify", "_after_audits",
    "_skip_empty_scoped_surface", "_fold_scoped", "_settle_delta", "_settle_delta_converged",
    "_settle_extra_audit", "_route_stall_self_recovery", "_handle_stall", "_terminal_converged",
    "_queue_fix_batch", "_break_it_kept_step",
})


def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True,
                          env=_GIT_ENV)
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


def _break_it_finding():
    return {"title": "Break-it: a retried charge runs twice", "file": TEST_PATH, "line": 1,
            "severity": "Important", "dimension": "Test", "taxonomy": break_it.TAXONOMY,
            "body": "payments risk area: the retry resends the charge",
            "consequence": "the customer is charged twice", "confidence": "High",
            "suggestion": _block(TEST_PATH, _TEST_FAILING)}


def _panel_artifact(*findings):
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["test-role"] = {"findings": list(findings)}
    return {"seats": seats}


class World:
    """A throwaway repo, a session dir whose meta.json records the head, and a loop state whose
    config carries `repoRoot` and `baseRef` but no `headSha` (the shape the command-line `next` builds)."""

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
        self.write_meta(headSha=self.head)
        self.config = {"leg": "code", "vendors": ["claude", "codex"], "diff": self.diff,
                       "fixerVendor": "claude", "repoRoot": str(self.repo),
                       "baseRef": self.base, "verifyCommand": "%s -c pass" % PY}
        assert "headSha" not in self.config and RD.FIX_FOLD_HEAD_KEY not in self.config
        self.state = RD.new_state(self.config)
        self.state["reviewedDiff"] = self.diff

    @property
    def session_dir(self):
        return str(self.session)

    def write_meta(self, **heads):
        meta = {"repoRoot": str(self.repo)}
        meta.update(heads)
        (self.session / RD.round_records.META_FILE).write_text(json.dumps(meta))

    def fold_panel(self, *findings):
        RD._fold(self.state, self.state["config"], RD.P_PANEL, _panel_artifact(*findings),
                 session_dir=self.session_dir)
        return self.state

    @property
    def round_record(self):
        return self.state["rounds"][str(self.state["round"])]

    def fix(self):
        """Commit the fix and its test; return the fix head."""
        _write(self.repo, CHARGE_PATH, _CHARGE_IDEMPOTENT)
        _write(self.repo, TEST_PATH, _TEST_FAILING)
        return _commit(self.repo, "fix the retry")

    def fixed_finding(self):
        """Fold the break-it finding at the setup head, then rule it fixed."""
        self.fold_panel(_break_it_finding())
        (run,) = self.round_record["breakItRuns"]
        assert run["outcome"] == "failed" and run["findingKey"], run
        RD._record_disposition(self.state, run["findingKey"], "fixed", 1)


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_t1_a_round_one_session_whose_head_only_meta_json_records_is_not_headless(world):
    world.fixed_finding()
    world.write_meta(headSha=world.fix())
    assert RD._break_it_kept_step(world.state, world.state["config"],
                                  session_dir=world.session_dir) is False
    (row,) = world.round_record["breakItKept"]
    assert row["outcome"] == "kept" and row["path"] == TEST_PATH, row


def test_t2_the_converge_chokepoint_certifies_a_round_one_session_headed_only_by_meta_json(world):
    world.fixed_finding()
    world.write_meta(headSha=world.fix())
    RD._terminal_converged(world.state, world.state["config"], full_panel=True,
                           session_dir=world.session_dir)
    assert world.state["terminal"] == "converged", world.state.get("certification")
    assert "cannot-certify" not in json.dumps(world.state.get("certification"))
    assert any(d["kind"] == "break-it-kept" for d in world.state["decisions"])


def test_t3_the_fix_fold_head_is_the_one_the_kept_step_checks(world):
    world.fixed_finding()
    fix_head = world.fix()
    # the older setup head holds no test; only the fix-fold head does
    world.write_meta(headSha=world.head, **{RD.FIX_FOLD_HEAD_KEY: fix_head})
    assert RD._break_it_kept_step(world.state, world.state["config"],
                                  session_dir=world.session_dir) is False
    (row,) = world.round_record["breakItKept"]
    assert row["outcome"] == "kept", row


def test_t4_a_session_with_no_head_anywhere_still_withholds(world):
    world.fixed_finding()
    world.fix()
    world.write_meta()
    assert RD._session_head(world.session_dir, world.state["config"]) is None
    assert RD._break_it_kept_step(world.state, world.state["config"],
                                  session_dir=world.session_dir) is True
    (row,) = world.round_record["breakItKept"]
    assert (row["outcome"], row["reason"]) == (break_it.KEPT_UNRESOLVED, "input-missing"), row
    assert world.state["terminal"] == "cannot-certify"


def _meta_file(tmp_path, name, content):
    session = tmp_path / name
    session.mkdir()
    if content is not None:
        (session / RD.round_records.META_FILE).write_text(content)
    return str(session)


FF, HS = RD.FIX_FOLD_HEAD_KEY, "headSha"


def test_t5_the_resolver_truth_table(tmp_path):
    def meta(**kv):
        return json.dumps(kv)

    rows = [
        # (name, meta.json text or None, config, expected)
        ("meta fix-fold beats everything", meta(**{FF: "m-ff", HS: "m-hs"}), {FF: "c-ff", HS: "c-hs"}, "m-ff"),
        ("meta headSha beats config keys", meta(**{HS: "m-hs"}), {FF: "c-ff", HS: "c-hs"}, "m-hs"),
        ("meta headSha beats config keys, empty meta fix-fold", meta(**{FF: "", HS: "m-hs"}), {FF: "c-ff"}, "m-hs"),
        ("config fix-fold beats config headSha", meta(), {FF: "c-ff", HS: "c-hs"}, "c-ff"),
        ("config headSha alone", meta(), {HS: "c-hs"}, "c-hs"),
        ("empty strings are skipped", meta(**{FF: "", HS: ""}), {FF: "", HS: "c-hs"}, "c-hs"),
        ("non-str values are skipped", meta(**{FF: 7, HS: ["x"]}), {FF: None, HS: "c-hs"}, "c-hs"),
        ("non-str values everywhere resolve to None", meta(**{FF: 7, HS: {}}), {FF: 1.5, HS: False}, None),
        ("missing meta.json falls to config", None, {FF: "c-ff", HS: "c-hs"}, "c-ff"),
        ("unreadable (non-JSON) meta.json falls to config", "{not json", {HS: "c-hs"}, "c-hs"),
        ("non-dict meta.json falls to config", json.dumps(["m-hs"]), {HS: "c-hs"}, "c-hs"),
        ("nothing recorded anywhere is None", meta(), {}, None),
    ]
    for index, (name, text, config, expected) in enumerate(rows):
        sd = _meta_file(tmp_path, "s%d" % index, text)
        assert RD._session_head(sd, config) == expected, name
        state = {"config": config}
        assert RD._session_certified_head(sd, state) == RD._session_head(sd, config), name
    # a falsy session_dir reads config only, even when a meta.json sits in the working directory's reach
    for falsy in (None, ""):
        assert RD._session_head(falsy, {FF: "c-ff", HS: "c-hs"}) == "c-ff"
        assert RD._session_head(falsy, {HS: "c-hs"}) == "c-hs"
        assert RD._session_head(falsy, {}) is None
    # a non-dict config reads as empty
    sd = _meta_file(tmp_path, "s-nondict", meta(**{HS: "m-hs"}))
    assert RD._session_head(sd, None) == "m-hs"
    assert RD._session_head(sd, ["c-hs"]) == "m-hs"
    assert RD._session_head(None, None) is None
    # _session_certified_head: a state that is not a dict, or has no dict config, reads config as empty
    empty = _meta_file(tmp_path, "s-empty", meta())
    for state in (None, "state", {}, {"config": None}, {"config": ["c-hs"]}):
        assert RD._session_certified_head(sd, state) == "m-hs"
        assert RD._session_certified_head(empty, state) is None


def _round_driver_tree():
    with open(os.path.join(_LIB, "round_driver.py"), encoding="utf-8") as fh:
        return ast.parse(fh.read())


def _function(tree, name):
    (found,) = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    return found


def _called_names(func):
    return {n.func.id for n in ast.walk(func)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


def _string_constants(func):
    return {n.value for n in ast.walk(func) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def _names(func):
    return {n.id for n in ast.walk(func) if isinstance(n, ast.Name)}


def _params(func):
    args = func.args
    return {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs}


def test_t6_census_a_the_kept_step_and_the_certified_head_read_through_the_resolver():
    tree = _round_driver_tree()
    kept = _function(tree, "_break_it_kept_step")
    assert "FIX_FOLD_HEAD_KEY" not in _names(kept)
    assert "headSha" not in _string_constants(kept)
    assert "_session_head" in _called_names(kept)
    certified = _function(tree, "_session_certified_head")
    assert "_session_head" in _called_names(certified)
    assert "headSha" not in _string_constants(certified)
    assert "FIX_FOLD_HEAD_KEY" not in _names(certified)


def _passed_session_dir(node, callee):
    """The expression a call passes as the callee's `session_dir`, or None when it passes none."""
    for keyword in node.keywords:
        if keyword.arg == "session_dir":
            return keyword.value
    args = callee.args
    positional = [a.arg for a in args.posonlyargs + args.args]
    if "session_dir" in positional and len(node.args) > positional.index("session_dir"):
        return node.args[positional.index("session_dir")]
    return None


def test_t6_census_b_every_chain_call_made_where_a_session_dir_is_held_passes_it():
    # axis: every call into a function that takes a session_dir, made where one is held, passes that
    # session_dir itself (never None, never omitted), so no route to the kept step loses it — see
    # bite-proof record wo_1_2393_kept_head
    tree = _round_driver_tree()
    defined = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    takes = {name for name, func in defined.items() if "session_dir" in _params(func)}
    missing, seen = [], set()
    for func in defined.values():
        if "session_dir" not in _params(func):
            continue
        for node in ast.walk(func):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in takes):
                seen.add(node.func.id)
                passed = _passed_session_dir(node, defined[node.func.id])
                if not (isinstance(passed, ast.Name) and passed.id == "session_dir"):
                    missing.append("%s:%d calls %s without its session_dir (%s)" % (
                        func.name, node.lineno, node.func.id,
                        "omitted" if passed is None else ast.unparse(passed)))
    assert sorted(CHAIN - seen) == [], "the census is not reaching every chain call"
    assert missing == []


def test_t6_census_c_every_chain_function_takes_a_session_dir():
    tree = _round_driver_tree()
    defined = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert sorted(CHAIN - set(defined)) == []
    assert sorted(name for name in CHAIN if "session_dir" not in _params(defined[name])) == []
