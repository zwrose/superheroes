# Bite-proof record: i2553_extra_audit_retired

Issue 2553, layer 2 of 2497: the advisor-ordered extra audit round is retired. Detector file:
`plugins/superheroes/lib/tests/test_extra_audit_retired_2553.py`. Each red and green below is one run of one exact node id with
`scripts/pinned-python -B -X pycache_prefix=/tmp/wt2497-pyc -m pytest <node id> -q -p no:xdist`.

The guarded-element set, declared in the order up front, is exactly these two: E-retired and E-noemit. Each was neutralized by a
targeted edit, run red, restored by the inverse edit, and run green. Captures are quoted whole except the
`warning: The UV_NATIVE_TLS ...` line (elided; each capture is under 2 KiB). No secret, token, URL or personal detail appears
in any capture; nothing was redacted beyond that elided warning line. Each node id below is written `file::test_name` with the
file being `plugins/superheroes/lib/tests/test_extra_audit_retired_2553.py`.

## E-retired

- **Guarded element:** `round_driver.py` `cmd_extra_audit`, the immediate refusal
  `_refuse_cmd(session_dir, EXTRA_AUDIT_CMD, EXTRA_AUDIT_RETIRED, detail=EXTRA_AUDIT_RETIRED_DETAIL)` (and its twin body for a
  session folder that does not exist). **Axis:** every `extra-audit` call refuses `extra-audit-retired` and names the bounded
  pass, before the lock, the upgrade gate, commit recovery or any read, and changes nothing but one journal row.
- **Detector (expected red):** `test_extra_audit_retired_2553.py::test_a_the_verb_refuses_extra_audit_retired_naming_the_bounded_pass_and_changes_nothing`
- **Neutralization:** one line inserted as the first statement after the docstring of `cmd_extra_audit`:
  `    return {"ok": True}`, so the function returns success instead of refusing.
- **Raw red:**
  ```
  >       assert out["ok"] is False and out["reason"] == RETIRED, out
  E       AssertionError: {'ok': True}
  E       assert (True is False)

  /home/user/wt-2497/plugins/superheroes/lib/tests/test_extra_audit_retired_2553.py:86: AssertionError
  FAILED plugins/superheroes/lib/tests/test_extra_audit_retired_2553.py::test_a_the_verb_refuses_extra_audit_retired_naming_the_bounded_pass_and_changes_nothing
  1 failed in 4.32s
  ```
- **Restore:** the inverse edit, deleting the inserted `    return {"ok": True}` line.
- **Restore receipt:** the restored lines, read back with a search of the file:
  ```
  13351:def cmd_extra_audit(session_dir, order_file, by, pr, repo=None, readers=None):
  13352-    """Refuse the retired `extra-audit` verb at once: no lock, no upgrade gate, no commit recovery, no
  13353-    read of the state, the receipt or the order file, and nothing posted. The one write is the journal
  13354-    row of a refusal, and only when the session folder exists."""
  13355-    if isinstance(session_dir, str) and os.path.isdir(session_dir):
  13356-        return _refuse_cmd(session_dir, EXTRA_AUDIT_CMD, EXTRA_AUDIT_RETIRED, detail=EXTRA_AUDIT_RETIRED_DETAIL)
  13357-    return {"ok": False, "reason": EXTRA_AUDIT_RETIRED, "detail": EXTRA_AUDIT_RETIRED_DETAIL}
  ```
  `git status --porcelain -- plugins/superheroes/lib/round_driver.py` printed ` M plugins/superheroes/lib/round_driver.py`
  (the file carries this order's own changes; it differs from the base by them and by no `return {"ok": True}` line).
- **Raw green:**
  ```
  .                                                                        [100%]
  1 passed in 5.92s
  ```

## E-noemit

- **Guarded element:** `review_record_session.py` line 1761, the conditional emitter
  `**({"extraAudit": {"why": extra.get("why")}} if isinstance(extra, dict) else {}),`. **Axis:** the account carries
  `rounds.extraAudit` only when the session state holds `extraAudit`, so a session that never held it never writes the key. The
  expression is already conditional at the base; the detector is the pin that keeps it so, and the file is otherwise unchanged by
  this order.
- **Detector (expected red):** `test_extra_audit_retired_2553.py::test_d_a_session_that_never_held_extra_audit_writes_an_account_with_no_rounds_extra_audit`
- **Neutralization:** the expression replaced with
  `**({"extraAudit": {"why": extra.get("why") if isinstance(extra, dict) else None}}),`, so the key is emitted for every session
  (with `why` `None` when the state holds no `extraAudit`), never a crash.
- **Raw red:**
  ```
  >       assert "extraAudit" not in account["rounds"], account["rounds"]
  E       AssertionError: {'count': 2, 'cap': 2, 'capKind': 'rounds', 'stoppedAtCap': True, ...}
  E       assert 'extraAudit' not in {'count': 2, 'cap': 2, 'capKind': 'rounds', 'stoppedAtCap': True, ...}

  /home/user/wt-2497/plugins/superheroes/lib/tests/test_extra_audit_retired_2553.py:175: AssertionError
  FAILED plugins/superheroes/lib/tests/test_extra_audit_retired_2553.py::test_d_a_session_that_never_held_extra_audit_writes_an_account_with_no_rounds_extra_audit
  1 failed in 5.40s
  ```
- **Restore:** the inverse edit, putting the original expression back.
- **Restore receipt:** `git status --porcelain -- plugins/superheroes/lib/review_record_session.py` printed nothing, and
  `git diff 667bfe8c7fb798ab8e4a389a0e4d8c37f0471f4b -- plugins/superheroes/lib/review_record_session.py` printed nothing: the file is
  byte-identical to the base. The restored line, quoted:
  `**({"extraAudit": {"why": extra.get("why")}} if isinstance(extra, dict) else {}),`
- **Raw green:**
  ```
  .                                                                        [100%]
  1 passed in 2.46s
  ```
