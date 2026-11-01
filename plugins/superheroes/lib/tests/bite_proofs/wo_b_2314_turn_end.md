# WO-B (#2314) bite-proofs — the `turn-end` standing ruling

Declared guarded-element set (from the order): (a) the composed-prompt delivery of the `turn-end`
ruling (`test_compose_turn_end_ruling_in_prompt`); (b) the verbatim copy in
`dispatch-mechanics.md` (`test_turn_end_ruling_matches_dispatch_mechanics`).

Commands used the pinned interpreter: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <node> -q`.
The `UV_NATIVE_TLS` deprecation warning line that opens each run is omitted below; nothing else is trimmed.
No secrets or tokens appear in these captures; nothing is redacted.

---

## (a) `test_compose_turn_end_ruling_in_prompt`

**Guarded element:** `plugins/superheroes/lib/tests/test_launcher.py::test_compose_turn_end_ruling_in_prompt` —
axis: the `turn-end` ruling line reaches the composed builder prompt (`launcher.compose_launch`).

**Neutralization (as ordered):** (1) deleted the whole `` - `turn-end` — ... `` line from the rulings
block in `plugins/superheroes/rubric/launch-doctrine.md`; (2) deleted `    "turn-end",` from
`RULING_IDS` in `plugins/superheroes/lib/launch_doctrine.py`.

**Raw red, first pass (ordered neutralization only) — wrong axis, recorded for honesty:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_compose_turn_end_ruling_in_prompt ____________________
...
/home/user/wt-2314-b/plugins/superheroes/lib/launcher.py:1393: in compose_launch
    doctrine = loader()
/home/user/wt-2314-b/plugins/superheroes/lib/launch_doctrine.py:387: in load
    return parse(text)
/home/user/wt-2314-b/plugins/superheroes/lib/launch_doctrine.py:339: in parse
    rulings, reason = _parse_rulings_block(text, rulings_body, rulings_block_start)
...
        for rid, phrases in RULING_INVARIANTS.items():
>           ruling_text = next(r["text"] for r in rulings if r["id"] == rid)
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E           StopIteration

/home/user/wt-2314-b/plugins/superheroes/lib/launch_doctrine.py:263: StopIteration
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_compose_turn_end_ruling_in_prompt
1 failed in 1.90s
```
(Middle of the pytest traceback, the `text`/`body` local dumps, is elided with `...`; this capture is
labelled incomplete for that reason.) This red is on the wrong axis: it comes from `parse` crashing
because `RULING_INVARIANTS["turn-end"]` still names a ruling that is no longer parsed — not from
the ruling being absent from the prompt.

**Additional neutralization (so the red lands on the claimed axis):** (3) also deleted the
`RULING_INVARIANTS["turn-end"]` entry (the 5-line `"turn-end": (...)` tuple) from
`plugins/superheroes/lib/launch_doctrine.py`.

**Raw red, second pass (all three neutralizations) — on axis:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_compose_turn_end_ruling_in_prompt ____________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_compose_turn_end_ruling_i0')

    def test_compose_turn_end_ruling_in_prompt(tmp_path):
      # axis: turn-end ruling text reaches the composed builder prompt
      # compose_launch verifies only ruling zero is present, so nothing else asserts that this
      # ruling survives composition into the payload a launched builder actually receives.
        repo = _init_repo(tmp_path / "repo")
        premise = _valid_premise(repo)
        result = L.compose_launch(repo, 889, premise)
        assert result["ok"] is True
        doctrine = LD.load()
        turn_end_line = LD.ruling_line(doctrine, "turn-end")
>       assert turn_end_line
E       assert None

/home/user/wt-2314-b/plugins/superheroes/lib/tests/test_launcher.py:571: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_compose_turn_end_ruling_in_prompt
1 failed in 5.90s
```
Compose succeeded (`result["ok"] is True`), and the `turn-end` line was absent — the claimed axis.

**Restore:** inverse Edit-tool edits, three of them: re-inserted the `"turn-end": (...)` invariants
tuple before `"gated-strings": (` in `RULING_INVARIANTS`; re-inserted `    "turn-end",` after
`    "await-dispatches",` in `RULING_IDS`; re-inserted the `turn-end` line after the
`await-dispatches` line in the rulings block.

**Restore receipt:** `launch_doctrine.py` matches for `turn-end` after restore:
`22:    "turn-end",` (RULING_IDS), `70:    "turn-end": (` (RULING_TEXT), `111:    "turn-end": (` (RULING_INVARIANTS);
the doctrine line is back, verbatim the ruling text, directly after the `await-dispatches` line (the
green run below parses it byte-for-byte against `RULING_TEXT`).

**Raw green:**
```
.                                                                        [100%]
1 passed in 7.59s
```

---

## (b) `test_turn_end_ruling_matches_dispatch_mechanics`

**Guarded element:** `plugins/superheroes/lib/tests/test_launch_doctrine.py::test_turn_end_ruling_matches_dispatch_mechanics` —
axis: the whitespace-normalised `RULING_TEXT["turn-end"]` is a substring of the whitespace-normalised
`skills/workhorse/reference/dispatch-mechanics.md`.

**Neutralization:** in `dispatch-mechanics.md` § The turn's final act, deleted one word:
`none of them is a turn's exit plan; until the` → `none of them is a turn's plan; until the`.

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_turn_end_ruling_matches_dispatch_mechanics ________________

    def test_turn_end_ruling_matches_dispatch_mechanics():
        # axis: the turn-end ruling text is carried verbatim (whitespace-normalised) in the
        # dispatch-mechanics reference's "The turn's final act" section
        with open(_DISPATCH_MECHANICS, encoding="utf-8") as fh:
            doc = " ".join(fh.read().split())
>       assert " ".join(LD.RULING_TEXT["turn-end"].split()) in doc
E       AssertionError: assert 'A headless lane never ends a turn with a background task or subagent still running: harness-tracked background work a...ack or park comment is posted, end every turn with a tool call, and await every outcome in-turn or park durably first.' in '# Contents 1. [Dispatch mechanics — long dispatches you own](#dispatch-mechanics--long-dispatches-you-own) 2. [Awaiti... stronger model to do its job, your command list was under-enumerated. Rewrite the list, or run the commands yourself.'
...
/home/user/wt-2314-b/plugins/superheroes/lib/tests/test_launch_doctrine.py:793: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_doctrine.py::test_turn_end_ruling_matches_dispatch_mechanics
1 failed in 0.41s
```
(pytest's own `...` truncation inside the assert message is as emitted; the `+  where` lines are elided
here with `...` and this capture is labelled incomplete for that reason.)

**Restore:** inverse Edit: `a turn's plan; until the` → `a turn's exit plan; until the`.

**Restore receipt:** restored lines in `dispatch-mechanics.md`:
`scheduling cannot wake a headless session, so none of them is a turn's exit plan; until the`
followed by `handback or park comment is posted, end every turn with a tool call, and await every outcome`.

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.38s
```

---

## Not separately proven

`test_turn_end_ruling_is_delivered_verbatim` and `test_doctrine_turn_end_ruling_invariant_missing`
were added by the order but are not in its declared bite-proof set; they were run green inside the
552-test scoped run and not neutralized individually.

## Neutralized-surface check

`git status --porcelain` (untracked dotfiles at the worktree root, present before the dispatch, filtered out):
```
 M plugins/superheroes/lib/launch_doctrine.py
 M plugins/superheroes/lib/tests/test_launch_doctrine.py
 M plugins/superheroes/lib/tests/test_launcher.py
 M plugins/superheroes/rubric/launch-doctrine.md
 M plugins/superheroes/skills/workhorse/reference/dispatch-mechanics.md
```
(The record file itself is untracked and was written after this capture.)
