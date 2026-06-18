# Workhorse eval fixtures

Beds for the seeded-failure arms in `../gate.md`. Each is a minimal repo context
that drives one GATE/applicability path. These are exercised by the dogfood and
the deterministic safety tests; they are intentionally small.

- `library-cli/` — a change with NO runnable surface (exercises the ④⑤⑥-skip arm).
- `review-skipped/` — a diff that makes review-code reach `exit_skipped`.
- `ci-red/` — a change whose CI stays red (exercises the ⑧ bound → revert + GATE).

(Populate per the dogfood in Task 15; the deterministic invariants above do not
depend on these being filled to pass.)
