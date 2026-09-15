# Coverage map — reset-landing-2026-09-14

Acceptance-level allocation: every acceptance criterion of Spec A (the forward doctrine) and Spec B (the re-derivation), both owner-stamped 2026-09-14, owned by exactly one child. Each FR's acceptance bullets are listed at the spec's own bullet granularity and ordinal (the round-1 package read found the first cut had dropped bullets whose label wraps onto a second line and had counted one consequence line as a criterion; both corrected), and Spec A's FR-F6 and FR-E1 numbered items count as criteria (FR-E1 twice: the plugin's item definitions and this repo's stamped values are separate sections of the spec). Splits are declared per row. Three non-child owners are declared for criteria that are not buildable work: **done at the stamp** (acts executed 2026-09-14 and recorded on #695), **outside the epic** (the verification-strategy spec's own children, #1105; the reciprocal seam is R28), and **closed by the stamp** (rules of Spec B's derivation method that bind the builders' re-verification at each child head, R26).

Children: C1 founding texts · C2 front-door references · C3 review doctrine and one home · C4 committed-docs correction · C5 merge-gate retirement · C6 keep-or-retire rollout · C7 charter restructure · C8 calmer reviews · C9 background-session trial · C10 dispatch entry shrink · C11 native channels and the probe · C12 receipt writer · C13 certification loop · C14 CLI Claude engine and Astra · C15 orchestration decommission · C16 sanitized-view shrink · C17 configuration items.

**Sequencing.** Wave 0: C1 alone, the seam; every other child cites its glossary and founding texts, so nothing launches until C1 has merged. Wave 1, after C1, on disjoint surfaces: C6 (the keep-or-retire doc, early so every later child can add its entries at birth), C9 (the trial, early so its receipt informs C15), C10, C16, C17. Wave 2: C2, C3, C4, C11 (after C10), C12 (after C6, so the writer's and checks' entries land in C12's own PR), C13 (after C12). Wave 3: C5 (after C3, same review-discipline file), C7 (after C2, C3, and C15: its one-hop targets and the orchestration that remains; a three-layer stack, one charter per layer), C8 (after C13), C14 (after C11), C15 (after C9's receipt and after C14: only one child at a time edits the launcher's spawn path, C14 retires the hand-built argv, then C15 removes detached spawn). The orderings the specs fix are honored: founding documents first, the trial early, CLI Claude after the dispatch shell, decommission after the trial's receipt, Astra after its probe (inside C14).

| Spec | FR | Bullet | Label | Criterion (opening words) | Owner |
| --- | --- | --- | --- | --- | --- |
| A | FR-A1 | 1 | Acceptance (rule, two doors; ruled 2026- | the door classifies every item at entry by FR-E1's machinery-versus-product test, the same test the… | **C2** |
| A | FR-A1 | 2 | Acceptance (rule): | "made to happen" means it broke in the field, or it was reproduced or probed in the lab. "Argued it… | **C2** |
| A | FR-A1 | 3 | Acceptance (rule, live vs dark): | a surface is live when it has at least one shipped consumer today: a shipped code path a shipped cal… | **C2** |
| A | FR-A1 | 4 | Acceptance (rule): | no severity thumb touches this bar. Every item needs executed evidence regardless of claimed severit… | **C2** |
| A | FR-A1 | 5 | Acceptance (rule): | an item that fails the bar is declined with a trigger (FR-A5), never silently dropped.… | **C2** |
| A | FR-A1 | 6 | Acceptance (rule): | lab evidence counts by design. Recorded rationale: the #1221 guidance-channel hole had zero field oc… | **C2** |
| A | FR-A2 | 1 | Acceptance (rule, impact instrument): | the severity ladder is a closed, owner-stamped enumeration of named bands with concrete examples in… | **C2** |
| A | FR-A2 | 2 | Acceptance (rule, urgency instrument): | urgency is the evidence tier (lab-only, field-once, field-recurrent), read directly off the FR-A1 ev… | **C2** |
| A | FR-A2 | 3 | Acceptance (record, surface heat deferre | the design artifact names a surface-heat adjustment without enumerating it. The owner deferred it to… | **C2** |
| A | FR-A2 | 4 | Acceptance (rule): | the grid stays two axes and a slot count. The framework acquiring its own machinery is the failure m… | **C2** |
| A | FR-A3 | 1 | Acceptance (rule): | a P1 or P0 grade waits on the owner's word to hold that tier. A cleared item may rest at P2 with no… | **C2** |
| A | FR-A3 | 2 | Acceptance (rule, the P2 carve-out): | the standing rule "no issue filing without the owner's word" (shipped as the owner-decisions contrac… | **C2** |
| A | FR-A3 | 3 | Acceptance (rule, template amendment 1,  | the tier vocabulary is an intake-and-commitment vocabulary orthogonal to roadmap structure. The doct… | **C2** |
| A | FR-A4 | 1 | Acceptance (rule): | every intake grading records its scoring durably on the item: band cited, evidence tier, resulting t… | **C2** |
| A | FR-A4 | 2 | Acceptance (rule): | a misses log captures three classes: declined-then-escaped, launched-then-regretted, and mis-tiered.… | **C2** |
| A | FR-A4 | 3 | Acceptance (rule, homes): | the misses log lives as a sibling section of the collector issue's pinned registry comment: one surf… | **C2** |
| A | FR-A4 | 4 | Acceptance (rule, the lane is a recorded | the routing record (FR-A9's routing-time calls, where the lane call is made) and every vet receipt n… | **C2** |
| A | FR-A5 | 1 | Acceptance (rule): | a declined item becomes a registry line with a named trigger: a concrete condition ("first real call… | **C2** |
| A | FR-A5 | 2 | Acceptance (rule, when triggers are read | a trigger gets exactly two detection moments, both existing acts. At the door, every new filing is c… | **C2** |
| A | FR-A5 | 3 | Acceptance (rule): | the worth-it gate's existing registry rows carry over unchanged. The gate's test retires at this spe… | **C2** |
| A | FR-A5 | 4 | Acceptance (rule, the registry seed from | the following lines are seeded at the stamp, each with the trigger the ruling gave it. Surface heat… | done at the stamp (2026-09-14), nothing owed |
| A | FR-A5 | 5 | Acceptance (rule): | the registry has one home (Change 7). The collector's pinned revisit-trigger registry comment remain… | **C2** |
| A | FR-A6 | 1 | Acceptance (rule): | filing is cheap; launching is the guarded act. The budget is N machinery lanes in flight at once, co… | **C2** |
| A | FR-A6 | 2 | Acceptance (rule, the dial, precisely): | the dial is a ceiling on the machinery share of wave capacity. Over each gardening window, at most 2… | **C2** |
| A | FR-A6 | 3 | Acceptance (rule, which instrument binds | the dial governs; N is its per-wave planning expression. The accounting unit is the authorized wave:… | **C2** |
| A | FR-A6 | 4 | Acceptance (rule, a convention at the la | the dial is a planning convention, always discussable at the launch word. At wave planning the advis… | **C2** |
| A | FR-A6 | 5 | Acceptance (rule): | tiers order entry through the door; the owner's word sits at launch, where the capacity is actually… | **C2** |
| A | FR-A6 | 6 | Acceptance (rule, the reset is outside t | the landing epic (Part 6) is a one-time strategic reset. Its children, the Part C builds included, a… | **C2** |
| A | FR-A6 | 7 | Acceptance (rule, after the reset, no ex | from the reset's landing, every epic and milestone is product-forward and is labeled so by the owner… | **C2** |
| A | FR-A7 | 1 | Acceptance (rule): | at epic decomposition, the backlog and the declined registry are scanned for P1s, P2s, and registry… | **C2** |
| A | FR-A7 | 2 | Acceptance (rule): | an issue adopted into an epic counts as product-forward: it rides the package as ratified scope, not… | **C2** |
| A | FR-A7 | 3 | Acceptance (rule): | mid-build improvisation stays forbidden, exactly as today.… | **C2** |
| A | FR-A8 | 1 | Acceptance (rule): | any filing that proposes an instrument, detector, report, or sweep carries a reader clause: the name… | **C2** |
| A | FR-A8 | 2 | Acceptance (rule): | each project declares one unconditional digest as the floor: the minimum standing read that keeps "s… | **C2** |
| A | FR-A8 | 3 | Acceptance (rule, applied to the door it | the door's own instruments carry their reader clauses here. The misses log, declined registry, scori… | **C2** |
| A | FR-A9 | 1 | Acceptance (rule): | at routing, any issue estimated over 1,000 non-test lines (a routing estimate, not a measurement) ca… | **C2** |
| A | FR-A9 | 2 | Acceptance (rule): | the slot is recorded in the routed issue body beside the lane call and the presentation call, at the… | **C2** |
| A | FR-A10 | 1 | Acceptance (rule, vocabulary): | a **ruling** is any decision the owner gives, in any session. A **decision walk** is any sitting in… | **C2** |
| A | FR-A10 | 2 | Acceptance (rule, trigger; ruled 2026-09 | the pass is owed seven days after the last gardening record, and it is done at an opportune sitting,… | **C2** |
| A | FR-A10 | 3 | Acceptance (rule, duties, closed list): | at each pass the advisor: 1. ages P1s: each P1 older than two passes is proposed promote, demote, or… | **C2** |
| A | FR-A10 | 4 | Acceptance (rule, the record's contents, | a gardening record carries: the batched words with their spines; the pending-words line (FR-A3); the… | **C2** |
| A | FR-A10 | 5 | Acceptance (rule, the record's shape; ru | the gardening record has no length cap. Each batched word carries the full per-item spine the owner-… | **C2** |
| A | FR-A10 | 6 | Acceptance (rule, windows are calendar d | the gardening window is the measurement window for the trend counts (forward share against the dial,… | **C2** |
| A | FR-A10 | 7 | Acceptance (rule, the tripwire on the pa | when the owner says at any walk that the pass or its keep-or-retire list is taking too long, or an i… | **C2** |
| A | FR-B1 | 1 | Acceptance (rule): | standing machinery may watch the work; it never watches other machinery. A guard's complete verifica… | **C3** |
| A | FR-B1 | 2 | Acceptance (rule, the boundary, precisel | evidence that a single act of work actually executed, riding in-band with that act (a control probe… | **C3** |
| A | FR-B1 | 3 | Acceptance (rule, tests, both sides of t | a guard's own tests, its birth bite-proof retained as a regression pin, are part of its diet and liv… | **C3** |
| A | FR-B1 | 4 | Acceptance (rule, the citation is record | "nothing mechanically watches guard X" stops being a buildable finding. It is answered by citing thi… | **C3** |
| A | FR-B1 | 5 | Acceptance (rule): | what survives of the old trust-floor framing is the **ground-truth sources** list *(renamed from "on… | **C3** |
| A | FR-B1 | 6 | Acceptance (record, the verification pol | the verification-strategy spec's guards-on-guards set (a named-edit record schema, a lane guard, a c… | outside the epic: the verification-strategy spec's own children (#1105), reciprocal seam R28 |
| A | FR-B1 | 7 | Acceptance (rule): | this rule is enforced as prose at the front door and the vet, deliberately. A gate that enforced it… | **C3** |
| A | FR-B2 | 1 | Acceptance (rule): | the four shapes, preferred upward: 1, make the bad state impossible; 2, verify at an already-trusted… | **C3** |
| A | FR-B2 | 2 | Acceptance (rule, rung 4's three birth d | a detector is admitted only with (i) a bite-proof: it demonstrably fires on a planted defect, and "d… | **C3** |
| A | FR-B2 | 3 | Acceptance (rule, the widened third duty | any hand-maintained parallel enumeration (a field list patched per-site, an enum whose consumers are… | **C3** |
| A | FR-B2 | 4 | Acceptance (rule, scope line): | the test suite is machinery, at two distinct granularities. Detector-shaped tests (drift pins, invar… | **C3** |
| A | FR-B2 | 5 | Acceptance (rule, retroactivity bounded; | the three birth duties bind at birth: new detectors from the stamp forward. An existing detector-sha… | **C3** |
| A | FR-B2 | 6 | Acceptance (rule): | enforced as prose at the door and the vet, same rationale as FR-B1.… | **C3** |
| A | FR-B3 | 1 | Acceptance (rule, the unit): | the keep-or-retire list's unit is the **plugin component**: one census mechanism. Doctrine sections… | **C6** |
| A | FR-B3 | 2 | Acceptance (rule, the line; reshaped 202 | each component gets a keep-or-retire entry of six fields: the component and the cost or annoyance th… | **C6** |
| A | FR-B3 | 3 | Acceptance (rule, condition shapes, clos | a retirement condition takes one of three shapes, chosen per component. Catch-based: no real catch i… | **C6** |
| A | FR-B3 | 4 | Acceptance (rule, well-formedness bar): | a well-formed condition names its signal (which of the three shapes, counting what), its window, and… | **C6** |
| A | FR-B3 | 5 | Acceptance (rule, tags; ruled 2026-09-05 | each component carries one of four tags, set at the rollout from the Part C classification (at birth… | **C6** |
| A | FR-B3 | 6 | Acceptance (rule, engine family): | where a component guards a model behavior, its notes record the engine family the evidence was obser… | **C6** |
| A | FR-B3 | 7 | Acceptance (rule, consumer evidence; rul | a component's evidence comes from wherever it is observed: this repo, a consuming project, an extern… | **C6** |
| A | FR-B3 | 8 | Acceptance (rule, unmeasured): | "unmeasured" is the state of a component with no catch, citation, or usage signal at all, and of a c… | **C6** |
| A | FR-B3 | 9 | Acceptance (rule, foundational component | a **foundational component** carries no retirement condition and never enters the queue; changing on… | **C6** |
| A | FR-B3 | 10 | Acceptance (rule, authority surfaces; ru | a condition on a component that implements an owner hard line proposes like every other condition, a… | **C6** |
| A | FR-B3 | 11 | Acceptance (rule, the queue; ruled 2026- | fired components enter a queue ordered by the mass they would reclaim, counted as lines of code, tes… | **C6** |
| A | FR-B3 | 12 | Acceptance (rule, the rollout, no sittin | the landing epic's keep-or-retire rollout child drafts a condition for every component (the census m… | **C6** |
| A | FR-B3 | 13 | Acceptance (rule, births): | a new component ships with its retirement condition and its tag at birth (FR-B2 duty ii). The rollou… | **C6** |
| A | FR-B3 | 14 | Acceptance (rule, the tripwire on the in | FR-A10 states it, in one place: when the keep-or-retire list outlasts the rest of the pass, or anyon… | **C2** |
| A | FR-B4 | 1 | Acceptance (rule): | the silent-failure question keeps its full force on the work. The class of "watch the guard" finding… | **C3** |
| A | FR-B4 | 2 | Acceptance (rule, what routes to the doo | a review finding that proposes new standing machinery (a new detector, gate, watcher, census, or a t… | **C3** |
| A | FR-B4 | 3 | Acceptance (rule, uncalibrated projects  | in a project whose door is not yet calibrated (FR-E1), a machinery-proposing finding routes to the o… | **C3** |
| A | FR-B4 | 4 | Acceptance (rule): | the router-first lane call, the deferral disposition contract, and round-count calming are designed… | **C3** |
| A | FR-B4 | 5 | Acceptance (record, one more design inpu | the child also takes "fewer lens prompts with family diversity kept" as an input, with #131 as the i… | **C8** |
| A | FR-B5 | 1 | Acceptance (rule, posture): | when a model-driven caller misses an exact token, the first ask is "can the interface shrink, or the… | **C1** |
| A | FR-B5 | 2 | Acceptance (rule, declared variance): | every LLM-backed surface's existing contract doc declares its variance envelope. The hard shell neve… | **split:** C10 owns the dispatch shell's declared envelope in the dispatch-mechanics doc; C13 owns the review loop's in the round-driver reference (the posture sentence is FR-B5's first bullet, C1) |
| A | FR-B5 | 3 | Acceptance (rule, the roster): | the initial roster of declared surfaces is the set of surfaces the landing epic's children touch. Th… | **split:** C10 owns the dispatch shell's declared envelope in the dispatch-mechanics doc; C13 owns the review loop's in the round-driver reference (the posture sentence is FR-B5's first bullet, C1) |
| A | FR-B5 | 4 | Acceptance (rule, the emphasis, consumer | the hard shell must stay tight. An unwieldy shell recreates engine 7 inside the treatment for it.… | **C1** |
| A | FR-B5 | 5 | Acceptance (rule, at the door): | in-envelope variance is not defect evidence. A filing must show the shell was breached, or, only whe… | **C2** |
| A | FR-B6 | 1 | Acceptance (rule, workaround markers): | every platform workaround is tagged as a workaround with a named delete-when condition ("delete when… | **C6** |
| A | FR-B6 | 2 | Acceptance (record, markers whose condit | six orchestration pieces have met their delete-when condition and are retirement candidates behind o… | **split:** C9 owns the trial itself (one wave across all three accounts on the background-session path, against the failure classes, recorded in LEDGERS, by hand on the harness primitives, no replacement code first, with the piece-by-piece receipt); C15 owns the retirements that wait on that receipt and, unconditionally, the plugin-root seam and its lint |
| A | FR-B6 | 3 | Acceptance (record, quota retired outrig | quota exhaustion is no longer a thing the plugin watches. The usage poller is parked, not deleted. P… | **C15** |
| A | FR-B6 | 4 | Acceptance (rule, no line budget; ruled  | there is no line budget and no knob count. Process mass is governed by three layers and one instrume… | **C7** |
| A | FR-B6 | 5 | Acceptance (rule, the document layer; ru | each charter is a map: one short section per duty, stating the rule and its completion criterion, wi… | **C7** |
| A | FR-B6 | 6 | Acceptance (rule, the sentence layer; ru | the technical-writing modes (reference, procedure, explanation) and the unslop filter, minus its met… | **C1** (moved from C3 on 2026-09-15, owner-ruled at the review of PR #1277: the prose standard lands with its first application) |
| A | FR-B6 | 7 | Acceptance (rule, the glossary and stabl | a canonical glossary owns the vocabulary (Part 7 seeds it) and owns a stable slug for every rule tha… | **C1** |
| A | FR-B6 | 8 | Acceptance (rule, doctrine is cut where  | prose has no event of its own to count, so it gets no meter, standing or one-time. The thirty-day ci… | **C7** |
| A | FR-B6 | 9 | Acceptance (record, the interim measurem | the always-loaded set at ratification is 3,826 lines across seven files, about 49,000 words, the CP2… | **C7** |
| A | FR-B7 | 1 | Acceptance (rule): | every rule, schema, and contract gets exactly one home; every other surface points, never restates.… | **C3** |
| A | FR-B7 | 2 | Acceptance (rule): | a drift pin on a mirror is a delete signal (delete the mirror), not a maintenance obligation. Foundi… | **C3** |
| A | FR-B7 | 3 | Acceptance (rule): | the surfaces that today still license the drift-tested-copy pattern (a dual-pattern rule, pointer al… | **C3** |
| A | FR-B7 | 4 | Acceptance (rule, the pin rule; ruled 20 | a test on a doctrine surface pins structure, never sentences. It may assert that a check id, a headi… | **C3** |
| A | FR-C1 | 1 | Acceptance (rule): | forward share, the fraction of capacity making progress on new goals versus maintaining the machine,… | **split:** C1 owns the forward-share principle in PHILOSOPHY, the test-pilot classification convention, and the sentence citing the recorded baseline; C2 owns the decisions-asked count as a gardening-record line |
| A | FR-C1 | 2 | Acceptance (rule, classification convent | test-pilot work classifies as product; it exercises the product, not the machine. Folded-in adoption… | **split:** C1 owns the forward-share principle in PHILOSOPHY, the test-pilot classification convention, and the sentence citing the recorded baseline; C2 owns the decisions-asked count as a gardening-record line |
| A | FR-C1 | 3 | Acceptance (record, the baseline, polari | measured 2026-08-30 and corrected at CP3: outward-facing work is about 14% of open board stock and a… | **split:** C1 owns the forward-share principle in PHILOSOPHY, the test-pilot classification convention, and the sentence citing the recorded baseline; C2 owns the decisions-asked count as a gardening-record line |
| A | FR-C1 | 4 | Acceptance (rule, the decisions-asked co | one count is recorded in every gardening record (FR-A10 duty 4), and nothing compares it yet: the **… | **split:** C1 owns the forward-share principle in PHILOSOPHY, the test-pilot classification convention, and the sentence citing the recorded baseline; C2 owns the decisions-asked count as a gardening-record line |
| A | FR-E1 | n1 | numbered | Severity ladder**: named bands with concrete examples. Seeding instruc… | **C17** |
| A | FR-E1 | n2 | numbered | P0 definition**: which ladder band(s) plus evidence qualify.… | **C17** |
| A | FR-E1 | n3 | numbered | The dial**: machinery-share ceiling (plugin default 20–30%; FR-A6's co… | **C17** |
| A | FR-E1 | n4 | numbered | Budget N**: explicit, or derived from the dial per FR-A6.… | **C17** |
| A | FR-E1 | n5 | numbered | Ground-truth sources** (FR-B1).… | **C17** |
| A | FR-E1 | n6 | numbered | Digest floor** (FR-A8).… | **C17** |
| A | FR-E1 | n7 | numbered | Condition windows** (FR-B3): the catch, citation, and usage defaults,… | **C17** |
| A | FR-E1 | n8 | numbered | Sanctioned stacking tool** (FR-A9).… | **C17** |
| A | FR-E1 | n9 | numbered | Keep-or-retire reporting** (FR-B3's consumer evidence): whether this p… | **C17** |
| A | FR-E1 | n10 | numbered | Declared threat model** (Part 7): free prose in the configure profile… | **C17** |
| A | FR-E1 | n11 | numbered | Guardian staleness thresholds** (FR-A10 duty 6): merges and days since… | **C17** |
| A | FR-E1 | n12 | numbered | The keep list** (Part 7, verification change 3): the short stamped fil… | **C17** |
| A | FR-E1 | n13 | numbered | The material-consequence line** *(ruled 2026-09-12 at the read-back)*:… | **C17** |
| A | FR-E1 | 1 | Acceptance (rule, declared dependencies; | four surfaces the rules above read but do not create are named here, so a consuming project can chec… | **C17** |
| A | FR-E1 | 2 | Acceptance (rule, "machinery", defined;  | everywhere the dial, N, forward share, and FR-C1's guardrails read "machinery", the word means work… | **split:** C2 owns the definition of machinery, the classification test, the judgment-only rule, and the label vocabulary in issue-contract.md; C17 owns creating the two kind labels per consuming repo at calibration |
| A | FR-E1 | 3 | Acceptance (rule, fail direction): | missing configuration items fail closed for authority-expanding acts. With no stamped ladder, no ban… | **C17** |
| A | FR-E1 | 4 | Acceptance (rule): | each configuration item's stamped value lives in the configure profile: its one home (Part 6).… | **C17** |
| A | FR-E1 | n1 | numbered | Severity ladder** *(ruled 2026-09-13, stamp sitting)*:… | **C17** |
| A | FR-E1 | n2 | numbered | P0 definition** *(ruled 2026-09-13)*: Band 1 by citation plus field ev… | **C17** |
| A | FR-E1 | n3 | numbered | Dial: one third** *(ruled 2026-09-13 at the stamp sitting; the advisor… | **C17** |
| A | FR-E1 | n4 | numbered | Budget N** *(ruled 2026-09-13)*: derived. One third of the wave's lane… | **C17** |
| A | FR-E1 | n5 | numbered | Ground-truth sources** *(ruled 2026-09-13, renamed)*: CI's exit code o… | **C17** |
| A | FR-E1 | n6 | numbered | Digest floor: ruled (a), pre-stamp, 2026-08-31** (owner-decisions walk… | **C17** |
| A | FR-E1 | n7 | numbered | Condition windows: ruled 2026-09-05.** Catch 45, citation 45, usage 60… | **C17** |
| A | FR-E1 | n8 | numbered | Stacking tool** *(ruled 2026-09-13)*: `gh-stack`.… | **C17** |
| A | FR-E1 | n9 | numbered | Keep-or-retire reporting** *(ruled 2026-09-13)*: this repo is the keep… | **C17** |
| A | FR-E1 | n10 | numbered | Threat model: ruled and written 2026-09-06** (sitting 1) in this repo'… | **C17** |
| A | FR-E1 | n11 | numbered | Guardian staleness** *(ruled 2026-09-13)*: the plugin defaults, ten me… | **C17** |
| A | FR-E1 | n12 | numbered | Keep list** *(ruled 2026-09-13)*: seeded by the verification-policy ch… | **C17** |
| A | FR-E1 | n13 | numbered | Material-consequence line** *(ruled 2026-09-13 at the stamp sitting, a… | **C17** |
| A | FR-F1 | 1 | Acceptance (rule): | approval is still the owner's and is never delegated. It is given as a scoped word in chat after the… | **C1** (all four homes of promise 1 amended together: PHILOSOPHY, the covenant, showrunner duty 6, merge-train.md) |
| A | FR-F1 | 2 | Acceptance (rule, a red merge train; rul | a red on the train (a per-lane green that goes red on the union or on main's post-merge run) is fixe… | **C1** (all four homes of promise 1 amended together: PHILOSOPHY, the covenant, showrunner duty 6, merge-train.md) |
| A | FR-F1 | 3 | Acceptance (rule, force-push): | the advisor states the reason in chat first and proceeds on a word; the word and the reason are reco… | **C1** (all four homes of promise 1 amended together: PHILOSOPHY, the covenant, showrunner duty 6, merge-train.md) |
| A | FR-F1 | 4 | Acceptance (rule, releases and publish;  | by default the advisor does not execute a release merge or a publish: it asks in chat and the owner… | **C1** (all four homes of promise 1 amended together: PHILOSOPHY, the covenant, showrunner duty 6, merge-train.md) |
| A | FR-F1 | 5 | Acceptance (rule, the floor): | there is no mechanical merge floor. The registry line "a mechanical merge floor" carries the trigger… | **C1** (all four homes of promise 1 amended together: PHILOSOPHY, the covenant, showrunner duty 6, merge-train.md) |
| A | FR-F2 | 1 | Acceptance (rule): | the whole family retires: the hook, `lib/owner_authority.py`, the per-project allowlist override and… | **C5** |
| A | FR-F2 | 2 | Acceptance (record, why): | the gate fired zero times in earnest, produced false positives, and was the annoyance; talking PRs t… | **C5** |
| A | FR-F2 | 3 | Acceptance (rule, the other hooks): | the worktree guard (structural, three catches), source_guard (eight catches), the bootstrap, and the… | **split:** C5 owns keeping the four hooks that stay and retiring the version-skew check with its trigger; C6 owns the bash-timeout hook's log line and citation-based condition |
| A | FR-F3 | 1 | Acceptance (rule): | superheroes reviews repos its owner trusts. Review of code of untrusted provenance, code that could… | **C1** |
| A | FR-F3 | 2 | Acceptance (rule, what changes): | the sanitized view shrinks to what trusted-repo pollution needs (#563, #684): a neutral-cwd export a… | **C16** |
| A | FR-F3 | 3 | Acceptance (rule, the seats read the dec | each project declares its threat model in its configure profile (FR-E1 item 10). The security lens r… | **split:** C4 owns the security lens sentence; C17 owns configuration item 10's definition |
| A | FR-F3 | 4 | Acceptance (rule, the machinery map's co | every component on the owner's machinery map carries what it assumes: A, an untrusted repo; B, agent… | **C16** |
| A | FR-F4 | 1 | Acceptance (rule): | Claude Code is the supported host. Codex loads the skills and runs the discipline layer with no host… | **C4** |
| A | FR-F4 | 2 | Acceptance (rule, vocabulary; R4): | "the host model" means whatever runs the current session, read from the hook payload and never assum… | **C4** |
| A | FR-F4 | 3 | Acceptance (record, deferred under R1's  | the Codex hook wiring, charter state outside the transcript, the dual-host acceptance run, and any C… | **C4** |
| A | FR-F5 | 1 | Acceptance (rule): | native in-session seats are declared live, never probed: a LEDGERS §3 residual with R1's trigger, an… | **split:** C14 owns the engine registration and the certification disclosure line; C4 owns the LEDGERS section 3 residual |
| A | FR-F5 | 2 | Acceptance (rule, Astra): | GPT-6 Astra becomes the codex reviewer-deep cell at effort high *(ruled 2026-09-14 at the stamp sitt… | **C14** |
| A | FR-F6 | n1 | numbered | No nightly ledger or classifier.** The escape rate is the gardening pa… | outside the epic: the verification-strategy spec's own children (#1105), reciprocal seam R28 |
| A | FR-F6 | n2 | numbered | No day count for bulk removal.** Bulk removal of behavior tests is an… | outside the epic: the verification-strategy spec's own children (#1105), reciprocal seam R28 |
| A | FR-F6 | n3 | numbered | Delete on contact; the keep list is the only record** *(simplified 202… | **split:** outside the epic (#1105's children) owns the keep-list seed and the verification spec's FR-1 amendment; C3 owns the builder's at-contact classification step as review-discipline text, which every child carries through R28 |
| A | FR-F6 | n4 | numbered | Mutation testing goes forward.** Bought, not built (mutmut or cosmic-r… | outside the epic: the verification-strategy spec's own children (#1105), reciprocal seam R28 |
| A | FR-F6 | n5 | numbered | The receipt fields land now; what runs where waits on weekly-eats' les… | outside the epic: the verification-strategy spec's own children (#1105), reciprocal seam R28 |
| A | FR-F6 | n6 | numbered | No guards on guards.** FR-B1 records it; the one check the sitting kep… | outside the epic: the verification-strategy spec's own children (#1105), reciprocal seam R28 |
| A | FR-F6 | n7 | numbered | Stable slugs.** FR-B6 records it.… | **C1** |
| A | FR-F7 | 1 | Acceptance (rule, guardian): | the guardian hold is lifted: weekly-eats ran three sweeps and consumed two decisions before the hold… | done at the stamp (2026-09-14), nothing owed |
| A | FR-F7 | 2 | Acceptance (record, the rest): | the detective earns its keep (four dispatches, three fixes); test-pilot is product (ruled at E); the… | done at the stamp (2026-09-14), nothing owed |
| B | FR-M1 | 1 | Acceptance (rule): | a KEEP row citing none of the three grounds is a defect of the derivation; "it could matter" keeps n… | **CLOSED-DERIVATION** |
| B | FR-M1 | 2 | Acceptance (rule, closed row-kind list): | the demand kinds are required key, exact enum value, mandatory sequence step, refusal condition, and… | **CLOSED-DERIVATION** |
| B | FR-M1 | 3 | Acceptance (rule, grouping licence): | a coherent family of demands may share one row when one ground covers every member identically. The… | **CLOSED-DERIVATION** |
| B | FR-M1 | 4 | Acceptance (rule, closed column list): | the columns are likewise closed and enumerated here: row id; demand kind; disposition; ground + cita… | **CLOSED-DERIVATION** |
| B | FR-M1 | 5 | Acceptance (rule, completeness, two legs | the row set derives from two legs. Leg (i) is the contract's machine-enumerable declared surface. Fo… | **CLOSED-DERIVATION** |
| B | FR-M1 | 6 | Acceptance (rule, parked rows hold their | an owner PARK still standing when the epic children launch means the affected surface's children hol… | done at the stamp (2026-09-14), nothing owed |
| B | FR-M1 | 7 | Acceptance (rule, the closing rule: a on | the tables drive the children and then close. Each child moves the live declaration of its surface i… | **split:** C10, C11, C12, and C13 each own the closing note and the live-declaration move for their own surface (R26) |
| B | FR-M2 | 1 | Acceptance (rule): | every surviving KEEP-(a) demand must be checkable from artifacts that are side effects of performing… | **C12** |
| B | FR-M2 | 2 | Acceptance (record, one design input; ru | the check-runner as a plain shell task lands here as its home. The shell certifies evidence, never p… | **C7** |
| B | FR-M2 | 3 | Acceptance (rule, engagement is telemetr | whenever the machine needs to know that a seat actually looked (a review seat, a dispatch seat, a la… | **split:** C12 owns the unrun-review check reading telemetry; C14 owns the launcher's seat canary reading the transcript; C11 owns the conformance probe's engagement read |
| B | FR-M2 | 4 | Acceptance (rule, a tripwire firing sepa | every tripwire this spec names (FR-D3, FR-D6, FR-D9, FR-S1, FR-S7) is a prompt for an owner conversa… | **C2** |
| B | FR-M3 | 1 | Acceptance (rule): | every refusal names the accepted range or shape, meaning what would have been accepted, in the refus… | **split:** C10 owns the dispatch shell's refusals; C13 owns the round driver's |
| B | FR-M3 | 2 | Acceptance (rule): | agents repair from error text. A refusal that names its remedy converts a lost round into a self-cor… | **split:** C10 owns the dispatch shell's refusals; C13 owns the round driver's |
| B | FR-M4 | 1 | Acceptance (rule): | tolerant reading pairs with loud echo. Every resolved load-bearing parameter lands explicitly in the… | **split:** C10 owns the dispatch shell's echo set; C13 owns the round driver's |
| B | FR-M4 | 2 | Acceptance (rule, the echo set, complete | the derivation table carries a `resolves-caller-input` column on every row, whatever its disposition… | **split:** C10 owns the dispatch shell's echo set; C13 owns the round driver's |
| B | FR-M5 | 1 | Acceptance (rule): | each re-derived surface's contract doc declares its envelope per Spec A FR-B5. The surviving hard sh… | **split:** C10 owns the dispatch-mechanics envelope declaration; C13 owns the round-driver envelope declaration |
| B | FR-M5 | 2 | Acceptance (rule, soft still means bound | a declared-soft surface whose variance is count-, budget-, or retry-shaped (rounds, confirmations, r… | **split:** C10 owns the dispatch-mechanics envelope declaration; C13 owns the round-driver envelope declaration |
| B | FR-M6 | 1 | Acceptance (rule): | if a re-derived shell keeps any hand-maintained enumeration (an argument list, an accepted-shapes li… | **C10** |
| B | FR-M7 | 1 | Acceptance (rule, what the class table a | every row in the annexes belongs to exactly one class line above, and the counts are the annexes' ow… | **CLOSED-DERIVATION** |
| B | FR-M7 | 2 | Acceptance (rule, the coverage check): | FR-D1's class-coverage rule (each escape class keeps at least one preventer) is checked against the… | **C12** |
| B | FR-M7 | 3 | Acceptance (rule, the self-vouching KEEP | the annexes carry about fifty KEEP-(b) rows whose only citation is the code that enforces them or th… | **split:** C10 owns the C1 annex's family assignment (scrub and containment keep; the rest move, echoing what they resolve when they default or accept, echoing nothing when dropped); C13 owns the D1 annex's |
| B | FR-M7 | 4 | Acceptance (rule, the parks): | the four row-level PARKs (D1-031, D1-068, C1-R08, C1-E26), the disclosure-channel set (D1 PARK-03, a… | done at the stamp (2026-09-14), nothing owed |
| B | FR-D1 | 1 | Acceptance (rule): | the certification shell's escape-receipt rows derive from exactly the escapes certification exists t… | **C12** |
| B | FR-D1 | 2 | Acceptance (rule, class coverage survive | the derivation's verification pass confirms each of the four escape classes names at least one survi… | **C12** |
| B | FR-D2 | 1 | Acceptance (test, must-certify): | the re-derived contract is exercised against the FR#8 specimen shape: a 16-seat out-of-manifest audi… | **C12** |
| B | FR-D2 | 2 | Acceptance (test, must-refuse): | the paired counter-specimen: seat outputs authored but never executed must still refuse, in three sh… | **C12** |
| B | FR-D2 | 3 | Acceptance (rule, provenance binding, th | adopted out-of-manifest artifacts are accepted only with all three bindings. Content binding: the `p… | **C12** |
| B | FR-D2 | 4 | Acceptance (rule): | both specimens are preserved as fixtures with the derivation, and the must-certify fixture preserves… | **C12** |
| B | FR-D2 | 5 | Open decision, RULED 2026-09-13 at the s | the third binding is a would-refuse narrowing shipped inside an easing. A well-formed hand-landed en… | **C12** |
| B | FR-D3 | 1 | Acceptance (rule, baseline first): | before the shrink lands, the derivation records the pre-shrink baseline in the D1 values annex (its… | **C12** |
| B | FR-D3 | 2 | Acceptance (rule, the tripwire): | signal = usage-based: post-shrink full lanes reaching certified completion versus full lanes run, sa… | **C12** |
| B | FR-D3 | 3 | Acceptance (rule, the consumer report's  | a consumer report is an issue on the plugin repo carrying the `consumer-report` label and the shippe… | **C6** |
| B | FR-D3 | 4 | Acceptance (rule, both sides of the ledg | post-shrink escapes in FR-D1's classes are misses-log entries (Spec A FR-A4, read at every gardening… | **C12** |
| B | FR-D3 | 5 | Acceptance (rule): | the contract does not get a second re-derivation. The next stop is FR-D9's successor, or retirement.… | **C12** |
| B | FR-D3 | 6 | Acceptance (rule, where this condition l | this FR is the D1 loop component's usage-based retirement condition on Spec A's keep-or-retire list.… | **C6** |
| B | FR-D4 | 1 | Acceptance (rule): | the fold-owned guidance design is ruled: decision 1=b at the durable owner-gate ruling (PR #1255 iss… | **C13** |
| B | FR-D4 | 2 | Acceptance (rule, fail-closed leg): | any disposition of the guidance-channel row other than ground-(b) KEEP (leaving the contract, downgr… | **C13** |
| B | FR-D5 | 1 | Acceptance (rule): | no loop-state field is removed before the loop leaves under FR-D9. The store is what the driver writ… | **C12** |
| B | FR-D5 | 2 | Acceptance (record, what was cut and why | this FR formerly specified a storage shrink executed as a state-version migration, with a halt-integ… | **C12** |
| B | FR-D5 | 3 | Acceptance (rule, consumer-visible shape | consumers key vets on certification shapes (weekly-eats keys on `full-panel-confirmed`), so D1-029's… | **C12** |
| B | FR-D6 | 1 | Acceptance (rule): | the comparator: the driver hub's self-repair churn after the shrink, measured as the driver-core (ce… | **C12** |
| B | FR-D6 | 2 | Acceptance (rule, the question changed s | the structural split is no longer the successor. FR-D9's successor removes the loop's state machine… | **C12** |
| B | FR-D8 | 1 | Acceptance (rule, the concept): | a review certifies when every finding raised has a disposition and every disposition has a receipt o… | **split:** C12 owns what the receipt writer derives, checks, and refuses; C13 owns what the loop records and bounds (rounds, dispositions given, the canary leaving the gate) |
| B | FR-D8 | 2 | Acceptance (rule, "raised", "disposition | a finding is raised when a seat's result lands it in the record. A finding dropped at verification w… | **split:** C12 owns what the receipt writer derives, checks, and refuses; C13 owns what the loop records and bounds (rounds, dispositions given, the canary leaving the gate) |
| B | FR-D8 | 3 | Acceptance (rule, the third disposition) | a finding may be dispositioned out-of-scope-with-follow-up: correct, not this change's to fix, and c… | **split:** C12 owns what the receipt writer derives, checks, and refuses; C13 owns what the loop records and bounds (rounds, dispositions given, the canary leaving the gate) |
| B | FR-D8 | 4 | Acceptance (rule, what the third disposi | deferral is where this repo's escapes come from: of sixty-five escape stories with a known status, f… | **split:** C12 owns what the receipt writer derives, checks, and refuses; C13 owns what the loop records and bounds (rounds, dispositions given, the canary leaving the gate) |
| B | FR-D8 | 5 | Acceptance (rule, who dispositions, and  | dispositions are given by the review's orchestrator (the maker side, exactly as today) and recorded… | **split:** C12 owns what the receipt writer derives, checks, and refuses; C13 owns what the loop records and bounds (rounds, dispositions given, the canary leaving the gate) |
| B | FR-D8 | 6 | Acceptance (rule, an incomplete journal  | the receipt writer reconciles the journal against itself before it emits: every seat the seat map de… | **C12** |
| B | FR-D8 | 7 | Acceptance (rule, the four-class check): | the receipt writer runs four checks over that receipt, one per FR-D1 escape class, each artifact-che… | **C12** |
| B | FR-D8 | 8 | Acceptance (rule, hand-landed results): | a hand-landed seat result is a plain result file that goes through the same receipt writer and the s… | **C12** |
| B | FR-D8 | 9 | Acceptance (rule, the six cases; ruled 2 | the receipt writer's birth bite-proof (Spec A FR-B2's birth duties) is a fixed suite of six cases, e… | **C12** |
| B | FR-D8 | 10 | Acceptance (rule, the fence): | this FR ships behind one state-version bump under the driver's existing supported-versions mechanism… | **C12** |
| B | FR-D8 | 11 | Acceptance (rule, what this changes in t | the D1 rows stand as the child's inventory. Rows that implement the loop's state machine (latches, r… | **split:** C12 owns adding the receipt writer and its four checks as new D1 rows with their re-verification, live-declaration move, and closing note; C13 owns the existing rows it touches and their closing notes |
| B | FR-D8 | 12 | Acceptance (rule, the output is the succ | the receipt this FR produces is exactly the artifact FR-D9's checks read. Building FR-D8 is therefor… | **C12** |
| B | FR-D9 | 1 | Acceptance (rule, what the successor is) | certification without the loop's state machine. The four-class check and the receipt writer (FR-D8)… | **C13** |
| B | FR-D9 | 2 | Acceptance (rule, ruled in principle, th | the successor is ruled as the direction, so that no re-litigation of the direction is needed when th… | **C13** |
| B | FR-D9 | 3 | Acceptance (rule, the tripwire, three co | read at each gardening pass (Spec A FR-A10 duty 2 sweeps this spec's tripwires alongside the retirem… | **C13** |
| B | FR-D9 | 4 | Acceptance (rule, the coverage check run | before any line leaves, FR-D1's class-coverage rule is re-run against the FR-D8 receipt shape rather… | **C13** |
| B | FR-D9 | 5 | Acceptance (rule, sequencing against the | the deletion does not start while FR-D3's tripwire window is open, unless the owner rules it closed… | **C13** |
| B | FR-D9 | 6 | Acceptance (record, what this amends): | the CP2 verdict's D1 sequence, "shrink first, split behind it", is amended on post-CP2 evidence (the… | **C13** |
| B | FR-S1 | 1 | Acceptance (rule): | C1's fix history is two populations, and the re-derivation treats them as its starting classificatio… | **C10** |
| B | FR-S1 | 2 | Acceptance (rule, precedence): | the populations are guidance; the table's per-row grounds decide (FR-M1). A token serving both sides… | **C10** |
| B | FR-S1 | 3 | Acceptance (rule, the boundary parks own | a row inside the ruled parse/scrub/forfeit boundary that the derivation proposes to MOVE parks to th… | **C10** |
| B | FR-S1 | 4 | Acceptance (rule, entry-surface changes  | a dropped, renamed, or newly required argument ships without an alias window. The refusal a stale ca… | **C10** |
| B | FR-S1 | 5 | Acceptance (record, what was cut and why | the draft carried a one-window deprecation alias with a loud echo, a default-with-echo window for ne… | **C10** |
| B | FR-S1 | 6 | Acceptance (rule, the transport contract | the record behind this rule: the forfeit ledger holds zero rows (the attribution instrument was neve… | **C11** |
| B | FR-S1 | 7 | Acceptance (rule, the benefit is priced, | the native move retires the marker parser and the salvage tiers, the code behind the ten transport-c… | **C11** |
| B | FR-S1 | 8 | Acceptance (rule, supervision stays; cap | the journal, the run lock, and max-wait stay as hard shell. The stdout cap, the salvage paths, and t… | **C10** |
| B | FR-S1 | 9 | Acceptance (rule, the tripwire on either | after the dispatch-shell child lands, a second grader or salvage fix (a `fix` commit touching the ma… | **C11** |
| B | FR-S1 | 10 | Acceptance (record, what the owner decli | two seats per lens as redundancy (prohibitively expensive, and it treats the engines as the problem… | **C11** |
| B | FR-S2 | 1 | Acceptance (rule): | an off-allowlist model cannot be dispatched. The dispatch-guard check is wired into the dispatch sur… | **C10** |
| B | FR-S3 | 1 | Acceptance (rule): | #649 (one seat-bundle contract at every seam: `{vendor, model, effort}` passed intact, absent-effort… | **C10** |
| B | FR-S3 | 2 | Acceptance (rule, effort is echoed, not  | absent-effort unrepresentable composes with FR-M4. The resolved effort, and its source, lands in the… | **C10** |
| B | FR-S4 | 1 | Acceptance (rule): | the seven field-observed doc-gap legs from #1244/PR #1250 are adopted as friction specimens, not as… | **C10** |
| B | FR-S5 | 1 | Acceptance (rule): | the dispatch selftest's contract doc states plainly that it proves configuration, never engine liven… | **C11** |
| B | FR-S5 | 2 | Acceptance (rule, the conformance probe, | the wave-preflight probe is a conformance probe per engine per wave: one dispatch on the engine's na… | **C11** |
| B | FR-S5 | 3 | Acceptance (rule, the two Claude populat | native in-session seats (the `Agent` tool) are declared live and never probed; the docs-truth child… | **C14** |
| B | FR-S6 | 1 | Acceptance (rule): | the dispatch-trust caching policy question folded here by the B1 ruling (the acute panel-collapse de… | **C10** |
| B | FR-S7 | 1 | Acceptance (rule): | three refusal round-trips in a row on one caller's dispatch invocations (a refusal that cost the cal… | **C10** |
| B | FR-S7 | 2 | Acceptance (record, what was cut and why | this FR formerly carried a refusal-rate comparator in FR-D3's shape: a pre-shrink baseline measured… | **C10** |
| B | FR-S8 | 1 | Acceptance (rule): | the dispatch shell reviews repos that the owner running it trusts (Spec A FR-F3's "repos its owner t… | **C16** |
| B | FR-S8 | 2 | Acceptance (rule, stripped changes are s | the export keeps the agent-configuration paths out of the tree the seats run in (the twelve config f… | **C16** |
| B | FR-S8 | 3 | Acceptance (rule, what retires and what  | export-time path containment (the refusal of a symlink that points outside the export, recorded toda… | **C16** |
| B | FR-S8 | 4 | Acceptance (rule, the seats read the pro | the security lens reads the project's declared threat model (Spec A FR-E1 item 10). An accepted expo… | **C4** |
| B | FR-S9 | 1 | Acceptance (rule): | GPT-6 Astra registers under the codex vendor as the top rung (ladder terra, sol, astra), becomes the… | **C14** |
| B | FR-S9 | 2 | Acceptance (rule, the gate): | the registration lands only after one live security-lens dispatch on a planted fail-open returns a f… | **C14** |

**Counts.** C1: 7, C10: 14, C11: 6, C12: 24, C13: 9, C14: 4, C15: 1, C16: 5, C17: 29, C2: 45, C3: 20, C4: 4, C5: 3, C6: 16, C7: 5, C8: 1, CLOSED-DERIVATION: 6, OUTSIDE-VERIFICATION: 6, SPLIT-B5: 2, SPLIT-B6: 1, SPLIT-C1: 4, SPLIT-D8: 5, SPLIT-E1: 1, SPLIT-F1: 5, SPLIT-F3: 1, SPLIT-F5: 1, SPLIT-F6: 1, SPLIT-M1: 1, SPLIT-M2: 1, SPLIT-M3: 2, SPLIT-M4: 2, SPLIT-M5: 2, SPLIT-M7: 1, STAMP: 5. Total criteria: 240. Unallocated: 0.

**Re-check 2026-09-15 (package fix after the stamp; owner-ruled at the review of PR #1277):** FR-B6 bullet 6 (the sentence layer, `rubric/prose-standard.md`) moves from C3 to C1 so the standard lands with the founding texts it is first applied to; C3 keeps bullets it owned elsewhere unchanged. Spec A amendments #1 to #4 (FR-F1 twice, FR-F9, FR-C1) touch criteria owned by C1 only; every criterion stays owned once. Register entry R29 (no project provenance on shipped surfaces) added with sixteen consumers.
