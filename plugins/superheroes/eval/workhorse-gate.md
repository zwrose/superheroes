# Workhorse — eval gate

The producer's acceptance posture: **the safety behaviors are proven
deterministically; the happy path is the acceptance gate, not the only gate.**

## Deterministic invariants (the hard gate — pytest)

- **Never-merge floor.** Every merge/release/deploy/force-push shape — incl. the
  `gh api`/GraphQL merge paths — is DENIED by the enumerated deny-list, and the
  producer's own `git push` is ALLOWED (`test_enforcer.py`,
  `test_safety_invariants.py::test_never_merge_invariant_across_every_merge_shape`
  + `::test_producer_push_is_allowed`).
- **Self-protection (two surfaces).** Edits to band safety-machinery via Edit/Write
  AND via Bash (`sed -i` / redirection) are refused, and the Bash-write deny list
  covers every escalation safety basename (`test_hook_wiring.py`,
  `test_enforcer.py::test_denies_bash_write_to_safety_machinery`).
- **Process-level fail-closed.** The hook command is wrapped so a non-startable /
  crashing enforcer emits a deny (`test_hook_wiring.py` asserts the `||`-deny
  fallback); the step 0 **per-matcher canaries** (one through Bash, one through Write)
  refuse to run if EITHER hook surface isn't actually firing.
- **Path/ambiguity fail-closed.** The path guard, `reset.plan_reset`, `ci_loop`,
  and the `review_result` reader degrade to deny/GATE/halt on error or ambiguity,
  never to allow/clean/loop-free. (Command classification is by enumerated deny-list:
  a non-listed command is allowed by design — the producer must run build commands —
  so "fail-closed" for commands means the wrapper + non-string deny, not default-deny.)
- **CI-fix bound.** `ci_loop.decide` halts at max-N and on recurrence
  (`test_ci_loop.py`).
- **Base-freshness bound.** `freshness.decide` syncs while behind under the bound,
  `give_up_notify`s past it, and **GATEs on an unreadable ancestor read or a bad
  attempt** — it never assumes up-to-date on an unknown read (`test_freshness.py`).
- **Reset is state-scoped + protected-gated.** `reset.plan_reset` GATEs on a live
  lock; never auto-passes `--allow-protected`.
- **Parks-safely DECISION (pytest).** `reset.plan_reset` GATEs on a live lock or an
  unreadable status — it never claims a clean baseline it didn't achieve
  (`test_safety_invariants.py::test_parks_safely_decision_on_gate`). The *full* park
  (dev-server torn down + seeded state cleared + PR left draft) is orchestrator
  behavior (SKILL step 0 / "park safely"), exercised in the dogfood — not a unit invariant.

## Seeded-failure arms (fixtures)

- review `exit_skipped` / `halt` → GATE (the deterministic step 2 read).
- test-pilot failure → fix/GATE.
- CI red unfixable / loop exhausted → revert-to-draft + GATE.
- Branch behind base → freshen (merge base in, then CI on the integrated HEAD); an
  uncertain merge conflict → GATE; base advancing past the sync bound → NOTIFY at handback.
- **Library/CLI applicability arm** — the steps 4/5/6-skip path (the arm THIS repo's own
  changes take: no runnable surface → steps 2/3/7/8/9 only).

## Acceptance (dogfood)

Run Workhorse end-to-end on a real small issue: approved tasks → shipped PR + live
preview + readout. Acceptance, not the only gate.
