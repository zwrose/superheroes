"""A fixer order may name the not-yet-existing test file of a driver-run break-it finding (#1910 WO-2)."""
import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "_order_lint_siblings_1910", os.path.join(_HERE, "test_round_driver_order_lint.py"))
_sib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sib)

RD, OL = _sib.RD, _sib.OL
_seed_session, _emit_fixer, _FIXER_SKEY = _sib._seed_session, _sib._emit_fixer, _sib._FIXER_SKEY
break_it = RD.break_it

NEW_TEST = "tests/test_new_1910.py"


def _block(path):
    return "\n".join([
        "break-it-test v1",
        "path: %s" % path,
        "run: python -m pytest %s" % path,
        "---",
        "def test_it():\n    assert False\n",
    ])


def _break_it_row(path=NEW_TEST, stamp="driver"):
    row = {"taxonomy": "break-it-test", "file": path, "line": 1, "title": "break it",
           "severity": "Important", "consequence": "the guard is untested",
           "suggestion": _block(path)}
    if stamp == "driver":
        row[break_it.RUN_FIELD] = break_it._record(
            "H", {"path": path, "run": "python -m pytest %s" % path, "sha256": "0" * 64},
            "failed", exit_code=1)
    elif stamp == "other-path":
        row[break_it.RUN_FIELD] = break_it._record(
            "H", {"path": "tests/test_other_1910.py", "run": "python -m pytest tests/test_other_1910.py",
                  "sha256": "0" * 64}, "failed", exit_code=1)
    elif stamp == "none-path":
        row[break_it.RUN_FIELD] = break_it._record(
            "H", {"path": None, "run": None, "sha256": None}, "not-run", reason="suggestion-redacted")
    return row


def _session(tmp_path, monkeypatch, row):
    session_dir, state = _seed_session(tmp_path, monkeypatch)
    repo = str(tmp_path / "proj")
    os.makedirs(repo, exist_ok=True)
    state.setdefault("config", {})["repoRoot"] = repo
    state["_fixBatch"] = [row]
    return session_dir, state, repo


def _emit(session_dir, state, row):
    return _emit_fixer(session_dir, state, pending_payload={"batch": [row]})


def test_t1_a_driver_stamped_break_it_test_still_to_be_created_reaches_the_fixer(tmp_path, monkeypatch):
    row = _break_it_row()
    session_dir, state, repo = _session(tmp_path, monkeypatch, row)
    assert not os.path.exists(os.path.join(repo, NEW_TEST))
    anchor = _emit(session_dir, state, row)
    assert "manifestSha256" in anchor


def test_t2_an_unresolved_edit_target_still_refuses(tmp_path, monkeypatch):
    row = {"file": "src/missing_1910.py", "line": 1, "title": "edit a file that is not there"}
    session_dir, state, _repo = _session(tmp_path, monkeypatch, row)
    with pytest.raises(ValueError) as exc:
        _emit(session_dir, state, row)
    assert "order-path-unresolved" in str(exc.value)
    assert "src/missing_1910.py" in str(exc.value)


@pytest.mark.parametrize("stamp", ["none", "other-path", "none-path"])
def test_t3_a_break_it_row_without_the_drivers_stamp_for_its_file_still_refuses(
        tmp_path, monkeypatch, stamp):
    row = _break_it_row(stamp=stamp)
    session_dir, state, _repo = _session(tmp_path, monkeypatch, row)
    with pytest.raises(ValueError) as exc:
        _emit(session_dir, state, row)
    assert "order-path-unresolved:%s" % NEW_TEST in str(exc.value)


def test_t4_a_stamped_path_through_a_symlink_out_of_the_repo_still_refuses(tmp_path, monkeypatch):
    path = "tests_link/test_new.py"
    row = _break_it_row(path=path)
    session_dir, state, repo = _session(tmp_path, monkeypatch, row)
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(str(outside), os.path.join(repo, "tests_link"))
    with pytest.raises(ValueError) as exc:
        _emit(session_dir, state, row)
    assert "order-path-unresolved:%s:escapes-root" % path in str(exc.value)


def _lint(text, root, **kw):
    return OL.check_text(text, root, **kw)


def test_t5_create_items_exempt_the_existence_check_only(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    root = str(root)
    text = "Write `%s` and read `src/other_1910.py`.\n" % NEW_TEST
    assert [f["detail"] for f in _lint(text, root, kind="fixer")["findings"]] == [
        NEW_TEST, "src/other_1910.py"]
    found = _lint(text, root, kind="fixer", create_items=[NEW_TEST])["findings"]
    assert [f["detail"] for f in found] == ["src/other_1910.py"]
    os.symlink(str(tmp_path), os.path.join(root, "out_link"))
    found = _lint("See `out_link/new.py`.\n", root, kind="fixer",
                  create_items=["out_link/new.py"])["findings"]
    assert [(f["token"], f["detail"]) for f in found] == [
        (OL.TOKEN_PATH_UNRESOLVED, "out_link/new.py:escapes-root")]


@pytest.mark.parametrize("item,reason", [
    ("/abs/new.py", "absolute"), ("a\\b.py", "backslash"), ("../up/new.py", "escapes-root"),
    ("", "empty")])
def test_t5_an_invalid_create_item_is_a_finding(tmp_path, item, reason):
    found = _lint("Nothing cited here.\n", str(tmp_path), kind="fixer",
                  create_items=[item])["findings"]
    assert [(f["token"], f["detail"]) for f in found] == [
        (OL.TOKEN_PATH_UNRESOLVED, "%s:%s" % (item, reason))]


def test_t5_create_items_alone_do_not_make_the_fixer_literal_ambiguous(tmp_path):
    text = 'Nothing is cited here. {"fixes": []}\n'
    found = _lint(text, str(tmp_path), kind="fixer", allow_payload_contract=True,
                  create_items=[NEW_TEST])["findings"]
    assert not [f for f in found if f["token"] == OL.TOKEN_RESULT_SHAPE_AMBIGUOUS]
    found = _lint(text, str(tmp_path), kind="fixer", allow_payload_contract=True,
                  expect_items=[NEW_TEST])["findings"]
    assert [f["token"] for f in found] == [OL.TOKEN_RESULT_SHAPE_AMBIGUOUS]
