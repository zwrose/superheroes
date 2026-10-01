# plugins/superheroes/lib/tests/test_sandbox_access_calibration_1562.py
"""sandboxAccess json key (#1562): validate, normalize, read, write, CLI, carry-forward, view.

Token literals are spelled out as strings on purpose: a test that reaches them through the
module constants stays green under any value (rubric/bite-proof.md, external-contract constant).

Detector axes (bite-proof):
- test_validate_* — refusal: each malformed shape names its token, field and accepted shape
- test_read_* / test_write_* / test_cli_* — fail-closed read, refused write, empty stdin
- test_carry_forward_* — preservation: every core.md rewrite path keeps sandboxAccess raw
- test_view_* — display: the configure view always shows the sandbox state
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

_KEY = "sandboxAccess"


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

_ACCEPTED_OBJECT = (
    "an object with any of the keys allowedDomains, localPorts, localSockets, extraWritePaths")
_ACCEPTED_DOMAIN = (
    "a bare hostname such as pypi.org, or a subdomain wildcard such as *.example.com "
    "— no scheme, path, port, or bare *")
_ACCEPTED_BOOL = "true or false"
_ACCEPTED_PATH = "an absolute path such as /Users/me/Library/Caches/ms-playwright"
_ACCEPTED_PATH_BELOW_ROOT = "an absolute path below / — the whole filesystem is never writable"

_ALL_OFF = {"allowedDomains": [], "localPorts": False, "localSockets": False,
            "extraWritePaths": []}
_CONFIGURED = {
    "allowedDomains": ["pypi.org", "*.example.com"],
    "localPorts": True,
    "localSockets": False,
    "extraWritePaths": ["/Users/me/cache"],
}


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


def _parsed(repo, store):
    text = open(CM.core_path(repo, store)).read()
    return json.loads(CM._JSON_BLOCK.search(text).group(1))


def _only(items):
    assert len(items) == 1, items
    return items[0]


# --- literal pins ---------------------------------------------------------------------------

def test_literal_pins():
    # axis: the external-contract literals WO-2/WO-3 and core.md readers match on
    assert CM.SANDBOX_ACCESS_KEY == "sandboxAccess"
    assert CM.SANDBOX_ACCESS_FIELDS == (
        "allowedDomains", "localPorts", "localSockets", "extraWritePaths")
    assert CM.SANDBOX_ACCESS_REASON_MALFORMED == "sandbox-access-malformed"
    assert CM.SANDBOX_ACCESS_REASON_INPUT_UNPARSEABLE == "sandbox-access-input-unparseable"
    assert CM.SANDBOX_ACCESS_REASON_ROUND_TRIP == "sandbox-access-round-trip-refused"
    assert CM.SANDBOX_ACCESS_MALFORMED_NOT_AN_OBJECT == "sandbox-access-not-an-object"
    assert CM.SANDBOX_ACCESS_MALFORMED_UNKNOWN_FIELD == "sandbox-access-unknown-field"
    assert CM.SANDBOX_ACCESS_MALFORMED_NOT_A_LIST == "sandbox-access-not-a-list"
    assert CM.SANDBOX_ACCESS_MALFORMED_DOMAIN_INVALID == "sandbox-access-domain-invalid"
    assert CM.SANDBOX_ACCESS_MALFORMED_NOT_A_BOOL == "sandbox-access-not-a-bool"
    assert CM.SANDBOX_ACCESS_MALFORMED_PATH_NOT_ABSOLUTE == "sandbox-access-path-not-absolute"
    assert CM.SANDBOX_ACCESS_MALFORMED_PATH_IS_ROOT == "sandbox-access-path-is-root"


def test_all_off_is_fresh():
    first = CM.sandbox_access_all_off()
    assert first == _ALL_OFF
    first["allowedDomains"].append("x.org")
    assert CM.sandbox_access_all_off() == _ALL_OFF


# --- validator ------------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["pypi.org", [], None, 5, ["allowedDomains"]], ids=repr)
def test_validate_not_an_object(value):
    # axis: E1 a non-dict value is refused with the not-an-object token and the accepted shape
    item = _only(CM.validate_sandbox_access(value))
    assert item["reason"] == "sandbox-access-not-an-object"
    assert item["field"] is None
    assert item["index"] is None
    assert item["accepted"] == _ACCEPTED_OBJECT


def test_validate_unknown_field():
    # axis: E2 a typo'd key is named, never silently ignored
    item = _only(CM.validate_sandbox_access({"allowedDomain": ["pypi.org"]}))
    assert item["reason"] == "sandbox-access-unknown-field"
    assert item["field"] == "allowedDomain"
    assert item["accepted"] == _ACCEPTED_OBJECT


def test_validate_unknown_field_alongside_valid_ones():
    # axis: E2 an unknown key is refused even when every known key is valid
    value = dict(_CONFIGURED, extra=1)
    item = _only(CM.validate_sandbox_access(value))
    assert item["reason"] == "sandbox-access-unknown-field"
    assert item["field"] == "extra"


@pytest.mark.parametrize("value", ["pypi.org", None, {"a": 1}, 5], ids=repr)
def test_validate_domains_not_a_list(value):
    # axis: E3 allowedDomains present and not a list
    item = _only(CM.validate_sandbox_access({"allowedDomains": value}))
    assert item["reason"] == "sandbox-access-not-a-list"
    assert item["field"] == "allowedDomains"
    assert item["accepted"] == 'a list of hostnames, such as ["pypi.org", "*.example.com"]'


_BAD_DOMAINS = [
    "*", "*.com", "*.", "a*.example.com", "*.*.example.com", "*.a*.com",
    "https://pypi.org", "ftp://x.org", "pypi.org/simple", "pypi.org:443",
    " pypi.org", "pypi.org ", "pypi org", "pypi.org\n", "", ".pypi.org", "pypi..org",
    "pypi.org.", 5, None, True, ["pypi.org"],
]


@pytest.mark.parametrize("form", _BAD_DOMAINS, ids=repr)
def test_validate_domain_invalid(form):
    # axis: E4 each invalid domain form is refused with domain-invalid at its index
    item = _only(CM.validate_sandbox_access({"allowedDomains": ["pypi.org", form]}))
    assert item["reason"] == "sandbox-access-domain-invalid"
    assert item["field"] == "allowedDomains"
    assert item["index"] == 1
    assert item["accepted"] == _ACCEPTED_DOMAIN


@pytest.mark.parametrize(
    "form", ["pypi.org", "localhost", "a-b.c1.io", "*.example.com", "*.a.b.example.com", "PyPI.org"],
    ids=repr)
def test_validate_domain_accepted(form):
    # axis: the accepted domain shapes stay accepted (the refusal is not over-broad)
    assert CM.validate_sandbox_access({"allowedDomains": [form]}) == []


@pytest.mark.parametrize("field", ["localPorts", "localSockets"])
@pytest.mark.parametrize("form", [1, 0, "true", "false", None, [], {}], ids=repr)
def test_validate_flag_not_a_bool(field, form):
    # axis: E5 a non-bool flag (truthy or not) is refused with not-a-bool
    item = _only(CM.validate_sandbox_access({field: form}))
    assert item["reason"] == "sandbox-access-not-a-bool"
    assert item["field"] == field
    assert item["accepted"] == _ACCEPTED_BOOL


@pytest.mark.parametrize("field", ["localPorts", "localSockets"])
@pytest.mark.parametrize("form", [True, False])
def test_validate_flag_bool_accepted(field, form):
    assert CM.validate_sandbox_access({field: form}) == []


@pytest.mark.parametrize("value", ["/tmp/x", None, {"a": 1}, 5], ids=repr)
def test_validate_paths_not_a_list(value):
    # axis: E6 extraWritePaths present and not a list
    item = _only(CM.validate_sandbox_access({"extraWritePaths": value}))
    assert item["reason"] == "sandbox-access-not-a-list"
    assert item["field"] == "extraWritePaths"
    assert item["accepted"] == "a list of absolute paths"


@pytest.mark.parametrize("form", ["x/y", "~/x", "~", "", ".", "../x", 5, None, ["/a"]], ids=repr)
def test_validate_path_not_absolute(form):
    # axis: E7 relative, tilde and non-string paths are refused (no ~ expansion)
    item = _only(CM.validate_sandbox_access({"extraWritePaths": ["/ok/path", form]}))
    assert item["reason"] == "sandbox-access-path-not-absolute"
    assert item["field"] == "extraWritePaths"
    assert item["index"] == 1
    assert item["accepted"] == _ACCEPTED_PATH


@pytest.mark.parametrize("form", ["/", "//", "/.", "///", "/..", "/a/.."], ids=repr)
def test_validate_path_is_root(form):
    # axis: E8 any absolute path whose normalized form is the filesystem root is refused
    item = _only(CM.validate_sandbox_access({"extraWritePaths": [form]}))
    assert item["reason"] == "sandbox-access-path-is-root"
    assert item["field"] == "extraWritePaths"
    assert item["index"] == 0
    assert item["accepted"] == _ACCEPTED_PATH_BELOW_ROOT


@pytest.mark.parametrize("value", [{}, _ALL_OFF, _CONFIGURED, {"localPorts": True}], ids=repr)
def test_validate_valid_values(value):
    assert CM.validate_sandbox_access(value) == []


def test_validate_collects_every_problem():
    # axis: every malformed item is reported, in field order, each with accepted
    got = CM.validate_sandbox_access({
        "bogus": 1, "allowedDomains": ["*"], "localPorts": 1, "extraWritePaths": ["x"]})
    assert [(i["field"], i["index"], i["reason"]) for i in got] == [
        ("bogus", None, "sandbox-access-unknown-field"),
        ("allowedDomains", 0, "sandbox-access-domain-invalid"),
        ("localPorts", None, "sandbox-access-not-a-bool"),
        ("extraWritePaths", 0, "sandbox-access-path-not-absolute"),
    ]
    assert all(i["accepted"] for i in got)


# --- normalize ------------------------------------------------------------------------------

def test_normalize_fills_missing_keys():
    assert CM.normalize_sandbox_access({}) == _ALL_OFF
    assert CM.normalize_sandbox_access({"localSockets": True}) == dict(
        _ALL_OFF, localSockets=True)


def test_normalize_dedupes_preserving_order_and_normalizes_paths():
    got = CM.normalize_sandbox_access({
        "allowedDomains": ["b.org", "a.org", "b.org"],
        "extraWritePaths": ["/x/y/", "/z", "/x/./y", "/z"],
    })
    assert got["allowedDomains"] == ["b.org", "a.org"]
    assert got["extraWritePaths"] == ["/x/y", "/z"]


# --- reader ---------------------------------------------------------------------------------

def test_read_key_absent_is_all_off(tmp_path):
    # axis: an absent key is declared False with every option off
    repo, store = _setup_repo(tmp_path)
    got = CM.read_sandbox_access(repo, store)
    assert got["declared"] is False
    assert got["reason"] is None
    assert got["access"] == _ALL_OFF
    assert got["malformed"] == []
    assert got["behind"] is False


def test_read_core_md_absent_is_all_off_with_reason(tmp_path):
    # axis: E9 an absent core.md reads all off, reason core-md-absent
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _init_repo(tmp_path)
    MR.write_registry(repo, MR.IN_REPO, "rk", root=store)
    got = CM.read_sandbox_access(repo, store)
    assert got["declared"] is False
    assert got["reason"] == "core-md-absent"
    assert got["access"] == _ALL_OFF


def test_read_valid_is_normalized(tmp_path):
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: {
        "allowedDomains": ["pypi.org", "pypi.org"], "extraWritePaths": ["/a/b/"]}})
    got = CM.read_sandbox_access(repo, store)
    assert got["declared"] is True
    assert got["reason"] is None
    assert got["access"] == {"allowedDomains": ["pypi.org"], "localPorts": False,
                             "localSockets": False, "extraWritePaths": ["/a/b"]}


def test_read_malformed_has_no_access(tmp_path):
    # axis: E10 a malformed key reads access None, never the all-off default
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: {"allowedDomains": ["*"]}})
    got = CM.read_sandbox_access(repo, store)
    assert got["declared"] is True
    assert got["access"] is None
    assert got["reason"] == "sandbox-access-malformed"
    item = _only(got["malformed"])
    assert item["reason"] == "sandbox-access-domain-invalid"
    assert item["accepted"] == _ACCEPTED_DOMAIN


@pytest.mark.parametrize("raw", [None, "pypi.org", [], True], ids=repr)
def test_read_non_dict_key_is_malformed(tmp_path, raw):
    # axis: E1 through the reader — a present key holding a non-dict never reads as all off
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: raw})
    got = CM.read_sandbox_access(repo, store)
    assert got["declared"] is True
    assert got["access"] is None
    assert got["reason"] == "sandbox-access-malformed"
    assert _only(got["malformed"])["reason"] == "sandbox-access-not-an-object"


def test_read_unparseable_core_md(tmp_path):
    # axis: E11 an unparseable core.md reads access None
    repo, store = _setup_repo(tmp_path)
    open(CM.core_path(repo, store), "w").write("no json fence\n")
    got = CM.read_sandbox_access(repo, store)
    assert got["reason"] == "core-md-unparseable"
    assert got["access"] is None


def test_read_two_blocks_refused(tmp_path):
    repo, store = _setup_repo(tmp_path)
    path = CM.core_path(repo, store)
    open(path, "a").write("\n```json superheroes-core\n{}\n```\n")
    got = CM.read_sandbox_access(repo, store)
    assert got["reason"] == "multiple-core-blocks"
    assert got["access"] is None


def test_read_duplicate_key_is_structural_refusal(tmp_path):
    # axis: E12 a duplicate sandboxAccess key is the structural refusal, access None
    repo, store = _setup_repo(tmp_path)
    path = CM.core_path(repo, store)
    text = open(path).read()
    inner = (
        '{\n  "schemaVersion": %d,\n  "verifyCommand": "a",\n  "stackTags": [],\n'
        '  "sandboxAccess": {"localPorts": true},\n  "sandboxAccess": {"localPorts": false}\n}'
        % CM.SCHEMA_VERSION)
    open(path, "w").write(text.replace(CM._JSON_BLOCK.search(text).group(1), inner))
    got = CM.read_sandbox_access(repo, store)
    assert got["reason"] == "duplicate-core-key:sandboxAccess"
    assert got["access"] is None


def test_read_repo_root_unavailable(monkeypatch):
    def _raise(*a, **k):
        raise CM.RepoRootUnavailable("no root")

    monkeypatch.setattr(CM, "core_path", _raise)
    got = CM.read_sandbox_access(".", None)
    assert got["access"] is None
    assert got["reason"] == "repo-root-unavailable"


def test_read_newer_schema_marks_behind(tmp_path):
    repo, store = _setup_repo(tmp_path, extra_block={"schemaVersion": CM.SCHEMA_VERSION + 1})
    got = CM.read_sandbox_access(repo, store)
    assert got["behind"] is True


# --- writer ---------------------------------------------------------------------------------

def test_write_stores_normalized(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = CM.write_sandbox_access(
        repo, {"allowedDomains": ["a.org", "a.org"], "extraWritePaths": ["/x/./y"]}, root=store)
    assert got["action"] == "written"
    assert _parsed(repo, store)[_KEY] == {
        "allowedDomains": ["a.org"], "localPorts": False, "localSockets": False,
        "extraWritePaths": ["/x/y"]}
    assert CM.read_sandbox_access(repo, store)["declared"] is True


def test_write_same_value_is_noop(tmp_path):
    repo, store = _setup_repo(tmp_path)
    assert CM.write_sandbox_access(repo, _CONFIGURED, root=store)["action"] == "written"
    assert CM.write_sandbox_access(repo, _CONFIGURED, root=store)["action"] == "noop"


def test_write_malformed_refused_file_unchanged(tmp_path):
    # axis: E13 a malformed value is refused with the malformed items; core.md untouched
    repo, store = _setup_repo(tmp_path)
    path = CM.core_path(repo, store)
    before = open(path, "rb").read()
    got = CM.write_sandbox_access(repo, {"allowedDomains": ["https://pypi.org"]}, root=store)
    assert got["action"] == "refused"
    assert got["reason"] == "sandbox-access-malformed"
    assert _only(got["malformed"])["reason"] == "sandbox-access-domain-invalid"
    assert open(path, "rb").read() == before


def test_write_non_dict_refused_file_unchanged(tmp_path):
    repo, store = _setup_repo(tmp_path)
    path = CM.core_path(repo, store)
    before = open(path, "rb").read()
    got = CM.write_sandbox_access(repo, ["pypi.org"], root=store)
    assert got["action"] == "refused"
    assert _only(got["malformed"])["reason"] == "sandbox-access-not-an-object"
    assert open(path, "rb").read() == before


def test_clear_removes_key(tmp_path):
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: _CONFIGURED})
    got = CM.clear_sandbox_access(repo, root=store)
    assert got["action"] == "written"
    assert got["cleared"] is True
    assert _KEY not in _parsed(repo, store)
    assert CM.read_sandbox_access(repo, store)["access"] == _ALL_OFF


# --- CLI ------------------------------------------------------------------------------------

def test_cli_write_and_read_round_trip(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_CONFIGURED)))
    assert CM.main(["write-sandbox-access", "--cwd", repo, "--root", store]) == 0
    proc = subprocess.run(
        [sys.executable, _CORE_MD, "sandbox-access", "--cwd", repo, "--root", store],
        capture_output=True, text=True, check=True)
    payload = json.loads(proc.stdout)
    assert payload["declared"] is True
    assert payload["access"] == _CONFIGURED


def test_cli_empty_stdin_refused(tmp_path, monkeypatch, capsys):
    # axis: E14 empty stdin is refused, never a silent clear
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: _CONFIGURED})
    monkeypatch.setattr("sys.stdin", io.StringIO("  \n"))
    assert CM.main(["write-sandbox-access", "--cwd", repo, "--root", store]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"action": "refused", "reason": "sandbox-access-input-unparseable"}
    assert _parsed(repo, store)[_KEY] == _CONFIGURED


def test_cli_invalid_json_refused(tmp_path, monkeypatch, capsys):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    assert CM.main(["write-sandbox-access", "--cwd", repo, "--root", store]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"action": "refused", "reason": "sandbox-access-input-unparseable"}
    assert _KEY not in _parsed(repo, store)


def test_cli_duplicate_stdin_key_refused(tmp_path, monkeypatch, capsys):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr(
        "sys.stdin", io.StringIO('{"localPorts": true, "localPorts": false}'))
    assert CM.main(["write-sandbox-access", "--cwd", repo, "--root", store]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"action": "refused", "reason": "duplicate-core-key:localPorts"}
    assert _KEY not in _parsed(repo, store)


def test_cli_malformed_refused(tmp_path, monkeypatch, capsys):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO('{"extraWritePaths": ["~/x"]}'))
    assert CM.main(["write-sandbox-access", "--cwd", repo, "--root", store]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["action"] == "refused"
    assert out["reason"] == "sandbox-access-malformed"
    assert _only(out["malformed"])["reason"] == "sandbox-access-path-not-absolute"
    assert _KEY not in _parsed(repo, store)


def test_cli_clear_flag(tmp_path, capsys):
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: _CONFIGURED})
    assert CM.main(["write-sandbox-access", "--cwd", repo, "--root", store, "--clear"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["cleared"] is True
    assert _KEY not in _parsed(repo, store)


def test_cli_read_prints_all_off_when_absent(tmp_path, capsys):
    repo, store = _setup_repo(tmp_path)
    assert CM.main(["sandbox-access", "--cwd", repo, "--root", store]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["declared"] is False
    assert out["access"] == _ALL_OFF


# --- Invariant 1: every core.md rewrite path carries sandboxAccess forward raw ---------------

_RAW_VALUES = {
    "valid-unnormalized": {"allowedDomains": ["b.org", "b.org"], "extraWritePaths": ["/x/./y/"]},
    "malformed": {"allowedDomains": ["*"], "typo": True},
    "not-a-dict": ["pypi.org"],
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
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: raw})
    assert CM.read(repo, store)[_KEY] == raw


@pytest.mark.parametrize("raw", list(_RAW_VALUES.values()), ids=list(_RAW_VALUES))
def test_carry_forward_confirm_all_keeps_key_byte_equal(tmp_path, raw):
    # axis: (b) confirm_all on a provisional core.md leaves sandboxAccess byte-equal
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
    # axis: (c) write_vet_checks / clear_vet_checks leave sandboxAccess intact
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: raw})
    before = json.dumps(_parsed(repo, store)[_KEY], indent=2)
    checks = [{"name": "A", "evidence": "e", "records": "r"}]
    assert CM.write_vet_checks(repo, checks, root=store)["action"] == "written"
    assert json.dumps(_parsed(repo, store)[_KEY], indent=2) == before
    assert CM.clear_vet_checks(repo, root=store)["action"] == "written"
    assert json.dumps(_parsed(repo, store)[_KEY], indent=2) == before


def test_carry_forward_sandbox_writer_leaves_vet_checks_intact(tmp_path):
    checks = [{"name": "A", "evidence": "e", "records": "r"}]
    repo, store = _setup_repo(tmp_path, extra_block={"vetChecks": checks})
    assert CM.write_sandbox_access(repo, _CONFIGURED, root=store)["action"] == "written"
    assert _parsed(repo, store)["vetChecks"] == checks


# --- Invariant 2: the configure view always shows the sandbox state ---------------------------

def _sandbox_section(screen):
    start = screen.index("### Sandbox access")
    return screen[start:].split("\n\n", 1)[0]


def test_view_all_off_when_key_absent(tmp_path):
    # axis: absent key shows the one-line offline state
    repo, store = _setup_repo(tmp_path)
    section = _sandbox_section(CV.render(repo, root=store))
    assert section.splitlines() == ["### Sandbox access", "all off (offline)"]


def test_view_all_off_when_declared_all_off(tmp_path):
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: _ALL_OFF})
    section = _sandbox_section(CV.render(repo, root=store))
    assert section.splitlines() == ["### Sandbox access", "all off (offline)"]


def test_view_all_off_when_declared_empty_object(tmp_path):
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: {}})
    section = _sandbox_section(CV.render(repo, root=store))
    assert section.splitlines() == ["### Sandbox access", "all off (offline)"]


def test_view_all_off_when_core_md_absent(tmp_path):
    # axis: core-md-absent shows all off, no unreadable warning (no-core branch)
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _init_repo(tmp_path)
    MR.write_registry(repo, MR.IN_REPO, "rk", root=store)
    screen = CV.render(repo, root=store)
    assert "(no core calibration yet)" in screen
    section = _sandbox_section(screen)
    assert section.splitlines() == ["### Sandbox access", "all off (offline)"]


def test_view_configured_values_four_lines(tmp_path):
    # axis: a configured value shows four lines, never the all-off line
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: _CONFIGURED})
    section = _sandbox_section(CV.render(repo, root=store))
    assert section.splitlines() == [
        "### Sandbox access",
        "allowed domains: pypi.org, *.example.com",
        "local ports: on",
        "local sockets: off",
        "extra writable paths: /Users/me/cache",
    ]


def test_view_configured_flag_only_shows_none_for_lists(tmp_path):
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: {"localSockets": True}})
    section = _sandbox_section(CV.render(repo, root=store))
    assert section.splitlines() == [
        "### Sandbox access",
        "allowed domains: (none)",
        "local ports: off",
        "local sockets: on",
        "extra writable paths: (none)",
    ]


def test_view_malformed_names_item_and_accepted(tmp_path):
    # axis: a malformed key shows the warning, each item, and the accepted shape — not all off
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: {"allowedDomains": ["pypi.org", "*"]}})
    section = _sandbox_section(CV.render(repo, root=store))
    assert section.splitlines() == [
        "### Sandbox access",
        "⚠ sandbox access unreadable: sandbox-access-malformed",
        "⚠ malformed item field allowedDomains index 1: sandbox-access-domain-invalid",
        "accepted: " + _ACCEPTED_DOMAIN,
    ]
    assert "all off" not in section


def test_view_no_core_branch_other_reason(tmp_path):
    # axis: the no-core branch also carries the block, and another reason is named
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _init_repo(tmp_path)
    MR.write_registry(repo, MR.IN_REPO, "rk", root=store)
    CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    open(CM.core_path(repo, store), "w").write("no json fence\n")
    screen = CV.render(repo, root=store)
    assert "(no core calibration yet)" in screen
    section = _sandbox_section(screen)
    assert section.splitlines() == [
        "### Sandbox access", "⚠ sandbox access unreadable: core-md-unparseable"]


def test_view_read_failure_monkeypatch(tmp_path, monkeypatch):
    # axis: E15 a raising read surfaces sandbox-access-read-failed in the view
    repo, store = _setup_repo(tmp_path)

    def _boom(*a, **k):
        raise RuntimeError("synthetic")

    monkeypatch.setattr(CV.core_md, "read_sandbox_access", _boom)
    screen = CV.render(repo, root=store)
    section = _sandbox_section(screen)
    assert section.splitlines() == [
        "### Sandbox access", "⚠ sandbox access unreadable: sandbox-access-read-failed"]


def test_view_collect_carries_sandbox_access(tmp_path):
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: _CONFIGURED})
    assert CV.collect(repo, store)["sandboxAccess"]["access"] == _CONFIGURED
