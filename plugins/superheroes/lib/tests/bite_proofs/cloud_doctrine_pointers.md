# Cloud doctrine pointers bite-proof — `test_cloud_doctrine_pointers.py`

**Provenance:** claude write channel.

## Summary

| Class | Representative element | Axis | Proving test | Verdict |
|---|---|---|---|---|
| P-missing | charter section 11 pointer line | a cloud section with no pointer to the cloud reference | `test_each_cloud_section_points_at_the_cloud_reference[11]` | proven |
| V-unknown | `intake` verb in `cloud.md` | a verb the reference names that the CLI lacks | `test_every_cloud_builder_verb_the_reference_names_exists` | proven |
| V-token | the verb capture in `_named_verbs` | a misspelled verb that merely starts with a real one reads as the whole token | `test_verb_census_reads_whole_tokens` | proven |
| S-note-a | the words "builder note" in `### Size` of `review-discipline.md` | a Size section that does not name the builder note | `test_size_names_the_builder_note` | proven |
| S-note-b | the `skills/workhorse/reference/cloud.md` pointer in `### Size` | a Size section with no pointer to the cloud reference | `test_size_names_the_builder_note` | proven |

Unproven (no neutralization run, inside the order's four-run budget): the pointer lines of sections
1, 2, 3, 10 and 12 (same failure mode as section 11, one parametrized node each); the empty-set leg and
the required-verb leg of the verb test.

---

## P-missing — a cloud section without its pointer

**guarded element:** the pointer line in charter section 11. **axis:** the section body names
`skills/workhorse/reference/cloud.md`.

**neutralization:** deleted the line (and its trailing blank line) in `skills/workhorse/SKILL.md`:
`**Read \`skills/workhorse/reference/cloud.md\` § Handback when the launch prompt says \`Place: cloud session\`.**`

**raw red:**
```
F                                                                        [100%]
E       AssertionError: charter section 11 has no pointer to skills/workhorse/reference/cloud.md
FAILED plugins/superheroes/lib/tests/test_cloud_doctrine_pointers.py::test_each_cloud_section_points_at_the_cloud_reference[11]
1 failed in 0.37s
EXIT=1
```

**restore:** the inverse edit, putting the line and its blank line back just before the section's
`**Done when:**` paragraph.

**restore receipt:** after the restore the file reads
`**Read \`skills/workhorse/reference/cloud.md\` § Handback when the launch prompt says \`Place: cloud session\`.**`
followed by a blank line and `**Done when:** the ready PR's remote head contains …`.

**raw green:**
```
.                                                                        [100%]
1 passed in 1.42s
EXIT=0
```

## V-unknown — a verb the CLI lacks

**guarded element:** the `intake` verb in `skills/workhorse/reference/cloud.md`. **axis:** every
`cloud_builder.py <verb>` the reference names is a subcommand of `cloud_builder._build_parser()`.

**neutralization:** in `cloud.md`, `lib/cloud_builder.py intake --repo-root` became
`lib/cloud_builder.py intak --repo-root`.

**raw red:**
```
E       AssertionError: verbs the CLI lacks: ['intak']
FAILED plugins/superheroes/lib/tests/test_cloud_doctrine_pointers.py::test_every_cloud_builder_verb_the_reference_names_exists
1 failed in 0.38s
EXIT=1
```

**restore:** the inverse edit, `intak` back to `intake`.

**restore receipt:** `grep -n 'cloud_builder.py intak' cloud.md` printed only line 37, which reads
`2. Run \`python3 -B <plugin root>/lib/cloud_builder.py intake --repo-root <root> --launch-file <file>\`.`

**raw green:**
```
.                                                                        [100%]
1 passed in 0.34s
EXIT=0
```

## V-token — a verb read as a whole token

**guarded element:** the capture group of the regex in `_named_verbs`. **axis:** the captured verb is
the whole whitespace- or backtick-delimited token after `cloud_builder.py`, so `intake2` is not read
as `intake`.

**neutralization:** in `_named_verbs`, the regex `cloud_builder\.py\s+([^\s`]+)` became the old
`cloud_builder\.py\s+([a-z][a-z-]*)`.

**raw red:**
```
>       assert named == {"intake2"}
E       AssertionError: assert {'intake'} == {'intake2'}
E         Extra items in the left set:
E         'intake'
E         Extra items in the right set:
E         'intake2'
FAILED plugins/superheroes/lib/tests/test_cloud_doctrine_pointers.py::test_verb_census_reads_whole_tokens
1 failed in 0.22s
```

**restore:** the inverse edit, the old regex back to `cloud_builder\.py\s+([^\s`]+)`.

**restore receipt:** after the restore `_named_verbs` reads
`return set(re.findall(r"cloud_builder\.py\s+([^\s`]+)", text))`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.21s
```

## S-note-a — the Size section names the builder note

**guarded element:** the words "builder note" in `### Size` of `rubric/review-discipline.md`, line 64. **axis:** the Size section contains `builder note`.

**neutralization:** in `review-discipline.md`, `posting a builder note on its issue` became `posting a note on its issue`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________________ test_size_names_the_builder_note _______________________

    def test_size_names_the_builder_note():
        # axis: the Size section; the review-discipline Size section not naming the builder note and the cloud reference
        text = _read_plugin("rubric/review-discipline.md")
        match = re.search(r"(?ms)^### Size\n.*?(?=^#{2,3} |\Z)", text)
        assert match, "review-discipline.md has no ### Size section"
>       assert "builder note" in match.group(0)
E       assert 'builder note' in '### Size\n\nThis section is the one home of the size rule. The charters, the issue contract and the vet receipt\nsay ...eces do not work\napart — and the PR says why. Otherwise the tiebreak above holds: in doubt, more and smaller PRs.\n\n'
E        +  where '### Size\n\nThis section is the one home of the size rule. The charters, the issue contract and the vet receipt\nsay ...eces do not work\napart — and the PR says why. Otherwise the tiebreak above holds: in doubt, more and smaller PRs.\n\n' = <built-in method group of re.Match object at 0x7f631aea2ec0>(0)
E        +    where <built-in method group of re.Match object at 0x7f631aea2ec0> = <re.Match object; span=(1912, 7877), match="### Size\n\nThis section is the one home of the s>.group

/home/user/c8a-wo3/plugins/superheroes/lib/tests/test_cloud_doctrine_pointers.py:63: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_doctrine_pointers.py::test_size_names_the_builder_note
1 failed in 2.08s
EXIT=1
```

**restore:** the inverse edit, `posting a note on its issue` back to `posting a builder note on its issue`.

**restore receipt:** `sed -n 64p review-discipline.md` printed `builder in a cloud session messages the advisor by posting a builder note on its issue`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.10s
EXIT=0
```

## S-note-b — the Size section points at the cloud reference

**guarded element:** the `skills/workhorse/reference/cloud.md` pointer in `### Size` of `rubric/review-discipline.md`, line 65. **axis:** the Size section contains the cloud reference path.

**neutralization:** in `review-discipline.md`, `on its issue`, a newline and ``(`skills/workhorse/reference/cloud.md`). The`` became `on its issue. The`, which removes the pointer.

**raw red** (the run was piped through `grep -v "^E        +"`, which drops the two `where` lines of the assertion message and nothing else; the `EXIT=0` the shell printed is grep's, not pytest's. Pytest reported `1 failed`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________________ test_size_names_the_builder_note _______________________

    def test_size_names_the_builder_note():
        # axis: the Size section; the review-discipline Size section not naming the builder note and the cloud reference
        text = _read_plugin("rubric/review-discipline.md")
        match = re.search(r"(?ms)^### Size\n.*?(?=^#{2,3} |\Z)", text)
        assert match, "review-discipline.md has no ### Size section"
        assert "builder note" in match.group(0)
>       assert _CLOUD_REF in match.group(0)
E       assert 'skills/workhorse/reference/cloud.md' in '### Size\n\nThis section is the one home of the size rule. The charters, the issue contract and the vet receipt\nsay ...eces do not work\napart — and the PR says why. Otherwise the tiebreak above holds: in doubt, more and smaller PRs.\n\n'

/home/user/c8a-wo3/plugins/superheroes/lib/tests/test_cloud_doctrine_pointers.py:64: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_doctrine_pointers.py::test_size_names_the_builder_note
1 failed in 0.41s
```

**restore:** the inverse edit, `on its issue. The` back to `on its issue`, a newline and ``(`skills/workhorse/reference/cloud.md`). The``.

**restore receipt:** `sed -n 64,65p review-discipline.md` printed `builder in a cloud session messages the advisor by posting a builder note on its issue` then ``(`skills/workhorse/reference/cloud.md`). The``.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.11s
EXIT=0
```
