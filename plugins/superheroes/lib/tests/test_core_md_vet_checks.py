# plugins/superheroes/lib/tests/test_core_md_vet_checks.py
"""vetChecks json key: validate, read, write, CLI, preservation.

Detector axes (bite-proof):
- test_literal_pins — module pins and malformed-reason registry
- test_validate_vet_checks_* — validator tokens and multi-field ordering
- test_read_vet_checks_* — structural/read refusal and declared states
- test_write_vet_checks_* / clear_vet_checks — write, declared-empty, clear, malformed refuse
- test_preservation_* — vetChecks survives unrelated writers
- test_cli_* / test_subprocess_* — CLI stdin, --clear, and argv boundaries
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

_VET_CHECKS_KEY = "vetChecks"


def _load(name):
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    path = os.path.join(_LIB, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CM = _load("core_md")

_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}

_VALID_CHECKS = [
    {
        "name": " Alpha ",
        "evidence": " ev ",
        "records": " rec ",
    }
]

_MALFORMED_SEED = [{"name": ""}]


def _write_core(repo, schema_version, status="confirmed", extra_block=None):
    block = {
        "schemaVersion": schema_version,
        "verifyCommand": "npm test",
        "stackTags": ["node"],
    }
    if extra_block:
        block.update(extra_block)
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    text = (
        "<!-- superheroes-core: schemaVersion=%d status=%s created=2026-06-26 "
        "updated=2026-06-26 -->\n\n## Threat model\n\nsingle-user\n\n"
        "## Canonical patterns\n\n- x: a.ts:1\n\n"
        "```json superheroes-core\n%s\n```\n"
        % (schema_version, status, json.dumps(block, indent=2))
    )
    path = os.path.join(d, "core.md")
    open(path, "w").write(text)
    return path, text


def _setup_repo(tmp_path, schema=None, extra_block=None, status="confirmed"):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    if schema is None:
        CM.write(repo, dict(_CORE_FACTS), status, root=store, now="2026-06-26")
    else:
        CM.mode_registry.ensure_project_store(repo, store)
        _write_core(repo, schema, status=status, extra_block=extra_block)
    return repo, store


def _parsed(repo, store):
    path = CM.core_path(repo, store)
    return CM.parse_core(open(path, encoding="utf-8").read())


def test_literal_pins():
    # axis: vetChecks key literals and malformed-reason registry are single-sourced in core_md
    assert CM.VET_CHECKS_KEY == _VET_CHECKS_KEY
    assert CM.VET_CHECK_FIELD_NAMES == ("name", "evidence", "records")
    assert len(CM.VET_CHECKS_MALFORMED_REASONS) == len(set(CM.VET_CHECKS_MALFORMED_REASONS))
    assert CM.VET_CHECKS_REASON_MALFORMED == "vet-checks-malformed"
    assert CM.VET_CHECKS_REASON_INPUT_UNPARSEABLE == "vet-checks-input-unparseable"
    assert CM.VET_CHECKS_REASON_ROUND_TRIP == "vet-checks-round-trip-refused"


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, [{"index": None, "field": None, "reason": "vet-checks-not-a-list"}]),
        ([], []),
        (
            "x",
            [{"index": None, "field": None, "reason": "vet-checks-not-a-list"}],
        ),
        (
            [1],
            [{"index": 0, "field": None, "reason": "vet-checks-entry-not-an-object"}],
        ),
        (
            [{}],
            [
                {"index": 0, "field": "name", "reason": "vet-checks-entry-missing-field"},
                {"index": 0, "field": "evidence", "reason": "vet-checks-entry-missing-field"},
                {"index": 0, "field": "records", "reason": "vet-checks-entry-missing-field"},
            ],
        ),
        (
            [{"name": "a", "evidence": "e", "records": "r", "extra": 1}],
            [{"index": 0, "field": "extra", "reason": "vet-checks-entry-unknown-field"}],
        ),
        (
            [{"name": "", "evidence": "e", "records": "r"}],
            [{"index": 0, "field": "name", "reason": "vet-checks-field-not-a-nonempty-string"}],
        ),
        (
            [
                {"name": "a", "evidence": "e", "records": "r"},
                {"name": "a", "evidence": "e2", "records": "r2"},
            ],
            [{"index": 1, "field": "name", "reason": "vet-checks-duplicate-name"}],
        ),
    ],
)
def test_validate_vet_checks_tokens(value, expected):
    # axis: validate_vet_checks emits only registry-listed malformed reason tokens
    got = CM.validate_vet_checks(value)
    assert got == expected
    for item in got:
        assert item["reason"] in CM.VET_CHECKS_MALFORMED_REASONS


def test_validate_vet_checks_multi_problem_ordered():
    # axis: validator reports every distinct field problem on one entry in stable order
    value = [{"name": 1, "bogus": True}]
    got = CM.validate_vet_checks(value)
    assert got == [
        {"index": 0, "field": "bogus", "reason": "vet-checks-entry-unknown-field"},
        {"index": 0, "field": "evidence", "reason": "vet-checks-entry-missing-field"},
        {"index": 0, "field": "records", "reason": "vet-checks-entry-missing-field"},
        {"index": 0, "field": "name", "reason": "vet-checks-field-not-a-nonempty-string"},
    ]


def test_read_vet_checks_repo_root_unavailable(monkeypatch):
    # axis: read_vet_checks refuses when core_path cannot resolve repo root
    def _raise(*a, **k):
        raise CM.RepoRootUnavailable("no root")

    monkeypatch.setattr(CM, "core_path", _raise)
    got = CM.read_vet_checks(".", root=None)
    assert got["reason"] == "repo-root-unavailable"
    assert got["declared"] is False
    assert got["checks"] == []


def test_read_vet_checks_core_absent(tmp_path):
    # axis: missing core.md yields core-md-absent without treating checks as declared
    repo, store = _setup_repo(tmp_path)
    os.remove(CM.core_path(repo, store))
    got = CM.read_vet_checks(repo, store)
    assert got["reason"] == "core-md-absent"


def test_read_vet_checks_unreadable_bytes(tmp_path):
    # axis: unreadable core bytes surface core-md-unreadable
    repo, store = _setup_repo(tmp_path)
    open(CM.core_path(repo, store), "wb").write(b"\xff\xfe")
    got = CM.read_vet_checks(repo, store)
    assert got["reason"] == "core-md-unreadable"
    assert got["detail"]


def test_read_vet_checks_unparseable_block(tmp_path):
    repo, store = _setup_repo(tmp_path)
    open(CM.core_path(repo, store), "w").write("no json fence\n")
    got = CM.read_vet_checks(repo, store)
    assert got["reason"] == "core-md-unparseable"


def test_read_vet_checks_two_blocks(tmp_path):
    repo, store = _setup_repo(tmp_path)
    path = CM.core_path(repo, store)
    text = open(path).read()
    open(path, "w").write(text + "\n```json superheroes-core\n{}\n```\n")
    got = CM.read_vet_checks(repo, store)
    assert got["reason"] == "multiple-core-blocks"


def test_read_vet_checks_duplicate_root_key(tmp_path):
    repo, store = _setup_repo(tmp_path)
    path = CM.core_path(repo, store)
    text = open(path).read()
    inner = (
        '{\n  "schemaVersion": %d,\n  "verifyCommand": "a",\n  "verifyCommand": "b",\n'
        '  "stackTags": ["node"]\n}' % CM.SCHEMA_VERSION
    )
    open(path, "w").write(text.replace(CM._JSON_BLOCK.search(text).group(1), inner))
    got = CM.read_vet_checks(repo, store)
    assert got["reason"] == "duplicate-core-key:verifyCommand"


def test_read_vet_checks_duplicate_name_member(tmp_path):
    repo, store = _setup_repo(tmp_path, schema=CM.SCHEMA_VERSION)
    path = CM.core_path(repo, store)
    text = open(path).read()
    inner = (
        '{\n  "schemaVersion": %d,\n  "verifyCommand": "npm test",\n  "stackTags": ["node"],\n'
        '  "vetChecks": [\n    {"name": "a", "name": "b", "evidence": "e", "records": "r"}\n  ]\n}'
        % CM.SCHEMA_VERSION
    )
    open(path, "w").write(text.replace(CM._JSON_BLOCK.search(text).group(1), inner))
    got = CM.read_vet_checks(repo, store)
    assert got["reason"] == "duplicate-core-key:name"


def test_read_vet_checks_key_absent(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = CM.read_vet_checks(repo, store)
    assert got["declared"] is False
    assert got["reason"] is None
    assert got["checks"] == []


def test_read_vet_checks_present_empty_list(tmp_path):
    repo, store = _setup_repo(
        tmp_path, schema=CM.SCHEMA_VERSION, extra_block={_VET_CHECKS_KEY: []})
    got = CM.read_vet_checks(repo, store)
    assert got["declared"] is True
    assert got["checks"] == []
    assert got["reason"] is None


def test_read_vet_checks_present_null(tmp_path):
    repo, store = _setup_repo(
        tmp_path, schema=CM.SCHEMA_VERSION, extra_block={_VET_CHECKS_KEY: None})
    got = CM.read_vet_checks(repo, store)
    assert got["declared"] is True
    assert got["reason"] == "vet-checks-malformed"
    assert got["checks"] == []


def test_read_vet_checks_present_scalar(tmp_path):
    repo, store = _setup_repo(
        tmp_path, schema=CM.SCHEMA_VERSION, extra_block={_VET_CHECKS_KEY: "x"})
    got = CM.read_vet_checks(repo, store)
    assert got["declared"] is True
    assert got["reason"] == "vet-checks-malformed"


def test_read_vet_checks_malformed_list(tmp_path):
    repo, store = _setup_repo(
        tmp_path, schema=CM.SCHEMA_VERSION, extra_block={_VET_CHECKS_KEY: _MALFORMED_SEED})
    got = CM.read_vet_checks(repo, store)
    assert got["declared"] is True
    assert got["checks"] == []
    assert got["reason"] == "vet-checks-malformed"
    assert got["malformed"]


def test_read_vet_checks_valid_stripped(tmp_path):
    repo, store = _setup_repo(
        tmp_path, schema=CM.SCHEMA_VERSION, extra_block={_VET_CHECKS_KEY: _VALID_CHECKS})
    got = CM.read_vet_checks(repo, store)
    assert got["checks"] == [{"name": "Alpha", "evidence": "ev", "records": "rec"}]


def test_read_vet_checks_behind_schema(tmp_path):
    repo, store = _setup_repo(
        tmp_path,
        schema=99,
        extra_block={_VET_CHECKS_KEY: _VALID_CHECKS},
    )
    got = CM.read_vet_checks(repo, store)
    assert got["behind"] is True
    assert got["checks"]


def test_write_vet_checks_roundtrip(tmp_path):
    repo, store = _setup_repo(tmp_path)
    res = CM.write_vet_checks(repo, _VALID_CHECKS, root=store)
    assert res["action"] == "written"
    got = CM.read_vet_checks(repo, store)
    assert got["checks"] == [{"name": "Alpha", "evidence": "ev", "records": "rec"}]


def test_write_vet_checks_noop(tmp_path):
    repo, store = _setup_repo(tmp_path)
    CM.write_vet_checks(repo, _VALID_CHECKS, root=store)
    res = CM.write_vet_checks(repo, _VALID_CHECKS, root=store)
    assert res["action"] == "noop"


def test_write_vet_checks_clear_removes_key(tmp_path):
    # axis: clear_vet_checks removes vetChecks; declared-empty [] keeps the key present
    repo, store = _setup_repo(tmp_path)
    CM.write_vet_checks(repo, _VALID_CHECKS, root=store)
    res = CM.clear_vet_checks(repo, root=store)
    assert res["action"] == "written"
    assert res.get("cleared") is True
    parsed = _parsed(repo, store)
    assert _VET_CHECKS_KEY not in parsed


def test_write_vet_checks_declared_empty_persists_key(tmp_path):
    # axis: write_vet_checks([]) stores declared-empty vetChecks without deleting the key
    repo, store = _setup_repo(tmp_path)
    CM.write_vet_checks(repo, _VALID_CHECKS, root=store)
    res = CM.write_vet_checks(repo, [], root=store)
    assert res["action"] == "written"
    parsed = _parsed(repo, store)
    assert parsed[_VET_CHECKS_KEY] == []
    got = CM.read_vet_checks(repo, store)
    assert got["declared"] is True
    assert got["checks"] == []


def test_write_vet_checks_malformed_refused_bytes_unchanged(tmp_path):
    # axis: malformed write refuses and leaves core.md bytes unchanged
    repo, store = _setup_repo(tmp_path)
    path = CM.core_path(repo, store)
    before = open(path, "rb").read()
    res = CM.write_vet_checks(repo, _MALFORMED_SEED, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == "vet-checks-malformed"
    assert res["malformed"]
    assert open(path, "rb").read() == before


def test_json_block_round_trip_vet_checks_only_diff():
    orig = {"schemaVersion": 2, "verifyCommand": "x", "stackTags": []}
    new = dict(orig, vetChecks=[])
    assert CM._json_block_key_round_trip_ok(orig, new, "projectConfiguration") is False


@pytest.mark.parametrize(
    "writer_name,kwargs,expect_action",
    [
        ("confirm", {}, "confirmed"),
        ("write_show_it_surface", {"prose": "demo surface"}, "written"),
        ("write_threat_model", {"prose": "new threat"}, "written"),
        ("write_builder_dispatch_tier", {"tier": "sonnet"}, "written"),
        (
            "write_engine_pref_pins",
            {"key": "codexModels", "pins": {"implementer": "gpt-5.6-sol"}},
            "written",
        ),
        (
            "write_review_gate_policy",
            {
                "policy": {
                    "schema": "gate-policy/1",
                    "default": "park",
                    "rules": [],
                }
            },
            "written",
        ),
        ("write_project_config", {"mapping": {"lint": {"enabled": True}}}, "written"),
        ("write_project_config_item", {"slug": "dial", "value": 3}, "written"),
        ("write_declared_dependencies", {"mapping": {"eslint": "^9"}}, "written"),
        ("write_declared_dependency_item", {"slug": "eslint", "value": "^10"}, "written"),
    ],
)
@pytest.mark.parametrize("seed_kind", ["valid", "malformed", "empty_list"])
def test_preservation_matrix(tmp_path, writer_name, kwargs, expect_action, seed_kind):
    # axis: unrelated core.md writers preserve vetChecks seed (valid, malformed, empty list, absent)
    extra = None
    if seed_kind == "valid":
        extra = {_VET_CHECKS_KEY: copy.deepcopy(_VALID_CHECKS)}
    elif seed_kind == "malformed":
        extra = {_VET_CHECKS_KEY: copy.deepcopy(_MALFORMED_SEED)}
    elif seed_kind == "empty_list":
        extra = {_VET_CHECKS_KEY: []}
    status = "provisional" if writer_name == "confirm" else "confirmed"
    repo, store = _setup_repo(tmp_path, schema=CM.SCHEMA_VERSION, extra_block=extra, status=status)
    seeded = _parsed(repo, store).get(_VET_CHECKS_KEY, "__absent__")
    writer = getattr(CM, writer_name)
    if writer_name == "confirm":
        res = writer(repo, root=store)
    elif writer_name == "write_show_it_surface":
        res = writer(repo, kwargs["prose"], root=store)
    elif writer_name == "write_threat_model":
        res = writer(repo, kwargs["prose"], root=store)
    elif writer_name == "write_builder_dispatch_tier":
        res = writer(repo, kwargs["tier"], root=store)
    elif writer_name == "write_engine_pref_pins":
        res = writer(repo, kwargs["key"], kwargs["pins"], root=store)
    elif writer_name == "write_review_gate_policy":
        res = writer(repo, kwargs["policy"], root=store)
    elif writer_name == "write_project_config":
        res = writer(repo, kwargs["mapping"], root=store)
    elif writer_name == "write_project_config_item":
        res = writer(repo, kwargs["slug"], kwargs["value"], root=store)
    elif writer_name == "write_declared_dependencies":
        res = writer(repo, kwargs["mapping"], root=store)
    else:
        res = writer(repo, kwargs["slug"], kwargs["value"], root=store)
    assert res["action"] == expect_action
    after = _parsed(repo, store).get(_VET_CHECKS_KEY, "__absent__")
    assert after == seeded


def test_preservation_absent_stays_absent_through_confirm(tmp_path):
    repo, store = _setup_repo(tmp_path, status="provisional")
    assert _VET_CHECKS_KEY not in _parsed(repo, store)
    res = CM.confirm(repo, root=store)
    assert res["action"] == "confirmed"
    assert _VET_CHECKS_KEY not in _parsed(repo, store)


def _git_env():
    return {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }


def test_subprocess_write_vet_checks_argv_stdin_boundary(tmp_path):
    repo, store = _setup_repo(tmp_path)
    env = {**os.environ, **_git_env()}
    write_proc = subprocess.run(
        [
            sys.executable,
            "-B",
            _CORE_MD,
            "write-vet-checks",
            "--cwd",
            repo,
            "--root",
            store,
        ],
        input=json.dumps(_VALID_CHECKS),
        capture_output=True,
        text=True,
        env=env,
    )
    assert write_proc.returncode == 0
    write_out = json.loads(write_proc.stdout)
    assert write_out["action"] == "written"
    read_proc = subprocess.run(
        [
            sys.executable,
            "-B",
            _CORE_MD,
            "vet-checks",
            "--cwd",
            repo,
            "--root",
            store,
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert read_proc.returncode == 0
    read_out = json.loads(read_proc.stdout)
    assert read_out["checks"] == [
        {"name": "Alpha", "evidence": "ev", "records": "rec"}
    ]
    assert read_out["reason"] is None
    bad_proc = subprocess.run(
        [
            sys.executable,
            "-B",
            _CORE_MD,
            "write-vet-checks",
            "--cwd",
            repo,
            "--root",
            store,
        ],
        input='{"a": 1}',
        capture_output=True,
        text=True,
        env=env,
    )
    assert bad_proc.returncode == 0
    bad_out = json.loads(bad_proc.stdout)
    assert bad_out["reason"] == "vet-checks-malformed"
    assert bad_out["malformed"][0]["reason"] == "vet-checks-not-a-list"


def test_cli_write_and_read_vet_checks(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_VALID_CHECKS)))
    rc = CM.main(["write-vet-checks", "--cwd", repo, "--root", store])
    assert rc == 0
    proc = subprocess.run(
        [sys.executable, _CORE_MD, "vet-checks", "--cwd", repo, "--root", store],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["checks"] == [{"name": "Alpha", "evidence": "ev", "records": "rec"}]


def test_cli_write_vet_checks_empty_stdin_refused(tmp_path, monkeypatch, capsys):
    # axis: empty stdin on write-vet-checks is refused, not an silent clear
    repo, store = _setup_repo(tmp_path)
    CM.write_vet_checks(repo, _VALID_CHECKS, root=store)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    rc = CM.main(["write-vet-checks", "--cwd", repo, "--root", store])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["action"] == "refused"
    assert out["reason"] == "vet-checks-input-unparseable"
    assert _VET_CHECKS_KEY in _parsed(repo, store)


def test_cli_write_vet_checks_clear_flag(tmp_path, capsys):
    # axis: --clear explicitly removes vetChecks and marks the result cleared
    repo, store = _setup_repo(tmp_path)
    CM.write_vet_checks(repo, _VALID_CHECKS, root=store)
    rc = CM.main(["write-vet-checks", "--cwd", repo, "--root", store, "--clear"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out.get("cleared") is True
    assert _VET_CHECKS_KEY not in _parsed(repo, store)


def test_cli_write_vet_checks_literal_empty_list_declared(tmp_path, monkeypatch):
    # axis: JSON [] persists declared-empty vetChecks (distinct from key absence)
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO("[]"))
    rc = CM.main(["write-vet-checks", "--cwd", repo, "--root", store])
    assert rc == 0
    got = CM.read_vet_checks(repo, store)
    assert got["declared"] is True
    assert got["checks"] == []
    assert _parsed(repo, store)[_VET_CHECKS_KEY] == []


def test_cli_write_vet_checks_invalid_json(tmp_path, monkeypatch, capsys):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO("not-json"))
    rc = CM.main(["write-vet-checks", "--cwd", repo, "--root", store])
    out = json.loads(capsys.readouterr().out)
    assert out["reason"] == "vet-checks-input-unparseable"


def test_cli_write_vet_checks_nested_duplicate(tmp_path, monkeypatch, capsys):
    repo, store = _setup_repo(tmp_path)
    raw = '[{"name": "a", "name": "b", "evidence": "e", "records": "r"}]'
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    rc = CM.main(["write-vet-checks", "--cwd", repo, "--root", store])
    out = json.loads(capsys.readouterr().out)
    assert out["reason"] == "duplicate-core-key:name"


def test_cli_write_vet_checks_malformed(tmp_path, monkeypatch, capsys):
    repo, store = _setup_repo(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_MALFORMED_SEED)))
    rc = CM.main(["write-vet-checks", "--cwd", repo, "--root", store])
    out = json.loads(capsys.readouterr().out)
    assert out["reason"] == "vet-checks-malformed"
    assert out["malformed"]
