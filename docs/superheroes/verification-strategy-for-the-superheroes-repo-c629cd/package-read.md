# Package-read audit trail — verification-strategy package (spec #1105)

**Read:** light weight, advisor-called (measurables: 8 buildable children + 1 decision row;
~15 register entries; one cross-epic seam). Ceiling 2 rounds; escalation-by-sentence stated.
Seats: non-Anthropic only (author family excluded — spec, plan, and artifacts are all
Claude-authored, and so is the reading advisor).

## Round 1 — seats and topology

| Lens | Engine / model / effort | Order id |
| --- | --- | --- |
| allocation | codex / gpt-5.6-sol / xhigh | pkgread-1105-allocation |
| grounding & contradiction | codex / gpt-5.6-sol / xhigh | pkgread-1105-grounding |
| premortem | codex / gpt-5.6-sol / xhigh | pkgread-1105-premortem |
| register conformance & coupling | cursor CLI / grok-4.6 / xhigh | pkgread-1105-register-r2 |
| gradability | cursor CLI / grok-4.6 / xhigh | pkgread-1105-gradability-r2 |

Dispatch mechanics: pinned tree at `7cec7fd4`, full-oid diff base `89649130…`, findings-only JSON
plus a mandatory investigated list (min 8 entries) per seat; anti-hijack preamble; explicit
document-review framing (a docs-only diff is the subject, and a vacuous "no code to review"
return is a failed review). One config error at dispatch: the two cursor seats were first sent to
`composer-2.5` with an effort string — refused at `engine-config:invalid-model-effort` (composer
is effort-less, and it is the implementer model, not the judge) — re-dispatched on `grok-4.6@xhigh`,
the judge model, per the standing engine-economics rule. The refusal cost two dispatch calls and
shipped no degradation.

## Topology divergence — recorded for the doctrine (owner-directed, 2026-08-28)

Two advisors ran the package-read protocol in the same week with different seat topologies, both
charter-conformant (the charter fixes the five lenses and author-family exclusion, not the
seat-to-lens mapping):

- **superheroes (this read, LIGHT): one seat per lens** — five dispatches, each model spending a
  full xhigh run on one adversarial question; findings lens-attributable. Named weakness: every
  question gets exactly one model's reading (a per-question vendor blind spot has no redundant
  catch), and the lens is vendor-confounded.
- **weekly-eats (FULL, 9 children, interlocked D1/DE/D3 core): one seat per vendor** — each seat
  carries all five lens questions across the whole package; every question gets two independent
  models, disagreement is signal, and the round is cheaper. Named weakness: attention dilutes
  across five questions in one run, and — the risk that matters specifically at FULL weight —
  **premature convergence**: full weight terminates when a round returns only mechanical items, and
  two diluted seats can both return thin, reading as convergence when it is exhaustion of
  attention, not of findings.

**Mitigations identified for per-vendor-at-full** (relayed to the weekly-eats advisor): (1) make
the investigated list per-lens — a round is valid only when each seat's investigated entries
demonstrate real coverage of every lens, so a diluted seat is detectable before it terminates the
loop; (2) scope later rounds per-lens on the interlocked core, converting the topology to per-lens
exactly where depth is owed; (3) the cross-topology check is cheap in either direction — a thin or
suspiciously clean lens in a per-lens read gets cross-dispatched to the other vendor (this read's
own stated valve), and a suspiciously quiet round in a per-vendor read gets one dedicated-lens
probe seat.

Doctrine disposition: **observation recorded, no rule minted** — two data points is calibration
evidence, not a basis for pinning topology in `decomposition.md`. When either shape produces a
post-read escape (a package defect the read missed that a child build later hits), that escape
names the topology it escaped, and the doctrine call gets made on escapes, not on preference.

## Round 1 — results

*(pending — seats running)*

**Round 1 results (45 findings; all seats engaged — codex 65k–90k tokens each, grok engaged per
transport):** allocation 9 · grounding 8 · premortem 7 · register 12 · gradability 9 (one
Critical: the FR-10 enablement seam; a second Critical: the seam-completeness claim falsified).
Systematic repairs landed in commit `09f185b1` (see the map's and register's round-1 annotations).
One dispatch degradation: every seat's investigated list was rejected by the result parser (shape
mismatch between the order's requested format and the harness's record shape) — engagement was
instead evidenced by token counts, wall time, and finding quality; the investigated-list floor is
therefore partially degraded for round 1 and disclosed here.

## Escalation to full weight

Round 2 (per-vendor topology: codex + grok, whole package) returned 22 findings, none mechanical —
light's ceiling (2) reached unconverged. Per the escalation valve stated at the weight call
("interlocking findings → full, by one sentence"): **escalated to full weight** — the findings were
converging in scope (45 → 22) and mostly graded the round-1 repairs, so continuing beat parking.
Ceiling at full: 4 rounds.

**Round 2 (22 findings):** both vendors independently confirmed two spec contradictions the
round-1 rewrite introduced (R17/R19 trampling FR-26's exemption — an owner-authorized flake
removal is a coverage obligation, not a cut) and the FR-18g specimen misallocation; grok added a
Critical (Wave-1 P2's refresh riding Wave-2 P3b's nightly runner) and the enablement-vs-UFR-9
shape; codex re-corrected FR-2 (membership cannot be the definition — FR-18c must catch a rail
absent from the inventory) and pressed the seam list to the PA–PD doctrine mirrors. **One finding
REFUTED with the spec's own text:** grok's claim that R10's reference rule does not belong in the
protected set — FR-19 explicitly names "the escape-candidate detection rule" a protected artifact,
and FR-19's own acceptance says that rule and FR-18d's reference are the same thing. Repairs in
commit `b62a3a15`.

**Round 3 (10 unique findings: codex 8, grok 2; first mechanical-tagged items appear):**
cross-vendor convergence on P5's own drift check needing its specimen (now in R20); precision
repairs — R19's window wording restored to the spec's exact shape (60 calendar days, settled rows
only, exclusion never extends the window), R13 gains the rate + sample size R19 reads and the
ledger-day count P8 quotes, R11 gains UFR-7's resolvable fields, R14 gains the nightly reporting
shape, R7 gains FR-12's two refusal arms, FR-2 reformatted as three singly-owned rows, FR-4's
execution bullet moved to P3b. Repairs in the commit carrying this file.

## Round 4 — convergence round

*(recorded below when terminal)*

**Round 4 (owner-extended by ruling b; 5 findings: codex 4, grok 1, cross-vendor convergent on the
map/R20 inconsistency):** repairs in `90b52fed`. **Round 5 (owner-extended by a second ruling b;
5 findings: codex 2, grok 3):** the read's most consequential catch — the register's table format
parsed to **zero entries** under `register_check.py`, which would have blocked every child filing
fail-closed; the register was reformatted to the checker's canonical entry shape and **proven
mechanically**: `register_check.py` now parses all 20 entries and resolves a required set for
every child token (P1–P8, F2, F1, F3) — a machine receipt no model round could give. Plus four
one-line content fixes (FR-3's entry-metadata phrase; R19 binding the freeze to P8's checkpoint
per UFR-6's own halt list; R20's consumers enumerated as child tokens; FR-11's post-lift receipt
citation owned by P3b).

**Round 6 (owner-extended by a third ruling b; 4 unique findings: codex 3, grok 2, both vendors
converging on the same top defect):** R19 conflated UFR-6's two halt modes — its third defect in
three rounds, read as the third-rework tripwire firing on one sentence's *shape*. Structural
repair: **R19 split into R19 (breach freeze: halts everything including P7's cuts and P8's
checkpoint, owner-only lift) and R21 (insufficient-sample park: same holds except the owner-ruled
P7 warm-up carve-out; condition-based end when the window becomes readable)** — the conflation
removed by construction. Plus two map rows: P8's UFR-6 checkpoint-hold, and FR-8's per-participant
status production allocated to P6/P2 per R14. Register re-parse-proven after the split (21
entries, all child tokens resolve).

**Round 7 (owner-extended by a fourth ruling b; 3 unique findings: codex 2, grok 1):** all
one-line precision fixes on the UFR-6 complex — R19's trigger now requires a *readable* window
(no unlinked-fix majority; a low-confidence window is R21's regime, so the two entries are
mutually exclusive by construction — grok's catch); R21's park-end boundary corrected to the
spec's own low-confidence line (unlinked must OUTNUMBER linked; equality is readable — codex's
catch); the UFR-6 breach-decision delivery allocated explicitly as advisor process with R13 as
its input (codex's catch).
