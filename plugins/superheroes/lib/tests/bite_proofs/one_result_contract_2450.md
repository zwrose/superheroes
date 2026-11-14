# Bite-proof — `test_one_result_contract_2450.py` (#2450: one result contract per review order)

Detector: `plugins/superheroes/lib/tests/test_one_result_contract_2450.py`, run unedited for every red and
green below. Command shape for every run (one test element each):

`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2450 -m pytest plugins/superheroes/lib/tests/test_one_result_contract_2450.py -q -x -k <element> -p no:cacheprovider`

Guarded-element set (declared by the order): **(a)** the fed prompt of a real codex dispatch, **(b)** the
files a seat is pointed at, **(c)** the real driver emission, **(d)** the render-level healthy sibling.
Each neutralization is a targeted edit undone by the inverse edit; no `git stash`/`checkout`/`restore`.
Receipts are test-runner output with no secrets, tokens, private URLs or PII; nothing is redacted. Pytest's
`UV_NATIVE_TLS` deprecation warning line is omitted from the captures (one line each, tooling noise).

Disclosure on (a): the element holds several assertions (one `Review result contract` line, native contract
is the tail, no `## Payload contract`, the null-for-omitted line once, no omit line naming a finding member).
The order's budget allows one neutralization per element, so only the first (a second contract appended to
the fed prompt) was proven red; the other four assertions of (a) are **unproven by a separate neutralization**.
The omit-line assertion is proven red through (b), which runs the same `_omit_lines` helper over files.

## (a) a real codex order, dispatched, carries exactly one contract — `-k element_a`

- **Axis:** count of `Review result contract` lines in the `fedPrompt` of the run `dispatch_review` opens.
- **Neutralization:** `plugins/superheroes/lib/engine_dispatch.py`, in `_dispatch_review_impl` directly after the
  native-contract append, a second identical append was added:
  `fed_prompt += _prompt_section_sep + engine_result_channel.review_result_contract_from_schema(native_schema, delivery=delivery,)`
- **Raw red:**
```
F
=================================== FAILURES ===================================
_____ test_element_a_codex_fed_prompt_states_one_result_contract[findings] _____
...
        headings = [ln for ln in fed.splitlines() if ln.startswith(_CONTRACT_LINE_PREFIX)]
>       assert len(headings) == 1, headings
E       AssertionError: ['Review result contract (your graded result file must match the declared schema):', 'Review result contract (your graded result file must match the declared schema):']
E       assert 2 == 1
/home/user/wt-2450/plugins/superheroes/lib/tests/test_one_result_contract_2450.py:121: AssertionError
FAILED plugins/superheroes/lib/tests/test_one_result_contract_2450.py::test_element_a_codex_fed_prompt_states_one_result_contract[findings]
1 failed, 10 deselected in 2.34s
```
  (elided: the test body and fixture echo between the `...` markers — about 25 lines; the failing assertion, its
  message and the summary are verbatim.)
- **Restore:** the inserted second append was removed by the inverse edit.
- **Restore receipt:** `grep -n "BITE-PROOF" engine_dispatch.py` printed nothing; lines 6653-6662 show the
  single `if ... CHANNEL_NATIVE:` block ending with one `fed_prompt += ... review_result_contract_from_schema(native_schema, delivery=delivery,)`.
- **Raw green:**
```
....                                                                     [100%]
4 passed, 10 deselected in 2.20s
```

## (b) the files a seat is pointed at omit no member — `-k element_b`

- **Axis:** a line of `rubric/review-base.md` or a reviewer agent file that names a findings-item property in
  backticks or quotes and says `omit`.
- **Neutralization:** `plugins/superheroes/rubric/review-base.md` line 161, the finding-format example:
  `"tradeoff": "<true only if multiple valid fix approaches exist; false otherwise>",` became `... exist; omit otherwise>",`
- **Raw red:**
```
F
=================================== FAILURES ===================================
________ test_element_b_pointed_at_files_tell_no_seat_to_omit_a_member _________
...
>       assert offenders == []
E       assert ['rubric/revi...otherwise>",'] == []
E
E         Left contains one more item: 'rubric/review-base.md:161: "tradeoff": "<true only if multiple valid fix approaches exist; omit otherwise>",'
E         Use -v to get more diff
FAILED plugins/superheroes/lib/tests/test_one_result_contract_2450.py::test_element_b_pointed_at_files_tell_no_seat_to_omit_a_member
1 failed, 13 deselected in 2.38s
```
  (elided: the test body between the `...` markers, about 12 lines.)
- **Restore:** `omit otherwise` set back to `false otherwise` by the inverse edit.
- **Restore receipt:** `grep -n '"tradeoff"' plugins/superheroes/rubric/review-base.md` printed
  `161:    "tradeoff": "<true only if multiple valid fix approaches exist; false otherwise>",`
- **Raw green:**
```
.                                                                        [100%]
1 passed, 13 deselected in 2.38s
```

## (c) the real driver emission — `-k element_c`

- **Axis:** the `## Payload contract` heading count in the order file the driver writes for a codex seat
  (`test_round_driver_order_channel._emit`), and that a claude host seat's order keeps exactly one.
- **Neutralization:** `plugins/superheroes/lib/round_orders.py` `render_order`, the gate
  `if context.get("host_seat") is True or phase == round_phases.P_SWEEP:` became
  `if True or context.get("host_seat") is True or phase == round_phases.P_SWEEP:` (every order gets the block).
- **Raw red:**
```
F
=================================== FAILURES ===================================
_ test_element_c_driver_emission_codex_seat_defers_and_claude_host_seat_keeps_its_one_contract _
...
        engine_order = orders[TROC.ENGINE_SEAT]
>       assert _heading_count(engine_order) == 0
E       assert 1 == 0
E        +  where 1 = _heading_count("You are reviewing pr for repo unknown, target unknown.\nReview session mode was not set in session metadata or driver... example in this order shows the payload's fields, not the envelope. Never write a landing file (read-only sandbox).\n")
/home/user/wt-2450/plugins/superheroes/lib/tests/test_one_result_contract_2450.py:164: AssertionError
FAILED plugins/superheroes/lib/tests/test_one_result_contract_2450.py::test_element_c_driver_emission_codex_seat_defers_and_claude_host_seat_keeps_its_one_contract
1 failed, 13 deselected in 2.55s
```
  (elided: the test body between the `...` markers, about 10 lines.)
- **Restore:** `if True or ` removed by the inverse edit.
- **Restore receipt:** `grep -n 'host_seat") is True or phase' round_orders.py` printed
  `641:        if context.get("host_seat") is True or phase == round_phases.P_SWEEP:`
- **Raw green:**
```
.                                                                        [100%]
1 passed, 13 deselected in 3.25s
```

## (d) healthy sibling at render level — `-k element_d`

- **Axis:** per phase, a host-seat render carries exactly one `## Payload contract`; a stdout-channel render
  carries none, except sweep (out of scope), which keeps exactly one.
- **Neutralization:** `plugins/superheroes/lib/round_orders.py` `render_order`, the gate lost its sweep clause:
  `if context.get("host_seat") is True or phase == round_phases.P_SWEEP:` became `if context.get("host_seat") is True:`
  (a stdout sweep order loses its block). The other seven phases passed under this neutralization, as they should.
- **Raw red:**
```
.......F
=================================== FAILURES ===================================
_______ test_element_d_render_contract_count_by_channel[dispatch-sweep] ________
...
        if phase == RP.P_SWEEP:
>           assert _heading_count(stdout) == 1
E           assert 0 == 1
E            +  where 0 = _heading_count('You are a searcher. You search a fixed list of files for one described mistake and report every\nplace that makes it....emit `{"hits": [...]}` as your final response with nothing after it. Never write a landing file (read-only sandbox).\n')
/home/user/wt-2450/plugins/superheroes/lib/tests/test_one_result_contract_2450.py:182: AssertionError
FAILED plugins/superheroes/lib/tests/test_one_result_contract_2450.py::test_element_d_render_contract_count_by_channel[dispatch-sweep]
1 failed, 7 passed, 6 deselected in 2.22s
```
  (elided: the test body between the `...` markers, about 8 lines.)
- **Restore:** `or phase == round_phases.P_SWEEP` re-added by the inverse edit.
- **Restore receipt:** the same `641:` line quoted under (c) (lines 639-645 of `round_orders.py` read back).
- **Raw green:**
```
........                                                                 [100%]
8 passed, 6 deselected in 1.97s
```

## (e) element (a) runs inside its own tmp_path — `-k element_a`

- **Axis:** every test that runs `ED.dispatch_review` writes its sanitized view and its dispatch journal only
  under that test's own `tmp_path`. The assertion reads both from the run: the view path from the `run-opened`
  record (`_review_opened_record(run_dir)["viewPath"]`) and the journal root from the run dir's
  `journal-root.txt`; both must sit under `os.path.realpath(tmp_path)`.
- **Neutralization:** in `test_one_result_contract_2450.py`, the line
  `from test_engine_dispatch import _pin_temp_base_to_tmp_path  # noqa: F401  autouse: keeps views and journals under tmp_path`
  was removed (the autouse fixture is then not active in the module).
- **Raw red** (`-x`, so only the first parametrization ran; the `tmp_path` and view path are this sandbox's):
```
F
=================================== FAILURES ===================================
_____ test_element_a_codex_fed_prompt_states_one_result_contract[findings] _____
...
        tmp_root = os.path.realpath(str(tmp_path)) + os.sep
>       assert os.path.realpath(opened["viewPath"]).startswith(tmp_root), opened["viewPath"]
E       AssertionError: /tmp/claude-0/superheroes-sanitized-view-1
E       assert False
E        +  where False = <built-in method startswith of str object at 0x7f773917fa50>('/tmp/claude-0/pytest-of-root/pytest-12/test_element_a_codex_fed_promp0/')
...
/home/user/wt-2450/plugins/superheroes/lib/tests/test_one_result_contract_2450.py:122: AssertionError
FAILED plugins/superheroes/lib/tests/test_one_result_contract_2450.py::test_element_a_codex_fed_prompt_states_one_result_contract[findings]
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 10 deselected in 6.70s
```
  (elided: the test body and the nested `where` lines, about 30 lines. The view landed in the shared system temp
  folder, which is the defect the assertion detects. The red run left that folder behind outside the repo.)
- **Restore:** the import line re-added by the inverse edit, directly above `import test_round_driver_order_channel as TROC`.
- **Restore receipt:** lines 23-28 of the test file read back:
  `from test_engine_dispatch import (` / `    ED, FakeRunner, _codex_seat, _fake_build_view, _repo, _review_opened_record, _valid_prompt,` / `)` /
  `from test_engine_dispatch import _pin_temp_base_to_tmp_path  # noqa: F401  autouse: keeps views and journals under tmp_path` /
  `import test_round_driver_order_channel as TROC`.
- **Raw green:**
```
....                                                                     [100%]
4 passed, 10 deselected in 4.78s
```
