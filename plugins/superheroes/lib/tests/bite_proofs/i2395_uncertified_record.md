# Work order A (#2395) bite-proof: a review record never reads reviewed when its session did not converge

**Provenance:** claude / sonnet (implementer, work order A), maker family claude. Production under proof: `plugins/superheroes/lib/review_record.py` (`_status`, the summary claim check) and `plugins/superheroes/lib/review_record_session.py` (`account_from_session`). Test: `plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py`.

Declared guarded-element set (from the order): **E-line** (the `_status` append of `uncertified_line(...)`), **E-account** (the session writer setting `uncertified`), **E-mask** (the claim-check exclusion of the line); work order B adds **E-scope** (the exemption covers the `Left:` entry only) and **E-displayed** (the exemption reads the displayed entry, not a regenerated one). The order declares no other element, so `_validate`'s `uncertified` check, the clip and the `build_record` copy carry no neutralization here; this record claims no bite-proof for them.

Every command below is `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2395 -m pytest "<node id>" -q -p no:xdist` (a single node, so xdist was switched off in place of `-n auto`). Each neutralization is one Edit-tool edit, restored by the inverse Edit-tool edit; no `git checkout`, `git restore`, `git reset` or `git stash` was used.

## E-line: the `_status` append

- **guarded element:** `plugins/superheroes/lib/review_record.py`, `_status`, the `if rec.get("uncertified"):` block's `lines.append(uncertified_line(rec["uncertified"]))` (line 1664).
- **axis:** a session that did not converge never reads reviewed, whatever else is clear (the `# axis:` comment above the block).
- **neutralization:** replaced
  `        lines.append(uncertified_line(rec["uncertified"]))`
  with
  `        pass`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_cannot_certify_session_with_every_other_line_clear_reads_not_reviewed`
- **command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2395 -m pytest "plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_cannot_certify_session_with_every_other_line_clear_reads_not_reviewed" -q -p no:xdist`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_cannot_certify_session_with_every_other_line_clear_reads_not_reviewed _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-2/test_a_cannot_certify_session_0')

    def test_a_cannot_certify_session_with_every_other_line_clear_reads_not_reviewed(tmp_path):
        """axis: E-line — the withheld-certificate line alone keeps a record not-reviewed; the same session ended converged reads reviewed."""
        ctl_session, ctl_fake, ctl_body = _ended(_sub(tmp_path, "ctl"), "converged", _cert(REASON))
        assert _write(tmp_path, ctl_session, ctl_fake, ctl_body)["status"] == "reviewed"
        out, rec = _record(tmp_path, "cannot-certify", _cert(REASON))
        line = rr.uncertified_line({"terminal": "cannot-certify", "reason": REASON})
>       assert out["status"] == rec["status"] == "not-reviewed"
E       AssertionError: assert 'reviewed' == 'not-reviewed'
E         
E         - not-reviewed
E         ? ----
E         + reviewed

/home/user/wt-2395/plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py:72: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_cannot_certify_session_with_every_other_line_clear_reads_not_reviewed
1 failed in 0.79s
```

### restore

The inverse Edit put `lines.append(uncertified_line(rec["uncertified"]))` back in place of `pass`.

### restore receipt (restored lines quoted from the file)

```
1662-    # axis: a session that did not converge never reads reviewed, whatever else is clear — see bite-proof record i2395_uncertified_record
1663-    if rec.get("uncertified"):
1664:        lines.append(uncertified_line(rec["uncertified"]))
```

### raw green

```
.                                                                        [100%]
1 passed in 0.82s
```

## E-account: the session writer sets `uncertified`

- **guarded element:** `plugins/superheroes/lib/review_record_session.py`, `account_from_session`, the condition `if abandoned is None and state["terminal"] != "converged":` (line 1385).
- **axis:** a session that ended on any terminal but converged carries its terminal and the driver's reason (the `# axis:` comment above the condition).
- **neutralization:** replaced
  `    if abandoned is None and state["terminal"] != "converged":`
  with
  `    if abandoned is None and state["terminal"] != "converged" and False:`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_every_terminal_but_converged_reads_not_reviewed_and_names_itself[halted]`
- **command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2395 -m pytest "plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_every_terminal_but_converged_reads_not_reviewed_and_names_itself[halted]" -q -p no:xdist`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_every_terminal_but_converged_reads_not_reviewed_and_names_itself[halted] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_every_terminal_but_conver0')
terminal = 'halted'

    @pytest.mark.parametrize("terminal", UNCERTIFIED_TERMINALS)
    def test_every_terminal_but_converged_reads_not_reviewed_and_names_itself(tmp_path, terminal):
        """axis: E-account — the session writer carries the terminal and the driver's reason for each non-converged terminal."""
        kind = LAST_KIND.get(terminal)
        decisions = [{"round": 1, "kind": kind, "detail": "the driver's last word"}] if kind else []
        _, rec = _record(tmp_path, terminal, _cert(f"{terminal} for a stated cause"), decisions)
>       assert rec["status"] == "not-reviewed" and not rr.cleared(rec["status"])
E       AssertionError: assert ('reviewed' == 'not-reviewed'
E         
E         - not-reviewed
E         ? ----
E         + reviewed)

/home/user/wt-2395/plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py:85: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_every_terminal_but_converged_reads_not_reviewed_and_names_itself[halted]
1 failed in 3.99s
```

### restore

The inverse Edit removed ` and False` from the condition.

### restore receipt (restored lines quoted from the file)

```
1383-    uncertified = None
1384-    # axis: a session that ended on any terminal but converged carries the terminal and the driver's reason, so its record never reads reviewed — see bite-proof record i2395_uncertified_record
1385:    if abandoned is None and state["terminal"] != "converged":
```

### raw green

```
.                                                                        [100%]
1 passed in 0.75s
```

## E-mask: the claim-check exclusion of the line

Re-run in work order B against the new code: the work order A form (`checked_text.replace(uncertified_line(...), "")`) no longer exists.

- **guarded element:** `plugins/superheroes/lib/review_record.py`, `_summary`, the recomposed first line handed to the claim check: `checked_text = "\n".join((checked_first if l is first_line else l) for l in lines` (line 2762).
- **axis:** the exemption is the displayed withheld-certificate entry in the first line's `Left:` text only (the `# axis:` comment above the block).
- **neutralization:** replaced
  `    checked_text = "\n".join((checked_first if l is first_line else l) for l in lines`
  with
  `    checked_text = "\n".join((first_line if l is first_line else l) for l in lines`
  (the displayed first line, not the recomposed one, goes to `_assert_no_bug_free_claim`).
- **detector:** `plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_reason_naming_a_forbidden_claim_still_writes_and_keeps_its_cause_in_the_line`
- **command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2395b -m pytest "plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_reason_naming_a_forbidden_claim_still_writes_and_keeps_its_cause_in_the_line" -q -p no:xdist`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_reason_naming_a_forbidden_claim_still_writes_and_keeps_its_cause_in_the_line _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_a_reason_naming_a_forbidd0')

    def test_a_reason_naming_a_forbidden_claim_still_writes_and_keeps_its_cause_in_the_line(tmp_path):
        """axis: E-mask — the line's literal cause is left out of the claim check; the record writes and reads not-reviewed."""
        cause = "the kept bug-free check errored at setup"
>       _, rec = _record(tmp_path, "cannot-certify", _cert(cause))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2395/plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py:127: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_a_reason_naming_a_forbidd0')
terminal = 'cannot-certify'
certification = {'shape': None, 'reason': 'the kept bug-free check errored at setup'}
decisions = (), ledger = None

    def _record(tmp_path, terminal, certification=None, decisions=(), ledger=None):
        session, fake, body = _ended(tmp_path, terminal, certification, decisions, ledger)
        out = _write(tmp_path, session, fake, body)
>       assert out["ok"], out
E       AssertionError: {'ok': False, 'reason': 'review-record-forbidden-claim', 'detail': 'bug-free'}
E       assert False

/home/user/wt-2395/plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py:62: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_reason_naming_a_forbidden_claim_still_writes_and_keeps_its_cause_in_the_line
1 failed in 0.77s
```

### restore

The inverse Edit put `checked_first` back in place of `first_line` in the join expression.

### restore receipt (restored lines quoted from the file)

```
2762:    checked_text = "\n".join((checked_first if l is first_line else l) for l in lines
```

### raw green

```
.                                                                        [100%]
1 passed in 0.88s
```

## E-scope: the exemption covers the `Left:` entry only

- **guarded element:** `plugins/superheroes/lib/review_record.py`, `_summary`, the recomposed first line (lines 2756-2762): only the first line's `Left:` text loses the entry; the same text anywhere else (the Lane line, any other field) is still checked.
- **axis:** the exemption is the displayed `Left:` entry only, never every occurrence of the text (the `# axis:` comment above the block).
- **neutralization:** one Edit replaced the join and the check call
  `    checked_text = "\n".join((checked_first if l is first_line else l) for l in lines ...` and `    _assert_no_bug_free_claim(checked_text)`
  with the same join over `first_line` (the displayed first line), then the global form before the check call:
  `    if r.get("uncertified") and not compact and at is not None:`
  `        checked_text = checked_text.replace(missing[at], "")`
  (the displayed entry is removed from the whole checked text).
- **detector:** `plugins/superheroes/lib/tests/test_review_record_uncertified_mask_scope_684.py::test_identical_certificate_text_in_lane_reason_is_still_checked`
- **command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2395b -m pytest "plugins/superheroes/lib/tests/test_review_record_uncertified_mask_scope_684.py::test_identical_certificate_text_in_lane_reason_is_still_checked" -q -p no:xdist`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_identical_certificate_text_in_lane_reason_is_still_checked ________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-13/test_identical_certificate_tex0')

    def test_identical_certificate_text_in_lane_reason_is_still_checked(tmp_path):
        """axis: only the certificate occurrence in Left is exempt; identical forbidden text in Lane is refused before posting."""
        reason = "the kept bug-free check errored at setup"
        session, fake, body = _ended(tmp_path, "cannot-certify", _cert(reason))
        lane_reason = rr.uncertified_line({"terminal": "cannot-certify", "reason": reason})
        out = _write(tmp_path, session, fake, body, laneReason=lane_reason)
>       assert out["ok"] is False and out["reason"] == "review-record-forbidden-claim", out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E       assert (True is False)

/home/user/wt-2395/plugins/superheroes/lib/tests/test_review_record_uncertified_mask_scope_684.py:13: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_uncertified_mask_scope_684.py::test_identical_certificate_text_in_lane_reason_is_still_checked
1 failed in 0.79s
```

### restore

The inverse Edit put back the join over `checked_first` and removed the two `.replace` lines.

### restore receipt (restored lines quoted from the file)

```
2762:    checked_text = "\n".join((checked_first if l is first_line else l) for l in lines
2765:    _assert_no_bug_free_claim(checked_text)
```

### raw green

```
.                                                                        [100%]
1 passed in 0.70s
```

## E-displayed: the exemption reads the displayed entry, not a regenerated one

- **guarded element:** `plugins/superheroes/lib/review_record.py`, `_summary`, the entry lookup `at = next((i for i, m in enumerate(missing) if m.startswith(UNCERTIFIED_OPENING)), None)` (line 2758).
- **axis:** the exemption is the displayed entry, as clipped before the record was scrubbed, not a line regenerated from the scrubbed reason (the `# axis:` comment above the block).
- **neutralization:** replaced
  `if m.startswith(UNCERTIFIED_OPENING)), None)`
  with
  `if m == uncertified_line(r["uncertified"])), None)`
  (the entry is identified by the regenerated line).
- **detector:** `plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_long_reason_shortened_by_redaction_still_writes_and_keeps_the_line`
- **command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2395b -m pytest "plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_long_reason_shortened_by_redaction_still_writes_and_keeps_the_line" -q -p no:xdist`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_a_long_reason_shortened_by_redaction_still_writes_and_keeps_the_line ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-15/test_a_long_reason_shortened_b0')

    def test_a_long_reason_shortened_by_redaction_still_writes_and_keeps_the_line(tmp_path):
        """axis: E-displayed — the exemption is the entry as displayed (clipped before the scrub), not a line regenerated from the scrubbed reason."""
        # a token shape the record's scrub replaces in place (an assignment shape would be withheld whole), built from pieces
        secret = "gh" + "p_" + "A" * 36
        reason = "the kept bug-free check errored at setup " + secret + " " + "y" * 400
        assert len(reason) > 300
>       out, rec = _record(tmp_path, "cannot-certify", _cert(reason))
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2395/plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py:143: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-15/test_a_long_reason_shortened_b0')
terminal = 'cannot-certify'
certification = {'shape': None, 'reason': 'the kept bug-free check errored at setup [credential-shaped test token, redacted in this record] [run of y characters, elided]'}
decisions = (), ledger = None

    def _record(tmp_path, terminal, certification=None, decisions=(), ledger=None):
        session, fake, body = _ended(tmp_path, terminal, certification, decisions, ledger)
        out = _write(tmp_path, session, fake, body)
>       assert out["ok"], out
E       AssertionError: {'ok': False, 'reason': 'review-record-forbidden-claim', 'detail': 'bug-free'}
E       assert False

/home/user/wt-2395/plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py:62: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_long_reason_shortened_by_redaction_still_writes_and_keeps_the_line
1 failed in 0.73s
```

### restore

The inverse Edit put `m.startswith(UNCERTIFIED_OPENING)` back in place of `m == uncertified_line(r["uncertified"])`.

### restore receipt (restored lines quoted from the file)

```
2758:        at = next((i for i, m in enumerate(missing) if m.startswith(UNCERTIFIED_OPENING)), None)
```

### raw green

```
.                                                                        [100%]
1 passed in 0.73s
```

## Work order C2 entries: the attested session and the hand account's terminal, source and note

**Provenance:** claude / sonnet (implementer, work order C2). Detectors are the tests work order C wrote in `plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py`. Every command below is `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2395c2 -m pytest "<node id>" -q -p no:xdist`. Each neutralization is one Edit-tool edit inside the named production function, restored by the inverse Edit-tool edit; no `git checkout`, `git restore`, `git reset` or `git stash` was used.

## E-attested: `account_from_session`'s `uncertified-manual` branch

- **guarded element:** `plugins/superheroes/lib/review_record_session.py`, `account_from_session`, the condition `if abandoned is None and state["terminal"] == decision_kinds.ATTESTED_VERDICT:` (line 1399).
- **axis:** an attested manual session is stamped by the session writer from the driver's own state, never from an extras key, so its record reads not-reviewed whatever else is written (the `# axis:` comment on line 1400).
- **neutralization:** replaced
  `    if abandoned is None and state["terminal"] == decision_kinds.ATTESTED_VERDICT:`
  with
  `    if abandoned is None and state["terminal"] == decision_kinds.ATTESTED_VERDICT and False:`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_an_attested_session_writes_not_reviewed_with_the_drivers_text`
- **command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2395c2 -m pytest "plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_an_attested_session_writes_not_reviewed_with_the_drivers_text" -q -p no:xdist`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_an_attested_session_writes_not_reviewed_with_the_drivers_text ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-21/test_an_attested_session_write0')

    def test_an_attested_session_writes_not_reviewed_with_the_drivers_text(tmp_path):
        """axis: E-attested — the session writer stamps an uncertified-manual session itself, so its record reads not-reviewed whatever the extras say."""
        session, fake, body = _attested(tmp_path, "att")
        out = _write(tmp_path, session, fake, body)
        assert out["ok"] is True and out["status"] == "not-reviewed", out
        rec = rr.read(7, readers=fake.readers())
        (line,) = rec["whatIsMissing"]
        assert rec["status"] == "not-reviewed" and not rr.cleared(rec["status"])
>       assert line == rr.uncertified_line({"terminal": "uncertified-manual", "reason": DRIVER_TEXT})
E       AssertionError: assert 'the review s...ason recorded' == 'the review s...s unreadable)'
E         
E         Skipping 83 identical leading characters in diff, use -v to show
E         - withheld: attested by hand over a driver failure (kind driver-error, class seat-defect, phase dispatch-panel, failure the seat result was unreadable)
E         + withheld: no reason recorded

/home/user/wt-2395/plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py:129: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_an_attested_session_writes_not_reviewed_with_the_drivers_text
1 failed in 0.84s
```

### restore

The inverse Edit removed ` and False` from the condition.

### restore receipt (restored lines quoted from the file)

```
1399:    if abandoned is None and state["terminal"] == decision_kinds.ATTESTED_VERDICT:
```

### raw green

```
.                                                                        [100%]
1 passed in 2.00s
```

## E-vocab: `_validate`'s `uncertified` terminal check

- **guarded element:** `plugins/superheroes/lib/review_record.py`, `_validate`, the `uncertified` check's `unc.get("terminal") in decision_kinds.ALL_VERDICTS` (line 832).
- **axis:** the withheld-certificate entry's terminal is one of the driver's own verdicts but converged, so no free text enters the record as a driver's word (the `# axis:` comment on line 830).
- **neutralization:** replaced
  `unc.get("terminal") in decision_kinds.ALL_VERDICTS`
  with
  `isinstance(unc.get("terminal"), str)`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_hand_account_terminal_is_one_of_the_drivers_verdicts_but_converged` (free-text ids `bug-free`, `mystery` and the empty string `""`; non-string ids `None` and `5`)
- **ids that go red:** `[bug-free]`, `[mystery]`, `[]` (the empty string). `[None]` and `[5]` stay green, as expected: the `isinstance` check still refuses a non-string terminal, so those two ids do not discriminate this neutralization.
- **command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2395c2 -m pytest "plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_hand_account_terminal_is_one_of_the_drivers_verdicts_but_converged" -q -p no:xdist`

### raw red

```
FFF..                                                                    [100%]
=================================== FAILURES ===================================
_ test_a_hand_account_terminal_is_one_of_the_drivers_verdicts_but_converged[bug-free] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-23/test_a_hand_account_terminal_i0')
bad = 'bug-free'

    @pytest.mark.parametrize("bad", ["bug-free", "mystery", "", None, 5])
    def test_a_hand_account_terminal_is_one_of_the_drivers_verdicts_but_converged(tmp_path, bad):
        """axis: E-vocab — a terminal that is not a driver verdict is refused; each verdict but converged is accepted."""
        out, fake = _hand(tmp_path, "bad", {"terminal": bad, "reason": None})
>       assert out["ok"] is False and out["reason"] == "review-account-invalid" and out["detail"] == "uncertified", out
E       AssertionError: {'ok': False, 'reason': 'review-record-forbidden-claim', 'detail': 'bug-free'}
E       assert (False is False and 'review-recor...rbidden-claim' == 'review-account-invalid'
E         
E         - review-account-invalid
E         + review-record-forbidden-claim)

/home/user/wt-2395/plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py:170: AssertionError
_ test_a_hand_account_terminal_is_one_of_the_drivers_verdicts_but_converged[mystery] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-23/test_a_hand_account_terminal_i1')
bad = 'mystery'

    @pytest.mark.parametrize("bad", ["bug-free", "mystery", "", None, 5])
    def test_a_hand_account_terminal_is_one_of_the_drivers_verdicts_but_converged(tmp_path, bad):
        """axis: E-vocab — a terminal that is not a driver verdict is refused; each verdict but converged is accepted."""
        out, fake = _hand(tmp_path, "bad", {"terminal": bad, "reason": None})
>       assert out["ok"] is False and out["reason"] == "review-account-invalid" and out["detail"] == "uncertified", out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...}
E       assert (True is False)

/home/user/wt-2395/plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py:170: AssertionError
_ test_a_hand_account_terminal_is_one_of_the_drivers_verdicts_but_converged[] __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-23/test_a_hand_account_terminal_i2')
bad = ''

    @pytest.mark.parametrize("bad", ["bug-free", "mystery", "", None, 5])
    def test_a_hand_account_terminal_is_one_of_the_drivers_verdicts_but_converged(tmp_path, bad):
        """axis: E-vocab — a terminal that is not a driver verdict is refused; each verdict but converged is accepted."""
        out, fake = _hand(tmp_path, "bad", {"terminal": bad, "reason": None})
>       assert out["ok"] is False and out["reason"] == "review-account-invalid" and out["detail"] == "uncertified", out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...}
E       assert (True is False)

/home/user/wt-2395/plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py:170: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_hand_account_terminal_is_one_of_the_drivers_verdicts_but_converged[bug-free]
FAILED plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_hand_account_terminal_is_one_of_the_drivers_verdicts_but_converged[mystery]
FAILED plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_hand_account_terminal_is_one_of_the_drivers_verdicts_but_converged[]
3 failed, 2 passed in 1.00s
```

### restore

The inverse Edit put `unc.get("terminal") in decision_kinds.ALL_VERDICTS` back in place of `isinstance(unc.get("terminal"), str)`.

### restore receipt (restored lines quoted from the file)

```
832:                        and unc.get("terminal") in decision_kinds.ALL_VERDICTS and unc["terminal"] != "converged"
```

### raw green

```
.....                                                                    [100%]
5 passed in 0.73s
```

## E-source: `_summary`'s exemption condition

- **guarded element:** `plugins/superheroes/lib/review_record.py`, `_summary`, the condition `if r.get("uncertified") and r["uncertified"].get("source") == "session" and not compact:` (line 2762).
- **axis:** only an entry the session writer stamped is left out of the claim check; a hand account's entry is claim-checked (the `# axis:` comment on line 2760).
- **neutralization:** replaced
  `    if r.get("uncertified") and r["uncertified"].get("source") == "session" and not compact:`
  with
  `    if r.get("uncertified") and not compact:`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_hand_accounts_withheld_entry_is_claim_checked_but_the_sessions_is_not`
- **command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2395c2 -m pytest "plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_hand_accounts_withheld_entry_is_claim_checked_but_the_sessions_is_not" -q -p no:xdist`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_hand_accounts_withheld_entry_is_claim_checked_but_the_sessions_is_not _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-25/test_a_hand_accounts_withheld_0')

    def test_a_hand_accounts_withheld_entry_is_claim_checked_but_the_sessions_is_not(tmp_path):
        """axis: E-source — only an entry the session writer stamped is exempt from the claim check."""
        cause = "the kept bug-free check errored at setup"
        out, fake = _hand(tmp_path, "hand", {"terminal": "cannot-certify", "reason": cause})
>       assert out["ok"] is False and out["reason"] == "review-record-forbidden-claim", out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...}
E       assert (True is False)

/home/user/wt-2395/plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py:199: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_hand_accounts_withheld_entry_is_claim_checked_but_the_sessions_is_not
1 failed in 0.73s
```

### restore

The inverse Edit put ` and r["uncertified"].get("source") == "session"` back into the condition.

### restore receipt (restored lines quoted from the file)

```
2762:    if r.get("uncertified") and r["uncertified"].get("source") == "session" and not compact:
```

### raw green

```
.                                                                        [100%]
1 passed in 0.76s
```

## E-note: `uncertified_line` never carries the attestation note

- **guarded element:** `plugins/superheroes/lib/review_record.py`, `uncertified_line`, the returned line `return f"{UNCERTIFIED_OPENING}{u['terminal']}, not converged, so its certificate was withheld: {cause}"` (line 1635).
- **axis:** the human's attestation note is kept in the record's `uncertified.note` as data and enters no summary line.
- **neutralization:** replaced
  `    return f"{UNCERTIFIED_OPENING}{u['terminal']}, not converged, so its certificate was withheld: {cause}"`
  with
  `    return f"{UNCERTIFIED_OPENING}{u['terminal']}, not converged, so its certificate was withheld: {cause}" + (f"; note: {u['note']}" if isinstance(u.get("note"), str) else "")`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_the_attestation_note_is_kept_as_data_and_never_enters_the_summary`
- **command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2395c2 -m pytest "plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_the_attestation_note_is_kept_as_data_and_never_enters_the_summary" -q -p no:xdist`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_the_attestation_note_is_kept_as_data_and_never_enters_the_summary ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-27/test_the_attestation_note_is_k0')

    def test_the_attestation_note_is_kept_as_data_and_never_enters_the_summary(tmp_path):
        """axis: E-note — the human's attestation note is in the record's uncertified.note and in no summary line."""
        note = "the owner says it is bug-free"
        session, fake, body = _attested(tmp_path, "att", dict(ATTESTATION, note=note))
        out = _write(tmp_path, session, fake, body)
        assert out["ok"] is True and out["status"] == "not-reviewed", out
        rec = rr.read(7, readers=fake.readers())
        assert rec["uncertified"]["note"] == note and rec["uncertified"]["source"] == "session"
        for level in (0, 1):
>           assert note not in rr._summary(rec, level), level
E           AssertionError: 0
E           assert 'the owner s... is bug-free' not in '**Review re...tant · fixed'
E             
E             'the owner says it is bug-free' is contained here:
E               e); note: the owner says it is bug-free.
E               Nothing waits for the owner.
E               Lane: full (reported by the session).
E               Risk floor: full — risk-unclear-not-set: the project's risk areas are not set (missing: core-md-absent); proposal-taken: full is at or above the floor.
E               Withheld from reviewers: none....
E             
E             ...Full output truncated, use '-vv' to show

/home/user/wt-2395/plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py:143: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_the_attestation_note_is_kept_as_data_and_never_enters_the_summary
1 failed in 0.77s
```

### restore

The inverse Edit removed the appended `+ (f"; note: ...")` expression from the returned line.

### restore receipt (restored lines quoted from the file)

```
1635:    return f"{UNCERTIFIED_OPENING}{u['terminal']}, not converged, so its certificate was withheld: {cause}"
```

### raw green

```
.                                                                        [100%]
1 passed in 0.70s
```

## Disclosures

- Work order C2 redaction: the `/tmp/claude-0/...` pytest temp paths are kept as printed; the `UV_NATIVE_TLS` deprecation warning that `scripts/pinned-python` prints first was left out of the quoted captures; every other line is as printed.
- Captures are well under the 32 KiB per-element ceiling; nothing was moved outside the repository.
- Redaction: the `/tmp/claude-0/...` pytest temp path is kept as printed. In the E-displayed red capture, pytest printed the credential-shaped test token whole inside the `certification = ...` line; that token and the run of padding characters after it are replaced there by the bracketed notes, and the line is shortened accordingly. Every other line is as printed. The `UV_NATIVE_TLS` deprecation warning that `scripts/pinned-python` prints first was left out of the quoted captures. The `^^^` marker lines under `_record(...)` in the E-mask and E-displayed captures were retyped and their caret counts may differ from pytest's own.
- The E-line and E-account entries are work order A's captures (pycache prefix `/tmp/superheroes-pyc-2395`), not re-run in work order B; their guarded lines are unchanged except that `uncertified_line` now spells its opening through `UNCERTIFIED_OPENING`.
