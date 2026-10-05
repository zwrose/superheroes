# plugins/superheroes/lib/tests/test_size_exclude_calibration_1583.py
"""sizeExclude json key (#1583): validate, read, write, CLI, carry-forward, view.

Token literals are spelled out as strings on purpose: a test that reaches them through the
module constants stays green under any value (rubric/bite-proof.md, external-contract constant).

Detector axes (bite-proof):
- test_validate_* — refusal: each malformed shape names its token and accepted shape
- test_read_* / test_write_* / test_cli_* — total read-only read, refused write, stdin refusals
- test_carry_forward_* — preservation: every core.md rewrite path keeps sizeExclude raw
- test_view_* — display: the configure view always shows the size count exclusions
"""
import copy
import importlib.util
import io
import json
import os
import subprocess
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_LIB = os.path.join(_REPO_ROOT, "plugins/superheroes/lib")
_CORE_MD = os.path.join(_LIB, "core_md.py")

_KEY = "sizeExclude"


def _load(name):
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    path = os.path.join(_LIB, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CM = _load("core_md")
CV = _load("configure_view")
MR = _load("mode_registry")

_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}

_ACCEPTED_LIST = 'a list of repo-relative path globs, such as ["docs/**", "*.generated.ts"]'
_ACCEPTED_GLOB = "a repo-relative glob, no leading /"

_GLOBS = ["docs/**", "*.generated.ts"]

_NONE_LINE = "(none — every non-test path counts; lockfiles are always left out)"
_EMPTY_LINE = "(declared empty — nothing extra excluded; lockfiles are always left out)"


def _init_repo(d):
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)
    subprocess.run(
        ["git", "-C", str(d), "remote", "add", "origin", "git@github.com:o/r.git"],
        check=True,
    )


def _patch_block(repo, store, updates):
    path = CM.core_path(repo, store)
    text = open(path).read()
    inner = CM._JSON_BLOCK.search(text).group(1)
    block = json.loads(inner)
    block.update(updates)
    open(path, "w").write(text.replace(inner, json.dumps(block, indent=2)))
    return path


def _setup_repo(tmp_path, extra_block=None, status="confirmed"):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _init_repo(tmp_path)
    MR.write_registry(repo, MR.IN_REPO, "rk", root=store)
    CM.write(repo, dict(_CORE_FACTS), status, root=store, now="2026-06-26")
    if extra_block:
        _patch_block(repo, store, extra_block)
    return repo, store


def _setup_core_absent(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _init_repo(tmp_path)
    MR.write_registry(repo, MR.IN_REPO, "rk", root=store)
    return repo, store


def _parsed(repo, store):
    text = open(CM.core_path(repo, store)).read()
    return json.loads(CM._JSON_BLOCK.search(text).group(1))


def _only(items):
    assert len(items) == 1, items
    return items[0]


def _file_set(tree):
    found = set()
    for dirpath, dirnames, filenames in os.walk(tree):
        for name in dirnames + filenames:
            found.add(os.path.join(dirpath, name))
    return found


# --- literal pins ---------------------------------------------------------------------------

def test_literal_pins():
    # axis: the external-contract literals WO-A and core.md readers match on
    assert CM.SIZE_EXCLUDE_KEY == "sizeExclude"
    assert CM.SIZE_EXCLUDE_REASON_MALFORMED == "size-exclude-malformed"
    assert CM.SIZE_EXCLUDE_REASON_INPUT_UNPARSEABLE == "size-exclude-input-unparseable"
    assert CM.SIZE_EXCLUDE_REASON_ROUND_TRIP == "size-exclude-round-trip-refused"
    assert CM.SIZE_EXCLUDE_REASON_UNREADABLE == "size-exclude-unreadable"
    assert CM.SIZE_EXCLUDE_MALFORMED_NOT_A_LIST == "size-exclude-not-a-list"
    assert CM.SIZE_EXCLUDE_MALFORMED_ENTRY_NOT_STRING == (
        "size-exclude-entry-not-a-nonempty-string")
    assert CM.SIZE_EXCLUDE_MALFORMED_ENTRY_ABSOLUTE == "size-exclude-entry-absolute"


# --- validator ------------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["docs/**", None, 5, {"a": 1}, True], ids=repr)
def test_validate_not_a_list(value):
    # axis: E1 a non-list value is refused with the not-a-list token and the accepted shape
    item = _only(CM.validate_size_exclude(value))
    assert item["reason"] == "size-exclude-not-a-list"
    assert item["index"] is None
    assert item["accepted"] == _ACCEPTED_LIST


@pytest.mark.parametrize("form", [5, None, True, ["a"], {"a": 1}], ids=repr)
def test_validate_entry_not_a_string(form):
    # axis: E2 a non-string entry is refused with the nonempty-string token at its index
    item = _only(CM.validate_size_exclude(["docs/**", form]))
    assert item["reason"] == "size-exclude-entry-not-a-nonempty-string"
    assert item["index"] == 1
    assert item["accepted"] == _ACCEPTED_GLOB


@pytest.mark.parametrize("form", ["", " ", "   ", "\t", "\n", " \t\n "], ids=repr)
def test_validate_entry_empty_or_whitespace(form):
    # axis: E2 an empty or whitespace-only entry is refused with the nonempty-string token
    item = _only(CM.validate_size_exclude([form, "docs/**"]))
    assert item["reason"] == "size-exclude-entry-not-a-nonempty-string"
    assert item["index"] == 0
    assert item["accepted"] == _ACCEPTED_GLOB


@pytest.mark.parametrize("form", ["/", "/docs/**", "/abs/path", "//x"], ids=repr)
def test_validate_entry_absolute(form):
    # axis: E3 a glob with a leading / can never match a repo-relative path and is refused
    item = _only(CM.validate_size_exclude(["docs/**", form]))
    assert item["reason"] == "size-exclude-entry-absolute"
    assert item["index"] == 1
    assert item["accepted"] == _ACCEPTED_GLOB


@pytest.mark.parametrize(
    "value",
    [[], _GLOBS, ["a/**", "a/**"], [" docs/** "], ["*"], ["**/*.min.js"], ["./x", "../y"]],
    ids=repr)
def test_validate_valid_values(value):
    # axis: [] is valid, duplicates are allowed, entries are not normalized — not over-broad
    assert CM.validate_size_exclude(value) == []


def test_validate_collects_every_problem_in_order():
    got = CM.validate_size_exclude(["ok", "", "/x", 5, "  "])
    assert [(i["index"], i["reason"]) for i in got] == [
        (1, "size-exclude-entry-not-a-nonempty-string"),
        (2, "size-exclude-entry-absolute"),
        (3, "size-exclude-entry-not-a-nonempty-string"),
        (4, "size-exclude-entry-not-a-nonempty-string"),
    ]


def test_validate_never_raises_on_odd_values():
    class Odd:
        def __iter__(self):
            raise RuntimeError("not iterable here")

    assert CM.validate_size_exclude(Odd())[0]["reason"] == "size-exclude-not-a-list"
    assert CM.validate_size_exclude([Odd(), object()])[0]["index"] == 0


# --- reader ---------------------------------------------------------------------------------

def test_read_key_absent(tmp_path):
    # axis: an absent key is declared False, globs None, no reason
    repo, store = _setup_repo(tmp_path)
    got = CM.read_size_exclude(repo, store)
    assert got == {"declared": False, "globs": None, "malformed": [], "reason": None,
                   "detail": None, "behind": False}


def test_read_core_md_absent(tmp_path):
    # axis: E5 an absent core.md reads like an absent key, reason core-md-absent
    repo, store = _setup_core_absent(tmp_path)
    got = CM.read_size_exclude(repo, store)
    assert got["declared"] is False
    assert got["globs"] is None
    assert got["reason"] == "core-md-absent"
    assert got["detail"] is None


def test_read_valid_globs_as_stored(tmp_path):
    stored = ["b/**", "b/**", " x ", "*.ts"]
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: stored})
    got = CM.read_size_exclude(repo, store)
    assert got["declared"] is True
    assert got["reason"] is None
    assert got["malformed"] == []
    assert got["globs"] == stored


def test_read_declared_empty(tmp_path):
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: []})
    got = CM.read_size_exclude(repo, store)
    assert got["declared"] is True
    assert got["globs"] == []
    assert got["reason"] is None


def test_read_malformed_has_no_globs(tmp_path):
    # axis: a malformed key reads globs None, never an empty list
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: ["ok", "/abs"]})
    got = CM.read_size_exclude(repo, store)
    assert got["declared"] is True
    assert got["globs"] is None
    assert got["reason"] == "size-exclude-malformed"
    item = _only(got["malformed"])
    assert item == {"index": 1, "reason": "size-exclude-entry-absolute", "accepted": _ACCEPTED_GLOB}


@pytest.mark.parametrize("raw", [None, "docs/**", {"a": 1}, True, 5], ids=repr)
def test_read_non_list_key_is_malformed(tmp_path, raw):
    # axis: E1 through the reader — a present key holding a non-list never reads as nothing
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: raw})
    got = CM.read_size_exclude(repo, store)
    assert got["declared"] is True
    assert got["globs"] is None
    assert got["reason"] == "size-exclude-malformed"
    assert _only(got["malformed"])["reason"] == "size-exclude-not-a-list"


def test_read_entry_not_a_string_through_reader(tmp_path):
    # axis: E2 through the reader
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: ["ok", 5, ""]})
    got = CM.read_size_exclude(repo, store)
    assert got["reason"] == "size-exclude-malformed"
    assert [(i["index"], i["reason"]) for i in got["malformed"]] == [
        (1, "size-exclude-entry-not-a-nonempty-string"),
        (2, "size-exclude-entry-not-a-nonempty-string"),
    ]


def test_read_unparseable_core_md(tmp_path):
    # axis: E6 an unparseable core.md reads globs None with the unreadable reason and a detail
    repo, store = _setup_repo(tmp_path)
    open(CM.core_path(repo, store), "w").write("no json fence\n")
    got = CM.read_size_exclude(repo, store)
    assert got["reason"] == "size-exclude-unreadable"
    assert got["globs"] is None
    assert got["declared"] is False
    assert got["detail"].startswith("core-md-unparseable:")


def test_read_two_blocks_refused(tmp_path):
    repo, store = _setup_repo(tmp_path)
    open(CM.core_path(repo, store), "a").write("\n```json superheroes-core\n{}\n```\n")
    got = CM.read_size_exclude(repo, store)
    assert got["reason"] == "size-exclude-unreadable"
    assert got["globs"] is None
    assert got["detail"].startswith("multiple-core-blocks:")


def test_read_duplicate_key_is_structural_refusal(tmp_path):
    # axis: E7 a duplicate core key is the structural refusal, globs None, detail names the key
    repo, store = _setup_repo(tmp_path)
    path = CM.core_path(repo, store)
    text = open(path).read()
    inner = (
        '{\n  "schemaVersion": %d,\n  "verifyCommand": "a",\n  "stackTags": [],\n'
        '  "sizeExclude": ["a/**"],\n  "sizeExclude": ["b/**"]\n}' % CM.SCHEMA_VERSION)
    open(path, "w").write(text.replace(CM._JSON_BLOCK.search(text).group(1), inner))
    got = CM.read_size_exclude(repo, store)
    assert got["reason"] == "size-exclude-unreadable"
    assert got["globs"] is None
    assert got["detail"] == "duplicate-core-key:sizeExclude"


def test_read_verify_command_42_reparse_raises(tmp_path):
    # axis: E8 a parse that raises VerifyCommandMalformed is a named read refusal, never a raise
    repo, store = _setup_repo(tmp_path, extra_block={"verifyCommand": 42})
    got = CM.read_size_exclude(repo, store)
    assert got["reason"] == "size-exclude-unreadable"
    assert got["globs"] is None
    assert got["declared"] is False
    assert got["detail"].startswith("VerifyCommandMalformed:")


def test_read_plain_non_git_dir_is_greenfield_core_absent(tmp_path):
    # measured: a directory with no .git ancestor is greenfield (repo root = cwd), so the reader
    # reads it as core.md absent; the repo-root-unavailable refusal needs a .git git declines
    got = CM.read_size_exclude(str(tmp_path), str(tmp_path / "store"))
    assert got["reason"] == "core-md-absent"
    assert got["globs"] is None


def test_read_repo_root_unavailable(tmp_path):
    # axis: E9 a cwd whose repo root cannot be resolved (a .git entry git declines) reads
    # globs None with the unreadable reason
    os.mkdir(str(tmp_path / ".git"))
    got = CM.read_size_exclude(str(tmp_path), str(tmp_path / "store"))
    assert got["reason"] == "size-exclude-unreadable"
    assert got["globs"] is None
    assert got["declared"] is False
    assert got["detail"].startswith("repo-root-unavailable:")


def test_read_any_other_exception_is_total(tmp_path, monkeypatch):
    # axis: E10 the outer wrap — a helper raising RuntimeError never escapes the reader
    repo, store = _setup_repo(tmp_path)

    def _boom(*a, **k):
        raise RuntimeError("synthetic")

    monkeypatch.setattr(CM, "_core_candidates", _boom)
    got = CM.read_size_exclude(repo, store)
    assert got["reason"] == "size-exclude-unreadable"
    assert got["globs"] is None
    assert got["detail"] == "RuntimeError: synthetic"


def test_read_no_core_md_no_registry_writes_nothing(tmp_path):
    # axis: E13 the read-only path — with hero evidence and no registry, the default resolve
    # would backfill-write registry.json; the reader must leave the store tree unchanged
    repo = str(tmp_path / "repo")
    store = str(tmp_path / "store")
    os.makedirs(repo)
    _init_repo(repo)
    hero_layer = os.path.join(repo, ".claude", "superheroes", "review-crew.md")
    os.makedirs(os.path.dirname(hero_layer))
    open(hero_layer, "w").write("layer\n")
    assert MR.resolve(repo, store, persist_backfill=False)["source"] == "evidence"
    before = _file_set(store)
    got = CM.read_size_exclude(repo, store)
    assert _file_set(store) == before
    assert not os.path.exists(os.path.join(MR.project_store_dir(repo, store), "registry.json"))
    assert got["reason"] == "core-md-absent"
    assert got["globs"] is None


def _two_copies(tmp_path, mode):
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: ["in-repo/**"]})
    in_repo, global_path = CM._core_candidates(repo, store)
    text = open(in_repo).read()
    inner = CM._JSON_BLOCK.search(text).group(1)
    block = json.loads(inner)
    block[_KEY] = ["global/**"]
    os.makedirs(os.path.dirname(global_path), exist_ok=True)
    open(global_path, "w").write(text.replace(inner, json.dumps(block, indent=2)))
    MR.write_registry(repo, mode, "rk", root=store, allow_migration=True)
    return repo, store


@pytest.mark.parametrize("mode, expected", [("in-repo", ["in-repo/**"]), ("global", ["global/**"])])
def test_read_both_copies_resolve_by_recorded_mode(tmp_path, mode, expected):
    repo, store = _two_copies(tmp_path, mode)
    assert CM.read_size_exclude(repo, store)["globs"] == expected


def test_read_newer_schema_marks_behind(tmp_path):
    repo, store = _setup_repo(
        tmp_path, extra_block={"schemaVersion": CM.SCHEMA_VERSION + 1, _KEY: ["a/**"]})
    got = CM.read_size_exclude(repo, store)
    assert got["behind"] is True
    assert got["globs"] == ["a/**"]


# --- writer ---------------------------------------------------------------------------------

def test_write_then_read_round_trip(tmp_path):
    # axis: configure set then show — what the writer stores, the reader and the view return
    repo, store = _setup_repo(tmp_path)
    stored = ["b/**", "b/**", "*.ts"]
    got = CM.write_size_exclude(repo, stored, root=store)
    assert got["action"] == "written"
    assert _parsed(repo, store)[_KEY] == stored
    read = CM.read_size_exclude(repo, store)
    assert read["declared"] is True
    assert read["globs"] == stored
    section = _size_section(CV.render(repo, root=store))
    assert section.splitlines() == ["### Size count exclusions", "- b/**", "- b/**", "- *.ts"]


def test_write_empty_list_is_declared_empty(tmp_path):
    repo, store = _setup_repo(tmp_path)
    assert CM.write_size_exclude(repo, [], root=store)["action"] == "written"
    assert _parsed(repo, store)[_KEY] == []
    assert CM.read_size_exclude(repo, store)["declared"] is True


def test_write_same_value_is_noop(tmp_path):
    repo, store = _setup_repo(tmp_path)
    assert CM.write_size_exclude(repo, _GLOBS, root=store)["action"] == "written"
    assert CM.write_size_exclude(repo, _GLOBS, root=store)["action"] == "noop"


@pytest.mark.parametrize(
    "value, reason",
    [
        ("docs/**", "size-exclude-not-a-list"),
        (["/abs"], "size-exclude-entry-absolute"),
        ([""], "size-exclude-entry-not-a-nonempty-string"),
    ],
    ids=repr)
def test_write_malformed_refused_file_unchanged(tmp_path, value, reason):
    # axis: a malformed value is refused with the malformed items; core.md untouched
    repo, store = _setup_repo(tmp_path)
    path = CM.core_path(repo, store)
    before = open(path, "rb").read()
    got = CM.write_size_exclude(repo, value, root=store)
    assert got["action"] == "refused"
    assert got["reason"] == "size-exclude-malformed"
    assert _only(got["malformed"])["reason"] == reason
    assert open(path, "rb").read() == before


def test_clear_removes_key(tmp_path):
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: _GLOBS})
    got = CM.clear_size_exclude(repo, root=store)
    assert got["action"] == "written"
    assert got["cleared"] is True
    assert _KEY not in _parsed(repo, store)
    read = CM.read_size_exclude(repo, store)
    assert read["declared"] is False
    assert read["globs"] is None


# --- CLI ------------------------------------------------------------------------------------

def test_cli_write_and_read_round_trip(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_GLOBS)))
    assert CM.main(["write-size-exclude", "--cwd", repo, "--root", store]) == 0
    proc = subprocess.run(
        [sys.executable, _CORE_MD, "size-exclude", "--cwd", repo, "--root", store],
        capture_output=True, text=True, check=True)
    payload = json.loads(proc.stdout)
    assert payload["declared"] is True
    assert payload["globs"] == _GLOBS
    assert payload["reason"] is None


def test_cli_empty_stdin_refused(tmp_path, monkeypatch, capsys):
    # axis: E11 empty stdin without --clear is refused, never a silent clear
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: _GLOBS})
    monkeypatch.setattr("sys.stdin", io.StringIO("  \n"))
    assert CM.main(["write-size-exclude", "--cwd", repo, "--root", store]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"action": "refused", "reason": "size-exclude-input-unparseable"}
    assert _parsed(repo, store)[_KEY] == _GLOBS


@pytest.mark.parametrize("stdin", ["{not json", "docs/**", "null"], ids=repr)
def test_cli_non_json_stdin_refused(tmp_path, monkeypatch, capsys, stdin):
    # axis: E12 stdin that is not a JSON value is refused, nothing written
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    assert CM.main(["write-size-exclude", "--cwd", repo, "--root", store]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"action": "refused", "reason": "size-exclude-input-unparseable"}
    assert _KEY not in _parsed(repo, store)


def test_cli_duplicate_stdin_key_refused(tmp_path, monkeypatch, capsys):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO('{"a": 1, "a": 2}'))
    assert CM.main(["write-size-exclude", "--cwd", repo, "--root", store]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"action": "refused", "reason": "duplicate-core-key:a"}
    assert _KEY not in _parsed(repo, store)


def test_cli_malformed_refused(tmp_path, monkeypatch, capsys):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO('["/abs"]'))
    assert CM.main(["write-size-exclude", "--cwd", repo, "--root", store]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["action"] == "refused"
    assert out["reason"] == "size-exclude-malformed"
    assert _only(out["malformed"])["reason"] == "size-exclude-entry-absolute"
    assert _KEY not in _parsed(repo, store)


def test_cli_clear_flag(tmp_path, capsys):
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: _GLOBS})
    assert CM.main(["write-size-exclude", "--cwd", repo, "--root", store, "--clear"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["cleared"] is True
    assert _KEY not in _parsed(repo, store)


def test_cli_read_prints_absent_state(tmp_path, capsys):
    repo, store = _setup_repo(tmp_path)
    assert CM.main(["size-exclude", "--cwd", repo, "--root", store]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["declared"] is False
    assert out["globs"] is None
    assert out["reason"] is None


# --- Invariant: every core.md rewrite path carries sizeExclude forward raw -------------------

_RAW_VALUES = {
    "valid-unnormalized": ["b/**", "b/**", " x "],
    "malformed": ["/abs", 5, ""],
    "not-a-list": "docs/**",
}


@pytest.mark.parametrize("raw", list(_RAW_VALUES.values()), ids=list(_RAW_VALUES))
def test_carry_forward_parse_render_round_trip(raw):
    # axis: (a) parse_core(render_core(facts)) round-trips the raw value, malformed included
    facts = dict(_CORE_FACTS, **{_KEY: copy.deepcopy(raw)})
    text = CM.render_core(facts, "confirmed", "2026-06-26", "2026-06-26")
    assert CM.parse_core(text)[_KEY] == raw


def test_carry_forward_render_without_key_has_no_key():
    text = CM.render_core(dict(_CORE_FACTS), "confirmed", "2026-06-26", "2026-06-26")
    assert _KEY not in CM.parse_core(text)


@pytest.mark.parametrize("raw", list(_RAW_VALUES.values()), ids=list(_RAW_VALUES))
def test_carry_forward_read_exposes_raw(tmp_path, raw):
    # axis: (b) read() exposes the raw value, malformed included
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: raw})
    assert CM.read(repo, store)[_KEY] == raw


def test_carry_forward_read_without_key_has_no_key(tmp_path):
    repo, store = _setup_repo(tmp_path)
    assert _KEY not in CM.read(repo, store)


@pytest.mark.parametrize("raw", list(_RAW_VALUES.values()), ids=list(_RAW_VALUES))
def test_carry_forward_confirm_all_keeps_key_byte_equal(tmp_path, raw):
    # axis: (c) confirm_all on a provisional core.md leaves sizeExclude byte-equal
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: raw}, status="provisional")
    before = json.dumps(_parsed(repo, store)[_KEY], indent=2)
    result = CM.confirm_all(repo, root=store)
    assert result["core"]["action"] == "confirmed"
    after = json.dumps(_parsed(repo, store)[_KEY], indent=2)
    assert after == before
    assert _parsed(repo, store)[_KEY] == raw


def test_carry_forward_confirm_all_without_key_adds_none(tmp_path):
    repo, store = _setup_repo(tmp_path, status="provisional")
    CM.confirm_all(repo, root=store)
    assert _KEY not in _parsed(repo, store)


@pytest.mark.parametrize("raw", list(_RAW_VALUES.values()), ids=list(_RAW_VALUES))
def test_carry_forward_vet_checks_writers_leave_key_intact(tmp_path, raw):
    # axis: (d) write_vet_checks / clear_vet_checks leave sizeExclude intact
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: raw})
    before = json.dumps(_parsed(repo, store)[_KEY], indent=2)
    checks = [{"name": "A", "evidence": "e", "records": "r"}]
    assert CM.write_vet_checks(repo, checks, root=store)["action"] == "written"
    assert json.dumps(_parsed(repo, store)[_KEY], indent=2) == before
    assert CM.clear_vet_checks(repo, root=store)["action"] == "written"
    assert json.dumps(_parsed(repo, store)[_KEY], indent=2) == before


def test_carry_forward_size_writer_leaves_sibling_keys_intact(tmp_path):
    checks = [{"name": "A", "evidence": "e", "records": "r"}]
    sandbox = {"localPorts": True}
    repo, store = _setup_repo(
        tmp_path, extra_block={"vetChecks": checks, "sandboxAccess": sandbox})
    assert CM.write_size_exclude(repo, _GLOBS, root=store)["action"] == "written"
    assert _parsed(repo, store)["vetChecks"] == checks
    assert _parsed(repo, store)["sandboxAccess"] == sandbox
    assert CM.clear_size_exclude(repo, root=store)["action"] == "written"
    assert _parsed(repo, store)["vetChecks"] == checks
    assert _parsed(repo, store)["sandboxAccess"] == sandbox


# --- the configure view always shows the size count exclusions --------------------------------

def _size_section(screen):
    start = screen.index("### Size count exclusions")
    return screen[start:].split("\n\n", 1)[0]


def test_view_absent_key_shows_none_line(tmp_path):
    # axis: an absent key shows the one-line default, core-present branch
    repo, store = _setup_repo(tmp_path)
    section = _size_section(CV.render(repo, root=store))
    assert section.splitlines() == ["### Size count exclusions", _NONE_LINE]


def test_view_declared_empty(tmp_path):
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: []})
    section = _size_section(CV.render(repo, root=store))
    assert section.splitlines() == ["### Size count exclusions", _EMPTY_LINE]


def test_view_declared_globs_one_line_each(tmp_path):
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: _GLOBS})
    section = _size_section(CV.render(repo, root=store))
    assert section.splitlines() == [
        "### Size count exclusions", "- docs/**", "- *.generated.ts"]


def test_view_malformed_names_items_and_each_accepted_shape_once(tmp_path):
    # axis: a malformed key shows the warning, each item, and the accepted shape — not "none"
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: ["ok", "/abs", "", 5]})
    section = _size_section(CV.render(repo, root=store))
    assert section.splitlines() == [
        "### Size count exclusions",
        "⚠ size count exclusions unreadable: size-exclude-malformed",
        "⚠ malformed item index 1: size-exclude-entry-absolute",
        "⚠ malformed item index 2: size-exclude-entry-not-a-nonempty-string",
        "⚠ malformed item index 3: size-exclude-entry-not-a-nonempty-string",
        "accepted: " + _ACCEPTED_GLOB,
    ]


def test_view_not_a_list_shows_list_shape(tmp_path):
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: "docs/**"})
    section = _size_section(CV.render(repo, root=store))
    assert section.splitlines() == [
        "### Size count exclusions",
        "⚠ size count exclusions unreadable: size-exclude-malformed",
        "⚠ malformed item index None: size-exclude-not-a-list",
        "accepted: " + _ACCEPTED_LIST,
    ]


def test_view_core_absent_branch_shows_none_line(tmp_path):
    # axis: the no-core branch also carries the block; core-md-absent is not a warning
    repo, store = _setup_core_absent(tmp_path)
    screen = CV.render(repo, root=store)
    assert "(no core calibration yet)" in screen
    section = _size_section(screen)
    assert section.splitlines() == ["### Size count exclusions", _NONE_LINE]


def test_view_core_unparseable_branch_names_reason_and_detail(tmp_path):
    repo, store = _setup_repo(tmp_path)
    open(CM.core_path(repo, store), "w").write("no json fence\n")
    screen = CV.render(repo, root=store)
    assert "(no core calibration yet)" in screen
    lines = _size_section(screen).splitlines()
    assert lines[:2] == [
        "### Size count exclusions",
        "⚠ size count exclusions unreadable: size-exclude-unreadable"]
    assert lines[2] == "cause: core-md-unparseable"
    assert len(lines) == 3
    assert CM.core_path(repo, store) not in screen


def test_view_unreadable_detail_shows_path_free_cause():
    payload = {"declared": False, "globs": None, "reason": "size-exclude-unreadable",
               "detail": "multiple-core-blocks:/abs/x/core.md"}
    assert CV._size_exclude_view_lines(payload) == [
        "### Size count exclusions",
        "⚠ size count exclusions unreadable: size-exclude-unreadable",
        "cause: multiple-core-blocks"]


_PAYLOAD_SHAPES = {
    "absent": (
        {"declared": False, "globs": None, "reason": None},
        ["### Size count exclusions", _NONE_LINE]),
    "declared-empty": (
        {"declared": True, "globs": [], "reason": None},
        ["### Size count exclusions", _EMPTY_LINE]),
    "globs": (
        {"declared": True, "globs": ["a/**", "b"], "reason": None},
        ["### Size count exclusions", "- a/**", "- b"]),
    "malformed": (
        {"declared": True, "globs": None, "reason": "size-exclude-malformed",
         "malformed": [{"index": 0, "reason": "size-exclude-entry-absolute",
                        "accepted": _ACCEPTED_GLOB}]},
        ["### Size count exclusions",
         "⚠ size count exclusions unreadable: size-exclude-malformed",
         "⚠ malformed item index 0: size-exclude-entry-absolute",
         "accepted: " + _ACCEPTED_GLOB]),
    "other-reason-with-detail": (
        {"declared": False, "globs": None, "reason": "size-exclude-unreadable",
         "detail": "duplicate-core-key:sizeExclude"},
        ["### Size count exclusions",
         "⚠ size count exclusions unreadable: size-exclude-unreadable",
         "cause: duplicate-core-key"]),
    "other-reason-no-detail": (
        {"declared": False, "globs": None, "reason": "size-exclude-read-failed"},
        ["### Size count exclusions",
         "⚠ size count exclusions unreadable: size-exclude-read-failed"]),
}


@pytest.mark.parametrize("branch", ["core-present", "core-absent"])
@pytest.mark.parametrize("shape", list(_PAYLOAD_SHAPES))
def test_view_five_shapes_in_both_render_branches(tmp_path, monkeypatch, branch, shape):
    # axis: each shape renders in both render branches, directly after the Sandbox access block
    payload, expected = _PAYLOAD_SHAPES[shape]
    if branch == "core-present":
        repo, store = _setup_repo(tmp_path)
    else:
        repo, store = _setup_core_absent(tmp_path)
    monkeypatch.setattr(CV.core_md, "read_size_exclude", lambda *a, **k: payload)
    screen = CV.render(repo, root=store)
    assert ("(no core calibration yet)" in screen) == (branch == "core-absent")
    assert _size_section(screen).splitlines() == expected
    lines = screen.splitlines()
    heading = lines.index("### Size count exclusions")
    assert lines[heading - 1] == ""
    assert lines[heading - 2] != ""
    sandbox = lines.index("### Sandbox access")
    assert sandbox < heading
    assert "" not in lines[sandbox:heading - 1]


def test_view_read_failure_monkeypatch(tmp_path, monkeypatch):
    # axis: a raising read surfaces size-exclude-read-failed in the view
    repo, store = _setup_repo(tmp_path)

    def _boom(*a, **k):
        raise RuntimeError("synthetic")

    monkeypatch.setattr(CV.core_md, "read_size_exclude", _boom)
    section = _size_section(CV.render(repo, root=store))
    assert section.splitlines() == [
        "### Size count exclusions",
        "⚠ size count exclusions unreadable: size-exclude-read-failed"]


def test_view_collect_carries_size_exclude(tmp_path):
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: _GLOBS})
    assert CV.collect(repo, store)["sizeExclude"]["globs"] == _GLOBS
