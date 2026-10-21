"""Tests for cloud_setup_text (#1744 WO-B): the setup text writer.

Every fixture project is a real git repository under tmp_path; every store, home and Claude config
directory is under tmp_path too. No test reads the real home directory or the network, and every
token-shaped value is built at run time from small parts.
"""
import base64
import difflib
import hashlib
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import architect_config  # noqa: E402
import cloud_check  # noqa: E402
import cloud_pass  # noqa: E402
import cloud_plugin_pin  # noqa: E402
import cloud_setup  # noqa: E402
import core_md  # noqa: E402
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
    signin = w.home / ".codex" / "auth.json"
    signin.parent.mkdir()
    tokens = {name: "ey" + "J" + name[:2] * 6 + "." + name[:3] * 5 + "." + name[:4] * 4
              for name in ("access_token", "id_token", "refresh_token")}
    signin.write_text(json.dumps({"auth_mode": "chatgpt", "tokens": tokens}))
    pass_value = base64.b64encode(signin.read_bytes()).decode("ascii")
    w.env[cloud_pass.PASS_ENV] = pass_value
    result = _compose(w)
    assert result["action"] == "written"
    text = result["text"]
    assert CS._scan(text) is None
    for value in list(tokens.values()) + [pass_value, cloud_pass.PASS_ENV]:
        assert value not in text and value not in json.dumps(result["calibration"])
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


def test_inside_fixture_carries_exactly_the_machine_local_document_policy(tmp_path):
    import architect_config
    w = _inside(tmp_path)
    policy = json.dumps({"location": "specs/custom", "visibility": "committed",
                         "confirmed": True}).encode() + b"\n"
    _put(w, "doc-policy.json", policy)
    _put(w, "config/core.md", b"IN-REPO-CALIBRATION-MARKER\n")
    assert CS.calibration_files(w.cwd, w.root) == {"doc-policy.json": policy}
    result = _compose(w)
    assert result["header"].endswith("calibration in the repository")
    assert result["calibration"]["placed"] is False
    assert result["calibration"]["files"] == ["doc-policy.json"]
    assert result["calibration"]["stamp"] == _stamp({"doc-policy.json": policy})
    assert "IN-REPO-CALIBRATION-MARKER" not in result["text"]
    proc, _ = _run_script(w, result["text"])
    assert proc.returncode == 0, proc.stderr
    cloud_root = str(w.home / ".claude" / "superheroes")
    assert architect_config.read_policy(w.cwd, cloud_root)["location"] == "specs/custom"
    assert architect_config.read_policy(w.cwd, w.root)["location"] == "specs/custom"


# --- the script runs ------------------------------------------------------------------------

def _stubs(tmp_path, code=0, apt_install_fails_first=False):
    stub = tmp_path / "stubs"
    stub.mkdir()
    log = tmp_path / "stub-calls.log"
    for name in ("git", "npm", "apt-get", "uv"):
        path = stub / name
        path.write_text('#!/bin/bash\necho "%s $*" >> "%s"\nexit %d\n' % (name, log, code))
        path.chmod(0o755)
    # `uv` also records whether UV_PYTHON reached it, and (in a second log) where it ran.
    (stub / "uv").write_text(
        '#!/bin/bash\n'
        'echo "uv $* UV_PYTHON=${UV_PYTHON-unset}" >> "%s"\n'
        'echo "$PWD" >> "%s"\n'
        'exit %d\n' % (log, tmp_path / "uv-cwd.log", code)
    )
    if apt_install_fails_first:
        # `apt-get install` fails the first time it is run and succeeds after; every other
        # `apt-get` verb (`update`) succeeds. A counter file carries the count between runs.
        counter = tmp_path / "apt-install-count"
        (stub / "apt-get").write_text(
            '#!/bin/bash\n'
            'echo "apt-get $*" >> "%s"\n'
            'if [ "$1" = install ]; then\n'
            '  n=$(cat "%s" 2>/dev/null || echo 0)\n'
            '  n=$((n + 1))\n'
            '  echo "$n" > "%s"\n'
            '  [ "$n" -ge 2 ] || exit 1\n'
            'fi\n'
            'exit 0\n' % (log, counter, counter)
        )
    return stub, log


def _run_script(w, text, code=0, pinned=False, apt_install_fails_first=False, pin_in=None,
                extra_env=None, pin_text="3.12\n", git_clone=False):
    """Runs the script from a working directory of its own, with every tool stubbed to exit `code`
    (or, with `apt_install_fails_first`, `apt-get install` failing once and then succeeding).
    `pinned` puts a `.python-version` in the working directory; `pin_in` puts it in that named
    directory inside the working directory instead; `extra_env` is added to the script's env;
    `git_clone` puts a stub clone (a `.git` directory) at `work/corner-shop`, or in `work` itself
    when it is "here"."""
    stub, log = _stubs(w.tmp, code, apt_install_fails_first)
    work = w.tmp / "work"
    work.mkdir()
    if git_clone == "here":
        (work / ".git").mkdir()
    elif git_clone:
        (work / "corner-shop" / ".git").mkdir(parents=True)
    if pin_in is not None:
        (work / pin_in).mkdir()
        (work / pin_in / ".python-version").write_text(pin_text)
    elif pinned:
        (work / ".python-version").write_text(pin_text)
    env = {"HOME": str(w.home), "PATH": "%s:/usr/bin:/bin" % stub, **(extra_env or {})}
    proc = subprocess.run(["bash", "-c", text], env=env, capture_output=True, text=True, timeout=60,
                          cwd=str(work))
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


def test_script_destination_comes_from_the_shared_store_layout(tmp_path):
    w = _outside(tmp_path)
    expected = mode_registry.project_store_dir(w.cwd, "$HOME/.claude/superheroes")
    assert 'DEST="%s"' % expected in _compose(w)["text"]


def test_script_publishes_no_stamp_when_a_calibration_file_cannot_be_written(tmp_path):
    w = _outside(tmp_path)
    dest = w.home / ".claude" / "superheroes" / "projects" / w.key
    (dest / "config" / "core.md").mkdir(parents=True)
    (dest / "cloud-setup-stamp").write_text("stale\n")
    proc, _ = _run_script(w, _compose(w)["text"])
    assert proc.returncode == 0
    assert not (dest / "cloud-setup-stamp").exists()
    assert "calibration FAILED" in (w.home / "superheroes-cloud-setup.log").read_text()


def test_script_exits_zero_even_when_every_tool_fails(tmp_path):
    w = _inside(tmp_path)
    proc, log = _run_script(w, _compose(w)["text"], code=1, pinned=True)
    assert proc.returncode == 0, proc.stderr
    setup_log = (w.home / "superheroes-cloud-setup.log").read_text()
    assert "plugin FAILED" in setup_log and "reviewer cli FAILED" in setup_log
    assert "duplication checker FAILED" in setup_log
    calls = log.read_text()
    assert "apt-get " in calls and "uv " in calls


def test_setup_text_installs_the_sandbox_tools_and_the_pinned_python_before_the_wait(tmp_path):
    lines = _compose(_inside(tmp_path))["text"].splitlines()
    install = "apt-get install -y bubblewrap socat"
    wait = lines.index("wait")
    marker = lines.index(CS.TOOL_STEPS_MARKER)
    assert any(install in line for line in lines[:wait])
    assert any("uv python install" in line for line in lines[:wait])
    assert wait < marker


def test_failing_sandbox_tools_and_pinned_python_are_logged_and_the_script_exits_zero(tmp_path):
    w = _inside(tmp_path)
    proc, log = _run_script(w, _compose(w)["text"], code=1, pinned=True)
    assert proc.returncode == 0, proc.stderr
    setup_log = (w.home / "superheroes-cloud-setup.log").read_text()
    assert "sandbox tools FAILED" in setup_log and "pinned python FAILED" in setup_log
    assert "sandbox tools ok" not in setup_log and "pinned python ok" not in setup_log
    assert "apt-get update" in log.read_text()


def test_working_sandbox_tools_and_pinned_python_are_logged_ok(tmp_path):
    w = _inside(tmp_path)
    proc, log = _run_script(w, _compose(w)["text"], pinned=True)
    assert proc.returncode == 0, proc.stderr
    setup_log = (w.home / "superheroes-cloud-setup.log").read_text()
    assert "sandbox tools ok" in setup_log and "pinned python ok" in setup_log
    calls = log.read_text().splitlines()
    assert "uv python install UV_PYTHON=unset" in calls
    assert "apt-get install -y bubblewrap socat" in calls
    assert "apt-get update" not in calls


def test_a_sandbox_tools_install_that_fails_once_is_retried_after_apt_update(tmp_path):
    # axis: the first `apt-get install` failing does not fail the step — `apt-get update` runs
    # once, the install runs a second time, and the log says ok — see bite-proof record c8c_wo_b.md
    w = _inside(tmp_path)
    proc, log = _run_script(w, _compose(w)["text"], pinned=True, apt_install_fails_first=True)
    assert proc.returncode == 0, proc.stderr
    setup_log = (w.home / "superheroes-cloud-setup.log").read_text()
    assert "sandbox tools ok" in setup_log
    assert "sandbox tools FAILED" not in setup_log
    apt_calls = [line for line in log.read_text().splitlines() if line.startswith("apt-get ")]
    assert apt_calls == [
        "apt-get install -y bubblewrap socat",
        "apt-get update",
        "apt-get install -y bubblewrap socat",
    ], apt_calls


def test_no_python_version_file_is_logged_by_directory_and_uv_is_never_called(tmp_path):
    w = _inside(tmp_path)
    proc, log = _run_script(w, _compose(w)["text"])
    assert proc.returncode == 0, proc.stderr
    setup_log = (w.home / "superheroes-cloud-setup.log").read_text()
    work = w.tmp / "work"
    assert "pinned python: no .python-version in %s or %s/corner-shop" % (work, work) in setup_log
    assert "pinned python ok" not in setup_log and "pinned python FAILED" not in setup_log
    assert "uv " not in log.read_text()


def test_pinned_python_is_installed_from_the_clone_when_the_script_runs_from_its_parent(tmp_path):
    # axis: the pin is found from the clone's parent directory
    w = _inside(tmp_path)
    proc, log = _run_script(w, _compose(w)["text"], pin_in="corner-shop")
    assert proc.returncode == 0, proc.stderr
    setup_log = (w.home / "superheroes-cloud-setup.log").read_text()
    assert "pinned python ok" in setup_log and "pinned python FAILED" not in setup_log
    assert "uv python install UV_PYTHON=unset" in log.read_text().splitlines()


def test_an_inherited_uv_python_does_not_change_the_installed_pin(tmp_path):
    # axis: the installed version is the file's, not the environment's — an inherited UV_PYTHON
    # never reaches uv, and uv runs in the clone directory where it reads the file
    w = _inside(tmp_path)
    proc, log = _run_script(w, _compose(w)["text"], pin_in="corner-shop",
                            extra_env={"UV_PYTHON": "3.11"})
    assert proc.returncode == 0, proc.stderr
    uv_calls = [line for line in log.read_text().splitlines() if line.startswith("uv ")]
    assert uv_calls == ["uv python install UV_PYTHON=unset"], uv_calls
    assert (w.tmp / "uv-cwd.log").read_text().splitlines() == [str(w.tmp / "work" / "corner-shop")]


def test_a_commented_python_version_file_is_read_by_uv_not_flattened(tmp_path):
    # axis: uv parses the version file itself (comments and all), not the shell
    w = _inside(tmp_path)
    proc, log = _run_script(w, _compose(w)["text"], pin_in="corner-shop",
                            pin_text="3.12\n# project interpreter\n")
    assert proc.returncode == 0, proc.stderr
    setup_log = (w.home / "superheroes-cloud-setup.log").read_text()
    assert "pinned python ok" in setup_log and "pinned python FAILED" not in setup_log
    calls = log.read_text()
    assert [line for line in calls.splitlines() if line.startswith("uv ")] == [
        "uv python install UV_PYTHON=unset"
    ]
    assert "3.12#projectinterpreter" not in calls


@pytest.mark.parametrize("pin_text", [" \n\t\n", "# nothing\n\n"])
def test_an_empty_python_version_file_fails_the_step_without_calling_uv(tmp_path, pin_text):
    w = _inside(tmp_path)
    proc, log = _run_script(w, _compose(w)["text"], pin_in="corner-shop", pin_text=pin_text)
    assert proc.returncode == 0, proc.stderr
    setup_log = (w.home / "superheroes-cloud-setup.log").read_text()
    assert "pinned python FAILED" in setup_log and "pinned python ok" not in setup_log
    assert "uv " not in log.read_text()


def test_clone_dir_is_the_remote_repo_name_or_none(tmp_path):
    w = _inside(tmp_path)
    assert CS._clone_dir(w.cwd) == "corner-shop"
    bare = tmp_path / "no-remote"
    bare.mkdir()
    _git(bare, "init", "-q")
    assert CS._clone_dir(str(bare)) is None
    for url in ("https://github.com/acme/a b", "https://github.com/acme/a$b",
                "https://github.com/acme/.."):
        _git(w.repo, "remote", "set-url", "origin", url)
        assert CS._clone_dir(w.cwd) is None, url


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
        parts["markets"]["superheroes"]["source"] = {"source": "directory", "path": "/x"}

    _write_records(w, tweak)
    _refusal(_discovering(w), "plugin-source-unsupported")


def test_discovery_accepts_the_github_marketplace_source(tmp_path):
    w = _inside(tmp_path)

    def tweak(parts):
        parts["markets"]["superheroes"]["source"] = {"source": "github", "repo": "acme/superheroes"}

    _write_records(w, tweak)
    result = _discovering(w)
    assert result["action"] == "written"
    assert 'git fetch -q --depth 1 "%s" %s' % (SOURCE, COMMIT) in result["text"]


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
        "sk-", "ghp_", "gho_", "ghu_", "ghs_", "github_pat_", "xoxb-", "xoxp-", "xoxa-",
        "ghr_", "xoxr-", "xoxs-", "sess-", "rt_")],
    ("provider key", "prefix-AKIA", lambda: "AKIA" + "A1" * 8),
    ("private key block", "private-key",
     lambda: "-----BEGIN " + "RSA PRIVATE" + " KEY-----"),
    *[("credential assignment", "json-" + n, _assignment(n)) for n in (
        "access_token", "id_token", "refresh_token", "OPENAI_API_KEY", cloud_pass.PASS_ENV)],
    ("credential assignment", "shell-pass-env", _assignment(cloud_pass.PASS_ENV, quote=False)),
    ("bearer credential", "bearer", lambda: "Bearer " + "t" * 20),
    ("registry token", "npm-token", lambda: "npm_" + "a1B2c3D4" * 4),
    ("registry token", "npm-auth-token",
     lambda: "//registry.example.com/:_authToken=" + "k" * 12),
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


def test_url_credential_env_reference_passes():
    assert CS._plain_shape("pip install --index-url https://builder:${PIP_PASS}@host/simple x") is None
    assert CS._plain_shape("git clone https://github.com/a/b.git") is None


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


def test_the_first_setting_leaves_the_stamp_of_a_core_without_configuration(tmp_path):
    w = _outside(tmp_path)
    bare = b'# Core\n```json superheroes-core\n{\n  "name": "x"\n}\n```\n'
    first = bare.replace(b'"name": "x"', b'"name": "x",\n  "projectConfiguration": {"%s": true}'
                         % project_config.CLOUD_BUILDS_SLUG.encode())
    assert (_real(w, bare)["calibration"]["stamp"] == _real(w, first)["calibration"]["stamp"])


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


def _encoded_pass():
    signin = {"auth_mode": "chatgpt", "OPENAI_API_KEY": None,
              "tokens": {"id_token": "i" * 20, "access_token": "a" * 20, "refresh_token": ""}}
    return base64.b64encode(json.dumps(signin).encode()).decode("ascii")


@pytest.mark.parametrize("form", [
    "{value}",
    '{{"SUPERHEROES_REVIEWER_PASS": " {value}"}}',
    "**SUPERHEROES_REVIEWER_PASS**: {value}",
    "__{value}__",
], ids=["bare", "quoted-leading-space", "markdown-labelled", "underscore-emphasis"])
def test_s9_encoded_reviewer_pass_is_refused(tmp_path, form):
    w = _outside(tmp_path)
    planted = _encoded_pass()
    _put(w, "config/core.md", ("note: %s\n" % form.format(value=planted)).encode())
    result = _compose(w)
    _refusal(result, "secret-shaped-content")
    assert planted not in json.dumps(result)


def test_encoded_pass_split_by_markdown_emphasis_is_still_found():
    planted = _encoded_pass()
    assert CS._scan("note: " + planted[:50] + "**" + planted[50:]) == "encoded credential"


def test_provider_key_shape_covers_every_cloud_setup_prefix():
    import cloud_setup
    for prefix in cloud_setup._SECRET_PREFIXES:
        assert CS._scan(prefix + "A1" * 10) == "provider key"


def test_inside_policy_is_selected_by_the_owning_modules_filename(tmp_path, monkeypatch):
    import architect_config
    w = _inside(tmp_path)
    _put(w, "moved-policy.json", b"{}\n")
    monkeypatch.setattr(architect_config, "policy_path",
                        lambda cwd, root=None: os.path.join(w.store, "moved-policy.json"))
    assert list(CS.calibration_files(w.cwd, w.root)) == ["moved-policy.json"]


# --- the file names come from the modules that own them ------------------------------------

def test_writer_follows_a_renamed_registry_file(tmp_path, monkeypatch):
    w = _outside(tmp_path)
    monkeypatch.setattr(mode_registry, "REGISTRY_FILENAME", "renamed-registry.json")
    _put(w, "renamed-registry.json", b"{}\n")
    files = CS.calibration_files(w.cwd, w.root)
    assert "renamed-registry.json" in files and "registry.json" not in files


def test_writer_follows_a_renamed_meta_file(tmp_path, monkeypatch):
    w = _outside(tmp_path)
    monkeypatch.setattr(mode_registry, "META_FILENAME", "renamed-meta.json")
    _put(w, "renamed-meta.json", b"{}\n")
    files = CS.calibration_files(w.cwd, w.root)
    assert "renamed-meta.json" in files and "meta.json" not in files


def test_writer_follows_a_renamed_core_file_and_config_directory(tmp_path, monkeypatch):
    w = _outside(tmp_path)
    monkeypatch.setattr(core_md, "CORE_FILENAME", "renamed-core.md")
    monkeypatch.setattr(mode_registry, "CONFIG_DIRNAME", "renamed-config")
    _put(w, "renamed-config/renamed-core.md", _core(True))
    files = CS.calibration_files(w.cwd, w.root)
    assert list(files) == ["doc-policy.json", "meta.json", "permission/rules.json",
                           "registry.json", "renamed-config/renamed-core.md"]
    stamped = CS.stamped_files(w.cwd, w.root)
    assert stamped["renamed-config/renamed-core.md"] == CS._without_setting(_core("absent"))
    assert project_config.CLOUD_BUILDS_SLUG.encode() not in stamped["renamed-config/renamed-core.md"]
    assert project_config.CLOUD_BUILDS_SLUG.encode() in files["renamed-config/renamed-core.md"]


def test_writer_follows_a_renamed_policy_file_outside_the_repository(tmp_path, monkeypatch):
    w = _outside(tmp_path)
    _put(w, "moved-policy.json", b"{}\n")
    monkeypatch.setattr(architect_config, "policy_path",
                        lambda cwd, root=None: os.path.join(w.store, "moved-policy.json"))
    files = CS.calibration_files(w.cwd, w.root)
    assert "moved-policy.json" in files and "doc-policy.json" not in files


def test_writer_spells_no_calibration_name_itself():
    with open(os.path.join(_LIB, "cloud_setup_text.py"), encoding="utf-8") as fh:
        source = fh.read()
    for owned in ("registry.json", "meta.json", "doc-policy.json", "core.md", "config"):
        assert '"%s"' % owned not in source, owned
    assert re.search(r'"[^"\n]*/core\.md"', source) is None


def test_a_command_under_the_tool_steps_marker_runs(tmp_path):
    w = _inside(tmp_path)
    text = _compose(w)["text"]
    lines = text.split("\n")
    assert lines.count(CS.TOOL_STEPS_MARKER) == 1 and text.count(CS.TOOL_STEPS_MARKER) == 1
    assert CS.TOOL_STEPS_MARKER == "# The project's own tool steps, if any, go below this line."
    out = tmp_path / "tool-step-output.txt"
    at = lines.index(CS.TOOL_STEPS_MARKER)
    lines.insert(at + 1, 'echo toolstepword >> "%s"' % out)
    proc, _ = _run_script(w, "\n".join(lines))
    assert proc.returncode == 0, proc.stderr
    assert out.read_text() == "toolstepword\n"


# --- the project's own setup commands (configure item 17) ------------------------------------

_UNSET = object()
_CORE_FACTS = {"verifyCommand": "npm test", "stackTags": ["node"], "threatModel": "single-user",
               "patterns": "- x: a.ts:1"}
SLUG = "cloudSetupCommands"


def _edit_core_block(w, edit):
    """Writes a real core when the project has none that parses, then lets `edit` change the
    parsed json block and writes it back."""
    if core_md.read(w.cwd, w.root, persist_backfill=False) is None:
        stale = core_md.core_path(w.cwd, w.root, persist_backfill=False)
        if os.path.exists(stale):
            os.remove(stale)
        done =core_md.write(w.cwd, dict(_CORE_FACTS), "confirmed", root=w.root, now="2026-06-26")
        assert done["action"] in ("written", "reused"), done
    path = core_md.core_path(w.cwd, w.root, persist_backfill=False)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    obj = json.loads(core_md._json_block_inner_text(text))
    edit(obj)
    spliced = core_md._splice_single_json_block(text, json.dumps(obj, indent=2, sort_keys=True))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(spliced)


def _store_commands(w, value):
    """Stores `value` under item 17 in the project's core, whatever it is (no validation)."""
    def edit(obj):
        settings = obj.setdefault("projectConfiguration", {})
        if value is _UNSET:
            settings.pop(SLUG, None)
        else:
            settings[SLUG] = value
    _edit_core_block(w, edit)


def _both_modes(tmp_path):
    worlds = []
    for name, make in (("outside", _outside), ("inside", _inside)):
        (tmp_path / name).mkdir()
        worlds.append((name, make(tmp_path / name)))
    return worlds


def test_two_setup_commands_are_one_block_in_order_after_every_step_before_the_marker(tmp_path):
    commands = ["npm ci", "make 'build all'"]
    for name, w in _both_modes(tmp_path):
        _store_commands(w, commands)
        text = _compose(w)["text"]
        assert text.count("# Run the project's own setup commands") == 1
        lines = text.splitlines()
        start = next(i for i, ln in enumerate(lines) if ln.startswith("# Run the project's own"))
        # axis: the commands are listed once, quoted, in the stored order
        assert "  for cmd in %s; do" % " ".join(shlex.quote(c) for c in commands) in lines
        # axis: the block sits after the last step (the wait, and the calibration block when
        # there is one) and before the marker
        marker = lines.index(CS.TOOL_STEPS_MARKER)
        assert lines.index("wait") < start < marker
        if name == "outside":
            assert max(i for i, ln in enumerate(lines) if ln.startswith('echo "calibration:')) < start
        proc = subprocess.run(["bash", "-n"], input=text, text=True, capture_output=True)
        assert proc.returncode == 0, proc.stderr


def _setup_log(w):
    return (w.home / "superheroes-cloud-setup.log").read_text()


def test_setup_commands_run_in_the_clone_and_the_first_failure_skips_the_rest(tmp_path):
    w = _inside(tmp_path)
    _store_commands(w, ['echo first >> "$PWD/ran.txt"; exit 3', 'echo second >> "$PWD/ran.txt"'])
    proc, _ = _run_script(w, _compose(w)["text"], git_clone=True)
    # axis: a listed command that failed or was skipped ends non-zero, so an unfinished setup is not cached
    assert proc.returncode == 1, proc.stderr
    log = _setup_log(w)
    assert "setup command 1 FAILED" in log
    # axis: a command after a failed one is skipped, never run
    assert "setup command 2 skipped: setup command 1 FAILED" in log
    assert "setup command 2 ok" not in log
    work = w.tmp / "work"
    assert (work / "corner-shop" / "ran.txt").read_text() == "first\n"
    assert not (work / "ran.txt").exists()
    assert "setup end" in log


def _stamp_file(w):
    return w.home / ".claude" / "superheroes" / "projects" / w.key / "cloud-setup-stamp"


def test_a_failed_setup_command_leaves_no_stamp(tmp_path):
    w = _inside(tmp_path)
    _store_commands(w, ["exit 3"])
    result = _compose(w)
    # axis: a stale stamp is cleared and the failed setup does not publish its own
    stamp = _stamp_file(w)
    stamp.parent.mkdir(parents=True)
    stamp.write_text("stale\n")
    proc, _ = _run_script(w, result["text"], git_clone=True)
    # axis: a listed command that failed or was skipped ends non-zero, so an unfinished setup is not cached
    assert proc.returncode == 1, proc.stderr
    assert "setup command 1 FAILED" in _setup_log(w) and "setup end" in _setup_log(w)
    assert not stamp.exists()


def test_a_missing_clone_leaves_no_stamp(tmp_path):
    w = _inside(tmp_path)
    _store_commands(w, ["true"])
    proc, _ = _run_script(w, _compose(w)["text"])
    # axis: a listed command that failed or was skipped ends non-zero, so an unfinished setup is not cached
    assert proc.returncode == 1, proc.stderr
    assert "setup command 1 skipped" in _setup_log(w)
    assert not _stamp_file(w).exists()


def test_setup_commands_that_all_pass_publish_the_stamp(tmp_path):
    w = _inside(tmp_path)
    _store_commands(w, ["true", "true"])
    result = _compose(w)
    proc, _ = _run_script(w, result["text"], git_clone=True)
    assert proc.returncode == 0, proc.stderr
    assert _stamp_file(w).read_text() == result["calibration"]["stamp"] + "\n"


def test_setup_commands_that_pass_are_each_logged_ok_in_order(tmp_path):
    w = _inside(tmp_path)
    _store_commands(w, ['echo one >> "$PWD/ran.txt"', 'echo two >> "$PWD/ran.txt"'])
    proc, _ = _run_script(w, _compose(w)["text"], git_clone=True)
    assert proc.returncode == 0, proc.stderr
    log = _setup_log(w)
    assert log.index("setup command 1 ok") < log.index("setup command 2 ok")
    assert "setup command 1 FAILED" not in log and "setup command 2 skipped" not in log
    assert (w.tmp / "work" / "corner-shop" / "ran.txt").read_text() == "one\ntwo\n"


def test_setup_commands_run_in_the_working_directory_when_it_is_the_clone(tmp_path):
    w = _inside(tmp_path)
    _store_commands(w, ['echo here >> "$PWD/ran.txt"'])
    proc, _ = _run_script(w, _compose(w)["text"], git_clone="here")
    assert proc.returncode == 0, proc.stderr
    assert "setup command 1 ok" in _setup_log(w)
    assert (w.tmp / "work" / "ran.txt").read_text() == "here\n"


def test_setup_commands_with_no_clone_are_each_skipped_and_the_script_exits_non_zero(tmp_path):
    w = _inside(tmp_path)
    _store_commands(w, ['echo one >> "$PWD/ran.txt"', 'echo two >> "$PWD/ran.txt"'])
    proc, _ = _run_script(w, _compose(w)["text"])
    # axis: a listed command that failed or was skipped ends non-zero, so an unfinished setup is not cached
    assert proc.returncode == 1, proc.stderr
    work = w.tmp / "work"
    log = _setup_log(w)
    for n in (1, 2):
        assert "setup command %d skipped: no clone in %s or %s/corner-shop" % (n, work, work) in log
    assert not (work / "ran.txt").exists() and "setup end" in log


def test_a_hostile_setup_command_fails_only_itself(tmp_path):
    w = _inside(tmp_path)
    _store_commands(w, ['echo "unbalanced', 'echo second >> "$PWD/ran.txt"'])
    text = _compose(w)["text"]
    assert subprocess.run(["bash", "-n"], input=text, text=True,
                          capture_output=True).returncode == 0
    proc, _ = _run_script(w, text, git_clone=True)
    # axis: a listed command that failed or was skipped ends non-zero, so an unfinished setup is not cached
    assert proc.returncode == 1, proc.stderr
    log = _setup_log(w)
    assert "setup command 1 FAILED" in log
    assert "setup command 2 skipped: setup command 1 FAILED" in log
    assert not (w.tmp / "work" / "corner-shop" / "ran.txt").exists() and "setup end" in log


def test_without_a_clone_name_the_clone_is_looked_for_only_in_the_working_directory(
        tmp_path, monkeypatch):
    monkeypatch.setattr(CS, "_clone_dir", lambda cwd: None)
    w = _inside(tmp_path)
    _store_commands(w, ["true"])
    text = _compose(w)["text"]
    assert "CLONE" not in text
    assert subprocess.run(["bash", "-n"], input=text, text=True,
                          capture_output=True).returncode == 0
    proc, _ = _run_script(w, text)
    # axis: a listed command that failed or was skipped ends non-zero, so an unfinished setup is not cached
    assert proc.returncode == 1, proc.stderr
    assert "setup command 1 skipped: no clone in %s" % (w.tmp / "work") in _setup_log(w).splitlines()


def _golden(w, mode):
    """The no-commands golden for `mode`, with the world pinned to the time it was rendered at."""
    path = os.path.join(_HERE, "fixtures", "cloud_setup_text", "no_commands_%s.sh" % mode)
    with open(path, encoding="utf-8") as fh:
        expected = fh.read().replace("@VERSION@", VERSION)
    if mode == "outside":
        # the registry file carries the time it was written, so the world's is set to the one the
        # fixture was rendered with
        pinned = re.search(r"<<'SUPERHEROES_END_6'\n(.*?)\nSUPERHEROES_END_6\n", expected, re.S)
        _put(w, "registry.json", pinned.group(1).encode("utf-8") + b"\n")
    return expected


_GOLDEN_KW = dict(source_dir="/opt/fixture/src", plugin_dir="/opt/fixture/plugin")


@pytest.mark.parametrize("mode", ["outside", "inside"])
def test_unset_setup_commands_leave_the_text_as_it_was(tmp_path, mode):
    # axis: an unset list changes nothing: the text is byte for byte today's
    w = (_outside if mode == "outside" else _inside)(tmp_path)
    expected = _golden(w, mode)
    result = _compose(w, **_GOLDEN_KW)
    assert result["action"] == "written"
    assert result["text"] == expected
    assert "setupCommands" not in result["calibration"]


def test_an_empty_list_outside_the_repo_changes_only_the_core_and_its_stamp(tmp_path):
    # axis: the placed calibration already removes the stamp, so an empty list adds no line there
    w = _outside(tmp_path)
    expected = _golden(w, "outside")
    _store_commands(w, [])
    # the stored core is now a real one, so its heredoc and the stamp are the core's; every other
    # line is the fixture's
    stored = CS.calibration_files(w.cwd, w.root)["config/core.md"].decode("utf-8")
    old = "# Core\nline two\nSUPERHEROES_END_1\n"
    assert expected.count(old) == 1
    expected = expected.replace(old, stored + "SUPERHEROES_END_1\n")
    expected = re.sub(r"'2026-10-10:[0-9a-f]+'", "'2026-10-10:fixed'", expected)
    result = _compose(w, stamp_fn=lambda files: "2026-10-10:fixed", **_GOLDEN_KW)
    assert result["action"] == "written"
    assert result["text"] == expected
    assert "setupCommands" not in result["calibration"]


def test_an_empty_list_in_the_repo_adds_only_the_stamp_removal(tmp_path):
    # axis: an empty list adds the stamp removal and nothing else to the golden text
    w = _inside(tmp_path)
    expected = _golden(w, "inside")
    _store_commands(w, [])
    result = _compose(w, **_GOLDEN_KW)
    assert result["action"] == "written"
    assert "setupCommands" not in result["calibration"]
    assert result["calibration"]["stamp"] is None
    lines = result["text"].splitlines()
    diff = [ln for ln in difflib.ndiff(expected.splitlines(), lines) if ln[0] in "+-"]
    assert diff and all(ln[0] == "+" for ln in diff), diff
    assert 'rm -f "$DEST/%s"' % CS.STAMP_FILE in [ln[2:] for ln in diff]
    assert lines.index('rm -f "$DEST/%s"' % CS.STAMP_FILE) < lines.index(CS.TOOL_STEPS_MARKER)


def test_clearing_the_list_retires_the_stamp_a_longer_list_left(tmp_path):
    # axis: a list cleared to [] removes the stamp an earlier non-empty list placed
    w = _inside(tmp_path)
    store = mode_registry.project_store_dir(w.cwd, str(w.home / ".claude" / "superheroes"))
    stamp_path = os.path.join(store, CS.STAMP_FILE)
    _store_commands(w, [])
    assert project_config.set_item(w.cwd, SLUG, ["true"], root=w.root)["action"] == "written"
    proc, _ = _run_script(w, _compose(w)["text"], git_clone="here")
    assert proc.returncode == 0, proc.stderr
    assert os.path.isfile(stamp_path)
    assert project_config.set_item(w.cwd, SLUG, [], root=w.root)["action"] == "written"
    # a second run, from a working directory of its own, against the same home
    w.tmp = tmp_path / "second"
    w.tmp.mkdir()
    proc, _ = _run_script(w, _compose(w)["text"], git_clone="here")
    assert proc.returncode == 0, proc.stderr
    assert not os.path.exists(stamp_path)
    # the check's expectation for that state: nothing placed, so no stamp file
    local = cloud_check._placed_stamp(w.cwd, w.root)
    assert local == "none"
    assert cloud_check._stamp_file(w.cwd, str(w.home / ".claude" / "superheroes")) is None


def test_the_stamp_moves_with_the_command_list_in_both_storage_modes(tmp_path):
    states = {"unset": _UNSET, "empty": [], "a": ["a"], "b": ["b"], "ab": ["a", "b"],
              "ba": ["b", "a"]}
    for mode, w in _both_modes(tmp_path):
        stamps = {}
        for name, value in states.items():
            _store_commands(w, value)
            result = _compose(w, stamp_fn=None)
            stamp = stamps[name] = result["calibration"]["stamp"]
            if stamp is None:
                assert CS.stamped_files(w.cwd, w.root) == {}
            else:
                assert cloud_setup.calibration_stamp(CS.stamped_files(w.cwd, w.root)) == stamp
            if name == "empty":
                # an empty list adds nothing to the stamped files (the placed core, which holds
                # the empty list, is the same bytes either way)
                assert CS.SETUP_COMMANDS_STAMP_KEY not in CS.stamped_files(w.cwd, w.root)
        # axis: any change to the list changes the stamp, its order included
        assert stamps["a"] != stamps["unset"] and stamps["a"] != stamps["b"]
        assert stamps["ab"] != stamps["ba"] and stamps["a"] != stamps["ab"]
        if mode == "inside":
            # with no calibration file placed, the list alone is what the stamp covers
            assert stamps["unset"] is None and stamps["empty"] is None
            assert STAMP_SHAPE.fullmatch(stamps["a"])


def test_an_in_repository_project_with_commands_and_no_files_still_writes_its_stamp(tmp_path):
    w = _inside(tmp_path)
    assert CS.calibration_files(w.cwd, w.root) == {}
    _store_commands(w, ["true"])
    result = _compose(w, stamp_fn=None)
    assert result["calibration"]["files"] == [] and result["calibration"]["setupCommands"] == 1
    assert STAMP_SHAPE.fullmatch(result["calibration"]["stamp"])
    proc, _ = _run_script(w, result["text"], git_clone=True)
    assert proc.returncode == 0, proc.stderr
    dest = w.home / ".claude" / "superheroes" / "projects" / w.key
    # axis: the stamp file is written even when no calibration file is placed
    assert (dest / "cloud-setup-stamp").read_text() == result["calibration"]["stamp"] + "\n"
    log = _setup_log(w)
    assert "calibration: 0 of 0 files written" in log and "calibration FAILED" not in log
    assert "setup command 1 ok" in log


@pytest.mark.parametrize("stored", [None, "npm ci", {"a": "b"}, ["a\nb"], ["a\rb"], [""], ["  "],
                                    [1], ["ok", None], ["token: Bearer " + "t" * 20]],
                         ids=["null", "string", "object", "newline", "carriage-return", "empty",
                              "blank", "non-string", "null-entry", "secret-shaped"])
def test_a_present_setting_that_is_not_a_valid_list_is_refused(tmp_path, stored):
    for _, w in _both_modes(tmp_path):
        _store_commands(w, stored)
        # axis: a stored value that fails the validator is refused, never read as an empty list
        _refusal(_compose(w), "setup-commands-malformed")
        with pytest.raises(CS._Refused):
            CS.stamped_files(w.cwd, w.root)


def test_a_core_that_cannot_be_read_refuses_with_its_own_reason(tmp_path, monkeypatch):
    w = _inside(tmp_path)
    _store_commands(w, ["npm ci"])
    unreadable = os.path.realpath(core_md.core_path(w.cwd, w.root, persist_backfill=False))
    real_open = open

    def refusing_open(file, *args, **kwargs):
        if isinstance(file, (str, bytes, os.PathLike)) and os.path.realpath(file) == unreadable:
            raise PermissionError("unreadable")
        return real_open(file, *args, **kwargs)

    # core_md.read stays the real one, so its own error handling is what the refusal rests on
    monkeypatch.setattr("builtins.open", refusing_open)
    _refusal(_compose(w), "setup-commands-unreadable")


def test_a_corrupt_core_means_no_commands_and_the_text_is_written(tmp_path):
    for _, w in _both_modes(tmp_path):
        path = core_md.core_path(w.cwd, w.root, persist_backfill=False)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(b"# Core\n```json superheroes-core\n{not json\n```\n")
        result = _compose(w)
        assert result["action"] == "written"
        assert "setup commands" not in result["text"]


def test_a_core_that_names_setup_commands_but_cannot_be_parsed_is_refused(tmp_path):
    for _, w in _both_modes(tmp_path):
        path = core_md.core_path(w.cwd, w.root, persist_backfill=False)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(b'# Core\n```json superheroes-core\n'
                     b'{"projectConfiguration": {"cloudSetupCommands": ["npm ci"],}}\n```\n')
        _refusal(_compose(w), "setup-commands-unreadable")


ENV_REF_COMMAND = 'echo "OPENAI_API_KEY=\\"$BUILD_OPENAI_KEY\\"" > .env'


def test_env_reference_command_is_set_and_composes_in_both_modes(tmp_path):
    for name, w in _both_modes(tmp_path):
        _store_commands(w, [])
        done = project_config.set_item(w.cwd, SLUG, [ENV_REF_COMMAND], root=w.root)
        assert done["action"] == "written", (name, done)
        result = _compose(w)
        assert result["action"] == "written", (name, result)


def test_literal_credential_in_a_listed_command_is_refused_in_both_modes(tmp_path):
    command = 'echo "OPENAI_API_KEY=\\"%s\\"" > .env' % ("v" * 20)
    for name, w in _both_modes(tmp_path):
        _store_commands(w, [command])
        result = _compose(w)
        assert result["action"] == "refused" and "text" not in result, (name, result)
        assert result["reason"] in ("secret-shaped-content", "setup-commands-malformed"), result
        assert "v" * 20 not in json.dumps(result)


def test_literal_credential_elsewhere_in_the_placed_core_is_still_refused(tmp_path):
    planted = SHAPE_CASES[0][2]()
    w = _outside(tmp_path)
    _store_commands(w, [ENV_REF_COMMAND])
    _edit_core_block(w, lambda obj: obj.__setitem__("note", planted))
    _refusal(_compose(w), "secret-shaped-content")


# --- URL forms without a literal secret are not refused ---------------------------------------

@pytest.mark.parametrize("text", [
    "pip install --index-url https://$TOKEN@packages.example.invalid/simple demo",
    "pip install --index-url https://${TOKEN}@packages.example.invalid/simple demo",
    "curl https://user:$TOKEN@host.example.invalid/",
    "curl https://$U:$P@host.example.invalid/",
    "git clone ssh://git@host.example.invalid/x.git",
    "git clone ssh://git@github.com/x/y.git",
    "pip install git+ssh://git@host.example.invalid/x.git",
    "git clone git@github.com:x/y.git",
    "pip install --index-url https://packages.example.invalid/simple demo",
])
def test_scan_allows_url_forms_without_a_literal_secret(text):
    assert CS._scan(text) is None


# --- a serialized verification command keeps its shell word boundaries (#2009) ----------------

def _compose_with_verify_command(tmp_path, command):
    w = _outside(tmp_path)
    _edit_core_block(w, lambda obj: obj.update(verifyCommand=command))
    return _compose(w)


def test_serialized_verify_command_with_an_environment_reference_composes(tmp_path):
    # axis: the JSON quotes around a command are not shell quotes; `npm test` is a separate word
    result = _compose_with_verify_command(
        tmp_path, "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY npm test")
    assert result["action"] == "written", result


def test_serialized_verify_command_ending_in_a_quoted_reference_composes(tmp_path):
    # axis: the JSON delimiters beside a value ending in a quote survive the empty-quote normalization
    result = _compose_with_verify_command(tmp_path, 'make test DATABASE_PASSWORD="$PW"')
    assert result["action"] == "written", result


@pytest.mark.parametrize("command", [
    'printf AWS_SECRET_ACCESS_KEY=%s "$KEY" > .env && npm test',
    'printf "AWS_SECRET_ACCESS_KEY=%s\\n" "$KEY" > .env && npm test',
])
def test_serialized_verify_command_keeps_the_printf_and_reference_exemptions(tmp_path, command):
    result = _compose_with_verify_command(tmp_path, command)
    assert result["action"] == "written", result


# --- the plugin pin hook: what the setup text and its stamp do with it ------------------------

PIN = {"source": SOURCE, "commit": COMMIT, "subdir": SUBDIR, "version": VERSION}
ABSENT = {"state": "absent", "reason": None, "pin": None}
PIN_KEYS = (CS.SETUP_STEPS_STAMP_KEY, CS.SETUP_INVENTORY_STAMP_KEY)


def _with_pin(w, pin=PIN):
    result = cloud_plugin_pin.sync(w.cwd, pin)
    assert result["action"] == "written", result
    assert cloud_plugin_pin.in_tree(w.cwd)["state"] == "valid"


def _break_pin(w):
    with open(os.path.join(w.cwd, ".claude", "superheroes-plugin-pin"), "w") as fh:
        fh.write("not a pin\n")
    assert cloud_plugin_pin.in_tree(w.cwd)["state"] == "broken"


def _plugin_copy(tmp_path, monkeypatch):
    """A plugin directory of the parts a cloud session loads at its start, standing in for the real one."""
    root = tmp_path / "plugin-copy"
    for sub in ("skills/alpha", "agents", "hooks"):
        (root / sub).mkdir(parents=True)
    (root / "version.txt").write_text(VERSION + "\n")
    (root / "skills" / "alpha" / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: first\n---\nbody one\n")
    (root / "agents" / "helper.md").write_text("agent one\n")
    (root / "hooks" / "hooks.json").write_text('{"hooks": {}}\n')
    monkeypatch.setattr(CS, "_plugin_root", lambda: str(root))
    return root


def _real_stamp(w):
    return cloud_setup.calibration_stamp(CS.stamped_files(w.cwd, w.root))


def test_a_project_without_the_hook_composes_and_stamps_as_it_did_without_the_pin(
        tmp_path, monkeypatch):
    for name, make in (("outside", _outside), ("inside", _inside)):
        (tmp_path / name).mkdir()
        w = make(tmp_path / name)
        _store_commands(w, ["npm ci"])
        assert cloud_plugin_pin.in_tree(w.cwd)["state"] == "absent"
        got = _compose(w)
        stamped = CS.stamped_files(w.cwd, w.root)
        # axis: an absent hook leaves every output as it was before the pin was read
        monkeypatch.setattr(CS, "_pin_state", lambda cwd: ABSENT)
        expected = _compose(w)
        assert got == expected and got["pluginPin"] is False
        assert CS.stamped_files(w.cwd, w.root) == stamped
        monkeypatch.undo()
        assert not set(PIN_KEYS) & set(stamped)
        assert "follows the committed pin" not in got["header"]
        assert got["text"].splitlines()[1] == "# " + got["header"]
        assert got["calibration"]["stamp"] == _stamp(stamped)


def test_a_project_without_the_hook_has_no_pin_entries_in_its_stamp(tmp_path):
    w = _outside(tmp_path)
    # axis: the two pin entries are in no stamp of a project whose working tree has no hook
    assert not set(PIN_KEYS) & set(CS.stamped_files(w.cwd, w.root))
    assert set(CS.stamped_files(w.cwd, w.root)) == set(CS.calibration_files(w.cwd, w.root))


def test_a_valid_hook_adds_exactly_the_two_entries_and_names_the_pin(tmp_path, monkeypatch):
    _plugin_copy(tmp_path, monkeypatch)
    w = _outside(tmp_path)
    before = CS.stamped_files(w.cwd, w.root)
    _with_pin(w)
    after = CS.stamped_files(w.cwd, w.root)
    assert set(after) - set(before) == set(PIN_KEYS) and set(before) <= set(after)
    result = _compose(w)
    assert result["action"] == "written" and result["pluginPin"] is True
    assert result["header"] == ("Corner Shop · plugin %s · follows the committed pin"
                                " · calibration from 10 Oct" % VERSION)
    assert result["calibration"]["stamp"] == _stamp(after)
    steps = after[CS.SETUP_STEPS_STAMP_KEY].decode("utf-8")
    assert 'git fetch -q --depth 1 "SOURCE" PINNED \\' in steps
    assert 'ln -sfn "$SRC/SUBDIR" "$LINK"' in steps
    for value in (SOURCE, COMMIT, SUBDIR):
        assert value not in steps


def test_a_valid_hook_writes_a_stamp_even_with_no_files_and_no_commands(tmp_path, monkeypatch):
    _plugin_copy(tmp_path, monkeypatch)
    w = _inside(tmp_path)
    assert CS.calibration_files(w.cwd, w.root) == {}
    _with_pin(w)
    result = _compose(w, stamp_fn=None)
    assert result["action"] == "written" and result["pluginPin"] is True
    assert result["calibration"]["files"] == [] and "setupCommands" not in result["calibration"]
    stamp = result["calibration"]["stamp"]
    assert STAMP_SHAPE.fullmatch(stamp) and stamp == _real_stamp(w)
    assert "printf '%%s\\n' '%s' > \"$DEST/%s\"" % (stamp, "cloud-setup-stamp") in result["text"]
    # without the hook the same project writes no stamp
    cloud_plugin_pin.sync(w.cwd, None)
    plain = _compose(w, stamp_fn=None)
    assert plain["calibration"]["stamp"] is None and "cloud-setup-stamp" not in plain["text"].replace(
        'rm -f "$DEST/cloud-setup-stamp"', "")


def test_a_broken_hook_is_refused_by_the_text_and_the_stamp_readers(tmp_path, monkeypatch):
    _plugin_copy(tmp_path, monkeypatch)
    for name, make in (("outside", _outside), ("inside", _inside)):
        (tmp_path / name).mkdir()
        w = make(tmp_path / name)
        _with_pin(w)
        _break_pin(w)
        # axis: a broken state is refused, never composed as absent or valid
        _refusal(_compose(w), "plugin-pin-broken")
        with pytest.raises(CS._Refused) as raised:
            CS.stamped_files(w.cwd, w.root)
        assert raised.value.reason == "plugin-pin-broken"


def test_the_composed_text_with_the_hook_carries_no_secret_shape_and_no_pass(tmp_path, monkeypatch):
    _plugin_copy(tmp_path, monkeypatch)
    w = _outside(tmp_path)
    w.env[cloud_pass.PASS_ENV] = base64.b64encode(b"pass-value-" + b"x" * 40).decode("ascii")
    _with_pin(w)
    result = _compose(w)
    assert result["action"] == "written"
    assert CS._scan(result["text"]) is None
    assert cloud_pass.PASS_ENV not in result["text"] and w.env[cloud_pass.PASS_ENV] not in result["text"]


def test_the_stamp_is_unchanged_when_only_the_plugin_commit_differs(tmp_path, monkeypatch):
    _plugin_copy(tmp_path, monkeypatch)
    w = _outside(tmp_path)
    _with_pin(w)
    one = _compose(w, stamp_fn=None)
    other = _compose(w, stamp_fn=None, plugin_commit="f" * 40, plugin_source=SOURCE + ".other",
                     plugin_subdir="plugins/other")
    assert one["pluginCommit"] != other["pluginCommit"]
    assert one["calibration"]["stamp"] == other["calibration"]["stamp"] == _real_stamp(w)
    # a pin commit moves the pin file, which the stamp does not cover
    _with_pin(w, dict(PIN, commit="e" * 40))
    assert _real_stamp(w) == one["calibration"]["stamp"]


def test_the_stamp_changes_when_a_tool_step_of_the_setup_text_changes(tmp_path, monkeypatch):
    _plugin_copy(tmp_path, monkeypatch)
    w = _outside(tmp_path)
    _with_pin(w)
    before = _real_stamp(w)
    monkeypatch.setattr(CS, "REVIEWER_CLI_PACKAGE", "@openai/codex@9.9.9")
    # axis: the setup-steps entry covers the install and fetch steps a pin commit cannot move
    assert _real_stamp(w) != before
    assert _compose(w, stamp_fn=None)["calibration"]["stamp"] == _real_stamp(w)


def test_the_stamp_changes_when_a_skill_frontmatter_changes_but_not_its_body(tmp_path, monkeypatch):
    root = _plugin_copy(tmp_path, monkeypatch)
    w = _outside(tmp_path)
    _with_pin(w)
    before = _real_stamp(w)
    skill = root / "skills" / "alpha" / "SKILL.md"
    skill.write_text("---\nname: alpha\ndescription: first\n---\nbody two, quite different\n")
    assert _real_stamp(w) == before
    skill.write_text("---\nname: alpha\ndescription: second\n---\nbody one\n")
    assert _real_stamp(w) != before


def test_the_stamp_changes_when_an_agent_file_changes(tmp_path, monkeypatch):
    root = _plugin_copy(tmp_path, monkeypatch)
    w = _outside(tmp_path)
    _with_pin(w)
    before = _real_stamp(w)
    (root / "agents" / "helper.md").write_text("agent two\n")
    # axis: the inventory entry covers each agent file, loaded at a session's start
    assert _real_stamp(w) != before


def test_the_stamp_changes_when_the_plugin_hooks_file_changes(tmp_path, monkeypatch):
    root = _plugin_copy(tmp_path, monkeypatch)
    w = _outside(tmp_path)
    _with_pin(w)
    before = _real_stamp(w)
    (root / "hooks" / "hooks.json").write_text('{"hooks": {"SessionStart": []}}\n')
    assert _real_stamp(w) != before
    (root / "hooks" / "hooks.json").unlink()
    assert _real_stamp(w) not in (before, None)


def test_the_stamp_changes_when_a_registered_hook_module_or_its_import_changes(tmp_path, monkeypatch):
    root = _plugin_copy(tmp_path, monkeypatch)
    w = _outside(tmp_path)
    _with_pin(w)
    (root / "hooks" / "mod").mkdir()
    (root / "hooks" / "hooks.json").write_text('{"modules": ["./mod/register.ts"], "hooks": {}}\n')
    (root / "hooks" / "mod" / "register.ts").write_text("import { A } from './resume'\n")
    (root / "hooks" / "mod" / "resume.ts").write_text("export const A = 1\n")
    before = _real_stamp(w)
    (root / "hooks" / "mod" / "resume.ts").write_text("export const A = 2\n")
    # axis: a loaded module is not reloaded by the pin swap, so its change must move the stamp
    after_import = _real_stamp(w)
    assert after_import != before
    (root / "hooks" / "mod" / "register.ts").write_text("import { A } from './resume'\n// edit\n")
    assert _real_stamp(w) != after_import


def test_an_unreadable_inventory_file_is_refused_by_the_text_and_the_stamp_readers(
        tmp_path, monkeypatch):
    root = _plugin_copy(tmp_path, monkeypatch)
    w = _outside(tmp_path)
    _with_pin(w)
    (root / "agents" / "unreadable.md").mkdir()
    _refusal(_compose(w), "plugin-inventory-unreadable")
    with pytest.raises(CS._Refused) as raised:
        CS.stamped_files(w.cwd, w.root)
    assert raised.value.reason == "plugin-inventory-unreadable"
