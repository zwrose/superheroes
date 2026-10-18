import os
import pwd
import subprocess

_REAL_HOME = pwd.getpwuid(os.getuid()).pw_dir


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd)] + list(args), capture_output=True, text=True,
                          check=True).stdout.strip()


def test_session_pins_git_config_outside_real_home():
    config = os.environ["GIT_CONFIG_GLOBAL"]
    assert os.path.isfile(config)
    real_home = os.path.realpath(_REAL_HOME)
    assert os.path.commonpath([os.path.realpath(config), real_home]) != real_home
    assert os.environ.get("GIT_CONFIG_NOSYSTEM") == "1"


def test_commit_without_inline_options_uses_session_config(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "x")
    assert _git(tmp_path, "config", "--get", "commit.gpgsign") == "false"


def test_repository_local_setting_beats_session_config(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "local-wins")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "x")
    assert _git(tmp_path, "log", "-1", "--format=%an") == "local-wins"
