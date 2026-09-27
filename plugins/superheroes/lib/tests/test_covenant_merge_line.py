"""Guards the covenant's merge hard line against losing any of its seven elements.

The first bullet under `## The hard lines` in rubric/covenant.md must keep its
compaction-safe minimum: the owner's word for a merge itself, the three merge
preconditions, the closed precondition list joined by "and" (never "or"), the
own-word requirement for release/publish/force-push, and the pointer to the
showrunner charter's duty 6.
"""
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN = os.path.abspath(os.path.join(_HERE, "..", ".."))


def _read_plugin(rel):
    with open(os.path.join(_PLUGIN, rel), encoding="utf-8") as fh:
        return fh.read()


# axis: presence of each of the seven merge-line elements in the covenant's first hard-line bullet; any one element alone missing must fail. The review-evidence literal carries its governing "only with" connective, not just the bare noun phrase, so inverting it (e.g. to "even without") fails that element. The precondition-list literal is the whole closed clause joined by "and", so swapping any of its internal conjunctions to "or" (an AND-to-OR weakening) fails that element even though each individual precondition phrase still appears elsewhere in the bullet.
# coverage: closed enumeration — the seven elements are the whole compaction-safe minimum of this bullet; an eighth element is added here, not elsewhere.
def test_covenant_merge_line_keeps_its_minimum():
    text = _read_plugin("rubric/covenant.md")

    section_match = re.search(r"## The hard lines.*?(?=\n## )", text, re.DOTALL)
    assert section_match, "rubric/covenant.md: '## The hard lines' section not found"
    section = section_match.group(0)

    bullet_match = re.search(
        r"- \*\*Never merge.*?(?=\n- \*\*)", section, re.DOTALL
    )
    assert bullet_match, (
        "rubric/covenant.md hard lines: the merge bullet ('- **Never merge') not found"
    )
    bullet = re.sub(r"\s+", " ", bullet_match.group(0))

    elements = {
        "own-word for a merge": "only inside the owner's word",
        "review-evidence precondition": "only with the lane's review evidence",
        "ci-green precondition": "CI green on the recorded head",
        "branch-current precondition": "a branch current with its base",
        "precondition list joined by and": (
            "only with the lane's review evidence, CI green on the recorded head, "
            "and a branch current with its base"
        ),
        "own-word for release, publish, force-push": (
            "a release, publish, or force-push needs a word for that act itself"
        ),
        "pointer to showrunner duty 6": "`skills/showrunner/SKILL.md` duty 6",
    }

    missing = [label for label, literal in elements.items() if literal not in bullet]
    assert not missing, (
        "rubric/covenant.md merge hard line missing element(s): " + ", ".join(missing)
    )
