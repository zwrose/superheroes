# plugins/superheroes/lib/tests/test_lane_call.py
"""The lane floor (#1795): every lane is at or above one floor, computed in one place."""
import ast
import importlib.util
import inspect
import json
import os
import socket
import subprocess
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_LIB = os.path.join(_REPO_ROOT, "plugins/superheroes/lib")
_PINNED_PYTHON = os.path.join(_REPO_ROOT, "scripts", "pinned-python")


def _load(name):
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    path = os.path.join(_LIB, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


L = _load("lane_call")
CM = _load("core_md")

_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}

PAYMENTS = {
    "name": "Payments",
    "covers": ["src/payments/*"],
    "why": "Charges customers.",
    "undo": "Hard: a charge needs a refund.",
}
CUSTOMER_DATA = {
    "name": "Customer data",
    "covers": ["src/db/*.sql", "migrations/*"],
    "why": "Holds personal details.",
    "undo": "Hard: a leak cannot be taken back.",
}
RESULT_KEYS = {"floor", "lane", "why", "riskAreas", "touched", "unmatchable", "proposed", "proposalTaken"}
TOKENS = ("touches-risk-area", "risk-unclear-not-set", "risk-unclear-unmatchable", "risk-unclear-no-paths",
          "no-floor", "proposal-below-floor", "proposal-taken", "no-proposal-defaults-full", "proposal-invalid")


def _repo(tmp_path, areas=None, *, with_key=True):
    """A repo whose core.md holds the fixture facts and, when asked, the given riskAreas."""
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    if with_key:
        res = CM.write_project_config_item(repo, CM.RISK_AREAS_KEY, areas, root=store)
        assert res["action"] == "written"
    return repo, store


def _raw_core(tmp_path, json_text):
    """A repo whose in-repo core.md carries exactly the given json block text."""
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.mode_registry.ensure_project_store(repo, store)
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    text = (
        "<!-- superheroes-core: schemaVersion=2 status=confirmed created=2026-06-26 "
        "updated=2026-06-26 -->\n\n## Threat model\n\nsingle-user\n\n"
        "## Canonical patterns\n\n- x: a.ts:1\n\n"
        "```json superheroes-core\n%s\n```\n" % json_text
    )
    with open(os.path.join(d, "core.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    return repo, store


def _tokens(got):
    assert got["why"] and all(isinstance(w, str) for w in got["why"])
    return [w.split(": ", 1)[0] for w in got["why"]]


def _payments_repo(tmp_path):
    return _repo(tmp_path, [PAYMENTS, CUSTOMER_DATA])


# --- the invariant: a change that touches a risk area gets the floor full -------------------


def test_a_two_line_change_to_a_payments_file_gets_the_full_lane(tmp_path):
    # axis: the touched floor; a change touching a risk area leaving the floor below full, or the lane below it, whatever its size
    # the paths are the only input about the change: there is no size, line count or diff parameter
    assert list(inspect.signature(L.call).parameters) == ["cwd", "paths", "proposed", "root"]
    repo, store = _payments_repo(tmp_path)
    got = L.call(repo, ["src/payments/charge.py"], root=store)
    assert set(got) == RESULT_KEYS
    assert got["floor"] == "full" and got["lane"] == "full"
    assert got["why"][0] == "touches-risk-area: Payments (src/payments/charge.py)"
    assert got["touched"] == [{"name": "Payments", "matched": ["src/payments/charge.py"]}]
    assert got["riskAreas"] == {"state": "set", "reason": None, "detail": None}
    assert got["unmatchable"] == [] and got["proposed"] is None and got["proposalTaken"] is False


def test_a_model_that_judged_the_payments_change_trivial_still_gets_the_full_lane(tmp_path):
    # axis: the touched floor over a light proposal; the proposal lowering the lane or being taken
    repo, store = _payments_repo(tmp_path)
    got = L.call(repo, ["src/payments/charge.py"], proposed="light", root=store)
    assert got["floor"] == "full" and got["lane"] == "full"
    assert got["proposed"] == "light" and got["proposalTaken"] is False
    assert "proposal-below-floor" in _tokens(got) and "proposal-taken" not in _tokens(got)


def test_a_change_outside_every_area_takes_a_proposal_at_or_above_no_floor(tmp_path):
    # axis: the touched floor's other side; a floor raised with no area touched, or a valid proposal not taken
    repo, store = _payments_repo(tmp_path)
    full = L.call(repo, ["docs/readme.md"], proposed="full", root=store)
    assert full["floor"] is None and full["lane"] == "full" and full["proposalTaken"] is True
    light = L.call(repo, ["docs/readme.md"], proposed="light", root=store)
    assert light["floor"] is None and light["lane"] == "light" and light["proposalTaken"] is True
    assert _tokens(light) == ["no-floor", "proposal-taken"]
    micro = L.call(repo, ["docs/readme.md"], proposed="micro", root=store)
    assert micro["lane"] == "micro" and micro["proposalTaken"] is True
    none = L.call(repo, ["docs/readme.md"], root=store)
    assert none["floor"] is None and none["lane"] == "full" and none["proposalTaken"] is False
    assert _tokens(none) == ["no-floor", "no-proposal-defaults-full"]


# --- fail-closed edges ------------------------------------------------------------------------


def test_e1_risk_areas_not_set_for_any_reason_get_the_floor_full(tmp_path):
    # axis: the not-set floor; missing, empty or unreadable risk areas leaving the floor open or the lane below full
    missing = tmp_path / "missing"
    empty = tmp_path / "empty"
    unreadable = tmp_path / "unreadable"
    for d in (missing, empty, unreadable):
        d.mkdir()
    cases = [
        ("missing", _repo(missing, with_key=False)),
        ("empty", _repo(empty, [])),
        ("unreadable", _raw_core(unreadable, json.dumps(
            {"schemaVersion": 2, "verifyCommand": "npm test", "stackTags": ["node"],
             "projectConfiguration": ["risk"]}))),
    ]
    for reason, (repo, store) in cases:
        got = L.call(repo, ["docs/readme.md"], proposed="light", root=store)
        assert got["riskAreas"]["state"] == "not-set" and got["riskAreas"]["reason"] == reason
        assert got["floor"] == "full" and got["lane"] == "full" and got["proposalTaken"] is False
        assert "risk-unclear-not-set" in _tokens(got)
        assert got["touched"] == []


def test_e2_an_all_unmatchable_change_with_set_areas_gets_the_floor_full_never_light(tmp_path):
    # axis: the unmatchable floor; a change of only unmatchable paths leaving the floor open or the lane below full
    repo, store = _payments_repo(tmp_path)
    paths = ["/etc/passwd", "../outside.py", "src/../../x.py", ""]
    got = L.call(repo, paths, proposed="light", root=store)
    assert got["riskAreas"]["state"] == "set" and got["touched"] == []
    assert got["unmatchable"] == paths
    assert got["floor"] == "full" and got["lane"] == "full" and got["proposalTaken"] is False
    assert "risk-unclear-unmatchable" in _tokens(got)


def test_e3_a_mixed_matchable_and_unmatchable_change_touching_nothing_gets_the_floor_full(tmp_path):
    # axis: the unmatchable floor; an unmatchable path beside a matchable one that touches nothing leaving the floor open
    repo, store = _payments_repo(tmp_path)
    got = L.call(repo, ["docs/readme.md", "/abs/path.py"], proposed="micro", root=store)
    assert got["touched"] == [] and got["unmatchable"] == ["/abs/path.py"]
    assert got["floor"] == "full" and got["lane"] == "full" and got["proposalTaken"] is False
    assert _tokens(got)[0] == "risk-unclear-unmatchable"


def test_e4_an_empty_paths_list_gets_the_floor_full_even_with_set_areas(tmp_path):
    # axis: the no-paths floor; an empty paths list leaving the floor open or the lane below full
    repo, store = _payments_repo(tmp_path)
    got = L.call(repo, [], proposed="light", root=store)
    assert got["riskAreas"]["state"] == "set"
    assert got["floor"] == "full" and got["lane"] == "full" and got["proposalTaken"] is False
    assert _tokens(got)[0] == "risk-unclear-no-paths"


@pytest.mark.parametrize("paths", [None, "src/payments/charge.py", ("a",), {"a": 1}, ["a", 3], [None]])
def test_e5_a_paths_value_that_is_not_a_list_of_strings_gets_the_floor_full(tmp_path, paths):
    # axis: the not-set floor; a paths value that is not a list of strings leaving the floor open or the lane below full
    repo, store = _payments_repo(tmp_path)
    got = L.call(repo, paths, proposed="light", root=store)
    assert got["riskAreas"]["state"] == "not-set"
    assert got["floor"] == "full" and got["lane"] == "full" and got["proposalTaken"] is False
    assert "risk-unclear-not-set" in _tokens(got) and "risk-unclear-no-paths" not in _tokens(got)


@pytest.mark.parametrize("proposed", ["light", "micro"])
def test_e6_a_proposal_below_the_floor_gets_full_and_is_not_taken(tmp_path, proposed):
    # axis: never-lower; a proposal below the floor being taken or lowering the lane
    repo, store = _payments_repo(tmp_path)
    got = L.call(repo, ["src/db/schema.sql"], proposed=proposed, root=store)
    assert got["floor"] == "full" and got["lane"] == "full"
    assert got["proposed"] == proposed and got["proposalTaken"] is False
    assert any(w.startswith("proposal-below-floor: ") for w in got["why"])


@pytest.mark.parametrize("proposed", ["medium", 3, "", "FULL", ["full"], {"lane": "light"}, True, 0])
def test_e7_an_invalid_proposal_never_lowers_the_lane(tmp_path, proposed):
    # axis: an invalid proposal; one that lowers the lane, is taken, or goes unmarked proposal-invalid
    repo, store = _payments_repo(tmp_path)
    for paths in (["src/payments/charge.py"], ["docs/readme.md"], [], None):
        got = L.call(repo, paths, proposed=proposed, root=store)
        assert got["lane"] == "full" and got["proposalTaken"] is False and got["proposed"] == proposed
        assert "proposal-invalid" in _tokens(got)
        assert L.rank(got["lane"]) >= L.rank(got["floor"])


# --- a project with no risk areas -------------------------------------------------------------


def test_a_project_with_no_risk_areas_gives_a_money_change_the_full_lane(tmp_path):
    # axis: the not-set floor; a project with no risk areas lowering the lane for a money change
    repo, store = _repo(tmp_path, with_key=False)
    got = L.call(repo, ["src/billing/refund.py"], proposed="light", root=store)
    assert got["floor"] == "full" and got["lane"] == "full" and got["proposalTaken"] is False
    assert got["riskAreas"]["state"] == "not-set" and got["riskAreas"]["reason"] == "missing"
    assert got["why"][0].startswith("risk-unclear-not-set: ")


# --- the census -------------------------------------------------------------------------------


def test_census_every_routed_change_lands_in_the_three_lanes_at_or_above_its_floor(tmp_path):
    # axis: the three-lane census; a routed change landing outside micro, light and full, or below its floor
    assert L.LANES == ("micro", "light", "full") and len(L.LANES) == 3 and L.FLOOR_FULL == "full"
    assert [L.rank(lane) for lane in L.LANES] == [0, 1, 2] and L.rank("medium") < 0 and L.rank(None) < 0
    (tmp_path / "set").mkdir()
    (tmp_path / "none").mkdir()
    set_repo, set_store = _payments_repo(tmp_path / "set")
    none_repo, none_store = _repo(tmp_path / "none", with_key=False)
    changes = [
        (["src/payments/charge.py"], True),
        (["src/payments/charge.py", "README.md"], True),
        (["migrations/001.sql"], True),
        (["README.md"], False),
        (["docs/a.md", "docs/b.md"], False),
        (["README.md", "/abs"], True),
        (["/abs"], True),
        ([], True),
        (None, True),
        (["a", 1], True),
    ]
    proposals = [None, "micro", "light", "full", "medium", 3]
    seen = set()
    for paths, floored in changes:
        for proposed in proposals:
            for repo, store, areas_set in ((set_repo, set_store, True), (none_repo, none_store, False)):
                got = L.call(repo, paths, proposed=proposed, root=store)
                assert set(got) == RESULT_KEYS
                assert got["lane"] in L.LANES
                assert got["floor"] in (None, "full")
                assert (got["floor"] == "full") == (floored or not areas_set)
                assert L.rank(got["lane"]) >= L.rank(got["floor"])
                assert got["proposalTaken"] == (got["lane"] == proposed and proposed in L.LANES)
                assert got["why"] and all(w.split(": ", 1)[0] in TOKENS and ": " in w for w in got["why"])
                json.dumps(got)
                seen.add(got["lane"])
    assert seen == set(L.LANES)


# --- pure: no process, no network, no write, one reader call ----------------------------------


def _snapshot(root):
    out = {}
    for base, _, names in os.walk(root):
        for name in names:
            p = os.path.join(base, name)
            with open(p, "rb") as fh:
                out[p] = fh.read()
    return out


def test_call_makes_no_model_call_and_writes_nothing(tmp_path, monkeypatch):
    # axis: the no-process check; call starting a process, a shell or a connection, or writing a file
    repo, store = _payments_repo(tmp_path)
    real_run, real_popen = subprocess.run, subprocess.Popen
    passed_through = []

    def _refuse(*args, **kwargs):
        raise AssertionError("a process, a shell or a connection was started")

    def _is_identity_lookup(argv):
        # the repo-root and gitdir lookups (rev-parse) and the remote lookup (remote get-url)
        return bool(argv) and argv[0] == "git" and (
            "rev-parse" in argv or argv[-3:-1] == ["remote", "get-url"])

    def _only_the_identity_lookups(argv, *args, **kwargs):
        if _is_identity_lookup(argv):
            passed_through.append(list(argv))
            # the real run starts its process through Popen: let it, for this one call only
            monkeypatch.setattr(subprocess, "Popen", real_popen)
            try:
                return real_run(argv, *args, **kwargs)
            finally:
                monkeypatch.setattr(subprocess, "Popen", _refuse)
        return _refuse()

    # the reader's git identity lookups run for real; anything else call started would reach
    # the raising stand-ins
    monkeypatch.setattr(subprocess, "run", _only_the_identity_lookups)
    monkeypatch.setattr(subprocess, "Popen", _refuse)
    monkeypatch.setattr(os, "system", _refuse)
    monkeypatch.setattr(socket.socket, "connect", _refuse)
    before = _snapshot(tmp_path)
    got = L.call(repo, ["src/payments/charge.py", "./src/payments/charge.py"], proposed="light", root=store)
    assert got["floor"] == "full" and got["touched"] == [{"name": "Payments", "matched": ["src/payments/charge.py"]}]
    assert passed_through and all(_is_identity_lookup(argv) for argv in passed_through)
    assert _snapshot(tmp_path) == before


def test_call_asks_the_one_reader_exactly_once_and_matches_no_path_itself(tmp_path, monkeypatch):
    repo, store = _payments_repo(tmp_path)
    seen = []
    real = L.risk_areas.touched

    def counting(cwd, paths, root=None):
        seen.append((cwd, paths, root))
        return real(cwd, paths, root=root)

    monkeypatch.setattr(L.risk_areas, "touched", counting)
    L.call(repo, ["src/payments/charge.py"], root=store)
    assert seen == [(repo, ["src/payments/charge.py"], store)]
    with open(os.path.join(_LIB, "lane_call.py"), encoding="utf-8") as fh:
        source = fh.read()
    assert "fnmatch" not in source and "pattern_matches" not in source and "normalize_change_path" not in source


def test_lane_call_module_imports_no_process_network_or_engine_module():
    # axis: the no-process check; lane_call importing a process, network or engine module
    with open(os.path.join(_LIB, "lane_call.py"), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & {"subprocess", "socket", "urllib", "http", "engine_dispatch"}


# --- the unavailable basis: fail-closed, nothing read -----------------------------------------


def test_unavailable_carries_exactly_the_call_keys_and_the_full_floor(tmp_path):
    # axis: a basis that was never read gets the floor full; an unread basis leaving no floor or a lower lane
    repo, store = _payments_repo(tmp_path)
    got = L.unavailable("risk-unclear-not-set: nothing was read")
    assert set(got) == RESULT_KEYS == set(L.call(repo, ["docs/readme.md"], root=store))
    assert got["floor"] == "full" and got["lane"] == "full"
    assert got["why"] == ["risk-unclear-not-set: nothing was read"]
    assert got["riskAreas"] == {"state": "not-set", "reason": "unreadable", "detail": "not-read"}
    assert got["touched"] == [] and got["unmatchable"] == []
    assert got["proposed"] is None and got["proposalTaken"] is False
    assert list(inspect.signature(L.unavailable).parameters) == ["why", "proposed"]
    json.dumps(got)


@pytest.mark.parametrize("proposed,tokens,taken", [
    ("light", ["risk-unclear-no-paths", "proposal-below-floor"], False),
    ("micro", ["risk-unclear-no-paths", "proposal-below-floor"], False),
    ("full", ["risk-unclear-no-paths"], True),
    ("medium", ["risk-unclear-no-paths", "proposal-invalid"], False),
    (3, ["risk-unclear-no-paths", "proposal-invalid"], False),
    (None, ["risk-unclear-no-paths"], False),
])
def test_unavailable_records_the_proposal_and_never_lowers_the_lane(proposed, tokens, taken):
    # axis: unavailable with a proposal; a proposal below full being taken or lowering the lane
    got = L.unavailable("risk-unclear-no-paths: the changed files could not be read", proposed=proposed)
    assert got["floor"] == "full" and got["lane"] == "full"
    assert got["proposed"] == proposed and got["proposalTaken"] is taken
    assert _tokens(got) == tokens
    assert got["why"][0] == "risk-unclear-no-paths: the changed files could not be read"
    assert "proposal-taken" not in _tokens(got) and "no-proposal-defaults-full" not in _tokens(got)


def test_unavailable_starts_no_process_reads_no_store_and_writes_nothing(tmp_path, monkeypatch):
    # axis: the no-process check on unavailable; it starting a process, reading the store or writing a file
    def _refuse(*args, **kwargs):
        raise AssertionError("a process, a shell, a connection or a store read was started")

    monkeypatch.setattr(subprocess, "run", _refuse)
    monkeypatch.setattr(subprocess, "Popen", _refuse)
    monkeypatch.setattr(os, "system", _refuse)
    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(L.risk_areas, "touched", _refuse)
    before = _snapshot(tmp_path)
    got = L.unavailable("risk-unclear-not-set: nothing was read", proposed="light")
    assert got["floor"] == "full" and _snapshot(tmp_path) == before


# --- the command line -------------------------------------------------------------------------


def _cli(*args):
    return subprocess.run([_PINNED_PYTHON, "-B", os.path.join(_LIB, "lane_call.py"), *args],
                          capture_output=True, text=True, timeout=120)


def test_cli_round_trip_prints_the_result_as_json_and_exits_zero(tmp_path):
    repo, store = _payments_repo(tmp_path)
    run = _cli("call", "--cwd", repo, "--root", store, "--path", "src/payments/charge.py",
               "--proposed", "light")
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == L.call(repo, ["src/payments/charge.py"], proposed="light", root=store)
    assert run.stdout.startswith("{\n  ")
    out = json.loads(run.stdout)
    assert out["floor"] == "full" and out["lane"] == "full" and out["proposalTaken"] is False
    free = json.loads(_cli("call", "--cwd", repo, "--root", store, "--path", "docs/a.md",
                           "--proposed", "light").stdout)
    assert free["floor"] is None and free["lane"] == "light" and free["proposalTaken"] is True


def test_cli_with_no_path_reports_no_paths_and_a_paths_file_is_read(tmp_path):
    repo, store = _payments_repo(tmp_path)
    run = _cli("call", "--cwd", repo, "--root", store)
    assert run.returncode == 0 and json.loads(run.stdout)["why"][0].startswith("risk-unclear-no-paths: ")
    listing = tmp_path / "paths.bin"
    listing.write_bytes(b"docs/a.md\0src/payments/b.py\0")
    run = _cli("call", "--cwd", repo, "--root", store, "--paths-file", str(listing), "--nul")
    out = json.loads(run.stdout)
    assert run.returncode == 0 and out["touched"] == [{"name": "Payments", "matched": ["src/payments/b.py"]}]


def test_cli_unreadable_paths_file_exits_two_with_an_error(tmp_path):
    repo, store = _payments_repo(tmp_path)
    run = _cli("call", "--cwd", repo, "--root", store, "--paths-file", str(tmp_path / "missing.txt"))
    out = json.loads(run.stdout)
    assert run.returncode == 2 and out["error"] == "paths-file-unreadable" and out["detail"]


def test_a_broad_change_keeps_every_path_in_touched_but_bounds_the_why_lines(tmp_path):
    # axis: the why line stays short however many paths match; touched and unmatchable stay complete
    repo, store = _payments_repo(tmp_path)
    matched = ["src/payments/%s%04d.py" % ("x" * 50, i) for i in range(3000)]
    unmatched = ["/abs/%s%04d.py" % ("y" * 50, i) for i in range(3000)]
    got = L.call(repo, matched + unmatched, root=store)
    assert got["floor"] == "full"
    assert got["touched"] == [{"name": "Payments", "matched": matched}] and got["unmatchable"] == unmatched
    assert got["why"][0] == "touches-risk-area: Payments (3000 paths: %s, ...)" % ", ".join(matched[:3])
    unmatchable_why = next(w for w in got["why"] if w.startswith("risk-unclear-unmatchable"))
    assert "3000 changed path(s)" in unmatchable_why and repr(unmatched[2]) in unmatchable_why
    assert repr(unmatched[3]) not in unmatchable_why
    assert sum(len(w) for w in got["why"]) < 2000


def test_stripping_a_line_built_for_a_longer_area_name_keeps_that_whole_name():
    # axis: the area name kept when one name prefixes another; the longer name cut back to its shorter prefix
    names = ["Payments", "Payments (refunds)"]
    line = "%s %s (%s)" % (L.WHY_TOUCHES, "Payments (refunds)", "src/refunds/a.py, src/refunds/b.py")
    assert L.why_line_paths_stripped(line, names) == "%s Payments (refunds)" % L.WHY_TOUCHES


def test_stripping_a_line_built_for_the_shorter_area_name_keeps_that_name():
    # axis: the area name kept when one name prefixes another; the shorter name widened to its longer neighbour
    names = ["Payments", "Payments (refunds)"]
    line = "%s %s (%s)" % (L.WHY_TOUCHES, "Payments", "src/payments/a.py, src/payments/b.py")
    assert L.why_line_paths_stripped(line, names) == "%s Payments" % L.WHY_TOUCHES


def test_review_record_repeats_no_lane_reason_token_literal():
    """lane_call owns the reason tokens and the path-stripping format; review_record imports them."""
    import lane_call as lc
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "review_record.py"),
               encoding="utf-8").read()
    tokens = [getattr(lc, n) for n in dir(lc) if n.startswith("WHY_") and isinstance(getattr(lc, n), str)
              and n != "WHY_SAMPLE"]
    assert len(tokens) >= 9
    for token in tokens + [lc._AGAINST_AREA.strip(), lc.WHY_TOUCHES.rstrip(":")]:
        assert token not in src, token
