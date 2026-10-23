# WO-1 (#2110) bite-proof — the host model falls back to the session transcript

**Provenance:** detectors typed by claude / sonnet-5.5 (implementer, effort high; WO-1, WO-1b), `plugins/superheroes/lib/host_model.py`, `plugins/superheroes/lib/launcher.py`. Proofs run and this record written by the build orchestrator (claude / opus-5.5 host session) in a detached probe worktree at `ba4001d1`: the implementer's own proof command was refused by a harness shell check before it ran, so it produced no receipts, and the orchestrator ran every element itself.

Declared guarded-element set (from the order): G1–G4. Each was neutralized by one exact text swap in production code only, made with the host's Edit tool; the proving node was run red; the neutralization was undone by the inverse Edit; the same node was run green. Every node was selected by its exact node id. All runs: `scripts/pinned-python -B -X pycache_prefix=<scratch>/pyc -m pytest "<node>" -q -p no:cacheprovider` from `<repo>`. Redactions: the probe worktree root is `<repo>`, pytest temp paths are `<tmp>`, object addresses are `0x…`, and uv's deprecation warning line is dropped; nothing else was edited.

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| G1 | the transcript branch of `host_model.resolve` (`plugins/superheroes/lib/host_model.py:122`) | a start event that names no model resolves the host model from the session transcript, so compose keeps a known `hostFamily` and records no `host-model-unknown` (the DoD's "drop the fallback and the no-model test goes red") | `test_no_model_in_the_start_event_reads_the_session_transcript` |
| G2 | the start-offset bound in `from_transcript` (`host_model.py:89`) | a main-chain turn written before this start (a resumed or copied transcript's history) never stands in for the live model | `test_a_model_recorded_before_this_start_never_stands_in` |
| G3 | the sidechain skip in `_line_model` (`host_model.py:76`) | a subagent (sidechain) turn never stands in for the host model | `test_from_transcript_picks_the_last_main_chain_assistant_model` |
| G4 | the session-variable pop in `launcher._spawn_attempt` (`plugins/superheroes/lib/launcher.py:2074`) | a parent's `SUPERHEROES_HOST_MODEL`, `SUPERHEROES_SESSION_TRANSCRIPT` and `SUPERHEROES_SESSION_TRANSCRIPT_FROM` never reach a spawned child | `test_spawn_attempt_drops_the_session_variables_from_the_child` |

## Disclosures

- Every declared element has a proving node that went red under its neutralization; none is recorded as unproven.
- Not separately neutralized, so unproven here: the `<synthetic>` and malformed-line skips (guarded green by `test_from_transcript_picks_the_last_main_chain_assistant_model` and `test_from_transcript_only_sidechain_synthetic_or_foreign_lines_gives_empty`), the hook's three exports (guarded green by the `test_hook_*` tests in `test_host_model_2110.py`), and the start-event-wins branch (guarded green by `test_the_start_event_model_wins_over_the_transcript`).
- Baseline sha256 before any neutralization: `cb12b71f3a15e1b9b9c1148acfbc2d02b504cb9830195fc0a74074259061640a  plugins/superheroes/lib/host_model.py`, `0103738d49627be4c4f95c0c0f221357f804a3e7f90bb30dd03be10574eb0685  plugins/superheroes/lib/launcher.py`. After every restore the file hashed to its baseline and `git status --porcelain` in the probe worktree printed nothing.

---

## G1 — the transcript branch of `host_model.resolve` (`plugins/superheroes/lib/host_model.py:122`)

- **axis:** a start event that names no model resolves the host model from the session transcript, so compose keeps a known `hostFamily` and records no `host-model-unknown` (the DoD's "drop the fallback and the no-model test goes red")
- **neutralization:** `        model = from_transcript(transcript_path, transcript_start)` → `        model = ""  # BITE-PROOF G1: transcript fallback dropped`
- **sha256 neutralized:** `02bc9a9a7d43d0a045560e11c00528c07bb04bfeba03e8e9ea008c85b355ea70`
- **raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_no_model_in_the_start_event_reads_the_session_transcript _________

capsys = <_pytest.capture.CaptureFixture object at 0x…>
tmp_path = PosixPath('<tmp>')

    def test_no_model_in_the_start_event_reads_the_session_transcript(capsys, tmp_path):
        # axis: the DoD's no-model test — the transcript fallback in resolve keeps the Claude seat
        # (bite-proof G1, see wo_2110_host_model_transcript)
        transcript = _write(tmp_path / "t.jsonl", _assistant("claude-opus-5-5"))
        receipt = _compose(capsys, ["--host-model", "", "--session-transcript", transcript,
                                    "--session-transcript-from", "0"])
>       assert not _unknown(receipt)
E       assert not [{'constraint': 'host-model-unknown', 'reason': "host model unknown — neither the start event nor the session transcri...ily fell back to the claude host's family (anthropic); the author family is the cursor implementation engine's (xai)"}]
E        +  where [{'constraint': 'host-model-unknown', 'reason': "host model unknown — neither the start event nor the session transcri...ily fell back to the claude host's family (anthropic); the author family is the cursor implementation engine's (xai)"}] = _unknown({'seats': {'code-reviewer': {'vendor': 'claude', 'model': 'opus-5.5', 'effort': 'xhigh', 'tier': 'reviewer-deep', ...}...y is the cursor implementation engine's (xai)"}], 'seed': 400306947, 'liveVendors': ['claude', 'codex', 'cursor'], ...})

<repo>/plugins/superheroes/lib/tests/test_host_model_2110.py:68: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_host_model_2110.py::test_no_model_in_the_start_event_reads_the_session_transcript
1 failed in 1.37s
```

- **restore:** the inverse Edit, back to the original line.
- **restore receipt:** sha256 after restore `cb12b71f3a15e1b9b9c1148acfbc2d02b504cb9830195fc0a74074259061640a` (equal to the baseline); `git status --porcelain` empty.
- **raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.55s
```

---

## G2 — the start-offset bound in `from_transcript` (`host_model.py:89`)

- **axis:** a main-chain turn written before this start (a resumed or copied transcript's history) never stands in for the live model
- **neutralization:** `        begin = int(start)` → `        begin = 0  # BITE-PROOF G2: start offset ignored`
- **sha256 neutralized:** `de6d079d8700774a266454f8e447746264119307dbcc2a9ba7c29260a7bb57fa`
- **raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_a_model_recorded_before_this_start_never_stands_in ____________

capsys = <_pytest.capture.CaptureFixture object at 0x…>
tmp_path = PosixPath('<tmp>')

    def test_a_model_recorded_before_this_start_never_stands_in(capsys, tmp_path):
        # axis: B1 — history before the start offset is not the live model (bite-proof G2)
        path = tmp_path / "t.jsonl"
        transcript = _write(path, _assistant("gpt-5.6-sol"))
        start = str(os.path.getsize(transcript))
        args = ["--host-model", "", "--session-transcript", transcript, "--session-transcript-from", start]
        stale = _compose(capsys, args)
>       assert len(_unknown(stale)) == 1
E       AssertionError: assert 0 == 1
E        +  where 0 = len([])
E        +    where [] = _unknown({'seats': {'code-reviewer': {'vendor': 'claude', 'model': 'opus-5.5', 'effort': 'xhigh', 'tier': 'reviewer-deep', ...}... 'reviewer-deep', ...}, ...}, 'degradations': [], 'seed': 400306947, 'liveVendors': ['claude', 'codex', 'cursor'], ...})

<repo>/plugins/superheroes/lib/tests/test_host_model_2110.py:100: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_host_model_2110.py::test_a_model_recorded_before_this_start_never_stands_in
1 failed in 1.61s
```

- **restore:** the inverse Edit, back to the original line.
- **restore receipt:** sha256 after restore `cb12b71f3a15e1b9b9c1148acfbc2d02b504cb9830195fc0a74074259061640a` (equal to the baseline); `git status --porcelain` empty.
- **raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.53s
```

---

## G3 — the sidechain skip in `_line_model` (`host_model.py:76`)

- **axis:** a subagent (sidechain) turn never stands in for the host model
- **neutralization:** `obj.get("type") != "assistant" or obj.get("isSidechain") is True:` → `obj.get("type") != "assistant":  # BITE-PROOF G3: sidechain skip dropped`
- **sha256 neutralized:** `09989b64517b1a598ac47aa88731d7fd5052832d7e2931aa4307402b4fb079c4`
- **raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_from_transcript_picks_the_last_main_chain_assistant_model ________

tmp_path = PosixPath('<tmp>')

    def test_from_transcript_picks_the_last_main_chain_assistant_model(tmp_path):
        # axis: sidechain, synthetic, non-assistant and malformed lines never stand in (bite-proof G3)
        path = tmp_path / "t.jsonl"
        path.write_bytes(b"".join(line.encode() for line in (
            _assistant("claude-haiku-5-5"),
            _assistant("gpt-5.6-sol", sidechain=True),
            json.dumps({"type": "user", "message": {"model": "gpt-5.6-sol"}}) + "\n",
            "{not json\n")) + b"\xff\xfe\n" + b"".join(line.encode() for line in (
            json.dumps({"type": "assistant", "message": "claude-x"}) + "\n",
            json.dumps({"type": "assistant", "isSidechain": False}) + "\n",
            _assistant("<synthetic>"),
            _assistant("claude-opus-5-5"),
            _assistant("gpt-5.6-sol", sidechain=True),
            _assistant("<synthetic>"))))
>       assert HM.from_transcript(str(path), "0") == "claude-opus-5-5"
E       AssertionError: assert 'gpt-5.6-sol' == 'claude-opus-5-5'
E         
E         - claude-opus-5-5
E         + gpt-5.6-sol

<repo>/plugins/superheroes/lib/tests/test_host_model_2110.py:126: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_host_model_2110.py::test_from_transcript_picks_the_last_main_chain_assistant_model
1 failed in 1.47s
```

- **restore:** the inverse Edit, back to the original line.
- **restore receipt:** sha256 after restore `cb12b71f3a15e1b9b9c1148acfbc2d02b504cb9830195fc0a74074259061640a` (equal to the baseline); `git status --porcelain` empty.
- **raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.60s
```

---

## G4 — the session-variable pop in `launcher._spawn_attempt` (`plugins/superheroes/lib/launcher.py:2074`)

- **axis:** a parent's `SUPERHEROES_HOST_MODEL`, `SUPERHEROES_SESSION_TRANSCRIPT` and `SUPERHEROES_SESSION_TRANSCRIPT_FROM` never reach a spawned child
- **neutralization:** `        child_env.pop(name, None)   # a child session` → `        pass  # BITE-PROOF G4: pop dropped   # a child session`
- **sha256 neutralized:** `493b8ac08bce48cca8e511e7a170acd350795d6df2a00b4e9d57f1498c9a6df1`
- **raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_spawn_attempt_drops_the_session_variables_from_the_child _________

tmp_path = PosixPath('<tmp>')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x…>

    def test_spawn_attempt_drops_the_session_variables_from_the_child(tmp_path, monkeypatch):
        # axis: E6 — a parent's host model and transcript never reach a spawned child (bite-proof G4)
        L = TL.L
        repo = TL._init_repo(tmp_path / "repo")
        ledger_root = TL._ledger_env(tmp_path, monkeypatch)
        launch_id = "launch-2110-session-vars"
        ll.reserve(repo, {
            "event": "reserved", "launchId": launch_id, "ts": time.time(), "schema": ll.SCHEMA,
            "batchId": "batch-2110", "repoId": ll.repo_identity(repo), "issue": 2110,
            "surfaces": ["plugins/superheroes/lib"], "premise": {}, "preflight": {}, "argv": [],
            "doctrineDigest": "abc", "model": "test",
        })
        captured = {}
    
        def capture_spawn(argv, repo_root, out_fh, err_fh, child_env):
            captured.update(child_env)
    
            class _Proc:
                pid = 424248
    
            out_fh.close()
            err_fh.close()
            return _Proc()
    
        log_dir = str(tmp_path / "logs")
        os.makedirs(log_dir)
        parent_env = {ll.LEDGER_ROOT_ENV: ledger_root}
        parent_env.update({name: "parent-value" for name in HM.SESSION_ENV_VARS})
        result = L._spawn_attempt(
            repo, launch_id, 1, ["claude", "-p", "test"],
            os.path.join(log_dir, "out.log"), os.path.join(log_dir, "err.log"), 900000,
            env=parent_env, spawn_fn=capture_spawn, cwd=TL._spawn_cwd(tmp_path),
        )
        assert result["ok"] is True
        assert len(HM.SESSION_ENV_VARS) == 3
        for name in HM.SESSION_ENV_VARS:
>           assert name not in captured
E           AssertionError: assert 'SUPERHEROES_HOST_MODEL' not in {'SUPERHEROES_HOST_MODEL': 'parent-value', 'SUPERHEROES_SESSION_TRANSCRIPT': 'parent-value', 'SUPERHEROES_SESSION_TRANSCRIPT_FROM': 'parent-value', 'SUPERHEROES_LAUNCH_ID': 'launch-2110-session-vars', ...}

<repo>/plugins/superheroes/lib/tests/test_host_model_2110.py:370: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_host_model_2110.py::test_spawn_attempt_drops_the_session_variables_from_the_child
1 failed in 1.53s
```

- **restore:** the inverse Edit, back to the original line.
- **restore receipt:** sha256 after restore `0103738d49627be4c4f95c0c0f221357f804a3e7f90bb30dd03be10574eb0685` (equal to the baseline); `git status --porcelain` empty.
- **raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.50s
```
