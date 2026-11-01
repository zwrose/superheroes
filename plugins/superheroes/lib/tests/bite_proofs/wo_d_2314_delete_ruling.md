# WO-D (#2314) bite-proofs — the `no-compound-delete` standing ruling

Declared guarded-element set (from the order): (a) the compose census — the `no-compound-delete` ruling
line reaches every composed builder prompt (`test_every_launch_path_carries_the_no_compound_delete_ruling`);
(b) the invariant — the ruling keeps its "one path per call" phrase
(`test_doctrine_no_compound_delete_ruling_invariant_missing`).

Commands used the pinned interpreter: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-d -m pytest <node> -q -p no:cacheprovider`.
The `UV_NATIVE_TLS` deprecation warning line that opens each run is omitted below; nothing else is trimmed.
No secrets or tokens appear in these captures; nothing is redacted.

---

## (a) `test_every_launch_path_carries_the_no_compound_delete_ruling`

**Guarded element:** `plugins/superheroes/lib/tests/test_launcher_cloud.py::test_every_launch_path_carries_the_no_compound_delete_ruling` —
axis: the `no-compound-delete` ruling line (`DELETE_RULE`) reaches every composed builder prompt (local fresh,
local adopt, cloud fresh, cloud adopt).

**Neutralization:** Edit tool, deleted `    "no-compound-delete",` from `RULING_IDS` in
`plugins/superheroes/lib/launch_doctrine.py` (the doctrine line, the `RULING_TEXT` entry and the
`RULING_INVARIANTS` entry were left in place).

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_every_launch_path_carries_the_no_compound_delete_ruling _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_every_launch_path_carries0')

    def test_every_launch_path_carries_the_no_compound_delete_ruling(tmp_path):
        # axis: the no-compound-delete ruling (DELETE_RULE) reaches every composed builder prompt, local and cloud, fresh and adopt
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_d_2314_delete_ruling.md (wo_d_2314_delete_ruling)
        repo = _init_repo(tmp_path / "repo")
        adopting = dict(_stamped(repo), adoptsBranch="feature/adopted", adoptsHead=_head_sha(repo))
        composed = {
            "local fresh": L.compose_launch(repo, 656, _stamped(repo)),
            "local adopt": L.compose_launch(repo, 656, adopting, place="local"),
            "cloud fresh": _compose_cloud(repo),
            "cloud adopt": L.compose_launch(repo, 656, adopting, place="cloud", cloud_environment=ENV_ID,
                                            session_name="issue-656-preview"),
        }
        line = launch_doctrine.ruling_line(launch_doctrine.load(), "no-compound-delete")
>       assert line
E       assert None

/home/user/wt-2314-d/plugins/superheroes/lib/tests/test_launcher_cloud.py:408: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_every_launch_path_carries_the_no_compound_delete_ruling
1 failed in 2.46s
```
Which assertion went red: the first one, `assert line` (line 408), because `launch_doctrine.load()` returned a
refusal and `ruling_line` of a refused doctrine is `None`. This is a parse refusal, not a dropped line: the
doctrine file still carries the `no-compound-delete` line, so `set(parsed_ids) != set(RULING_IDS)` in
`_parse_rulings_block` refuses with `doctrine-ruling-ids-mismatch` (by reading `launch_doctrine.py`; the run did not
print the reason, so that reason string is read from the code, not observed). The same refusal makes every
`compose_launch` call return `ok: False` (`compose_launch` returns `_fail(doctrine.get("reason"))` when the doctrine
is not ok), so with the id dropped no launch prompt composes at all — the failure is loud, not a silent omission.

**Restore:** inverse Edit-tool edit, re-inserted `    "no-compound-delete",` between `    "turn-end",` and
`    "remote-head",` in `RULING_IDS`.

**Restore receipt:** `grep no-compound-delete lib/launch_doctrine.py` after both restores shows
`30:    "no-compound-delete",` (RULING_IDS), `85:    "no-compound-delete": command_refusals.DELETE_RULE,`
(RULING_TEXT), `125:    "no-compound-delete": (` (RULING_INVARIANTS).

**Raw green:**
```
.                                                                        [100%]
1 passed in 2.43s
```

---

## (b) `test_doctrine_no_compound_delete_ruling_invariant_missing`

**Guarded element:** `plugins/superheroes/lib/tests/test_launch_doctrine.py::test_doctrine_no_compound_delete_ruling_invariant_missing` —
axis: the `no-compound-delete` ruling must keep its "one path per call" phrase; the parse refuses with
`doctrine-ruling-invariant-missing:no-compound-delete:one path per call` and clears every payload field.

**Neutralization:** Edit tool, deleted the line `        "one path per call",` from
`RULING_INVARIANTS["no-compound-delete"]` in `plugins/superheroes/lib/launch_doctrine.py`, leaving only
`"inside a compound command"`.

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_doctrine_no_compound_delete_ruling_invariant_missing ___________

    def test_doctrine_no_compound_delete_ruling_invariant_missing():
        # axis: the no-compound-delete ruling must keep its "one path per call" phrase; the parse refuses and clears every payload field
        text = _mutate_once(_read_doctrine(), "one path per call", "one file per call")
        result = LD.parse(text)
        assert result["ok"] is False
>       assert result["reason"] == (
            "doctrine-ruling-invariant-missing:no-compound-delete:one path per call"
        )
E       AssertionError: assert 'doctrine-rul...mpound-delete' == 'doctrine-rul...path per call'
E         
E         - doctrine-ruling-invariant-missing:no-compound-delete:one path per call
E         + doctrine-ruling-text-mismatch:no-compound-delete

/home/user/wt-2314-d/plugins/superheroes/lib/tests/test_launch_doctrine.py:795: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_doctrine.py::test_doctrine_no_compound_delete_ruling_invariant_missing
1 failed in 0.46s
```
Which assertion went red: the `result["reason"]` equality. With the phrase no longer an invariant, the parse
falls through to the text-equality check and refuses with `doctrine-ruling-text-mismatch:no-compound-delete`
instead of the invariant reason. Note the text-mismatch check is a second guard that still refuses the mutated
doctrine, so the doctrine is not left unprotected, but the invariant reason, which names the missing phrase, is
what the test pins.

**Restore:** inverse Edit-tool edit, re-inserted `        "one path per call",` after `"inside a compound command",`.

**Restore receipt:** quoted back from `launch_doctrine.py`:
```
125:    "no-compound-delete": (
126:        "inside a compound command",
127:        "one path per call",
128:    ),
```

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.40s
```
