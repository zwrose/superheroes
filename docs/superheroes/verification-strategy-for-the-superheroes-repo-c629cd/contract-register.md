# Contract register — verification-strategy package (spec #1105)

**What this is.** The package's binding sentences — the contracts more than one child builds
against — each numbered, each naming its producer and consuming children, each **decided now**
(the package read eliminated every open decide-by; see [package-read.md](package-read.md)).
Register-consuming child issues quote their entries byte-exactly, and `register_check.py` gates
filing on this file — **entries therefore use the checker's canonical shape**: an `**R<n> — `
header, one binding paragraph, and a `*Consumers:*` line whose tokens are the children that must
quote the entry (producers included — a producer builds against its own contract). Authored by
the advisor (2026-08-28) under walk-11 ruling 5-a; revised across package-read rounds 1–5. The
coverage map allocates criteria; this file binds contracts.

**R1 — Lane classification artifact.** The lane classification is a versioned, committed artifact assigning every test file to exactly one lane, with owned paths on every behavior-lane file; its guard fails on an unassigned file, a doubly-assigned file, a behavior file lacking owned paths, or an unnamed narrowing; its version identifier (representation is P3a's to pick) is what gate receipts and ledger rows name as "the classification in force".
*Producer:* P3a
*Consumers:* P3a, P3b, P2, P5

**R2 — The named-edit record form.** A named edit takes one machine-checkable form on every surface the spec requires one (rail inventory, lane classification, risk-profile table, ledger protected artifacts, the P6 mutation budget, and the FR-17 checkpoint's owner amendment of FR-1): a structured JSON record committed beside the edited artifact in the same change, carrying `{"entry": <what changed>, "reason": <why>, "bar": <which spec bar applies>, "evidence": [<pointers the bar requires — owner-approval link, cannot-bite receipt, replay record>]}`; a guard's green path is "every change matches a well-formed record", never free prose. The shape is decided here, and the reference reader ships in P2 (Wave 1; its protected-artifact guard is the first mechanical consumer) — every later child conforms to P2's reader; field additions are backward-compatible, renames are not. This register is the form's one binding home — the plan's P3a boundary phrase and the map's "first shipping home" note both defer here.
*Producer:* the form is this register's; the reference reader is P2's
*Consumers:* P2, P7, P3a, P5, P6, P8

**R3 — The rail inventory is the rail lane's authority.** P3a's classifier derives the rail lane from the inventory, never independently, and the FR-3 guard activates in two phases — entry-disappearance inside P7 (with or before any cut), the re-laning arm when P3a's classification exists. Ordering: P7 lands with or before P3a in its wave; until the inventory lands, the rail-aware rules downstream (FR-18c's lens arm, FR-26's rail exclusion) are vet-carried against the pinned `rail-census-v3` seed, disclosed in each consumer's issue.
*Producer:* P7
*Consumers:* P7, P3a, P5, P2

**R4 — The gate receipt and its cross-repo schema.** The gate receipt is FR-9's field set; its cross-repo schema is F2's `gate-receipt/1`, carrying run id, source state, lanes run/skipped with reasons, result, and — per the owner's adoption ruling and the weekly-eats consumer read of 2026-08-28, not this spec — attempt history, wall time, and machine/runner identity (this repo's FR-9 already carries attempt number, prior-red set, and wall time, so the superset serves both consumers). F2 decides final field serialization — it lands in Wave 1, before P3b (Wave 2) emits, so the decider precedes every emitter; every reader is a tolerant reader (unknown fields ignored), and each consumer re-checks conformance when F2 lands. Cross-lane seam, recorded reciprocally: F2's issue body stands in for the plugin-side register; weekly-eats consumers are D1 (emits/validates) and D2 (its ledger reads wall time + runner identity per run).
*Producer:* P3b (project emission) + F2 (schema)
*Consumers:* P3b, F2, P2, P5

**R5 — The would-have-skipped set.** The would-have-skipped set is computed by the ledger per pull-request CI run, under the classification version in force when the run executed, and recorded immutably with the run; it is the counted population for FR-10's threshold. FR-11's false-negative detection reads that set OR the change's own handed-back receipt — the spec's two detection arms, both P2's to check. P3b produces the receipt's corroborating would-have-skipped field; it never reads the ledger's set.
*Producer:* P2
*Consumers:* P2, P3b

**R6 — The gate's shared trust reads.** The local gate reads UFR-9's three named trust states — the selection-suspension flag (FR-11), instrument staleness (UFR-3), and the calibration-home pin agreement (FR-12) — and runs full, saying which, when any is unreadable. Separately from UFR-9, the gate reads the selection-enablement record (FR-10's observation-to-live flip, recorded in the ledger with date and approver): the gate skips nothing unless a recorded enablement reads true — an absent, false, or unreadable record is not-enabled, and selection stays off with no UFR-9 phrase owed (that path is FR-5's own gating, not a trust-state failure). Storage location and read protocol of the ledger-side states are P2's to define in its own build, with P3b conforming; the pin state is R7's.
*Producer:* P2
*Consumers:* P2, P3b

**R7 — One Python pin, and the gate's refusal arms.** Exactly one committed home holds the Python pin; every runner resolves the interpreter through the pin, never by version literal or absolute path; UFR-8's validator-step check runs before any test. The gate's refusal arms bind here (FR-12): the local gate refuses to run when the out-of-repo calibration home disagrees with the pin, and refuses — never falls back to another interpreter — when the pinned interpreter cannot be provisioned; the refusal carries the spec's park route (builder parks with the refusal receipt; advisor routes: fix provisioning, or the owner records acceptance of CI as the sole gate for that change).
*Producer:* P1
*Consumers:* P1, P3b, P6, P4

**R8 — The machine-owned gate command.** The gate command is machine-owned (FR-9): it carries the bytecode-safety flags and never a retry/rerun flag; it is the subject of P4's gate-command census (which therefore lands with or after P3b), and that census is also FR-24's no-retry enforcement arm.
*Producer:* P3b
*Consumers:* P3b, P4

**R9 — Flake listings and the block's enforcement points.** A flake listing names the test, the run, and the recorded-at time; its only dispositions are fixed-at-cause, cannot-bite removal, or an FR-26 owner-authorized removal; the block's enforcement points are the vet's listing read plus the merge-time re-check record with the actor's identity, cross-checked nightly (P2). Interim: until P5's vet-checks encoding lands, the advisor's vet performs the listing read directly from the spec — the enforcement point exists from the day P2's listings do; P5 encodes it, it does not create it.
*Producer:* P2
*Consumers:* P2, P5

**R10 — One linked-fix reference rule.** One reference rule serves FR-18d and FR-19: "a named merged change in the fix's commit subject or body"; a fix satisfying FR-18d is by construction a linked fix; a pre-dates claim names nothing and counts unlinked. The rule's text lives with the ledger's protected artifacts (R12) — by the spec's own designation: FR-19 names "the escape-candidate detection rule" a protected artifact, and this reference rule is that rule (FR-19: "the reference FR-18d requires and the reference this rule detects are the same thing").
*Producer:* P2
*Consumers:* P2, P5

**R11 — The rule-set version and the review receipt's resolvable fields.** The test-lens calibration bears a rule-set version; review receipts name it together with a run identifier traceable independently of the receipt and the reviewed source state — the fields UFR-7's nightly fallback resolves (P2 checks the identifier resolves to a run producing the receipt, on the merged source state, under the current version); a bite-proofed drift check fails when the calibration no longer carries every FR-18a–f rule, FR-4b's grading, or the two FR-13 practice rules. Until F1 ships, the whole-touched-file check is encoded as vet-carried (the spec's owner-ruled interim; encode-twice taken by both repos); a small re-encode follows F1+F3. Cross-lane seam, recorded reciprocally: P5's shape depends on F3 (its section home) and re-encodes after F1 — recorded in F1's and F3's issue bodies as the plugin-side half, and mirrored by weekly-eats' DE policy-copy (its plan records the same encode-twice).
*Producer:* P5
*Consumers:* P5, P2, F1, F3

**R12 — Protected artifacts and the replay record.** The ledger's class predicates, infra-signature list, and escape-candidate rule are protected artifacts: changed only by an advisor/owner named edit (R2's form) accompanied by a recorded replay with the spec's exact scope — the trailing 60 days *including* the provisional most-recent-seven (unlike UFR-6's rate, which excludes them), or the whole available history while the ledger is younger than 60 days — naming which existing rows the edit would reclass and whose changes those rows concern; the author-exclusion is checked against that replay record; never by the author of an affected change; such an edit always takes a vetted lane, and the vet-check encoding for the replay record is P5's (the artifacts and nightly re-check are P2's).
*Producer:* P2
*Consumers:* P2, P5

**R13 — The ledger's publication surface.** The ledger publishes to one tracking item's body, refreshed nightly: the class counts, the provisional-7-day marking, the low-confidence flag, the complete-ledger-day count (the number P8's checkpoint item quotes in its first line), the escape-candidate rate with its merge-count sample size (the numbers the R19 freeze and R21 park read), and — once FR-10 enablement is recorded — the local-loop trailing-20 median (the NFR's measurement home); UFR-6 reads settled rows only.
*Producer:* P2
*Consumers:* P2, P8, P3b

**R14 — Nightly isolation and the reporting path.** The nightly workflow isolates the ledger refresh from the sweeps — a mutation or differential overrun never stales the ledger — and only three consecutive stale nights of the ledger itself revert the local tier to full. P2's refresh runs on its own schedule from the day P2 lands (Wave 1, no P3 dependency — the plan's own edge); when P3b's nightly tier (FR-8, Wave 2) lands, the refresh and P6's instruments ride it without coupling their failure domains — riding is a scheduling convenience, never a dependency that could stale the ledger. The nightly reporting path is part of this contract: each participant (P3b's tier, P6's instruments, and P2's own ledger refresh, which self-reports) reports, per night, executed-with-result or failed-with-reason, into the FR-8 receipt and into P2's tracking record (UFR-3's surface) — minimal shape: participant, night, status, reason-when-failed.
*Producer:* P3b (tier) + P2 (refresh) + P6 (instruments)
*Consumers:* P3b, P2, P6

**R15 — The six fixed receipt phrases.** The six receipt phrases are fixed and quoted exactly as the spec states them ("full — non-Python change", "full — unclassifiable (<reason>)", "full — selection suspended (false negative on <change>)", "full — instruments stale since <date>", "full — trust state unreadable (<which>)", "no owned path changed"); consumers match on these strings.
*Producer:* P3b
*Consumers:* P3b, P2

**R16 — Show-it surfaces are inherited scope.** Each Show-it surface in the spec's Coverage table is a DoD bullet in the owning child's issue: the first receipt, the suspended receipt, the stale-instruments receipt, and the phrase wording → P3b; the FR-10 threshold record and FR-25 breach delivery → P2; the FR-17 checkpoint's named item (first line = complete-ledger-day count) → P8 — carried on the checkpoint item itself (P8 files no issue by the plan's own rule; the named decision item, tracked in the collector, is its presentation surface) — so presentation is inherited as scope, never discovered at handback, on every child that owns a shown surface.
*Producer:* filing-time rule
*Consumers:* P3b, P2, P8

**R17 — One cannot-bite vocabulary, one re-run bar.** Cannot-bite evidence is one shared vocabulary (FR-1's grounds: the structural classes, break-stays-green demonstration, no-raise-is-suspect, unassessed-is-retained) with one shared bar (FR-14: independently re-run at verification, never accepted from the deleting party): P7's cuts carry it and P5's UFR-5 encoding checks it. FR-26 removals are explicitly outside this contract — FR-1's one named exception: owner-authorized, grounded in re-runnable diagnosis evidence, recorded as an open coverage obligation with a restore-by date, never a cut. The spec is the vocabulary's home; no child restates it.
*Producer:* the spec
*Consumers:* P7, P5

**R18 — The differential's candidate-ingest feed.** The flake differential's published differing-set is the candidate-ingest feed: P6 publishes, per night, the set of tests whose serial/parallel results differ (test id, night, both results); P2 records each as a candidate with a recorded-at time and drives the disposition lifecycle (confirmed → FR-23 listing; withdrawn with trace; overdue escalation). The feed's minimal shape is those three fields; P6 may add fields, P2 reads tolerantly.
*Producer:* P6
*Consumers:* P6, P2

**R19 — UFR-6's breach freeze.** When the ledger's escape-candidate rate over the trailing 60 calendar days, read over settled rows only (the provisional most-recent-seven excluded — exclusion never extends the window), exceeds the 17.4% baseline **on a readable window** — ≥100 merges AND no unlinked-fix majority; a low-confidence window is insufficient sample and R21's park governs instead, so the two entries are mutually exclusive by construction — (P2 computes and publishes the rate and sample size, R13), **all test removal halts** — FR-14 deletions, FR-15 burndown (suspended into debt), P7's cuts including its warm-up class, and P8's FR-17 checkpoint (UFR-6's own halt list names the checkpoint) — with exactly one exception: an owner-authorized FR-26 removal, which UFR-6 explicitly exempts (a coverage obligation, not a cut). **A breach freeze lifts only by the owner's recorded decision** — never by the rate later reading clean. The enforcement points are the vet-park encoding (P5) and the merge-time re-check of a removing change's clearance (P2's nightly cross-check + the recorded actor identity).
*Producer:* P2
*Consumers:* P2, P5, P7, P8

**R20 — A detector ships with its specimen.** Every guard, census, drift test, and classifier this policy introduces carries its bite-proof specimen (a seeded violation it demonstrably flags) in the build that ships the detector — P3a's classification guard, P1's pin drift check, P4's censuses, P7's inventory guard, P2's classifier (one specimen per class and per disjunction branch, FR-18g), and P5's own rule-set drift check — itself a detector, itself bite-proofed, its specimen shipping in P5. No child's specimen stands in for another's.
*Producer:* each detector's owner
*Consumers:* P3a, P1, P4, P2, P7, P5

**R21 — UFR-6's insufficient-sample park.** While the trailing window holds fewer than 100 merged changes, or unlinked fixes outnumber linked candidates (FR-19's low-confidence flag), the ledger reads "insufficient sample" and **the same holds apply as under a breach — including P8's FR-17 checkpoint — with one further exception beyond FR-26: the P7 warm-up carve-out** (cannot-bite deletions carrying FR-14's independently re-run evidence proceed during the ledger's warm-up, by the owner's 2026-08-28 ruling, stated with its bound in P7's issue — their safety argument is structural, not statistical). **The park is condition-based, not owner-lifted: it ends when the window becomes readable** (≥100 merges and no unlinked-fix majority — at equality, including zero and zero, the window is readable per FR-19's own boundary) — and if the then-readable rate breaches, R19's freeze takes over, owner-lift and all.
*Producer:* P2
*Consumers:* P2, P5, P7, P8

---

**Decide-by ledger:** **empty by design** — R2's form is decided in the register and its reference
reader is P2's; R4's decider is F2, which lands before every emitter; R6's storage is explicitly
P2's build-time call with a named conformer, which is ownership, not an open decision.

**Cross-epic seams — binding contracts that cross the package boundary (the complete set):**
**R4** (gate-receipt schema — F2's issue body is the plugin-side record; weekly-eats D1 + D2 the
far consumers) and **R11** (the vet-carried interim and F1+F3 re-encode — recorded in F1's and
F3's issue bodies; weekly-eats DE mirrors it).

**Doctrine mirrors — a weaker seam class, named so drift is watchable:** the plugin lane's PA–PD
ship universal *concepts* whose project-side twins are this spec's rules — PA ↔ FR-2/FR-3 (rail
concept), PB ↔ FR-1/FR-14 (deletion evidence), PC ↔ FR-23/FR-24's no-weakening rule, PD ↔ FR-18d
(fix naming, R10). These are prose mirrors, not shared machinery: each Lane-1 issue cites its spec
twin at filing, and a change to either side checks the other — recorded there, not as full
reciprocal registers.
