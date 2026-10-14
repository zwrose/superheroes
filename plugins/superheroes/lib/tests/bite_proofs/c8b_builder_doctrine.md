# Bite-proof record: the cloud builder's doctrine (WO-D1)

Detector: `plugins/superheroes/lib/tests/test_cloud_builder_doctrine.py` (`T`), six tests, one per item D1.1 to D1.6.
Guarded elements (declared by the order): D1.1 headless section, D1.2 container section, D1.3 environment-only test,
D1.4 per-round findings comment, D1.5 over-the-cap record rule, D1.6 answers on the issue.
D1.4 and D1.5 are grouped: the two sentences stand in adjacent paragraphs, and one neutralization (both paragraphs deleted) and one
red/green command (two nodes) cover both; each node went red on its own needles, listed below. Representative of the class: D1.4.

Each element was neutralized by a targeted edit in the shipped file (the cut text is quoted), the detector run alone,
then restored by the inverse edit (the cut text re-inserted at the same offset; the script asserted the restored file equals the
original byte-for-byte). Every command was run from the repository root as
`scripts/pinned-python -B -m pytest <node> -q -p no:cacheprovider`. The neutralize-run-restore-run sequence was driven by a
scratchpad script outside the repository. The test file was never edited during the proofs.

Disclosures:

- The `UV_NATIVE_TLS` deprecation warning that heads every run is omitted (it was removed with `grep -v` from the captures).
- The red captures below show the assertion and the summary lines; the long `assert ... in "<collapsed text>"` lines were
  display-cut at 400 characters (D1.4/D1.5) or 600 characters (D1.6) by `cut -c`. The cut lines are the `E   assert ...` echoes of the
  collapsed file text, not the verdict lines.
- D1.2: the test carries seven needles (one per bullet fact). Only the setup-text bullet was neutralized; the needles for the sandbox-network,
  signer, `pycache_prefix` and `size_count.py count --base` bullets are not individually proven by a red run.
- D1.1 and D1.3: likewise only the representative sentence was cut; the other needles in those tests are not individually proven.
- D1.6: the red proves the `wave-watch.md` side (the neutralization put the old text back). The `cloud.md` step 4 needles
  (`act on either copy inside the reply window`, `the issue comment carrying the advisor's answer`) sit in the same test
  after the `wave-watch.md` asserts, so they were not reached in the red run and are unproven by a red run.

## 1. D1.1 the headless section

Axis: the headless section names the question-dialog flag (a builder never asks in a dialog).

- Neutralization (`cloud.md`, `## A headless session`): deleted the sentence
  `It starts in auto permission mode with the question dialog off\n(`--disallowedTools AskUserQuestion`), so it never asks a question in a dialog. `
  (143 bytes, trailing space included).
- Node: `T::test_headless_section_follows_the_applies_section_and_names_the_dialog_flag_and_push_limits`.
- Red: `AssertionError: --disallowedTools AskUserQuestion`, `FAILED plugins/superheroes/lib/tests/test_cloud_builder_doctrine.py::test_headless_section_follows_the_applies_section_and_names_the_dialog_flag_and_push_limits` and `1 failed in 7.50s`.
- Restore: the inverse edit; the sentence re-inserted, quoted back:
  `It starts in auto permission mode with the question dialog off` / `(`--disallowedTools AskUserQuestion`), so it never asks a question in a dialog. `.
- Green: `1 passed in 0.16s`.

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

## 4. D1.4 and D1.5 (grouped; representative D1.4)

Axis (D1.4): each round's raw findings are posted on the PR before the next round. Axis (D1.5): a record over the cap is shortened and written again as one comment.

- Neutralization (`cloud.md`, `## Review`): deleted both paragraphs, from `After each review round, post` through `the reader parses one comment.` and its newline (538 bytes).
- Nodes (one command, two nodes): `T::test_each_review_rounds_findings_land_on_the_pr_as_the_round_lands` and `T::test_a_review_record_over_the_cap_is_shortened_never_split`.
- Red: `AssertionError: After each review round, post that round's raw findings` (D1.4), `AssertionError: `review-record-too-large`` (D1.5),
  `FAILED ...::test_each_review_rounds_findings_land_on_the_pr_as_the_round_lands`, `FAILED ...::test_a_review_record_over_the_cap_is_shortened_never_split` and `2 failed in 0.10s`.
- Restore: the inverse edit; both paragraphs re-inserted, quoted back:
  `After each review round, post that round's raw findings (or a short "no findings" line) as a PR` / `comment naming the round and the head it reviewed, before starting the next round. The review` / `session's own directory lives only on the container and is lost when the session ends.` / blank / `When the record writer refuses `review-record-too-large`, shorten the account to the outcome of each` / `round, pointing at the per-round findings comments, and write it again. Never split one record` / `across several comments, because the reader parses one comment.`
- Green: `2 passed in 0.11s`.
- Not separately proven: that D1.5's test stays red when only D1.4's paragraph is cut, and the reverse (the needles are disjoint, but no single-paragraph neutralization was run; the order's 18-command budget could not hold a sixth red/green pair).

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
