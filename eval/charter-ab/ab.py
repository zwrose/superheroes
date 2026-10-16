#!/usr/bin/env python3
"""A/B behavioural eval: does a charter change alter how the seat it governs behaves?

Stages (each resumable; existing non-empty outputs are kept unless --force):
  seats   run REPLICATES fresh headless claude seats per scenario per side, each in a throwaway
          git worktree of the BASE and CANDIDATE commits
  judge   blind-judge each scenario once over all 2*REPLICATES answers with codex (read-only)
  report  write results.md and verdict.json from the answers and judge outputs
  run     seats, judge, report in one go (records wall time per stage in walltime.txt)

Exit codes: 0 PASS, 1 FAIL, 2 INCOMPLETE (report/run); 3 refusal; seats/judge alone exit 0.

Everything the eval writes goes into the run dir (outside the repo). The run dir's sides.json is
the run identity: a later stage that disagrees with it (other commit, model, replicate count,
scenarios, ...) is refused rather than mixed in. Answers: answers/<id>.<side>.r<k>.txt.
Python >= 3.9, standard library only.
"""
import argparse
import concurrent.futures as cf
import contextlib
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SEAT_TIMEOUT = 600
JUDGE_TIMEOUT = 900
DEFAULT_CHARTER = "plugins/superheroes/skills/showrunner/SKILL.md"
DEFAULT_SCENARIOS = os.path.join(HERE, "scenarios", "showrunner.json")
DEFAULT_ROLE = "the seat this charter governs"
SIDES = ("base", "candidate")
DIFF = ("same", "minor-difference", "material-difference")
REQUIRED_FIELDS = ("id", "situation", "question", "expected_rule", "targeted_block")
IDENTITY_KEYS = ("base_ref", "base_sha", "candidate_ref", "candidate_sha", "charter", "scenarios_file",
                 "scenarios_sha256", "role", "model", "judge_model", "replicates", "seed")
UNGUARDED_KEYS = ("base_ref", "candidate_ref", "scenarios_file")  # names/paths only; the SHAs and hashes guard
EXIT_BY_VERDICT = {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2}
EXIT_REFUSED = 3

PROMPT = (
    "You are {role} for this repository. First read "
    "{charter} in full, and read any reference file it "
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

_LOG_LOCK = threading.Lock()


class Refusal(Exception):
    """A guard fired: the eval refuses to run (exit 3) rather than produce a mixed or unsafe result."""


# ---------------------------------------------------------------- pure functions

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
        # bites on: judge output with a missing/extra label or non-bool value must not count as a result
        if isinstance(c, dict) and set(c) == want and all(isinstance(v, bool) for v in c.values()) \
                and d.get("sources_differ") in DIFF:
            return d
    return None


def make_mapping(scenario_ids, reps, seed):
    rng = random.Random(seed)
    mapping = {}
    for sid in scenario_ids:
        per = {}
        for k in range(1, reps + 1):
            per[str(k)] = {"A": "base", "B": "candidate"} if rng.random() < 0.5 else {"A": "candidate", "B": "base"}
        x = "base" if rng.random() < 0.5 else "candidate"
        mapping[sid] = {"replicates": per, "X": x, "Y": "candidate" if x == "base" else "base"}
    return mapping


def unmap(mapping_entry, judged_correct, reps):
    """Per-side correctness lists (ordered by replicate) from one scenario's A/B-labelled judgement."""
    if not isinstance(judged_correct, dict) or set(judged_correct) != set(labels(reps)):
        raise ValueError(f"judged labels must be exactly {labels(reps)}")
    out = {s: [] for s in SIDES}
    for k in range(1, reps + 1):
        ab = mapping_entry["replicates"][str(k)]
        if sorted(ab.get(lab) for lab in "AB") != sorted(SIDES):
            raise ValueError(f"replicate {k} must map A and B to different sides")
        for lab in "AB":
            out[ab[lab]].append(bool(judged_correct[f"{k}{lab}"]))
    return out


def scenario_flags(base_correct, cand_correct, reps):
    """One human-readable string per failed test; an empty list means the scenario passes."""
    flags = []
    # bites on: a candidate that is worse than base by 2 or more correct answers must fail
    if cand_correct < base_correct - 1:
        flags.append(f"CANDIDATE {cand_correct}/{reps} < BASE {base_correct}/{reps} − 1")
    # bites on: candidate wrong in 2+ replicates while base is right in 2+ must fail even within the minus-1 bound
    if (reps - cand_correct) >= 2 and base_correct >= 2:
        flags.append(f"CANDIDATE wrong {reps - cand_correct}/{reps} while BASE right {base_correct}/{reps}")
    return flags


def verdict(per_scenario, reps):
    """The single chokepoint for the verdict: PASS only when every scenario is complete and unflagged."""
    incomplete, failing, both_wrong = [], [], []
    for s in per_scenario:
        done = s.get("complete") and isinstance(s.get("base"), int) and isinstance(s.get("candidate"), int)
        if not done:
            incomplete.append(s["id"])
            continue
        reasons = scenario_flags(s["base"], s["candidate"], reps)
        if reasons:
            failing.append({"id": s["id"], "reasons": reasons})
        if s["base"] == 0 and s["candidate"] == 0:
            both_wrong.append(s["id"])
    # bites on: an incomplete scenario, or no scenarios at all, must never be reported as PASS or FAIL
    if incomplete or not per_scenario:
        v = "INCOMPLETE"
    elif failing:
        v = "FAIL"
    else:
        v = "PASS"
    return {"verdict": v, "failing": failing, "both_wrong": both_wrong, "incomplete": incomplete}


def identity_mismatch(stored, current):
    return [k for k in IDENTITY_KEYS if k not in UNGUARDED_KEYS and stored.get(k) != current.get(k)]


def render_prompt(role, charter, situation, question):
    return PROMPT.format(role=role, charter=charter, situation=situation, question=question)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- small I/O helpers

def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def nonempty(path):
    try:
        return read_text(path).strip() != ""
    except (OSError, UnicodeDecodeError):
        return False


def atomic_write(path, text):
    """Write to a temp file in the same directory, then os.replace: readers never see a partial file."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def log(run_dir, msg):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
    with _LOG_LOCK:
        print(line, flush=True)
        with open(os.path.join(run_dir, "run.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")


def ans_path(run_dir, sid, side, rep):
    return os.path.join(run_dir, "answers", f"{sid}.{side}.r{rep}.txt")


def inside(path, root):
    path, root = os.path.realpath(path), os.path.realpath(root)
    return os.path.commonpath([path, root]) == root


# ---------------------------------------------------------------- git, worktrees

def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


def resolve_repo(arg):
    start = os.path.abspath(arg) if arg else HERE
    p = git(start, "rev-parse", "--show-toplevel")
    if p.returncode != 0 or not p.stdout.strip():
        raise Refusal(f"{start} is not inside a git repository")
    return os.path.realpath(p.stdout.strip())


def rev_parse_commit(repo, ref):
    if not ref or ref.startswith("-"):
        raise Refusal(f"bad ref {ref!r}")
    p = git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
    sha = p.stdout.strip()
    # bites on: a ref that does not resolve to a commit must refuse, never fall through to a guess (E8)
    if p.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise Refusal(f"cannot resolve {ref!r} to a commit in {repo}")
    return sha


def default_base(repo, cand_sha, cand_ref):
    for m in ("main", "origin/main"):
        if git(repo, "rev-parse", "--verify", "--quiet", m + "^{commit}").returncode == 0:
            p = git(repo, "merge-base", m, cand_sha)
            if p.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", p.stdout.strip()):
                raise Refusal(f"no merge-base between {m} and {cand_ref}; pass --base")
            return f"merge-base({m}, {cand_ref})", p.stdout.strip()
    raise Refusal("neither main nor origin/main resolves; pass --base")


@contextlib.contextmanager
def worktrees(repo, shas):
    """Detached worktrees of both commits in a fresh temp dir; always removed, even if the body raises."""
    tmp = tempfile.mkdtemp(prefix="charter-ab-wt-")
    made = []
    try:
        if inside(tmp, repo):
            raise Refusal(f"temp dir {tmp} is inside the repo")
        paths = {}
        for side in SIDES:
            path = os.path.join(tmp, side)
            made.append(path)  # recorded before the add, so a half-made worktree is still removed
            p = git(repo, "worktree", "add", "--detach", path, shas[side])
            if p.returncode != 0:
                raise Refusal(f"git worktree add failed for {side}: {p.stderr.strip()}")
            paths[side] = path
        yield paths
    finally:
        # bites on: a stage that raises must still remove the worktrees it created (E9)
        for path in made:
            git(repo, "worktree", "remove", "--force", path)
        git(repo, "worktree", "prune")
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- scenarios, identity

def load_scenarios(path):
    try:
        with open(path, "rb") as f:
            raw = f.read()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as e:
        raise Refusal(f"cannot read scenarios file {path}: {e}")
    if isinstance(data, list):
        role, scenarios = DEFAULT_ROLE, data
    elif isinstance(data, dict) and isinstance(data.get("scenarios"), list) and isinstance(data.get("role"), str) \
            and data["role"].strip():
        role, scenarios = data["role"], data["scenarios"]
    else:
        raise Refusal(f"{path}: expected a list, or an object with a non-empty string 'role' and a 'scenarios' list")
    seen = set()
    for i, sc in enumerate(scenarios):
        if not isinstance(sc, dict):
            raise Refusal(f"{path}: scenario #{i} is not an object")
        missing = [k for k in REQUIRED_FIELDS if k not in sc]
        if missing:
            raise Refusal(f"{path}: scenario #{i} lacks {', '.join(missing)}")
        if not isinstance(sc["id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", sc["id"]):
            raise Refusal(f"{path}: scenario #{i} has an unusable id {sc['id']!r}")
        if sc["id"] in seen:
            raise Refusal(f"{path}: duplicate scenario id {sc['id']!r}")
        seen.add(sc["id"])
        for k in REQUIRED_FIELDS:
            if not isinstance(sc[k], str):
                raise Refusal(f"{path}: scenario {sc['id']!r} field {k} is not a string")
    return role, scenarios, hashlib.sha256(raw).hexdigest()


def check_charter_path(charter):
    if not charter or os.path.isabs(charter) or ".." in charter.replace("\\", "/").split("/"):
        raise Refusal(f"--charter must be a repo-relative path, got {charter!r}")
    return charter


def read_sides(run_dir):
    path = os.path.join(run_dir, "sides.json")
    if not os.path.exists(path):
        return None
    stored = load_json(path)
    if not isinstance(stored, dict) or any(k not in stored for k in IDENTITY_KEYS):
        raise Refusal(f"{path} is unreadable or lacks identity keys")
    return stored


def build_identity(a, stage, repo, stored):
    """The identity this invocation would run under. seats/run recompute it from the arguments (defaults
    included); report/judge take anything not given explicitly from the stored identity."""
    strict = stage in ("seats", "run")

    def pick(val, key, default):
        if val is not None:
            return val
        return stored[key] if (not strict and stored) else default

    reps = a.replicates
    if reps is None and strict:
        try:
            reps = int(os.environ.get("REPLICATES", "3"))
        except ValueError:
            raise Refusal("env REPLICATES is not an integer")
    reps = pick(reps, "replicates", 3)
    if not isinstance(reps, int) or reps < 1:
        raise Refusal("--replicates must be a positive integer")
    charter = check_charter_path(pick(a.charter, "charter", DEFAULT_CHARTER))
    scen_file = os.path.abspath(a.scenarios or (stored["scenarios_file"] if (not strict and stored)
                                                 else DEFAULT_SCENARIOS))
    role, scenarios, scen_sha = load_scenarios(scen_file)

    if a.candidate:
        cand_ref, cand_sha = a.candidate, rev_parse_commit(repo, a.candidate)
    elif stored:
        cand_ref = stored["candidate_ref"]
        cand_sha = rev_parse_commit(repo, stored["candidate_sha"]) if strict else stored["candidate_sha"]
    else:
        raise Refusal("--candidate is required for the first use of a run dir")
    if a.base:
        base_ref, base_sha = a.base, rev_parse_commit(repo, a.base)
    elif stored:
        base_ref = stored["base_ref"]
        base_sha = rev_parse_commit(repo, stored["base_sha"]) if strict else stored["base_sha"]
    else:
        base_ref, base_sha = default_base(repo, cand_sha, cand_ref)

    ident = {"base_ref": base_ref, "base_sha": base_sha, "candidate_ref": cand_ref, "candidate_sha": cand_sha,
             "charter": charter, "scenarios_file": scen_file, "scenarios_sha256": scen_sha, "role": role,
             "model": pick(a.model, "model", "opus"),
             "judge_model": pick(a.judge_model, "judge_model", "gpt-6.1-sol"),
             "replicates": reps, "seed": pick(a.seed, "seed", 1882)}
    return ident, scenarios


# ---------------------------------------------------------------- seats

def exec_seat(cmd, cwd, env):
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, encoding="utf-8", errors="replace",
                       timeout=SEAT_TIMEOUT, stdin=subprocess.DEVNULL)
    return p.returncode, p.stdout, p.stderr


def run_seat(run_dir, side_dirs, sc, side, rep, force, ident, config_dir):
    out = ans_path(run_dir, sc["id"], side, rep)
    if nonempty(out) and not force:
        return {"id": sc["id"], "side": side, "rep": rep, "attempts": 0, "ok": True, "skipped": True}
    prompt = render_prompt(ident["role"], ident["charter"], sc["situation"], sc["question"])
    env = dict(os.environ)
    env["CLAUDE_CONFIG_DIR"] = config_dir
    cmd = ["claude", "-p", "--model", ident["model"], "--allowedTools", "Read,Grep,Glob",
           "--output-format", "text", prompt]
    attempts, ok = 0, False
    for attempt in (1, 2):
        attempts = attempt
        t0 = time.time()
        try:
            rc, text, err = exec_seat(cmd, side_dirs[side], env)
            # bites on: an answer is published only from a call that exited 0 with non-empty output
            ok = rc == 0 and text.strip() != ""
        except subprocess.TimeoutExpired:
            text, err, ok = "", "timeout", False
        except OSError as e:
            text, err, ok = "", f"could not run claude: {e}", False
        log(run_dir, f"seat {sc['id']}.{side}.r{rep} attempt {attempt} ok={ok} {time.time()-t0:.0f}s")
        if ok:
            atomic_write(out, text)
            break
        with open(out + f".fail{attempt}.err", "w", encoding="utf-8") as f:
            f.write(f"{err}\n---stdout---\n{text}")
    return {"id": sc["id"], "side": side, "rep": rep, "attempts": attempts, "ok": ok, "skipped": False}


def stage_seats(run_dir, side_dirs, scenarios, ident, force, jobs, config_dir):
    reps = ident["replicates"]
    os.makedirs(os.path.join(run_dir, "answers"), exist_ok=True)
    # replicate-major order so a partial run still leaves whole replicates
    tasks = [(sc, side, rep) for rep in range(1, reps + 1) for sc in scenarios for side in SIDES]
    path = os.path.join(run_dir, "answers", "seats.json")
    prior = {}
    if os.path.exists(path):
        prior = {(r["id"], r["side"], r["rep"]): r for r in (load_json(path) or [])}
    with cf.ThreadPoolExecutor(max_workers=max(1, min(jobs, 4))) as ex:
        futs = [ex.submit(run_seat, run_dir, side_dirs, sc, side, rep, force, ident, config_dir)
                for sc, side, rep in tasks]
        for fu in cf.as_completed(futs):
            r = fu.result()
            k = (r["id"], r["side"], r["rep"])
            if not r["skipped"] or k not in prior:
                prior[k] = r
    atomic_write(path, json.dumps(sorted(prior.values(), key=lambda r: (r["id"], r["side"], r["rep"])), indent=1))


# ---------------------------------------------------------------- judge

def render_judge(run_dir, sc, m, reps):
    """The judge prompt for one scenario from the current answers and mapping; None if an answer is missing."""
    blocks, xs, ys = [], [], []
    for k in range(1, reps + 1):
        for lab in "AB":
            side = m["replicates"][str(k)][lab]
            p = ans_path(run_dir, sc["id"], side, k)
            if not nonempty(p):
                return None
            blocks.append(f"## Answer {k}{lab}\n{read_text(p).strip()}\n")
            (xs if side == m["X"] else ys).append(f"{k}{lab}")
    return JUDGE.format(
        n=reps, situation=sc["situation"], question=sc["question"],
        expected_rule=sc["expected_rule"], answers="\n".join(blocks),
        sources=f"Variant X wrote answers {', '.join(xs)}. Variant Y wrote answers {', '.join(ys)}.",
        keys=", ".join(f'"{l}": true|false' for l in labels(reps)))


def judge_paths(run_dir, sid):
    jd = os.path.join(run_dir, "judge")
    return (os.path.join(jd, f"{sid}.out.txt"), os.path.join(jd, f"{sid}.prompt.md"),
            os.path.join(jd, f"{sid}.prompt.sha256"))


def prompt_bound(run_dir, sid, prompt):
    """True only when the stored hash is the hash of exactly this freshly rendered prompt."""
    _, _, shap = judge_paths(run_dir, sid)
    try:
        stored = read_text(shap).strip()
    except (OSError, UnicodeDecodeError):
        return False
    # bites on: a judge result made over different answers than the current ones must not be reused or counted
    return prompt is not None and stored == sha256_text(prompt)


def exec_judge(cmd, prompt):
    p = subprocess.run(cmd, input=prompt, capture_output=True, encoding="utf-8", errors="replace",
                       timeout=JUDGE_TIMEOUT)
    return p.returncode, p.stdout, p.stderr


def stage_judge(run_dir, scenarios, ident, force, jobs):
    reps, seed = ident["replicates"], ident["seed"]
    jd = os.path.join(run_dir, "judge")
    os.makedirs(jd, exist_ok=True)
    mpath = os.path.join(jd, "mapping.json")
    mapping = make_mapping([sc["id"] for sc in scenarios], reps, seed)
    if os.path.exists(mpath) and not force:
        old = load_json(mpath) or {}
        if all(sid in old and len(old[sid]["replicates"]) == reps for sid in mapping):
            mapping = old  # keep the mapping that existing judge outputs were made under
    atomic_write(mpath, json.dumps(mapping, indent=1))
    cmd = ["codex", "exec", "-m", ident["judge_model"], "-s", "read-only", "-c", "model_reasoning_effort=high",
           "--skip-git-repo-check", "-C", run_dir, "-"]

    def one(sc):
        sid = sc["id"]
        out, pp, shap = judge_paths(run_dir, sid)
        prompt = render_judge(run_dir, sc, mapping[sid], reps)
        if prompt is None:
            log(run_dir, f"judge {sid}: missing answer; skipped")
            return sid, -1
        atomic_write(pp, prompt)
        if not force and nonempty(out) and parse_judge(read_text(out), reps) and prompt_bound(run_dir, sid, prompt):
            return sid, 0
        for attempt in (1, 2):
            t0 = time.time()
            try:
                _, text, err = exec_judge(cmd, prompt)
            except subprocess.TimeoutExpired:
                text, err = "", "timeout"
            except OSError as e:
                text, err = "", f"could not run codex: {e}"
            ok = parse_judge(text, reps) is not None
            log(run_dir, f"judge {sid} attempt {attempt} ok={ok} {time.time()-t0:.0f}s")
            if ok:
                atomic_write(out, text)
                atomic_write(shap, sha256_text(prompt))  # written only after the output parsed
                return sid, attempt
            with open(out + f".fail{attempt}.err", "w", encoding="utf-8") as f:
                f.write(f"{err or ''}\n---stdout---\n{text}")
        return sid, -2

    path = os.path.join(jd, "judge-attempts.json")
    prior = load_json(path, {}) if os.path.exists(path) else {}
    with cf.ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        for sid, a in ex.map(one, scenarios):
            if a != 0 or sid not in prior:
                prior[sid] = a
    atomic_write(path, json.dumps(prior, indent=1))


# ---------------------------------------------------------------- completeness, report

def completeness(run_dir, scenarios, mapping, reps):
    """The single completeness check: per scenario, complete only with all 2*reps answers, a judge output
    that parses, and a stored prompt hash equal to the hash of the prompt re-rendered from the current
    answers and mapping."""
    per = []
    for sc in scenarios:
        sid = sc["id"]
        have = sum(nonempty(ans_path(run_dir, sid, s, k)) for s in SIDES for k in range(1, reps + 1))
        out, _, _ = judge_paths(run_dir, sid)
        d = None
        if os.path.exists(out):
            try:
                d = parse_judge(read_text(out), reps)
            except (OSError, UnicodeDecodeError):
                d = None
        m = mapping.get(sid)
        prompt = None
        if m is not None and have == 2 * reps:
            try:
                prompt = render_judge(run_dir, sc, m, reps)
            except (KeyError, TypeError):
                prompt = None
        bound = prompt_bound(run_dir, sid, prompt)
        rec = {"id": sid, "complete": False, "base": None, "candidate": None, "have": have,
               "parsed": d is not None, "bound": bound, "marks": None, "diff": None, "note": "", "X": None}
        if have == 2 * reps and d is not None and bound:
            try:
                per_side = unmap(m, d["correct"], reps)
            except (KeyError, TypeError, ValueError):
                per_side = None
            if per_side is not None:
                rec.update(complete=True, base=sum(per_side["base"]), candidate=sum(per_side["candidate"]),
                           marks={s: "".join("✓" if ok else "✗" for ok in per_side[s]) for s in SIDES},
                           diff=d["sources_differ"], note=str(d.get("note", "")).replace("|", "/"), X=m["X"])
        per.append(rec)
    return per


def stage_report(run_dir, scenarios, ident):
    reps = ident["replicates"]
    jd = os.path.join(run_dir, "judge")
    mapping = load_json(os.path.join(jd, "mapping.json"), {})
    if not isinstance(mapping, dict):
        mapping = {}
    seats = {}
    for r in load_json(os.path.join(run_dir, "answers", "seats.json"), []) or []:
        seats[(r["id"], r["side"], r["rep"])] = r
    retries = [f"seat {i}.{s}.r{k} ({'ok' if r['ok'] else 'FAILED'} after {r['attempts']})"
               for (i, s, k), r in sorted(seats.items()) if r.get("attempts", 0) > 1]
    ja = load_json(os.path.join(jd, "judge-attempts.json"), {}) or {}
    retries += [f"judge {k} (ok after 2)" for k, v in sorted(ja.items()) if v == 2]

    per = completeness(run_dir, scenarios, mapping, reps)
    result = verdict(per, reps)  # the only path to a verdict
    by_id = {p["id"]: p for p in per}
    flagged = {f["id"]: f["reasons"] for f in result["failing"]}

    rows, tot, material = [], {"base": 0, "candidate": 0}, []
    for sc in scenarios:
        p = by_id[sc["id"]]
        if not p["complete"]:
            rows.append(f"| {sc['id']} | {sc['targeted_block']} | ? | ? | ? | incomplete (answers {p['have']}/{2*reps}, "
                        f"judge {'parsed' if p['parsed'] else 'missing or unparsed'}, "
                        f"prompt hash {'bound' if p['bound'] else 'not bound to the current answers'}) |")
            continue
        tot["base"] += p["base"]
        tot["candidate"] += p["candidate"]
        diff = p["diff"]
        if diff == "material-difference":
            material.append(sc["id"])
        rows.append(f"| {sc['id']} | {sc['targeted_block']} | {p['base']}/{reps} ({p['marks']['base']}) | "
                    f"{p['candidate']}/{reps} ({p['marks']['candidate']}) | "
                    f"{'**' + diff + '**' if diff == 'material-difference' else diff} | "
                    f"[X={p['X'].upper()}] {p['note']} |")
    n = len(scenarios)
    n_answers = sum(p["have"] for p in per)
    n_parsed = sum(1 for p in per if p["complete"])

    if result["verdict"] == "INCOMPLETE":
        if not scenarios:
            vline = "INCOMPLETE — no verdict; the scenario list is empty"
        else:
            vline = ("INCOMPLETE — no verdict; missing answers, unparsed judge results or judge results not bound to "
                     f"the current answers for: {', '.join(result['incomplete'])}")
    elif result["verdict"] == "FAIL":
        vline = "FAIL — " + "; ".join(f"{f['id']} ({'; '.join(f['reasons'])})" for f in result["failing"])
    else:
        vline = (f"PASS — on every scenario CANDIDATE's correct count is at least BASE's minus 1 (of {reps}), "
                 f"and no scenario has CANDIDATE wrong in 2+ of {reps} while BASE is right in 2+ of {reps}")

    keyrows = [f"- **{sc['id']}** — {sc['key_change']}" for sc in scenarios if sc.get("key_change")]
    n_ctrl = sum(1 for sc in scenarios if sc.get("control") is True)
    nonpass = [f"- {f['id']}: {'; '.join(f['reasons'])}" for f in result["failing"]]
    nonpass += [f"- {i}: incomplete — no verdict contribution" for i in result["incomplete"]]
    lines = [
        "# Charter A/B behavioural eval",
        "",
        f"BASE = `{ident['base_ref']}` (`{ident['base_sha']}`); CANDIDATE = `{ident['candidate_ref']}` "
        f"(`{ident['candidate_sha']}`); charter = `{ident['charter']}`.",
        "",
        "## Method",
        "",
        f"- {n} scenarios (`{os.path.basename(ident['scenarios_file'])}`, sha256 `{ident['scenarios_sha256'][:12]}`): "
        f"{n - n_ctrl} aimed at blocks the change moved or deleted, {n_ctrl} controls on text it did not touch. "
        "Each has an `expected_rule` taken from BASE's own text.",
        f"- {reps} replicates per side per scenario: each a fresh headless `claude -p --model {ident['model']}` seat, "
        "`--allowedTools Read,Grep,Glob`, `CLAUDE_CONFIG_DIR` from the caller's environment, cwd = that side's "
        f"worktree of the commit above, role \"{ident['role']}\", the same prompt (`ab.py` PROMPT), at most 4 "
        "concurrent, 10-minute timeout, one retry on a failed or empty answer. "
        "Answers: `answers/<id>.<side>.r<k>.txt`.",
        f"- One codex judge call per scenario (`{ident['judge_model']}`, reasoning high, `-s read-only`, prompt on "
        f"stdin) over all {2*reps} answers. A/B labels are randomized per replicate (seed {ident['seed']}), and the "
        "two sides are named X/Y at random per scenario, so the judge never knows which side is the candidate "
        "(`judge/mapping.json`). The judge marks each answer correct or not against `expected_rule`, and says "
        "whether X and Y differ materially. A judge result counts only if its stored prompt hash equals the hash "
        "of the prompt re-rendered from the current answers.",
        f"- Verdict rule: PASS when, for every scenario, CANDIDATE correct ≥ BASE correct − 1 (of {reps}) and no "
        f"scenario has CANDIDATE wrong in ≥2 of {reps} while BASE is right in ≥2 of {reps}; FAIL when any scenario "
        "breaks either test; INCOMPLETE when any scenario lacks a complete, bound result (or there are no scenarios). "
        "The material-difference column is reported but does not enter the verdict.",
        "",
        "## Scoring-key changes (v1 keys kept as `expected_rule_v1`)",
        "",
        *(keyrows or ["- none"]),
        "- Keys without a `key_change` field are the keys as written in the scenarios file; none is disclosed as "
        "changed after answers were seen.",
        "",
        "## Results",
        "",
        "| id | targeted block | BASE correct | CANDIDATE correct | X vs Y | note (X = side named) |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
        f"**Totals:** BASE {tot['base']}/{n*reps}, CANDIDATE {tot['candidate']}/{n*reps}; answers present "
        f"{n_answers}/{2*reps*n}; complete judged scenarios {n_parsed}/{n}.",
        "",
        "**Scenarios that do not pass (with reasons):**",
        *(nonpass or ["- none"]),
        "",
        f"**Material difference between sides (informational):** {', '.join(material) or 'none'}",
        "",
        "**Both sides wrong on every replicate (charter gap, not a change effect):** "
        f"{', '.join(result['both_wrong']) or 'none'}",
        "",
        f"**Retries:** {', '.join(retries) or 'none'}",
        "",
        f"**Verdict:** {vline}",
        "",
    ]
    wt = os.path.join(run_dir, "walltime.txt")
    if os.path.exists(wt):
        lines += ["## Wall time", "", read_text(wt).strip(), ""]
    notes = os.path.join(run_dir, "notes.md")
    if os.path.exists(notes):
        lines += [read_text(notes).strip(), ""]
    text = "\n".join(lines)
    atomic_write(os.path.join(run_dir, "results.md"), text)
    atomic_write(os.path.join(run_dir, "verdict.json"), json.dumps(dict(result, identity=ident), indent=1) + "\n")
    print(text)
    return EXIT_BY_VERDICT[result["verdict"]]


# ---------------------------------------------------------------- CLI

def build_parser():
    ap = argparse.ArgumentParser(description="A/B behavioural eval of a charter change (see module docstring).")
    ap.add_argument("stage", choices=["seats", "judge", "report", "run"])
    ap.add_argument("--candidate", default=None, help="candidate ref (required on a run dir without sides.json)")
    ap.add_argument("--base", default=None, help="base ref (default: merge-base of main and the candidate)")
    ap.add_argument("--repo", default=None, help="repo path (default: git toplevel of this file's directory)")
    ap.add_argument("--charter", default=None, help=f"repo-relative charter path (default {DEFAULT_CHARTER})")
    ap.add_argument("--scenarios", default=None, help="scenarios JSON (default scenarios/showrunner.json)")
    ap.add_argument("--run-dir", default=None, help="run dir outside the repo (default: a new temp dir)")
    ap.add_argument("--model", default=None, help="seat model (default opus)")
    ap.add_argument("--judge-model", default=None, help="judge model (default gpt-6.1-sol)")
    ap.add_argument("--replicates", type=int, default=None, help="replicates per side (default env REPLICATES, else 3)")
    ap.add_argument("--jobs", type=int, default=4, help="concurrent seats, capped at 4")
    ap.add_argument("--judge-jobs", type=int, default=3)
    ap.add_argument("--seed", type=int, default=None, help="A/B label seed (default 1882)")
    ap.add_argument("--force", action="store_true")
    return ap


def fmt_secs(s):
    return f"{int(s) // 60} min {int(s) % 60} s"


def dispatch(a):
    stage = a.stage
    config_dir = None
    if stage in ("seats", "run"):
        # bites on: seats run with an unset/empty CLAUDE_CONFIG_DIR would silently use an unintended config (E1)
        config_dir = os.environ.get("CLAUDE_CONFIG_DIR", "")
        if not config_dir.strip():
            raise Refusal("CLAUDE_CONFIG_DIR is unset or empty; export it before running seats")
    repo = resolve_repo(a.repo)
    made_default = False
    if a.run_dir:
        run_dir = os.path.realpath(a.run_dir)
    elif stage in ("seats", "run"):
        run_dir, made_default = os.path.realpath(tempfile.mkdtemp(prefix="charter-ab-")), True
    else:
        raise Refusal(f"--run-dir is required for {stage}")
    # bites on: a run dir inside the repo tree would write eval output into the caller's checkout (E2)
    if inside(run_dir, repo):
        if made_default:
            with contextlib.suppress(OSError):
                os.rmdir(run_dir)
        raise Refusal(f"run dir {run_dir} is inside the repo {repo}; nothing writes into the repo")
    stored = read_sides(run_dir)
    if stored is None and stage in ("judge", "report"):
        raise Refusal(f"{run_dir} has no sides.json; run seats (or run) first")
    if a.jobs < 1 or a.judge_jobs < 1:
        raise Refusal("--jobs and --judge-jobs must be at least 1")
    ident, scenarios = build_identity(a, stage, repo, stored)
    if stored is not None:
        diff = identity_mismatch(stored, ident)
        # bites on: a stage run under a different commit/model/scenarios/replicates than the run dir's must not mix in (E3)
        if diff:
            raise Refusal(f"identity mismatch with {run_dir}/sides.json on: {', '.join(diff)}")
        ident.update({k: stored[k] for k in UNGUARDED_KEYS})
    os.makedirs(run_dir, exist_ok=True)
    if made_default:
        print(f"run dir: {run_dir}", flush=True)
    code = 0
    t0 = time.time()
    if stage in ("seats", "run"):
        with worktrees(repo, {"base": ident["base_sha"], "candidate": ident["candidate_sha"]}) as wts:
            for side, path in wts.items():
                if not os.path.isfile(os.path.join(path, ident["charter"])):
                    raise Refusal(f"{side} ({ident[side + '_sha']}) has no charter at {ident['charter']}")
            if stored is None:
                atomic_write(os.path.join(run_dir, "sides.json"), json.dumps(ident, indent=1) + "\n")
            stage_seats(run_dir, wts, scenarios, ident, a.force, min(a.jobs, 4), config_dir)
    t1 = time.time()
    if stage in ("judge", "run"):
        stage_judge(run_dir, scenarios, ident, a.force, a.judge_jobs)
    t2 = time.time()
    if stage == "run":
        with open(os.path.join(run_dir, "walltime.txt"), "a", encoding="utf-8") as f:
            f.write(f"- ab.py run invocation {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(t0))}: seats "
                    f"{fmt_secs(t1 - t0)}, judge {fmt_secs(t2 - t1)} (stages resume, so outputs already present "
                    "are skipped)\n")
    if stage in ("report", "run"):
        code = stage_report(run_dir, scenarios, ident)
    return code


def main(argv=None):
    a = build_parser().parse_args(argv)
    try:
        return dispatch(a)
    except Refusal as e:
        print(f"ab.py: refused: {e}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
