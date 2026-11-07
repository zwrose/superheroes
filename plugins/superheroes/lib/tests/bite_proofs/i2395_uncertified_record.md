# Work order A (#2395) bite-proof: a review record never reads reviewed when its session did not converge

**Provenance:** claude / sonnet (implementer, work order A), maker family claude. Production under proof: `plugins/superheroes/lib/review_record.py` (`_status`, the summary claim check) and `plugins/superheroes/lib/review_record_session.py` (`account_from_session`). Test: `plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py`.

Declared guarded-element set (from the order): **E-line** (the `_status` append of `uncertified_line(...)`), **E-account** (the session writer setting `uncertified`), **E-mask** (the claim-check exclusion of the line). The order declares no other element, so `_validate`'s `uncertified` check, the clip and the `build_record` copy carry no neutralization here; this record claims no bite-proof for them.

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

- **guarded element:** `plugins/superheroes/lib/review_record.py`, `_summary`, `checked_text = checked_text.replace(uncertified_line(r["uncertified"]), "")` (line 2753).
- **axis:** the withheld-certificate line's literal cause is left out of the claim check, by its exact text (the `# axis:` comment above the block).
- **neutralization:** replaced
  `        checked_text = checked_text.replace(uncertified_line(r["uncertified"]), "")`
  with
  `        checked_text = checked_text.replace(uncertified_line(r["uncertified"]), uncertified_line(r["uncertified"]))`
  (the unmasked text goes to `_assert_no_bug_free_claim`).
- **detector:** `plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_reason_naming_a_forbidden_claim_still_writes_and_keeps_its_cause_in_the_line`
- **command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2395 -m pytest "plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py::test_a_reason_naming_a_forbidden_claim_still_writes_and_keeps_its_cause_in_the_line" -q -p no:xdist`

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_reason_naming_a_forbidden_claim_still_writes_and_keeps_its_cause_in_the_line _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-6/test_a_reason_naming_a_forbidd0')

    def test_a_reason_naming_a_forbidden_claim_still_writes_and_keeps_its_cause_in_the_line(tmp_path):
        """axis: E-mask — the line's literal cause is left out of the claim check; the record writes and reads not-reviewed."""
        cause = "the kept bug-free check errored at setup"
>       _, rec = _record(tmp_path, "cannot-certify", _cert(cause))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2395/plugins/superheroes/lib/tests/test_review_record_uncertified_2395.py:127: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-6/test_a_reason_naming_a_forbidd0')
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
1 failed in 0.78s
```

### restore

The inverse Edit put `""` back as the replacement text.

### restore receipt (restored lines quoted from the file)

```
2751-    # axis: the withheld-certificate line's literal cause is left out of the claim check, by its exact text — see bite-proof record i2395_uncertified_record
2752-    if r.get("uncertified"):
2753:        checked_text = checked_text.replace(uncertified_line(r["uncertified"]), "")
```

### raw green

```
.                                                                        [100%]
1 passed in 0.77s
```

## Disclosures

- Captures are well under the 32 KiB per-element ceiling; nothing was moved outside the repository.
- Redaction: none needed. The `/tmp/claude-0/...` pytest temp path is kept as printed; no secret, token or private URL appears. The `UV_NATIVE_TLS` deprecation warning that `scripts/pinned-python` prints first was left out of the quoted captures. The `^^^` marker line under `_record(...)` in the E-mask capture was retyped and its caret count may differ from pytest's own; every other line is as printed.
