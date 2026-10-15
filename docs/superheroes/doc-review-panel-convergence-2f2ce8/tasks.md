---
superheroes: doc
schemaVersion: 1
docType: tasks
workItem: doc-review-panel-convergence-2f2ce8
issue: 397
size: medium
status: approved
gates: {review: passed}
producedBy: "the-architect@0.12.0"
created: "2026-07-12"
updated: "2026-07-12"
---
# Doc-review panel convergence — Tasks

> **Build contract (superheroes).** These tasks are executed by the producer's **Build**
> phase — **not here**. Build invokes superpowers **subagent-driven-development** with the
> worktree **pre-verified, not created**, and **without** `finishing-a-development-branch`;
> the **producer enforces both clips** at invocation. `size: medium`. Advance to Build
> only once `gates.review: passed`.

## Goal

Make document review (plan and tasks) converge instead of running a fixed seven rounds on
findings that never should have blocked. Three defects compose in the current loop and this
work fixes all three: (1) the doc panel is wired `maxRounds: 7`, so the breaker runs rounds
past where the #174 confirmation economics would stop — re-parameterize to a three-round cap
(baseline + two confirmations) that lines up with `MAX_CONFIRMATIONS = 2`; (2) reviewers
apply code-review severity to a design document, so plan-level granularity findings read as
blocking Importants that re-arm the loop — re-frame classification so a finding blocks only
when following the document would mislead the build, routing the rest to a durable hand-off
(plan → tasks) or the run journal (tasks); and (3) the park and journal record almost
nothing — make every boundary legible with a decision-list park, a convergence record, and
acceptance that survives a re-review. The single-source policy libs are shared by the native
showrunner and the interactive `review-plan`/`review-tasks` skills, so changing them once
gives plan-and-tasks parity (FR-13) for free.

Done means: a full-route run whose plan draws incident-class finding volume passes its plan
review within three completed rounds or parks with a readable decision list; the
finer-grained findings that fueled rounds 5–7 land in the tasks hand-off list (and the tasks
author demonstrably receives them) instead of blocking the plan gate; a park's journal event
carries the reason and the decision list; the tasks review shows the same capped, converging
behavior with its non-blocking findings journaled and kept out of build instructions; no
review ever passes with open, unaccepted blocking findings; a resume after a park never
re-asks a decision the owner already made; and every review leaves a convergence record so a
park-wall or demotion-wall shows up in the first runs as data.

## Architecture

Three seams, all inside the existing doc-review path; nothing new sits in the request path of
a code review. **Seam 1 (classification)** adds a `docType`-gated "Document-review severity"
addendum to `rubric/review-base.md`, threaded into the doc reviewer/synthesis framing in
`lib/showrunner.js` and the interactive skills; the keep-on-uncertain synthesis judge
enforces FR-1's fail-closed rule. **Seam 2 (round economics)** adds a `doc_mode` re-arm
parameter to `review_round_policy.confirmation_followup` (any open blocker re-arms, not only
Critical/cross-cutting) — a three-part edit per CONVENTIONS §11 (Python decider + its bundled
JS twin `confirmationFollowup` + `doc_mode` parity fixtures) — threaded through
`_further_confirmation_owed` → `tally_round_decider` → `review_panel_shell.tallyRoundDecider`
→ `runReviewDocPanel`, and drops the doc panel's `maxRounds` from 7 to 3 (both the native
panel and the interactive `loop_state.py --max-rounds`), with a doc-mode carve-out added to
the shared `reference/review-loop.md` contract. **Seam 3 (legibility)** hangs a set of pure
add-on routing/record components off the doc phase: a shared `lib/finding_identity.py` home,
new journal event types, a hand-off writer (`lib/review_handoff.py`), a tasks-leg journal
router, a park composer (`lib/review_park.py`), a convergence recorder, and an acceptance
ledger (`lib/review_acceptance.py`) the re-review consults. Every seam-3 writer fails closed
to disclosure (UFR-1) rather than corrupting the review; all read `round-records.json` and
write through the existing durable channels (`journal.py`, the work-item docs dir resolved by
`definition_doc.resolve_work_item_dir`, the gate writer).

## Tech Stack

Python 3.9+ for the decider/record libs (`lib/*.py`, run as courier-dispatched helpers) and
their pytest suites under `plugins/superheroes/lib/tests/`. Node 18+ for the showrunner
runtime (`lib/showrunner.js`, `lib/review_panel_shell.js`, `lib/review_round_policy.js`) and
its `node --test` smokes, bundled into `lib/showrunner.bundle.js` via
`node lib/bundle_showrunner.js --write`. Markdown for the rubric addendum
(`rubric/review-base.md`), the shared loop contract (`reference/review-loop.md`), the produce
leaf (`eval/produce-leaf.md`), and the interactive skills (`skills/review-plan/SKILL.md`,
`skills/review-tasks/SKILL.md`). JSON for the new on-disk artifacts (`plan-handoff.json`,
`plan-accept.json`/`tasks-accept.json`) and the append-only run journal (`events.jsonl`).
Cross-boundary facts follow CONVENTIONS §11 (single home + parity/drift tests). The
whole-repo gate is `python3 .github/scripts/validate_marketplace.py && python3
.github/scripts/validate_hosts.py && python3 .github/scripts/validate_skills.py && python3 -m
pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ plugins/superheroes/eval/tests/
eval/lib/tests/ -q`.

## Global Constraints

- **Repo root** for every command below is the git top-level
  (`ROOT="$(git rev-parse --show-toplevel)"`); the plugin lib root is
  `plugins/superheroes/lib`. Run pytest from `ROOT`.
- **Three-part edit (CONVENTIONS §11).** Any change to `review_round_policy.confirmation_followup`
  is made in the Python decider, its JS twin `confirmationFollowup`, and the parity fixtures
  under `lib/tests/parity/review_round_policy/confirmationFollowup/` — **never the Python side
  alone** — and the bundle is regenerated (`node lib/bundle_showrunner.js --write`).
- **Code review is untouched.** Every `doc_mode`/`docMode` gate defaults false; the code-review
  re-arm rule, cap, and prose stay exactly as ratified by #174/#382. A test pins each leg's rule.
- **Fail closed.** Ambiguous classification blocks (FR-1); a failed round neither passes nor
  consumes the cap (UFR-2); every new required write discloses on failure (UFR-1); an
  acceptance match fails closed to re-judging (FR-14).
- **No placeholders.** Every step ships real code and a real test command with expected output;
  never a vague back-reference standing in for a concrete step, and never a deferred "add error
  handling later".
- **Commit after each task** with a Conventional-Commit message scoped to `superheroes`, e.g.
  `feat(superheroes): add shared finding-identity home (#397)`.
- **Green bar.** After each task run the tests the task names; before the final commit run the
  whole-repo gate above and confirm it exits 0.

### Task 1: Extract the shared finding-identity home (`lib/finding_identity.py`)

The UFR-3 dedupe key and the FR-14 acceptance trace key are one normalization; per the plan
("one definition, two uses") it moves to a single home imported by the breaker, the hand-off
writer, and the acceptance ledger.

- [ ] Add a failing test `plugins/superheroes/lib/tests/test_finding_identity.py`:

```python
import importlib.util, os

LIB = os.path.join(os.path.dirname(__file__), "..")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_identity_is_file_plus_normalized_clamped_title():
    fi = _load("finding_identity")
    got = fi.finding_identity({"file": "plan.md", "title": "Unauthenticated Access Path!!"})
    assert got == "plan.md::unauthenticated access path"


def test_identity_prefers_title_then_summary_then_empty():
    fi = _load("finding_identity")
    assert fi.finding_identity({"summary": "Data loss on retry"}) == "::data loss on retry"
    assert fi.finding_identity({}) == "::"


def test_circuit_breaker_delegates_to_shared_home():
    fi = _load("finding_identity")
    cb = _load("circuit_breaker")
    f = {"file": "plan.md", "title": "Some Finding — with dashes"}
    assert cb.finding_identity(f) == fi.finding_identity(f)
```

- [ ] Create `plugins/superheroes/lib/finding_identity.py` — move `normalize_title` /
  `finding_label` / `finding_identity` verbatim from `circuit_breaker.py`, **including its
  `re.ASCII` flag** (JS `\w` is ASCII-only; the flag keeps JS/Python parity — dropping it would
  let a non-ASCII title normalize differently in the two languages and silently split an
  identity). `clamp_title` itself is **not** a `circuit_breaker.py` local — it already lives in
  `review_memory.py` as the one clamp every identity surface (including `review_memory.class_key`)
  consumes, and `circuit_breaker.py` today only imports it. Re-export it from the new home so
  `circuit_breaker.py` and the other two consumers get all four names from one import, without
  forking the clamp behavior:

```python
#!/usr/bin/env python3
"""The one deterministic finding-identity normalization (CONVENTIONS §11 single home).

Imported by circuit_breaker (dedupe/recurrence), review_handoff (UFR-3 dedupe), and
review_acceptance (the FR-14 recorded trace key). Reword-sensitive by construction — each
consumer is assigned the failure direction safe for it (see the plan's "Finding identity").

`clamp_title` is re-exported from `review_memory` (its canonical home — also consumed by
`review_memory.class_key`) so every caller here gets the same bounded title everywhere else
in the system uses, rather than a second clamp definition.
"""

import re

from review_memory import clamp_title

_NON_WORD = re.compile(r"[^\w\s]", re.ASCII)   # JS \w is ASCII-only — match it
_WS = re.compile(r"\s+", re.ASCII)


def normalize_title(title):
    t = title.lower()
    t = _NON_WORD.sub("", t)
    t = _WS.sub(" ", t)
    return t.strip()


def finding_label(finding):
    return finding.get("title") or finding.get("summary") or ""


def finding_identity(finding):
    return f"{finding.get('file') or ''}::{normalize_title(clamp_title(finding_label(finding)))}"
```

- [ ] In `plugins/superheroes/lib/circuit_breaker.py` replace the local
  `normalize_title` / `finding_label` / `finding_identity` definitions, and the direct
  `clamp_title` import from `review_memory`, with a single import from the shared home, keeping
  the module's public names intact so every existing caller (and `recurrence_key`) still works:

```python
from review_memory import canonical_class_key, class_key_aliases
from finding_identity import (
    clamp_title, normalize_title, finding_label, finding_identity,
)
```

  Delete the now-duplicated `_NON_WORD`/`_WS` and the three moved functions (`normalize_title`,
  `finding_label`, `finding_identity`) from `circuit_breaker.py`. Leave `is_blocking` /
  `is_critical` / `recurrence_key` where they are.
- [ ] Run: `cd "$ROOT" && python3 -m pytest plugins/superheroes/lib/tests/test_finding_identity.py plugins/superheroes/lib/tests/test_circuit_breaker.py -q`.
  Expected: all pass (the existing circuit-breaker tests stay green because the identity output
  is byte-identical — `clamp_title` is untouched, only re-exported through a new module).
- [ ] Commit: `refactor(superheroes): single home for finding-identity normalization (#397)`.

### Task 2: Add the three new journal event types + drift guard

FR-4/FR-3/FR-15 write new event kinds; `journal.append` fail-closes on unknown types, so the
`EVENT_TYPES` set is the single source and the renderers must know the same names.

- [ ] Add a failing test to `plugins/superheroes/lib/tests/test_journal.py`:

```python
def test_new_doc_review_event_types_are_accepted(tmp_path):
    import importlib.util, os
    lib = os.path.join(os.path.dirname(__file__), "..")
    spec = importlib.util.spec_from_file_location("journal", os.path.join(lib, "journal.py"))
    journal = importlib.util.module_from_spec(spec); spec.loader.exec_module(journal)
    events = str(tmp_path / "events.jsonl")
    for et in ("routed_forward", "review_convergence", "handoff_provided"):
        journal.append(events, et, payload={"doc": "plan"}, root=str(tmp_path))
    kinds = [e.get("type") for e in journal.read_events(events)]
    assert kinds == ["routed_forward", "review_convergence", "handoff_provided"]
```

- [ ] In `plugins/superheroes/lib/journal.py` add the three names to the `EVENT_TYPES` set
  (additive; no `schemaVersion` bump — matches the existing precedent noted in the set's
  comments), each with a one-line comment naming the FR it serves:

```python
    # #397 doc-review legibility: a tasks-review non-blocking finding routed to the journal
    # (FR-4), never into build instructions (FR-5). Structured non-secret payload, written as-is.
    "routed_forward",
    # #397 FR-15: the per-review convergence record — rounds used, per-round blocking vs
    # routed-forward counts, and the outcome — at every doc-review terminal.
    "review_convergence",
    # #397 FR-3 receipt: the tasks phase journaled that it was handed the plan review's
    # hand-off list (or, per UFR-5, that it could not be read).
    "handoff_provided",
```

- [ ] Find every renderer that enumerates event types (`run_watch.py`, `run_readout.py` — NOT
  `readout.py`, which only holds the `scrub`/`build_readout` seam and has no event-type map) and
  add the three names to their known-type maps so the drift test that asserts "renderers know
  the `EVENT_TYPES` names" passes. Locate them:
  `grep -rln "EVENT_TYPES\|phases_skipped\|final_review_handoff" plugins/superheroes/lib/*.py`
  then add a plain-language label for each new type in the same table the others live in.
- [ ] If a `test_ssot_drift.py` case enumerates `EVENT_TYPES` against the renderers, extend its
  copy-holder list to include the new names; otherwise add a drift test asserting the renderer's
  known-type set is a superset of `journal.EVENT_TYPES`.
- [ ] Run: `cd "$ROOT" && python3 -m pytest plugins/superheroes/lib/tests/test_journal.py plugins/superheroes/lib/tests/test_ssot_drift.py plugins/superheroes/lib/tests/test_run_watch.py -q`.
  Expected: all pass.
- [ ] Commit: `feat(superheroes): journal vocabulary for doc-review routing + convergence (#397)`.

### Task 3: Add the "Document-review severity" rubric addendum

FR-1's blocking bar lives in the rubric (model judgment, second-gated by the synthesis
judge), keyed to `docType` so it applies only to plan/tasks reviews and leaves code review
untouched.

- [ ] Add a failing test to `plugins/superheroes/lib/tests/test_skill_shape.py` (or a new
  `test_review_base_rubric.py`) asserting the addendum and the version bump exist:

```python
def test_review_base_has_doc_severity_addendum():
    import os
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    text = open(os.path.join(root, "plugins/superheroes/rubric/review-base.md"), encoding="utf-8").read()
    assert "<!-- rubric-version: 6 -->" in text
    assert "## Document-review severity" in text
    # docType-gated, states the plan-vs-tasks asymmetry and the fail-closed rule
    assert "docType" in text and "plan" in text and "tasks" in text
    assert "granularity" in text.lower()
    assert "ambiguity" in text.lower() or "fail closed" in text.lower()
    # the incident-anchored "always blocking" security carve-out must not be silently dropped —
    # it is the one clause protecting genuine security findings from demotion into the hand-off
    assert "unauthenticated" in text.lower()
    assert "security exemption" in text.lower() and "corrupt or lose data" in text.lower()
```

- [ ] In `plugins/superheroes/rubric/review-base.md` bump the header `<!-- rubric-version: 5 -->`
  → `<!-- rubric-version: 6 -->` (the staleness signal) and add a new section after
  `## Severity caps`:

```markdown
## Document-review severity (applies only when `docType` is `plan` or `tasks`)

This section **overrides the severity tiers above for document reviews only**. It does not
apply to code review (`docType` absent). A document is not code: judge every finding against
the reviewed document's **own job**, not against code-review severity.

**Blocking bar (FR-1).** A finding is **blocking** only if *following the document as written
would mislead the build or cause it to build something unsafe or incorrect*, judged against
the document's own job. Everything else is **non-blocking** and routes forward — it never
blocks the gate and never re-arms the loop.

**Plan vs tasks asymmetry.**
- In a **plan** review, task- and test-*specification granularity* is **non-blocking**:
  "no named unit test for this option", "this value appears as two separate literals", "this
  test doesn't pin a controlled clock" — specifying tasks and tests is the *tasks* document's
  job, not the plan's. Route these to the hand-off list.
- In a **tasks** review, a finding that the tasks document *mis-specifies a task or test the
  build will follow* is judged **directly against the bar** — never categorically demoted as
  "specification granularity" — because the tasks document is the build's contract.

**Always blocking (incident-anchored).** A finding of the class that legitimately blocked
round 1 of the 2026-07-12 incident run — an unauthenticated access path, a required security
exemption missing, a design that would corrupt or lose data — is **blocking** in either
document.

**Ambiguity fails closed.** A finding you cannot confidently place on either side of the bar
is **blocking**. A wrongly-demoted real blocker is invisible; a wrongly-promoted one costs at
most a readable park the owner can rule on. Example: "the plan's error-handling approach *may
be insufficient*" without naming what would break cannot be confidently placed — so it blocks.

*Few-shot anchors (2026-07-12 incident corpus).* Blocking (its round-1 findings): an
unauthenticated write path; a missing security-exemption the design required; a data-model
that would drop records on a concurrent edit. Non-blocking on a **plan** (its rounds 5–7
findings, which fueled the treadmill): "no named unit test for the fallback branch"; "the
retry constant is written twice as two literals"; "this test description doesn't specify a
frozen clock". On a **tasks** doc those same three ARE judged against the bar.
```

- [ ] Run: `cd "$ROOT" && python3 -m pytest plugins/superheroes/lib/tests/ -k "review_base or skill_shape or skill_markdown" -q && python3 .github/scripts/validate_skills.py`.
  Expected: pass (validate_skills.py checks rubric/skill token-shape; the addendum stays within
  its size envelope).
- [ ] Commit: `feat(superheroes): document-review severity addendum in review-base rubric (#397)`.

### Task 4: Thread the doc-severity framing into the native doc reviewer + synthesis leaves

The addendum only bites if the doc reviewer and synthesis judge are told to apply it. Both
leaves live in `lib/showrunner.js`.

- [ ] Add a smoke `plugins/superheroes/lib/tests/showrunner_doc_severity_frame_smoke.js`
  (registered in Task 12's node-smoke wiring) that stubs `globalThis.agent`, drives
  `docReviewerAgent` and `docSynthesisLeaf`, and asserts the prompt each dispatches names the
  document-severity rule:

```js
const assert = require('node:assert')
const test = require('node:test')
const sr = require('../showrunner.js')

test('doc reviewer + synthesis prompts carry the document-severity bar', async () => {
  const prompts = []
  globalThis.agent = async (prompt, opts) => {
    prompts.push(prompt)
    return opts && opts.label && opts.label.startsWith('synthesis')
      ? { verdicts: [] } : { findings: [] }
  }
  globalThis.__SR_OVERRIDES = null
  await sr.docReviewerAgent('architecture-reviewer',
    { docType: 'plan', docPath: 'plan.md' }, 'review-base', '/tmp/x', 1, {})
  await sr.docSynthesisLeaf([], { docType: 'plan', docPath: 'plan.md' }, 'review-base', '/tmp/x', 1)
  assert.ok(prompts.every((p) => /document-review severity|blocking bar|follow(ing)? the document/i.test(p)),
    'both doc leaves must steer to the document-severity rule')
})
```

- [ ] In `lib/showrunner.js` add a shared constant near the other reviewer instruction
  constants and splice it into both `docReviewerAgent` and `docSynthesisLeaf` prompts (the two
  functions read earlier at lines ~674 and ~691). Export `docReviewerAgent`/`docSynthesisLeaf`
  for the smoke:

```js
// #397 FR-1: the document-severity steering both doc leaves carry. A document is judged
// against its OWN job — a plan-level task/test granularity finding is non-blocking on a plan;
// ambiguity fails closed to blocking; the incident-anchored classes always block.
const DOC_SEVERITY_FRAME =
  'Apply the "Document-review severity" section of the rubric: classify a finding BLOCKING ' +
  'only if following this document as written would mislead the build or make it build ' +
  'something unsafe or incorrect, judged against this document\'s own job. In a PLAN review, ' +
  'task/test specification-granularity is NON-BLOCKING (it is the tasks doc\'s job). In a ' +
  'TASKS review, a mis-specified task/test is judged directly against the bar. Ambiguity ' +
  'fails closed to BLOCKING.'
module.exports.DOC_SEVERITY_FRAME = DOC_SEVERITY_FRAME
```

  In `docReviewerAgent`, append ` ${DOC_SEVERITY_FRAME}` to the review instruction string
  (before `Prompt context:`). In `docSynthesisLeaf`, append it after the
  `(plugins/superheroes/eval/synthesis-leaf.md)` clause so the keep-on-uncertain judge applies
  the same bar. Add the two `module.exports.docReviewerAgent = docReviewerAgent` /
  `module.exports.docSynthesisLeaf = docSynthesisLeaf` lines next to the existing
  `runReviewDocPanel` export.
- [ ] **`docSection` producer.** Tasks 14/18/20/21 all read a finding's `docSection`/
  `planSection`, but nothing upstream sets or preserves it — add the one producer here, at
  synthesis time, and keep it alive through skeleton persistence, so every doc-review finding
  the panel emits carries it from birth to disk:
  - In `FINDINGS_SCHEMA` (`lib/showrunner.js`, the `findings.items.properties` object shared by
    `docReviewerAgent` and the code-review reviewer dispatch), add
    `docSection: { type: 'string' }` — additive and optional, so code review (which never sets
    it) is unaffected.
  - Extend `DOC_SEVERITY_FRAME` (same constant edited above) with: `' For a document review,
    also set each finding's "docSection" to the exact markdown heading (verbatim subsection
    title) it concerns; use "docSection": null only when the finding genuinely spans more than
    one subsection or is structural.'` — the reviewer already reads the doc to write the
    finding, so naming the heading it just read costs nothing extra.
  - The doc-panel merge is `compileFindings` — a **registered parity twin** (`lib/panel_tally.js`
    + `lib/panel_tally.py::compile_findings`, pinned by `PARITY_TWINS` in
    `lib/tests/test_parity.py`). Its `Object.assign({}, f)` / dict-copy already passes
    `docSection` through on fresh entries (once sub-edit 1 admits it through `FINDINGS_SCHEMA`);
    the drop risk is the **dedupe-merge branch**, where the severity-winner may lack `docSection`
    while the other twin of the same finding carries it. In **both implementations**, after the
    winner is chosen, preserve `docSection` from either record when the winner lacks it (the same
    shape as the existing `dimension` union). The synthesis judge revises severity/action, never
    section attribution — this is a pass-through, not new judgment.
  - Pin the pass-through with a new parity fixture
    `lib/tests/parity/panel_tally/compileFindings/06_docsection_passthrough.json` — it runs
    against BOTH twins via the existing parity suite, so a silent `docSection` drop in either
    implementation turns CI red (no other test in this document drives `docSection` through the
    JS merge):

```json
{"input": [[{"file": "plan.md", "line": 10, "title": "Same finding", "severity": "Minor", "dimension": "Code", "evidence": "repro", "docSection": "## Architecture"}, {"file": "plan.md", "line": 10, "title": "Same finding", "severity": "Important", "dimension": "Security", "evidence": "repro"}]], "expected": [{"classification": "mechanical", "dimension": "Code + Security", "docSection": "## Architecture", "evidence": "repro", "file": "plan.md", "line": 10, "severity": "Important", "title": "Same finding"}]}
```
  - In `plugins/superheroes/lib/review_memory.py`, add `"docSection"` to the `_SKELETON_FIELDS`
    tuple `_skeleton_finding` reads. Without this, `summarize_record`/`persist_record` silently
    strip `docSection` before a finding ever reaches `round-records.json`, and Tasks 14/18/20/21
    would read `None` off a real run despite the reviewer having set it. Add a case to
    `plugins/superheroes/lib/tests/test_review_memory.py` asserting a finding carrying
    `docSection` survives `summarize_record` unchanged (mirror
    `test_persist_skeleton_strips_bodies_python_side`'s fixture shape).
  - `section_hash` (Task 20) already normalizes via `finding_identity.normalize_title` before
    comparing, and falls back to the whole-doc hash on no match — an approximately-quoted
    heading degrades safely to "re-judge", never a false accept.
- [ ] Regenerate the bundle: `cd "$ROOT" && node plugins/superheroes/lib/bundle_showrunner.js --write`.
- [ ] Run: `cd "$ROOT" && node --test plugins/superheroes/lib/tests/showrunner_doc_severity_frame_smoke.js && python3 -m pytest plugins/superheroes/lib/tests/test_bundle_drift.py plugins/superheroes/lib/tests/test_review_memory.py plugins/superheroes/lib/tests/test_parity.py -q`.
  Expected: pass (the parity suite exercises the new `06_docsection_passthrough` fixture against
  both `compileFindings` twins).
- [ ] Commit: `feat(superheroes): steer native doc reviewer + synthesis to the doc-severity bar (#397)`.

### Task 5: Add the `doc_mode` re-arm to the Python decider `confirmation_followup`

Seam 2 core: in `doc_mode`, **any** open blocker (Critical **or** Important) re-arms the one
further confirmation, and at the cap the doc review **always parks** (there is no cheap scoped
tier for documents — Never-auto-pass constraint). The cap and interface stay identical.

- [ ] Add failing unit tests to `plugins/superheroes/lib/tests/test_review_round_policy.py`:

```python
def test_doc_mode_important_under_cap_rearms():
    out = RP.confirmation_followup(["Important"], 1, False, doc_mode=True)
    assert out == {"rearm": True, "park": False, "atCap": False,
                   "reason": "open blocking finding in doc review — one more full confirmation panel required"}


def test_doc_mode_important_at_cap_parks():
    out = RP.confirmation_followup(["Important"], 2, False, doc_mode=True)
    assert out["rearm"] is False and out["park"] is True and out["atCap"] is True


def test_doc_mode_nothing_open_no_rearm():
    out = RP.confirmation_followup([], 1, False, doc_mode=True)
    assert out == {"rearm": False, "park": False, "atCap": False,
                   "reason": "no open blocking finding — doc review certifies"}


def test_doc_mode_critical_at_cap_parks():
    out = RP.confirmation_followup(["Critical"], 2, False, doc_mode=True)
    assert out["park"] is True and out["atCap"] is True


def test_code_mode_unchanged_important_at_cap_scoped_verify():
    # regression guard: code review's rule is untouched — a non-Critical, non-cross-cutting finding
    # at the cap certifies via scoped verify. `cross_cutting=False` exercises the actual early
    # `not trigger` return; passing True here would instead exercise the cross-cutting-at-cap branch,
    # which happens to produce the same {park, rearm, atCap} values and so would silently pass even
    # if the `not trigger` branch regressed.
    out = RP.confirmation_followup(["Important"], 2, False)
    assert out["park"] is False and out["rearm"] is False and out["atCap"] is True
```

- [ ] In `plugins/superheroes/lib/review_round_policy.py` add the keyword parameter and the
  doc-mode branch to `confirmation_followup`. Doc mode uses `is_blocking` (any open blocker),
  not `is_critical`; it never scoped-verify-certifies at the cap:

```python
def confirmation_followup(surfaced_severities, confirmations_run, cross_cutting,
                          max_confirmations=MAX_CONFIRMATIONS, doc_mode=False):
    """#174 confirmation-bar economics — the follow-up decision after a FULL confirmation panel.

    `doc_mode` (FR-8): a document review has no cheap scoped tier, so ANY open blocking finding
    (Critical OR Important) re-arms the one further confirmation, and at the cap the review
    ALWAYS parks (never auto-passes — the Never-auto-pass constraint). Code review's rule is
    unchanged when doc_mode is False.

    Returns {rearm, park, atCap, reason} — deterministic; the caller schedules another full
    confirmation iff `rearm`, and withholds certification (parks) iff `park`."""
    sevs = [s for s in (surfaced_severities or []) if isinstance(s, str)]
    at_cap = confirmations_run >= max_confirmations
    if doc_mode:
        has_blocking = any(circuit_breaker.is_blocking(s) for s in sevs)
        if not has_blocking:
            return {"rearm": False, "park": False, "atCap": at_cap,
                    "reason": "no open blocking finding — doc review certifies"}
        if at_cap:
            return {"rearm": False, "park": True, "atCap": True,
                    "reason": "open blocking finding at the doc-review round cap — park; "
                              "certification withheld"}
        return {"rearm": True, "park": False, "atCap": False,
                "reason": "open blocking finding in doc review — one more full confirmation "
                          "panel required"}
    # #291: case-normalized Critical match — a surfaced mis-cased `critical` must still park at the cap.
    has_critical = any(circuit_breaker.is_critical(s) for s in sevs)
    trigger = has_critical or bool(cross_cutting)
    if not trigger:
        return {"rearm": False, "park": False, "atCap": at_cap,
                "reason": "non-Critical findings, rework not cross-cutting — resolve by scoped "
                          "verify; no further confirmation panel"}
    if at_cap:
        if has_critical:
            return {"rearm": False, "park": True, "atCap": True,
                    "reason": "Critical surfaced at the confirmation-panel cap — park; "
                              "certification withheld"}
        return {"rearm": False, "park": False, "atCap": True,
                "reason": "confirmation-panel cap reached — resolve remaining by scoped verify; "
                          "no further panel"}
    return {"rearm": True, "park": False, "atCap": False,
            "reason": ("Critical surfaced by confirmation" if has_critical else "cross-cutting "
                       "rework") + " — one more full confirmation panel required"}
```

- [ ] Run: `cd "$ROOT" && python3 -m pytest plugins/superheroes/lib/tests/test_review_round_policy.py -q`.
  Expected: pass (new doc-mode tests + all existing code-mode tests).
- [ ] Commit: `feat(superheroes): doc_mode re-arm on any open blocker in confirmation_followup (#397)`.

### Task 6: Mirror `doc_mode` into the JS twin + regenerate the bundle

CONVENTIONS §11 three-part edit: the Python decider has a hand-maintained JS twin bundled into
`showrunner.bundle.js`. Keep them byte-parity.

- [ ] In `plugins/superheroes/lib/review_round_policy.js` add the `docMode = false` parameter
  and the mirrored branch to `confirmationFollowup`, using `isBlocking` for the doc-mode gate:

```js
function confirmationFollowup(surfacedSeverities, confirmationsRun, crossCutting,
  maxConfirmations = MAX_CONFIRMATIONS, docMode = false) {
  const sevs = (surfacedSeverities || []).filter((s) => typeof s === 'string')
  const atCap = confirmationsRun >= maxConfirmations
  if (docMode) {
    const hasBlocking = sevs.some((s) => isBlocking(s))
    if (!hasBlocking) {
      return { rearm: false, park: false, atCap,
        reason: 'no open blocking finding — doc review certifies' }
    }
    if (atCap) {
      return { rearm: false, park: true, atCap: true,
        reason: 'open blocking finding at the doc-review round cap — park; certification withheld' }
    }
    return { rearm: true, park: false, atCap: false,
      reason: 'open blocking finding in doc review — one more full confirmation panel required' }
  }
  // #291: case-normalized Critical match — a surfaced mis-cased `critical` must still park at the cap.
  const hasCritical = sevs.some((s) => isCritical(s))
  const trigger = hasCritical || !!crossCutting
  if (!trigger) {
    return { rearm: false, park: false, atCap,
      reason: 'non-Critical findings, rework not cross-cutting — resolve by scoped verify; no further confirmation panel' }
  }
  if (atCap) {
    if (hasCritical) {
      return { rearm: false, park: true, atCap: true,
        reason: 'Critical surfaced at the confirmation-panel cap — park; certification withheld' }
    }
    return { rearm: false, park: false, atCap: true,
      reason: 'confirmation-panel cap reached — resolve remaining by scoped verify; no further panel' }
  }
  return { rearm: true, park: false, atCap: false,
    reason: (hasCritical ? 'Critical surfaced by confirmation' : 'cross-cutting rework') + ' — one more full confirmation panel required' }
}
```

- [ ] At the top of `review_round_policy.js` extend the require to also pull `isBlocking`:
  `const { isCritical, isBlocking } = require('./circuit_breaker.js')`. Confirm
  `circuit_breaker.js` exports `isBlocking`
  (`grep -n "isBlocking" plugins/superheroes/lib/circuit_breaker.js`); if not, add it to that
  module's `module.exports` mirroring the Python `is_blocking`.
- [ ] Regenerate the bundle: `cd "$ROOT" && node plugins/superheroes/lib/bundle_showrunner.js --write`.
- [ ] Run the JS oracle + bundle drift: `cd "$ROOT" && python3 -m pytest plugins/superheroes/lib/tests/test_bundle_drift.py -q && node -e "const {confirmationFollowup}=require('./plugins/superheroes/lib/review_round_policy.js'); const a=confirmationFollowup(['Important'],1,false,undefined,true); if(!a.rearm) process.exit(1); const b=confirmationFollowup(['Important'],2,false,undefined,true); if(!b.park) process.exit(1); console.log('ok')"`.
  Expected: prints `ok`, bundle drift passes.
- [ ] Commit: `feat(superheroes): doc_mode re-arm in the JS confirmationFollowup twin + bundle (#397)`.

### Task 7: Pin the `doc_mode` rule with parity fixtures

The fixture-driven parity suite (`test_parity.py`, `PARITY_TWINS` registers
`confirmationFollowup`) runs both implementations against shared fixtures. The
`confirmationFollowup` fixture calls carry a 5th positional `docMode` arg.

- [ ] Add fixtures under
  `plugins/superheroes/lib/tests/parity/review_round_policy/confirmationFollowup/`, one per
  file, matching the existing `NN_name.json` shape (`{"input": [...], "expected": {...}}`).
  First confirm the parity runner passes positional args through to both twins
  (`sed -n '1,60p' plugins/superheroes/lib/tests/parity_runner.js` and the oracle in
  `test_parity.py` lines ~141–180); the input array is the positional argument list, so a
  doc-mode case is `[surfaced, confirmationsRun, crossCutting, maxConfirmations, docMode]`:

  `09_doc_mode_important_under_cap_rearm.json`:
```json
{"input": [["Important"], 1, false, 2, true], "expected": {"rearm": true, "park": false, "atCap": false, "reason": "open blocking finding in doc review — one more full confirmation panel required"}}
```
  `10_doc_mode_important_at_cap_park.json`:
```json
{"input": [["Important"], 2, false, 2, true], "expected": {"rearm": false, "park": true, "atCap": true, "reason": "open blocking finding at the doc-review round cap — park; certification withheld"}}
```
  `11_doc_mode_nothing_open_certify.json`:
```json
{"input": [[], 1, false, 2, true], "expected": {"rearm": false, "park": false, "atCap": false, "reason": "no open blocking finding — doc review certifies"}}
```
  `12_doc_mode_critical_at_cap_park.json`:
```json
{"input": [["Critical"], 2, false, 2, true], "expected": {"rearm": false, "park": true, "atCap": true, "reason": "open blocking finding at the doc-review round cap — park; certification withheld"}}
```

- [ ] Verify the existing code-mode fixtures (`01`–`08`) still pass unchanged — their inputs
  omit the 5th arg, which defaults `docMode`/`doc_mode` to false in both twins, so their
  expectations are untouched.
- [ ] Run: `cd "$ROOT" && python3 -m pytest plugins/superheroes/lib/tests/test_parity.py -q`.
  Expected: pass (both the JS-twin oracle and the Python oracle run every fixture, including the
  four doc-mode cases).
- [ ] Commit: `test(superheroes): doc_mode parity fixtures pin the Python+JS re-arm rule (#397)`.

### Task 8: Thread `doc_mode` through the Python tally decider AND the round-scheduling decider

`tally_round_decider` folds the confirmation economics via `_further_confirmation_owed`, which
calls `confirmation_followup` — that is the tally-side (verdict-after-the-round) consumer.
**`_further_confirmation_owed` has a SECOND caller: `_confirmation_ready` (line ~252), the
round-SCHEDULING decider that `plan_round_decider` uses to decide whether the round about to
run IS the full confirmation panel.** If only the tally side learns `doc_mode`, the two
deciders disagree in doc mode: tally correctly refuses to certify with an open Important, but
`_confirmation_ready` — still asking `confirmation_followup` the code-mode question ("was this
Critical or cross-cutting?") — answers `owed: false` for a plain Important and never schedules
the full panel that was supposed to resolve it, so the run stalls without ever running the
confirmation round tally is waiting on. Both callers of `_further_confirmation_owed` need the
flag, carried from the same new CLI option.

- [ ] Add a failing test to `plugins/superheroes/lib/tests/test_review_loop_plan.py` that, with
  a round-records fixture holding a marked-pending clean round plus one open Important surfaced
  since the last qualifying panel, asserts `doc_mode=True` parks where the default certifies.
  Build the fixture with the module's existing helpers (mirror the confirmation-economics tests
  already in that file), then:

```python
def test_tally_doc_mode_parks_on_open_important_at_cap(tmp_path):
    # Two qualifying confirmation panels have run (rounds 2 and 4); the second surfaces a plain
    # Important (not Critical, not cross-cutting — changedSubjects stays a single "Code" the whole
    # way). Code mode resolves it by scoped verify; doc mode has no scoped-verify tier and must
    # park (Never-auto-pass) on the same open Important at the confirmation cap.
    important = [{"title": "spec gap", "file": "a.js", "severity": "Important", "dimension": "Code"}]
    recs = [
        _skeleton_round(1, {n: _dim() for n in FULL_ROSTER}, changed_subjects=["Code"]),
        _skeleton_round(2, {n: _dim() for n in FULL_ROSTER}, kind="confirmation",
                        confirmation_pending=True, changed_subjects=["Code"]),
        _skeleton_round(3, {n: _dim() for n in FULL_ROSTER}, kind="intermediate",
                        changed_subjects=["Code"]),
        # second qualifying confirmation panel that surfaces the open Important
        _skeleton_round(4, dict({n: _dim() for n in FULL_ROSTER},
                                **{"code-reviewer": _dim(findings=important)}),
                        kind="confirmation", confirmation_pending=True, changed_subjects=["Code"]),
        _skeleton_round(5, {n: _dim() for n in FULL_ROSTER}, kind="intermediate",
                        changed_subjects=["Code"]),
    ]
    records_path = _write_records(tmp_path, recs)
    # code mode (default): a non-Critical at the cap resolves by scoped verify -> not halted
    code = _tally(records_path, 5, roster=FULL_ROSTER, gate="clean", present_blocking=0)
    assert code["terminal"] != "halted"
    # doc mode: the same open Important at the cap PARKS (Never-auto-pass)
    doc = _tally(records_path, 5, roster=FULL_ROSTER, gate="clean", present_blocking=0,
                doc_mode=True)
    assert doc["terminal"] == "halted"


def test_plan_round_doc_mode_schedules_confirmation_for_open_important(tmp_path):
    # Through the SCHEDULING decider this time (not tally): one qualifying confirmation panel has
    # already run (round 1), then an intermediate round 2 surfaces a plain (non-Critical,
    # non-cross-cutting) open Important. At round 3, code mode does not owe a further confirmation
    # (a plain Important doesn't re-arm) — but doc mode does (any open blocker re-arms), the exact
    # disagreement a doc_mode-blind `_confirmation_ready` would produce.
    important = [{"title": "spec gap", "file": "a.js", "severity": "Important", "dimension": "Code"}]
    recs = [
        _skeleton_round(1, {n: _dim() for n in FULL_ROSTER}, kind="confirmation",
                        confirmation_pending=True, changed_subjects=["Code"]),
        _skeleton_round(2, dict({n: _dim() for n in FULL_ROSTER},
                                **{"code-reviewer": _dim(findings=important)}),
                        kind="intermediate", changed_subjects=["Code"]),
    ]
    records_path = _write_records(tmp_path, recs)
    code = rlp.plan_round_decider(records_path, 3, FULL_ROSTER, ["Code"], just_marked=False)
    assert code["enterConfirmation"] is False   # code mode: a plain Important doesn't re-arm
    doc = rlp.plan_round_decider(records_path, 3, FULL_ROSTER, ["Code"], just_marked=False,
                                 doc_mode=True)
    assert doc["enterConfirmation"] is True      # doc mode: any open blocker re-arms the panel
```

- [ ] In `plugins/superheroes/lib/review_loop_plan.py`:
  - Give `_further_confirmation_owed(records, doc_mode=False)` the flag and pass it through:
    `followup = review_round_policy.confirmation_followup(surfaced, len(qualifying),
    review_round_policy.is_cross_cutting(_rework_across(since)), doc_mode=doc_mode)`.
  - Give `tally_round_decider(..., doc_mode=False)` the keyword and pass it at the one
    `_further_confirmation_owed(records)` call inside the `marked_pending` branch:
    `owe = _further_confirmation_owed(records, doc_mode=doc_mode)`.
  - Give `_confirmation_ready(records, round_no, just_marked, doc_mode=False)` the same flag and
    pass it at ITS `_further_confirmation_owed(records)` call (line ~252):
    `if not _further_confirmation_owed(records, doc_mode=doc_mode)["owed"]: return False`.
  - Give `plan_round_decider(..., doc_mode=False)` the keyword and pass it at its
    `_confirmation_ready(records, round_no, just_marked)` call:
    `enter_confirmation = _confirmation_ready(records, round_no, just_marked, doc_mode=doc_mode)`.
  - In `_build_parser()` add `--doc-mode` (`action="store_true"`) to **both** the `plan-round`
    subparser and the `tally-round` subparser, and in `main()` pass `doc_mode=args.doc_mode` into
    both `plan_round_decider(...)` and `tally_round_decider(...)`.
- [ ] Run: `cd "$ROOT" && python3 -m pytest plugins/superheroes/lib/tests/test_review_loop_plan.py -q`.
  Expected: pass.
- [ ] Commit: `feat(superheroes): thread doc_mode through both the tally AND round-scheduling deciders + CLI (#397)`.

### Task 9: Thread `docMode` + `maxRounds: 3` through the panel shell and the doc panel

The JS shell must pass `--doc-mode` to **both** the tally CLI and the plan-round CLI (Task 8
added `--doc-mode` to both `plan-round` and `tally-round`, since `_confirmation_ready` — the
round-SCHEDULING decider — needs it just as much as the tally-side verdict does) when the leg
is a doc leg, and the doc panel must run at `maxRounds: 3`.

- [ ] Add a smoke `plugins/superheroes/lib/tests/showrunner_doc_cap_smoke.js` (registered in
  Task 12) that captures the argv `tallyRoundDecider` AND `planRoundDecider` build and asserts
  `--doc-mode` is present on both (and `--max-rounds 3` on the tally call) when `legKind.docMode`
  is set, and absent for a code leg. Drive it through the exported deciders with a fake
  `ioApi.runHelper` that records `args`:

```js
const assert = require('node:assert')
const test = require('node:test')
const shell = require('../review_panel_shell.js')

test('doc leg tally passes --doc-mode and max-rounds 3', async () => {
  let captured = null
  const ioApi = { join: (...p) => p.join('/'),
    runHelper: async (_bin, args) => { captured = args; return '{"terminal":"clean"}' } }
  await shell.tallyRoundDecider({ runDir: '/tmp/r', round: 1, roster: ['a'], maxRounds: 3,
    gate: 'clean', confidence: 'high', missing: [], presentBlocking: 0, fixStatus: 'completed',
    verifyResult: null, enterConfirmation: false, ioApi, docMode: true })
  assert.ok(captured.includes('--doc-mode'), 'doc leg must pass --doc-mode')
  const i = captured.indexOf('--max-rounds'); assert.strictEqual(captured[i + 1], '3')
})

test('doc leg plan-round ALSO passes --doc-mode (the round-scheduling decider, not just tally)', async () => {
  let captured = null
  const ioApi = { join: (...p) => p.join('/'),
    runHelper: async (_bin, args) => { captured = args; return '{"ok":true,"enterConfirmation":false,"dimensions":{},"carried":{},"latestCoverageDecisionIds":[]}' } }
  await shell.planRoundDecider({ runDir: '/tmp/r', round: 1, roster: ['a'],
    changedSubjects: null, justMarked: false, coverageTarget: null, ioApi, docMode: true })
  assert.ok(captured.includes('--doc-mode'), 'doc leg plan-round must ALSO pass --doc-mode')
})
```

- [ ] In `plugins/superheroes/lib/review_panel_shell.js`:
  - `tallyRoundDecider({ ..., docMode })`: after the `--fix-status` push, add
    `if (docMode) args.push('--doc-mode')`.
  - `planRoundDecider({ ..., docMode })`: after the `--just-marked` push, add
    `if (docMode) args.push('--doc-mode')` — the same flag, required because
    `_confirmation_ready` (the round-scheduling decider `plan_round_decider` calls) reads
    `doc_mode` independently of the tally decider (Task 8).
  - `tallyRound(...)`: accept `docMode` (thread from `legKind.docMode`) and pass it into every
    `tallyRoundDecider({ ... })` call it makes.
  - In `reviewPanel(...)`, at each `tallyRound({ ... })` call site, pass
    `docMode: legKind && legKind.docMode`, and at the `planRoundDecider({ ... })` call site
    (inside the round loop, non-`entryPlan` branch) also pass
    `docMode: legKind && legKind.docMode`.
  - In `gatherReviewSetup({ ..., legKind })` (folds round 1's `plan-round` answer via
    `review_setup_gather.py gather`): pass `--doc-mode` to that helper too when
    `legKind && legKind.docMode`, so round 1 (which never calls `planRoundDecider` directly —
    it consumes the folded `entryPlan` instead) gets the same scheduling answer a later round
    would.
- [ ] In `plugins/superheroes/lib/review_setup_gather.py`:
  - Add `--doc-mode` (`action="store_true"`) to the `gather` subparser.
  - Give `gather(..., doc_mode=False)` the flag and pass it into its
    `review_loop_plan.plan_round_decider(records_path, resume.get("round"), dimensions, changed,
    just_marked=False, doc_mode=doc_mode)` call — the one place this file schedules round 1's
    confirmation entry, and the exact call that silently ran code-mode scheduling for every
    doc-panel round 1 otherwise.
  - In `main()`, pass `doc_mode=args.doc_mode` into `gather(...)`.
  - Add a case to this file's own test (or a new `test_review_setup_gather_doc_mode.py`)
    asserting `gather(..., doc_mode=True)` on a fixture with an open Important surfaced
    schedules `enterConfirmation: True` in the folded `plan`, matching the standalone
    `plan_round_decider(..., doc_mode=True)` answer from Task 8's new test.
- [ ] In `plugins/superheroes/lib/showrunner.js`, `runReviewDocPanel` (function body, its one
  `reviewPanel({ ... })` call): change `maxRounds: 7, legKind: { panel: true, code: false },
  ...` to `maxRounds: 3, legKind: { panel: true, code: false, docMode: true }`. This is the
  function's ONLY `reviewPanel` call and its only `maxRounds: 7` — there is no second one to
  find. Separately, in `reviewDocPhase` (the caller), its `gatherReviewSetup({ ... legKind: {
  panel: true, code: false }, ... })` call already carries a `legKind`; add `docMode: true` to
  it there. `runReviewDocPanel` itself, by contrast, takes NO `legKind` parameter from its
  caller — `reviewDocPhase`'s call to it passes only `{ workItem, docType, docPath, runDir,
  runtimeDeferred, preloaded }` — it builds its own `legKind` internally at the `reviewPanel`
  call edited above, so there is nothing to add at `reviewDocPhase`'s `runReviewDocPanel({ ...
  })` call site. This is no longer cosmetic symmetry: `gatherReviewSetup` now reads
  `legKind.docMode` to decide whether round 1's folded `plan-round` answer is scheduled in doc
  mode — omitting it at the `gatherReviewSetup` call silently reverts round 1 of every doc panel
  to code-mode scheduling while every later round correctly runs doc mode.
- [ ] Regenerate the bundle: `cd "$ROOT" && node plugins/superheroes/lib/bundle_showrunner.js --write`.
- [ ] Run: `cd "$ROOT" && node --test plugins/superheroes/lib/tests/showrunner_doc_cap_smoke.js && python3 -m pytest plugins/superheroes/lib/tests/test_bundle_drift.py plugins/superheroes/lib/tests/test_review_setup_gather*.py -q`.
  Expected: pass.
- [ ] Commit: `feat(superheroes): doc panel runs maxRounds 3 with docMode threaded (#397)`.

### Task 10: Add the doc-mode carve-out to the shared loop contract

`reference/review-loop.md`'s "## Convergent Shared Review Loop" hard-codes the code-review
re-arm prose. The interactive `review-plan`/`review-tasks` skills defer to it, so without a
doc-gated paragraph their prose contradicts the `doc_mode` decider they call.

- [ ] Add a failing assertion to `plugins/superheroes/lib/tests/test_skill_markdown.py` (or the
  drift test that reads `review-loop.md`) requiring the doc-mode paragraph:

```python
def test_review_loop_has_doc_mode_carveout():
    import os
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    text = open(os.path.join(root, "plugins/superheroes/reference/review-loop.md"), encoding="utf-8").read()
    assert "review-loop-version: 2" in text
    assert "document review" in text.lower() and "three completed rounds" in text.lower()
    assert "any open blocking finding" in text.lower() or "Critical **or** Important" in text
```

- [ ] In `plugins/superheroes/reference/review-loop.md` bump `<!-- review-loop-version: 1 -->`
  → `<!-- review-loop-version: 2 -->` and add a doc-gated paragraph inside
  `## Convergent Shared Review Loop`, right after the code-review confirmation-bar paragraph
  ("Only a **Critical** surfaced ... while a Critical still parks"):

```markdown
**Document reviews (`review-plan`, `review-tasks`) diverge on the re-arm rule and the cap
(#397).** A doc-panel round is a full-document, full-panel spend with no cheap scoped tier, so
the total is **three completed rounds** — one baseline plus at most **two** confirmation
panels — and **any open blocking finding** (Critical **or** Important) re-arms the one further
confirmation, not only a Critical or cross-cutting rework. There is no scoped-round tier for
new Importants and no scoped-verify certify at the cap: **at the cap a document review always
parks** (certification withheld — there is no stronger downstream reviewer to catch what this
gate would wave through). Everything else in this section — the full baseline panel, the
convergence record, fail-closed on malformed/stale receipts — is identical. This rule is
implemented once in `review_round_policy.confirmation_followup(doc_mode=True)` and its bundled
JS twin; do not restate the numbers elsewhere.
```

- [ ] Run: `cd "$ROOT" && python3 -m pytest plugins/superheroes/lib/tests/ -k "skill_markdown or review_loop or ssot_drift" -q && python3 .github/scripts/validate_skills.py`.
  Expected: pass.
- [ ] Commit: `docs(superheroes): doc-mode carve-out in the shared review-loop contract (#397)`.

### Task 11: Drop the interactive doc legs' cap 7 → 3 and pin both legs to it

The interactive `review-plan` / `review-tasks` skills call `loop_state.py --max-rounds 7`.
Move them to 3 so the two review surfaces (native + interactive) agree; the native cap already
moved in Task 9.

- [ ] Add a test `plugins/superheroes/lib/tests/test_doc_cap_agreement.py` that reads both
  skill files and the native `runReviewDocPanel`, and asserts all three carry the same doc cap
  (3), reading the values rather than restating them:

```python
import os, re
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def _read(p):
    return open(os.path.join(ROOT, p), encoding="utf-8").read()


def test_interactive_doc_legs_cap_at_three():
    for skill in ("plugins/superheroes/skills/review-plan/SKILL.md",
                  "plugins/superheroes/skills/review-tasks/SKILL.md"):
        text = _read(skill)
        assert "--max-rounds 3" in text, f"{skill} must cap the doc loop at 3"
        assert "--max-rounds 7" not in text, f"{skill} must not keep the old 7-round cap"


def test_native_doc_panel_caps_at_three():
    text = _read("plugins/superheroes/lib/showrunner.js")
    # showrunner.js has TWO `reviewPanel({ ... })` call sites: `runReviewCodePanel`'s (earlier
    # in the file, no `docMode` key at all — every doc_mode/docMode gate defaults false) and
    # `runReviewDocPanel`'s (the one this test pins). An un-scoped `re.search` starts at the
    # FIRST occurrence (the code leg's) and, since `.*?` is dot-all (re.S) and there is no
    # `docMode: true` before it closes, the lazy scan crosses straight through that call's own
    # closing `})` looking for the next "docMode: true" — landing on the doc leg's, many lines
    # later, and matching the entire wrongly-scoped span between the two calls (the assertion
    # below would then pass even if the CODE leg's `maxRounds` were wrong, since `maxRounds: 3`
    # only needs to appear somewhere in that oversized span). Anchor the search to
    # `runReviewDocPanel`'s own body first so the regex can only match ITS `reviewPanel` call.
    fn_start = text.index("async function runReviewDocPanel")
    body = text[fn_start:]
    # `docMode: true` sits INSIDE the nested `legKind: { ... }` object literal, one brace level
    # below `reviewPanel({ ... })` itself (see Task 9's edit) — a `[^}]*?` scanner can never
    # cross that inner closing `}` to reach the call's own closing `})`, so it must be `.*?`
    # (dot-all via re.S, already passed) rather than a `}`-excluding class.
    m = re.search(r"reviewPanel\(\{.*?docMode:\s*true.*?\}\s*\)", body, re.S)
    # the docMode reviewPanel call carries maxRounds: 3
    assert m and "maxRounds: 3" in m.group(0)
```

- [ ] In `plugins/superheroes/skills/review-plan/SKILL.md` and
  `plugins/superheroes/skills/review-tasks/SKILL.md`, change the `loop_state.py --round <N>
  --max-rounds 7` invocation (line ~421/422 in each) to `--max-rounds 3`, and adjust any
  surrounding prose that says "seven rounds" for the doc legs to "three completed rounds
  (baseline + at most two confirmations)". Do **not** touch `review-code`'s cap.
- [ ] The `showrunner.js` docMode `reviewPanel` call already reads `maxRounds: 3` from Task 9;
  this task only re-checks agreement — the `test_native_doc_panel_caps_at_three` case reads it.
  If the regex does not match because the `reviewPanel` call spans differently, adjust the
  showrunner call so `maxRounds: 3` and `docMode: true` sit in the same object literal.
- [ ] Run: `cd "$ROOT" && python3 -m pytest plugins/superheroes/lib/tests/test_doc_cap_agreement.py -q && python3 .github/scripts/validate_skills.py`.
  Expected: pass.
- [ ] Commit: `feat(superheroes): interactive doc legs cap at three rounds, pinned to the native cap (#397)`.

### Task 12: Register the new node smokes in the pytest wrapper

The Node smokes added in Tasks 4 and 9 must run under CI's pytest wrapper.

- [ ] In `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py` append the two new smoke
  paths to the `SHOWRUNNER_SMOKES` list:

```python
    "plugins/superheroes/lib/tests/showrunner_doc_severity_frame_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_doc_cap_smoke.js",
```

- [ ] Run: `cd "$ROOT" && python3 -m pytest plugins/superheroes/lib/tests/test_showrunner_node_smokes.py -q`.
  Expected: pass (the wrapper runs both smokes via `node --test`).
- [ ] Commit: `test(superheroes): register doc-severity + doc-cap node smokes (#397)`.

### Task 13: Route non-blocking findings out of the fixer worklist on both doc legs

FR-5/6/7: routed (non-blocking) findings never run or restart a round. `compose_fix_context`
today folds all severities into the fixer worklist; on a doc leg it must include only blocking
findings so non-blocking ones route forward instead of driving doc revisions.

- [ ] Add a failing test to `plugins/superheroes/lib/tests/test_review_loop_plan.py`:

```python
def test_compose_fix_context_doc_mode_excludes_non_blocking(tmp_path):
    # `_write_records(tmp_path, records)` is the file's existing fixture helper (it does
    # `tmp_path / name` itself and returns the written path) — pass the tmp_path fixture, not a
    # pre-built path string.
    records_path = _write_records(tmp_path, [
        {"round": 1, "findings": [
            {"file": "plan.md", "title": "unauth path", "severity": "Critical"},
            {"file": "plan.md", "title": "no named unit test", "severity": "Minor"},
        ], "dimensions": {}}])
    out = str(tmp_path / "worklist.json")
    res = rlp.compose_fix_context(records_path, None, None, "code", 1, FULL_ROSTER, out, doc_mode=True)
    assert res["ok"]
    import json
    wl = json.loads(open(out).read())
    titles = [f["title"] for f in wl["findings"]]
    assert "unauth path" in titles and "no named unit test" not in titles
```

- [ ] In `plugins/superheroes/lib/review_loop_plan.py` give `compose_fix_context(..., doc_mode=False)`
  the flag and, when true, keep only blocking findings in `prior_findings` and `current_findings`
  before assembling `all_findings` (use `circuit_breaker.is_blocking`):

```python
    if doc_mode:
        prior_findings = [f for f in prior_findings if circuit_breaker.is_blocking(f.get("severity"))]
        current_findings = [f for f in current_findings if circuit_breaker.is_blocking(f.get("severity"))]
```

  Thread `doc_mode` from `tally_round_decider`'s fold call
  (`fc = compose_fix_context(..., worklist_out_path, doc_mode=doc_mode)`) and add
  `--doc-mode` handling already added in Task 8 (the same `args.doc_mode` reaches this fold).
- [ ] Add a drift/coverage assertion (same test file) that a `doc_mode=True` worklist for a
  round of only non-blocking findings is empty (`wl["findings"] == []`), proving routed findings
  never reach the fixer.
- [ ] Run: `cd "$ROOT" && python3 -m pytest plugins/superheroes/lib/tests/test_review_loop_plan.py -q`.
  Expected: pass.
- [ ] Commit: `feat(superheroes): exclude non-blocking findings from the doc-review fixer worklist (#397)`.

### Task 14: Add the hand-off writer `lib/review_handoff.py`

FR-2: a plan review's non-blocking findings are written to a durable `plan-handoff.json` in
the work-item docs dir, deduped by the deterministic identity key (UFR-3).

- [ ] Add a failing test `plugins/superheroes/lib/tests/test_review_handoff.py`:

```python
import importlib.util, json, os

LIB = os.path.join(os.path.dirname(__file__), "..")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def test_write_dedupes_and_names_plan_section(tmp_path):
    rh = _load("review_handoff")
    findings = [
        {"file": "plan.md", "title": "no named unit test", "severity": "Minor",
         "planSection": "Components & interfaces", "summary": "add a unit test for option A"},
        {"file": "plan.md", "title": "No Named Unit Test", "severity": "Minor",
         "planSection": "Components & interfaces", "summary": "dup, reworded case"},
        {"file": "plan.md", "title": "two literals for retry", "severity": "Minor",
         "planSection": "Data flow", "summary": "retry constant appears twice"},
    ]
    out = rh.write_handoff(str(tmp_path), "wi-1", findings)
    assert out["ok"]
    data = json.loads(open(os.path.join(str(tmp_path), "plan-handoff.json")).read())
    assert data["schemaVersion"] == 1 and data["workItem"] == "wi-1"
    assert data["counts"]["distinct"] == 2   # the two same-identity entries collapse
    assert {e["planSection"] for e in data["findings"]} == {"Components & interfaces", "Data flow"}


def test_read_absent_returns_structured_not_found(tmp_path):
    rh = _load("review_handoff")
    res = rh.read_handoff(str(tmp_path))
    assert res == {"ok": False, "reason": "absent"}


def test_read_roundtrips(tmp_path):
    rh = _load("review_handoff")
    rh.write_handoff(str(tmp_path), "wi-1", [
        {"file": "plan.md", "title": "x", "severity": "Minor", "planSection": "Goals"}])
    res = rh.read_handoff(str(tmp_path))
    assert res["ok"] and len(res["findings"]) == 1


def test_write_scrubs_finding_text_before_it_reaches_disk(tmp_path):
    # plan-handoff.json is a durable FILE, not a journal event, but it carries the same
    # free-text finding titles a courier round-tripped — Bearer-token shape matches an existing
    # pr_comment._SCRUB_PATTERNS pattern, same fixture review_park.py's scrub test uses (#397).
    rh = _load("review_handoff")
    rh.write_handoff(str(tmp_path), "wi-1", [
        {"file": "plan.md", "title": "rotate the leaked token: Bearer abcdef0123456789",
         "severity": "Minor", "planSection": "Security"}])
    data = json.loads(open(os.path.join(str(tmp_path), "plan-handoff.json")).read())
    text = data["findings"][0]["text"]
    assert "abcdef0123456789" not in text
    assert "[REDACTED]" in text
```

- [ ] Create `plugins/superheroes/lib/review_handoff.py`. It takes the docs dir directly
  (the caller resolves it storage-mode-aware); idempotent overwrite; fail closed on read:

```python
#!/usr/bin/env python3
"""#397 FR-2/FR-3/UFR-3/UFR-5: the plan-review -> tasks-author hand-off of non-blocking findings.

`write_handoff` dedupes by the deterministic finding-identity key (a reworded dup collapses;
the failure direction is a harmless redundant entry, never a dropped finding) and writes
`plan-handoff.json` into the work-item docs dir (the caller passes the resolved dir).
`read_handoff` returns the list or a structured {ok:false, reason} so the tasks phase can
disclose an absent/unreadable hand-off (UFR-5) rather than proceed silently.
"""

import argparse
import json
import os
import sys

import finding_identity
import readout   # the same scrub seam journal.py/review_park.py use — see below

SCHEMA_VERSION = 1
FILENAME = "plan-handoff.json"


def _entry(finding):
    # `text` is free text a courier round-tripped from the finding's title/summary — the exact
    # shape review_park.py's `_decision()` scrubs before it reaches a journal payload. This
    # writer's output is a DURABLE FILE (plan-handoff.json), not an event payload, but the risk
    # (an unscrubbed secret embedded in reworded finding text) is identical, so scrub HERE, at
    # entry-composition time, the same way — never write the raw text to disk.
    text = finding.get("summary") or finding.get("title") or ""
    return {
        "identity": finding_identity.finding_identity(finding),
        "planSection": finding.get("planSection") or finding.get("docSection") or "",
        "text": readout.scrub(text)[0],
    }


def write_handoff(docs_dir, work_item, findings):
    seen = {}
    order = []
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        e = _entry(f)
        if e["identity"] not in seen:
            seen[e["identity"]] = e
            order.append(e["identity"])
    entries = [seen[i] for i in order]
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "workItem": work_item,
        "findings": entries,
        "counts": {"distinct": len(entries)},
    }
    path = os.path.join(docs_dir, FILENAME)
    try:
        os.makedirs(docs_dir, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, sort_keys=True)
        os.replace(tmp, path)
    except OSError as exc:
        return {"ok": False, "reason": "handoff-write-failed: " + str(exc), "counts": payload["counts"]}
    return {"ok": True, "path": path, "counts": payload["counts"]}


def read_handoff(docs_dir):
    path = os.path.join(docs_dir, FILENAME)
    if not os.path.exists(path):
        return {"ok": False, "reason": "absent"}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return {"ok": False, "reason": "unreadable: " + str(exc)}
    findings = data.get("findings") if isinstance(data, dict) else None
    if not isinstance(findings, list):
        return {"ok": False, "reason": "malformed"}
    return {"ok": True, "findings": findings, "counts": (data.get("counts") or {})}


def main(argv):
    ap = argparse.ArgumentParser(description="#397 plan-review hand-off list")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--docs-dir", required=True)
    w.add_argument("--work-item", required=True)
    w.add_argument("--findings", required=True, help="path to a JSON array of findings")
    r = sub.add_parser("read")
    r.add_argument("--docs-dir", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "write":
        with open(args.findings, encoding="utf-8") as fh:
            findings = json.load(fh)
        print(json.dumps(write_handoff(args.docs_dir, args.work_item, findings)))
    else:
        print(json.dumps(read_handoff(args.docs_dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] Run: `cd "$ROOT" && python3 -m pytest plugins/superheroes/lib/tests/test_review_handoff.py -q`.
  Expected: pass.
- [ ] Commit: `feat(superheroes): plan-review hand-off writer/reader for non-blocking findings (#397)`.

### Task 15: Emit `plan-handoff.json` at the plan-review terminal

Wire the writer into `reviewDocPhase` so a **plan** review (pass or park) writes the hand-off
from its non-blocking findings, and disclose a write failure (UFR-1).

- [ ] Add a smoke `plugins/superheroes/lib/tests/showrunner_plan_handoff_smoke.js` that drives
  `reviewDocPhase('plan', ...)` with a stubbed panel verdict carrying non-blocking findings and
  an overridable docs-dir, and asserts the phase invoked the hand-off write with those findings.
  Use the existing showrunner smoke seams (`sr._io` / `globalThis.__SR_DOC_DIRS` planting)
  already used by `showrunner_fronthalf_docdir_smoke.js` as the pattern; assert the resulting
  `plan-handoff.json` exists in the planted docs dir and its `counts.distinct` matches the
  distinct non-blocking findings. **Register it directly**: append
  `"plugins/superheroes/lib/tests/showrunner_plan_handoff_smoke.js"` to the `SHOWRUNNER_SMOKES`
  list in `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py` — Task 12 already ran
  earlier in this sequence and seeded only the smokes that existed by then, so every smoke added
  from here on registers itself in that same list rather than deferring to Task 12.
- [ ] In `lib/showrunner.js`, in `reviewDocPhase` after the verdict is computed and before/at
  the terminal-record persist, when `doc === 'plan'` collect the review's non-blocking findings
  (read from the run's `round-records.json` via a small courier helper that shells
  `review_handoff.py write`), passing the storage-mode-aware docs dir `docDirFor(workItem)`.
  Dispatch it through the exec courier (mirroring `docRecordDeferred`'s pipe), staging the
  non-blocking findings to `${runDir}/nonblocking.json` first:

```js
// #397 FR-2: at the plan-review terminal, write the non-blocking findings to the durable
// hand-off list the tasks author receives. A write failure discloses (UFR-1) — never silent.
// The whole block is guarded (readGate's pattern, showrunner.js ~1991): exec() has no internal
// try/catch, so a courier-dispatch REJECTION (transport error/timeout) would otherwise
// propagate and abort the rest of the review terminal (the gate/journal/convergence writes
// that follow) — a hand-off outage must degrade to the same one-line disclosure, never
// take down the terminal sequence.
if (doc === 'plan') {
  let handoffOk = false
  try {
    const nonBlocking = await collectNonBlockingFindings(runDir)  // reads round-records.json, filters !is_blocking
    await io().writeFile(`${runDir}/nonblocking.json`, JSON.stringify(nonBlocking || []))
    const res = await exec([
      `python3 ${libPath('review_handoff.py')} write --docs-dir ${shq(docDirFor(workItem))} ` +
      `--work-item ${shq(workItem)} --findings ${shq(runDir + '/nonblocking.json')}`,
    ], 'write plan hand-off')
    handoffOk = !!(res && res[0] && res[0].ok)
  } catch (_) { handoffOk = false }
  if (!handoffOk) {
    phaseResult.assumptions.push(`plan-handoff.json write may have failed for ${workItem}`)
    try { log(`reviewDocPhase: plan hand-off write failed for ${workItem} (UFR-1 disclosure)`) } catch (_) {}
  }
}
```

  Implement `collectNonBlockingFindings(runDir)` as a courier-dispatched Python one-liner that
  loads `round-records.json`, flattens every round's findings, keeps `not is_blocking(severity)`,
  and adds a `planSection` field from each finding's `docSection`/`section` (falling back to
  its `dimension`). Place the disclosure on the existing `phaseResult.assumptions` so it reaches
  the readout on both a passing and a parking terminal.
- [ ] Add a second case to `showrunner_plan_handoff_smoke.js` proving UFR-1 (this is the only
  test in the doc that exercises the disclosure, not just the happy path): stub the `exec`
  courier so the `review_handoff.py write` dispatch returns a non-ok result, drive
  `reviewDocPhase('plan', ...)` the same way, and assert `phaseResult.assumptions` contains a
  string matching `/plan-handoff\.json write may have failed/` — proving a hand-off write
  failure surfaces on the readout instead of failing silently. Add a third case where the
  stubbed dispatch **rejects** (throws) rather than resolving non-ok, and assert BOTH the same
  disclosure lands AND the phase still returns its terminal result (the guard above, not an
  aborted phase) — this pins the reject path the try/catch exists for.
- [ ] Regenerate the bundle: `cd "$ROOT" && node plugins/superheroes/lib/bundle_showrunner.js --write`.
- [ ] Run: `cd "$ROOT" && node --test plugins/superheroes/lib/tests/showrunner_plan_handoff_smoke.js && python3 -m pytest plugins/superheroes/lib/tests/test_bundle_drift.py -q`.
  Expected: pass.
- [ ] Commit: `feat(superheroes): emit plan-handoff.json at the plan-review terminal (#397)`.

### Task 16: Deliver the hand-off to the tasks author as a named input

FR-3: the produce leaf's prompt gains a "Hand-off from the plan review" section populated from
`review_handoff.py read`, and the tasks phase journals `handoff_provided` (or, per UFR-5, that
it could not be read).

- [ ] In `plugins/superheroes/eval/produce-leaf.md` add a new input bullet under `## Input`
  and a handling clause under `## Your job` for the tasks docType:

```markdown
- Hand-off from the plan review (tasks only): <plan-handoff.json findings, or the note that it
  was absent/unreadable>. When present, treat each entry as a finer-grained concern the plan
  review surfaced but did not block on — fold the relevant ones into the task/test breakdown.
  This is advisory input to authoring; it never gates the doc.
```

  And, in the "Your job" numbered list, add: "For a **tasks** doc, if a hand-off list was
  provided, ground the relevant entries into concrete tasks/tests; if the input says the
  hand-off was absent or unreadable, proceed without it and do not claim to have consumed it
  (the phase has already journaled that disclosure — UFR-5)."
- [ ] In `lib/showrunner.js`, in the front-half tasks produce path (where the produce leaf is
  dispatched for `doc === 'tasks'`), before building the leaf prompt call
  `review_handoff.py read --docs-dir <docDirFor(workItem)>` via the exec courier and:
  - on `{ok:true}`, splice the findings into the leaf prompt's hand-off section and append a
    `handoff_provided` journal event with payload `{doc: 'tasks', delivered: <count>}`;
  - on `{ok:false}`, splice the note "hand-off absent/unreadable: <reason>" into the prompt and
    append a `handoff_provided` event with payload `{doc: 'tasks', delivered: 0, reason: <reason>}`
    so the receipt is honest either way (FR-3 + UFR-5);
  - guard the dispatch itself (same rationale as Task 15's guard): a courier **rejection**
    (transport error/timeout — `exec()` has no internal try/catch) is treated exactly as
    `{ok:false, reason: "handoff read dispatch failed: <error>"}` — the produce phase proceeds
    without the hand-off and journals the honest receipt; it never aborts on a read outage.
    Locate the tasks produce dispatch:
    `grep -n "produce\|produceLeaf\|docType === 'tasks'\|author-plan\|produce-leaf" plugins/superheroes/lib/showrunner.js`.
- [ ] Add a smoke `plugins/superheroes/lib/tests/showrunner_handoff_delivery_smoke.js` that
  plants a `plan-handoff.json` in the docs dir, drives the tasks produce path, and asserts (a)
  the leaf prompt contains the hand-off entries and (b) a `handoff_provided` event with
  `delivered > 0` was journaled; plus a second case with no hand-off file asserting a
  `handoff_provided` event with `delivered: 0` and a `reason`. **Register it directly**: append
  `"plugins/superheroes/lib/tests/showrunner_handoff_delivery_smoke.js"` to the
  `SHOWRUNNER_SMOKES` list in `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py`
  (Task 12 already ran; register here, not there).
- [ ] Regenerate the bundle and run:
  `cd "$ROOT" && node plugins/superheroes/lib/bundle_showrunner.js --write && node --test plugins/superheroes/lib/tests/showrunner_handoff_delivery_smoke.js && python3 -m pytest plugins/superheroes/lib/tests/test_bundle_drift.py -q`.
  Expected: pass.
- [ ] Commit: `feat(superheroes): deliver the plan hand-off to the tasks author as a named input (#397)`.

### Task 17: Route tasks-review non-blocking findings to the journal, never to the build

FR-4/FR-5: a tasks review's non-blocking findings are recorded as `routed_forward` journal
events and — by construction (Task 13 already excludes them from the fixer worklist) — never
reach the workhorse build, whose contract is the tasks doc alone.

- [ ] In `lib/showrunner.js`, in `reviewDocPhase` when `doc === 'tasks'`, at the terminal
  collect the non-blocking findings (reuse `collectNonBlockingFindings(runDir)` from Task 15)
  and append one `routed_forward` journal event per distinct finding (dedupe by
  `finding_identity`), payload `{doc: 'tasks', identity, section, text}`. **`journal.append`
  writes `payload` as-is — it is not on the `detail`/`world` scrub path (see
  `journal.py`'s module docstring and `_scrub`) — so `text` (a finding's title/summary, free
  text a courier round-tripped) MUST be scrubbed before it enters the payload, not after.**
  Route it through the same seam `journal.py` itself uses: scrub each `text` value with
  `readout.scrub(text)` (no `root` needed — `readout.scrub` accepts `root` only for call-site
  compatibility) in the Python courier one-liner/helper that builds the event, so the scrubbed
  string is what lands in `payload`, never the raw finding text. A journal write failure
  discloses on `phaseResult.assumptions` (UFR-1). Do **not** write a hand-off file for tasks
  (that is plan-only).
- [ ] Add a drift test `plugins/superheroes/lib/tests/test_tasks_routed_not_in_build.py` (a NEW
  file — this task creates it) that proves FR-5 structurally: build a fixer worklist with
  `compose_fix_context(..., doc_mode=True)` from a tasks-review records fixture containing both
  blocking and non-blocking findings and assert no non-blocking (routed) finding's identity
  appears in the worklist `findings`. This is the "a tasks-review routed finding appears in no
  build instruction" guard named in the plan:

```python
import json
import os

import review_loop_plan as rlp

FULL_ROSTER = ["architecture-reviewer", "code-reviewer", "security-reviewer",
               "test-reviewer", "premortem-reviewer"]


def _write_records(tmp_path, records, name="round-records.json"):
    p = tmp_path / name
    p.write_text(json.dumps(records))
    return str(p)


def test_routed_tasks_finding_absent_from_build_worklist(tmp_path):
    records_path = _write_records(tmp_path, [{"round": 1, "findings": [
        {"file": "tasks.md", "title": "task 3 mis-specifies the clock", "severity": "Important"},
        {"file": "tasks.md", "title": "nit: rename local var", "severity": "Minor"},
    ], "dimensions": {}}])
    out = str(tmp_path / "worklist.json")
    rlp.compose_fix_context(records_path, None, None, "code", 1, FULL_ROSTER, out, doc_mode=True)
    titles = [f["title"] for f in json.loads(open(out).read())["findings"]]
    assert "nit: rename local var" not in titles   # routed forward, never in the build worklist
    assert "task 3 mis-specifies the clock" in titles  # blocking tasks finding IS judged/built
```

- [ ] Add a case to the SAME `test_tasks_routed_not_in_build.py` (this file already exists —
  created by the previous bullet) asserting a `routed_forward` payload's `text` has been
  scrubbed: build a finding whose title embeds a secret shape `pr_comment._SCRUB_PATTERNS`
  matches (e.g. `"rotate the leaked token: Bearer abcdef0123456789"`), drive the same
  composition path the showrunner uses to build the payload, and assert
  `"abcdef0123456789"` is absent from the resulting `text` (replaced with `Bearer [REDACTED]`)
  while the non-secret portion of the title survives.
- [ ] Add a smoke asserting the `routed_forward` events are journaled at a tasks terminal
  (extend an existing tasks-leg smoke, or add `showrunner_tasks_routed_smoke.js`), plus a
  dispatch-failure case (same class as Tasks 15/18/19's disclosure cases): stub the courier so
  the routed-forward journal dispatch rejects, drive the tasks terminal, and assert the phase
  still completes with a disclosure on `phaseResult.assumptions` — a routing outage never aborts
  the terminal (UFR-1). If a new file
  is added, **register it directly**: append
  `"plugins/superheroes/lib/tests/showrunner_tasks_routed_smoke.js"` to the `SHOWRUNNER_SMOKES`
  list in `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py` (Task 12 already ran;
  register here, not there).
- [ ] Regenerate the bundle and run:
  `cd "$ROOT" && node plugins/superheroes/lib/bundle_showrunner.js --write && python3 -m pytest plugins/superheroes/lib/tests/test_tasks_routed_not_in_build.py -q && node --test plugins/superheroes/lib/tests/showrunner_tasks_routed_smoke.js`.
  Expected: pass.
- [ ] Commit: `feat(superheroes): journal tasks-review non-blocking findings, keep them out of the build (#397)`.

### Task 18: Add the park composer `lib/review_park.py` and enrich the parked event

FR-10/FR-11: on a doc-review halt, compose a plain-language decision list from the terminal
round's open blocking findings and carry it as the `parked` event payload and the readout.

- [ ] Add a failing test `plugins/superheroes/lib/tests/test_review_park.py`:

```python
import importlib.util, json, os

LIB = os.path.join(os.path.dirname(__file__), "..")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def test_compose_decision_list_from_open_blockers(tmp_path):
    rp = _load("review_park")
    records = str(tmp_path / "round-records.json")
    # round-records.json is a bare list on disk (review_memory.load_records_state fails closed
    # to "corrupt" on anything else) — the same shape Tasks 13/17's fixtures use.
    open(records, "w").write(json.dumps([
        {"round": 3, "findings": [
            {"file": "plan.md", "title": "unauth write path", "severity": "Critical",
             "docSection": "Architecture", "summary": "the write path skips auth"},
            {"file": "plan.md", "title": "nit", "severity": "Minor", "docSection": "Goals"},
        ]}]))
    out = rp.compose_park(records, 3, "plan", "open blocking finding at the doc-review round cap")
    assert out["ok"]
    assert out["payload"]["reason"].startswith("open blocking finding")
    dl = out["payload"]["decisions"]
    assert len(dl) == 1                      # only the blocking finding becomes a decision
    d = dl[0]
    assert d["docSection"] == "Architecture"
    assert "accept" in d["moves"][0].lower() or "fix" in d["moves"][0].lower()
    assert len(d["moves"]) == 2              # the two owner moves (direct-a-fix, accept-through-gate)


def test_unreadable_records_still_parks_with_note(tmp_path):
    rp = _load("review_park")
    out = rp.compose_park(str(tmp_path / "missing.json"), 3, "plan", "cap reached")
    assert out["ok"] and out["payload"]["decisions"] == []
    assert "could not" in out["payload"]["note"].lower()


def test_decision_text_is_scrubbed_before_it_reaches_the_payload(tmp_path):
    # journal.append writes `payload` as-is (no scrub) — compose_park is the only place left
    # that can protect the `parked` event from a finding whose title/summary round-tripped a
    # secret shape. Bearer-token shape matches an existing pr_comment._SCRUB_PATTERNS pattern.
    rp = _load("review_park")
    records = str(tmp_path / "round-records.json")
    open(records, "w").write(json.dumps([
        {"round": 3, "findings": [
            {"file": "plan.md", "title": "rotate the leaked token: Bearer abcdef0123456789",
             "severity": "Critical", "docSection": "Security"},
        ]}]))
    out = rp.compose_park(records, 3, "plan", "open blocking finding at the doc-review round cap")
    d = out["payload"]["decisions"][0]
    assert "abcdef0123456789" not in d["statement"]
    assert "abcdef0123456789" not in d["accepting_means"]
    assert "[REDACTED]" in d["statement"]
```

- [ ] Create `plugins/superheroes/lib/review_park.py`:

```python
#!/usr/bin/env python3
"""#397 FR-10/FR-11: compose the doc-review park decision list.

On a doc-review halt, read the terminal round's open BLOCKING findings from round-records.json
and turn each into a plain-language decision the owner can rule on: the statement, the doc
section it concerns, what accepting it would mean, and the two owner moves (direct a fix + a
fresh review, or accept the finding through the existing gate-approval step). The output is the
structured `payload` of the `parked` journal event and the readout block. Fail-soft: an
unreadable record still parks, with the reason and a note that the list could not be composed."""

import argparse
import json
import os
import sys

import circuit_breaker
import readout   # the same scrub seam journal.py itself uses — see below

MOVE_FIX = "Direct a fix, then re-review (the ordinary path): the review re-runs and this finding must clear the bar."
MOVE_ACCEPT = "Accept this finding through the existing gate-approval step: the gate reads passed with it recorded as accepted."


def _decision(finding):
    # `statement`/`accepting_means` are built from the finding's own title/summary — free text a
    # courier round-tripped, potentially embedding a copied secret. This payload becomes the
    # `parked` journal event's `payload` verbatim, and journal.append writes `payload` as-is (no
    # scrub — only `detail`/`world` are on that path). Scrub HERE, at composition time, so no
    # caller of compose_park can forget to and no unscrubbed finding text ever reaches the event.
    section = finding.get("docSection") or finding.get("planSection") or finding.get("section") or ""
    statement = readout.scrub(finding.get("summary") or finding.get("title") or "")[0]
    return {
        "statement": statement,
        "docSection": section,
        "accepting_means": "The build proceeds as the document stands on this point; "
                           + (statement or "this concern") + " is left as-is.",
        "moves": [MOVE_FIX, MOVE_ACCEPT],
    }


def compose_park(records_path, round_no, doc, reason):
    payload = {"doc": doc, "round": round_no, "reason": reason, "decisions": [], "note": ""}
    try:
        with open(records_path, encoding="utf-8") as fh:
            data = json.load(fh)
        # round-records.json is a bare list on disk (review_memory.load_records_state's shape) —
        # match it exactly rather than tolerating a second, never-produced wrapped shape.
        records = data if isinstance(data, list) else []
        rec = next((r for r in (records or []) if isinstance(r, dict) and r.get("round") == round_no), None)
        if rec is None and records:
            rec = records[-1]
        findings = (rec or {}).get("findings") or []
    except (OSError, ValueError, TypeError):
        payload["note"] = "the open-findings list could not be composed (round record unreadable)"
        return {"ok": True, "payload": payload}
    payload["decisions"] = [_decision(f) for f in findings
                            if isinstance(f, dict) and circuit_breaker.is_blocking(f.get("severity"))]
    if not payload["decisions"]:
        payload["note"] = "no open blocking findings were recorded for the terminal round"
    return {"ok": True, "payload": payload}


def main(argv):
    ap = argparse.ArgumentParser(description="#397 doc-review park composer")
    ap.add_argument("--path", required=True, help="round-records.json")
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--doc", required=True, choices=["plan", "tasks"])
    ap.add_argument("--reason", required=True)
    args = ap.parse_args(argv)
    print(json.dumps(compose_park(args.path, args.round, args.doc, args.reason)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] In `lib/showrunner.js` (or the phase-park path in `phase_progress_entry.py` that appends
  the `parked` event at line ~70), when a doc review parks, dispatch `review_park.py` via the
  courier and attach its `payload` to the `parked` journal event (replacing the bare
  `detail=str(park_reason)` with the structured payload) and surface the decision list in the
  readout via `phaseResult.parkDetail`. Confirm the `parked` append carries a non-empty payload
  for a doc-review park (FR-11). **Failure story (UFR-1):** `compose_park` itself is fail-soft
  (returns `{ok: True, payload: {..., decisions: [], note: "..."}}` on an unreadable
  round-records file — see the module), but the courier DISPATCH around it can still fail (exec
  error, non-JSON answer, timeout). On that failure the park must still proceed — a composer
  outage must never block the park itself — falling back to a minimal payload
  `{doc, round, reason: park_reason, decisions: [], note: "decision list could not be
  composed: <dispatch failure>"}` for the `parked` event, and push a matching note onto
  `phaseResult.assumptions` (the same disclosure seam Task 15's hand-off write failure uses) so
  the readout shows the decision list is missing rather than silently rendering an empty one.
- [ ] Add a smoke `plugins/superheroes/lib/tests/showrunner_park_disclosure_smoke.js` proving
  UFR-1 on the dispatch path (the Python-level `test_review_park.py` only covers
  `compose_park`'s own fail-soft behavior, not the courier-dispatch failure this bullet
  describes): stub the courier so the `review_park.py` dispatch rejects/returns non-JSON, drive
  a doc-review park, and assert (a) the `parked` event's payload is the minimal fallback shape
  (`decisions: []`, a `note` matching `/could not be composed/`) and (b) `phaseResult.assumptions`
  carries a matching disclosure. **Register it directly**: append
  `"plugins/superheroes/lib/tests/showrunner_park_disclosure_smoke.js"` to the
  `SHOWRUNNER_SMOKES` list in `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py`
  (Task 12 already ran; register here, not there).
- [ ] Run: `cd "$ROOT" && python3 -m pytest plugins/superheroes/lib/tests/test_review_park.py plugins/superheroes/lib/tests/test_phase_step.py -q && node --test plugins/superheroes/lib/tests/showrunner_park_disclosure_smoke.js`.
  Expected: pass.
- [ ] Commit: `feat(superheroes): readable doc-review park with a decision list (#397)`.

### Task 19: Record a `review_convergence` event at every doc-review terminal

FR-15: at every doc-review terminal (pass, accepted pass, park) journal
`{doc, roundsUsed, perRound: [{round, blocking, routedForward}], outcome}` so a park-wall or
demotion-wall is visible across runs as data.

- [ ] Add a decider `plugins/superheroes/lib/review_convergence.py` (small, pure) that computes
  the convergence payload from `round-records.json` + the terminal outcome, with a test
  `plugins/superheroes/lib/tests/test_review_convergence.py`:

```python
import importlib.util, json, os

LIB = os.path.join(os.path.dirname(__file__), "..")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_convergence_counts_blocking_and_routed_per_round(tmp_path):
    rc = _load("review_convergence")
    records = str(tmp_path / "round-records.json")
    # round-records.json is a bare list on disk (review_memory.load_records_state's shape) — the
    # same shape Tasks 13/17's fixtures use.
    open(records, "w").write(json.dumps([
        {"round": 1, "findings": [
            {"severity": "Critical", "title": "a"}, {"severity": "Minor", "title": "b"}]},
        {"round": 2, "findings": [{"severity": "Minor", "title": "c"}]},
    ]))
    out = rc.compose_convergence(records, "plan", "passed")
    assert out["doc"] == "plan" and out["roundsUsed"] == 2 and out["outcome"] == "passed"
    assert out["perRound"] == [
        {"round": 1, "blocking": 1, "routedForward": 1},
        {"round": 2, "blocking": 0, "routedForward": 1}]


def test_convergence_unreadable_records_fails_soft(tmp_path):
    rc = _load("review_convergence")
    out = rc.compose_convergence(str(tmp_path / "missing.json"), "plan", "parked")
    assert out == {"doc": "plan", "outcome": "parked", "roundsUsed": 0, "perRound": []}
```

  Create `plugins/superheroes/lib/review_convergence.py`:

```python
#!/usr/bin/env python3
"""#397 FR-15: the per-review convergence record — rounds used, per-round blocking vs
routed-forward finding counts, and the outcome — emitted at every doc-review terminal (pass,
accepted pass, park) so a park-wall or demotion-wall is visible across runs as data.

Read-only over round-records.json; never mutates anything. Fail-soft: an unreadable or
malformed records file still returns a payload (`roundsUsed: 0`, `perRound: []`) so a
convergence-record write failure never blocks the terminal itself (UFR-1 disclosure is the
caller's job, same as Tasks 15/18's write paths)."""

import argparse
import json
import sys

import circuit_breaker


def compose_convergence(records_path, doc, outcome):
    try:
        with open(records_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {"doc": doc, "outcome": outcome, "roundsUsed": 0, "perRound": []}
    # round-records.json is a bare list on disk (review_memory.load_records_state's shape).
    records = data if isinstance(data, list) else []
    per_round = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        findings = [f for f in (rec.get("findings") or []) if isinstance(f, dict)]
        blocking = sum(1 for f in findings if circuit_breaker.is_blocking(f.get("severity")))
        per_round.append({"round": rec.get("round"), "blocking": blocking,
                          "routedForward": len(findings) - blocking})
    return {"doc": doc, "outcome": outcome, "roundsUsed": len(records), "perRound": per_round}


def main(argv):
    ap = argparse.ArgumentParser(description="#397 per-review convergence record")
    ap.add_argument("--path", required=True, help="round-records.json")
    ap.add_argument("--doc", required=True, choices=["plan", "tasks"])
    ap.add_argument("--outcome", required=True)
    args = ap.parse_args(argv)
    print(json.dumps(compose_convergence(args.path, args.doc, args.outcome)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```
- [ ] In `lib/showrunner.js` `reviewDocPhase`, at every terminal (passing, parking, accepted),
  dispatch `review_convergence.py` and append a `review_convergence` journal event with its
  payload. A write failure discloses on `phaseResult.assumptions` (UFR-1): on a dispatch
  failure (exec error, non-JSON answer), skip the journal append and push
  `"review_convergence record may have failed for ${workItem}"` (or equivalent) onto
  `phaseResult.assumptions` — the same disclosure seam Tasks 15/18 use — rather than raising or
  silently omitting the record.
- [ ] Add a smoke `plugins/superheroes/lib/tests/showrunner_convergence_smoke.js` asserting a
  `review_convergence` event is journaled on both a passing and a parking doc terminal, plus a
  third case proving the UFR-1 disclosure: stub the courier so the `review_convergence.py`
  dispatch fails, drive the same terminal, and assert no `review_convergence` event was
  journaled AND `phaseResult.assumptions` carries a matching failure note.
  **Register it directly**: append
  `"plugins/superheroes/lib/tests/showrunner_convergence_smoke.js"` to the `SHOWRUNNER_SMOKES`
  list in `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py` (Task 12 already ran;
  register here, not there).
- [ ] Regenerate the bundle and run:
  `cd "$ROOT" && node plugins/superheroes/lib/bundle_showrunner.js --write && python3 -m pytest plugins/superheroes/lib/tests/test_review_convergence.py -q && node --test plugins/superheroes/lib/tests/showrunner_convergence_smoke.js`.
  Expected: pass.
- [ ] Commit: `feat(superheroes): per-review convergence record at every doc terminal (#397)`.

### Task 20: Add the acceptance ledger `lib/review_acceptance.py`

FR-14: on the owner's gate-approval of a parked doc review, record `{identity, docSection,
contentHash}` per accepted finding; the re-review treats a finding as accepted (not blocking)
when its concerned-section content hash still matches AND the synthesis judge confirms sameness
(fail-closed to re-judging). The concerned section is the whole matched subsection
(heading-to-next-heading of the same-or-shallower level); a cross-cutting finding is recorded
with `docSection: null` keyed to the whole-doc hash.

- [ ] Add a failing test `plugins/superheroes/lib/tests/test_review_acceptance.py`:

```python
import importlib.util, json, os

LIB = os.path.join(os.path.dirname(__file__), "..")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


DOC = """# Plan

## Architecture

The write path authenticates every request.

## Data flow

Records are append-only.
"""


def test_section_hash_spans_whole_subsection(tmp_path):
    ra = _load("review_acceptance")
    # the "Architecture" span is heading-to-next-heading — the whole subsection, not one line
    h1 = ra.section_hash(DOC, "Architecture")
    edited = DOC.replace("authenticates every request", "authenticates every request (added a note)")
    h2 = ra.section_hash(edited, "Architecture")
    assert h1 != h2                      # an edit anywhere in the subsection invalidates the hash
    assert ra.section_hash(DOC, "Data flow") == ra.section_hash(edited, "Data flow")


def test_unresolved_heading_falls_back_to_whole_doc_hash(tmp_path):
    ra = _load("review_acceptance")
    assert ra.section_hash(DOC, "No Such Heading") == ra.whole_doc_hash(DOC)


def test_record_and_match_unchanged_section(tmp_path):
    ra = _load("review_acceptance")
    ra.record(str(tmp_path), "plan", [
        {"file": "plan.md", "title": "unauth path", "docSection": "Architecture"}], DOC)
    led = json.loads(open(os.path.join(str(tmp_path), "plan-accept.json")).read())
    assert led["accepted"][0]["identity"] == "plan.md::unauth path"
    # unchanged doc -> the section hash still matches (candidate for suppression)
    cands = ra.candidates(str(tmp_path), "plan", DOC)
    assert cands[0]["identity"] == "plan.md::unauth path" and cands[0]["hashMatches"] is True
    # edited section -> no longer a candidate (judged afresh)
    edited = DOC.replace("authenticates", "skips authenticating")
    cands2 = ra.candidates(str(tmp_path), "plan", edited)
    assert cands2[0]["hashMatches"] is False


def test_cross_cutting_finding_keyed_to_whole_doc(tmp_path):
    ra = _load("review_acceptance")
    ra.record(str(tmp_path), "plan", [
        {"file": "plan.md", "title": "structural", "docSection": None}], DOC)
    led = json.loads(open(os.path.join(str(tmp_path), "plan-accept.json")).read())
    assert led["accepted"][0]["docSection"] is None
    assert led["accepted"][0]["contentHash"] == ra.whole_doc_hash(DOC)
```

- [ ] Create `plugins/superheroes/lib/review_acceptance.py`:

```python
#!/usr/bin/env python3
"""#397 FR-14: the owner-acceptance ledger for parked doc reviews.

record()      — on gate-approval, persist {identity, docSection, contentHash} per accepted
                finding into plan-accept.json / tasks-accept.json in the work-item docs dir.
candidates()  — at re-review, return each accepted finding with whether its concerned-section
                content hash still matches the current doc. Suppression is the caller's job and
                requires BOTH a hash match AND the synthesis judge's sameness confirmation
                (fail-closed to re-judging) — this module never suppresses on the hash alone.

The concerned section is drawn generously: the finding's matched heading through the next
heading of the same-or-shallower level — the whole subsection. A heading that can't be
resolved, or a finding whose substance spans subsections (docSection: null), is keyed to the
whole-doc hash — the safe direction (re-judge), never a silently-stale accept."""

import argparse
import hashlib
import json
import os
import re
import sys

import finding_identity

SCHEMA_VERSION = 1
_FILENAME = {"plan": "plan-accept.json", "tasks": "tasks-accept.json"}
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.M)


def whole_doc_hash(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def section_hash(text, heading):
    """Hash the whole subsection: the matched heading line through the next heading of the same
    or shallower level. An unresolved heading falls back to the whole-doc hash (fail-closed)."""
    if not heading:
        return whole_doc_hash(text)
    matches = list(_HEADING.finditer(text or ""))
    for i, m in enumerate(matches):
        if finding_identity.normalize_title(m.group(2)) == finding_identity.normalize_title(heading):
            level = len(m.group(1))
            start = m.start()
            end = len(text)
            for n in matches[i + 1:]:
                if len(n.group(1)) <= level:
                    end = n.start()
                    break
            return hashlib.sha256(text[start:end].encode("utf-8")).hexdigest()[:16]
    return whole_doc_hash(text)


def _path(docs_dir, doc):
    return os.path.join(docs_dir, _FILENAME[doc])


def record(docs_dir, doc, findings, doc_text):
    entries = []
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        section = f.get("docSection")
        content_hash = whole_doc_hash(doc_text) if section in (None, "") else section_hash(doc_text, section)
        entries.append({
            "identity": finding_identity.finding_identity(f),
            "docSection": section if section not in ("",) else None,
            "contentHash": content_hash,
        })
    payload = {"schemaVersion": SCHEMA_VERSION, "doc": doc, "accepted": entries}
    path = _path(docs_dir, doc)
    os.makedirs(docs_dir, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, sort_keys=True)
    os.replace(tmp, path)
    return {"ok": True, "path": path, "count": len(entries)}


def candidates(docs_dir, doc, doc_text):
    path = _path(docs_dir, doc)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            led = json.load(fh)
    except (OSError, ValueError):
        return []
    out = []
    for e in led.get("accepted") or []:
        section = e.get("docSection")
        current = whole_doc_hash(doc_text) if section in (None, "") else section_hash(doc_text, section)
        out.append({"identity": e.get("identity"), "docSection": section,
                    "hashMatches": current == e.get("contentHash")})
    return out


def main(argv):
    ap = argparse.ArgumentParser(description="#397 doc-review acceptance ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--docs-dir", required=True)
    r.add_argument("--doc", required=True, choices=["plan", "tasks"])
    r.add_argument("--findings", required=True)
    r.add_argument("--doc-path", required=True)
    c = sub.add_parser("candidates")
    c.add_argument("--docs-dir", required=True)
    c.add_argument("--doc", required=True, choices=["plan", "tasks"])
    c.add_argument("--doc-path", required=True)
    args = ap.parse_args(argv)
    doc_text = open(args.doc_path, encoding="utf-8").read()
    if args.cmd == "record":
        with open(args.findings, encoding="utf-8") as fh:
            findings = json.load(fh)
        print(json.dumps(record(args.docs_dir, args.doc, findings, doc_text)))
    else:
        print(json.dumps(candidates(args.docs_dir, args.doc, doc_text)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] Run: `cd "$ROOT" && python3 -m pytest plugins/superheroes/lib/tests/test_review_acceptance.py -q`.
  Expected: pass.
- [ ] Commit: `feat(superheroes): doc-review acceptance ledger keyed to the concerned subsection (#397)`.

### Task 21: Consult the acceptance ledger at re-review; record on gate-approval

Wire the ledger into the two ends: record accepted findings when the owner approves a parked
doc through the existing gate-approval step, and at re-review treat a re-raised finding as
accepted (not blocking) when its section hash matches AND the synthesis judge confirms sameness
(keep-on-uncertain → not the same → judged afresh). No new owner verb (Constraint).

- [ ] Add the failing tests first. `plugins/superheroes/lib/tests/test_acceptance_rereview.py`
  (Python-level for the deterministic prefilter; the judge call is stubbed): assert that a
  candidate with a matching hash is offered to the judge, a candidate with a changed-section
  hash is **not** offered (judged afresh), and that a stubbed judge "different" verdict leaves
  the finding blocking. Assert the FR-14 acceptance property end-to-end via a smoke
  `plugins/superheroes/lib/tests/showrunner_acceptance_rereview_smoke.js`: record an acceptance,
  re-review the unchanged doc, and assert the accepted finding does not re-block (the re-review
  can pass with it accepted) and the owner is not re-asked. Add a third case to the SAME smoke
  proving UFR-1 on the record leg (below): stub the courier so `review_acceptance.py record`
  fails, drive the gate-approval path, and assert (a) the `gates.review: passed` write still
  succeeds (a ledger-write failure never blocks the owner's approval) and (b) a disclosure note
  matching `/acceptance record could not be written/` lands on `phaseResult.assumptions` (or the
  skill's approval-step output for the interactive path). **Register it directly**: append
  `"plugins/superheroes/lib/tests/showrunner_acceptance_rereview_smoke.js"` to the
  `SHOWRUNNER_SMOKES` list in `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py`
  (Task 12 already ran; register here, not there).
- [ ] Record leg: find where the owner's gate-approval writes `gates.review: passed` on a
  parked doc (the `set-gate` path via `definition_doc.py`) — locate the parked-review approval
  flow: `grep -rn "gate-approval\|accept\|set-gate\|gates.review" plugins/superheroes/skills/review-plan/SKILL.md plugins/superheroes/skills/review-tasks/SKILL.md plugins/superheroes/lib/definition_doc.py | head`.
  At that approval point, call `review_acceptance.py record --docs-dir <docsDir> --doc <doc>
  --findings <open-blockers.json> --doc-path <doc.md>` with the parked round's open blocking
  findings (the same list the park composer used). The FR-12 trail then shows the acceptance
  came after the park event. **Failure story:** the owner's `gates.review: passed` write is the
  approval of record — a `review_acceptance.py record` failure (write error, unreadable
  findings file) must NOT block that gate write (the owner already ruled; there is no stronger
  downstream check to defer to). But it must disclose (UFR-1): surface a plain-language note
  ("acceptance record could not be written: <reason> — a re-review of unchanged content will
  re-judge this finding rather than treat it as accepted") in the same place Task 15/18 surface
  their write-failure disclosures (the skill's approval-step output / `phaseResult.assumptions`
  for the native path) — the exact behavior the third smoke case above pins. This degrades
  safely by construction: FR-14 is fail-closed to re-judging, so a missing ledger entry just
  means the next re-review re-asks the judge instead of silently treating the finding as
  accepted — never the reverse.
- [ ] Re-review leg: in the doc-review synthesis/tally path, before a re-raised finding counts
  as blocking, call `review_acceptance.py candidates` and, for a finding whose `identity` is a
  candidate with `hashMatches: true`, ask the synthesis judge "is this re-raised finding the
  same concern the owner accepted?" (keep-on-uncertain → treat as NOT the same → judge afresh).
  Only a hash-match **and** a judge-confirmed sameness demotes the finding to accepted. Thread
  this through `docSynthesisLeaf` (it already emits keep/drop verdicts) by passing the candidate
  identities into its prompt context and treating a judge "same" verdict as drop-to-accepted.
- [ ] Regenerate the bundle and run:
  `cd "$ROOT" && node plugins/superheroes/lib/bundle_showrunner.js --write && python3 -m pytest plugins/superheroes/lib/tests/test_acceptance_rereview.py -q && node --test plugins/superheroes/lib/tests/showrunner_acceptance_rereview_smoke.js`.
  Expected: pass.
- [ ] Commit: `feat(superheroes): accepted doc findings survive a re-review of unchanged content (#397)`.

### Task 22: Bound the per-round retry (UFR-4) at two attempts before parking

The spec leaves the retry number to the plan; the plan chose **2 failed attempts per round**
before parking (a failed round must not consume a completed round under UFR-2, so an unbounded
retry could flap forever under the 3-round cap). This is the plan's **NOTIFY** default — a
threshold the owner may want tuned.

There is no existing per-round "attempt loop" to extend — a round's tally step
(`tallyRound`'s call to `tallyRoundDecider` in `plugins/superheroes/lib/review_panel_shell.js`,
read at line ~960) currently has ZERO retries: its surrounding `try`/`catch` (lines ~927–984)
returns `terminal: 'halted'` on the FIRST exception (courier dispatch error, decider throw). The
failed attempt is never persisted as a round-record (persistence happens only on a successful
`tallyRound` return, later in `reviewPanel`'s loop), so UFR-2 ("a failed round must not consume a
completed round") already holds for a single failure — this task only needs to bound how many
times that single attempt is retried IN PLACE before the existing halted path is allowed through.

- [ ] Add a smoke `plugins/superheroes/lib/tests/showrunner_doc_round_retry_smoke.js` that stubs
  `tallyRoundDecider` to throw once then succeed and asserts `tallyRound` returns the successful
  verdict (the single retry absorbed it, doc leg only — `DOC_ROUND_RETRY_ATTEMPTS` is 2 TOTAL
  tries, so a recoverable case can fail at most once before the second, succeeding call); then
  stubs it to throw on every call and asserts the returned `terminal` is `'halted'` with a reason
  naming the failure, after exactly `DOC_ROUND_RETRY_ATTEMPTS` (2) attempts (assert the stub's
  call count is 2, not 3 — the loop never makes a third call). A code leg (`legKind.docMode`
  falsy) must see the existing zero-retry behavior unchanged (`legKind: {}` throws once → halted
  immediately, call count 1) — pin that in the same file. **Register it directly**: append
  `"plugins/superheroes/lib/tests/showrunner_doc_round_retry_smoke.js"` to
  the `SHOWRUNNER_SMOKES` list in `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py`
  (Task 12 already ran; register here, not there).
- [ ] In `plugins/superheroes/lib/review_panel_shell.js`, add the named constant near the top:

```js
const DOC_ROUND_RETRY_ATTEMPTS = 2   // #397 UFR-4: 2 failed attempts per round before parking
                                      // (doc legs only — a code-leg round still fails on attempt 1)
```

  Then wrap the existing `tallyRoundDecider({ ... })` call inside `tallyRound`'s `try` block (the
  call at line ~960) in a small bounded retry, gated on `legKind.docMode` so the code-review leg's
  zero-retry behavior is byte-identical to today:

```js
async function _tallyRoundDeciderRetrying(opts, docMode) {
  const attempts = docMode ? DOC_ROUND_RETRY_ATTEMPTS : 1
  let lastErr
  for (let i = 0; i < attempts; i += 1) {
    try {
      return await tallyRoundDecider(opts)
    } catch (e) {
      lastErr = e
      if (docMode) { try { log(`review-panel r${opts.round}: tally attempt ${i + 1}/${attempts} failed (${e && e.message ? e.message : e})`) } catch (_) {} }
    }
  }
  throw lastErr
}
```

  Replace the direct `const decided = await tallyRoundDecider({ ... })` call with
  `const decided = await _tallyRoundDeciderRetrying({ ... }, legKind && legKind.docMode)` (same
  argument object, unchanged). The existing outer `catch (exc)` (lines ~980–984) is untouched —
  it still returns `terminal: 'halted'` with the last exception's message once the retries are
  exhausted, and that halted answer is still never persisted as a round-record, so a doubly-failed
  doc round costs 2 attempts but consumes 0 of the `maxRounds: 3` budget.
- [ ] Run: `cd "$ROOT" && node --test plugins/superheroes/lib/tests/showrunner_doc_round_retry_smoke.js`.
  Expected: pass.
- [ ] Commit: `feat(superheroes): bound doc-review round retries at two attempts before parking (#397)`.

### Task 23: Full-gate green + coverage sweep

Confirm every spec requirement maps to a landed task and the whole-repo gate is green.

- [ ] Sweep the requirement → task map and confirm each is covered by a test: FR-1 (Tasks 3–4,
  10), FR-2 (Task 15), FR-3 (Task 16), FR-4/FR-5 (Tasks 13, 17), FR-6/FR-7 (Tasks 5–9 — the
  clean-baseline pass and ratchet exit ride the shared confirmation economics with the 3-round
  cap), FR-8/FR-9 (Tasks 5–9, 11), FR-10/FR-11 (Task 18), FR-12 (Tasks 8, 21 — no path passes
  with open unaccepted blockers; the honest-gate behavior is `gateForTerminal`, unchanged, plus
  the park-then-accept trail), FR-13 (Tasks 6–11 — both legs share the libs/rubric/contract),
  FR-14 (Tasks 20–21), FR-15 (Task 19); UFR-1 (Tasks 15–19, 21 disclosures), UFR-2 (Tasks 8,
  22), UFR-3 (Task 14), UFR-4 (Task 22), UFR-5 (Tasks 14, 16).
- [ ] Run the whole-repo gate:
  `cd "$ROOT" && python3 .github/scripts/validate_marketplace.py && python3 .github/scripts/validate_hosts.py && python3 .github/scripts/validate_skills.py && python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ plugins/superheroes/eval/tests/ eval/lib/tests/ -q`.
  Expected: exits 0.
- [ ] Confirm the bundle is fresh: `cd "$ROOT" && node plugins/superheroes/lib/bundle_showrunner.js --check` exits 0.
- [ ] Commit any residual doc/wiring touch-ups: `chore(superheroes): finalize doc-review convergence wiring (#397)`.
