<!-- covers: A1, A2, A3, A4, A5, A7, B1, B2, B3, B4, B6 -->

#### A1 — Owner-authority gate

- **Component.** PreToolUse(Bash) gate and classifier that ask before enumerated owner-authority
  actions on calibrated projects; it costs a stdin parse and command inspection on every Bash call.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing an
  owner-authority gate `ask` that blocked an unauthorized merge, release, force-push, default-branch
  push, or workflow dispatch. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Re-derived tool-to-subcommand matching to close a silent
  classification bypass in workflow dispatch (#989).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — implements the never-merge-on-agent-authority hard line; a zero citation
  count means the floor is holding, not that the bypass class is gone.

#### A2 — Worktree guard

- **Component.** PreToolUse(Bash) gate and classifier that deny destructive git discard on dirty
  calibrated worktrees; it costs a git status probe on matching commands.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing a
  worktree-guard `deny` that prevented the checkout-revert wipe class. On firing, a proposal to the
  owner at a gardening pass.
- **Last demonstrated benefit.** Refuses destructive `git` discard when uncommitted work would be
  lost, guarding the checkout-revert wipe class (#682).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — guards unrecoverable worktree loss; a zero citation count means agents are
  not attempting the wipe, not that the defect class vanished.

#### A3 — Handback receipt gate (hook)

- **Component.** PreToolUse(Bash) handback-receipt hook shipped dark and unwired from the live hook
  chain, with zero shipped consumers ever; K1 retires it with `handback_gate.py` (#954).
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing a live
  handback-receipt refusal (none possible while dark and unwired). On firing, a retirement proposal
  to the owner at a gardening pass. An absent, unreadable, or short-of-window record reads
  unmeasured, never zero.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** harness-limit — the host PreToolUse chain does not arm this hook; review-before-handback
  is held in charter prose until K1 lands.

#### A4 — Bash timeout hook

- **Component.** PreToolUse(Bash) input rewrite that floors omitted Bash tool timeouts to 600s; it
  costs a stdin parse on every Bash call and works around the host's 120s default.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts in which the
  injected timeout floor is what let a command finish. On firing, a proposal to the owner at a
  gardening pass. A citation reads this hook's own record; an absent, unreadable, or short-of-window
  record reads unmeasured, never zero.
- **Last demonstrated benefit.** Probe-verified that injected timeout takes effect and that plugin
  PreToolUse hooks fire inside subagent leaves (hooks/bash_timeout.py docstring, 2026-07-04).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** harness-limit — leaf models omit `timeout` stochastically and the host default kills long
  spine commands; explicit model-passed timeouts are never touched.

#### A5 — Session bootstrap (covenant inject, compaction recovery, skew notice)

- **Component.** SessionStart bootstrap and PreCompact charter-aware compaction skeleton; the row is
  process prose machinery loaded on every spawn and compact, and it costs context tokens per
  session.
- **Condition.** Usage-based, 60 days: calibrated sessions where bootstrap or compaction context
  fired (startup, resume, clear, or compact sources). On firing, a proposal to the owner at a
  gardening pass.
- **Last demonstrated benefit.** Probe-verified that native harness context loads on all spawn paths
  while bootstrap still supplies plugin roots and the distilled covenant (#627).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — covenant and plugin-root inject are structural; charter-aware compaction preserve
  directives are capability-gap until the host offers native charter steering.

#### A7 — Version-skew guard

- **Component.** Plugin-version skew detector appended to seat-map degradations; K2 retires it with
  trigger to rebuild at the front door when a real skew incident recurs.
- **Condition.** Citation-based, 45 days: real skew-incident receipts (the K2 rebuild trigger). On
  firing, a rebuild proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** capability-gap — detection-only record with zero recorded firings; the motivating
  incident (#675) predates the module and was fixed by other means.

#### B1 — Launcher + launch ledger (declare-batch/launch/record-outcome/amend)

- **Component.** Headless launcher, launch ledger, doctrine, and build-lane stamp that walk preflight,
  reserve, spawn, and outcome recording for unattended waves; it costs ledger I/O and detached-spawn
  plumbing on every batch.
- **Condition.** Usage-based, 60 days: unattended launch batches that reach a stamped ledger outcome
  via launcher verbs. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — load-bearing spine for declare-batch, launch, record-outcome, and amend;
  wave_watch and heartbeat read the ledger it writes.

#### B2 — wave_watch (loop watcher + re-arm doctrine)

- **Component.** Ledger-driven batch watcher and loop re-arm doctrine with its reference doc; it
  costs polling, gh child spawns, and advisor attention per armed batch.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts citing a
  wave_watch qualifying event that drove advisor action. On firing, a proposal to the owner at a
  gardening pass.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** harness-limit — the host offers no native batch watcher; auto-re-arm redesign is queued
  at the front door while the silent-death class it targets still recurs in field evidence.

#### B3 — Heartbeat

- **Component.** Semantic builder heartbeat stamp and advisor sweep classifier; a false `fresh` answer
  is the dangerous failure mode, and every lane carries periodic stamp overhead.
- **Condition.** Catch-based, 45 days: heartbeat sweep classifications of `stale` or `terminal` that
  drove advisor or wave_watch action. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Classified six stalled lanes in one advisor sweep (cp2-scoreboards).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — fail-closed liveness signal for unattended builders; a low catch count means
  builders are finishing, not that wedged lanes stopped happening.

#### B4 — Seat canary (planted-defect control probe)

- **Component.** Planted-defect control probe that dispatches a known-bad fixture through the real
  seat path and scores engagement and plant detection; each run costs a full seat dispatch.
- **Condition.** Catch-based, 45 days: canary runs where engagement or plant-detection axes scored a
  miss. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Tripwire scored seven correct fires in one wave (cp2-scoreboards).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** capability-gap — measures whether review seats investigate and name planted defects;
  evidence observed on the real dispatch path (#668).

#### B6 — File lock + store family

- **Component.** Substrate row: `file_lock`, `store_core`, `store_sweep`, and test-pilot-only
  `store.py` guard concurrent engine applies and project-store writes; proposals on this row are
  shrink or split, not row deletion.
- **Condition.** Usage-based, 60 days: consuming acts that acquire `file_lock` or write through the
  store family (engine dispatch, calibration, test-pilot). On firing, a shrink proposal to the owner
  at a gardening pass.
- **Last demonstrated benefit.** Foreign-host reclaim and tri-state `same_boot` doctrine settled a
  permanent-wedge defect class (#953).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — load-bearing substrate for parallel worktree agents and store I/O; shrink
  targets members, not the row's existence.
