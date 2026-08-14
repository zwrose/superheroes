import importlib.util
import os
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
        "- `quota` (always) — Account and quota headroom",
        "- `quota` (conditional) — Account and quota headroom",
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
        "**Account and quota headroom** (`quota`, always) —",
        "**Account and quota headroom** (quota, always) —",
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

    assert len(artifact_tuple) == 8
    assert len(charter_tuple) == 8
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
        "— repo-local `.git/config` when set, otherwise this environment's global config; "
        "never pass `-c user.name` or `-c user.email` and never synthesize one; a missing or "
        "wrong identity — an empty *resolved* `git config user.email`/`user.name`, never an "
        "empty `--local` — is a park-and-report, not an improvisation."
    )
    # Delivery into the composed builder prompt is asserted against launcher.compose_launch in
    # test_launcher.py::test_compose_git_identity_ruling_in_prompt — not here. Re-checking the
    # block for the line at this point would be vacuous: a parsed ruling exists only because
    # _parse_rulings_block matched that exact line in that exact block.


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
    )
