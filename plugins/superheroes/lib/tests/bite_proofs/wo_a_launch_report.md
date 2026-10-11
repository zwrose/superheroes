# Launch report WO-A bite-proof: the "Still on your machine" state's clearing leg

Bite-proof record for `plugins/superheroes/lib/launch_report.py` (G12), detector in `plugins/superheroes/lib/tests/test_launch_report.py` (`TLR`). Split out of `wo_a_place_call.md`, where G12 was recorded against `launch_place.py` and `test_launch_place.py` (`TL`) before the launch report and the still line moved into their own module.

**Status.** The red, restore and green below are carried over verbatim from `wo_a_place_call.md`; they were run before the split, so the paths they print (`launch_place.py`, `test_launch_place.py`, and the line numbers) are the pre-split ones. The neutralization and node lines name the module and test file that now hold the element. The proof is re-run on the split head by the orchestrator.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<T>::<node>" -q -p no:cacheprovider`.
- **Pinned condition.** `TLR` builds its stores, repositories, account files and records under `tmp_path`; the clock is a fixed `today` (`2026-10-11`) and readiness is injected. The pin makes unobservable: the real home directory, the process environment, the network and the real wall clock.

## Declared guarded-element set

G12 the still state's reported-fact clearing leg is a strictly later day.

## Per-element receipts

### G12: the still state's reported-fact leg clears only on a strictly later day. Axis: boundary (>)

- **Neutralization applied.** In `launch_report._fixed`, `fromisoformat(checked) > fromisoformat(state["observedOn"])` replaced with `>=`.
- **Node.** `TLR::test_R_still_leg_d_a_reported_fact_clears_only_on_a_strictly_later_check`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_R_still_leg_d_a_reported_fact_clears_only_on_a_strictly_later_check ___

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1138/test_R_still_leg_d_a_reported_0')

    def test_R_still_leg_d_a_reported_fact_clears_only_on_a_strictly_later_check(tmp_path):
        cases = [("no-pass", {"noPass": True}), ("unreachable", {"unreachable": True}),
                 ("version", {"pluginVersion": "0.41.0"})]
        for index, (code, reported) in enumerate(cases):
            repo, store = _still_with(_sub(tmp_path, str(index)), _call(reason=code, cloud="0.41.0", advisor="0.42.0",
                                                  reported=reported))
            ready = _now(ready=True)
            for checked in (None, "2026-10-10", "2026-10-11", "garbage"):
>               assert LP.still_line(repo, root=store, today=TODAY, readiness_fn=lambda *a, **k: dict(
                    ready, checkedAt=checked)) is not None, (code, checked)
E               AssertionError: ('no-pass', '2026-10-11')
E               assert None is not None
E                +  where None = <function still_line at 0x10c69a840>('/private/tmp/claude-501/pytest-of-zwrose/pytest-1138/test_R_still_leg_d_a_reported_0/0/repo', root='/private/tmp/claude-501/pytest-of-zwrose/pytest-1138/test_R_still_leg_d_a_reported_0/0/store', today=datetime.date(2026, 10, 11), readiness_fn=<function test_R_still_leg_d_a_reported_fact_clears_only_on_a_strictly_later_check.<locals>.<lambda> at 0x10c6e60c0>)
E                +    where <function still_line at 0x10c69a840> = LP.still_line

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launch_place.py:1108: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_place.py::test_R_still_leg_d_a_reported_fact_clears_only_on_a_strictly_later_check
1 failed in 0.62s
```

- **Restore.** The inverse Edit; quoted from `launch_place.py:460`: `        return datetime.date.fromisoformat(checked) > datetime.date.fromisoformat(state["observedOn"])`.
- **Green.**

```
.                                                                        [100%]
1 passed in 1.92s
```
