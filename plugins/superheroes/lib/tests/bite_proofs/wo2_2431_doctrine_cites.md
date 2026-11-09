# WO-2 (#2431) bite-proofs — the doctrine cites the session-wide refusal rule

Guarded-element set: the order declared exactly three elements (a, b, c), one neutralization and one
red each. The order declared no wider set. Element (c) was dropped in the vet 883 fix leg (see its
section below); (a) and (b) stand.

All runs: `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <node> -q`, from
the worktree root. No receipt below holds a secret, token, or private URL; the home-folder part of every absolute path was redacted to `/path/to/home/`; nothing else was redacted. The
red `body = ...` reprs are cut by pytest itself; nothing was edited out by hand.

---

## (a) the cite census — `test_doctrine_cites_the_session_rule[vetting]`

**Guarded element:** the `A vet re-runs no refused act.` paragraph in
`plugins/superheroes/skills/showrunner/reference/vetting.md`. Axis: the surface names the rule's one
home (`lib/command_refusals.py`) and `SANCTIONED_RETRIES` or `SESSION_RULE`.

**Neutralization:** with the Edit tool, deleted the parenthetical (leading space and backticks
included) from that paragraph:
```
 (`SANCTIONED_RETRIES` in `lib/command_refusals.py`)
```

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_session_refusal_rule_doctrine.py::test_doctrine_cites_the_session_rule[vetting]" -q
```

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_doctrine_cites_the_session_rule[vetting] _________________

relpath = 'skills/showrunner/reference/vetting.md'

    @pytest.mark.parametrize("relpath", list(_DOCTRINE.values()), ids=list(_DOCTRINE))
    def test_doctrine_cites_the_session_rule(relpath):
        body = _body(relpath)
        # axis: the cite census — the surface names the rule's one home — see bite-proof record wo2_2431_doctrine_cites
>       assert "lib/command_refusals.py" in body
E       AssertionError: assert 'lib/command_refusals.py' in '# Contents - [Vetting — the mechanism behind duty 4](#vetting--the-mechanism-behind-duty-4) - [Order-quality accounti...Instructions nobody executed are reconstruction with extra steps. - **attended** and **none** remain the honest floor.'

/path/to/home/.superheroes-worktrees/superheroes/issue-2431-f8f492f5d738c44a/plugins/superheroes/lib/tests/test_session_refusal_rule_doctrine.py:32: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_session_refusal_rule_doctrine.py::test_doctrine_cites_the_session_rule[vetting]
1 failed in 0.16s
```
**Restore:** by the inverse Edit, reinserted the parenthetical after `names a vet`.

**Restore receipt:** the restored text, quoted back: `only when a sanctioned retry names a vet
(`SANCTIONED_RETRIES` in `lib/command_refusals.py`), only on that entry's conditions`.

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.14s
```

---

## (b) the no-copy guard — `test_doctrine_cites_the_session_rule[check-runner]`

**Guarded element:** the last two asserts of `test_doctrine_cites_the_session_rule`, on
`plugins/superheroes/agents/check-runner.md`. Axis: a surface cites the rule and never carries a copy
of `CR.SESSION_RULE_HEAD` or `CR.SESSION_RULE_TAIL`.

**Neutralization:** with the Edit tool, appended `CR.SESSION_RULE_TAIL`'s exact text as a new final
line of `agents/check-runner.md`, directly after `Nothing else. No verdict, no reading of what the
results mean, no "ready".`:
```
A refused act that no entry covers stays a stop for the whole session: record it, and a claim it would have proved goes back UNVERIFIED. A new entry needs the owner's word, with the field sightings behind it.
```

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_session_refusal_rule_doctrine.py::test_doctrine_cites_the_session_rule[check-runner]" -q
```

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_doctrine_cites_the_session_rule[check-runner] ______________

relpath = 'agents/check-runner.md'

    @pytest.mark.parametrize("relpath", list(_DOCTRINE.values()), ids=list(_DOCTRINE))
    def test_doctrine_cites_the_session_rule(relpath):
        body = _body(relpath)
        # axis: the cite census — the surface names the rule's one home — see bite-proof record wo2_2431_doctrine_cites
        assert "lib/command_refusals.py" in body
        assert "SANCTIONED_RETRIES" in body or "SESSION_RULE" in body
        # axis: the no-copy guard — a cite, never a copy of the rule — see bite-proof record wo2_2431_doctrine_cites
        assert " ".join(CR.SESSION_RULE_HEAD.split()) not in body
>       assert " ".join(CR.SESSION_RULE_TAIL.split()) not in body
E       assert 'A refused a...s behind it.' not in '--- name: c...s behind it.'
E         
E         'A refused act that...ightings behind it.' is contained here:
E           o "ready". A refused act that no entry covers stays a stop for the whole session: record it, and a claim it would have proved goes back UNVERIFIED. A new entry needs the owner's word, with the field sightings behind it.

/path/to/home/.superheroes-worktrees/superheroes/issue-2431-f8f492f5d738c44a/plugins/superheroes/lib/tests/test_session_refusal_rule_doctrine.py:36: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_session_refusal_rule_doctrine.py::test_doctrine_cites_the_session_rule[check-runner]
1 failed in 0.16s
```

**Restore:** by the inverse Edit, removed exactly the appended line.

**Restore receipt:** the file again ends with the line `Nothing else. No verdict, no reading of what
the results mean, no "ready".`; the appended sentence is gone.

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.09s
```

---

## (c) the same-say guard — `test_workhorse_and_vet_doctrine_say_the_same` (dropped)

The test was deleted in the vet 883 fix leg because it pinned a doctrine sentence fragment, against
the pin rule in `rubric/review-discipline.md`: a paraphrase with the same meaning turned it red, and
a rule rewritten to mean the opposite kept it green. WO-2 (c) is dropped and no test replaces it; the
doctrine's agreement is checked at review and vet by reading.
