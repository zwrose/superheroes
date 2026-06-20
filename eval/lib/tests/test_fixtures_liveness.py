import json, os, glob, skills

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
FIXDIR = os.path.join(ROOT, "eval", "skills", "fixtures")

def _key(path):
    parts = path.split(os.sep)
    return f"{parts[-4]}__{parts[-2]}"

def test_every_skill_has_a_parseable_fixture_with_both_directions():
    keys = {_key(p) for p in skills.iter_skill_paths(os.path.join(ROOT, "plugins"))}
    files = {os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(FIXDIR, "*.json"))}
    assert keys <= files, f"skills missing fixtures: {keys - files}"
    for f in glob.glob(os.path.join(FIXDIR, "*.json")):
        d = json.load(open(f))
        assert d["should_fire"] and isinstance(d["should_fire"], list), f
        assert isinstance(d["should_not_fire"], list), f
