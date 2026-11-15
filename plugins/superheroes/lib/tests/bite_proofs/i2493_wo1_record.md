# Work order WO-1 (#2493, #2494) bite-proof: the review record certifies low-risk-to-merge

**Provenance:** claude / sonnet-5.5 (implementer, WO-1), maker family claude. Production under proof: `plugins/superheroes/lib/review_record.py` (`listed_for_merge`, `waits_for_owner`, `repeat_held_elsewhere`, `_finding_lines`, `_status`, `carry_refusal`, `build_record`) and `plugins/superheroes/lib/leftover_accepting.py` (`_leftovers`). Detector file: `plugins/superheroes/lib/tests/test_review_record_certified_2493.py`.

Declared guarded-element set (from the order): **E-sev**, **E-risk**, **E-riskTrue**, **E-stamp**, **E-noout-minor**, **E-noout-important**, **E-repeat**, **E-carry**, **E-accept**, **E-noci**, plus **E-census** (its red is the pre-change run). Eleven elements, eleven entries; no equivalence class is used. Elements outside the declared set that the same file asserts (the production reader `_finding_risk`, the no-reason clause of `_finding_lines`, the summary's listed line, `_owner_only`'s use of `waits_for_owner`, the `leftForOwner` and `listedForMerge` lists) have **no neutralization declared and none run**: they are unproven by this record.

Every command is `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/superheroes-pyc-wo1 -m pytest <node id> -q -p no:xdist --tb=short` (the E-census red used the default traceback). The leading `warning: The UV_NATIVE_TLS environment variable is deprecated ...` line of every run is left out; it is the launcher's, not pytest's. Each neutralization is one Edit-tool edit, restored by the inverse Edit-tool edit; no `git checkout`, `git restore`, `git reset` or `git stash` was used. Nothing quoted below is a secret, token, private URL or personal detail, so nothing is redacted. Every capture is far under the 32 KiB per element and 128 KiB ceilings.

One run is not a proof and is disclosed: the first attempt at E-risk issued the Edit and the pytest run in parallel; the Edit was refused (its search text matched two places), so the run that came back `1 passed` ran against the **unneutralized** code. It is discarded and counts as no receipt; E-risk was redone sequentially (below).

## E-census: no copy of the awaits-owner test outside the predicates

- **guarded element:** the one-home rule: `review_record.py` and `leftover_accepting.py` read "left for the owner and not held elsewhere" only inside `listed_for_merge`, `waits_for_owner` and `repeat_held_elsewhere`.
- **axis:** a copy of the awaits-owner test reading the outcome and the repeat holder on its own (the docstring of the test).
- **neutralization:** none by edit. The red is the detector run once on the **unchanged base** (`7c8ffc6`), before any production change, where four such copies stand (`leftover_accepting.py` line 78 and three in `review_record.py`).
- **detector:** `test_16_no_site_pairs_the_left_for_owner_outcome_with_the_repeat_test_outside_the_predicates`

### raw red (base, detector unedited)

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_16_no_site_pairs_the_left_for_owner_outcome_with_the_repeat_test_outside_the_predicates _

    def test_16_no_site_pairs_the_left_for_owner_outcome_with_the_repeat_test_outside_the_predicates():
        """axis: the one-home census; a copy of the awaits-owner test reading the outcome and the repeat holder on its own."""
        homes = ("listed_for_merge", "waits_for_owner", "repeat_held_elsewhere")
        pair = re.compile(r"_LEFT_FOR_OWNER[\s\S]{0,120}?repeat_held_elsewhere")
        copies, found = [], []
        for name in ("review_record.py", "leftover_accepting.py"):
            text = (LIB / name).read_text(encoding="utf-8")
            lines = text.split("\n")
            for node in ast.parse(text).body:
                if isinstance(node, ast.FunctionDef) and node.name in homes:
                    found.append(node.name)
                    for n in range(node.lineno - 1, node.end_lineno):
                        lines[n] = ""
            rest = "\n".join(lines)
            copies += [f"{name}:{rest.count(chr(10), 0, m.start()) + 1}" for m in pair.finditer(rest)]
>       assert copies == []
E       AssertionError: assert ['review_reco...epting.py:78'] == []
E         
E         Left contains 4 more items, first extra item: 'review_record.py:1646'
E         Use -v to get more diff

/home/user/wt-2493/plugins/superheroes/lib/tests/test_review_record_certified_2493.py:267: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_certified_2493.py::test_16_no_site_pairs_the_left_for_owner_outcome_with_the_repeat_test_outside_the_predicates
1 failed in 1.40s
```

### restore

Nothing was neutralized; the production change itself is the cure.

### restore receipt

Not applicable (no edit to undo). The detector reads the changed sources in the green run.

### raw green (after the change)

```
.                                                                        [100%]
1 passed in 1.17s
```

## E-sev: `listed_for_merge`'s severity check

- **guarded element:** `review_record.py:1642`, `listed_for_merge`, `f.get("severity") in LISTED_SEVERITIES`.
- **axis:** only a Minor or Nit is listed; an Important, Critical or unknown severity left for the owner always waits.
- **neutralization:** replaced `f.get("severity") in LISTED_SEVERITIES and f.get("inRiskArea") is False` with `f.get("severity") in (*LISTED_SEVERITIES, "Important") and f.get("inRiskArea") is False`.
- **detector:** `test_8_an_important_or_critical_finding_left_for_the_owner_waits_whatever_its_risk_reading[Important]`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_8_an_important_or_critical_finding_left_for_the_owner_waits_whatever_its_risk_reading[Important] _
/home/user/wt-2493/plugins/superheroes/lib/tests/test_review_record_certified_2493.py:153: in test_8_an_important_or_critical_finding_left_for_the_owner_waits_whatever_its_risk_reading
    assert rec["status"] == rr.AWAITS_OWNER
E   AssertionError: assert 'reviewed' == 'awaits-owner'
E     
E     - awaits-owner
E     + reviewed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_certified_2493.py::test_8_an_important_or_critical_finding_left_for_the_owner_waits_whatever_its_risk_reading[Important]
1 failed in 2.05s
```

### restore

The inverse Edit put `f.get("severity") in LISTED_SEVERITIES and f.get("inRiskArea") is False` back.

### restore receipt (quoted from the file, `review_record.py:1642`)

```
1642:    return (isinstance(f, dict) and f.get("severity") in LISTED_SEVERITIES and f.get("inRiskArea") is False
```

### raw green

```
.                                                                        [100%]
1 passed in 1.29s
```

## E-risk: `listed_for_merge`'s `is False`

- **guarded element:** `review_record.py:1642`, `f.get("inRiskArea") is False`.
- **axis:** a finding is listed only when its risk reading is exactly False; an unknown reading keeps the card.
- **neutralization:** replaced `f.get("inRiskArea") is False` with `f.get("inRiskArea") is not True` (the edit's search text carried the following line `and (f.get("outcome") == _LEFT_FOR_OWNER` so it matched once).
- **detector:** `test_3_a_minor_of_unknown_risk_stays_a_card`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_3_a_minor_of_unknown_risk_stays_a_card __________________
/home/user/wt-2493/plugins/superheroes/lib/tests/test_review_record_certified_2493.py:77: in test_3_a_minor_of_unknown_risk_stays_a_card
    assert rec["status"] == rr.AWAITS_OWNER
E   AssertionError: assert 'reviewed' == 'awaits-owner'
E     
E     - awaits-owner
E     + reviewed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_certified_2493.py::test_3_a_minor_of_unknown_risk_stays_a_card
1 failed in 1.09s
```

### restore

The inverse Edit put `f.get("inRiskArea") is False` back.

### restore receipt (quoted from the file, `review_record.py:1642`)

```
1642:    return (isinstance(f, dict) and f.get("severity") in LISTED_SEVERITIES and f.get("inRiskArea") is False
```

### raw green

```
.                                                                        [100%]
1 passed in 1.15s
```

## E-riskTrue: the same check, dropped

- **guarded element:** `review_record.py:1642`, `f.get("inRiskArea") is False` (the other side: a risk-area finding).
- **axis:** a Minor inside a declared risk area is never listed.
- **neutralization:** replaced `f.get("inRiskArea") is False` with `True`.
- **detector:** `test_2_a_minor_in_a_declared_risk_area_stays_a_card`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_2_a_minor_in_a_declared_risk_area_stays_a_card ______________
/home/user/wt-2493/plugins/superheroes/lib/tests/test_review_record_certified_2493.py:68: in test_2_a_minor_in_a_declared_risk_area_stays_a_card
    assert rec["status"] == rr.AWAITS_OWNER
E   AssertionError: assert 'reviewed' == 'awaits-owner'
E     
E     - awaits-owner
E     + reviewed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_certified_2493.py::test_2_a_minor_in_a_declared_risk_area_stays_a_card
1 failed in 1.37s
```

### restore

The inverse Edit put `f.get("inRiskArea") is False` back in place of `True`.

### restore receipt (quoted from the file, `review_record.py:1642`)

```
1642:    return (isinstance(f, dict) and f.get("severity") in LISTED_SEVERITIES and f.get("inRiskArea") is False
```

### raw green

```
.                                                                        [100%]
1 passed in 1.20s
```

## E-stamp: the `inRiskArea` stamp in `build_record`

- **guarded element:** `review_record.py:2128-2129`, the `inRiskArea=rd["finding_risk"](a.get("repoRoot"), f.get("file"))` stamp.
- **axis:** every finding is stamped with the writer's own reading; an account's `inRiskArea` is overwritten, never trusted.
- **neutralization:** replaced `inRiskArea=rd["finding_risk"](a.get("repoRoot"), f.get("file"))` with `inRiskArea=f.get("inRiskArea", rd["finding_risk"](a.get("repoRoot"), f.get("file")))`.
- **detector:** `test_5_an_account_value_for_inriskarea_is_ignored`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_5_an_account_value_for_inriskarea_is_ignored _______________
/home/user/wt-2493/plugins/superheroes/lib/tests/test_review_record_certified_2493.py:97: in test_5_an_account_value_for_inriskarea_is_ignored
    assert rec["findings"][0]["inRiskArea"] is True
E   assert False is True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_certified_2493.py::test_5_an_account_value_for_inriskarea_is_ignored
1 failed in 1.74s
```

### restore

The inverse Edit put the stamp back as the reader's answer alone.

### restore receipt (quoted from the file, `review_record.py:2129`)

```
2129:                     inRiskArea=rd["finding_risk"](a.get("repoRoot"), f.get("file"))) for f in findings]
```

### raw green

```
.                                                                        [100%]
1 passed in 1.35s
```

## E-noout-minor: `_finding_lines` step 2 (a no-outcome Minor or Nit that waits)

- **guarded element:** `review_record.py:1701-1702`, the `if waits_for_owner(f, findings): lines.append(leftover_line(f))` under the no-outcome, Minor-or-Nit branch.
- **axis:** a no-outcome Minor or Nit in a risk area, or of unknown risk, is a card and adds the leftover line, never "has no outcome".
- **neutralization:** replaced `lines.append(leftover_line(f))` (in that branch) with `lines.append(f"finding {_name(f)} has no outcome")`.
- **detector:** `test_9_a_minor_with_no_outcome_is_listed_outside_a_risk_area_and_a_card_inside_one` (both parametrized cases, Minor and Nit)

### raw red

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_9_a_minor_with_no_outcome_is_listed_outside_a_risk_area_and_a_card_inside_one[Minor] _
/home/user/wt-2493/plugins/superheroes/lib/tests/test_review_record_certified_2493.py:166: in test_9_a_minor_with_no_outcome_is_listed_outside_a_risk_area_and_a_card_inside_one
    assert inside["status"] == rr.AWAITS_OWNER
E   AssertionError: assert 'not-reviewed' == 'awaits-owner'
E     
E     - awaits-owner
E     + not-reviewed
_ test_9_a_minor_with_no_outcome_is_listed_outside_a_risk_area_and_a_card_inside_one[Nit] _
/home/user/wt-2493/plugins/superheroes/lib/tests/test_review_record_certified_2493.py:166: in test_9_a_minor_with_no_outcome_is_listed_outside_a_risk_area_and_a_card_inside_one
    assert inside["status"] == rr.AWAITS_OWNER
E   AssertionError: assert 'not-reviewed' == 'awaits-owner'
E     
E     - awaits-owner
E     + not-reviewed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_certified_2493.py::test_9_a_minor_with_no_outcome_is_listed_outside_a_risk_area_and_a_card_inside_one[Minor]
FAILED plugins/superheroes/lib/tests/test_review_record_certified_2493.py::test_9_a_minor_with_no_outcome_is_listed_outside_a_risk_area_and_a_card_inside_one[Nit]
2 failed in 1.35s
```

### restore

The inverse Edit put `lines.append(leftover_line(f))` back.

### restore receipt (quoted from the file)

```
1701-                if waits_for_owner(f, findings):
1702:                    lines.append(leftover_line(f))
```

### raw green

```
..                                                                       [100%]
2 passed in 1.29s
```

## E-noout-important: `_finding_lines` step 3 (a no-outcome Important, Critical or unknown severity)

- **guarded element:** `review_record.py:1705`, the `else:` branch `lines.append(f"finding {_name(f)} has no outcome")`.
- **axis:** a no-outcome Important, Critical or unknown severity keeps its "has no outcome" line, so it withholds.
- **neutralization:** replaced `lines.append(f"finding {_name(f)} has no outcome")` (in that branch) with `pass`.
- **detector:** `test_10_an_important_or_critical_finding_with_no_outcome_keeps_its_line_and_the_record_not_reviewed` (Important and Critical)

### raw red

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_10_an_important_or_critical_finding_with_no_outcome_keeps_its_line_and_the_record_not_reviewed[Important] _
/home/user/wt-2493/plugins/superheroes/lib/tests/test_review_record_certified_2493.py:176: in test_10_an_important_or_critical_finding_with_no_outcome_keeps_its_line_and_the_record_not_reviewed
    assert rec["status"] == rr.NOT_REVIEWED
E   AssertionError: assert 'reviewed' == 'not-reviewed'
E     
E     - not-reviewed
E     ? ----
E     + reviewed
_ test_10_an_important_or_critical_finding_with_no_outcome_keeps_its_line_and_the_record_not_reviewed[Critical] _
/home/user/wt-2493/plugins/superheroes/lib/tests/test_review_record_certified_2493.py:176: in test_10_an_important_or_critical_finding_with_no_outcome_keeps_its_line_and_the_record_not_reviewed
    assert rec["status"] == rr.NOT_REVIEWED
E   AssertionError: assert 'reviewed' == 'not-reviewed'
E     
E     - not-reviewed
E     ? ----
E     + reviewed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_certified_2493.py::test_10_an_important_or_critical_finding_with_no_outcome_keeps_its_line_and_the_record_not_reviewed[Important]
FAILED plugins/superheroes/lib/tests/test_review_record_certified_2493.py::test_10_an_important_or_critical_finding_with_no_outcome_keeps_its_line_and_the_record_not_reviewed[Critical]
2 failed in 1.21s
```

### restore

The inverse Edit put `lines.append(f"finding {_name(f)} has no outcome")` back in place of `pass`.

### restore receipt (quoted from the file)

```
1704-                # axis: a no-outcome Important, Critical or unknown severity keeps its "has no outcome" line, so it withholds — see bite-proof record i2493_wo1_record (E-noout-important)
1705:                lines.append(f"finding {_name(f)} has no outcome")
```

### raw green

```
..                                                                       [100%]
2 passed in 1.22s
```

## E-repeat: the holder set in `repeat_held_elsewhere`

- **guarded element:** `review_record.py:1662-1663`, the `and not listed_for_merge(g)` clause of the `left` holder set.
- **axis:** a listed earlier finding holds no card, so a waiting repeat of it keeps its own.
- **neutralization:** removed ` and not listed_for_merge(g)` from `if isinstance(g, dict) and g.get("outcome") == _LEFT_FOR_OWNER and not listed_for_merge(g)}`.
- **detector:** `test_12_a_repeat_of_a_listed_finding_keeps_its_own_card`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_12_a_repeat_of_a_listed_finding_keeps_its_own_card ____________
/home/user/wt-2493/plugins/superheroes/lib/tests/test_review_record_certified_2493.py:198: in test_12_a_repeat_of_a_listed_finding_keeps_its_own_card
    assert rec["leftForOwner"] == ["r"]
E   AssertionError: assert [] == ['r']
E     
E     Right contains one more item: 'r'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_certified_2493.py::test_12_a_repeat_of_a_listed_finding_keeps_its_own_card
1 failed in 1.23s
```

### restore

The inverse Edit put ` and not listed_for_merge(g)` back.

### restore receipt (quoted from the file, `review_record.py:1663`)

```
1663:            if isinstance(g, dict) and g.get("outcome") == _LEFT_FOR_OWNER and not listed_for_merge(g)}
```

### raw green

```
.                                                                        [100%]
1 passed in 1.22s
```

## E-carry: `carry_refusal`'s admission of a no-outcome finding

- **guarded element:** `review_record.py:562`, `(f.get("outcome") is not None or listed_for_merge(f) or waits_for_owner(f, findings))`.
- **axis:** a no-outcome Important, Critical or unknown-severity earlier finding stops the carry; only a listed or card Minor or Nit passes.
- **neutralization:** replaced `(f.get("outcome") is not None or listed_for_merge(f) or waits_for_owner(f, findings))` with `(f.get("outcome") is not None or True)`.
- **detector:** `test_14_the_carry_rule_admits_a_listed_or_waiting_finding_and_refuses_an_important_with_no_outcome`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_14_the_carry_rule_admits_a_listed_or_waiting_finding_and_refuses_an_important_with_no_outcome _
/home/user/wt-2493/plugins/superheroes/lib/tests/test_review_record_certified_2493.py:236: in test_14_the_carry_rule_admits_a_listed_or_waiting_finding_and_refuses_an_important_with_no_outcome
    assert ask(dict(minor, severity=severity)) == "an earlier finding is still open"
E   AssertionError: assert None == 'an earlier finding is still open'
E    +  where None = <function test_14_the_carry_rule_admits_a_listed_or_waiting_finding_and_refuses_an_important_with_no_outcome.<locals>.ask at 0x7f18cf641800>({'id': 'm', 'severity': 'Important', 'file': 'a.py', 'outcome': None})
E    +    where {'id': 'm', 'severity': 'Important', 'file': 'a.py', 'outcome': None} = dict({'id': 'm', 'severity': 'Minor', 'file': 'a.py', 'outcome': None}, severity='Important')
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_certified_2493.py::test_14_the_carry_rule_admits_a_listed_or_waiting_finding_and_refuses_an_important_with_no_outcome
1 failed in 1.32s
```

### restore

The inverse Edit put the three-clause admission back in place of `(f.get("outcome") is not None or True)`.

### restore receipt (quoted from the file, `review_record.py:562`)

```
562:            isinstance(f, dict) and (f.get("outcome") is not None or listed_for_merge(f) or waits_for_owner(f, findings))
```

### raw green

```
.                                                                        [100%]
1 passed in 1.07s
```

## E-accept: `leftover_accepting`'s waiting match

- **guarded element:** `leftover_accepting.py:79`, `held = [f for f in findings if review_record.waits_for_owner(f, findings) and review_record._name(f) == name]`.
- **axis:** a `leftForOwner` entry is matched to a finding that waits for the owner, by the record's one predicate; a no-outcome risk-area Minor is asked for.
- **neutralization:** replaced the line with the base's two-line match, `held = [f for f in findings if f.get("outcome") == review_record._LEFT_FOR_OWNER` / `and review_record._name(f) == name and not review_record.repeat_held_elsewhere(f, findings)]`.
- **detector:** `test_15_the_leftover_check_asks_for_the_waiting_set_only`
- **not discriminated:** the test's second half (a listed Minor makes the record unreadable) holds under the base match as well as under the new one, so it does not tell them apart; the red above comes from the first half (a waiting no-outcome risk-area Minor).

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_15_the_leftover_check_asks_for_the_waiting_set_only ___________
/home/user/wt-2493/plugins/superheroes/lib/tests/test_review_record_certified_2493.py:245: in test_15_the_leftover_check_asks_for_the_waiting_set_only
    assert la.missing({"ok": True, "findings": [waiting], "leftForOwner": ["f1"]}, "") == [{"id": "f1", "title": "Slow retry"}]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2493/plugins/superheroes/lib/leftover_accepting.py:631: in missing
    leftovers = _leftovers(record)
                ^^^^^^^^^^^^^^^^^^
/home/user/wt-2493/plugins/superheroes/lib/leftover_accepting.py:83: in _leftovers
    raise Unreadable("leftForOwner entry %r names no finding left for the owner" % (name,))
E   leftover_accepting.Unreadable: leftForOwner entry 'f1' names no finding left for the owner
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_certified_2493.py::test_15_the_leftover_check_asks_for_the_waiting_set_only
1 failed in 1.38s
```

### restore

The inverse Edit put the one-line `waits_for_owner` match back.

### restore receipt (quoted from the file, `leftover_accepting.py:79`)

```
79:        held = [f for f in findings if review_record.waits_for_owner(f, findings) and review_record._name(f) == name]
```

### raw green

```
.                                                                        [100%]
1 passed in 1.42s
```

## E-noci: CI leaves `_status`

- **guarded element:** `review_record.py:1746-1747`, `_status`, the absence of any CI condition before `lines += finding_lines`.
- **axis:** a red, pending or unread CI withholds nothing from the certificate, and the record keeps its `ci` reading.
- **neutralization:** inserted, before `lines += finding_lines`, `if rec["ci"]["state"] != "green":` / `lines.append("CI is red")`. The order's text names `ci["state"]`; `_status` no longer holds a local `ci`, so the inserted line reads `rec["ci"]["state"]`.
- **detector:** `test_13_ci_is_not_part_of_the_certificate_but_the_record_still_carries_it` (red, pending, unavailable)

### raw red

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_13_ci_is_not_part_of_the_certificate_but_the_record_still_carries_it[red] _
/home/user/wt-2493/plugins/superheroes/lib/tests/test_review_record_certified_2493.py:212: in test_13_ci_is_not_part_of_the_certificate_but_the_record_still_carries_it
    assert rec["status"] == rr.REVIEWED and rec["whatIsMissing"] == []
E   AssertionError: assert ('not-reviewed' == 'reviewed'
E     
E     - reviewed
E     + not-reviewed
E     ? ++++)
_ test_13_ci_is_not_part_of_the_certificate_but_the_record_still_carries_it[pending] _
/home/user/wt-2493/plugins/superheroes/lib/tests/test_review_record_certified_2493.py:212: in test_13_ci_is_not_part_of_the_certificate_but_the_record_still_carries_it
    assert rec["status"] == rr.REVIEWED and rec["whatIsMissing"] == []
E   AssertionError: assert ('not-reviewed' == 'reviewed'
E     
E     - reviewed
E     + not-reviewed
E     ? ++++)
_ test_13_ci_is_not_part_of_the_certificate_but_the_record_still_carries_it[unavailable] _
/home/user/wt-2493/plugins/superheroes/lib/tests/test_review_record_certified_2493.py:212: in test_13_ci_is_not_part_of_the_certificate_but_the_record_still_carries_it
    assert rec["status"] == rr.REVIEWED and rec["whatIsMissing"] == []
E   AssertionError: assert ('not-reviewed' == 'reviewed'
E     
E     - reviewed
E     + not-reviewed
E     ? ++++)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_certified_2493.py::test_13_ci_is_not_part_of_the_certificate_but_the_record_still_carries_it[red]
FAILED plugins/superheroes/lib/tests/test_review_record_certified_2493.py::test_13_ci_is_not_part_of_the_certificate_but_the_record_still_carries_it[pending]
FAILED plugins/superheroes/lib/tests/test_review_record_certified_2493.py::test_13_ci_is_not_part_of_the_certificate_but_the_record_still_carries_it[unavailable]
3 failed in 1.38s
```

### restore

The inverse Edit removed the two inserted lines.

### restore receipt (quoted from the file)

```
1746-    # axis: CI is no part of the certificate; a red, pending or unread CI withholds nothing here, and the record keeps its `ci` reading for the merge sheet — see bite-proof record i2493_wo1_record (E-noci)
1747:    lines += finding_lines
```

### raw green

```
...                                                                      [100%]
3 passed in 1.21s
```
