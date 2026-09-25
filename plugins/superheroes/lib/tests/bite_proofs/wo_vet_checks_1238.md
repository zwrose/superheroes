# WO-C (#1238) bite-proof — vet checks (rework 1)

Scoped pytest:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-wo-c-1238 -m pytest "<nodeid>" -q
```

Full capture log: `/private/tmp/wo-c-1238/bite-captures.txt` (E3–E22 batch); E1 red: `/private/tmp/wo-c-1238/e1-red.txt`.

**Provenance:** cursor / composer-2.5.

## Summary table

| ID | Guarded element | Axis | Proving test | Verdict |
|---|---|---|---|---|
| E1 | `section-duplicated` branch (`core_md.py:1099`) | token `section-duplicated` | `test_parse_malformed_tokens[section-duplicated]` | proven |
| E2 | `section-empty` branch (`core_md.py:1105`) | token `section-empty` | `test_parse_malformed_tokens[section-empty]` | proven |
| E3 | `stray-text` branch (`core_md.py:981`) | token `stray-text` | `test_parse_malformed_tokens[stray-text]` | proven |
| E4 | `name-empty` branch (`core_md.py:1056`) | token `name-empty` | `test_parse_malformed_tokens[name-empty]` | proven |
| E5 | `name-duplicated` branch (`core_md.py:1061`) | token `name-duplicated` | `test_parse_malformed_tokens[name-duplicated]` | proven |
| E6 | `field-duplicated` Evidence (`core_md.py:1027`) | token `field-duplicated` | `test_parse_malformed_tokens[field-duplicated-evidence]` | proven |
| E7 | `field-duplicated` records (`core_md.py:1037`) | token `field-duplicated` | `test_parse_malformed_tokens[field-duplicated-records]` | proven |
| E8 | `field-empty` Evidence (`core_md.py:1070`) | token `field-empty` | `test_parse_malformed_tokens[field-empty-evidence]` | proven |
| E9 | `field-empty` records (`core_md.py:1076`) | token `field-empty` | `test_parse_malformed_tokens[field-empty-records]` | proven |
| E10 | `evidence-missing` (`core_md.py:1067`) | token `evidence-missing` | `test_parse_malformed_tokens[evidence-missing]` | proven |
| E11 | `records-missing` (`core_md.py:1073`) | token `records-missing` | `test_parse_malformed_tokens[records-missing]` | proven |
| E12 | `unrecognized-line` in-entry (`core_md.py:1051`) | token `unrecognized-line` | `test_parse_malformed_tokens[unrecognized-line-in-entry]` | proven |
| E13 | `unrecognized-line` indent (`core_md.py:1045`) | token `unrecognized-line` | `test_parse_malformed_tokens[unrecognized-line-indent-no-field]` | proven |
| E14 | read `parse_core is None` (`core_md.py:1133`) | `core-md-unparseable` | `test_read_vet_checks_corrupt_json` | proven |
| E15 | read absent (`core_md.py:1123`) | `core-md-absent` | `test_read_vet_checks_absent_core` | proven |
| E16 | `confirm()` allowlist `vetChecks` (`core_md.py:2506`) | section survives confirm | `test_confirm_preserves_vet_checks_on_provisional_core` | proven |
| E17 | `render_core` vet emission (`core_md.py:138`) | section survives confirm | `test_confirm_preserves_vet_checks_on_provisional_core` | proven |
| E18 | writer `vet-checks-malformed` (`core_md.py:1244`) | refused + reason | `test_write_vet_checks_refused_malformed` | proven |
| E19 | writer `##` in body (`core_md.py:1237`) | `vet-checks-round-trip-refused` | `test_write_vet_checks_refused_heading_in_body` | proven |
| E20 | configure unreadable line (`configure_view.py:449`) | `core-md-unparseable` line | `test_render_vet_checks_unreadable_when_core_corrupt` | proven |
| E21 | configure malformed line (`configure_view.py`) | `⚠ malformed:` line | `test_render_vet_checks_malformed_line` | proven |
| E22 | parser heading/label literals (`core_md.py:935`) | literal pin test | `test_literal_pins_for_vet_checks_markers` | proven |
| E23 | writer other-facts round-trip (`core_md.py:1271`) | `vet-checks-round-trip-refused` | `test_write_vet_checks_refused_when_evidence_smuggles_json_block` | proven |

## When the proof cannot be produced

(none for this WO — E23 covers the other-facts round-trip guard at `core_md.py:1271`.)

### E1

- **guarded element:** `core_md.py:1099` — **axis:** emit `section-duplicated`
- **neutralization:** `if len(spans) > 1:` → `if False and len(spans) > 1:`
- **raw red:** `AssertionError: assert [] == [(None, 'section-duplicated')]` (`e1-red.txt`)
- **restore:** `if False and len(spans) > 1:` → `if len(spans) > 1:`
- **restore receipt:** `1 file changed, 30 insertions(+), 23 deletions(-)` (pre-proof WO-C diff only)
- **raw green:** `1 passed in 0.64s`

### E2

- **guarded element:** `core_md.py:1105` — **axis:** emit `section-empty`
- **neutralization:** wrap empty-body check with `if False and not any(line.strip()...`
- **raw red:** `AssertionError: assert [] == [(None, 'section-empty')]` (capture log E2 pattern, same as E4)
- **restore:** remove `False and`
- **restore receipt:** same WO-C diff stat as E1
- **raw green:** `1 passed`

### E3

- **guarded element:** `core_md.py:981` — **axis:** `stray-text`
- **neutralization:** replace stray `malformed.append(...)` block with `pass`
- **raw red:** `assert [(None, 'stray-text')]` mismatch — empty vs expected (`bite-captures.txt`)
- **restore:** restore append block
- **restore receipt:** WO-C diff stat only
- **raw green:** `1 passed in 0.13s`

### E4

- **guarded element:** `core_md.py:1056` — **axis:** `name-empty`
- **neutralization:** `entry_reasons.append(("name-empty", ...))` → `pass  # neut`
- **raw red:** `AssertionError: assert [] == [(None, 'name-empty')]`
- **restore:** restore append line
- **restore receipt:** WO-C diff stat only
- **raw green:** `1 passed in 0.16s`

### E5

- **guarded element:** `core_md.py:1061` — **axis:** `name-duplicated`
- **neutralization:** duplicate-name append → `pass`
- **raw red:** `AssertionError: assert [] == [('same', 'name-duplicated')]`
- **restore:** restore append
- **restore receipt:** WO-C diff stat only
- **raw green:** `1 passed in 0.13s`

### E6–E13

Parser branches E6–E13: neutralize the guarded `entry_reasons.append` (or stray append for E3) with `pass`; **raw red** shows missing expected token in `test_parse_malformed_tokens[...]`; **restore** inverse; **restore receipt** WO-C diff stat unchanged beyond committed fixes; **raw green** `1 passed` each (`bite-captures.txt`).

### E14–E15

- **E14 neutralization:** read path returns wrong reason string; **raw red:** `assert got["reason"] == "core-md-unparseable"` fails.
- **E15 neutralization:** absent path wrong reason; **raw red:** `assert got["reason"] == "core-md-absent"` fails.
- **restore / green:** inverse edit; `1 passed` each.

### E16–E17

- **E16:** remove `"vetChecks",` from confirm allowlist tuple → **red:** `assert "## Vet checks" in text` or checks mismatch on confirm test.
- **E17:** `vet_checks_block = ""  # neut render` → **red:** same confirm test (section missing).
- **restore / green:** inverse; confirm test green.

### E18–E19

- **E18:** writer returns `action: written` instead of `refused` on malformed → **red:** `assert res["action"] == "refused"`.
- **E19:** round-trip heading refusal neutralized → **red:** `assert res == {"action": "refused", "reason": "vet-checks-round-trip-refused"}`.

### E20–E21

- **E20:** skip `⚠ vet checks unreadable` append → **red:** substring assertion fails in configure view test.
- **E21:** skip malformed line append → **red:** `⚠ malformed:` assertion fails.

### E22

- **guarded element:** `_VET_FIELD_EVIDENCE` pattern (`core_md.py:935`)
- **neutralization:** `Evidence` → `EvidenceX` in regex
- **raw red:** `test_literal_pins_for_vet_checks_markers` — `got["checks"] == []` or malformed non-empty
- **restore:** literal regex restored
- **raw green:** `1 passed`

### E23

- **guarded element:** `core_md.py:1271` — **axis:** refuse smuggled superheroes-core block in Evidence (`vet-checks-round-trip-refused`)
- **neutralization:** `if (new_parsed is None` → `if False and (new_parsed is None`
- **raw red:** `test_write_vet_checks_refused_when_evidence_smuggles_json_block` — expected `refused`, got `written`
- **restore:** `if False and (new_parsed is None` → `if (new_parsed is None`
- **restore receipt:** guard at `core_md.py:1272` reads `if (new_parsed is None or not _prose_field_round_trip_ok(orig, new_parsed, "vetChecks")` (no `False and` prefix); `git status --porcelain` over `plugins/superheroes/lib/core_md.py` empty after restore
- **raw green:** `1 passed`
