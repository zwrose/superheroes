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


def test_runs_release_bump_tripwire():
    text = _text()
    assert ".github/scripts/check_release_bump.py" in text


def test_tripwire_fetches_tags_in_same_step():
    text = _text()
    assert "git fetch --tags" in text
    # fetch and check must share the tripwire step's run block
    tripwire = text.split("Release-bump tripwire")[1]
    assert "git fetch --tags" in tripwire
    assert "check_release_bump.py" in tripwire


def test_tripwire_uses_app_token_for_gh():
    text = _text()
    assert "GH_TOKEN: ${{ steps.app-token.outputs.token }}" in text


def test_tripwire_runs_after_release_please():
    import yaml
    with open(_WF) as fh:
        data = yaml.safe_load(fh)
    steps = data["jobs"]["release-please"]["steps"]
    rp_idx = next(
        i for i, s in enumerate(steps)
        if str(s.get("uses", "")).startswith("googleapis/release-please-action@")
    )
    tw_idx = next(
        i for i, s in enumerate(steps)
        if "Release-bump tripwire" in (s.get("name") or "")
    )
    assert tw_idx > rp_idx


def test_tripwire_does_not_continue_on_error():
    import yaml
    with open(_WF) as fh:
        data = yaml.safe_load(fh)
    steps = data["jobs"]["release-please"]["steps"]
    tw = next(s for s in steps if "Release-bump tripwire" in (s.get("name") or ""))
    assert "continue-on-error" not in tw


_LEDGER = os.path.join(_ROOT, ".github", "release-exclusions.txt")
_LEDGER_LINE = re.compile(
    r"^[0-9a-f]{40}  [0-9a-f]{40}  \d{4}-\d{2}-\d{2}  .+$"
)


def test_release_exclusions_ledger_format():
    assert os.path.isfile(_LEDGER), f"missing ledger: {_LEDGER}"
    with open(_LEDGER) as fh:
        for lineno, line in enumerate(fh, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            assert _LEDGER_LINE.match(line.rstrip("\n")), (
                f"malformed ledger line {lineno}: {line!r}"
            )
