"""Determinate, fence-aware guard over the four review-crew SKILL.md files.

Rule 1: neither path literal may appear INSIDE a fenced code block.
Rule 2: the literal profile existence test must not appear at all in the three
        review skills (anti-regression for the resolver-driven guard fix).

Assumptions (intentionally narrow — the skills only use these forms):
  - The fence parser (`_lines_in_fences`) recognizes ``` fences only, not ~~~.
  - Rule 2 targets only the `[ -f review-profile.md ]` existence-test form
    (via `pat`); it is not a general literal-in-prose check.
These rules guard fenced code blocks and the existence-test form; they do NOT
police descriptive prose, which legitimately still mentions the literals.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.normpath(os.path.join(HERE, "..", "..", "skills"))

PATH_LITERALS = (".claude/review-profile.md", ".claude/review-decisions.json")
REVIEW_SKILLS = ("review-code", "review-plan", "review-spec", "review-tasks", "audit-debt")
ALL_SKILLS = REVIEW_SKILLS + ("review-init",)
REPO = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))


def _lines_in_fences(text):
    """Yield (lineno, line) for lines inside ``` fenced blocks."""
    in_fence = False
    for i, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            yield i, line


def _read(skill):
    with open(os.path.join(SKILLS, skill, "SKILL.md")) as fh:
        return fh.read()


def _read_repo(path):
    with open(os.path.join(REPO, path)) as fh:
        return fh.read()


def _section(text, heading, next_heading=None):
    start = text.index(heading)
    if next_heading is None:
        return text[start:]
    end = text.index(next_heading, start + len(heading))
    return text[start:end]


def test_rule1_no_path_literal_inside_fences():
    offenders = []
    for skill in ALL_SKILLS:
        for lineno, line in _lines_in_fences(_read(skill)):
            for lit in PATH_LITERALS:
                if lit in line:
                    offenders.append(f"{skill}/SKILL.md:{lineno}: {lit}")
    assert not offenders, "path literal inside a fence:\n" + "\n".join(offenders)


def test_rule2_no_literal_existence_test_in_review_skills():
    pat = re.compile(r"\[\s*!?\s*-f\s+\.claude/review-profile\.md\s*\]")
    offenders = []
    for skill in REVIEW_SKILLS:
        for i, line in enumerate(_read(skill).splitlines(), 1):
            if pat.search(line):
                offenders.append(f"{skill}/SKILL.md:{i}")
    assert not offenders, "literal existence test still present:\n" + "\n".join(offenders)


def test_review_dispatch_prompts_require_bounded_session_artifact_reads():
    cases = {
        "review-code/reference/auto-fix-loop.md": ("## Your assignment", "## Context files", (
            "diff.txt",
            "offset/limit",
            "bounded shell",
            "<=800",
            "never one whole-file",
            "until the diff is covered",
        )),
        "review-plan/SKILL.md": ("## Your assignment", "## Context files", (
            "$SESSION_DIR/plan.md",
            "$SESSION_DIR/spec.md",
            "bounded chunks",
            "<=800",
            "bounded shell",
            "never one whole-file",
        )),
        "review-spec/SKILL.md": ("## Your assignment", "## Context files", (
            "$SESSION_DIR/spec.md",
            "bounded chunks",
            "<=800",
            "bounded shell",
            "never one whole-file",
        )),
        "review-tasks/SKILL.md": ("## Your assignment", "## Context files", (
            "$SESSION_DIR/tasks.md",
            "$SESSION_DIR/plan.md",
            "$SESSION_DIR/spec.md",
            "bounded chunks",
            "<=800",
            "bounded shell",
            "never one whole-file",
        )),
        "audit-debt/SKILL.md": ("## Context files", "## Calibration precedence", (
            "$SESSION_DIR/sweep-prep/files.txt",
            "bounded chunks",
            "<=800",
            "bounded shell",
            "never one whole-file",
        )),
    }
    missing = []
    for rel_path, (heading, next_heading, needles) in cases.items():
        text = _section(
            _read_repo(f"plugins/superheroes/skills/{rel_path}"),
            heading,
            next_heading,
        ).lower()
        for needle in needles:
            if needle.lower() not in text:
                missing.append(f"{rel_path}: {needle}")
    assert not missing, "missing bounded-read dispatch guidance:\n" + "\n".join(missing)


def test_showrunner_step_1_5_preflight_readout_confirm_override_loop():
    """Task 11: the showrunner SKILL gains a step 1.5 (the one interactive confirm/override/decline
    surface) between the pre-flight gate (step 1) and the bundle launch (step 2). Assert its shape
    structurally: it lives between the gate and the launch, shells the three preflight_readout CLI
    verbs + run_overrides.write, names all three owner choices, and states the FR-1 no-dispatch-
    before-confirm + UFR-1 decline-is-side-effect-free + UFR-3 fail-closed guarantees."""
    text = _read_repo("plugins/superheroes/skills/showrunner/SKILL.md")

    # The step exists and is numbered 1.5.
    assert "1.5" in text, "no step 1.5 heading in the showrunner SKILL"

    # It sits AFTER the pre-flight gate (preflight.py) and BEFORE the bundle launch (Workflow tool
    # on showrunner.bundle.js) — the readout slots between step 1 and step 2.
    gate = text.index("preflight.py")
    step_1_5 = text.index("1.5")
    launch = text.index("showrunner.bundle.js")
    assert gate < step_1_5 < launch, "step 1.5 must sit between the pre-flight gate and the launch"

    section = _section(text, "1.5", "## Resume")
    low = section.lower()

    # Shells the three verified CLI verbs of the pure core + the durable freeze seam.
    for needle in ("preflight_readout.py", "assemble", "render",
                   "validate-override", "run_overrides"):
        assert needle in section, f"step 1.5 missing shell of {needle}"

    # Names all three owner choices, resolved via the host ask primitive (host-neutral).
    assert "ask primitive" in low, "step 1.5 must reach the interactive host ask primitive"
    for choice in ("confirm", "override", "decline"):
        assert choice in low, f"step 1.5 missing the {choice} branch"

    # FR-1: no agent dispatches before confirm. UFR-1: decline is side-effect-free (no write, no
    # launch, run not started, no branch/PR). UFR-3: a total-failure assemble is fail-closed (STOP).
    assert "before this confirm" in low or "no dispatch precedes" in low or "no agent dispatch" in low, \
        "step 1.5 must state the FR-1 no-dispatch-before-confirm guarantee"
    assert "no changes" in low or "no side effect" in low or "not marked started" in low, \
        "step 1.5 must state the UFR-1 side-effect-free decline"
    assert "stop" in low and ("ok:false" in low or "ok: false" in low or "total-failure" in low), \
        "step 1.5 must fail closed (STOP) on a total-failure assemble (UFR-3)"

    # FR-14 / FR-4: a stale override and an unauthorized-engine fallback surface as per-row flags.
    assert "no longer valid" in low, "step 1.5 must reference the FR-14 stale-override row flag"
    assert "falls back to claude" in low, "step 1.5 must reference the FR-4 fallback row flag"


def test_review_loop_has_doc_mode_carveout():
    text = _read_repo("plugins/superheroes/reference/review-loop.md")
    assert "review-loop-version: 2" in text
    assert "document review" in text.lower() and "three completed rounds" in text.lower()
    assert "any open blocking finding" in text.lower() or "Critical **or** Important" in text


def test_host_maps_document_claude_dispatch_recovery_and_codex_asymmetry():
    claude_needles = (
        "dispatch reliability",
        "existence and mtime",
        "retry the identical dispatch once",
        "general-purpose",
        "agents/<name>.md",
        "minus frontmatter",
        "never compile",
        "freshly write",
    )
    codex_needles = (
        "dispatch reliability",
        "spawn_agent",
        "has not exhibited",
        "do not apply the claude fallback",
    )

    for rel_path in ("hosts/claude-tools.md", "plugins/superheroes/hosts/claude-tools.md"):
        text = _read_repo(rel_path).lower()
        missing = [needle for needle in claude_needles if needle not in text]
        assert not missing, f"{rel_path} missing: {missing}"

    for rel_path in ("hosts/codex-tools.md", "plugins/superheroes/hosts/codex-tools.md"):
        text = _read_repo(rel_path).lower()
        missing = [needle for needle in codex_needles if needle not in text]
        assert not missing, f"{rel_path} missing: {missing}"
