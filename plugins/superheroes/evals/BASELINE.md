# Baseline: main before the charter restructure

The "before" for every case: the suite run against **main at `8a40742a30b0b51434701f20dedbcea523424b44`**
(plugin 0.34.0), on 2026-09-26, with Claude Code 2.1.281. The agent and the judge were both
`claude-opus-5-5`, and the account was `~/.claude-three`. Commands are in `README.md`. Pass counts come
from `summary.jq`, which ignores the `diag-*` graders.

X1's grader changed after the main run, so its row comes from a run on the final grader, against the
same main commit. A case that read 2/3 got one re-run of 3. W5's re-run is the with-plugin arm of its
no-plugin pass.

| Case | Baseline pass | Re-run (2/3 only) | Cost, 3 runs | Without plugin |
|---|---|---|---|---|
| r8-no-overtrigger | 3/3 | | $0.29 | 1/1 (by construction) |
| w1-missing-anchor | 3/3 | | $1.51 | 0/1 |
| w2-size-tripwire | 3/3 | | $1.76 | 0/1 |
| w3-pr-body-shape | 3/3 | | $1.64 | 0/1 |
| w4-guard-premise | 3/3 | | $1.74 | **1/1** |
| w5-pid-kill | 2/3 | 3/3 | $1.97 | 0/3 |
| s1-vet-receipt | 3/3 | | $2.53 | 0/1 |
| s2-owner-decisions | 2/3 | **1/3** | $2.48 | 0/1 |
| s3-release-click | 3/3 | | $1.26 | **1/1** |
| s4-size-split | 3/3 | | $2.14 | 0/1 |
| s5-codex-preflight-hold | 3/3 | | $1.48 | 0/3 |
| s6-launch-via-launcher | 3/3 | | $3.58 | 0/1 |
| s7-merge-word-scope | 3/3 | | $1.70 | 0/1 |
| d1-demonstrate-first | 3/3 | | $1.04 | 0/1 |
| d2-declines-patch | 3/3 | | $0.52 | 0/1 |
| x1-silent-fallback-disclosed | 2/3 | **1/3** | $2.36 | 0/3 |

Cost is the agent's cost only. The Opus judge added about $0.05 per run: $2.19 across the 48 runs of
the main pass.

The "without plugin" column is the bite-proof: the same case with no plugin loaded, one run per
case (three for W5, S5 and X1). A case that passes there is not testing the plugin alone.

## Findings (not gates)

1. **13 cases can gate a head at the 3/3 bar:** R8, W1–W4, S1, S3–S7, D1 and D2. **D1, S4 and S6 now
   read 3/3.** Under the earlier small judge they read 2/3 twice, and the failures traced to the judge.
   With the Opus judge that noise is gone.
2. **W5 read 2/3, then 3/3 on its re-run, so it is not among the 13.** Under the 3/3 rule it cannot
   gate a head. If W5 fails on a head, re-run it and read the failing answers by hand before
   concluding anything.
3. **S2 and X1 cannot gate.** S2 read 2/3, then 1/3, and its with-plugin run in the no-plugin pass
   also failed. The Opus judge fails the walk's item template and batch shape on main, so treat S2
   as a hand-read case until that is understood. X1 read 2/3, then 1/3. In all three failing runs
   the owner half described the seat only in plain words ("the deep, adversarial reviewer"), without
   the `codex-deep` id. In one of them the build-record bullet also said "the deep seat" without the
   id. The pass rule needs the id in both places, so these are misses against the rule on main, not
   judge noise.
4. **R8, W4 and S3 also pass without the plugin.** For them, a capable model with no plugin already
   does the right thing. They still catch a restructure that makes the agent do worse, but a pass on
   them says little about the charter. R8 passes by construction: with no plugin loaded, no
   superheroes skill can fire. W2 no longer passes without the plugin (0/1 here, 1/1 before).
5. **The `diag-*` page-read diagnostics hit 0/3 on W1, W3, W4, W5, S3, D1 and D2 in the main pass (R8
   and X1 carry none; W5 hit 2/3 on its re-run).** On main the rules sit in the charter itself, so no
   page needs opening. That is expected, and it is
   why they are not scored.
