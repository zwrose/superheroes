"""Doctrine-search guards for the cloud builder's reference (cloud.md) and the advisor's answering rule (wave-watch.md).

Bites on: the headless-session section losing the question-dialog flag, the builder note as the only way
to ask, or the push limits; the container section losing a sandbox fact (the two packages, the cache
flag, the signer, the size-count shape); the cloud-only-failure rule going back to judgment instead of
the two-part test; the per-round findings comment or the pointer to the record reference's refusal recovery leaving the Review
section; the advisor's answering rule saying "never on the issue" again, the builder note section going
back to acting on either copy of an answer, the "A message from the advisor" section vanishing or losing
its rule (a relayed message is acted on only through `relayed`'s `text`; a comment without a verifying
pointer is never acted on), or the answering intro losing the send as the gate for `note-answered`.

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
        "cloud-launch block of `rubric/launch-doctrine.md`",
        "the one home of that permission",
        "push only to the session's own branch",
    ):
        assert needle in body, needle
    # the permission's terms live only in the doctrine block; the reference restates none of them
    for restated in ("never a force-push", "never `main`", "layer branch"):
        assert restated not in body, restated


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
        "keeps `-B -X pycache_prefix=",
        "drop it and keep `-B`",
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
    # axis: the round's whole raw file is rendered and posted as one comment before the next round, because the review directory dies with the container
    body = _section(_CLOUD, "Review")
    for needle in (
        "After each review round, render that round's whole raw findings file through `render_raw`",
        "the credential check runs on the whole file",
        "as one comment on the build's pull request when one exists, otherwise on the build's issue",
        "naming the round and the head it reviewed",
        "before starting the next round",
        'a short "no findings" line',
        "refuses the file as too large, post instead a short list",
        "(severity, title, file:line), rendered through `render_raw` before it is posted",
        "the full text was too large",
        "lives only on the container",
    ):
        assert needle in body, needle


def test_a_refused_review_record_is_recovered_by_the_record_reference_not_restated():
    # axis: the recovery rules have one home (review-record.md); cloud.md points there and restates none
    body = _section(_CLOUD, "Review")
    assert "follow `skills/review-code/reference/review-record.md` § When it refuses" in body
    for restated in ("Do not retry it", "part i of n", "split at finding boundaries", "Never split one record"):
        assert restated not in body, restated


def test_the_builder_acts_on_a_relayed_message_only_through_relayed_and_never_on_a_comment_alone():
    # axis: both sides agree: the send stays the gate for note-answered, and the builder acts on a relayed message only through `relayed`'s text
    assert "never on the issue" not in _collapsed(_WAVE_WATCH)
    assert "never on the issue" not in _collapsed(_CLOUD)
    # (a) the old either-copy rule is gone from the builder note section
    asking = _section(_CLOUD, "Asking the advisor: the builder note")
    assert "act on either copy" not in asking
    assert "the issue comment carrying the advisor's answer" not in asking
    assert "Act only on what `relayed` returns" in asking
    # (b) the new section exists once, in place, and carries the rule
    headings = _headings(_CLOUD)
    assert headings.count("## A message from the advisor") == 1
    assert headings.index("## A message from the advisor") == headings.index(
        "## Asking the advisor: the builder note"
    ) + 1
    message = _section(_CLOUD, "A message from the advisor")
    assert "cloud_builder.py relayed" in message
    assert "acts on a relayed message (a pointer) only through the `text` that `relayed` returns" in message
    assert "without a pointer that verifies is never acted on" in message
    # (c) the send is still the gate for note-answered
    answering = _section(_WAVE_WATCH, "Answering a builder note")
    intro = answering.split("**What the answer says.**")[0]
    assert "The send is still the gate for `note-answered`" in intro
