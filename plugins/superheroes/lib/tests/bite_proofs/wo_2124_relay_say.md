# Bite-proof record: #2124 the relay check blames only a step it can see, and the advisor sends exactly the composed text

Detectors under proof:
- `plugins/superheroes/lib/tests/test_cloud_relay.py`
  `test_the_mismatch_sentences_name_only_the_relays_send_against_the_stored_text` (`[header-dropped]`, `[unattributable]`).
- `plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py`
  `test_the_relayed_answer_steps_carry_the_advisor_send_rule` (six rule phrases).

Guarded code: `plugins/superheroes/lib/cloud_relay.py` `_say`, and
`plugins/superheroes/skills/showrunner/reference/wave-watch.md` § "Another account", steps 2 to 4.
Base: `2fb9eb6d` (committed before any probe). Orchestrator-typed, light lane.
Every neutralization was a targeted Edit, undone by the inverse Edit before the next element; the tree
read clean (`git status --short` empty) after the last revert. No `git checkout`, `restore`, `reset` or
`stash` was used. Detectors were not edited between red and green.
Command prefix (worktree root): `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest <node ids> -q -p no:cacheprovider`.
Captures below drop only the uv `UV_NATIVE_TLS` deprecation warning line and pytest's traceback body;
nothing else was redacted.

## E1 the unattributable mismatch sentence

- **Guarded element:** `_say`, the `relay-text-mismatch` entry of `why` (the `# axis:` line above `_say`'s header-dropped branch).
  Axis: a mismatch it cannot attribute names only the relay's send against the stored text.
- **Neutralization:** restored the pre-change sentence `"The relay sent message %s with text that differs from yours (first difference at character %s)"`.
- **Raw red:**

```
E             - The relay's send of message 13db7907b9fc differs from the stored text (first difference at character 70); this check sees only that send, so it cannot tell which step changed the text; it was not delivered.
E             + The relay sent message 13db7907b9fc with text that differs from yours (first difference at character 70); it was not delivered.
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_the_mismatch_sentences_name_only_the_relays_send_against_the_stored_text[unattributable]
1 failed, 1 passed in 0.94s
```

## E2 the header-dropped sentence

- **Guarded element:** `_say`, the `headerDropped` branch's return.
  Axis: a header-dropped send is described as the relay's send against the stored text, not as the relay dropping it.
- **Neutralization:** restored `"The relay sent message %s with its header line dropped; it was not delivered."`.
- **Raw red:**

```
E             - The relay's send of message 8f2b09d4fc8d is the stored text with its header line dropped; it was not delivered.
E             + The relay sent message 8f2b09d4fc8d with its header line dropped; it was not delivered.
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_the_mismatch_sentences_name_only_the_relays_send_against_the_stored_text[header-dropped]
1 failed, 1 passed in 0.45s
```

## E3 the advisor-send rule in the doctrine

- **Guarded element:** wave-watch.md step 2's sentence "Then print the whole composed `relayMessage`, never a truncated view …".
  Axis: the advisor sends exactly the composed text it read. One phrase was neutralized as the
  representative; the other five parametrized phrases are the same `in` assertion on the same slice.
- **Neutralization:** deleted that sentence.
- **Raw red:**

```
E       AssertionError: assert 'print the whole composed `relayMessage`, never a truncated view' in '**Another account.** The answer goes through a relay, ...'
FAILED plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py::test_the_relayed_answer_steps_carry_the_advisor_send_rule[print-whole]
1 failed, 5 passed, 9 deselected in 0.19s
```

## Green (after the last revert, same node ids)

```
8 passed, 9 deselected in 0.48s
```

**Residual blind spots:** the doctrine test is a phrase match, so a rewording that keeps the rule but
drops a phrase fails it, and a phrase kept in a sentence that no longer states the rule passes it. The
sentence test pins the exact text, so it cannot tell a harmless rewording from a reintroduced blame
beyond the four blame phrases it forbids.
