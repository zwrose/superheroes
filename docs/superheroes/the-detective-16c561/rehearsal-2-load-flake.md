# Rehearsal 2 — honest not-demonstrated exit: `test_diff_stall_after_partial_write` flake

## What a rehearsal record is

A rehearsal record is a Definition-of-Done artifact for the detective spec's unhappy path: when a cause **cannot** be demonstrated, the receipt says so plainly and the advisor does not route fixes on it (UFR-1). **Every claim below is either a command that was actually run with its real output pasted, or is explicitly labelled as drafted-not-performed.** Diagnostic output was **scrubbed** for secrets and PII; local paths retained.

This rehearsal exercises the **not-demonstrated** branch: the flake observation from PR #1041's build record was **not reproduced** in this session; the receipt and vet reflect that honest outcome.

---

## Incident

PR #1041's build record reports `plugins/superheroes/lib/tests/test_sanitized_view.py::test_diff_stall_after_partial_write` **failing in a full-suite run** and **passing on isolated re-run**, twice, under heavy host load — recorded as a **flake observation**, not a regression. The cause has never been demonstrated.

**Examined surface:** the test and its behavior (observe-only; no test or lib edits in this rehearsal).

**Dispatch budget (this session):** five isolated runs of the named test, three parallel file runs (`-n auto`), plus ruled-out hypotheses — budget reached after parallel load attempts showed no intermittent pass/fail pattern.

---

## Diagnosis receipt — `PRODUCED`

### 1. What happened, with receipts

**Recorded flake shape (from PR #1041 build record, not re-run here).** Full CI suite: test **failed**; isolated re-run: test **passed** (twice); under heavy load; classified flake observation.

**Reproduction attempts (this session, 2026-08-16).** Host: darwin, Python 3.9.6, pytest 8.4.2, pytest-xdist 3.8.0. Repo: `/private/tmp/sh931-woF` at `9013a46e42a60c7cca058633dedd69a51f045b98`.

**Isolated runs (5×) — named test only:**

```text
$ /usr/bin/python3 -m pytest plugins/superheroes/lib/tests/test_sanitized_view.py::test_diff_stall_after_partial_write -v --tb=short --durations=0
```

Representative output (all five runs matched this failure shape; excerpt):

```text
plugins/superheroes/lib/tests/test_sanitized_view.py::test_diff_stall_after_partial_write FAILED [100%]

=================================== FAILURES ===================================
_____________________ test_diff_stall_after_partial_write ______________________
plugins/superheroes/lib/tests/test_sanitized_view.py:4157: in test_diff_stall_after_partial_write
    assert proc is not None
E   assert None is not None
============================== slowest durations ===============================
1.23s call     plugins/superheroes/lib/tests/test_sanitized_view.py::test_diff_stall_after_partial_write
0.01s setup    plugins/superheroes/lib/tests/test_sanitized_view.py::test_diff_stall_after_partial_write
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_sanitized_view.py::test_diff_stall_after_partial_write
============================== 1 failed in 1.72s ===============================
```

Summary across isolated runs 1–5: **5 failed, 0 passed**. Failure line **4157**: `assert proc is not None` — the monkeypatched `Popen` wrapper never captured the stalled git-diff subprocess (`stall_proc["proc"]` stayed `None`).

**Parallel load — containing file, `-n auto`, 3 repetitions:**

```text
$ /usr/bin/python3 -m pytest plugins/superheroes/lib/tests/test_sanitized_view.py -n auto -q --durations=5
```

All three runs: same test **FAILED** at line 4157 (`proc is None`). No run showed pass/fail alternation within the attempt.

**Contrast with flake observation.** The PR #1041 record describes **intermittent** failure under full-suite load with **isolated pass**. This session shows **stable failure** in isolation and under xdist — the **flake pattern was not reproduced**.

### 2. Demonstrated root cause

**Not demonstrated.** No reproduction of the recorded flake (fail full-suite / pass isolated). No A/B isolates a cause for the intermittent CI behavior. The consistent local failure (`proc is None`) may reflect environment divergence from CI (Python 3.9.6 macOS local vs Python 3.12 ubuntu CI per repo CI config) but that does not demonstrate why the test **passed** on isolated re-run in the original flake observation.

### 3. Blast radius

If the flake is real on CI ubuntu under suite load: intermittent red on `test_diff_stall_after_partial_write` in full `pytest -n auto` runs; isolated green misleads triage. **Unconfirmed in this session** — only the historical observation applies.

### 4. Recommended follow-ups

1. **Park flake routing** — do not file a fix issue on this diagnosis; cause not demonstrated (UFR-1).
2. **CI-side reproduction** — re-run full suite with `-n auto` on ubuntu-22.04 / Python 3.12 matching `.github/workflows/ci.yml`; capture flake if it recurs with run link (per CLAUDE.md flake policy).
3. **Local env note** — document that this test **consistently fails** on macOS Python 3.9.6 in this worktree (separate from the CI flake; may warrant a separate build if CI is green).

### Ruled-out list (budget exhausted)

| Hypothesis | What we tried | Outcome |
| --- | --- | --- |
| Intermittent flake reproduces locally under isolation | 5 isolated runs of named test | **Ruled out** — 5/5 failed, same assertion; no pass |
| Concurrency / xdist load triggers flake | 3× full file with `-n auto` | **Ruled out** — stable fail; no intermittent pass |
| Stall timeout vs diff-failed detail | Failure before detail assertion — `proc` never set | **Inconclusive** for CI flake; local path differs from stall-timeout story |
| Heavy host CPU load (PR #1041 context) | Not simulated beyond xdist parallel file runs | **Could not test** — no load generator; budget spent on pytest attempts |

**Budget end:** five isolated + three parallel file runs completed; flake pattern not observed; session stops per UFR-3.

---

## Five-check vet verdict — `PRODUCED`

| Check | Grade | Notes |
| --- | --- | --- |
| 1. Cause demonstrated | **Pass (truthfulness)** | Receipt **plainly states cause not demonstrated** — honest negative per UFR-1; not a failed vet. |
| 2. Fix targets cause, not symptom | **Pass** | **No fix routed** on undemonstrated cause; park + CI re-observation only. |
| 3. Blast radius stated | **Pass** | Scoped to unconfirmed CI flake; local stable fail noted separately. |
| 4. Follow-ups carry right anchor | **Pass** | Park, CI repro, local env note — each anchored to this receipt. |
| 5. No smuggled product opinion | **Pass** | No new requirements. |

**Verdict (plain language).** This is the **not-demonstrated** terminal branch (UFR-1): the diagnosis did its job. The flake observation from PR #1041 was **not reproduced**; the receipt is truthful. **Do not route a fix issue** on the undemonstrated flake cause. If the flake recurs on CI, record it with a run link per repo flake policy — that is follow-up observation, not this diagnosis.

**No fix routed.** Incident body update not applicable (no confirmed cause to promote).

---

## Untouched-surface evidence

**Before rehearsal:**

```text
$ git rev-parse HEAD
9013a46e42a60c7cca058633dedd69a51f045b98
$ git status --porcelain | shasum -a 256
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  -
```

**After rehearsal** (before committing these record files):

```text
$ git rev-parse HEAD
9013a46e42a60c7cca058633dedd69a51f045b98
$ git status --porcelain | shasum -a 256
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  -
```

HEAD and porcelain hash **match** before adding these docs — no edits to `plugins/` or test code during observation.

**Disposable copy:** no persistent disposable copy required for this rehearsal (pytest used pytest `tmp_path` internally only).

---

## Finding for orchestrator

Rehearsal 2's **flake cause did not reproduce**. Local runs show a **stable failure** (`proc is None` at line 4157), which is a **different signal** from the PR #1041 flake record (isolated pass). That stable failure was **not** the subject of this rehearsal's demonstrated-cause path — it is noted as environment divergence for separate triage if CI stays green.
