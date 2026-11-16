# i2496_wo_b_record_commit — the review record certifies the commit its session reviewed

Declared guarded-element set (from work order wo-b-2496): **E-source** the three-way choice of the final commit's source
(`build_record`, `_status`); **E-session-row** a reviewer row only the session reports counts only when GitHub confirmed
the final commit as the PR head (`_reviewer`); **E-paths** the lane basis's path list is bound to the certified commit
(`_lane_basis`, `commit_paths`); **E-only-line** the only-open-line pin (`_status`).

Each element was neutralized by a targeted edit in `plugins/superheroes/lib/review_record.py`, the element's detector
nodes run alone (`-k`), and the edit undone by its inverse edit. **E-paths owes three neutralizations** (its three
independently neutralizable legs: P1 the head-equality gate, P2 the git read bound to the certified commit, P3 the
whole-row-or-None parse), so six reds were taken in all. Detectors:
`plugins/superheroes/lib/tests/test_review_record_certifies_commit_2496.py`, unedited throughout.

**Green runs are consolidated.** The work order's budget of ten test invocations cannot hold a green after each of six
reds, so every restore was shown by quoting the restored lines (below) and one green run followed the last restore. It
ran all seven budgeted files, the whole detector file included (every detector node of every element), and passed:
```
700 passed in 51.25s
```
Redaction: the pytest tmp paths are as printed by pytest (local temp paths); the `UV_NATIVE_TLS` deprecation warning
line that precedes each run is dropped from the quotes. Nothing else was secret.

## E-source — the three-way source choice

**Guarded element:** `build_record`, the `fc = {"sha": a["finalCommit"], "source": ...}` expression; and `_status`'s
`if fc["source"] == SESSION:` could-not-be-read line. Axis: the source is `GitHub PR` when the PR head read equals the
certified commit, `HEAD_MOVED_SOURCE` (with `headAtWrite` beside it) when it differs, and `SESSION` when it could not be
read; a moved head never reads as unread.

**Neutralization:** the source expression `SESSION if head_read is None else FINAL_COMMIT_CONFIRMED if head_read ==
a["finalCommit"] else HEAD_MOVED_SOURCE` → `FINAL_COMMIT_CONFIRMED` (always confirmed).

**Raw red** (`-k "earlier_commit_than_the_pr_head or unreadable_pr_keeps or github_source or adds_no_could_not"`):
```
F.F.                                                                     [100%]
_ test_a_session_on_an_earlier_commit_than_the_pr_head_reads_reviewed_on_its_own_commit _
>       assert rec["finalCommit"] == {"sha": EARLIER, "source": rr.HEAD_MOVED_SOURCE}
E       AssertionError: assert {'sha': 'aaaa...: 'GitHub PR'} == {'sha': 'aaaa...oved past it'}
E         Differing items:
E         {'source': 'GitHub PR'} != {'source': 'reported by the session; the PR head had moved past it'}
_ test_an_unreadable_pr_keeps_the_session_source_and_the_could_not_be_read_line _
>       assert rec["finalCommit"] == {"sha": HEAD, "source": rr.SESSION}
E       AssertionError: assert {'sha': 'bbbb...: 'GitHub PR'} == {'sha': 'bbbb... the session'}
E         Differing items:
E         {'source': 'GitHub PR'} != {'source': 'reported by the session'}
FAILED ...::test_a_session_on_an_earlier_commit_than_the_pr_head_reads_reviewed_on_its_own_commit
FAILED ...::test_an_unreadable_pr_keeps_the_session_source_and_the_could_not_be_read_line
2 failed, 2 passed, 17 deselected in 2.84s
```
The red is on the claimed axis: the source is read wrong in both the moved-head and the unread-PR case, while the
confirmed-head node and the no-line node (which a constant `GitHub PR` still satisfies) pass.

**Restore:** inverse edit. **Restore receipt** (restored lines quoted from `review_record.py:2104-2106`):
```
    fc = {"sha": a["finalCommit"],
          "source": SESSION if head_read is None
          else FINAL_COMMIT_CONFIRMED if head_read == a["finalCommit"] else HEAD_MOVED_SOURCE}
```
**Raw green:** the consolidated run above.

## E-session-row — BR1's demotion of a session-only row

**Guarded element:** `_reviewer`, the `if head_confirmed:` branch of the `reported-by-session` arm. Axis: a row only the
session reports counts only when GitHub confirmed the final commit as the PR head; otherwise it reads `not-run` with the
BR1 note and the usual disagreement entry.

**Neutralization:** `        if head_confirmed:` → `        if True:` (every such row counts).

**Raw red** (`-k "br1_note or never_covers_a_commit_github"`):
```
FFF                                                                      [100%]
_ test_a_session_only_row_on_a_moved_head_reads_not_run_with_the_br1_note[unnamed row] _
>       assert row["ran"] == "not-run" and row["runNote"] == BR1 and row["coversFinalCommit"] is False
E       AssertionError: assert ('reported-by-session' == 'not-run'
_ test_a_session_only_row_on_a_moved_head_reads_not_run_with_the_br1_note[row naming the certified commit] _
E       AssertionError: assert ('reported-by-session' == 'not-run'
_____ test_a_session_only_row_never_covers_a_commit_github_did_not_confirm _____
>       assert row["ran"] == "not-run" and row["runNote"] == BR1
E       AssertionError: assert ('reported-by-session' == 'not-run'
3 failed, 18 deselected in 0.85s
```
The red is on the claimed axis: the unconfirmed row reads `reported-by-session` on a moved head (both row shapes) and on an
unreadable head.

**Restore:** inverse edit. **Restore receipt** (`review_record.py:1496`): `        if head_confirmed:`
**Raw green:** the consolidated run above.

## E-paths — the path list is bound to the certified commit

### P1 — the head-equality gate in `_lane_basis`

**Guarded element:** `_lane_basis`, `if stable and isinstance(paths, list):`. Axis: the PR's changed files are the lane
basis only when the head read before and after them equals the certified commit.

**Neutralization:** `        if stable and isinstance(paths, list):` → `        if isinstance(paths, list):`.

**Raw red** (`-k "moves_during_the_files_read"`):
```
F                                                                        [100%]
_ test_a_head_that_moves_during_the_files_read_reads_the_certified_commits_paths_from_git _
        assert len(reads) == 2 and rec["finalCommit"] == {"sha": x, "source": "GitHub PR"}
>       assert rec["laneBasis"]["source"] == "lane rule over the certified commit's changed files (git)"
E       AssertionError: assert 'lane rule ov...changed files' == 'lane rule ov...d files (git)'
E         - lane rule over the certified commit's changed files (git)
E         + lane rule over the PR's changed files
1 failed, 20 deselected in 1.50s
```
The red is on the claimed axis: the head's file list became the basis for a head that is not the certified commit.

**Restore:** inverse edit. **Restore receipt** (`review_record.py:1343`): `        if stable and isinstance(paths, list):`

### P2 — the git read is bound to the certified commit

**Guarded element:** `commit_paths`, the `git diff ... base...sha` range. Axis: the list is the certified commit's own
change against the pinned base, never a later commit's.

**Neutralization:** `f"{base}...{sha}"` → `f"{base}...HEAD"` (the test repo's checked-out head is the later commit).

**Raw red** (`-k "reads_the_certified_commits_paths_from_git_not or with_each_renames_source"`):
```
FF                                                                       [100%]
_ test_a_moved_head_reads_the_certified_commits_paths_from_git_not_the_heads_files _
        assert basis["source"] == "lane rule over the certified commit's changed files (git)"
>       assert basis["floor"] is None and basis["touched"] == [] and "headMoved" not in basis
E       AssertionError: assert ('full' is None)
_ test_the_commit_paths_reader_gives_the_certified_commits_paths_with_each_renames_source _
>       assert sorted(rr.commit_paths(str(repo), base, x)) == ["docs/guide.md", "src/billing/charge.py",
E       AssertionError: assert ['docs/guide....ents/late.py'] == ['docs/guide....ts/charge.py']
E         Left contains one more item: 'src/payments/late.py'
2 failed, 19 deselected in 1.23s
```
The red is on the claimed axis: a risk-area file changed only after the certified commit raised the floor to full.

**Restore:** inverse edit. **Restore receipt** (`review_record.py:211`):
`    out = _run(["git", "-C", repo_root, "diff", "--name-status", "-M", "--no-color", f"{base}...{sha}"])`

### P3 — the reader gives the whole list or None

**Guarded element:** `commit_paths`, the row check `if len(parts) != want or not all(p and not p.startswith('"') ...)`.
Axis: a row the reader cannot read whole (a git-quoted path) makes the list None, never a shorter or misspelled list.

**Neutralization:** `not all(p and not p.startswith('"') for p in parts[1:])` → `not all(p for p in parts[1:])`.

**Raw red** (`-k "gives_none_never_a_partial_list"`):
```
F                                                                        [100%]
_________ test_the_commit_paths_reader_gives_none_never_a_partial_list _________
        assert rr.commit_paths(str(repo), base, x) == ["docs/guide.md"]
>       assert rr.commit_paths(str(repo), base, odd) is None
E       assert ['docs/guide.md', '"odd\\tname.py"'] is None
1 failed, 20 deselected in 0.84s
```
The red is on the claimed axis: the quoted path went into the list as if it were a path.

**Restore:** inverse edit. **Restore receipt** (`review_record.py:222`):
`        if len(parts) != want or not all(p and not p.startswith('"') for p in parts[1:]):`

**Not neutralized (listed, not claimed):** the `isinstance(got, list)` branch of `_lane_basis` (a git failure reads the
unavailable basis) and the withheld reader taking the basis's own list are pinned by
`test_git_failure_gives_the_unavailable_basis_never_a_partial_list` and the `recorder(seen)` assertions of the three lane
basis tests, but no neutralization of either was run, so their bite is unproven. The reader's input guards (no repository
root, a base or commit that is not a full sha) are likewise pinned by the last test and not neutralized.

**Raw green (P1, P2, P3):** the consolidated run above.

## E-only-line — the only open line of a record whose reviewers did not run on the certified commit

**Guarded element:** `_status`, `elif not any(v["coversFinalCommit"] for v in ran):` (the "no planned reviewer's run covers
the final commit" line). Axis: a record none of whose planned reviewers ran on the commit it certifies reads
`not-reviewed` with exactly that one line in `whatIsMissing`.

**Neutralization:** `    elif not any(v["coversFinalCommit"] for v in ran):` → `    elif False and not any(v["coversFinalCommit"] for v in ran):`.

**Raw red** (`-k "the_one_open_line"`):
```
FF                                                                       [100%]
_ test_a_record_none_of_whose_planned_reviewers_ran_on_the_certified_commit_has_the_one_open_line[engine row covers the PR head, session ended earlier] _
        assert row["ran"] == "engine-record" and row["coversFinalCommit"] is False
>       assert rec["status"] == "not-reviewed" and rec["parked"] is False
E       AssertionError: assert ('reviewed' == 'not-reviewed'
_ test_a_record_none_of_whose_planned_reviewers_ran_on_the_certified_commit_has_the_one_open_line[engine row covers an earlier commit, session ended on the PR head] _
>       assert rec["status"] == "not-reviewed" and rec["parked"] is False
E       AssertionError: assert ('reviewed' == 'not-reviewed'
2 failed, 19 deselected in 2.57s
```
The red is on the claimed axis: the record reads `reviewed` although no planned reviewer ran on the certified commit.

**Restore:** inverse edit. **Restore receipt** (`review_record.py:1812`): `    elif not any(v["coversFinalCommit"] for v in ran):`
**Raw green:** the consolidated run above.

---

## Added at layer 2's review, round 1: E-abbrev (2026-11-16, typed and run by the build session)

**guard:** `build_record`, `a = dict(a, finalCommit=_full_final_commit(...))` (commit 9d2f0b42): an abbreviated session final commit becomes its one full sha, the PR head it abbreviates, else git's reading.

**neutralization:** `finalCommit=a["finalCommit"] or _full_final_commit(...)` (the abbreviation kept as given).

**raw red:** `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest plugins/superheroes/lib/tests/test_review_record_certifies_commit_2496.py -k abbreviated -q -p no:cacheprovider`, in a detached probe worktree at 9d2f0b42
```
2 failed, 23 deselected in 1.48s
```

**restore:** the inverse Edit; `git status --short` printed nothing. **green:** the same file, `25 passed in 2.96s`.

---

## Added at layer 2's review, rework 1: E-review-base (2026-11-16, typed and run by the build session)

Three elements, three neutralizations, three reds. Each red ran the one detector alone, with
`scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest <file> -k <test> -q -p no:cacheprovider`.

### E-review-base-read — `review_record._lane_basis`, the base given to `commit_paths`

**guarded element:** `got = rd["commit_paths"](repo_root, a.get("reviewBase") or a.get("carryBase"), final_sha)`. **Axis:** a
moved head reads the certified commit's paths from git against the session's own pinned review base on any session, not only
a carry session.

**neutralization:** `a.get("reviewBase") or ` removed, so only `carryBase` is read.

**raw red** (`test_review_record_certifies_commit_2496.py -k review_base_and_no_carry_base`):
```
F                                                                        [100%]
_ test_a_moved_head_with_a_review_base_and_no_carry_base_reads_the_certified_commits_paths_from_git _
test_review_record_certifies_commit_2496.py:210: in test_a_moved_head_with_a_review_base_and_no_carry_base_reads_the_certified_commits_paths_from_git
    assert basis["source"] == "lane rule over the certified commit's changed files (git)"
E   AssertionError: assert 'unavailable' == 'lane rule ov...d files (git)'
1 failed, 31 deselected in 4.67s
```
The red is on the claimed axis: with no `carryBase` and the `reviewBase` unread, the moved-head basis reads unavailable.

**restore:** the inverse Edit. **restore receipt** (`review_record.py:1355`):
`    got = rd["commit_paths"](repo_root, a.get("reviewBase") or a.get("carryBase"), final_sha)`
**raw green** (same command): `1 passed, 31 deselected in 4.49s`.

### E-review-base-validate — `review_record._validate`, the `reviewBase` check

**guarded element:** `chk(a.get("reviewBase") is None or _full_sha(a["reviewBase"]), "reviewBase")`. **Axis:** the optional
review base is None or a full sha; anything else is refused `review-account-invalid` naming `reviewBase`, never handed to git.

**neutralization:** the check became `chk(True, "reviewBase")`.

**raw red** (`test_review_record_certifies_commit_2496.py -k review_base_that_is_not`, `--tb=line`):
```
FFFFFF                                                                   [100%]
E   Failed: DID NOT RAISE Refusal (six times, one per case: symbolic, short, not hex, empty, not a string, a list)
6 failed, 26 deselected in 3.87s
```
The red is on the claimed axis: each malformed base is accepted where the test requires the refusal.

**restore:** the inverse Edit. **restore receipt** (`review_record.py:961`):
`    chk(a.get("reviewBase") is None or _full_sha(a["reviewBase"]), "reviewBase")`
**raw green:** the five-file run after both restores, `651 passed in 39.10s`.

### E-review-base-set — `review_record_session.account_from_session`, the `reviewBase` key

**guarded element:** `"reviewBase": cfg["baseRef"] if review_record._full_sha(cfg.get("baseRef")) else None`. **Axis:** every
account carries the session's pinned base as `reviewBase` when the config's `baseRef` is a full sha, else None.

**neutralization:** the value became `None`.

**raw red** (`test_review_record_session.py -k review_base`, `--tb=line`):
```
F...                                                                     [100%]
E   AssertionError: assert None == 'cccccccccccccccccccccccccccccccccccccccc'
1 failed, 3 passed, 98 deselected in 0.35s
```
The red is on the claimed axis: the full-sha case loses its base. The three non-sha cases (symbolic, short, absent) stay
green by design, since None is their right answer; they pin the fail-closed edge against a guessed base, and a neutralization
that guessed one (for example `cfg.get("baseRef")` unchecked) was not run, so that half is pinned but not proven to bite.

**restore:** the inverse Edit. **restore receipt** (`review_record_session.py:1703`):
`            "reviewBase": cfg["baseRef"] if review_record._full_sha(cfg.get("baseRef")) else None,`
**raw green:** the five-file run after both restores, `651 passed in 39.10s`.
