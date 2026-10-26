"""adopt_version plan's cloudStart field and the adopt-version skill's owed cloud step (issue #2177).

`cloudStart` says, per installed release in range, whether a part a cloud session loads at start
changed or the setup text's own steps changed; the skill turns that and the pin hook's state into
one owed setup-text paste or pin commit per cloud environment.
"""
import json
import os
import re
import sys

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PLUGIN = os.path.dirname(_LIB)
_SKILL_MD = os.path.join(_PLUGIN, "skills", "adopt-version", "SKILL.md")
_TRANSITION = os.path.join(_PLUGIN, "TRANSITION.md")

if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import adopt_version as av  # noqa: E402

_SETUP_TEXT = '''\
import helper

PKG = "{pkg}"
OTHER = "{other}"
CLONE = "{clone}"
FILL = "{fill}"
STORE = "{store}"


def _clone_dir():
    return CLONE


def _steps(source, clone):
    """{doc}"""
    return ["install " + PKG, source, clone, helper.DIR]


def _pin_view():
    return _steps("src", _clone_dir())


def _fill_lines():
    return [FILL]


def _view_for(files):
    return files + _pin_view() + _fill_lines()


def _store_files():
    return [STORE]


def stamped_files():
    return _view_for(_store_files())


def _elsewhere():
    return OTHER
'''


def _tree(cache, ver, *, front="description: a", body="body", agent="agent",
          hooks='{"hooks": {}}', pkg="tool", other="x", doc="Steps.", clone="c", helper="d",
          fill="f", stamp="sha256", store="s", setup=True):
    root = cache / ver
    (root / "skills" / "a").mkdir(parents=True)
    (root / "skills" / "a" / "SKILL.md").write_text("---\nname: a\n%s\n---\n\n%s\n" % (front, body))
    (root / "agents").mkdir()
    (root / "agents" / "x.md").write_text(agent)
    (root / "hooks").mkdir()
    (root / "hooks" / "hooks.json").write_text(hooks)
    (root / "lib").mkdir()
    (root / "lib" / "helper.py").write_text('DIR = "%s"\n' % helper)
    (root / "lib" / "cloud_setup.py").write_text(
        'def calibration_stamp(files):\n    return "%s"\n' % stamp)
    if setup:
        (root / "lib" / "cloud_setup_text.py").write_text(
            _SETUP_TEXT.format(pkg=pkg, other=other, doc=doc, clone=clone, fill=fill, store=store))
    (root / "TRANSITION.md").write_text("## %s\n" % ver)
    (root / "CHANGELOG.md").write_text("## %s\n" % ver)
    return root


def _plan(capsys, cache, frm, to):
    code = av.main(["plan", "--role", "showrunner", "--from", frm, "--to", to,
                    "--cache-dir", str(cache)])
    out = capsys.readouterr().out.strip()
    assert code == 0, out
    return json.loads(out)


def test_nothing_start_loaded_changed(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0", body="a changed skill body", other="y", doc="Other words.")
    data = _plan(capsys, cache, "0.1.0", "0.2.0")
    assert data["cloudStart"] == [
        {"version": "0.2.0", "since": "0.1.0", "startLoaded": [], "setupSteps": False}]
    assert data["cloudStartChanged"] is False


def test_start_loaded_parts_name_each_change(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0", front="description: b", agent="agent two", hooks='{"hooks": {"a": 1}}')
    data = _plan(capsys, cache, "0.1.0", "0.2.0")
    entry = data["cloudStart"][0]
    assert entry["startLoaded"] == ["agents/x.md", "hooks/hooks.json", "skills/a/SKILL.md"]
    assert entry["setupSteps"] is False
    assert data["cloudStartChanged"] is True


def test_added_agent_counts(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0")
    (cache / "0.2.0" / "agents" / "y.md").write_text("new")
    data = _plan(capsys, cache, "0.1.0", "0.2.0")
    assert data["cloudStart"][0]["startLoaded"] == ["agents/y.md"]
    assert data["cloudStartChanged"] is True


def test_setup_steps_change_counts(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0", pkg="tool@2")
    data = _plan(capsys, cache, "0.1.0", "0.2.0")
    assert data["cloudStart"][0]["setupSteps"] is True
    assert data["cloudStart"][0]["startLoaded"] == []
    assert data["cloudStartChanged"] is True


def test_a_step_input_reached_through_the_pin_view_counts(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0", clone="other-clone")
    _tree(cache, "0.3.0", clone="other-clone", helper="elsewhere")
    data = _plan(capsys, cache, "0.1.0", "0.3.0")
    assert [e["setupSteps"] for e in data["cloudStart"]] == [True, True]
    assert data["cloudStartChanged"] is True


def test_the_fill_step_and_the_stamp_hash_count(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0", fill="g")
    _tree(cache, "0.3.0", fill="g", stamp="sha512")
    data = _plan(capsys, cache, "0.1.0", "0.3.0")
    assert [e["setupSteps"] for e in data["cloudStart"]] == [True, True]


def test_a_calibration_store_change_counts(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0", store="normalized")
    data = _plan(capsys, cache, "0.1.0", "0.2.0")
    assert data["cloudStart"][0]["setupSteps"] is True
    assert data["cloudStartChanged"] is True


def test_unreadable_setup_steps_read_as_changed(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0", setup=False)
    _tree(cache, "0.2.0")
    data = _plan(capsys, cache, "0.1.0", "0.2.0")
    assert data["cloudStart"][0]["setupSteps"] is None
    assert data["cloudStartChanged"] is True


def test_one_entry_per_installed_release(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0", agent="agent two")
    _tree(cache, "0.3.0", agent="agent two")
    data = _plan(capsys, cache, "0.1.0", "0.3.0")
    assert [(e["since"], e["version"], e["startLoaded"]) for e in data["cloudStart"]] == [
        ("0.1.0", "0.2.0", ["agents/x.md"]), ("0.2.0", "0.3.0", [])]
    assert data["cloudStartChanged"] is True


def test_up_to_date_has_no_entries(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    data = _plan(capsys, cache, "0.1.0", "0.1.0")
    assert data["cloudStart"] == []
    assert data["cloudStartChanged"] is False


def _step(text, n):
    start = text.index("## Step %d " % n)
    end = text.index("## Step %d " % (n + 1))
    return text[start:end]


def _skill():
    with open(_SKILL_MD, encoding="utf-8") as fh:
        return fh.read()


def _bullet(step4, label):
    match = re.search(r"^- \*\*%s\*\* (.*?)(?=^- |^\n)" % re.escape(label), step4, re.M | re.S)
    assert match, "step 4 has no %r bullet" % label
    return " ".join(match.group(1).split())


def test_skill_owes_the_setup_text_paste_per_environment():
    step4 = _step(_skill(), 4)
    assert "`lib/cloud_setup.py` `read" in step4
    assert "`cloudStartChanged`" in step4
    paste = _bullet(step4, "The setup-text paste")
    assert ("`owed: paste new setup text into cloud environment <environment> "
            "(account <account>) (<to>)`") in paste
    assert "is not `valid`" in paste and "`cloudStartChanged` is true" in paste
    assert "older than **from** or newer than **to**" in paste


def test_skill_owes_the_pin_commit_whenever_the_hook_is_valid():
    step4 = _step(_skill(), 4)
    pin = _bullet(step4, "The pin commit")
    assert "`owed: pin commit for cloud environment <environment> (account <account>) (<to>)`" in pin
    assert "whenever the pin hook's `state` is `valid`" in pin
    assert "`lib/cloud_plugin_pin.py` `write" in pin
    assert "cloudStartChanged" not in pin and "paste" not in pin


def test_skill_owes_both_with_a_valid_old_pin_and_a_start_change_pin_first():
    step4 = " ".join(_step(_skill(), 4).split())
    assert "The two owed steps add up" in step4
    assert "skills/configure/reference/set-up.md" in step4
    assert ("When both are owed, the order is the pin commit (write, commit, push), then the paste, "
            "then the cloud check.") in step4
    # a valid hook owes the pin commit unconditionally, and a start change owes the paste as well
    assert "valid" in _bullet(_step(_skill(), 4), "The pin commit")
    assert "`cloudStartChanged` is true" in _bullet(_step(_skill(), 4), "The setup-text paste")
    assert step4.index("**The pin commit**") < step4.index("**The setup-text paste**")


def test_skill_keeps_the_cloud_check_out_of_adoption():
    step4 = " ".join(_step(_skill(), 4).split())
    assert "Never run it in steps 1–7" in step4
    assert "only after that project's owed paste or pin commit has landed" in step4


def test_skill_brief_names_the_owed_cloud_step():
    step8 = " ".join(_step(_skill(), 8).split())
    assert "a setup-text paste is the owner's and names each cloud environment and its account" in step8


def test_transition_unreleased_says_what_the_advisor_now_sees():
    with open(_TRANSITION, encoding="utf-8") as fh:
        text = fh.read()
    start = text.index("## Unreleased\n")
    unreleased = text[start:text.index("\n## ", start + 1)]
    assert "### Adopt-version: the cloud environments' setup text is an owed step" in unreleased
    assert "`cloudStart`" in unreleased and "`cloudStartChanged`" in unreleased
