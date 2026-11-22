"""#2518: characterization of `review_record._validate` and `receipt_disclosures.build_degraded_prose`,
pinned on the unsplit functions.

A later change splits both functions into named stages; these tests prove it changed no behaviour. The
invariant: for every input in the scenario set this module builds, `review_record._validate(account)` and
`receipt_disclosures.build_degraded_prose(state, form, journal)` produce exactly the outcome stored in
`fixtures/validate_degraded_prose_golden_2518.json`, which was generated on the unsplit code:

  - the same returned value, compared as canonical JSON (`sort_keys=True`, list order kept; for
    `build_degraded_prose` the `(degraded_out, skipped_blockers)` tuple is encoded as a list), or
  - the same refusal (`Refusal.reason` and `Refusal.detail`), or
  - the same non-refusal exception (type name and `str()`).

How the golden stores an outcome (one helper, `_encode_return`): a `_validate` return is stored as
`{"returnSha256": <sha256 hex of the canonical JSON string above>}`, not as the string itself. The reason is size:
a `_validate` return is the whole normalised account, repeated in full for each of the 600 returning scenarios, and
stored in full it made the golden 2.7 MB. A hash still fails on any byte change: the test compares the hash of the
canonical JSON it computes now with the stored hash, and two distinct strings do not share a sha256. What a hash
gives up is only readability of the returned account, which no reviewer could read at that size. A `_validate`
refusal stays `{"refusal": [...]}`, and every `build_degraded_prose` outcome (return and raise) stays in full text,
because the prose is the part a reader can read.

The test calls only the two entry points `review_record._validate(a)` and
`receipt_disclosures.build_degraded_prose(state, form, journal=None)`. It never names, imports or
inspects any other function of either module, so the split may add private stage functions freely.

Scenario set A1 (`_validate`): three rich valid accounts (`minimal`, `full`, `carried`); for each, every dict
key at every depth and index 0 of every list is deleted (dict keys only) or replaced by each of ten fixed
values; plus every pair of the nineteen stage-boundary faults G0..G18 on the full and the carried account (a
fault whose path the account lacks is left out); plus a few non-dict accounts.

Scenario set A2 (`build_degraded_prose`): every run-level line and its skip side, every per-round channel the
loop reads (a well-formed value, an edge value that survives the selector, values the selector drops, values
that survive and emit nothing, and values that raise), round order, the three receipt forms with and without
`schemaVersion`, the native-seat tail, and state shapes that raise.

Regenerate the golden on the code as it stands with:
    scripts/pinned-python -B plugins/superheroes/lib/tests/test_validate_degraded_prose_characterization_2518.py --write-golden
(`--out <path>` writes the golden to <path> instead, so two runs can be diffed.)

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/validate_degraded_prose_characterization_2518.md
"""
import copy
import functools
import hashlib
import json
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import receipt_disclosures  # noqa: E402
import review_record  # noqa: E402
import session_contract  # noqa: E402

GOLDEN_PATH = os.path.join(_HERE, "fixtures", "validate_degraded_prose_golden_2518.json")

HEAD = "b" * 40
EARLIER = "a" * 40
BASE = "c" * 40


# --- the one outcome encoder, used for both functions ---------------------------------------------

def _encode_return(text, hashed):
    """The one place that chooses how a returned value is stored: the canonical JSON `text` in full (prose), or its
    sha256 hex under `returnSha256` (a `_validate` return; see the module docstring for why)."""
    if hashed:
        return {"returnSha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    return {"return": text}


def _outcome(call, as_list=False, hash_return=False):
    try:
        value = call()
        if as_list:
            value = list(value)
    except review_record.Refusal as exc:
        return {"refusal": [exc.reason, exc.detail]}
    except Exception as exc:  # noqa: BLE001 — a non-refusal exception is itself the pinned outcome
        return {"raise": [type(exc).__name__, str(exc)]}
    return _encode_return(json.dumps(value, sort_keys=True, default=repr), hash_return)


# --- A1: the rich valid accounts -------------------------------------------------------------------

def _minimal():
    """The account `account()` builds in test_review_record.py (copied, not imported)."""
    return {"schema": "review-account/1", "pr": 7, "sessionId": "s1", "lane": "full", "laneReason": "big",
            "finalCommit": HEAD, "ci": "green",
            "reviewers": [{"name": "code-reviewer", "vendor": "codex", "model": "gpt-6.2-sol", "planned": True,
                           "ran": True, "runDir": "/run/code-reviewer"}],
            "findings": [], "rawFindingsFiles": [],
            "rounds": {"count": 1, "cap": 3, "stoppedAtCap": False}, "goAheads": [], "checked": ["read the diff"],
            "makers": [{"family": "anthropic"}]}


def _full():
    """Every optional member `_validate` reads, each in a valid shape (`abandoned` and `noResult` absent)."""
    return {
        "schema": "review-account/1", "pr": 7, "repo": "o/r", "sessionId": "s1", "lane": "full", "laneReason": "big",
        "finalCommit": HEAD, "ci": "green",
        "uncertified": {"terminal": "held", "reason": "the owner holds it", "note": "n"},
        "reviewers": [
            {"name": "code-reviewer", "vendor": "codex", "model": "gpt-6.2-sol", "planned": True, "ran": True,
             "runDir": "/run/c", "commit": HEAD, "step": 1, "notIndependent": False, "ownerWord": {"words": "go"},
             "readParts": [{"file": "a.py", "lines": [[1, 5], [7, 9]]}]},
            {"name": "test-role", "vendor": "claude", "model": "opus-5.5", "planned": True, "ran": True,
             "runDir": "/run/t", "commit": HEAD, "step": 2, "notIndependent": True, "ownerWord": {"words": "ok"},
             "readParts": [{"file": "b.py", "lines": [[2, 3]]}]},
        ],
        "makers": [{"family": "anthropic", "fromStep": 1}],
        "findings": [
            {"id": "code-001", "findingKey": "rr1:0001", "file": "a.py", "title": "t", "consequence": "c",
             "outcome": "fixed", "reason": "fixed in 1a2b3c4", "decidedBy": {"kind": "verifier"},
             "raisedBy": "code-reviewer",
             "grade": {"verdict": "confirmed", "reason": "read the line"},
             "repeatOf": {"findingKey": "rr1:0000", "id": "code-000", "fixHolds": True,
                          "kept": {"outcome": "fixed", "verdict": "confirmed", "members": ["code-000"]}},
             "breakItRuns": [{"test": "tests/t.py::t", "commit": HEAD, "changedWhy": None, "status": "ran",
                              "exitCode": 1, "output": "1 failed", "reason": None}],
             "kindOfMistake": {"kind": "uncapped retry", "places": [{"file": "a.py", "line": 3, "fixed": True}]},
             "fixGroup": {"id": "g1", "members": ["code-001", "code-002"], "commit": HEAD, "repairedAlone": True}},
            {"id": "code-002", "findingKey": "rr1:0002", "file": "b.py", "title": "u", "outcome": "ruling",
             "reason": "ruled", "decidedBy": {"kind": "owner-ruling"}},
            {"id": "code-003", "findingKey": "rr1:0003", "file": "c.py", "title": "v", "outcome": "left-for-owner",
             "reason": "for the owner",
             "boundedPassEvidence": {"fixCommit": None, "raisedByFinalAudit": True}},
        ],
        "rawFindingsFiles": ["raw/c.json"], "checked": ["read the diff"],
        "goAheads": [{"reviewer": "code-reviewer", "kind": "standing-ruling"}],
        "refused": [{"title": "t", "reason": "r"}],
        "commandRefusals": [{"round": 1, "command": "git push", "refusedBy": "hook", "next": "stopped",
                             "hook": "guard", "route": None}],
        "carriedChecks": [{"key": "code-001", "settled": "fixed", "evidence": "ran it", "commit": HEAD,
                           "checkedHead": HEAD}],
        "ownerRulings": [{"key": "code-002", "url": "http://c/2", "words": "go ahead"}],
        "sheetAnswers": {}, "baseRef": "origin/main", "reviewBase": BASE,
        "rounds": {"count": 2, "cap": 3, "stoppedAtCap": False, "capKind": "rounds",
                   "wider": [{"round": 2, "why": "wider look"}], "extraAudit": {"why": "one more"},
                   "boundedPass": {"trigger": "round-cap", "rounds": [2, 3], "auditedRounds": [3]}},
        "rerunChecks": [{"round": 1, "check": "validate", "decision": "went-on", "heads": [HEAD, None],
                         "runs": [{"status": "ran", "exitCode": 1, "output": "1 failed", "reason": None},
                                  {"status": "timed-out", "exitCode": None, "output": "", "reason": "timed out"}]}],
        "synthesisRounds": [1, 2],
        "outsideThisPR": [{"source": {"kind": "sweep", "name": "n", "sweepId": "s1"},
                           "hits": [{"id": "h1", "file": "x.py", "title": "t", "line": 4}]}],
        "unreadShare": {"unreadLines": 2, "countableLines": 10, "parts": [{"file": "a.py", "lines": [[1, 2]]}]},
        "sliceRecoveries": [{"seat": "code-reviewer:s1", "round": 1, "wave": 1, "recoveredInWave": 2,
                             "recoveredBy": ["code-reviewer:s2"], "commit": HEAD}],
        "provenCopies": [{"file": "a.py", "source": "b.py", "sha256": "a" * 64}],
        "sessionCost": {"tokens": 300, "minutes": 3.5, "runs": 3, "runsWithoutFigure": 1, "runsPartial": 1,
                        "complete": False,
                        "bySeat": {"code-reviewer": {"tokens": 100, "minutes": 1.0, "runs": 1},
                                   "test-role": {"tokens": 200, "minutes": 2.5, "runs": 2}}},
        "silenceWatchdogEnds": [{"seat": "code-reviewer", "attempt": 1, "silentSeconds": 90.5}],
        "unboundRuns": [{"seat": "test-role", "nonce": "n1", "case": "not-in-extras"}],
    }


def _carried():
    """An abandoned, carried account: a planned not-run reviewer with `noResult`, `carriedReview` + `carryBase` + a
    reviewer's `carriedFrom`, a finding open at its loop's end and one with bounded-pass audit evidence."""
    return {
        "schema": "review-account/1", "pr": 8, "sessionId": "s2", "lane": "full", "laneReason": None,
        "finalCommit": HEAD, "ci": None, "reviewBase": BASE,
        "abandoned": {"reason": "the session was stopped"},
        "reviewers": [
            {"name": "security-reviewer", "vendor": "codex", "model": "gpt-6.2-sol", "planned": True, "ran": False,
             "runDir": None, "commit": None, "noResult": "no-result"},
            {"name": "code-reviewer", "vendor": "codex", "model": "gpt-6.2-sol", "planned": True, "ran": True,
             "runDir": "/run/c", "commit": EARLIER, "carriedFrom": EARLIER},
        ],
        "carriedReview": {"lastReviewed": EARLIER, "why": "nothing changed since"}, "carryBase": BASE,
        "makers": [{"family": "anthropic"}],
        "findings": [
            {"id": "code-001", "findingKey": "rr1:1001", "file": "a.py", "title": "t", "outcome": "left-for-owner",
             "reason": "open at the loop's end",
             session_contract.OPEN_AT_LOOP_END_FIELD: True},
            {"id": "code-002", "findingKey": "rr1:1002", "file": "b.py", "title": "u", "outcome": "left-for-owner",
             "reason": "left after the bounded pass",
             session_contract.BOUNDED_PASS_EVIDENCE_FIELD: {
                 "fixCommit": "1a2b3c4",
                 "audit": {"ruling": "not-discharged", "reasonKind": "still-open", "reason": "no cap yet"}}},
        ],
        "rawFindingsFiles": [], "checked": ["read the diff"], "goAheads": [], "sheetAnswers": {},
        "rounds": {"count": 1, "cap": 3, "stoppedAtCap": True,
                   "boundedPass": {"trigger": "fix-keeps-failing", "rounds": [1], "auditedRounds": []}},
    }


ACCOUNTS = {"minimal": _minimal, "full": _full, "carried": _carried}

_VALUES = (("None", None), ("empty", ""), ("blank", "  "), ("0", 0), ("-1", -1), ("True", True), ("[]", []),
           ("{}", {}), ("x", "x"), ("sha40", "a" * 40))

# The stage-boundary faults, in the line order of `_validate`: (label, path tokens, "del" or the bad value).
_GROUPS = (
    ("G00", ("findings",), "del"),
    ("G01", ("schema",), "review-account/0"),
    ("G02", ("pr",), 0),
    ("G03", ("reviewers", 0, "name"), ""),
    ("G04", ("reviewBase",), "x"),
    ("G05", ("makers", 0, "family"), ""),
    ("G06", ("findings", 0, "id"), ""),
    ("G07", ("checked", 0), ""),
    ("G08", ("goAheads", 0, "kind"), "x"),
    ("G09", ("commandRefusals", 0, "round"), 0),
    ("G10", ("carriedChecks", 0, "settled"), "x"),
    ("G11", ("ownerRulings", 0, "url"), ""),
    ("G12", ("sheetAnswers",), []),
    ("G13", ("rounds", "count"), "x"),
    ("G14", ("rounds", "boundedPass", "trigger"), "x"),
    ("G15", ("synthesisRounds",), [2, 1]),
    ("G16", ("sessionCost", "tokens"), -1),
    ("G17", ("silenceWatchdogEnds", 0, "attempt"), 0),
    ("G18", ("unboundRuns", 0, "case"), "x"),
)


def _paths(obj, tokens=()):
    out = []
    if isinstance(obj, dict):
        for key in obj:
            out.append(tokens + (key,))
            out.extend(_paths(obj[key], tokens + (key,)))
    elif isinstance(obj, list) and obj:
        out.append(tokens + (0,))
        out.extend(_paths(obj[0], tokens + (0,)))
    return out


def _path_text(tokens):
    text = ""
    for token in tokens:
        if isinstance(token, int):
            text += "[%d]" % token
        elif text:
            text += "." + token
        else:
            text += token
    return text


def _has_path(root, tokens):
    node = root
    try:
        for token in tokens:
            node = node[token]
    except (KeyError, IndexError, TypeError):
        return False
    return True


def _mutate(root, tokens, value):
    parent = root
    for token in tokens[:-1]:
        parent = parent[token]
    if isinstance(value, str) and value == "del" and isinstance(tokens[-1], str):
        del parent[tokens[-1]]
    else:
        parent[tokens[-1]] = copy.deepcopy(value)


def _build_validate_scenarios():
    out = {}
    for name, build in ACCOUNTS.items():
        base = build()
        for tokens in sorted(_paths(base), key=_path_text):
            text = _path_text(tokens)
            if isinstance(tokens[-1], str):
                account = build()
                _mutate(account, tokens, "del")
                out["%s|%s|del" % (name, text)] = account
            for label, value in _VALUES:
                account = build()
                _mutate(account, tokens, value)
                out["%s|%s|%s" % (name, text, label)] = account
    for name in ("full", "carried"):
        base = ACCOUNTS[name]()
        live = [g for g in _GROUPS if _has_path(base, g[1])]
        for i, first in enumerate(live):
            for second in live[i + 1:]:
                account = ACCOUNTS[name]()
                for _label, tokens, value in (first, second):
                    if _has_path(account, tokens):
                        _mutate(account, tokens, value)
                out["%s|pair|%s+%s" % (name, first[0], second[0])] = account
    for label, value in (("None", None), ("list", []), ("str", "x"), ("int", 5), ("empty_dict", {}),
                         ("only_findings", {"findings": []})):
        out["root|%s" % label] = value
    return out


VALIDATE_SCENARIOS = _build_validate_scenarios()


# --- A2: the degraded-prose states -----------------------------------------------------------------

CERT = receipt_disclosures.RECEIPT_FORM_CERTIFIED
ATTESTED = receipt_disclosures.RECEIPT_FORM_ATTESTED
INTERIM = receipt_disclosures.RECEIPT_FORM_INTERIM

# channel -> well-formed value (ok), a value that survives the selector with a malformed inner row or a missing
# key (edge), values the selector drops (dropped), values that survive and emit nothing (quiet), values that
# survive and raise (raises), and further shapes (extra).
CHANNELS = {
    "fellOpen": {
        "ok": [{"seat": "code-reviewer", "configured": "codex", "reason": "timeout", "ran": "claude"}],
        "edge": [{"seat": "test-role"}, {}],
        "dropped": [[{"seat": "a"}, "junk"], [], "junk"]},
    "fellOpenProvenanceMissing": {
        "ok": ["code-reviewer", "test-role"], "edge": ["x"], "dropped": [["a", 1], []]},
    "seatMapUnavailable": {"ok": ["codex", "cursor"], "edge": ["claude"], "dropped": [[None], []]},
    "seatMapUnjudgeable": {
        "ok": ["no-seats"], "edge": ["self-asserted-author-family", "no-author-family"], "dropped": [[1]]},
    "vacuousSeats": {"ok": ["test-role"], "edge": ["a", "b", "c"], "dropped": [["a", None]]},
    "engagedArtifactSeats": {"ok": ["security-reviewer"], "edge": ["x", "y"], "dropped": [[3]]},
    "recordOrphansIgnored": {"ok": ["code-reviewer"], "edge": ["a", "b"], "dropped": [[{}]]},
    "priorCommentsUnavailable": {"ok": True, "edge": True, "dropped": [False, "yes", 1]},
    "focusNotesNotCarried": {
        "ok": [{"phase": "verify", "seats": ["a", "b"]}, {"phase": "collect", "seats": ["c"]}],
        "edge": [{"phase": 3, "seats": ["a"]}, {"phase": "", "seats": ["b"]}, {"phase": "p", "seats": "c"},
                 {"phase": "p", "seats": ["d", 1]}, {"phase": "good", "seats": []}],
        "quiet": [[{"phase": 3, "seats": ["a"]}, {"phase": "p"}]],
        "dropped": [[{"phase": "p", "seats": ["a"]}, "junk"]]},
    "judgmentDispositions": {
        "ok": [{"failClosed": True}, {"failClosed": False}, {"failClosed": True}],
        "edge": [{"failClosed": True}, {"x": 1}],
        "quiet": [[{"failClosed": False}, {}]],
        "dropped": [[{"failClosed": True}, 3]]},
    "gateGuidanceRowCarried": {
        "ok": [{"row": 1}, {"row": 2}], "edge": [{}], "dropped": [[{"row": 1}, "x"]]},
    "verifyVia": {
        "ok": {"via": "ci-exact-head", "workflow": "ci.yml", "runId": 5, "headSha": "abcdef1234567",
               "conclusion": "success", "reason": "local verify unavailable"},
        "edge": {"via": "ci-exact-head"},
        "quiet": [{"via": "local"}],
        "dropped": [{"via": 5}, "ci-exact-head"]},
    "breakItRuns": {
        "ok": [{"outcome": "not-run", "path": "tests/a.py", "reason": "no runner"},
               {"outcome": "ran", "path": "tests/b.py"}],
        "edge": [{"outcome": "not-run"}, {}],
        "quiet": [[{"outcome": "ran"}]],
        "dropped": [[{"outcome": "not-run"}, "junk"]]},
    "breakItMalformed": {
        "ok": [{"seat": "test-role:s1", "path": "tests/a.py", "error": "unexpected indent"}],
        "edge": [{}], "dropped": [["junk"]]},
    "verifierProvenance": {
        "ok": [{"outcome": "verdicts-ignored", "expected": "codex", "ran": "claude", "reason": "fell open"},
               {"outcome": "verdicts-ignored", "expected": "a", "ran": "b"}],
        "edge": [{"outcome": "verdicts-ignored"}],
        "quiet": [[{"outcome": "ok"}]],
        "dropped": [[{"outcome": "verdicts-ignored"}, "junk"]]},
    "synthesisUnseatable": {"ok": [{"cell": "proven"}], "edge": [{}], "dropped": [["junk"]]},
    "secondTestUnseatable": {
        "ok": [{"held": ["f1", "f2"]}, {"held": None}, {}],
        "edge": [{"held": "abc"}, {"held": {"a": 1}}],
        "raises": [[{"held": 1}], [{"held": 1.5}], [{"held": True}], [{"held": ["f"]}, {"held": 7}]],
        "dropped": [[{"held": ["f"]}, "junk"]]},
    "sweeps": {
        "ok": [{"sweepId": "s1", "title": "t", "notRun": "no budget", "missing": ["p1", 2], "ungraded": 3}],
        "edge": [{"missing": []}, {"ungraded": True}, {"ungraded": "2"}, {"ungraded": 2}, {}],
        "quiet": [[{"ungraded": 0}], [{"x": 1}]],
        "dropped": [[{"x": 1}, "junk"]]},
    "breakItKept": {
        "ok": [{"outcome": "dropped", "path": "tests/a.py"}, {"outcome": "kept", "path": "tests/b.py"}],
        "edge": [{"path": "q"}, {}],
        "quiet": [[{"outcome": "kept"}, {"outcome": "not-required"}, {"outcome": "ruled-out-of-scope"}]],
        "dropped": [[{"outcome": "kept"}, "junk"]]},
    "orderVendorProvenanceGaps": {
        "ok": [{"seat": "code-reviewer", "phase": "verify", "vendorSource": "defaulted"}, {"seat": "test-role"}],
        "edge": [{"seat": "a", "phase": 3}, {"seat": "b", "phase": ""}, {"seat": "c", "occurrence": 0},
                 {"seat": "d", "occurrence": True}],
        "dropped": [[{"seat": ""}], [{"seat": "a", "occurrence": -1}], [{"seat": "a", "occurrence": "1"}],
                    ["junk"]]},
    "adapterProvenance": {
        "ok": {"byPhase": {"collect": {"dispatchManifestUnavailable": True},
                           "verify": {"vendorEchoMismatch": [
                               {"seat": "s", "echo": "x", "recorded": "y"},
                               {"seat": "t", "echo": "a", "manifest": "m"}, "junk"]}}},
        "edge": {"byPhase": {"p": "notdict", "q": {"vendorEchoMismatch": []},
                             "r": {"dispatchManifestUnavailable": False}, "s": {"vendorEchoMismatch": ["junk"]}}},
        "quiet": [{"byPhase": {}}, {"other": 1}],
        "dropped": [{"byPhase": 5}, "junk", {}],
        "extra": [{"dispatchManifestUnavailable": True,
                   "vendorEchoMismatch": [{"seat": "s", "echo": "e", "recorded": "r"}]}]},
}


def _map(seats=None, **over):
    """A seat map with no violation under a driver author family of `anthropic` (two codex seats, a base roster)."""
    seat = {"vendor": "codex", "tier": "reviewer-deep", "source": "composed"}
    base = {"seats": seats if seats is not None else {"code-reviewer": dict(seat), "test-role": dict(seat)},
            "roster": ["code-reviewer", "test-role"], "laneBasis": {"floor": None}, "authorFamily": "anthropic"}
    base.update(over)
    return base


def _receipts(*maps):
    return [{"round": str(i + 1), "map": m} for i, m in enumerate(maps)]


CLAUDE = {"fixerVendor": "claude"}


def _build_prose_scenarios():
    out = {}

    def add(name, state, form=CERT, journal=None):
        assert name not in out, name
        out[name] = {"state": state, "form": form, "journal": journal}

    # -- run-level lines and their skip side
    add("run|empty_state", {})
    add("run|independence", {"independenceDegraded": True})
    add("run|independence_falsy", {"independenceDegraded": 0})
    add("run|base_degraded_with_fetch", {"config": {"baseDegraded": True, "baseFetch": "fetch-failed (offline)"}})
    add("run|base_degraded_no_fetch", {"config": {"baseDegraded": True}})
    add("run|base_fetch_not_degraded", {"config": {"baseFetch": "fetched"}})
    add("run|clean_map_no_lines", {"config": dict(CLAUDE), "seatMapReceipts": _receipts(_map())})
    add("run|panel_independence", {
        "config": dict(CLAUDE),
        "seatMap": _map(degradations=[{"constraint": "same-family", "seat": "code-reviewer"}]),
        "seatMapReceipts": _receipts(_map(degradations=[
            {"constraint": "same-family", "seat": "test-role"}, {"constraint": "same-family"},
            {"constraint": "other", "seat": "zzz"}, "junk", {"constraint": "same-family", "seat": "test-role"}]))})
    add("run|panel_independence_skip_other_degradations", {
        "config": dict(CLAUDE),
        "seatMapReceipts": _receipts(_map(degradations=[{"constraint": "other", "seat": "x"}]),
                                     _map(degradations="junk"))})
    add("run|same_family_on_a_maker_seat", {
        "config": dict(CLAUDE),
        "seatMapReceipts": _receipts(_map(
            seats={"code-reviewer": {"vendor": "claude", "tier": "reviewer-deep", "source": "composed"},
                   "test-role": {"vendor": "codex", "tier": "reviewer-deep", "source": "composed"}},
            degradations=[{"constraint": "same-family", "seat": "code-reviewer"}]))})
    pinned = _map(seats={
        "code-reviewer": {"vendor": "codex", "tier": "reviewer-deep", "source": "composed"},
        "test-role": {"vendor": "codex", "tier": "reviewer-deep", "source": "composed"},
        "security-reviewer": {"vendor": "codex", "tier": "reviewer", "source": "pinned"}},
        roster=["code-reviewer", "test-role", "security-reviewer"],
        violations=[{"constraint": "strong-tier", "seat": "security-reviewer"}])
    add("run|pin_excusal", {"config": dict(CLAUDE), "seatMapReceipts": _receipts(pinned)})
    unpinned = copy.deepcopy(pinned)
    unpinned["seats"]["security-reviewer"]["source"] = "composed"
    add("run|pin_excusal_skip_when_not_pinned", {"config": dict(CLAUDE), "seatMapReceipts": _receipts(unpinned)})

    violations = [
        {"constraint": "maker-family", "seat": "code-reviewer", "evidence": "alternative-live"},
        {"constraint": "critical-diversity", "evidence": "unproven-liveness"},
        {"constraint": "strong-tier", "seat": "security-reviewer"},
        {"constraint": "roster-missing-required"},
        {"constraint": "", "seat": "s"}, {"seat": "no-constraint"}, "junk",
        {"constraint": "maker-family", "seat": "code-reviewer"}]
    add("run|breach_withheld", {"rounds": {"1": {"seatMapViolations": copy.deepcopy(violations)}}})
    add("run|breach_marked_constraint_violated", {
        "rounds": {"1": {"seatMapViolations": copy.deepcopy(violations)}},
        "certification": {"shape": "full-constraint-violated"}})
    add("run|breach_shape_without_suffix", {
        "rounds": {"1": {"seatMapViolations": [{"constraint": "x"}]}}, "certification": {"shape": "full"}})
    add("run|breach_shape_not_a_string", {
        "rounds": {"1": {"seatMapViolations": [{"constraint": "x"}]}}, "certification": {"shape": 5}})
    add("run|breach_certification_not_a_dict_raises", {
        "rounds": {"1": {"seatMapViolations": [{"constraint": "x"}]}}, "certification": "full"})
    add("run|breach_rounds_two_dedupe", {"rounds": {
        "1": {"seatMapViolations": [{"constraint": "b", "seat": "s"}, {"constraint": "a"}]},
        "2": {"seatMapViolations": [{"constraint": "b", "seat": "s", "evidence": "alternative-live"}, "junk"]},
        "3": {"seatMapViolations": "junk"}, "4": "junk"}})
    add("run|breach_from_a_submitted_map", {"config": dict(CLAUDE), "seatMapReceipts": _receipts(_map(
        violations=[{"constraint": "maker-family", "seat": "code-reviewer", "evidence": "alternative-live"},
                    {"constraint": "strong-tier", "seat": "security-reviewer"}]))})
    add("run|breach_author_family_mismatch", {
        "config": dict(CLAUDE), "seatMapReceipts": _receipts(_map(authorFamily="openai"))})
    add("run|skipped_blockers", {"_skippedBlockers": [
        {"id": "b1", "title": "T1", "severity": "Critical", "reason": "owner chose", "file": "a.py", "line": 3},
        "junk", {"title": "only a title"}, {}, 5]})
    add("run|skipped_blockers_empty", {"_skippedBlockers": []})
    add("run|skipped_blockers_none", {"_skippedBlockers": None})
    add("run|skipped_blockers_a_string_iterates_chars", {"_skippedBlockers": "ab"})
    add("run|skipped_blockers_an_int_raises", {"_skippedBlockers": 5})
    add("run|unjudgeable_run_level", {"seatMapReceipts": _receipts(_map())})
    add("run|unjudgeable_covered_by_a_round_line", {
        "seatMapReceipts": _receipts(_map()),
        "rounds": {"1": {"seatMapUnjudgeable": ["self-asserted-author-family"]}}})
    add("run|unjudgeable_one_of_two_rounds_covered", {
        "seatMapReceipts": _receipts(_map(), _map()),
        "rounds": {"1": {"seatMapUnjudgeable": ["self-asserted-author-family"]}}})
    add("run|unjudgeable_no_seats_rounds_sorted", {"seatMapReceipts": [
        {"round": "10", "map": {"seats": {}}}, {"round": "2", "map": {"seats": {}}},
        {"round": "1", "map": {"seats": {}}}, {"round": "x", "map": {"seats": {}}}]})
    add("run|unjudgeable_none_with_empty_receipts", {"seatMapReceipts": []})
    add("run|unjudgeable_flag_in_a_round_alone", {"rounds": {"1": {"seatMapUnjudgeable": ["no-seats"]}}})

    # -- the native-seat tail
    recorded = {"outcome": "recorded"}
    add("native|no_transport", {}, journal=[dict(recorded, seat="code-reviewer")])
    add("native|runner_only_is_not_disclosed", {}, journal=[
        dict(recorded, seat="code-reviewer", **{session_contract.SEAT_TRANSPORT_KEY: session_contract.SEAT_TRANSPORT_RUNNER})])
    add("native|disclosed_transports_sorted", {}, journal=[
        dict(recorded, seat="zeta", **{session_contract.SEAT_TRANSPORT_KEY: session_contract.SEAT_TRANSPORT_NATIVE}),
        dict(recorded, seat="alpha", **{session_contract.SEAT_TRANSPORT_KEY: session_contract.SEAT_TRANSPORT_HAND_LANDED}),
        dict(recorded, seat="mid", **{session_contract.SEAT_TRANSPORT_KEY: session_contract.SEAT_TRANSPORT_ORCHESTRATOR}),
        dict(recorded, seat="odd", **{session_contract.SEAT_TRANSPORT_KEY: "something-else"})])
    add("native|missing_records_skipped", {}, journal=[
        dict(recorded, seat="a", cmd="record-missing"),
        dict(recorded, seat="b", casToken=session_contract.SEAT_MISSING_SCHEMA),
        dict(recorded, seat="c")])
    add("native|latest_record_per_identity_wins", {}, journal=[
        dict(recorded, seat="s", phase="p", round=1, attempt=1),
        dict(recorded, seat="s", phase="p", round=1, attempt=1,
             **{session_contract.SEAT_TRANSPORT_KEY: session_contract.SEAT_TRANSPORT_RUNNER}),
        dict(recorded, seat="t", phase="p", round=1, attempt=1, occurrence=0),
        dict(recorded, seat="t", phase="p", round=1, attempt=1, occurrence=1)])
    add("native|identity_from_record_identity", {}, journal=[
        dict(recorded, recordIdentity={"seat": "viaident", "phase": "q", "attempt": 2}),
        dict(recorded, recordIdentity="junk"), dict(recorded, seat=""), dict(recorded, seat=5)])
    add("native|journal_noise_ignored", {}, journal=["junk", {"outcome": "failed", "seat": "x"}, 5, None])
    add("native|journal_not_a_list", {}, journal="junk")
    add("native|journal_empty", {}, journal=[])

    # -- per-round channels
    for chan, spec in CHANNELS.items():
        add("ch|%s|ok" % chan, {"rounds": {"1": {chan: copy.deepcopy(spec["ok"])}}})
        add("ch|%s|edge" % chan, {"rounds": {"1": {chan: copy.deepcopy(spec["edge"])}}})
        for kind in ("dropped", "quiet", "raises", "extra"):
            for i, value in enumerate(spec.get(kind, [])):
                add("ch|%s|%s%d" % (chan, kind, i), {"rounds": {"1": {chan: copy.deepcopy(value)}}})
    all_ok = {chan: copy.deepcopy(spec["ok"]) for chan, spec in CHANNELS.items()}
    all_edge = {chan: copy.deepcopy(spec["edge"]) for chan, spec in CHANNELS.items()}
    add("all|every_channel_ok", {"rounds": {"1": copy.deepcopy(all_ok)}})
    add("all|every_channel_edge", {"rounds": {"1": copy.deepcopy(all_edge)}})

    # -- round order
    add("rounds|numeric_order_not_text_order", {"rounds": {
        "2": {"vacuousSeats": ["two"]}, "10": {"vacuousSeats": ["ten"]}, "1": {"vacuousSeats": ["one"]},
        "abc": {"vacuousSeats": ["word"]}}})
    add("rounds|every_channel_over_four_rounds", {"rounds": {
        "2": copy.deepcopy(all_ok), "10": copy.deepcopy(all_edge), "1": copy.deepcopy(all_ok),
        "abc": copy.deepcopy(all_edge)}})
    add("rounds|non_digit_keys_tie_at_zero_in_insertion_order", {"rounds": {
        "b": {"vacuousSeats": ["b"]}, "1": {"vacuousSeats": ["one"]}, "a": {"vacuousSeats": ["a"]},
        "0": {"vacuousSeats": ["zero"]}, "": {"vacuousSeats": ["blank"]}}})
    add("rounds|int_keys", {"rounds": {2: {"vacuousSeats": ["two"]}, 1: {"vacuousSeats": ["one"]}}})
    add("rounds|superscript_digit_key_raises", {"rounds": {"²": {"vacuousSeats": ["x"]}}})
    add("rounds|empty_dict", {"rounds": {}})
    add("rounds|none", {"rounds": None})
    add("rounds|non_dict_round_records", {"rounds": {"1": "junk", "2": None, "3": 5, "4": [],
                                                      "5": {"vacuousSeats": ["five"]}}})
    add("rounds|a_list_raises", {"rounds": ["1"]})
    add("rounds|a_string_raises", {"rounds": "junk"})

    # -- shapes of the state itself
    add("state|none_raises", None)
    add("state|list_raises", [])
    add("state|config_a_list_raises", {"config": ["x"]})
    add("state|config_none", {"config": None})

    # -- forms and the `verifyPasses` gating (the key rides a round entry; the prose never reads it)
    verify_round = {"verifyPasses": [{"pass": 1}], "vacuousSeats": ["a"]}
    for form in (CERT, ATTESTED, INTERIM, "bogus", None):
        for label, version in (("absent", "__absent__"), ("2", 2), ("3", 3), ("4", 4), ("5", 5), ("99", 99),
                               ("True", True), ("str3", "3"), ("None", None)):
            state = {"rounds": {"1": copy.deepcopy(verify_round)}}
            if version != "__absent__":
                state["schemaVersion"] = version
            add("form|%s|version=%s" % (form, label), state, form=form)
    add("form|bogus|no_verify_passes_returns", {"rounds": {"1": {"vacuousSeats": ["a"]}}}, form="bogus")
    add("form|bogus|empty_verify_passes_returns", {"rounds": {"1": {"verifyPasses": []}}}, form="bogus")
    add("form|bogus|malformed_verify_passes_returns", {"rounds": {"1": {"verifyPasses": ["junk"]}}}, form="bogus")

    # -- everything at once
    add("combo|every_run_level_line_and_a_round", {
        "independenceDegraded": True,
        "config": {"fixerVendor": "claude", "baseDegraded": True, "baseFetch": "fetch-failed"},
        "seatMapReceipts": _receipts(
            _map(degradations=[{"constraint": "same-family", "seat": "test-role"}]), pinned,
            {"seats": {}}),
        "_skippedBlockers": [{"id": "b", "title": "T", "severity": "Critical", "reason": "r", "file": "f", "line": 1}],
        "certification": {"shape": "full-constraint-violated"},
        "rounds": {"2": copy.deepcopy(all_ok), "1": {"seatMapViolations": [{"constraint": "c", "seat": "s"}],
                                                      "vacuousSeats": ["v"]}}},
        journal=[dict(recorded, seat="native-seat")])
    return out


PROSE_SCENARIOS = _build_prose_scenarios()


# --- running -----------------------------------------------------------------------------------------

def _run_validate(account):
    return _outcome(lambda: review_record._validate(copy.deepcopy(account)), hash_return=True)


def _run_prose(scenario):
    state = copy.deepcopy(scenario["state"])
    journal = copy.deepcopy(scenario["journal"])
    return _outcome(lambda: receipt_disclosures.build_degraded_prose(state, scenario["form"], journal=journal),
                    as_list=True)


def _compute_golden():
    return {"validate": {sid: _run_validate(VALIDATE_SCENARIOS[sid]) for sid in sorted(VALIDATE_SCENARIOS)},
            "prose": {sid: _run_prose(PROSE_SCENARIOS[sid]) for sid in sorted(PROSE_SCENARIOS)}}


@functools.lru_cache(maxsize=None)
def _generated():
    return _compute_golden()


@functools.lru_cache(maxsize=None)
def _golden():
    with open(GOLDEN_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def _diff_report(set_name):
    generated, golden = _generated()[set_name], _golden()[set_name]
    diffs = [sid for sid in sorted(set(generated) | set(golden)) if generated.get(sid) != golden.get(sid)]
    lines = ["%s: %d of %d scenarios differ (first %d shown):" % (set_name, len(diffs), len(generated), min(20, len(diffs)))]
    for sid in diffs[:20]:
        lines.append("  %s\n    now:    %s\n    golden: %s" % (sid, str(generated.get(sid))[:300], str(golden.get(sid))[:300]))
    return diffs, "\n".join(lines)


# --- the detectors -----------------------------------------------------------------------------------

def test_rich_accounts_are_valid():
    # axis: each rich account is accepted today, so the scenario set is not refused at the first check everywhere
    # (not among the declared bite-proof elements E1-E6; no neutralization was run for it)
    for name, build in ACCOUNTS.items():
        account = build()
        accepted = review_record._validate(copy.deepcopy(account))
        assert isinstance(accepted, dict), name
        assert accepted["pr"] == account["pr"], name


def test_validate_matches_golden():
    # axis: every `_validate` scenario returns, is refused or raises exactly as the golden recorded on the unsplit code
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/validate_degraded_prose_characterization_2518.md
    diffs, report = _diff_report("validate")
    assert not diffs, report


def test_prose_matches_golden():
    # axis: every `build_degraded_prose` scenario returns or raises exactly as the golden recorded on the unsplit code
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/validate_degraded_prose_characterization_2518.md
    diffs, report = _diff_report("prose")
    assert not diffs, report


def test_golden_covers_the_scenario_set():
    # axis: the golden's scenario ids equal the generated ids, so a scenario added or lost fails
    # (not among the declared bite-proof elements E1-E6; no neutralization was run for it)
    golden = _golden()
    assert sorted(golden) == ["prose", "validate"]
    assert sorted(golden["validate"]) == sorted(VALIDATE_SCENARIOS)
    assert sorted(golden["prose"]) == sorted(PROSE_SCENARIOS)
    assert len(VALIDATE_SCENARIOS) == len(set(VALIDATE_SCENARIOS))


# The text before the first " (" or ":" of every line `build_degraded_prose` can emit, copied from its format strings.
PROSE_PREFIXES = (
    # run level
    "independence", "base", "panel independence", "seat-map pin excusal", "seat-map constraint breach",
    "skipped-blocker", "seat-map-unjudgeable", "unprobed native seat(s)",
    # per round
    "reviewer-fell-open", "reviewer-fell-open-provenance-unavailable", "reviewer-fell-open-seatmap-unavailable",
    "vacuous-seat", "engaged-artifact-seat", "record-orphans-ignored", "prior-comments-unavailable",
    "focus-notes-not-carried", "judgment-fail-closed", "gate-guidance-row-carried", "verify-via-ci",
    "break-it-test-not-run", "break-it-test-malformed", "verifier-verdicts-ignored", "synthesis-unseatable",
    "second-test-unseatable", "sweep-not-run", "sweep-incomplete", "sweep-hit-ungraded",
    "break-it-test-not-kept", "order-vendor-provenance-gap", "adapter-provenance",
)


def _line_prefix(line):
    prefix = re.split(r" \(|:", line, maxsplit=1)[0]
    # the native-seat tail names its seats before the first colon: "unprobed native seat(s) a, b: ..."
    return "unprobed native seat(s)" if prefix.startswith("unprobed native seat(s) ") else prefix


def test_scenario_set_reaches_every_outcome_kind():
    # axis: the golden holds the outcome kinds and prose prefixes the scenario set exists to pin
    # (not among the declared bite-proof elements E1-E6; no neutralization was run for it)
    golden = _golden()
    kinds = {name: {kind for outcome in golden[name].values() for kind in outcome} for name in ("validate", "prose")}
    generated_kinds = {name: {kind for outcome in _generated()[name].values() for kind in outcome}
                       for name in ("validate", "prose")}
    # a `_validate` return is stored as `returnSha256`, never as a full `return`
    assert {"returnSha256", "refusal"} <= kinds["validate"]
    assert "return" not in kinds["validate"]
    # a `raise` is in the A1 golden exactly when the generated A1 set produces one
    assert ("raise" in kinds["validate"]) == ("raise" in generated_kinds["validate"])
    details = {outcome["refusal"][1] for outcome in golden["validate"].values() if "refusal" in outcome}
    assert len(details) >= 40, len(details)
    assert {"return", "raise"} <= kinds["prose"]
    lines = set()
    for outcome in golden["prose"].values():
        if "return" in outcome:
            lines.update(json.loads(outcome["return"])[0])
    reached = {_line_prefix(line) for line in lines}
    missing = [p for p in PROSE_PREFIXES if p not in reached]
    assert not missing, "prose prefixes no scenario reaches: %s" % missing


if __name__ == "__main__":
    if "--write-golden" in sys.argv[1:]:
        argv = sys.argv[1:]
        target = argv[argv.index("--out") + 1] if "--out" in argv else GOLDEN_PATH
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(_compute_golden(), handle, sort_keys=True, indent=1, ensure_ascii=False)
            handle.write("\n")
