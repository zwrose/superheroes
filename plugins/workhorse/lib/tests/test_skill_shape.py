import os
import re

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SKILL = os.path.join(_PLUGIN, "skills", "workhorse", "SKILL.md")


def _text():
    with open(_SKILL, encoding="utf-8") as fh:
        return fh.read()


def test_frontmatter_name_matches_dir():
    t = _text()
    m = re.search(r"^---\n(.*?)\n---", t, re.S)
    assert m and re.search(r"^name:\s*workhorse\s*$", m.group(1), re.M)
    assert re.search(r"^description:\s*\S", m.group(1), re.M)


def test_references_each_owned_lib_and_subskill():
    t = _text()
    for ref in ("enforcer.py", "ci_loop.py", "detect.py", "devserver.py",
                "reset.py", "readout.py",
                "subagent-driven-development", "review-crew:review-code",
                "test-pilot-plan", "test-pilot-execute", "engine.py"):
        assert ref in t, ref


def test_states_never_merge_and_startup_selfcheck():
    t = _text().lower()
    assert "never merge" in t or "merge is yours" in t
    assert "selfcheck" in t or "self-check" in t
    assert "gates.review" in _text() and "passed" in _text()  # input precondition


def test_skill_documents_resume_substrate():
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    skill = os.path.join(os.path.dirname(os.path.dirname(here)), "skills", "workhorse", "SKILL.md")
    body = open(skill, encoding="utf-8").read().lower()
    for needle in ("reconcile", "ref-lease", "fence", "ci_fix_attempt",
                   "re-arm", "startup lock", "control-plane"):
        assert needle in body, needle
