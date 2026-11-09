# #2399 bite-proof — the repository-sweep searcher agent

**Provenance:** claude (implementer), work order WO-2 (detectors added by WO-1, commit `b63ae5de`). Worktree `/home/user/wt-2399`, branch `claude/task-auijfg`, base `c72c4282bbb980a3108d37d732645c5305989a73`.
Every run is `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "<node id>" -q` from the worktree, the detector unedited, on the single test node named in each entry.
Each neutralization is one targeted Edit, undone by the inverse Edit; the restore receipt is the restored line quoted back (the Edit's exact inverse string) plus the green run of the same node.
Captures are far under the 32 KiB / 128 KiB ceilings. Nothing was redacted (no credential-like text appears). Dropped from every capture: the `UV_NATIVE_TLS` deprecation warning line, shown once per run and omitted below; the runs are otherwise shown whole.

## Guarded elements (declared in WO-2) and how they are grouped

| ID | Guarded element (axis) | File : site | Detector node |
|---|---|---|---|
| G1 | the searcher's parsed `tools:` grant equals Read, Grep, Glob exactly (an added tool fails; a removed tool fails) | `plugins/superheroes/agents/searcher.md:4` | `test_seat_tool_grants.py::test_searcher_grant_is_exactly_read_grep_glob` |
| G2 | the searcher dispatch paragraph names the `superheroes:searcher` plugin agent (and `general-purpose` appears only in a `never` sentence) | `plugins/superheroes/skills/review-code/reference/auto-fix-loop.md:742` | `test_seat_tool_grants.py::test_searcher_dispatch_names_the_plugin_agent_and_never_general_purpose` |
| G3 | the host-seat sweep order replies and carries no write line | `plugins/superheroes/lib/round_orders.py:431` (`_format_landing_block`) | `test_round_orders.py::test_sweep_host_seat_order_replies_and_never_writes` |

G1 is proven on two distinct failure modes (a tool added, a tool removed), each its own red. No element is left unproven.

## G1 — the searcher grant is exactly Read, Grep, Glob

### G1 red 1 — a tool added

**neutralization** (`agents/searcher.md`, line 4):
```diff
-tools: Read, Grep, Glob
+tools: Read, Grep, Glob, Bash
```
**raw red** (`::test_searcher_grant_is_exactly_read_grep_glob`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_searcher_grant_is_exactly_read_grep_glob _________________

    def test_searcher_grant_is_exactly_read_grep_glob():
        """Axis: the repository-sweep searcher's parsed tools: grant equals Read, Grep, Glob exactly —
        adding a tool (a write, shell, session or messaging tool) or removing one fails (#2399)."""
        tools = _parse_tools(
            _read_required(os.path.join(PLUGIN, "agents", "searcher.md"),
                           "the repository-sweep searcher seat"),
            "searcher")
>       assert sorted(tools) == SEARCHER_EXACT_TOOLS, (
            "searcher-grant-not-exact: %s" % sorted(tools))
E       AssertionError: searcher-grant-not-exact: ['Bash', 'Glob', 'Grep', 'Read']
E       assert ['Bash', 'Glo...Grep', 'Read'] == ['Glob', 'Grep', 'Read']
E         
E         At index 0 diff: 'Bash' != 'Glob'
E         Left contains one more item: 'Read'
E         Use -v to get more diff

/home/user/wt-2399/plugins/superheroes/lib/tests/test_seat_tool_grants.py:862: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_tool_grants.py::test_searcher_grant_is_exactly_read_grep_glob
1 failed in 0.15s
```
Failing assertion line: `AssertionError: searcher-grant-not-exact: ['Bash', 'Glob', 'Grep', 'Read']`.
**restore:** the inverse Edit (`tools: Read, Grep, Glob, Bash` back to `tools: Read, Grep, Glob`). **restore receipt:** the restored line quoted back, `tools: Read, Grep, Glob`, and `git status --porcelain -- plugins` at the end of the dispatch does not list `agents/searcher.md`.
**raw green** (same node):
```
.                                                                        [100%]
1 passed in 0.15s
```
Pass line: `1 passed in 0.15s`.

### G1 red 2 — a tool removed

**neutralization** (`agents/searcher.md`, line 4):
```diff
-tools: Read, Grep, Glob
+tools: Read, Grep
```
**raw red** (same node):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_searcher_grant_is_exactly_read_grep_glob _________________

    def test_searcher_grant_is_exactly_read_grep_glob():
        """Axis: the repository-sweep searcher's parsed tools: grant equals Read, Grep, Glob exactly —
        adding a tool (a write, shell, session or messaging tool) or removing one fails (#2399)."""
        tools = _parse_tools(
            _read_required(os.path.join(PLUGIN, "agents", "searcher.md"),
                           "the repository-sweep searcher seat"),
            "searcher")
>       assert sorted(tools) == SEARCHER_EXACT_TOOLS, (
            "searcher-grant-not-exact: %s" % sorted(tools))
E       AssertionError: searcher-grant-not-exact: ['Grep', 'Read']
E       assert ['Grep', 'Read'] == ['Glob', 'Grep', 'Read']
E         
E         At index 0 diff: 'Grep' != 'Glob'
E         Right contains one more item: 'Read'
E         Use -v to get more diff

/home/user/wt-2399/plugins/superheroes/lib/tests/test_seat_tool_grants.py:862: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_tool_grants.py::test_searcher_grant_is_exactly_read_grep_glob
1 failed in 0.22s
```
Failing assertion line: `AssertionError: searcher-grant-not-exact: ['Grep', 'Read']`.
**restore:** the inverse Edit (`tools: Read, Grep` back to `tools: Read, Grep, Glob`). **restore receipt:** the restored line quoted back, `tools: Read, Grep, Glob`. **raw green** (same node):
```
.                                                                        [100%]
1 passed in 0.14s
```
Pass line: `1 passed in 0.14s`.

## G2 — the dispatch paragraph names the plugin agent

**neutralization** (`auto-fix-loop.md`, line 742, the `**Dispatching searchers.**` paragraph; the first `superheroes:searcher`):
```diff
-as the read-only plugin agent `superheroes:searcher` (`agents/searcher.md`), by
+as the read-only plugin agent `general-purpose` (`agents/searcher.md`), by
```
**raw red** (`::test_searcher_dispatch_names_the_plugin_agent_and_never_general_purpose`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_searcher_dispatch_names_the_plugin_agent_and_never_general_purpose ____

    def test_searcher_dispatch_names_the_plugin_agent_and_never_general_purpose():
        """Axis: every searcher dispatch site names the `superheroes:searcher` agent, and the only
        `general-purpose` mentions sit in a sentence that says `never` (#2399)."""
        paragraph = _dispatching_searchers_paragraph()
>       assert "superheroes:searcher" in paragraph, "searcher-dispatch-agent-not-named: auto-fix-loop.md"
E       AssertionError: searcher-dispatch-agent-not-named: auto-fix-loop.md
E       assert 'superheroes:searcher' in "**Dispatching searchers.** The `dispatch-sweep` phase's seats (`searcher:<sweepId>:<part>`) are each dispatched\nas t.... See [the `dispatch-sweep` row](round-driver.md#actions-and-payloads)\nfor the payload and how the hits are routed.\n"

/home/user/wt-2399/plugins/superheroes/lib/tests/test_seat_tool_grants.py:882: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_tool_grants.py::test_searcher_dispatch_names_the_plugin_agent_and_never_general_purpose
1 failed in 0.18s
```
Failing assertion line: `AssertionError: searcher-dispatch-agent-not-named: auto-fix-loop.md`.
**restore:** the inverse Edit. **restore receipt:** the restored text quoted back, ``as the read-only plugin agent `superheroes:searcher` (`agents/searcher.md`), by``, and the final `git diff HEAD` over `auto-fix-loop.md` shows only the one citation replacement. **raw green** (same node):
```
.                                                                        [100%]
1 passed in 0.16s
```
Pass line: `1 passed in 0.16s`.

## G3 — the host-seat sweep order replies and never writes

**neutralization** (`plugins/superheroes/lib/round_orders.py:431`, `_format_landing_block`):
```diff
-    if host_seat and phase == round_phases.P_SWEEP:
+    if False:
```
**raw red** (`::test_sweep_host_seat_order_replies_and_never_writes`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_sweep_host_seat_order_replies_and_never_writes ______________

    def test_sweep_host_seat_order_replies_and_never_writes():
        """Axis: the host-seat sweep order carries the reply delivery and the landing path, and no write
        instruction in either the channel block or the landing block (the searcher holds no write tool)."""
        ctx = _GOLDEN_CONTEXTS[RP.P_SWEEP]()
        text, reason = RO.render_order(RP.P_SWEEP, "golden-seat", ctx)
        assert reason is None, reason
        assert RO._SWEEP_HOST_REPLY_DELIVERY in text, "sweep-host-reply-delivery-missing"
        assert ctx["landing_path"] in text, "sweep-landing-path-missing"
>       assert "Write **only** your payload artifact" not in text, "sweep-host-landing-write-line"
E       AssertionError: sweep-host-landing-write-line
E       assert 'Write **onl...oad artifact' not in 'You are a s...yload.json\n'
E         
E         'Write **only** your payload artifact' is contained here:
E           r result
E           
E           Write **only** your payload artifact to the landing path below — no envelope header, no stub copy.
E         ? ++++++++++++++++++++++++++++++++++++
E           
E           - Payload landing path: /tmp/superheroes-session-wo4-golden/round-2/landing/dispatch-sweep/searcher-s-1-1-ebb8eeb8adb8d8fc.a0.payload.json

/home/user/wt-2399/plugins/superheroes/lib/tests/test_round_orders.py:477: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_orders.py::test_sweep_host_seat_order_replies_and_never_writes
1 failed in 0.23s
```
Failing assertion line: `AssertionError: sweep-host-landing-write-line` (the host write line returns).
**restore:** the inverse Edit (`    if False:` back to `    if host_seat and phase == round_phases.P_SWEEP:`). **restore receipt:** the restored line quoted back, `    if host_seat and phase == round_phases.P_SWEEP:`, and `git status --porcelain -- plugins` at the end of the dispatch does not list `round_orders.py`. **raw green** (same node):
```
.                                                                        [100%]
1 passed in 0.19s
```
Pass line: `1 passed in 0.19s`.

## Final tree after every restore

Both detector files together, every element restored (`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_seat_tool_grants.py plugins/superheroes/lib/tests/test_round_orders.py -q`):
```
........................................................................ [ 65%]
......................................                                   [100%]
110 passed in 1.56s
```
`git status --porcelain -- plugins` at that point lists only `auto-fix-loop.md` and `round-driver.md` (the two citation fixes) beside this new record; `agents/searcher.md` and `round_orders.py` do not differ from the committed tree.
