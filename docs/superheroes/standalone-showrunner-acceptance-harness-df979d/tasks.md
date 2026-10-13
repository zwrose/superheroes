---
superheroes: doc
schemaVersion: 1
docType: tasks
workItem: standalone-showrunner-acceptance-harness-df979d
issue: null
size: medium
status: approved
gates: {review: passed}
producedBy: "the-architect@0.4.0"
created: "2026-07-02"
updated: "2026-07-02"
---
# Standalone showrunner acceptance harness — Tasks

> **Build contract (superheroes).** These tasks are executed by the producer's **Build**
> phase — **not here**. Build invokes superpowers **subagent-driven-development** with the
> worktree **pre-verified, not created**, and **without** `finishing-a-development-branch`;
> the **producer enforces both clips** at invocation. `size: medium`. Advance to Build only
> once `gates.review: passed`.

## Goal

Durabilize the one-shot manual acceptance run into a single owner-invoked command
(`superheroes:acceptance`): launch the real showrunner on a canned throwaway fixture work-item in
the real repo, let it run its whole pipeline to a ready-for-review PR, judge the terminal outcome
against machine-checkable facts (including a readout-vs-reality consistency check), tear down every
artifact the run created on every exit path, and hand back exactly one plain-language pass/fail
verdict — unattended, never merging, and protected against mutating real state by structure.

## Architecture

Two layers plus one owner-facing skill front door, matching the band posture (CONVENTIONS §10.1:
scripts orchestrate; pure deciders do single-purpose, unit-testable judgment). The pure deciders
(`acceptance_verdict`, `acceptance_ceiling`, `acceptance_retry`, `acceptance_cleanup`,
`acceptance_reclaim`) each expose a `decide()`/`classify()`/`plan()` over a plain dict — no I/O,
mirroring `preflight.decide`. The mechanical layer (`acceptance_launch` process-group launcher +
ceiling watch, `acceptance_run` orchestrator, `acceptance_fixture` materializer/drift-check,
`acceptance_result` record writer + report renderer) does the I/O and process control; every
judgment is delegated to a decider. The showrunner runs **out-of-process** as a headless
`claude`-CLI host-session child in its own process group so a ceiling breach can hard-kill the
whole group from outside the run under test. Structural never-merge (UFR-6) is an additive
**deny-only mode** in the existing `lib/enforcer.py`: an environment marker the launcher sets on
the child switches every owner-authority action (merge / release / run-workflow / force-push /
push-to-default) from `ask` to `deny`, with allowance overlays not honored. The harness's own
lease + result record live under a harness namespace in `lib/control_plane.py`, never touching a
real work-item's records. All new deciders/mechanics are unit-tested against injected fakes; only
the DoD's single live acceptance run touches a real showrunner.

## Tech Stack

Python 3 (all new libs: the five pure deciders, the `acceptance_launch` process-group launcher,
the `acceptance_run` orchestrator, `acceptance_fixture` materializer, `acceptance_result` record
writer + renderer, and the additive deny-only mode in `enforcer.py`), driving the already-installed
`claude` CLI in non-interactive headless mode as the launch vehicle for `lib/showrunner.bundle.js`
via the `superheroes:showrunner` skill's Workflow-tool path; `git`/`gh` CLIs for artifact facts and
cleanup; reused libs `lib/preflight.py`, `lib/buildtree.py`, `lib/control_plane.py`,
`lib/ref_lock.py`/`lib/fence_cli.py`, `lib/run_readout.py`; pytest for every deterministic behavior
(no live run required), plus the committed fixture under `plugins/superheroes/eval/fixtures/acceptance/`.

## Global Constraints

- **Commits:** Conventional Commits scoped to `superheroes` (e.g. `feat(superheroes): add acceptance-harness verdict decider (#112)`). Do **not** hand-edit `version` in either `plugin.json` — release-please owns it.
- **Deciders are pure:** every `acceptance_*` decider is a pure function over a plain dict — no file, network, clock, or subprocess I/O inside `decide()`/`classify()`/`plan()`. All I/O (clock, `gh`, process control, store reads/writes) lives in the mechanical modules (`acceptance_run`, `acceptance_launch`, `acceptance_fixture`, `acceptance_result`) and is injected into tests. This is what makes "every deterministic behavior proven without a live run" (DoD) achievable.
- **Fail-closed everywhere:** any unreadable required fact, unconfirmable liveness, or ambiguous classification yields the safe outcome — a fail verdict (never a false pass), a refusal (never a reclaim of a possibly-live run), or "behavioral / no retry" (never an unwarranted retry). Mirror the fail-closed posture already in `preflight.py` and `front_half.is_usable_draft`.
- **Never mutate real state:** the harness only ever closes the fixture PR / deletes the fixture branch / removes the stamped throwaway work-item and its run-state. Cleanup is scoped to artifacts whose names parse to a valid **full harness stamp** — never a bare prefix or substring match. The launcher sets the enforcement env marker so the child's owner-authority actions are structurally denied (UFR-6).
- **Reserved harness prefix + full stamp:** define the reserved prefix and the full-stamp token shape **once** (in `acceptance_fixture`) and import it everywhere (fixture, cleanup, reclaim discovery). The stamp = reserved prefix + a per-launch unique id, embedded whole in a defined name position of every artifact (slug, branch, PR title).
- **New lib-test discovery:** every new `plugins/superheroes/lib/tests/test_acceptance_*.py` is picked up by the existing pytest collection under `plugins/superheroes/lib/tests/` — no registry edit needed (unlike node smokes). Confirm collection in the final gate task.
- **Local CI gate (run before any push):**
  ```bash
  python3 .github/scripts/validate_marketplace.py
  python3 .github/scripts/validate_hosts.py
  python3 .github/scripts/validate_skills.py
  python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ plugins/superheroes/eval/tests/ eval/lib/tests/ -q
  ```

---

### Task 1: Reserved stamp + fixture materializer & drift check (`acceptance_fixture.py`)

**Files:**
- Create: `plugins/superheroes/lib/acceptance_fixture.py`
- Create: `plugins/superheroes/eval/fixtures/acceptance/spec.md`, `plan.md`, `tasks.md` (the committed fixture triple)
- Create: `plugins/superheroes/eval/fixtures/acceptance/target.txt` (the fixture's single target file the drift check anchors on)
- Test: `plugins/superheroes/lib/tests/test_acceptance_fixture.py`

**Interfaces:**
- Consumes: nothing (foundational). Reads the committed fixture triple + the pipeline's current phase list (injected in tests; read from the fixture's declared `expected_phases` and compared to a supplied `pipeline_phases`).
- Produces:
  - `RESERVED_PREFIX` (str) — the harness-owned namespace prefix (e.g. `"accept-harness-"`).
  - `make_stamp(unique_id) -> str` — reserved prefix + unique id → the full stamp token.
  - `parse_stamp(name) -> str | None` — returns the full stamp if `name` contains a structurally-valid full stamp in its defined position, else `None` (a bare prefix that does not parse to a full stamp returns `None`).
  - `materialize(unique_id, fixture_dir, dest_store_dir) -> {"work_item": str, "branch": str, "pr_title": str, "paths": [str]}` — copies the committed fixture triple into a fresh stamped throwaway work-item slug (`gates.review: passed` so preflight admits it) and returns the stamped names. Two consecutive materializations with distinct `unique_id`s never collide.
  - `drift_check(fixture_dir, pipeline_phases, target_exists) -> {"ok": bool, "reason": str}` — `ok` only when the fixture's declared `expected_phases` equals `pipeline_phases` AND its single target file exists; else `ok: False` naming the drift (absent fixture, phase-list drift, or missing target).

- [ ] **Step 1: Write the failing test**

```python
# plugins/superheroes/lib/tests/test_acceptance_fixture.py
import os, sys, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_fixture as af

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "..", "eval", "fixtures", "acceptance")


def test_reserved_prefix_and_full_stamp_roundtrip():
    stamp = af.make_stamp("abc123")
    assert stamp.startswith(af.RESERVED_PREFIX)
    assert af.parse_stamp("wi-%s-branch" % stamp) == stamp
    assert af.parse_stamp(stamp) == stamp


def test_bare_prefix_that_is_not_a_full_stamp_does_not_parse():
    # a prefix match that is NOT a full structurally-valid stamp must return None
    # (cleanup routes it to the reported-left-behind path, never a delete).
    assert af.parse_stamp(af.RESERVED_PREFIX) is None
    assert af.parse_stamp(af.RESERVED_PREFIX + "!!not-a-valid-id") is None


def test_two_materializations_never_collide():
    store = tempfile.mkdtemp()
    try:
        a = af.materialize("id-one", FIXTURE, store)
        b = af.materialize("id-two", FIXTURE, store)
        assert a["work_item"] != b["work_item"]
        assert a["branch"] != b["branch"]
        assert a["pr_title"] != b["pr_title"]
        # the materialized tasks doc carries a passed review gate so preflight admits it
        tasks = os.path.join(store, a["work_item"], "tasks.md")
        assert os.path.isfile(tasks)
        assert "gates: {review: passed}" in open(tasks).read()
    finally:
        shutil.rmtree(store, ignore_errors=True)


def test_drift_check_passes_when_phases_match_and_target_exists():
    # the committed fixture declares expected_phases; feed the same list.
    phases = af.expected_phases(FIXTURE)
    res = af.drift_check(FIXTURE, pipeline_phases=phases, target_exists=True)
    assert res["ok"] is True


def test_drift_check_fails_on_phase_list_drift():
    res = af.drift_check(FIXTURE, pipeline_phases=["only-one-phase"], target_exists=True)
    assert res["ok"] is False
    assert "phase" in res["reason"].lower()


def test_drift_check_fails_on_missing_target():
    phases = af.expected_phases(FIXTURE)
    res = af.drift_check(FIXTURE, pipeline_phases=phases, target_exists=False)
    assert res["ok"] is False
    assert "target" in res["reason"].lower()


def test_drift_check_fails_on_absent_fixture():
    res = af.drift_check("/no/such/fixture/dir", pipeline_phases=["x"], target_exists=True)
    assert res["ok"] is False
    assert "fixture" in res["reason"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_fixture.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'acceptance_fixture'`.

- [ ] **Step 3: Author the committed fixture triple + target file**

Create `plugins/superheroes/eval/fixtures/acceptance/target.txt` with a single line the fixture's one task appends to (the cheapest one-file change):

```
acceptance-harness fixture target — the run appends one dated line below.
```

Create `plugins/superheroes/eval/fixtures/acceptance/spec.md` — a minimal approved spec for a one-file change (frontmatter `docType: spec`, `status: approved`, `gates: {review: passed}`), body sections `Purpose`, `Functional requirements` (FR-1: append exactly one line to `target.txt`), `Definition of done`. No open choice.

Create `plugins/superheroes/eval/fixtures/acceptance/plan.md` — approved plan for that change (frontmatter `docType: plan`, `status: approved`, `gates: {review: passed}`), sections `Overview`, `Goals & non-goals`, `Architecture`, `Components & interfaces`, `How the requirements are met`, `Key decisions & alternatives`, `Risks & mitigations`, `Dependencies & assumptions`.

Create `plugins/superheroes/eval/fixtures/acceptance/tasks.md` — approved tasks for that change (frontmatter `docType: tasks`, `status: approved`, `gates: {review: passed}`), sections `## Goal`, `## Architecture`, `## Tech Stack`, plus exactly one `### Task 1: Append the dated line to target.txt` with TDD steps touching only `target.txt`. Add an `expected_phases:` list in the tasks frontmatter (or a sibling `phases.json`) enumerating the pipeline phases this fixture expects to traverse — this is what `drift_check` compares. Pick the representation `expected_phases()` reads in Step 4; keep it a plain YAML/JSON list.

- [ ] **Step 4: Write minimal implementation**

Implement `RESERVED_PREFIX`, `make_stamp`, `parse_stamp` (a compiled regex anchoring the reserved prefix + a `[a-z0-9-]+` unique id in the defined name position; `parse_stamp` returns the matched full token or `None`), `expected_phases(fixture_dir)` (read the fixture's declared phase list; missing → `[]`), `materialize` (copy the triple, rewrite each frontmatter `workItem` to the stamped slug, ensure the tasks `gates: {review: passed}`, return stamped slug/branch/pr_title/paths), and `drift_check` (absent fixture dir → fail naming fixture; `expected_phases != pipeline_phases` → fail naming phase drift; `not target_exists` → fail naming target). All pure/deterministic given inputs; `materialize` is the one I/O function.

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_fixture.py -q`
Expected: PASS — all seven tests green.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(superheroes): acceptance-harness fixture, stamp, and drift check (#112)"
```

---

### Task 2: Verdict decider (`acceptance_verdict.py`) — FR-3 / FR-4 / UFR-9

**Files:**
- Create: `plugins/superheroes/lib/acceptance_verdict.py`
- Test: `plugins/superheroes/lib/tests/test_acceptance_verdict.py`

**Interfaces:**
- Consumes: a plain `facts` dict assembled by the orchestrator from the run-outcome + live `gh` reads: `{terminal, pr_exists, pr_ready_for_review, checks_green, phases_traversed, expected_phases, readout_exists, readout_pr_link, readout_claimed_checks_green, live_checks_green, readout_claimed_pr, live_pr, unreadable: [str]}`.
- Produces: `decide(facts) -> {"verdict": "pass"|"fail", "reason": str}` — `pass` **only** when every required fact is present, true, and readable AND the readout-vs-reality consistency holds; else `fail` naming the first false/unreadable/inconsistent fact.

- [ ] **Step 1: Write the failing test**

```python
# plugins/superheroes/lib/tests/test_acceptance_verdict.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_verdict as v

PASS = dict(
    terminal="ready", pr_exists=True, pr_ready_for_review=True, checks_green=True,
    phases_traversed=["plan", "tasks", "build", "review", "ship"],
    expected_phases=["plan", "tasks", "build", "review", "ship"],
    readout_exists=True, readout_pr_link="https://x/pr/1",
    readout_claimed_checks_green=True, live_checks_green=True,
    readout_claimed_pr="https://x/pr/1", live_pr="https://x/pr/1",
    unreadable=[],
)


def test_all_facts_true_is_pass():
    assert v.decide(dict(PASS))["verdict"] == "pass"


def test_terminal_not_ready_is_fail_naming_it():
    f = dict(PASS); f["terminal"] = "parked"
    r = v.decide(f); assert r["verdict"] == "fail" and "terminal" in r["reason"].lower()


def test_missing_pr_is_fail():
    f = dict(PASS); f["pr_exists"] = False
    assert v.decide(f)["verdict"] == "fail"


def test_red_checks_is_fail():
    f = dict(PASS); f["checks_green"] = False
    assert v.decide(f)["verdict"] == "fail"


def test_missing_phase_is_fail():
    f = dict(PASS); f["phases_traversed"] = ["plan", "tasks", "build", "review"]
    assert v.decide(f)["verdict"] == "fail"


def test_readout_missing_or_no_pr_link_is_fail():
    f = dict(PASS); f["readout_pr_link"] = ""
    assert v.decide(f)["verdict"] == "fail"


def test_readout_claims_green_but_live_red_is_inconsistent_fail():
    f = dict(PASS); f["readout_claimed_checks_green"] = True; f["live_checks_green"] = False
    r = v.decide(f)
    assert r["verdict"] == "fail" and "inconsistent" in r["reason"].lower()


def test_readout_pr_differs_from_live_pr_is_inconsistent_fail():
    f = dict(PASS); f["readout_claimed_pr"] = "https://x/pr/9"; f["live_pr"] = "https://x/pr/1"
    r = v.decide(f)
    assert r["verdict"] == "fail" and "inconsistent" in r["reason"].lower()


def test_unreadable_required_fact_is_fail_naming_it_never_pass():
    f = dict(PASS); f["unreadable"] = ["live_checks_green"]
    r = v.decide(f)
    assert r["verdict"] == "fail" and "live_checks_green" in r["reason"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_verdict.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'acceptance_verdict'`.

- [ ] **Step 3: Write minimal implementation**

Implement `decide(facts)`: first, if `facts.get("unreadable")` is non-empty, fail naming those facts (UFR-9 — an unreadable fact never contributes to a pass). Then check, in order, each required fact (`terminal == "ready"`, `pr_exists`, `pr_ready_for_review`, `checks_green`, `set(phases_traversed) >= set(expected_phases)`, `readout_exists`, truthy `readout_pr_link`), failing with a reason naming the first false one. Then the consistency comparison (FR-4): if `readout_claimed_checks_green != live_checks_green` or `readout_claimed_pr != live_pr`, fail with a reason containing "inconsistent with reality". Otherwise `pass`. Pure; never raises (treat a missing key as its false/unreadable form).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_verdict.py -q`
Expected: PASS — all nine tests green.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(superheroes): acceptance-harness verdict decider (#112)"
```

---

### Task 3: Ceiling decider (`acceptance_ceiling.py`) — FR-8 / FR-9 / UFR-2

**Files:**
- Create: `plugins/superheroes/lib/acceptance_ceiling.py`
- Test: `plugins/superheroes/lib/tests/test_acceptance_ceiling.py`

**Interfaces:**
- Consumes: `{elapsed_sec, spend_sampled, spend_readable, ceilings: {elapsed_sec, spend}, attempt, budget_consumed: {elapsed_sec, spend}}`.
- Produces: `decide(state) -> {"action": "continue"|"kill", "ceiling": None|"elapsed"|"spend", "remaining": {"elapsed_sec": float, "spend": float|None}}` — the breach test is **invocation-scoped**: it compares `elapsed_sec + budget_consumed["elapsed_sec"]` (and, when readable, `spend_sampled + budget_consumed["spend"]`) against the ceilings, so a retry (`attempt >= 2`, non-zero `budget_consumed`) trips on the *remaining* budget rather than a fresh full ceiling. `kill(elapsed)` or `kill(spend)` on breach; when spend is unreadable it governs on elapsed alone (fail-closed on the readable ceiling) and never kills on spend; `remaining` is the budget a retry inherits (invocation-scoped: `ceiling - budget_consumed`).
- Also `DEFAULT_CEILINGS` (built-in conservative defaults applied when the owner configured nothing — FR-8).

- [ ] **Step 1: Write the failing test**

```python
# plugins/superheroes/lib/tests/test_acceptance_ceiling.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_ceiling as c

C = {"elapsed_sec": 1800.0, "spend": 5.0}
BASE = dict(ceilings=C, attempt=1, budget_consumed={"elapsed_sec": 0.0, "spend": 0.0})


def test_defaults_exist():
    assert c.DEFAULT_CEILINGS["elapsed_sec"] > 0
    assert c.DEFAULT_CEILINGS["spend"] > 0


def test_under_both_ceilings_continues():
    r = c.decide(dict(BASE, elapsed_sec=10.0, spend_sampled=0.5, spend_readable=True))
    assert r["action"] == "continue"


def test_elapsed_breach_kills_naming_elapsed():
    r = c.decide(dict(BASE, elapsed_sec=1801.0, spend_sampled=0.5, spend_readable=True))
    assert r["action"] == "kill" and r["ceiling"] == "elapsed"


def test_spend_breach_kills_naming_spend():
    r = c.decide(dict(BASE, elapsed_sec=10.0, spend_sampled=5.5, spend_readable=True))
    assert r["action"] == "kill" and r["ceiling"] == "spend"


def test_unreadable_spend_governs_on_elapsed_only():
    # spend unreadable -> never kill on spend; only elapsed can trip (fail-closed on readable).
    under = c.decide(dict(BASE, elapsed_sec=10.0, spend_sampled=None, spend_readable=False))
    assert under["action"] == "continue"
    over = c.decide(dict(BASE, elapsed_sec=1801.0, spend_sampled=None, spend_readable=False))
    assert over["action"] == "kill" and over["ceiling"] == "elapsed"


def test_remaining_budget_is_invocation_scoped_for_retry():
    r = c.decide(dict(ceilings=C, attempt=2, elapsed_sec=10.0, spend_sampled=1.0,
                      spend_readable=True, budget_consumed={"elapsed_sec": 600.0, "spend": 2.0}))
    assert r["remaining"]["elapsed_sec"] == 1200.0   # 1800 - 600
    assert r["remaining"]["spend"] == 3.0            # 5 - 2


def test_retry_breach_is_invocation_scoped_not_fresh_ceiling():
    # attempt 2 with 1700s already consumed: a 200s elapsed (1700+200 > 1800) MUST kill,
    # even though 200s alone is far under the 1800s ceiling. Same for spend.
    r = c.decide(dict(ceilings=C, attempt=2, elapsed_sec=200.0, spend_sampled=0.5,
                      spend_readable=True, budget_consumed={"elapsed_sec": 1700.0, "spend": 0.0}))
    assert r["action"] == "kill" and r["ceiling"] == "elapsed"
    s = c.decide(dict(ceilings=C, attempt=2, elapsed_sec=10.0, spend_sampled=1.0,
                      spend_readable=True, budget_consumed={"elapsed_sec": 0.0, "spend": 4.5}))
    assert s["action"] == "kill" and s["ceiling"] == "spend"   # 4.5+1.0 > 5.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_ceiling.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'acceptance_ceiling'`.

- [ ] **Step 3: Write minimal implementation**

Implement `DEFAULT_CEILINGS` (conservative, e.g. `{"elapsed_sec": 1800.0, "spend": 5.0}`) and `decide(state)`: default `budget_consumed` to `{"elapsed_sec": 0.0, "spend": 0.0}` when absent; compute `remaining` from `ceilings - budget_consumed` (spend `None` when unreadable). Form the **invocation-scoped** totals `total_elapsed = elapsed_sec + budget_consumed["elapsed_sec"]` and (when `spend_readable`) `total_spend = spend_sampled + budget_consumed["spend"]`. If `total_elapsed >= ceilings["elapsed_sec"]` → `kill(elapsed)`. Else if `spend_readable` and `total_spend >= ceilings["spend"]` → `kill(spend)`. Else `continue`. Never kill on spend when `spend_readable` is false. On attempt 1 (`budget_consumed` all zero) this reduces to the raw comparison, so existing behavior is unchanged. Pure; never raises.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_ceiling.py -q`
Expected: PASS — every test in `test_acceptance_ceiling.py` green (including the invocation-scoped retry-breach cases).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(superheroes): acceptance-harness ceiling decider (#112)"
```

---

### Task 4: Retry classifier (`acceptance_retry.py`) — FR-9 / UFR-9

**Files:**
- Create: `plugins/superheroes/lib/acceptance_retry.py`
- Test: `plugins/superheroes/lib/tests/test_acceptance_retry.py`

**Interfaces:**
- Consumes: `failure_facts` dict: `{kind, unreadable: bool, attempt, park_reason, environmental_signal}` where `kind` is the failure category the orchestrator derived (e.g. `"check-runner-errored-before-running"`, `"host-unreachable"`, `"parked-blocking-review"`, `"red-check"`, `"unknown"`).
- Produces: `classify(failure_facts) -> {"retry": bool, "class": "environmental"|"behavioral"|"unconfirmable", "reason": str}` — `retry: True` only for a **confidently environmental** first-attempt failure; behavioral (parked / red check / blocking review) never retries; unconfirmable/unreadable → behavioral-equivalent, no retry (fail-closed); a second attempt (`attempt >= 2`) never retries again.

- [ ] **Step 1: Write the failing test**

```python
# plugins/superheroes/lib/tests/test_acceptance_retry.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_retry as r


def test_environmental_first_attempt_retries():
    res = r.classify({"kind": "check-runner-errored-before-running", "unreadable": False,
                      "attempt": 1})
    assert res["retry"] is True and res["class"] == "environmental"


def test_host_unreachable_first_attempt_retries():
    res = r.classify({"kind": "host-unreachable", "unreadable": False, "attempt": 1})
    assert res["retry"] is True and res["class"] == "environmental"


def test_parked_blocking_review_is_behavioral_no_retry():
    res = r.classify({"kind": "parked-blocking-review", "unreadable": False, "attempt": 1})
    assert res["retry"] is False and res["class"] == "behavioral"


def test_red_check_on_its_change_is_behavioral_no_retry():
    res = r.classify({"kind": "red-check", "unreadable": False, "attempt": 1})
    assert res["retry"] is False and res["class"] == "behavioral"


def test_unclassifiable_defaults_to_behavioral_no_retry():
    res = r.classify({"kind": "unknown", "unreadable": False, "attempt": 1})
    assert res["retry"] is False and res["class"] == "behavioral"


def test_unreadable_fact_never_justifies_retry_fail_closed():
    res = r.classify({"kind": "check-runner-errored-before-running", "unreadable": True,
                      "attempt": 1})
    assert res["retry"] is False


def test_second_attempt_never_retries_again():
    res = r.classify({"kind": "host-unreachable", "unreadable": False, "attempt": 2})
    assert res["retry"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_retry.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'acceptance_retry'`.

- [ ] **Step 3: Write minimal implementation**

Implement `classify(facts)`: if `facts.get("unreadable")` → `{retry: False, class: "unconfirmable"}` (fail-closed). If `facts.get("attempt", 1) >= 2` → no retry. Maintain an `_ENVIRONMENTAL` set of `kind` values (`check-runner-errored-before-running`, `host-unreachable`, and any other confidently-infrastructure kinds); if `kind` is in it → `{retry: True, class: "environmental"}`. Everything else → `{retry: False, class: "behavioral"}`. Pure; never raises.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_retry.py -q`
Expected: PASS — all seven tests green.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(superheroes): acceptance-harness retry classifier (#112)"
```

---

### Task 5: Cleanup planner (`acceptance_cleanup.py`) — FR-7 / UFR-3 / UFR-8

**Files:**
- Create: `plugins/superheroes/lib/acceptance_cleanup.py`
- Test: `plugins/superheroes/lib/tests/test_acceptance_cleanup.py`

**Interfaces:**
- Consumes: `plan(discovered_artifacts, run_stamp)` where `discovered_artifacts` is a list of `{kind, name}` (`kind` in `pr`/`branch`/`work_item`/`record`) and `run_stamp` is the full stamp for the current run (or `None` for record-less UFR-8 discovery, where each artifact's name is parsed independently).
- Produces: `plan(...) -> {"reap": [{kind, name}], "leave_behind": [{kind, name, reason}]}` — an artifact is in `reap` only when its name parses (via `acceptance_fixture.parse_stamp`) to a valid full stamp AND (when `run_stamp` is given) equals it; a name matching the reserved prefix but failing the full-stamp parse goes to `leave_behind` (UFR-3 reported path), never reaped; on already-clean input the plan is empty (idempotent).

- [ ] **Step 1: Write the failing test**

```python
# plugins/superheroes/lib/tests/test_acceptance_cleanup.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_fixture as af
import acceptance_cleanup as cl

STAMP = af.make_stamp("run-1")
OTHER = af.make_stamp("run-2")


def test_empty_input_is_empty_plan_idempotent():
    p = cl.plan([], run_stamp=STAMP)
    assert p["reap"] == [] and p["leave_behind"] == []


def test_matching_full_stamp_is_reaped():
    arts = [{"kind": "branch", "name": "wi-%s" % STAMP},
            {"kind": "pr", "name": "PR: %s fixture" % STAMP}]
    p = cl.plan(arts, run_stamp=STAMP)
    assert {a["name"] for a in p["reap"]} == {a["name"] for a in arts}
    assert p["leave_behind"] == []


def test_reserved_prefix_but_unparseable_is_left_behind_never_reaped():
    arts = [{"kind": "branch", "name": af.RESERVED_PREFIX + "!!garbage"}]
    p = cl.plan(arts, run_stamp=None)
    assert p["reap"] == []
    assert len(p["leave_behind"]) == 1


def test_other_runs_stamp_is_not_reaped_when_run_stamp_pinned():
    arts = [{"kind": "branch", "name": "wi-%s" % OTHER}]
    p = cl.plan(arts, run_stamp=STAMP)
    assert p["reap"] == []


def test_recordless_discovery_reaps_any_valid_full_stamp():
    arts = [{"kind": "branch", "name": "wi-%s" % OTHER}]
    p = cl.plan(arts, run_stamp=None)   # UFR-8: parse each independently
    assert {a["name"] for a in p["reap"]} == {"wi-%s" % OTHER}


def test_non_harness_artifact_is_ignored_never_reaped_or_left():
    arts = [{"kind": "branch", "name": "feature/real-owner-work"}]
    p = cl.plan(arts, run_stamp=None)
    assert p["reap"] == [] and p["leave_behind"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_cleanup.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'acceptance_cleanup'`.

- [ ] **Step 3: Write minimal implementation**

Implement `plan(discovered_artifacts, run_stamp)`: for each artifact, compute `parsed = acceptance_fixture.parse_stamp(name)`. If `parsed is None` and the name starts with `RESERVED_PREFIX` → `leave_behind` (unparseable-but-reserved). If `parsed is None` and no reserved prefix → ignore (a real owner artifact — never touched). If `parsed` is a valid full stamp: when `run_stamp` is set, reap only if `parsed == run_stamp` (else ignore — a different run's artifact, not this invocation's target); when `run_stamp is None` (UFR-8 record-less discovery), reap any valid full stamp. Pure; never raises.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_cleanup.py -q`
Expected: PASS — all six tests green.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(superheroes): acceptance-harness cleanup planner (#112)"
```

---

### Task 6: Reclaim decider (`acceptance_reclaim.py`) — UFR-4 / UFR-8

**Files:**
- Create: `plugins/superheroes/lib/acceptance_reclaim.py`
- Test: `plugins/superheroes/lib/tests/test_acceptance_reclaim.py`

**Interfaces:**
- Consumes: `decide(recorded_state, liveness)` where `recorded_state` is `{"in_flight": bool, "stamp": str|None, "has_record": bool}` and `liveness` is `"alive"|"dead"|"unconfirmable"`.
- Produces: `{"action": "proceed"|"reclaim"|"refuse", "class": str, "reason": str, "write_orphan_record": bool}` — refuse-in-flight on confirmed-alive (UFR-4); reclaim (then proceed) only on confirmed death (UFR-8), writing an orphan record only when `has_record` is false; refuse on unconfirmable liveness (treated as UFR-4); proceed when no recorded run is in flight.

- [ ] **Step 1: Write the failing test**

```python
# plugins/superheroes/lib/tests/test_acceptance_reclaim.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_reclaim as rc


def test_no_in_flight_state_proceeds():
    r = rc.decide({"in_flight": False, "stamp": None, "has_record": False}, liveness="dead")
    assert r["action"] == "proceed"


def test_confirmed_alive_refuses_in_flight():
    r = rc.decide({"in_flight": True, "stamp": "s", "has_record": True}, liveness="alive")
    assert r["action"] == "refuse"


def test_confirmed_dead_reclaims_and_writes_orphan_record_when_none():
    r = rc.decide({"in_flight": True, "stamp": "s", "has_record": False}, liveness="dead")
    assert r["action"] == "reclaim"
    assert r["write_orphan_record"] is True


def test_confirmed_dead_with_existing_record_does_not_write_second():
    r = rc.decide({"in_flight": True, "stamp": "s", "has_record": True}, liveness="dead")
    assert r["action"] == "reclaim"
    assert r["write_orphan_record"] is False


def test_unconfirmable_liveness_refuses_like_ufr4():
    r = rc.decide({"in_flight": True, "stamp": "s", "has_record": True}, liveness="unconfirmable")
    assert r["action"] == "refuse"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_reclaim.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'acceptance_reclaim'`.

- [ ] **Step 3: Write minimal implementation**

Implement `decide(recorded_state, liveness)`: if not `in_flight` → `proceed`. Else branch on `liveness`: `"alive"` → `refuse` (UFR-4, in-flight); `"unconfirmable"` → `refuse` (fail-closed, treated as UFR-4); `"dead"` → `reclaim` with `write_orphan_record = not recorded_state["has_record"]` (UFR-8). Pure; never raises.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_reclaim.py -q`
Expected: PASS — all five tests green.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(superheroes): acceptance-harness reclaim decider (#112)"
```

---

### Task 7: Result record writer + verdict-report renderer (`acceptance_result.py`) — FR-5 / FR-6

**Files:**
- Create: `plugins/superheroes/lib/acceptance_result.py`
- Test: `plugins/superheroes/lib/tests/test_acceptance_result.py`

**Interfaces:**
- Consumes (write): a `result` dict with at least `{verdict, reason, pr_link, phases, spend, spend_partial, elapsed_sec, launched_at, terminated_at, retried, attempts: [...]}` and a target dir (the harness namespace in the control-plane store).
- Produces:
  - `SCHEMA_VERSION` (int) and `write_record(result, dest_dir) -> path` — writes exactly one `acceptance-result.json` (schemaVersion-guarded); overwriting is not allowed for the same invocation (one record per invocation).
  - `read_record(dest_dir) -> dict|None` — never raises (mirrors `loop_readout`): a missing/older/corrupt record returns `None` rather than throwing.
  - `render_report(result) -> str` — the plain-language verdict report with exactly the four elements: verdict, reason, where the record lives, and what was cleaned up / left behind.
- Contract: a record missing any required element is rejected by `write_record` (raises `ValueError`) so FR-5's "all listed elements" is enforced at the writer.

- [ ] **Step 1: Write the failing test**

```python
# plugins/superheroes/lib/tests/test_acceptance_result.py
import os, sys, json, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_result as ar

FULL = dict(
    verdict="fail", reason="terminal was parked", pr_link="https://x/pr/1",
    phases=["plan", "tasks"], spend=1.25, spend_partial=False, elapsed_sec=42.0,
    launched_at="2026-07-02T00:00:00Z", terminated_at="2026-07-02T00:01:00Z",
    retried=False, attempts=[{"stamp": "s1", "verdict": "fail"}],
    cleaned_up=["branch wi-s1"], left_behind=[],
)


def test_write_then_read_roundtrips_with_schema_version():
    d = tempfile.mkdtemp()
    try:
        p = ar.write_record(dict(FULL), d)
        assert os.path.isfile(p)
        rec = ar.read_record(d)
        assert rec["schemaVersion"] == ar.SCHEMA_VERSION
        assert rec["verdict"] == "fail"
        assert rec["attempts"][0]["stamp"] == "s1"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_missing_required_element_is_rejected():
    d = tempfile.mkdtemp()
    try:
        bad = dict(FULL); del bad["elapsed_sec"]
        try:
            ar.write_record(bad, d)
            assert False, "expected ValueError for a record missing a required element"
        except ValueError:
            pass
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_read_missing_record_returns_none_never_raises():
    d = tempfile.mkdtemp()
    try:
        assert ar.read_record(d) is None
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_render_report_has_all_four_elements():
    out = ar.render_report(dict(FULL))
    assert "fail" in out.lower()                 # verdict
    assert "terminal was parked" in out          # reason
    assert "record" in out.lower()               # where the record lives
    assert ("cleaned" in out.lower() or "left behind" in out.lower())  # cleaned-up/left-behind


def test_render_report_notes_partial_spend_when_flagged():
    r = dict(FULL); r["spend_partial"] = True
    assert "partial" in ar.render_report(r).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_result.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'acceptance_result'`.

- [ ] **Step 3: Write minimal implementation**

Implement `SCHEMA_VERSION = 1`; `write_record(result, dest_dir)` validates every FR-5 required key is present (else `ValueError`), stamps `schemaVersion`, writes `acceptance-result.json` (atomic write to a temp file then rename), returns the path; `read_record(dest_dir)` reads the file and returns the dict only when `schemaVersion == SCHEMA_VERSION`, else `None` — any OSError/JSON error → `None` (never raises), mirroring `loop_readout`. `render_report(result)` emits the four elements as plain text, appending a "spend is partial" note when `spend_partial` is true. Report renderer never raises.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_result.py -q`
Expected: PASS — all five tests green.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(superheroes): acceptance-harness result record + verdict-report renderer (#112)"
```

---

### Task 8: Enforcer deny-only mode (`enforcer.py`, additive) — UFR-6

**Files:**
- Modify: `plugins/superheroes/lib/enforcer.py`
- Test: `plugins/superheroes/lib/tests/test_enforcer.py` (add cases; if that file does not exist, create it — but check first and extend the existing coverage)

**Interfaces:**
- New behavior: when the launcher-set enforcement environment marker is present (a well-known env var, e.g. `SUPERHEROES_ACCEPTANCE_DENY_ONLY=1`), `classify_command` returns `deny` for the owner-authority (gated) set **even when `host == "claude"`** (overriding the `ask` path) **and even when `in_scope` is false** — the marker deny must be evaluated **before** the `if not in_scope: return ("allow","")` short-circuit, because the showrunner child's Build phase runs from a build worktree under `~/.superheroes-worktrees` whose fresh checkout contains only tracked files, and `docs/superheroes/` is gitignored (`git ls-files docs/` = 0), so `_in_superheroes_repo` returns False and `in_scope` is False there. If the marker deny sat inside the in-scope branch, the floor would be bypassed from exactly the worktree the child builds in. The hook's allowance overlay is **not** honored under the marker (the child cannot mint its way past the floor). Note the overlay itself only runs on the deny-only (non-claude) host path (the enforcer gates it on `host != "claude"`); the harness child runs `--host claude`, where the floor is the marker deny in `classify_command` alone. The `and not _deny_only()` guard on the overlay is a defense-in-depth belt for any deny-only-host caller and is tested on that reachable path. The marker is read from the environment (inherited by every subagent/grandchild), so the floor is independent of cwd/worktree/store resolution — including the build worktree.
- Unchanged: the unconditional deny surfaces (canary, safety-writes), the out-of-repo `allow` **when the marker is unset**, the ordinary producer commands (`git commit`, non-force branch push).

- [ ] **Step 1: Write the failing test**

```python
# plugins/superheroes/lib/tests/test_enforcer.py  (add these cases)
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import enforcer

MARKER = "SUPERHEROES_ACCEPTANCE_DENY_ONLY"


def _with_marker(monkeypatch, on):
    if on:
        monkeypatch.setenv(MARKER, "1")
    else:
        monkeypatch.delenv(MARKER, raising=False)


def test_deny_only_marker_turns_claude_ask_into_deny(monkeypatch):
    _with_marker(monkeypatch, True)
    # without the marker, claude in-scope gets ask; with it, deny.
    assert enforcer.classify_command("gh pr merge 1", host="claude", in_scope=True)[0] == "deny"


def test_deny_only_marker_covers_full_owner_authority_set(monkeypatch):
    _with_marker(monkeypatch, True)
    for cmd in ["gh pr merge 1", "gh release create v1", "gh workflow run ci",
                "git push --force origin b", "git push origin main"]:
        assert enforcer.classify_command(cmd, host="claude", in_scope=True)[0] == "deny", cmd


def test_without_marker_claude_still_asks(monkeypatch):
    _with_marker(monkeypatch, False)
    assert enforcer.classify_command("gh pr merge 1", host="claude", in_scope=True)[0] == "ask"


def test_marker_does_not_change_ordinary_commands(monkeypatch):
    _with_marker(monkeypatch, True)
    assert enforcer.classify_command("git commit -m x", host="claude", in_scope=True)[0] == "allow"


def test_deny_only_marker_denies_out_of_scope_from_build_worktree(monkeypatch):
    # UFR-6 security floor: the showrunner child's Build phase runs from a build worktree
    # whose fresh checkout has no docs/superheroes/ (gitignored), so in_scope resolves False.
    # Without the marker, out-of-scope owner-authority is allowed; UNDER the marker it MUST
    # still deny — the marker deny is evaluated before the `if not in_scope: allow` short-circuit.
    _with_marker(monkeypatch, True)
    assert enforcer.classify_command("gh pr merge 1", host="claude", in_scope=False)[0] == "deny"
    for cmd in ["gh release create v1", "gh workflow run ci",
                "git push --force origin b", "git push origin main"]:
        assert enforcer.classify_command(cmd, host="claude", in_scope=False)[0] == "deny", cmd
    # the marker does NOT widen non-gated commands: ordinary out-of-scope stays allow.
    assert enforcer.classify_command("git commit -m x", host="claude", in_scope=False)[0] == "allow"


def test_without_marker_out_of_scope_owner_authority_still_allowed(monkeypatch):
    # regression guard: default (marker unset) out-of-repo behavior is byte-identical to today.
    _with_marker(monkeypatch, False)
    assert enforcer.classify_command("gh pr merge 1", host="claude", in_scope=False)[0] == "allow"


def test_allowance_overlay_not_honored_under_marker(monkeypatch):
    # The allowance overlay lives in `hook()` and only fires on the deny-only (non-claude) host
    # path (enforcer gates it on `host != "claude"`). Under the marker, the `and not _deny_only()`
    # guard must stop `hook()` from consuming an allowance to flip a denied owner-authority action
    # — exercised on the reachable (host="codex") path so this is a real test of the guard, not a
    # no-op. We assert the hook does NOT emit an allow even when a matching allowance is mintable.
    import json as _json
    _with_marker(monkeypatch, True)
    consumed = {"called": False}
    monkeypatch.setattr(enforcer.allowance, "consume",
                        lambda *a, **k: consumed.__setitem__("called", True) or True)
    emitted = {}
    monkeypatch.setattr(enforcer, "_emit",
                        lambda decision, reason: emitted.__setitem__("d", decision))
    # a superheroes-repo cwd so in_scope is True on this deny-only host path:
    payload = _json.dumps({"tool_name": "Bash", "tool_input": {"command": "gh pr merge 1"},
                           "cwd": os.getcwd()})
    enforcer.hook(payload, host="codex")
    assert emitted.get("d") == "deny"            # denied despite a mintable allowance
    assert consumed["called"] is False           # the overlay was NOT consulted under the marker


def test_deny_only_floor_holds_on_claude_host_without_allowance_path(monkeypatch):
    # On the claude host the allowance overlay never runs at all; the floor is purely the
    # marker deny in classify_command, so this documents the load-bearing UFR-6 path directly.
    _with_marker(monkeypatch, True)
    assert enforcer.classify_command("gh pr merge 1", host="claude", in_scope=True)[0] == "deny"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_enforcer.py -q`
Expected: FAIL — the new deny-only cases fail (marker not yet honored: claude returns `ask`).

- [ ] **Step 3: Write minimal implementation**

Add a module-level marker name `_DENY_ONLY_ENV = "SUPERHEROES_ACCEPTANCE_DENY_ONLY"` and a helper `_deny_only()` reading `os.environ.get(_DENY_ONLY_ENV)` truthily. In `classify_command`, in the gated-action branch (`if action:`), **first** — before the `if not in_scope: return ("allow","")` short-circuit — when `_deny_only()` is true return `deny` (with a reason naming the deny-only floor) regardless of `host` **and regardless of `in_scope`**. This ordering is load-bearing for UFR-6: the showrunner child's Build phase runs from a build worktree under `~/.superheroes-worktrees` whose fresh checkout has no `docs/superheroes/` (gitignored, `git ls-files docs/` = 0), so `_in_superheroes_repo` → False → `in_scope` False there; if the marker deny sat after the in-scope short-circuit, an owner-authority action from the build worktree would fall through to `allow` and the structural never-merge floor would be bypassed. Only after that marker check does the existing order stand: `if not in_scope: return ("allow","")`, then the `host == "claude"` ask branch, then the deny-only-host deny. In `hook`, guard the allowance-consume overlay with `and not _deny_only()` so no allowance flips a denied owner-authority action under the marker. Leave every unconditional surface, the out-of-repo allow **when the marker is unset**, and ordinary commands untouched. Keep the change additive: default (marker unset) behavior is byte-identical to today (out-of-scope owner-authority still `allow`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_enforcer.py -q`
Expected: PASS — the new deny-only cases green and every pre-existing enforcer test still green.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(superheroes): enforcer deny-only mode for the acceptance harness floor (#112)"
```

---

### Task 9: Child-process launcher + ceiling watch (`acceptance_launch.py`) — FR-1 / FR-8 / UFR-2 / UFR-5 / UFR-6

**Files:**
- Create: `plugins/superheroes/lib/acceptance_launch.py`
- Test: `plugins/superheroes/lib/tests/test_acceptance_launch.py`

**Interfaces:**
- Consumes: the stamped work-item, resolved ceilings, an optional `budget_consumed` (`{elapsed_sec, spend}` already spent by a prior attempt of this invocation; defaults to zero on attempt 1), the `attempt` number, and **injectable** dependencies — a `child_factory` (returns a child handle exposing `poll()`, `killpg()`, `group_empty()`, `terminal_location()`), a `clock`, and a `spend_sampler` (returns `(spend_or_none, readable_bool)`). Real defaults spawn the headless `claude` CLI as a process-group leader (`start_new_session=True`) with the execution-context marker (`SUPERHEROES_ACCEPTANCE_CONTEXT=1`, read by the skill to refuse nesting — UFR-5) and the enforcement marker (`SUPERHEROES_ACCEPTANCE_DENY_ONLY=1`, Task 8 — UFR-6) set on the child env, plus the harness-scoped permission profile.
- Produces: `run(stamped, ceilings, child_factory, clock, spend_sampler, engine_pref_reader, budget_consumed=None, attempt=1) -> {"outcome": "exited"|"killed", "ceiling": None|"elapsed"|"spend", "terminal_location": str|None, "spend_partial": bool, "spend": float|None, "elapsed_sec": float}` — samples elapsed + spend each tick, feeds `acceptance_ceiling.decide` **with `budget_consumed` and `attempt` threaded in** (so the ceiling watch enforces the invocation's *remaining* budget on a retry — `ceiling - budget_consumed` — never a fresh full ceiling: FR-8's invocation-scoped bound), and on a `kill` decision signals the **whole group** (SIGTERM → escalate to SIGKILL), returning `killed` with which ceiling tripped; on natural exit returns the child's terminal location. **Returns the final sampled `spend` and computed `elapsed_sec` on every path** so the orchestrator has a real source for the FR-5-required record fields (Task 7's `write_record` rejects a record missing `spend`/`elapsed_sec`); `spend` is `None` when spend was unreadable throughout. Teardown-readiness gate: it only reports the child confirmed-dead when `group_empty()` is true (no surviving group member); if group membership cannot be enumerated it returns a leftover-path signal (never a clean exit). Marks `spend_partial` true when any role's engine preference resolves to an external engine (engine-dispatched leaf spend is outside the sampled stream) — the engine-preference read is injected in tests.

- [ ] **Step 1: Write the failing test**

```python
# plugins/superheroes/lib/tests/test_acceptance_launch.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_launch as al

CEIL = {"elapsed_sec": 100.0, "spend": 10.0}


class FakeClock:
    def __init__(self, ticks): self.ticks = list(ticks); self.i = -1
    def now(self):
        self.i += 1
        return self.ticks[min(self.i, len(self.ticks) - 1)]


class FakeChild:
    def __init__(self, exits_after, group_empty_after=None):
        self.calls = 0; self.exits_after = exits_after
        self.signals = []; self._group_empty_after = group_empty_after
        self._killed_at = None
    def poll(self):
        self.calls += 1
        if self._killed_at is not None:
            return 0
        return None if self.calls < self.exits_after else 0
    def killpg(self, sig):
        self.signals.append(sig)
        if self._killed_at is None:
            self._killed_at = self.calls
    def group_empty(self):
        if self._group_empty_after is None:
            return self._killed_at is not None
        return self._killed_at is not None and self.calls - self._killed_at >= self._group_empty_after
    def terminal_location(self):
        return "/run/terminal-record.json"


def test_natural_exit_returns_terminal_location_and_spend_elapsed():
    child = FakeChild(exits_after=2)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 1, 2]), spend_sampler=lambda: (0.1, True),
                 engine_pref_reader=lambda: {"all": "claude"})
    assert res["outcome"] == "exited"
    assert res["terminal_location"] == "/run/terminal-record.json"
    assert res["spend_partial"] is False
    # the launcher MUST surface the final sampled spend + elapsed so the orchestrator can
    # populate the FR-5-required record fields (Task 7 write_record rejects them missing).
    assert "spend" in res and "elapsed_sec" in res
    assert res["spend"] == 0.1
    assert res["elapsed_sec"] >= 0.0


def test_unreadable_spend_surfaces_none_spend_not_crash():
    child = FakeChild(exits_after=2)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 1, 2]), spend_sampler=lambda: (None, False),
                 engine_pref_reader=lambda: {"all": "claude"})
    assert res["outcome"] == "exited"
    assert res["spend"] is None            # unreadable throughout -> None, still present
    assert "elapsed_sec" in res


def test_retry_budget_threaded_trips_on_reduced_ceiling():
    # FR-8 invocation-scoped budget: attempt 2 inherits budget_consumed, so the ceiling watch
    # enforces (ceiling - consumed). With 90s already spent against a 100s ceiling, a 20s
    # elapsed on attempt 2 (90+20 > 100) MUST trip elapsed — not get a fresh full 100s.
    child = FakeChild(exits_after=999)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 5, 20, 20]), spend_sampler=lambda: (0.1, True),
                 engine_pref_reader=lambda: {"all": "claude"},
                 budget_consumed={"elapsed_sec": 90.0, "spend": 0.0}, attempt=2)
    assert res["outcome"] == "killed" and res["ceiling"] == "elapsed"


def test_elapsed_breach_kills_whole_group_and_names_ceiling():
    child = FakeChild(exits_after=999)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 50, 101, 101]), spend_sampler=lambda: (0.1, True),
                 engine_pref_reader=lambda: {"all": "claude"})
    assert res["outcome"] == "killed" and res["ceiling"] == "elapsed"
    assert child.signals  # the group was signaled (SIGTERM at least)


def test_spend_breach_kills_and_names_spend():
    child = FakeChild(exits_after=999)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 1, 2, 3]), spend_sampler=lambda: (10.5, True),
                 engine_pref_reader=lambda: {"all": "claude"})
    assert res["outcome"] == "killed" and res["ceiling"] == "spend"


def test_external_engine_pref_marks_spend_partial():
    child = FakeChild(exits_after=2)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 1, 2]), spend_sampler=lambda: (0.1, True),
                 engine_pref_reader=lambda: {"review": "codex"})
    assert res["spend_partial"] is True


def test_kill_confirmed_dead_only_when_group_empty():
    # SIGTERM then SIGKILL escalation until the group is empty.
    child = FakeChild(exits_after=999, group_empty_after=1)
    res = al.run("wi", CEIL, child_factory=lambda: child,
                 clock=FakeClock([0, 101, 101, 101, 101]), spend_sampler=lambda: (0.1, True),
                 engine_pref_reader=lambda: {"all": "claude"})
    assert res["outcome"] == "killed"
    assert len(child.signals) >= 2  # SIGTERM then SIGKILL escalation
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_launch.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'acceptance_launch'`.

- [ ] **Step 3: Write minimal implementation**

Implement `run(stamped, ceilings, child_factory, clock, spend_sampler, engine_pref_reader, budget_consumed=None, attempt=1)`: default `budget_consumed` to `{"elapsed_sec": 0.0, "spend": 0.0}`; spawn the child via `child_factory`; record `start = clock.now()`. Track `last_spend = None` and `last_elapsed = 0.0` across ticks. Loop: `poll()`; if the child exited return `{outcome: "exited", ceiling: None, terminal_location: child.terminal_location(), spend_partial, "spend": last_spend, "elapsed_sec": last_elapsed}`. Sample `elapsed = clock.now() - start` and `(spend, readable) = spend_sampler()`; set `last_elapsed = elapsed`, and `last_spend = spend` when `readable` (leave `None` if never readable); call `acceptance_ceiling.decide({..., "attempt": attempt, "budget_consumed": budget_consumed})` — the decider compares `elapsed + budget_consumed["elapsed_sec"]` (and spend likewise) so the retry enforces the *remaining* invocation budget; on `kill`, `killpg(SIGTERM)`, then poll/escalate to `killpg(SIGKILL)` until `group_empty()` is true (bounded escalation), and return `{outcome: "killed", ceiling: <tripped>, terminal_location: None, spend_partial, "spend": last_spend, "elapsed_sec": last_elapsed}`. Compute `spend_partial = any pref != "claude"` from `engine_pref_reader()`. Provide real defaults for `child_factory`/`clock`/`spend_sampler`/`engine_pref_reader` that use `subprocess`/`os.killpg`/`time`/the band's engine-pref lib — but the tests drive only the injected fakes (no live run). Keep the real-default spawn path thin and mechanical; all judgment is in the ceiling decider.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_launch.py -q`
Expected: PASS — every test in `test_acceptance_launch.py` green (including the spend/elapsed surfacing and the budget-threaded retry breach).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(superheroes): acceptance-harness process-group launcher + ceiling watch (#112)"
```

---

### Task 10: Orchestrator (`acceptance_run.py`) — the invocation lifecycle + one-record/one-report contract

**Files:**
- Create: `plugins/superheroes/lib/acceptance_run.py`
- Test: `plugins/superheroes/lib/tests/test_acceptance_run.py`

**Interfaces:**
- Consumes: injectable seams for every I/O boundary — `launcher` (Task 9's `run`), `fixture` (Task 1), `gh_reader` (live PR/check facts), `store` (control-plane namespace read/write for the lease + record), `reclaim_probe` (recorded-state + liveness), and the pure deciders (imported directly). A JSON CLI (`--fixture`, `--root`; ceilings from config with `acceptance_ceiling.DEFAULT_CEILINGS` fallback).
- Produces: `invoke(deps) -> {"verdict": ..., "report": str, "record_path": str|None}` — the full lifecycle: reclaim/refuse → materialize → `preflight.decide` on the fixture → launch → read run-outcome + live `gh` facts → `acceptance_verdict.decide` → `acceptance_cleanup.plan` → reap → **write the record** → **release the lease (only after the record is durably written)** → render report. The launcher result is the sole source of the FR-5-required `spend` and `elapsed_sec` record fields (Task 9 now returns both); the orchestrator threads them straight into the record it hands `write_record` (never invents or omits them, which would trip the writer's ValueError). On any internal harness error it still runs teardown and yields a **fail** verdict naming the error (never a pass). On a record-write failure it ends **with the lease held** (so the next invocation's UFR-8 path writes the missing failed record). Exactly one record + one report per invocation (covering both attempts when a retry ran). The retry (FR-9) launches attempt 2 with `budget_consumed` = attempt 1's returned `{elapsed_sec, spend}` and `attempt=2`, so the second launch enforces the invocation's *remaining* budget, and both attempts fold into the single record (`retried: True`, `attempts: [..2..]`).

- [ ] **Step 1: Write the failing test**

```python
# plugins/superheroes/lib/tests/test_acceptance_run.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_run as run


def _deps(**over):
    """A fully-stubbed happy-path dep bundle; override any seam per test."""
    state = {"records_written": [], "lease_released": False}
    base = dict(
        reclaim_probe=lambda: ({"in_flight": False, "stamp": None, "has_record": False}, "dead"),
        preflight_ok=lambda wi: {"ok": True},
        materialize=lambda: {"work_item": "wi-s1", "branch": "b-s1", "pr_title": "PR s1",
                             "stamp": "s1"},
        launcher=lambda stamped, budget_consumed=None, attempt=1: {
            "outcome": "exited", "terminal_location": "/t.json", "spend_partial": False,
            "spend": 1.25, "elapsed_sec": 42.0},
        run_outcome=lambda loc: {"terminal": "ready", "phases": ["plan", "tasks", "build",
                                 "review", "ship"], "readout_pr_link": "https://x/pr/1",
                                 "readout_claimed_checks_green": True,
                                 "readout_claimed_pr": "https://x/pr/1"},
        gh_reader=lambda: {"pr_exists": True, "pr_ready_for_review": True, "checks_green": True,
                           "live_checks_green": True, "live_pr": "https://x/pr/1", "unreadable": []},
        expected_phases=lambda: ["plan", "tasks", "build", "review", "ship"],
        discover_artifacts=lambda stamp: [{"kind": "branch", "name": "b-s1"}],
        reap=lambda planned: {"cleaned_up": [a["name"] for a in planned["reap"]], "left_behind": []},
        write_record=lambda rec: state["records_written"].append(rec) or "/rec.json",
        release_lease=lambda: state.__setitem__("lease_released", True),
        clock_now=lambda: "2026-07-02T00:00:00Z",
        _state=state,
    )
    base.update(over)
    return base


def test_happy_path_is_pass_one_record_one_report_lease_released():
    d = _deps()
    r = run.invoke(d)
    assert r["verdict"] == "pass"
    assert len(d["_state"]["records_written"]) == 1
    assert r["record_path"] == "/rec.json"
    assert d["_state"]["lease_released"] is True   # released AFTER the record write
    # the FR-5-required spend/elapsed come from the launcher result, not invented downstream.
    rec = d["_state"]["records_written"][0]
    assert rec["spend"] == 1.25 and rec["elapsed_sec"] == 42.0


def test_confirmed_alive_prior_run_refuses_creating_nothing():
    d = _deps(reclaim_probe=lambda: ({"in_flight": True, "stamp": "old", "has_record": True},
                                     "alive"))
    calls = []
    d["materialize"] = lambda: calls.append("m") or {"work_item": "x"}
    r = run.invoke(d)
    assert r["verdict"] == "fail"
    assert "in flight" in r["report"].lower() or "in-flight" in r["report"].lower()
    assert calls == []   # nothing materialized/launched


def test_parked_terminal_is_fail_but_teardown_still_runs():
    d = _deps(run_outcome=lambda loc: {"terminal": "parked", "phases": ["plan"],
                                       "readout_pr_link": "", "readout_claimed_checks_green": False,
                                       "readout_claimed_pr": "", })
    reaped = []
    d["reap"] = lambda planned: reaped.append(planned) or {"cleaned_up": ["b-s1"], "left_behind": []}
    r = run.invoke(d)
    assert r["verdict"] == "fail"
    assert reaped   # teardown still ran on the non-ready terminal (UFR-1)


def test_internal_harness_error_still_teardowns_and_fails_never_pass():
    boom = _deps()
    boom["gh_reader"] = lambda: (_ for _ in ()).throw(RuntimeError("gh blew up"))
    reaped = []
    boom["reap"] = lambda planned: reaped.append(1) or {"cleaned_up": [], "left_behind": []}
    r = run.invoke(boom)
    assert r["verdict"] == "fail"
    assert "gh blew up" in r["report"] or "error" in r["report"].lower()
    assert reaped   # teardown ran despite the internal error


def test_record_write_failure_ends_with_lease_held():
    d = _deps(write_record=lambda rec: (_ for _ in ()).throw(OSError("disk full")))
    r = run.invoke(d)
    assert r["verdict"] == "fail"
    assert d["_state"]["lease_released"] is False   # lease held so UFR-8 backstop stays armed


def test_environmental_retry_folds_two_attempts_into_one_record_sharing_budget():
    # FR-9: attempt 1 fails environmentally -> exactly one retry, one record naming both
    # attempts, and the retry launch is fed the invocation's REMAINING budget (budget_consumed
    # from attempt 1), not a fresh full ceiling.
    launches = []

    def _launcher(stamped, budget_consumed=None, attempt=1):
        launches.append({"attempt": attempt, "budget_consumed": budget_consumed})
        if attempt == 1:
            # environmental first-attempt failure (host unreachable), 300s + $1 consumed.
            return {"outcome": "exited", "terminal_location": "/t1.json",
                    "spend_partial": False, "spend": 1.0, "elapsed_sec": 300.0}
        return {"outcome": "exited", "terminal_location": "/t2.json",
                "spend_partial": False, "spend": 0.5, "elapsed_sec": 120.0}

    def _run_outcome(loc):
        if loc == "/t1.json":
            # a classifiably-environmental terminal (host-unreachable) -> retry.
            return {"terminal": "host-unreachable", "phases": [], "readout_pr_link": "",
                    "readout_claimed_checks_green": False, "readout_claimed_pr": "",
                    "failure_kind": "host-unreachable"}
        return {"terminal": "ready", "phases": ["plan", "tasks", "build", "review", "ship"],
                "readout_pr_link": "https://x/pr/1", "readout_claimed_checks_green": True,
                "readout_claimed_pr": "https://x/pr/1"}

    stamps = iter(["s1", "s2"])
    d = _deps(
        launcher=_launcher, run_outcome=_run_outcome,
        materialize=lambda: (lambda s: {"work_item": "wi-%s" % s, "branch": "b-%s" % s,
                                        "pr_title": "PR %s" % s, "stamp": s})(next(stamps)),
    )
    r = run.invoke(d)
    assert r["verdict"] == "pass"                       # the retry succeeded
    # exactly two launches: the second fed attempt-1's consumed budget (remaining, not fresh).
    assert [l["attempt"] for l in launches] == [1, 2]
    assert launches[1]["budget_consumed"]["elapsed_sec"] == 300.0
    assert launches[1]["budget_consumed"]["spend"] == 1.0
    # exactly one record, naming BOTH attempts.
    assert len(d["_state"]["records_written"]) == 1
    rec = d["_state"]["records_written"][0]
    assert rec["retried"] is True
    assert len(rec["attempts"]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_run.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'acceptance_run'`.

- [ ] **Step 3: Write minimal implementation**

Implement `invoke(deps)` wrapping the whole lifecycle in a try/except so any internal error still routes through teardown → fail-verdict-naming-the-error → record write → report. Order: (1) `reclaim_probe` → `acceptance_reclaim.decide`; on `refuse`, return a fail verdict + report naming the in-flight/unconfirmable run, creating nothing; on `reclaim`, run the record-less discovery cleanup and (if `write_orphan_record`) write the orphan's failed record before proceeding. (2) `materialize`. (3) `preflight.decide` on the fixture; a failed preflight → fail-refuse naming the drifted/missing prerequisite. (4) `launcher.run(stamped, budget_consumed=..., attempt=n)` — attempt 1 passes zero/`None` budget; **capture the returned `spend` and `elapsed_sec`** for this attempt; a `killed` outcome → fail naming the tripped ceiling. (5) assemble `facts` from `run_outcome` + `gh_reader` + `expected_phases`; call `acceptance_verdict.decide`. (6) `acceptance_cleanup.plan(discover_artifacts(stamp), run_stamp=stamp)` → `reap`. (7) `write_record` — build the FR-5 record from the verdict + the launcher's `spend`/`elapsed_sec` (for a retried invocation, the aggregate over both attempts) + `retried`/`attempts`; covers all attempts. (8) `release_lease` — **only after** the record write succeeds; if `write_record` raised, skip the release (lease held) and report the write failure. (9) `render_report`. Wire the FR-9 retry: when the verdict is fail and `acceptance_retry.classify` (fed the run-outcome's `failure_kind` + `attempt`) says environmental (attempt 1), clean the first attempt first (if that cleanup fails → no retry, UFR-3 path), re-materialize with a fresh stamp, and relaunch as `launcher.run(stamped2, budget_consumed={"elapsed_sec": <attempt-1 elapsed_sec>, "spend": <attempt-1 spend>}, attempt=2)` — sharing the remaining budget, never a fresh ceiling — then fold both attempts into the single record (`retried: True`, `attempts` with an entry per attempt). Keep every judgment in a decider; the orchestrator only sequences and does I/O.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_run.py -q`
Expected: PASS — every test in `test_acceptance_run.py` green (including the environmental retry-fold covering both attempts and the budget-shared relaunch).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(superheroes): acceptance-harness orchestrator + one-record/one-report lifecycle (#112)"
```

---

### Task 11: Owner front-door skill (`skills/acceptance/SKILL.md`) — the UFR-5 nesting refusal + delegation

**Files:**
- Create: `plugins/superheroes/skills/acceptance/SKILL.md`
- Test: `plugins/superheroes/lib/tests/test_acceptance_skill_contract.py` (a lib-level contract test asserting the skill file's shape + the nesting-refusal helper it relies on)
- Modify (if a new skill requires eval-gate scaffolding — see the #80 memory note): add the skill's activation fixture / activation-result / registry entry / strict-YAML frontmatter that `validate_skills.py` requires. Confirm against `validate_skills.py` in Step 4.

**Interfaces:**
- The skill is a thin control-flow shell: it takes no free-form input (canned fixture — closes UFR-7's no-free-form-input surface), refuses **before any launch or create** when invoked from inside a showrunner/acceptance run (reads the execution-context marker `SUPERHEROES_ACCEPTANCE_CONTEXT` — distinct from `active_run` on-disk state, UFR-5), and otherwise delegates the whole invocation to `acceptance_run.invoke`. It resolves host-neutral actions via the host tool map like every other skill (CONVENTIONS §7).
- Provide a small pure helper `acceptance_run.nesting_refusal(env) -> {"refuse": bool, "reason": str}` the skill and a test both call, so the UFR-5 refusal is unit-tested without a live run.

- [ ] **Step 1: Write the failing test**

```python
# plugins/superheroes/lib/tests/test_acceptance_skill_contract.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_run as run

SKILL = os.path.join(os.path.dirname(__file__), "..", "..", "skills", "acceptance", "SKILL.md")


def test_skill_file_exists_and_declares_frontmatter():
    assert os.path.isfile(SKILL)
    head = open(SKILL, encoding="utf-8").read(400)
    assert head.startswith("---")
    assert "name:" in head and "description:" in head


def test_nesting_refusal_true_inside_a_run():
    r = run.nesting_refusal({"SUPERHEROES_ACCEPTANCE_CONTEXT": "1"})
    assert r["refuse"] is True
    assert "nest" in r["reason"].lower()


def test_nesting_refusal_false_at_top_level():
    r = run.nesting_refusal({})
    assert r["refuse"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_skill_contract.py -q`
Expected: FAIL — the skill file is absent and `nesting_refusal` is undefined.

- [ ] **Step 3: Write minimal implementation**

Add `nesting_refusal(env)` to `acceptance_run.py`: `refuse: True` naming the no-nesting rule when `env.get("SUPERHEROES_ACCEPTANCE_CONTEXT")` is truthy, else `refuse: False`. Author `skills/acceptance/SKILL.md` with strict-YAML frontmatter (`name: superheroes:acceptance`, a description matching the band's skill-description contract per `validate_skills.py`), a body that: states it takes no free-form input; reads the execution-context marker and refuses on nesting before doing anything (UFR-5); runs `preflight` + the fixture drift check (UFR-7) and refuses naming the missing/drifted piece; delegates the whole invocation to `acceptance_run.invoke`; and renders the single verdict report. Cite CONVENTIONS §7 (host tool map) and the escalation base. Keep it within the skill line-count / description-size limits `validate_skills.py` enforces.

- [ ] **Step 4: Run test + validators to verify it passes**

```bash
python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_skill_contract.py -q
python3 .github/scripts/validate_skills.py
```
Expected: the contract test passes; `validate_skills.py` prints OK (the new skill's frontmatter, description size, required phrases, reference links, and CONVENTIONS citation all pass). Fix any validator complaint (add the eval-gate scaffolding the #80 note calls out) until green.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(superheroes): acceptance harness owner front-door skill (#112)"
```

---

### Task 12: Catalog/host wiring + full local gate (all validators + pytest)

**Files:**
- Modify (as the validators require): any manifest/host-map/skill-registry file the new `superheroes:acceptance` skill must appear in for `validate_marketplace.py` / `validate_hosts.py` / `validate_skills.py` to pass. Inspect each validator's expectations and wire exactly what it needs — do not invent surfaces it does not check.
- Verify: the whole new lib surface + the additive enforcer change are collected and green.

**Interfaces:**
- Consumes: everything built in Tasks 1–11.
- Produces: a green tree ready for the producer's review-code + PR — all three validators, the full pytest suite, and the fixture/skill wiring pass.

- [ ] **Step 1: Run the full validator + pytest gate**

```bash
python3 .github/scripts/validate_marketplace.py
python3 .github/scripts/validate_hosts.py
python3 .github/scripts/validate_skills.py
python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ plugins/superheroes/eval/tests/ eval/lib/tests/ -q
```
Expected: all validators print OK; pytest reports all passed — including every new `test_acceptance_*.py` and the extended `test_enforcer.py`.

- [ ] **Step 2: Confirm requirement → test coverage floor**

Verify by inspection that every FR/UFR has a deterministic (no-live-run) test:
FR-1/FR-2 → `test_acceptance_fixture.py` (stamp uniqueness, fixture shape, drift). FR-3/UFR-9 → `test_acceptance_verdict.py` (each false/unreadable fact). FR-4 → `test_acceptance_verdict.py` (consistency mismatches). FR-5 → `test_acceptance_result.py` (required-element rejection, roundtrip) + `test_acceptance_run.py` (record-write-failure holds the lease; one record). FR-6 → `test_acceptance_result.py` (four elements) + `test_acceptance_run.py` (one report). FR-7 → `test_acceptance_cleanup.py` (stamp-scoped reap, non-harness untouched) + `test_acceptance_run.py` (teardown on error/parked). FR-8/UFR-2 → `test_acceptance_ceiling.py` (kill + **invocation-scoped retry-breach** enforcing `ceiling - budget_consumed`) + `test_acceptance_launch.py` (kill + group-empty gate + budget-threaded retry breach + spend/elapsed surfacing). FR-9 → `test_acceptance_retry.py` (classify) + `test_acceptance_run.py` (**environmental retry-fold: two attempts into one record, retry launched with attempt-1's `budget_consumed`**). UFR-1 → `test_acceptance_run.py` (parked). UFR-3 → `test_acceptance_cleanup.py` (leave-behind) + `test_acceptance_result.py`. UFR-4/UFR-8 → `test_acceptance_reclaim.py` + `test_acceptance_run.py` (refuse/reclaim). UFR-5 → `test_acceptance_skill_contract.py` (nesting refusal). UFR-6 → `test_enforcer.py` (deny-only marker across the full owner-authority set + **out-of-scope `in_scope=False` deny from the build worktree, evaluated before the in-scope short-circuit** + allowance-not-honored).

- [ ] **Step 3: Commit any wiring fixes**

```bash
git add -A
git commit -m "chore(superheroes): wire acceptance skill into manifests + green the full gate (#112)"
```

(If Steps 1–2 were already green with nothing to wire, skip the commit.)

---

### Task 13: One live acceptance run (DoD) + issue #112 reshape

**Files:**
- No source change expected. Run the harness end-to-end once, capture the result record + verdict report, and update GitHub issue #112 to the standalone shape.

**Interfaces:**
- Consumes: the complete harness (Tasks 1–12).
- Produces: the DoD evidence — one live end-to-end acceptance run demonstrating a computed verdict, a written result record, and a cleanup that left no fixture PR / branch / working copy / run-state behind; plus issue #112 updated.

- [ ] **Step 1: Invoke the harness once, unattended**

Run the `superheroes:acceptance` skill (or `python3 plugins/superheroes/lib/acceptance_run.py --fixture <committed-fixture> --root "$(git rev-parse --show-toplevel)"`) on the real repo. Let it launch the showrunner on the fixture, judge, and clean up. Do **not** merge anything (the deny-only floor blocks it structurally; verify no owner-authority action succeeded).

- [ ] **Step 2: Verify the DoD facts**

Confirm: exactly one `acceptance-result.json` exists under the harness namespace with all FR-5 elements; the verdict report has all four FR-6 elements; and after the run there is **no** open fixture PR, no fixture branch, no leftover working copy, and no fixture run-state records (`gh pr list` + `git branch -a` + a store scan show nothing carrying the reserved harness prefix). Capture the record + report text for the PR body.

- [ ] **Step 3: Update issue #112 to the standalone shape**

```bash
gh issue edit 112 --title "Standalone showrunner acceptance harness" \
  --body-file <a short standalone-shape description drawn from the spec Purpose>
```
(If the owner prefers to edit #112 by hand, surface the intended text in the hand-back instead — this is the one owner-visible external mutation and it is a non-owner-authority `gh issue edit`, permitted by the enforcer.)

- [ ] **Step 4: Record the DoD evidence for the PR**

Fold the captured verdict report + record path + the "no leftovers" checks into the branch's PR body so the producer's ship hand-back carries the live-run proof.

---

## Self-Review

**Spec coverage:** FR-1 (Task 1 stamp/materialize + Task 9 launch). FR-2 (Task 1 committed one-task/one-file fixture + `expected_phases`). FR-3 (Task 2 verdict facts). FR-4 (Task 2 readout-vs-reality consistency). FR-5 (Task 7 record writer + Task 10 one-record + lease-held-on-write-failure). FR-6 (Task 7 four-element report + Task 10 one-report). FR-7 (Task 5 stamp-scoped plan + Task 10 teardown-on-every-exit incl. harness error). FR-8 (Task 3 ceilings + defaults + invocation-scoped remaining-budget comparison + Task 9 external sampling + budget threaded into the retry launch). FR-9 (Task 4 retry classifier + Task 10 retry fold with budget-shared relaunch + pre-retry-cleanup-fails path). UFR-1 (Task 10 parked terminal). UFR-2 (Task 3 kill + Task 9 group-empty gate). UFR-3 (Task 5 leave-behind + Task 7 record-still-written + Task 10 re-runnable cleanup action). UFR-4 (Task 6 refuse-in-flight + Task 10 creates-nothing). UFR-5 (Task 9 execution-context marker set + Task 11 skill nesting refusal). UFR-6 (Task 8 enforcer deny-only across the full owner-authority set + allowance-not-honored + Task 9 markers set on child + Task 13 live no-merge verification). UFR-7 (Task 1 drift check + Task 11 preflight/drift refusal). UFR-8 (Task 5 record-less discovery + Task 6 reclaim-on-confirmed-death + Task 10 orphan-record-when-none). UFR-9 (Task 2 unreadable-fact fail + Task 4 fail-closed retry). NFRs: Cost-harness (every verdict input a lookup — no model judgment in any decider), Cost-fixture (Task 1 cheapest one-file fixture), Verdict determinism (pure deciders), Unattended (Task 11 no-input skill on the deny-only host), Privacy (Task 7 local-only record/report). DoD (Task 13 live run + #112 reshape; Task 12 no-live-run test floor).

**Type consistency:** every decider returns a plain dict with stable keys (`verdict`/`reason`, `action`/`ceiling`/`remaining`, `retry`/`class`/`reason`, `reap`/`leave_behind`, `action`/`write_orphan_record`); `acceptance_launch.run` returns `{outcome, ceiling, terminal_location, spend_partial, spend, elapsed_sec}` (the last two are the FR-5 record's sole source; `spend` is `None` when unreadable) and accepts `budget_consumed`/`attempt` so a retry enforces the invocation's remaining budget; `acceptance_run.invoke` returns `{verdict, report, record_path}`. `acceptance_fixture.parse_stamp`/`make_stamp`/`RESERVED_PREFIX` are the single source of the stamp shape and are imported by `acceptance_cleanup` (no re-implementation). The enforcement/execution-context env markers (`SUPERHEROES_ACCEPTANCE_DENY_ONLY`, `SUPERHEROES_ACCEPTANCE_CONTEXT`) are named identically in the launcher (set), the enforcer (read), and the skill (read). Every I/O seam in the orchestrator/launcher is injected so all deterministic behavior is proven without a live run (DoD), and Task 13 is the single live exercise.
