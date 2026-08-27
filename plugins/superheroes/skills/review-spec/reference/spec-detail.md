<!-- spec-detail-version: 1 -->

## Common Mistakes

| Mistake                                                                     | Fix                                                                                                                                                             |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Marking the spec approved / writing `passed`                                | review-spec is **advisory** — it **never writes `passed`** (the owner approves in Discovery step 8). Its only gate write is resetting a *stale* approval to `pending` (step 6). Approval stays the owner's call.       |
| Proposing a technical approach in a finding                                 | The spec is the *what*. Flag tech that leaked in; don't add more. The *how* stays with the build.                                                                |
| Inventing an answer to a requirements question                              | A genuine "what should happen here?" is a `judgment` finding for the owner — surface it; never fabricate the behavior.                                           |
| Adding implementation detail while "fixing" a vague requirement             | Keep the owner's plain-language voice. Replace vagueness with a concrete behavior/fit-criterion, not a mechanism.                                                |
| Flagging a missing unhappy path already tagged Defer-to-build / N-A         | Check the coverage tags before raising it — a recorded Defer/N-A is a decision, not a gap.                                                                       |
| Citing line numbers from the wrong file                                     | Spec citations point at `$SESSION_DIR/spec.md`. There is no parent doc to cross-cite for a spec.                                                                 |
| Re-raising findings the user skipped                                        | Check the `skip-set` and prior rounds before raising a finding.                                                                                                 |
| Skipping the all-six-lenses rule based on classification                    | The `touches` array is informational. All six doc-native lenses (Clarity, Verifiability, Failure-Mode, Coherence, Safety & access, Grounding) always run — each returns `[]` when there's nothing in its dimension.                                            |
| Dispatching reviewers by reading an agent file                              | The six lenses are bundled plugin agents — the five shared review-code reviewers in doc-native identity plus the spec-only `grounding-reviewer` seat. Dispatch the `<name>` reviewer with its methodology (resolve dispatch via the host tool map (`hosts/<host>-tools.md` at the plugin root)).               |
| Skipping the profile bootstrap                                              | If no profile resolves, run review-init's create procedure inline first; every run gets a provisional strict profile.                                        |
| Reading an annex as background (not checking for new decisions)             | Apply the annex-opinion test in **Annex opinion** below — if the core spec alone would decide differently, the annex carries an unapproved opinion; flag it under Coherence. |

## Annex opinion (finding class)

An **annex that introduces a new opinion** is a finding. An annex may only **elaborate decisions its core spec already makes**; a decision that is new belongs in the core, as an amendment.

**How to recognize it.** Take the sentence in the annex and ask whether the core spec, read alone, already decides it. If a builder reading only the core would build something different, the annex is deciding, not elaborating — that is the finding.

**Why a named class.** An annex is where a new decision is most likely to arrive looking like detail: it reads as elaboration, it sits below the core, and it is where a reviewer's attention is lowest. The class exists to point attention at exactly that.

**Severity.** An annex opinion that a build would act on is at least **Important** — the owner never approved it.

**What it is not.** An annex that restates a core decision in more detail is **not** this finding; neither is an annex that is merely long. The finding is *new opinion*, not verbosity.

**At review time.** Walk annex prose sentence by sentence. For each, state what the core alone implies; when they diverge, the annex is the finding, not background texture.

**Disposition.** Raise under Coherence; the fix is move the decision into the core (or an amendment), not delete elaboration that truly restates the core.

**Example shape (not a template).** Core says "owner picks a date"; annex says "default to next Monday" — the default is a new opinion unless the core already states it.
