# Contract register — verification-strategy package (spec #1105)

**What this is.** The package's binding sentences — the contracts more than one child builds
against — each numbered, each naming its producer and consuming children, each **decided now**
(the package read eliminated every open decide-by; see [package-read.md](package-read.md)).
Register-consuming child issues quote their entries byte-exactly, and `register_check.py` gates
filing on this file — **entries therefore use the checker's canonical shape**: an `**R<n> — `
header, one binding paragraph, and a `*Consumers:*` line whose tokens are the children that must
quote the entry (producers included — a producer builds against its own contract). Authored by
the advisor (2026-08-28) under walk-11 ruling 5-a; revised across package-read rounds 1–5. The
coverage map allocates criteria; this file binds contracts. Amended 2026-10-02 with the spec's
amendment #5: entries that bound dropped or held machinery are withdrawn (listed at the end,
outside the entry shape, so no child is asked to quote them), the survivors are rewritten to the
amended spec, and R22 records the keep-list seam.

**R3 — The rail inventory is a plain file.** P7 produces the rail inventory as a plain file listing the rails by id, seeded from the pinned `rail-census-v3` set (53 files) with advisor corrections limited to additions and entry metadata, recorded with why; a rail's entry lands in the PR that adds the rail; removing an entry carries FR-3's bar, and the PR body carries a `Rail removed: <entry id>` line that the vet checks when the inventory is in the diff — never a CI rule. Until the inventory lands, the rail-aware rules (FR-18c's lens arm, FR-26's rail exclusion) are vet-carried against the pinned seed.
*Producer:* P7
*Consumers:* P7, P5

**R4 — The receipt fields are hand-written.** A builder's handback carries the spec's FR-9 fields in the PR body — what ran, what was skipped and why, the source state, the interpreter, the attempt number and whether the prior attempt was red — with the tests that failed on that same source state, named or quoted from a traceable log reference, when it was — and elapsed time; the vet reads them and nothing checks them mechanically. The plugin's `gate-receipt/1` format (`plugins/superheroes/reference/gate-receipt.md`, shipped 2026-09-30) is optional: a project may emit it, and no child is required to emit or meet it.
*Producer:* the spec (the convention)
*Consumers:* P5

**R7 — One Python pin.** Exactly one committed home holds the Python pin (`.python-version`); every runner resolves the interpreter through the pin, never by version literal or absolute path; UFR-8's validator-step check runs before any test; `scripts/pinned-python` refuses — never falls back — when the pinned interpreter cannot be provisioned, with the spec's park route. The out-of-repo calibration home comes into line by calling `scripts/pinned-python`; the gate-side refusal when it disagrees is held with the gate driver. Shipped by P1.
*Producer:* P1
*Consumers:* P1, P9

**R9 — Flake notes and the vet finding.** A flake is recorded by hand on the collector when it is seen, naming the test, the run and the date; that note is the advisory flake listing. A listed flake is a vet finding on any PR that touches that test and blocks nothing repo-wide; its dispositions are a fix at the cause with red-under-cause and green-after evidence, a cannot-bite removal, an advisor withdrawal naming a non-test cause, or an owner-authorized removal under FR-26 (diagnosis evidence and the open coverage obligation retained), with a second withdrawal of the same test inside thirty days going to the owner (FR-26). Until P5's vet-checks encoding lands, the advisor's vet reads the listing directly from the spec.
*Producer:* the spec (the advisor and the vet record and read)
*Consumers:* P5

**R10 — One linked-fix reference rule.** One reference rule serves FR-18d and the gardening pass's escape classification: "a named merged change in the fix's commit subject or body"; a fix satisfying FR-18d is by construction linked to the change it fixes; a pre-dates claim names nothing. The rule's home is the spec's FR-18d.
*Producer:* the spec
*Consumers:* P5

**R11 — The whole-touched-file check is vet-carried until F1.** FR-15/FR-18f's whole-touched-file check is carried by the advisor's vet until F1 ships binding project rules with scope-override; a small re-encode follows F1. The test-lens calibration carries no rule-set version and no drift check (FR-B1). P5's test-lens slice and F1 are both parked under the owner's review hold (2026-10-02); this contract binds them when they unpark.
*Producer:* P5
*Consumers:* P5, F1

**R17 — One cannot-bite vocabulary, one re-run bar.** Cannot-bite evidence is one shared vocabulary (FR-1's grounds: the structural classes, break-stays-green demonstration, no-raise-is-suspect, unassessed-is-retained) with one shared bar (FR-14: independently re-run at verification, never accepted from the deleting party): P7's cuts and later cuts from mutation survivors carry it, and P5's UFR-5 encoding checks it. FR-1's other three bases sit outside this contract, each with its own bar: obsolete-expectation deletion on contact (the classification and its reason in the PR body, and the file absent from the stamped keep list); retired-subject removal (the owner's recorded approval, named in the PR body); and FR-26 flake removal (owner-authorized on re-runnable diagnosis evidence, recorded on the collector as an open coverage obligation with a restore-by date). The spec is the vocabulary's home; no child restates it.
*Producer:* the spec
*Consumers:* P7, P5, P9

**R22 — Delete on contact waits for the keep list (the reset register's R28).** Delete on contact is the shipped rule in plugins/superheroes/rubric/review-discipline.md § A behavior test that goes red (the spec's FR-1 cites it; neither restates it). It activates only once the owner has stamped the keep list; P7 seeds the keep list with Spec A FR-E1 item 12's three kinds for that stamp. *Cross-epic seam:* the keep list is seeded by the verification-strategy spec's own children (#1105's set); recorded reciprocally on #1105.
*Reciprocal seam:* R22 is this register's side of the reset register's R28; R28's sentence "expectations are not rewritten" contradicts the shipped rule, and bringing R28 into line (both homes) is the advisor's follow-up.
*Producer:* P7 (the seed); the owner (the stamp)
*Consumers:* P7, P5

---

**Decide-by ledger:** **empty by design** — every surviving contract is decided in the amended spec
or in the entry itself; no open decision remains, and the survivors are all one-owner conventions
or single-producer artifacts.

**Cross-epic seams — binding contracts that cross the package boundary (the complete set):**
**R22** (the reset register's R28: one contract in two homes, the keep-list seed on this side) and
**R11** (F1's binding project rules and the small re-encode after them; F1 is parked under the
owner's review hold).

**Doctrine mirrors — a weaker seam class, named so drift is watchable:** the plugin lane's PA–PD
ship universal *concepts* whose project-side twins are this spec's rules — PA ↔ FR-2/FR-3 (rail
concept), PB ↔ FR-1/FR-14 (deletion evidence — reconciled: PB's concept is that a deletion on the
cannot-bite basis carries its evidence; FR-1's other bases (obsolete expectation under a stamped
keep list, retired subject, owner-authorized flake removal) carry their own bars — never "any
deletion needs cannot-bite evidence"), PC ↔ FR-24/UFR-4's no-weakening rule, PD ↔ FR-18d
(fix naming, R10). These are prose mirrors, not shared machinery: each Lane-1 issue cites its spec
twin at filing, and a change to either side checks the other — recorded there, not as full
reciprocal registers. PA–PD are parked under the owner's review hold (2026-10-02).

**Withdrawn entries (amendment #5, 2026-10-02).** Entry numbers are stable; these numbers are
retired, and no child quotes them.

- R1 — Lane classification artifact: withdrawn; the lane classification is held on the registry (Spec A FR-F6 change 5), and its guard is dropped (Spec A FR-B1).
- R2 — The named-edit record form: withdrawn; the form is dropped (Spec A FR-B1) — FR-3 and FR-1 now take the owner's recorded approval named in the PR body and the `Rail removed: <entry id>` convention.
- R5 — The would-have-skipped set: withdrawn; held with selection and the gate driver (Spec A FR-F6 change 5).
- R6 — The gate's shared trust reads: withdrawn; held with selection and the gate driver (Spec A FR-F6 change 5), and its trust reads also read the declined ledger (Spec A FR-F6 change 1).
- R8 — The machine-owned gate command: withdrawn; the driver is held (Spec A FR-F6 change 5) and the census over its command is dropped (Spec A FR-B1).
- R12 — Protected artifacts and the replay record: withdrawn; declined with the ledger and the nightly instruments (Spec A FR-F6 change 1).
- R13 — The ledger's publication surface: withdrawn; declined with the ledger and the nightly instruments (Spec A FR-F6 change 1).
- R14 — Nightly isolation and the reporting path: withdrawn; declined with the ledger and the nightly instruments (Spec A FR-F6 change 1).
- R15 — The six fixed receipt phrases: withdrawn; the phrases were the gate driver's output, held (Spec A FR-F6 change 5).
- R16 — Show-it surfaces are inherited scope: withdrawn; every Show-it surface it allocated belonged to P3b, P2 or P8, all closed or withdrawn — the amended spec's one Show-it row, the hand-written receipt, is the convention itself (spec FR-9).
- R18 — The differential's candidate-ingest feed: withdrawn; the flake differential is declined to the registry (Spec A FR-F6 change 4).
- R19 — UFR-6's breach freeze: withdrawn; the ledger-rate freeze is cut with the ledger (Spec A FR-F6 change 1) — the spec's reshaped UFR-6 reads the gardening pass's hand count and binds no child contract.
- R20 — A detector ships with its specimen: withdrawn; the birth bite-proof rule stays in the spec (FR-18g), and every detector it listed was withdrawn or has shipped (P1's pin check).
- R21 — UFR-6's insufficient-sample park: withdrawn; cut with the ledger (Spec A FR-F6 change 1) — the spec's reshaped UFR-6 reads the gardening pass's hand count and binds no child contract.
