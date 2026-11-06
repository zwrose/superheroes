"""Doctrine guards for the relay's pointer path in the advisor's references.

Bites on: any of the five places that tell an advisor how to send a message to a cloud builder on another
account (wave-watch.md's "Another account" steps, merge-train.md's cleanup step 2, orchestration.md's
`sendBack` send, orchestration.md's fix-order send, wave-watch.md's archive paragraph) losing the `point`
step, or losing the post of the composed file (`--body-file`) and any pointer to wave-watch.md's steps;
merge-train.md's cleanup step 2 or orchestration.md's `sendBack` bullets going back to settling a send by
relay reasons instead of `nothingReached`.

**Residual blind spots:** these are phrase searches over the collapsed text, so a home that keeps `point`
in a sentence that no longer sends the pointer passes; the five homes are the ones the order named, so a
sixth place that tells the advisor to relay a message is not covered.
"""
import os
import re

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_REF = os.path.join(_PLUGIN, "skills", "showrunner", "reference")
_WAVE_WATCH = os.path.join(_REF, "wave-watch.md")
_MERGE_TRAIN = os.path.join(_REF, "merge-train.md")
_ORCHESTRATION = os.path.join(_REF, "orchestration.md")

_POINT = re.compile(r"`point\b")  # the verb, as `point` or `point --repo-root …`, never `pointer-…`
_POINTS_TO_STEPS = "§ Answering a builder note"


def _read(path):
    # Strict decoding on purpose: a file that cannot be read fails the test, never passes it.
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _collapsed(path):
    return " ".join(_read(path).split())


def _between(path, start, end):
    """The collapsed text from ``start`` up to ``end``; each marker must occur exactly once."""
    text = _collapsed(path)
    assert text.count(start) == 1, f"{start!r} must occur once in {os.path.basename(path)}"
    first = text.index(start)
    assert text.count(end) >= 1 and text.find(end, first) > first, f"{end!r} not found after {start!r}"
    return text[first : text.index(end, first)]


def _cleanup_step_2():
    text = _read(_MERGE_TRAIN)
    section = re.search(
        r"^## Cleaning up a finished cloud lane\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL
    )
    assert section, "the cleanup section was not found"
    step = re.search(r"^2\. (.*?)(?=^3\. )", section.group(1), re.MULTILINE | re.DOTALL)
    assert step, "step 2 of the cleanup procedure was not found"
    return " ".join(step.group(1).split())


def _fix_order_bullet():
    return _between(
        _ORCHESTRATION,
        "- **Send a NOT-READY back to a live original builder.**",
        "The builder fixes, pushes and hands back as usual.",
    )


def _send_back_steps():
    return _between(
        _ORCHESTRATION,
        "For each item under `sendBack`",
        "- After a direct `SendMessage` returns",
    )


def _send_back_bullets():
    return _between(
        _ORCHESTRATION,
        "- After a direct `SendMessage` returns",
        "No further word from the owner is needed",
    )


def _homes():
    return {
        "wave-watch-steps": _between(
            _WAVE_WATCH, "**Another account.**", "**Not delivered, or `ensure` refused.**"
        ),
        "merge-train-step-2": _cleanup_step_2(),
        "orchestration-send-back": _send_back_steps(),
        "orchestration-fix-order": _fix_order_bullet(),
        "wave-watch-archive": _between(
            _WAVE_WATCH, "Any other message you send to a cloud session on another account", "The archive request's own steps"
        ),
    }


_HOME_IDS = [
    "wave-watch-steps",
    "merge-train-step-2",
    "orchestration-send-back",
    "orchestration-fix-order",
    "wave-watch-archive",
]


def test_there_are_five_relay_step_homes():
    # axis: the guard below covers exactly the five homes the order named, none dropped by a failed slice
    assert sorted(_homes()) == sorted(_HOME_IDS)


def test_each_relay_step_home_names_point_and_the_post_or_points_to_the_steps():
    # axis: every place that tells the advisor how to relay a message names `point` and the post of the composed file, or points to wave-watch's steps
    homes = _homes()
    for name in _HOME_IDS:
        text = homes[name]
        assert _POINT.search(text), f"{name} does not name the `point` step"
        assert "--body-file" in text or _POINTS_TO_STEPS in text, f"{name} neither names --body-file nor points to wave-watch's steps"


def test_merge_train_step_2_settles_by_nothing_reached():
    # axis: the cleanup records `failed` on nothingReached, never on a named relay reason
    step = _cleanup_step_2()
    # Each of the two settlements (the attempt's own record, and the resume of an unconfirmed one) is
    # checked by its own rule, so neither can drift while the other still names the token.
    assert "`failed` when it reads `nothingReached: true`, otherwise" in step, "the attempt's record"
    assert "`failed` when it reads `nothingReached: true` (nothing reached the" in step, "the resume's record"
    assert "relay-send-failed" not in step


def test_the_send_back_bullets_settle_by_nothing_reached():
    # axis: the send-back records read delivered / nothingReached / otherwise uncertain, never an enumerated relay reason
    bullets = _send_back_bullets()
    # Each bullet's settlement is checked on its own: the uncertain record and the no-record retry.
    assert "neither `delivered: true` nor `nothingReached: true`, run `sent --uncertain`" in bullets, "the uncertain record"
    assert "a `point` refusal or `nothingReached: true`, do not run `sent`." in bullets, "the no-record retry"
    for reason in ("relay-silent", "relay-text-mismatch", "relay-send-unconfirmed", "relay-send-failed"):
        assert reason not in bullets, reason
