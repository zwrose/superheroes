# Workhorse eval fixtures

Beds for the seeded-failure arms in `../gate.md`. Each is a minimal repo context
that drives one GATE/applicability path. These are exercised by the dogfood and
the deterministic safety tests; they are intentionally small.

- `library-cli/` — a change with NO runnable surface (exercises the steps 4/5/6-skip arm).
- `review-skipped/` — a diff that makes review-code reach `exit_skipped`.
- `ci-red/` — a change whose CI stays red (exercises the step 8 bound → revert + GATE).

(Populate per the dogfood in Task 15; the deterministic invariants above do not
depend on these being filled to pass.)
