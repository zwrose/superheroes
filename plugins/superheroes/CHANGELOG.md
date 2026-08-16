# Changelog

## [0.28.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.27.0...superheroes-v0.28.0) (2026-08-16)


### Features

* **superheroes:** adopt cursor-grok-4.6 as the cursor judge model — replace 4.5, §7.5 pair amendment, post-acquisition family-prose fix (release re-statement of [#1013](https://github.com/zwrose/superheroes/issues/1013)) ([#1033](https://github.com/zwrose/superheroes/issues/1033)) ([fe83ac7](https://github.com/zwrose/superheroes/commit/fe83ac7c53431ef1bbdcf6450926130a5a824125))
* **superheroes:** dispatch-review --mode brief-check — sanctioned diff-less brief-check dispatch through the runner ([#1020](https://github.com/zwrose/superheroes/issues/1020)) ([5dfd186](https://github.com/zwrose/superheroes/commit/5dfd186b5576d1145ec914177778b29a625c05aa))
* **superheroes:** launcher record-outcome --await-exit — wait out the builder's exit so wave_watch loop is the sole watcher ([#1045](https://github.com/zwrose/superheroes/issues/1045)) ([fc14211](https://github.com/zwrose/superheroes/commit/fc14211635ea27113c8631433cce3932b6e644aa))
* **superheroes:** owner-decisions delivery contract — reference, charter pointers, collector preamble, /superheroes:discuss-open-decisions ([#1018](https://github.com/zwrose/superheroes/issues/1018)) ([fc85fdd](https://github.com/zwrose/superheroes/commit/fc85fddf8a1ed96d860b200d3ba893e6c8ee88e0))
* **superheroes:** wave_watch discloses an unresolved transcript read (transcript-unresolved) and searches the lane's recorded config dir ([#1041](https://github.com/zwrose/superheroes/issues/1041)) ([bae2e48](https://github.com/zwrose/superheroes/commit/bae2e48228be9e75f16dbbabbbfbbd7cff174533))
* **superheroes:** wave_watch loop verb — one background arm per batch, arming doctrine rewrite, wave_watch.py rider family (release re-statement of [#1012](https://github.com/zwrose/superheroes/issues/1012)) ([#1032](https://github.com/zwrose/superheroes/issues/1032)) ([aca7b64](https://github.com/zwrose/superheroes/commit/aca7b64a78d726f792faf20c00903e2de7ab5676))


### Bug Fixes

* **superheroes:** dispatch-review carries verdict-shaped results as a first-class kind; retire --schema-path ([#1027](https://github.com/zwrose/superheroes/issues/1027)) ([d675f28](https://github.com/zwrose/superheroes/commit/d675f28e93fbd40650e2af9be9dd159f37a2a24e))
* **superheroes:** emitted seat orders' output contract follows the seat's channel — engine seats emit on stdout, never a landing-path write ([#1043](https://github.com/zwrose/superheroes/issues/1043)) ([eaee0a7](https://github.com/zwrose/superheroes/commit/eaee0a7d51d2ff45835e8541c804188fb03bf95f))
* **superheroes:** empty-object findings members parse as a completed review — close the residual fail-open at the parse boundary ([#1010](https://github.com/zwrose/superheroes/issues/1010)) ([cd3db0c](https://github.com/zwrose/superheroes/commit/cd3db0c129c0ef4fadcad902e03bf26f61ee69b5))
* **superheroes:** owner-authority gate — a `+`-prefixed refspec is a force spelling (asks as force-push) ([#1025](https://github.com/zwrose/superheroes/issues/1025)) ([92d514c](https://github.com/zwrose/superheroes/commit/92d514c81b09c0c98a2dbfcb996046e5ee3411f3))
* **superheroes:** owner-authority gate — state end-of-word once, closing the silent-bypass class ([#1022](https://github.com/zwrose/superheroes/issues/1022)) ([dc6b001](https://github.com/zwrose/superheroes/commit/dc6b0014e7c90eae40870e87e65f57ecdfbd6aae))
* **superheroes:** record-outcome --await-exit accepts up to 1800 s (30 min), sized from the field ([#1048](https://github.com/zwrose/superheroes/issues/1048)) ([236b6cb](https://github.com/zwrose/superheroes/commit/236b6cb340874c389841e70e4788bfb4393b2bbc))
* **superheroes:** resolve a lane's transcript by recorded session id, not inference ([#1029](https://github.com/zwrose/superheroes/issues/1029)) ([9398660](https://github.com/zwrose/superheroes/commit/9398660cd9d9b183e679718c7ed7aa1d3447a3e1))
* **superheroes:** round_driver certification is reachable when the loop converges — last-two-rounds stall breaker, three-choice stall menu with a once-only one-more-round, accept-risk from stalled targets, advance folds run-verify; lens-coverage receipt field ([#1028](https://github.com/zwrose/superheroes/issues/1028)) ([5154a32](https://github.com/zwrose/superheroes/commit/5154a32aa1ae8ba7e6ff7b25c7d8f658305d049a))
* **superheroes:** seat_canary probe --effort is optional so cursor's effort-less config is expressible ([#1019](https://github.com/zwrose/superheroes/issues/1019)) ([60ad237](https://github.com/zwrose/superheroes/commit/60ad2376c4b8a9d1af7bd09108cf8493408cbf57))


### Chores

* **superheroes:** drain the vets-92–105 hygiene collector ([#1005](https://github.com/zwrose/superheroes/issues/1005)) ([#1011](https://github.com/zwrose/superheroes/issues/1011)) ([af7c21f](https://github.com/zwrose/superheroes/commit/af7c21fda25869ccafa041af7b83ceb44f89d9cf))

## [0.27.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.26.0...superheroes-v0.27.0) (2026-08-15)


### Features

* **superheroes:** launcher pre-creates the build worktree and starts the session inside it ([#979](https://github.com/zwrose/superheroes/issues/979)) ([1432aa4](https://github.com/zwrose/superheroes/commit/1432aa480f979187ae5eb1726c6fe6a502fdb5ff))
* **superheroes:** owner-authority allowlist — grantable ref shape for branch-preview workflow dispatches ([#987](https://github.com/zwrose/superheroes/issues/987)) ([879bdf7](https://github.com/zwrose/superheroes/commit/879bdf7a8ba1b8ffc23e02d32b87a22a6ce7c3e7))
* **superheroes:** wave_watch — ledger-driven single-shot wave watcher ([#988](https://github.com/zwrose/superheroes/issues/988)) ([7357fe1](https://github.com/zwrose/superheroes/commit/7357fe175dffa5004a22c18f057429f04f8da90d))


### Bug Fixes

* **superheroes:** dispatch-review result contract — canonical schema, loud rejects, readable clean verdicts, and the demonstrated cause of empty investigated records ([#984](https://github.com/zwrose/superheroes/issues/984)) ([4cc0395](https://github.com/zwrose/superheroes/commit/4cc0395b2e62c2ae654af8e8013840eea553a73c))
* **superheroes:** owner-authority gate classifies gh/git commands with inherited flags ([#997](https://github.com/zwrose/superheroes/issues/997)) ([3883d35](https://github.com/zwrose/superheroes/commit/3883d35cfae3a6f2c4911beef3e872427d356dfd))
* **superheroes:** round-driver certification path — record/submit fence, manifest disclosure, durable-path docs (release re-statement of [#983](https://github.com/zwrose/superheroes/issues/983)) ([#994](https://github.com/zwrose/superheroes/issues/994)) ([404be8f](https://github.com/zwrose/superheroes/commit/404be8f139af0b7fa67f1b1220fcfa3363f0e37c))


### Chores

* **superheroes:** align agent-facing language with writing-for-agents principles ([#998](https://github.com/zwrose/superheroes/issues/998)) ([5beef05](https://github.com/zwrose/superheroes/commit/5beef050e40bb0f350c8582b8fc4f5e941d5d87a))
* **superheroes:** doctrine/consumer batch for 0.27.0 — wave_watch arm-pointer + LEDGERS row, §10.7 sentence, naming gloss, gated-strings as-data restore ([#999](https://github.com/zwrose/superheroes/issues/999)) ([012d617](https://github.com/zwrose/superheroes/commit/012d617bd6ad03aa52cc96898199d0fda076436c))
* **superheroes:** hygiene 9 — commit-graph pin split, four untested guards pinned, lock reason fidelity, de-timing ([#986](https://github.com/zwrose/superheroes/issues/986)) ([2fc0761](https://github.com/zwrose/superheroes/commit/2fc0761012d2a007111908d1f7df85c53aab9bd0))
* **superheroes:** hygiene C — doctrine/prose family ([#753](https://github.com/zwrose/superheroes/issues/753)) ([#980](https://github.com/zwrose/superheroes/issues/980)) ([5ae50ab](https://github.com/zwrose/superheroes/commit/5ae50abe3918b1786dbf89d27f426e68785c0a23))
* **superheroes:** hygiene D — guards-and-validators family, [#699](https://github.com/zwrose/superheroes/issues/699) riders 17, 19-21, 23, 29-31 ([#981](https://github.com/zwrose/superheroes/issues/981)) ([e95f662](https://github.com/zwrose/superheroes/commit/e95f662eb9033d618239fbee8cc1e02158c9cf69))
* **superheroes:** relocate the perceivability list + dispatch-preflight checks to showrunner reference ([#703](https://github.com/zwrose/superheroes/issues/703)) ([#985](https://github.com/zwrose/superheroes/issues/985)) ([985a2b7](https://github.com/zwrose/superheroes/commit/985a2b7f1caeb87730b954f1e434be69fb07901e))

## [0.26.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.25.0...superheroes-v0.26.0) (2026-08-12)


### Features

* **superheroes:** write-path skill step-bodies at pointable reference paths — orders cite, never inline ([#965](https://github.com/zwrose/superheroes/issues/965)) ([92448a1](https://github.com/zwrose/superheroes/commit/92448a1ff685afbbac1437dbffdd4dae3af08ddb))


### Bug Fixes

* **superheroes:** file_lock staleness survives hostname change + kern.boottime jitter ([#964](https://github.com/zwrose/superheroes/issues/964)) ([84e19cf](https://github.com/zwrose/superheroes/commit/84e19cf471137eff0a2d998ed8345ca868e95978))
* **superheroes:** state the write-report contract the runner grades against, and name report loss honestly ([#969](https://github.com/zwrose/superheroes/issues/969)) ([d88f910](https://github.com/zwrose/superheroes/commit/d88f910dcb1484e27bc12b435ebe843df5cd518b))

## [0.25.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.24.0...superheroes-v0.25.0) (2026-08-11)


### Features

* **superheroes:** car 4a — order emission + per-order hash binding + templates as shipped data ([#723](https://github.com/zwrose/superheroes/issues/723)) ([#942](https://github.com/zwrose/superheroes/issues/942)) ([c9bf103](https://github.com/zwrose/superheroes/commit/c9bf103f20b510590ecbeaae3caee9fa8f90a182))
* **superheroes:** car 4b — gate-policy/1 grammar, advance wiring, configure surface, caller contracts ([#723](https://github.com/zwrose/superheroes/issues/723)) ([#943](https://github.com/zwrose/superheroes/issues/943)) ([06ae7c3](https://github.com/zwrose/superheroes/commit/06ae7c3977d7f96fda59ffec0cdb683b85d1d7ad))
* **superheroes:** car 5 — per-phase contracts published, handback gate shipped dark, LEDGERS truth ([#723](https://github.com/zwrose/superheroes/issues/723)) ([#955](https://github.com/zwrose/superheroes/issues/955)) ([ea12306](https://github.com/zwrose/superheroes/commit/ea12306d67cbf57f5fec1994f46cabf8c1936536))
* **superheroes:** compaction checkpoint command + charter-scoped compaction recovery hooks ([#917](https://github.com/zwrose/superheroes/issues/917)) ([23b10f3](https://github.com/zwrose/superheroes/commit/23b10f32c31b041060dab50c802eecb1cd18f01d))
* **superheroes:** launcher batch accounting — record re-handbacks and vet outcomes the terminal counter cannot see ([#878](https://github.com/zwrose/superheroes/issues/878)) ([246be79](https://github.com/zwrose/superheroes/commit/246be79bb40d4d69fdb2edc490d918e8f3449f27))
* **superheroes:** launcher refuses an unslotted parallel launch on a slot-calibrated project ([#913](https://github.com/zwrose/superheroes/issues/913)) ([825c468](https://github.com/zwrose/superheroes/commit/825c468dead1fda52d7174bfa97ac9d25c9db724))
* **superheroes:** owner-calibrated workflow allowlist for the owner-authority gate ([#950](https://github.com/zwrose/superheroes/issues/950)) ([6e5a9fd](https://github.com/zwrose/superheroes/commit/6e5a9fdde8505a5d23fa09c9e9ad2de8ffad2834))
* **superheroes:** pilot framework A1 — contract home: schema, types, probe vocabulary, seed/mint interfaces ([#837](https://github.com/zwrose/superheroes/issues/837)) ([9af98da](https://github.com/zwrose/superheroes/commit/9af98da037169530e16d6d7945d1cc40e887b382))
* **superheroes:** pilot framework A2a — slot lifecycle: identity, generations, provisioning journal, partial-failure report ([#849](https://github.com/zwrose/superheroes/issues/849)) ([4cb84be](https://github.com/zwrose/superheroes/commit/4cb84be134d1dbebf5dd08d2e402eb2bb1165988))
* **superheroes:** pilot framework A2b — reclaim safety: quarantine, sweep, reassignment probe, deletion rules ([#858](https://github.com/zwrose/superheroes/issues/858)) ([0f1c148](https://github.com/zwrose/superheroes/commit/0f1c1480db12a01dad3c57b6441a64b19d370151))
* **superheroes:** pilot framework A3 — target boundary: per-slot binding, policy out of builder reach, observed datastore identity ([#841](https://github.com/zwrose/superheroes/issues/841)) ([c3fc350](https://github.com/zwrose/superheroes/commit/c3fc350dbcdbd9099cfb7a69f284db6f8f3e0295))
* **superheroes:** pilot framework B4 — attended seeding: per-slot owner sign-in, verify-at-seed, no stored credential ([#916](https://github.com/zwrose/superheroes/issues/916)) ([41d28f7](https://github.com/zwrose/superheroes/commit/41d28f76e8e72eec0661c668c637c6a07e268bf7))
* **superheroes:** pilot framework B5 — per-slot app lifecycle: stand-up, readiness, wave teardown, deadline runtime ([#856](https://github.com/zwrose/superheroes/issues/856)) ([65701b0](https://github.com/zwrose/superheroes/commit/65701b06bf427550b5692c17bcb8cc4f5b9ccc41))
* **superheroes:** pilot framework B6 — auth contract exercises: identity probes, margin math, mint client, lapse path ([#852](https://github.com/zwrose/superheroes/issues/852)) ([c22ee25](https://github.com/zwrose/superheroes/commit/c22ee252e54c345a5323b6550286900328ffeedb))
* **superheroes:** pilot framework C10 — per-slot artifact store + headless conformance run ([#923](https://github.com/zwrose/superheroes/issues/923)) ([82098f7](https://github.com/zwrose/superheroes/commit/82098f70458e3e127c3afba2e5ea355e096ca3c4))
* **superheroes:** pilot framework C7 — per-slot browser topology: Playwright provisioning, seed injection, per-generation teardown ([#854](https://github.com/zwrose/superheroes/issues/854)) ([b995d0c](https://github.com/zwrose/superheroes/commit/b995d0c81b02e2a0163b41449c7ad381261510e5))
* **superheroes:** pilot framework C8 — charter integration: advisor provisioning duty, workhorse verify-or-create, ledger grammar ([#906](https://github.com/zwrose/superheroes/issues/906)) ([934c11e](https://github.com/zwrose/superheroes/commit/934c11e64576049974ce7840c829ddc130fcf889))
* **superheroes:** pilot framework C9 — cleanup effect receipt + resurrection/reseed ([#857](https://github.com/zwrose/superheroes/issues/857)) ([9c3d08e](https://github.com/zwrose/superheroes/commit/9c3d08e2d480eb903c12cd49e8b44750268253fe))
* **superheroes:** pilot framework D11a — acceptance matrix + mechanical §14 tripwires ([#925](https://github.com/zwrose/superheroes/issues/925)) ([f2e0c0e](https://github.com/zwrose/superheroes/commit/f2e0c0e2cd63a0a52a0359adf6d885c963a65a1a))
* **superheroes:** review-loop durability — per-seat durable records, advance/record-result/attest ([#723](https://github.com/zwrose/superheroes/issues/723) PR-1) ([#914](https://github.com/zwrose/superheroes/issues/914)) ([c02e7af](https://github.com/zwrose/superheroes/commit/c02e7afedc0011e2cec04883c66a2cc00333e304))
* **superheroes:** round-driver commit protocol — durable intent/parts/completion + replay for multi-artifact writes ([#918](https://github.com/zwrose/superheroes/issues/918)) ([#921](https://github.com/zwrose/superheroes/issues/921)) ([027e33a](https://github.com/zwrose/superheroes/commit/027e33ac75f1e9b6eaabc8ecef2294cf4f4e4fb6))


### Bug Fixes

* **superheroes:** assert_results_only key collision — account names no longer collide with plan-step keys ([#870](https://github.com/zwrose/superheroes/issues/870)) ([1ae4207](https://github.com/zwrose/superheroes/commit/1ae4207bac3c8dc550c76f0ff193693416f9699c))
* **superheroes:** audit target ids are per-location and unique — same-titled findings no longer collapse ([#915](https://github.com/zwrose/superheroes/issues/915)) ([#924](https://github.com/zwrose/superheroes/issues/924)) ([e840479](https://github.com/zwrose/superheroes/commit/e8404798f6104e0da0b1009e111bae58bbf43200))
* **superheroes:** builder-tier config hardening — resolver display form, self-maintaining round-trip guard, engine-pin writer ([#840](https://github.com/zwrose/superheroes/issues/840)) ([544b31c](https://github.com/zwrose/superheroes/commit/544b31cfbccf793ff59f3058e5fba9c4bc1b586b))
* **superheroes:** calibration_resolve refuses an unresolvable --root loudly instead of reporting a confident "none" ([#880](https://github.com/zwrose/superheroes/issues/880)) ([d61dbfd](https://github.com/zwrose/superheroes/commit/d61dbfd8cf7e906596d7da33683ba458c3c22743))
* **superheroes:** cleanup source binding refuses a receipt when any argv-tail path cannot be content-digested ([#868](https://github.com/zwrose/superheroes/issues/868)) ([900fbda](https://github.com/zwrose/superheroes/commit/900fbda38423c49c34e357efcab1eda766db6420))
* **superheroes:** cursor write-dispatch — diagnose the dead report channel and add declared-item delivery verification ([#951](https://github.com/zwrose/superheroes/issues/951)) ([77558ed](https://github.com/zwrose/superheroes/commit/77558edb2b303d0eeac05c654da7848585fe19c4))
* **superheroes:** end_effect verifies the effect's origin — close the silent wrong-kind/same-slot journal hole ([#892](https://github.com/zwrose/superheroes/issues/892)) ([abca0b5](https://github.com/zwrose/superheroes/commit/abca0b51dc41581acb2204b35b881a5cb0c4cdc4))
* **superheroes:** FR-8 document-review confirmation rule fires in production ([#890](https://github.com/zwrose/superheroes/issues/890)) ([2af20a5](https://github.com/zwrose/superheroes/commit/2af20a56619caae6106449caed3b95f265476a95))
* **superheroes:** independent dispatches batch — concurrent shape on three surfaces, invariant pinned ([#956](https://github.com/zwrose/superheroes/issues/956)) ([a736714](https://github.com/zwrose/superheroes/commit/a736714f14129b5360ada7b07f1da6e7d5f7ab2c))
* **superheroes:** pilot_appctl.stop() reaps before its kill loops — no more 20s burned per stop ([#876](https://github.com/zwrose/superheroes/issues/876)) ([5825467](https://github.com/zwrose/superheroes/commit/582546700d0964ea18418dde02603c30206dd007))
* **superheroes:** PR-body skeleton emits the advisor-vet slot marker + charter specifies the owner-half register ([#900](https://github.com/zwrose/superheroes/issues/900)) ([8093041](https://github.com/zwrose/superheroes/commit/8093041b1f23a128a075d2aa47b5c4e5629c427c))
* **superheroes:** refuse out-of-range engine_dispatch --max-wait; reclaim run.lock from a confirmed-dead holder ([#869](https://github.com/zwrose/superheroes/issues/869)) ([8cff857](https://github.com/zwrose/superheroes/commit/8cff857ff9b9f30811925e37ea8f67517a7c3a2a))
* **superheroes:** round_driver panel submit refuses a mis-keyed seats artifact ([#877](https://github.com/zwrose/superheroes/issues/877)) ([30cfd50](https://github.com/zwrose/superheroes/commit/30cfd50d6ff8f11973fdc91d51138aa869cbecab))
* **superheroes:** round_driver refuses malformed verify/audit submit artifacts instead of halting the loop ([#899](https://github.com/zwrose/superheroes/issues/899)) ([1f50c2a](https://github.com/zwrose/superheroes/commit/1f50c2a5a2eab7ca1f3736651b45756a633f6210))
* **superheroes:** SAFETY_MACHINERY covers the owner-named-risk guards and their hook wrappers ([#851](https://github.com/zwrose/superheroes/issues/851)) ([63398aa](https://github.com/zwrose/superheroes/commit/63398aacbde9a15a05c38c32a900cf4aea7553e8))
* **superheroes:** stable parametrize IDs in test_pilot_malformed_input — repr(object()) embedded a per-process address ([#898](https://github.com/zwrose/superheroes/issues/898)) ([266ebce](https://github.com/zwrose/superheroes/commit/266ebce4f418f772651a2ebf94ff177158bf4ed5))
* **superheroes:** worktree-guard refusal message hints at the prose-mention case ([#875](https://github.com/zwrose/superheroes/issues/875)) ([ae99a18](https://github.com/zwrose/superheroes/commit/ae99a181d425a86d801ec963d5fca32375b6cd86))
* **superheroes:** write-dispatch report salvage — recover the implementer's report from the raw stream ([#839](https://github.com/zwrose/superheroes/issues/839)) ([0a5fe48](https://github.com/zwrose/superheroes/commit/0a5fe48dd40913785d7103616230b3a92e6bdfe4))


### Chores

* **superheroes:** audit cleanup — dead modules, stale refs, vestigial tail ([#838](https://github.com/zwrose/superheroes/issues/838)) ([04c9375](https://github.com/zwrose/superheroes/commit/04c937526ac6472726309542b74189128650b46c))
* **superheroes:** config-knobs sweep — retire five dead knobs, document the guardian-config fence ([#881](https://github.com/zwrose/superheroes/issues/881)) ([1e90dc7](https://github.com/zwrose/superheroes/commit/1e90dc79b144bfd6fdac59573e7f4660b1e8c088))
* **superheroes:** pilot hygiene batch — conftest env pinning, bounded-runner extraction, vocabulary single-homing, contract ToC + LEDGERS row repairs ([#879](https://github.com/zwrose/superheroes/issues/879)) ([16d39ad](https://github.com/zwrose/superheroes/commit/16d39ad2a6e001bf26fb067a454baf6c51ec60e3))
* **superheroes:** remove provision_server's legacy non-pre-spawn path — zero live callers ([#874](https://github.com/zwrose/superheroes/issues/874)) ([b441fef](https://github.com/zwrose/superheroes/commit/b441fef5c92a8147d2c930a11909f4d58da594ef))

## [0.24.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.23.0...superheroes-v0.24.0) (2026-08-02)


### Features

* **superheroes:** builder-dispatch model tier — opus default in loaded surfaces, owner knob, launcher pin ([#755](https://github.com/zwrose/superheroes/issues/755)) ([#805](https://github.com/zwrose/superheroes/issues/805)) ([b503c9c](https://github.com/zwrose/superheroes/commit/b503c9cbe1c4cef518d625b0a5bd675fc9240c83))
* **superheroes:** forfeit observability — per-attempt telemetry, attribution ledger, forfeit-with-engaged-artifact + verified salvage valve ([#804](https://github.com/zwrose/superheroes/issues/804)) ([87ebf63](https://github.com/zwrose/superheroes/commit/87ebf63a73c454fdbc859a900f7ef00988f5fbd1))
* **superheroes:** launch-shape mechanization — the ledger's grammar has one authority ([#656](https://github.com/zwrose/superheroes/issues/656)) ([#758](https://github.com/zwrose/superheroes/issues/758)) ([e4ea239](https://github.com/zwrose/superheroes/commit/e4ea239d7cd1473dfcfd12a5a0879c09481c4cd6))
* **superheroes:** recovery doctrine into plugin surfaces — adopt-never-resume, unpushed-work sweep, transcript pinning ([#775](https://github.com/zwrose/superheroes/issues/775)) ([#788](https://github.com/zwrose/superheroes/issues/788)) ([ca4fbfc](https://github.com/zwrose/superheroes/commit/ca4fbfcf067149546f92304c3e73a601e9010987))
* **superheroes:** semantic liveness signal for headless builds (advisor-consumed heartbeat) ([#657](https://github.com/zwrose/superheroes/issues/657)) ([#791](https://github.com/zwrose/superheroes/issues/791)) ([16f2931](https://github.com/zwrose/superheroes/commit/16f293179bfcebf1f3f0e3024f2cfe72fa4e8501))


### Bug Fixes

* **superheroes:** close the file_lock crash window — one guarded reclaimer, no unreclaimable locks ([#733](https://github.com/zwrose/superheroes/issues/733)) ([#759](https://github.com/zwrose/superheroes/issues/759)) ([c27e642](https://github.com/zwrose/superheroes/commit/c27e6427754401b515d782eb1b3ea05fd7b83e0b))
* **superheroes:** findings delivery contract is channel-keyed at its source — review-base.md ordered a write the review sandbox forbids ([#776](https://github.com/zwrose/superheroes/issues/776)) ([#783](https://github.com/zwrose/superheroes/issues/783)) ([8db94c2](https://github.com/zwrose/superheroes/commit/8db94c230d16332aaf3ab22bccbcb2bdccebcd12))
* **superheroes:** hygiene B — config-surface family, riders 7/18/25-27 ([#752](https://github.com/zwrose/superheroes/issues/752)) ([#778](https://github.com/zwrose/superheroes/issues/778)) ([3d85c74](https://github.com/zwrose/superheroes/commit/3d85c7408fa407e3b89d82bf21693e592757647f))
* **superheroes:** lean the workhorse/showrunner charters — conflict-pass + relocation, no rule loss ([#801](https://github.com/zwrose/superheroes/issues/801)) ([9d7f001](https://github.com/zwrose/superheroes/commit/9d7f00129406c44fa6f5861f5d4c50fe91aac8c0))
* **superheroes:** liveness probe dispatches through the hardened path — no inherited stdin, no positional prompt ([#745](https://github.com/zwrose/superheroes/issues/745)) ([aa3a5ae](https://github.com/zwrose/superheroes/commit/aa3a5ae1eba5db1a38f64689a6961300fed54f5d))
* **superheroes:** pin the codex dispatch fast-exit trigger — transport diagnosis, real telemetry, pre-spawn schema refusal ([#746](https://github.com/zwrose/superheroes/issues/746)) ([625c898](https://github.com/zwrose/superheroes/commit/625c8980a97e30a9ae90bf3b049004eac48f87bf))
* **superheroes:** resolve the review-diff merge-base outside the repository's git directory ([#748](https://github.com/zwrose/superheroes/issues/748)) ([#761](https://github.com/zwrose/superheroes/issues/761)) ([93ac9c5](https://github.com/zwrose/superheroes/commit/93ac9c55f45e70a9686f1701c3ed2e634c62233d))
* **superheroes:** review-code auto-fix branch guard accepts adopted builds ([#769](https://github.com/zwrose/superheroes/issues/769)) ([#780](https://github.com/zwrose/superheroes/issues/780)) ([4a78de1](https://github.com/zwrose/superheroes/commit/4a78de116e46dc1d2566b4ec848a88e03707114a))
* **superheroes:** six sibling _repo_root copies + get_gitdir fall open on a broken repo — one fail-closed chokepoint ([#742](https://github.com/zwrose/superheroes/issues/742)) ([#760](https://github.com/zwrose/superheroes/issues/760)) ([e5932e1](https://github.com/zwrose/superheroes/commit/e5932e165759c0f3850d39e7d0e589c1845fb1ae))
* **superheroes:** workhorse preserves advisor-authored PR-body content verbatim; retire the LEDGERS residual ([#734](https://github.com/zwrose/superheroes/issues/734)) ([#779](https://github.com/zwrose/superheroes/issues/779)) ([07d05c8](https://github.com/zwrose/superheroes/commit/07d05c8857294088f72d28a62c53737fbf400919))
* **superheroes:** worktree guard — refuse destructive git discards on dirty trees ([#682](https://github.com/zwrose/superheroes/issues/682)) ([#756](https://github.com/zwrose/superheroes/issues/756)) ([f8faa45](https://github.com/zwrose/superheroes/commit/f8faa452f787d9788fe44684b92bd24024c3d09e))


### Chores

* **superheroes:** cursor implementer order template — targeted verify, short structured returns, forfeit recovery ([#713](https://github.com/zwrose/superheroes/issues/713)) ([#743](https://github.com/zwrose/superheroes/issues/743)) ([62833de](https://github.com/zwrose/superheroes/commit/62833de464e1683a36cdb3a7268418289febbf9b))
* **superheroes:** every new detector ships a recorded bite-proof ([#765](https://github.com/zwrose/superheroes/issues/765)) ([#799](https://github.com/zwrose/superheroes/issues/799)) ([4c3cf49](https://github.com/zwrose/superheroes/commit/4c3cf4972792f3200cf08db972e516a5ed1bd879))
* **superheroes:** implementer contract — one open reporting obligation + a total precedence ladder ([#750](https://github.com/zwrose/superheroes/issues/750)) ([#757](https://github.com/zwrose/superheroes/issues/757)) ([ab45ce8](https://github.com/zwrose/superheroes/commit/ab45ce88f295b595026f3b93c3f194cddb21e7d8))
* **superheroes:** review-code body diet — 508 → 363 lines, ceiling 515 → 400 ([#646](https://github.com/zwrose/superheroes/issues/646)) ([#802](https://github.com/zwrose/superheroes/issues/802)) ([6bab310](https://github.com/zwrose/superheroes/commit/6bab31099d13c056b7f9b630c2f0ff42fea2737d))

## [0.23.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.22.0...superheroes-v0.23.0) (2026-07-31)


### ⚠ BREAKING CHANGES

* **superheroes:** remove migrate_on_read — the legacy-profile migration path is deleted, replaced by a named refusal ([#724](https://github.com/zwrose/superheroes/issues/724)) (#730)

### Features

* **superheroes:** orchestration doctrine — LEDGERS §4 + covenant merge-line repair + R1–R5 charter text ([#697](https://github.com/zwrose/superheroes/issues/697)) ([4f1b962](https://github.com/zwrose/superheroes/commit/4f1b96284dacce4945376938b5f4df59e484f107))
* **superheroes:** PR-body doctrine — owner half + build record, show-it wayfinding, omission floor ([#661](https://github.com/zwrose/superheroes/issues/661) ratified) ([#715](https://github.com/zwrose/superheroes/issues/715)) ([1925eb5](https://github.com/zwrose/superheroes/commit/1925eb5f811025c2c20ae4ad93926a5bdcbaf9bd))
* **superheroes:** remove migrate_on_read — the legacy-profile migration path is deleted, replaced by a named refusal ([#724](https://github.com/zwrose/superheroes/issues/724)) ([#730](https://github.com/zwrose/superheroes/issues/730)) ([c115e8a](https://github.com/zwrose/superheroes/commit/c115e8a3d04fe0bb1de14c84a28ae16b3e05c94d))
* **superheroes:** supervised dispatch — write verb, durable journaling, reviewer retrofit (release re-statement of [#726](https://github.com/zwrose/superheroes/issues/726)) ([#740](https://github.com/zwrose/superheroes/issues/740)) ([4fe4d89](https://github.com/zwrose/superheroes/commit/4fe4d89ffb12323d09062c8d98d3ce36d3166ec6))
* **superheroes:** the check-runner seat + "a review seat never changes the repository, and never claims a run it did not make" ([#719](https://github.com/zwrose/superheroes/issues/719)) ([#731](https://github.com/zwrose/superheroes/issues/731)) ([da90558](https://github.com/zwrose/superheroes/commit/da90558ea778b0ebb41f0c701863130f67f59614))
* **superheroes:** three-lane build doctrine (full/light/micro) — review-discipline + charters, micro hard-line named ([#709](https://github.com/zwrose/superheroes/issues/709)) ([4e1f0bf](https://github.com/zwrose/superheroes/commit/4e1f0bf20e0f14f31de58626ec0d58ca03d9f6da))
* **superheroes:** vet-receipt doctrine — spine + triggered fields, owner-half verdict write, collector reconciliation ([#672](https://github.com/zwrose/superheroes/issues/672) ratified) ([#729](https://github.com/zwrose/superheroes/issues/729)) ([ed29199](https://github.com/zwrose/superheroes/commit/ed29199ffdeaee00796d540b82ae6bf1b8a74ba7))


### Bug Fixes

* **superheroes:** charter hygiene 8 part B — config-surface fall-opens become named refusals ([#699](https://github.com/zwrose/superheroes/issues/699) riders 7-12) [PARKED — rework tripwire fired] ([#732](https://github.com/zwrose/superheroes/issues/732)) ([2d197b7](https://github.com/zwrose/superheroes/commit/2d197b785e73397dbb305d80954d1c9450591a08))
* **superheroes:** config gates fail closed on an unreadable core.md — one (prefs, status) accessor ([#701](https://github.com/zwrose/superheroes/issues/701)) ([6249bbf](https://github.com/zwrose/superheroes/commit/6249bbf01eefc1341848ceef05ac67f4f5854b02))
* **superheroes:** seat_map verify() violations drive the certification shape — per-seat excusal evidence ([#680](https://github.com/zwrose/superheroes/issues/680)) ([#700](https://github.com/zwrose/superheroes/issues/700)) ([e7006ec](https://github.com/zwrose/superheroes/commit/e7006ecbc34cc73b243ad3b8285f50c117d918a7))
* **superheroes:** test-pilot execution calibration teeth — accessible-name selection, pointer events, aria-disabled, N/N procedure-suspicion ([#728](https://github.com/zwrose/superheroes/issues/728)) ([c48b5f6](https://github.com/zwrose/superheroes/commit/c48b5f6c6806ea72f8c18bd702d322a84079130f))


### Chores

* release re-statement of [#726](https://github.com/zwrose/superheroes/issues/726) and [#716](https://github.com/zwrose/superheroes/issues/716) — two commits the release-please parser silently dropped from 0.23.0 ([#739](https://github.com/zwrose/superheroes/issues/739)) ([868dce5](https://github.com/zwrose/superheroes/commit/868dce5b978a729348f7c72b4f506f6128213d71))
* **superheroes:** charter hygiene 7 — four riders ([#685](https://github.com/zwrose/superheroes/issues/685)) ([#698](https://github.com/zwrose/superheroes/issues/698)) ([e2419ec](https://github.com/zwrose/superheroes/commit/e2419ec142c1183f5dde441f53339cb5cce0e652))
* **superheroes:** charter hygiene 8 — part A of [#699](https://github.com/zwrose/superheroes/issues/699), riders 1-6 and 13-15 (release re-statement of [#716](https://github.com/zwrose/superheroes/issues/716)) ([#741](https://github.com/zwrose/superheroes/issues/741)) ([6743317](https://github.com/zwrose/superheroes/commit/67433175164f49ffbdc5b3ce89dab752a61fd9e5))
* **superheroes:** extend the boundary sync guard to the named cross-lane invariants ([#721](https://github.com/zwrose/superheroes/issues/721)) ([#727](https://github.com/zwrose/superheroes/issues/727)) ([62f8855](https://github.com/zwrose/superheroes/commit/62f88552fff5fd82976a0f2f754aaafcb7707660))
* **superheroes:** PHILOSOPHY amendment — approval/execution distinction (owner-ratified) + covenant note removal + LEDGERS R3 resolution ([#708](https://github.com/zwrose/superheroes/issues/708)) ([0d918cf](https://github.com/zwrose/superheroes/commit/0d918cfca0f43ec0ee2955ff1922936ac7402338))
* **superheroes:** retire the orphaned pr-body model tier role ([#692](https://github.com/zwrose/superheroes/issues/692)) ([#696](https://github.com/zwrose/superheroes/issues/696)) ([721ca00](https://github.com/zwrose/superheroes/commit/721ca00a8a206e0ceb008c0f2405c894d85d0617))

## [0.22.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.21.2...superheroes-v0.22.0) (2026-07-27)


### ⚠ BREAKING CHANGES

* **superheroes:** Claude 5 model refresh + cursor first-party family merge (release re-statement of #653) ([#673](https://github.com/zwrose/superheroes/issues/673))

### Features

* **superheroes:** Claude 5 model refresh + cursor first-party family merge (release re-statement of [#653](https://github.com/zwrose/superheroes/issues/653)) ([#673](https://github.com/zwrose/superheroes/issues/673)) ([9f73450](https://github.com/zwrose/superheroes/commit/9f7345072a357cccfca71ad8ef1e744963ca9fe5))
* **superheroes:** cursor CLI is first-party-only; sunset the fable-on-external fall-open ([#650](https://github.com/zwrose/superheroes/issues/650)) ([#675](https://github.com/zwrose/superheroes/issues/675)) ([00f730f](https://github.com/zwrose/superheroes/commit/00f730f76194bc880af6b8bef99a62b91d4fab0b))
* **superheroes:** maker family barred from every panel seat — disclosed same-family degradation only when no alternative family is live ([#670](https://github.com/zwrose/superheroes/issues/670)) ([#679](https://github.com/zwrose/superheroes/issues/679)) ([9b26f25](https://github.com/zwrose/superheroes/commit/9b26f250121d01a329d7fa4defb7aac70af56a7e))
* **superheroes:** review base guard as machinery — round_driver enforces resolve-to-commit + non-empty diff; fork mismatch fails loud ([#648](https://github.com/zwrose/superheroes/issues/648)) ([#667](https://github.com/zwrose/superheroes/issues/667)) ([ae6ebbe](https://github.com/zwrose/superheroes/commit/ae6ebbe4cb4dbc2e5b1f2d00ae14879e8b6788c4))
* **superheroes:** review-trust cluster — pinned read seats, an investigation floor, and a standing control probe ([#665](https://github.com/zwrose/superheroes/issues/665), [#666](https://github.com/zwrose/superheroes/issues/666), [#668](https://github.com/zwrose/superheroes/issues/668)) ([#683](https://github.com/zwrose/superheroes/issues/683)) ([abcbcf0](https://github.com/zwrose/superheroes/commit/abcbcf032ed2dd74d9c17e24a7000440640e16f2))
* **superheroes:** sanitized view for external review seats — the reviewed repo can neither steer nor hide from its own reviewer ([#684](https://github.com/zwrose/superheroes/issues/684)) ([#688](https://github.com/zwrose/superheroes/issues/688)) ([e2bc300](https://github.com/zwrose/superheroes/commit/e2bc300451bc613d3d7a2790db3653b48d30dcc2))


### Chores

* **superheroes:** charter hygiene 5 — eight mechanical riders ([#638](https://github.com/zwrose/superheroes/issues/638)) ([#663](https://github.com/zwrose/superheroes/issues/663)) ([a0b32e9](https://github.com/zwrose/superheroes/commit/a0b32e96cfede2f91eb626affdf16a53b9a37c09))
* **superheroes:** charter hygiene 6 — eight riders ([#652](https://github.com/zwrose/superheroes/issues/652)) ([#686](https://github.com/zwrose/superheroes/issues/686)) ([9d4f107](https://github.com/zwrose/superheroes/commit/9d4f107b9b7c1cbe2550534f7208eeb276c964ab))

## [0.21.2](https://github.com/zwrose/superheroes/compare/superheroes-v0.21.1...superheroes-v0.21.2) (2026-07-26)


### Bug Fixes

* **superheroes:** guardian duplication lens — jscpd input via config file, replacing the 100KB argv ceiling ([#644](https://github.com/zwrose/superheroes/issues/644)) ([b0290fd](https://github.com/zwrose/superheroes/commit/b0290fd7b396e4dbb406ea78e0547d1d03effb10))
* **superheroes:** pin review-code's diff base to a fetched remote commit ([#637](https://github.com/zwrose/superheroes/issues/637)) ([#641](https://github.com/zwrose/superheroes/issues/641)) ([5faab2f](https://github.com/zwrose/superheroes/commit/5faab2f71c137c3371b189b88cddf7d328093573))
* **superheroes:** source dispatch-calibration model columns from the registry ([#642](https://github.com/zwrose/superheroes/issues/642)) ([0dccb4f](https://github.com/zwrose/superheroes/commit/0dccb4f464c169d7efd52d0745ffaa0d0a5590bd))
* **superheroes:** unify the dispatch model vocabulary — round-tripping tokens, honored pins, named refusals ([#636](https://github.com/zwrose/superheroes/issues/636)) ([#643](https://github.com/zwrose/superheroes/issues/643)) ([bf8c194](https://github.com/zwrose/superheroes/commit/bf8c194581ca795d5cd923178a178667abd4c9bf))

## [0.21.1](https://github.com/zwrose/superheroes/compare/superheroes-v0.21.0...superheroes-v0.21.1) (2026-07-25)


### Bug Fixes

* **superheroes:** slim the SessionStart bootstrap to its unique payload + harness-dependency tripwire ([#631](https://github.com/zwrose/superheroes/issues/631)) ([c9c5f97](https://github.com/zwrose/superheroes/commit/c9c5f974488402b24bb2a9858b49c5bb8d516b4f))


### Chores

* **superheroes:** charter context-fit pass ([#630](https://github.com/zwrose/superheroes/issues/630)) — prune, mechanics relocation, await-widening, host-precedence note, LEDGERS records ([#633](https://github.com/zwrose/superheroes/issues/633)) ([47becd3](https://github.com/zwrose/superheroes/commit/47becd3c946be22a707035e8a29eaa03d6a0e538))
* **superheroes:** charter hygiene 4 — riders 1,3,4,5,6 ([#620](https://github.com/zwrose/superheroes/issues/620)) ([#634](https://github.com/zwrose/superheroes/issues/634)) ([3958c7f](https://github.com/zwrose/superheroes/commit/3958c7f201fd435ce638432cb26bc41737e4d6c5))

## [0.21.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.20.0...superheroes-v0.21.0) (2026-07-24)


### Features

* **superheroes:** coarsen transient identity markers out of the deps drift key ([#613](https://github.com/zwrose/superheroes/issues/613)) ([#619](https://github.com/zwrose/superheroes/issues/619)) ([d208240](https://github.com/zwrose/superheroes/commit/d2082401bdb8d5f62f86601e740e54593e812844))
* **superheroes:** loud fall-open by machinery — fell-open dispatch provenance ([#563](https://github.com/zwrose/superheroes/issues/563) PR C) ([#612](https://github.com/zwrose/superheroes/issues/612)) ([78aea6a](https://github.com/zwrose/superheroes/commit/78aea6af5cb2022961e737b0403e29e8f4746b79))
* **superheroes:** owner per-seat pin config surface — enginePreferences.seatPins feeds seat_map --pins ([#607](https://github.com/zwrose/superheroes/issues/607)) ([#617](https://github.com/zwrose/superheroes/issues/617)) ([17ae7b6](https://github.com/zwrose/superheroes/commit/17ae7b6e40b6f8bf0c623dcf29d999e8976a7e99))
* **superheroes:** panel composition v2 — per-seat engines, seat map, vendor preflight, loud pins ([#510](https://github.com/zwrose/superheroes/issues/510)) ([#603](https://github.com/zwrose/superheroes/issues/603)) ([ed20551](https://github.com/zwrose/superheroes/commit/ed205514d04919b6fb69051c96fff4643991f5bb))
* **superheroes:** reviewer-scoped engine dispatch runner — auto-retry + liveness ([#563](https://github.com/zwrose/superheroes/issues/563) PR B) ([#606](https://github.com/zwrose/superheroes/issues/606)) ([6b2bd5b](https://github.com/zwrose/superheroes/commit/6b2bd5b27adcf097817bbeb7bf0c90598f1b5d4a))
* **superheroes:** seat-map preflight economics — gate to panel paths, TTL liveness cache, pin-reachable probes ([#610](https://github.com/zwrose/superheroes/issues/610)) ([#622](https://github.com/zwrose/superheroes/issues/622)) ([3d8d0a3](https://github.com/zwrose/superheroes/commit/3d8d0a344869c20582228bb40edc27e0ffedde62))
* **superheroes:** workhorse dispatch-path model validation — consume the [#510](https://github.com/zwrose/superheroes/issues/510) registry allowlists ([#600](https://github.com/zwrose/superheroes/issues/600)) ([#611](https://github.com/zwrose/superheroes/issues/611)) ([02a0fcc](https://github.com/zwrose/superheroes/commit/02a0fcc8840e170bc079b04bb2923936b936f4d7))


### Bug Fixes

* **superheroes:** codex reviewer-seat reliability PR A — parse-result bounds, empty-prompt guard, dispatch docs ([#563](https://github.com/zwrose/superheroes/issues/563)) ([#602](https://github.com/zwrose/superheroes/issues/602)) ([c859d82](https://github.com/zwrose/superheroes/commit/c859d826a569555a55c1c1694fd9e191d6d2de13))
* **superheroes:** round_driver --fixer-vendor degrade on unknown fixer + pin engine_dispatch.py ([#608](https://github.com/zwrose/superheroes/issues/608)) ([#621](https://github.com/zwrose/superheroes/issues/621)) ([163b677](https://github.com/zwrose/superheroes/commit/163b6778a6ddc9e2de334e6925d451703ac9b92e))


### Chores

* **superheroes:** guardian collect/classify status-seam cleanup ([#567](https://github.com/zwrose/superheroes/issues/567) items 4, 10) ([#605](https://github.com/zwrose/superheroes/issues/605)) ([c734fbc](https://github.com/zwrose/superheroes/commit/c734fbcc8d89c6afb42237d60b8f95fd3e713514))

## [0.20.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.19.0...superheroes-v0.20.0) (2026-07-23)


### Features

* **superheroes:** guardian inaugural-baseline validation — validate the quiet before it fossilizes ([#574](https://github.com/zwrose/superheroes/issues/574)) ([#593](https://github.com/zwrose/superheroes/issues/593)) ([c1ceb49](https://github.com/zwrose/superheroes/commit/c1ceb49ce4f6c303c3ffc5eb31e9ef51967283d3))
* **superheroes:** rated Python audit — lockfile + transitive coverage (poetry/uv/Pipfile) ([#582](https://github.com/zwrose/superheroes/issues/582)) ([#596](https://github.com/zwrose/superheroes/issues/596)) ([3c8595e](https://github.com/zwrose/superheroes/commit/3c8595eeb5ed7e18f917b2a8c14b020b781129a8))
* **superheroes:** vitals gap identity — key comparability on ecosystem+part+cause code ([#585](https://github.com/zwrose/superheroes/issues/585)) ([#590](https://github.com/zwrose/superheroes/issues/590)) ([01d71e3](https://github.com/zwrose/superheroes/commit/01d71e32e434c9ffceeb3076ec127668cd36a26a))


### Bug Fixes

* **superheroes:** coupling lens — plugin-pinned TypeScript for dependency-cruiser + real-module path normalization ([#575](https://github.com/zwrose/superheroes/issues/575)) ([#595](https://github.com/zwrose/superheroes/issues/595)) ([e4a76ab](https://github.com/zwrose/superheroes/commit/e4a76ab4758d042e3208a3e80aef662cc9dbb289))
* **superheroes:** guardian stack-tags — unknown vocabulary is unverifiable, never mismatched; learn framework tags ([#588](https://github.com/zwrose/superheroes/issues/588)) ([dd0b2aa](https://github.com/zwrose/superheroes/commit/dd0b2aac5087ce62973faab5252df9e8fb5531b1))


### Chores

* **superheroes:** charter hygiene 2 — advisor follow-up-disposition duty; terminal-forfeit-only reviewer fallback; headless-dispatch discipline; [#591](https://github.com/zwrose/superheroes/issues/591) hygiene bundle ([#594](https://github.com/zwrose/superheroes/issues/594)) ([9bd89a5](https://github.com/zwrose/superheroes/commit/9bd89a5c177497edb11847535820d8859218c3c4))
* **superheroes:** workhorse field hardening — preflight write probe, work-order authoring rules, receipt-integrity contract lines ([#591](https://github.com/zwrose/superheroes/issues/591)) ([c4a2054](https://github.com/zwrose/superheroes/commit/c4a2054fb7b23c283c689845e3194d1a5852c3d1))

## [0.19.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.18.0...superheroes-v0.19.0) (2026-07-23)


### Features

* **superheroes:** rated Python advisory source (OSV) — critical-vuln red line fires for Python ([#581](https://github.com/zwrose/superheroes/issues/581)) ([7dd0ef0](https://github.com/zwrose/superheroes/commit/7dd0ef0d7248d950393836937e60f9f1b8c9d83f))


### Bug Fixes

* **superheroes:** canonical string dimension — list-valued dimension crashed _settle_delta ([#583](https://github.com/zwrose/superheroes/issues/583)) ([#586](https://github.com/zwrose/superheroes/issues/586)) ([702d9a1](https://github.com/zwrose/superheroes/commit/702d9a1a0229518b48eb8fa25c82f02dbffbc997))


### Chores

* **superheroes:** charter hygiene bundle — eight ratified conventions into workhorse + showrunner ([#573](https://github.com/zwrose/superheroes/issues/573)) ([8b2078b](https://github.com/zwrose/superheroes/commit/8b2078bd26c4ae10bda3baf32ec3a788f6f8e39e))

## [0.18.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.17.0...superheroes-v0.18.0) (2026-07-22)


### Features

* **superheroes:** delta rounds, one-entrypoint round driver, audit-keyed breaker, stall menu ([#507](https://github.com/zwrose/superheroes/issues/507)) ([#555](https://github.com/zwrose/superheroes/issues/555)) ([d679db5](https://github.com/zwrose/superheroes/commit/d679db58262b47856addc593d4eac21aa333baca))
* **superheroes:** guardian collection-honesty seam — one collect-status design, degradation hardening, per-collector conformance harness ([#558](https://github.com/zwrose/superheroes/issues/558)) ([#560](https://github.com/zwrose/superheroes/issues/560)) ([9bf1042](https://github.com/zwrose/superheroes/commit/9bf1042c58c67a1e5b61432b196d71255a98b1c8))
* **superheroes:** guardian core — sweep shell, lens contract, drift-over-baseline, report writer ([#535](https://github.com/zwrose/superheroes/issues/535)) ([#545](https://github.com/zwrose/superheroes/issues/545)) ([e83618f](https://github.com/zwrose/superheroes/commit/e83618f693bd7989293579d72708405cc74daeed))
* **superheroes:** guardian coupling lens — dependency-cruiser/import-linter data-gatherer, high findings bar ([#538](https://github.com/zwrose/superheroes/issues/538)) ([#548](https://github.com/zwrose/superheroes/issues/548)) ([5ebe07a](https://github.com/zwrose/superheroes/commit/5ebe07a14d5bf19c0b3ddc25bc4f054476564860))
* **superheroes:** guardian invocation-safety seam — shared collector-invocation guard ([#557](https://github.com/zwrose/superheroes/issues/557)) ([#559](https://github.com/zwrose/superheroes/issues/559)) ([cd65fe4](https://github.com/zwrose/superheroes/commit/cd65fe485af7aa7dd87c52b3d20f5d444d8d6b73))
* **superheroes:** guardian lenses A — duplication drift (jscpd) + complexity×churn hotspots (size-normalized) ([#536](https://github.com/zwrose/superheroes/issues/536)) ([#553](https://github.com/zwrose/superheroes/issues/553)) ([6f5f1b2](https://github.com/zwrose/superheroes/commit/6f5f1b2c9a4fe3ea6512c8bbc2ce9fb1a3c14c03))
* **superheroes:** guardian lenses B — dependency freshness, doc freshness, dead code ([#537](https://github.com/zwrose/superheroes/issues/537)) ([#552](https://github.com/zwrose/superheroes/issues/552)) ([f23800b](https://github.com/zwrose/superheroes/commit/f23800b1538b0b581435fdead416ae153b7cd717))
* **superheroes:** guardian memory — dispositions ledger, report card, storage, vitals ([#539](https://github.com/zwrose/superheroes/issues/539)) ([#556](https://github.com/zwrose/superheroes/issues/556)) ([f30b801](https://github.com/zwrose/superheroes/commit/f30b80147085a97edf3558bbc5dc9ddef28173b3))
* **superheroes:** high-noise review-eval fixture — near-miss traps, FP-rate instrument ([#546](https://github.com/zwrose/superheroes/issues/546)) ([#554](https://github.com/zwrose/superheroes/issues/554)) ([c896f6a](https://github.com/zwrose/superheroes/commit/c896f6a5e7f3a9c0ccfba143f937ee0af0645f8f))
* **superheroes:** implementer-escalation policy — demonstrated-fragility, ladder-first, per-order maker-family accounting ([#547](https://github.com/zwrose/superheroes/issues/547)) ([#550](https://github.com/zwrose/superheroes/issues/550)) ([a975f3e](https://github.com/zwrose/superheroes/commit/a975f3e51b6da2a29586c8aec6edf9e13b27ebbd))
* **superheroes:** per-finding verification — 3-state verdicts, location-grouped, repo-grounded ([#506](https://github.com/zwrose/superheroes/issues/506)) ([#543](https://github.com/zwrose/superheroes/issues/543)) ([75a0c46](https://github.com/zwrose/superheroes/commit/75a0c46022269505a1a3d45bd1a5d4a21b93317c))


### Bug Fixes

* **superheroes:** confine guardian duplication census to git-tracked files ([#564](https://github.com/zwrose/superheroes/issues/564)) ([#565](https://github.com/zwrose/superheroes/issues/565)) ([75bb9bf](https://github.com/zwrose/superheroes/commit/75bb9bfd5fcf64295883a1a6e5ceec1e94a0f5d7))
* **superheroes:** guardian seam composition — run_tool production path routes through invoke hardening ([#561](https://github.com/zwrose/superheroes/issues/561)) ([#562](https://github.com/zwrose/superheroes/issues/562)) ([534da5d](https://github.com/zwrose/superheroes/commit/534da5d24a2e8560f6c8b39a05bed4f145c8a127))
* **superheroes:** reconcile JS/Python reviewer-retry-count asymmetry in the parity twins ([#542](https://github.com/zwrose/superheroes/issues/542)) ([cd7833d](https://github.com/zwrose/superheroes/commit/cd7833dbd5ffe2be6de66716a2187906b6ef33a9))

## [0.17.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.16.0...superheroes-v0.17.0) (2026-07-21)


### Features

* **superheroes:** doc lens recast — six doc-native review-spec lenses, roster guard, focus flags ([#531](https://github.com/zwrose/superheroes/issues/531)) ([d9f5ea2](https://github.com/zwrose/superheroes/commit/d9f5ea222074bc6976ae2dafa6169d2eba4ce59d))
* **superheroes:** launch-prompt discipline — command + issue pointer, intake receipts extras & flags conflicts ([#521](https://github.com/zwrose/superheroes/issues/521)) ([8c8632a](https://github.com/zwrose/superheroes/commit/8c8632a8a2da3f05c8ede940a2bea3a80f139682))
* **superheroes:** lens enrichment — deleted-line audit, caller tracing, do-not-flag bar, grounding seat, focus flags ([#511](https://github.com/zwrose/superheroes/issues/511)) ([#532](https://github.com/zwrose/superheroes/issues/532)) ([4dfbdc7](https://github.com/zwrose/superheroes/commit/4dfbdc773d2bf3497064e2234ff003f0ad1d4f7c))
* **superheroes:** provenance pincer — the-architect citation rule + review-spec validator + grounding seat ([#530](https://github.com/zwrose/superheroes/issues/530)) ([3a9d120](https://github.com/zwrose/superheroes/commit/3a9d120392a754f9fe00d2c49b936bd68fc6ff32))
* **superheroes:** role/vendor taxonomy foundation — vendor registry, config ladders, role×vendor matrix, code-fixer/doc-reviser split ([#509](https://github.com/zwrose/superheroes/issues/509)) ([#523](https://github.com/zwrose/superheroes/issues/523)) ([236b69b](https://github.com/zwrose/superheroes/commit/236b69b4c9355ceeb1cb6586b3365c13013fca06))


### Bug Fixes

* **superheroes:** reconcile doc-loop cap contradiction + post-halt-edit tripwire ([#528](https://github.com/zwrose/superheroes/issues/528)) ([747677e](https://github.com/zwrose/superheroes/commit/747677e24298db03483a6400b2b64ce715115a9b))
* **superheroes:** retire panel-level confidence escalation ([#505](https://github.com/zwrose/superheroes/issues/505)) ([#522](https://github.com/zwrose/superheroes/issues/522)) ([a7413a3](https://github.com/zwrose/superheroes/commit/a7413a3e0ecfb2e2bf6d92a10063a3cfd069fb07))

## [0.16.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.15.0...superheroes-v0.16.0) (2026-07-19)


### Features

* **superheroes:** mandate the DoD disposition table in the workhorse ready-PR contract ([#499](https://github.com/zwrose/superheroes/issues/499)) ([69eca53](https://github.com/zwrose/superheroes/commit/69eca538b79f8e4b6656e18b7362f47465aac4f1))


### Bug Fixes

* **superheroes:** launch-mismatch guard — verify session root == target repo before build ([#500](https://github.com/zwrose/superheroes/issues/500)) ([aeeddfb](https://github.com/zwrose/superheroes/commit/aeeddfb23091fc3a6198b05259502e72d656a860)), closes [#496](https://github.com/zwrose/superheroes/issues/496)


### Chores

* **superheroes:** front-half skills v2 prose pass — retire stale plan/tasks framing ([#498](https://github.com/zwrose/superheroes/issues/498)) ([1beac19](https://github.com/zwrose/superheroes/commit/1beac19bd2149985d178b84132d0f358361320b2))

## [0.15.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.14.0...superheroes-v0.15.0) (2026-07-19)


### ⚠ BREAKING CHANGES

* **superheroes:** retire the plan/tasks legs — The Architect narrows to the what ([#479](https://github.com/zwrose/superheroes/issues/479))
* **superheroes:** retire the execution spine ([#478](https://github.com/zwrose/superheroes/issues/478))

### Features

* **superheroes:** add the showrunner and workhorse charter skills ([#481](https://github.com/zwrose/superheroes/issues/481)) ([2e056c0](https://github.com/zwrose/superheroes/commit/2e056c0a4a79de1631bcf2bf728d370bbbc5249e))
* **superheroes:** PHILOSOPHY amendments, the covenant, and SessionStart injection ([#480](https://github.com/zwrose/superheroes/issues/480)) ([a4771b2](https://github.com/zwrose/superheroes/commit/a4771b2e0697a2db8df57d8a45848f27feb36d17))
* **superheroes:** retire the execution spine ([#478](https://github.com/zwrose/superheroes/issues/478)) ([9e11860](https://github.com/zwrose/superheroes/commit/9e11860cf2b79b2264d9025ee8a259280040d407))
* **superheroes:** retire the plan/tasks legs — The Architect narrows to the what ([#479](https://github.com/zwrose/superheroes/issues/479)) ([8680b0e](https://github.com/zwrose/superheroes/commit/8680b0e119672ec8b398c7a31943f8068140b2f9))
* **superheroes:** S1 train 5 — configure trim + v2 model/engine knobs ([#488](https://github.com/zwrose/superheroes/issues/488)) ([d21ba68](https://github.com/zwrose/superheroes/commit/d21ba685badeabab1426e4e471b8c185aa5ed89a))
* **superheroes:** S1 train 5b — minimal owner-authority gate (the never-merge floor) ([#487](https://github.com/zwrose/superheroes/issues/487)) ([bf75305](https://github.com/zwrose/superheroes/commit/bf75305b33b68aa038704605b80127d7dec24c96))
* **superheroes:** S1 train 6 — docs finale; the discipline layer is the product ([#492](https://github.com/zwrose/superheroes/issues/492)) ([cc2fe1e](https://github.com/zwrose/superheroes/commit/cc2fe1e01d174fc408247578d92e27a0a9b16e38))
* **superheroes:** test-pilot-execute becomes observe-and-report — fixes route to the caller ([#486](https://github.com/zwrose/superheroes/issues/486)) ([ef8c07d](https://github.com/zwrose/superheroes/commit/ef8c07d7fd64e63be42896334dbf285a02b78e40))


### Bug Fixes

* **superheroes:** journal truth under courier retries — idempotent external_dispatch appends + loud re-execute-and-discard disclosure ([#459](https://github.com/zwrose/superheroes/issues/459)) ([c920425](https://github.com/zwrose/superheroes/commit/c92042599a2764a2189250dd5677b55a0151c842))
* **superheroes:** launch test-pilot dev server in the build worktree + honor its .env.local PORT ([#451](https://github.com/zwrose/superheroes/issues/451)) ([#454](https://github.com/zwrose/superheroes/issues/454)) ([873d6f8](https://github.com/zwrose/superheroes/commit/873d6f875c58760294d90138fac13fc92162ac70))
* **superheroes:** manual-completion receipt + terminal checkpoint state ([#450](https://github.com/zwrose/superheroes/issues/450)) ([#453](https://github.com/zwrose/superheroes/issues/453)) ([0381a93](https://github.com/zwrose/superheroes/commit/0381a938935e2076144cfbc951c146e2c5470647))
* **superheroes:** post-[#472](https://github.com/zwrose/superheroes/issues/472) calibration nits — degenerate engine dict, cursor probe model, override root threading ([#490](https://github.com/zwrose/superheroes/issues/490)) ([2943a63](https://github.com/zwrose/superheroes/commit/2943a63912c7d34cca531bba7898107d737e298b))
* **superheroes:** post-dispatch primary-repo confinement tripwire for engine subprocesses ([#355](https://github.com/zwrose/superheroes/issues/355)) ([#457](https://github.com/zwrose/superheroes/issues/457)) ([e28b642](https://github.com/zwrose/superheroes/commit/e28b642a69ec8d5a42e5a38752e7b745500f2bb1))
* **superheroes:** register freeze_run_rules + record_deferred at the composed-exact chokepoint, make self-management prompts classifier-benign ([#413](https://github.com/zwrose/superheroes/issues/413), [#449](https://github.com/zwrose/superheroes/issues/449)) ([#455](https://github.com/zwrose/superheroes/issues/455)) ([11cec3d](https://github.com/zwrose/superheroes/commit/11cec3d76edb689e0aa507ab28685fdb7a3c4bae))
* **superheroes:** scrub staging-denial reasons before they journal ([#383](https://github.com/zwrose/superheroes/issues/383)) ([#452](https://github.com/zwrose/superheroes/issues/452)) ([776a504](https://github.com/zwrose/superheroes/commit/776a504ababbc7c8b9a819c1ba6a4856688c1921))


### Chores

* **superheroes:** rip the orphaned legacy engine roles (author/author-plan/planAuthor/builder) ([#491](https://github.com/zwrose/superheroes/issues/491)) ([3eaf143](https://github.com/zwrose/superheroes/commit/3eaf1436395dedc0e710f950712cfb06796c2fc3)), closes [#485](https://github.com/zwrose/superheroes/issues/485)

## [0.14.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.13.2...superheroes-v0.14.0) (2026-07-15)


### Features

* **superheroes:** doc reviews converge — document-altitude severity, three-round ratchet, routed hand-off, legible parks + acceptance ([#397](https://github.com/zwrose/superheroes/issues/397)) ([#431](https://github.com/zwrose/superheroes/issues/431)) ([515e0c1](https://github.com/zwrose/superheroes/commit/515e0c1ddd0ab6f5bb3fd36235a7aee0e69c481a))


### Bug Fixes

* **superheroes:** commit_result handles history-shape engine fixes honestly — empty-diff folds are a named outcome, not a silent failure ([#392](https://github.com/zwrose/superheroes/issues/392)) ([#439](https://github.com/zwrose/superheroes/issues/439)) ([6f2157f](https://github.com/zwrose/superheroes/commit/6f2157fc66950994c4bd4376f3bf04f83ae30315))
* **superheroes:** configure view surfaces rejected codex pins; authz probe respects configured pins ([#409](https://github.com/zwrose/superheroes/issues/409)) ([#438](https://github.com/zwrose/superheroes/issues/438)) ([6a8909e](https://github.com/zwrose/superheroes/commit/6a8909e3d8cab24ac35a29ab954c5187811b07f3))
* **superheroes:** doc-panel reviewer receipts enforced at the schema layer on the receipt-missing retry — schema-minimal answers stop burning the retry budget ([#418](https://github.com/zwrose/superheroes/issues/418)) ([#441](https://github.com/zwrose/superheroes/issues/441)) ([a4725dc](https://github.com/zwrose/superheroes/commit/a4725dc5ef06edb2a013d2cef00ca280d334c577))
* **superheroes:** final-review fix commits carry a Task-Id trailer the UFR-7 gate accepts — resumes no longer fail-closed ([#375](https://github.com/zwrose/superheroes/issues/375)) ([#440](https://github.com/zwrose/superheroes/issues/440)) ([a376f28](https://github.com/zwrose/superheroes/commit/a376f2845f5ba54cebf1ed95bff9fc32dace0407))
* **superheroes:** passed-gate skip records nothing when no round state exists — absent is not unreadable; assumption-parks carry their reason ([#446](https://github.com/zwrose/superheroes/issues/446)) ([#447](https://github.com/zwrose/superheroes/issues/447)) ([18f0e31](https://github.com/zwrose/superheroes/commit/18f0e3121e2eae7b10551abe0ead503b4ca1470a))
* **superheroes:** synthesis folds match on staged ids the judge echoes — unmatched verdicts disclose loudly; doc surfaces get parity or a named exception ([#430](https://github.com/zwrose/superheroes/issues/430)) ([#443](https://github.com/zwrose/superheroes/issues/443)) ([77e5ebf](https://github.com/zwrose/superheroes/commit/77e5ebf7783e8dcaca45e983deb46b030b26e97e))

## [0.13.2](https://github.com/zwrose/superheroes/compare/superheroes-v0.13.1...superheroes-v0.13.2) (2026-07-15)


### Bug Fixes

* **superheroes:** migration commit never records core/layer deletions; store.create stops minting legacy profile.md ([#428](https://github.com/zwrose/superheroes/issues/428)) ([#429](https://github.com/zwrose/superheroes/issues/429)) ([855b3ad](https://github.com/zwrose/superheroes/commit/855b3ad84fa882010654d67ad7c429521bd83695))

## [0.13.1](https://github.com/zwrose/superheroes/compare/superheroes-v0.13.0...superheroes-v0.13.1) (2026-07-14)


### Bug Fixes

* **superheroes:** courier prompts state fidelity as transparency, not concealment-shaped prohibition ([#425](https://github.com/zwrose/superheroes/issues/425)) ([#426](https://github.com/zwrose/superheroes/issues/426)) ([7695f90](https://github.com/zwrose/superheroes/commit/7695f909c94182426fad7507b24e62bd52eda3bf))

## [0.13.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.12.0...superheroes-v0.13.0) (2026-07-14)


### Features

* **superheroes:** add GPT-5.6 Codex support ([#406](https://github.com/zwrose/superheroes/issues/406)) ([513e832](https://github.com/zwrose/superheroes/commit/513e8323d8a6aac50c329e9f328a90bac788c4c7))


### Bug Fixes

* **superheroes:** acceptance fixture seeds its own target.txt baseline ([#419](https://github.com/zwrose/superheroes/issues/419)) ([#420](https://github.com/zwrose/superheroes/issues/420)) ([d7a0a37](https://github.com/zwrose/superheroes/commit/d7a0a37df6ae753607ced6c243e33879275e93df))
* **superheroes:** add payload-is-data clause to courier prompts ([#403](https://github.com/zwrose/superheroes/issues/403)) ([491232d](https://github.com/zwrose/superheroes/commit/491232dafc9ba772bad9073df6f36997c1624905))
* **superheroes:** attribute allowance journaling to the triggering session's run ([#379](https://github.com/zwrose/superheroes/issues/379)) ([#405](https://github.com/zwrose/superheroes/issues/405)) ([5a57bcc](https://github.com/zwrose/superheroes/commit/5a57bcc7e000108bb86b327a0b0209e1ce955a1e))
* **superheroes:** DoD gate folds markdown-wrapped bullets; fill heals pre-fold truncated rows ([#422](https://github.com/zwrose/superheroes/issues/422)) ([#423](https://github.com/zwrose/superheroes/issues/423)) ([8203ce3](https://github.com/zwrose/superheroes/commit/8203ce3152413f3abf0e725652349627992d2844))
* **superheroes:** fold work-item into ALL engine staging keys — bare taskId paths were project-blind ([#408](https://github.com/zwrose/superheroes/issues/408)) ([#415](https://github.com/zwrose/superheroes/issues/415)) ([15dc66a](https://github.com/zwrose/superheroes/commit/15dc66a99a4b1534961e45d4e1d00cf7a5d1a597))
* **superheroes:** io.writeFile verifies every courier write — refused or mutated writes fail loudly ([#410](https://github.com/zwrose/superheroes/issues/410)) ([#417](https://github.com/zwrose/superheroes/issues/417)) ([e64c867](https://github.com/zwrose/superheroes/commit/e64c867f5891de79a4605fdfcb266fc146b7be3d))
* **superheroes:** re-align FR-8 composed-exact to executed bytes + denial-terminal couriers ([#402](https://github.com/zwrose/superheroes/issues/402)) ([#407](https://github.com/zwrose/superheroes/issues/407)) ([806b9cd](https://github.com/zwrose/superheroes/commit/806b9cd2a409e75cc713ade40b02b475bd3f4aaa))
* **superheroes:** test-pilot engine resolves the unified calibration layer ([#412](https://github.com/zwrose/superheroes/issues/412)) ([#416](https://github.com/zwrose/superheroes/issues/416)) ([f14c7e1](https://github.com/zwrose/superheroes/commit/f14c7e11f0c3c4044af502110ba2a163562bb284))
* **superheroes:** test-pilot prepare surfaces the leaf's real park reason ([#411](https://github.com/zwrose/superheroes/issues/411)) ([#414](https://github.com/zwrose/superheroes/issues/414)) ([6892a20](https://github.com/zwrose/superheroes/commit/6892a20d724b0525a8ec9501c8f79a5be09f19d1))

## [0.12.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.11.2...superheroes-v0.12.0) (2026-07-12)


### Features

* **superheroes:** compose real draft-PR bodies ([#219](https://github.com/zwrose/superheroes/issues/219)) ([#376](https://github.com/zwrose/superheroes/issues/376)) ([dff5409](https://github.com/zwrose/superheroes/commit/dff54095ef0536362668a1124302e94848da4681))


### Bug Fixes

* **superheroes:** final-review leg schedules its honest deep tier — no identical escalation re-dispatch ([#394](https://github.com/zwrose/superheroes/issues/394)) ([#398](https://github.com/zwrose/superheroes/issues/398)) ([fcc0318](https://github.com/zwrose/superheroes/commit/fcc031880319c4159c4ea17ec9bc9b93c85e6eab))
* **superheroes:** final-review verify gate runs in the build worktree with an enforced timeout ([#396](https://github.com/zwrose/superheroes/issues/396)) ([#399](https://github.com/zwrose/superheroes/issues/399)) ([87f2e10](https://github.com/zwrose/superheroes/commit/87f2e10fd29f9f60ff9e38563abd40efc4cf5919))

## [0.11.2](https://github.com/zwrose/superheroes/compare/superheroes-v0.11.1...superheroes-v0.11.2) (2026-07-12)


### Bug Fixes

* **superheroes:** journal external dispatch attempts that die at staging/preSHA ([#373](https://github.com/zwrose/superheroes/issues/373)) ([#374](https://github.com/zwrose/superheroes/issues/374)) ([3ca6bca](https://github.com/zwrose/superheroes/commit/3ca6bca5b756c7e430fda0f326091c0a45fb7c64))
* **superheroes:** stage engine dispatch payloads plain-readable with hash-verify ([#257](https://github.com/zwrose/superheroes/issues/257)) ([#377](https://github.com/zwrose/superheroes/issues/377)) ([3321580](https://github.com/zwrose/superheroes/commit/332158084b11e2ee2e63221744ee4cf1b31ea78a))
* **superheroes:** the external-write committer preserves the engine's own commit message ([#386](https://github.com/zwrose/superheroes/issues/386)) ([#387](https://github.com/zwrose/superheroes/issues/387)) ([35a7b6f](https://github.com/zwrose/superheroes/commit/35a7b6f14181fce11950fa2778235f8ef4ad1211))
* **superheroes:** whole-branch final review runs one review + one fix pass and hands off to review-code ([#381](https://github.com/zwrose/superheroes/issues/381)) ([#382](https://github.com/zwrose/superheroes/issues/382)) ([ec158de](https://github.com/zwrose/superheroes/commit/ec158dee50a19f7670fc9eec3c892af8f7b77f77))

## [0.11.1](https://github.com/zwrose/superheroes/compare/superheroes-v0.11.0...superheroes-v0.11.1) (2026-07-10)


### Bug Fixes

* **superheroes:** acceptance verdict requires authentic external dispatch + fix engine-pref store-root read ([#310](https://github.com/zwrose/superheroes/issues/310)) ([#331](https://github.com/zwrose/superheroes/issues/331)) ([ee81602](https://github.com/zwrose/superheroes/commit/ee816025f883ab495fa8606e32d27b9b48528259))
* **superheroes:** bound the watchdog stdout relay + unwrap the stream-json result envelope ([#347](https://github.com/zwrose/superheroes/issues/347)) ([#348](https://github.com/zwrose/superheroes/issues/348)) ([96a30f3](https://github.com/zwrose/superheroes/commit/96a30f355086fec636b1cd34b7e759eb2f75b481))
* **superheroes:** carry the acceptance driver protocol on a repo-local acceptance-driver skill ([#344](https://github.com/zwrose/superheroes/issues/344)) ([#345](https://github.com/zwrose/superheroes/issues/345)) ([b30216d](https://github.com/zwrose/superheroes/commit/b30216d0ff8a18beed1019e18cbaced7f09c81b4))
* **superheroes:** disclose ship-freshen fetch failures, rollup corruption, courier retries, bootstrap breadcrumbs ([#315](https://github.com/zwrose/superheroes/issues/315)) ([#334](https://github.com/zwrose/superheroes/issues/334)) ([3ae11f2](https://github.com/zwrose/superheroes/commit/3ae11f2875561b3a2a39ab0f2d0163d2e20286a5))
* **superheroes:** engine-dispatch couriers use the hardened path + honest courier-declined outcome + per-engine authenticity gate ([#341](https://github.com/zwrose/superheroes/issues/341)) ([#343](https://github.com/zwrose/superheroes/issues/343)) ([abff57c](https://github.com/zwrose/superheroes/commit/abff57c77eeeb04f87a4e0d416a4f05911eb9a06))
* **superheroes:** external fix dispatches state the worker output contract ([#357](https://github.com/zwrose/superheroes/issues/357)) ([#358](https://github.com/zwrose/superheroes/issues/358)) ([f93582c](https://github.com/zwrose/superheroes/commit/f93582c405bcc0033ac8bad01e8a8be90825d6bf))
* **superheroes:** make the [#286](https://github.com/zwrose/superheroes/issues/286) allowance layer operative — emit allows, confine on real exec dir, loud unseeded state ([#311](https://github.com/zwrose/superheroes/issues/311)) ([#335](https://github.com/zwrose/superheroes/issues/335)) ([d685bb2](https://github.com/zwrose/superheroes/commit/d685bb24dd6f7d9681dfddb7768bb8efde3b2f0b))
* **superheroes:** parse engine output from the shell-written capture — never re-stage it through a courier ([#349](https://github.com/zwrose/superheroes/issues/349)) ([#351](https://github.com/zwrose/superheroes/issues/351)) ([7f9166b](https://github.com/zwrose/superheroes/commit/7f9166bc5318fdcc7f86897adc0416f632bb95b7))
* **superheroes:** strictify codex --output-schema at the dispatch staging seam ([#307](https://github.com/zwrose/superheroes/issues/307)) ([#330](https://github.com/zwrose/superheroes/issues/330)) ([04de660](https://github.com/zwrose/superheroes/commit/04de660683129489d65d1c3e6e851dc943ef1962))
* **superheroes:** thread resolved model + role-appropriate timeouts through all external dispatch sites ([#308](https://github.com/zwrose/superheroes/issues/308)) ([#309](https://github.com/zwrose/superheroes/issues/309)) ([#332](https://github.com/zwrose/superheroes/issues/332)) ([1d0429f](https://github.com/zwrose/superheroes/commit/1d0429fbe420d164ec2125c92bc5d41210e0f75d))

## [0.11.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.10.0...superheroes-v0.11.0) (2026-07-08)


### Features

* **superheroes:** add permission_rules.worktree_confined (FR-5, UFR-5) ([#286](https://github.com/zwrose/superheroes/issues/286)) ([e1cc216](https://github.com/zwrose/superheroes/commit/e1cc216063ca8d7433de0ca82097e5f8e79fe4ee))
* **superheroes:** preflight readout confirm gate — dispatch roster, freeze snapshot, per-run overrides ([#162](https://github.com/zwrose/superheroes/issues/162)) ([#285](https://github.com/zwrose/superheroes/issues/285)) ([e49dc99](https://github.com/zwrose/superheroes/commit/e49dc99021c119125c5a04661bf552c6a3008840))


### Bug Fixes

* **superheroes:** bounded verify re-run + honest verify park reason ([#279](https://github.com/zwrose/superheroes/issues/279)) ([#283](https://github.com/zwrose/superheroes/issues/283)) ([c99cdd0](https://github.com/zwrose/superheroes/commit/c99cdd08afd9da4397e70990b7256c2f089d62eb))
* **superheroes:** build gate fails closed on stringy leaf ok ([#275](https://github.com/zwrose/superheroes/issues/275)) ([#280](https://github.com/zwrose/superheroes/issues/280)) ([d2fada5](https://github.com/zwrose/superheroes/commit/d2fada5045a067d09974e96d2e38709a6329fd56))
* **superheroes:** de-flake final-review smokes — pid-unique runDir + surfaced cannot-certify reason ([#290](https://github.com/zwrose/superheroes/issues/290)) ([624d401](https://github.com/zwrose/superheroes/commit/624d40194a20f59c8362f692cebc0040428d2b77))
* **superheroes:** de-flake nine more smokes — pid-unique /tmp state + root-pinned cwd ([#294](https://github.com/zwrose/superheroes/issues/294)) ([44227d5](https://github.com/zwrose/superheroes/commit/44227d50f380389864d45c114c0c23c485486cd1))
* **superheroes:** external-engine dispatch survives the Workflow sandbox ([#277](https://github.com/zwrose/superheroes/issues/277)) ([#282](https://github.com/zwrose/superheroes/issues/282)) ([51abc54](https://github.com/zwrose/superheroes/commit/51abc544553d436d2877e19374d4c37f06302373))
* **superheroes:** make fill-dod leaf schema require the rows payload ([#301](https://github.com/zwrose/superheroes/issues/301)) ([#302](https://github.com/zwrose/superheroes/issues/302)) ([63bd1f0](https://github.com/zwrose/superheroes/commit/63bd1f0c8d55b1ea9dfbd959685f97d5a4fb6a92))
* **superheroes:** parse_result honors external build/fix refusals ([#288](https://github.com/zwrose/superheroes/issues/288)) ([#292](https://github.com/zwrose/superheroes/issues/292)) ([9d2bf02](https://github.com/zwrose/superheroes/commit/9d2bf02900a7566306c76f8fb7381e3c39d2a453))
* **superheroes:** per-task review gates on verdicts + fails closed on unknown severity ([#276](https://github.com/zwrose/superheroes/issues/276)) ([#278](https://github.com/zwrose/superheroes/issues/278)) ([6f0f401](https://github.com/zwrose/superheroes/commit/6f0f401ad3cb760538bfffd6e22507a69916b849))
* **superheroes:** refuse a non-ancestor --root in the acceptance harness + raise the default ceiling ([#298](https://github.com/zwrose/superheroes/issues/298)) ([#304](https://github.com/zwrose/superheroes/issues/304)) ([4683e4a](https://github.com/zwrose/superheroes/commit/4683e4aa1bfc3e70476188176e5678962ca0cf81))
* **superheroes:** startup gather rides the __SR_EXIT proof-of-execution marker ([#281](https://github.com/zwrose/superheroes/issues/281)) ([#289](https://github.com/zwrose/superheroes/issues/289)) ([14f2998](https://github.com/zwrose/superheroes/commit/14f2998f379af5544d153fab668d686024502a4e))
* **superheroes:** strip comments at bundle-emit time to stay under Workflow script-size cap ([#297](https://github.com/zwrose/superheroes/issues/297)) ([bd84ac0](https://github.com/zwrose/superheroes/commit/bd84ac050bc0c9ad4846ae98b90ce93863fd92fd))

## [0.10.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.9.0...superheroes-v0.10.0) (2026-07-06)


### Features

* **superheroes:** acceptance-harness fixture, stamp, and drift check ([#112](https://github.com/zwrose/superheroes/issues/112)) ([#205](https://github.com/zwrose/superheroes/issues/205)) ([ae90976](https://github.com/zwrose/superheroes/commit/ae90976837adfd19d59d88622db24459a85688b7))
* **superheroes:** pre-release evidence gate + release-eval skill; de-distribute acceptance skill ([#241](https://github.com/zwrose/superheroes/issues/241)) ([c2f30a1](https://github.com/zwrose/superheroes/commit/c2f30a1abfc1fcabb9b6b01f510b73c43be36d13))
* **superheroes:** premortem charter interrogates fail-direction + LLM-courier transport contracts ([#188](https://github.com/zwrose/superheroes/issues/188)) ([#239](https://github.com/zwrose/superheroes/issues/239)) ([00cec7f](https://github.com/zwrose/superheroes/commit/00cec7fb9a71ed39abd8afb150d354d8f5734cf0))
* **superheroes:** project-level courier allow-rules via configure (+ revert [#254](https://github.com/zwrose/superheroes/issues/254) prompt clause) ([#256](https://github.com/zwrose/superheroes/issues/256)) ([86c536f](https://github.com/zwrose/superheroes/commit/86c536f3f026d8153044f8d04ed93becae4acda6))
* **superheroes:** ship-phase honesty gates — DoD disposition + no-silent-stubs ([#228](https://github.com/zwrose/superheroes/issues/228)) ([#234](https://github.com/zwrose/superheroes/issues/234)) ([e38d88c](https://github.com/zwrose/superheroes/commit/e38d88cc73a302a1d690fa8e0975d948cfaac90f))


### Bug Fixes

* **superheroes:** acceptance harness --spine-lib pre-release spine override ([#236](https://github.com/zwrose/superheroes/issues/236)) ([11ad3fd](https://github.com/zwrose/superheroes/commit/11ad3fddc9fbbc26f7839ea03ec648d5b29bd963))
* **superheroes:** acceptance harness live seams — 7 findings from the 0.10.0 qualification ([#244](https://github.com/zwrose/superheroes/issues/244)) ([e7cd430](https://github.com/zwrose/superheroes/commit/e7cd43095d57380915ec41eca62c25a2cdb48f52))
* **superheroes:** acceptance verifier waits out pending checks (finding [#14](https://github.com/zwrose/superheroes/issues/14)) ([#264](https://github.com/zwrose/superheroes/issues/264)) ([7600243](https://github.com/zwrose/superheroes/commit/760024368bc4ce1d00ecb26c699f1b56945d756c))
* **superheroes:** argv-shape store writes — sensitive-file guard never fires (finding [#13](https://github.com/zwrose/superheroes/issues/13)) ([#262](https://github.com/zwrose/superheroes/issues/262)) ([da2818e](https://github.com/zwrose/superheroes/commit/da2818ec2ea71644e21005c4ea4f6e4ed91083c4))
* **superheroes:** CLI subprocess tests sweep a throwaway git root, not the real repo ([#247](https://github.com/zwrose/superheroes/issues/247)) ([174a3ff](https://github.com/zwrose/superheroes/commit/174a3ff1bf7f496cbcf4f62017c58d7189ba43aa))
* **superheroes:** declare courier intent in-prompt — classifier false-positive hardening ([#254](https://github.com/zwrose/superheroes/issues/254)) ([c969a4c](https://github.com/zwrose/superheroes/commit/c969a4ca2c14edcd7132bc898d01cbd7212ce45c))
* **superheroes:** DoD disposition-filler leg + ship CI settle-wait (findings [#10](https://github.com/zwrose/superheroes/issues/10)–[#11](https://github.com/zwrose/superheroes/issues/11), 0.10.0 qualification) ([#251](https://github.com/zwrose/superheroes/issues/251)) ([39e44a8](https://github.com/zwrose/superheroes/commit/39e44a8e1a2eb203ecd8d1a6506b05ad1c0513e0))
* **superheroes:** DoD propose leaf must evidence every bullet (finding [#17](https://github.com/zwrose/superheroes/issues/17)) ([#268](https://github.com/zwrose/superheroes/issues/268)) ([e3575bd](https://github.com/zwrose/superheroes/commit/e3575bdf9afcc0712d9553cae2f067a3b7c0be6b))
* **superheroes:** headless acceptance child runs in default permission mode ([#259](https://github.com/zwrose/superheroes/issues/259)) ([a5fcf5a](https://github.com/zwrose/superheroes/commit/a5fcf5aa35cc37bc215c17c3a00514670c13d37c))
* **superheroes:** honest circuit-breaker cap-halt message — actual round + real fix state ([#224](https://github.com/zwrose/superheroes/issues/224)) ([b61e2e0](https://github.com/zwrose/superheroes/commit/b61e2e0bfd936164b73d0bfa96bf56d1e6db7bb8))
* **superheroes:** move terminal-record handoff out of the sensitive tree (finding [#16](https://github.com/zwrose/superheroes/issues/16)) ([#266](https://github.com/zwrose/superheroes/issues/266)) ([8268dec](https://github.com/zwrose/superheroes/commit/8268dec7b5cba42c38211bbc657f5c449f497bfc))
* **superheroes:** normalize head reads + prefix-tolerant compare (finding [#15](https://github.com/zwrose/superheroes/issues/15)) ([#265](https://github.com/zwrose/superheroes/issues/265)) ([0e5590d](https://github.com/zwrose/superheroes/commit/0e5590d58823eac94aa05287af52dd6bb1f29825))
* **superheroes:** real store-base in engine-prefs gather + doc-pointer in workhorse prompts ([#221](https://github.com/zwrose/superheroes/issues/221), [#222](https://github.com/zwrose/superheroes/issues/222)) ([#225](https://github.com/zwrose/superheroes/issues/225)) ([adb9b10](https://github.com/zwrose/superheroes/commit/adb9b10e3caba7cdd5ed60be08a6ffad11a06f65))
* **superheroes:** reap orphaned child group after ungraceful harness death ([#245](https://github.com/zwrose/superheroes/issues/245)) ([#246](https://github.com/zwrose/superheroes/issues/246)) ([f670d79](https://github.com/zwrose/superheroes/commit/f670d798d9e0fc71987e8589b4815330927d7a2c))
* **superheroes:** route full-vs-quick at the framing brief, not up front ([#223](https://github.com/zwrose/superheroes/issues/223)) ([#240](https://github.com/zwrose/superheroes/issues/240)) ([6db6636](https://github.com/zwrose/superheroes/commit/6db6636fee800e73a6c40dbb8b20455b40230196))
* **superheroes:** route libRoot probes through __SR_EXIT marker protocol ([#232](https://github.com/zwrose/superheroes/issues/232)) ([5ca7dfb](https://github.com/zwrose/superheroes/commit/5ca7dfb2074ff2222e001404fecebb56855b587f))
* **superheroes:** settle CI before the DoD proposal leaf (finding [#12](https://github.com/zwrose/superheroes/issues/12)) ([#261](https://github.com/zwrose/superheroes/issues/261)) ([d2fe7de](https://github.com/zwrose/superheroes/commit/d2fe7de798349059dce5f5c48422ecca46e2e578))
* **superheroes:** ship push tolerates a committed CI fix + lag-proof push read-back ([#220](https://github.com/zwrose/superheroes/issues/220)) ([6073c50](https://github.com/zwrose/superheroes/commit/6073c50d57e41e99efabd97c4dbe6b043f62c08c))
* **superheroes:** verifier reads commit statuses via ci_status (finding [#18](https://github.com/zwrose/superheroes/issues/18)) ([#271](https://github.com/zwrose/superheroes/issues/271)) ([52ef686](https://github.com/zwrose/superheroes/commit/52ef686671f2565a27ee11e857b9f47c0269e1fb))


### Chores

* **superheroes:** one-home-per-cross-boundary-fact convention (§11) + roster drift guard ([#238](https://github.com/zwrose/superheroes/issues/238)) ([8827cd4](https://github.com/zwrose/superheroes/commit/8827cd46aa49941947809985c2873b94e1f7b6a6))

## [0.9.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.8.0...superheroes-v0.9.0) (2026-07-05)


### Features

* **superheroes:** quick-discovery the-architect leg — routing, in-session task authoring, alignment probe, gate/launch wiring ([#25](https://github.com/zwrose/superheroes/issues/25) · PR 2) ([#210](https://github.com/zwrose/superheroes/issues/210)) ([ceafd72](https://github.com/zwrose/superheroes/commit/ceafd72a57df7dd9390ac42faa56abddfe57dc64))
* **superheroes:** quick-route showrunner intake — spec-less-but-never-review-less ([#25](https://github.com/zwrose/superheroes/issues/25) · PR 1) ([#200](https://github.com/zwrose/superheroes/issues/200)) ([761e79b](https://github.com/zwrose/superheroes/commit/761e79b1a19437263b5ba36917be8652b510b1be))
* **superheroes:** review-discipline convention — repo rule + portable to calibrated projects ([#190](https://github.com/zwrose/superheroes/issues/190)) ([7d5898a](https://github.com/zwrose/superheroes/commit/7d5898af4e920575f50dcb50358677991a664447))
* **superheroes:** review-loop deciders — decisions up, pointers down ([#211](https://github.com/zwrose/superheroes/issues/211) · PR 1 of 3) ([#214](https://github.com/zwrose/superheroes/issues/214)) ([c7dfd8d](https://github.com/zwrose/superheroes/commit/c7dfd8d508d9bd5b20548551261cf44420ff2f13))
* **superheroes:** review-loop shell cutover — decisions up, pointers down ([#211](https://github.com/zwrose/superheroes/issues/211) · PR 2 of 3) ([#216](https://github.com/zwrose/superheroes/issues/216)) ([d517cc3](https://github.com/zwrose/superheroes/commit/d517cc37e12ad1aa1a594f6c29e37cb23f439299))


### Bug Fixes

* **superheroes:** first test-pilot status write must treat an absent file as apply-needed ([#209](https://github.com/zwrose/superheroes/issues/209)) ([d15dda0](https://github.com/zwrose/superheroes/commit/d15dda09e7f81ff77dab86c29f31a9ed16becd53))
* **superheroes:** raw-text read-chunk fallback + delete the cutover-orphaned machinery ([#211](https://github.com/zwrose/superheroes/issues/211) · PR 3 of 3) ([#217](https://github.com/zwrose/superheroes/issues/217)) ([2ff4b28](https://github.com/zwrose/superheroes/commit/2ff4b280c3dde5d1d909a8edf8d59397e4b27556))
* **superheroes:** review-loop cures receipt-less answers — corrective retry, fix-before-park, honest reasons ([#212](https://github.com/zwrose/superheroes/issues/212)) ([#215](https://github.com/zwrose/superheroes/issues/215)) ([b588ff0](https://github.com/zwrose/superheroes/commit/b588ff09392bafc84727e7be7d4dcd23e22ef285))
* **superheroes:** self-cert gate snippets use the fenced set-gate form ([#213](https://github.com/zwrose/superheroes/issues/213)) ([7894b6b](https://github.com/zwrose/superheroes/commit/7894b6b64c569d02d4a55913394bc3c81a377662))

## [0.8.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.7.0...superheroes-v0.8.0) (2026-07-04)


### Features

* **superheroes:** entry-bootstrap resume decider — ship decisions, not record content ([#193](https://github.com/zwrose/superheroes/issues/193)) ([#199](https://github.com/zwrose/superheroes/issues/199)) ([1d9438c](https://github.com/zwrose/superheroes/commit/1d9438cec480d20660ab196a1d8536401ecd10fa))
* **superheroes:** lean courier agent — cut the ~34k fixed context every one-command leaf pays ([#194](https://github.com/zwrose/superheroes/issues/194)) ([#198](https://github.com/zwrose/superheroes/issues/198)) ([0770830](https://github.com/zwrose/superheroes/commit/0770830539b461f5fea0d6cd8b091ce4fe45047b))


### Bug Fixes

* **superheroes:** de-bait chunk relay payloads + payload-tier read pins ([#192](https://github.com/zwrose/superheroes/issues/192)) ([31e2fa4](https://github.com/zwrose/superheroes/commit/31e2fa459a9f7dc2ef13a755398736cfa28e9617))
* **superheroes:** fall back to default dispatch when the courier agent type is unknown ([#206](https://github.com/zwrose/superheroes/issues/206)) ([44ee2e5](https://github.com/zwrose/superheroes/commit/44ee2e562acf137887eb23adca1d8f0f1a652435))
* **superheroes:** push the build branch before draft-PR creation ([#203](https://github.com/zwrose/superheroes/issues/203)) ([a7ebb84](https://github.com/zwrose/superheroes/commit/a7ebb84c26b3bb5e4b961b82f3f7dcf5fd6040c4))
* **superheroes:** state the engine-dispatch timeout expiry contract (structural via [#204](https://github.com/zwrose/superheroes/issues/204)) ([#202](https://github.com/zwrose/superheroes/issues/202)) ([#207](https://github.com/zwrose/superheroes/issues/207)) ([fe5fc2b](https://github.com/zwrose/superheroes/commit/fe5fc2b2e479130300e1f2f8763d233508fb5d72))
* **superheroes:** structural Bash timeout floor via PreToolUse updatedInput hook ([#204](https://github.com/zwrose/superheroes/issues/204)) ([d220280](https://github.com/zwrose/superheroes/commit/d22028011501cb8e7dc04c88ab4f4a589f489f79))
* **superheroes:** tolerate bare-array reviewer output + state the stdout shape contract ([#196](https://github.com/zwrose/superheroes/issues/196)) ([#201](https://github.com/zwrose/superheroes/issues/201)) ([db08e3e](https://github.com/zwrose/superheroes/commit/db08e3e3dec43abc4a235771b5f077fdfc793e8f))
* **superheroes:** verify read-back must survive a thrown courier ([#195](https://github.com/zwrose/superheroes/issues/195)) ([8802019](https://github.com/zwrose/superheroes/commit/8802019efb1ae779c7932be6a784b776edbe41b5))

## [0.7.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.6.0...superheroes-v0.7.0) (2026-07-04)


### Features

* **superheroes:** confirmation-bar economics for the shared review loop ([#174](https://github.com/zwrose/superheroes/issues/174) · PR 1) ([#181](https://github.com/zwrose/superheroes/issues/181)) ([6c3c76a](https://github.com/zwrose/superheroes/commit/6c3c76affaf40003b7c3759cf675629793eb2b58))
* **superheroes:** fail-closed synthesis pass in standalone review-code + honest review-base rewrite ([#174](https://github.com/zwrose/superheroes/issues/174) · PR 3) ([#185](https://github.com/zwrose/superheroes/issues/185)) ([2b73745](https://github.com/zwrose/superheroes/commit/2b73745c8f3247470b8490ab6039377c7bd78566))
* **superheroes:** script-owned round scheduler for review-code ([#174](https://github.com/zwrose/superheroes/issues/174) · PR 2) ([#182](https://github.com/zwrose/superheroes/issues/182)) ([c7657ff](https://github.com/zwrose/superheroes/commit/c7657ffeb2ea0742bf7a5e653d9858d8bb2de219))
* **superheroes:** token telemetry — per-phase cost in the journal, readout, and a per-work-item trend ([#130](https://github.com/zwrose/superheroes/issues/130)) ([#179](https://github.com/zwrose/superheroes/issues/179)) ([dbb7393](https://github.com/zwrose/superheroes/commit/dbb7393d1b19bdc27f3ae8be49611ecbfbe8360d))


### Bug Fixes

* **superheroes:** courier inline-backtick tolerance + rooted synthesis verification + drop-identity fallback ([#178](https://github.com/zwrose/superheroes/issues/178)) ([034caa7](https://github.com/zwrose/superheroes/commit/034caa7575fdd44e9f0787ec13b102ccd52a2e6f))
* **superheroes:** flag blocking→non-blocking synthesis downgrades like drops ([#186](https://github.com/zwrose/superheroes/issues/186)) ([#187](https://github.com/zwrose/superheroes/issues/187)) ([1e5b643](https://github.com/zwrose/superheroes/commit/1e5b64325ca90fb985a7ef0cf2b937a0af8e738f))
* **superheroes:** harden review dispatch reliability ([#176](https://github.com/zwrose/superheroes/issues/176)) ([7957f5b](https://github.com/zwrose/superheroes/commit/7957f5b218154d79c6ab00ebf53baae5f70f68dd))

## [0.6.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.5.0...superheroes-v0.6.0) (2026-07-03)


### Features

* **superheroes:** common-dir coordination store + guard cleanup (PR 2 of [#170](https://github.com/zwrose/superheroes/issues/170)) ([#172](https://github.com/zwrose/superheroes/issues/172)) ([6bf7d2b](https://github.com/zwrose/superheroes/commit/6bf7d2bf353691591cc4182c9d338da5b24587f0))
* **superheroes:** Fable plan-authoring options — author-plan tier + planAuthor engine ([#168](https://github.com/zwrose/superheroes/issues/168)) ([b2e96f8](https://github.com/zwrose/superheroes/commit/b2e96f89118f688aeb7eba77cb9e358ec155e989))
* **superheroes:** libRoot — portable, version-pinned spine (PR 1 of [#170](https://github.com/zwrose/superheroes/issues/170)) ([#171](https://github.com/zwrose/superheroes/issues/171)) ([746b741](https://github.com/zwrose/superheroes/commit/746b7414ece878fae32bc6396d5c963454e7829c))
* **superheroes:** script-owned review-spec round scheduler ([#164](https://github.com/zwrose/superheroes/issues/164)) ([#167](https://github.com/zwrose/superheroes/issues/167)) ([26c4e15](https://github.com/zwrose/superheroes/commit/26c4e1578348e3cd1c64e7a0b5eb5f8d245cb715))


### Bug Fixes

* **superheroes:** fail closed on synthesized review findings ([#169](https://github.com/zwrose/superheroes/issues/169)) ([d54f9e1](https://github.com/zwrose/superheroes/commit/d54f9e192d9587ef3100dd4dcc1d7c8e0e070e6c))
* **superheroes:** per-task reviewer honors reviewer engine + model tier ([#160](https://github.com/zwrose/superheroes/issues/160)) ([#163](https://github.com/zwrose/superheroes/issues/163)) ([97dafcd](https://github.com/zwrose/superheroes/commit/97dafcdfee4cbbfbdc5113f8a0802b4ca46ecbbf))
* **superheroes:** preserve review loop changed subjects ([#161](https://github.com/zwrose/superheroes/issues/161)) ([26c2f99](https://github.com/zwrose/superheroes/commit/26c2f991797b9ae2d9f47c06102dfbf1bb5cfc1c))

## [0.5.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.4.0...superheroes-v0.5.0) (2026-07-03)


### Features

* **superheroes:** add run_watch live watch CLI ([#155](https://github.com/zwrose/superheroes/issues/155)) ([015d770](https://github.com/zwrose/superheroes/commit/015d770ef137ca87466e0b2a7c6df3576e36657d))
* **superheroes:** add task-scoped labels to build-phase leaves ([#150](https://github.com/zwrose/superheroes/issues/150)) ([#153](https://github.com/zwrose/superheroes/issues/153)) ([8f9effc](https://github.com/zwrose/superheroes/commit/8f9effc52de87c25e601fdcb5621f0c843e8a6bb))
* **superheroes:** close the [#118](https://github.com/zwrose/superheroes/issues/118) courier-collapse acceptance gaps and land the D3 review-round durability rework ([#138](https://github.com/zwrose/superheroes/issues/138)) ([05a1965](https://github.com/zwrose/superheroes/commit/05a1965b70f0a36173375dd239fec0566c198979))
* **superheroes:** record store provenance and add orphan report/sweep ([#134](https://github.com/zwrose/superheroes/issues/134)) ([b153911](https://github.com/zwrose/superheroes/commit/b153911ed2774c965a24dea63328a8b62c0ba0db))


### Bug Fixes

* **superheroes:** build-half resolver bypass + transport hardening ([#146](https://github.com/zwrose/superheroes/issues/146)) ([a705f5a](https://github.com/zwrose/superheroes/commit/a705f5aa78729654a489dcea264b482aba325eb8))
* **superheroes:** collapse the review-loop bookkeeping stretches to the [#118](https://github.com/zwrose/superheroes/issues/118) 0-or-1-leaf bar ([#141](https://github.com/zwrose/superheroes/issues/141)) ([e5b0091](https://github.com/zwrose/superheroes/commit/e5b009168ef4844edf527833fafdb62335d70c65))
* **superheroes:** compose terminal-record Python-side to survive the courier ([#144](https://github.com/zwrose/superheroes/issues/144)) ([4e496c8](https://github.com/zwrose/superheroes/commit/4e496c84161f395b7539c130b325c9a2055b6edc))
* **superheroes:** derive policy subjects from code-fixer file-path shape ([#157](https://github.com/zwrose/superheroes/issues/157)) ([#158](https://github.com/zwrose/superheroes/issues/158)) ([538e883](https://github.com/zwrose/superheroes/commit/538e883219ccc22f3c91a670ed97fb919042f882))
* **superheroes:** descriptive exec-courier labels ([#151](https://github.com/zwrose/superheroes/issues/151)) ([#154](https://github.com/zwrose/superheroes/issues/154)) ([fc256fb](https://github.com/zwrose/superheroes/commit/fc256fb05e9f3ab8d483c8f7b78eb042a6fe737e))
* **superheroes:** drop top-level allOf from FINDINGS_SCHEMA ([#156](https://github.com/zwrose/superheroes/issues/156)) ([2eef51b](https://github.com/zwrose/superheroes/commit/2eef51b7fe3dcea9196dedd7df6103ca24e9c12f))
* **superheroes:** fence-blind runHelper + two-JSON-line persist park (run-8 dogfood) ([#140](https://github.com/zwrose/superheroes/issues/140)) ([a2eb441](https://github.com/zwrose/superheroes/commit/a2eb4413ab574de7e870c7fa98e98b9af959dcf8))
* **superheroes:** finish [#123](https://github.com/zwrose/superheroes/issues/123) unified layout migration for review-code ([#148](https://github.com/zwrose/superheroes/issues/148)) ([476d167](https://github.com/zwrose/superheroes/commit/476d1675d248265f4d7703dcce9ec92e87a6b58a))
* **superheroes:** five showrunner-spine defects from the 2026-07-02 live dogfood run ([#136](https://github.com/zwrose/superheroes/issues/136)) ([d248a29](https://github.com/zwrose/superheroes/commit/d248a295d6cb2eaa0cee08a4f83b58a7fc217e1a))
* **superheroes:** harden run_watch fail-soft + status accuracy ([#159](https://github.com/zwrose/superheroes/issues/159)) ([68a5297](https://github.com/zwrose/superheroes/commit/68a529744d24fc062792f23818c902680c670093))
* **superheroes:** harden showrunner leaf model governance ([#142](https://github.com/zwrose/superheroes/issues/142)) ([c6bb970](https://github.com/zwrose/superheroes/commit/c6bb970e278bf3ebf524abe1161d61f73f81f46d))
* **superheroes:** restore review-loop convergence levers ([#145](https://github.com/zwrose/superheroes/issues/145)) ([c1127b0](https://github.com/zwrose/superheroes/commit/c1127b08792aacc13c0ccfe0db435b8baffc455c))
* **superheroes:** stop fabricating verification receipts + remove dead build_progress_cli.py ([#139](https://github.com/zwrose/superheroes/issues/139)) ([9f29253](https://github.com/zwrose/superheroes/commit/9f29253ad0aff3ca543217d90f42d065e27a5c52))
* **superheroes:** Task-Id body parse + workhorse park lease release ([#147](https://github.com/zwrose/superheroes/issues/147)) ([0034454](https://github.com/zwrose/superheroes/commit/0034454ec3daae370312877d7de27cf75a3ce483))

## [0.4.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.3.0...superheroes-v0.4.0) (2026-07-02)


### Features

* **superheroes:** collapse showrunner haiku-courier surface to one leaf per stretch ([#127](https://github.com/zwrose/superheroes/issues/127)) ([e0fd8b0](https://github.com/zwrose/superheroes/commit/e0fd8b0654d7d29854f00a3c5326d97f9d49d3bd))
* **superheroes:** make the shared review-and-fix loop converge faster ([#125](https://github.com/zwrose/superheroes/issues/125)) ([#129](https://github.com/zwrose/superheroes/issues/129)) ([e3e7b0b](https://github.com/zwrose/superheroes/commit/e3e7b0bbe25ddf045462bb5f66bd211d9fb3a4c7))
* **superheroes:** onboard Codex and Cursor as per-role review and build engines ([#38](https://github.com/zwrose/superheroes/issues/38)) ([#128](https://github.com/zwrose/superheroes/issues/128)) ([10e7134](https://github.com/zwrose/superheroes/commit/10e7134e309514e16af1e740d6c7eb66d42891ce))
* **superheroes:** wire the native showrunner back-half — CI-fix loop, freshen, fence ([#120](https://github.com/zwrose/superheroes/issues/120)) ([#126](https://github.com/zwrose/superheroes/issues/126)) ([c174c28](https://github.com/zwrose/superheroes/commit/c174c2853c531ab4d8fd664a27513fbf5e3ca857))


### Bug Fixes

* **superheroes:** [#121](https://github.com/zwrose/superheroes/issues/121) calibration/storage hardening — confirm path, data-loss guards, store rename, unified-layout reconciliation ([#122](https://github.com/zwrose/superheroes/issues/122)) ([d14961f](https://github.com/zwrose/superheroes/commit/d14961f652aa9699f9a3272a67e925e79e76559f))

## [0.3.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.2.0...superheroes-v0.3.0) (2026-06-29)


### Features

* **superheroes:** add native test-pilot workflow phase ([#109](https://github.com/zwrose/superheroes/issues/109)) ([5a40dab](https://github.com/zwrose/superheroes/commit/5a40dab46658a92484d14d993aea2a80171b84e4))
* **superheroes:** code-execution-native showrunner spine ([#115](https://github.com/zwrose/superheroes/issues/115)) ([#114](https://github.com/zwrose/superheroes/issues/114)) ([f07787a](https://github.com/zwrose/superheroes/commit/f07787aeb42b10a06c664e2a41c8de1f06c8c684))
* **superheroes:** native front-half (plan & tasks phases) on the shared review-and-fix loop ([#88](https://github.com/zwrose/superheroes/issues/88)) ([#108](https://github.com/zwrose/superheroes/issues/108)) ([d7cfd06](https://github.com/zwrose/superheroes/commit/d7cfd06418ad5e8d79bf5b6dff1fde6645d95997))
* **superheroes:** native review-code panel + auto-fix loop ([#89](https://github.com/zwrose/superheroes/issues/89)) ([#106](https://github.com/zwrose/superheroes/issues/106)) ([cf60f5f](https://github.com/zwrose/superheroes/commit/cf60f5ff33b9940da44ed014cd24dc5eba8ef698))
* **superheroes:** native workhorse build phase ([#87](https://github.com/zwrose/superheroes/issues/87)) ([#107](https://github.com/zwrose/superheroes/issues/107)) ([3d4d834](https://github.com/zwrose/superheroes/commit/3d4d834a2ffcd7a979664e474bd6ac0c45bc9734))
* **superheroes:** review-crew + test-pilot honor the storage-mode registry (I2, [#79](https://github.com/zwrose/superheroes/issues/79)) ([#99](https://github.com/zwrose/superheroes/issues/99)) ([559866c](https://github.com/zwrose/superheroes/commit/559866cad7e31b40771745ec4e89e95f4fea6ac2))
* **superheroes:** shared core.md calibration brain + unified profile format ([#81](https://github.com/zwrose/superheroes/issues/81)) ([#113](https://github.com/zwrose/superheroes/issues/113)) ([64880e9](https://github.com/zwrose/superheroes/commit/64880e927f1b46c1d0d74bffb43707cbe5a2434f))
* **superheroes:** shared review-and-fix loop (extract-first, [#104](https://github.com/zwrose/superheroes/issues/104)) ([#105](https://github.com/zwrose/superheroes/issues/105)) ([155692f](https://github.com/zwrose/superheroes/commit/155692feb0922ba7b2764d7f83b1622d6da23910))
* **superheroes:** showrunner per-issue Workflow spine (thin slice) ([#103](https://github.com/zwrose/superheroes/issues/103)) ([4243fef](https://github.com/zwrose/superheroes/commit/4243fef46ef629405d661cfc8a15287839444a5a)), closes [#21](https://github.com/zwrose/superheroes/issues/21)
* **superheroes:** the-architect mode-aware definition-docs + doc-policy (I3) ([#101](https://github.com/zwrose/superheroes/issues/101)) ([f377732](https://github.com/zwrose/superheroes/commit/f377732c55527b4c01751e7d52311085e664df56))
* **superheroes:** unified superheroes:configure — set up, fix, view & tune ([#82](https://github.com/zwrose/superheroes/issues/82), [#83](https://github.com/zwrose/superheroes/issues/83)) ([#116](https://github.com/zwrose/superheroes/issues/116)) ([bc670eb](https://github.com/zwrose/superheroes/commit/bc670ebc4eecf5e7ec70705f5ad208e98f1b7fcb))


### Bug Fixes

* **superheroes:** scope workhorse enforcer to owner-role actions, not generic danger ([#117](https://github.com/zwrose/superheroes/issues/117)) ([d3ed088](https://github.com/zwrose/superheroes/commit/d3ed088b7a75210c50bbacf65744c8a48cd3519b))

## [0.2.0](https://github.com/zwrose/superheroes/compare/superheroes-v0.1.0...superheroes-v0.2.0) (2026-06-21)


### Features

* **superheroes:** fail-closed GitHub-access preflight at workhorse step 0 ([#26](https://github.com/zwrose/superheroes/issues/26)) ([#94](https://github.com/zwrose/superheroes/issues/94)) ([d498815](https://github.com/zwrose/superheroes/commit/d498815990a4675ce4b8462fbb81012906b5be1d))
* **superheroes:** front-load decision context across discovery + escalation, slim discovery's pre-spec gate ([#91](https://github.com/zwrose/superheroes/issues/91)) ([f940baa](https://github.com/zwrose/superheroes/commit/f940baadcfa8aaf894af53bc53036c482710a756))
* **superheroes:** inject session-context bootstrap on SessionStart ([#95](https://github.com/zwrose/superheroes/issues/95)) ([ec9daaf](https://github.com/zwrose/superheroes/commit/ec9daaff28122ce3cb17c7fe60b57ec6a4844166))
* **superheroes:** managed build-worktree lifecycle ([#77](https://github.com/zwrose/superheroes/issues/77)) ([#98](https://github.com/zwrose/superheroes/issues/98)) ([facddba](https://github.com/zwrose/superheroes/commit/facddba305376e6b25c8a08c7e3e283ae5cb4315))
* **superheroes:** reusable review-panel + loop-to-clean building block ([#86](https://github.com/zwrose/superheroes/issues/86)) ([#96](https://github.com/zwrose/superheroes/issues/96)) ([0ce63f7](https://github.com/zwrose/superheroes/commit/0ce63f7f7ab3a0aaef0f9443308e2c0209816215))
* **superheroes:** storage-mode registry, resolver & reconciler foundation (I1) ([#97](https://github.com/zwrose/superheroes/issues/97)) ([23b44e1](https://github.com/zwrose/superheroes/commit/23b44e16cdde0fabed23efed7394be361dd29007))

## 0.1.0 (2026-06-20)


### ⚠ BREAKING CHANGES

* **superheroes:** consolidate the band into one plugin ([#72](https://github.com/zwrose/superheroes/issues/72))

### Features

* **superheroes:** consolidate the band into one plugin ([#72](https://github.com/zwrose/superheroes/issues/72)) ([6a37479](https://github.com/zwrose/superheroes/commit/6a374793fecb67ae9f502b1e924ce933799a99f7))


### Bug Fixes

* **superheroes:** seed release-please baseline at 0.0.0 so the first release computes 0.1.0 ([#74](https://github.com/zwrose/superheroes/issues/74)) ([684f3d8](https://github.com/zwrose/superheroes/commit/684f3d8a18e687b70b94442075be46c5703c825b))

## Changelog — superheroes
