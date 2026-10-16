#!/usr/bin/env bash
# Re-run the whole showrunner-charter-trim A/B battery.
# Usage: run.sh [BASE_WORKTREE] [TRIM_WORKTREE]   (defaults: ../ab-base, ../ab-trim next to this dir)
# Env: REPLICATES (default 3) seats per side per scenario.
#      FORCE=1 re-runs every seat and judge call instead of resuming finished outputs.
set -euo pipefail
AB="$(cd "$(dirname "$0")" && pwd)"
BASE="${1:-$AB/../ab-base}"
TRIM="${2:-$AB/../ab-trim}"
REPLICATES="${REPLICATES:-3}"
FORCE_FLAG=()
[[ "${FORCE:-0}" == "1" ]] && FORCE_FLAG=(--force)
COMMON=(--ab "$AB" --base "$BASE" --trim "$TRIM" --replicates "$REPLICATES")

stamp() { date -u +%s; }
fmt() { echo "$(( $1 / 60 )) min $(( $1 % 60 )) s"; }

t0=$(stamp)
python3 -I "$AB/ab.py" seats "${COMMON[@]}" --jobs 4 ${FORCE_FLAG[@]+"${FORCE_FLAG[@]}"}
t1=$(stamp)
python3 -I "$AB/ab.py" judge "${COMMON[@]}" --judge-jobs 3 ${FORCE_FLAG[@]+"${FORCE_FLAG[@]}"}
t2=$(stamp)
echo "- run.sh invocation $(date -u -r "$t0" +%Y-%m-%dT%H:%MZ): seats $(fmt $((t1 - t0))), judge $(fmt $((t2 - t1))) (stages resume, so outputs already present are skipped)" >> "$AB/walltime.txt"
python3 -I "$AB/ab.py" report "${COMMON[@]}"
