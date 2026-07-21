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
REVIEW_SKILLS = ("review-code", "review-spec", "audit-debt")
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
        "review-spec/SKILL.md": ("## Your assignment", "## Context files", (
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


def test_review_loop_has_doc_mode_carveout():
    import re as _re
    import review_round_policy
    text = _read_repo("plugins/superheroes/reference/review-loop.md")
    assert "review-loop-version: 3" in text
    # #518: the retired, contradictory "three completed rounds" claim must be gone for good.
    assert "three completed rounds" not in text.lower()
    # doc-mode re-arm rule preserved
    norm = " ".join(text.split())
    assert "any open blocking finding" in norm.lower()
    # #518 drift guard — the two caps are stated separately and bound to their CODE homes:
    # (a) overall round cap in the prose == the deciders' --max-rounds default == the skill's
    #     operative --max-rounds CLI arg (binds the reconciled 7 to code, not prose-to-prose).
    spec_plan = _read_repo("plugins/superheroes/lib/spec_loop_plan.py")
    m_call = _re.search(r'add_argument\(\s*"--max-rounds"[^)]*\)', spec_plan)
    assert m_call, "spec_loop_plan.py must declare a --max-rounds argument"
    m_def = _re.search(r"default=(\d+)", m_call.group(0))
    assert m_def, "spec_loop_plan.py --max-rounds must have a numeric default"
    cap = m_def.group(1)
    spec_skill = _read_repo("plugins/superheroes/skills/review-spec/SKILL.md")
    m_skill = _re.search(r"--max-rounds\s+(\d+)", spec_skill)
    assert m_skill and m_skill.group(1) == cap, "skill --max-rounds must match the code default"
    assert _re.search(rf"overall round cap is \*\*{cap}\*\*", text), \
        f"review-loop.md must state the overall round cap as {cap} in its cap sentence"
    # (b) confirmation-panel budget in the prose == review_round_policy.MAX_CONFIRMATIONS
    n_conf = review_round_policy.MAX_CONFIRMATIONS
    assert _re.search(rf"MAX_CONFIRMATIONS = {n_conf}\b", text), \
        f"review-loop.md must state the confirmation budget as MAX_CONFIRMATIONS = {n_conf}"
    # #518: the post-halt-edit named violation is stated in the shared contract...
    assert "post-halt" in text.lower()
    # ...and carried by review-spec's receipt (the "receipt says so" requirement).
    assert "post-halt" in spec_skill.lower() and "terminal claim" in spec_skill.lower()


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
