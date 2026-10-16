# WO-B (#1797) bite-proof — seat orders carry the brief, the threat model and the standing rulings; non-panel seats sit outside the makers; the panel follows the roster

**Provenance:** claude / sonnet-5.5 (implementer), WO-B4. Production surface: `plugins/superheroes/lib/round_driver.py`, `round_orders.py`, `receipt_disclosures.py`. Detectors: `lib/tests/test_seat_order_blocks_1797.py`, `test_nonpanel_independence_1797.py`, `test_round_driver_order_channel.py`.

Declared guarded-element set (WO-B H1-H7, WO-B2 H8): H1-H8 below. Each was neutralized by a targeted text edit in production code only, the single proving node was run red with the detector unedited, the neutralization was undone by the inverse text edit (never `git checkout`, `git restore`, `git reset` or `git stash`), and the same node was run green. Redaction: pytest temp roots appear as `<tmp>` and the worktree root as `<repo>`; nothing else was edited or elided. The fixed fixture path `/tmp/rd1035-census/...` inside rendered orders is a literal in the test fixture, not a temp root, and is left as printed.

Single-node runs never carry the sandbox `--deselect` string (none of the proving nodes is in that list). Every node ran in the sandbox; none touched a throwaway git commit.

## Guarded elements

| ID | Guarded element | Axis | Proving node |
|---|---|---|---|
| H1 | `ROLE_BRIEF_SEATS` covers every lens (`round_driver.py` L110) | a lens seat's panel order dropping its own absolute brief path | `test_seat_order_blocks_1797.py::test_panel_order_names_each_lens_seats_brief_on_both_channels[security-reviewer-host-file]` |
| H2 | threat-model block appended to every phase (`round_orders.py` `render_order`, `blocks` list) | the threat-model block missing from one phase's order | `test_seat_order_blocks_1797.py::test_threat_model_block_on_every_phase[dispatch-verifiers-host-file]` |
| H3 | standing-rulings block appended to every phase (`round_orders.py` `render_order`, `blocks` list) | the standing-rulings block missing from one phase's order | `test_seat_order_blocks_1797.py::test_standing_rulings_block_on_every_phase[dispatch-verifiers-host-file]` |
| H4 | `{{` escaping of both quoted-data blocks (`round_orders.py` `format_threat_model_block`, `format_rulings_block`) | an unescaped double-brace token in owner prose trips the renderer's placeholder refusal | `test_seat_order_blocks_1797.py::test_double_brace_in_threat_model_and_rulings_is_escaped_not_refused[dispatch-verifiers]` |
| H5 | `independent_reviewer` bars maker families (`receipt_disclosures.py` L209) | a candidate whose reviewer family is a maker's is never chosen | `test_nonpanel_independence_1797.py::test_independent_reviewer_bars_maker_families` |
| H6 | an unseatable non-panel seat gets no order (`round_driver.py` `_emit_orders_manifest`, L8728) | every slot of the phase is skipped, so the manifest holds no seat | `test_nonpanel_independence_1797.py::test_unseatable_nonpanel_seat_gets_no_order_and_a_missing_record` |
| H7 | panel dimensions follow the seeded seat map's roster (`round_driver.py` `_default_config`, L1173) | the default dimensions are the roster's lens seats, not all five | `test_seat_order_blocks_1797.py::test_panel_dimensions_follow_the_seeded_seat_map_roster_in_dimensions_order` |
| H8 | a replaced defaulted reviewer vendor keeps `defaulted` (`round_driver.py` `_nonpanel_reviewer_vendor`, L7727) | the provenance gap is still disclosed when B5 replaces a defaulted vendor | `test_round_driver_order_channel.py::test_a_defaulted_reviewer_vendor_is_disclosed_not_merely_made_safe[dispatch-verifiers]` |

## Disclosures

- **H4 is two neutralizations.** The escape sits at two call sites. Run order: threat-model escape neutralized, red; inverse edit; rulings escape neutralized, red; inverse edit; one green after both were restored. The shared green covers both restores (the node asserts both blocks); the first restore is also shown by the quoted line and the hash comparison.
- **Equivalence classes by phase and seat.** H2 and H3 each have one append site for all phases (`blocks` list in `render_order`); the neutralization skips one phase (`dispatch-verifiers`, representative of the class "the block is missing from a phase's order"). The census tests parametrize every phase in `ORDER_PHASES` and both channels, but only the representative node was run red. Other phases are not separately neutralized and are listed as unproven. H1's representative seat is `security-reviewer` (the set is derived from `AGENT_SUFFIX`; other lens seats are not separately neutralized, and the engine-stdout channel was not run red). H8's representative phase is `dispatch-verifiers` (`dispatch-gap-sweep` and `dispatch-scoped-finder` share the one edited site).
- **Not separately neutralized (listed as unproven):** in `independent_reviewer`, the fixer-family addition to the barred set (`barred.add(fixer_fam)`) and the `v == fixer_vendor` skip; the `_nonpanel_reviewer_vendor` consumer of `independent_reviewer` (H5 is proven at the helper, as the order declared it); the `P_PANEL` branch of `unfilled`; `VENDOR_SOURCE_INDEPENDENT` being treated as resolved by `_vendor_is_resolved`.
- **H6 red shape:** the neutralization keeps the slot's order instead of skipping it, so the manifest holds a seat. The red is the first assertion (`manifest["seats"] == {}`), which is the axis (no order for the unseatable seat).
- **Detectors unedited.** The only test-file edit made for this record is one axis comment line added to the H8 detector (`test_round_driver_order_channel.py`, after the docstring). The test body and assertions are unchanged.
- **Restore receipts.** The neutralized line is quoted back as it stands after the inverse edit, `git diff --stat` over the three production files is empty, and sha256 of each is compared with the value taken before the first neutralization.

sha256 before the first neutralization, and after every restore (identical each time):
```
29199b81940ec9284cb94301f9398210afecd56092343fd954ac96fbb1389b64  plugins/superheroes/lib/round_driver.py
7fe1d3614f7351e11727c78617d2680bddc12ce584ab55981cf02bdf8ab9b986  plugins/superheroes/lib/round_orders.py
da417f584d5ba211e2c874506190e51a0d89c754511af528991b73a20a03ed96  plugins/superheroes/lib/receipt_disclosures.py
```

---

## H1 — `ROLE_BRIEF_SEATS` covers every lens (`round_driver.py` L110)

- **axis:** a lens seat's panel order dropping its own absolute brief path

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
--- before (restored text)
ROLE_BRIEF_SEATS = frozenset(AGENT_SUFFIX)
+++ neutralized
ROLE_BRIEF_SEATS = frozenset(AGENT_SUFFIX) - {"security-reviewer"}
```

**command:**
```
python3 -B -m pytest "plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py::test_panel_order_names_each_lens_seats_brief_on_both_channels[security-reviewer-host-file]" -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_panel_order_names_each_lens_seats_brief_on_both_channels[security-reviewer-host-file] _

seat = 'security-reviewer', host_seat = True

    @pytest.mark.parametrize("host_seat", [True, False], ids=["host-file", "engine-stdout"])
    @pytest.mark.parametrize("seat", sorted(RD.AGENT_SUFFIX))
    def test_panel_order_names_each_lens_seats_brief_on_both_channels(seat, host_seat):
        # axis: a lens seat's panel order dropping its own absolute brief path, per channel —
        # see bite-proof record wo_b_1797_seat_orders
        text = _render(RD.P_PANEL, host_seat, seat=seat, brief_for=seat)
        expected = _ROLE_BRIEF_PREFIX + RD._role_brief_path(seat)
>       assert expected in text.splitlines(), seat
E       AssertionError: security-reviewer
E       assert '- Your role brief (read it first; it binds over the generic assignment above): ' in ['You are reviewing branch for repo r, target t.', 'Review session mode branch (from session metadata).', '', '## Your...nd-1/diff.txt for your dimension.', 'Read `diff.txt` in bounded chunks (<=800 lines): use Read offset/limit when', ...]
E        +  where ['You are reviewing branch for repo r, target t.', 'Review session mode branch (from session metadata).', '', '## Your...nd-1/diff.txt for your dimension.', 'Read `diff.txt` in bounded chunks (<=800 lines): use Read offset/limit when', ...] = <built-in method splitlines of str object at 0x190e6b50>()
E        +    where <built-in method splitlines of str object at 0x190e6b50> = 'You are reviewing branch for repo r, target t.\nReview session mode branch (from session metadata).\n\n## Your assign... no envelope header, no stub copy.\n\n- Payload landing path: /tmp/rd1035-census/round-1/landing/p/skey.a1.bare.json\n'.splitlines

<repo>/plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py:85: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py::test_panel_order_names_each_lens_seats_brief_on_both_channels[security-reviewer-host-file]
1 failed in 0.35s
red exit: 1
```

**restore:** the inverse text edit of the neutralization above (the "before" text put back).

**restore receipt** (restored text as it stands in `round_driver.py`; `git diff --stat` empty):
```
110:ROLE_BRIEF_SEATS = frozenset(AGENT_SUFFIX)
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 1.47s
green exit: 0
```

---

## H2 — threat-model block appended to every phase (`round_orders.py` `render_order`)

- **axis:** the threat-model block missing from one phase's order

**neutralization** (`plugins/superheroes/lib/round_orders.py`, skip the block for `dispatch-verifiers`):
```diff
--- before (restored text)
                  format_threat_model_block(context).rstrip(),
+++ neutralized
                  ("" if phase == round_phases.P_VERIFIERS else format_threat_model_block(context).rstrip()),
```

**command:**
```
python3 -B -m pytest "plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py::test_threat_model_block_on_every_phase[dispatch-verifiers-host-file]" -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_threat_model_block_on_every_phase[dispatch-verifiers-host-file] _____

phase = 'dispatch-verifiers', host_seat = True

    @pytest.mark.parametrize("host_seat", [True, False], ids=["host-file", "engine-stdout"])
    @pytest.mark.parametrize("phase", RO.ORDER_PHASES)
    def test_threat_model_block_on_every_phase(phase, host_seat):
        # axis: the threat-model block missing from one phase's order — see bite-proof record
        # wo_b_1797_seat_orders
        text = _render(phase, host_seat, threat_model="Attackers can forge session cookies.")
>       assert ("## Project threat model (project calibration, quoted data)\n\n-----\n"
                "Attackers can forge session cookies.\n-----") in text, phase
E       AssertionError: dispatch-verifiers
E       assert '## Project threat model (project calibration, quoted data)\n\n-----\nAttackers can forge session cookies.\n-----' in 'You are the per-finding verifier for one cluster of a review panel. You are given a\nCLUSTER of merged issues (duplic... no envelope header, no stub copy.\n\n- Payload landing path: /tmp/rd1035-census/round-1/landing/p/skey.a1.bare.json\n'

<repo>/plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py:96: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py::test_threat_model_block_on_every_phase[dispatch-verifiers-host-file]
1 failed in 1.46s
red exit: 1
```

**restore:** the inverse text edit (the "before" line put back).

**restore receipt** (`round_orders.py` L589-591 as restored; `git diff --stat` empty):
```
        blocks = [body.rstrip(), _format_residual_block(context).rstrip(),
                  format_threat_model_block(context).rstrip(),
                  format_rulings_block(context).rstrip()]
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.16s
green exit: 0
```

---

## H3 — standing-rulings block appended to every phase (`round_orders.py` `render_order`)

- **axis:** the standing-rulings block missing from one phase's order

**neutralization** (`plugins/superheroes/lib/round_orders.py`, skip the block for `dispatch-verifiers`):
```diff
--- before (restored text)
                  format_rulings_block(context).rstrip()]
+++ neutralized
                  ("" if phase == round_phases.P_VERIFIERS else format_rulings_block(context).rstrip())]
```

**command:**
```
python3 -B -m pytest "plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py::test_standing_rulings_block_on_every_phase[dispatch-verifiers-host-file]" -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_standing_rulings_block_on_every_phase[dispatch-verifiers-host-file] ___

phase = 'dispatch-verifiers', host_seat = True

    @pytest.mark.parametrize("host_seat", [True, False], ids=["host-file", "engine-stdout"])
    @pytest.mark.parametrize("phase", RO.ORDER_PHASES)
    def test_standing_rulings_block_on_every_phase(phase, host_seat):
        # axis: the standing-rulings block missing from one phase's order — see bite-proof record
        # wo_b_1797_seat_orders
        text = _render(phase, host_seat, standing_rulings=[
            {"findingKey": "src/a.py:Edge case", "reason": "owner deferred it to the next milestone"}])
>       assert "## Standing rulings (recorded this session, quoted data)" in text, phase
E       AssertionError: dispatch-verifiers
E       assert '## Standing rulings (recorded this session, quoted data)' in 'You are the per-finding verifier for one cluster of a review panel. You are given a\nCLUSTER of merged issues (duplic... no envelope header, no stub copy.\n\n- Payload landing path: /tmp/rd1035-census/round-1/landing/p/skey.a1.bare.json\n'

<repo>/plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py:168: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py::test_standing_rulings_block_on_every_phase[dispatch-verifiers-host-file]
1 failed in 0.17s
red exit: 1
```

**restore:** the inverse text edit (the "before" line put back).

**restore receipt** (`round_orders.py` L589-591 as restored; `git diff --stat` empty):
```
        blocks = [body.rstrip(), _format_residual_block(context).rstrip(),
                  format_threat_model_block(context).rstrip(),
                  format_rulings_block(context).rstrip()]
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.16s
green exit: 0
```

---

## H4 — `{{` escaping of both quoted-data blocks (`round_orders.py`)

- **axis:** an unescaped double-brace token in owner prose trips the renderer's placeholder refusal (`post-condition-placeholder-leak`) instead of rendering

### H4a — threat-model escape

**neutralization** (`plugins/superheroes/lib/round_orders.py` `format_threat_model_block`):
```diff
--- before (restored text)
        lines.extend(["-----", escape_placeholder_syntax(text.strip()), "-----"])
+++ neutralized
        lines.extend(["-----", text.strip(), "-----"])
```

**command:**
```
python3 -B -m pytest "plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py::test_double_brace_in_threat_model_and_rulings_is_escaped_not_refused[dispatch-verifiers]" -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_double_brace_in_threat_model_and_rulings_is_escaped_not_refused[dispatch-verifiers] _

phase = 'dispatch-verifiers'

    @pytest.mark.parametrize("phase", RO.ORDER_PHASES)
    def test_double_brace_in_threat_model_and_rulings_is_escaped_not_refused(phase):
        # axis: the double-brace escape on BOTH quoted-data blocks (an unescaped token trips the
        # renderer's unfilled-placeholder refusal) — see bite-proof record wo_b_1797_seat_orders
>       text = _render(phase, True, threat_model="Never trust %s ever." % _TOKEN,
                       standing_rulings=[{"findingKey": "k-%s" % _TOKEN,
                                          "reason": "reason with %s inside" % _TOKEN}])

<repo>/plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py:125: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

phase = 'dispatch-verifiers', host_seat = True, seat = 'seat', brief_for = None
ctx_extra = {'threat_model': 'Never trust {{ROUND}} ever.', 'standing_rulings': [{'findingKey': 'k-{{ROUND}}', 'reason': 'reason with {{ROUND}} inside'}]}

    def _render(phase, host_seat, seat="seat", brief_for=None, **ctx_extra):
        text, reason = RO.render_order(phase, seat, _context(phase, host_seat, brief_for, **ctx_extra))
>       assert reason is None, (phase, host_seat, reason)
E       AssertionError: ('dispatch-verifiers', True, 'post-condition-placeholder-leak')
E       assert 'post-condition-placeholder-leak' is None

<repo>/plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py:55: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py::test_double_brace_in_threat_model_and_rulings_is_escaped_not_refused[dispatch-verifiers]
1 failed in 0.18s
red exit (H4a threat-model escape): 1
```

**restore:** the inverse text edit (the "before" line put back) before H4b was applied.

### H4b — rulings escape (H4a already restored)

**neutralization** (`plugins/superheroes/lib/round_orders.py` `format_rulings_block`):
```diff
--- before (restored text)
            lines.append(escape_placeholder_syntax(
                "- %s: out of scope — %s" % (key, reason or "(no reason recorded)")))
+++ neutralized
            lines.append(
                "- %s: out of scope — %s" % (key, reason or "(no reason recorded)"))
```

**command:** the same node as H4a.

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_double_brace_in_threat_model_and_rulings_is_escaped_not_refused[dispatch-verifiers] _

phase = 'dispatch-verifiers'

    @pytest.mark.parametrize("phase", RO.ORDER_PHASES)
    def test_double_brace_in_threat_model_and_rulings_is_escaped_not_refused(phase):
        # axis: the double-brace escape on BOTH quoted-data blocks (an unescaped token trips the
        # renderer's unfilled-placeholder refusal) — see bite-proof record wo_b_1797_seat_orders
>       text = _render(phase, True, threat_model="Never trust %s ever." % _TOKEN,
                       standing_rulings=[{"findingKey": "k-%s" % _TOKEN,
                                          "reason": "reason with %s inside" % _TOKEN}])

<repo>/plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py:125: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

phase = 'dispatch-verifiers', host_seat = True, seat = 'seat', brief_for = None
ctx_extra = {'threat_model': 'Never trust {{ROUND}} ever.', 'standing_rulings': [{'findingKey': 'k-{{ROUND}}', 'reason': 'reason with {{ROUND}} inside'}]}

    def _render(phase, host_seat, seat="seat", brief_for=None, **ctx_extra):
        text, reason = RO.render_order(phase, seat, _context(phase, host_seat, brief_for, **ctx_extra))
>       assert reason is None, (phase, host_seat, reason)
E       AssertionError: ('dispatch-verifiers', True, 'post-condition-placeholder-leak')
E       assert 'post-condition-placeholder-leak' is None

<repo>/plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py:55: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py::test_double_brace_in_threat_model_and_rulings_is_escaped_not_refused[dispatch-verifiers]
1 failed in 0.17s
red exit (H4b rulings escape; threat-model escape restored): 1
```

**restore:** the inverse text edit (the "before" lines put back). Both H4 restores are now in place.

**restore receipt** (call sites of `escape_placeholder_syntax` in `round_orders.py` as restored; `git diff --stat` empty):
```
224:def escape_placeholder_syntax(text):
252:        lines.extend(["-----", escape_placeholder_syntax(text.strip()), "-----"])
280:            lines.append(escape_placeholder_syntax(
```

**raw green** (after both restores):
```
.                                                                        [100%]
1 passed in 0.17s
green exit: 0
```

---

## H5 — `independent_reviewer` bars maker families (`receipt_disclosures.py` L209)

- **axis:** a candidate whose reviewer family is a maker's is never chosen

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py` `independent_reviewer`):
```diff
--- before (restored text)
        if cand_fam is not None and cand_fam not in barred:
            return v, cand_fam
+++ neutralized
        if cand_fam is not None:
            return v, cand_fam
```

**command:**
```
python3 -B -m pytest "plugins/superheroes/lib/tests/test_nonpanel_independence_1797.py::test_independent_reviewer_bars_maker_families" -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_independent_reviewer_bars_maker_families _________________

    def test_independent_reviewer_bars_maker_families():
        # axis: the barred-family check on the candidate's reviewer family — see bite-proof record
        # wo_b_1797_seat_orders
        cfg = {"vendors": ["claude", "codex"]}
        # the preferred vendor stands when its family is not a maker's
        assert RDS.independent_reviewer(cfg, "codex", frozenset({"anthropic"}), None) == ("codex", "openai")
        # a preferred vendor in a maker family is replaced by the first live vendor outside them
>       assert RDS.independent_reviewer(cfg, "claude", frozenset({"anthropic"}), None) == ("codex", "openai")
E       AssertionError: assert ('claude', 'anthropic') == ('codex', 'openai')
E         
E         At index 0 diff: 'claude' != 'codex'
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_independence_1797.py:35: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_independence_1797.py::test_independent_reviewer_bars_maker_families
1 failed in 0.08s
red exit: 1
```

**restore:** the inverse text edit (the "before" line put back).

**restore receipt** (`receipt_disclosures.py`; L186 is the separate `independent_auditor` line, L209 is `independent_reviewer`; `git diff --stat` empty):
```
186:            if cand_fam is not None and cand_fam not in barred:
209:        if cand_fam is not None and cand_fam not in barred:
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.07s
green exit: 0
```

---

## H6 — an unseatable non-panel seat gets no order (`round_driver.py` `_emit_orders_manifest`, L8728)

- **axis:** every slot of the phase is skipped, so the orders manifest holds no seat and each slot is recorded missing

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
--- before (restored text)
            unfilled = frozenset(key for key, _occ in round_records.roster_slots(roster))
+++ neutralized
            unfilled = unfilled
```

**command:**
```
python3 -B -m pytest "plugins/superheroes/lib/tests/test_nonpanel_independence_1797.py::test_unseatable_nonpanel_seat_gets_no_order_and_a_missing_record" -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_unseatable_nonpanel_seat_gets_no_order_and_a_missing_record _______

tmp_path = PosixPath('<tmp>/pytest-of-root/pytest-34/test_unseatable_nonpanel_seat_0')

    def test_unseatable_nonpanel_seat_gets_no_order_and_a_missing_record(tmp_path):
        # axis: the unseatable non-panel seat getting NO order — see bite-proof record
        # wo_b_1797_seat_orders
        session_dir, gitdir, head_path = TRI._bootstrap(
            tmp_path, name="b5-unseatable", vendors=["claude"], fixerVendor="claude")
        TRI._drive_to_phase(session_dir, gitdir, [TRI._blocking_finding("bounds A", 2)], head_path,
                            RD.P_VERIFIERS)
        state = TRI._state(session_dir)
        pend = state["pending"]
        assert pend["phase"] == RD.P_VERIFIERS
        roster, reason = RA.roster_for(pend["phase"], state, state.get("config") or {})
        assert reason is None and roster
        manifest_path = RD._orders_manifest_path(session_dir, pend["round"], pend["phase"], pend["attempt"])
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
>       assert manifest["seats"] == {}
E       AssertionError: assert {'verifier-sr...': None, ...}} == {}
E         
E         Left contains 1 more item:
E         {'verifier-src-f00-py-0-cc6e975994215308': {'channel': 'stdout',
E                                                     'engine': None,
E                                                     'envelopeStubPath': '<tmp>/pytest-of-root/pytest-34/test_unseatable_nonpanel_seat_0/b5-unseatable/round-1/orders/dispatch-verifiers/verifier-src-f00-py-0-cc6e975994215308.a0.envelope.json',
E                                                     'model': None,
E                                                     'occurrence': 0,...
E         
E         ...Full output truncated (7 lines hidden), use '-vv' to show

<repo>/plugins/superheroes/lib/tests/test_nonpanel_independence_1797.py:126: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_independence_1797.py::test_unseatable_nonpanel_seat_gets_no_order_and_a_missing_record
1 failed in 0.65s
red exit: 1
```

(pytest itself printed "Full output truncated (7 lines hidden)" in that capture; that is pytest's own truncation, reported as it came.)

**restore:** the inverse text edit (the "before" line put back).

**restore receipt** (`round_driver.py`; `git diff --stat` empty):
```
8728:            unfilled = frozenset(key for key, _occ in round_records.roster_slots(roster))
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.57s
green exit: 0
```

---

## H7 — panel dimensions follow the seeded seat map's roster (`round_driver.py` `_default_config`, L1173)

- **axis:** the default dimensions are the roster's lens seats in `DIMENSIONS` order, not all five

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
--- before (restored text)
        cfg["dimensions"] = _roster_lens_dimensions(cfg.get("seatMap")) or list(DIMENSIONS)
+++ neutralized
        cfg["dimensions"] = list(DIMENSIONS)
```

**command:**
```
python3 -B -m pytest "plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py::test_panel_dimensions_follow_the_seeded_seat_map_roster_in_dimensions_order" -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_panel_dimensions_follow_the_seeded_seat_map_roster_in_dimensions_order __

    def test_panel_dimensions_follow_the_seeded_seat_map_roster_in_dimensions_order():
        # axis: the roster-derived default dimensions (neutralize back to all five) — see bite-proof
        # record wo_b_1797_seat_orders
        seat_map = {"roster": ["test-role", "grounding-seat", "code-reviewer", "unknown-seat"]}
        cfg = RD._default_config({"seatMap": seat_map})
>       assert cfg["dimensions"] == ["code-reviewer", "test-role"]
E       AssertionError: assert ['architectur...tem-reviewer'] == ['code-reviewer', 'test-role']
E         
E         At index 0 diff: 'architecture-reviewer' != 'code-reviewer'
E         Left contains 3 more items, first extra item: 'security-reviewer'
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py:273: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_order_blocks_1797.py::test_panel_dimensions_follow_the_seeded_seat_map_roster_in_dimensions_order
1 failed in 0.17s
red exit: 1
```

**restore:** the inverse text edit (the "before" line put back).

**restore receipt** (`round_driver.py`; `git diff --stat` empty):
```
1173:        cfg["dimensions"] = _roster_lens_dimensions(cfg.get("seatMap")) or list(DIMENSIONS)
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.25s
green exit: 0
```

---

## H8 — a replaced defaulted reviewer vendor keeps `defaulted` (`round_driver.py` `_nonpanel_reviewer_vendor`, L7727)

- **axis:** when the preference read did not answer and B5 replaces the defaulted vendor, `vendorSource` stays `defaulted`, so the provenance gap is still disclosed and the seat still folds to the stdout contract

**neutralization** (`plugins/superheroes/lib/round_driver.py`; a replaced defaulted vendor now reports `independent`):
```diff
--- before (restored text)
    if chosen == vendor or source == VENDOR_SOURCE_DEFAULTED:
+++ neutralized
    if chosen == vendor:
```

**command:**
```
python3 -B -m pytest "plugins/superheroes/lib/tests/test_round_driver_order_channel.py::test_a_defaulted_reviewer_vendor_is_disclosed_not_merely_made_safe[dispatch-verifiers]" -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_defaulted_reviewer_vendor_is_disclosed_not_merely_made_safe[dispatch-verifiers] _

tmp_path = PosixPath('<tmp>/pytest-of-root/pytest-38/test_a_defaulted_reviewer_vend0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fcf255ba3f0>
phase = 'dispatch-verifiers'

    @pytest.mark.parametrize("phase", [RD.P_VERIFIERS, RD.P_GAPSWEEP, RD.P_SCOPED])
    def test_a_defaulted_reviewer_vendor_is_disclosed_not_merely_made_safe(tmp_path, monkeypatch,
                                                                           phase):
        """Safe is not the same as silent — the defaulted fallback owes a receipt (#1037 rider).
    
        The collector used to be panel-scoped, so a reviewer-phase fallback folded safely to stdout and
        disclosed NOTHING. It now derives from the same predicate the channel folds on, so the
        disclosure cannot lag the fold."""
        # axis: a defaulted reviewer vendor replaced by an independent one keeps `defaulted`, so the
        # provenance gap is still disclosed — see bite-proof record wo_b_1797_seat_orders
        session_dir = str(tmp_path / ("disc-" + phase))
        os.makedirs(session_dir, exist_ok=True)
        out = RD.cmd_next(session_dir, {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF,
                                        "fixerVendor": "claude", "verifyCommand": "none",
                                        "seatMap": _mixed_seat_map()})
        assert out["ok"], out
        ok, state = RD.load_state(session_dir)
        assert ok, state
        state["headDiff"] = DIFF
        rnd_key = str(state["round"])
        state["rounds"].setdefault(rnd_key, {}).pop("orderVendorProvenanceGaps", None)   # clear round-1
    
        monkeypatch.setattr(RD.engine_pref, "load_engine_prefs",
                            lambda _root: RD.engine_pref.refusal_engine_prefs("core.md unreadable"))
        seat = _seat_for(phase)
        RD._emit_orders_manifest(session_dir, state, state["round"], phase, 0, [seat],
                                 journal_cmd="next", pending_payload=_payload_for(phase), seat_map={})
        gaps = (state["rounds"].get(rnd_key) or {}).get("orderVendorProvenanceGaps")
>       assert gaps, "a defaulted reviewer vendor must be disclosed, not silently made safe"
E       AssertionError: a defaulted reviewer vendor must be disclosed, not silently made safe
E       assert None

<repo>/plugins/superheroes/lib/tests/test_round_driver_order_channel.py:478: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver_order_channel.py::test_a_defaulted_reviewer_vendor_is_disclosed_not_merely_made_safe[dispatch-verifiers]
1 failed in 0.96s
red exit: 1
```

**restore:** the inverse text edit (the "before" line put back).

**restore receipt** (`round_driver.py`; `git diff --stat` over the three production files is empty):
```
7727:    if chosen == vendor or source == VENDOR_SOURCE_DEFAULTED:
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.86s
green exit: 0
```
