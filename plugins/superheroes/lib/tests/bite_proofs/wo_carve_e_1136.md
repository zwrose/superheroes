# WO-CARVE-E (#1136) bite-proofs — bite-proof directory excluded from content census

## BP-E1 — `test_retired_presence_premise_literals_census[no human]` (bite-proof receipts excluded)

**Guarded element:** `_census_excluded` / `_CENSUS_EXCLUDED_DIRS` — axis: files under `lib/tests/bite_proofs/` must not be read by premise or INTERACTIVE content censuses; a proof must be free to quote the literal it proves.

**Before-state (from order):** `test_retired_presence_premise_literals_census[no human]` was red because `lib/tests/bite_proofs/wo_d_1136.md` quotes the allowlisted sentence `no human` in order to prove the allowlist works.

**Neutralization:** none (baseline after implementing `_census_excluded` chokepoint).

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest 'plugins/superheroes/lib/tests/test_presence_flag_retired.py::test_retired_presence_premise_literals_census[no human]' -q -p no:randomly -p no:xdist
```

**Green run:**
```
.                                                                        [100%]
1 passed in 0.29s
```

**Restore:** n/a (no mutation).

**Restore receipt:** n/a.

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
