"""Tests for cloud_setup_text (#1744 WO-B): the setup text writer.

Every fixture project is a real git repository under tmp_path; every store, home and Claude config
directory is under tmp_path too. No test reads the real home directory or the network, and every
token-shaped value is built at run time from small parts.
"""
import base64
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_pass  # noqa: E402
import cloud_setup  # noqa: E402
import mode_registry  # noqa: E402
import project_config  # noqa: E402
import store_core  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location(
        "cloud_setup_text", os.path.join(_LIB, "cloud_setup_text.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CS = _load()

VERSION = open(os.path.join(CS._plugin_root(), "version.txt")).read().strip()
SOURCE = "https://github.com/acme/superheroes.git"
COMMIT = "0123456789abcdef" * 2 + "01234567"
SUBDIR = "plugins/superheroes"
DAY_10_OCT = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc).timestamp()
DAY_5_MAR = datetime(2026, 3, 5, 12, 0, tzinfo=timezone.utc).timestamp()
ORIGIN = "https://github.com/acme/corner-shop.git"


class World:
    pass


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _world(tmp_path, mode):
    w = World()
    w.tmp = tmp_path
    w.repo = tmp_path / "repo"
    w.repo.mkdir()
    _git(w.repo, "init", "-q")
    _git(w.repo, "remote", "add", "origin", ORIGIN)
    w.cwd = str(w.repo)
    w.root = str(tmp_path / "store-root")
    w.home = tmp_path / "home"
    w.home.mkdir()
    w.env = {"HOME": str(w.home), "CLAUDE_CONFIG_DIR": str(tmp_path / "claude-config"),
             "PATH": os.environ.get("PATH", "")}
    remote_key = store_core.derive_identifiers(w.cwd)["remote_hash"]
    mode_registry.write_registry(w.cwd, mode, remote_key, root=w.root)
    w.store = mode_registry.project_store_dir(w.cwd, w.root)
    w.key = mode_registry.config_key(w.cwd)
    return w


def _put(w, rel, data):
    path = os.path.join(w.store, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


GLOBAL_FILES = {
    "config/core.md": b"# Core\nline two\n",
    "config/review-crew.md": b"# Crew\nsecond\n",
    "permission/rules.json": b'{"rules": []}\n',
    "meta.json": b'{"schemaVersion": 1}\n',
    "doc-policy.json": b'{"docs": "x"}\n',
}
EXCLUDED = {
    "config/core.md.bak-2026-01-01": b"BACKUP-MARKER\n",
    "state/x.json": b"STATE-MARKER\n",
    "config.lock": b"LOCK-MARKER\n",
}
EXPECTED_PATHS = ["config/core.md", "config/review-crew.md", "doc-policy.json", "meta.json",
                  "permission/rules.json", "registry.json"]


def _outside(tmp_path):
    w = _world(tmp_path, mode_registry.GLOBAL)
    for rel, data in {**GLOBAL_FILES, **EXCLUDED}.items():
        _put(w, rel, data)
    return w


def _inside(tmp_path):
    return _world(tmp_path, mode_registry.IN_REPO)


def _stamp(files):
    digest = hashlib.sha256(json.dumps(sorted((k, v.hex()) for k, v in files.items())).encode())
    return "2026-10-10:" + digest.hexdigest()[:12]


def _compose(w, **kw):
    args = dict(now=DAY_10_OCT, stamp_fn=_stamp, plugin_source=SOURCE, plugin_commit=COMMIT,
                plugin_subdir=SUBDIR, project_name="Corner Shop", root=w.root, env=w.env,
                source_dir=str(w.tmp / "opt" / "src"), plugin_dir=str(w.tmp / "opt" / "plugin"))
    args.update(kw)
    return CS.compose(w.cwd, **args)


def _refusal(result, reason):
    assert result["action"] == "refused" and result["reason"] == reason, result
    assert "text" not in result
    assert isinstance(result["detail"], str) and result["detail"]


def _heredoc(index, rel, data):
    tag = CS._end_tag(index)
    return """cat > "$DEST/%s" <<'%s'\n%s%s\n""" % (rel, tag, data.decode("utf-8"), tag)


# --- the outside-the-repository fixture ------------------------------------------------------

def test_outside_fixture_text_carries_everything_and_nothing_else(tmp_path):
    w = _outside(tmp_path)
    expected = CS.calibration_files(w.cwd, w.root)
    result = _compose(w)
    assert result["action"] == "written" and result["reason"] is None
    text = result["text"]
    assert result["header"] == "Corner Shop \u00b7 plugin %s \u00b7 calibration from 10 Oct" % VERSION
    assert text.splitlines()[1] == "# " + result["header"]
    assert result["pluginVersion"] == VERSION and result["pluginCommit"] == COMMIT
    assert result["picksUpVersionByItself"] is False
    assert 'git fetch -q --depth 1 "%s" %s' % (SOURCE, COMMIT) in text
    assert 'npm install -g "@openai/codex"' in text
    assert 'npm install -g "jscpd@5.0.12"' in text
    assert list(expected) == EXPECTED_PATHS
    assert result["calibration"]["files"] == EXPECTED_PATHS
    assert result["calibration"]["placed"] is True
    assert result["calibration"]["date"] == "2026-10-10"
    assert result["calibration"]["stamp"] == _stamp(expected)
    for index, (rel, data) in enumerate(expected.items(), 1):
        assert _heredoc(index, rel, data) in text
    assert "printf '%%s\\n' '%s' > \"$DEST/%s\"" % (result["calibration"]["stamp"],
                                                    "cloud-setup-stamp") in text
    for data in EXCLUDED.values():
        assert data.strip().decode() not in text
    assert text.splitlines()[0] == "#!/bin/bash"
    assert text.rstrip("\n").endswith("exit 0")


def test_scan_finds_nothing_for_pass_token_shapes_and_main_sign_in(tmp_path):
    w = _outside(tmp_path)
    text = _compose(w)["text"]
    assert CS._scan(text) is None
    signin = w.home / ".codex" / "auth.json"
    signin.parent.mkdir()
    tokens = {name: "ey" + "J" + name[:2] * 6 + "." + name[:3] * 5 + "." + name[:4] * 4
              for name in ("access_token", "id_token", "refresh_token")}
    signin.write_text(json.dumps({"auth_mode": "chatgpt", "tokens": tokens}))
    pass_value = base64.b64encode(signin.read_bytes()).decode("ascii")
    for value in list(tokens.values()) + [pass_value, cloud_pass.PASS_ENV]:
        assert value not in text
    for builder in (b for _, _, b in SHAPE_CASES):
        assert builder() not in text


# --- the in-repository fixture (registry written with mode_registry.write_registry) ----------

def test_inside_fixture_has_no_calibration_in_the_text(tmp_path):
    w = _inside(tmp_path)
    assert os.path.isfile(os.path.join(w.store, "registry.json"))
    assert CS.calibration_files(w.cwd, w.root) == {}
    result = _compose(w)
    text = result["text"]
    assert result["action"] == "written"
    assert "<<" not in text
    assert ".claude/superheroes/projects" not in text
    assert w.key not in text and CS.STAMP_FILE not in text
    assert result["calibration"] == {"placed": False, "files": [], "date": None, "stamp": None}
    assert result["header"].endswith("calibration in the repository")
    assert result["header"] == "Corner Shop \u00b7 plugin %s \u00b7 calibration in the repository" % VERSION


# --- the script runs ------------------------------------------------------------------------

def _stubs(tmp_path):
    stub = tmp_path / "stubs"
    stub.mkdir()
    log = tmp_path / "stub-calls.log"
    for name in ("git", "npm"):
        path = stub / name
        path.write_text('#!/bin/bash\necho "%s $*" >> "%s"\nexit 0\n' % (name, log))
        path.chmod(0o755)
    return stub, log


def _run_script(w, text):
    stub, log = _stubs(w.tmp)
    env = {"HOME": str(w.home), "PATH": "%s:/usr/bin:/bin" % stub}
    proc = subprocess.run(["bash", "-c", text], env=env, capture_output=True, text=True, timeout=60)
    return proc, log


def test_script_places_calibration_stamp_and_link(tmp_path):
    w = _outside(tmp_path)
    _put(w, "config/core.md", b"no trailing newline")
    expected = CS.calibration_files(w.cwd, w.root)
    assert expected["config/core.md"] == b"no trailing newline\n"
    result = _compose(w)
    proc, log = _run_script(w, result["text"])
    assert proc.returncode == 0, proc.stderr
    dest = w.home / ".claude" / "superheroes" / "projects" / w.key
    for rel, data in expected.items():
        assert (dest / rel).read_bytes() == data
    assert (dest / "cloud-setup-stamp").read_text() == result["calibration"]["stamp"] + "\n"
    assert not (dest / "config" / "core.md.bak-2026-01-01").exists()
    assert not (dest / "state").exists() and not (dest / "config.lock").exists()
    assert os.path.islink(str(w.tmp / "opt" / "plugin"))
    assert os.readlink(str(w.tmp / "opt" / "plugin")) == str(w.tmp / "opt" / "src" / SUBDIR)
    calls = log.read_text()
    assert COMMIT in calls and SOURCE in calls
    assert "npm install -g @openai/codex" in calls and "npm install -g jscpd@5.0.12" in calls
    setup_log = (w.home / "superheroes-cloud-setup.log").read_text()
    assert "calibration: 6 of 6 files written" in setup_log and "setup end" in setup_log


def test_script_exits_zero_even_when_every_tool_fails(tmp_path):
    w = _inside(tmp_path)
    text = _compose(w)["text"]
    stub = tmp_path / "failing"
    stub.mkdir()
    for name in ("git", "npm"):
        (stub / name).write_text("#!/bin/bash\nexit 1\n")
        (stub / name).chmod(0o755)
    env = {"HOME": str(w.home), "PATH": "%s:/usr/bin:/bin" % stub}
    proc = subprocess.run(["bash", "-c", text], env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0
    log = (w.home / "superheroes-cloud-setup.log").read_text()
    assert "plugin FAILED" in log and "reviewer cli FAILED" in log
    assert "duplication checker FAILED" in log


@pytest.mark.parametrize("build", [_outside, _inside])
def test_bash_syntax_check_passes(tmp_path, build):
    text = _compose(build(tmp_path))["text"]
    proc = subprocess.run(["bash", "-n"], input=text, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr


def test_default_paths_are_the_cloud_ones(tmp_path):
    w = _inside(tmp_path)
    text = CS.compose(w.cwd, plugin_source=SOURCE, plugin_commit=COMMIT, plugin_subdir=SUBDIR,
                      project_name="Corner Shop", root=w.root, env=w.env)["text"]
    assert 'SRC="/opt/superheroes/plugin-src"' in text
    assert 'LINK="%s"' % cloud_pass.CLOUD_PLUGIN_DIR in text
    assert 'mkdir -p "/opt/superheroes"' in text


# --- the head line --------------------------------------------------------------------------

def test_head_line_for_ten_october_and_a_single_digit_day(tmp_path):
    w = _outside(tmp_path)
    assert _compose(w, now=DAY_10_OCT)["header"] == (
        "Corner Shop \u00b7 plugin %s \u00b7 calibration from 10 Oct" % VERSION)
    assert _compose(w, now=DAY_5_MAR)["header"] == (
        "Corner Shop \u00b7 plugin %s \u00b7 calibration from 5 Mar" % VERSION)


def test_head_line_uses_the_utc_date_and_accepts_a_datetime(tmp_path):
    w = _outside(tmp_path)
    late = datetime.fromisoformat("2026-10-10T23:30:00-05:00")
    result = _compose(w, now=late)
    assert result["calibration"]["date"] == "2026-10-11"
    assert result["header"].endswith("calibration from 11 Oct")


def test_project_name_line_breaks_become_spaces_and_default_is_the_remote_repo(tmp_path):
    w = _inside(tmp_path)
    assert "a b c" in _compose(w, project_name="a\nb\r\nc")["header"]
    assert _compose(w, project_name=None)["header"].startswith("corner-shop \u00b7 ")
    bare = tmp_path / "bare-project"
    bare.mkdir()
    _git(bare, "init", "-q")
    assert CS._project_name(str(bare)) == "bare-project"


# --- discovery of the plugin's source --------------------------------------------------------

def _write_records(w, tweak=None):
    """Write the three plugin record files; `tweak` edits the dict of their parsed values, and a
    value set to None leaves that file absent, a string is written raw."""
    market_root = w.tmp / "market"
    parts = {
        "installed": {"plugins": {"superheroes@superheroes": [{
            "scope": "user", "installPath": CS._plugin_root(), "version": VERSION,
            "gitCommitSha": COMMIT}]}},
        "markets": {"superheroes": {"source": {"source": "git", "url": SOURCE},
                                    "installLocation": str(market_root)}},
        "listing": {"plugins": [{"name": "superheroes", "source": "./" + SUBDIR}]},
    }
    if tweak:
        tweak(parts)
    plugins = w.tmp / "claude-config" / "plugins"
    plugins.mkdir(parents=True, exist_ok=True)
    (market_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    paths = {"installed": plugins / "installed_plugins.json",
             "markets": plugins / "known_marketplaces.json",
             "listing": market_root / ".claude-plugin" / "marketplace.json"}
    for name, value in parts.items():
        if value is not None:
            paths[name].write_text(value if isinstance(value, str) else json.dumps(value))


def _discovering(w):
    return _compose(w, plugin_source=None, plugin_commit=None, plugin_subdir=None)


def test_discovery_reads_the_installed_record_and_the_marketplace(tmp_path):
    w = _inside(tmp_path)
    _write_records(w)
    result = _discovering(w)
    assert result["action"] == "written" and result["pluginCommit"] == COMMIT
    assert 'git fetch -q --depth 1 "%s" %s' % (SOURCE, COMMIT) in result["text"]
    assert 'ln -sfn "$SRC/%s" "$LINK"' % SUBDIR in result["text"]


def _set(name, value):
    return lambda parts: parts.__setitem__(name, value)


def _other_path(parts):
    parts["installed"]["plugins"]["superheroes@superheroes"][0]["installPath"] = "/nowhere/else"


def _no_sha(parts):
    del parts["installed"]["plugins"]["superheroes@superheroes"][0]["gitCommitSha"]


def _not_listed(parts):
    parts["listing"]["plugins"] = [{"name": "other", "source": "./x"}]


S1_CASES = {
    "installed-missing": _set("installed", None),
    "installed-unparseable": _set("installed", "{not json"),
    "installed-empty": _set("installed", {}),
    "no-matching-entry": _other_path,
    "no-commit": _no_sha,
    "markets-missing": _set("markets", None),
    "no-marketplace": _set("markets", {}),
    "no-listing-file": _set("listing", None),
    "plugin-not-listed": _not_listed,
}


@pytest.mark.parametrize("case", sorted(S1_CASES))
def test_s1_plugin_source_unknown(tmp_path, case):
    w = _inside(tmp_path)
    _write_records(w, S1_CASES[case])
    _refusal(_discovering(w), "plugin-source-unknown")


def test_s1_config_directory_unresolvable(tmp_path):
    w = _inside(tmp_path)
    w.env = {"CLAUDE_CONFIG_DIR": "relative/dir", "PATH": w.env["PATH"]}
    _refusal(CS.compose("relative-cwd-is-not-a-dir", plugin_source=None, root=w.root, env=w.env,
                        source_dir=str(tmp_path / "a" / "b"), plugin_dir=str(tmp_path / "c" / "d")),
             "plugin-source-unknown")


def test_s2_plugin_source_unsupported(tmp_path):
    w = _inside(tmp_path)

    def tweak(parts):
        parts["markets"]["superheroes"]["source"] = {"source": "github", "repo": "acme/superheroes"}

    _write_records(w, tweak)
    _refusal(_discovering(w), "plugin-source-unsupported")


# --- the edges ------------------------------------------------------------------------------

def test_s3_plugin_source_invalid_partial_and_bad_directories(tmp_path):
    w = _inside(tmp_path)
    _refusal(_compose(w, plugin_commit=None), "plugin-source-invalid")
    _refusal(_compose(w, plugin_subdir=None, plugin_commit=None), "plugin-source-invalid")
    for bad in ("relative/dir", "/opt", "/", "/opt/../etc", "/opt/with space/x", "/opt/./x"):
        _refusal(_compose(w, source_dir=bad), "plugin-source-invalid")
        _refusal(_compose(w, plugin_dir=bad), "plugin-source-invalid")


def test_s4_plugin_version_unreadable(tmp_path, monkeypatch):
    w = _inside(tmp_path)
    root = tmp_path / "fake-plugin"
    root.mkdir()
    monkeypatch.setattr(CS, "_plugin_root", lambda: str(root))
    _refusal(_compose(w), "plugin-version-unreadable")
    (root / "version.txt").write_text("  \n")
    _refusal(_compose(w), "plugin-version-unreadable")


def test_s5_storage_mode_unknown(tmp_path, monkeypatch):
    w = _inside(tmp_path)
    record = json.loads(open(os.path.join(w.store, "registry.json")).read())
    record["schemaVersion"] = mode_registry.SCHEMA_VERSION + 1
    _put(w, "registry.json", json.dumps(record).encode())
    _refusal(_compose(w), "storage-mode-unknown")
    monkeypatch.setattr(CS.mode_registry, "resolve", lambda *a, **k: {"mode": "somewhere-else"})
    _refusal(_compose(w), "storage-mode-unknown")


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0, reason="needs a non-root user")
def test_s6_calibration_unreadable(tmp_path):
    w = _outside(tmp_path)
    path = os.path.join(w.store, "config", "core.md")
    os.chmod(path, 0)
    try:
        _refusal(_compose(w), "calibration-unreadable")
    finally:
        os.chmod(path, 0o644)


@pytest.mark.parametrize("case", ["not-utf8", "nul", "bad-path", "end-tag-line"])
def test_s7_calibration_unplaceable(tmp_path, case):
    w = _world(tmp_path, mode_registry.GLOBAL)
    os.remove(os.path.join(w.store, "registry.json"))
    os.remove(os.path.join(w.store, "meta.json"))
    bodies = {"not-utf8": ("doc-policy.json", b"\xff\xfe\n"),
              "nul": ("doc-policy.json", b"a\x00b\n"),
              "bad-path": ("config/my notes.md", b"fine\n"),
              "end-tag-line": ("doc-policy.json", ("x\n%s\ny\n" % CS._end_tag(1)).encode())}
    rel, data = bodies[case]
    _put(w, rel, data)
    assert list(CS.calibration_files(w.cwd, w.root)) == [rel]
    _refusal(_compose(w), "calibration-unplaceable")


@pytest.mark.parametrize("stamp_fn", [lambda files: 1 / 0, lambda files: "bad stamp!",
                                      lambda files: "", lambda files: 7])
def test_s8_stamp_unavailable(tmp_path, stamp_fn):
    w = _outside(tmp_path)
    _refusal(_compose(w, stamp_fn=stamp_fn), "stamp-unavailable")


def test_s8_with_no_stamp_function_the_real_stamp_is_used(tmp_path):
    w = _outside(tmp_path)
    result = _compose(w, stamp_fn=None)
    assert result["action"] == "written"
    expected = cloud_setup.calibration_stamp(CS.stamped_files(w.cwd, w.root))
    assert result["calibration"]["stamp"] == expected


def test_s8_does_not_apply_when_the_repository_carries_the_calibration(tmp_path):
    assert _compose(_inside(tmp_path), stamp_fn=None)["action"] == "written"


def test_s10_calibration_missing(tmp_path):
    w = _world(tmp_path, mode_registry.GLOBAL)
    for name in ("registry.json", "meta.json"):
        os.remove(os.path.join(w.store, name))
    assert CS.calibration_files(w.cwd, w.root) == {}
    _refusal(_compose(w), "calibration-missing")


def test_a_project_with_no_record_resolves_global_and_is_s10(tmp_path):
    w = _world(tmp_path, mode_registry.GLOBAL)
    _refusal(_compose(w, root=str(tmp_path / "empty-store")), "calibration-missing")


def test_precedence_s4_then_s3_then_s1_then_s5(tmp_path, monkeypatch):
    w = _inside(tmp_path)
    nothing = dict(plugin_source=None, plugin_commit=None, plugin_subdir=None)
    # S3 (partial) beats S1 (nothing discoverable) beats S5 (unknown storage mode).
    monkeypatch.setattr(CS.mode_registry, "resolve", lambda *a, **k: {"mode": "odd"})
    _refusal(_compose(w, **{**nothing, "plugin_source": SOURCE}), "plugin-source-invalid")
    _refusal(_compose(w, **nothing), "plugin-source-unknown")
    _refusal(_compose(w), "storage-mode-unknown")
    # S4 beats S3.
    root = tmp_path / "fake-plugin"
    root.mkdir()
    monkeypatch.setattr(CS, "_plugin_root", lambda: str(root))
    _refusal(_compose(w, plugin_commit="nope"), "plugin-version-unreadable")


def test_precedence_s7_beats_s8(tmp_path):
    w = _world(tmp_path, mode_registry.GLOBAL)
    _put(w, "doc-policy.json", b"a\x00\n")
    _refusal(_compose(w, stamp_fn=None), "calibration-unplaceable")


def _provider(prefix):
    return lambda: prefix + "k" * 20


def _assignment(name, quote=True):
    if quote:
        return lambda: '{"%s": "%s"}' % (name, "v" * 12)
    return lambda: "%s=%s" % (name, "v" * 12)


SHAPE_CASES = [
    ("signed token", "signed-token",
     lambda: "ey" + "J" + "h" * 10 + "." + "p" * 10 + "." + "s" * 10),
    *[("provider key", "prefix-" + p, _provider(p)) for p in (
        "sk-", "ghp_", "gho_", "ghu_", "ghs_", "github_pat_", "xoxb-", "xoxp-", "xoxa-")],
    ("provider key", "prefix-AKIA", lambda: "AKIA" + "A1" * 8),
    ("private key block", "private-key",
     lambda: "-----BEGIN " + "RSA PRIVATE" + " KEY-----"),
    *[("credential assignment", "json-" + n, _assignment(n)) for n in (
        "access_token", "id_token", "refresh_token", "OPENAI_API_KEY", cloud_pass.PASS_ENV)],
    ("credential assignment", "shell-pass-env", _assignment(cloud_pass.PASS_ENV, quote=False)),
    ("bearer credential", "bearer", lambda: "Bearer " + "t" * 20),
]


def test_every_scan_shape_has_a_case():
    assert {name for name, _ in CS._SECRET_SHAPES} == {name for name, _, _ in SHAPE_CASES}


@pytest.mark.parametrize("shape,builder", [(s, b) for s, _, b in SHAPE_CASES],
                         ids=[i for _, i, _ in SHAPE_CASES])
def test_s9_secret_shaped_content(tmp_path, shape, builder):
    w = _outside(tmp_path)
    planted = builder()
    _put(w, "config/core.md", ("note: %s\n" % planted).encode())
    result = _compose(w)
    _refusal(result, "secret-shaped-content")
    assert shape in result["detail"] and "config/core.md" in result["detail"]
    assert planted not in json.dumps(result)
    assert planted.split(":")[-1].strip(' "}') not in result["detail"]


def test_s9_in_the_head_line_names_the_shape_only(tmp_path):
    w = _inside(tmp_path)
    planted = "Bearer " + "t" * 20
    result = _compose(w, project_name=planted)
    _refusal(result, "secret-shaped-content")
    assert "bearer credential" in result["detail"] and planted not in result["detail"]
    assert "(in " not in result["detail"]


@pytest.mark.parametrize("field,value", [
    ("plugin_source", "https://github.com/a/b'.git"),
    ("plugin_source", "https://github.com/a/b .git"),
    ("plugin_source", "https://github.com/a/$(id).git"),
    ("plugin_source", "https://github.com/a/b;ls"),
    ("plugin_source", "https://user:pw@github.com/a/b.git"),
    ("plugin_source", "http://github.com/a/b.git"),
    ("plugin_source", "git@github.com:a/b.git"),
    ("plugin_commit", "main"),
    ("plugin_commit", COMMIT[:39]),
    ("plugin_commit", COMMIT.upper()),
    ("plugin_commit", COMMIT + "\n"),
    ("plugin_subdir", "plugins/../etc"),
    ("plugin_subdir", "/plugins/superheroes"),
    ("plugin_subdir", "plugins/super heroes"),
    ("plugin_subdir", ""),
])
def test_injection_is_refused_as_plugin_source_invalid(tmp_path, field, value):
    w = _inside(tmp_path)
    _refusal(_compose(w, **{field: value}), "plugin-source-invalid")


# --- the command line -----------------------------------------------------------------------

def _cli_args(w, *extra):
    return ["write", "--cwd", w.cwd, "--root", w.root, "--plugin-source", SOURCE,
            "--plugin-commit", COMMIT, "--plugin-subdir", SUBDIR, "--project-name", "Corner Shop",
            *extra]


def test_cli_write_prints_the_script(tmp_path, capsys):
    w = _inside(tmp_path)
    assert CS.main(_cli_args(w)) == 0
    out = capsys.readouterr()
    assert out.out.startswith("#!/bin/bash\n# Corner Shop") and out.err == ""


def test_cli_runs_as_a_script(tmp_path):
    w = _inside(tmp_path)
    proc = subprocess.run([sys.executable, os.path.join(_LIB, "cloud_setup_text.py"), *_cli_args(w)],
                          capture_output=True, text=True, timeout=60,
                          env={**os.environ, **w.env})
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("#!/bin/bash\n")


def test_cli_refusal_prints_nothing_on_standard_output(tmp_path, capsys):
    w = _inside(tmp_path)
    args = _cli_args(w)
    args[args.index("--plugin-commit") + 1] = "not-a-commit"
    assert CS.main(args) == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert json.loads(out.err)["reason"] == "plugin-source-invalid"


def test_cli_write_prints_the_script_for_outside_calibration(tmp_path, capsys):
    w = _outside(tmp_path)
    assert CS.main(_cli_args(w)) == 0
    out = capsys.readouterr()
    assert out.out.startswith("#!/bin/bash\n# Corner Shop") and out.err == ""


def test_cli_clipboard_prints_the_result_without_text(tmp_path, capsys, monkeypatch):
    w = _inside(tmp_path)
    bin_dir = tmp_path / "clipbin"
    bin_dir.mkdir()
    sink = tmp_path / "clip.txt"
    (bin_dir / "fakeclip").write_text("#!/bin/sh\ncat > %s\n" % sink)
    (bin_dir / "fakeclip").chmod(0o755)
    monkeypatch.setattr(cloud_pass, "_CLIPBOARD_COMMANDS", (("fakeclip",),))
    monkeypatch.setenv("PATH", "%s:%s" % (bin_dir, os.environ["PATH"]))
    assert CS.main(_cli_args(w, "--clipboard")) == 0
    printed = json.loads(capsys.readouterr().out)
    assert "text" not in printed and printed["action"] == "written"
    assert sink.read_text().startswith("#!/bin/bash\n")


def test_cli_clipboard_missing_is_a_refusal(tmp_path, capsys, monkeypatch):
    w = _inside(tmp_path)
    monkeypatch.setattr(cloud_pass, "_CLIPBOARD_COMMANDS", (("no-such-clipboard-command",),))
    assert CS.main(_cli_args(w, "--clipboard")) == 1
    out = capsys.readouterr()
    assert out.out == "" and json.loads(out.err)["reason"] == "no-clipboard"


# --- the stamp leaves the cloud-builds setting out ------------------------------------------

STAMP_SHAPE = re.compile(r"sha256:[0-9a-f]{64}")


def _core(setting="absent", other="a", prose="intro"):
    settings = {"other": other}
    if setting != "absent":
        settings[project_config.CLOUD_BUILDS_SLUG] = setting
    body = json.dumps({"projectConfiguration": settings, "name": "x"}, indent=2)
    return ("# Core\n%s\n```json superheroes-core\n%s\n```\ntail\n" % (prose, body)).encode()


def _real(w, core=None, **kw):
    if core is not None:
        _put(w, "config/core.md", core)
    return _compose(w, stamp_fn=None, **kw)


def test_toggling_the_setting_leaves_the_stamp_unchanged(tmp_path):
    w = _outside(tmp_path)
    results = {state: _real(w, _core(state)) for state in ("absent", False, True)}
    stamps = {r["calibration"]["stamp"] for r in results.values()}
    assert len(stamps) == 1 and STAMP_SHAPE.fullmatch(stamps.pop())
    texts = {state: r["text"] for state, r in results.items()}
    assert len(set(texts.values())) == 3
    for state, text in texts.items():
        assert _core(state).decode()[:-1] in text


@pytest.mark.parametrize("change", ["other-key", "prose", "other-file"])
def test_any_other_change_moves_the_stamp(tmp_path, change):
    w = _outside(tmp_path)
    base = _real(w, _core())["calibration"]["stamp"]
    if change == "other-file":
        _put(w, "config/review-crew.md", b"# Crew\nchanged\n")
        moved = _real(w)
    else:
        moved = _real(w, _core(other="b") if change == "other-key" else _core(prose="edited"))
    assert STAMP_SHAPE.fullmatch(moved["calibration"]["stamp"])
    assert moved["calibration"]["stamp"] != base


@pytest.mark.parametrize("core", [
    b"# Core\nno block here\n",
    b"# Core\n```json superheroes-core\n{not json\n```\n",
    b"# Core\n```json superheroes-core\n[1, 2]\n```\n",
    b"# Core\n```json superheroes-core\n{}\n```\n```json superheroes-core\n{}\n```\n",
], ids=["no-block", "not-json", "not-object", "two-blocks"])
def test_a_core_without_a_readable_setting_is_stamped_as_placed(tmp_path, core):
    w = _outside(tmp_path)
    result = _real(w, core)
    assert result["action"] == "written"
    placed = cloud_setup.calibration_stamp(CS.calibration_files(w.cwd, w.root))
    assert result["calibration"]["stamp"] == placed


# --- external literals ----------------------------------------------------------------------

def test_external_literals_are_pinned():
    assert CS.REVIEWER_CLI_PACKAGE == "@openai/codex"
    assert CS.DUPLICATION_CHECKER_PACKAGE == "jscpd@5.0.12"
    assert CS.SOURCE_DIR == "/opt/superheroes/plugin-src"
    assert CS.STAMP_FILE == "cloud-setup-stamp"
    assert CS.PICKS_UP_VERSION_BY_ITSELF is False
