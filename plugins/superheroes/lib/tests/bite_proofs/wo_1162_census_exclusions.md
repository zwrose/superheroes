# #1162 bite-proofs — the last three censuses stop reading bite-proof records

Orchestrator-typed (light lane, no implementer dispatch). Every run below was executed on this
branch's head, not transcribed. Raw captures are unredacted only because none of them carry a
secret, token, private URL, or PII — nothing was elided.

**This record is itself the proof material.** It quotes each census's guarded literal below; that
is only safe because the exclusion under proof exists. Neutralize the exclusion and this file is
what turns the census red.

---

## BP-1 — `test_closure_doctrine.py` R8 element-sentence walk

**Guarded element:** `_CENSUS_EXCLUDED_DIRS` / `_census_excluded()` in
`plugins/superheroes/lib/tests/test_closure_doctrine.py` — axis: the R8 walk reads no path under
`lib/tests/bite_proofs/`.

**Guarded literal quoted in this record (the neutralization's ammunition):**

> The closure receipt enumerates exactly: coverage map complete; all other children merged with green vets; amendments reconciled — meaning the Amendments log is valid against R4's format AND UFR-4's propagation is verified: every affected child carried the amended text or an explicit notice, and the coverage map still allocates every acceptance criterion; one end-to-end validation run against the current spec body with its result stated; aggregated Show-it items; delivered versus deferred/declined named; and NFR conformance checked across the delivery (owner reading load, plain language, guidelines never hardened into gates) — an absent element is named with why.

**Neutralization:** `_CENSUS_EXCLUDED_DIRS` collapsed to the empty tuple — the smallest edit that
puts the walk back on its old shape, with the detector itself unedited.

```
-_CENSUS_EXCLUDED_DIRS = ("lib/tests/bite_proofs",)
+_CENSUS_EXCLUDED_DIRS = ()
```

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-1162 -m pytest plugins/superheroes/lib/tests/test_closure_doctrine.py::test_r8_element_sentence_has_exactly_one_plugin_home -q
```

**Red run (exit 1):**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_r8_element_sentence_has_exactly_one_plugin_home _____________
    def test_r8_element_sentence_has_exactly_one_plugin_home():
        hits = _r8_element_hits(_PLUGIN_ROOT)
>       assert hits == [(_CLOSURE_REF, 1)], (
            "R8 element list must live in closure.md and nowhere else in the plugin; found %r"
            % (hits,)
        )
E       AssertionError: R8 element list must live in closure.md and nowhere else in the plugin; found [('lib/tests/bite_proofs/wo_1162_census_exclusions.md', 1), ('skills/showrunner/reference/closure.md', 1)]
E       assert [('lib/tests/...osure.md', 1)] == [('skills/sho...osure.md', 1)]
E         
E         At index 0 diff: ('lib/tests/bite_proofs/wo_1162_census_exclusions.md', 1) != ('skills/showrunner/reference/closure.md', 1)
E         Left contains one more item: ('skills/showrunner/reference/closure.md', 1)
E         Use -v to get more diff
plugins/superheroes/lib/tests/test_closure_doctrine.py:468: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_closure_doctrine.py::test_r8_element_sentence_has_exactly_one_plugin_home
1 failed in 0.45s
```

**Restore:** inverse edit — `_CENSUS_EXCLUDED_DIRS` restored to `("lib/tests/bite_proofs",)`.

**Restore receipt:** `git status --porcelain plugins/superheroes/lib/tests/test_closure_doctrine.py`
→ empty output (file byte-identical to HEAD).

**Green run (exit 0):**
```
.                                                                        [100%]
1 passed in 0.54s
```

**The census still bites (consumer surface outside `bite_proofs/`).** The same sentence planted in
an ordinary plugin surface — `plugins/superheroes/rubric/covenant.md` — with the exclusion in place:

**Red run (exit 1):**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_r8_element_sentence_has_exactly_one_plugin_home _____________
    def test_r8_element_sentence_has_exactly_one_plugin_home():
        hits = _r8_element_hits(_PLUGIN_ROOT)
>       assert hits == [(_CLOSURE_REF, 1)], (
            "R8 element list must live in closure.md and nowhere else in the plugin; found %r"
            % (hits,)
        )
E       AssertionError: R8 element list must live in closure.md and nowhere else in the plugin; found [('rubric/covenant.md', 1), ('skills/showrunner/reference/closure.md', 1)]
E       assert [('rubric/cov...osure.md', 1)] == [('skills/sho...osure.md', 1)]
E         
E         At index 0 diff: ('rubric/covenant.md', 1) != ('skills/showrunner/reference/closure.md', 1)
E         Left contains one more item: ('skills/showrunner/reference/closure.md', 1)
E         Use -v to get more diff
plugins/superheroes/lib/tests/test_closure_doctrine.py:468: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_closure_doctrine.py::test_r8_element_sentence_has_exactly_one_plugin_home
1 failed in 0.36s
```

**Restore receipt:** the planted paragraph removed by the inverse write; `git status --porcelain` over the whole tree → empty output.

---

## BP-2 — `test_ssot_drift.py` shared plugin-source collector (both censuses)

**Guarded element:** `_CENSUS_EXCLUDED_DIRS` / `_census_excluded()` at
`plugins/superheroes/lib/tests/test_ssot_drift.py`'s `_collect_plugin_source_paths()` — axis:
neither the retired-grok census nor the routing census reads a path under `lib/tests/bite_proofs/`.

One predicate, one neutralization, **two** census tests red — the two walks share the collector,
so the guarded element is one, not two, and both consumers are named in the command below.

**Guarded literals quoted in this record (the neutralization's ammunition):**

- retired cursor judge id: `cursor-grok-4.5`
- retired route name: `needs-discovery`

**Neutralization:**

```
-_CENSUS_EXCLUDED_DIRS = ("lib/tests/bite_proofs",)
+_CENSUS_EXCLUDED_DIRS = ()
```

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-1162 -m pytest plugins/superheroes/lib/tests/test_ssot_drift.py::test_retired_cursor_grok_4_5_literal_census plugins/superheroes/lib/tests/test_ssot_drift.py::test_retired_discovery_route_name_census -q
```

**Red run (exit 1):**
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_________________ test_retired_cursor_grok_4_5_literal_census __________________
    def test_retired_cursor_grok_4_5_literal_census():
        """I4: the retired cursor judge id may appear only in the two drift-guard tuple declarations (I1)."""
        allowed = _allowed_retired_grok_literal_sites()
        paths = _retired_grok_census_paths()
        hits = _scan_paths_for_retired_grok_literal(paths)
        unexpected = sorted(set(hits) - allowed)
>       assert not unexpected, (
            "retired literal %r outside intentional declaration sites %r — stale hits: %r"
            % (_retired_grok_literal(), sorted(allowed), unexpected)
        )
E       AssertionError: retired literal 'cursor-grok-4.5' outside intentional declaration sites [('lib/tests/test_ssot_drift.py', 1584), ('lib/tests/test_ssot_drift.py', 1600)] — stale hits: [('lib/tests/bite_proofs/wo_1162_census_exclusions.md', 74)]
E       assert not [('lib/tests/bite_proofs/wo_1162_census_exclusions.md', 74)]
plugins/superheroes/lib/tests/test_ssot_drift.py:1923: AssertionError
___________________ test_retired_discovery_route_name_census ___________________
    def test_retired_discovery_route_name_census():
        # axis: absence of the retired route name across plugin source, README, CONVENTIONS
        # docs/ is out of scope — specs and child definition-docs quote the retired name as history.
        literal = _retired_discovery_route_literal()
        paths = _routing_census_paths()
        hits = _scan_paths_for_literal(paths, literal)
>       assert not hits, (
            "retired route name %r found outside allowed history-only docs — hits: %r"
            % (literal, hits)
        )
E       AssertionError: retired route name 'needs-discovery' found outside allowed history-only docs — hits: [('lib/tests/bite_proofs/wo_1162_census_exclusions.md', 75)]
E       assert not [('lib/tests/bite_proofs/wo_1162_census_exclusions.md', 75)]
plugins/superheroes/lib/tests/test_ssot_drift.py:5553: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ssot_drift.py::test_retired_cursor_grok_4_5_literal_census
FAILED plugins/superheroes/lib/tests/test_ssot_drift.py::test_retired_discovery_route_name_census
2 failed in 1.39s
```

**Restore:** inverse edit — `_CENSUS_EXCLUDED_DIRS` restored to `("lib/tests/bite_proofs",)`.

**Restore receipt:** `git status --porcelain plugins/superheroes/lib/tests/test_ssot_drift.py`
→ empty output (file byte-identical to HEAD).

**Green run (exit 0):**
```
..                                                                       [100%]
2 passed in 2.13s
```

**The censuses still bite (consumer surface outside `bite_proofs/`).** Each retired literal planted
in an ordinary plugin surface — `plugins/superheroes/rubric/covenant.md` — with the exclusion in
place:

**Red run (exit 1):**
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_________________ test_retired_cursor_grok_4_5_literal_census __________________
    def test_retired_cursor_grok_4_5_literal_census():
        """I4: the retired cursor judge id may appear only in the two drift-guard tuple declarations (I1)."""
        allowed = _allowed_retired_grok_literal_sites()
        paths = _retired_grok_census_paths()
        hits = _scan_paths_for_retired_grok_literal(paths)
        unexpected = sorted(set(hits) - allowed)
>       assert not unexpected, (
            "retired literal %r outside intentional declaration sites %r — stale hits: %r"
            % (_retired_grok_literal(), sorted(allowed), unexpected)
        )
E       AssertionError: retired literal 'cursor-grok-4.5' outside intentional declaration sites [('lib/tests/test_ssot_drift.py', 1584), ('lib/tests/test_ssot_drift.py', 1600)] — stale hits: [('rubric/covenant.md', 63)]
E       assert not [('rubric/covenant.md', 63)]
plugins/superheroes/lib/tests/test_ssot_drift.py:1923: AssertionError
___________________ test_retired_discovery_route_name_census ___________________
    def test_retired_discovery_route_name_census():
        # axis: absence of the retired route name across plugin source, README, CONVENTIONS
        # docs/ is out of scope — specs and child definition-docs quote the retired name as history.
        literal = _retired_discovery_route_literal()
        paths = _routing_census_paths()
        hits = _scan_paths_for_literal(paths, literal)
>       assert not hits, (
            "retired route name %r found outside allowed history-only docs — hits: %r"
            % (literal, hits)
        )
E       AssertionError: retired route name 'needs-discovery' found outside allowed history-only docs — hits: [('rubric/covenant.md', 63)]
E       assert not [('rubric/covenant.md', 63)]
plugins/superheroes/lib/tests/test_ssot_drift.py:5553: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ssot_drift.py::test_retired_cursor_grok_4_5_literal_census
FAILED plugins/superheroes/lib/tests/test_ssot_drift.py::test_retired_discovery_route_name_census
2 failed in 2.94s
```

**Restore receipt:** the planted line removed by the inverse write; `git status --porcelain` over the whole tree → empty output.
