# WO-A (#2530) bite-proof — a single-vendor panel outside every maker's family is not a critical-diversity breach

**Provenance:** claude / sonnet-5.5 (implementer), `plugins/superheroes/lib/seat_map.py`, `plugins/superheroes/lib/seat_map_receipts.py`. Shape and ceilings: `plugins/superheroes/rubric/bite-proof.md`.

Declared guarded-element set (from the order): G1-G9. Each was neutralized by one targeted text edit of that one production line, the proving node was run red, the neutralization was undone by the inverse text edit, and the same node was run green. Redactions: `<repo>` for the worktree root, `<venv>` for the throwaway interpreter path pytest prints; the two leading noise lines of every run (the `UV_NATIVE_TLS` deprecation warning and `bringing up nodes...`) are dropped; nothing else was edited. Every command ran from `<repo>` through the pinned interpreter, e.g.:

```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/wo-a-pyc -m pytest <node id> -q -n auto
```

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| G1 | `verify()` critical-diversity gate (`seat_map.py` `verify`) | a panel outside every maker's family is not reported as a critical-diversity breach | `test_seat_map.py::test_verify_reports_no_critical_diversity_for_a_panel_outside_the_makers` |
| G2 | `derived_violations()` drop (`seat_map.py` `derived_violations`) | a stored (submitted) critical-diversity record on a panel outside the makers never reaches the classifier | `test_seat_map.py::test_derived_violations_drops_a_submitted_critical_diversity_on_a_panel_outside_the_makers` |
| G3 | `build()` relaxation gate (`seat_map.py` `build`) | a chosen panel outside the makers is not recorded as a critical-diversity relaxation | `test_seat_map.py::test_a_fresh_panel_outside_the_makers_records_no_critical_diversity_degradation` |
| G4 | `emit_receipt_seat_map()` degradation drop (`seat_map_receipts.py`) | a receipt's critical-diversity degradation row is not emitted for a panel outside the makers | `test_seat_map_receipts.py::test_emit_receipt_seat_map_drops_a_critical_diversity_row_for_a_panel_outside_the_makers` |
| G5 | predicate maker-set membership (`panel_outside_makers`) | a seat in the author's or an extra maker's family keeps today's records | `test_seat_map.py::test_panel_outside_makers_edge_a_a_seat_in_the_authors_family_is_not_outside` and `...edge_b_an_extra_maker_seated_is_not_outside` |
| G6 | predicate malformed-`makerFamilies` check | a `makerFamilies` that is present but not a list of non-empty strings is unusable maker evidence | `test_seat_map.py::test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside` |
| G7 | predicate unknown-author check | an unknown author family leaves the maker set unprovable | `test_seat_map.py::test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside` |
| G8 | predicate unresolvable-family check | a walked seat whose family does not resolve cannot be proven outside the makers | `test_seat_map.py::test_panel_outside_makers_edge_e_an_unresolvable_or_malformed_seat_is_not_outside` |
| G9 | predicate filled-critical-seat check | a map with no filled critical seat is governed by `seat-unfilled`, never exempt | `test_seat_map.py::test_panel_outside_makers_edge_f_no_filled_critical_seat_is_not_outside` |

Baseline sha256, taken after the last production edit and before G1 (the same two lines came back after every restore):
```
672c4510b88f0432a570da2ba9479fa1f8c4adc19f7ad2c4a663e14df8894583  plugins/superheroes/lib/seat_map.py
d3198b03fe9dd259633a978ac3cb41c489ff6289bcf406f53b86647c6bb11f36  plugins/superheroes/lib/seat_map_receipts.py
```

---

## G1 — `verify()` critical-diversity gate (`seat_map.py` `verify`)

- **axis:** a panel outside every maker's family is not reported as a critical-diversity breach

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
    if len(critical_families) < required_critical_families(roster) and not panel_outside_makers(seat_map, author_family):
+++ neutralized
    if len(critical_families) < required_critical_families(roster):
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/wo-a-pyc -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_verify_reports_no_critical_diversity_for_a_panel_outside_the_makers -q -n auto
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_verify_reports_no_critical_diversity_for_a_panel_outside_the_makers ___
[gw0] linux -- Python 3.12.13 <venv>/bin/python

    def test_verify_reports_no_critical_diversity_for_a_panel_outside_the_makers():
        # axis: verify reports critical-diversity only when the panel is not outside the makers — see bite-proof record wo_a_2530_single_vendor_panel
        for live, author in ((["claude"], "xai"), (["claude", "codex"], "anthropic")):
            m = SM.build(SM.PANEL_ROSTER, live, author, 0)
>           assert SM.verify(m, author) == [], (live, author)
E           AssertionError: (['claude'], 'xai')
E           assert [{'constraint...l-diversity'}] == []
E             
E             Left contains one more item: {'constraint': 'critical-diversity'}
E             Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4631: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_verify_reports_no_critical_diversity_for_a_panel_outside_the_makers
1 failed in 5.83s
```

**restore:** the inverse text edit of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored line as it stands in the file, `seat_map.py:1385`):
```
    if len(critical_families) < required_critical_families(roster) and not panel_outside_makers(seat_map, author_family):
```

**raw green** (after restore, exit 0):
```
.                                                                        [100%]
1 passed in 3.87s
```

---

## G2 — `derived_violations()` drop (`seat_map.py` `derived_violations`)

- **axis:** a stored (submitted) critical-diversity record on a panel outside every maker's family never reaches the classifier

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
    if panel_outside_makers(seat_map, author_family):
        out = [v for v in out if v.get("constraint") != "critical-diversity"]
+++ neutralized
    if False:
        out = [v for v in out if v.get("constraint") != "critical-diversity"]
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/wo-a-pyc -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_derived_violations_drops_a_submitted_critical_diversity_on_a_panel_outside_the_makers -q -n auto
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_derived_violations_drops_a_submitted_critical_diversity_on_a_panel_outside_the_makers _
[gw0] linux -- Python 3.12.13 <venv>/bin/python

    def test_derived_violations_drops_a_submitted_critical_diversity_on_a_panel_outside_the_makers():
        # axis: derived_violations drops a stored critical-diversity record for a panel outside the makers — see bite-proof record wo_a_2530_single_vendor_panel
        stored = _legacy_stored_outside_panel()
        assert SM.panel_outside_makers(stored, "anthropic")
>       assert SM.derived_violations(stored) == []
E       AssertionError: assert [{'constraint...l-diversity'}] == []
E         
E         Left contains one more item: {'constraint': 'critical-diversity'}
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4639: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_derived_violations_drops_a_submitted_critical_diversity_on_a_panel_outside_the_makers
1 failed in 3.94s
```

**restore:** the inverse text edit of the neutralization above (no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored line, `seat_map.py:1194`):
```
    if panel_outside_makers(seat_map, author_family):
```

**raw green** (after restore, exit 0):
```
.                                                                        [100%]
1 passed in 1.35s
```

---

## G3 — `build()` relaxation gate (`seat_map.py` `build`)

- **axis:** a chosen panel outside every maker's family is not recorded as a critical-diversity relaxation

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
                if not panel_outside_makers(chosen_map, author_family):
+++ neutralized
                if True:
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/wo-a-pyc -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_a_fresh_panel_outside_the_makers_records_no_critical_diversity_degradation -q -n auto
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_fresh_panel_outside_the_makers_records_no_critical_diversity_degradation _
[gw0] linux -- Python 3.12.13 <venv>/bin/python

    def test_a_fresh_panel_outside_the_makers_records_no_critical_diversity_degradation():
        # axis: build records the critical-diversity relaxation only for a chosen panel that is not outside the makers — see bite-proof record wo_a_2530_single_vendor_panel
        for live, author in ((["claude"], "xai"), (["claude", "codex"], "anthropic")):
            m = SM.build(SM.PANEL_ROSTER, live, author, 0)
            assert len({m["seats"][s]["family"] for s in SM.CRITICAL_SEATS}) == 1, (live, author)
>           assert not _has_critical_diversity(m["degradations"]), (live, author)
E           AssertionError: (['claude'], 'xai')
E           assert not True
E            +  where True = _has_critical_diversity([{'constraint': 'critical-diversity', 'reason': 'relaxed critical-diversity — no assignment spanned ≥2 families'}])

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4605: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_a_fresh_panel_outside_the_makers_records_no_critical_diversity_degradation
1 failed in 1.46s
```

**restore:** the inverse text edit of the neutralization above (no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored line, `seat_map.py:1037`):
```
                if not panel_outside_makers(chosen_map, author_family):
```

**raw green** (after restore, exit 0):
```
.                                                                        [100%]
1 passed in 1.49s
```

---

## G4 — `emit_receipt_seat_map()` degradation drop (`seat_map_receipts.py`)

- **axis:** a receipt's critical-diversity degradation row is not emitted for a panel outside every maker's family

**neutralization** (`plugins/superheroes/lib/seat_map_receipts.py`):
```diff
--- before (restored text)
                if outside_makers and row.get("constraint") == "critical-diversity":
+++ neutralized
                if False and row.get("constraint") == "critical-diversity":
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/wo-a-pyc -m pytest plugins/superheroes/lib/tests/test_seat_map_receipts.py::test_emit_receipt_seat_map_drops_a_critical_diversity_row_for_a_panel_outside_the_makers -q -n auto
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_emit_receipt_seat_map_drops_a_critical_diversity_row_for_a_panel_outside_the_makers _
[gw0] linux -- Python 3.12.13 <venv>/bin/python

    def test_emit_receipt_seat_map_drops_a_critical_diversity_row_for_a_panel_outside_the_makers():
        # axis: a receipt's critical-diversity degradation is not emitted for a panel outside every maker's family — see bite-proof record wo_a_2530_single_vendor_panel
        stored = _stored_outside_makers_map()
        other = {"constraint": "pin", "reason": "pin for unknown seat nope"}
        stored["degradations"] = stored["degradations"] + [other]
        for driver in (None, "anthropic"):
            emitted = _emit([stored], driver)
>           assert not _has_critical_diversity(emitted["degradations"]), driver
E           AssertionError: None
E           assert not True
E            +  where True = _has_critical_diversity([{'constraint': 'critical-diversity', 'reason': 'relaxed critical-diversity — no assignment spanned ≥2 families'}, {'constraint': 'pin', 'reason': 'pin for unknown seat nope'}])

<repo>/plugins/superheroes/lib/tests/test_seat_map_receipts.py:424: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map_receipts.py::test_emit_receipt_seat_map_drops_a_critical_diversity_row_for_a_panel_outside_the_makers
1 failed in 1.32s
```

**restore:** the inverse text edit of the neutralization above (no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored line, `seat_map_receipts.py:273`):
```
                if outside_makers and row.get("constraint") == "critical-diversity":
```

**raw green** (after restore, exit 0):
```
.                                                                        [100%]
1 passed in 1.37s
```

---

## G5 — predicate maker-set membership (`seat_map.py` `panel_outside_makers`)

- **axis:** a walked seat in the author's family or an extra maker's family keeps today's records (E-a, E-b)

**neutralization** (`plugins/superheroes/lib/seat_map.py`) — the maker-set membership return deleted:
```diff
--- before (restored text)
        if fam in makers:
            return False
+++ neutralized
        if fam in makers:
            pass
```

**command** (both proving nodes, one invocation):
```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/wo-a-pyc -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_a_a_seat_in_the_authors_family_is_not_outside plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_b_an_extra_maker_seated_is_not_outside -q -n auto
```

**raw red** (exit 1; the long `where` lines are cut at the `...` pytest itself prints):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
____ test_panel_outside_makers_edge_b_an_extra_maker_seated_is_not_outside _____
[gw1] linux -- Python 3.12.13 <venv>/bin/python

    def test_panel_outside_makers_edge_b_an_extra_maker_seated_is_not_outside():
        # axis: a seat in an extra maker's family keeps today's records — see bite-proof record wo_a_2530_single_vendor_panel
        m = dict(_outside_panel(**{"test-role": _seat_cfg("cursor")}), makerFamilies=["xai"])
>       assert not SM.panel_outside_makers(m, "anthropic")
E       AssertionError: assert not True
E        +  where True = <function panel_outside_makers at 0x7fa81cec0400>({'seats': {'code-reviewer': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', .....iewer', 'security-reviewer', 'test-role', 'premortem-reviewer'], 'authorFamily': 'anthropic', 'makerFamilies': ['xai']}, 'anthropic')
E        +    where <function panel_outside_makers at 0x7fa81cec0400> = SM.panel_outside_makers

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4680: AssertionError
_ test_panel_outside_makers_edge_a_a_seat_in_the_authors_family_is_not_outside _
[gw0] linux -- Python 3.12.13 <venv>/bin/python

    def test_panel_outside_makers_edge_a_a_seat_in_the_authors_family_is_not_outside():
        # axis: a seat in the author's family keeps today's records — see bite-proof record wo_a_2530_single_vendor_panel
        for seat in ("security-reviewer", "test-role"):
            m = _outside_panel(**{seat: _seat_cfg("claude")})
>           assert not SM.panel_outside_makers(m, "anthropic"), seat
E           AssertionError: security-reviewer
E           assert not True
E            +  where True = <function panel_outside_makers at 0x7f90ef0d0860>({'seats': {'code-reviewer': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', .......}}, 'roster': ['code-reviewer', 'security-reviewer', 'test-role', 'premortem-reviewer'], 'authorFamily': 'anthropic'}, 'anthropic')
E        +    where <function panel_outside_makers at 0x7f90ef0d0860> = SM.panel_outside_makers

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4668: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_b_an_extra_maker_seated_is_not_outside
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_a_a_seat_in_the_authors_family_is_not_outside
2 failed in 1.45s
```

**restore:** the inverse text edit of the neutralization above (no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored lines, `seat_map.py:471-472`):
```
        if fam in makers:
            return False
```

**raw green** (after restore, exit 0):
```
..                                                                       [100%]
2 passed in 1.46s
```

---

## G6 — predicate malformed-`makerFamilies` check (`seat_map.py` `panel_outside_makers`)

- **axis:** a `makerFamilies` that is present but not a list of non-empty strings is unusable maker evidence (E-c)

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
        if not isinstance(raw_makers, list) or not all(isinstance(f, str) and f for f in raw_makers):
            return False
+++ neutralized
        if False:
            return False
```

**command** (the whole parametrized function, nine cases):
```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/wo-a-pyc -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside -q -n auto
```

**raw red, INCOMPLETE** (exit 1). The shell tool truncated the middle of this run's output ("[7859 characters truncated]" below is the tool's own marker, not an edit). What follows is exactly the output that was received — the head and the tail and the summary, nothing reconstructed:
```
FFFFFFFFF                                                                [100%]
=================================== FAILURES ===================================
_ test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside[bad4] _
[gw2] linux -- Python 3.12.13 <venv>/bin/python

bad = ['xai', 5]

    @pytest.mark.parametrize("bad", ["xai", None, 7, {"xai": True}, ["xai", 5], ["xai", None], ["xai", ""], [""], [["xai"]]])
    def test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside(bad):
        # axis: a malformed makerFamilies is unusable maker evidence and keeps today's records — see bite-proof record wo_a_2530_single_vendor_panel
        m = dict(_outside_panel(), makerFamilies=bad)
>       assert not SM.panel_outside_makers(m, "anthropic")
E       AssertionError: assert not True
E        +  where True = <function panel_outside_makers at 0x7fb47b6c8220>({'seats': {'code-reviewer': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', .....er', 'security-reviewer', 'test-role', 'premortem-reviewer'], 'authorFamily': 'anthropic', 'makerFamilies': ['xai', 5]}, 'anthropic')

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4691: AssertionError

... [7859 characters truncated] ...

        if "makerFamilies" in seat_map:
            raw_makers = seat_map["makerFamilies"]
            # axis: a malformed makerFamilies (scalar, None, a non-string or empty member) is unusable maker evidence — see bite-proof record wo_a_2530_single_vendor_panel
            if False:
                return False
>           makers.update(raw_makers)
E           TypeError: unhashable type: 'list'

<repo>/plugins/superheroes/lib/seat_map.py:457: TypeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside[bad4]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside[xai]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside[bad6]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside[7]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside[bad5]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside[bad7]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside[None]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside[bad3]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside[bad8]
9 failed in 1.83s
```

**raw red, complete capture of two of the nine cases** (a second run with the neutralization still in place, two nodes only, so nothing was truncated; exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside[bad6] _
[gw1] linux -- Python 3.12.13 <venv>/bin/python

bad = ['xai', '']

    @pytest.mark.parametrize("bad", ["xai", None, 7, {"xai": True}, ["xai", 5], ["xai", None], ["xai", ""], [""], [["xai"]]])
    def test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside(bad):
        # axis: a malformed makerFamilies is unusable maker evidence and keeps today's records — see bite-proof record wo_a_2530_single_vendor_panel
        m = dict(_outside_panel(), makerFamilies=bad)
>       assert not SM.panel_outside_makers(m, "anthropic")
E       AssertionError: assert not True
E        +  where True = <function panel_outside_makers at 0x7f47f1d302c0>({'seats': {'code-reviewer': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', .....r', 'security-reviewer', 'test-role', 'premortem-reviewer'], 'authorFamily': 'anthropic', 'makerFamilies': ['xai', '']}, 'anthropic')
E        +    where <function panel_outside_makers at 0x7f47f1d302c0> = SM.panel_outside_makers

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4691: AssertionError
_ test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside[xai] _
[gw0] linux -- Python 3.12.13 <venv>/bin/python

bad = 'xai'

    @pytest.mark.parametrize("bad", ["xai", None, 7, {"xai": True}, ["xai", 5], ["xai", None], ["xai", ""], [""], [["xai"]]])
    def test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside(bad):
        # axis: a malformed makerFamilies is unusable maker evidence and keeps today's records — see bite-proof record wo_a_2530_single_vendor_panel
        m = dict(_outside_panel(), makerFamilies=bad)
>       assert not SM.panel_outside_makers(m, "anthropic")
E       AssertionError: assert not True
E        +  where True = <function panel_outside_makers at 0x7f9b611982c0>({'seats': {'code-reviewer': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', .....eviewer', 'security-reviewer', 'test-role', 'premortem-reviewer'], 'authorFamily': 'anthropic', 'makerFamilies': 'xai'}, 'anthropic')
E        +    where <function panel_outside_makers at 0x7f9b611982c0> = SM.panel_outside_makers

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4691: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside[bad6]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_c_malformed_maker_families_is_not_outside[xai]
2 failed in 1.47s
```

**restore:** the inverse text edit of the neutralization above (no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored line, `seat_map.py:455`):
```
        if not isinstance(raw_makers, list) or not all(isinstance(f, str) and f for f in raw_makers):
```

**raw green** (after restore, all nine cases, exit 0):
```
.........                                                                [100%]
9 passed in 1.43s
```

## G7 — predicate unknown-author check (`seat_map.py` `panel_outside_makers`)

- **axis:** an unknown author family (None, empty, non-string) leaves the maker set unprovable, so the panel is never exempt (E-d)

**neutralization** (`plugins/superheroes/lib/seat_map.py`, line 450):
```diff
--- before (restored text)
    if not isinstance(author_family, str) or not author_family:
        return False
+++ neutralized
    if not isinstance(author_family, str) or not author_family:
        pass
```

**command** (the whole parametrized function, twelve cases; from here on the runs of WO-A2 used `-X pycache_prefix=/tmp/claude-0/wo-a2-pyc` and no `-n auto`, so no `[gwN]` line is printed):
```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/wo-a2-pyc -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside -q
```

**What the red actually was.** With the check made a no-op, the neutralized function goes on to `makers = {author_family}`. For an author of `None`, `""` or `42` that set is built and the function returns True (the panel is wrongly exempt): the visible cases below fail on `assert not SM.panel_outside_makers(m, author)` with `assert not True`. For the unhashable author `["anthropic"]` the next line raises `TypeError: unhashable type: 'list'` instead of returning True (visible for `[makers2-author3]` below). So the red is a mix of returned-True failures and an exception, as the order asked to be said.

**raw red, INCOMPLETE** (exit 1, 12 failed). The shell tool truncated the middle of this run's output ("[10958 characters truncated]" below is the tool's own marker, not an edit). What follows is exactly the output that was received, the head, the tail and the summary, nothing reconstructed. Redactions: `<repo>` for the worktree root; the `UV_NATIVE_TLS` warning line dropped. Because of the truncation, the individual failure messages of the cases between `[absent-author3]` and `[makers2-42]` were not received and are not claimed; the 12-case summary list at the end is complete.
```
FFFFFFFFFFFF                                                             [100%]
=================================== FAILURES ===================================
_ test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside[absent-None] _

author = None, makers = 'absent'

    @pytest.mark.parametrize("author", [None, "", 42, ["anthropic"]])
    @pytest.mark.parametrize("makers", ["absent", [], ["xai"]])
    def test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside(author, makers):
        # axis: an unknown author family leaves the maker set unprovable and keeps today's records — see bite-proof record wo_a_2530_single_vendor_panel
        m = _outside_panel()
        if makers != "absent":
            m["makerFamilies"] = makers
>       assert not SM.panel_outside_makers(m, author)
E       AssertionError: assert not True
E        +  where True = <function panel_outside_makers at 0x7f0515639f80>({'seats': {'code-reviewer': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', .......}}, 'roster': ['code-reviewer', 'security-reviewer', 'test-role', 'premortem-reviewer'], 'authorFamily': 'anthropic'}, None)
E        +    where <function panel_outside_makers at 0x7f0515639f80> = SM.panel_outside_makers

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4703: AssertionError
_ test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside[absent-] _

author = '', makers = 'absent'

    @pytest.mark.parametrize("author", [None, "", 42, ["anthropic"]])
    @pytest.mark.parametrize("makers", ["absent", [], ["xai"]])
    def test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside(author, makers):
        # axis: an unknown author family leaves the maker set unprovable and keeps today's records — see bite-proof record wo_a_2530_single_vendor_panel
        m = _outside_panel()
        if makers != "absent":
            m["makerFamilies"] = makers
>       assert not SM.panel_outside_makers(m, author)
E       AssertionError: assert not True
E        +  where True = <function panel_outside_makers at 0x7f0515639f80>({'seats': {'code-reviewer': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', .......}}, 'roster': ['code-reviewer', 'security-reviewer', 'test-role', 'premortem-reviewer'], 'authorFamily': 'anthropic'}, '')
E        +    where <function panel_outside_makers at 0x7f0515639f80> = SM.panel_outside_makers

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4703: AssertionError
_ test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside[absent-42] _

author = 42, makers = 'absent'

    @pytest.mark.parametrize("author", [None, "", 42, ["anthropic"]])
    @pytest.mark.parametrize("makers", ["absent", [], ["xai"]])
    def test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside(author, makers):
        # axis: an unknown author family leaves the maker set unprovable and keeps today's records — see bite-proof record wo_a_2530_single_vendor_panel
        m = _outside_panel()
        if makers != "absent":
            m["makerFamilies"] = makers
>       assert not SM.panel_outside_makers(m, author)
E       AssertionError: assert not True
E        +  where True = <function panel_outside_makers at 0x7f0515639f80>({'seats': {'code-reviewer': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', .......}}, 'roster': ['code-reviewer', 'security-reviewer', 'test-role', 'premortem-reviewer'], 'authorFamily': 'anthropic'}, 42)
E        +    where <function panel_outside_makers at 0x7f0515639f80> = SM.panel_outside_makers

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4703: AssertionError
_ test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside[absent-author3] _

author = ['anthropic'], makers = 'absent'

    @pytest.mark.parametrize("author", [None, "", 42, ["anthropic"]])
    @pytest.mark.parametrize("makers", ["absent", [], ["xai"]])
    def test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside(author, makers):
        # axis: an unknown author family leaves the maker set unprovable and keeps today's records — see bite-proof record wo_a_2530_single_vendor_panel
        m = _outside_panel()
        if makers != "absent":
            m["makerFamilies"] = makers
>       assert not SM.panel_outside_makers(m, author)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4703: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

seat_map = {'seats': {'code-reviewer': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', .......}}, 'roster': ['code-reviewer', 'security-reviewer',

... [10958 characters truncated] ...

ssertionError: assert not True
E        +  where True = <function panel_outside_makers at 0x7f0515639f80>({'seats': {'code-reviewer': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', .....iewer', 'security-reviewer', 'test-role', 'premortem-reviewer'], 'authorFamily': 'anthropic', 'makerFamilies': ['xai']}, 42)
E        +    where <function panel_outside_makers at 0x7f0515639f80> = SM.panel_outside_makers

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4703: AssertionError
_ test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside[makers2-author3] _

author = ['anthropic'], makers = ['xai']

    @pytest.mark.parametrize("author", [None, "", 42, ["anthropic"]])
    @pytest.mark.parametrize("makers", ["absent", [], ["xai"]])
    def test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside(author, makers):
        # axis: an unknown author family leaves the maker set unprovable and keeps today's records — see bite-proof record wo_a_2530_single_vendor_panel
        m = _outside_panel()
        if makers != "absent":
            m["makerFamilies"] = makers
>       assert not SM.panel_outside_makers(m, author)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4703: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

seat_map = {'seats': {'code-reviewer': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', .....iewer', 'security-reviewer', 'test-role', 'premortem-reviewer'], 'authorFamily': 'anthropic', 'makerFamilies': ['xai']}
author_family = ['anthropic']

    def panel_outside_makers(seat_map: dict, author_family: str | None) -> bool:
        """True when every filled seat of the panel is outside every maker's family, and at least one
        critical seat is filled (#2530). Independence is that the seats are outside the makers' families;
        a panel that shares one vendor or one family among them is not a critical-diversity breach.
    
        FAIL-CLOSED: every case this cannot prove returns False, which is today's behaviour — a map that
        is not a dict, seats that are not a dict, an unknown author family, a `makerFamilies` that is
        present but not a list of non-empty strings, a walked seat that is not a dict or whose family does
        not resolve, a seat in a maker's family, and a map with no filled critical seat. An unfilled seat
        is skipped here; `seat-unfilled` governs it. Callers pass the effective author family."""
        if not isinstance(seat_map, dict):
            return False
        seats = seat_map.get("seats")
        if not isinstance(seats, dict):
            return False
        # axis: an unknown author family leaves the maker set unprovable, so the panel is never exempt — see bite-proof record wo_a_2530_single_vendor_panel
        if not isinstance(author_family, str) or not author_family:
            pass
>       makers = {author_family}
                 ^^^^^^^^^^^^^^^

E       TypeError: unhashable type: 'list'

<repo>/plugins/superheroes/lib/seat_map.py:451: TypeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside[absent-None]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside[absent-]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside[absent-42]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside[absent-author3]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside[makers1-None]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside[makers1-]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside[makers1-42]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside[makers1-author3]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside[makers2-None]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside[makers2-]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside[makers2-42]
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_d_an_unknown_author_family_is_not_outside[makers2-author3]
12 failed in 1.42s
```

**restore:** the inverse text edit of the neutralization above (`pass` put back to `return False`; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored lines as they stand in the file, `seat_map.py:449-450`):
```
    if not isinstance(author_family, str) or not author_family:
        return False
```

**raw green** (after restore, all twelve cases, exit 0):
```
............                                                             [100%]
12 passed in 0.63s
```

---

## G8 — predicate unresolvable-family check (`seat_map.py` `panel_outside_makers`)

- **axis:** a walked seat whose family does not resolve (unknown vendor, no vendor, null vendor) cannot be proven outside the makers (E-e)

**neutralization** (`plugins/superheroes/lib/seat_map.py`, line 468-469):
```diff
--- before (restored text)
        if fam is None:
            return False
+++ neutralized
        if fam is None:
            pass
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/wo-a2-pyc -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_e_an_unresolvable_or_malformed_seat_is_not_outside -q
```

**raw red** (exit 1; complete, nothing truncated; the failure is the first case, an unknown vendor, returning True; `<repo>` and the dropped `UV_NATIVE_TLS` warning line are the only redactions):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_panel_outside_makers_edge_e_an_unresolvable_or_malformed_seat_is_not_outside _

    def test_panel_outside_makers_edge_e_an_unresolvable_or_malformed_seat_is_not_outside():
        # axis: a walked seat whose family does not resolve cannot be proven outside the makers — see bite-proof record wo_a_2530_single_vendor_panel
        unresolvable = {"vendor": "nosuchvendor", "model": "x", "effort": "high", "tier": "reviewer", "source": "rotated"}
        no_vendor = {"model": "x", "effort": "high", "tier": "reviewer", "source": "rotated"}
        null_vendor = {"vendor": None, "source": "rotated"}
        for bad in (unresolvable, no_vendor, null_vendor, "codex", 7, None, ["codex"]):
            for seat in ("test-role", "security-reviewer"):
                m = _outside_panel(**{seat: bad})
>               assert not SM.panel_outside_makers(m, "anthropic"), (seat, bad)
E               AssertionError: ('test-role', {'vendor': 'nosuchvendor', 'model': 'x', 'effort': 'high', 'tier': 'reviewer', ...})
E               assert not True
E                +  where True = <function panel_outside_makers at 0x7f58ec8d5f80>({'seats': {'code-reviewer': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', .......}}, 'roster': ['code-reviewer', 'security-reviewer', 'test-role', 'premortem-reviewer'], 'authorFamily': 'anthropic'}, 'anthropic')
E                +    where <function panel_outside_makers at 0x7f58ec8d5f80> = SM.panel_outside_makers

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4717: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_e_an_unresolvable_or_malformed_seat_is_not_outside
1 failed in 0.64s
```

**restore:** the inverse text edit of the neutralization above (`pass` put back to `return False`; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored lines, `seat_map.py:468-469`; the second `if fam is None:` in the file, at line 753, returns `None` and was never touched):
```
        if fam is None:
            return False
```

**raw green** (after restore, exit 0):
```
.                                                                        [100%]
1 passed in 0.55s
```

---

## G9 — predicate filled-critical-seat check (`seat_map.py` `panel_outside_makers`)

- **axis:** a map with no filled critical seat (all critical seats unfilled, absent, or not dicts) is governed by `seat-unfilled`, never exempt (E-f)

**neutralization** (`plugins/superheroes/lib/seat_map.py`, lines 474-477 collapsed to one line):
```diff
--- before (restored text)
    return any(
        s in seats and isinstance(seats[s], dict) and not is_unfilled(seats[s])
        for s in CRITICAL_SEATS
    )
+++ neutralized
    return True
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/wo-a2-pyc -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_f_no_filled_critical_seat_is_not_outside -q
```

**raw red** (exit 1; complete, nothing truncated; the failure is the all-unfilled-critical-seats case returning True; `<repo>` and the dropped `UV_NATIVE_TLS` warning line are the only redactions):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_panel_outside_makers_edge_f_no_filled_critical_seat_is_not_outside ____

    def test_panel_outside_makers_edge_f_no_filled_critical_seat_is_not_outside():
        # axis: a map with no filled critical seat is governed by seat-unfilled, never exempt — see bite-proof record wo_a_2530_single_vendor_panel
        unfilled = SM._unfilled_cfg("reviewer-deep")
        all_unfilled = _outside_panel(**{seat: dict(unfilled) for seat in SM.CRITICAL_SEATS})
>       assert not SM.panel_outside_makers(all_unfilled, "anthropic")
E       AssertionError: assert not True
E        +  where True = <function panel_outside_makers at 0x7f246d6620c0>({'seats': {'code-reviewer': {'vendor': None, 'model': None, 'effort': None, 'tier': 'reviewer-deep', ...}, 'security-r.....}}, 'roster': ['code-reviewer', 'security-reviewer', 'test-role', 'premortem-reviewer'], 'authorFamily': 'anthropic'}, 'anthropic')
E        +    where <function panel_outside_makers at 0x7f246d6620c0> = SM.panel_outside_makers

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4724: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_edge_f_no_filled_critical_seat_is_not_outside
1 failed in 0.65s
```

**restore:** the inverse text edit of the neutralization above (`return True` put back to the three-line `return any(...)` form; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored lines, `seat_map.py:474-477`):
```
    return any(
        s in seats and isinstance(seats[s], dict) and not is_unfilled(seats[s])
        for s in CRITICAL_SEATS
    )
```

**raw green** (after restore, exit 0):
```
.                                                                        [100%]
1 passed in 0.57s
```

---

# WO-C (#2530, advisor fix order from vet 952) — the exemption reads the session's whole maker set

**Provenance:** claude / sonnet-5.5 (implementer), `plugins/superheroes/lib/seat_map.py`, `plugins/superheroes/lib/seat_map_receipts.py`. Shape and ceilings: `plugins/superheroes/rubric/bite-proof.md`.

Declared guarded-element set (from the order): H1-H4. Each was neutralized by one targeted text edit of that one production line, the proving node(s) were run red, the neutralization was undone by the inverse text edit, and the same node(s) were run green. Redactions: the one `UV_NATIVE_TLS` deprecation warning line that `scripts/pinned-python` prints before every run is dropped; nothing else was edited. Every command ran from the worktree root through the pinned interpreter, with the shell tool's own timeout of 900000 ms and no pytest timeout flag:

```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/wo-c-pyc -m pytest <node ids> -q
```

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| H1 | `extra_makers` union inside `panel_outside_makers` (`seat_map.py`) | the session's other makers (a later map's omission, a replaced fixer's family) are makers of the exemption too | `test_round_driver.py::test_a_later_receipt_that_omits_an_earlier_maker_does_not_release_it_from_the_exemption`, `...::test_a_former_fixer_family_is_a_maker_for_the_exemption`, `test_seat_map.py::test_panel_outside_makers_extra_makers_are_makers_of_the_whole_session` |
| H2 | `pin_excused_records` threading (`seat_map_receipts.py`) | the pin-excused critical-diversity record reads the session's whole maker set | the two `test_round_driver.py` nodes above, `test_seat_map_receipts.py::test_state_level_pin_excused_records_read_the_sessions_makers` |
| H3 | state-level `unexcused_violations` threading (`seat_map_receipts.py`) | the unexcused critical-diversity record reads the session's whole maker set | `test_seat_map_receipts.py::test_state_level_unexcused_violations_read_the_sessions_former_fixer_family` (added by this order: neither `test_round_driver.py` node goes red here) |
| H4 | `emit_receipt_seat_map` threading at its `panel_outside_makers` call (`seat_map_receipts.py`) | the emitted seat map keeps a receipt's critical-diversity row when a session maker is in the panel's family | `test_seat_map_receipts.py::test_emit_receipt_seat_map_keeps_the_critical_diversity_row_when_a_former_fixer_is_a_maker` (added by this order) |

**Break-it run of the round-driver detectors against the unmodified `12a3c1b0` code** (production edits not yet made; exit 1; the two failures are the clean label `full-panel-confirmed` where `full-panel-confirmed-degraded` is asserted; the healthy and malformed-input tests pass, as they must on base):
```
FF..                                                                     [100%]
=================================== FAILURES ===================================
_ test_a_later_receipt_that_omits_an_earlier_maker_does_not_release_it_from_the_exemption _

    def test_a_later_receipt_that_omits_an_earlier_maker_does_not_release_it_from_the_exemption():
        # axis: the exemption reads the session's whole maker set, so a later map that leaves out a maker an
        # earlier one named still degrades an all-codex panel — see bite-proof record wo_a_2530_single_vendor_panel
        SM = _load("seat_map")
        latest = _legacy_pinned_single_vendor_map()
        earlier = _earlier_receipt_naming_openai()
        state, receipt = _certify_session([earlier, latest])
>       assert state["certification"]["shape"] == "full-panel-confirmed-degraded"
E       AssertionError: assert 'full-panel-confirmed' == 'full-panel-c...rmed-degraded'
E         
E         - full-panel-confirmed-degraded
E         ?                     ---------
E         + full-panel-confirmed

/home/user/wt-2530/plugins/superheroes/lib/tests/test_round_driver.py:3973: AssertionError
___________ test_a_former_fixer_family_is_a_maker_for_the_exemption ____________

    def test_a_former_fixer_family_is_a_maker_for_the_exemption():
        # axis: formerFixerFamilies joins the maker set the exemption reads — see bite-proof record wo_a_2530_single_vendor_panel
        stored = _legacy_pinned_single_vendor_map()
        state, receipt = _certify_session([stored], former_fixer_families=["openai"])
>       assert state["certification"]["shape"] == "full-panel-confirmed-degraded"
E       AssertionError: assert 'full-panel-confirmed' == 'full-panel-c...rmed-degraded'
E         
E         - full-panel-confirmed-degraded
E         ?                     ---------
E         + full-panel-confirmed

/home/user/wt-2530/plugins/superheroes/lib/tests/test_round_driver.py:3987: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_later_receipt_that_omits_an_earlier_maker_does_not_release_it_from_the_exemption
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_former_fixer_family_is_a_maker_for_the_exemption
2 failed, 2 passed in 1.76s
```

**Shape measured after the fix** (the detectors' own assertions, green): `state["certification"]["shape"] == "full-panel-confirmed-degraded"`, `shapeDrivers == ["seat-pin"]`, `independence == "independent"` (the `independence` field reads the separate `_degraded` channel, which `seat-pin` does not drive; this is the same as the existing `test_seat_map_pin_excusal_degraded_shape_and_disclosure` shape), for both shape (a) and shape (b). The healthy case reads `full-panel-confirmed`, `independence == "independent"`, `shapeDrivers == []`.

---

## H1 — `extra_makers` union (`seat_map.py` `panel_outside_makers`)

- **axis:** the session's other makers join the maker set the exemption reads

**neutralization** (`plugins/superheroes/lib/seat_map.py`, the line after the `makerFamilies` block, line 463):
```diff
--- before (restored text)
    makers.update(f for f in extra_makers if isinstance(f, str) and f)
+++ neutralized
    pass
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/wo-c-pyc -m pytest plugins/superheroes/lib/tests/test_round_driver.py::test_a_later_receipt_that_omits_an_earlier_maker_does_not_release_it_from_the_exemption plugins/superheroes/lib/tests/test_round_driver.py::test_a_former_fixer_family_is_a_maker_for_the_exemption plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_extra_makers_are_makers_of_the_whole_session -q
```

**raw red** (exit 1; complete, nothing truncated):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_a_later_receipt_that_omits_an_earlier_maker_does_not_release_it_from_the_exemption _

    def test_a_later_receipt_that_omits_an_earlier_maker_does_not_release_it_from_the_exemption():
        # axis: the exemption reads the session's whole maker set, so a later map that leaves out a maker an
        # earlier one named still degrades an all-codex panel — see bite-proof record wo_a_2530_single_vendor_panel
        SM = _load("seat_map")
        latest = _legacy_pinned_single_vendor_map()
        earlier = _earlier_receipt_naming_openai()
        state, receipt = _certify_session([earlier, latest])
>       assert state["certification"]["shape"] == "full-panel-confirmed-degraded"
E       AssertionError: assert 'full-panel-confirmed' == 'full-panel-c...rmed-degraded'
E         
E         - full-panel-confirmed-degraded
E         ?                     ---------
E         + full-panel-confirmed

/home/user/wt-2530/plugins/superheroes/lib/tests/test_round_driver.py:3973: AssertionError
___________ test_a_former_fixer_family_is_a_maker_for_the_exemption ____________

    def test_a_former_fixer_family_is_a_maker_for_the_exemption():
        # axis: formerFixerFamilies joins the maker set the exemption reads — see bite-proof record wo_a_2530_single_vendor_panel
        stored = _legacy_pinned_single_vendor_map()
        state, receipt = _certify_session([stored], former_fixer_families=["openai"])
>       assert state["certification"]["shape"] == "full-panel-confirmed-degraded"
E       AssertionError: assert 'full-panel-confirmed' == 'full-panel-c...rmed-degraded'
E         
E         - full-panel-confirmed-degraded
E         ?                     ---------
E         + full-panel-confirmed

/home/user/wt-2530/plugins/superheroes/lib/tests/test_round_driver.py:3988: AssertionError
____ test_panel_outside_makers_extra_makers_are_makers_of_the_whole_session ____

    def test_panel_outside_makers_extra_makers_are_makers_of_the_whole_session():
        # axis: the session's other makers join the maker set — see bite-proof record wo_a_2530_single_vendor_panel
        m = _outside_panel()
        assert SM.panel_outside_makers(m, "anthropic")
        assert SM.panel_outside_makers(m, "anthropic", extra_makers=())
>       assert not SM.panel_outside_makers(m, "anthropic", extra_makers={"openai"})
E       AssertionError: assert not True
E        +  where True = <function panel_outside_makers at 0x7f4a0b3dd120>({'seats': {'code-reviewer': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', .......}}, 'roster': ['code-reviewer', 'security-reviewer', 'test-role', 'premortem-reviewer'], 'authorFamily': 'anthropic'}, 'anthropic', extra_makers={'openai'})
E        +    where <function panel_outside_makers at 0x7f4a0b3dd120> = SM.panel_outside_makers

/home/user/wt-2530/plugins/superheroes/lib/tests/test_seat_map.py:4763: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_later_receipt_that_omits_an_earlier_maker_does_not_release_it_from_the_exemption
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_former_fixer_family_is_a_maker_for_the_exemption
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_panel_outside_makers_extra_makers_are_makers_of_the_whole_session
3 failed in 2.65s
```

**restore:** the inverse text edit of the neutralization above (`pass` put back to the `makers.update(...)` line; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored line, `seat_map.py:463`, under the `# axis:` comment on line 462):
```
    makers.update(f for f in extra_makers if isinstance(f, str) and f)
```

**raw green** (after restore, same command, exit 0):
```
...                                                                      [100%]
3 passed in 1.66s
```

---

## H2 — `pin_excused_records` threading (`seat_map_receipts.py`)

- **axis:** the pin-excused critical-diversity record (the `seat-pin` shape driver's source) reads the session's whole maker set

**neutralization** (`plugins/superheroes/lib/seat_map_receipts.py`, line 150):
```diff
--- before (restored text)
        classified = seat_map.classify_violations(entry["map"], driver_author_family, extra_makers=session_makers)
+++ neutralized
        classified = seat_map.classify_violations(entry["map"], driver_author_family, extra_makers=())
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/wo-c-pyc -m pytest plugins/superheroes/lib/tests/test_round_driver.py::test_a_later_receipt_that_omits_an_earlier_maker_does_not_release_it_from_the_exemption plugins/superheroes/lib/tests/test_round_driver.py::test_a_former_fixer_family_is_a_maker_for_the_exemption plugins/superheroes/lib/tests/test_seat_map_receipts.py::test_state_level_pin_excused_records_read_the_sessions_makers -q
```

**raw red** (exit 1; complete, nothing truncated; the two round-driver nodes fail on the same clean-label assertion as in H1, and the state-level detector fails on the empty pin-excused list):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_a_later_receipt_that_omits_an_earlier_maker_does_not_release_it_from_the_exemption _

    def test_a_later_receipt_that_omits_an_earlier_maker_does_not_release_it_from_the_exemption():
        # axis: the exemption reads the session's whole maker set, so a later map that leaves out a maker an
        # earlier one named still degrades an all-codex panel — see bite-proof record wo_a_2530_single_vendor_panel
        SM = _load("seat_map")
        latest = _legacy_pinned_single_vendor_map()
        earlier = _earlier_receipt_naming_openai()
        state, receipt = _certify_session([earlier, latest])
>       assert state["certification"]["shape"] == "full-panel-confirmed-degraded"
E       AssertionError: assert 'full-panel-confirmed' == 'full-panel-c...rmed-degraded'
E         
E         - full-panel-confirmed-degraded
E         ?                     ---------
E         + full-panel-confirmed

/home/user/wt-2530/plugins/superheroes/lib/tests/test_round_driver.py:3973: AssertionError
___________ test_a_former_fixer_family_is_a_maker_for_the_exemption ____________

    def test_a_former_fixer_family_is_a_maker_for_the_exemption():
        # axis: formerFixerFamilies joins the maker set the exemption reads — see bite-proof record wo_a_2530_single_vendor_panel
        stored = _legacy_pinned_single_vendor_map()
        state, receipt = _certify_session([stored], former_fixer_families=["openai"])
>       assert state["certification"]["shape"] == "full-panel-confirmed-degraded"
E       AssertionError: assert 'full-panel-confirmed' == 'full-panel-c...rmed-degraded'
E         
E         - full-panel-confirmed-degraded
E         ?                     ---------
E         + full-panel-confirmed

/home/user/wt-2530/plugins/superheroes/lib/tests/test_round_driver.py:3988: AssertionError
________ test_state_level_pin_excused_records_read_the_sessions_makers _________

    def test_state_level_pin_excused_records_read_the_sessions_makers():
        stored = _stored_outside_makers_map()
        assert not _has_critical_diversity(SMR.pin_excused_records(_session_state([stored]), "anthropic"))
        for state in (
            _session_state([stored], former_fixer_families=["openai"]),
            _session_state([dict(stored, makerFamilies=["anthropic", "openai"]), stored]),
        ):
>           assert _has_critical_diversity(SMR.pin_excused_records(state, "anthropic"))
E           AssertionError: assert False
E            +  where False = _has_critical_diversity([])
E            +    where [] = <function pin_excused_records at 0x7efe74105d00>({'seatMapReceipts': [{'round': '1', 'map': {'seats': {'test-role': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort...t spanned ≥2 families'}], 'seed': 0, 'liveVendors': ['codex'], ...}}], 'rounds': {}, 'formerFixerFamilies': ['openai']}, 'anthropic')
E            +      where <function pin_excused_records at 0x7efe74105d00> = SMR.pin_excused_records

/home/user/wt-2530/plugins/superheroes/lib/tests/test_seat_map_receipts.py:532: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_later_receipt_that_omits_an_earlier_maker_does_not_release_it_from_the_exemption
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_former_fixer_family_is_a_maker_for_the_exemption
FAILED plugins/superheroes/lib/tests/test_seat_map_receipts.py::test_state_level_pin_excused_records_read_the_sessions_makers
3 failed in 1.65s
```

**restore:** the inverse text edit of the neutralization above (`extra_makers=()` put back to `extra_makers=session_makers`; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored line, `seat_map_receipts.py:150`):
```
        classified = seat_map.classify_violations(entry["map"], driver_author_family, extra_makers=session_makers)
```

**raw green** (after restore, same command, exit 0):
```
...                                                                      [100%]
3 passed in 1.39s
```

---

## H3 — state-level `unexcused_violations` threading (`seat_map_receipts.py`)

- **axis:** the unexcused critical-diversity record reads the session's whole maker set

**neutralization** (`plugins/superheroes/lib/seat_map_receipts.py`, line 137):
```diff
--- before (restored text)
        for v in seat_map.unexcused_violations(entry["map"], driver_author_family, extra_makers=session_makers):
+++ neutralized
        for v in seat_map.unexcused_violations(entry["map"], driver_author_family, extra_makers=()):
```

**Which detector goes red, measured.** Run with the two round-driver nodes (T-a, T-b) alongside the detector this order added for H3: only the added detector goes red. T-a and T-b stay green because their maps are pinned with a submitted `critical-diversity` record, which `classify_violations` excuses by pin (an H2 path), so the state-level unexcused projection never carries it. The order's own rule applies: none of the existing detectors bites H3, so the added one is the proof. It uses an unpinned all-codex map with no submitted violation, so the session maker (openai, from `formerFixerFamilies`, or from an earlier receipt) makes `critical-diversity` DERIVED, and a derived record is never excused.

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/wo-c-pyc -m pytest plugins/superheroes/lib/tests/test_round_driver.py::test_a_later_receipt_that_omits_an_earlier_maker_does_not_release_it_from_the_exemption plugins/superheroes/lib/tests/test_round_driver.py::test_a_former_fixer_family_is_a_maker_for_the_exemption plugins/superheroes/lib/tests/test_seat_map_receipts.py::test_state_level_unexcused_violations_read_the_sessions_former_fixer_family -q
```

**raw red** (exit 1; complete, nothing truncated; `..F`: the two round-driver nodes pass, the added detector fails):
```
..F                                                                      [100%]
=================================== FAILURES ===================================
_ test_state_level_unexcused_violations_read_the_sessions_former_fixer_family __

    def test_state_level_unexcused_violations_read_the_sessions_former_fixer_family():
        # axis: the state-level unexcused projection judges a map against the session's whole maker set — see bite-proof record wo_a_2530_single_vendor_panel
        m = _unpinned_all_codex_map()
        assert seat_map.panel_outside_makers(m, "anthropic")
        assert not _has_critical_diversity(SMR.unexcused_violations(_session_state([m]), "anthropic"))
        # an openai fixer a session upgrade replaced is still a maker: the all-codex panel is in its family
        state = _session_state([m], former_fixer_families=["openai"])
        unexcused = SMR.unexcused_violations(state, "anthropic")
>       assert _has_critical_diversity(unexcused)
E       assert False
E        +  where False = _has_critical_diversity([])

/home/user/wt-2530/plugins/superheroes/lib/tests/test_seat_map_receipts.py:518: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map_receipts.py::test_state_level_unexcused_violations_read_the_sessions_former_fixer_family
1 failed, 2 passed in 1.41s
```

**restore:** the inverse text edit of the neutralization above (`extra_makers=()` put back to `extra_makers=session_makers`; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored line, `seat_map_receipts.py:137`):
```
        for v in seat_map.unexcused_violations(entry["map"], driver_author_family, extra_makers=session_makers):
```

**raw green** (after restore, the added detector alone, exit 0):
```
.                                                                        [100%]
1 passed in 0.22s
```

---

## H4 — `emit_receipt_seat_map` threading (`seat_map_receipts.py`)

- **axis:** the emitted seat map keeps a receipt's critical-diversity row and violation when a session maker is in the panel's family

**neutralization** (`plugins/superheroes/lib/seat_map_receipts.py`, line 282, the `panel_outside_makers` call's third argument):
```diff
--- before (restored text)
            entry["map"], seat_map.effective_author_family(entry["map"], driver_author_family), session_makers,
+++ neutralized
            entry["map"], seat_map.effective_author_family(entry["map"], driver_author_family), (),
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/wo-c-pyc -m pytest plugins/superheroes/lib/tests/test_seat_map_receipts.py::test_emit_receipt_seat_map_keeps_the_critical_diversity_row_when_a_former_fixer_is_a_maker -q
```

**raw red** (exit 1; complete, nothing truncated; the dropped row is the failure):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_emit_receipt_seat_map_keeps_the_critical_diversity_row_when_a_former_fixer_is_a_maker _

    def test_emit_receipt_seat_map_keeps_the_critical_diversity_row_when_a_former_fixer_is_a_maker():
        # axis: the emitted seat map judges each receipt against the session's whole maker set — see bite-proof record wo_a_2530_single_vendor_panel
        stored = _stored_outside_makers_map()
        healthy = SMR.emit_receipt_seat_map(_session_state([stored]), "anthropic")
        assert not _has_critical_diversity(healthy.get("degradations"))
        assert not _has_critical_diversity(healthy.get("violations"))
        for state in (
            _session_state([stored], former_fixer_families=["openai"]),
            _session_state([dict(stored, makerFamilies=["anthropic", "openai"]), stored]),
        ):
            emitted = SMR.emit_receipt_seat_map(state, "anthropic")
>           assert _CRITICAL_DIVERSITY_ROW in emitted["degradations"]
E           AssertionError: assert {'constraint': 'critical-diversity', 'reason': 'relaxed critical-diversity — no assignment spanned ≥2 families'} in []

/home/user/wt-2530/plugins/superheroes/lib/tests/test_seat_map_receipts.py:547: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map_receipts.py::test_emit_receipt_seat_map_keeps_the_critical_diversity_row_when_a_former_fixer_is_a_maker
1 failed in 0.26s
```

**restore:** the inverse text edit of the neutralization above (`(),` put back to `session_makers,`; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored line, `seat_map_receipts.py:282`):
```
            entry["map"], seat_map.effective_author_family(entry["map"], driver_author_family), session_makers,
```

**raw green** (after restore, exit 0):
```
.                                                                        [100%]
1 passed in 0.23s
```

---

## Threaded without a guarded element of its own

`same_family_seats` (`seat_map_receipts.py`) passes `extra_makers=session_makers` too, as the order lists, but the one thing it reads from `unexcused_violations` is the `maker-family` constraint, and `extra_makers` only changes whether `critical-diversity` is dropped, so the threading there changes no output and no test can tell it from `extra_makers=()`. **Unprovable as placed**: it is unproven and carries no protection claim; it becomes provable only if `extra_makers` ever reaches the `maker-family` rule. `test_same_family_seats_reads_a_session_with_a_former_fixer_without_error` only proves the call does not raise.

---

# WO-D2 (#2530, advisor fix order from vet 953) — the review-fix union in the liveness excusal is withdrawn

The review-fix change at `d96a92a5` added the session's makers to `classify_violations`' liveness `maker_set`. Vet 953 measured that it makes an unpinned all-codex panel with a recorded `critical-diversity` read `full-panel-confirmed` (cleaner than base) when live alternatives are proven, and the advisor ruled that union withdrawn. The line is removed again; the element below guards its absence.

## J1 — the absence of session makers in `classify_violations`' liveness `maker_set` (`seat_map.py` `classify_violations`)

- **axis:** `classify_violations`' liveness excusal counts only the map's own `makerFamilies` and the author family as makers, so the session's other makers (`extra_makers`) never turn a live alternative into an excused one; with live alternatives proven, no variant of shapes a and b reads cleaner than base

**neutralization** (`plugins/superheroes/lib/seat_map.py`, directly after `maker_set.add(author_family)`, line 1284): the two lines removed by this order are put back exactly as at `d96a92a5`:
```diff
--- before (restored text)
        maker_set.add(author_family)
        achievable: set[str] | None = set()
+++ neutralized
        maker_set.add(author_family)
        # axis: the session's other makers are makers in the excusal arithmetic too, never live alternatives — see bite-proof record wo_a_2530_single_vendor_panel
        maker_set.update(f for f in extra_makers if isinstance(f, str) and f)
        achievable: set[str] | None = set()
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/wo-d2-pyc -m pytest plugins/superheroes/lib/tests/test_round_driver.py -k "reads_constraint_violated_for_unpinned_seats or no_variant_of_the_two_shapes" -q
```

**raw red** (exit 1; complete, nothing truncated; both unpinned tests and the matrix's `a-False-True` and `b-False-True` rows read `full-panel-confirmed`):
```
FF..F...F.                                                               [100%]
=================================== FAILURES ===================================
_ test_a_later_receipt_that_omits_an_earlier_maker_reads_constraint_violated_for_unpinned_seats _

    def test_a_later_receipt_that_omits_an_earlier_maker_reads_constraint_violated_for_unpinned_seats():
        # axis: the liveness excusal never reads the session's makers out of the live alternatives, so a
        # recorded critical-diversity on unpinned seats is no cleaner than base — see bite-proof record
        # wo_a_2530_single_vendor_panel (J1)
>       assert _single_vendor_shape("a", pinned=False, recorded=True) == "full-panel-confirmed-constraint-violated"
E       AssertionError: assert 'full-panel-confirmed' == 'full-panel-c...aint-violated'
E         
E         - full-panel-confirmed-constraint-violated
E         + full-panel-confirmed

/home/user/wt-2530/plugins/superheroes/lib/tests/test_round_driver.py:4050: AssertionError
___ test_a_former_fixer_family_reads_constraint_violated_for_unpinned_seats ____

    def test_a_former_fixer_family_reads_constraint_violated_for_unpinned_seats():
        # axis: same as above, for the maker held in formerFixerFamilies — see bite-proof record
        # wo_a_2530_single_vendor_panel (J1)
>       assert _single_vendor_shape("b", pinned=False, recorded=True) == "full-panel-confirmed-constraint-violated"
E       AssertionError: assert 'full-panel-confirmed' == 'full-panel-c...aint-violated'
E         
E         - full-panel-confirmed-constraint-violated
E         + full-panel-confirmed

/home/user/wt-2530/plugins/superheroes/lib/tests/test_round_driver.py:4056: AssertionError
_ test_no_variant_of_the_two_shapes_reads_cleaner_than_base[a-False-True-full-panel-confirmed-constraint-violated] _

shape = 'a', pinned = False, recorded = True
base_shape = 'full-panel-confirmed-constraint-violated'

    (parametrize decorator with the 8 rows, repeated verbatim in pytest's output, elided here)
    def test_no_variant_of_the_two_shapes_reads_cleaner_than_base(shape, pinned, recorded, base_shape):
        # axis: with live alternatives proven, no variant of shape a or b (pinned or not, recorded or not)
        # certifies cleaner than the base commit does — see bite-proof record wo_a_2530_single_vendor_panel (J1)
>       assert _single_vendor_shape(shape, pinned, recorded) == base_shape
E       AssertionError: assert 'full-panel-confirmed' == 'full-panel-c...aint-violated'
E         
E         - full-panel-confirmed-constraint-violated
E         + full-panel-confirmed

/home/user/wt-2530/plugins/superheroes/lib/tests/test_round_driver.py:4075: AssertionError
_ test_no_variant_of_the_two_shapes_reads_cleaner_than_base[b-False-True-full-panel-confirmed-constraint-violated] _

shape = 'b', pinned = False, recorded = True
base_shape = 'full-panel-confirmed-constraint-violated'

    (parametrize decorator with the 8 rows, repeated verbatim in pytest's output, elided here)
    def test_no_variant_of_the_two_shapes_reads_cleaner_than_base(shape, pinned, recorded, base_shape):
        # axis: with live alternatives proven, no variant of shape a or b (pinned or not, recorded or not)
        # certifies cleaner than the base commit does — see bite-proof record wo_a_2530_single_vendor_panel (J1)
>       assert _single_vendor_shape(shape, pinned, recorded) == base_shape
E       AssertionError: assert 'full-panel-confirmed' == 'full-panel-c...aint-violated'
E         
E         - full-panel-confirmed-constraint-violated
E         + full-panel-confirmed

/home/user/wt-2530/plugins/superheroes/lib/tests/test_round_driver.py:4075: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_later_receipt_that_omits_an_earlier_maker_reads_constraint_violated_for_unpinned_seats
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_former_fixer_family_reads_constraint_violated_for_unpinned_seats
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_no_variant_of_the_two_shapes_reads_cleaner_than_base[a-False-True-full-panel-confirmed-constraint-violated]
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_no_variant_of_the_two_shapes_reads_cleaner_than_base[b-False-True-full-panel-confirmed-constraint-violated]
4 failed, 6 passed, 413 deselected in 1.91s
```
(The only elision is the 8-row `parametrize` decorator that pytest echoes inside each of the two matrix failures; the failing lines, assertions and the summary are verbatim.)

**restore:** the inverse text edit of the neutralization above (the `# axis:` comment and the `maker_set.update(...)` line removed again; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored lines, `seat_map.py:1284-1285`):
```
        maker_set.add(author_family)
        achievable: set[str] | None = set()
```

**raw green** (after restore, exit 0):
```
..........                                                               [100%]
10 passed, 413 deselected in 1.67s
```

(end of record)
