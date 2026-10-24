"""Pins the vet-drafter agent (#2107) and the pointers that route the advisor to it.

The owner ruled on 2026-10-23 (held for Canon as ``2026-10-23-0b372f49-2``, an explicit
exception to ``2026-10-17-a0ca556b-18``) that the vet-drafter runs on the advisor's own model:
its definition says ``model: inherit`` and the advisor dispatches it with no model parameter.
This module pins that ``model: inherit`` line, the stated tool grant, the three rules every
draft keeps, the no-post / no-slot-write obligation, and the vetting reference and duty-4
pointers that tell the advisor when to use the drafter.
"""

import os
import re

PLUGIN_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")

AGENT = os.path.join("agents", "vet-drafter.md")
VETTING = os.path.join("skills", "showrunner", "reference", "vetting.md")
SKILL = os.path.join("skills", "showrunner", "SKILL.md")


def _read(rel):
    path = os.path.join(PLUGIN_ROOT, rel)
    assert os.path.isfile(path), f"{rel} is missing from the plugin root ({path})"
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _frontmatter_and_body(text):
    lines = text.split("\n")
    assert lines and lines[0].strip() == "---", "agent file must open with a --- frontmatter fence"
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    assert end is not None, "agent file frontmatter is never closed by a second --- line"
    pairs = []
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        pairs.append((key.strip(), value.strip().strip("\"'")))
    return pairs, "\n".join(lines[end + 1 :])


def _collapse(text):
    return re.sub(r"\s+", " ", text)


def _agent():
    return _frontmatter_and_body(_read(AGENT))


def test_vet_drafter_model_is_inherit_never_a_pin():
    pairs, _ = _agent()
    models = [value for key, value in pairs if key == "model"]
    # axis: the drafter must run on the advisor's own model, never a pinned tier
    assert len(models) == 1, f"vet-drafter must carry exactly one model key, found {models!r}"
    assert models[0] == "inherit", (
        f"vet-drafter model is {models[0]!r}; #2107 and the owner's ruling of 2026-10-23 "
        "require `model: inherit` so the draft runs on the advisor's own model"
    )


def test_vet_drafter_grant_is_the_stated_shape():
    pairs, _ = _agent()
    disallowed = [value for key, value in pairs if key == "disallowedTools"]
    # axis: a disallowedTools key strips granted tools while the tools line stays unchanged
    assert not disallowed, (
        f"vet-drafter carries a disallowedTools key {disallowed!r}; it would remove tools "
        "the drafter needs for its probes"
    )
    tools_values = [value for key, value in pairs if key == "tools"]
    assert len(tools_values) == 1, f"vet-drafter must carry exactly one tools key, found {tools_values!r}"
    tools = [t.strip() for t in tools_values[0].split(",")]
    # axis: the grant is exactly the stated six tools, with no dispatch, MCP or web tool
    assert len(tools) == len(set(tools)), f"vet-drafter tools has duplicates: {tools!r}"
    assert set(tools) == {"Read", "Grep", "Glob", "Edit", "Write", "Bash"}, (
        f"vet-drafter tools drifted from the stated shape: {tools!r}"
    )


def test_vet_drafter_names_the_three_misses():
    _, body = _agent()
    body = _collapse(body)
    # axis: each of the three rules every draft keeps stands as its whole bold sentence, decision included
    for phrase in (
        "**A finding the vet catches before merge is never a review escape.**",
        "**A stack layer is not held NOT-READY for review leftovers its own PR body does not name when "
        "the stack's sheet carries them as cards.**",
        "**Write the receipt as the advisor's own.**",
    ):
        assert phrase in body, f"vet-drafter body no longer carries the rule sentence {phrase!r}"


def test_vet_drafter_forbids_posting_and_the_slot_write():
    _, body = _agent()
    body = _collapse(body)
    # axis: the no-post and no-slot-write obligations and the two draft file names stay stated
    for phrase in (
        "You **post nothing**",
        "never run `lib/vet_slot.py write`",
        "draft-receipt<ordinal>.md",
        "draft-slot<ordinal>.md",
    ):
        assert phrase in body, f"vet-drafter body no longer carries {phrase!r}"


def test_vetting_reference_and_duty_4_point_at_the_drafter():
    vetting = _read(VETTING)
    skill = _read(SKILL)
    heading = "## Parallel vets — the vet-drafter"
    # axis: the vetting reference carries the one section and tells the advisor not to override the model
    assert vetting.split("\n").count(heading) == 1, (
        f"{VETTING} must carry the heading line {heading!r} exactly once"
    )
    assert "no model parameter" in _collapse(vetting), f"{VETTING} must say the drafter is dispatched with no model parameter"
    lines = skill.split("\n")
    starts = [i for i, line in enumerate(lines) if line.startswith("4. **Vet PRs from artifacts, never narratives.**")]
    ends = [i for i, line in enumerate(lines) if line.startswith("5. **")]
    assert len(starts) == 1, f"{SKILL} must carry exactly one line opening duty 4, found {len(starts)}"
    assert len(ends) == 1, f"{SKILL} must carry exactly one line opening duty 5, found {len(ends)}"
    assert starts[0] < ends[0], f"{SKILL} duty 5 must come after duty 4"
    duty_4 = _collapse("\n".join(lines[starts[0] : ends[0]]))
    pointer = "`${CLAUDE_PLUGIN_ROOT}/skills/showrunner/reference/vetting.md` § Parallel vets"
    # axis: the charter names `§ Parallel vets` exactly once
    assert skill.count("§ Parallel vets") == 1, (
        f"{SKILL} must carry `§ Parallel vets` exactly once (the #2107 duty-4 pointer)"
    )
    # axis: duty 4 itself cites the vetting reference by its exact path, so the pointer neither retargets nor leaves duty 4
    assert pointer in duty_4, f"{SKILL} duty 4 must carry the exact #2107 pointer {pointer!r}"
