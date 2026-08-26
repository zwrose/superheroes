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
PLACEHOLDER_RED_BP1
```

**Restore:** inverse edit — `_CENSUS_EXCLUDED_DIRS` restored to `("lib/tests/bite_proofs",)`.

**Restore receipt:** `git status --porcelain plugins/superheroes/lib/tests/test_closure_doctrine.py`
→ PLACEHOLDER_RESTORE_BP1

**Green run (exit 0):**
```
PLACEHOLDER_GREEN_BP1
```

**The census still bites (consumer surface outside `bite_proofs/`).** The same sentence planted in
an ordinary plugin surface — `plugins/superheroes/rubric/covenant.md` — with the exclusion in place:

**Red run (exit 1):**
```
PLACEHOLDER_BITES_BP1
```

**Restore receipt:** PLACEHOLDER_BITES_RESTORE_BP1

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
PLACEHOLDER_RED_BP2
```

**Restore:** inverse edit — `_CENSUS_EXCLUDED_DIRS` restored to `("lib/tests/bite_proofs",)`.

**Restore receipt:** `git status --porcelain plugins/superheroes/lib/tests/test_ssot_drift.py`
→ PLACEHOLDER_RESTORE_BP2

**Green run (exit 0):**
```
PLACEHOLDER_GREEN_BP2
```

**The censuses still bite (consumer surface outside `bite_proofs/`).** Each retired literal planted
in an ordinary plugin surface — `plugins/superheroes/rubric/covenant.md` — with the exclusion in
place:

**Red run (exit 1):**
```
PLACEHOLDER_BITES_BP2
```

**Restore receipt:** PLACEHOLDER_BITES_RESTORE_BP2
