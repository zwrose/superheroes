# Recorded charter A/B results

One line per results file. To record a new run, copy its `results.md` here under a dated name and add a line.

- `c11-2026-10-16-before-fix.md` — C11 showrunner-charter trim run, before the scoring-key fix; produced by the seed version of the eval (commit `3f09b5dd` on `advisor/charter-ab-seed`, sides named BASE/TRIM there), before this port.
- `c11-2026-10-16.md` — C11 showrunner-charter trim run, after the scoring-key fix (the verdict of record); produced by the seed version of the eval (commit `3f09b5dd` on `advisor/charter-ab-seed`, sides named BASE/TRIM there), before this port.
- `c11-final-2026-10-16-0435146d-measured.md` — Produced by this port at commit `e7545eb6`: BASE `06269f3d` vs CANDIDATE `0435146d` (C11 with the duty-5 pointer), each seat bound to its own side's plugin with `--plugin-dir`. Verdict as measured: FAIL on s04, under s04's original scoring key.
- `c11-final-2026-10-16-0435146d-s04-rejudged.md` — The same run's answers, re-judged after the advisor's ruling amended s04's key on 2026-10-16 (the `key_change` field discloses it); only s04 was re-judged, so the prompt-hash binding re-ran just that scenario. The run dir's identity was moved to the amended scenarios file by hand, as disclosed in the PR record. Verdict: PASS (the verdict of record for this pair).
- `c11-final-2026-10-16-10b34946-measured.md` — Produced by this port at commit `e7545eb6`: BASE `06269f3d` vs CANDIDATE `10b34946` (C11 trim without the pointer), plugin-bound seats. Verdict: PASS, with s10 3/3 on both sides; this corrects the seed-era s10 FAIL, whose seats read the installed plugin's reference files, not the side's.
