"""The test role's attempt and retry ceilings scale with its slice (#2415).

One rule, `round_phases.seat_ceiling(seat_key, lines)`, gives every external review seat of a `dispatch-panel` step its
attempt and retry ceilings; `round_driver._panel_ceilings` carries them in the panel payload; review-code's dispatch recipe
(`skills/review-code/reference/auto-fix-loop.md`) passes them as `--timeout` / `--retry-timeout`. The journaled bound of the
attempt after a silence-watchdog cut is pinned in `test_engine_dispatch_e2e.py`.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/i2415_test_role_ceiling.md
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engine_dispatch as ED  # noqa: E402
import round_driver as RD  # noqa: E402
import round_phases as RP  # noqa: E402

_PLUGIN_ROOT = os.path.dirname(_LIB)
_RECIPE = os.path.join(_PLUGIN_ROOT, "skills", "review-code", "reference", "auto-fix-loop.md")

_SMALL_DIFF = ("diff --git a/a.py b/a.py\nindex 1..2 100644\n--- a/a.py\n+++ b/a.py\n"
               "@@ -1 +1,2 @@\n-old\n+new\n+more\n")
CFG = {"leg": "code", "vendors": ["claude", "codex"], "diff": _SMALL_DIFF, "fixerVendor": "claude"}


def _new_file_diff(n):
    body = "".join("+line %d\n" % i for i in range(n))
    return ("diff --git a/big.py b/big.py\nnew file mode 100644\nindex 0000000..1111111\n--- /dev/null\n"
            "+++ b/big.py\n@@ -0,0 +1,%d @@\n" % n + body)


def _panel_payload(diff):
    state = RD.new_state(dict(CFG, diff=diff))
    state["reviewedDiff"] = diff
    return state, RD._advance(state, state["config"])["payload"]


# --- the rule ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("seat_key,lines,expected", [
    ("test-role", 0, 900),
    ("test-role", 300, 900),
    ("test-role", 301, 902),
    ("test-role", 820, 1680),
    ("test-role", 900, 1800),
    ("test-role", 1000, 1800),
    ("test-role", None, 900),
    ("code-reviewer", 1000, 900),
    ("test-role:s1", 820, 1680),
    # E3: a negative count is not a size
    ("test-role", -5, 900),
    # a bool is not a count
    ("test-role", True, 900),
    ("test-role", "900", 900),
    ("test-role", 1000.0, 900),
])
def test_seat_ceiling_values(seat_key, lines, expected):
    # axis: the rule's worked values (not a declared guarded element of the bite-proof record)
    value = RP.seat_ceiling(seat_key, lines)
    assert value == expected
    assert type(value) is int


def test_the_floor_equals_the_retry_minimum():
    # axis: the ceiling floor cannot drift below the retry minimum the dispatcher enforces
    assert RP.SEAT_CEILING_FLOOR_SECONDS == ED.RETRY_MIN_TIMEOUT == 900


def test_an_every_other_lens_keeps_the_floor_at_any_size():
    # axis: only the test role scales; no other lens's ceiling grows with the change's size
    for lens in RP.DIMENSIONS:
        if lens != "test-role":
            assert RP.seat_ceiling(lens, 5000) == 900


def test_the_dispatch_review_flags_accept_a_computed_ceiling(tmp_path):
    # axis: the dispatch-review parser takes a computed ceiling above the floor as an int for both flags
    value = RP.seat_ceiling("test-role", 301)
    (tmp_path / ".git").mkdir()  # the `--repo-root` type only checks that a `.git` entry exists; nothing is dispatched
    args = ED.build_parser().parse_args([
        "dispatch-review", "--seat", json.dumps({"vendor": "codex", "model": "m", "effort": None, "role": "reviewer"}),
        "--prompt-path", str(tmp_path / "prompt.md"), "--repo-root", str(tmp_path),
        "--timeout", str(value), "--retry-timeout", str(value)])
    assert args.timeout == value == 902
    assert args.retry_timeout == value
    assert type(args.timeout) is int and type(args.retry_timeout) is int


# --- the payload ------------------------------------------------------------------------------------------------------


def test_a_sliced_plan_gives_each_seat_its_ceiling_row():
    # axis: G1 — the panel payload carries each seat's ceiling from its slice's weight
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2415_test_role_ceiling.md
    state, payload = _panel_payload(_new_file_diff(3000))
    weights = {s["id"]: s["weight"] for s in state["slicePlan"]["slices"]}
    assert weights and max(weights.values()) > 300
    assert set(payload["ceilings"]) == set(payload["dimensions"])
    saw_test_slice = False
    for key in payload["dimensions"]:
        row = payload["ceilings"][key]
        if key.startswith("test-role:"):
            saw_test_slice = True
            weight = weights[key.partition(":")[2]]
            assert row["lines"] == weight
            assert row["timeout"] == row["retryTimeout"] == RP.seat_ceiling(key, weight)
            if weight > 300:
                assert row["timeout"] > 900
        else:
            assert (row["timeout"], row["retryTimeout"]) == (900, 900)
    assert saw_test_slice


def test_an_unsliced_small_change_keeps_the_floor():
    # axis: a small unsliced change is not given a raised ceiling
    state, payload = _panel_payload(_new_file_diff(50))
    assert state["slicePlan"]["sliced"] is False
    row = payload["ceilings"]["test-role"]
    assert row == {"lines": state["slicePlan"]["countable"], "timeout": 900, "retryTimeout": 900}


def test_an_unsliced_change_of_about_800_lines_raises_the_test_role_ceiling():
    # axis: G1 — the #2403 session-1 shape (one unsliced change of about 800 countable lines)
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2415_test_role_ceiling.md
    state, payload = _panel_payload(_new_file_diff(800))
    plan = state["slicePlan"]
    assert plan["sliced"] is False and plan["countable"] > 600
    row = payload["ceilings"]["test-role"]
    assert row["lines"] == plan["countable"]
    assert row["timeout"] == row["retryTimeout"] == RP.seat_ceiling("test-role", plan["countable"]) > 900
    for key, other in payload["ceilings"].items():
        if key != "test-role":
            assert (other["timeout"], other["retryTimeout"]) == (900, 900)


def test_no_slice_plan_reads_every_row_as_the_floor():
    # axis: an absent slice plan reads every seat as unknown size, at the floor
    state = RD.new_state(dict(CFG, diff=_new_file_diff(800)))
    state.pop("slicePlan", None)
    payload = RD._advance(state, state["config"])["payload"]
    assert set(payload["ceilings"]) == set(payload["dimensions"])
    for row in payload["ceilings"].values():
        assert row == {"lines": None, "timeout": 900, "retryTimeout": 900}


def _plan_state(plan):
    return {"slicePlan": plan}


def test_a_non_int_or_bool_weight_reads_as_unknown():
    # axis: a slice weight that is not a plain int (bool, str, float, absent) is not a size
    # E1
    plan = {"sliced": True, "countable": 2000, "slices": [
        {"id": "s1", "weight": True}, {"id": "s2", "weight": "900"}, {"id": "s3", "weight": 1000},
        {"id": "s4", "weight": 1000.0}, {"id": "s5"}]}
    roster = ["test-role:s1", "test-role:s2", "test-role:s3", "test-role:s4", "test-role:s5"]
    rows = RD._panel_ceilings(_plan_state(plan), roster)
    for key in ("test-role:s1", "test-role:s2", "test-role:s4", "test-role:s5"):
        assert rows[key] == {"lines": None, "timeout": 900, "retryTimeout": 900}
    assert rows["test-role:s3"] == {"lines": 1000, "timeout": 1800, "retryTimeout": 1800}


def test_a_slice_seat_whose_id_is_not_in_the_plan_reads_as_unknown():
    # axis: a slice seat the plan does not name reads as unknown size, while a whole-change seat reads the plan total
    # E2
    plan = {"sliced": True, "countable": 2000, "slices": [{"id": "s1", "weight": 1000}]}
    rows = RD._panel_ceilings(_plan_state(plan), ["test-role:s9", "test-role"])
    assert rows["test-role:s9"] == {"lines": None, "timeout": 900, "retryTimeout": 900}
    # a whole-change seat reads the plan's countable, not a slice row
    assert rows["test-role"] == {"lines": 2000, "timeout": 1800, "retryTimeout": 1800}


def test_a_wave_marked_slice_row_still_gives_its_weight():
    # axis: a wave-marked slice row is found by id and gives its weight like any other slice
    plan = {"sliced": True, "countable": 3000, "slices": [
        {"id": "s1", "weight": 1000}, {"id": "u2s1", "weight": 820, "wave": 2}]}
    rows = RD._panel_ceilings(_plan_state(plan), ["test-role:u2s1"])
    assert rows["test-role:u2s1"] == {"lines": 820, "timeout": 1680, "retryTimeout": 1680}


@pytest.mark.parametrize("state", [
    {}, {"slicePlan": None}, {"slicePlan": "plan"}, {"slicePlan": []},
    {"slicePlan": {"slices": "x", "countable": "9"}}, {"slicePlan": {"slices": [None, 3, {"id": 7}], "countable": True}},
])
def test_a_malformed_plan_never_raises_and_reads_as_the_floor(state):
    # axis: a malformed slice plan fails closed to the floor and never raises
    rows = RD._panel_ceilings(state, ["test-role", "test-role:s1", "code-reviewer"])
    assert set(rows) == {"test-role", "test-role:s1", "code-reviewer"}
    for row in rows.values():
        assert row == {"lines": None, "timeout": 900, "retryTimeout": 900}


# --- the recipe -------------------------------------------------------------------------------------------------------


def _recipe_block():
    with open(_RECIPE, encoding="utf-8") as fh:
        text = fh.read()
    start = text.index('> ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"')
    end = text.index("\n> ```", start)
    return [line[2:] if line.startswith("> ") else line.lstrip(">") for line in text[start:end].splitlines()]


def test_the_recipe_passes_the_resolved_ceilings_at_both_invocations():
    # axis: the recipe passes the resolved ceilings at both dispatch-review invocations, never a hard-coded 900
    with open(_RECIPE, encoding="utf-8") as fh:
        text = fh.read()
    assert "--timeout 900 --retry-timeout 900" not in text
    block = "\n".join(_recipe_block())
    flags = '--timeout "$SEAT_TIMEOUT" --retry-timeout "$SEAT_RETRY_TIMEOUT"'
    assert block.count('engine_dispatch.py" dispatch-review') == 2
    assert block.count(flags) == 2
    assert ".ceilings[" in block
    assert '".seats[\\"$SEAT_LENS\\"] // empty"' in block
    assert 'SEAT_LENS="${SEAT_KEY%%:*}"' in block
    # the scoped-finder test stays on the roster seat key
    assert '[ "$SEAT_KEY" = "scoped-finder" ]' in block


def _ceiling_snippet():
    lines = _recipe_block()
    start = lines.index("SEAT_TIMEOUT=900; SEAT_RETRY_TIMEOUT=900")
    end = lines.index("fi", start)
    return "\n".join(lines[start:end + 1])


def _run_ceiling(phase, payload, key="test-role:s1"):
    script = _ceiling_snippet() + '\necho "$SEAT_TIMEOUT $SEAT_RETRY_TIMEOUT"\n'
    env = dict(os.environ, SEAT_KEY=key, SEAT_PHASE=phase, PAYLOAD=json.dumps(payload))
    return subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=30)


@pytest.mark.skipif(shutil.which("jq") is None or shutil.which("bash") is None, reason="needs bash and jq")
class TestRecipeCeilingResolution:
    def test_a_panel_row_is_passed_through(self):
        # axis: a panel row's integer ceilings reach the recipe's timeout variables unchanged
        done = _run_ceiling("dispatch-panel", {"ceilings": {"test-role:s1": {"lines": 820, "timeout": 1680, "retryTimeout": 1680}}})
        assert (done.returncode, done.stdout.strip()) == (0, "1680 1680")

    def test_e4_a_panel_with_ceilings_but_no_row_for_the_seat_fails_closed(self):
        # axis: a panel that carries ceilings but no row for the seat stops the recipe rather than guessing a ceiling
        done = _run_ceiling("dispatch-panel", {"ceilings": {"code-reviewer": {"lines": 1, "timeout": 900, "retryTimeout": 900}}})
        assert done.returncode == 1
        assert "fail closed" in done.stderr and "test-role:s1" in done.stderr

    @pytest.mark.parametrize("row", [
        {"lines": 5, "timeout": "1800", "retryTimeout": 1800},
        {"lines": 5, "timeout": 1800, "retryTimeout": None},
        {"lines": 5, "timeout": 1800.5, "retryTimeout": 1800},
        {"lines": 5, "timeout": 1800},
    ])
    def test_e4_a_row_without_integer_ceilings_fails_closed(self, row):
        # axis: a row whose timeout or retryTimeout is not an integer stops the recipe
        done = _run_ceiling("dispatch-panel", {"ceilings": {"test-role:s1": row}})
        assert done.returncode == 1
        assert "fail closed" in done.stderr

    def test_e5_a_panel_payload_with_no_ceilings_key_keeps_the_floor(self):
        # axis: compatibility, a panel payload persisted by an earlier plugin version (no ceilings key) keeps 900/900
        done = _run_ceiling("dispatch-panel", {"dimensions": ["test-role:s1"], "tier": "deep", "slices": []})
        assert (done.returncode, done.stdout.strip()) == (0, "900 900")

    def test_e6_any_other_phase_keeps_the_floor(self):
        # axis: only a dispatch-panel step reads ceilings; every other phase keeps 900/900
        payload = {"ceilings": {"test-role:s1": {"lines": 820, "timeout": 1680, "retryTimeout": 1680}}}
        for phase in ("dispatch-audits", "dispatch-verifiers", "dispatch-synthesis", "dispatch-seams-check", ""):
            done = _run_ceiling(phase, payload)
            assert (done.returncode, done.stdout.strip()) == (0, "900 900"), phase
