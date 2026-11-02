# Lane pin WO-A (#2327) bite-proof: the local argv `--plugin-dir` pin, the local prompt's version line and the mismatch refusal

Bite-proof record for `plugins/superheroes/lib/launcher.py` (`compose_launch`, `lane_version_check`) and `plugins/superheroes/lib/engine_adapter.py` (`claude_builder_argv`). The detectors are in `plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py`.

**Status.** The implementer ran every proof (BP1 to BP3): each neutralization is a targeted Edit in the shipped `launcher.py`, the red is the whole new test file run alone, the restore is the inverse Edit, and the green is the same command. The red of BP1 below is the pytest output of the run, shortened as marked; the reds of BP2 and BP3 are the decisive lines of the run (the `>` source line, the `E` assertion line and the `FAILED` summary lines, selected with a line filter over the captured output, with the filter's line numbers kept), because each red fails five or eleven nodes and the full tracebacks repeat. The full capture of each red went to session scratch outside the repository and was read before this record was written; the lines quoted here are every line the filter kept, none edited. The greens are the complete pytest output. The `UV_NATIVE_TLS` deprecation warning that precedes every run is omitted. The absolute `tmp_path` prefixes and the worktree path are as printed. No fixture holds a real secret, so nothing is redacted.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py -q`, run from the worktree root.
- **Restore receipt, every element.** The restored line is quoted back from the shipped file after the inverse Edit.
- **Pinned condition.** The tests build the fake plugin root `A` and its manifest, the throwaway repository and the launch files under `tmp_path`; `launcher.plugin_root` is monkeypatched to `A` and the running version is passed as an argument or monkeypatched. The pin makes unobservable: the real plugin root, the real manifest version and the real `claude` binary (the argv is only composed, never spawned).

## Declared guarded-element set

BP1 the local argv `--plugin-dir <advisor plugin root>` pin (`launcher.py` `compose_launch`, the local `claude_builder_argv` call); BP2 the local prompt's `Advisor plugin version: <version>` line (plain and adopt formats); BP3 the mismatch refusal in `lane_version_check` (`launcher.py`, the comparison).

Not neutralized, and so unproven by a run in this record: the `compose-plugin-version-unreadable` refusal for a local lane (E1; tested by `test_an_unreadable_root_version_refuses_a_local_compose`), the no-line admission (E2), the duplicate-line rule (E3), the unreadable-running-version wording (E4), the unreadable launch file refusal (E5), the `engine_adapter.claude_builder_argv` `plugin_dir` append and its no-op for other values, and the `pluginRoot` / `pluginVersion` result keys. None is a declared element; the first five are covered by their own tests and the later ones by `test_claude_builder_argv_appends_*` and `_assert_pinned`.

### BP1: the local argv `--plugin-dir` pin. Axis: a local lane's argv starts the child on the advisor's own plugin root

- **Neutralization applied.** In `compose_launch`, `            token, session_id, prompt, plugin_dir=plugin_root(),` replaced with `            token, session_id, prompt,`, so the local argv carries no `--plugin-dir`.
- **Detector.** The whole new test file (the four local-compose nodes fail).
- **Red** (4 failed, 33 passed; the tracebacks of the first two failures are shown, the other two are the same assertion):

```
F.FFF................................                                    [100%]
=================================== FAILURES ===================================
_ test_a_local_workhorse_lane_starts_on_root_a_and_a_lane_running_version_b_is_refused _
...
>       _assert_pinned(composed, root_a, "9.1.0")

/home/user/wt-2327/plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py:68: 
...
    def _assert_pinned(composed, root, version):
        # axis: a composed local lane carries the pin on all three faces — argv, prompt and result
        assert composed["ok"] is True, composed
        argv = composed["argv"]
>       assert "--plugin-dir" in argv
E       AssertionError: assert '--plugin-dir' in ['claude', '--model', 'opus', '--session-id', '05d684cc-fbb9-4fec-a4d0-713f6c4002d4', '-p', ...]

/home/user/wt-2327/plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py:50: AssertionError
...
>       assert "--plugin-dir" in argv
E       AssertionError: assert '--plugin-dir' in ['claude', '--model', 'opus', '--session-id', '72f54aa7-94d9-4bfa-a1fb-21bf2000828c', '-p', ...]
...
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_a_local_workhorse_lane_starts_on_root_a_and_a_lane_running_version_b_is_refused
FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_a_local_adopt_lane_carries_the_same_pin
FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_a_local_detective_lane_carries_the_same_pin
FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_place_local_is_pinned_like_place_none
4 failed, 33 passed in 2.74s
```

- **Restore.** The inverse Edit; quoted from `launcher.py:1496`: `            token, session_id, prompt, plugin_dir=plugin_root(),`
- **Green.**

```
.....................................                                    [100%]
37 passed in 2.23s
```

### BP2: the local prompt's version line. Axis: a local prompt names the advisor's plugin version on its own line

- **Neutralization applied.** In `compose_launch`, the plain local format `"%s\n\n%s\n\n%s\n\n%s" % (cmd, issue_line, version_line, rulings_block)` replaced with `"%s\n\n%s\n\n%s" % (cmd, issue_line, rulings_block)`, and the adopt format `"%s\n\n%s\n\n%s\n%s\n%s\n\n%s" % (cmd, issue_line, version_line, adopts, base_line, rulings_block)` replaced with `"%s\n\n%s\n\n%s\n%s\n\n%s" % (cmd, issue_line, adopts, base_line, rulings_block)`.
- **Detector.** The whole new test file (five local-compose nodes fail).
- **Red** (5 failed, 32 passed; the line-filtered lines of the capture, numbered as in the capture):

```
16:>       _assert_pinned(composed, root_a, "9.1.0")
32:>       assert _version_lines(composed["prompt"]) == ["%s %s" % (VERSION_LABEL, version)]
33:E       AssertionError: assert [] == ['Advisor plu...rsion: 9.1.0']
35:E         Right contains one more item: 'Advisor plugin version: 9.1.0'
50:>       assert composed["prompt"] == "%s\n\nIssue: #656\n\nAdvisor plugin version: 9.1.0\n\n%s" % (
52:E       AssertionError: assert '/superheroes...is forbidden.' == '/superheroes...is forbidden.'
57:E         - 
58:E         - Advisor plugin version: 9.1.0
76:>       _assert_pinned(composed, root_a, "9.1.0")
92:>       assert _version_lines(composed["prompt"]) == ["%s %s" % (VERSION_LABEL, version)]
93:E       AssertionError: assert [] == ['Advisor plu...rsion: 9.1.0']
111:>       _assert_pinned(composed, root_a, "9.1.0")
127:>       assert _version_lines(composed["prompt"]) == ["%s %s" % (VERSION_LABEL, version)]
128:E       AssertionError: assert [] == ['Advisor plu...rsion: 9.1.0']
145:>       _assert_pinned(composed, root_a, "9.1.0")
161:>       assert _version_lines(composed["prompt"]) == ["%s %s" % (VERSION_LABEL, version)]
162:E       AssertionError: assert [] == ['Advisor plu...rsion: 9.1.0']
169:FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_a_local_workhorse_lane_starts_on_root_a_and_a_lane_running_version_b_is_refused
170:FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_the_prompt_places_the_version_line_directly_after_the_issue_line
171:FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_a_local_adopt_lane_carries_the_same_pin
172:FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_a_local_detective_lane_carries_the_same_pin
173:FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_place_local_is_pinned_like_place_none
174:5 failed, 32 passed in 2.47s
```

- **Restore.** The inverse Edits; quoted from `launcher.py:1464` and `launcher.py:1469`: `            cmd, issue_line, version_line, adopts, base_line, rulings_block,` and `        prompt = "%s\n\n%s\n\n%s\n\n%s" % (cmd, issue_line, version_line, rulings_block)`
- **Green.**

```
.....................................                                    [100%]
37 passed in 2.10s
```

### BP3: the mismatch refusal. Axis: a lane whose running plugin version differs from its launch's named version is refused naming both

- **Neutralization applied.** In `lane_version_check`, `    if running is not None and running == launched:` replaced with `    if True or (running is not None and running == launched):`, so every pinned launch is admitted.
- **Detector.** The whole new test file (eleven nodes fail: the DoD row, the adopt and detective rows, the disagreeing-lines row, the five unreadable-running-version rows, the omitted-running-version row and the CLI mismatch row).
- **Red** (11 failed, 26 passed; the line-filtered lines of the capture, numbered as in the capture):

```
19:>       assert refused["ok"] is False
20:E       assert True is False
39:>       assert L.lane_version_check(composed["prompt"], running_version="9.2.0")["ok"] is False
40:E       assert True is False
58:>       assert L.lane_version_check(composed["prompt"], running_version="9.2.0")["ok"] is False
59:E       assert True is False
68:>       assert got["ok"] is False and got["pinned"] is True
69:E       assert (True is False)
80:>       assert got["ok"] is False and got["pinned"] is True
81:E       assert (True is False)
92:>       assert got["ok"] is False and got["pinned"] is True
93:E       assert (True is False)
104:>       assert got["ok"] is False and got["pinned"] is True
105:E       assert (True is False)
116:>       assert got["ok"] is False and got["pinned"] is True
117:E       assert (True is False)
128:>       assert got["ok"] is False and got["pinned"] is True
129:E       assert (True is False)
140:>       assert L.lane_version_check("Advisor plugin version: 9.2.0")["ok"] is False
141:E       assert True is False
153:>       assert L.main(["lane-version", "--launch-file", _launch_file(tmp_path, "9.1.0")]) == 1
154:E       AssertionError: assert 0 == 1
162:FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_a_local_workhorse_lane_starts_on_root_a_and_a_lane_running_version_b_is_refused
163:FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_a_local_adopt_lane_carries_the_same_pin
164:FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_a_local_detective_lane_carries_the_same_pin
165:FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_two_disagreeing_version_lines_are_refused_with_no_launched_version
166:FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_an_unreadable_running_version_is_refused_naming_an_unreadable_version[None]
167:FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_an_unreadable_running_version_is_refused_naming_an_unreadable_version[]
168:FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_an_unreadable_running_version_is_refused_naming_an_unreadable_version[   ]
169:FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_an_unreadable_running_version_is_refused_naming_an_unreadable_version[9]
170:FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_an_unreadable_running_version_is_refused_naming_an_unreadable_version[running4]
171:FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_an_omitted_running_version_is_read_from_the_plugin_manifest
172:FAILED plugins/superheroes/lib/tests/test_lane_plugin_pin_2327.py::test_the_lane_version_verb_exits_1_on_a_mismatch_and_0_on_a_match
173:11 failed, 26 passed in 2.59s
```

- **Restore.** The inverse Edit; quoted from `launcher.py:1569`: `    if running is not None and running == launched:`
- **Green.**

```
.....................................                                    [100%]
37 passed in 2.23s
```
