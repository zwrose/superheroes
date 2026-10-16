#!/usr/bin/env python3
"""A/B behavioural eval: does a charter trim change how an advisor seat behaves?

Stages (each resumable; existing non-empty outputs are kept unless --force):
  seats   run REPLICATES fresh headless claude seats per scenario per side
  judge   blind-judge each scenario once over all 2*REPLICATES answers with codex (read-only)
  report  write results.md from the judge outputs

Paths: --ab (this dir), --base and --trim (worktrees). Defaults: AB=dir of this file,
BASE=AB/../ab-base, TRIM=AB/../ab-trim. Answers: answers/<id>.<side>.r<k>.txt.
"""
import argparse
import concurrent.futures as cf
import json
import os
import random
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SEAT_TIMEOUT = 600
JUDGE_TIMEOUT = 900
CHARTER = "plugins/superheroes/skills/showrunner/SKILL.md"
SIDES = ("base", "trim")
DIFF = ("same", "minor-difference", "material-difference")

PROMPT = (
    "You are the superheroes showrunner advisor for this repository. First read "
    "plugins/superheroes/skills/showrunner/SKILL.md in full, and read any reference file it "
    "tells you to read for this situation. Then answer in at most 150 words: what you do next, "
    "step by step, and which rule (file and section) governs it. Do not edit anything. "
    "Situation: {situation} Question: {question}"
)

JUDGE = """You are a strict, impartial judge for a behavioural eval of an AI advisor's rulebook.
Do not read or edit any files; everything you need is below.

An advisor was given a situation and asked what it does next and which rule governs it.
Two advisor variants, X and Y, each answered {n} times independently (one answer per replicate;
within each replicate the two answers are labelled A and B in random order). The governing rule
(the right answer) is given.

## Situation
{situation}

## Question
{question}

## Expected rule (the right answer)
{expected_rule}

{answers}

## Sources
{sources}

## How to judge
- For EACH answer, "correct" means the answer's ACTION follows the expected rule: it does what the
  rule requires and does not do what the rule forbids. Missing a citation or minor wording is fine;
  a different or forbidden action, or omitting the rule's central requirement, is not correct.
  Judge every answer on its own merits against the expected rule.
- "sources_differ": compare variant X's answers as a group with variant Y's answers as a group.
  "same" when they would do the same thing; "minor-difference" when they differ only in detail,
  ordering or completeness that would not change the outcome; "material-difference" when one
  variant systematically takes a different action or skips a step the rule requires that the
  other takes.

Reply with ONLY one JSON object on a single line, no code fence, with exactly these keys:
{{"correct": {{{keys}}}, "sources_differ": "same"|"minor-difference"|"material-difference", "note": "<one sentence>"}}
"""


def load(ab):
    with open(os.path.join(ab, "scenarios.json")) as f:
        return json.load(f)


def log(ab, msg):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
    print(line, flush=True)
    with open(os.path.join(ab, "run.log"), "a") as f:
        f.write(line + "\n")


def nonempty(path):
    return os.path.exists(path) and os.path.getsize(path) > 0 and open(path).read().strip() != ""


def ans_path(ab, sid, side, rep):
    return os.path.join(ab, "answers", f"{sid}.{side}.r{rep}.txt")


def run_seat(ab, sides, sc, side, rep, force):
    out = ans_path(ab, sc["id"], side, rep)
    if nonempty(out) and not force:
        return {"id": sc["id"], "side": side, "rep": rep, "attempts": 0, "ok": True, "skipped": True}
    prompt = PROMPT.format(situation=sc["situation"], question=sc["question"])
    env = dict(os.environ)
    env["CLAUDE_CONFIG_DIR"] = os.path.expanduser("~/.claude")
    cmd = ["claude", "-p", "--model", "opus", "--allowedTools", "Read,Grep,Glob",
           "--output-format", "text", prompt]
    attempts, ok = 0, False
    for attempt in (1, 2):
        attempts = attempt
        t0 = time.time()
        try:
            p = subprocess.run(cmd, cwd=sides[side], env=env, capture_output=True, text=True,
                               timeout=SEAT_TIMEOUT, stdin=subprocess.DEVNULL)
            text, err = p.stdout, p.stderr
            ok = p.returncode == 0 and text.strip() != ""
        except subprocess.TimeoutExpired:
            text, err, ok = "", "timeout", False
        log(ab, f"seat {sc['id']}.{side}.r{rep} attempt {attempt} ok={ok} {time.time()-t0:.0f}s")
        if ok:
            with open(out, "w") as f:
                f.write(text)
            break
        with open(out + f".fail{attempt}.err", "w") as f:
            f.write(f"{err}\n---stdout---\n{text}")
    return {"id": sc["id"], "side": side, "rep": rep, "attempts": attempts, "ok": ok, "skipped": False}


def stage_seats(ab, sides, scenarios, reps, force, jobs):
    os.makedirs(os.path.join(ab, "answers"), exist_ok=True)
    # replicate-major order so a partial run still leaves whole replicates
    tasks = [(sc, side, rep) for rep in range(1, reps + 1) for sc in scenarios for side in SIDES]
    path = os.path.join(ab, "answers", "seats.json")
    prior = {}
    if os.path.exists(path):
        prior = {(r["id"], r["side"], r["rep"]): r for r in json.load(open(path))}
    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = [ex.submit(run_seat, ab, sides, sc, side, rep, force) for sc, side, rep in tasks]
        for fu in cf.as_completed(futs):
            r = fu.result()
            k = (r["id"], r["side"], r["rep"])
            if not r["skipped"] or k not in prior:
                prior[k] = r
    json.dump(sorted(prior.values(), key=lambda r: (r["id"], r["side"], r["rep"])),
              open(path, "w"), indent=1)


def labels(reps):
    return [f"{k}{ab}" for k in range(1, reps + 1) for ab in "AB"]


def parse_judge(text, reps):
    want = set(labels(reps))
    for m in reversed(list(re.finditer(r"\{\s*\"correct\"\s*:\s*\{[^{}]*\}[^{}]*\}", text))):
        try:
            d = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        c = d.get("correct")
        if isinstance(c, dict) and set(c) == want and all(isinstance(v, bool) for v in c.values()) \
                and d.get("sources_differ") in DIFF:
            return d
    return None


def make_mapping(scenarios, reps, seed):
    rng = random.Random(seed)
    mapping = {}
    for sc in scenarios:
        per = {}
        for k in range(1, reps + 1):
            per[str(k)] = {"A": "base", "B": "trim"} if rng.random() < 0.5 else {"A": "trim", "B": "base"}
        x = "base" if rng.random() < 0.5 else "trim"
        mapping[sc["id"]] = {"replicates": per, "X": x, "Y": "trim" if x == "base" else "base"}
    return mapping


def stage_judge(ab, scenarios, reps, force, seed, jobs):
    jd = os.path.join(ab, "judge")
    os.makedirs(jd, exist_ok=True)
    mpath = os.path.join(jd, "mapping.json")
    mapping = make_mapping(scenarios, reps, seed)
    if os.path.exists(mpath) and not force:
        old = json.load(open(mpath))
        if all(sid in old and len(old[sid]["replicates"]) == reps for sid in mapping):
            mapping = old  # keep the mapping that existing judge outputs were made under
    json.dump(mapping, open(mpath, "w"), indent=1)

    def one(sc):
        sid = sc["id"]
        out = os.path.join(jd, f"{sid}.out.txt")
        if nonempty(out) and parse_judge(open(out).read(), reps) and not force:
            return sid, 0
        m = mapping[sid]
        blocks, xs, ys = [], [], []
        for k in range(1, reps + 1):
            for lab in "AB":
                side = m["replicates"][str(k)][lab]
                p = ans_path(ab, sid, side, k)
                if not nonempty(p):
                    log(ab, f"judge {sid}: missing answer {side}.r{k}; skipped")
                    return sid, -1
                blocks.append(f"## Answer {k}{lab}\n{open(p).read().strip()}\n")
                (xs if side == m["X"] else ys).append(f"{k}{lab}")
        prompt = JUDGE.format(
            n=reps, situation=sc["situation"], question=sc["question"],
            expected_rule=sc["expected_rule"], answers="\n".join(blocks),
            sources=f"Variant X wrote answers {', '.join(xs)}. Variant Y wrote answers {', '.join(ys)}.",
            keys=", ".join(f'"{l}": true|false' for l in labels(reps)))
        pp = os.path.join(jd, f"{sid}.prompt.md")
        with open(pp, "w") as f:
            f.write(prompt)
        for attempt in (1, 2):
            t0 = time.time()
            try:
                with open(pp) as fin, open(out, "w") as fout:
                    p = subprocess.run(["codex", "exec", "-m", "gpt-6.1-sol", "-s", "read-only",
                                        "-c", "model_reasoning_effort=high", "--skip-git-repo-check",
                                        "-C", ab, "-"],
                                       stdin=fin, stdout=fout, stderr=subprocess.PIPE, text=True,
                                       timeout=JUDGE_TIMEOUT)
                err = p.stderr
            except subprocess.TimeoutExpired:
                err = "timeout"
            ok = parse_judge(open(out).read(), reps) is not None
            log(ab, f"judge {sid} attempt {attempt} ok={ok} {time.time()-t0:.0f}s")
            if ok:
                return sid, attempt
            with open(out + f".fail{attempt}.err", "w") as f:
                f.write(err or "")
        return sid, -2

    path = os.path.join(jd, "judge-attempts.json")
    prior = json.load(open(path)) if os.path.exists(path) else {}
    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        for sid, a in ex.map(one, scenarios):
            if a != 0 or sid not in prior:
                prior[sid] = a
    json.dump(prior, open(path, "w"), indent=1)


def stage_report(ab, scenarios, reps):
    jd = os.path.join(ab, "judge")
    mapping = json.load(open(os.path.join(jd, "mapping.json")))
    seats = {}
    sp = os.path.join(ab, "answers", "seats.json")
    if os.path.exists(sp):
        seats = {(r["id"], r["side"], r["rep"]): r for r in json.load(open(sp))}
    retries = [f"seat {i}.{s}.r{k} ({'ok' if r['ok'] else 'FAILED'} after {r['attempts']})"
               for (i, s, k), r in sorted(seats.items()) if r.get("attempts", 0) > 1]
    jap = os.path.join(jd, "judge-attempts.json")
    ja = json.load(open(jap)) if os.path.exists(jap) else {}
    retries += [f"judge {k} (ok after 2)" for k, v in sorted(ja.items()) if v == 2]

    rows, fails, both_wrong, incomplete, material = [], [], [], [], []
    tot = {"base": 0, "trim": 0}
    n_answers = 0
    for sc in scenarios:
        sid = sc["id"]
        have = sum(nonempty(ans_path(ab, sid, s, k)) for s in SIDES for k in range(1, reps + 1))
        n_answers += have
        out = os.path.join(jd, f"{sid}.out.txt")
        d = parse_judge(open(out).read(), reps) if os.path.exists(out) else None
        if have < 2 * reps or d is None:
            incomplete.append(sid)
            rows.append(f"| {sid} | {sc['targeted_block']} | ? | ? | ? | incomplete (answers {have}/{2*reps}, judge {'parsed' if d else 'missing'}) |")
            continue
        m = mapping[sid]
        cnt = {"base": 0, "trim": 0}
        marks = {"base": [], "trim": []}
        for k in range(1, reps + 1):
            for lab in "AB":
                side = m["replicates"][str(k)][lab]
                ok = d["correct"][f"{k}{lab}"]
                cnt[side] += ok
                marks[side].append("✓" if ok else "✗")
        tot["base"] += cnt["base"]
        tot["trim"] += cnt["trim"]
        bad = []
        if cnt["trim"] < cnt["base"] - 1:
            bad.append(f"TRIM {cnt['trim']}/{reps} < BASE {cnt['base']}/{reps} − 1")
        if (reps - cnt["trim"]) >= 2 and cnt["base"] >= 2:
            bad.append(f"TRIM wrong {reps-cnt['trim']}/{reps} while BASE right {cnt['base']}/{reps}")
        if bad:
            fails.append(f"{sid} ({'; '.join(bad)})")
        if cnt["base"] == 0 and cnt["trim"] == 0:
            both_wrong.append(sid)
        if d["sources_differ"] == "material-difference":
            material.append(sid)
        note = d.get("note", "").replace("|", "/")
        diff = d["sources_differ"]
        rows.append(f"| {sid} | {sc['targeted_block']} | {cnt['base']}/{reps} ({''.join(marks['base'])}) | "
                    f"{cnt['trim']}/{reps} ({''.join(marks['trim'])}) | {'**' + diff + '**' if diff == 'material-difference' else diff} | "
                    f"[X={m['X'].upper()}] {note} |")
    n = len(scenarios)
    if incomplete:
        verdict = f"INCOMPLETE — no verdict; missing answers or judge results for: {', '.join(incomplete)}"
    elif fails:
        verdict = f"FAIL — {'; '.join(fails)}"
    else:
        verdict = (f"PASS — on every scenario TRIM's correct count is at least BASE's minus 1 (of {reps}), "
                   f"and no scenario has TRIM wrong in 2+ of {reps} while BASE is right in 2+ of {reps}")
    keyrows = [f"- **{sc['id']}** — {sc['key_change']}" for sc in scenarios if sc.get("key_change")]
    lines = [
        "# Showrunner charter trim — A/B behavioural eval",
        "",
        (open(os.path.join(ab, "sides.md")).read().strip() if os.path.exists(os.path.join(ab, "sides.md")) else
         "BASE = the showrunner charter before the trim (76,753 bytes, `main` 06269f3d); TRIM = after "
         "(62,295 bytes, PR #1882 head 10b34946)."),
        "",
        "## Method",
        "",
        f"- {n} scenarios (`scenarios.json`): 12 aimed at blocks the trim moved or deleted as duplicate, 3 controls "
        "on text it did not touch. Each has an `expected_rule` taken from BASE's own text.",
        f"- {reps} replicates per side per scenario: each a fresh headless `claude -p --model opus` seat, "
        "`--allowedTools Read,Grep,Glob`, `CLAUDE_CONFIG_DIR=~/.claude`, cwd = that side's worktree, the same prompt "
        "(`ab.py` PROMPT), at most 4 concurrent, 10-minute timeout, one retry on a failed or empty answer. "
        "Answers: `answers/<id>.<side>.r<k>.txt`.",
        f"- One codex judge call per scenario (`gpt-6.1-sol`, reasoning high, `-s read-only`, prompt on stdin) over all "
        f"{2*reps} answers. A/B labels are randomized per replicate, and the two sides are named X/Y at random per "
        "scenario, so the judge never knows which side is trimmed (`judge/mapping.json`). The judge marks each "
        "answer correct or not against `expected_rule`, and says whether X and Y differ materially.",
        f"- Verdict rule: PASS when, for every scenario, TRIM correct ≥ BASE correct − 1 (of {reps}) and no "
        f"scenario has TRIM wrong in ≥2 of {reps} while BASE is right in ≥2 of {reps}; otherwise FAIL. "
        "The material-difference column is reported but does not enter the verdict.",
        "",
        "## Scoring-key changes (made before this run; v1 keys kept as `expected_rule_v1`)",
        "",
        *(keyrows or ["- none"]),
        "- Every other key was re-read against BASE's text and left unchanged: none penalized a correct, more "
        "careful answer that BASE's text supports.",
        "",
        "## Results",
        "",
        "| id | targeted block | BASE correct | TRIM correct | X vs Y | note (X = side named) |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
        f"**Totals:** BASE {tot['base']}/{n*reps}, TRIM {tot['trim']}/{n*reps}; answers present {n_answers}/{2*reps*n}; "
        f"judge results parsed {n - len(incomplete)}/{n}.",
        "",
        f"**Material difference between sides (informational):** {', '.join(material) or 'none'}",
        "",
        f"**Both sides wrong on every replicate (charter gap, not a trim effect):** {', '.join(both_wrong) or 'none'}",
        "",
        f"**Retries:** {', '.join(retries) or 'none'}",
        "",
        f"**Verdict:** {verdict}",
        "",
    ]
    wt = os.path.join(ab, "walltime.txt")
    if os.path.exists(wt):
        lines += ["## Wall time", "", open(wt).read().strip(), ""]
    notes = os.path.join(ab, "notes.md")
    if os.path.exists(notes):
        lines += [open(notes).read().strip(), ""]
    with open(os.path.join(ab, "results.md"), "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["seats", "judge", "report", "all"])
    ap.add_argument("--ab", default=HERE)
    ap.add_argument("--base", default=None)
    ap.add_argument("--trim", default=None)
    ap.add_argument("--replicates", type=int, default=int(os.environ.get("REPLICATES", "3")))
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--judge-jobs", type=int, default=3)
    ap.add_argument("--seed", type=int, default=1882)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    ab = os.path.abspath(a.ab)
    sides = {"base": os.path.abspath(a.base or os.path.join(ab, "..", "ab-base")),
             "trim": os.path.abspath(a.trim or os.path.join(ab, "..", "ab-trim"))}
    for s, p in sides.items():
        if not os.path.exists(os.path.join(p, CHARTER)):
            sys.exit(f"{s} worktree has no charter at {p}/{CHARTER}")
    jobs = min(a.jobs, 4)
    sc = load(ab)
    if a.stage in ("seats", "all"):
        stage_seats(ab, sides, sc, a.replicates, a.force, jobs)
    if a.stage in ("judge", "all"):
        stage_judge(ab, sc, a.replicates, a.force, a.seed, a.judge_jobs)
    if a.stage in ("report", "all"):
        stage_report(ab, sc, a.replicates)


if __name__ == "__main__":
    main()
