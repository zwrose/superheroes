"""adopt_version plan's cloudStart field and the adopt-version skill's owed cloud steps (issue #2177).

`cloudStart` says, per installed release in range, whether a part a cloud session loads at start
changed and whether the project's setup stamp, computed by each release's own code, differs; the
skill turns that and the pin hook's state into the owed pin commit and setup-text paste per cloud
environment.
"""
import json
import os
import re
import subprocess
import sys

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PLUGIN = os.path.dirname(_LIB)
_SKILL_MD = os.path.join(_PLUGIN, "skills", "adopt-version", "SKILL.md")
_TRANSITION = os.path.join(_PLUGIN, "TRANSITION.md")

if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import adopt_version as av  # noqa: E402
import cloud_plugin_pin  # noqa: E402
import cloud_setup_text  # noqa: E402
import transition_notes  # noqa: E402

# A stand-in for a release's own setup-text code: `stamped_files` reads the project's calibration,
# builds the setup steps and reaches a store root through an import made inside a function.
_SETUP_TEXT = '''\
import os

import helper

PKG = "{pkg}"
OTHER = "{other}"
{definition}

def _store_files(cwd):
    with open(os.path.join(cwd, "calibration.md"), encoding="utf-8") as fh:
        return fh.read(){store}


def _steps():
    """{doc}"""
    return ["install " + PKG, "fetch " + helper.SOURCE]


def _root():
    import vault
    return vault.store_root()


def stamped_files(cwd, root):
    return {{"files": _store_files(cwd), "steps": _steps(), "root": _root()}}


def _elsewhere():
    return OTHER
'''

_CLOUD_SETUP = '''\
import hashlib
import json


def calibration_stamp(files):
    return "sha256:" + hashlib.{algo}(json.dumps(
        files, sort_keys=True, default=lambda v: v.hex() if isinstance(v, bytes) else str(v)
    ).encode()).hexdigest()
'''

# A stand-in whose `stamped_files` answers a view of bytes, holding the inventory entry as given.
_BYTES_SETUP_TEXT = '''\
INVENTORY = {inventory!r}
STEPS = {steps!r}


def stamped_files(cwd, root):
    return {{"setup-steps": STEPS, "setup-plugin-inventory": INVENTORY}}
'''

# A stand-in that, like a release's own code, reads the pin hook with its own reader (here one that
# finds it broken), and builds its view only when that reader says valid.
_PIN_SETUP_TEXT = '''\
def _pin_state(cwd):
    return {"state": "broken", "reason": "script-differs", "pin": None}


def stamped_files(cwd, root):
    if _pin_state(cwd)["state"] != "valid":
        raise RuntimeError("the pin hook is not valid")
    return {"steps": "pinned"}
'''


def _tree(cache, ver, *, front="description: a", body="body", agent="agent",
          other_hook="guard one", session_hook="start one", start="start hook",
          covenant="covenant", pkg="tool", other="x", doc="Steps.", source="git",
          store="", algo="sha256", store_root="/store", setup=True, definition=None,
          setup_text=None):
    root = cache / ver
    (root / "skills" / "a").mkdir(parents=True)
    (root / "skills" / "a" / "SKILL.md").write_text("---\nname: a\n%s\n---\n\n%s\n" % (front, body))
    (root / "agents").mkdir()
    (root / "agents" / "x.md").write_text(agent)
    (root / "hooks").mkdir()
    (root / "hooks" / "hooks.json").write_text(json.dumps(
        {"modules": [], "hooks": {"PreToolUse": [other_hook], "SessionStart": [session_hook]}}))
    (root / "hooks" / "session_start.py").write_text(start)
    (root / "rubric").mkdir()
    (root / "rubric" / "covenant.md").write_text(covenant)
    (root / "lib").mkdir()
    (root / "lib" / "helper.py").write_text('SOURCE = "%s"\n' % source)
    # not `store.py`: that name is in the start hook's read set, which the plan counts as a start part
    (root / "lib" / "vault.py").write_text('def store_root():\n    return "%s"\n' % store_root)
    (root / "lib" / "cloud_setup.py").write_text(_CLOUD_SETUP.format(algo=algo))
    if setup:
        (root / "lib" / "cloud_setup_text.py").write_text(
            setup_text if setup_text is not None else _SETUP_TEXT.format(
                pkg=pkg, other=other, doc=doc, store=store,
                definition="" if definition is None else "STAMP_DEFINITION = %d\n" % definition))
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
        {"version": "0.2.0", "since": "0.1.0", "startLoaded": [], "setupSteps": False,
         "stampDefinitionChanged": False}]
    assert list(data["cloudStart"][0]) == [
        "version", "since", "startLoaded", "setupSteps", "stampDefinitionChanged"]
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
    assert data["cloudStart"][0]["stampDefinitionChanged"] is None
    assert data["cloudStartChanged"] is True


def test_no_project_reads_as_changed(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0")
    data = _plan(capsys, cache, "0.1.0", "0.2.0")
    assert data["cloudStart"][0]["setupSteps"] is None
    assert data["cloudStart"][0]["stampDefinitionChanged"] is None
    assert data["cloudStartChanged"] is True


def test_start_loaded_parts_name_each_change(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0", start="start hook two", covenant="covenant two",
          session_hook="start two")
    data = _plan(capsys, cache, "0.1.0", "0.2.0", _project(tmp_path))
    entry = data["cloudStart"][0]
    assert entry["startLoaded"] == [
        "hooks/hooks.json#SessionStart", "hooks/session_start.py", "rubric/covenant.md"]
    assert entry["setupSteps"] is False
    assert data["cloudStartChanged"] is True


def test_start_loaded_parts_name_each_part_alone(capsys, tmp_path):
    for index, (change, part) in enumerate((
            ({"start": "start hook two"}, "hooks/session_start.py"),
            ({"covenant": "covenant two"}, "rubric/covenant.md"),
            ({"session_hook": "start two"}, "hooks/hooks.json#SessionStart"))):
        cache = tmp_path / ("cache%d" % index)
        _tree(cache, "0.1.0")
        _tree(cache, "0.2.0", **change)
        data = _plan(capsys, cache, "0.1.0", "0.2.0", _project(tmp_path))
        assert data["cloudStart"][0]["startLoaded"] == [part]
        assert data["cloudStartChanged"] is True


def test_parts_read_after_the_pin_swap_do_not_count(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0", front="description: b", body="other body", agent="agent two",
          other_hook="guard two")
    data = _plan(capsys, cache, "0.1.0", "0.2.0", _project(tmp_path))
    assert data["cloudStart"][0]["startLoaded"] == []
    assert data["cloudStart"][0]["setupSteps"] is False
    assert data["cloudStartChanged"] is False


def test_an_added_agent_does_not_count(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0")
    (cache / "0.2.0" / "agents" / "y.md").write_text("new")
    data = _plan(capsys, cache, "0.1.0", "0.2.0", _project(tmp_path))
    assert data["cloudStart"][0]["startLoaded"] == []
    assert data["cloudStartChanged"] is False


def test_one_entry_per_installed_release(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0", start="start hook two")
    _tree(cache, "0.3.0", start="start hook two", pkg="tool@3")
    data = _plan(capsys, cache, "0.1.0", "0.3.0", _project(tmp_path))
    assert [(e["since"], e["version"], e["startLoaded"], e["setupSteps"],
             e["stampDefinitionChanged"]) for e in data["cloudStart"]] == [
        ("0.1.0", "0.2.0", ["hooks/session_start.py"], False, False),
        ("0.2.0", "0.3.0", [], True, False)]
    assert data["cloudStartChanged"] is True


def test_a_new_stamp_definition_counts_even_with_identical_steps_and_parts(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0")
    _tree(cache, "0.2.0", definition=2)
    data = _plan(capsys, cache, "0.1.0", "0.2.0", _project(tmp_path))
    entry = data["cloudStart"][0]
    assert entry["startLoaded"] == []
    assert entry["stampDefinitionChanged"] is True
    assert entry["setupSteps"] is True
    assert data["cloudStartChanged"] is True


def _git_project_with_pin(tmp_path):
    project = _project(tmp_path)
    subprocess.run(["git", "-C", str(project), "init", "-q"], check=True, capture_output=True)
    pin = {"source": "https://github.com/acme/superheroes.git", "commit": "0123456789abcdef" * 2 + "01234567",
           "subdir": "plugins/superheroes", "version": "0.1.0"}
    result = cloud_plugin_pin.sync(str(project), pin)
    assert result["action"] == "written", result
    assert cloud_setup_text._pin_state(str(project))["state"] == "valid"
    return project


def test_a_release_reads_the_pin_hook_the_current_reader_finds_valid(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0", setup_text=_PIN_SETUP_TEXT)
    _tree(cache, "0.2.0", setup_text=_PIN_SETUP_TEXT)
    # each release's own reader finds the hook broken; the planner stands in the current reader's answer
    data = _plan(capsys, cache, "0.1.0", "0.2.0", _git_project_with_pin(tmp_path))
    assert data["cloudStart"][0]["setupSteps"] is False
    assert data["cloudStart"][0]["stampDefinitionChanged"] is False
    assert data["cloudStartChanged"] is False


def test_a_project_with_no_pin_hook_gets_no_override(capsys, tmp_path):
    cache = tmp_path / "cache"
    _tree(cache, "0.1.0", setup_text=_PIN_SETUP_TEXT)
    _tree(cache, "0.2.0", setup_text=_PIN_SETUP_TEXT)
    project = _project(tmp_path)
    subprocess.run(["git", "-C", str(project), "init", "-q"], check=True, capture_output=True)
    data = _plan(capsys, cache, "0.1.0", "0.2.0", project)
    assert data["cloudStart"][0]["setupSteps"] is None
    assert data["cloudStartChanged"] is True


def _old_inventory_trees(cache, first, second, steps=(b"steps\n", b"steps\n"), **second_change):
    _tree(cache, "0.1.0", setup_text=_BYTES_SETUP_TEXT.format(inventory=first, steps=steps[0]))
    _tree(cache, "0.2.0", setup_text=_BYTES_SETUP_TEXT.format(inventory=second, steps=steps[1]),
          **second_change)


def test_an_older_definitions_inventory_is_re_read_under_the_current_one(capsys, tmp_path):
    cache = tmp_path / "cache"
    # the two inventories differ as an old agent change would make them; the start-read parts do not
    _old_inventory_trees(cache, b"agent one\n", b"agent two\n")
    data = _plan(capsys, cache, "0.1.0", "0.2.0", _project(tmp_path))
    entry = data["cloudStart"][0]
    assert entry["startLoaded"] == []
    assert entry["stampDefinitionChanged"] is False
    assert entry["setupSteps"] is False
    assert data["cloudStartChanged"] is False


def test_an_older_definitions_re_read_keeps_a_setup_step_change(capsys, tmp_path):
    cache = tmp_path / "cache"
    # axis: re-reading an older inventory replaces only that entry; a setup-step change still counts
    _old_inventory_trees(cache, b"agent one\n", b"agent one\n",
                         steps=(b"install tool@1\n", b"install tool@2\n"))
    data = _plan(capsys, cache, "0.1.0", "0.2.0", _project(tmp_path))
    entry = data["cloudStart"][0]
    assert entry["startLoaded"] == []
    assert entry["stampDefinitionChanged"] is False
    assert entry["setupSteps"] is True
    assert data["cloudStartChanged"] is True


def test_an_older_definitions_inventory_moves_with_the_start_hook(capsys, tmp_path):
    cache = tmp_path / "cache"
    _old_inventory_trees(cache, b"agent one\n", b"agent one\n", start="start hook two")
    data = _plan(capsys, cache, "0.1.0", "0.2.0", _project(tmp_path))
    entry = data["cloudStart"][0]
    assert entry["startLoaded"] == ["hooks/session_start.py"]
    assert entry["setupSteps"] is True
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
    text = transition_notes.transition_text(_PLUGIN)
    note = text.index("\n### Adopt-version: the cloud environments' setup text is an owed step\n")
    start = text.rindex("\n## ", 0, note)
    end = text.find("\n## ", note)
    section = text[start:end if end != -1 else len(text)]
    assert "`cloudStart`" in section and "`cloudStartChanged`" in section
