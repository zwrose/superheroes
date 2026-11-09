# WO-2 (#2431) bite-proofs — the doctrine cites the session-wide refusal rule

Guarded-element set: the order declared exactly three elements (a, b, c), one neutralization and one
red each. The order declared no wider set.

All runs: `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <node> -q`, from
the worktree root. No receipt below holds a secret, token, or private URL; nothing was redacted. The
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

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2431-f8f492f5d738c44a/plugins/superheroes/lib/tests/test_session_refusal_rule_doctrine.py:32: AssertionError
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

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2431-f8f492f5d738c44a/plugins/superheroes/lib/tests/test_session_refusal_rule_doctrine.py:36: AssertionError
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

## (c) the same-say guard — `test_workhorse_and_vet_doctrine_say_the_same`

**Guarded element:** the `owner's word with its field sightings` assert of
`test_workhorse_and_vet_doctrine_say_the_same`, on the vetting.md paragraph. Axis: workhorse duty 8
and the vet doctrine both state the entry rule beside `SANCTIONED_RETRIES`.

**Neutralization:** with the Edit tool, deleted `A new entry needs the owner's word with its field
sightings.` (with its leading space) from the `A vet re-runs no refused act.` paragraph.

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_session_refusal_rule_doctrine.py::test_workhorse_and_vet_doctrine_say_the_same -q
```

**Raw red:**
```
.F                                                                       [100%]
=================================== FAILURES ===================================
____________ test_workhorse_and_vet_doctrine_say_the_same[vetting] _____________

relpath = 'skills/showrunner/reference/vetting.md'

    @pytest.mark.parametrize(
        "relpath",
        ["skills/workhorse/SKILL.md", "skills/showrunner/reference/vetting.md"],
        ids=["workhorse-skill", "vetting"],
    )
    def test_workhorse_and_vet_doctrine_say_the_same(relpath):
        body = _body(relpath)
        # axis: same-say guard — workhorse duty 8 and the vet doctrine state the same list and entry rule
        # — see bite-proof record wo2_2431_doctrine_cites
        assert "SANCTIONED_RETRIES" in body
>       assert "owner's word with its field sightings" in body
E       assert "owner's word with its field sightings" in '# Contents - [Vetting — the mechanism behind duty 4](#vetting--the-mechanism-behind-duty-4) - [Order-quality accounti...Instructions nobody executed are reconstruction with extra steps. - **attended** and **none** remain the honest floor.'

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2431-f8f492f5d738c44a/plugins/superheroes/lib/tests/test_session_refusal_rule_doctrine.py:49: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_session_refusal_rule_doctrine.py::test_workhorse_and_vet_doctrine_say_the_same[vetting]
1 failed, 1 passed in 0.10s
```

**Restore:** by the inverse Edit, reinserted the sentence after `under its degradations.`

**Restore receipt:** the restored text, quoted back: `...recorded in the receipt as unverified, under
its degradations. A new entry needs the owner's word with its field sightings.`

**Raw green:**
```
..                                                                       [100%]
2 passed in 0.10s
```
