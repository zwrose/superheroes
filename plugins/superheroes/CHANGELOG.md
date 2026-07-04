# Changelog

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
