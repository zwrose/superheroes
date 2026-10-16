# Bite-proof record: the cloud builder's doctrine (WO-D1)

Detector: `plugins/superheroes/lib/tests/test_cloud_builder_doctrine.py` (`T`), six tests, one per item D1.1 to D1.6.
Guarded elements (declared by the order): D1.1 headless section, D1.2 container section, D1.3 environment-only test,
D1.4 per-round findings comment, D1.5 over-the-cap record rule, D1.6 answers on the issue.
D1.4 and D1.5 are no longer grouped: the pre-handback review's fix rounds replaced the over-the-cap paragraph with a pointer to the record reference, and
D1.5 is guarded by its own node now (entry 4 proves each with its own neutralization and red).

Each element was neutralized by a targeted edit in the shipped file (the cut text is quoted), the detector run alone,
then restored by the inverse edit (the cut text re-inserted at the same offset; the script asserted the restored file equals the
original byte-for-byte). Every command was run from the repository root as
`scripts/pinned-python -B -m pytest <node> -q -p no:cacheprovider`. The neutralize-run-restore-run sequence was driven by a
scratchpad script outside the repository. The test file was never edited during the proofs.

Disclosures:

- The `UV_NATIVE_TLS` deprecation warning that heads every run is omitted (it was removed with `grep -v` from the captures).
- The red captures below show the assertion and the summary lines; the long `assert ... in "<collapsed text>"` lines were
  display-cut at 600 characters (D1.6) by `cut -c`, and at 300 characters for entry 4's first red (D1.4, re-run at the final head). The cut lines are the `E   assert ...` echoes of the
  collapsed file text, not the verdict lines.
- D1.2: the test carries seven needles (one per bullet fact). Only the setup-text bullet was neutralized; the needles for the sandbox-network,
  signer, `pycache_prefix` and `size_count.py count --base` bullets are not individually proven by a red run.
- D1.1 and D1.3: likewise only the representative sentence was cut; the other needles in those tests are not individually proven.
- D1.6: the red proves the `wave-watch.md` side (the neutralization put the old text back). The `cloud.md` step 4 needles
  (`act on either copy inside the reply window`, `the issue comment carrying the advisor's answer`) sit in the same test
  after the `wave-watch.md` asserts, so they were not reached in the red run and are unproven by a red run.

## 1. D1.1 the headless section

Axis: the headless section names the question-dialog flag (a builder never asks in a dialog).

Note: the earlier text of this entry was changed by the pre-handback review's fix rounds (the sentence was reworded twice and the needle changed); re-proven at the final head.

- Neutralization (`cloud.md`, `## A headless session`): deleted the parenthetical `\n(its launch argv disallows the question tool through `--disallowedTools`)`
  (the line break before it included), leaving `It starts in auto permission mode with the question dialog off, so it never asks a` / `question in a dialog.`.
- Node: `T::test_headless_section_follows_the_applies_section_and_names_the_dialog_flag_and_push_limits`.
- Red: `AssertionError: disallows the question tool through `--disallowedTools``, `FAILED plugins/superheroes/lib/tests/test_cloud_builder_doctrine.py::test_headless_section_follows_the_applies_section_and_names_the_dialog_flag_and_push_limits` and `1 failed, 5 deselected in 0.15s`.
- Restore: the inverse edit; the parenthetical re-inserted, quoted back (`cloud.md:40-41`):
  `The cloud builder runs headless. It starts in auto permission mode with the question dialog off` / `(its launch argv disallows the question tool through `--disallowedTools`), so it never asks a`.
- Green: `1 passed, 5 deselected in 0.09s`.

## 2. D1.2 the container section

Axis: the container section names the packages the write sandbox needs (`bubblewrap`, `socat`) and the install fallback.

- Neutralization (`cloud.md`, `## The cloud container`): deleted the first bullet, from `- The setup text installs` through `disclose it in the build record.` and its newline (358 bytes).
- Node: `T::test_container_section_names_the_sandbox_facts`.
- Red: `AssertionError: `bubblewrap` and `socat``, `FAILED plugins/superheroes/lib/tests/test_cloud_builder_doctrine.py::test_container_section_names_the_sandbox_facts` and `1 failed in 0.11s`.
- Restore: the inverse edit; the bullet re-inserted, quoted back:
  `- The setup text installs `bubblewrap` and `socat` (the Claude write sandbox needs both on Linux;` / `  without them every claude implementer dispatch fails at start) and the project's pinned` / `  interpreter. When any of them is missing, install it with the package manager (or` / `  `uv python install`) before the first dispatch and disclose it in the build record.`
- Green: `1 passed in 0.09s`.

## 3. D1.3 environment-only by a test

Axis: a base-red failure that is not shown to be a named container limitation is an unresolved base failure, never environment-only.

- Neutralization (`cloud.md`, `## Verify: cloud-only failures`): deleted the paragraph
  `Anything else that is red on the base too is an unresolved base failure. Report it as that, never\nas environment-only.\n` (119 bytes).
- Node: `T::test_environment_only_failure_needs_both_the_base_run_and_a_named_limitation`.
- Red: `AssertionError: unresolved base failure`, `FAILED plugins/superheroes/lib/tests/test_cloud_builder_doctrine.py::test_environment_only_failure_needs_both_the_base_run_and_a_named_limitation` and `1 failed in 0.14s`.
- Restore: the inverse edit; the paragraph re-inserted, quoted back:
  `Anything else that is red on the base too is an unresolved base failure. Report it as that, never` / `as environment-only.`
- Green: `1 passed in 0.11s`.

## 4. D1.4 and D1.5 (two elements, two nodes, one neutralization and one red each)

Note: the earlier text of this entry was changed by the pre-handback review's fix rounds. The paragraphs it quoted were deleted and replaced, and its D1.5 test was replaced by a pointer test. Both halves are re-proven at the final head, each against its own paragraph.

### 4a. D1.4 the per-round post paragraph

Axis: each round's whole raw findings file is rendered through `render_raw` and posted as one comment before the next round.

- Neutralization (`cloud.md`, `## Review`): deleted the paragraph from `After each review round, render that round's whole raw findings file through `render_raw` in` through `session's own directory lives only on the container and is lost when the session ends.` and its blank line. The pointer paragraph after it was left as shipped.
- Node: `T::test_each_review_rounds_findings_land_on_the_pr_as_the_round_lands`.
- Red: `AssertionError: After each review round, render that round's whole raw findings file through `render_raw``, `FAILED plugins/superheroes/lib/tests/test_cloud_builder_doctrine.py::test_each_review_rounds_findings_land_on_the_pr_as_the_round_lands` and `1 failed, 5 deselected in 0.12s`.
- Restore: the inverse edit; the paragraph re-inserted after the `handback follows` / `skills/review-code/reference/review-record.md`.` lines, quoted back (`cloud.md:213-220`):
  `After each review round, render that round's whole raw findings file through `render_raw` in` / `` `lib/review_record.py` (the credential check runs on the whole file) and post it as one comment on `` / `the build's pull request when one exists, otherwise on the build's issue, naming the round and the` / `head it reviewed, before starting the next round. For a round with no findings, post a short "no` / `findings" line. If `render_raw` refuses the file as too large, post instead a short list of that` / `round's findings (severity, title, file:line), rendered through `render_raw` before it is posted, and` / `say the full text was too large. The review` / `session's own directory lives only on the container and is lost when the session ends.`
- Green: `1 passed, 5 deselected in 0.10s`.

### 4b. D1.5 the review-record pointer

Axis: the recovery rules for a refused record have one home (`review-record.md` § When it refuses); `cloud.md` points there and restates none of them.

- Neutralization (`cloud.md`, `## Review`): deleted the paragraph `When the record writer refuses, follow `skills/review-code/reference/review-record.md` § When it` / `refuses.` and its blank line. The per-round post paragraph was left as shipped.
- Node: `T::test_a_refused_review_record_is_recovered_by_the_record_reference_not_restated`.
- Red: `assert 'follow `skills/review-code/reference/review-record.md` § When it refuses' in "Every independent review seat runs through the reviewer pass. ...`, `FAILED plugins/superheroes/lib/tests/test_cloud_builder_doctrine.py::test_a_refused_review_record_is_recovered_by_the_record_reference_not_restated` and `1 failed, 5 deselected in 0.12s`.
- Restore: the inverse edit; the paragraph re-inserted before `## The cloud container`, quoted back (`cloud.md:222-223`):
  `When the record writer refuses, follow `skills/review-code/reference/review-record.md` § When it` / `refuses.`
- Green: `1 passed, 5 deselected in 0.10s`.
- Not proven by a red run: the second half of this test (the four restated phrases `Do not retry it`, `part i of n`, `split at finding boundaries`, `Never split one record` must be absent) was not neutralized; only the pointer needle was.

## 5. D1.6 answers on the issue

Axis: the advisor's answering rule no longer says "never on the issue"; the message stays the gate for `note-answered` and the issue copy is the allowed durable record.

- Neutralization (`wave-watch.md`, § Answering a builder note): replaced the two-sentence rule
  `Answer by message, or through the relay below. The send is still the gate for `note-answered`; posting the same answer on the issue as the durable record is allowed and recommended.`
  (181 bytes) with the old text `Answer by message, never on the issue.` (the fix reverted, which is a stronger neutralization than deleting the sentence).
- Node: `T::test_the_advisor_may_answer_on_the_issue_and_the_builder_acts_on_either_copy`.
- Red: `assert 'never on the issue' not in '# Contents ...'` with `'never on the issue' is contained here:`, `FAILED plugins/superheroes/lib/tests/test_cloud_builder_doctrine.py::test_the_advisor_may_answer_on_the_issue_and_the_builder_acts_on_either_copy` and `1 failed in 0.12s`.
- Restore: the inverse edit; the old text replaced by the rule, quoted back:
  `Answer by message, or through the relay below. The send is still the gate for `note-answered`; posting the same answer on the issue as the durable record is allowed and recommended.`
- Green: `1 passed in 0.10s`.

## 6. The container section's test-fixture git pin (WO-E)

Axis: a test whose fixture makes a git commit fails inside the write sandbox (the signer is unreachable), so the container section says to pin the fixture's git config in the test (`GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM`). Guarded by the new needle `GIT_CONFIG_GLOBAL` in the container test.

- Neutralization (`cloud.md`, `## The cloud container`, signer bullet): deleted the added sentences, from ` A test whose fixture makes a git commit fails` through `leaves the run to the builder's own shell.` and the line breaks inside them, keeping the bullet's first two sentences and the closing newline.
- Node: `T::test_container_section_names_the_sandbox_facts`.
- Red: `AssertionError: GIT_CONFIG_GLOBAL`, `FAILED plugins/superheroes/lib/tests/test_cloud_builder_doctrine.py::test_container_section_names_the_sandbox_facts` and `1 failed in 9.14s`. The `UV_NATIVE_TLS` deprecation warning is omitted from this record.
- Restore: the inverse edit; the sentences re-inserted after `The builder commits their work from its own shell.`, quoted back:
  `A test whose fixture makes a git commit fails` / `there for the same reason, so the test pins its own git config (`GIT_CONFIG_GLOBAL` set to` / `` `os.devnull`, `GIT_CONFIG_NOSYSTEM` set to `1`, the fixture passing its commit identity inline) `` / `and does not depend on the developer's. An order that runs such tests authorizes that pin or` / `leaves the run to the builder's own shell.`
- Green: `1 passed in 9.07s`.
- Not proven by a red run: the other seven needles of this test were not re-neutralized in this order (entry 2 covers the setup-text bullet only).
