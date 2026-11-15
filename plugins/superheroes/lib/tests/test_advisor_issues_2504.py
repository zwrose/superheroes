# plugins/superheroes/lib/tests/test_advisor_issues_2504.py
"""Conformance: configuration item 20 (advisorIssues), its one total reader, and the verb.

The invariant: item 20's state is read through exactly one total reader, and a stored value that
cannot be read is reported unreadable, never read as nothing declared."""
import copy
import importlib.util
import json
import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_LIB = os.path.join(_REPO_ROOT, "plugins/superheroes/lib")


def _load(name):
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    path = os.path.join(_LIB, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PC = _load("project_config")
CM = _load("core_md")
CORE = PC.core_md  # the module instance project_config itself calls

_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}

SLUG = "advisorIssues"
VALID = {"collector": 11, "inboxes": [12, 13]}


def _setup_repo(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    return repo, store


def _edit_block(repo, store, mutate):
    """Rewrite the core file's JSON block through ``mutate(block_dict)``; the rest is kept."""
    path = CM.core_path(repo, store)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = CM._JSON_BLOCK.search(text)
    block = json.loads(m.group(1))
    mutate(block)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text[:m.start(1)] + json.dumps(block, indent=2) + text[m.end(1):])


def _store_raw(repo, store, value):
    """Store ``value`` (any JSON value, a null included) raw under projectConfiguration."""
    _edit_block(repo, store,
                lambda block: block.setdefault("projectConfiguration", {}).update({SLUG: value}))


def _replace_block_text(repo, store, block_text):
    path = CM.core_path(repo, store)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = CM._JSON_BLOCK.search(text)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text[:m.start(1)] + block_text + text[m.end(1):])


def _core_text(repo, store):
    with open(CM.core_path(repo, store), encoding="utf-8") as fh:
        return fh.read()


def _make_non_object(repo, store):
    _edit_block(repo, store, lambda block: block.update({"projectConfiguration": []}))


def _make_duplicate_key(repo, store):
    _replace_block_text(
        repo, store,
        '{"schemaVersion": %d, "verifyCommand": "npm test", "stackTags": ["node"],'
        ' "projectConfiguration": {"advisorIssues": {"collector": 5, "inboxes": []},'
        ' "advisorIssues": {"collector": 6, "inboxes": []}}}' % CM.SCHEMA_VERSION)


def _make_bad_verify_command(repo, store):
    _edit_block(repo, store, lambda block: block.update({"verifyCommand": ""}))


def _make_unparseable_core(repo, store):
    with open(CM.core_path(repo, store), "w", encoding="utf-8") as fh:
        fh.write("not core\n")


def _make_stored_invalid(repo, store):
    _store_raw(repo, store, {"collector": 0, "inboxes": []})


def _make_stored_null(repo, store):
    _store_raw(repo, store, None)


_UNREADABLE_CASES = {
    "non-object-project-configuration": _make_non_object,
    "duplicate-key": _make_duplicate_key,
    "unparseable-core": _make_unparseable_core,
    "stored-invalid": _make_stored_invalid,
    "stored-null": _make_stored_null,
}


def _item(payload, slug=SLUG):
    for item in payload["items"]:
        if item["slug"] == slug:
            return item
    raise KeyError(slug)


# --- the registry entry -----------------------------------------------------------------------


def test_registry_entry_for_item_20():
    item = next(entry for entry in PC.ITEMS if entry["slug"] == "advisorIssues")
    assert item == {
        "number": 20,
        "slug": "advisorIssues",
        "name": "Advisor issues",
        "home": PC.HOME_PROJECT_CONFIGURATION,
        "shape": "advisorIssues",
        "plugin_default": None,
    }
    assert PC.ADVISOR_ISSUES_SLUG == "advisorIssues"
    assert (PC.ADVISOR_ISSUES_DECLARED, PC.ADVISOR_ISSUES_UNSET, PC.ADVISOR_ISSUES_UNREADABLE) == (
        "declared", "unset", "unreadable")


# --- the validator edges, each through set_item ------------------------------------------------


def _assert_set_refused_and_unchanged(tmp_path, value):
    repo, store = _setup_repo(tmp_path)
    before = _core_text(repo, store)
    got = PC.set_item(repo, SLUG, value, root=store)
    assert got == {"action": "refused", "reason": "malformed-value"}
    assert _core_text(repo, store) == before
    assert PC.advisor_issues(repo, root=store)["status"] == "unset"


def test_e1_not_a_dict_refuses(tmp_path):
    _assert_set_refused_and_unchanged(tmp_path, [11, 12])


def test_e1_null_and_scalar_refuse(tmp_path):
    for value in (None, 11, "11"):
        assert PC.validate_item_value(PC._item_by_slug(SLUG), value) == "malformed-value"


def test_e2_missing_key_refuses(tmp_path):
    _assert_set_refused_and_unchanged(tmp_path, {"collector": 11})


def test_e2_extra_key_refuses(tmp_path):
    _assert_set_refused_and_unchanged(tmp_path, {"collector": 11, "inboxes": [], "note": "x"})


def test_e3_collector_not_a_positive_int_refuses(tmp_path):
    _assert_set_refused_and_unchanged(tmp_path, {"collector": "11", "inboxes": []})


def test_e3_collector_zero_negative_and_bool_refuse(tmp_path):
    item = PC._item_by_slug(SLUG)
    for bad in (0, -3, True, 1.5, None):
        assert PC.validate_item_value(item, {"collector": bad, "inboxes": []}) == "malformed-value"


def test_e4_inboxes_not_a_list_refuses(tmp_path):
    _assert_set_refused_and_unchanged(tmp_path, {"collector": 11, "inboxes": 12})


def test_e4_inbox_entry_not_a_positive_int_refuses(tmp_path):
    _assert_set_refused_and_unchanged(tmp_path, {"collector": 11, "inboxes": [12, "13"]})


def test_e4_inbox_entry_zero_or_bool_refuses(tmp_path):
    item = PC._item_by_slug(SLUG)
    for bad in (0, -1, True):
        assert PC.validate_item_value(item, {"collector": 11, "inboxes": [12, bad]}) == "malformed-value"


def test_e5_duplicate_inbox_refuses(tmp_path):
    _assert_set_refused_and_unchanged(tmp_path, {"collector": 11, "inboxes": [12, 13, 12]})


def test_e6_inbox_equal_to_collector_refuses(tmp_path):
    _assert_set_refused_and_unchanged(tmp_path, {"collector": 11, "inboxes": [12, 11]})


@pytest.mark.parametrize("value", [
    {"collector": 11, "inboxes": []},
    {"collector": 11, "inboxes": [12, 13]},
])
def test_valid_value_sets_and_reads_back(tmp_path, value):
    repo, store = _setup_repo(tmp_path)
    got = PC.set_item(repo, SLUG, value, root=store)
    assert got["action"] == "written"
    read_back = PC.get_item(repo, SLUG, root=store)
    assert read_back["raw"] == value
    assert read_back["effective"] == value
    assert read_back["source"] == "stamped"
    assert read_back["malformed"] is False
    assert PC.advisor_issues(repo, root=store) == {
        "status": "declared", "collector": value["collector"], "inboxes": value["inboxes"],
        "reason": None, "detail": None}


def test_set_keeps_sibling_keys(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config(repo, {"stackingTool": "gh-stack"}, root=store)
    assert PC.set_item(repo, SLUG, VALID, root=store)["action"] == "written"
    assert PC.get_item(repo, "stackingTool", root=store)["raw"] == "gh-stack"


# --- advisor_issues statuses -----------------------------------------------------------------


_RESULT_KEYS = {"status", "collector", "inboxes", "reason", "detail"}


def test_advisor_issues_declared_returns_the_values(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _store_raw(repo, store, copy.deepcopy(VALID))
    got = PC.advisor_issues(repo, root=store)
    assert set(got) == _RESULT_KEYS
    assert got == {"status": "declared", "collector": 11, "inboxes": [12, 13],
                   "reason": None, "detail": None}


def test_advisor_issues_unset_when_no_key(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = PC.advisor_issues(repo, root=store)
    assert got == {"status": "unset", "collector": None, "inboxes": [],
                   "reason": None, "detail": None}


def test_advisor_issues_unset_profile_absent_without_core(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    got = PC.advisor_issues(repo, root=store)
    assert got == {"status": "unset", "collector": None, "inboxes": [],
                   "reason": "profile-absent", "detail": None}


def test_advisor_issues_stored_invalid_value_is_unreadable_malformed(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _make_stored_invalid(repo, store)
    got = PC.advisor_issues(repo, root=store)
    assert got == {"status": "unreadable", "collector": None, "inboxes": [],
                   "reason": "malformed-value", "detail": None}


def test_r2_stored_null_is_unreadable_malformed(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _make_stored_null(repo, store)
    assert json.loads(CM._JSON_BLOCK.search(_core_text(repo, store)).group(1))[
        "projectConfiguration"][SLUG] is None
    got = PC.advisor_issues(repo, root=store)
    assert got == {"status": "unreadable", "collector": None, "inboxes": [],
                   "reason": "malformed-value", "detail": None}


def test_r1_non_object_project_configuration_is_unreadable(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _make_non_object(repo, store)
    got = PC.advisor_issues(repo, root=store)
    assert set(got) == _RESULT_KEYS
    assert got["status"] == "unreadable"
    assert got["reason"] == "profile-unparseable"
    assert got["detail"].startswith("project-configuration-not-an-object: list at ")
    assert got["collector"] is None and got["inboxes"] == []


def test_r3_malformed_verify_command_is_unreadable(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _make_bad_verify_command(repo, store)
    got = PC.advisor_issues(repo, root=store)
    assert got["status"] == "unreadable"
    assert got["reason"] == "profile-unparseable"
    assert got["detail"].startswith("VerifyCommandMalformed: ")


def test_r4_duplicate_core_key_is_unreadable(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _make_duplicate_key(repo, store)
    got = PC.advisor_issues(repo, root=store)
    assert got["status"] == "unreadable"
    assert got["reason"] == "profile-unparseable"
    assert got["detail"] == "duplicate-core-key:advisorIssues"
    assert got["collector"] is None and got["inboxes"] == []


def test_advisor_issues_unparseable_core_is_unreadable(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _make_unparseable_core(repo, store)
    got = PC.advisor_issues(repo, root=store)
    assert got["status"] == "unreadable"
    assert got["reason"] == "profile-unparseable"
    assert got["detail"].startswith("core-md-unparseable: ")


def test_advisor_issues_internal_exception_is_unreadable(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)

    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(PC.core_md, "read_project_config_value", _boom)
    got = PC.advisor_issues(repo, root=store)
    assert got == {"status": "unreadable", "collector": None, "inboxes": [],
                   "reason": "profile-unparseable", "detail": "RuntimeError: boom"}


def test_advisor_issues_writes_nothing(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _store_raw(repo, store, copy.deepcopy(VALID))
    before = _core_text(repo, store)
    PC.advisor_issues(repo, root=store)
    assert _core_text(repo, store) == before


# --- get_item and view ----------------------------------------------------------------------


def test_get_item_and_view_report_stamped_for_declared(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _store_raw(repo, store, copy.deepcopy(VALID))
    got = PC.get_item(repo, SLUG, root=store)
    assert got["raw"] == VALID
    assert got["effective"] == {"collector": 11, "inboxes": [12, 13]}
    assert got["source"] == "stamped"
    assert got["malformed"] is False
    viewed = [i for i in PC.view(repo, root=store)["items"] if i["slug"] == SLUG]
    assert len(viewed) == 1
    assert viewed[0]["number"] == 20 and viewed[0]["name"] == "Advisor issues"
    assert viewed[0]["source"] == "stamped" and viewed[0]["malformed"] is False


def test_get_item_and_view_report_unset_when_no_key(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = PC.get_item(repo, SLUG, root=store)
    assert got["raw"] is None and got["effective"] is None
    assert got["source"] == "unset" and got["malformed"] is False
    assert _item(PC.view(repo, root=store))["malformed"] is False


@pytest.mark.parametrize("case", sorted(_UNREADABLE_CASES))
def test_v1_read_reports_unreadable_item_20_as_malformed(tmp_path, case):
    repo, store = _setup_repo(tmp_path)
    _UNREADABLE_CASES[case](repo, store)
    got = PC.get_item(repo, SLUG, root=store)
    assert got["malformed"] is True
    assert got["effective"] is None
    assert got["source"] == "unset"
    viewed = _item(PC.view(repo, root=store))
    assert viewed["malformed"] is True
    assert viewed["effective"] is None
    assert viewed["source"] == "unset"


def test_unreadable_stored_value_keeps_its_raw_value(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _make_stored_invalid(repo, store)
    got = PC.get_item(repo, SLUG, root=store)
    assert got["raw"] == {"collector": 0, "inboxes": []}
    assert got["malformed"] is True


def test_read_calls_the_reader_once(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    calls = []
    real = PC.core_md.read_project_config_value

    def _counting(cwd, key, root=None):
        calls.append(key)
        return real(cwd, key, root)

    monkeypatch.setattr(PC.core_md, "read_project_config_value", _counting)
    PC.read(repo, root=store)
    assert calls.count("advisorIssues") == 1


def test_configure_view_screen_shows_unreadable_as_malformed(tmp_path):
    CV = _load("configure_view")
    repo, store = _setup_repo(tmp_path)
    _make_stored_invalid(repo, store)
    screen = CV.render(repo, root=store)
    row = next(line for line in screen.splitlines() if line.startswith("20. Advisor issues"))
    assert "malformed (stamped value not applied)" in row


# --- the CLI verb ---------------------------------------------------------------------------


def test_cli_advisor_issues_prints_the_same_dict(tmp_path, capsys):
    repo, store = _setup_repo(tmp_path)
    _store_raw(repo, store, copy.deepcopy(VALID))
    rc = PC.main(["advisor-issues", "--cwd", repo, "--root", store])
    assert rc == 0
    printed = capsys.readouterr().out
    assert json.loads(printed) == PC.advisor_issues(repo, root=store)
    assert printed == json.dumps(PC.advisor_issues(repo, root=store), indent=2) + "\n"


def test_cli_advisor_issues_unreadable_still_exits_zero(tmp_path, capsys):
    repo, store = _setup_repo(tmp_path)
    _make_stored_null(repo, store)
    rc = PC.main(["advisor-issues", "--cwd", repo, "--root", store])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["status"] == "unreadable"


# --- dependencies() collector ----------------------------------------------------------------


def test_dependencies_collector_declared_from_item_20(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _store_raw(repo, store, copy.deepcopy(VALID))
    assert PC.dependencies(repo, root=store)["collector"] == {
        "status": "declared", "collector": 11}


def test_dependencies_collector_declared_wins_over_declared_dependencies(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_declared_dependencies(repo, {"collector": True}, root=store)
    _store_raw(repo, store, copy.deepcopy(VALID))
    assert PC.dependencies(repo, root=store)["collector"] == {
        "status": "declared", "collector": 11}


def test_dependencies_collector_unset_item_20_keeps_today_absent(tmp_path):
    repo, store = _setup_repo(tmp_path)
    assert PC.dependencies(repo, root=store)["collector"] == {
        "status": "absent", "fallback": PC._DEPENDENCY_FALLBACKS["collector"]}


def test_dependencies_collector_unset_item_20_keeps_today_declared(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_declared_dependencies(repo, {"collector": True}, root=store)
    assert PC.dependencies(repo, root=store)["collector"] == {"status": "declared"}


def test_dependencies_collector_marks_unreadable_item_20(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _make_stored_invalid(repo, store)
    assert PC.dependencies(repo, root=store)["collector"] == {
        "status": "absent", "fallback": PC._DEPENDENCY_FALLBACKS["collector"],
        "advisorIssues": "unreadable"}


def test_dependencies_collector_unreadable_keeps_declared_status(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_declared_dependencies(repo, {"collector": True}, root=store)
    _make_stored_null(repo, store)
    assert PC.dependencies(repo, root=store)["collector"] == {
        "status": "declared", "advisorIssues": "unreadable"}


# --- core_md.read_project_config_value --------------------------------------------------------


def test_reader_present_returns_a_deep_copy(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _store_raw(repo, store, copy.deepcopy(VALID))
    got = CM.read_project_config_value(repo, SLUG, root=store)
    assert set(got) == {"present", "value", "reason", "detail", "behind"}
    assert got["present"] is True and got["value"] == VALID
    assert got["reason"] is None and got["detail"] is None and got["behind"] is False
    got["value"]["inboxes"].append(99)
    again = CM.read_project_config_value(repo, SLUG, root=store)
    assert again["value"] == VALID


def test_reader_absent_key(tmp_path):
    repo, store = _setup_repo(tmp_path)
    assert CM.read_project_config_value(repo, SLUG, root=store) == {
        "present": False, "value": None, "reason": None, "detail": None, "behind": False}


def test_reader_stored_null_is_present_with_value_none(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _make_stored_null(repo, store)
    assert CM.read_project_config_value(repo, SLUG, root=store) == {
        "present": True, "value": None, "reason": None, "detail": None, "behind": False}


def test_reader_core_md_absent(tmp_path):
    got = CM.read_project_config_value(str(tmp_path), SLUG, root=str(tmp_path / "store"))
    assert got == {"present": False, "value": None, "reason": "core-md-absent",
                   "detail": None, "behind": False}


def test_reader_non_object_project_configuration_detail(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _make_non_object(repo, store)
    got = CM.read_project_config_value(repo, SLUG, root=store)
    assert got["reason"] == "project-config-unreadable" and got["present"] is False
    assert got["detail"].startswith("project-configuration-not-an-object: list at ")


def test_reader_duplicate_key_detail(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _make_duplicate_key(repo, store)
    got = CM.read_project_config_value(repo, SLUG, root=store)
    assert got["reason"] == "project-config-unreadable" and got["present"] is False
    assert got["detail"] == "duplicate-core-key:advisorIssues"


def test_reader_malformed_verify_command_detail(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _make_bad_verify_command(repo, store)
    got = CM.read_project_config_value(repo, SLUG, root=store)
    assert got["reason"] == "project-config-unreadable"
    assert got["detail"].startswith("VerifyCommandMalformed: ")


def test_reader_unparseable_core_detail(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _make_unparseable_core(repo, store)
    got = CM.read_project_config_value(repo, SLUG, root=store)
    assert got["reason"] == "project-config-unreadable"
    assert got["detail"].startswith("core-md-unparseable: corrupt or unreadable core.md at ")


def test_reader_not_a_regular_file_detail(tmp_path):
    repo, store = _setup_repo(tmp_path)
    path = CM.core_path(repo, store)
    os.remove(path)
    os.mkdir(path)
    got = CM.read_project_config_value(repo, SLUG, root=store)
    assert got["reason"] == "project-config-unreadable"
    assert got["detail"].startswith("core-md-unreadable")


def test_reader_repo_root_unavailable_detail(tmp_path, monkeypatch):
    def _no_root(*a, **k):
        raise PC.core_md.RepoRootUnavailable("no root")

    monkeypatch.setattr(PC.core_md, "_size_exclude_core_path", _no_root)
    got = PC.core_md.read_project_config_value(str(tmp_path), SLUG, root=str(tmp_path / "s"))
    assert got["reason"] == "project-config-unreadable"
    assert got["detail"].startswith("repo-root-unavailable: ")


def test_reader_other_exception_detail(tmp_path, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(PC.core_md, "_size_exclude_core_path", _boom)
    got = PC.core_md.read_project_config_value(str(tmp_path), SLUG, root=str(tmp_path / "s"))
    assert got == {"present": False, "value": None, "reason": "project-config-unreadable",
                   "detail": "RuntimeError: boom", "behind": False}


def test_reader_behind_schema(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _store_raw(repo, store, copy.deepcopy(VALID))
    _edit_block(repo, store, lambda block: block.update({"schemaVersion": CM.SCHEMA_VERSION + 1}))
    got = CM.read_project_config_value(repo, SLUG, root=store)
    assert got["present"] is True and got["behind"] is True


def test_reader_writes_nothing(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _store_raw(repo, store, copy.deepcopy(VALID))
    before = _core_text(repo, store)
    CM.read_project_config_value(repo, SLUG, root=store)
    assert _core_text(repo, store) == before
