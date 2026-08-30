# WO-cont-B (#1247) bite-proof — investigation evidence required for engagement

**Provenance: implementer-authored.** Both neutralizations target `_engaged_from_dispatch` in
`plugins/superheroes/lib/seat_canary.py`. Detectors (tests) were left unedited; only the production
chokepoint was temporarily neutralized and restored by inverse edit.

Command for every run:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_seat_canary.py -q -n auto
```

Targeted red runs used `-k` with the exact test names below (no `-n auto` on single-test runs).

## Guarded elements

| ID | Guarded element | Axis |
|---|---|---|
| BP-cont-B1 | `test_tool_calls_without_investigated_not_engaged` | a tool-call count with zero investigated paths does not earn engagement |
| BP-cont-B2 | `test_engaged_from_dispatch_investigation_evidence_table` fail-closed shape rows | a malformed or content-empty `investigated` value does not earn engagement |

---

## BP-cont-B1 — tool-call count without investigated paths

- **axis:** a tool-call count with zero investigated paths does not earn engagement

**neutralization** (restore the pre-build `toolCalls >= 1` fallback through the production path):
```python
    investigated = res.get("investigated") or []
    if investigated:
        return True
    eng = _safe_engagement(res.get("engagement"))
    tool_calls = eng.get("toolCalls")
    return tool_calls is not None and tool_calls >= 1
```
(replacing the strict list/tuple + non-empty-string entry loop and final `return False`.)

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_tool_calls_without_investigated_not_engaged _______________

    def test_tool_calls_without_investigated_not_engaged():
        def dispatch_one(engine, **kwargs):
            return _base_dispatch_result(
                engagement={"tokens": None, "toolCalls": 1, "stdoutBytes": 0, "wallSeconds": 0.0},
            )

>       assert SC.run_canary(
            "cursor", engine_model="c", effort="high", repo_root="/r", dispatch=dispatch_one,
        )["engaged"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_seat_canary.py:277: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_canary.py::test_tool_calls_without_investigated_not_engaged
1 failed, 43 deselected in 0.39s
```

**restore:** reinstate the strict investigated entry loop:
```python
    investigated = res.get("investigated")
    if not isinstance(investigated, (list, tuple)):
        return False
    for entry in investigated:
        if isinstance(entry, str) and entry.strip():
            return True
    return False
```

**restore receipt:** `git status --porcelain` over the neutralized path returned ` M plugins/superheroes/lib/seat_canary.py` (production edits retained; neutralization undone by inverse edit).

**raw green:** `43 passed, 1 failed in 1.76s` — the sole failure is
`test_vacuous_with_tool_calls_still_engaged_path_alive`, which asserts the old tool-call-only
engagement path the build intentionally removes (reported to orchestrator; outside this order's
named test inversions).

---

## BP-cont-B2 — fail-closed investigated shapes

- **axis:** a malformed or content-empty `investigated` value does not earn engagement

**neutralization** (bare truthiness on `investigated` instead of list/tuple + non-empty string entries):
```python
    investigated = res.get("investigated")
    if investigated:
        return True
    return False
```
(replacing the strict list/tuple + non-empty-string entry loop.)

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_engaged_from_dispatch_investigation_evidence_table ____________

    def test_engaged_from_dispatch_investigation_evidence_table():
        ...
        for label, overrides, expected in cases:
            res = dict(engaged_base)
            res.update(overrides)
            assert EA.engagement_read(res) == "engaged", label
>           assert SC._engaged_from_dispatch(res) is expected, label
E           AssertionError: investigated bare string
E           assert True is False
E            +  where True = <function _engaged_from_dispatch at 0x1061264c0>({'engagement': {'toolCalls': 1}, 'findings': [], 'investigated': 'lib/a.py'})
E            +    where <function _engaged_from_dispatch at 0x1061264c0> = SC._engaged_from_dispatch

plugins/superheroes/lib/tests/test_seat_canary.py:583: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_canary.py::test_engaged_from_dispatch_investigation_evidence_table
1 failed, 43 deselected in 0.26s
```

The same neutralization also makes the `investigated whitespace-only strings` row (`["", "  "]`)
truthy; the table stops at the first failing row.

**restore:** reinstate the strict investigated entry loop (same lines as BP-cont-B1 restore above).

**restore receipt:** `git status --porcelain` over the neutralized path returned ` M plugins/superheroes/lib/seat_canary.py`.

**raw green:** same as BP-cont-B1 green half (`43 passed, 1 failed` on the vacuous contradiction).

---

## Residue

After the final restore, `git status --porcelain` over the whole worktree:
```
 M plugins/superheroes/lib/seat_canary.py
 M plugins/superheroes/lib/tests/test_seat_canary.py
?? plugins/superheroes/lib/tests/bite_proofs/wo_cont_b_1247.md
```
(intended WO-cont-B edits only; no neutralization residue in production code.)

---

## BP-cont-B1 extension — `test_vacuous_with_tool_calls_only_not_engaged`

Element 1's neutralization (restoring the `toolCalls >= 1` fallback in `_engaged_from_dispatch`)
now also reddens the tool-call-only vacuous probe added in WO-cont-B2.

**neutralization:** same as BP-cont-B1 above (toolCalls fallback through the production path).

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_vacuous_with_tool_calls_only_not_engaged _________________

    def test_vacuous_with_tool_calls_only_not_engaged():
        def dispatch(engine, **kwargs):
            return {
                "ok": False,
                "reason": "vacuous",
                "attempts": 2,
                "forfeited": True,
                "findings": [],
                "engagement": {
                    "tokens": 50000,
                    "toolCalls": 30,
                    "stdoutBytes": 999,
                    "wallSeconds": 600.0,
                },
                "disclosure": "vacuous seat",
            }

        out = SC.run_canary(
            "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch,
        )
>       assert out["engaged"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_seat_canary.py:273: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_canary.py::test_vacuous_with_tool_calls_only_not_engaged
1 failed, 44 deselected in 0.22s
```

**restore:** reinstate the strict investigated entry loop (same lines as BP-cont-B1 restore above).

**restore receipt:** `git status --porcelain` over the neutralized path returned ` M plugins/superheroes/lib/seat_canary.py`.

**raw green:**
```
bringing up nodes...
bringing up nodes...

.............................................                            [100%]
45 passed in 1.34s
```


---

## Orchestrator re-verification (final head `eb1e998d`)

Verification authority never delegates: the orchestrator re-ran both declared elements itself on the
final integrated head, with the detectors unedited.

**A false-green worth recording (bite-proof trap 4).** The orchestrator's first attempt at element
1's neutralization re-added the `toolCalls >= 1` fallback *below* the new
`isinstance(investigated, (list, tuple))` type guard. Every fixture in this file omits
`investigated` entirely, so the type guard short-circuited and the fallback was unreachable — all
three tests stayed **green** where the reasoning said red. The cure was fixing the neutralization
(restore the pre-change body exactly: `res.get("investigated") or []`, no type guard), never
relaxing an assertion. A neutralization that does not reach the guarded branch proves nothing.

### Element 1 — tool-call count without investigated paths

- **neutralization**: `_engaged_from_dispatch` body restored to the pre-change form —
  `investigated = res.get("investigated") or []; if investigated: return True;` then the
  `toolCalls is not None and tool_calls >= 1` fallback.
- **raw red** (three node-ids, exact names, no `-k`):

```
FAILED plugins/superheroes/lib/tests/test_seat_canary.py::test_tool_calls_without_investigated_not_engaged
FAILED plugins/superheroes/lib/tests/test_seat_canary.py::test_vacuous_with_tool_calls_only_not_engaged
FAILED plugins/superheroes/lib/tests/test_seat_canary.py::test_engaged_from_dispatch_investigation_evidence_table
3 failed in 0.37s
```

- **restore**: inverse edit back to the shipped body.
- **restore receipt**: `git status --porcelain plugins/superheroes/lib/seat_canary.py` → empty.

### Element 2 — fail-closed `investigated` shapes

- **neutralization** (distinct from element 1): the body replaced by
  `investigated = res.get("investigated"); return bool(investigated)`.
- **raw red**:

```
E           AssertionError: investigated bare string
E           assert True is False
E            +  where True = <function _engaged_from_dispatch at 0x10818c700>({'engagement': {'toolCalls': 1}, 'findings': [], 'investigated': 'lib/a.py'})
plugins/superheroes/lib/tests/test_seat_canary.py:609: AssertionError
FAILED plugins/superheroes/lib/tests/test_seat_canary.py::test_engaged_from_dispatch_investigation_evidence_table
1 failed in 0.36s
```

  The red is on the declared axis: a bare string `investigated` is truthy, so a content-empty /
  malformed value earns engagement under the neutralization and does not under the shipped code.
- **restore**: inverse edit back to the shipped body.
- **restore receipt**: `git status --porcelain plugins/superheroes/lib/seat_canary.py` → empty.
- **raw green** (whole file, post-restore): `45 passed in 0.92s`.

### Final-head re-run (head `1fd7f8fc`, post-review)

Both elements re-run again after the review's two fix rounds, detectors unedited.

- **Element 1** (restore the `toolCalls >= 1` fallback in `_engaged_from_dispatch`) — raw red:

```
FAILED plugins/superheroes/lib/tests/test_seat_canary.py::test_tool_calls_without_investigated_not_engaged
FAILED plugins/superheroes/lib/tests/test_seat_canary.py::test_vacuous_with_tool_calls_only_not_engaged
FAILED plugins/superheroes/lib/tests/test_seat_canary.py::test_engaged_from_dispatch_investigation_evidence_table
3 failed in 0.16s
```

- **Element 2** (`return bool(investigated)`) — raw red:

```
plugins/superheroes/lib/tests/test_seat_canary.py:609: AssertionError
FAILED plugins/superheroes/lib/tests/test_seat_canary.py::test_engaged_from_dispatch_investigation_evidence_table
1 failed in 0.13s
```

**restore receipt:** whole-worktree `git status --porcelain` → empty. **raw green:** `60 passed in 1.33s`
(census + seat_canary files together).
