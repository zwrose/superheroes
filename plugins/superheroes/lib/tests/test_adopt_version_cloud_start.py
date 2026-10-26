"""adopt_version plan's cloudStart field and the adopt-version skill's owed cloud steps (issue #2177).

`cloudStart` says, per installed release in range, whether a part a cloud session loads at start
changed and whether the project's setup stamp, computed by each release's own code, differs; the
skill turns that and the pin hook's state into the owed pin commit and setup-text paste per cloud
environment.
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

# A stand-in for a release's own setup-text code: `stamped_files` reads the project's calibration,
# builds the setup steps and reaches a store root through an import made inside a function.
_SETUP_TEXT = '''\
import os

import helper

PKG = "{pkg}"
OTHER = "{other}"


def _store_files(cwd):
    with open(os.path.join(cwd, "calibration.md"), encoding="utf-8") as fh:
        return fh.read(){store}


def _steps():
    """{doc}"""
    return ["install " + PKG, "fetch " + helper.SOURCE]


def _root():
    import store
    return store.store_root()


def stamped_files(cwd, root):
    return {{"files": _store_files(cwd), "steps": _steps(), "root": _root()}}


def _elsewhere():
    return OTHER
'''

_CLOUD_SETUP = '''\
import hashlib
import json


def calibration_stamp(files):
    return "sha256:" + hashlib.{algo}(json.dumps(files, sort_keys=True).encode()).hexdigest()
'''


def _tree(cache, ver, *, front="description: a", body="body", agent="agent",
          hooks='{"hooks": {}}', pkg="tool", other="x", doc="Steps.", source="git",
          store="", algo="sha256", store_root="/store", setup=True):
    root = cache / ver
    (root / "skills" / "a").mkdir(parents=True)
    (root / "skills" / "a" / "SKILL.md").write_text("---\nname: a\n%s\n---\n\n%s\n" % (front, body))
    (root / "agents").mkdir()
    (root / "agents" / "x.md").write_text(agent)
    (root / "hooks").mkdir()
    (root / "hooks" / "hooks.json").write_text(hooks)
    (root / "lib").mkdir()
    (root / "lib" / "helper.py").write_text('SOURCE = "%s"\n' % source)
    (root / "lib" / "store.py").write_text('def store_root():\n    return "%s"\n' % store_root)
    (root / "lib" / "cloud_setup.py").write_text(_CLOUD_SETUP.format(algo=algo))
    if setup:
        (root / "lib" / "cloud_setup_text.py").write_text(
            _SETUP_TEXT.format(pkg=pkg, other=other, doc=doc, store=store))
    (root / "TRANSITION.md").write_text("## %s\n" % ver)
    (root / "CHANGELOG.md").write_text("## %s\n" % ver)
    return root


def _project(tmp_path):
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    (project / "calibration.md").write_text("  calibration  \n")
    return project


def _snapshot(directory):
    out = {}
    for dp, _, fns in os.walk(directory):
        for fn in fns:
            path = os.path.join(dp, fn)
            st = os.stat(path)
            with open(path, "rb") as fh:
                out[path] = (st.st_mtime_ns, fh.read())
    return out


def _plan(capsys, cache, frm, to, project=None):
    argv = ["plan", "--role", "showrunner", "--from", frm, "--to", to, "--cache-dir", str(cache)]
    if project is not None:
        argv += ["--project", str(project)]
    code = av.main(argv)
    out = capsys.readouterr().out.strip()
    assert code == 0, out
    return json.loads(out)


def _steps_changed(capsys, tmp_path, **changed):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0", **changed)
    data = _plan(capsys, cache, "0.1.0", "0.2.0", _project(tmp_path))
    assert data["cloudStart"][0]["startLoaded"] == []
    return data


def test_an_unchanged_stamp_reads_false(capsys, tmp_path):
    data = _steps_changed(capsys, tmp_path, body="a changed skill body", other="y",
                          doc="Other words.")
    assert data["cloudStart"] == [
        {"version": "0.2.0", "since": "0.1.0", "startLoaded": [], "setupSteps": False}]
    assert data["cloudStartChanged"] is False


def test_a_change_behind_stamped_files_counts(capsys, tmp_path):
    data = _steps_changed(capsys, tmp_path, pkg="tool@2")
    assert data["cloudStart"][0]["setupSteps"] is True
    assert data["cloudStartChanged"] is True


def test_a_change_behind_calibration_stamp_counts(capsys, tmp_path):
    data = _steps_changed(capsys, tmp_path, algo="sha512")
    assert data["cloudStart"][0]["setupSteps"] is True


def test_a_calibration_store_change_counts(capsys, tmp_path):
    data = _steps_changed(capsys, tmp_path, store=".strip()")
    assert data["cloudStart"][0]["setupSteps"] is True


def test_a_setup_step_fetch_change_counts(capsys, tmp_path):
    data = _steps_changed(capsys, tmp_path, source="git --depth 1")
    assert data["cloudStart"][0]["setupSteps"] is True


def test_a_change_behind_an_import_inside_a_function_counts(capsys, tmp_path):
    data = _steps_changed(capsys, tmp_path, store_root="/other-store")
    assert data["cloudStart"][0]["setupSteps"] is True


def test_computing_the_stamp_writes_nothing_to_the_project(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0", pkg="tool@2")
    project = _project(tmp_path)
    before = _snapshot(project)
    _plan(capsys, cache, "0.1.0", "0.2.0", project)
    assert _snapshot(project) == before


def test_an_uncomputable_stamp_reads_as_changed(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0", setup=False)
    _tree(cache, "0.2.0")
    data = _plan(capsys, cache, "0.1.0", "0.2.0", _project(tmp_path))
    assert data["cloudStart"][0]["setupSteps"] is None
    assert data["cloudStartChanged"] is True


def test_no_project_reads_as_changed(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0")
    data = _plan(capsys, cache, "0.1.0", "0.2.0")
    assert data["cloudStart"][0]["setupSteps"] is None
    assert data["cloudStartChanged"] is True


def test_start_loaded_parts_name_each_change(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0", front="description: b", agent="agent two", hooks='{"hooks": {"a": 1}}')
    data = _plan(capsys, cache, "0.1.0", "0.2.0", _project(tmp_path))
    entry = data["cloudStart"][0]
    assert entry["startLoaded"] == ["agents/x.md", "hooks/hooks.json", "skills/a/SKILL.md"]
    assert entry["setupSteps"] is False
    assert data["cloudStartChanged"] is True


def test_added_agent_counts(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0")
    (cache / "0.2.0" / "agents" / "y.md").write_text("new")
    data = _plan(capsys, cache, "0.1.0", "0.2.0", _project(tmp_path))
    assert data["cloudStart"][0]["startLoaded"] == ["agents/y.md"]
    assert data["cloudStartChanged"] is True


def test_one_entry_per_installed_release(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0", agent="agent two")
    _tree(cache, "0.3.0", agent="agent two", pkg="tool@3")
    data = _plan(capsys, cache, "0.1.0", "0.3.0", _project(tmp_path))
    assert [(e["since"], e["version"], e["startLoaded"], e["setupSteps"])
            for e in data["cloudStart"]] == [
        ("0.1.0", "0.2.0", ["agents/x.md"], False), ("0.2.0", "0.3.0", [], True)]
    assert data["cloudStartChanged"] is True


def test_up_to_date_has_no_entries(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    data = _plan(capsys, cache, "0.1.0", "0.1.0", _project(tmp_path))
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


def _condition(bullet):
    """A bullet's condition: its text up to the colon that opens its owed line."""
    return bullet[:bullet.index(": `owed:")]


def test_skill_owes_the_pin_commit_whenever_the_project_has_the_hook():
    step4 = _step(_skill(), 4)
    pin = _bullet(step4, "The pin commit")
    assert _condition(pin) == (
        "whenever the pin hook's `state` is `valid` or `broken` (the project has the hook)")
    assert "`owed: pin commit for cloud environment <environment> (account <account>) (<to>)`" in pin
    assert "`lib/cloud_plugin_pin.py` `write" in pin
    assert ("A hook a release left `broken` (`script-differs`) is rewritten by that same write, "
            "before the paste.") in pin


def test_skill_owes_both_with_a_valid_old_pin_and_a_start_change_pin_first():
    step4 = " ".join(_step(_skill(), 4).split())
    assert "The two owed steps add up" in step4
    assert "skills/configure/reference/set-up.md" in step4
    assert ("When both are owed, the order is the pin commit (write, commit, push), then the paste, "
            "then the cloud check.") in step4
    # a valid hook owes the pin commit unconditionally, and a start change owes the paste as well
    assert "`valid` or `broken`" in _condition(_bullet(_step(_skill(), 4), "The pin commit"))
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
    # The release checklist renames "## Unreleased" to the version at each cut,
    # so find the note's own release section rather than a fixed heading.
    with open(_TRANSITION, encoding="utf-8") as fh:
        text = fh.read()
    note = text.index("\n### Adopt-version: the cloud environments' setup text is an owed step\n")
    start = text.rindex("\n## ", 0, note)
    end = text.find("\n## ", note)
    section = text[start:end if end != -1 else len(text)]
    assert "`cloudStart`" in section and "`cloudStartChanged`" in section
