# C1-L11f (WO-F) bite-proof — a stacked light-lane layer opens as a draft and is marked ready only after the PR-mode handback check passes

**Provenance:** implementer WO-F, recording the two prose guards of `plugins/superheroes/lib/tests/test_c1l11f_wo_f_light_ready.py` over `plugins/superheroes/skills/workhorse/SKILL.md` (§ 11) and `plugins/superheroes/skills/workhorse/reference/handback.md` (the paragraph after "Before the ready marking").

Declared guarded elements (from the order): F-G1 the § 11 sentence; F-G2 the handback.md sequence. Each was neutralized with one targeted Edit (the added prose removed) and restored by the inverse Edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2279-f` (base `4f350065` plus this dispatch's uncommitted work) under `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-f -m pytest "<node id>" -q -p no:cacheprovider`. Each capture is the runner's whole output apart from the `UV_NATIVE_TLS` deprecation warning line (the first line of each real output), which is left out. Nothing else is trimmed; nothing is redacted (no secrets, tokens or URLs appear).

| ID | Guarded element | Axis | Proving test (in `plugins/superheroes/lib/tests/test_c1l11f_wo_f_light_ready.py`) |
|---|---|---|---|
| F-G1 | `workhorse/SKILL.md` § 11 opening sentence | an unstacked light-lane PR opens ready; a stacked layer opens as a draft and is marked ready only after the PR-mode handback check passes on its pushed head | `test_workhorse_section_11_opens_a_stacked_light_lane_layer_as_a_draft` |
| F-G2 | `workhorse/reference/handback.md`, the stacked light-lane paragraph after "Before the ready marking" | the sequence is push, open the PR as a draft, run `vet_slot.py handback --pr <n> --repo <owner/name>`, fix until `"ok": true`, then mark ready | `test_handback_before_ready_paragraph_names_the_stacked_light_lane_sequence` |

Not separately neutralized (unproven): each test asserts several phrases; only the removal of the whole added prose was neutralized, so each phrase assertion (for example the "no stacked layer, on any lane" clause alone, or the ordering check alone) is **unproven** as a separate guard.

---

## F-G1 — the § 11 sentence

**axis:** § 11 says a stacked light-lane layer opens as a draft and is marked ready only after the PR-mode handback check passes.

**neutralization** (`SKILL.md` § 11, line 643 to 645: the added clause removed, one Edit):
```
-opens ready, except that a stacked light-lane layer opens as a draft and is marked ready only after
-the PR-mode handback check passes on its pushed head: no stacked layer, on any lane, is marked or
-opened ready before that check passes.** Its body
+opens ready.** Its body
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11f_wo_f_light_ready.py::test_workhorse_section_11_opens_a_stacked_light_lane_layer_as_a_draft" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_workhorse_section_11_opens_a_stacked_light_lane_layer_as_a_draft _____

    def test_workhorse_section_11_opens_a_stacked_light_lane_layer_as_a_draft():
        # axis: § 11 says an unstacked light-lane PR opens ready, a stacked layer opens as a draft, and no stacked layer is ready before the PR-mode handback check passes — see bite-proof record c1l11f_wo_f_light_ready
        section = _section_11()
        assert "A light-lane PR opens ready" in section
>       assert "a stacked light-lane layer opens as a draft" in section
E       AssertionError: assert 'a stacked light-lane layer opens as a draft' in '## 11. Hand back the ready PR **A full-lane PR, opened as a draft before review, is marked ready at handback. A light...r and reminder, and the build-record, degradations, follow-ups, size tripwire, and DoD table sections are all present.'

/home/user/wt-2279-f/plugins/superheroes/lib/tests/test_c1l11f_wo_f_light_ready.py:45: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_f_light_ready.py::test_workhorse_section_11_opens_a_stacked_light_lane_layer_as_a_draft
1 failed in 0.20s
```

**restore:** the inverse Edit.

**restore receipt** (`SKILL.md` lines 643 to 646, quoted back after the restore):
```
**A full-lane PR, opened as a draft before review, is marked ready at handback. A light-lane PR
opens ready, except that a stacked light-lane layer opens as a draft and is marked ready only after
the PR-mode handback check passes on its pushed head: no stacked layer, on any lane, is marked or
opened ready before that check passes.** Its body has two addressees and one home per fact. The **owner
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 0.15s
```

---

## F-G2 — the handback.md sequence

**axis:** the before-ready paragraph gives the stacked light-lane sequence, draft then `vet_slot.py handback --pr` then ready.

**neutralization** (`handback.md`, after line 161: the added paragraph removed, one Edit):
```
-
-A stacked light-lane layer has no draft stage of its own, so it takes one for this check: push, open
-the PR as a draft, run `vet_slot.py handback --pr <n> --repo <owner/name>` on it, fix and re-run until
-it prints `"ok": true`, then mark it ready.
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11f_wo_f_light_ready.py::test_handback_before_ready_paragraph_names_the_stacked_light_lane_sequence" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_handback_before_ready_paragraph_names_the_stacked_light_lane_sequence __

    def test_handback_before_ready_paragraph_names_the_stacked_light_lane_sequence():
        # axis: handback.md's before-ready paragraph gives the stacked light-lane sequence — push, open as a draft, run the PR-mode handback check, fix until ok, mark ready — see bite-proof record c1l11f_wo_f_light_ready
        paragraph = _before_ready_paragraph()
>       assert "stacked light-lane layer" in paragraph
E       assert 'stacked light-lane layer' in 'Before the ready marking, also run `python3 -B "${CLAUDE_PLUGIN_ROOT}/lib/vet_slot.py" handback --pr <n> --repo <owne...R\'s pushed head is behind its lower layer\'s current head, or `stack-lower-unreadable` when that head cannot be read.'

/home/user/wt-2279-f/plugins/superheroes/lib/tests/test_c1l11f_wo_f_light_ready.py:53: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_f_light_ready.py::test_handback_before_ready_paragraph_names_the_stacked_light_lane_sequence
1 failed in 0.18s
```

**restore:** the inverse Edit.

**restore receipt** (`handback.md` lines 158 to 166, quoted back after the restore):
```
Before the ready marking, also run `python3 -B "${CLAUDE_PLUGIN_ROOT}/lib/vet_slot.py" handback --pr <n>
--repo <owner/name>` on the pushed PR. On a stacked layer it refuses `stack-not-caught-up`, naming the
catch-up step (`rubric/native-stacks.md` § How a stack stays current), while the PR's pushed head is
behind its lower layer's current head, or `stack-lower-unreadable` when that head cannot be read.

A stacked light-lane layer has no draft stage of its own, so it takes one for this check: push, open
the PR as a draft, run `vet_slot.py handback --pr <n> --repo <owner/name>` on it, fix and re-run until
it prints `"ok": true`, then mark it ready.
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 0.14s
```
