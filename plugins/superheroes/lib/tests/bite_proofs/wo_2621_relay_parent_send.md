# Bite-proof record: #2621 only the advisor's own session sends a relay message; a fork hands it back

Detectors under proof:
- `plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py`
  `test_the_relayed_answer_steps_carry_the_advisor_send_rule` (`[parent-sends]`, `[fork-hands-back]`).

Guarded code: `plugins/superheroes/skills/showrunner/reference/wave-watch.md` § "Another account", step 5.
Base: `e9ed68e3` (committed before any probe). Orchestrator-typed, light lane.
The neutralization was a targeted Edit, undone by the inverse Edit; the tree read clean
(`git status --short` empty) after the revert. No `git checkout`, `restore`, `reset` or `stash` was
used. The detector was not edited between red and green.
Command prefix (worktree root): `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest <node ids> -q -p no:cacheprovider --tb=line`.
Captures below drop the long collapsed-section text inside the assertion lines (shown as `...`) and
pytest's `where` lines; nothing else was redacted.

## E1 the parent-only send rule and the fork hand-back

- **Guarded element:** step 5's two added sentences, "Only the advisor's own session sends it, never a
  fork of that session: …" and "A fork that ran the steps above writes the printed `relayMessage` to a
  file and hands the file back; …".
  Axis: only the advisor's own session sends a relay message; a fork hands the printed message back.
- **Neutralization:** deleted both sentences (the edit also joined step 6 onto step 5's line; the
  inverse edit restored both).
- **Raw red:**

```
E   assert "Only the advisor's own session sends it, never a fork of that session" in "**Another account.** The answer goes through a relay, ..."
E   assert 'A fork that ran the steps above writes the printed `relayMessage` to a file and hands the file back' in "**Another account.** The answer goes through a relay, ..."
FAILED plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py::test_the_relayed_answer_steps_carry_the_advisor_send_rule[parent-sends]
FAILED plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py::test_the_relayed_answer_steps_carry_the_advisor_send_rule[fork-hands-back]
2 failed, 6 passed in 3.44s
```

## Green (after the revert, same node ids)

```
8 passed in 0.14s
```

**Residual blind spots:** the test is a phrase match, so a rewording that keeps the rule but drops a
phrase fails it, and a phrase kept in a sentence that no longer states the rule passes it. It reads
only the "Another account" steps of wave-watch.md, not any other place an advisor might send a relay
message from.
