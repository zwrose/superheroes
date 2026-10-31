# Generation-6 session fixtures

Three session directories left by the earlier plugin version, which stamps `sessionGeneration: 6`.
They were minted from commit `e372aa4d` (the base this change builds on), where
`SESSION_GENERATION = 6` and `STATE_SCHEMA_VERSION = 5`.

## How they were minted

Nothing here is written by hand. The plugin tree at `e372aa4d` was extracted from `git archive`, and a
short throwaway script (not committed) imported that copy's round driver and drove it through its own
`next` and `submit` entry points, with the scripted reviewer, verifier, auditor and fixer artifacts
that the driver's own tests use. Each session was left exactly where the driver stopped; the script
then copied the session directory here. The copy leaves out the git checkout the session was driven
in (a nested repository cannot be committed; a test makes its own) and any lock file.

## The sessions

- `waiting-at-judgment`: a review with a plain defect and a tradeoff blocker, stopped at the
  judgment gate the earlier version put to the owner. The state holds the blockers it asked about in
  `_judgmentFindings`. Stored `maxRounds` is 7.
- `waiting-at-stall-menu`: a review whose fix kept failing its audit, stopped at the stall menu
  after its one recovery attempt. The state holds the menu in `_stallChoices` and the stalled targets
  in `_stallTargets`. Stored `maxRounds` is 7.
- `near-its-boundary`: stored `maxRounds` 7, sitting in round 7 with the fix leg pending and a
  blocking finding open.

## Using them

A test copies a session directory to its own temporary directory, gives it a fresh checkout, and points
`meta.json` at that checkout before driving it. A fixture is never driven in place.

The files carry the absolute paths of the machine they were minted on (the order manifests and the
`path` entries in the state that name them). They are bookkeeping from the minting run, and the tests
that drive a copy do not depend on them.
