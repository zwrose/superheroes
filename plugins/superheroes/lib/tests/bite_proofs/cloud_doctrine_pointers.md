# Cloud doctrine pointers bite-proof — `test_cloud_doctrine_pointers.py`

**Provenance:** claude write channel.

## Summary

| Class | Representative element | Axis | Proving test | Verdict |
|---|---|---|---|---|
| P-missing | charter section 11 pointer line | a cloud section with no pointer to the cloud reference | `test_each_cloud_section_points_at_the_cloud_reference[11]` | proven |
| V-unknown | `intake` verb in `cloud.md` | a verb the reference names that the CLI lacks | `test_every_cloud_builder_verb_the_reference_names_exists` | proven |

Unproven (no neutralization run, inside the order's four-run budget): the pointer lines of sections
1, 2, 3, 10 and 12 (same failure mode as section 11, one parametrized node each); the empty-set leg and
the required-verb leg of the verb test; `test_size_names_the_builder_note`.

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
