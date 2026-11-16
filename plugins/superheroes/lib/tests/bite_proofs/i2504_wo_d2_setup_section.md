# #2504 bite-proof — WO-D2: the set-up section test follows this PR's section to § 4.11

Detector changed: `test_set_up_has_section_4_11_and_its_contents_line` (renamed from `test_set_up_has_section_4_10_and_its_contents_line`) in `plugins/superheroes/lib/tests/test_advisor_inboxes_doctrine_2504.py`.

Declared guarded-element set (from the order): **S2**. Redaction: none needed. Each capture omits only the first line the runner prints (`warning: The UV_NATIVE_TLS environment variable is deprecated ...`); everything else is verbatim. Every command ran from the worktree root as `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2504d2 -m pytest plugins/superheroes/lib/tests/test_advisor_inboxes_doctrine_2504.py -q -p no:cacheprovider -k test_set_up_has_section_4_11`.

## S2 — this PR's section sits right after § 4.10

Guarded element: the test's location of this PR's section after main's § 4.10 (`test_advisor_inboxes_doctrine_2504.py:337-338` for the Contents line, `:342-343` for the headings). Axis: the section sits right after § 4.10.

Neutralization (`plugins/superheroes/skills/configure/reference/set-up.md`, Contents lines 15-16): swap the two lines.

```
- §4.10 — Duplication skip trees — none by default
- §4.11 — Advisor issues — the collector and the inboxes
```
became
```
- §4.11 — Advisor issues — the collector and the inboxes
- §4.10 — Duplication skip trees — none by default
```

Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_set_up_has_section_4_11_and_its_contents_line ______________

    def test_set_up_has_section_4_11_and_its_contents_line():
        lines = _lines(SET_UP)
        contents = lines[: lines.index("# configure — set-up path")]
        assert "- §4.11 — Advisor issues — the collector and the inboxes" in contents, (
            "set-up.md ## Contents has no §4.11 line")
        at = contents.index("- §4.11 — Advisor issues — the collector and the inboxes")
>       assert contents[at - 1] == "- §4.10 — Duplication skip trees — none by default", (
            "the §4.11 Contents line is not right after §4.10's")
E       AssertionError: the §4.11 Contents line is not right after §4.10's
E       assert '- §4.9 — Siz...ne by default' == '- §4.10 — Du...ne by default'
E         
E         - - §4.10 — Duplication skip trees — none by default
E         + - §4.9 — Size count exclusions — none by default

/home/user/superheroes-wt-2504/plugins/superheroes/lib/tests/test_advisor_inboxes_doctrine_2504.py:337: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_advisor_inboxes_doctrine_2504.py::test_set_up_has_section_4_11_and_its_contents_line
1 failed, 21 deselected in 0.14s
```

Restore: the inverse edit (swapped the two Contents lines back).

Restore receipt: `set-up.md` lines 14-16 read back:

```
- §4.9 — Size count exclusions — none by default
- §4.10 — Duplication skip trees — none by default
- §4.11 — Advisor issues — the collector and the inboxes
```

Raw green:

```
.                                                                        [100%]
1 passed, 21 deselected in 0.17s
```

Not separately neutralized: the heading-order check (`:342-343`, the `## 4.10` / `## 4.11` headings). The order's S2 neutralization swaps the Contents lines only, and the Contents assert fires first, so this red does not show the heading assert biting.
