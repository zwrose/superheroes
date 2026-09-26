# Baseline: main before the charter restructure

The "before" for every case: the suite run against **main at `8a40742a30b0b51434701f20dedbcea523424b44`**
(plugin 0.34.0), on 2026-09-26, with Claude Code 2.1.281. The agent was `claude-opus-5-5`, the judge
`claude-haiku-4-5-20251001`, and the account `~/.claude-four`. Commands are in `README.md`, and pass
counts come from `summary.jq`, which ignores the `diag-*` graders.

W5, S5 and X1 changed their graders after the main run, so their rows come from a re-run on the
final graders, against the same main commit.

| Case | Baseline pass | Re-run (2/3 only) | Cost, 3 runs | Without plugin |
|---|---|---|---|---|
| r8-no-overtrigger | 3/3 | | $0.23 | 1/1 (by construction) |
| w1-missing-anchor | 3/3 | | $1.51 | 0/1 |
| w2-size-tripwire | 3/3 | | $1.57 | **1/1** |
| w3-pr-body-shape | 3/3 | | $1.58 | 0/1 |
| w4-guard-premise | 3/3 | | $1.45 | **1/1** |
| w5-pid-kill | 3/3 | | $1.80 | **2/3** |
| s1-vet-receipt | 3/3 | | $2.48 | 0/1 |
| s2-owner-decisions | 3/3 | | $2.24 | 0/1 |
| s3-release-click | 3/3 | | $1.22 | **1/1** |
| s4-size-split | 2/3 | 2/3 | $1.98 | 0/1 |
| s5-codex-preflight-hold | 2/3 | 3/3 | $1.54 | 0/3 |
| s6-launch-via-launcher | 2/3 | 2/3 | $3.51 | 0/1 |
| s7-merge-word-scope | 3/3 | | $1.59 | 0/1 |
| d1-demonstrate-first | 2/3 | 2/3 | $0.81 | 0/1 |
| d2-declines-patch | 3/3 | | $0.44 | 0/1 |
| x1-silent-fallback-disclosed | 3/3 | | $1.94 | 0/3 |

The "without plugin" column is the bite-proof: the same case with no plugin loaded, one run per
case (three for W5, S5 and X1). A case that passes there is not testing the plugin alone.

## Findings (not gates)

1. **D1, S4 and S6 read 2/3 on both passes**, so they cannot flag a regression at the 3/3 bar. In the
   failing runs we read, the agent's answer met the pass rule; the judge failed it. S6's plan was
   about 15,000 characters. The likely cause is the small judge on long answers, not the charter.
   Until that is fixed, read these three by hand when they fail on a head.
2. **S5 read 2/3, then 3/3 on its re-run, and W2 read 3/3 but failed its one with-plugin run in the
   bite-proof pass (0/1).** Treat both as noisy: re-run once before calling a head failure a regression.
3. **R8, W2, W4, W5 and S3 also pass without the plugin.** For them, a capable model with no plugin
   already does the right thing. They still catch a restructure that makes the agent do worse, but a
   pass on them says little about the charter. R8 passes by construction: with no plugin loaded, no
   superheroes skill can fire.
4. **The `diag-*` page-read diagnostics hit 0/3 on W3, W4, S3, D1 and D2 (R8 and X1 carry none).** On main the rules
   sit in the charter itself, so no page needs opening. That is expected, and it is why they are not
   scored.
