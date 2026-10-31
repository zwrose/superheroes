import importlib.util
import os
import re
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOD = os.path.join(_HERE, "..", "launch_doctrine.py")
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_DOCTRINE = os.path.join(_PLUGIN_ROOT, "rubric", "launch-doctrine.md")
# Preflight charter block lives in dispatch-preflight.md (not SKILL.md).
_CHARTER = os.path.join(
    _PLUGIN_ROOT, "skills", "showrunner", "reference", "dispatch-preflight.md"
)


def _load():
    spec = importlib.util.spec_from_file_location("launch_doctrine", _MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LD = _load()

_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}


def _opening_ruling_count_word(text):
    match = re.search(r"\bthe ([a-z]+) rulings\b", text, re.IGNORECASE)
    if not match:
        raise AssertionError(
            "launch-doctrine.md opening must contain 'the <word> rulings' — "
            "count word not found"
        )
    return match.group(1).lower()


def _read_doctrine():
    with open(_DOCTRINE, encoding="utf-8") as fh:
        return fh.read()


def _read_charter():
    with open(_CHARTER, encoding="utf-8") as fh:
        return fh.read()


def _mutate_once(text, old, new):
    assert text.count(old) == 1, f"expected exactly one occurrence of {old!r}"
    return text.replace(old, new)


def test_load_happy_path():
    result = LD.load()
    assert result["ok"] is True
    assert result["reason"] is None
    assert [r["id"] for r in result["rulings"]] == list(LD.RULING_IDS)
    assert [(c["id"], c["class"]) for c in result["checks"]] == list(LD.PREFLIGHT_CHECKS)
    # One line per pinned ruling, so N rulings joined by N-1 newlines. Derived from
    # RULING_IDS rather than hand-counted: a bare literal here silently rots the moment
    # a ruling is added, and the block is the byte-pinned payload a launched builder gets.
    assert result["rulingsBlock"].count("\n") == len(LD.RULING_IDS) - 1
    for rid in LD.RULING_IDS:
        assert any(rid in line for line in result["rulingsBlock"].split("\n"))
    assert len(result["digest"]) == 64
    assert all(c in "0123456789abcdef" for c in result["digest"])


_CLOUD_BEGIN = "<!-- launch-doctrine:cloud-launch:begin -->"
_CLOUD_END = "<!-- launch-doctrine:cloud-launch:end -->"


def test_shipped_doctrine_carries_the_cloud_launch_line():
    # axis: the parser returns the doctrine block's own text, read here by plain string operations
    # rather than through the parser — see bite-proof record c8c_wo_c.md
    text = _read_doctrine()
    assert text.count(_CLOUD_BEGIN) == 1
    assert text.count(_CLOUD_END) == 1
    block = text.split(_CLOUD_BEGIN, 1)[1].split(_CLOUD_END, 1)[0].strip()
    result = LD.load()
    assert result["ok"] is True
    assert result["cloudLaunchLine"] == block
    assert block.count("\n") == 0
    assert "never a force-push" in block
    assert "never `main`" in block


def test_cloud_launch_block_is_introduced_as_parsed():
    # axis: the label above the parsed block must not call it unparsed — see bite-proof record c8c_wo_c.md
    before = _read_doctrine().split(_CLOUD_BEGIN, 1)[0]
    label = before.rstrip("\n").split("\n\n")[-1]
    assert label.startswith("**Cloud launch permission"), label
    assert "not parsed" not in label, label


def _cloud_line():
    return LD.load()["cloudLaunchLine"]


def _assert_cloud_refusal(text, reason):
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == reason
    assert result["cloudLaunchLine"] is None
    assert result["rulingsBlock"] is None
    assert result["digest"] is None


def test_doctrine_missing_cloud_launch_block():
    _assert_cloud_refusal(
        _read_doctrine().replace(_CLOUD_BEGIN, ""), "doctrine-missing-block:cloud-launch"
    )


def test_doctrine_duplicate_cloud_launch_block():
    text = _mutate_once(_read_doctrine(), _CLOUD_BEGIN, _CLOUD_BEGIN + "\n" + _CLOUD_BEGIN)
    _assert_cloud_refusal(text, "doctrine-duplicate-block:cloud-launch")


def test_doctrine_empty_cloud_launch_block_is_malformed():
    text = _mutate_once(_read_doctrine(), _cloud_line() + "\n", "")
    result = LD.parse(text)
    assert result["ok"] is False
    assert re.fullmatch(r"doctrine-malformed-line:\d+", result["reason"])
    assert result["cloudLaunchLine"] is None


def test_doctrine_two_line_cloud_launch_block_is_malformed():
    text = _mutate_once(
        _read_doctrine(), _cloud_line(), _cloud_line() + "\nAnd one more line."
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert re.fullmatch(r"doctrine-malformed-line:\d+", result["reason"])
    assert result["cloudLaunchLine"] is None


@pytest.mark.parametrize("phrase", LD.CLOUD_LAUNCH_INVARIANTS)
def test_doctrine_cloud_launch_missing_invariant_refuses(phrase):
    line = _cloud_line()
    assert phrase in line
    text = _mutate_once(_read_doctrine(), line, line.replace(phrase, "never anything"))
    _assert_cloud_refusal(text, f"doctrine-cloud-launch-invariant-missing:{phrase}")


_DETECTIVE_BEGIN = "<!-- launch-doctrine:cloud-detective:begin -->"
_DETECTIVE_END = "<!-- launch-doctrine:cloud-detective:end -->"


def test_shipped_doctrine_carries_the_detective_cloud_line():
    # axis: the parser returns the detective block's own text, read here by plain string operations
    text = _read_doctrine()
    assert text.count(_DETECTIVE_BEGIN) == 1
    assert text.count(_DETECTIVE_END) == 1
    block = text.split(_DETECTIVE_BEGIN, 1)[1].split(_DETECTIVE_END, 1)[0].strip()
    result = LD.load()
    assert result["ok"] is True
    assert result["detectiveCloudLine"] == block
    assert block.count("\n") == 0
    for phrase in LD.DETECTIVE_CLOUD_INVARIANTS:
        assert phrase in block
    assert result["detectiveCloudLine"] != result["cloudLaunchLine"]


def _detective_line():
    return LD.load()["detectiveCloudLine"]


def _assert_detective_refusal(text, reason):
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == reason
    assert result["detectiveCloudLine"] is None
    assert result["cloudLaunchLine"] is None
    assert result["rulingsBlock"] is None
    assert result["digest"] is None


def test_doctrine_missing_detective_cloud_block():
    _assert_detective_refusal(
        _read_doctrine().replace(_DETECTIVE_BEGIN, ""), "doctrine-missing-block:cloud-detective"
    )


def test_doctrine_empty_detective_cloud_block_is_malformed():
    text = _mutate_once(_read_doctrine(), _detective_line() + "\n", "")
    result = LD.parse(text)
    assert result["ok"] is False
    assert re.fullmatch(r"doctrine-malformed-line:\d+", result["reason"])
    assert result["detectiveCloudLine"] is None


def test_doctrine_two_line_detective_cloud_block_is_malformed():
    text = _mutate_once(
        _read_doctrine(), _detective_line(), _detective_line() + "\nAnd one more line."
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert re.fullmatch(r"doctrine-malformed-line:\d+", result["reason"])
    assert result["detectiveCloudLine"] is None


@pytest.mark.parametrize("phrase", LD.DETECTIVE_CLOUD_INVARIANTS)
def test_doctrine_detective_cloud_missing_invariant_refuses(phrase):
    line = _detective_line()
    assert phrase in line
    text = _mutate_once(_read_doctrine(), line, line.replace(phrase, "nothing at all"))
    _assert_detective_refusal(text, f"doctrine-cloud-detective-invariant-missing:{phrase}")


def test_opening_ruling_count_word_matches_ruling_ids():
    text = _read_doctrine()
    count_word = _opening_ruling_count_word(text)
    if count_word not in _NUMBER_WORDS:
        raise AssertionError(
            f"launch-doctrine.md opening uses unknown ruling-count word {count_word!r} — "
            f"extend _NUMBER_WORDS or fix the doc"
        )
    assert _NUMBER_WORDS[count_word] == len(LD.RULING_IDS), (
        "launch-doctrine.md opening ruling-count word no longer matches "
        f"len(RULING_IDS): doc says {_NUMBER_WORDS[count_word]!r} ({count_word!r}), "
        f"code has {len(LD.RULING_IDS)!r}"
    )


def test_doctrine_unreadable(tmp_path):
    missing = tmp_path / "missing.md"
    result = LD.load(str(missing))
    assert result["ok"] is False
    assert result["reason"] == "doctrine-unreadable"
    assert result["rulings"] == []
    assert result["checks"] == []
    assert result["rulingsBlock"] is None
    assert result["digest"] is None


def test_doctrine_missing_block_rulings():
    text = _read_doctrine().replace("<!-- launch-doctrine:rulings:begin -->", "")
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == "doctrine-missing-block:rulings"
    assert result["rulings"] == []
    assert result["checks"] == []
    assert result["rulingsBlock"] is None
    assert result["digest"] is None


def test_doctrine_duplicate_block_rulings():
    text = _mutate_once(
        _read_doctrine(),
        "<!-- launch-doctrine:rulings:begin -->",
        "<!-- launch-doctrine:rulings:begin -->\n<!-- launch-doctrine:rulings:begin -->",
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == "doctrine-duplicate-block:rulings"
    assert result["rulings"] == []
    assert result["checks"] == []
    assert result["rulingsBlock"] is None
    assert result["digest"] is None


def test_doctrine_end_before_begin_treated_as_missing():
    text = _read_doctrine()
    begin = "<!-- launch-doctrine:rulings:begin -->"
    end = "<!-- launch-doctrine:rulings:end -->"
    assert text.count(begin) == 1
    assert text.count(end) == 1
    text = text.replace(begin, "TEMP_BEGIN")
    text = text.replace(end, begin)
    text = text.replace("TEMP_BEGIN", end)
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == "doctrine-missing-block:rulings"
    assert result["rulings"] == []
    assert result["checks"] == []
    assert result["rulingsBlock"] is None
    assert result["digest"] is None


def test_doctrine_malformed_line():
    text = _mutate_once(
        _read_doctrine(),
        "- `own-worktree` — build in your OWN worktree, NEVER the primary checkout.",
        "- own-worktree — build in your OWN worktree, NEVER the primary checkout.",
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"].startswith("doctrine-malformed-line:")
    assert result["rulings"] == []
    assert result["checks"] == []
    assert result["rulingsBlock"] is None
    assert result["digest"] is None


def test_doctrine_ruling_ids_mismatch():
    text = _mutate_once(
        _read_doctrine(),
        "- `own-worktree` — build in your OWN worktree, NEVER the primary checkout.\n",
        "",
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == "doctrine-ruling-ids-mismatch"
    assert result["rulings"] == []
    assert result["checks"] == []
    assert result["rulingsBlock"] is None
    assert result["digest"] is None


def test_doctrine_ruling_order():
    text = _read_doctrine()
    line_a = "- `own-worktree` — build in your OWN worktree, NEVER the primary checkout.\n"
    line_b = "- `base-moved` — if your base merges mid-build, rebase onto main, retarget, and disclose.\n"
    assert text.count(line_a) == 1
    assert text.count(line_b) == 1
    text = text.replace(line_a + line_b, line_b + line_a)
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == "doctrine-ruling-order"
    assert result["rulings"] == []
    assert result["checks"] == []
    assert result["rulingsBlock"] is None
    assert result["digest"] is None


def test_doctrine_duplicate_id():
    text = _mutate_once(
        _read_doctrine(),
        "- `remote-head` — verify the REMOTE head against your receipts before declaring the PR ready.",
        "- `remote-head` — verify the REMOTE head against your receipts before declaring the PR ready.\n"
        "- `remote-head` — duplicate line.",
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == "doctrine-duplicate-id:remote-head"
    assert result["rulings"] == []
    assert result["checks"] == []
    assert result["rulingsBlock"] is None
    assert result["digest"] is None


def test_doctrine_empty_text():
    text = _mutate_once(
        _read_doctrine(),
        "- `own-worktree` — build in your OWN worktree, NEVER the primary checkout.",
        "- `own-worktree` —    ",
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == "doctrine-empty-text:own-worktree"
    assert result["rulings"] == []
    assert result["checks"] == []
    assert result["rulingsBlock"] is None
    assert result["digest"] is None


def test_doctrine_ruling_invariant_missing():
    text = _mutate_once(
        _read_doctrine(),
        "- `own-worktree` — build in your OWN worktree, NEVER the primary checkout.",
        "- `own-worktree` — build in your own worktree, never the primary checkout.",
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == "doctrine-ruling-invariant-missing:own-worktree:OWN worktree"
    assert result["rulings"] == []
    assert result["checks"] == []
    assert result["rulingsBlock"] is None
    assert result["digest"] is None


def test_doctrine_check_mismatch():
    text = _mutate_once(
        _read_doctrine(),
        "- `engine-auth` (always) — Engine and CLI authentication",
        "- `engine-auth` (conditional) — Engine and CLI authentication",
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == "doctrine-check-mismatch"
    assert result["rulings"] == []
    assert result["checks"] == []
    assert result["rulingsBlock"] is None
    assert result["digest"] is None


@pytest.mark.parametrize("bad_input", [None, 42, "", b"bytes"])
def test_parse_refuses_non_string_or_empty(bad_input):
    result = LD.parse(bad_input)
    assert result["ok"] is False
    assert result["rulings"] == []
    assert result["checks"] == []
    assert result["rulingsBlock"] is None
    assert result["digest"] is None


def test_charter_missing_block():
    text = _read_charter().replace("<!-- launch-doctrine:preflight-charter:begin -->", "")
    result = LD.charter_checks(text)
    assert result["ok"] is False
    assert result["reason"] == "charter-missing-block"
    assert result["checks"] == []


def test_charter_duplicate_block():
    text = _mutate_once(
        _read_charter(),
        "<!-- launch-doctrine:preflight-charter:begin -->",
        "<!-- launch-doctrine:preflight-charter:begin -->\n<!-- launch-doctrine:preflight-charter:begin -->",
    )
    result = LD.charter_checks(text)
    assert result["ok"] is False
    assert result["reason"] == "charter-duplicate-block"
    assert result["checks"] == []


def test_charter_malformed_line():
    text = _mutate_once(
        _read_charter(),
        "**Engine and CLI authentication** (`engine-auth`, always) — relaunch practice, not policy, until this makes it policy.",
        "**Engine and CLI authentication** (engine-auth, always) — relaunch practice, not policy, until this makes it policy.",
    )
    result = LD.charter_checks(text)
    assert result["ok"] is False
    assert result["reason"].startswith("charter-malformed-line:")
    assert result["checks"] == []


# Bite: reworded ruling drops pinned invariant phrase — must refuse
def test_reworded_ruling_zero_refuses():
    text = _mutate_once(
        _read_doctrine(),
        "- `own-worktree` — build in your OWN worktree, NEVER the primary checkout.",
        "- `own-worktree` — build in a worktree of your own; do not use the primary checkout.",
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"].startswith("doctrine-ruling-invariant-missing:own-worktree:")


# Bite: reworded ruling (different words, same intent) — must refuse exact-text pin
def test_reworded_ruling_text_refuses():
    text = _mutate_once(
        _read_doctrine(),
        "- `own-worktree` — build in your OWN worktree, NEVER the primary checkout.",
        "- `own-worktree` — work in your OWN worktree, NEVER the primary checkout.",
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == "doctrine-ruling-text-mismatch:own-worktree"


# Bite: negated ruling keeps old substrings but inverts meaning — must refuse exact-text pin
def test_negated_ruling_zero_refuses():
    text = _mutate_once(
        _read_doctrine(),
        "- `own-worktree` — build in your OWN worktree, NEVER the primary checkout.",
        (
            "- `own-worktree` — use the primary checkout; OWN worktree and "
            "NEVER the primary checkout are obsolete."
        ),
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == "doctrine-ruling-text-mismatch:own-worktree"


# Bite: reordered rulings — must refuse with doctrine-ruling-order
def test_reordered_rulings_refuse():
    text = _read_doctrine()
    own = "- `own-worktree` — build in your OWN worktree, NEVER the primary checkout.\n"
    remote = "- `remote-head` — verify the REMOTE head against your receipts before declaring the PR ready.\n"
    assert text.count(own) == 1
    text = text.replace(own, "")
    text = text.replace(remote, own + remote)
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == "doctrine-ruling-order"


# Bite: removed ruling — must refuse with doctrine-ruling-ids-mismatch
def test_removed_ruling_refuses():
    text = _mutate_once(
        _read_doctrine(),
        "- `own-worktree` — build in your OWN worktree, NEVER the primary checkout.\n",
        "",
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == "doctrine-ruling-ids-mismatch"


# Bite: extra ruling id not in pinned set — must refuse with doctrine-ruling-ids-mismatch
def test_extra_ruling_id_refuses():
    text = _mutate_once(
        _read_doctrine(),
        "<!-- launch-doctrine:rulings:end -->",
        "- `extra-ruling` — this id is not in the pinned set.\n<!-- launch-doctrine:rulings:end -->",
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == "doctrine-ruling-ids-mismatch"


# Bite: leading/trailing whitespace inside ruling text — must refuse verbatim pin
def test_ruling_text_whitespace_refuses():
    text = _mutate_once(
        _read_doctrine(),
        "- `own-worktree` — build in your OWN worktree, NEVER the primary checkout.",
        "- `own-worktree` — build in your OWN worktree, NEVER the primary checkout. ",
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == "doctrine-ruling-text-mismatch:own-worktree"


def test_charter_and_artifact_agree():
    doctrine_text = _read_doctrine()
    charter_text = _read_charter()

    artifact = LD.parse(doctrine_text)
    assert artifact["ok"] is True
    artifact_tuple = tuple((c["id"], c["class"], c["text"]) for c in artifact["checks"])

    charter = LD.charter_checks(charter_text)
    assert charter["ok"] is True
    charter_tuple = tuple((c["id"], c["class"], c["text"]) for c in charter["checks"])

    assert len(artifact_tuple) == 7
    assert len(charter_tuple) == 7
    assert artifact_tuple == charter_tuple

    stripped = charter_text.replace("<!-- launch-doctrine:preflight-charter:begin -->", "")
    refused = LD.charter_checks(stripped)
    assert refused["ok"] is False
    assert refused["reason"] == "charter-missing-block"
    assert refused["checks"] == []


def test_artifact_blocks_exactly_once():
    text = _read_doctrine()
    assert text.count("<!-- launch-doctrine:rulings:begin -->") == 1
    assert text.count("<!-- launch-doctrine:rulings:end -->") == 1
    assert text.count("<!-- launch-doctrine:preflight:begin -->") == 1
    assert text.count("<!-- launch-doctrine:preflight:end -->") == 1


def test_ruling_line_returns_exact_source():
    result = LD.load()
    line = LD.ruling_line(result, "own-worktree")
    assert line == "- `own-worktree` — build in your OWN worktree, NEVER the primary checkout."
    assert LD.ruling_line(result, "nonexistent") is None
    assert LD.ruling_line({"ok": False}, "own-worktree") is None


def test_await_dispatches_ruling_states_the_real_slice_contract():
    import engine_dispatch

    parsed = LD.parse(_read_doctrine())
    assert parsed["ok"] is True
    ruling_text = next(r["text"] for r in parsed["rulings"] if r["id"] == "await-dispatches")
    expected_range = "%d..%d" % (
        engine_dispatch.MIN_SYNC_WAIT,
        engine_dispatch.MAX_SYNC_WAIT,
    )
    assert expected_range in ruling_text
    assert "positive slice" in ruling_text


# Bite: reworded await-dispatches ruling (stale zero-slice parenthetical) — must refuse exact-text pin
def test_reworded_await_dispatches_ruling_refuses():
    text = _mutate_once(
        _read_doctrine(),
        (
            "(a slice of 0..540 seconds — on `dispatch-review` a zero slice opens the run and "
            "returns now without starting an attempt; on `dispatch-write` a zero or too-short slice "
            "can return terminal `git-preflight-timeout` with nothing opened, so size the launch "
            "slice to the repository's git-preflight cost; progress comes from a re-invocation with "
            "a positive slice)"
        ),
        "(positive, never 0 — a zero slice launches nothing)",
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == "doctrine-ruling-text-mismatch:await-dispatches"


def test_ruling_text_constant_matches_the_artifact_for_every_ruling():
    parsed = LD.parse(_read_doctrine())
    assert parsed["ok"] is True
    by_id = {r["id"]: r["text"] for r in parsed["rulings"]}
    for rid in LD.RULING_IDS:
        assert by_id[rid] == LD.RULING_TEXT[rid]


# Independent oracle for the git-identity ruling. Every other assertion in this file derives
# its expectation from RULING_IDS, so a coordinated edit that drops the ruling from BOTH the
# markdown block and the constant would leave the whole suite green while a launched builder
# silently stops receiving the invariant. These literals are the thing that fails in that case.
def test_git_identity_ruling_is_delivered_with_its_prohibitions():
    parsed = LD.parse(_read_doctrine())
    assert parsed["ok"] is True
    assert "git-identity" in LD.RULING_IDS
    text = next(r["text"] for r in parsed["rulings"] if r["id"] == "git-identity")
    # Pinned in full, not by substring. Substring checks would still pass if a coordinated edit
    # appended an exception clause ("...unless an override is needed") around the asserted
    # phrases, which would leave the launched payload carrying a conditional invariant. Exact
    # equality means any softening has to edit this literal too — a third, deliberate site.
    assert text == (
        "commits inherit the git identity the worktree resolves through git's normal cascade "
        "— the `GIT_AUTHOR_*`/`GIT_COMMITTER_*` environment variables when set, otherwise "
        "repo-local `.git/config`, otherwise this environment's global config; "
        "never pass `-c user.name` or `-c user.email` and never synthesize one; a missing or "
        "wrong identity — `git -c user.useConfigOnly=true var GIT_AUTHOR_IDENT` or "
        "`GIT_COMMITTER_IDENT` failing, never an empty `git config` answer alone — "
        "is a park-and-report, not an improvisation."
    )
    # Delivery into the composed builder prompt is asserted against launcher.compose_launch in
    # test_launcher.py::test_compose_git_identity_ruling_in_prompt — not here. Re-checking the
    # block for the line at this point would be vacuous: a parsed ruling exists only because
    # _parse_rulings_block matched that exact line in that exact block.


# --- git_identity: the one test of whether a session has a commit identity -------------------

_IDENTITY_VARS = ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")


@pytest.fixture
def identity_repo(tmp_path, monkeypatch):
    """A real git repository whose git sees no configuration but its own and no identity variable."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for var in _IDENTITY_VARS + ("EMAIL",):
        monkeypatch.delenv(var, raising=False)
    path = tmp_path / "identity-repo"
    subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True, text=True)
    return str(path)


def test_git_identity_is_true_on_a_variables_only_environment(identity_repo, monkeypatch):
    for var, value in zip(_IDENTITY_VARS, ("A", "a@example.invalid", "C", "c@example.invalid")):
        monkeypatch.setenv(var, value)
    # axis: a builder whose identity comes only from the four variables does not park
    assert LD.git_identity(identity_repo) == {"author": True, "committer": True}


def test_git_identity_is_false_when_nothing_is_set(identity_repo):
    # axis: a session with no variable and no config resolves no identity, so it parks
    assert LD.git_identity(identity_repo) == {"author": False, "committer": False}


def test_git_identity_is_true_for_a_repo_local_name_and_email(identity_repo):
    for key, value in (("user.name", "Owner"), ("user.email", "owner@example.invalid")):
        subprocess.run(["git", "-C", identity_repo, "config", "--local", key, value], check=True,
                       capture_output=True, text=True)
    # axis: an identity set in the repository's own config counts
    assert LD.git_identity(identity_repo) == {"author": True, "committer": True}


def test_git_identity_is_false_when_only_EMAIL_is_set(identity_repo, monkeypatch):
    monkeypatch.setenv("EMAIL", "guess@example.invalid")
    # axis: an identity git would guess (from $EMAIL) never counts
    assert LD.git_identity(identity_repo) == {"author": False, "committer": False}


def test_gated_strings_ruling_is_delivered_with_its_prohibitions():
    parsed = LD.parse(_read_doctrine())
    assert parsed["ok"] is True
    assert "gated-strings" in LD.RULING_IDS
    text = next(r["text"] for r in parsed["rulings"] if r["id"] == "gated-strings")
    # Pinned in full, not by substring. Substring checks would still pass if a coordinated edit
    # appended an exception clause around the asserted phrases, which would leave the launched
    # payload carrying a conditional invariant. Exact equality means any softening has to edit
    # this literal too — a third, deliberate site.
    assert text == (
        "gated command strings reach disk only through file-write tools: a permission-gated literal "
        "that is being written or matched as data — a probe's test string, a memory or ledger append, "
        "any carrier that is not the command you intend to run — is never embedded inline in Bash text; "
        "a probe reads its test string from a file, a heredoc counts as Bash text, and a memory or "
        "ledger append carrying a gated literal is written with a file-write tool, never echoed "
        "through a shell. A command the session genuinely intends to execute — including the preflight "
        "`gh` write — is issued as itself in Bash so the permission classifier sees it; staging a "
        "gated command in a file and executing the file to dodge the gate is forbidden."
    )
    # Delivery into the composed builder prompt is asserted against launcher.compose_launch in
    # test_launcher.py::test_compose_gated_strings_ruling_in_prompt — not here.


def test_await_dispatches_ruling_is_delivered_with_its_prohibitions():
    parsed = LD.parse(_read_doctrine())
    assert parsed["ok"] is True
    assert "await-dispatches" in LD.RULING_IDS
    text = next(r["text"] for r in parsed["rulings"] if r["id"] == "await-dispatches")
    # Pinned in full, not by substring. The expectation is spelled out in this file — an
    # independent third site — so a coordinated edit to both launch-doctrine.md and RULING_TEXT
    # still fails here unless this literal is updated too.
    assert text == (
        'Ending the turn ends a headless session; "wait" must be an in-turn poll, never a final message. '
        "Until the handback or park comment is posted, every turn ends with a tool call; "
        "await every dispatch in-turn, and run each external engine dispatch you invoke directly "
        "through `dispatch-review`/`dispatch-write --max-wait` (a slice of 0..540 seconds — on "
        "`dispatch-review` a zero slice opens the run and returns now without starting an attempt; on "
        "`dispatch-write` a zero or too-short slice can return terminal `git-preflight-timeout` with "
        "nothing opened, so size the launch slice to the repository's git-preflight cost; progress "
        "comes from a re-invocation with a positive slice) re-invoked on the same `--run-dir` until the structured "
        "result is terminal, never an external `setsid`/`nohup` wrapper or an exit-code sentinel; "
        "independent dispatches go out CONCURRENTLY — give each member its own `--run-dir`, launch each one "
        "with a short positive slice, then re-invoke the originating verb on every non-terminal run in rotation "
        "until each returns terminal, so a batch costs its slowest member and not their sum; "
        "the concurrency comes from the engines working while you poll the others, never from issuing the "
        "calls together in one message — measured on one host: run-action calls serialize, and a launch call "
        "blocks for its whole slice, so keep the launch slice short; a native-subagent batch is the other "
        "channel and does go out as parallel dispatches in one message, harness-managed; "
        "independent means no result dependency, no shared writable worktree, and no shared output path — "
        "dependent orders and dispatches sharing a writable worktree stay sequenced; "
        "the concurrency changes a batch's shape, never its invariant: "
        "in-turn awaiting only; never harness-external backgrounding (`&`/setsid/nohup), never an "
        "unwatched run-dir at turn end; skill-owned seats and native subagents keep their own lifecycle; "
        "when the in-turn poll cannot fit the turn, park durably on the issue or PR. "
        "The same rule covers anything long-running you start locally — a full-suite run, a build, a long script — "
        "not only engine dispatches: await it in-turn, or park; never end a turn to wait."
    )
    # Delivery into the composed builder prompt is asserted against launcher.compose_launch in
    # test_launcher.py — not here.


def test_doctrine_gated_strings_ruling_invariant_missing():
    text = _mutate_once(
        _read_doctrine(),
        "- `gated-strings` — gated command strings reach disk only through file-write tools: "
        "a permission-gated literal that is being written or matched as data — a probe's test string, "
        "a memory or ledger append, any carrier that is not the command you intend to run — is never "
        "embedded inline in Bash text; a probe reads its test string from a file, a heredoc counts as "
        "Bash text, and a memory or ledger append carrying a gated literal is written with a file-write "
        "tool, never echoed through a shell. A command the session genuinely intends to execute — "
        "including the preflight `gh` write — is issued as itself in Bash so the permission classifier "
        "sees it; staging a gated command in a file and executing the file to dodge the gate is forbidden.",
        "- `gated-strings` — gated command strings reach disk only through file-write tools: "
        "a permission-gated literal that is being written or matched as data — a probe's test string, "
        "a memory or ledger append, any carrier that is not the command you intend to run — is not "
        "embedded inline in Bash text; a probe reads its test string from a file, a heredoc counts as "
        "Bash text, and a memory or ledger append carrying a gated literal is written with a file-write "
        "tool, never echoed through a shell. A command the session genuinely intends to execute — "
        "including the preflight `gh` write — is issued as itself in Bash so the permission classifier "
        "sees it; staging a gated command in a file and executing the file to dodge the gate is forbidden.",
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == (
        "doctrine-ruling-invariant-missing:gated-strings:never embedded inline in Bash text"
    )
    assert result["rulings"] == []
    assert result["checks"] == []
    assert result["rulingsBlock"] is None
    assert result["digest"] is None


def test_reworded_gated_strings_ruling_refuses():
    text = _mutate_once(
        _read_doctrine(),
        "- `gated-strings` — gated command strings reach disk only through file-write tools: "
        "a permission-gated literal that is being written or matched as data — a probe's test string, "
        "a memory or ledger append, any carrier that is not the command you intend to run — is never "
        "embedded inline in Bash text; a probe reads its test string from a file, a heredoc counts as "
        "Bash text, and a memory or ledger append carrying a gated literal is written with a file-write "
        "tool, never echoed through a shell. A command the session genuinely intends to execute — "
        "including the preflight `gh` write — is issued as itself in Bash so the permission classifier "
        "sees it; staging a gated command in a file and executing the file to dodge the gate is forbidden.",
        "- `gated-strings` — gated command strings go to disk only through file-write tools: "
        "a permission-gated literal that is being written or matched as data — a probe's test string, "
        "a memory or ledger append, any carrier that is not the command you intend to run — is never "
        "embedded inline in Bash text; a probe reads its test string from a file, a heredoc counts as "
        "Bash text, and a memory or ledger append carrying a gated literal is written with a file-write "
        "tool, never echoed through a shell. A command the session genuinely intends to execute — "
        "including the preflight `gh` write — is issued as itself in Bash so the permission classifier "
        "sees it; staging a gated command in a file and executing the file to dodge the gate is forbidden.",
    )
    result = LD.parse(text)
    assert result["ok"] is False
    assert result["reason"] == "doctrine-ruling-text-mismatch:gated-strings"


def test_gated_strings_ruling_invariants_registered():
    assert "gated-strings" in LD.RULING_INVARIANTS
    assert LD.RULING_INVARIANTS["gated-strings"] == (
        "never embedded inline in Bash text",
        "a heredoc counts as Bash text",
        "written with a file-write tool",
        "written or matched as data",
        "to dodge the gate is forbidden",
    )
