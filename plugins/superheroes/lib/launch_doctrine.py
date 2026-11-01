#!/usr/bin/env python3
"""Machine home of the launch doctrine artifact.

Parses ``rubric/launch-doctrine.md`` and ``skills/showrunner/reference/dispatch-preflight.md``.
Every refusal is fail-closed: a caller that cannot parse the doctrine must never proceed as if
it had. None of these functions raise out of themselves."""
# WORKAROUND: machine parser for launch doctrine prose the host does not supply natively
# delete-when: the host injects launch rulings and preflight checks without a parsed artifact
from __future__ import annotations

import hashlib
import os
import re
import subprocess

RULING_IDS = (
    "own-worktree",
    "base-moved",
    "no-force-push",
    "design-forks",
    "await-dispatches",
    "turn-end",
    "remote-head",
    "git-identity",
    "gated-strings",
)
PREFLIGHT_CHECKS = (
    ("engine-auth", "always"),
    ("base-state", "always"),
    ("disjoint-surfaces", "conditional"),
    ("workspace-isolation", "always"),
    ("standing-rulings", "conditional"),
    ("owner-capability", "conditional"),
    ("grant-state", "conditional"),
)
RULING_TEXT = {
    "own-worktree": "build in your OWN worktree, NEVER the primary checkout.",
    "base-moved": "if your base merges mid-build, rebase onto main, retarget, and disclose.",
    "no-force-push": "never force-push (it is gated); use a fresh branch if history must move.",
    "design-forks": (
        "design forks inside ratified scope are your call with disclosure; "
        "park only genuinely consequential ones."
    ),
    "await-dispatches": (
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
    ),
    "turn-end": (
        "A headless lane never ends a turn with a background task or subagent still running: "
        "harness-tracked background work and a running subagent die when the turn ends, and "
        "`Monitor`, harness background-run completion and wakeup scheduling cannot wake a headless "
        "session, so none of them is a turn's exit plan; until the handback or park comment is "
        "posted, end every turn with a tool call, and await every outcome in-turn or park durably first."
    ),
    "remote-head": "verify the REMOTE head against your receipts before declaring the PR ready.",
    "git-identity": (
        "commits inherit the git identity the worktree resolves through git's normal cascade "
        "— the `GIT_AUTHOR_*`/`GIT_COMMITTER_*` environment variables when set, otherwise "
        "repo-local `.git/config`, otherwise this environment's global config; "
        "never pass `-c user.name` or `-c user.email` and never synthesize one; a missing or "
        "wrong identity — `git -c user.useConfigOnly=true var GIT_AUTHOR_IDENT` or "
        "`GIT_COMMITTER_IDENT` failing, never an empty `git config` answer alone — "
        "is a park-and-report, not an improvisation."
    ),
    "gated-strings": (
        "gated command strings reach disk only through file-write tools: a permission-gated literal "
        "that is being written or matched as data — a probe's test string, a memory or ledger append, "
        "any carrier that is not the command you intend to run — is never embedded inline in Bash text; "
        "a probe reads its test string from a file, a heredoc counts as Bash text, and a memory or "
        "ledger append carrying a gated literal is written with a file-write tool, never echoed "
        "through a shell. A command the session genuinely intends to execute — including the preflight "
        "`gh` write — is issued as itself in Bash so the permission classifier sees it; staging a "
        "gated command in a file and executing the file to dodge the gate is forbidden."
    ),
}
RULING_INVARIANTS = {
    "own-worktree": ("OWN worktree", "NEVER the primary checkout"),
    "git-identity": (
        "never pass `-c user.name` or `-c user.email`",
        "never synthesize one",
        "park-and-report",
        "`git -c user.useConfigOnly=true var GIT_AUTHOR_IDENT`",
    ),
    "await-dispatches": (
        "in-turn awaiting only; never harness-external backgrounding (`&`/setsid/nohup), never an unwatched run-dir at turn end",
        "no result dependency, no shared writable worktree, and no shared output path",
        'Ending the turn ends a headless session; "wait" must be an in-turn poll, never a final message.',
    ),
    "turn-end": (
        "never ends a turn with a background task or subagent still running",
        "cannot wake a headless session",
        "end every turn with a tool call",
    ),
    "gated-strings": (
        "never embedded inline in Bash text",
        "a heredoc counts as Bash text",
        "written with a file-write tool",
        "written or matched as data",
        "to dodge the gate is forbidden",
    ),
}
LAUNCHER_OWNED_CHECKS = ("standing-rulings",)
# The cloud-launch sentence lives once, in rubric/launch-doctrine.md; the parser checks only what it must carry.
CLOUD_LAUNCH_INVARIANTS = ("never a force-push", "never `main`")
# The detective cloud sentence lives once, in rubric/launch-doctrine.md; the parser checks only what it must carry.
DETECTIVE_CLOUD_INVARIANTS = (
    "cloud_builder.py intake",
    "disposable copies live only inside this cloud session",
    "push no branch",
)

_RULINGS_BEGIN = "<!-- launch-doctrine:rulings:begin -->"
_RULINGS_END = "<!-- launch-doctrine:rulings:end -->"
_PREFLIGHT_BEGIN = "<!-- launch-doctrine:preflight:begin -->"
_PREFLIGHT_END = "<!-- launch-doctrine:preflight:end -->"
_CLOUD_LAUNCH_BEGIN = "<!-- launch-doctrine:cloud-launch:begin -->"
_CLOUD_LAUNCH_END = "<!-- launch-doctrine:cloud-launch:end -->"
_DETECTIVE_CLOUD_BEGIN = "<!-- launch-doctrine:cloud-detective:begin -->"
_DETECTIVE_CLOUD_END = "<!-- launch-doctrine:cloud-detective:end -->"
_CHARTER_BEGIN = "<!-- launch-doctrine:preflight-charter:begin -->"
_CHARTER_END = "<!-- launch-doctrine:preflight-charter:end -->"

_RULING_LINE = re.compile(r"^- `(?P<id>[^`]+)` — (?P<text>.+)$")
_PREFLIGHT_LINE = re.compile(
    r"^- `(?P<id>[^`]+)` \((?P<class>always|conditional)\) — (?P<text>.+)$"
)
_CHARTER_LINE = re.compile(
    r"^\s*\d+\. \*\*(?P<label>[^*]+)\*\*"
    r".*? \(`(?P<id>[^`]+)`, (?P<class>always|conditional)\)"
    r".*$"
)
_CHARTER_ITEM_START = re.compile(r"^\s*\d+\.")


def git_identity(cwd):
    """{"author": bool, "committer": bool}: whether git, run in `cwd`, resolves a configured author
    and committer identity — the test the `git-identity` ruling names. `user.useConfigOnly`
    refuses only git's guessed identity (from $EMAIL, the host name or the passwd entry), so the
    GIT_AUTHOR_*/GIT_COMMITTER_* variables, repo config and global config all count. Never raises;
    carries no name or email."""
    found = {}
    for role, var in (("author", "GIT_AUTHOR_IDENT"), ("committer", "GIT_COMMITTER_IDENT")):
        try:
            got = subprocess.run(["git", "-c", "user.useConfigOnly=true", "var", var], cwd=cwd,
                                 capture_output=True, text=True, timeout=10)
            found[role] = got.returncode == 0
        except Exception:
            found[role] = False
    return found


def _refuse(reason: str) -> dict:
    return {
        "ok": False,
        "reason": reason,
        "rulings": [],
        "checks": [],
        "rulingsBlock": None,
        "digest": None,
        "cloudLaunchLine": None,
        "detectiveCloudLine": None,
    }


def _ok(
    rulings: list[dict],
    checks: list[dict],
    rulings_block: str,
    digest: str,
    cloud_launch_line: str,
    detective_cloud_line: str,
) -> dict:
    return {
        "ok": True,
        "reason": None,
        "rulings": rulings,
        "checks": checks,
        "rulingsBlock": rulings_block,
        "digest": digest,
        "cloudLaunchLine": cloud_launch_line,
        "detectiveCloudLine": detective_cloud_line,
    }


def doctrine_path(root: str | None = None) -> str:
    """Absolute path to the launch-doctrine artifact."""
    if root is None:
        base = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(os.path.join(base, "..", "rubric", "launch-doctrine.md"))
    return os.path.normpath(os.path.join(root, "rubric", "launch-doctrine.md"))


def _extract_block(text: str, begin: str, end: str, name: str) -> tuple[str | None, str | None]:
    """Return (body, reason). body excludes delimiter lines."""
    begin_count = text.count(begin)
    end_count = text.count(end)
    if begin_count == 0 or end_count == 0:
        return None, f"doctrine-missing-block:{name}"
    if begin_count > 1 or end_count > 1:
        return None, f"doctrine-duplicate-block:{name}"
    begin_idx = text.find(begin)
    end_idx = text.find(end)
    if end_idx < begin_idx:
        return None, f"doctrine-missing-block:{name}"
    body_start = begin_idx + len(begin)
    if body_start > 0 and text[body_start - 1] == "\n":
        body_start += 1
    body_end = end_idx
    if body_end > 0 and text[body_end - 1] == "\n":
        body_end -= 1
    return text[body_start:body_end], None


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _parse_rulings_block(text: str, body: str, body_start: int) -> tuple[list[dict] | None, str | None]:
    rulings: list[dict] = []
    seen: set[str] = set()
    for raw_line in body.split("\n"):
        if not raw_line.strip():
            continue
        m = _RULING_LINE.match(raw_line)
        if not m:
            offset = text.find(raw_line, body_start)
            return None, f"doctrine-malformed-line:{_line_number(text, offset)}"
        rid = m.group("id")
        rtext = m.group("text")
        if rid in seen:
            return None, f"doctrine-duplicate-id:{rid}"
        seen.add(rid)
        if not rtext.strip():
            return None, f"doctrine-empty-text:{rid}"
        rulings.append({"id": rid, "text": rtext, "line": raw_line})
    parsed_ids = tuple(r["id"] for r in rulings)
    if set(parsed_ids) != set(RULING_IDS):
        return None, "doctrine-ruling-ids-mismatch"
    if parsed_ids != RULING_IDS:
        return None, "doctrine-ruling-order"
    for rid, phrases in RULING_INVARIANTS.items():
        ruling_text = next(r["text"] for r in rulings if r["id"] == rid)
        for phrase in phrases:
            if phrase not in ruling_text:
                return None, f"doctrine-ruling-invariant-missing:{rid}:{phrase}"
    for ruling in rulings:
        rid = ruling["id"]
        if ruling["text"] != RULING_TEXT[rid]:
            return None, f"doctrine-ruling-text-mismatch:{rid}"
    return rulings, None


def _parse_preflight_block(text: str, body: str, body_start: int) -> tuple[list[dict] | None, str | None]:
    checks: list[dict] = []
    for raw_line in body.split("\n"):
        if not raw_line.strip():
            continue
        m = _PREFLIGHT_LINE.match(raw_line)
        if not m:
            offset = text.find(raw_line, body_start)
            return None, f"doctrine-malformed-line:{_line_number(text, offset)}"
        checks.append(
            {
                "id": m.group("id"),
                "class": m.group("class"),
                "text": m.group("text"),
            }
        )
    parsed = tuple((c["id"], c["class"]) for c in checks)
    if parsed != PREFLIGHT_CHECKS:
        return None, "doctrine-check-mismatch"
    return checks, None


def _parse_one_line_block(
    text: str, body: str, body_start: int, invariants: tuple[str, ...], stem: str,
) -> tuple[str | None, str | None]:
    lines = [raw_line for raw_line in body.split("\n") if raw_line.strip()]
    if len(lines) != 1:
        return None, f"doctrine-malformed-line:{_line_number(text, body_start)}"
    for phrase in invariants:
        if phrase not in lines[0]:
            return None, f"doctrine-{stem}-invariant-missing:{phrase}"
    return lines[0], None


def _parse_cloud_launch_block(text: str, body: str, body_start: int) -> tuple[str | None, str | None]:
    return _parse_one_line_block(text, body, body_start, CLOUD_LAUNCH_INVARIANTS, "cloud-launch")


def _parse_detective_cloud_block(text: str, body: str, body_start: int) -> tuple[str | None, str | None]:
    return _parse_one_line_block(text, body, body_start, DETECTIVE_CLOUD_INVARIANTS, "cloud-detective")


def parse(text: object) -> dict:
    """Parse doctrine text. Never raises."""
    if not isinstance(text, str) or not text:
        return _refuse("doctrine-missing-block:rulings")

    rulings_body, reason = _extract_block(text, _RULINGS_BEGIN, _RULINGS_END, "rulings")
    if reason is not None:
        return _refuse(reason)

    preflight_body, reason = _extract_block(text, _PREFLIGHT_BEGIN, _PREFLIGHT_END, "preflight")
    if reason is not None:
        return _refuse(reason)

    rulings_begin_idx = text.find(_RULINGS_BEGIN)
    rulings_end_idx = text.find(_RULINGS_END)
    rulings_block_start = rulings_begin_idx + len(_RULINGS_BEGIN)
    if rulings_block_start < len(text) and text[rulings_block_start] == "\n":
        rulings_block_start += 1
    rulings_block_end = rulings_end_idx
    if rulings_block_end > 0 and text[rulings_block_end - 1] == "\n":
        rulings_block_end -= 1
    rulings_block = text[rulings_block_start:rulings_block_end]

    rulings, reason = _parse_rulings_block(text, rulings_body, rulings_block_start)
    if reason is not None:
        return _refuse(reason)

    preflight_begin_idx = text.find(_PREFLIGHT_BEGIN)
    preflight_block_start = preflight_begin_idx + len(_PREFLIGHT_BEGIN)
    if preflight_block_start < len(text) and text[preflight_block_start] == "\n":
        preflight_block_start += 1

    checks, reason = _parse_preflight_block(text, preflight_body, preflight_block_start)
    if reason is not None:
        return _refuse(reason)

    cloud_body, reason = _extract_block(text, _CLOUD_LAUNCH_BEGIN, _CLOUD_LAUNCH_END, "cloud-launch")
    if reason is not None:
        return _refuse(reason)
    cloud_block_start = text.find(_CLOUD_LAUNCH_BEGIN) + len(_CLOUD_LAUNCH_BEGIN)
    if cloud_block_start < len(text) and text[cloud_block_start] == "\n":
        cloud_block_start += 1

    cloud_launch_line, reason = _parse_cloud_launch_block(text, cloud_body, cloud_block_start)
    if reason is not None:
        return _refuse(reason)

    detective_body, reason = _extract_block(
        text, _DETECTIVE_CLOUD_BEGIN, _DETECTIVE_CLOUD_END, "cloud-detective")
    if reason is not None:
        return _refuse(reason)
    detective_block_start = text.find(_DETECTIVE_CLOUD_BEGIN) + len(_DETECTIVE_CLOUD_BEGIN)
    if detective_block_start < len(text) and text[detective_block_start] == "\n":
        detective_block_start += 1

    detective_cloud_line, reason = _parse_detective_cloud_block(text, detective_body, detective_block_start)
    if reason is not None:
        return _refuse(reason)

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return _ok(rulings, checks, rulings_block, digest, cloud_launch_line, detective_cloud_line)


def load(path: str | None = None) -> dict:
    """Load and parse the doctrine artifact. Never raises."""
    target = doctrine_path() if path is None else path
    try:
        with open(target, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return _refuse("doctrine-unreadable")
    return parse(text)


def ruling_line(parsed: dict, ruling_id: str) -> str | None:
    """Return the exact source line for a ruling id, or None."""
    if not parsed.get("ok"):
        return None
    for ruling in parsed.get("rulings", []):
        if ruling["id"] == ruling_id:
            return ruling["line"]
    return None


def _extract_charter_block(text: str) -> tuple[str | None, str | None]:
    begin_count = text.count(_CHARTER_BEGIN)
    end_count = text.count(_CHARTER_END)
    if begin_count == 0 or end_count == 0:
        return None, "charter-missing-block"
    if begin_count > 1 or end_count > 1:
        return None, "charter-duplicate-block"
    begin_idx = text.find(_CHARTER_BEGIN)
    end_idx = text.find(_CHARTER_END)
    if end_idx < begin_idx:
        return None, "charter-missing-block"
    body_start = begin_idx + len(_CHARTER_BEGIN)
    if body_start < len(text) and text[body_start] == "\n":
        body_start += 1
    body_end = end_idx
    if body_end > 0 and text[body_end - 1] == "\n":
        body_end -= 1
    return text[body_start:body_end], None


def charter_checks(charter_text: object) -> dict:
    """Parse dispatch-preflight.md's marked block. Never raises."""
    if not isinstance(charter_text, str) or not charter_text:
        return {"ok": False, "reason": "charter-missing-block", "checks": []}

    body, reason = _extract_charter_block(charter_text)
    if reason is not None:
        return {"ok": False, "reason": reason, "checks": []}

    checks: list[dict] = []
    body_start = charter_text.find(body) if body else 0
    for raw_line in body.split("\n"):
        if not raw_line.strip():
            continue
        if not _CHARTER_ITEM_START.match(raw_line):
            continue
        m = _CHARTER_LINE.match(raw_line)
        if not m:
            offset = charter_text.find(raw_line, body_start)
            return {
                "ok": False,
                "reason": f"charter-malformed-line:{_line_number(charter_text, offset)}",
                "checks": [],
            }
        checks.append(
            {
                "id": m.group("id"),
                "class": m.group("class"),
                "text": m.group("label"),
            }
        )
    return {"ok": True, "reason": None, "checks": checks}
