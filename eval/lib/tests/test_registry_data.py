import os, skills

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
REGISTRY = os.path.join(ROOT, "eval", "skills", "registry.json")

def _key(path):  # plugins/<plugin>/skills/<skill>/SKILL.md -> <plugin>/<skill>
    parts = path.split(os.sep)
    return f"{parts[-4]}/{parts[-2]}"

def test_required_phrases_keys_match_skills_exactly_and_are_present():
    reg = skills.load_registry(REGISTRY)
    paths = skills.iter_skill_paths(os.path.join(ROOT, "plugins"))
    assert paths, "no skills found"
    skill_keys = {_key(p) for p in paths}
    # bidirectional: no skill missing an entry, and no stale entry for a removed skill
    assert set(reg["requiredPhrases"]) == skill_keys, \
        f"requiredPhrases drift: {set(reg['requiredPhrases']) ^ skill_keys}"
    for p in paths:
        key = _key(p)
        desc, _ = skills.read_skill(p)
        for phrase in reg["requiredPhrases"][key]:
            assert phrase in desc, f"{key}: required phrase {phrase!r} not in current description"

def test_body_ceilings_cover_the_six():
    reg = skills.load_registry(REGISTRY)
    assert set(reg["bodyCeilings"]) == {
        "review-crew/review-code", "review-crew/review-spec", "review-crew/review-plan",
        "review-crew/review-tasks", "review-crew/audit-debt", "the-architect/plan",
    }
