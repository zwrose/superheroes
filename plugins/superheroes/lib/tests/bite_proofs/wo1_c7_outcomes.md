# Bite-proof record: WO-1 outcomes (C7 L1)

Detector file: `plugins/superheroes/lib/tests/test_finding_outcomes_c7.py` (unedited during the proof).
Guarded file: `plugins/superheroes/lib/finding_outcomes.py`, run with `scripts/pinned-python -B`
(no bytecode written). Each neutralization is one targeted edit, restored by the inverse edit.
Restore receipt per element: the restored line quoted back and the sha256 of the file.

Declared guarded-element set (unchanged from WO-1): G1, G2, G3, G4, G5.

sha256 before every neutralization and after every restore:
`b7a40489af2efbf88f08c2532d20b9ac15d2573025ebf4256a070bac9cb90d98`

Each red/green run is the one test node named, run alone. The node id is the function; its
parametrized cases all run.

## G1 `has_stated_consequence` whitespace check (`finding_outcomes.py:30`)

Axis: a consequence that is only whitespace is not a stated consequence.

- Neutralization: `consequence.strip() != ""` became `consequence != ""`.
- sha256 neutralized: `a339e47675269e274c5e76ce3fb729dafc4fe6b27d7f5b6a111d789f8854354a`
- Detector: `test_e1_unstated_consequence`. Red: `1 failed, 7 passed`; the failing case is
  `[whitespace]`, `assert True is False` for `{'consequence': '  \n\t '}`.
- Restored line: `    return isinstance(consequence, str) and consequence.strip() != ""`
- Green: `8 passed in 0.32s`

## G2 `merged_consequence` any-real-wins rule (`finding_outcomes.py:42`)

Axis: a merged finding is `real` when any member is `real`, whatever the member order.

- Neutralization: `if review_findings_schema.REAL in kinds:` became
  `if False and review_findings_schema.REAL in kinds:`.
- sha256 neutralized: `a9b6a8ec2cc6cc8b43e64d4c4c313e223d6e3d14c1c87185def9b8d5311e0868`
- Detector: `test_e3_merged_kind`. Red: `3 failed, 5 passed`; failing cases `[cq-real]`,
  `[real-cq]`, `[real-real]`, each `assert None == 'real'`.
- Restored lines: `    if review_findings_schema.REAL in kinds:` then
  `        kind = review_findings_schema.REAL`
- Green: `8 passed in 0.14s`

## G3 `canon_decides` supersession check (`finding_outcomes.py:75`)

Axis: a Canon entry that a later complete entry supersedes does not decide.

- Neutralization: `if _supersedes_target(line) == entry_id:` became
  `if False and _supersedes_target(line) == entry_id:`.
- sha256 neutralized: `8ac499e21b5332a5819f1ca5baccf10778e26ff59afea0400bffd32d19482f98`
- Detector: `test_e4_canon_does_not_decide`. Red: `1 failed, 4 passed`; failing case
  `[superseded]`, `assert True is False`.
- Restored lines: `        if _supersedes_target(line) == entry_id:` then `            return False`
- Green: `5 passed in 0.11s`

## G4 `sheet_answer_decides` settled-answer check (`finding_outcomes.py:113`)

Axis: only an `accept` answer, or an `option` answer with a non-blank option id, decides.

- Neutralization: the final return
  `return answer == "option" and isinstance(option_id, str) and option_id.strip() != ""`
  became `return True`.
- sha256 neutralized: `551bf0602adbd18e76b710233e24c4af65e1572bbac333da3b7230acd8fc9ce2`
- Detector: `test_e5_sheet_answer_decides`. Red: `7 failed, 13 passed`; failing cases
  `answers5` to `answers11` (discuss, something-else, None, aligned, option with no id, option with
  empty id, option with int id), each `assert True is False`.
- Red capture note: the tool display truncated the middle of the red output (5941 characters,
  covering the failure bodies for `answers7` to `answers10`). The captured parts are the first
  three failure bodies, the last two, and the full short-test-summary listing of the 7 failures.
  The lost span is not reconstructed.
- Restored lines: `    option_id = doc.get("optionId")` then
  `    return answer == "option" and isinstance(option_id, str) and option_id.strip() != ""`
- Green: `20 passed in 0.18s`

## G5 `settle` craft-only-when-exactly-code-quality branch (`finding_outcomes.py:172`)

Axis: only a kind of exactly `code-quality` settles as craft; any other value goes to the owner.

- Neutralization: `== review_findings_schema.CODE_QUALITY:` became
  `!= review_findings_schema.REAL:` in the condition at line 172.
- sha256 neutralized: `b69add599171459c5be2624ee1fdc9d4bd6808d5c4a7757667a088ee329e20a3`
- Detector: `test_e2_kind_not_code_quality_goes_to_owner`. Red: `5 failed`; failing cases
  `[none]`, `[unknown]`, `[case]`, `[int]`, `[list]`, each `assert 'craft' == 'left-for-owner'`.
- Restored line:
  `    if finding.get(review_findings_schema.CONSEQUENCE_KIND_KEY) == review_findings_schema.CODE_QUALITY:`
- Green: `5 passed in 0.12s`
