# WO-1 (#2140) bite-proofs — the own-scripts approver hook (`plugins/superheroes/hooks/plugin_scripts_allow.py`)

Declared guarded-element set (from the order): G1 refused characters, G2 quote-aware expansion scan, G3 operator tokens, G4 program `python3` with at most one `-B`, G5 absolute / no `..` / plugin-root path, G6 `APPROVED_SCRIPTS` membership, G7 round_driver verb allowlist, G8 command-flag prefix refusal, G9 worktree guard's last word, G10 the hooks.json wiring position. One entry per element; no equivalence classes; no element unproven.

Every run used this command from `/home/user/wt-2140`, with the detector (both test files) unedited:

`scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py plugins/superheroes/lib/tests/test_hook_wiring.py -q --tb=line -p no:cacheprovider`

Baseline before any neutralization (the committed text): `157 passed in 1.25s`.

Each neutralization is one targeted Edit; each restore is the inverse Edit, with the neutralized lines read back after it. No git command was used. Captures are verbatim, each far under 32 KiB. No secrets, tokens, private URLs or PII appear; nothing was redacted. The captured outputs contain the absolute path `/home/user/wt-2140` as pytest printed it.

---

## G1 — refused characters (step 2)

**Guarded element:** `plugins/superheroes/hooks/plugin_scripts_allow.py:98` `if any(ch in _REFUSED_CHARS for ch in command): return None`. Axis: `# $ backtick \ newline CR NUL` anywhere in the command refuses, since each hides or adds a command from the token view.

**Neutralization:** line 98 `if any(ch in _REFUSED_CHARS for ch in command):` → `if False and any(ch in _REFUSED_CHARS for ch in command):`.

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................FF..FFFF........................ [ 45%]
...........................FFFFFFF...................................... [ 91%]
.............                                                            [100%]
=================================== FAILURES ===================================
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir `id`
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir `id`
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir $SESSION
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir $SESSION
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir a\ b
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir a\ b
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s\nrm -rf /tmp/x
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s\nrm -rf /tmp/x
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s\rrm -rf /tmp/x
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s\rrm -rf /tmp/x
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s\0
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s\0
E   AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat 'a\0b'
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:293: AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat 'a\0b'
E   AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat 'a\nb'
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:293: AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat 'a\nb'
E   AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat 'a\rb'
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:293: AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat 'a\rb'
E   AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat 'a#b'
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:293: AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat 'a#b'
E   AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat 'a$b'
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:293: AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat 'a$b'
E   AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat 'a\b'
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:293: AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat 'a\b'
E   AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat 'a`b'
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:293: AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat 'a`b'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir `id`]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir $SESSION]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir a\\ b]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s\\nrm -rf /tmp/x]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s\\rrm -rf /tmp/x]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s\\0]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_each_refused_character_alone_gets_no_decision[U+0000]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_each_refused_character_alone_gets_no_decision[U+000A]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_each_refused_character_alone_gets_no_decision[U+000D]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_each_refused_character_alone_gets_no_decision[U+0023]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_each_refused_character_alone_gets_no_decision[U+0024]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_each_refused_character_alone_gets_no_decision[U+005C]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_each_refused_character_alone_gets_no_decision[U+0060]
13 failed, 144 passed in 1.29s
```
Red on the claimed axis: the seven refused characters each pass through when the check is off (`test_each_refused_character_alone_gets_no_decision` U+0000, U+000A, U+000D, U+0023, U+0024, U+005C, U+0060, and the backtick, `$`, backslash, newline, CR and NUL rows of `test_everything_else_gets_no_decision`).

**Restore:** line 98 `if False and any(ch in _REFUSED_CHARS for ch in command):` → `if any(ch in _REFUSED_CHARS for ch in command):`.

**Restore receipt (lines 96-99 read back after the restore):**
```
    # 2. characters the tokenizer would hide from us (default shlex drops everything after `#`)
    # axis: `# $ backtick \ newline CR NUL` anywhere refuses — each hides or adds a command from the token view
    if any(ch in _REFUSED_CHARS for ch in command):
        return None
```

**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 45%]
........................................................................ [ 91%]
.............                                                            [100%]
157 passed in 1.27s
```

---

## G2 — quote-aware expansion scan (step 3)

**Guarded element:** `plugins/superheroes/hooks/plugin_scripts_allow.py:103` `if _unquoted_expansion(command): return None`. Axis: `{ } * ? [ ] ~` outside quotes (glob, brace, tilde) refuse, and they pass inside quotes.

**Neutralization:** line 103 `if _unquoted_expansion(command):` → `if False and _unquoted_expansion(command):`.

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
................................................FFFFF................... [ 45%]
.........................F........FFFFFFF............................... [ 91%]
.............                                                            [100%]
=================================== FAILURES ===================================
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/*
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/*
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir ~/x
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir ~/x
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s?
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s?
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/[ab]
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/[ab]
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/{a,b}
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/{a,b}
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --{verify-command,verify-command}=id
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --{verify-command,verify-command}=id
E   AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat a*b
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:307: AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat a*b
E   AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat a?b
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:307: AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat a?b
E   AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat a[b
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:307: AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat a[b
E   AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat a]b
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:307: AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat a]b
E   AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat a{b
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:307: AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat a{b
E   AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat a}b
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:307: AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat a}b
E   AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat a~b
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:307: AssertionError: python3 -B <root>/lib/dispatch_guard.py check --seat a~b
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/*]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir ~/x]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s?]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/[ab]]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/{a,b}]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --{verify-command,verify-command}=id]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_each_expansion_character_is_refused_unquoted_and_allowed_quoted[*]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_each_expansion_character_is_refused_unquoted_and_allowed_quoted[?]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_each_expansion_character_is_refused_unquoted_and_allowed_quoted[[]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_each_expansion_character_is_refused_unquoted_and_allowed_quoted[]]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_each_expansion_character_is_refused_unquoted_and_allowed_quoted[{]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_each_expansion_character_is_refused_unquoted_and_allowed_quoted[}]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_each_expansion_character_is_refused_unquoted_and_allowed_quoted[~]
13 failed, 144 passed in 1.33s
```
Red on the claimed axis: each of the seven expansion characters, unquoted, now gets approved (`test_each_expansion_character_is_refused_unquoted_and_allowed_quoted` for `*`, `?`, `[`, `]`, `{`, `}`, `~`, and the unquoted-glob, tilde, brace rows of `test_everything_else_gets_no_decision`). The three unbalanced-quote rows stay green under this neutralization: the scan's unbalanced-quote return is redundant with step 4, where shlex raises `ValueError` on an unclosed quote and `_approved_name` turns that into no decision. So the scan's "unbalanced quote" clause has no test that bites on it alone; the unbalanced-quote edge (E4) is held by the shlex path, which the same three rows exercise.

**Restore:** line 103 `if False and _unquoted_expansion(command):` → `if _unquoted_expansion(command):`.

**Restore receipt (lines 101-104 read back after the restore):**
```
    # 3. quote-aware expansion scan: Bash expands these outside quotes, the token view does not show it
    # axis: `{ } * ? [ ] ~` outside quotes (glob, brace, tilde) and an unbalanced quote refuse; inside quotes they pass
    if _unquoted_expansion(command):
        return None
```

**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 45%]
........................................................................ [ 91%]
.............                                                            [100%]
157 passed in 1.27s
```

---

## G3 — operator tokens (step 4)

**Guarded element:** `plugins/superheroes/hooks/plugin_scripts_allow.py:113` `if any(_is_operator(t) for t in tokens): return None`. Axis: any operator token (`;` `&&` `||` `|` `&` `<` `>` `>>` `2>&1`) refuses, with no redirect exception.

**Neutralization:** line 113 `if any(_is_operator(t) for t in tokens):` → `if False and any(_is_operator(t) for t in tokens):`.

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.............................FFFFFFFFF.................................. [ 45%]
...............................................................F........ [ 91%]
.............                                                            [100%]
=================================== FAILURES ===================================
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s ; rm -rf /tmp/x
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s ; rm -rf /tmp/x
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s && echo x
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s && echo x
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s || echo x
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s || echo x
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s | cat
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s | cat
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s &
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s &
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s > /tmp/out
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s > /tmp/out
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s >> /tmp/out
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s >> /tmp/out
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s < /tmp/in
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s < /tmp/in
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s 2>&1
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s 2>&1
E   assert '{"hookSpecif...iver.py)"}}\n' == ''
      
      + {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow", "permissionDecisionReason": "superheroes: this plugin's own review-loop or build helper script (lib/round_driver.py)"}}
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:450: assert '{"hookSpecif...iver.py)"}}\n' == ''
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s ; rm -rf /tmp/x]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s && echo x]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s || echo x]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s | cat]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s &]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s > /tmp/out]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s >> /tmp/out]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s < /tmp/in]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s 2>&1]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_process_no_decision_row_prints_nothing[python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py next --session-dir /tmp/s ; rm -rf /tmp/x]
10 failed, 147 passed in 1.31s
```
Red on the claimed axis: `;`, `&&`, `||`, `|`, `&`, `>`, `>>`, `<` and `2>&1` each get approved, and the real hook process prints an allow line for the `;` compound. The `( … )` subshell row stays green under this neutralization: its first token `(` is not `python3`, so G4 refuses it. That row is held by G4, not G3.

**Restore:** line 113 `if False and any(_is_operator(t) for t in tokens):` → `if any(_is_operator(t) for t in tokens):`.

**Restore receipt (lines 112-114 read back after the restore):**
```
    # axis: any operator token (`;` `&&` `||` `|` `&` `<` `>` …) refuses — no redirect exception here
    if any(_is_operator(t) for t in tokens):
        return None
```

**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 45%]
........................................................................ [ 91%]
.............                                                            [100%]
157 passed in 1.24s
```

---

## G4 — program `python3`, at most one `-B` (step 5)

**Guarded element:** `plugins/superheroes/hooks/plugin_scripts_allow.py:118-122` `if not tokens or tokens[0] != "python3": return None`, then `i = 1`, then skip at most one `-B`. Axis: the program is bare `python3` with at most one `-B`; any other program or a second `-B` refuses.

**Neutralization:** lines 118-122 changed in one Edit, dropping the program-name check and letting any number of `-`-prefixed tokens be skipped:
```
    if not tokens or tokens[0] != "python3":      →    if not tokens:
        return None                                       return None
    i = 1                                                 i = 1
    if i < len(tokens) and tokens[i] == "-B":     →    while i < len(tokens) and tokens[i].startswith("-"):
        i += 1                                            i += 1
```

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...................................................................FFFF. [ 45%]
....F................................................................... [ 91%]
.............                                                            [100%]
=================================== FAILURES ===================================
E   AssertionError: python -B <root>/lib/round_driver.py next --session-dir /tmp/s
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python -B <root>/lib/round_driver.py next --session-dir /tmp/s
E   AssertionError: bash <root>/lib/round_driver.py next --session-dir /tmp/s
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: bash <root>/lib/round_driver.py next --session-dir /tmp/s
E   AssertionError: node <root>/lib/round_driver.py next --session-dir /tmp/s
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: node <root>/lib/round_driver.py next --session-dir /tmp/s
E   AssertionError: /usr/bin/python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: /usr/bin/python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s
E   AssertionError: python3 -B -B <root>/lib/round_driver.py next --session-dir /tmp/s
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B -B <root>/lib/round_driver.py next --session-dir /tmp/s
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python -B <root>/lib/round_driver.py next --session-dir /tmp/s]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[bash <root>/lib/round_driver.py next --session-dir /tmp/s]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[node <root>/lib/round_driver.py next --session-dir /tmp/s]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[/usr/bin/python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B -B <root>/lib/round_driver.py next --session-dir /tmp/s]
5 failed, 152 passed in 1.34s
```
Red on the claimed axis: `python`, `bash`, `node`, an absolute `/usr/bin/python3` and `-B -B` each get approved. Rows that stay green under this neutralization, and why: `env python3 …` and `FOO=1 python3 …` (the token after the skipped flags is `python3`, a non-absolute script path, refused by G5), `python3 -c 'print(1)'`, `python3 -m pytest` and `python3 -B -X x …` (the script candidate is `print(1)`, `pytest` or `x`, none absolute, refused by G5), and the `python3` / `python3 -B` only rows (no script token, refused at the `i >= len(tokens)` check). Those rows are held by G5 and that check when G4 is removed; the program name and a doubled `-B` are the parts only G4 holds.

**Restore:** the inverse Edit, putting back the original four lines.

**Restore receipt (lines 116-122 read back after the restore):**
```
    # 5. bare `python3`, at most one `-B`
    # axis: the program is bare `python3` with at most one `-B`; any other program or interpreter flag refuses
    if not tokens or tokens[0] != "python3":
        return None
    i = 1
    if i < len(tokens) and tokens[i] == "-B":
        i += 1
```

**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 45%]
........................................................................ [ 91%]
.............                                                            [100%]
157 passed in 1.34s
```

---

## G5 — absolute, no `..`, plugin-root path (step 6, path half)

**Guarded element:** `plugins/superheroes/hooks/plugin_scripts_allow.py:130-137` the `isabs` / `..` refusal and the loop that sets `name` only when the script's directory is a plugin root's `lib`. Axis: the script path is absolute, has no `..` segment, and normalizes to exactly `<plugin root>/lib/<name>`.

**Neutralization:** lines 130-137 replaced in one Edit by the two lines `normalized = os.path.normpath(script)` and `name = os.path.basename(normalized)`, so any path's basename is taken as the name and `APPROVED_SCRIPTS` (G6) still applies.

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................FFFFFF.......... [ 45%]
...........................................................FF...F....... [ 91%]
.............                                                            [100%]
=================================== FAILURES ===================================
E   AssertionError: python3 -B /tmp/other/plugin/lib/round_driver.py next --session-dir /tmp/s
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B /tmp/other/plugin/lib/round_driver.py next --session-dir /tmp/s
E   AssertionError: python3 -B /tmp/other/plugin/lib/dispatch_guard.py check
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B /tmp/other/plugin/lib/dispatch_guard.py check
E   AssertionError: python3 -B <root>/lib/../lib/round_driver.py next --session-dir /tmp/s
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/../lib/round_driver.py next --session-dir /tmp/s
E   AssertionError: python3 -B <root>/../x/lib/round_driver.py next --session-dir /tmp/s
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/../x/lib/round_driver.py next --session-dir /tmp/s
E   AssertionError: python3 -B lib/round_driver.py next --session-dir /tmp/s
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B lib/round_driver.py next --session-dir /tmp/s
E   AssertionError: python3 -B <root>/lib/tests/round_driver.py next --session-dir /tmp/s
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/tests/round_driver.py next --session-dir /tmp/s
E   AssertionError: assert True is False
     +  where True = _decide({'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /tmp/claude-0/pytest-of-root/pytest-13/test_plugin_root_from_environm0/lib/round_driver.py next --session-dir /tmp/s'}}, {})
     +    where {'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /tmp/claude-0/pytest-of-root/pytest-13/test_plugin_root_from_environm0/lib/round_driver.py next --session-dir /tmp/s'}} = _payload('python3 -B /tmp/claude-0/pytest-of-root/pytest-13/test_plugin_root_from_environm0/lib/round_driver.py next --session-dir /tmp/s')
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:405: AssertionError: assert True is False
E   AssertionError: assert True is False
     +  where True = _decide({'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /tmp/claude-0/pytest-of-root/pytest-13/test_relative_plugin_root_in_e0/some/relative/root/lib/round_driver.py next --session-dir /tmp/s'}}, {'CLAUDE_PLUGIN_ROOT': 'some/relative/root'})
     +    where {'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /tmp/claude-0/pytest-of-root/pytest-13/test_relative_plugin_root_in_e0/some/relative/root/lib/round_driver.py next --session-dir /tmp/s'}} = _payload('python3 -B /tmp/claude-0/pytest-of-root/pytest-13/test_relative_plugin_root_in_e0/some/relative/root/lib/round_driver.py next --session-dir /tmp/s')
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:418: AssertionError: assert True is False
E   assert '{"hookSpecif...iver.py)"}}\n' == ''
      
      + {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow", "permissionDecisionReason": "superheroes: this plugin's own review-loop or build helper script (lib/round_driver.py)"}}
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:450: assert '{"hookSpecif...iver.py)"}}\n' == ''
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B /tmp/other/plugin/lib/round_driver.py next --session-dir /tmp/s]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B /tmp/other/plugin/lib/dispatch_guard.py check]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/../lib/round_driver.py next --session-dir /tmp/s]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/../x/lib/round_driver.py next --session-dir /tmp/s]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B lib/round_driver.py next --session-dir /tmp/s]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/tests/round_driver.py next --session-dir /tmp/s]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_plugin_root_from_environment_is_allowed
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_relative_plugin_root_in_environment_is_ignored
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_process_no_decision_row_prints_nothing[python3 -B /tmp/other/plugin/lib/round_driver.py next --session-dir /tmp/s]
9 failed, 148 passed in 1.41s
```
Red on the claimed axis: another root's `lib` (two rows plus the process row), a `..` that normalizes back into `lib`, a `..` that climbs to another `lib`, a relative path, a nested `lib/tests/` path, and both environment-root tests (the one that checks a root missing from the environment is another root's script, and the one that checks a relative `CLAUDE_PLUGIN_ROOT` is ignored). The session's pytest temporary directory path appears in two captured lines; it holds no secret and was not redacted.

**Restore:** the inverse Edit, putting back lines 130-137.

**Restore receipt (lines 124-140 read back after the restore):**
```
    # 6. the script is one of this plugin's own approved lib scripts, by absolute path
    if i >= len(tokens):
        return None
    script = tokens[i]
    rest = tokens[i + 1:]
    # axis: the script path is absolute, has no `..` segment, and normalizes to a plugin root's lib/<name>
    if not os.path.isabs(script) or ".." in script.split("/"):
        return None
    normalized = os.path.normpath(script)
    name = None
    for root in roots:
        if os.path.dirname(normalized) == os.path.normpath(os.path.join(root, "lib")):
            name = os.path.basename(normalized)
            break
    # axis: the name is on APPROVED_SCRIPTS — an unlisted plugin script gets no decision
    if name not in APPROVED_SCRIPTS:
        return None
```

**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 45%]
........................................................................ [ 91%]
.............                                                            [100%]
157 passed in 1.33s
```

---

## G6 — `APPROVED_SCRIPTS` membership (step 6, list half)

**Guarded element:** `plugins/superheroes/hooks/plugin_scripts_allow.py:139` `if name not in APPROVED_SCRIPTS: return None`. Axis: only a script on the ten-name list gets a decision; any other script under the plugin's own `lib` does not.

**Neutralization:** line 139 `if name not in APPROVED_SCRIPTS:` → `if name is None:`. The path half (G5) stays in place.

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..............................................................FFFFF..... [ 45%]
...........................................................F.....F...... [ 91%]
.............                                                            [100%]
=================================== FAILURES ===================================
E   AssertionError: python3 -B <root>/lib/engine_dispatch.py check
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/engine_dispatch.py check
E   AssertionError: python3 -B <root>/lib/seat_map.py check
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/seat_map.py check
E   AssertionError: python3 -B <root>/lib/build_lane.py check
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/build_lane.py check
E   AssertionError: python3 -B <root>/lib/cloud_builder.py check
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/cloud_builder.py check
E   AssertionError: python3 -B <root>/lib/review_record.py check
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/review_record.py check
E   AssertionError: assert True is False
     +  where True = _decide({'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /tmp/claude-0/pytest-of-root/pytest-15/test_plugin_root_from_environm0/lib/engine_dispatch.py check'}}, {'CLAUDE_PLUGIN_ROOT': '/tmp/claude-0/pytest-of-root/pytest-15/test_plugin_root_from_environm0'})
     +    where {'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /tmp/claude-0/pytest-of-root/pytest-15/test_plugin_root_from_environm0/lib/engine_dispatch.py check'}} = _payload('python3 -B /tmp/claude-0/pytest-of-root/pytest-15/test_plugin_root_from_environm0/lib/engine_dispatch.py check')
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:410: AssertionError: assert True is False
E   assert '{"hookSpecif...atch.py)"}}\n' == ''
      
      + {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow", "permissionDecisionReason": "superheroes: this plugin's own review-loop or build helper script (lib/engine_dispatch.py)"}}
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:450: assert '{"hookSpecif...atch.py)"}}\n' == ''
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/engine_dispatch.py check]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/seat_map.py check]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/build_lane.py check]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/cloud_builder.py check]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/review_record.py check]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_plugin_root_from_environment_is_allowed
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_process_no_decision_row_prints_nothing[python3 -B /home/user/wt-2140/plugins/superheroes/lib/engine_dispatch.py check]
7 failed, 150 passed in 1.35s
```
Red on the claimed axis: `engine_dispatch.py`, `seat_map.py`, `build_lane.py`, `cloud_builder.py` and `review_record.py` under the plugin's own `lib` each get approved, as does an unlisted name under an environment root, and the real hook process prints an allow line for `engine_dispatch.py`. The session's pytest temporary directory path appears in two captured lines; it holds no secret and was not redacted.

**Restore:** line 139 `if name is None:` → `if name not in APPROVED_SCRIPTS:`.

**Restore receipt (lines 138-140 read back after the restore):**
```
    # axis: the name is on APPROVED_SCRIPTS — an unlisted plugin script gets no decision
    if name not in APPROVED_SCRIPTS:
        return None
```

**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 45%]
........................................................................ [ 91%]
.............                                                            [100%]
157 passed in 1.39s
```

---

## G7 — round_driver verb allowlist (step 7, verb check)

**Guarded element:** `plugins/superheroes/hooks/plugin_scripts_allow.py:145` `if not rest or rest[0] not in ROUND_DRIVER_VERBS: return None`. Axis: the first token after `round_driver.py` is one of the eight allowed verbs; `run-verify`, `rule`, `--help`, an option before the verb, an unknown verb refuse.

**Neutralization:** line 145 `if not rest or rest[0] not in ROUND_DRIVER_VERBS:` → `if not rest:`. The no-token refusal (E8) stays in place; only the verb membership is removed.

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 45%]
.........FFF.FF......................................F............F..... [ 91%]
.............                                                            [100%]
=================================== FAILURES ===================================
E   AssertionError: python3 -B <root>/lib/round_driver.py run-verify --session-dir /tmp/s
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py run-verify --session-dir /tmp/s
E   AssertionError: python3 -B <root>/lib/round_driver.py rule --session-dir /tmp/s --ruling-file /tmp/r --by x
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py rule --session-dir /tmp/s --ruling-file /tmp/r --by x
E   AssertionError: python3 -B <root>/lib/round_driver.py --help
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py --help
E   AssertionError: python3 -B <root>/lib/round_driver.py --session-dir /tmp/s next
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py --session-dir /tmp/s next
E   AssertionError: python3 -B <root>/lib/round_driver.py nuke --session-dir /tmp/s
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py nuke --session-dir /tmp/s
E   AssertionError: assert True is False
     +  where True = _decide({'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py run-verify --session-dir /tmp/claude-0/pytest-of-root/pytest-17/test_run_verify_gets_no_decisi0'}})
     +    where {'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py run-verify --session-dir /tmp/claude-0/pytest-of-root/pytest-17/test_run_verify_gets_no_decisi0'}} = _payload('python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py run-verify --session-dir /tmp/claude-0/pytest-of-root/pytest-17/test_run_verify_gets_no_decisi0')
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:342: AssertionError: assert True is False
E   assert '{"hookSpecif...iver.py)"}}\n' == ''
      
      + {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow", "permissionDecisionReason": "superheroes: this plugin's own review-loop or build helper script (lib/round_driver.py)"}}
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:450: assert '{"hookSpecif...iver.py)"}}\n' == ''
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py run-verify --session-dir /tmp/s]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py rule --session-dir /tmp/s --ruling-file /tmp/r --by x]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py --help]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py --session-dir /tmp/s next]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py nuke --session-dir /tmp/s]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_run_verify_gets_no_decision_whatever_the_session_state_holds
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_process_no_decision_row_prints_nothing[python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py run-verify --session-dir /tmp/s]
7 failed, 150 passed in 1.41s
```
Red on the claimed axis: `run-verify`, `rule`, `--help`, an option before the verb and an unknown verb each get approved, and so does `run-verify` through the real hook process and through the F2 session-state test. The bare `round_driver.py` row (E8) stays green, as designed: the neutralization keeps the `not rest` refusal. The session's pytest temporary directory path appears in two captured lines; it holds no secret and was not redacted.

**Restore:** line 145 `if not rest:` → `if not rest or rest[0] not in ROUND_DRIVER_VERBS:`.

**Restore receipt (lines 142-145 read back after the restore; the read ended at line 145, so the `return None` below it is not in this quote):**
```
    # 7. the round driver: one of the eight verbs, and no flag that hands it a command line
    if name == "round_driver.py":
        # axis: the first token after the driver is an allowed verb (`run-verify`, `rule`, `--help`, an option, nothing refuse)
        if not rest or rest[0] not in ROUND_DRIVER_VERBS:
```

**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 45%]
........................................................................ [ 91%]
.............                                                            [100%]
157 passed in 1.29s
```

---

## G8 — command-flag prefix refusal (step 7, flag loop)

**Guarded element:** `plugins/superheroes/hooks/plugin_scripts_allow.py:152-155` the flag loop's `if stem and any(flag.startswith(stem) for flag in COMMAND_FLAGS): return None`. Axis: `--verify-command` and `--break-it-interpreter` refuse in full, with `=value`, and as any argparse prefix abbreviation.

**Neutralization:** line 154 `if stem and any(flag.startswith(stem) for flag in COMMAND_FLAGS):` → `if stem and any(flag == stem for flag in COMMAND_FLAGS):`, so only a spelled-out flag name still refuses and a prefix abbreviation no longer does.

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 45%]
..................FFF.FF................................................ [ 91%]
.............                                                            [100%]
=================================== FAILURES ===================================
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --verify-c x
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --verify-c x
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --verify x
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --verify x
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --v x
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --v x
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --break-it-i=x
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --break-it-i=x
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --br x
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --br x
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --verify-c x]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --verify x]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --v x]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --break-it-i=x]
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --br x]
5 failed, 152 passed in 1.34s
```
Red on the claimed axis: `--verify-c`, `--verify`, `--v`, `--break-it-i=x` and `--br` each get approved. The rows for the full spellings (`--verify-command`, `--verify-command=none`, a quoted flag, `--break-it-interpreter`, the `submit` verb row and the brace-expansion row) stay green, as designed, because the exact-match neutralization still refuses them. The loop's other check, the bare `--` refusal (lines 148-150), is a separate branch this proof did not neutralize: no element in the declared set names it, so it is not proven by this entry.

**Restore:** line 154 `flag == stem` → `flag.startswith(stem)`.

**Restore receipt (lines 147-155 read back after the restore):**
```
        for t in rest[1:]:
            # axis: `--` ends option parsing and is refused
            if t == "--":
                return None
            # axis: `--verify-command` / `--break-it-interpreter`, in full or as an argparse prefix abbreviation, refuse
            if t.startswith("--"):
                stem = t[2:].split("=", 1)[0]
                if stem and any(flag.startswith(stem) for flag in COMMAND_FLAGS):
                    return None
```

**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 45%]
........................................................................ [ 91%]
.............                                                            [100%]
157 passed in 1.38s
```

---

## G9 — worktree guard's last word (step 8)

**Guarded element:** `plugins/superheroes/hooks/plugin_scripts_allow.py:161` `if decision == "deny": return None`. Axis: an otherwise-approved command gets no decision when the worktree guard's classifier says `deny`. The real denied shape is `test_classifier_deny_wins_on_a_real_destructive_git_mention` (a destructive `git reset --hard` mention in an approved call's arguments, which the real classifier denies on a calibrated project).

**Neutralization:** line 161 `if decision == "deny":` → `if False and decision == "deny":`.

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 45%]
......................................................FF................ [ 91%]
.............                                                            [100%]
=================================== FAILURES ===================================
E   AssertionError: assert True is False
     +  where True = _decide({'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py next --session-dir /tmp/s git reset --hard'}, 'cwd': '/tmp'})
     +    where {'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py next --session-dir /tmp/s git reset --hard'}, 'cwd': '/tmp'} = _payload('python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py next --session-dir /tmp/s git reset --hard', cwd='/tmp')
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:359: AssertionError: assert True is False
E   AssertionError: assert True is False
     +  where True = _decide({'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py next --session-dir /tmp/s'}})
     +    where {'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py next --session-dir /tmp/s'}} = _payload('python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py next --session-dir /tmp/s')
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:366: AssertionError: assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_classifier_deny_wins_on_a_real_destructive_git_mention
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_classifier_deny_wins
2 failed, 155 passed in 1.34s
```
Red on the claimed axis: with the check off, the real denied shape (`git reset --hard` after an approved call, line 359) and the stubbed `("deny", "x")` classifier (line 366) are both approved.

**Restore:** line 161 `if False and decision == "deny":` → `if decision == "deny":`.

**Restore receipt (lines 157-163 read back after the restore):**
```
    # 8. the worktree guard's classifier has the last word
    # axis: an otherwise-approved command is refused when the worktree guard says deny
    import worktree_guard
    decision, _ = worktree_guard.classify(command, payload.get("cwd"))
    if decision == "deny":
        return None
    return name
```

**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 45%]
........................................................................ [ 91%]
.............                                                            [100%]
157 passed in 1.29s
```

---

## G10 — the hooks.json wiring position (`test_hook_wiring.py` chain test)

**Guarded element:** `plugins/superheroes/hooks/hooks.json:10-11` the Bash `PreToolUse` chain's order: `plugin_scripts_allow.py` is the fourth hook, directly after `iphone_allow.py`, before `implementer_fence.py`. Axis: the Bash chain is exactly five hooks in the order guard, timeout, iPhone approver, own-scripts approver, native fence. The detector is `test_bash_pretooluse_chain_is_exactly_guard_timeout_iphone_scripts_then_fence`.

**Neutralization:** in `hooks.json`, lines 10 and 11 swapped, so `plugin_scripts_allow.py` sits at index 2 and `iphone_allow.py` at index 3.

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 45%]
........................................................................ [ 91%]
........F....                                                            [100%]
=================================== FAILURES ===================================
E   AssertionError: hook 2 must be iphone_allow.py, got 'python3 -B "${CLAUDE_PLUGIN_ROOT}/hooks/plugin_scripts_allow.py" || true'
    assert 'iphone_allow.py' in 'python3 -B "${CLAUDE_PLUGIN_ROOT}/hooks/plugin_scripts_allow.py" || true'
/home/user/wt-2140/plugins/superheroes/lib/tests/test_hook_wiring.py:113: AssertionError: hook 2 must be iphone_allow.py, got 'python3 -B "${CLAUDE_PLUGIN_ROOT}/hooks/plugin_scripts_allow.py" || true'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_hook_wiring.py::test_bash_pretooluse_chain_is_exactly_guard_timeout_iphone_scripts_then_fence
1 failed, 156 passed in 1.21s
```
Red on the claimed axis: the order assertion at `test_hook_wiring.py:113` fires. The sibling `test_plugin_scripts_allow_hook_is_wired_fail_soft_after_worktree_guard` stays green, as it should: it checks only that the approver is after the worktree guard and fail-soft, and the swap keeps both true. The chain test alone holds the position among the approvers.

**Restore:** the inverse Edit, swapping lines 10 and 11 back.

**Restore receipt (lines 8-12 read back after the restore; line 8 is the worktree-guard entry, quoted in full by the read and abbreviated here with `…`):**
```
          { "type": "command", "command": "python3 -B \"${CLAUDE_PLUGIN_ROOT}/hooks/worktree_guard_gate.py\" || printf '{…}'" },
          { "type": "command", "command": "python3 -B \"${CLAUDE_PLUGIN_ROOT}/hooks/bash_timeout.py\" || true" },
          { "type": "command", "command": "python3 -B \"${CLAUDE_PLUGIN_ROOT}/hooks/iphone_allow.py\" || true" },
          { "type": "command", "command": "python3 -B \"${CLAUDE_PLUGIN_ROOT}/hooks/plugin_scripts_allow.py\" || true" },
          { "type": "command", "command": "python3 -B \"${CLAUDE_PLUGIN_ROOT}/hooks/implementer_fence.py\" || true" }
```

**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 45%]
........................................................................ [ 91%]
.............                                                            [100%]
157 passed in 1.24s
```

---

## G8 supplement — the bare `--` branch of the flag loop (extra, not in the declared set)

The G8 entry above disclosed that its neutralization did not touch the loop's bare `--` refusal. A spare run proves it, so it is recorded here as a supplement, not as an eleventh element.

**Guarded element:** `plugins/superheroes/hooks/plugin_scripts_allow.py:149` `if t == "--": return None`. Axis: a bare `--` after the verb ends option parsing and refuses.

**Neutralization:** line 149 `if t == "--":` → `if False and t == "--":`.

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 45%]
..........................F............................................. [ 91%]
.............                                                            [100%]
=================================== FAILURES ===================================
E   AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:275: AssertionError: python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/round_driver.py next --session-dir /tmp/s --]
1 failed, 156 passed in 1.25s
```

**Restore:** line 149 `if False and t == "--":` → `if t == "--":`.

**Restore receipt (lines 147-150 read back after the restore):**
```
        for t in rest[1:]:
            # axis: `--` ends option parsing and is refused
            if t == "--":
                return None
```

**Raw green (this is the final run of the dispatch, after every restore):**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 45%]
........................................................................ [ 91%]
.............                                                            [100%]
157 passed in 1.32s
```

---

## G6′ — review_result.py exclusion (WO-2)

**Guarded element:** `plugins/superheroes/hooks/plugin_scripts_allow.py` `APPROVED_SCRIPTS` membership (lines 39-43) — the exclusion of `review_result.py`. Axis: a script that replaces a caller-named path gets no decision. Detector: the new row `python3 -B <root>/lib/review_result.py write --path /tmp/x --action halt --round 1` in `_NO_DECISION_ROWS` of `test_plugin_scripts_allow_hook.py`, which `test_everything_else_gets_no_decision` asserts is False (the pinned-list test `test_the_lists_are_pinned` goes red too).

**Neutralization:** in `APPROVED_SCRIPTS`, `"grounding_stage.py",` → `"grounding_stage.py", "review_result.py",` (one Edit).

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F.................................................................F..... [ 45%]
........................................................................ [ 91%]
.............                                                            [100%]
=================================== FAILURES ===================================
E   AssertionError: assert frozenset({'b...int.py', ...}) == frozenset({'b...int.py', ...})
      
      Extra items in the left set:
      'review_result.py'
      Use -v to get more diff
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:76: AssertionError: assert frozenset({'b...int.py', ...}) == frozenset({'b...int.py', ...})
E   AssertionError: python3 -B <root>/lib/review_result.py write --path /tmp/x --action halt --round 1
    assert True is False
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:277: AssertionError: python3 -B <root>/lib/review_result.py write --path /tmp/x --action halt --round 1
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_the_lists_are_pinned
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_everything_else_gets_no_decision[python3 -B <root>/lib/review_result.py write --path /tmp/x --action halt --round 1]
2 failed, 155 passed in 1.12s
```

**Restore:** the inverse Edit, `"grounding_stage.py", "review_result.py",` → `"grounding_stage.py",`.

**Restore receipt (lines 39-42 read back after the restore):**
```
APPROVED_SCRIPTS = frozenset((
    "round_driver.py", "break_it.py", "review_store.py", "grounding_stage.py",
    "mode_reconcile.py", "calibration_resolve.py", "size_count.py", "order_lint.py",
    "dispatch_guard.py",
```

**Raw green (after the restore):**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 45%]
........................................................................ [ 91%]
.............                                                            [100%]
157 passed in 1.18s
```

---

## G10′ — exact hook invocation (WO-3)

**Guarded element:** `plugins/superheroes/lib/tests/test_hook_wiring.py` `test_plugin_scripts_allow_hook_is_wired_fail_soft_after_worktree_guard`, the assertion `approver == [_PLUGIN_SCRIPTS_ALLOW_COMMAND]`. Axis: the whole own-scripts approver invocation is pinned — the interpreter, the plugin-root path and fail-soft; a command that lost `python3 -B ` (the hook file is mode 100644, so it cannot run directly, and `|| true` would swallow the launch failure) goes red.

This entry runs only `test_hook_wiring.py`, the one file WO-3 changes, with this command from `/home/user/wt-2140`:

`scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_hook_wiring.py -q --tb=line -p no:cacheprovider`

Baseline before the neutralization (the new assertion in place, hooks.json committed text): `10 passed in 0.16s`.

**Neutralization:** in `plugins/superheroes/hooks/hooks.json` line 11, the `plugin_scripts_allow.py` entry's command loses `python3 -B ` (one Edit): `python3 -B \"${CLAUDE_PLUGIN_ROOT}/hooks/plugin_scripts_allow.py\"` → `\"${CLAUDE_PLUGIN_ROOT}/hooks/plugin_scripts_allow.py\"`.

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
....F.....                                                               [100%]
=================================== FAILURES ===================================
E   assert ['"${CLAUDE_P....py" || true'] == ['python3 -B ....py" || true']
      
      At index 0 diff: '"${CLAUDE_PLUGIN_ROOT}/hooks/plugin_scripts_allow.py" || true' != 'python3 -B "${CLAUDE_PLUGIN_ROOT}/hooks/plugin_scripts_allow.py" || true'
      Use -v to get more diff
/home/user/wt-2140/plugins/superheroes/lib/tests/test_hook_wiring.py:87: assert ['"${CLAUDE_P....py" || true'] == ['python3 -B ....py" || true']
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_hook_wiring.py::test_plugin_scripts_allow_hook_is_wired_fail_soft_after_worktree_guard
1 failed, 9 passed in 0.16s
```
Red on the claimed axis: the exact-invocation assertion fires at `test_hook_wiring.py:87`. The old `assert "|| true" in approver[0]` would have stayed green here, since `|| true` is still present.

**Restore:** the inverse Edit, putting `python3 -B ` back.

**Restore receipt (hooks.json lines 9-12 read back after the restore):**
```
          { "type": "command", "command": "python3 -B \"${CLAUDE_PLUGIN_ROOT}/hooks/bash_timeout.py\" || true" },
          { "type": "command", "command": "python3 -B \"${CLAUDE_PLUGIN_ROOT}/hooks/iphone_allow.py\" || true" },
          { "type": "command", "command": "python3 -B \"${CLAUDE_PLUGIN_ROOT}/hooks/plugin_scripts_allow.py\" || true" },
          { "type": "command", "command": "python3 -B \"${CLAUDE_PLUGIN_ROOT}/hooks/implementer_fence.py\" || true" }
```

**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..........                                                               [100%]
10 passed in 0.18s
```

Edges not neutralized in this proof: a command missing `|| true` and a duplicate wiring of the hook. Both fail the same equality by construction (the string differs, or the list has two elements), but only the missing-`python3 -B ` edge was run red.

---

## G11 — the session-state stamp check (WO-4)

**Guarded element:** `plugins/superheroes/hooks/plugin_scripts_allow.py:127` in `_session_state_is_drivers`, the comparison `return mirror["stateSha256"] == hashlib.sha256(state_bytes).hexdigest()`. Axis: a driver call whose saved `loop-state.json` does not hash to the `stateSha256` stamped in `loop-state.mirror.json` gets no decision.

Command (the order's, from `/home/user/wt-2140`, both test files unedited): `scripts/pinned-python -B -X pycache_prefix=/home/user/wt-2140/docs/pyc-wo4 -m pytest plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py plugins/superheroes/lib/tests/test_hook_wiring.py -q --tb=line -p no:cacheprovider`

Baseline before the neutralization (WO-4b edits in place): `183 passed in 1.43s`.

**Neutralization:** line 127 `return mirror["stateSha256"] == hashlib.sha256(state_bytes).hexdigest()` → `return mirror["stateSha256"] == mirror["stateSha256"]` (one Edit), so the comparison is always true for any readable mirror holding a string stamp.

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 39%]
.........................................................F.F............ [ 78%]
.FF....F...............................                                  [100%]
=================================== FAILURES ===================================
E   AssertionError: assert True is False
     +  where True = _decide({'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py next --session-dir /tmp/claude-0/pytest-of-root/pytest-36/test_run_verify_gets_no_decisi0/session'}})
     +    where {'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py next --session-dir /tmp/claude-0/pytest-of-root/pytest-36/test_run_verify_gets_no_decisi0/session'}} = _payload('python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py next --session-dir /tmp/claude-0/pytest-of-root/pytest-36/test_run_verify_gets_no_decisi0/session')
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:369: AssertionError: assert True is False
E   AssertionError: assert True is False
     +  where True = _decide({'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py submit --session-dir /tmp/claude-0/pytest-of-root/pytest-36/test_a_state_edited_after_the_0/session'}})
     +    where {'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py submit --session-dir /tmp/claude-0/pytest-of-root/pytest-36/test_a_state_edited_after_the_0/session'}} = _payload('python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py submit --session-dir /tmp/claude-0/pytest-of-root/pytest-36/test_a_state_edited_after_the_0/session')
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:406: AssertionError: assert True is False
E   AssertionError: assert True is False
     +  where True = _decide({'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py submit --session-dir session'}, 'cwd': '/tmp/claude-0/pytest-of-root/pytest-36/test_a_relative_session_dir_is0'})
     +    where {'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py submit --session-dir session'}, 'cwd': '/tmp/claude-0/pytest-of-root/pytest-36/test_a_relative_session_dir_is0'} = _payload('python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py submit --session-dir session', cwd='/tmp/claude-0/pytest-of-root/pytest-36/test_a_relative_session_dir_is0')
     +      where '/tmp/claude-0/pytest-of-root/pytest-36/test_a_relative_session_dir_is0' = str(PosixPath('/tmp/claude-0/pytest-of-root/pytest-36/test_a_relative_session_dir_is0'))
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:463: AssertionError: assert True is False
E   AssertionError: assert True is False
     +  where True = _decide({'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py submit --session-dir=/tmp/claude-0/pytest-of-root/pytest-36/test_session_dir_equals_form_i0/session'}})
     +    where {'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py submit --session-dir=/tmp/claude-0/pytest-of-root/pytest-36/test_session_dir_equals_form_i0/session'}} = _payload('python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py submit --session-dir=/tmp/claude-0/pytest-of-root/pytest-36/test_session_dir_equals_form_i0/session')
     +      where 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py submit --session-dir=/tmp/claude-0/pytest-of-root/pytest-36/test_session_dir_equals_form_i0/session' = _submit('--session-dir=/tmp/claude-0/pytest-of-root/pytest-36/test_session_dir_equals_form_i0/session')
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:471: AssertionError: assert True is False
E   AssertionError: assert True is False
     +  where True = _decide({'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py submit --session-dir /tmp/claude-0/pytest-of-root/pytest-36/test_a_state_the_real_driver_w0/session'}})
     +    where {'tool_name': 'Bash', 'tool_input': {'command': 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py submit --session-dir /tmp/claude-0/pytest-of-root/pytest-36/test_a_state_the_real_driver_w0/session'}} = _payload('python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py submit --session-dir /tmp/claude-0/pytest-of-root/pytest-36/test_a_state_the_real_driver_w0/session')
     +      where 'python3 -B /home/user/wt-2140/plugins/superheroes/lib/round_driver.py submit --session-dir /tmp/claude-0/pytest-of-root/pytest-36/test_a_state_the_real_driver_w0/session' = _submit('--session-dir', PosixPath('/tmp/claude-0/pytest-of-root/pytest-36/test_a_state_the_real_driver_w0/session'))
/home/user/wt-2140/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:509: AssertionError: assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_run_verify_gets_no_decision_whatever_the_session_state_holds
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_a_state_edited_after_the_mirror_was_written_gets_no_decision
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_a_relative_session_dir_is_resolved_against_the_payload_cwd
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_session_dir_equals_form_is_allowed_for_a_matching_session
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_a_state_the_real_driver_wrote_is_allowed
5 failed, 178 passed in 1.41s
```
Red on the claimed axis: row (a), `test_a_state_edited_after_the_mirror_was_written_gets_no_decision`, fails at `test_plugin_scripts_allow_hook.py:406` (a hand-edited state is approved). Four more rows that edit the state after the stamp fail the same way, including the rewritten `run-verify` test at line 369 and the real-driver row at line 509.
**Restore:** the inverse Edit, line 127 `mirror["stateSha256"] == mirror["stateSha256"]` → `mirror["stateSha256"] == hashlib.sha256(state_bytes).hexdigest()`.

**Restore receipt (hook lines 121-129 read back after the restore):**
```
        with open(state_path, "rb") as f:
            state_bytes = f.read()
        with open(os.path.join(session_dir, MIRROR_FILE), "rb") as f:
            mirror = json.loads(f.read().decode("utf-8"))
        if not isinstance(mirror, dict) or not isinstance(mirror.get("stateSha256"), str):
            return False
        return mirror["stateSha256"] == hashlib.sha256(state_bytes).hexdigest()
    except Exception:
        return False
```

**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 39%]
........................................................................ [ 78%]
.......................................                                  [100%]
183 passed in 1.53s
```
No secrets, tokens, private URLs or PII; nothing redacted.

---

## WO-5 — deterministic ids under xdist

**Guarded element:** none new. This order changes detector scaffolding in `plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py`, not a guard: the import-time `_FRESH` temp folder (a per-process random path inside parametrize values and ids) is replaced by the `{SESSION}` placeholder, filled at run time from a `fresh` fixture (a folder under `tmp_path`). Axis claimed: every collected node id is the same in every pytest-xdist worker. The proof is the parallel run itself.

**Red (the orchestrator's capture of the unchanged file at `5318ea6e`, quoted from the work order; this implementer did not re-run it — the file was edited before any run):**
```
$ scripts/pinned-python -B ... -m pytest plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py -q -n 4 -p no:cacheprovider
ERROR gw2 - Different tests were collected between gw0 and gw2. The differenc...
ERROR gw1 - Different tests were collected between gw0 and gw1. The differenc...
ERROR gw3 - Different tests were collected between gw0 and gw3. The differenc...
3 errors in 0.62s
```

**Change (restore is not applicable — nothing was neutralized):** the file is the changed file.

**Green (same command shape, run after the change, from `/home/user/wt-2140`):**
`scripts/pinned-python -B -X pycache_prefix=/home/user/wt-2140/docs/pyc-wo5 -m pytest plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py -q --tb=line -n 4 -p no:cacheprovider`
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

........................................................................ [ 41%]
........................................................................ [ 83%]
.............................                                            [100%]
173 passed in 1.06s
```

**Serial run after the change (both test files):** `scripts/pinned-python -B -X pycache_prefix=/home/user/wt-2140/docs/pyc-wo5 -m pytest plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py plugins/superheroes/lib/tests/test_hook_wiring.py -q --tb=line -p no:cacheprovider`
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 39%]
........................................................................ [ 78%]
.......................................                                  [100%]
183 passed in 1.53s
```
The count equals the committed baseline (`183 passed`), so no row was dropped.

No secrets, tokens, private URLs or PII; nothing redacted.

