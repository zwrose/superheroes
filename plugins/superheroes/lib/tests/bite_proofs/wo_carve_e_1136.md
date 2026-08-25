# WO-CARVE-E (#1136) bite-proofs — bite-proof directory excluded from content census

## BP-E1 — `test_retired_presence_premise_literals_census[no human]` (bite-proof receipts excluded)

**Guarded element:** `_census_excluded` / `_CENSUS_EXCLUDED_DIRS` — axis: files under `lib/tests/bite_proofs/` must not be read by premise or INTERACTIVE content censuses; a proof must be free to quote the literal it proves.

**Before-state (from order):** `test_retired_presence_premise_literals_census[no human]` was red because `lib/tests/bite_proofs/wo_d_1136.md` quotes the allowlisted sentence `no human` in order to prove the allowlist works.

**Neutralization:** `_CENSUS_EXCLUDED_DIRS` collapsed to the empty tuple — the smallest edit that
removes only the bite-proof-directory exclusion while leaving `_CENSUS_SELF_PATHS` and the
`_census_excluded` chokepoint itself intact, so the red can come from nothing else:

```diff
-_CENSUS_EXCLUDED_DIRS = (
-    os.path.normpath(os.path.join(_PLUGIN_ROOT, "lib/tests/bite_proofs")),
-)
+_CENSUS_EXCLUDED_DIRS = ()
```

Applied as a targeted, reversible edit through the host's edit action (never a whole-file rewrite,
never a shell edit). Whole-file scope so **both** census walks that route through `_census_excluded`
are observed, not just the one parametrized row.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_presence_flag_retired.py -q -p no:randomly -p no:xdist
```

**Red run** (detector unedited; only the excluded-dirs tuple neutralized):
```
FAILED plugins/superheroes/lib/tests/test_presence_flag_retired.py::test_no_interactive_presence_flag_in_census_trees
FAILED plugins/superheroes/lib/tests/test_presence_flag_retired.py::test_retired_presence_premise_literals_census[no human]
2 failed, 19 passed in 1.68s
```
`PYTEST_EXIT=1`.

**Red is on the claimed axis, mechanically.** Every hit line the two assertions printed pointed
inside `lib/tests/bite_proofs/` — **56 of 56**, with **0** hits outside that directory. Counted over
the capture with a whitespace-tolerant match, because pytest indents `E` continuation lines by a
variable amount:

```
grep -cE '^E +lib/'                        → 56   # every hit line
grep -E '^E +lib/' | grep -c  'bite_proofs/' → 56   # inside the guarded directory
grep -E '^E +lib/' | grep -vc 'bite_proofs/' → 0    # outside it
```

So the red came from the exclusion being gone, not from unrelated drift.

*Two further capture lines mention `bite_proofs/` without being hit lines — the two assertions'
`assert not [...]` summary lines, which re-quote the first hit of each list. A broader
`grep -cE '^E .*bite_proofs/'` therefore returns **58**; the hit-line count is **56**.*

**Counting note, recorded because this record tripped it.** An earlier draft of this paragraph
counted the outside-hits with `grep -E '^E   lib/'` — exactly three spaces after `E`. Pytest emits
nine, so that pattern matched **nothing** and would have reported `0` outside-hits whether or not
any existed: the number was true but its evidence was vacuous. That is the bite-proof rubric's
mode 4 fixture-vacuity face — a probe green (here, a reassuring zero) that the fixture could
never have produced any other way. Caught by the confirming review round on this build. The
patterns above are the corrected, tolerant ones.

First two hit lines, verbatim:
```
E         lib/tests/bite_proofs/wo_carve_e_1136.md:5: **Guarded element:** `_census_excluded` / `_CENSUS_EXCLUDED_DIRS` - axis: files under `lib/tests/bite_proofs/` must not be read by premise or INTERACTIVE content censuses; a proof must be free to quote the literal it proves.
E         lib/tests/bite_proofs/wo_carve_e_1136.md:84: **Guarded element:** INTERACTIVE census over `_CENSUS_ROOTS` - axis: `lib/` files outside `bite_proofs/` must still be policed for retired presence flags.
```
**Elision, disclosed:** the remaining 54 hit lines and both assertions' full tracebacks are
elided here (~6 KiB) to stay inside the per-element capture bound; they are the same shape as the
two quoted, each naming a `lib/tests/bite_proofs/` path. Nothing redacted — the capture contains no
secrets, tokens, private URLs, or PII.

**Both guarded directions bite.** The premise-literal census and the INTERACTIVE census are separate
walks that both route through `_census_excluded`; removing the exclusion reddens **both**, which is
what BP-E1 claimed and, until this record, had not shown.

**Restore:** the neutralization was undone by the inverse edit — `_CENSUS_EXCLUDED_DIRS` restored to
the one-entry tuple quoted in the diff above.

**Restore receipt:** post-restore `git status --porcelain` over the worktree returned **0 lines**
(byte-clean) and `HEAD` was unchanged at `d9a5f1138ce1b546e2945980f0f99ac643bdca79`. No residue;
nothing could not be reverted.

**Green run** (after restore):
```
21 passed in 1.56s
```
`PYTEST_EXIT=0`. The matching pre-mutation baseline over the same command was also `21 passed`
(`PYTEST_EXIT=0`), so the green brackets the red on both sides.

**Provenance of this record.** BP-E1 originally shipped with `Neutralization: none` — a green-only
record, vacuous under the bite-proof rubric. PR #1142's completion round produced the missing red
half as a receipt in that PR's build record and filed copying it into this file as follow-up 3
(#1148 item 4). The runs above were **re-executed from scratch** for #1148 rather than transcribed,
and independently reproduce PR #1142's counts (red 2 failed / 19 passed; green 21 passed).

---

## BP-E2 — `test_retired_presence_premise_literals_census[no human]` (lib/ outside bite_proofs still censused)

**Guarded element:** premise literal census over `_CENSUS_ROOTS` — axis: `lib/` files outside `bite_proofs/` must still be policed.

**Neutralization:** inserted comment line `# no human` at line 2 of `plugins/superheroes/lib/tests/test_mode_registry.py` (temporary edit; line removed after capture).

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest 'plugins/superheroes/lib/tests/test_presence_flag_retired.py::test_retired_presence_premise_literals_census[no human]' -q -p no:randomly -p no:xdist
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_retired_presence_premise_literals_census[no human] ____________

literal = 'no human'

    @pytest.mark.parametrize("literal", _PREMISE_LITERALS)
    # axis: retired presence-premise spellings — cardinality floor zero outside explicit allowlist.
    def test_retired_presence_premise_literals_census(literal):
        """#1136: premise spellings that detected owner presence must not survive unallowlisted."""
        hits = []
        for rel, lineno, matched in _premise_literal_hits(literal):
            line_text = _read_plugin_rel(rel).splitlines()[lineno - 1].strip()
            if (rel, line_text, matched) not in _PREMISE_LITERAL_ALLOWLIST:
                hits.append(f"{rel}:{lineno}: {line_text}")
>       assert not hits, (
            "retired presence-premise literal %r found outside the explicit allowlist (#1136). "
            "Every hit:\n" + "\n".join(hits)
        )
E       AssertionError: retired presence-premise literal %r found outside the explicit allowlist (#1136). Every hit:
E         lib/tests/test_mode_registry.py:2: # no human
E       assert not ['lib/tests/test_mode_registry.py:2: # no human']

plugins/superheroes/lib/tests/test_presence_flag_retired.py:463: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_presence_flag_retired.py::test_retired_presence_premise_literals_census[no human]
1 failed in 0.20s
```

**Restore:** removed the `# no human` comment line from `test_mode_registry.py`.

**Restore receipt:** `test_mode_registry.py` line 2 is again `import json, os, subprocess`.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.18s
```

---

## BP-E3 — `test_no_interactive_presence_flag_in_census_trees` (lib/ outside bite_proofs still censused)

**Guarded element:** INTERACTIVE census over `_CENSUS_ROOTS` — axis: `lib/` files outside `bite_proofs/` must still be policed for retired presence flags.

**Neutralization:** inserted comment line `# INTERACTIVE=true` at line 2 of `plugins/superheroes/lib/tests/test_mode_registry.py` (temporary edit; line removed after capture).

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_presence_flag_retired.py::test_no_interactive_presence_flag_in_census_trees -q -p no:randomly -p no:xdist
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_no_interactive_presence_flag_in_census_trees _______________

    def test_no_interactive_presence_flag_in_census_trees():
        """#1136 census: the retired presence flag must not survive anywhere under skills/lib/eval."""
        hits = []
        for root in _CENSUS_ROOTS:
            for path in _walk_text_files(root):
                if _census_excluded(path):
                    continue
                try:
                    with open(path, encoding="utf-8") as fh:
                        text = fh.read()
                except (UnicodeDecodeError, OSError):
                    continue
                rel = os.path.relpath(path, _PLUGIN_ROOT)
                for lineno, line in enumerate(text.splitlines(), 1):
                    for pat in _INTERACTIVE_PATTERNS:
                        if pat.search(line):
                            hits.append(f"{rel}:{lineno}: {line.strip()}")
>       assert not hits, (
            "#1136 retired detecting owner presence — INTERACTIVE or $INTERACTIVE still present. "
            "Every hit:\n" + "\n".join(hits)
        )
E       AssertionError: #1136 retired detecting owner presence — INTERACTIVE or $INTERACTIVE still present. Every hit:
E         lib/tests/test_mode_registry.py:2: # INTERACTIVE=true
E       assert not ['lib/tests/test_mode_registry.py:2: # INTERACTIVE=true']

plugins/superheroes/lib/tests/test_presence_flag_retired.py:382: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_presence_flag_retired.py::test_no_interactive_presence_flag_in_census_trees
1 failed in 0.60s
```

**Restore:** removed the `# INTERACTIVE=true` comment line from `test_mode_registry.py`.

**Restore receipt:** `test_mode_registry.py` line 2 is again `import json, os, subprocess`.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.40s
```

---

## BP-E4 — `test_no_interactive_presence_flag_in_census_trees` (self-path half of `_census_excluded`)

**Guarded element:** `_CENSUS_SELF_PATHS` folded into `_census_excluded` — axis: detector self-paths must remain excluded after the refactor; removing `test_review_only_headless.py` from the set must re-fire the census on that file's INTERACTIVE literals.

**Neutralization:** temporarily removed `os.path.normpath(os.path.join(_PLUGIN_ROOT, "lib/tests/test_review_only_headless.py"))` from `_CENSUS_SELF_PATHS` in `test_presence_flag_retired.py` (temporary edit; entry restored after capture).

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_presence_flag_retired.py::test_no_interactive_presence_flag_in_census_trees -q -p no:randomly -p no:xdist
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_no_interactive_presence_flag_in_census_trees _______________

    def test_no_interactive_presence_flag_in_census_trees():
        """#1136 census: the retired presence flag must not survive anywhere under skills/lib/eval."""
        hits = []
        for root in _CENSUS_ROOTS:
            for path in _walk_text_files(root):
                if _census_excluded(path):
                    continue
                try:
                    with open(path, encoding="utf-8") as fh:
                        text = fh.read()
                except (UnicodeDecodeError, OSError):
                    continue
                rel = os.path.relpath(path, _PLUGIN_ROOT)
                for lineno, line in enumerate(text.splitlines(), 1):
                    for pat in _INTERACTIVE_PATTERNS:
                        if pat.search(line):
                            hits.append(f"{rel}:{lineno}: {line.strip()}")
>       assert not hits, (
            "#1136 retired detecting owner presence — INTERACTIVE or $INTERACTIVE still present. "
            "Every hit:\n" + "\n".join(hits)
        )
E       AssertionError: #1136 retired detecting owner presence — INTERACTIVE or $INTERACTIVE still present. Every hit:
E         lib/tests/test_review_only_headless.py:4: The retired INTERACTIVE flag and its gating are gone. Instead:
E         lib/tests/test_review_only_headless.py:140: """#1136: review-code must not claim to detect owner presence via INTERACTIVE."""
E         lib/tests/test_review_only_headless.py:143: re.compile(r"\$INTERACTIVE"),
E         lib/tests/test_review_only_headless.py:143: re.compile(r"\$INTERACTIVE"),
E         lib/tests/test_review_only_headless.py:144: re.compile(r"(?<![\w-])INTERACTIVE(?![\w-])"),
E         lib/tests/test_review_only_headless.py:145: re.compile(r"^\s*INTERACTIVE=", re.MULTILINE),
E         lib/tests/test_review_only_headless.py:156: "INTERACTIVE flag or $INTERACTIVE on its surface. Hits:\n" + "\n".join(hits)
E         lib/tests/test_review_only_headless.py:156: "INTERACTIVE flag or $INTERACTIVE on its surface. Hits:\n" + "\n".join(hits)
E       assert not ['lib/tests/test_review_only_headless.py:4: The retired INTERACTIVE flag and its gating are gone. Instead:', 'lib/test...TIVE(?![\\w-])"),', 'lib/tests/test_review_only_headless.py:145: re.compile(r"^\\s*INTERACTIVE=", re.MULTILINE),', ...]

plugins/superheroes/lib/tests/test_presence_flag_retired.py:381: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_presence_flag_retired.py::test_no_interactive_presence_flag_in_census_trees
1 failed in 0.33s
```

**Restore:** re-added `os.path.normpath(os.path.join(_PLUGIN_ROOT, "lib/tests/test_review_only_headless.py"))` to `_CENSUS_SELF_PATHS`.

**Restore receipt:** `_CENSUS_SELF_PATHS` again contains both `lib/tests/test_presence_flag_retired.py` and `lib/tests/test_review_only_headless.py`.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.31s
```
