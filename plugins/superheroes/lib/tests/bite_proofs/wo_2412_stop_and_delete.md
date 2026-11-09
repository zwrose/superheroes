# WO-1 (#2412) bite-proofs — the `STOP_AND_DELETE_RULE` shared rule

Declared guarded-element set (from the order): (a) T1 — the dispatch-write staged prompt carries the rule text
exactly once and `WRITE_DISPATCH_PROCESS_RULE` is that constant (`test_census_stop_and_delete_rule_write_prompt`);
(b) T2 — the native implementer preamble carries it exactly once, before the order
(`test_census_stop_and_delete_rule_native_preamble`); (c) T3 — prose consumers cite it by name and never carry
its text (`test_census_stop_and_delete_rule_prose_cites`, representative `[implementer]`); (d) T4 — the text has
one home plus the parser-verified ruling line (`test_stop_and_delete_rule_has_one_home`, with T3 `[orders]`);
(e) T5 — every carrier of the delete rule also carries or cites the stop-and-delete rule
(`test_every_delete_rule_carrier_carries_the_stop_and_delete_rule`); (f) T7 — the `own-processes-and-paths`
ruling keeps its "only by its PID" invariant (`test_doctrine_own_processes_and_paths_ruling_invariant_missing`);
(g) T8 — the ruling reaches every composed builder prompt
(`test_every_launch_path_carries_the_own_processes_and_paths_ruling`).

Record shape: `plugins/superheroes/rubric/bite-proof.md` § The record.

Commands used the pinned interpreter, from `/home/user/wt-2412`:
`scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/wo2412-pyc -m pytest <node> -q -p no:cacheprovider`.
The `UV_NATIVE_TLS` deprecation warning line that opens each run is omitted below; nothing else is trimmed.
Every neutralization and restore was a targeted Edit-tool edit; no `git checkout`, `restore`, `reset` or `stash`.
No secrets or tokens appear in these captures; nothing is redacted. Where an assertion message was long, pytest
itself abbreviated it with `...`; those abbreviations are pytest's, not ours.

Not separately neutralized: T6 (`test_own_processes_and_paths_ruling_text_is_the_shared_rule`) and the other three
T3 parameters (`auto-fix-loop`, `review-code-skill`; `orders` is covered in (d)). They are siblings of the proven
detectors: T6 shares T7's parse path and `RULING_TEXT` entry, and the T3 parameters run the one function body
proven in (c) and (d). They are listed here as not independently proven.

---

## (a) T1 `test_census_stop_and_delete_rule_write_prompt`

**Guarded element:** `plugins/superheroes/lib/tests/test_command_refusals.py::test_census_stop_and_delete_rule_write_prompt` —
axis: the stop-and-delete rule text reaches every dispatch-write staged prompt exactly once, and
`ED.WRITE_DISPATCH_PROCESS_RULE is CR.STOP_AND_DELETE_RULE`.

**Neutralization:** Edit tool, in `plugins/superheroes/lib/engine_dispatch.py` replaced
`WRITE_DISPATCH_PROCESS_RULE = command_refusals.STOP_AND_DELETE_RULE` with
`WRITE_DISPATCH_PROCESS_RULE = "Never stop processes by name or pattern."`.

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_census_stop_and_delete_rule_write_prompt _________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-0/test_census_stop_and_delete_ru0')

    def test_census_stop_and_delete_rule_write_prompt(tmp_path):
        wt, _main = _linked_worktree(tmp_path)
        prompt_path = _prompt(tmp_path, "Implement exactly the assigned work order.\n")
        fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
        res = _dispatch_write(tmp_path, fake, cwd=wt, prompt_path=prompt_path)
        assert res["ok"] is True
        with open(os.path.join(str(tmp_path / "run"), ED.PROMPT_NAME), encoding="utf-8") as fh:
            staged = fh.read()
        # axis: the stop-and-delete rule reaches every dispatch-write order exactly once, and the process-rule name is that constant — see bite-proof record wo_2412_stop_and_delete
>       assert staged.count(CR.STOP_AND_DELETE_RULE) == 1
E       AssertionError: assert 0 == 1
E        +  where 0 = <built-in method count of str object at 0xd2f04d0>('Stop only a process you started yourself, and only by its PID, never by name or pattern (`pkill`, `killall`, or `kill...is session or one your task names for deletion, never by a name pattern or a glob over a directory you did not create.')
E        +    where <built-in method count of str object at 0xd2f04d0> = 'Implement exactly the assigned work order.\n\nNever stop processes by name or pattern.\n\nA refused or denied command...e stop rule in this prompt defines it, one entry each (command, refusedBy, hook, route, next); [] when you met none.\n'.count
E        +    and   'Stop only a process you started yourself, and only by its PID, never by name or pattern (`pkill`, `killall`, or `kill...is session or one your task names for deletion, never by a name pattern or a glob over a directory you did not create.' = CR.STOP_AND_DELETE_RULE

/home/user/wt-2412/plugins/superheroes/lib/tests/test_command_refusals.py:337: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_census_stop_and_delete_rule_write_prompt
1 failed in 0.96s
```
Which assertion went red: `staged.count(CR.STOP_AND_DELETE_RULE) == 1` (count 0): the staged prompt carries the
substitute literal, not the rule. (The `is` assertion after it is the second guard and was not reached.)

**Restore:** inverse Edit-tool edit, put back `WRITE_DISPATCH_PROCESS_RULE = command_refusals.STOP_AND_DELETE_RULE`.

**Restore receipt:** `grep -n "^WRITE_DISPATCH_PROCESS_RULE" plugins/superheroes/lib/engine_dispatch.py` after the restore:
`101:WRITE_DISPATCH_PROCESS_RULE = command_refusals.STOP_AND_DELETE_RULE`.

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.81s
```

---

## (b) T2 `test_census_stop_and_delete_rule_native_preamble`

**Guarded element:** `plugins/superheroes/lib/tests/test_command_refusals.py::test_census_stop_and_delete_rule_native_preamble` —
axis: the native implementer preamble carries the stop-and-delete rule exactly once, before "The order follows, verbatim.".

**Neutralization:** Edit tool, in `plugins/superheroes/lib/native_engine.py` item 4 removed
` + " " + command_refusals.STOP_AND_DELETE_RULE` (the line became `... + command_refusals.DELETE_RULE + """`).

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_census_stop_and_delete_rule_native_preamble _______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-2/test_census_stop_and_delete_ru0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f7fb4965ac0>
capsys = <_pytest.capture.CaptureFixture object at 0x7f7fb4964d70>

    def test_census_stop_and_delete_rule_native_preamble(tmp_path, monkeypatch, capsys):
        r = _make_repo(tmp_path)
        _routed(monkeypatch)
        code, _out = _open(capsys, r, deadline=600, items=["src/new.txt"])
        assert code == 0
        with open(os.path.join(os.path.realpath(r.run), "agent-prompt.md"), encoding="utf-8") as fh:
            prompt = fh.read()
        # axis: the stop-and-delete rule reaches the native implementer preamble exactly once — see bite-proof record wo_2412_stop_and_delete
>       assert prompt.count(CR.STOP_AND_DELETE_RULE) == 1
E       AssertionError: assert 0 == 1
E        +  where 0 = <built-in method count of str object at 0x137c4300>('Stop only a process you started yourself, and only by its PID, never by name or pattern (`pkill`, `killall`, or `kill...is session or one your task names for deletion, never by a name pattern or a glob over a directory you did not create.')
E        +    where <built-in method count of str object at 0x137c4300> = 'You are a native implementer subagent for one scoped work order, running in your own isolated git worktree. Follow th...r passes; the fence refuses your commands after it.\n\nThe order follows, verbatim.\n\n---\n\n# Order\nChange a.txt.\n'.count
E        +    and   'Stop only a process you started yourself, and only by its PID, never by name or pattern (`pkill`, `killall`, or `kill...is session or one your task names for deletion, never by a name pattern or a glob over a directory you did not create.' = CR.STOP_AND_DELETE_RULE

/home/user/wt-2412/plugins/superheroes/lib/tests/test_command_refusals.py:349: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_census_stop_and_delete_rule_native_preamble
1 failed in 0.98s
```
Which assertion went red: `prompt.count(CR.STOP_AND_DELETE_RULE) == 1` (count 0).

**Restore:** inverse Edit-tool edit, re-appended ` + " " + command_refusals.STOP_AND_DELETE_RULE` after `command_refusals.DELETE_RULE`.

**Restore receipt:** quoted back from `native_engine.py`:
```
87:4. """ + command_refusals.FILE_WRITE_RULE + " " + command_refusals.DELETE_RULE + " " + command_refusals.STOP_AND_DELETE_RULE + """
```

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.84s
```

---

## (c) T3 `test_census_stop_and_delete_rule_prose_cites[implementer]`

**Guarded element:** `plugins/superheroes/lib/tests/test_command_refusals.py::test_census_stop_and_delete_rule_prose_cites` —
axis: a prose consumer (representative: `agents/implementer.md`) cites `STOP_AND_DELETE_RULE` by name and does not carry
the rule text.

**Neutralization:** Edit tool, in `plugins/superheroes/agents/implementer.md` removed the new sentence
` The stop-and-delete rule (`STOP_AND_DELETE_RULE`, same home) binds every process you stop and every path you delete; read it there and follow it.`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_census_stop_and_delete_rule_prose_cites[implementer] ___________

relpath = 'agents/implementer.md'

    @pytest.mark.parametrize("relpath", [
        os.path.join("agents", "implementer.md"),
        os.path.join("skills", "review-code", "reference", "auto-fix-loop.md"),
        os.path.join("skills", "review-code", "SKILL.md"),
        os.path.join("skills", "workhorse", "reference", "orders.md"),
    ], ids=["implementer", "auto-fix-loop", "review-code-skill", "orders"])
    def test_census_stop_and_delete_rule_prose_cites(relpath):
        with open(os.path.join(_PLUGIN_ROOT, relpath), encoding="utf-8") as fh:
            body = " ".join(fh.read().split())
        # axis: a prose consumer cites the stop-and-delete rule by name, never carries its text (CONVENTIONS §11.4) — see bite-proof record wo_2412_stop_and_delete
>       assert "STOP_AND_DELETE_RULE" in body
E       assert 'STOP_AND_DELETE_RULE' in '--- name: implementer description: Internal build subagent — implements one scoped work order dispatched by the Workh...d out of scope. - Return per the **Short structured return** rule above. Nothing beyond that — no verdict, no "ready."'

/home/user/wt-2412/plugins/superheroes/lib/tests/test_command_refusals.py:363: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_census_stop_and_delete_rule_prose_cites[implementer]
1 failed in 0.76s
```
Which assertion went red: `"STOP_AND_DELETE_RULE" in body` (the citation half).

**Restore:** inverse Edit-tool edit, re-appended the sentence after "This file does not restate it.".

**Restore receipt:** quoted back from `implementer.md`:
```
58:run; read it there and follow it. This file does not restate it. The stop-and-delete rule (`STOP_AND_DELETE_RULE`, same home) binds every process you stop and every path you delete; read it there and follow it.
```

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.80s
```

---

## (d) T4 `test_stop_and_delete_rule_has_one_home` and T3 `[orders]`

**Guarded element:** `plugins/superheroes/lib/tests/test_command_refusals.py::test_stop_and_delete_rule_has_one_home` —
axis: the rule's text (marker "Delete only a path you created in this session") appears only in `lib/command_refusals.py`
and `rubric/launch-doctrine.md`; and `...::test_census_stop_and_delete_rule_prose_cites[orders]` — axis: `orders.md` never
carries the text.

**Neutralization:** Edit tool, in `plugins/superheroes/skills/workhorse/reference/orders.md` (line 80) inserted the full rule
text ("Stop only a process you started yourself, ... a directory you did not create.") immediately before
"They carry the stop-and-delete rule too". Both nodes run in one invocation, so (d) spends two proofs in one run.

**Raw red:**
```
FF                                                                       [100%]
=================================== FAILURES ===================================
____________________ test_stop_and_delete_rule_has_one_home ____________________

    def test_stop_and_delete_rule_has_one_home():
        # A hand copy of the sentence anywhere in the shipped plugin outside its home is a second
        # copy; prose consumers cite the home instead.
        marker = "Delete only a path you created in this session"
        allowed = [
            os.path.join("lib", "command_refusals.py"),
            # parser-verified copy: launch_doctrine.parse refuses any ruling whose text differs from RULING_TEXT, which is STOP_AND_DELETE_RULE itself
            os.path.join("rubric", "launch-doctrine.md"),
        ]
        copies = []
        for root, dirs, files in os.walk(_PLUGIN_ROOT):
            dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__", ".git")]
            for name in files:
                if not name.endswith((".py", ".md", ".json", ".txt")):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding="utf-8", errors="replace") as fh:
                    if marker in " ".join(fh.read().split()):
                        copies.append(os.path.relpath(path, _PLUGIN_ROOT))
        # axis: the stop-and-delete rule's text lives once, in its home plus the parser-verified ruling line — see bite-proof record wo_2412_stop_and_delete
>       assert sorted(copies) == allowed
E       AssertionError: assert ['lib/command...ce/orders.md'] == ['lib/command...-doctrine.md']
E         
E         Left contains one more item: 'skills/workhorse/reference/orders.md'
E         Use -v to get more diff

/home/user/wt-2412/plugins/superheroes/lib/tests/test_command_refusals.py:387: AssertionError
_____________ test_census_stop_and_delete_rule_prose_cites[orders] _____________

relpath = 'skills/workhorse/reference/orders.md'

    @pytest.mark.parametrize("relpath", [
        os.path.join("agents", "implementer.md"),
        os.path.join("skills", "review-code", "reference", "auto-fix-loop.md"),
        os.path.join("skills", "review-code", "SKILL.md"),
        os.path.join("skills", "workhorse", "reference", "orders.md"),
    ], ids=["implementer", "auto-fix-loop", "review-code-skill", "orders"])
    def test_census_stop_and_delete_rule_prose_cites(relpath):
        with open(os.path.join(_PLUGIN_ROOT, relpath), encoding="utf-8") as fh:
            body = " ".join(fh.read().split())
        # axis: a prose consumer cites the stop-and-delete rule by name, never carries its text (CONVENTIONS §11.4) — see bite-proof record wo_2412_stop_and_delete
        assert "STOP_AND_DELETE_RULE" in body
>       assert " ".join(CR.STOP_AND_DELETE_RULE.split()) not in body
E       AssertionError: assert 'Stop only a... not create.' not in '# Contents ... accounting.'
E         
E         'Stop only a proces...you did not create.' is contained here:
E           per call. Stop only a process you started yourself, and only by its PID, never by name or pattern (`pkill`, `killall`, or `kill` over a `pgrep` or `ps` match): other sessions share this machine. Delete only a path you created in this session or one your task names for deletion, never by a name pattern or a glob over a directory you did not create. They carry the stop-and-delete rule too (`STOP_AND_DELETE_RULE`, same home): a process is stopped only by its PID and only when the session started it, and a path ...
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2412/plugins/superheroes/lib/tests/test_command_refusals.py:387: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_stop_and_delete_rule_has_one_home
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_census_stop_and_delete_rule_prose_cites[orders]
2 failed in 0.95s
```
Which assertions went red: T4 `sorted(copies) == allowed` (the extra copy is named: `skills/workhorse/reference/orders.md`);
T3[orders] `rule text not in body` (the `"STOP_AND_DELETE_RULE" in body` half passed, since the citation is still there).
(The `:387` line number printed under the T3 traceback is pytest's own, as captured.)

**Restore:** inverse Edit-tool edit, removed the pasted rule text, leaving "call. They carry the stop-and-delete rule too".

**Restore receipt:** quoted back from `orders.md`:
```
79:  same home): a delete never rides a compound command; it is its own plain call, one path per
80:  call. They carry the stop-and-delete rule too (`STOP_AND_DELETE_RULE`, same home): a process is
81:  stopped only by its PID and only when the session started it, and a path is deleted only when the
82:  session created it or the order names it. When the dispatcher itself decides a different route is legitimate, the re-dispatched order says
```

**Raw green:**
```
..                                                                       [100%]
2 passed in 0.89s
```

---

## (e) T5 `test_every_delete_rule_carrier_carries_the_stop_and_delete_rule`

**Guarded element:** `plugins/superheroes/lib/tests/test_command_refusals.py::test_every_delete_rule_carrier_carries_the_stop_and_delete_rule` —
axis: every shipped file that carries or cites `DELETE_RULE` also carries or cites `STOP_AND_DELETE_RULE`.

**Neutralization:** Edit tool, in `plugins/superheroes/skills/review-code/SKILL.md` (line 157) removed
`, and the stop-and-delete rule, `STOP_AND_DELETE_RULE`, same home, bind these recipes` from the parenthetical, leaving
`(the delete rule, `DELETE_RULE` in `lib/command_refusals.py`)`.

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_every_delete_rule_carrier_carries_the_stop_and_delete_rule ________

    def test_every_delete_rule_carrier_carries_the_stop_and_delete_rule():
        # The invariant census: whatever carries or cites the delete rule also carries or cites the
        # stop-and-delete rule. TRANSITION.md and CHANGELOG.md are history and are skipped.
        delete_text = " ".join(CR.DELETE_RULE.split())
        stop_text = " ".join(CR.STOP_AND_DELETE_RULE.split())
        offenders = []
        for root, dirs, files in os.walk(_PLUGIN_ROOT):
            dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__", ".git")]
            for name in files:
                if not name.endswith((".py", ".md", ".json", ".txt")):
                    continue
                if name in ("TRANSITION.md", "CHANGELOG.md"):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding="utf-8", errors="replace") as fh:
                    raw = fh.read()
                body = " ".join(raw.split())
                carries_delete = "DELETE_RULE" in raw or delete_text in body
                carries_stop = "STOP_AND_DELETE_RULE" in raw or stop_text in body
                if carries_delete and not carries_stop:
                    offenders.append(os.path.relpath(path, _PLUGIN_ROOT))
        # axis: every carrier of the delete rule also carries or cites the stop-and-delete rule — see bite-proof record wo_2412_stop_and_delete
>       assert offenders == []
E       AssertionError: assert ['skills/revi...ode/SKILL.md'] == []
E         
E         Left contains one more item: 'skills/review-code/SKILL.md'
E         Use -v to get more diff

/home/user/wt-2412/plugins/superheroes/lib/tests/test_command_refusals.py:412: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_every_delete_rule_carrier_carries_the_stop_and_delete_rule
1 failed in 0.99s
```
Which assertion went red: `offenders == []`. The offender list holds exactly one path, `skills/review-code/SKILL.md`:
pytest abbreviates the list repr to `['skills/revi...ode/SKILL.md']`, and its "Left contains one more item:
'skills/review-code/SKILL.md'" line names the single item in full.

**Restore:** inverse Edit-tool edit, re-inserted the removed clause.

**Restore receipt:** quoted back from `SKILL.md` line 157:
```
(the delete rule, `DELETE_RULE` in `lib/command_refusals.py`, and the stop-and-delete rule, `STOP_AND_DELETE_RULE`, same home, bind these recipes)
```

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.79s
```

---

## (f) T7 `test_doctrine_own_processes_and_paths_ruling_invariant_missing`

**Guarded element:** `plugins/superheroes/lib/tests/test_launch_doctrine.py::test_doctrine_own_processes_and_paths_ruling_invariant_missing` —
axis: the `own-processes-and-paths` ruling must keep its "only by its PID" phrase; the parse refuses with
`doctrine-ruling-invariant-missing:own-processes-and-paths:only by its PID` and clears every payload field.

**Neutralization:** Edit tool, removed the `"own-processes-and-paths": ( ... )` entry (its three phrases) from
`RULING_INVARIANTS` in `plugins/superheroes/lib/launch_doctrine.py`.

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_doctrine_own_processes_and_paths_ruling_invariant_missing ________

    def test_doctrine_own_processes_and_paths_ruling_invariant_missing():
        # axis: the own-processes-and-paths ruling must keep its "only by its PID" phrase; the parse refuses and clears every payload field — see bite-proof record wo_2412_stop_and_delete
        text = _mutate_once(_read_doctrine(), "only by its PID", "by its name")
        result = LD.parse(text)
        assert result["ok"] is False
>       assert result["reason"] == (
            "doctrine-ruling-invariant-missing:own-processes-and-paths:only by its PID"
        )
E       AssertionError: assert 'doctrine-rul...ses-and-paths' == 'doctrine-rul...ly by its PID'
E         
E         - doctrine-ruling-invariant-missing:own-processes-and-paths:only by its PID
E         + doctrine-ruling-text-mismatch:own-processes-and-paths

/home/user/wt-2412/plugins/superheroes/lib/tests/test_launch_doctrine.py:820: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_doctrine.py::test_doctrine_own_processes_and_paths_ruling_invariant_missing
1 failed in 0.30s
```
Which assertion went red: the `result["reason"]` equality. With the phrase no longer an invariant, the parse falls through
to the text-equality check and refuses with `doctrine-ruling-text-mismatch:own-processes-and-paths` instead of the
invariant reason. The text-mismatch check is a second guard that still refuses the mutated doctrine, so the doctrine is
not left unprotected, but the invariant reason, which names the missing phrase, is what the test pins (the same shape as
wo_d_2314's element (b)).

**Restore:** inverse Edit-tool edit, re-inserted the three-phrase entry after the `no-compound-delete` entry.

**Restore receipt:** `RULING_INVARIANTS["own-processes-and-paths"]` is at `launch_doctrine.py:131`, with its three phrases
(`"only by its PID"`, `"one your task names for deletion"`, `"a glob over a directory you did not create"`).

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.19s
```

---

## (g) T8 `test_every_launch_path_carries_the_own_processes_and_paths_ruling`

**Guarded element:** `plugins/superheroes/lib/tests/test_launcher_cloud.py::test_every_launch_path_carries_the_own_processes_and_paths_ruling` —
axis: the `own-processes-and-paths` ruling line (`STOP_AND_DELETE_RULE`) reaches every composed builder prompt (local
fresh, local adopt, cloud fresh, cloud adopt).

**Neutralization:** Edit tool, deleted `    "own-processes-and-paths",` from `RULING_IDS` in
`plugins/superheroes/lib/launch_doctrine.py` (the doctrine line, the `RULING_TEXT` entry and the `RULING_INVARIANTS` entry
were left in place).

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_every_launch_path_carries_the_own_processes_and_paths_ruling _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-12/test_every_launch_path_carries0')

    def test_every_launch_path_carries_the_own_processes_and_paths_ruling(tmp_path):
        # axis: the own-processes-and-paths ruling (STOP_AND_DELETE_RULE) reaches every composed builder prompt, local and cloud, fresh and adopt — see bite-proof record wo_2412_stop_and_delete
        repo = _init_repo(tmp_path / "repo")
        adopting = dict(_stamped(repo), adoptsBranch="feature/adopted", adoptsHead=_head_sha(repo))
        composed = {
            "local fresh": L.compose_launch(repo, 656, _stamped(repo)),
            "local adopt": L.compose_launch(repo, 656, adopting, place="local"),
            "cloud fresh": _compose_cloud(repo),
            "cloud adopt": L.compose_launch(repo, 656, adopting, place="cloud", cloud_environment=ENV_ID,
                                            session_name="issue-656-preview"),
        }
        line = launch_doctrine.ruling_line(launch_doctrine.load(), "own-processes-and-paths")
>       assert line
E       assert None

/home/user/wt-2412/plugins/superheroes/lib/tests/test_launcher_cloud.py:430: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_every_launch_path_carries_the_own_processes_and_paths_ruling
1 failed in 1.05s
```
Which assertion went red: the first one, `assert line`, because `launch_doctrine.load()` returned a refusal and
`ruling_line` of a refused doctrine is `None`. This is a parse refusal, not a dropped line: the doctrine file still
carries the `own-processes-and-paths` line, so `set(parsed_ids) != set(RULING_IDS)` at `launch_doctrine.py:279` refuses
with `doctrine-ruling-ids-mismatch` (read from the code at lines 278-280; the run did not print the reason string). The
same refusal makes every `compose_launch` call return `ok: False`, so with the id dropped no launch prompt composes at
all: the failure is loud, not a silent omission.

**Restore:** inverse Edit-tool edit, re-inserted `    "own-processes-and-paths",` between `    "no-compound-delete",` and
`    "remote-head",` in `RULING_IDS`.

**Restore receipt:** quoted back from `launch_doctrine.py`:
```
30:    "no-compound-delete",
31:    "own-processes-and-paths",
32:    "remote-head",
```

**Raw green:**
```
.                                                                        [100%]
1 passed in 1.31s
```

---

## (h) `test_no_test_module_copies_the_stop_and_delete_rule` (review fix, round 2)

Added by the build session at review-code's `apply-fixes` step, after the fix auditor ruled the round-1 fix (the write-prompt test reading `CR.STOP_AND_DELETE_RULE` instead of a hand copy) not discharged because nothing would catch the copy coming back: the one-home census skips the tests tree.

**Guarded element:** `plugins/superheroes/lib/tests/test_command_refusals.py::test_no_test_module_copies_the_stop_and_delete_rule` —
axis: no test module keeps its own copy of the stop-and-delete rule's text (adjacent string literals joined by the parser).

**Neutralization:** Edit tool, restored the removed `_NO_PATTERN_KILL_RULE_LITERAL` constant (the full rule text over four adjacent literals) above `_finish_codex_write_runner` in `plugins/superheroes/lib/tests/test_engine_dispatch_write.py`.

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_no_test_module_copies_the_stop_and_delete_rule ______________

    def test_no_test_module_copies_the_stop_and_delete_rule():
        # A test reads the rule from its home (CONVENTIONS §11.3). The one-home census above skips the
        # tests tree, so this reads every test module's string constants (adjacent literals are joined
        # by the parser) and refuses any that holds the whole rule.
        tests_root = os.path.dirname(os.path.abspath(__file__))
        rule = " ".join(CR.STOP_AND_DELETE_RULE.split())
        squashed_rule = re.sub(r"[\s\"']", "", rule)
        copies = []
        for root, dirs, files in os.walk(tests_root):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
                # Cheap screen first: with quotes and whitespace removed, a copy split over adjacent
                # literals still reads as the rule; only such a file is parsed.
                if squashed_rule not in re.sub(r"[\s\"']", "", source):
                    continue
                tree = ast.parse(source, filename=path)
                for node in ast.walk(tree):
                    if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                            and rule in " ".join(node.value.split())):
                        copies.append("%s:%d" % (os.path.relpath(path, tests_root), node.lineno))
        # axis: no test module keeps its own copy of the stop-and-delete rule's text — see bite-proof record wo_2412_stop_and_delete
>       assert copies == []
E       AssertionError: assert ['test_engine...write.py:138'] == []
E         
E         Left contains one more item: 'test_engine_dispatch_write.py:138'
E         Use -v to get more diff

/home/user/wt-2412/plugins/superheroes/lib/tests/test_command_refusals.py:443: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_no_test_module_copies_the_stop_and_delete_rule
1 failed in 26.56s
```
Which assertion went red: `assert copies == []`, naming `test_engine_dispatch_write.py:138`, the restored constant.

**Restore:** Edit tool, the inverse edit removed the constant again; `git diff --stat` afterwards showed only `test_command_refusals.py` changed.

**Raw green:**
```
.                                                                        [100%]
1 passed in 1.20s
```
