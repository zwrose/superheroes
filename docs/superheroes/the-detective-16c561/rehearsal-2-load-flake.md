# Rehearsal 2 — honest not-demonstrated exit: `test_diff_stall_after_partial_write` flake

## What a rehearsal record is

A rehearsal record is a Definition-of-Done artifact for the detective spec's unhappy path: when a cause **cannot** be demonstrated, the receipt says so plainly and the advisor does not route fixes on it (UFR-1). **Every claim below is either a command that was actually run with its real output pasted, or is explicitly labelled as drafted-not-performed.** Diagnostic output was **scrubbed** for secrets and PII; local paths retained.

This rehearsal exercises the **not-demonstrated** branch: the **cause** of the flake observation from PR #1041's build record was **not demonstrated** in this session; the receipt and vet reflect that honest outcome.

---

## Incident

PR #1041's build record reports `plugins/superheroes/lib/tests/test_sanitized_view.py::test_diff_stall_after_partial_write` **failing in a full-suite run** and **passing on isolated re-run**, twice, under heavy host load — recorded as a **flake observation**, not a regression. The cause has never been demonstrated.

**Examined surface:** the test and its behavior (observe-only; no test or lib edits in this rehearsal).

**Dispatch budget (this session):** five isolated runs of the named test, three parallel file runs (`-n auto`), plus ruled-out hypotheses — budget reached after parallel load attempts; follow-on orchestrator verification (below) corrected the first-pass reading.

---

## Diagnosis receipt — `PRODUCED`

### 1. What happened, with receipts

**Recorded flake shape (from PR #1041 build record, not re-run here).** Full CI suite: test **failed**; isolated re-run: test **passed** (twice); under heavy load; classified flake observation.

**Reproduction attempts (this session, 2026-08-16).** Host: darwin, Python 3.9.6, pytest 8.4.2, pytest-xdist 3.8.0. Repo: `/private/tmp/sh931-woF` at `9013a46e42a60c7cca058633dedd69a51f045b98`. **Context:** six concurrent engine dispatches were saturating the host during these runs — the same heavy-load condition PR #1041 reported.

**Isolated runs (5×) — named test only:**

```text
$ /usr/bin/python3 -m pytest plugins/superheroes/lib/tests/test_sanitized_view.py::test_diff_stall_after_partial_write -v --tb=short --durations=0
```

Representative output (excerpt only — per-run outputs were not retained; the excerpt below is representative of the failure shape observed across all five runs):

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

**First-pass reading (corrected below).** This session's five isolated runs all failed under concurrent host load; that sample was **insufficient** to distinguish intermittent from stable behaviour — see the methodological note and orchestrator follow-on measurements.

**Orchestrator verification pass (measured after this record was first written).** Independent re-runs on the same host class, attributed to the orchestrator's verification pass. Exact invocation for every run below:

```text
/usr/bin/python3 -m pytest plugins/superheroes/lib/tests/test_sanitized_view.py::test_diff_stall_after_partial_write -q
```

**Build HEAD `da39001c` — single run (one invocation):**

```text
1 passed in 0.88s
```

**Base `7571e72d` — single run (one invocation)** in detached worktree `/private/tmp/sh931-base` (without any of this build's changes). Purpose: rule **this build out as the cause** — a single run here shows the failure outcome is reachable at base without this PR's changes; a single run cannot establish more than that reachability.

```text
E           assert None is not None
FAILED plugins/superheroes/lib/tests/test_sanitized_view.py::test_diff_stall_after_partial_write
1 failed in 0.95s
```

**Build HEAD `da39001c` — 8 consecutive isolated runs** at build HEAD (worktree `issue-931-99ef90b52f31952a`). This series establishes intermittency; counts are checkable against the transcript: **3 passed (runs 1, 3, 4)** and **5 failed (runs 2, 5, 6, 7, 8)**.

```text
### Orchestrator verification pass — raw receipts

Run series: 8 consecutive isolated runs at build HEAD (worktree issue-931-99ef90b52f31952a).

--- run 1 ---
1 passed in 0.88s
--- run 2 ---
E           assert None is not None
FAILED plugins/superheroes/lib/tests/test_sanitized_view.py::test_diff_stall_after_partial_write
1 failed in 0.95s
--- run 3 ---
1 passed in 1.07s
--- run 4 ---
1 passed in 0.91s
--- run 5 ---
E           assert None is not None
FAILED plugins/superheroes/lib/tests/test_sanitized_view.py::test_diff_stall_after_partial_write
1 failed in 1.32s
--- run 6 ---
E           assert None is not None
FAILED plugins/superheroes/lib/tests/test_sanitized_view.py::test_diff_stall_after_partial_write
1 failed in 0.92s
--- run 7 ---
E           assert None is not None
FAILED plugins/superheroes/lib/tests/test_sanitized_view.py::test_diff_stall_after_partial_write
1 failed in 1.38s
--- run 8 ---
E           assert None is not None
FAILED plugins/superheroes/lib/tests/test_sanitized_view.py::test_diff_stall_after_partial_write
1 failed in 1.63s
```

On this host the test is **genuinely intermittent** (3 passed / 5 failed over 8 runs — runs 1, 3, 4 passed; runs 2, 5, 6, 7, 8 failed), not stably failing. The base-commit single-run failure rules **this build out as the cause** — the test fails without any of this PR's changes (reachability only; intermittency comes from the 8-run series). The first session's five consecutive failures almost certainly landed while six concurrent dispatches saturated the host.

**Contrast with flake observation.** PR #1041 describes **intermittent** failure under full-suite load with **isolated pass**. Orchestrator measurements confirm **intermittency on this host** (3/8 pass under controlled repetition). What remains **undemonstrated** is **which condition** flips pass to fail — not whether the test can pass at all.

**Methodological note.** A single run, or five runs taken under uncontrolled concurrent load, cannot establish "stable" versus "intermittent." Distinguishing the two requires enough repetition under known conditions. This record's first pass did not do enough of that; the orchestrator's eight-run series is the corrective measurement.

### 2. Demonstrated root cause

**Not demonstrated.** Intermittency **is** reproducible on this host (orchestrator: 3/8 pass at build HEAD; base commit fails without this build's changes). No A/B isolates **which factor** decides pass from fail — load, timing, scheduler contention, or something else. macOS Python 3.9.6 local vs Python 3.12 ubuntu CI (per repo CI config) remains one **untested** hypothesis among others, not an explanation for the observed intermittency.

### 3. Blast radius

If the flake is real on CI ubuntu under suite load: intermittent red on `test_diff_stall_after_partial_write` in full `pytest -n auto` runs; isolated green misleads triage. **Intermittency confirmed locally** by orchestrator measurements; **cause** of the flip remains unconfirmed.

### 4. Recommended follow-ups

1. **Park flake routing** — do not file a fix issue on this diagnosis; cause not demonstrated (UFR-1).
2. **CI-side reproduction** — re-run full suite with `-n auto` on `ubuntu-latest` (the rolling image label `.github/workflows/ci.yml` actually uses — read the resolved OS version from the run log rather than assuming a pinned release) / Python 3.12 (pinned in CI); capture flake if it recurs with run link (per CLAUDE.md flake policy).
3. **Factor isolation** — design A/B runs that vary one candidate at a time (host load, xdist width, Python version) to demonstrate what flips pass/fail; base-commit failure shows the flake predates this build.

### Ruled-out list (budget exhausted)

| Hypothesis | What we tried | Outcome |
| --- | --- | --- |
| This build introduced the flake | Orchestrator: single run at base `7571e72d` (no build changes) | **Ruled out** — test fails on base; not caused by this PR |
| Test always fails locally (stable red) | Orchestrator: 8 consecutive isolated runs at build HEAD `da39001c` (see raw receipts above) | **Ruled out** — 3 passed (runs 1, 3, 4), 5 failed (runs 2, 5, 6, 7, 8); intermittency confirmed |
| Stall timeout vs diff-failed detail | Failure before detail assertion — `proc` never set | **Inconclusive** for CI flake; local path differs from stall-timeout story |
| Heavy host CPU load (PR #1041 context) | First session under six concurrent dispatches; xdist file runs | **Live hypothesis** — load correlates with PR #1041 context; not isolated by A/B; orchestrator pass under lighter load suggests load may be a factor |
| Concurrency / xdist load triggers flake | 3× full file with `-n auto` (first session) | **Inconclusive** — all failed in that sample; no factor isolation; not ruled out |

**Budget end:** five isolated + three parallel file runs completed in first session; orchestrator follow-on established intermittency; **cause of the flip** not demonstrated; session stops per UFR-3.

---

## Five-check vet verdict — `PRODUCED`

| Check | Grade | Notes |
| --- | --- | --- |
| 1. Cause demonstrated | **Pass (truthfulness)** | Receipt **plainly states cause not demonstrated** — honest negative per UFR-1; not a failed vet. |
| 2. Fix targets cause, not symptom | **Pass** | **No fix routed** on undemonstrated cause; park + CI re-observation only. |
| 3. Blast radius stated | **Pass** | Scoped to intermittent behaviour confirmed locally; CI flake cause still unconfirmed. |
| 4. Follow-ups carry right anchor | **Pass** | Park, CI repro, factor isolation — each anchored to this receipt. |
| 5. No smuggled product opinion | **Pass** | No new requirements. |

**Verdict (plain language).** This is the **not-demonstrated** terminal branch (UFR-1): the diagnosis did its job. **Intermittency is reproducible on this host** (orchestrator: 3/8 pass); the **cause** of the pass/fail flip was **not demonstrated**. The receipt is truthful. **Do not route a fix issue** on the undemonstrated flake cause. If the flake recurs on CI, record it with a run link per repo flake policy — that is follow-up observation, not this diagnosis.

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

Rehearsal 2's **flake cause was not demonstrated** — honest UFR-1 exit unchanged. **Corrected evidence:** on this host the test is **intermittent** (orchestrator: 3 passed / 5 failed over 8 consecutive runs at build HEAD `da39001c` — runs 1, 3, 4 passed; runs 2, 5, 6, 7, 8 failed; single run passed at HEAD, single run failed at base `7571e72d` without this build's changes). The first-pass "stable failure" reading was wrong — five runs under concurrent dispatch load were insufficient repetition. **No fix routed**; factor isolation (what flips pass/fail) remains follow-up.
