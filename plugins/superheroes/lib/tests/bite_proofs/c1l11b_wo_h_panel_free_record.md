# C1-L11b (WO-H) bite-proof — a returning session that ran no panel is recorded from the phases it did run, and refused only when none ran

**Provenance:** implementer WO-H3, re-capturing WO-H's guard on `lib/review_record_session.py`, `lib/tests/test_c1l11b_carried_findings.py`

Declared guarded element (from the order): H1 `review_record_session._status_reviewers`, the `if not any(status.values()) and not out:` refusal (the axis comment at `review_record_session.py:322` cites this record). The condition has two operands and so two directions; each was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2266` (head `af12ff89`) under `timeout 600 scripts/pinned-python -B -m pytest <node ids> -q -p no:cacheprovider`. The captures are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear in the captures; the `/tmp/claude-0/...` paths are pytest temp directories).

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| H1a | `review_record_session.py:323` `_status_reviewers`, the `and not out` operand | a returning session that ran no panel but did run other phases lists those phases and is not refused | `test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed[changed]` |
| H1b | the same line, the `not any(status.values())` operand | a session that ran no panel and no other phase is refused with `review-session-unsupported` | `test_e1_a_changed_session_with_an_empty_surface_completed_by_hand_writes_no_record` |

Not separately neutralized (the unproven part of this record): the `[full]` parameter of the T1 test (a session that ran a panel) is not run under either neutralization; the older refusal for a hand-submit session with no seat status (cited as `c7l3_wo2_session_writer`) is a different record and is not re-proved here; nothing here neutralizes the `Refusal(UNSUPPORTED, NO_SEAT_RESULT)` raise itself, only its condition.

---

## H1a — the `and not out` operand

**axis:** a returning session that ran no panel but did run other phases lists those phases and is not refused.

**neutralization** (`review_record_session.py`, `_status_reviewers`: the `not out` operand dropped, so a panel-free session is refused even when it ran an audit or scoped finder):
```python
-    if not any(status.values()) and not out:
+    if not any(status.values()):
```

**raw red:** `timeout 600 scripts/pinned-python -B -m pytest "plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed[changed]" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed[changed] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_t1_a_carried_finding_a_la0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fa5f109d970>
record = None, read = 'changed'
order = [('dispatch-audits', 1), ('dispatch-scoped-finder', 1)]

    @pytest.mark.parametrize("record,read,order", [
        (None, "changed", [(RD.P_AUDITS, 1), (RD.P_SCOPED, 1)]),
        (ABANDONED, "full", [(RD.P_AUDITS, 1), (RD.P_PANEL, 1)]),
    ], ids=["changed", "full"])
    def test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed(tmp_path, monkeypatch, record, read, order):
        finding = _finding(27)
        s = _session(tmp_path, monkeypatch, [finding], record=record)
        first = s.next()
        state = s.state()
        assert first["action"] == RD.P_AUDITS and first["round"] == 1, first
        assert state["config"]["returning"]["read"] == read and state["config"]["returning"]["lastReviewed"] == s.reviewed
        key = finding[SC.FINDING_KEY_FIELD]
        # seeded under the stored key before the audit ran: a raised sequence and no disposition yet
        seeded = _row(state, key)
        assert seeded.get("raisedSeq") and seeded.get("raisedRound") == 1 and "disposition" not in seeded, seeded
        assert [t["id"] for t in first["payload"]["targets"]] == [key]
        assert first["payload"]["targets"][0]["fixHunks"], "the audit is given the hunk of the change over the finding's line"
        n, seen = _run(s, _respond(audit="discharged"))
        assert n["action"] == RD.P_TERMINAL and n["payload"]["verdict"] == "converged", seen
        assert seen[:len(order)] == order and (RD.P_PANEL in [a for a, _ in seen]) == (read == "full"), seen
        assert RD.P_APPLY_FIXES not in [a for a, _ in seen]
        state = s.state()
        row = _row(state, key)
        assert row["disposition"] == "fixed" and row["dispositionRound"] == 1 and row["dispositionSeq"] > row["raisedSeq"], row
        assert _carried(state) == {"keys": [key], "discharged": [key], "sentBack": []}
        # the record account relists it once, under its stored key, as fixed; no undecided row is left
>       findings = _account_findings(s, state)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py:160: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py:125: in _account_findings
    return TLR._every_finding_has_an_outcome(s.dir, state)["findings"]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l10_later_rounds.py:96: in _every_finding_has_an_outcome
    account = RS.account_from_session(d, TRRS.extras())
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2266/plugins/superheroes/lib/review_record_session.py:798: in account_from_session
    reviewers, raw = _status_reviewers(state, meta.get("headSha"), rows), []
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

state = {'_auditOutcome': {'ambiguous': [], 'attributedChange': [], 'audits': [{'auditor': 'codex', 'classKey': '::::the edite...6 = 26\n-+edited_b = 1\n++edited_b = 2\n  value_shared_27 = 27\n  value_shared_28 = 28\n  value_shared_29 = 29\n', ...}
setup = None
rows = [{'appendId': '5e67a728927a40588aba6f1581fb26c2#6', 'attempt': 0, 'cmd': 'next', 'fault': 'caller-error', ...}, {'atte...'caller-error', ...}, {'attempt': 0, 'cmd': 'next', 'outcome': 'emitted', 'phase': 'dispatch-scoped-finder', ...}, ...]

    def _status_reviewers(state, setup=None, rows=()):
        """Reviewer rows for a session driven by hand submit, which journals no seat: each panel round's seat
        status says which seats ran, and the reviewers' raw outputs were not stored."""
        status = _panel_rounds_with_status(state)
        out, ran_in = [], {}
        for rnd, seats in status.items():
            for seat, value in seats.items():
                if value == "run":
                    ran_in.setdefault(seat, []).append(rnd)
        for rnd, seats in status.items():
            unfilled = receipt_disclosures.unfilled_seats(seat_map_receipts.round_governing_map(state, rnd)) \
                & set(round_phases.DIMENSIONS)
            for seat in sorted(seats):
                if seat in unfilled:
                    continue  # listed below as an unfilled seat
                commit = _panel_head(state, rnd, setup)
                ran = seats[seat] == "run" and commit is not None  # any other value, or a panel with no recoverable head, is never credited
                fell = next((f.get("ran") for f in ((state["rounds"].get(str(rnd)) or {}).get("fellOpen") or ()) if isinstance(f, dict)
                             and f.get("seat") == seat and isinstance(f.get("ran"), str) and f["ran"]), None) if ran else None
                if not ran and any(r > rnd for r in ran_in.get(seat, ())):
                    continue  # a later round ran this seat: the earlier miss is recovered
                if ran and not fell and seat in ((state["rounds"].get(str(rnd)) or {}).get("fellOpenProvenanceMissing") or ()):
                    fell = "unknown"  # the session could not establish which vendor ran: never credit the configured one
                out.append(_reviewer(state, rnd, seat, "", ran, {"vendor": fell, "model": "unknown"} if fell else None,
                                     commit=commit, phase=sc.PANEL_PHASE))
            out += [_unfilled_reviewer(rnd, seat) for seat in sorted(unfilled)
                    if not any(r > rnd for r in ran_in.get(seat, ()))]
        by_round = {int(n): rec["audits"] for n, rec in (state.get("rounds") if isinstance(state.get("rounds"), dict) else {}).items()
                    if str(n).isdigit() and isinstance(rec, dict) and isinstance(rec.get("audits"), list)}
        for rnd, audits in by_round.items():
            later = {_audit_key(a) for r, rows in by_round.items() if r > rnd for a in rows if isinstance(a, dict) and not _audit_silent(a)}
            out += _audit_reviewers(state, rnd, audits, later)
        for rnd, phase in sorted({(r["round"], r["phase"]) for r in rows if r.get("cmd") == "submit" and r.get("outcome") == "accepted"
                                  and _int(r.get("round")) and r.get("phase") in (round_phases.P_VERIFIERS, round_phases.P_SECOND_TEST, *_RAW_PHASES[1:])}):
            # axis: a hand-accepted verifier phase with no staged finding is not a planned reviewer — see bite-proof record wo_6_1910_empty_verifier
            if phase == round_phases.P_VERIFIERS and _nothing_to_verify(state, rnd):
                continue
            prov = [p.get("ran") for p in ((state["rounds"].get(str(rnd)) or {}).get("verifierProvenance") or ()) if isinstance(p, dict)
                    and p.get("outcome") == "verdicts-folded"] if phase == round_phases.P_VERIFIERS else []  # a hand-accepted verifier, gap sweep or scoped finder journals no seat: one row a phase; a verifier whose verdicts were ignored or empty never ran
            head = _panel_head(state, rnd, setup, phase)
            out.append(_reviewer(state, rnd, "reviewer", phase.removeprefix("dispatch-") + " ", bool(head) and (bool(prov) or phase != round_phases.P_VERIFIERS),
                                 {"vendor": _text(*prov, _panel_head(state, rnd, None, phase, "vendor")) or "unknown", "model": "unknown"}, commit=head, phase=phase))
        # axis: a hand-submit session with no seat status in any round and no audit, scoped-finder, verifier, gap-sweep or second-test row holds nothing that says a reviewer ran — see bite-proof record c7l3_wo2_session_writer
        # axis: a returning session that ran no panel lists the phases it did run, and refuses only when none ran — see bite-proof record c1l11b_wo_h_panel_free_record
        if not any(status.values()):
>           raise Refusal(UNSUPPORTED, NO_SEAT_RESULT)
E           review_record.Refusal: ('review-session-unsupported', 'the session recorded no seat result or seat status')

/home/user/wt-2266/plugins/superheroes/lib/review_record_session.py:324: Refusal
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed[changed]
1 failed in 0.71s
```

**restore:** the inverse edit — ` and not out` put back on the condition.

**restore receipt** (`grep -n "if not any(status.values())" plugins/superheroes/lib/review_record_session.py`, then `git status --porcelain plugins/superheroes/lib/review_record_session.py`, which printed nothing):
```
323:    if not any(status.values()) and not out:
```

**raw green:** the same command.
```
.                                                                        [100%]
1 passed in 0.68s
```

---

## H1b — the `not any(status.values())` operand

**axis:** a session that ran no panel and no other phase holds nothing that says a reviewer ran, and is refused with `review-session-unsupported`; no record is written.

**neutralization** (`review_record_session.py`, `_status_reviewers`: the refusal made unreachable):
```python
-    if not any(status.values()) and not out:
+    if False:
```

**raw red:** `timeout 600 scripts/pinned-python -B -m pytest "plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_e1_a_changed_session_with_an_empty_surface_completed_by_hand_writes_no_record" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e1_a_changed_session_with_an_empty_surface_completed_by_hand_writes_no_record _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_e1_a_changed_session_with0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f051179ab40>

    def test_e1_a_changed_session_with_an_empty_surface_completed_by_hand_writes_no_record(tmp_path, monkeypatch):
        def catch_up(repo):  # main moves and is merged: the change since the last reviewed commit has nothing to read
            repo.moved = repo.main_commit("docs/other.md", "other\n")
            repo.merge_main()
    
        s = TS.Session(tmp_path, monkeypatch, change=catch_up, base_after=lambda repo: repo.moved)
        answer = s.next()
        assert answer["action"] == RD.P_TERMINAL and answer["payload"]["verdict"] == "converged", answer
        state = s.state()
        assert state["rounds"]["1"]["scopedFinder"] == "skipped-empty-surface", state["rounds"]["1"]
        fake = TRRS.Fake(head=s.head)
        out = RS.write_from_session(s.dir, TRRS.put_extras(tmp_path, TRRS.extras(ci="green")), s.repo.root, fake.readers())
        # nothing ran, so there is no reviewer row to list: the writer refuses, and posts nothing
>       assert out["ok"] is False and out["reason"] == RS.UNSUPPORTED, out
E       AssertionError: {'ok': False, 'reason': 'review-account-invalid', 'detail': 'reviewers'}
E       assert (False is False and 'review-account-invalid' == 'review-session-unsupported'
E         
E         - review-session-unsupported
E         + review-account-invalid)

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py:377: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_e1_a_changed_session_with_an_empty_surface_completed_by_hand_writes_no_record
1 failed in 2.05s
```

**restore:** the inverse edit — `if False:` put back to `if not any(status.values()) and not out:`.

**restore receipt** (`grep -n "if not any(status.values())" plugins/superheroes/lib/review_record_session.py`, then `git status --porcelain plugins/superheroes/lib/review_record_session.py`, which printed nothing):
```
323:    if not any(status.values()) and not out:
```

**raw green:** the same command.
```
.                                                                        [100%]
1 passed in 0.30s
```
