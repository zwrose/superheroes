"""C1-L11b: a returning pull request's new review session reads only what changed (FR-44, FR-45, R3).

Pins, each at the place the rule is enforced:

I1  a fresh PR-mode session whose earlier record makes the decider answer `changed` runs round 1 as a returning
    round: no panel, and the scoped finder reads only the change since the last reviewed commit;
I2  every other fresh session (no earlier record, a `full` answer for any reason, a decision that could not be
    made) runs today's round 1 unchanged: a fault never reads `changed`;
I3  the decider answers `full` (`earlier-review-incomplete`) for an earlier record that was abandoned or is not
    `reviewed` / `awaits-owner`;
I4  a proven copy is in no returning-round input: not counted, not on the surface, not in any order, and its
    section (a binary one too) never reaches a diff parser;
I5  the decision is made once, at fresh state, and stored.

Drives the real round driver through the CLI functions (`cmd_next`, `cmd_submit`) on a real throwaway git repository.

Bite-proof record: c1l11b_wo_d1_returning_session
"""
import hashlib
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import countable_lines  # noqa: E402
import returning_review as R  # noqa: E402
import review_diff_bytes  # noqa: E402
import session_checkout  # noqa: E402
import test_returning_review_c1l11 as TR  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD  # the driver module these sessions run on is test_round_driver's own load of it

VENDORS = ["claude", "codex"]


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("GIT_CONFIG_PARAMETERS", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


# --- a returning session on a real repository ------------------------------------------------------------------

class Session:
    """A pull request reviewed once (``reviewed``) and then changed; its new session's directory and config."""

    def __init__(self, tmp_path, monkeypatch, *, first=None, change=None, record=None, areas=(TR.PAYMENTS, TR.CUSTOMER_DATA),
                 earlier="record", mode=None, cfg=None, base_after=None):
        self.repo = TR.Repo(tmp_path)
        self.base, self.reviewed, self.record = TR.returning(self.repo, first=first, areas=areas, **(record or {}))
        if change is not None:
            change(self.repo)
        self.head = self.repo.git("rev-parse", "HEAD")
        self.dir = str(tmp_path / "session")
        os.makedirs(self.dir)
        session_checkout.seed_session_meta(self.dir, self.repo.root)
        if mode is not None:
            meta_path = os.path.join(self.dir, "meta.json")
            with open(meta_path, encoding="utf-8") as fh:
                meta = json.load(fh)
            with open(meta_path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(dict(meta, mode=mode)) + "\n")
        if earlier == "record":
            self.write_earlier(self.record)
        elif earlier is not None:
            self.write_earlier(earlier)
        pinned = base_after(self.repo) if base_after is not None else self.base  # the base the session reviews against
        proc = review_diff_bytes.run_git_diff_three_dot(self.repo.root, pinned, self.head, timeout=60)
        # a returning session is given the seat map (`next --seat-map`) its scoped finder is seated from
        self.cfg = TRD._cfg(diff=proc.stdout.decode("utf-8"), repoRoot=self.repo.root, baseRef=pinned, maxRounds=4,
                            seatMap=TRD._assertable_seat_map(VENDORS, "claude"))
        self.cfg.update(cfg or {})
        monkeypatch.chdir(self.repo.root)

    def write_earlier(self, payload):
        with open(os.path.join(self.dir, "earlier-findings.json"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload))

    def next(self, first=True):
        answer = RD.cmd_next(self.dir, self.cfg if first else None)
        assert answer["ok"], answer
        return answer

    def state(self):
        ok, state = RD.load_state(self.dir)
        assert ok and isinstance(state, dict), state
        return state

    def round_one_files(self):
        """``{relative path: text}`` of everything under ``round-1/``: every order, sidecar and diff a seat is given."""
        found = {}
        top = os.path.join(self.dir, "round-1")
        for root, _dirs, names in os.walk(top):
            for name in names:
                with open(os.path.join(root, name), encoding="utf-8") as fh:
                    found[os.path.relpath(os.path.join(root, name), self.dir)] = fh.read()
        return found


def _append(rel, text):
    def change(repo):
        repo.write(rel, repo.read(rel) + text)
        repo.commit("fix")
    return change


def _write(rel, text):
    def change(repo):
        repo.write(rel, text)
        repo.commit("change")
    return change


def _spy(monkeypatch, replacement=None):
    """Replace the driver's decider seam with a recorder that calls ``replacement`` (default the real decider)."""
    calls = []
    real = replacement or RD._returning_decide

    def seam(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(RD, "_returning_decide", seam)
    return calls


def _stored(session):
    return session.state()["config"].get("returning")


def _round_one_is_the_panel(session):
    answer = session.next()
    state = session.state()
    assert answer["action"] == RD.P_PANEL and answer["round"] == 1, answer
    assert state["rounds"].get("1", {}).get("roundKind") != RD.RETURNING_KIND
    return answer, state


def _first_leg():
    return {"src/app.py": TR.numbered("app", 100), "src/util.py": TR.numbered("util", 30)}


# --- T1 (FR-44): a 40-line fix after one review reads only those lines -----------------------------------------------

def test_t1_a_forty_line_fix_runs_no_panel_and_the_scoped_finder_reads_only_the_fix(tmp_path, monkeypatch):
    fix = TR.numbered("fix", 40)
    s = Session(tmp_path, monkeypatch, first=_first_leg(), change=_append("src/app.py", fix))
    answer = s.next()
    state = s.state()
    assert (answer["action"], answer["phase"], answer["round"]) == (RD.P_SCOPED, RD.P_SCOPED, 1), answer
    assert state["rounds"]["1"]["roundKind"] == RD.RETURNING_KIND and state["fullPanelRan"] is False
    returning = state["rounds"]["1"]["returning"]
    assert returning["read"] == "changed" and returning["lastReviewed"] == s.reviewed and returning["countable"] == 40
    assert returning["newAreas"] == [] and set(returning) == {"read", "lastReviewed", "countable", "newAreas", "why"}
    assert [d for d in state["decisions"] if d["kind"] == RD.RETURNING_DECISION_KIND], state["decisions"]
    # the scoped finder's surface: the one file the fix touched, its 40 added lines as head lines 101..140
    hunks = answer["payload"]["hunks"]
    assert list(hunks) == ["src/app.py"], hunks
    assert [(h["start"], h["end"]) for h in hunks["src/app.py"] if h["start"]] == [(101, 140)], hunks
    inputs = s.round_one_files()
    fix_delta = inputs[os.path.join("round-1", "fix-delta.diff")]
    for i in range(40):
        assert "value_fix_%d = %d" % (i, i) in fix_delta
    [order_name] = [name for name in inputs
                    if name.startswith(os.path.join("round-1", "orders", RD.P_SCOPED)) and name.endswith(".md")]
    order = inputs[order_name]
    hunks_name, fix_delta_name = os.path.join("round-1", RD.ORDER_SIDECAR_SCOPED_HUNKS_FILE), os.path.join("round-1", "fix-delta.diff")
    # the scoped finder's seat inputs: the three files its order names (the hunks file and the fix-delta diff it fills
    # into its input lines, and the order itself). `diff.txt` (the whole change) is bookkeeping, not an input.
    assert os.path.join(s.dir, hunks_name) in order and os.path.join(s.dir, fix_delta_name) in order
    assert "The fixes' own diff" in order
    assert "head.diff" not in order and "diff.txt" not in order and "{{" not in order  # the whole change is no seat's input
    seat_inputs = {name: inputs[name] for name in (hunks_name, fix_delta_name, order_name)}
    # positive control: the scan reads the file the fix touched, so a leak of the untouched util module would show
    assert "src/app.py" in seat_inputs[hunks_name] and "src/app.py" in seat_inputs[fix_delta_name]
    # ... and nothing of what was already reviewed: no other file, no line of app.py beyond the hunk's own context
    for name, text in seat_inputs.items():
        assert "src/util.py" not in text and "value_util_" not in text, name
    for earlier_line in ("value_app_10 ", "value_app_50 ", "value_app_90 "):
        assert not any(earlier_line in text for text in seat_inputs.values()), earlier_line


def test_t1_a_returning_round_that_finds_nothing_converges_on_its_scoped_finder_with_no_panel(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, first=_first_leg(), change=_append("src/app.py", TR.numbered("fix", 40)))
    respond = TRD._responder(vendors=VENDORS)
    seen = []
    for step in range(20):
        n = s.next(first=step == 0)
        seen.append((n["action"], n["round"]))
        if n["action"] == RD.P_TERMINAL:
            break
        art = TRD._claim_reviewer(s.dir, n["phase"], respond(n["phase"], n["payload"], n["round"]))
        assert RD.cmd_submit(s.dir, n["phase"], n["attempt"], n["expectedStateHash"], art)["ok"]
    assert n["action"] == RD.P_TERMINAL and n["payload"]["verdict"] == "converged", seen
    assert n["payload"]["certification"]["fullPanel"] is False
    assert RD.P_PANEL not in [action for action, _ in seen] and (RD.P_SCOPED, 1) in seen, seen


# --- T2, T3, T4 (FR-45): the panel runs only for a big change, a new risk area, or an unclear risk ------------------

def test_t2_a_change_of_over_1000_countable_lines_since_the_last_reviewed_commit_runs_the_panel(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, change=_write("src/big.py", TR.numbered("big", 1001)))
    _answer, state = _round_one_is_the_panel(s)
    returning = state["rounds"]["1"]["returning"]
    assert returning["read"] == "full" and returning["countable"] == 1001
    assert any(w.startswith(R.WHY_OVER_BAR) for w in returning["why"]), returning


def test_t2_a_change_of_exactly_1000_countable_lines_runs_no_panel(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, change=_write("src/big.py", TR.numbered("big", 1000)))
    answer = s.next()
    assert answer["action"] == RD.P_SCOPED and s.state()["rounds"]["1"]["returning"]["countable"] == 1000


def test_t3_a_small_change_into_a_risk_area_the_pull_request_had_not_touched_runs_the_panel(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, change=_write("src/payments/charge.py", TR.numbered("charge", 5)))
    _answer, state = _round_one_is_the_panel(s)
    returning = state["rounds"]["1"]["returning"]
    assert returning["read"] == "full" and returning["newAreas"] == ["Payments"], returning
    assert any(w.startswith(R.WHY_NEW_AREA) for w in returning["why"]), returning


def test_t3_a_small_change_into_an_area_the_earlier_review_already_touched_runs_no_panel(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, first={"src/payments/pay.py": TR.numbered("pay", 20)},
                record={"touched": ["Payments"]}, change=_write("src/payments/charge.py", TR.numbered("charge", 5)))
    answer = s.next()
    assert answer["action"] == RD.P_SCOPED and s.state()["rounds"]["1"]["returning"]["newAreas"] == []


def test_t4_an_unclear_risk_runs_the_panel_when_the_earlier_review_was_clear(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, areas=None, change=_append("src/app.py", "extra = 1\n"))
    _answer, state = _round_one_is_the_panel(s)
    assert any(w.startswith(R.WHY_RISK_UNCLEAR) for w in state["rounds"]["1"]["returning"]["why"])


def test_t4_an_unclear_risk_runs_no_panel_when_the_earlier_review_was_unclear_too(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, areas=None, record={"unclear": True}, change=_append("src/app.py", "extra = 1\n"))
    answer = s.next()
    returning = s.state()["rounds"]["1"]["returning"]
    assert answer["action"] == RD.P_SCOPED and returning["read"] == "changed", answer
    assert any(w.startswith(R.WHY_UNCLEAR_AS_BEFORE) for w in returning["why"])


# --- T5 (R3): a proven copy a returning change adds is in no returning-round input ---------------------------------------

BLOB = bytes(range(256)) * 8  # a binary file: it has NUL bytes


def _write_blob(repo):
    os.makedirs(os.path.join(repo.root, "vendor"), exist_ok=True)
    with open(os.path.join(repo.root, "vendor", "blob.bin"), "wb") as fh:
        fh.write(BLOB)


def _vendor_a_binary_copy_and_edit(repo):
    _write_blob(repo)
    repo.write("src/app.py", repo.read("src/app.py") + TR.numbered("edit", 6))
    repo.commit("vendor a binary copy and edit")


def _blob_proof():
    return {"schema": countable_lines.PROOF_SCHEMA,
            "copies": [{"file": "vendor/blob.bin", "source": "upstream/blob.bin", "sha256": hashlib.sha256(BLOB).hexdigest()}]}


def test_t5_a_proven_binary_copy_beside_a_small_edit_is_counted_nowhere_and_read_nowhere(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, first=_first_leg(), change=_vendor_a_binary_copy_and_edit, cfg={"copyProof": _blob_proof()})
    assert "vendor/blob.bin" in s.cfg["diff"] and "Binary files" in s.cfg["diff"]
    answer = s.next()
    state = s.state()
    assert [c["file"] for c in state["provenCopies"]] == ["vendor/blob.bin"]
    assert answer["action"] == RD.P_SCOPED and answer["round"] == 1, answer
    returning = state["rounds"]["1"]["returning"]
    assert returning["read"] == "changed" and returning["countable"] == 6, returning
    assert not any(w.startswith(RD.RETURNING_SURFACE_UNKNOWN) for w in returning["why"]), returning
    assert all(d["kind"] != "fix-surface-unknown" for d in state["decisions"]), state["decisions"]
    assert list(answer["payload"]["hunks"]) == ["src/app.py"]
    assert [(h["start"], h["end"]) for h in answer["payload"]["hunks"]["src/app.py"] if h["start"]] == [(101, 106)]
    inputs = s.round_one_files()
    assert inputs and all("blob.bin" not in name and "blob.bin" not in text for name, text in inputs.items()), sorted(inputs)
    assert "blob.bin" not in state["_fixDeltaDiff"] and "blob.bin" not in json.dumps(state["_newSurface"])


def test_t5_a_returning_change_that_is_only_a_proven_binary_copy_converges_with_nothing_read(tmp_path, monkeypatch):
    def vendor_only(repo):
        _write_blob(repo)
        repo.commit("vendor a binary copy")

    s = Session(tmp_path, monkeypatch, change=vendor_only, cfg={"copyProof": _blob_proof()})
    answer = s.next()
    state = s.state()
    assert answer["action"] == RD.P_TERMINAL and answer["payload"]["verdict"] == "converged", answer
    assert state["rounds"]["1"]["returning"]["read"] == "changed" and state["rounds"]["1"]["returning"]["countable"] == 0
    assert state["rounds"]["1"]["scopedFinder"] == "skipped-empty-surface" and state["rounds"]["1"]["roundKind"] == RD.RETURNING_KIND
    assert all(d["kind"] != "fix-surface-unknown" for d in state["decisions"])


def test_t5_a_catch_up_merge_alone_converges_with_nothing_read(tmp_path, monkeypatch):
    def catch_up(repo):
        repo.moved = repo.main_commit("docs/other.md", "other\n")
        repo.merge_main()

    s = Session(tmp_path, monkeypatch, change=catch_up, base_after=lambda repo: repo.moved)
    answer = s.next()
    assert answer["action"] == RD.P_TERMINAL and answer["payload"]["verdict"] == "converged", answer
    assert s.state()["rounds"]["1"]["returning"]["read"] == "changed" and s.state()["rounds"]["1"]["returning"]["countable"] == 0


# --- T6: the fail-closed edges ----------------------------------------------------------------------------------------

def test_t6_e1_no_earlier_record_runs_todays_round_one_and_makes_no_decision(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, earlier=None, change=_append("src/shared.py", "extra = 1\n"))
    calls = _spy(monkeypatch)
    _answer, state = _round_one_is_the_panel(s)
    assert calls == [] and "returning" not in state["config"] and "returning" not in state["rounds"].get("1", {})
    assert not any(d["kind"] == RD.RETURNING_DECISION_KIND for d in state["decisions"])


def test_t6_e1_a_caller_cannot_supply_the_decision_itself(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, earlier=None, change=_append("src/shared.py", "extra = 1\n"),
                cfg={"returning": {"read": "changed", "lastReviewed": "a" * 40, "why": []}, "returningBaselineDiff": ""})
    _answer, state = _round_one_is_the_panel(s)
    assert "returning" not in state["config"] and "returningBaselineDiff" not in state["config"]


def test_t6_e2_a_review_record_missing_runs_the_panel(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, earlier={"ok": False, "reason": "review-record-missing"},
                change=_append("src/shared.py", "extra = 1\n"))
    _answer, state = _round_one_is_the_panel(s)
    returning = state["config"]["returning"]
    assert returning["read"] == "full" and returning["why"][0].startswith(R.WHY_NO_EARLIER), returning


def test_t6_e2_an_earlier_record_file_that_is_not_json_runs_the_panel(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, earlier=None, change=_append("src/shared.py", "extra = 1\n"))
    with open(os.path.join(s.dir, "earlier-findings.json"), "w", encoding="utf-8") as fh:
        fh.write("{not json")
    _answer, state = _round_one_is_the_panel(s)
    assert state["config"]["returning"]["read"] == "full"


def _raises(*_args, **_kwargs):
    raise RuntimeError("the decider broke")


@pytest.mark.parametrize("seam,token", [
    (_raises, RD.RETURNING_FAILED),
    (lambda *a, **k: None, RD.RETURNING_MALFORMED),
    (lambda *a, **k: "changed", RD.RETURNING_MALFORMED),
    (lambda *a, **k: {"read": "maybe", "why": []}, RD.RETURNING_MALFORMED),
    (lambda *a, **k: {"read": "changed", "lastReviewed": "a" * 40}, RD.RETURNING_MALFORMED),
    (lambda *a, **k: {"read": "changed", "why": ["changed-only: x"], "lastReviewed": "not-a-sha"}, RD.RETURNING_MALFORMED),
    (lambda *a, **k: {"read": "changed", "why": [3], "lastReviewed": "a" * 40}, RD.RETURNING_MALFORMED),
], ids=["raises", "none", "string", "unknown-read", "no-why", "no-last-reviewed", "why-not-text"])
def test_t6_e3_a_decider_that_raises_or_answers_badly_runs_the_panel_and_says_why(tmp_path, monkeypatch, seam, token):
    s = Session(tmp_path, monkeypatch, change=_append("src/shared.py", "extra = 1\n"))
    monkeypatch.setattr(RD, "_returning_decide", seam)
    _answer, state = _round_one_is_the_panel(s)
    returning = state["config"]["returning"]
    assert returning["read"] == "full" and returning["why"][0].startswith(token), returning
    assert "returningBaselineDiff" not in state["config"]
    assert state["rounds"]["1"]["returning"]["read"] == "full"


@pytest.mark.parametrize("cfg_drop", [{"repoRoot": None}, {"baseRef": None}, {"baseRef": "main"}], ids=["no-repo-root", "no-base", "base-not-a-sha"])
def test_t6_e4_a_missing_repo_root_or_a_base_that_is_not_a_sha_runs_the_panel_with_the_deciders_reason(tmp_path, monkeypatch, cfg_drop):
    s = Session(tmp_path, monkeypatch, change=_append("src/shared.py", "extra = 1\n"))
    for key, value in cfg_drop.items():
        if value is None:
            s.cfg.pop(key)
        else:
            s.cfg[key] = value
    # the checkout's session meta still names the repository; only the config lacks it
    _answer, state = _round_one_is_the_panel(s)
    returning = state["config"]["returning"]
    assert returning["read"] == "full" and returning["why"], returning
    assert returning["why"][0].split(":", 1)[0] in R.WHY_TOKENS, returning


def test_t6_e5_a_surface_the_driver_cannot_work_out_runs_the_panel_and_hands_nothing_back(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, first=_first_leg(), change=_append("src/app.py", TR.numbered("fix", 40)))
    monkeypatch.setattr(RD, "_fix_delta_surface", lambda *a, **k: None)
    _answer, state = _round_one_is_the_panel(s)
    assert state["terminal"] is None and all(d["kind"] != "fix-surface-unknown" for d in state["decisions"])
    returning = state["rounds"]["1"]["returning"]
    assert returning["read"] == "full" and returning["why"][-1].startswith(RD.RETURNING_SURFACE_UNKNOWN), returning
    assert state["config"]["returning"]["read"] == "full" and "returningBaselineDiff" not in state["config"]
    assert "_newSurface" not in state and state["step"] == RD.P_PANEL


def test_t6_e5_a_surface_that_raises_runs_the_panel(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, first=_first_leg(), change=_append("src/app.py", TR.numbered("fix", 40)))
    monkeypatch.setattr(RD, "_fix_delta_surface", _raises)
    _answer, state = _round_one_is_the_panel(s)
    assert state["rounds"]["1"]["returning"]["why"][-1].startswith(RD.RETURNING_SURFACE_UNKNOWN)


def test_t6_e5_a_baseline_diff_git_cannot_produce_runs_the_panel(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, first=_first_leg(), change=_append("src/app.py", TR.numbered("fix", 40)))
    monkeypatch.setattr(RD, "_returning_baseline_diff", lambda *a, **k: None)
    _answer, state = _round_one_is_the_panel(s)
    returning = state["rounds"]["1"]["returning"]
    assert returning["read"] == "full" and returning["why"][-1].startswith(RD.RETURNING_BASELINE_UNREADABLE), returning


@pytest.mark.parametrize("damage", [
    {"abandoned": {"reason": "the loop was closed before it ended"}},
    {"status": "not-reviewed"},
], ids=["abandoned", "not-reviewed"])
def test_t6_e6_an_earlier_review_that_was_abandoned_or_never_reviewed_runs_the_panel(tmp_path, monkeypatch, damage):
    s = Session(tmp_path, monkeypatch, change=_append("src/shared.py", "extra = 1\n"))
    s.write_earlier(dict(s.record, **damage))
    _answer, state = _round_one_is_the_panel(s)
    returning = state["config"]["returning"]
    assert returning["read"] == "full" and returning["why"][0].startswith(R.WHY_INCOMPLETE), returning


def test_t6_e7_a_loaded_state_never_decides_again(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, first=_first_leg(), change=_append("src/app.py", TR.numbered("fix", 40)))
    first = s.next()
    stored = _stored(s)
    assert first["action"] == RD.P_SCOPED and stored["read"] == "changed"
    # the record is now abandoned and the decider would raise: neither is read again
    s.write_earlier(dict(s.record, abandoned={"reason": "closed"}))
    monkeypatch.setattr(RD, "_returning_decide", _raises)
    calls = _spy(monkeypatch, replacement=lambda *a, **k: pytest.fail("the decider ran on a loaded state"))
    again = RD.cmd_next(s.dir, {"returning": {"read": "full", "why": []}})
    assert again["ok"] and again["action"] == RD.P_SCOPED and again["round"] == 1
    assert calls == [] and _stored(s) == stored


def test_t6_e8_a_branch_mode_session_makes_no_decision(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, mode="branch", change=_append("src/shared.py", "extra = 1\n"))
    calls = _spy(monkeypatch)
    _answer, state = _round_one_is_the_panel(s)
    assert calls == [] and "returning" not in state["config"] and "returning" not in state["rounds"].get("1", {})


# --- the decision is the decider's, and it is handed the session's proven copies ------------------------------------------

def test_the_driver_hands_the_decider_the_sessions_proven_copies_and_the_pinned_head(tmp_path, monkeypatch):
    s = Session(tmp_path, monkeypatch, first=_first_leg(), change=_vendor_a_binary_copy_and_edit, cfg={"copyProof": _blob_proof()})
    calls = _spy(monkeypatch)
    s.next()
    [(args, kwargs)] = calls
    assert args[:3] == (s.repo.root, s.base, s.head) and args[3]["finalCommit"]["sha"] == s.reviewed
    assert [c["file"] for c in kwargs["proven"]] == ["vendor/blob.bin"]
    assert kwargs["proven"] == [{k: c[k] for k in ("file", "source", "sha256")} for c in s.state()["provenCopies"]]


# --- T7 (I3): the decider reads full for an earlier review that did not finish -----------------------------------------

@pytest.mark.parametrize("damage,read", [
    ({"abandoned": {"reason": "closed"}}, "full"),
    ({"status": "not-reviewed"}, "full"),
    ({"status": None}, "full"),
    ({"status": "reviewed"}, "changed"),
    ({"status": "awaits-owner"}, "changed"),
], ids=["abandoned", "not-reviewed", "no-status", "reviewed", "awaits-owner"])
def test_t7_an_earlier_review_that_did_not_finish_reads_full_even_when_a_reviewer_covers_its_final_commit(tmp_path, damage, read):
    repo = TR.Repo(tmp_path)
    base, _, earlier = TR.returning(repo)
    assert earlier["reviewers"][0]["coversFinalCommit"] is True
    repo.write("src/app.py", repo.read("src/app.py") + "extra = 1\n")
    repo.commit("fix")
    record = {k: v for k, v in dict(earlier, **damage).items() if v is not None}
    got = TR.decide(repo, base, record)
    assert got["read"] == read, got["why"]
    if read == "full":
        assert TR.tokens(got) == [R.WHY_INCOMPLETE] and got["changedFiles"] == [] and got["countable"] is None
    else:
        assert TR.tokens(got) == [R.WHY_CHANGED_ONLY]
    assert R.WHY_INCOMPLETE in R.WHY_TOKENS
