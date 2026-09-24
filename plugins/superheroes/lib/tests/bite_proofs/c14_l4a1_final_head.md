# C14 layer 4a-1 (#1273) bite-proofs at the final head `a4452b8e`

**Provenance.** This file holds records only; there is no code or test change in it. It was typed by the orchestrator (claude, Opus 5.5).
- **Proofs I ran myself:** BP-F1–F3, BP-C1, and R1–R3 below. Each ran in a detached probe checkout at `a4452b8e`. Every neutralization was one targeted edit through the host's edit action, reverted with the inverse edit. `git status --porcelain` came back empty after each proof.
- **Proofs a subagent ran:** BP-A1–A10 and BP-C2–C7. A host subagent (claude sonnet, role implementer) re-ran them in a second detached probe checkout at the same head, following each record's own neutralization. The orchestrator read the raw captures off disk.
- **Command prefix** for every run: `/usr/bin/python3 -B -X pycache_prefix=<scratch> -m pytest <node> -q -p no:cacheprovider`.

**Rung lines.**
- R1: the census spawner-keyword rule belongs to D1 (`c14-l4a-D1`) and retires with it.
- R2: the stop-rule fork test retires when layer 4a-2 wires the launcher to `claude_session_stop_confirmed` and settles whether `_background_stop` delegates to it; the stale token forces this.
- R3: the pid-less-row rule retires with `claude_session_stop_confirmed`.

## Re-proved at the final head

| ID | Guarded element | Neutralization | Red (exit 1): the exact token or assertion | Green |
|---|---|---|---|---|
| BP-F1 | census: a second site in another file | `engine_dispatch._claude_cli`: add `cmd = ["claude"] + list(args)` before the adapter line | `AssertionError: claude-argv-outside-adapter:lib/engine_dispatch.py:861` | exit 0, 1 passed |
| BP-F2 | census: a second hit inside `compose_launch` | `launcher.compose_launch`: add `_probe = ["claude", "--bg"]` above the hand-built argv | `claude-argv-outside-adapter:lib/launcher.py:1102` and `…:1103` | exit 0 |
| BP-F3 | census: the recorded exception goes stale | `launcher.compose_launch`: first argv element `"claude"` becomes `str("claude")` | `AssertionError: claude-argv-exception-stale:lib/launcher.py:compose_launch` | exit 0 |
| BP-C1 | fold: partial background set (id+sessionId) refuses | `launch_ledger._validate_event_fields`: the `if not present / elif len(present) != 3 / else` chain becomes `if len(present) == 3:` | node `test_started_background_partial_set_refuses[partial_fields2]`: `assert result["ok"] is False` gives `E assert True is False` (the right axis; a KeyError would be wrong) | exit 0, 1 passed |
| BP-A1–A10 | the WO-A records (`wo_l4a_A_1273.md`) | as each record states | each red reproduces its record's token. BP-A4 gives `claude-argv-outside-adapter:lib/engine_dispatch.py:861`, BP-A9 gives `assert 'stopped' == 'background-stop-unconfirmed'`, BP-A10 gives `KeyError: 'droppedCause'` | all exit 0 |
| BP-C2, C4–C7 | the WO-C records (`wo_l4a_C_1273.md`) | as each record states | each red reproduces its record's token | all exit 0 |
| BP-C3 | fold: `backgroundId` shape | as recorded (the shape check becomes `if False:`) | `assert 'fold-bad-field:started:sessionId' == 'fold-bad-field:started:backgroundId'` | exit 0 |

**BP-C3 at this head.** The red fires on the test's own reason assertion: the expected `fold-bad-field:started:backgroundId` token is absent. The fixture's non-hex `backgroundId` also makes its `sessionId` fail the UUID parse, so with the shape check neutralized the fold refuses with the `sessionId` token instead. That is still red on the guarded axis, because the named refusal is missing. It differs from the `assert True is False` shape recorded at WO-C time. **Accepted.**

## Review-fix detectors (added in review rounds 1–2)

| ID | Guarded element | Neutralization | Red (exit 1) | Green |
|---|---|---|---|---|
| R1 | census: a claude literal passed as a spawner keyword (`executable="claude"`) is flagged | `test_claude_argv_census._allowed_constant`: delete the `_enclosing_call` spawner check in the `ast.keyword` branch | `[popen-executable-keyword]`: `AssertionError: expected violation for popen-executable-keyword: subprocess.Popen(["--bg"], executable="claude")` | exit 0 |
| R2a | stop-rule fork: a third stop home fails | `engine_dispatch._stop_confirmed_pid_dead`: add `if False: _claude_cli(["stop", "probe"], None)` | `test_claude_stop_rule_fork_enumeration`: `'claude-stop-rule-fork:_stop_confirmed_pid_dead'` | exit 0 |
| R2b | stop-rule fork: a vanished home fails as stale | `claude_session_stop_confirmed`: `_claude_cli(["stop", …])` becomes `_claude_cli(list(["stop", …]))` | `'claude-stop-rule-fork-stale:claude_session_stop_confirmed'` | exit 0 |
| R3a | a pid-less row that is not stopped/done never confirms (fail-open leg) | `_stop_confirmed_pid_dead`: the pid-less branch's final `return False` becomes `return True` | `..._missing_pid_unconfirmed`, `..._no_state_no_pid_unconfirmed`: `assert 'stopped' == 'background-stop-unconfirmed'` | exit 0 (4 passed) |
| R3b | a pid-less `stopped`/`done` row confirms (over-refusal leg) | the same branch: `if state in ("stopped", "done"): return True` becomes `return False` | `..._stopped_state_no_pid_stopped`, `..._done_state_no_pid_stopped`: `assert 'background-stop-unconfirmed' == 'stopped'` | exit 0 |

**Accepted residual on R2.** The enumeration only recognizes a list display as `_claude_cli`'s first argument. R2b shows that a `list([...])` wrapper hides a stop home from it, so a third home spelled that way would pass. The fork closes at 4a-2.

## Disclosure: a detector that cannot fail

`test_launch_ledger_compat.py::test_launch_mode_background_identity` asserts `launch_ledger.LAUNCH_MODE_BACKGROUND is claude_modes.MODE_BACKGROUND`. The probe was to set `LAUNCH_MODE_BACKGROUND = "background"` (a hand-copied literal). The test stayed **green**: exit 0, 1 passed. CPython interns the literal, so `is` holds for a copy. The test does not guard the one-home invariant it names.

The derivation itself is in place, and the round-3 fix audits discharged it. The detector gap is disclosed on the PR and routed as a follow-up: replace the test with an AST check that `launch_ledger.py` and `engine_adapter.py` bind no `"background"` string constant.
