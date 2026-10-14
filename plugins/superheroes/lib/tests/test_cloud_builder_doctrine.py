"""Doctrine-search guards for the cloud builder's reference (cloud.md) and the advisor's answering rule (wave-watch.md).

Bites on: the headless-session section losing the question-dialog flag, the builder note as the only way
to ask, or the push limits; the container section losing a sandbox fact (the two packages, the cache
flag, the signer, the size-count shape); the cloud-only-failure rule going back to judgment instead of
the two-part test; the per-round findings comment or the over-the-cap record rule leaving the Review
section; the advisor's answering rule saying "never on the issue" again, or the builder acting on only
one copy of the answer.

**Residual blind spots:** these are phrase searches over the collapsed text, so a section that keeps
the phrase but contradicts it in the next sentence passes; the container test carries one needle per
bullet and the bite-proof record proves only the representative bullet.
"""
import os
import re

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_CLOUD = os.path.join(_PLUGIN, "skills", "workhorse", "reference", "cloud.md")
_WAVE_WATCH = os.path.join(_PLUGIN, "skills", "showrunner", "reference", "wave-watch.md")


def _read(path):
    # Strict decoding on purpose: a file that cannot be read fails the test, never passes it.
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _collapsed(path):
    return " ".join(_read(path).split())


def _section(path, heading):
    """The collapsed body of the ``## heading`` section, up to the next ``## `` heading."""
    match = re.search(
        r"^## " + re.escape(heading) + r"\n(.*?)(?=^## |\Z)", _read(path), re.MULTILINE | re.DOTALL
    )
    assert match, f"the section {heading!r} was not found in {os.path.basename(path)}"
    return " ".join(match.group(1).split())


def _headings(path):
    return [line for line in _read(path).split("\n") if line.startswith("## ")]


def test_headless_section_follows_the_applies_section_and_names_the_dialog_flag_and_push_limits():
    # axis: a headless builder never asks in a dialog, parks with work pushed, and pushes only where the order allows
    headings = _headings(_CLOUD)
    assert headings.index("## A headless session") == headings.index("## When this file applies") + 1
    body = _section(_CLOUD, "A headless session")
    for needle in (
        "disallows the question tool through `--disallowedTools`",
        "builder note",
        "parks with its work pushed",
        "rubric/launch-doctrine.md",
        "never a force-push",
        "never `main`",
        "push only to the session's own branch",
    ):
        assert needle in body, needle


def test_container_section_names_the_sandbox_facts():
    # axis: the sandbox facts a cloud implementer dispatch fails without, one needle per bullet
    headings = _headings(_CLOUD)
    assert headings.index("## The cloud container") + 1 == headings.index("## Verify: cloud-only failures")
    body = _section(_CLOUD, "The cloud container")
    for needle in (
        "`bubblewrap` and `socat`",
        "uv python install",
        "inlines or cites only what is in the worktree",
        "so implementers never commit",
        "GIT_CONFIG_GLOBAL",
        "-X pycache_prefix",
        "keeps `-B`",
        "size_count.py count --base",
    ):
        assert needle in body, needle


def test_environment_only_failure_needs_both_the_base_run_and_a_named_limitation():
    # axis: environment-only is a test with two conditions, never a judgment; any other base-red failure is unresolved
    body = _section(_CLOUD, "Verify: cloud-only failures")
    for needle in (
        "only when both hold",
        "on the base commit in the same container",
        "the session runs as root",
        "the interpreter is not the project's pin",
        "unresolved base failure",
        "never as environment-only",
        "independent of the user",
    ):
        assert needle in body, needle


def test_each_review_rounds_findings_land_on_the_pr_as_the_round_lands():
    # axis: the round's raw findings are a PR comment before the next round, because the review directory dies with the container
    body = _section(_CLOUD, "Review")
    for needle in (
        "After each review round, post that round's raw findings",
        'a short "no findings" line',
        "naming the round and the head it reviewed",
        "before starting the next round",
        "lives only on the container",
    ):
        assert needle in body, needle


def test_a_review_record_over_the_cap_is_shortened_never_split():
    # axis: a too-large record is not retried or split; the builder parks naming the missing record
    body = _section(_CLOUD, "Review")
    for needle in (
        "`review-record-too-large`",
        "Do not retry it",
        "park, naming the oversized record",
        "Never split one record across several comments",
        "the reader parses one comment",
    ):
        assert needle in body, needle


def test_the_advisor_may_answer_on_the_issue_and_the_builder_acts_on_either_copy():
    # axis: both sides agree: the message stays the gate for note-answered, the issue comment is an allowed durable copy
    wave_watch = _collapsed(_WAVE_WATCH)
    assert "never on the issue" not in wave_watch
    assert "never on the issue" not in _collapsed(_CLOUD)
    answering = _section(_WAVE_WATCH, "Answering a builder note")
    intro = answering.split("**What the answer says.**")[0]
    assert "`note-answered`" in intro
    assert "as the durable record is allowed and recommended" in intro

    asking = _section(_CLOUD, "Asking the advisor: the builder note")
    assert "act on either copy inside the reply window" in asking
    assert "the issue comment carrying the advisor's answer" in asking
