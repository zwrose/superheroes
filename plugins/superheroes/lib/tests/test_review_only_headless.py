"""Detector for the #1136 converted `--review-only` contract.

The shape this pins: presence is an event, not a detected state (#1136 owner ruling).
The retired INTERACTIVE flag and its gating are gone. Instead:

- no review-code surface claims to detect owner presence;
- `--review-only` is a single path with no AskUserQuestion;
- the presentation contract names its durable artifact;
- the undecided set stays honest (neither approved nor dropped);
- inline bootstrap leaves created files uncommitted.

Each test names one guarded element. The old #1133 stall-shape detectors
(`test_setup_resolves_the_flag_fail_closed`, `test_interactivity_survives_compaction`,
`test_every_question_on_the_review_only_path_is_interactivity_gated`,
`test_interactive_presentation_is_intact`) were deleted — that contract retired with #1136.
"""
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_REVIEW_CODE = os.path.join(_PLUGIN_ROOT, "skills", "review-code")
_SKILL_MD = os.path.join(_REVIEW_CODE, "SKILL.md")
_SETUP_MD = os.path.join(_REVIEW_CODE, "reference", "setup.md")
_HEADLESS_MD = os.path.join(_REVIEW_CODE, "reference", "headless-presentation.md")
_VERIFICATION_MD = os.path.join(_REVIEW_CODE, "reference", "verification-pass.md")

_QUESTION = "AskUserQuestion"

# The durable artifact the presentation writes. One literal, quoted from the contract.
_ARTIFACT = "$SESSION_DIR/round-1/presentation.md"

# The headless contract's plugin-relative citation, as SKILL.md must spell it.
_CONTRACT_CITATION = "skills/review-code/reference/headless-presentation.md"

# review-code files whose surface must not reference the retired presence flag.
_PRESENCE_FLAG_SURFACE = (
    _SKILL_MD,
    _SETUP_MD,
    _HEADLESS_MD,
    _VERIFICATION_MD,
)

# Byte-pin: inline bootstrap must leave created files uncommitted — not a substring on
# "uncommitted" alone (C4).
_NORMATIVE_UNCOMMITTED_SENTENCE = (
    "When the created layer lands **in-repo**, **do not ask whether to commit** the new files: "
    "write the core + layer, leave them **uncommitted and untracked**, say so in the "
    "**dispatch summary**, and continue. Committing them unasked would be a review writing to "
    "the user's index — the honest answer is to leave the files for a human to stage."
)

# Literal census: every line carrying AskUserQuestion must match one pinned line byte-for-byte.
_ASK_USER_QUESTION_ALLOWED_LINES = frozenset({
    # skills/review-code/SKILL.md § --review-only
    "**Write the presentation artifact — the only path.** Follow "
    "`${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/headless-presentation.md`. "
    "Presence is an event, not a state a run can detect — the run never branches on whether a "
    "human is present and never opens a question that could block waiting for an answer. Never "
    "open `AskUserQuestion` on this path or any review-code path.",
    # skills/review-code/reference/headless-presentation.md
    "Open no `AskUserQuestion` on any review-code path, for any purpose.",
    "which posted to GitHub and kept its own `AskUserQuestion` review-event gate, was removed "
    "(#1121).",
})

# Branching prose that would reintroduce a second presentation channel.
_CHANNEL_BRANCH_PATTERNS = [
    re.compile(r"interactive\s+presentation", re.IGNORECASE),
    re.compile(r"headless\s+presentation", re.IGNORECASE),
    re.compile(r"presentation\s+channel", re.IGNORECASE),
    re.compile(r"if\s+.*interactive", re.IGNORECASE),
    re.compile(r"when\s+.*interactive", re.IGNORECASE),
]


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _section(text, heading):
    """The body of a markdown section: from `heading` to the next same-level heading."""
    marker = heading.strip()
    level = len(marker) - len(marker.lstrip("#"))
    start = text.index(heading)
    body_start = start + len(heading)
    nxt = re.compile(r"^#{1,%d} " % level, re.MULTILINE)
    m = nxt.search(text, body_start)
    return text[body_start:m.start()] if m else text[body_start:]


def _walk_review_code_markdown():
    """Derive the review-code markdown census — no hand-maintained file list."""
    for dirpath, dirnames, filenames in os.walk(_REVIEW_CODE):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
        for name in filenames:
            if name.endswith(".md"):
                yield os.path.join(dirpath, name)


def _ask_user_question_violations(text, label):
    """Every AskUserQuestion occurrence must be on an allowlisted line — inspect each independently."""
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if _QUESTION not in line:
            continue
        start = 0
        while True:
            idx = line.find(_QUESTION, start)
            if idx < 0:
                break
            if line not in _ASK_USER_QUESTION_ALLOWED_LINES:
                hits.append(f"{label} line {lineno}: {line}")
            start = idx + len(_QUESTION)
    return hits


@pytest.fixture(scope="module")
def review_only():
    """The shipped `### --review-only` section of review-code's SKILL.md."""
    return _section(_read(_SKILL_MD), "\n### `--review-only`\n")


@pytest.fixture(scope="module")
def skill_md():
    return _read(_SKILL_MD)


@pytest.fixture(scope="module")
def headless_contract():
    return _read(_HEADLESS_MD)


# axis: no retired presence-flag premise anywhere on review-code's surface — not merely absent
# from one file; the #1136 ruling retired detecting owner presence, not a variable name.
def test_no_presence_flag_on_review_code_surface():
    """#1136: review-code must not claim to detect owner presence via INTERACTIVE."""
    hits = []
    flag_patterns = [
        re.compile(r"\$INTERACTIVE"),
        re.compile(r"(?<![\w-])INTERACTIVE(?![\w-])"),
        re.compile(r"^\s*INTERACTIVE=", re.MULTILINE),
    ]
    for path in _PRESENCE_FLAG_SURFACE:
        text = _read(path)
        rel = os.path.relpath(path, _PLUGIN_ROOT)
        for lineno, line in enumerate(text.splitlines(), 1):
            for pat in flag_patterns:
                if pat.search(line):
                    hits.append(f"{rel}:{lineno}: {line.strip()}")
    assert not hits, (
        "#1136 retired detecting owner presence — review-code still references the "
        "INTERACTIVE flag or $INTERACTIVE on its surface. Hits:\n" + "\n".join(hits)
    )


# axis: `--review-only` is one path — no presentation branch on owner presence.
def test_review_only_is_a_single_path(review_only):
    """#1136: `--review-only` must not stall on or branch for owner presence."""
    branch_hits = []
    for lineno, line in enumerate(review_only.splitlines(), 1):
        for pat in _CHANNEL_BRANCH_PATTERNS:
            if pat.search(line):
                branch_hits.append(f"line {lineno}: {line.strip()}")
    assert not branch_hits, (
        "the `--review-only` section still selects between interactive and headless "
        "presentation channels — presence is an event, not a branch (#1136). Hits:\n"
        + "\n".join(branch_hits)
    )


# axis: literal AskUserQuestion census across every review-code markdown surface — derived walk.
def test_review_code_surfaces_ask_user_question_census():
    """#1136: every review-code markdown file must pin or prohibit each AskUserQuestion occurrence."""
    hits = []
    for path in _walk_review_code_markdown():
        rel = os.path.relpath(path, _PLUGIN_ROOT)
        hits.extend(_ask_user_question_violations(_read(path), rel))
    assert not hits, (
        "an `AskUserQuestion` occurrence is not one of the pinned prohibition lines — a positive "
        "instruction or evasion would pass a verb heuristic (#1136). Hits:\n" + "\n".join(hits)
    )


# axis: the presentation contract is reachable and names its durable artifact — citation resolves
# on disk and the contract names $SESSION_DIR/round-1/presentation.md. Not the section prose.
def test_presentation_contract_is_reachable_and_names_artifact(review_only):
    """The single presentation path cites a real contract that names the artifact."""
    assert _CONTRACT_CITATION in review_only, (
        "`--review-only` names no headless contract — the path has nowhere to send the "
        "presentation (#1136). Expected a citation of %s" % _CONTRACT_CITATION
    )
    assert os.path.isfile(_HEADLESS_MD), (
        "the headless contract %s is cited but does not exist — a dangling pointer is not "
        "a disposition (#1136)" % _HEADLESS_MD
    )
    contract = _read(_HEADLESS_MD)
    assert _ARTIFACT in contract, (
        "the headless contract does not name the durable artifact `%s` — a presentation that "
        "writes nowhere is indistinguishable from a review that never ran (#1136)" % _ARTIFACT
    )


# axis: the invocation surface states `--review-only` behavior concretely — an entry that names
# the artifact, not merely the flag name. Not the contract's internal wording.
def test_invocation_surface_states_the_artifact_path(skill_md):
    """A `--review-only` entry without the artifact cannot be told apart from another disposition."""
    artifact_hits = []
    for lineno, line in enumerate(skill_md.splitlines(), 1):
        if "--review-only" in line and _ARTIFACT in line:
            artifact_hits.append(lineno)
    assert artifact_hits, (
        "review-code's invocation surface has no `--review-only` entry naming the artifact "
        "`%s` — without it, read-only presentation cannot be distinguished from some other "
        "disposition (#1136)" % _ARTIFACT
    )


# axis: undecided-set honesty — the headless contract keeps Undecided as neither approved nor
# dropped and requires separate count summaries. Not the Approved section wording.
def test_undecided_set_preserved_as_category():
    """Folding undecided into approved would pass every other test in this file."""
    contract = _read(_HEADLESS_MD)
    assert "**Undecided — needs a human call.**" in contract, (
        "headless-presentation.md lost its Undecided heading — the ask-set has no honest category "
        "(#1136)"
    )
    assert "neither approved nor dropped" in contract, (
        "headless-presentation.md no longer says the undecided set is neither approved nor "
        "dropped — a run could silently approve or drop the ask-set (#1136)"
    )
    assert re.search(
        r"count summary.*separately|states the two sets separately",
        contract,
        re.IGNORECASE | re.DOTALL,
    ), (
        "headless-presentation.md no longer requires the count summary to state the two sets "
        "separately — one combined number reads as a decision that was never made (#1136)"
    )


# axis: inline review-init bootstrap still records the headless answer — byte-pin the normative
# sentence requiring files stay uncommitted and untracked with no commit question.
def test_inline_bootstrap_writes_headless_answers():
    """Setup's inline review-init route must still say files are left uncommitted."""
    setup = _read(_SETUP_MD)
    inline = [
        para for para in setup.split("\n\n")
        if "run review-init inline" in para
    ]
    assert inline, (
        "reference/setup.md no longer describes the inline review-init bootstrap — if that route "
        "moved, re-point this detector at its new home (#1136)"
    )
    route = "\n\n".join(inline + [
        para for para in setup.split("\n\n") if "not the only question in there" in para
    ])
    assert _NORMATIVE_UNCOMMITTED_SENTENCE in route, (
        "the inline bootstrap is missing the byte-pinned normative sentence requiring created "
        "files stay uncommitted and untracked with no commit question — prose that merely "
        "contains 'uncommitted' while authorizing the opposite would pass a substring search "
        "(#1136)"
    )
