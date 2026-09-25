# WO-A (#1238) bite-proof — vet checks chokepoint

Per-guard bite proof for `parse_vet_checks`, `read_vet_checks`, `write_vet_checks`, `render_core` vet emission, `confirm()` allowlist, and configure view vet lines. Command:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-wo-a-1238 -m pytest "<nodeid>" -q
```

Raw red/green captures: `/private/tmp/wo-a-1238/bite-summary.txt` (E1–E10, E12–E18) and `/private/tmp/wo-a-1238/e11-red.txt` + `e11-green.txt` (E11 parse_core branch).

**Provenance:** cursor / composer-2.5.

## Summary table

| ID | Guarded element | Axis | Proving test | Verdict |
|---|---|---|---|---|
| E1 | parse_vet_checks section-duplicated branch | token section-duplicated | `test_parse_malformed_tokens[…section-duplicated]` | proven |
| E2 | section-empty branch | token section-empty | `test_parse_malformed_tokens[-section-empty]` | proven |
| E3 | stray-text branch | token stray-text | `test_parse_malformed_tokens[…stray-text]` | proven |
| E4 | name-empty branch | token name-empty | `test_parse_malformed_tokens[…name-empty]` | proven |
| E5 | name-duplicated branch | token name-duplicated | `test_parse_malformed_tokens[…name-duplicated]` | proven |
| E6 | field-duplicated branch | token field-duplicated | `test_parse_malformed_tokens[…field-duplicated]` | proven |
| E7 | field-empty branch | token field-empty | `test_parse_malformed_tokens[…field-empty]` | proven |
| E8 | evidence-missing branch | token evidence-missing | `test_parse_malformed_tokens[…evidence-missing]` | proven |
| E9 | records-missing branch | token records-missing | `test_parse_malformed_tokens[…records-missing]` | proven |
| E10 | unrecognized-line branch | token unrecognized-line | `test_parse_malformed_tokens[…unrecognized-line]` | proven |
| E11 | read_vet_checks parse_core None → unparseable | reason core-md-unparseable | `test_read_vet_checks_corrupt_json` | proven |
| E12 | read_vet_checks absent → empty + null reason | declared false when absent | `test_read_vet_checks_absent_core` | proven |
| E13 | confirm allowlist vetChecks | section survives confirm | `test_confirm_preserves_vet_checks_on_provisional_core` | proven |
| E14 | render_core vetChecks emission | section survives confirm | same confirm test (render neutralized) | proven |
| E15 | write_vet_checks vet-checks-malformed refusal | action refused + reason | `test_write_vet_checks_refused_malformed` | proven |
| E16 | write_vet_checks round-trip on ## in body | vet-checks-round-trip-refused | `test_write_vet_checks_refused_heading_in_body` | proven |
| E17 | configure view unreadable line | exact core-md-unparseable line | `test_render_vet_checks_unreadable_when_core_corrupt` | proven |
| E18 | configure view malformed line | ⚠ malformed line | `test_render_vet_checks_malformed_line` | proven |
