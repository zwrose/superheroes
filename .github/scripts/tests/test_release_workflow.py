import os, re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_WF = os.path.join(_ROOT, ".github", "workflows", "release-please.yml")


def _text():
    with open(_WF) as fh:
        return fh.read()


def test_workflow_exists_and_parses():
    import yaml  # pyyaml is a CI dependency
    with open(_WF) as fh:
        data = yaml.safe_load(fh)
    assert "jobs" in data


def test_triggers_on_push_to_main_only():
    import yaml
    with open(_WF) as fh:
        data = yaml.safe_load(fh)
    # PyYAML parses the bare `on:` key as boolean True.
    on = data.get(True, data.get("on"))
    assert "push" in on
    assert on["push"]["branches"] == ["main"]
    assert "pull_request_target" not in on


def test_uses_app_token_not_default_github_token():
    text = _text()
    assert "RELEASE_APP_ID" in text and "RELEASE_APP_PRIVATE_KEY" in text
    # the privileged steps must NOT fall back to the default token
    assert "secrets.GITHUB_TOKEN" not in text and "github.token" not in text


def test_runs_release_please_action():
    assert "googleapis/release-please-action@" in _text()


def test_runs_defensive_conventional_commit_check():
    text = _text()
    assert ".github/scripts/check_conventional_commit.py" in text
    assert "git log -1 --pretty=%s" in text  # runs the check on the latest main commit subject


def test_all_third_party_actions_pinned_to_sha():
    for line in _text().splitlines():
        m = re.search(r"uses:\s*(\S+)", line)
        if not m:
            continue
        ref = m.group(1).split("@", 1)[1] if "@" in m.group(1) else ""
        assert re.fullmatch(r"[0-9a-f]{40}", ref), f"not SHA-pinned: {m.group(1)}"
