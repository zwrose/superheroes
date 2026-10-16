#!/usr/bin/env python3
"""A/B behavioural eval: does a charter change alter how the seat it governs behaves?

Stages (resumable; existing non-empty outputs are kept unless --force): seats (fresh headless claude seats per
scenario per side, in throwaway git worktrees of the BASE and CANDIDATE commits), judge (one blind codex judge call
per scenario, read-only), report (results.md and verdict.json), run (all three; wall time in walltime.txt).
Exit codes: 0 PASS, 1 FAIL, 2 INCOMPLETE (report/run); 3 refusal; seats/judge alone exit 0.
Everything is written to the run dir (outside the repo). Its sides.json is the run identity: a later stage that
disagrees with it (other commit, model, replicate count, scenarios, ...) is refused rather than mixed in.
Answers: answers/<id>.<side>.r<k>.txt. Python >= 3.9, standard library only.
"""
import argparse, contextlib, fcntl, hashlib, json, os, signal, random, re, shutil, subprocess, sys, tempfile, threading, time
import concurrent.futures as cf
from pathlib import Path

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
                 "scenarios_sha256", "role", "model", "judge_model", "replicates", "seed", "plugin_dir", "claude_config_dir")
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


def labels(reps):
    return [f"{k}{ab}" for k in range(1, reps + 1) for ab in "AB"]


def parse_judge(text, reps):
    """The last well-shaped judgment object anywhere in text, whatever its key order or the braces in its note."""
    want, dec, found = set(labels(reps)), json.JSONDecoder(), None
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            d = dec.raw_decode(text, i)[0]
        except ValueError:
            continue
        c = d.get("correct") if isinstance(d, dict) else None
        # bites on: judge output with a missing/extra label or non-bool value must not count as a result
        if isinstance(c, dict) and set(c) == want and all(isinstance(v, bool) for v in c.values()) \
                and d.get("sources_differ") in DIFF:
            found = d
    return found


def make_mapping(scenario_ids, reps, seed):
    rng, mapping = random.Random(seed), {}
    for sid in scenario_ids:
        per = {str(k): ({"A": "base", "B": "candidate"} if rng.random() < 0.5 else {"A": "candidate", "B": "base"})
               for k in range(1, reps + 1)}
        x = "base" if rng.random() < 0.5 else "candidate"
        mapping[sid] = {"replicates": per, "X": x, "Y": "candidate" if x == "base" else "base"}
    return mapping


def unmap(mapping_entry, judged_correct, reps):
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
        if not (s.get("complete") and isinstance(s.get("base"), int) and isinstance(s.get("candidate"), int)):
            incomplete.append(s["id"])
            continue
        if reasons := scenario_flags(s["base"], s["candidate"], reps):
            failing.append({"id": s["id"], "reasons": reasons})
        if s["base"] == 0 and s["candidate"] == 0:
            both_wrong.append(s["id"])
    # bites on: an incomplete scenario, or no scenarios at all, must never be reported as PASS or FAIL
    if incomplete or not per_scenario:
        v = "INCOMPLETE"
    else:
        v = "FAIL" if failing else "PASS"
    return {"verdict": v, "failing": failing, "both_wrong": both_wrong, "incomplete": incomplete}


def identity_mismatch(stored, current):
    return [k for k in IDENTITY_KEYS if k not in UNGUARDED_KEYS and stored.get(k) != current.get(k)]


def plugin_dir_for(root, charter):
    """Repo-relative nearest ancestor dir of charter, below root, that holds .claude-plugin/plugin.json; else None."""
    rel = os.path.normpath(os.path.relpath(charter, root) if os.path.isabs(charter) else charter)
    if rel == ".." or rel.startswith(".." + os.sep):
        return None
    for parent in Path(rel).parents:
        if parent == Path("."):
            break
        if os.path.isfile(os.path.join(root, parent, ".claude-plugin", "plugin.json")):
            return parent.as_posix()
    return None


def normalize_charter(root, charter):
    """Repo-relative, normalized charter path; an absolute path inside root is made relative, and any path
    that would leave root is refused, so each side's worktree (not the live checkout) supplies the file."""
    rel = os.path.normpath(os.path.relpath(charter, root) if os.path.isabs(charter) else charter)
    if rel == ".." or rel.startswith(".." + os.sep) or os.path.isabs(rel):
        raise Refusal(f"--charter must be a path inside the repository, got {charter}")
    return Path(rel).as_posix()


def render_prompt(role, charter, situation, question):
    return PROMPT.format(role=role, charter=charter, situation=situation, question=question)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def nonempty(path):
    try:
        return read_text(path).strip() != ""
    except (OSError, UnicodeDecodeError):
        return False


def atomic_write(path, text):
    """Write to a temp file in the same directory, then os.replace: readers never see a partial file."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def load_json(path, default=None):
    try:
        return json.loads(read_text(path))
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


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


def rev_parse_commit(repo, ref):
    p = git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
    # bites on: a ref that does not resolve to a commit must refuse, never fall through to a guess (E8)
    if p.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", p.stdout.strip()):
        raise Refusal(f"cannot resolve {ref!r} to a commit in {repo}")
    return p.stdout.strip()


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
    paths = {side: os.path.join(tmp, side) for side in SIDES}
    try:
        for side, path in paths.items():
            p = git(repo, "worktree", "add", "--detach", path, shas[side])
            if p.returncode != 0:
                raise Refusal(f"git worktree add failed for {side}: {p.stderr.strip()}")
        yield paths
    finally:
        # bites on: a stage that raises must still remove the worktrees it created (E9)
        for path in paths.values():
            git(repo, "worktree", "remove", "--force", path)
        git(repo, "worktree", "prune")
        shutil.rmtree(tmp, ignore_errors=True)


def load_scenarios(path):
    try:
        raw = Path(path).read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as e:
        raise Refusal(f"cannot read scenarios file {path}: {e}")
    if isinstance(data, list):
        data = {"role": DEFAULT_ROLE, "scenarios": data}
    if not (isinstance(data, dict) and isinstance(data.get("scenarios"), list) and isinstance(data.get("role"), str)
            and data["role"].strip()):
        raise Refusal(f"{path}: expected a list, or an object with a non-empty string 'role' and a 'scenarios' list")
    seen = set()
    for i, sc in enumerate(data["scenarios"]):
        missing = [k for k in REQUIRED_FIELDS if not isinstance(sc, dict) or k not in sc]
        if missing:
            raise Refusal(f"{path}: scenario #{i} lacks {', '.join(missing)}")
        rule = sc["expected_rule"]
        if not (isinstance(rule, str) and rule.strip()):
            raise Refusal(f"{path}: scenario #{i} needs a non-empty string expected_rule")
        if sc["id"] in seen:
            raise Refusal(f"{path}: duplicate scenario id {sc['id']!r}")
        seen.add(sc["id"])
    return data["role"], data["scenarios"], hashlib.sha256(raw).hexdigest()


def build_identity(a, stage, repo, stored):
    """The identity this invocation would run under. seats/run recompute it from the arguments (defaults
    included); report/judge take anything not given explicitly from the stored identity."""
    strict = stage in ("seats", "run")
    src = {} if strict or not stored else stored

    def pick(val, key, default):
        return val if val is not None else src.get(key, default)

    def resolve(arg, side):  # (ref, sha) from the argument, else from the stored identity, else None
        if arg:
            return arg, rev_parse_commit(repo, arg)
        if not stored:
            return None
        sha = stored[side + "_sha"]
        return stored[side + "_ref"], (rev_parse_commit(repo, sha) if strict else sha)

    reps = int(os.environ.get("REPLICATES", "3")) if a.replicates is None and strict else a.replicates
    scen_file = os.path.abspath(a.scenarios or src.get("scenarios_file", DEFAULT_SCENARIOS))
    role, scenarios, scen_sha = load_scenarios(scen_file)
    cand = resolve(a.candidate, "candidate")
    if cand is None:
        raise Refusal("--candidate is required for the first use of a run dir")
    base = resolve(a.base, "base") or default_base(repo, cand[1], cand[0])
    n_reps = pick(reps, "replicates", 3)
    # bites on: zero or negative replicates run no seats, and one replicate cannot trip either failure condition,
    # so both would report a vacuous PASS
    if n_reps < (2 if strict else 1):
        raise Refusal(f"replicates must be at least 2 to detect a regression, got {n_reps}")
    charter = normalize_charter(repo, pick(a.charter, "charter", DEFAULT_CHARTER))
    ident = {"base_ref": base[0], "base_sha": base[1], "candidate_ref": cand[0], "candidate_sha": cand[1],
             "charter": charter, "scenarios_file": scen_file,
             "scenarios_sha256": scen_sha, "role": role, "model": pick(a.model, "model", "opus"),
             "judge_model": pick(a.judge_model, "judge_model", "gpt-6.1-sol"),
             "replicates": n_reps, "seed": pick(a.seed, "seed", 1882),
             "plugin_dir": plugin_dir_for(repo, charter) if strict else src.get("plugin_dir")}
    return ident, scenarios


_RUNNING_PROCS, _RUNNING_PROCS_LOCK, _STOPPING = set(), threading.Lock(), threading.Event()


def run_group(cmd, timeout, prompt=None, **kw):
    """Run cmd in its own session, tracked so an interrupt can kill its whole group (SIGKILL cannot be forwarded)."""
    with _RUNNING_PROCS_LOCK:
        if _STOPPING.is_set():
            raise InterruptedError("interrupted; not starting another model call")
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE if prompt is not None else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8",
                                errors="replace", start_new_session=True, **kw)
        _RUNNING_PROCS.add(proc)
    try:
        out, err = proc.communicate(prompt, timeout=timeout)
    except BaseException:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise
    finally:
        with _RUNNING_PROCS_LOCK:
            _RUNNING_PROCS.discard(proc)
    return proc.returncode, out, err


@contextlib.contextmanager
def cancel_on_interrupt():
    """On Ctrl-C stop new attempts and kill every live model process group before the workers are joined."""
    _STOPPING.clear()
    try:
        yield
    except KeyboardInterrupt:
        with _RUNNING_PROCS_LOCK:
            _STOPPING.set()
            for proc in _RUNNING_PROCS:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGKILL)
        raise


def exec_seat(cmd, cwd, env):
    return run_group(cmd, SEAT_TIMEOUT, cwd=cwd, env=env)


def run_seat(run_dir, side_dirs, sc, side, rep, force, ident, config_dir):
    out, res = ans_path(run_dir, sc["id"], side, rep), {"id": sc["id"], "side": side, "rep": rep}
    if nonempty(out) and not force:
        return dict(res, attempts=0, ok=True, skipped=True)
    prompt = render_prompt(ident["role"], ident["charter"], sc["situation"], sc["question"])
    if force and nonempty(out):
        # bites on: a forced rerun that fails must stay incomplete, so the old answer leaves the active path first
        os.replace(out, out + ".prev")
    cmd = ["claude", "-p", "--model", ident["model"]]
    if ident["plugin_dir"] is not None:
        # bites on: each seat loads the plugin from its own side's worktree, not the installed one (v0)
        cmd += ["--plugin-dir", os.path.join(side_dirs[side], ident["plugin_dir"])]
    cmd += ["--allowedTools", "Read,Grep,Glob", "--output-format", "text", prompt]
    ok = False
    for attempt in (1, 2):
        if _STOPPING.is_set():
            break
        t0 = time.time()
        try:
            rc, text, err = exec_seat(cmd, side_dirs[side], dict(os.environ, CLAUDE_CONFIG_DIR=config_dir))
            # bites on: an answer is published only from a call that exited 0 with non-empty output
            ok = rc == 0 and text.strip() != ""
        except (subprocess.TimeoutExpired, OSError) as e:
            text, err, ok = "", f"{type(e).__name__}: {e}", False
        log(run_dir, f"seat {sc['id']}.{side}.r{rep} attempt {attempt} ok={ok} {time.time()-t0:.0f}s")
        if ok:
            atomic_write(out, text)
            break
        Path(out + f".fail{attempt}.err").write_text(f"{err}\n---stdout---\n{text}", encoding="utf-8")
    return dict(res, attempts=attempt, ok=ok, skipped=False)


def invalidate_reports(run_dir, force):
    """bites on: a forced rerun interrupted mid-way must not leave a saved PASS over answers that are now gone"""
    for name in ("results.md", "verdict.json") if force else ():
        with contextlib.suppress(FileNotFoundError):
            os.remove(os.path.join(run_dir, name))


def stage_seats(run_dir, side_dirs, scenarios, ident, force, jobs, config_dir):
    invalidate_reports(run_dir, force)
    os.makedirs(os.path.join(run_dir, "answers"), exist_ok=True)
    # replicate-major order so a partial run still leaves whole replicates
    tasks = [(sc, side, rep) for rep in range(1, ident["replicates"] + 1) for sc in scenarios for side in SIDES]
    path = os.path.join(run_dir, "answers", "seats.json")
    prior = {(r["id"], r["side"], r["rep"]): r for r in load_json(path, []) or []}
    with cf.ThreadPoolExecutor(max_workers=max(1, min(jobs, 4))) as ex, cancel_on_interrupt():
        for r in ex.map(lambda t: run_seat(run_dir, side_dirs, *t, force, ident, config_dir), tasks):
            if not r["skipped"] or (r["id"], r["side"], r["rep"]) not in prior:
                prior[(r["id"], r["side"], r["rep"])] = r
    atomic_write(path, json.dumps(sorted(prior.values(), key=lambda r: (r["id"], r["side"], r["rep"])), indent=1))


def redact_roots(text, roots):
    """bites on: a worktree path in an answer names its side (base/candidate), which would unblind the judge"""
    for root in sorted(roots, key=len, reverse=True):
        text = text.replace(root, "<worktree>")
    return text


def render_judge(run_dir, sc, m, reps):
    """The judge prompt for one scenario from the current answers and mapping; None if an answer is missing.
    Both stages render through here, so the redacted text is what the prompt hash binds."""
    blocks, xs, ys = [], [], []
    roots = load_json(os.path.join(run_dir, "worktrees.json"), []) or []
    for k in range(1, reps + 1):
        for lab in "AB":
            side = m["replicates"][str(k)][lab]
            p = ans_path(run_dir, sc["id"], side, k)
            if not nonempty(p):
                return None
            blocks.append(f"## Answer {k}{lab}\n{redact_roots(read_text(p).strip(), roots)}\n")
            (xs if side == m["X"] else ys).append(f"{k}{lab}")
    return JUDGE.format(
        n=reps, situation=sc["situation"], question=sc["question"],
        expected_rule=sc["expected_rule"], answers="\n".join(blocks),
        sources=f"Variant X wrote answers {', '.join(xs)}. Variant Y wrote answers {', '.join(ys)}.",
        keys=", ".join(f'"{l}": true|false' for l in labels(reps)))


def judge_paths(run_dir, sid):
    jd = os.path.join(run_dir, "judge")
    return tuple(os.path.join(jd, f"{sid}.{ext}") for ext in ("out.txt", "prompt.md", "prompt.sha256"))


def prompt_bound(run_dir, sid, prompt):
    """True only when the stored hash is the hash of exactly this freshly rendered prompt."""
    try:
        stored = read_text(judge_paths(run_dir, sid)[2]).strip()
    except (OSError, UnicodeDecodeError):
        return False
    # bites on: a judge result made over different answers than the current ones must not be reused or counted
    return prompt is not None and stored == sha256_text(prompt)


def exec_judge(cmd, prompt):
    return run_group(cmd, JUDGE_TIMEOUT, prompt)


def stage_judge(run_dir, scenarios, ident, force, jobs):
    reps, jd = ident["replicates"], os.path.join(run_dir, "judge")
    os.makedirs(jd, exist_ok=True)
    invalidate_reports(run_dir, force)
    mapping = make_mapping([sc["id"] for sc in scenarios], reps, ident["seed"])
    old = {} if force else load_json(os.path.join(jd, "mapping.json"), {}) or {}
    if all(sid in old and len(old[sid]["replicates"]) == reps for sid in mapping):
        mapping = old  # keep the mapping that existing judge outputs were made under
    atomic_write(os.path.join(jd, "mapping.json"), json.dumps(mapping, indent=1))
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
        if force:
            # bites on: a forced rerun that fails must stay incomplete, so the old output and hash leave the active path
            for stale in (out, shap):
                if os.path.exists(stale):
                    os.replace(stale, stale + ".prev")
        for attempt in (1, 2):
            if _STOPPING.is_set():
                break
            t0 = time.time()
            try:
                rc, text, err = exec_judge(cmd, prompt)
            except (subprocess.TimeoutExpired, OSError) as e:
                rc, text, err = None, "", f"{type(e).__name__}: {e}"
            # bites on: a judge call that exited non-zero is not published even when its stdout parses
            ok = rc == 0 and parse_judge(text, reps) is not None
            log(run_dir, f"judge {sid} attempt {attempt} ok={ok} {time.time()-t0:.0f}s")
            if ok:
                atomic_write(out, text)
                atomic_write(shap, sha256_text(prompt))  # written only after the output parsed
                return sid, attempt
            Path(out + f".fail{attempt}.err").write_text(f"{err}\n---stdout---\n{text}", encoding="utf-8")
        return sid, -2

    path = os.path.join(jd, "judge-attempts.json")
    prior = load_json(path, {})
    with cf.ThreadPoolExecutor(max_workers=max(1, jobs)) as ex, cancel_on_interrupt():
        for sid, a in ex.map(one, scenarios):
            if a != 0 or sid not in prior:
                prior[sid] = a
    atomic_write(path, json.dumps(prior, indent=1))


def completeness(run_dir, scenarios, mapping, reps):
    """The single completeness check: per scenario, complete only with all 2*reps answers, a judge output
    that parses, and a stored prompt hash equal to the hash of the prompt re-rendered from the current
    answers and mapping."""
    per = []
    for sc in scenarios:
        sid, m = sc["id"], mapping.get(sc["id"])
        have = sum(nonempty(ans_path(run_dir, sid, s, k)) for s in SIDES for k in range(1, reps + 1))
        out = judge_paths(run_dir, sid)[0]
        d = parse_judge(read_text(out), reps) if nonempty(out) else None
        rec = {"id": sid, "complete": False, "base": None, "candidate": None, "have": have,
               "parsed": d is not None, "bound": False, "marks": None, "diff": None, "note": "", "X": None}
        try:
            prompt = render_judge(run_dir, sc, m, reps) if m is not None and have == 2 * reps else None
            rec["bound"] = prompt_bound(run_dir, sid, prompt)
            if prompt is not None and d is not None and rec["bound"]:
                ps = unmap(m, d["correct"], reps)
                rec.update(complete=True, base=sum(ps["base"]), candidate=sum(ps["candidate"]),
                           marks={s: "".join("✓" if ok else "✗" for ok in ps[s]) for s in SIDES},
                           diff=d["sources_differ"], note=str(d.get("note", "")).replace("|", "/"), X=m["X"])
        except (KeyError, TypeError, ValueError):
            pass
        per.append(rec)
    return per


def stage_report(run_dir, scenarios, ident):
    reps, n, jd = ident["replicates"], len(scenarios), os.path.join(run_dir, "judge")
    mapping = load_json(os.path.join(jd, "mapping.json"), {})
    seats = load_json(os.path.join(run_dir, "answers", "seats.json"), []) or []
    retries = [f"seat {r['id']}.{r['side']}.r{r['rep']} ({'ok' if r['ok'] else 'FAILED'} after {r['attempts']})"
               for r in sorted(seats, key=lambda r: (r["id"], r["side"], r["rep"])) if r.get("attempts", 0) > 1]
    ja = load_json(os.path.join(jd, "judge-attempts.json"), {}) or {}
    retries += [f"judge {k} (ok after 2)" for k, v in sorted(ja.items()) if v == 2]
    per = completeness(run_dir, scenarios, mapping if isinstance(mapping, dict) else {}, reps)
    result = verdict(per, reps)  # the only path to a verdict
    rows, tot, material = [], {"base": 0, "candidate": 0}, []
    for sc, p in zip(scenarios, per):
        head = f"| {sc['id']} | {sc['targeted_block']} | "
        if not p["complete"]:
            rows.append(head + f"? | ? | ? | incomplete (answers {p['have']}/{2*reps}, "
                        f"judge {'parsed' if p['parsed'] else 'missing or unparsed'}, "
                        f"prompt hash {'bound' if p['bound'] else 'not bound to the current answers'}) |")
            continue
        tot["base"], tot["candidate"] = tot["base"] + p["base"], tot["candidate"] + p["candidate"]
        mat = p["diff"] == "material-difference"
        material += [sc["id"]] if mat else []
        rows.append(head + f"{p['base']}/{reps} ({p['marks']['base']}) | {p['candidate']}/{reps} "
                    f"({p['marks']['candidate']}) | {'**' + p['diff'] + '**' if mat else p['diff']} | "
                    f"[X={p['X'].upper()}] {p['note']} |")

    if result["verdict"] == "INCOMPLETE":
        vline = ("INCOMPLETE — no verdict; the scenario list is empty" if not scenarios else
                 "INCOMPLETE — no verdict; missing answers, unparsed judge results or judge results not bound to "
                 f"the current answers for: {', '.join(result['incomplete'])}")
    elif result["verdict"] == "FAIL":
        vline = "FAIL — " + "; ".join(f"{f['id']} ({'; '.join(f['reasons'])})" for f in result["failing"])
    else:
        vline = (f"PASS — on every scenario CANDIDATE's correct count is at least BASE's minus 1 (of {reps}), "
                 f"and no scenario has CANDIDATE wrong in 2+ of {reps} while BASE is right in 2+ of {reps}")

    plugin = f"`--plugin-dir {ident['plugin_dir']}` in that side's worktree" if ident["plugin_dir"] else "no plugin dir"
    n_ctrl = sum(sc.get("control") is True for sc in scenarios)
    nonpass = [f"- {f['id']}: {'; '.join(f['reasons'])}" for f in result["failing"]]
    nonpass += [f"- {i}: incomplete — no verdict contribution" for i in result["incomplete"]]
    keyrows = [f"- **{sc['id']}** — {sc['key_change']}" for sc in scenarios if sc.get("key_change")]
    lines = [  # an item ending in "\n" is followed by a blank line in the joined text
        "# Charter A/B behavioural eval\n",
        f"BASE = `{ident['base_ref']}` (`{ident['base_sha']}`); CANDIDATE = `{ident['candidate_ref']}` "
        f"(`{ident['candidate_sha']}`); charter = `{ident['charter']}`.\n",
        "## Method\n",
        f"- {n} scenarios (`{os.path.basename(ident['scenarios_file'])}`, sha256 `{ident['scenarios_sha256'][:12]}`): "
        f"{n - n_ctrl} aimed at blocks the change moved or deleted, {n_ctrl} controls on text it did not touch. "
        "Each has an `expected_rule` taken from BASE's own text.",
        f"- {reps} replicates per side per scenario: each a fresh headless `claude -p --model {ident['model']}` seat, "
        "`--allowedTools Read,Grep,Glob`, `CLAUDE_CONFIG_DIR` from the caller's environment, cwd = that side's "
        f"worktree of the commit above, plugin: {plugin}, role \"{ident['role']}\", the same prompt (`ab.py` "
        "PROMPT), at most 4 concurrent, 10-minute timeout, one retry on a failed or empty answer. "
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
        "The material-difference column is reported but does not enter the verdict.\n",
        "## Scoring-key changes (v1 keys kept as `expected_rule_v1`)\n",
        *(keyrows or ["- none"]),
        "- Keys without a `key_change` field are the keys as written in the scenarios file; none is disclosed as "
        "changed after answers were seen.\n",
        "## Results\n",
        "| id | targeted block | BASE correct | CANDIDATE correct | X vs Y | note (X = side named) |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
        f"**Totals:** BASE {tot['base']}/{n*reps}, CANDIDATE {tot['candidate']}/{n*reps}; answers present "
        f"{sum(p['have'] for p in per)}/{2*reps*n}; complete judged scenarios {sum(p['complete'] for p in per)}/{n}.\n",
        "**Scenarios that do not pass (with reasons):**",
        *(nonpass or ["- none"]),
        "",
        f"**Material difference between sides (informational):** {', '.join(material) or 'none'}\n",
        "**Both sides wrong on every replicate (charter gap, not a change effect):** "
        f"{', '.join(result['both_wrong']) or 'none'}\n",
        f"**Retries:** {', '.join(retries) or 'none'}\n",
        f"**Verdict:** {vline}\n",
    ]
    for name, head in (("walltime.txt", ["## Wall time\n"]), ("notes.md", [])):
        if os.path.exists(os.path.join(run_dir, name)):
            lines += [*head, read_text(os.path.join(run_dir, name)).strip() + "\n"]
    text = "\n".join(lines)
    atomic_write(os.path.join(run_dir, "results.md"), text)
    atomic_write(os.path.join(run_dir, "verdict.json"), json.dumps(dict(result, identity=ident), indent=1) + "\n")
    print(text)
    return EXIT_BY_VERDICT[result["verdict"]]


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


def dispatch(a, stack):
    stage, config_dir = a.stage, None
    if stage in ("seats", "run"):
        # bites on: seats run with an unset/empty CLAUDE_CONFIG_DIR would silently use an unintended config (E1)
        config_dir = os.environ.get("CLAUDE_CONFIG_DIR", "")
        if not config_dir.strip():
            raise Refusal("CLAUDE_CONFIG_DIR is unset or empty; export it before running seats")
    start = os.path.abspath(a.repo) if a.repo else HERE
    p = git(start, "rev-parse", "--show-toplevel")
    if p.returncode != 0 or not p.stdout.strip():
        raise Refusal(f"{start} is not inside a git repository")
    repo, made_default = os.path.realpath(p.stdout.strip()), False
    if a.run_dir:
        run_dir = os.path.realpath(a.run_dir)
    elif stage in ("seats", "run"):
        run_dir, made_default = os.path.realpath(tempfile.mkdtemp(prefix="charter-ab-")), True
    else:
        raise Refusal(f"--run-dir is required for {stage}")
    # bites on: a run dir inside the repo tree would write eval output into the caller's checkout (E2)
    if inside(run_dir, repo):
        if made_default:
            shutil.rmtree(run_dir, ignore_errors=True)  # our own fresh, empty temp dir
        raise Refusal(f"run dir {run_dir} is inside the repo {repo}; nothing writes into the repo")
    if stage in ("seats", "run"):
        os.makedirs(run_dir, exist_ok=True)
    if os.path.isdir(run_dir):
        # bites on: two invocations on one run dir must not both pass validation and mix identities (held to exit)
        fd = os.open(run_dir, os.O_RDONLY)
        stack.callback(os.close, fd)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Refusal(f"{run_dir} is in use by another ab.py invocation")
    stored = load_json(os.path.join(run_dir, "sides.json"))
    if stored is None and stage in ("judge", "report"):
        raise Refusal(f"{run_dir} has no sides.json; run seats (or run) first")
    if stored is None and stage in ("seats", "run") and os.path.isdir(run_dir) and os.listdir(run_dir):
        # bites on: a populated run dir whose sides.json is missing or unreadable must not take a new identity and
        # reuse the old answers and judgments under it
        raise Refusal(f"{run_dir} holds prior run artifacts but no readable sides.json; "
                      "use a fresh --run-dir (identity cannot be validated)")
    ident, scenarios = build_identity(a, stage, repo, stored)
    ident["claude_config_dir"] = os.path.realpath(config_dir) if config_dir else (stored or {}).get("claude_config_dir")
    if stored is not None:
        # bites on: a stage under a different commit/model/scenarios/replicates than the run dir's must not mix in (E3)
        if diff := identity_mismatch(stored, ident):
            raise Refusal(f"identity mismatch with {run_dir}/sides.json on: {', '.join(diff)}")
        ident.update({k: stored[k] for k in UNGUARDED_KEYS})
    os.makedirs(run_dir, exist_ok=True)
    if made_default:
        print(f"run dir: {run_dir}", flush=True)
    code, t0 = 0, time.time()
    if stage in ("seats", "run"):
        with worktrees(repo, {"base": ident["base_sha"], "candidate": ident["candidate_sha"]}) as wts:
            for side, path in wts.items():
                if not os.path.isfile(os.path.join(path, ident["charter"])):
                    raise Refusal(f"{side} ({ident[side + '_sha']}) has no charter at {ident['charter']}")
                # bites on: a side whose worktree lacks the plugin manifest must refuse, not load another plugin (E10)
                if ident["plugin_dir"] and not os.path.isfile(
                        os.path.join(path, ident["plugin_dir"], ".claude-plugin", "plugin.json")):
                    raise Refusal(f"{side} ({ident[side + '_sha']}) has no plugin manifest at "
                                  f"{ident['plugin_dir']}/.claude-plugin/plugin.json")
            wtf = os.path.join(run_dir, "worktrees.json")  # every root any seat of this run dir has run under
            roots = set(load_json(wtf, []) or []) | {r for q in wts.values() for r in (q, os.path.realpath(q))}
            atomic_write(wtf, json.dumps(sorted(roots)))
            if stored is None:
                atomic_write(os.path.join(run_dir, "sides.json"), json.dumps(ident, indent=1) + "\n")
            stage_seats(run_dir, wts, scenarios, ident, a.force, a.jobs, config_dir)
    t1 = time.time()
    if stage in ("judge", "run"):
        stage_judge(run_dir, scenarios, ident, a.force, a.judge_jobs)
    t2 = time.time()
    if stage == "run":
        (m1, s1), (m2, s2) = divmod(int(t1 - t0), 60), divmod(int(t2 - t1), 60)
        with open(os.path.join(run_dir, "walltime.txt"), "a", encoding="utf-8") as f:
            f.write(f"- ab.py run invocation {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(t0))}: seats "
                    f"{m1} min {s1} s, judge {m2} min {s2} s (stages resume, so outputs already present are skipped)\n")
    if stage in ("report", "run"):
        code = stage_report(run_dir, scenarios, ident)
    return code


def main(argv=None):
    a = build_parser().parse_args(argv)
    try:
        with contextlib.ExitStack() as stack:
            return dispatch(a, stack)
    except Refusal as e:
        print(f"ab.py: refused: {e}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
