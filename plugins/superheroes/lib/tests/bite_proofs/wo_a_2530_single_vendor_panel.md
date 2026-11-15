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

(end of record)
