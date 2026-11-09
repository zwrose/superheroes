# WO-1 (#2431) bite-proofs — session-wide refusal rule and its sanctioned-retry list

Guarded-element set (declared by the order, exactly six):

- (a) `session_rule` renders each entry's conditions.
- (b) `ORDER_TEXT` is composed from the session rule.
- (c) the uncovered-act stop (`SESSION_RULE_TAIL` closes every rendering).
- (d) the entry shape of `SANCTIONED_RETRIES`.
- (e) the implementer template's citation of the session rule and its list.
- (f) one home: no entry's rendered text or disclosure is copied outside `lib/command_refusals.py`.

All runs: `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <node> -q`,
from the worktree root, one exact test node each. Every neutralization was a single targeted Edit and
every restore the exact inverse Edit; no `git checkout`, `git restore`, `git reset` or `git stash`.
No receipt below holds a secret, token, or private URL; nothing was redacted. Where a red shows a
truncated `assert` line (`...`), pytest itself cut it; nothing was edited out by hand.

---

## (a) `test_session_rule_renders_every_entry`

**Guarded element:** `session_rule` in `plugins/superheroes/lib/command_refusals.py`, the
`", ".join(e["conditions"])` term of the rendered item. Axis: every condition of every entry reaches
the session rule (and so the order text).

**Neutralization:** `", ".join(e["conditions"])` changed to `e["conditions"][0]`.

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_command_refusals.py::test_session_rule_renders_every_entry -q
```

**Raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_session_rule_renders_every_entry _____________________

    def test_session_rule_renders_every_entry():
        for entry in CR.SANCTIONED_RETRIES:
            fields = [entry["act"]] + list(entry["who"]) + list(entry["conditions"]) + [entry["disclosure"]]
            for field in fields:
                # axis: every field of every entry is rendered into the session rule and the order text — see bite-proof record wo1_2431_session_rule
>               assert field in CR.SESSION_RULE
E               assert 'with the mutation reverted' in "A refusal binds the whole build session, not only the seat that met it. No seat, the orchestrator and a vet included,...aim it would have proved goes back UNVERIFIED. A new entry needs the owner's word, with the field sightings behind it."
E                +  where "A refusal binds the whole build session, not only the seat that met it. No seat, the orchestrator and a vet included,...aim it would have proved goes back UNVERIFIED. A new entry needs the owner's word, with the field sightings behind it." = CR.SESSION_RULE

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2431-f8f492f5d738c44a/plugins/superheroes/lib/tests/test_command_refusals.py:181: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_session_rule_renders_every_entry
1 failed in 0.46s
```
The red is on the claimed axis: the entry's second condition, `with the mutation reverted`, is absent
from `SESSION_RULE`.

**Restore:** inverse Edit, `e["conditions"][0]` back to `", ".join(e["conditions"])`.

**Restore receipt:** the restored line, quoted back:
`n, e["act"], " or ".join(e["who"]), ", ".join(e["conditions"]), e["disclosure"])`

**Raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.49s
```

---

## (b) `test_order_text_composition`

**Guarded element:** `compose_order_text` in `plugins/superheroes/lib/command_refusals.py`, the
`session_rule(entries)` term of its list. Axis: `ORDER_TEXT` is the stop rule, then the session rule,
then the refusal meaning and entry shape.

**Neutralization:** `" ".join([STOP_RULE, session_rule(entries), REFUSAL_MEANING, ENTRY_SHAPE])`
changed to `" ".join([STOP_RULE, REFUSAL_MEANING, ENTRY_SHAPE])`.

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_command_refusals.py::test_order_text_composition -q
```

**Raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________________ test_order_text_composition __________________________

    def test_order_text_composition():
        # axis: the composition of ORDER_TEXT — see bite-proof record wo1_2011_stop_rule
        assert CR.ORDER_TEXT.startswith(CR.STOP_RULE)
        assert CR.REFUSAL_MEANING in CR.ORDER_TEXT
        assert CR.ENTRY_SHAPE in CR.ORDER_TEXT
        for member in CR.REFUSED_BY + CR.ENTRY_REQUIRED + CR.ENTRY_OPTIONAL:
            assert member in CR.ENTRY_SHAPE
        # axis: ORDER_TEXT is composed from the session rule, in order — see bite-proof record wo1_2431_session_rule
>       assert CR.ORDER_TEXT == " ".join([CR.STOP_RULE, CR.SESSION_RULE, CR.REFUSAL_MEANING, CR.ENTRY_SHAPE])
E       AssertionError: assert 'A refused or...you met none.' == 'A refused or...you met none.'
E         
E         Skipping 1042 identical leading characters in diff, use -v to show
E         - m. A refusal binds the whole build session, not only the seat that met it. No seat, the orchestrator and a vet included, takes a refused act in any form, and handing a refused act to another seat (an implementer, a check-runner, a pilot) is taking it in another form. The stop rule's two exceptions belong to the seat that met the refusal, taken once by that seat; no other seat inherits them. The only other exceptions are the sanctioned retries listed in SANCTIONED_RETRIES in lib/command_refusals.py, each...
E         
E         ...Full output truncated, use '-vv' to show

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2431-f8f492f5d738c44a/plugins/superheroes/lib/tests/test_command_refusals.py:132: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_order_text_composition
1 failed in 0.50s
```
The red is on the claimed axis: the composed `ORDER_TEXT` lacks the session rule.

**Restore:** inverse Edit, re-inserting `session_rule(entries), ` after `STOP_RULE, `.

**Restore receipt:** the restored line, quoted back:
`    return " ".join([STOP_RULE, session_rule(entries), REFUSAL_MEANING, ENTRY_SHAPE])`

**Raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.51s
```

---

## (c) `test_an_uncovered_refusal_stays_a_stop`

**Guarded element:** `session_rule` in `plugins/superheroes/lib/command_refusals.py`, the
`[SESSION_RULE_TAIL]` term of its return. Axis: a refused act no entry covers stays a stop, for the
shipped list and for the empty list alike.

**Neutralization:** `(items or ["none."]) + [SESSION_RULE_TAIL])` changed to
`(items or ["none."]) + [])`.

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_command_refusals.py::test_an_uncovered_refusal_stays_a_stop -q
```

**Raw red** (exit 1; both parametrized cases fail):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_______________ test_an_uncovered_refusal_stays_a_stop[entries0] _______________

entries = ({'act': 'a bite-proof red or green run', 'who': ("the build's orchestrator", 'a vet'), 'conditions': ('in a throwaway...ver committed or pushed'), 'disclosure': 'the PR body (for a vet, the vet receipt) names the refusal and the re-run'},)

    @pytest.mark.parametrize("entries", [CR.SANCTIONED_RETRIES, ()])
    def test_an_uncovered_refusal_stays_a_stop(entries):
        rule = CR.session_rule(entries)
        # axis: the rule keeps its binding head and its uncovered-act stop tail, for any list — see bite-proof record wo1_2431_session_rule
        assert CR.SESSION_RULE_HEAD in rule
>       assert CR.SESSION_RULE_TAIL in rule
E       assert "A refused act that no entry covers stays a stop for the whole session: record it, and a claim it would have proved goes back UNVERIFIED. A new entry needs the owner's word, with the field sightings behind it." in 'A refusal binds the whole build session, not only the seat that met it. No seat, the orchestrator and a vet included,...tation reverted, never committed or pushed; the PR body (for a vet, the vet receipt) names the refusal and the re-run.'
E        +  where "A refused act that no entry covers stays a stop for the whole session: record it, and a claim it would have proved goes back UNVERIFIED. A new entry needs the owner's word, with the field sightings behind it." = CR.SESSION_RULE_TAIL

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2431-f8f492f5d738c44a/plugins/superheroes/lib/tests/test_command_refusals.py:212: AssertionError
_______________ test_an_uncovered_refusal_stays_a_stop[entries1] _______________

entries = ()

    @pytest.mark.parametrize("entries", [CR.SANCTIONED_RETRIES, ()])
    def test_an_uncovered_refusal_stays_a_stop(entries):
        rule = CR.session_rule(entries)
        # axis: the rule keeps its binding head and its uncovered-act stop tail, for any list — see bite-proof record wo1_2431_session_rule
        assert CR.SESSION_RULE_HEAD in rule
>       assert CR.SESSION_RULE_TAIL in rule
E       assert "A refused act that no entry covers stays a stop for the whole session: record it, and a claim it would have proved goes back UNVERIFIED. A new entry needs the owner's word, with the field sightings behind it." in 'A refusal binds the whole build session, not only the seat that met it. No seat, the orchestrator and a vet included,...ommand_refusals.py, each taken only by the seats it names, only on its conditions, and only with its disclosure: none.'
E        +  where "A refused act that no entry covers stays a stop for the whole session: record it, and a claim it would have proved goes back UNVERIFIED. A new entry needs the owner's word, with the field sightings behind it." = CR.SESSION_RULE_TAIL

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2431-f8f492f5d738c44a/plugins/superheroes/lib/tests/test_command_refusals.py:212: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_an_uncovered_refusal_stays_a_stop[entries0]
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_an_uncovered_refusal_stays_a_stop[entries1]
2 failed in 0.45s
```
The red is on the claimed axis: the uncovered-act stop sentence (`SESSION_RULE_TAIL`) is absent from the
rendering, for the shipped list and the empty one.

**Restore:** inverse Edit, `+ [])` back to `+ [SESSION_RULE_TAIL])`.

**Restore receipt:** the restored line, quoted back:
`    return " ".join([SESSION_RULE_HEAD] + (items or ["none."]) + [SESSION_RULE_TAIL])`

**Raw green** (exit 0):
```
..                                                                       [100%]
2 passed in 0.44s
```

---

## (d) `test_sanctioned_retries_entry_shape`

**Guarded element:** the bite-proof entry's `"conditions"` value in `SANCTIONED_RETRIES`
(`plugins/superheroes/lib/command_refusals.py`). Axis: a malformed entry is caught by the shape test
itself, not by a crash in some other test.

**Neutralization:** the three-line tuple
`"conditions": ("in a throwaway copy of the tree", "with the mutation reverted", "never committed or pushed"),`
(written across five lines in the file) replaced by the single string
`"conditions": "in a throwaway copy of the tree",`.

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_command_refusals.py::test_sanctioned_retries_entry_shape -q
```

**Raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________________ test_sanctioned_retries_entry_shape ______________________

    def test_sanctioned_retries_entry_shape():
        # axis: every sanctioned-retry entry has the four-field shape the renderer reads — see bite-proof record wo1_2431_session_rule
        assert isinstance(CR.SANCTIONED_RETRIES, tuple) and CR.SANCTIONED_RETRIES
        for entry in CR.SANCTIONED_RETRIES:
            # axis: no missing or extra key in an entry — see bite-proof record wo1_2431_session_rule
            assert set(entry) == {"act", "who", "conditions", "disclosure"}
            # axis: act and disclosure are non-blank strings — see bite-proof record wo1_2431_session_rule
            for key in ("act", "disclosure"):
                assert isinstance(entry[key], str) and entry[key].strip()
            # axis: who and conditions are non-empty tuples of non-blank strings — see bite-proof record wo1_2431_session_rule
            for key in ("who", "conditions"):
>               assert isinstance(entry[key], tuple) and entry[key]
E               AssertionError: assert (False)
E                +  where False = isinstance('in a throwaway copy of the tree', tuple)

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2431-f8f492f5d738c44a/plugins/superheroes/lib/tests/test_command_refusals.py:152: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_sanctioned_retries_entry_shape
1 failed in 0.44s
```
The red is on the claimed axis: the shape test itself rejects the string where a tuple belongs.

**Restore:** inverse Edit, the single-string line back to the five-line tuple.

**Restore receipt:** the restored text, quoted back:
```
        "conditions": (
            "in a throwaway copy of the tree",
            "with the mutation reverted",
            "never committed or pushed",
        ),
```

**Raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.45s
```

---

## (e) `test_census_implementer_md`

**Guarded element:** the inserted citation sentence in `plugins/superheroes/agents/implementer.md`,
in the refused-commands paragraph between "An empty list means you met none." and "This dominates
every rung below:". Axis: the implementer template cites `SESSION_RULE` and `SANCTIONED_RETRIES` and
their home, inside the refused-commands block.

**Neutralization:** the three-line citation sentence ("A refusal also binds the whole build session,
not only you: ... take no retry the list does not give your seat.") deleted.

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_command_refusals.py::test_census_implementer_md -q
```

**Raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________________ test_census_implementer_md __________________________

    def test_census_implementer_md():
        with open(_IMPLEMENTER_MD, encoding="utf-8") as fh:
            body = fh.read()
        flat = " ".join(body.split())
        # axis: the stop rule reaches the implementer template — see bite-proof record wo1_2011_stop_rule
        assert " ".join((CR.STOP_RULE + " " + CR.REFUSAL_MEANING + " " + CR.ENTRY_SHAPE).split()) in flat
        # axis: the template cites the session rule and its list by name and home — see bite-proof record wo1_2431_session_rule
        cite = "`SESSION_RULE` and `SANCTIONED_RETRIES` in `lib/command_refusals.py`"
>       assert cite in flat
E       assert '`SESSION_RULE` and `SANCTIONED_RETRIES` in `lib/command_refusals.py`' in '--- name: implementer description: Internal build subagent — implements one scoped work order dispatched by the Workh...d out of scope. - Return per the **Short structured return** rule above. Nothing beyond that — no verdict, no "ready."'

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2431-f8f492f5d738c44a/plugins/superheroes/lib/tests/test_command_refusals.py:306: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_census_implementer_md
1 failed in 0.45s
```
The red is on the claimed axis: the citation is absent, while the stop-rule leg above it still passed.

**Restore:** inverse Edit, the three lines reinserted after "An empty list means you met none." and
before "This dominates every rung below:".

**Restore receipt:** the restored text, quoted back:
```
A refusal also binds the whole build session, not only you: the session rule and its list of
sanctioned retries (`SESSION_RULE` and `SANCTIONED_RETRIES` in `lib/command_refusals.py`) ride in
every order you receive; read them there, and take no retry the list does not give your seat.
```

**Raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.48s
```

---

## (f) `test_sanctioned_retries_have_one_home`

**Guarded element:** the one-home census walk over `_PLUGIN_ROOT` in the test itself. Axis: no
entry's rendered text or disclosure is hand-copied into a shipped file outside
`lib/command_refusals.py`.

**Neutralization:** appended to `plugins/superheroes/agents/implementer.md`, as a new last line after
`- Return per the **Short structured return** rule above. Nothing beyond that — no verdict, no "ready."`,
the bite-proof entry's disclosure text:
`the PR body (for a vet, the vet receipt) names the refusal and the re-run`

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_command_refusals.py::test_sanctioned_retries_have_one_home -q
```

**Raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_sanctioned_retries_have_one_home _____________________

    def test_sanctioned_retries_have_one_home():
        # A hand copy of an entry's rendered item or disclosure anywhere in the shipped plugin outside
        # its home is a second copy; prose consumers cite the home instead.
        markers = []
        for entry in CR.SANCTIONED_RETRIES:
            markers.append("%s may re-run it, only %s" % (" or ".join(entry["who"]), ", ".join(entry["conditions"])))
            markers.append(entry["disclosure"])
        copies = []
        for root, dirs, files in os.walk(_PLUGIN_ROOT):
            dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__", ".git")]
            for name in files:
                if not name.endswith((".py", ".md", ".json", ".txt")):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding="utf-8", errors="replace") as fh:
                    flat = " ".join(fh.read().split())
                if any(" ".join(marker.split()) in flat for marker in markers):
                    copies.append(os.path.relpath(path, _PLUGIN_ROOT))
        # axis: no entry's rendered text or disclosure is hand-copied outside lib/command_refusals.py — see bite-proof record wo1_2431_session_rule
>       assert [c for c in copies if c != os.path.join("lib", "command_refusals.py")] == []
E       AssertionError: assert ['agents/implementer.md'] == []
E         
E         Left contains one more item: 'agents/implementer.md'
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2431-f8f492f5d738c44a/plugins/superheroes/lib/tests/test_command_refusals.py:456: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_sanctioned_retries_have_one_home
1 failed in 0.51s
```
The red is on the claimed axis: the copy is found in `agents/implementer.md` and in no other file.

**Restore:** inverse Edit, the appended line removed.

**Restore receipt:** the file again ends with
`- Return per the **Short structured return** rule above. Nothing beyond that — no verdict, no "ready."`
(see the post-restore `git diff --stat` in the dispatch report).

**Raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.55s
```
