# Work order B (#2137) bite-proof: an abandoned session's record never reads reviewed

**Provenance:** claude / sonnet (implementer, work order B), maker family claude. Production under proof: `plugins/superheroes/lib/review_record.py` (`_status`). Test: `plugins/superheroes/lib/tests/test_review_record_abandoned_2137.py`.

Declared guarded-element set (from the order): **E-status** (the one element), the `_status` abandoned line. The order declares no other element, so the other new checks (`_validate`'s `abandoned` check and the empty-reviewers allowance, the `--abandoned` refusals in `review_record_session.py`) carry no neutralization here; this record claims no bite-proof for them.

## E-status: the `_status` abandoned line

- **guarded element:** `plugins/superheroes/lib/review_record.py`, `_status`, the `if rec.get("abandoned"):` block's `lines.append("session abandoned: ...")` (line 922).
- **axis:** an abandoned session's record never reads reviewed (the `# axis:` comment above the block).
- **neutralization:** one Edit-tool edit replaced the line
  `        lines.append("session abandoned: the review loop was closed before it ended, so this record cannot read reviewed")`
  with
  `        pass`
  (the `if rec.get("abandoned"):` line and the `# fixed prose: no data enters` comment stayed).
- **detector:** `plugins/superheroes/lib/tests/test_review_record_abandoned_2137.py::test_an_abandoned_session_whose_every_other_condition_holds_still_reads_not_reviewed`, run alone by exact node id.
- **command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-b -m pytest "<node id>" -q -p no:xdist` (a single node, so xdist was switched off in place of `-n auto`), with `echo "pytest exit: $?"` after it.

### raw red (neutralized; unedited test)

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_an_abandoned_session_whose_every_other_condition_holds_still_reads_not_reviewed _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_an_abandoned_session_whos0')

    def test_an_abandoned_session_whose_every_other_condition_holds_still_reads_not_reviewed(tmp_path):
        """axis: E4 — the abandoned line alone keeps a record not-reviewed when findings are settled, CI is green on the
        final commit, a maker is named and a planned reviewer covered the final commit."""
        ctl_session, ctl_runs, ctl_body = _settled(_sub(tmp_path, "ctl"), "converged")
        ctl = Fake(runs=ctl_runs)
        assert _write(tmp_path, ctl_session, ctl, **ctl_body)["status"] == "reviewed"  # the same session, ended: reviewed
        assert "abandoned" not in rr.read(7, readers=ctl.readers())
        session, runs, body = _settled(_sub(tmp_path, "abn"), None)
        fake = Fake(runs=runs)
        out = _write(tmp_path, session, fake, abandoned=REASON, **body)
>       assert out["ok"] and out["status"] == "not-reviewed", out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E       assert (True and 'reviewed' == 'not-reviewed'
E         
E         - not-reviewed
E         ? ----
E         + reviewed)

/home/user/wt-2137-b/plugins/superheroes/lib/tests/test_review_record_abandoned_2137.py:73: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_abandoned_2137.py::test_an_abandoned_session_whose_every_other_condition_holds_still_reads_not_reviewed
1 failed in 0.50s
pytest exit: 1
```

The red is on the axis: with the line gone, the abandoned session whose other conditions all hold reads `reviewed`.

### restore

The inverse Edit-tool edit put the `lines.append(...)` back in place of `pass`. No `git checkout`, `git restore`, `git reset` or `git stash` was used.

### restore receipt (restored lines quoted from the file)

```
919-    # axis: an abandoned session's record never reads reviewed — see bite-proof record wo_b_2137_abandoned_record
920-    if rec.get("abandoned"):
921-        # fixed prose: no data enters
922:        lines.append("session abandoned: the review loop was closed before it ended, so this record cannot read reviewed")
```

### raw green (restored; same node, same command)

```
.                                                                        [100%]
1 passed in 0.47s
pytest exit: 0
```

## Disclosures

- Captures are well under the 32 KiB per-element ceiling; nothing was moved outside the repository.
- Redaction: none needed. The `/tmp/claude-0/...` pytest temp path is kept as printed; no secret, token or private URL appears. The pytest warning line about `UV_NATIVE_TLS` that `scripts/pinned-python` prints first was left out of the quoted captures.
