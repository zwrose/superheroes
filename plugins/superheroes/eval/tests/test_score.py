import json
import re

import pytest
import score


# ---- helpers -------------------------------------------------------------

def _write(path, obj):
    path.write_text(json.dumps(obj) if not isinstance(obj, str) else obj)
    return str(path)


def _make_fixture(tmp_path, expected, diff):
    fdir = tmp_path / "fixture"
    fdir.mkdir()
    (fdir / "expected.json").write_text(json.dumps(expected))
    (fdir / "diff.txt").write_text(diff)
    return str(fdir)


# A small synthetic diff for one file. New-file line numbers (the `+` side)
# start at 1 here. Functions span the lines shown.
SYNTH_DIFF = """diff --git a/src/app.ts b/src/app.ts
--- a/src/app.ts
+++ b/src/app.ts
@@ -0,0 +1,20 @@
+import { db } from "./db";
+
+export function getNote(id) {
+  return db.notes.findOne({ id });
+}
+
+export function classifyOrder(order) {
+  if (order.status === "open") {
+    if (order.total > 100) {
+      return "large";
+    }
+  }
+  return "small";
+}
+
+function persistNote(record) {
+  return db.notes.insert(record);
+}
+
+const x = 1;
"""

# Line numbers in the new file (1-based):
# 1  import { db } from "./db";
# 2  (blank)
# 3  export function getNote(id) {
# 4    return db.notes.findOne({ id });
# 5  }
# 6  (blank)
# 7  export function classifyOrder(order) {
# 8    if (order.status === "open") {
# 9      if (order.total > 100) {
# 10       return "large";
# 11     }
# 12   }
# 13   return "small";
# 14 }
# 15 (blank)
# 16 function persistNote(record) {
# 17   return db.notes.insert(record);
# 18 }
# 19 (blank)
# 20 const x = 1;


# ---- line-scoped slack (test case 1) -------------------------------------

def test_line_scoped_exact_match(tmp_path):
    expected = {"seeds": [{"dimension": "Code", "taxonomy": "hardcoded-error-string",
                           "file": "src/app.ts",
                           "lineHint": "  return db.notes.findOne({ id });"}],
                "traps": []}
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    findings = [{"dimension": "Code", "file": "src/app.ts", "line": 4}]  # seed is line 4
    r = score.score_fixture(fdir, findings)
    assert r["recall"]["matched"] == 1
    assert r["recall"]["total"] == 1


def test_line_scoped_within_two_lines(tmp_path):
    expected = {"seeds": [{"dimension": "Code", "taxonomy": "hardcoded-error-string",
                           "file": "src/app.ts",
                           "lineHint": "  return db.notes.findOne({ id });"}],
                "traps": []}
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    findings = [{"dimension": "Code", "file": "src/app.ts", "line": 6}]  # +2 from line 4
    r = score.score_fixture(fdir, findings)
    assert r["recall"]["matched"] == 1


def test_line_scoped_three_lines_off_not_matched(tmp_path):
    expected = {"seeds": [{"dimension": "Code", "taxonomy": "hardcoded-error-string",
                           "file": "src/app.ts",
                           "lineHint": "  return db.notes.findOne({ id });"}],
                "traps": []}
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    findings = [{"dimension": "Code", "file": "src/app.ts", "line": 7}]  # +3 from line 4
    r = score.score_fixture(fdir, findings)
    assert r["recall"]["matched"] == 0
    assert len(r["recall"]["missed"]) == 1


# ---- function-scoped span (test case 2) ----------------------------------

def test_function_scoped_match_several_lines_off(tmp_path):
    # cognitive-complexity seed on classifyOrder (declaration at line 7).
    # A finding several lines off (line 10, the deepest branch) is still inside
    # the function span window -> matched, even though it is > 2 lines away.
    expected = {"seeds": [{"dimension": "Code", "taxonomy": "cognitive-complexity",
                           "file": "src/app.ts",
                           "lineHint": "export function classifyOrder(order) {"}],
                "traps": []}
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    findings = [{"dimension": "Code", "file": "src/app.ts", "line": 10}]
    r = score.score_fixture(fdir, findings)
    assert r["recall"]["matched"] == 1


def test_function_scoped_same_taxonomy_anywhere_in_file(tmp_path):
    # Function-scoped fallback: same file + dimension + taxonomy matches even
    # outside the +/-K window.
    expected = {"seeds": [{"dimension": "Code", "taxonomy": "cognitive-complexity",
                           "file": "src/app.ts",
                           "lineHint": "export function classifyOrder(order) {"}],
                "traps": []}
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    findings = [{"dimension": "Code", "file": "src/app.ts", "line": 200,
                 "taxonomy": "cognitive-complexity"}]
    r = score.score_fixture(fdir, findings)
    assert r["recall"]["matched"] == 1


# ---- traps / precision (test case 3) -------------------------------------

def test_trap_flagged_counts_as_fp(tmp_path):
    expected = {"seeds": [],
                "traps": [{"file": "src/app.ts",
                           "lineHint": "  return db.notes.insert(record);",
                           "whyNotFlagged": "context-line"}]}  # line 17
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    findings = [{"dimension": "Code", "file": "src/app.ts", "line": 17}]
    r = score.score_fixture(fdir, findings)
    assert r["precision"]["traps_flagged"] == 1
    assert "src/app.ts:17" in r["precision"]["trap_hits"]


# ---- net_new (test case 4) -----------------------------------------------

def test_net_new_when_matching_neither(tmp_path):
    expected = {"seeds": [{"dimension": "Code", "taxonomy": "hardcoded-error-string",
                           "file": "src/app.ts",
                           "lineHint": "  return db.notes.findOne({ id });"}],
                "traps": []}
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    # line 20 matches neither the seed (line 4) nor any trap
    findings = [{"dimension": "Code", "file": "src/app.ts", "line": 4, "title": "seed hit"},
                {"dimension": "Code", "file": "src/app.ts", "line": 20, "title": "extra"}]
    r = score.score_fixture(fdir, findings)
    assert r["recall"]["matched"] == 1
    assert len(r["net_new"]) == 1
    assert r["net_new"][0]["line"] == 20


# ---- recall math + by_dimension (test case 5) ----------------------------

def test_recall_math_by_dimension(tmp_path):
    expected = {"seeds": [
        {"dimension": "Code", "taxonomy": "hardcoded-error-string", "file": "src/app.ts",
         "lineHint": "  return db.notes.findOne({ id });"},                 # line 4
        {"dimension": "Security", "taxonomy": "BOLA", "file": "src/app.ts",
         "lineHint": "  return db.notes.insert(record);"},                  # line 17
        {"dimension": "Security", "taxonomy": "BOPLA", "file": "src/app.ts",
         "lineHint": "const x = 1;"},                                       # line 20
    ], "traps": []}
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    # Hit the Code seed and one of two Security seeds.
    findings = [{"dimension": "Code", "file": "src/app.ts", "line": 4},
                {"dimension": "Security", "file": "src/app.ts", "line": 17}]
    r = score.score_fixture(fdir, findings)
    assert r["recall"]["matched"] == 2
    assert r["recall"]["total"] == 3
    assert r["recall"]["by_dimension"]["Code"] == {"matched": 1, "total": 1}
    assert r["recall"]["by_dimension"]["Security"] == {"matched": 1, "total": 2}
    # the missed Security/BOPLA seed surfaces in missed[]
    assert len(r["recall"]["missed"]) == 1


def test_dimension_mismatch_does_not_match(tmp_path):
    expected = {"seeds": [{"dimension": "Code", "taxonomy": "hardcoded-error-string",
                           "file": "src/app.ts",
                           "lineHint": "  return db.notes.findOne({ id });"}],
                "traps": []}
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    # Right line, wrong dimension -> not a recall match (and becomes net_new).
    findings = [{"dimension": "Security", "file": "src/app.ts", "line": 4}]
    r = score.score_fixture(fdir, findings)
    assert r["recall"]["matched"] == 0
    assert len(r["net_new"]) == 1


# ---- baseline gate (test case 6) -----------------------------------------

def test_gate_pass_when_improved(tmp_path):
    expected = {"seeds": [{"dimension": "Code", "taxonomy": "hardcoded-error-string",
                           "file": "src/app.ts",
                           "lineHint": "  return db.notes.findOne({ id });"}],
                "traps": [{"file": "src/app.ts",
                           "lineHint": "  return db.notes.insert(record);",
                           "whyNotFlagged": "context-line"}]}  # line 17
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    improved = [{"dimension": "Code", "file": "src/app.ts", "line": 4}]   # seed hit, no trap
    baseline = [{"dimension": "Code", "file": "src/app.ts", "line": 17}]  # missed seed, hit trap
    r = score.score_fixture(fdir, improved, baseline_findings=baseline)
    assert r["gate"] == "PASS"


def test_gate_fail_on_lost_seed(tmp_path):
    expected = {"seeds": [{"dimension": "Code", "taxonomy": "hardcoded-error-string",
                           "file": "src/app.ts",
                           "lineHint": "  return db.notes.findOne({ id });"}],
                "traps": []}
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    improved = []                                                          # lost the seed
    baseline = [{"dimension": "Code", "file": "src/app.ts", "line": 4}]    # caught it
    r = score.score_fixture(fdir, improved, baseline_findings=baseline)
    assert r["gate"] == "FAIL"


def test_gate_fail_on_new_trap(tmp_path):
    expected = {"seeds": [{"dimension": "Code", "taxonomy": "hardcoded-error-string",
                           "file": "src/app.ts",
                           "lineHint": "  return db.notes.findOne({ id });"}],
                "traps": [{"file": "src/app.ts",
                           "lineHint": "  return db.notes.insert(record);",
                           "whyNotFlagged": "context-line"}]}  # line 17
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    improved = [{"dimension": "Code", "file": "src/app.ts", "line": 4},     # seed hit
                {"dimension": "Code", "file": "src/app.ts", "line": 17}]    # but flags a trap
    baseline = [{"dimension": "Code", "file": "src/app.ts", "line": 4}]     # seed hit, no trap
    r = score.score_fixture(fdir, improved, baseline_findings=baseline)
    assert r["gate"] == "FAIL"


def test_gate_na_without_baseline(tmp_path):
    expected = {"seeds": [], "traps": []}
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    r = score.score_fixture(fdir, [])
    assert r["gate"] == "n/a"


# ---- findings loading from disk ------------------------------------------

def test_load_findings_from_glob_merges_arrays(tmp_path):
    d = tmp_path / "out"
    d.mkdir()
    _write(d / "a.json", [{"dimension": "Code", "file": "x.ts", "line": 1}])
    _write(d / "b.json", [{"dimension": "Security", "file": "y.ts", "line": 2}])
    loaded = score.load_findings(str(d))
    assert len(loaded) == 2


# ---- smoke test against a real fixture -----------------------------------

def test_smoke_real_refactor_fixture(tmp_path):
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    fdir = os.path.join(os.path.dirname(here), "fixtures", "refactor")
    # A perfect-recall, no-trap improved findings set citing the seed lines.
    findings = [
        {"dimension": "Architecture", "taxonomy": "AcyclicDependencies",
         "file": "src/services/billing.ts", "line": 4},
        {"dimension": "Code", "taxonomy": "cognitive-complexity",
         "file": "src/services/orders.ts", "line": 12},
        {"dimension": "Security", "taxonomy": "BFLA",
         "file": "src/handlers/admin-orders.ts", "line": 7},
        {"dimension": "Security", "taxonomy": "BOPLA",
         "file": "src/handlers/admin-orders.ts", "line": 19},
        {"dimension": "Test", "taxonomy": "mock-echo",
         "file": "src/services/orders.test.ts", "line": 13},
    ]
    r = score.score_fixture(fdir, findings)
    assert r["recall"]["total"] == 5
    assert r["recall"]["matched"] == 5
    assert r["precision"]["traps_flagged"] == 0


# ---- Failure-Mode whole-flow classes (premortem-reviewer) ------------------

# CONVENTIONS §11.3: this is a deliberate test-INPUT enumeration of the Failure-Mode
# whole-flow classes, blessed as a tripwire — NOT a contract test restating the home.
# The authoritative agent-table ↔ score.py sync is enforced by test_taxonomy_sync.py
# (which reads the premortem-reviewer agent table live). Typed once here as a single
# module-local constant, reused by the parametrize and the coverage assertion below, so
# these classes exercise scoring behavior from one place rather than two hand-kept copies.
_WHOLE_FLOW_CLASSES = (
    "concurrency/race",
    "partial-failure",
    "dependency-failure",
    "resource-exhaustion",
    "migration-rollback",
    "fail-direction",
    "transport-contract",
)


@pytest.mark.parametrize("taxonomy", _WHOLE_FLOW_CLASSES)
def test_failure_mode_seed_matches_at_flow_distance(tmp_path, taxonomy):
    # Whole-flow classes are function-scoped: a correct finding citing a
    # different line of the same flow (10 lines off) must still match.
    expected = {"seeds": [{"dimension": "Failure-Mode", "taxonomy": taxonomy,
                           "file": "src/app.ts",
                           "lineHint": "export function getNote(id) {"}],  # line 3
                "traps": []}
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    findings = [{"dimension": "Failure-Mode", "file": "src/app.ts", "line": 13}]
    r = score.score_fixture(fdir, findings)
    assert r["recall"]["matched"] == 1


@pytest.mark.parametrize("taxonomy", ["detectability", "assumption-violation"])
def test_line_scoped_failure_mode_taxonomies_stay_line_scoped(tmp_path, taxonomy):
    # detectability and assumption-violation keep the exact +/-2 default
    # (they are NOT in FUNCTION_SCOPED). A finding 4 lines off must not match.
    expected = {"seeds": [{"dimension": "Failure-Mode", "taxonomy": taxonomy,
                           "file": "src/app.ts",
                           "lineHint": "export function getNote(id) {"}],  # line 3
                "traps": []}
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    findings = [{"dimension": "Failure-Mode", "file": "src/app.ts", "line": 7, "taxonomy": taxonomy}]  # +4 off
    r = score.score_fixture(fdir, findings)
    assert r["recall"]["matched"] == 0


def test_failure_mode_seed_matches_at_exact_window_boundary(tmp_path):
    # Boundary pin: a finding exactly K=15 lines from the seed's resolved line
    # (line 3) must still match (|18 - 3| == 15 == FUNCTION_WINDOW).
    expected = {"seeds": [{"dimension": "Failure-Mode", "taxonomy": "partial-failure",
                           "file": "src/app.ts",
                           "lineHint": "export function getNote(id) {"}],  # line 3
                "traps": []}
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    findings = [{"dimension": "Failure-Mode", "file": "src/app.ts", "line": 18}]  # exactly 15 off
    r = score.score_fixture(fdir, findings)
    assert r["recall"]["matched"] == 1


@pytest.mark.parametrize("reason_token", [
    "profile-excluded-race",
    "retry-wrapped",
    "framework-transaction",
])
def test_failure_mode_trap_reason_is_function_scoped(tmp_path, reason_token):
    # A bait trap whose whyNotFlagged carries a Failure-Mode scope token uses
    # the +/-15 window: a finding 10 lines off still counts as a trap hit.
    expected = {"seeds": [],
                "traps": [{"file": "src/app.ts",
                           "lineHint": "export function getNote(id) {",  # line 3
                           "whyNotFlagged": reason_token + " — guarded, see CLAUDE.md"}]}
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    findings = [{"dimension": "Failure-Mode", "file": "src/app.ts", "line": 13}]
    r = score.score_fixture(fdir, findings)
    assert r["precision"]["traps_flagged"] == 1


def test_token_less_trap_reason_stays_line_scoped(tmp_path):
    # A prose reason with NO scope token silently degrades to +/-2 — the spec
    # requires bait reasons to carry their token; this test pins the behavior
    # that makes that requirement load-bearing.
    expected = {"seeds": [],
                "traps": [{"file": "src/app.ts",
                           "lineHint": "export function getNote(id) {",  # line 3
                           "whyNotFlagged": "this is fine because reasons"}]}
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    findings = [{"dimension": "Failure-Mode", "file": "src/app.ts", "line": 13}]
    r = score.score_fixture(fdir, findings)
    assert r["precision"]["traps_flagged"] == 0


def test_finding_outside_all_windows_lands_net_new(tmp_path):
    # Negative boundary: 16+ lines from a function-scoped trap is outside the
    # +/-15 window — the FP lands in net_new, NOT traps.
    expected = {"seeds": [],
                "traps": [{"file": "src/app.ts",
                           "lineHint": "import { db } from \"./db\";",  # line 1
                           "whyNotFlagged": "framework-transaction — atomic"}]}
    fdir = _make_fixture(tmp_path, expected, SYNTH_DIFF)
    findings = [{"dimension": "Failure-Mode", "file": "src/app.ts", "line": 17}]  # 16 off
    r = score.score_fixture(fdir, findings)
    assert r["precision"]["traps_flagged"] == 0
    assert len(r["net_new"]) == 1


# ---- real-fixture liveness smokes (failure-modes fixtures) -----------------

def _real_fixture(name):
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "fixtures", name)


def test_smoke_failure_modes_perfect_recall():
    # Liveness: every seed's lineHint resolves, and a finding citing each
    # resolved line exactly scores matched == total. An unresolvable seed
    # would fail loudly here (missed[]), before any agent ever runs.
    fdir = _real_fixture("failure-modes")
    expected = score.load_expected(fdir)
    with open(fdir + "/diff.txt") as f:
        by_file = score._parse_diff_lines(f.read())
    findings = []
    for seed in expected["seeds"]:
        line = score._resolve_line(by_file, seed["file"], seed["lineHint"])
        assert line is not None, f"seed lineHint does not resolve: {seed['lineHint']!r}"
        findings.append({"dimension": seed["dimension"],
                         "file": seed["file"], "line": line})
    r = score.score_fixture(fdir, findings)
    assert r["recall"]["total"] == len(_WHOLE_FLOW_CLASSES)
    assert {s["taxonomy"] for s in expected["seeds"]} == set(_WHOLE_FLOW_CLASSES)
    assert r["recall"]["matched"] == r["recall"]["total"] == len(expected["seeds"])
    assert r["precision"]["traps_flagged"] == 0


def test_smoke_bait_fixture_traps_are_live():
    # Liveness: every bait trap's lineHint resolves AND fires when a finding
    # is placed on it. traps_flagged == 0 is otherwise vacuously satisfiable
    # by a dead trap whose lineHint never matches (no warning from score.py).
    fdir = _real_fixture("failure-modes-bait")
    expected = score.load_expected(fdir)
    assert expected["seeds"] == []
    with open(fdir + "/diff.txt") as f:
        by_file = score._parse_diff_lines(f.read())
    findings = []
    for trap in expected["traps"]:
        line = score._resolve_line(by_file, trap["file"], trap["lineHint"])
        assert line is not None, f"trap lineHint does not resolve: {trap['lineHint']!r}"
        findings.append({"dimension": "Failure-Mode", "file": trap["file"], "line": line})
    assert len(expected["traps"]) == 3
    r = score.score_fixture(fdir, findings)
    assert r["precision"]["traps_flagged"] == len(expected["traps"])


# ---- real-fixture liveness smokes (high-noise fixture) ---------------------

def _raw_diff_occurrences(diff_text):
    """Per-file list of (new_line, prefix, stripped) for '+' and context lines.

    Mirrors _parse_diff_lines line-number accounting; keeps every occurrence
    (not first-occurrence-wins) so uniqueness can be asserted.
    """
    by_file = {}
    cur_file = None
    new_lineno = 0
    for raw in diff_text.splitlines():
        if raw.startswith("diff --git"):
            cur_file = None
            continue
        if raw.startswith("+++ "):
            path = raw[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            cur_file = path
            by_file.setdefault(cur_file, [])
            continue
        if raw.startswith("--- "):
            continue
        if raw.startswith("@@"):
            try:
                plus = raw.split("+", 1)[1]
                new_start = int(plus.split(",", 1)[0].split(" ", 1)[0])
                new_lineno = new_start - 1
            except (IndexError, ValueError):
                new_lineno = 0
            continue
        if cur_file is None:
            continue
        if raw.startswith("+"):
            new_lineno += 1
            by_file[cur_file].append((new_lineno, "+", raw[1:].strip()))
        elif raw.startswith("-"):
            continue
        else:
            new_lineno += 1
            text = raw[1:].strip() if raw.startswith(" ") else raw.strip()
            by_file[cur_file].append((new_lineno, " ", text))
    return by_file


def _high_noise_fixture():
    fdir = _real_fixture("high-noise")
    expected = score.load_expected(fdir)
    with open(fdir + "/diff.txt") as f:
        diff_text = f.read()
    by_file = score._parse_diff_lines(diff_text)
    raw_by_file = _raw_diff_occurrences(diff_text)
    return fdir, expected, by_file, raw_by_file


def test_smoke_high_noise_hints_resolve_and_are_unique():
    # Liveness: own-dimension recall 1/1 and traps_flagged == 0 are both
    # vacuously satisfiable by a broken fixture — an unresolvable lineHint is
    # silently never matched, and a dead trap can never be flagged (score.py
    # warns about neither). Pin every seed/trap lineHint to exactly one diff
    # line and to _resolve_line's answer before any agent ever runs. Also pin
    # context-line traps to a real context (' ') prefix — a trap whose anchor
    # silently drifts onto a '+' line would punish a correct in-scope finding
    # while expected.json still calls it pre-existing.
    fdir, expected, by_file, raw_by_file = _high_noise_fixture()
    for seed in expected["seeds"]:
        hint = seed["lineHint"].strip()
        assert hint, f"seed lineHint is blank: {seed!r}"
        occs = [(ln, pfx) for ln, pfx, txt in raw_by_file[seed["file"]] if txt == hint]
        assert len(occs) == 1, (
            f"seed lineHint must occur exactly once in {seed['file']!r}: {hint!r} ({len(occs)} hits)")
        line, prefix = occs[0]
        resolved = score._resolve_line(by_file, seed["file"], seed["lineHint"])
        assert resolved == line
        assert prefix == "+", (
            f"seed lineHint must sit on a '+' line per README contract: {hint!r}")
    for trap in expected["traps"]:
        hint = trap["lineHint"].strip()
        assert hint, f"trap lineHint is blank: {trap!r}"
        occs = [(ln, pfx) for ln, pfx, txt in raw_by_file[trap["file"]] if txt == hint]
        assert len(occs) == 1, (
            f"trap lineHint must occur exactly once in {trap['file']!r}: {hint!r} ({len(occs)} hits)")
        line, prefix = occs[0]
        resolved = score._resolve_line(by_file, trap["file"], trap["lineHint"])
        assert resolved == line
        reason = trap.get("whyNotFlagged") or ""
        if reason.startswith("context-line"):
            assert prefix == " ", (
                f"context-line trap must sit on a context line, not '+': {hint!r}")


def test_smoke_high_noise_perfect_recall():
    # Liveness: one finding per seed on its resolved line with that seed's
    # dimension must score recall.matched == recall.total == 5 and
    # traps_flagged == 0 — the fixture's two acceptance bars together.
    fdir, expected, by_file, _raw = _high_noise_fixture()
    findings = []
    for seed in expected["seeds"]:
        line = score._resolve_line(by_file, seed["file"], seed["lineHint"])
        findings.append({"dimension": seed["dimension"],
                         "file": seed["file"], "line": line,
                         "taxonomy": seed.get("taxonomy")})
    r = score.score_fixture(fdir, findings)
    assert r["recall"]["matched"] == r["recall"]["total"] == 5
    for dim in r["recall"]["by_dimension"]:
        assert r["recall"]["by_dimension"][dim]["matched"] == r["recall"]["by_dimension"][dim]["total"]
    assert r["precision"]["traps_flagged"] == 0


def test_smoke_high_noise_every_trap_is_live():
    # Liveness: traps_flagged == 0 is vacuously satisfiable by a dead trap
    # whose lineHint never matches (no warning from score.py). One finding at
    # a time proves each trap fires alone — no dead traps. Anchor-only probing
    # cannot see partial window overlap (two function-scoped anchors 16–30
    # lines apart each score alone at their own anchor, yet a finding between
    # them counts against both); so also assert every same-file pair of
    # effective scorer windows is disjoint.
    fdir, expected, by_file, _raw = _high_noise_fixture()
    assert len(expected["traps"]) == 14
    intervals_by_file = {}
    for trap in expected["traps"]:
        line = score._resolve_line(by_file, trap["file"], trap["lineHint"])
        findings = [{"dimension": "Code", "file": trap["file"], "line": line}]
        r = score.score_fixture(fdir, findings)
        assert r["precision"]["traps_flagged"] == 1
        assert r["precision"]["trap_hits"] == ["%s:%s" % (trap["file"], line)]
        reason = trap.get("whyNotFlagged") or ""
        half = (score.FUNCTION_WINDOW
                if any(token in reason for token in score.FUNCTION_SCOPED_TRAP_REASONS)
                else score.LINE_SLACK)
        intervals_by_file.setdefault(trap["file"], []).append(
            (line - half, line + half, trap))
    for file_path, intervals in intervals_by_file.items():
        for i, (a_lo, a_hi, a_trap) in enumerate(intervals):
            for b_lo, b_hi, b_trap in intervals[i + 1:]:
                assert a_hi < b_lo or b_hi < a_lo, (
                    f"trap windows overlap in {file_path!r}: "
                    f"{a_trap['lineHint']!r} [{a_lo},{a_hi}] vs "
                    f"{b_trap['lineHint']!r} [{b_lo},{b_hi}]")


def test_smoke_high_noise_seed_windows_never_touch_a_trap():
    # Collision proof: trap matching ignores the finding's dimension, so a
    # correct finding on a seed that drifts a few lines can land in a nearby
    # trap's window and score as a false positive — the artifact documented
    # in RESULTS.md for the 0.14.0 run. Every real line of each seed's
    # accepted window must keep traps_flagged == 0 while still matching that
    # seed. For function-scoped seeds, _matches_location also accepts the
    # taxonomy anywhere in the same file — so the fixture's safety claim is
    # that those files contain no traps at all; assert that directly rather
    # than under-approximating with a ±15 sweep alone.
    fdir, expected, by_file, raw_by_file = _high_noise_fixture()
    for seed in expected["seeds"]:
        line = score._resolve_line(by_file, seed["file"], seed["lineHint"])
        taxonomy = seed.get("taxonomy")
        if taxonomy in score.FUNCTION_SCOPED:
            assert not any(t["file"] == seed["file"] for t in expected["traps"]), (
                f"function-scoped seed {taxonomy!r} shares a file with traps; "
                f"unbounded same-file taxonomy match would be unsafe")
        window = (score.FUNCTION_WINDOW if taxonomy in score.FUNCTION_SCOPED
                  else score.LINE_SLACK)
        valid_lines = {ln for ln, _pfx, _txt in raw_by_file[seed["file"]]}
        for offset in range(-window, window + 1):
            at_line = line + offset
            if at_line < 1 or at_line not in valid_lines:
                continue
            findings = [{"dimension": seed["dimension"],
                         "file": seed["file"], "line": at_line,
                         "taxonomy": taxonomy}]
            r = score.score_fixture(fdir, findings)
            assert r["precision"]["traps_flagged"] == 0, (
                f"seed {taxonomy!r} at line {at_line} (offset {offset:+d}) hit a trap")
            assert r["recall"]["matched"] == 1, (
                f"seed {taxonomy!r} at line {at_line} (offset {offset:+d}) missed recall")


def test_smoke_high_noise_trap_scope_tokens_match_intended_scope():
    # Token guard: only reasons in FUNCTION_SCOPED_TRAP_REASONS widen a trap
    # to ±15 (substring containment); every other reason silently degrades to
    # ±2. If a whole-symbol trap loses its token in score.py it narrows to ±2,
    # a real false positive lands in net_new instead of traps, and the FP rate
    # is under-reported. Classify every trap with the scorer's own predicate
    # (not a second hardcoded copy), assert that equals the fixture's intended
    # set, then behaviour-probe every trap at ~10 lines off.
    fdir, expected, by_file, _raw = _high_noise_fixture()
    intended_function_prefixes = (
        "size-only",
        "clear-non-duplicative",
        "retry-wrapped",
        "framework-transaction",
    )
    function_scoped_traps = []
    line_scoped_traps = []
    for trap in expected["traps"]:
        reason = trap.get("whyNotFlagged") or ""
        intended_hits = [pfx for pfx in intended_function_prefixes
                         if reason.startswith(pfx)]
        assert len(intended_hits) <= 1, (
            f"trap carries more than one function-scope token: {reason!r}")
        intended_func = bool(intended_hits)
        scorer_func = any(token in reason
                          for token in score.FUNCTION_SCOPED_TRAP_REASONS)
        assert scorer_func == intended_func, (
            f"scorer scope disagrees with fixture intent for {reason!r}: "
            f"scorer={scorer_func} intended={intended_func}")
        if intended_func:
            function_scoped_traps.append(trap)
        else:
            line_scoped_traps.append(trap)
    assert len(function_scoped_traps) == 4
    assert {t["whyNotFlagged"].split(" —", 1)[0] for t in function_scoped_traps} == set(
        intended_function_prefixes)
    assert len(line_scoped_traps) == 10

    for func_trap in function_scoped_traps:
        func_line = score._resolve_line(by_file, func_trap["file"], func_trap["lineHint"])
        finding = {"dimension": "Code",
                   "file": func_trap["file"],
                   "line": func_line + 10}
        assert score._matches_location(
            finding, func_trap["file"], func_line, True), (
            f"function-scoped trap did not match at +10: {func_trap['whyNotFlagged']!r}")
        r = score.score_fixture(fdir, [finding])
        trap_key = "%s:%s" % (func_trap["file"], func_line)
        assert trap_key in r["precision"]["trap_hits"], (
            f"function-scoped trap did not flag at +10: {func_trap['whyNotFlagged']!r}")
        assert r["precision"]["traps_flagged"] == 1

    for line_trap in line_scoped_traps:
        line_trap_line = score._resolve_line(
            by_file, line_trap["file"], line_trap["lineHint"])
        finding = {"dimension": "Code",
                   "file": line_trap["file"],
                   "line": line_trap_line + 10}
        assert not score._matches_location(
            finding, line_trap["file"], line_trap_line, False), (
            f"line-scoped trap matched at +10: {line_trap['whyNotFlagged']!r}")
        r = score.score_fixture(fdir, [finding])
        trap_key = "%s:%s" % (line_trap["file"], line_trap_line)
        assert trap_key not in r["precision"]["trap_hits"], (
            f"line-scoped trap flagged at +10: {line_trap['whyNotFlagged']!r}")


def test_smoke_high_noise_expected_shape():
    # Cheap structural pin: five seeds, fourteen traps, required fields present,
    # and the five lens dimensions exactly as the fixture claims.
    _fdir, expected, _by_file, _raw = _high_noise_fixture()
    assert len(expected["seeds"]) == 5
    assert len(expected["traps"]) == 14
    seed_dims = set()
    for seed in expected["seeds"]:
        assert seed.get("dimension")
        assert seed.get("severity")
        assert seed.get("taxonomy")
        assert seed.get("file")
        assert seed.get("lineHint")
        assert seed.get("why")
        seed_dims.add(seed["dimension"])
    # taxonomy selects function-scoped vs line-scoped matching windows in score.py —
    # frozen ground truth, not an incidental label.
    assert {(s["dimension"], s["taxonomy"]) for s in expected["seeds"]} == {
        ("Security", "BOLA"),
        ("Code", "hardcoded-error-string"),
        ("Architecture", "premature-abstraction"),
        ("Failure-Mode", "partial-failure"),
        ("Test", "claim-test-mismatch"),
    }
    for trap in expected["traps"]:
        assert trap.get("file")
        assert trap.get("lineHint")
        assert trap.get("whyNotFlagged")
    assert seed_dims == {"Architecture", "Code", "Security", "Test", "Failure-Mode"}


def test_smoke_high_noise_hunk_headers_match_their_bodies():
    # Without this, a hunk whose @@ header advertises lengths that disagree
    # with its body still leaves every other high-noise smoke green:
    # score._parse_diff_lines and _raw_diff_occurrences both derive line
    # numbers from the @@ start and ignore declared lengths entirely. The
    # advertised patch then stops applying intact (git apply treats surplus
    # body lines as outside the hunk) while CI stays silent. That regression
    # actually occurred on the documents.test.ts hunk (+1,52 vs 53 body
    # lines) and was repaired; this pin keeps it from returning.
    fdir = _real_fixture("high-noise")
    with open(fdir + "/diff.txt") as f:
        lines = f.read().splitlines()

    hunk_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    files_seen = set()
    cur_file = None
    i = 0
    while i < len(lines):
        raw = lines[i]
        if raw.startswith("+++ "):
            path = raw[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            cur_file = path
            files_seen.add(cur_file)
            i += 1
            continue
        m = hunk_re.match(raw)
        if m is None:
            i += 1
            continue
        old_len = int(m.group(2)) if m.group(2) is not None else 1
        new_len = int(m.group(4)) if m.group(4) is not None else 1
        context = removed = added = 0
        i += 1
        while i < len(lines):
            body = lines[i]
            if (body.startswith("@@") or body.startswith("diff --git")
                    or body.startswith("--- ") or body.startswith("+++ ")):
                break
            if body.startswith("\\"):
                i += 1
                continue
            if body.startswith("+"):
                added += 1
            elif body.startswith("-"):
                removed += 1
            else:
                context += 1
            i += 1
        assert context + removed == old_len, (
            f"{cur_file}: context+removed={context + removed} != oldLen={old_len}")
        assert context + added == new_len, (
            f"{cur_file}: context+added={context + added} != newLen={new_len}")
    assert len(files_seen) == 9
