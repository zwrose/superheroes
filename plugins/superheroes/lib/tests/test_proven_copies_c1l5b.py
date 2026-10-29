"""Tests for proven copies end to end: the copy proof at `next`, the diffs every seat is given, the leave-out file,
the test role's risk-area clause, the unread surface, the session account and the review record.

Edges: E1 a proof file that cannot be used refuses and writes no state · E2 a proof on a loaded state refuses · E3 a
head that cannot be resolved rejects every copy · E4 a copy whose section changed in a later round is given back · E5 a
rejected copy stays in every diff and never reaches the record · E6 a state from before the proof has no copy keys ·
E7 malformed stored entries are skipped · E8 a malformed `provenCopies` in an account refuses.
"""
import hashlib
import json
import os
import subprocess

import pytest

import countable_lines as cl
import review_record as rr
import review_record_session as rs
import round_driver as RD

from test_review_record import Fake as RecordFake, account as record_account, send as record_send
from test_review_record_session import Fake, Session, extras, put_extras

_PINNED_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
_IDENTITY = ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid"]

COPY = "src/payments/copy.py"
OTHER = "src/other.py"
MISMATCH = "src/mismatch.py"
COPY_SOURCE = "vendor/orig.py"
COPY_BYTES = b"".join(b"line %d\n" % i for i in range(1, 6))
OTHER_BYTES = b"print('other')\n"
MISMATCH_BYTES = b"alpha\nbeta\n"
RISK_AREAS = [{"name": "Payments", "covers": ["src/payments/*"], "why": "Charges customers.",
               "undo": "Hard: a charge needs a refund."}]
HEX = "a" * 64


@pytest.fixture(autouse=True)
def _pin_git_for_the_module(monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def _git(root, *args):
    proc = subprocess.run(["git", "-C", str(root), *_IDENTITY, *args], env=_PINNED_ENV, capture_output=True,
                          text=True, check=True)
    return proc.stdout


def _write(root, rel, data):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _commit(root, message):
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "HEAD").strip()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _core_md():
    block = json.dumps({"schemaVersion": 3, "verifyCommand": "npm test", "stackTags": ["node"],
                        "projectConfiguration": {"riskAreas": RISK_AREAS}}, indent=2)
    return ("<!-- superheroes-core: schemaVersion=3 status=confirmed created=2026-06-26 updated=2026-06-26 -->\n\n"
            "## Threat model\n\nsingle-user\n\n## Canonical patterns\n\n- x: a.ts:1\n\n"
            "```json superheroes-core\n%s\n```\n" % block).encode("utf-8")


def _proof(*copies):
    return {"schema": "copy-proof/1", "copies": list(copies)}


def _files(text):
    return [s["file"] for s in cl.parse_sections(text)]


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _next(session_dir, argv, capsys):
    rc = RD.main(["next", "--session-dir", session_dir, *argv])
    lines = [ln for ln in capsys.readouterr().out.strip().splitlines() if ln.strip()]
    return rc, (json.loads(lines[-1]) if lines else {})


class Fx:
    """A fixture repo (a base commit, then a head commit adding a proven copy, an uncovered file and a copy whose
    bytes do not match its proof) and a session directory that satisfies the base guard."""

    def __init__(self, tmp_path):
        self.root = tmp_path / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.root)], env=_PINNED_ENV, check=True,
                       capture_output=True)
        _write(self.root, ".claude/superheroes/core.md", _core_md())
        _write(self.root, "README.md", b"readme\n")
        self.base = _commit(self.root, "base")
        _write(self.root, COPY, COPY_BYTES)
        _write(self.root, OTHER, OTHER_BYTES)
        _write(self.root, MISMATCH, MISMATCH_BYTES)
        self.head = _commit(self.root, "head")
        self.diff = self.diff_now()
        self.proof = _proof(
            {"file": COPY, "source": COPY_SOURCE, "sha256": _sha(COPY_BYTES)},
            {"file": MISMATCH, "source": "vendor/orig2.py", "sha256": _sha(b"not these bytes\n")})
        self.proof_path = str(tmp_path / "proof.json")
        with open(self.proof_path, "w", encoding="utf-8") as fh:
            json.dump(self.proof, fh)
        self.dir = str(tmp_path / "session")
        os.makedirs(os.path.join(self.dir, "round-1"))
        self.diff_path = os.path.join(self.dir, "round-1", "diff.txt")
        with open(self.diff_path, "w", encoding="utf-8") as fh:
            fh.write(self.diff)
        toplevel = _git(self.root, "rev-parse", "--show-toplevel").strip()
        with open(os.path.join(self.dir, "meta.json"), "w", encoding="utf-8") as fh:
            json.dump({"mode": "branch", "baseRef": self.base, "baseBranch": "main", "baseFetch": "fetched",
                       "repoRoot": toplevel, "headSha": self.head}, fh)

    def diff_now(self):
        return _git(self.root, "diff", self.base + "...HEAD")

    def argv(self, *extra, fresh=True):
        out = ["--repo-root", str(self.root)]
        if fresh:
            out += ["--diff-path", self.diff_path]
        return out + list(extra)

    def state(self):
        ok, state = RD.load_state(self.dir)
        assert ok and state is not None
        return state


@pytest.fixture
def fx(tmp_path):
    return Fx(tmp_path)


@pytest.fixture
def started(fx, capsys):
    rc, out = _next(fx.dir, fx.argv("--copy-proof", fx.proof_path), capsys)
    assert rc == 0 and out["ok"], out
    return fx


def test_a_fresh_next_with_a_proof_gives_no_seat_the_proven_copy(started):
    # axis: the round's diff.txt leaves out the proven copy and keeps the uncovered file and the mismatched copy
    text = _read(os.path.join(started.dir, "round-1", "diff.txt"))
    assert sorted(_files(text)) == [MISMATCH, OTHER]
    assert COPY not in text
    assert _files(started.diff) == sorted([COPY, MISMATCH, OTHER])


def test_the_leave_out_file_names_exactly_the_proven_copy(started):
    # axis: the engine reviewer's leave-out file holds the proven copies and nothing else
    leave_out = json.loads(_read(os.path.join(started.dir, "reviewer-leave-out.json")))
    assert leave_out == {"schema": "leave-out/1", "files": [COPY]}


def test_the_state_stores_what_the_proof_proved_and_rejected(started):
    # axis: each proven copy is stored with its source, checksum and section digest; a rejected copy with its reason
    state = started.state()
    assert state["provenCopies"] == [{"file": COPY, "source": COPY_SOURCE, "sha256": _sha(COPY_BYTES),
                                      "section": cl.section_digest(started.diff, COPY)}]
    assert state["copyProofRejected"] == [{"file": MISMATCH, "reason": "checksum-mismatch"}]
    assert state["provenCopiesHead"] == started.head


def test_the_test_role_risk_clause_does_not_name_the_proven_copy(started):
    # axis: the risk-area clause reads the changed paths less the proven copies, which sit under a declared area
    state = started.state()
    control = RD._risk_areas_text("test-role", str(started.root), started.base, started.head)
    assert control == "Payments (matched: %s)" % COPY
    ph = RD._order_placeholders(RD.P_PANEL, "test-role", 0, state, state["config"], None, started.dir, 1, {},
                                RD.CHANNEL_FILE)
    assert ph["RISK_AREAS_TEXT"] == "none of this project's risk areas"


def test_the_counter_leaves_the_proven_copy_out_and_counts_the_other_two(started):
    # axis: the stored proven copies feed the counter, which leaves the copy out and counts the rest
    state = started.state()
    result = cl.count(started.diff, str(started.root), state["provenCopies"], head=state["provenCopiesHead"])
    rows = {row["file"]: row for row in result["files"]}
    assert rows[COPY]["counted"] is False and rows[COPY]["why"] == "proven-copy"
    assert rows[OTHER]["counted"] is True and rows[MISMATCH]["counted"] is True
    assert result["countable"] == rows[OTHER]["lines"] + rows[MISMATCH]["lines"] == 3
    assert result["unsettled"] == []


def test_the_unread_surface_leaves_out_the_proven_copy(started):
    # axis: a proven copy is no unread part, however little the read lists cover
    state = started.state()
    read_lists = [[{"file": MISMATCH, "lines": [[1, 2]]}, {"file": OTHER, "lines": [[1, 1]]}]]
    assert RD.unread_surface(state, started.diff, read_lists) == []
    # without the proof the copy would be the one unread part
    assert cl.unread_surface(started.diff, read_lists) == [{"file": COPY, "lines": [[1, 5]]}]
    partly = [[{"file": OTHER, "lines": [[1, 1]]}]]
    assert RD.unread_surface(state, started.diff, partly) == [{"file": MISMATCH, "lines": [[1, 2]]}]


def test_a_session_without_a_proof_writes_the_whole_diff_and_an_empty_leave_out(fx, capsys):
    # axis: no proof leaves today's diff.txt bytes, no copy keys in the state, and a leave-out file that names nothing
    rc, out = _next(fx.dir, fx.argv(), capsys)
    assert rc == 0 and out["ok"], out
    state = fx.state()
    assert not {"provenCopies", "copyProofRejected", "provenCopiesHead"} & set(state)
    assert _read(os.path.join(fx.dir, "round-1", "diff.txt")) == fx.diff
    assert json.loads(_read(os.path.join(fx.dir, "reviewer-leave-out.json"))) == {"schema": "leave-out/1", "files": []}


def test_a_later_round_gives_a_copy_back_when_its_section_changed(started):
    # axis: a copy whose section differs from the one checked is back in head.diff, out of the leave-out file
    state = started.state()
    os.makedirs(os.path.join(started.dir, "round-2"))
    state["headDiff"] = started.diff
    kept_path = RD._ensure_round_head_diff(started.dir, 2, state)
    assert COPY not in _read(kept_path)
    assert json.loads(_read(os.path.join(started.dir, "reviewer-leave-out.json")))["files"] == [COPY]
    _write(started.root, COPY, COPY_BYTES + b"line 6\n")
    _commit(started.root, "edit the copy")
    changed = started.diff_now()
    state["headDiff"] = changed
    head_path = RD._ensure_round_head_diff(started.dir, 2, state)
    assert sorted(_files(_read(head_path))) == sorted([COPY, MISMATCH, OTHER])
    assert _read(head_path) == changed
    assert json.loads(_read(os.path.join(started.dir, "reviewer-leave-out.json"))) == {
        "schema": "leave-out/1", "files": []}
    assert RD._left_out(state, changed) == []
    state["reviewedDiff"] = changed
    assert COPY in _read(RD._ensure_round_diff(started.dir, 2, state))


@pytest.mark.parametrize("body,detail", [
    (None, "proof-unreadable"),
    ("{not json", "proof-bad-json"),
    ('{"schema": "copy-proof/1", "copies": []}', "copies"),
    ('{"schema": "copy-proof/2", "copies": [{"file": "a", "source": "b", "sha256": "%s"}]}' % HEX, "schema"),
])
def test_a_proof_file_that_cannot_be_used_refuses_and_writes_no_state(fx, capsys, tmp_path, body, detail):
    # axis: a missing, unparseable or malformed proof refuses copy-proof-invalid, never a silent "no proof"
    path = str(tmp_path / "bad-proof.json")
    if body is not None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
    rc, out = _next(fx.dir, fx.argv("--copy-proof", path), capsys)
    assert rc == 1
    assert out == {"ok": False, "reason": "copy-proof-invalid", "detail": detail, "value": path}
    assert RD.load_state(fx.dir) == (True, None)


def test_a_proof_on_a_loaded_state_refuses(started, capsys):
    # axis: the proof is checked once, so it is refused on a state that already exists
    rc, out = _next(started.dir, started.argv("--copy-proof", started.proof_path, fresh=False), capsys)
    assert rc == 1
    assert out == {"ok": False, "reason": "copy-proof-not-fresh-state", "value": started.proof_path}


def test_a_head_that_cannot_be_resolved_rejects_every_copy(fx, tmp_path):
    # axis: with no head to read, every copy is rejected and nothing is left out
    nowhere = tmp_path / "not-a-repo"
    nowhere.mkdir()
    state = RD.new_state({"diff": fx.diff, "repoRoot": str(nowhere), "copyProof": fx.proof})
    assert state["provenCopies"] == []
    assert state["copyProofRejected"] == [{"file": COPY, "reason": "unreadable"},
                                          {"file": MISMATCH, "reason": "unreadable"}]
    assert state["provenCopiesHead"] is None
    os.makedirs(os.path.join(fx.dir, "round-2"))
    assert _read(RD._ensure_round_diff(fx.dir, 2, state)) == fx.diff
    assert json.loads(_read(os.path.join(fx.dir, "reviewer-leave-out.json")))["files"] == []


def test_a_state_from_before_the_proof_behaves_as_it_did(fx):
    # axis: a state with no copy keys writes the whole diff and an empty leave-out file
    state = {"reviewedDiff": fx.diff, "headDiff": None}
    os.makedirs(os.path.join(fx.dir, "round-2"))
    assert _read(RD._ensure_round_diff(fx.dir, 2, state)) == fx.diff
    assert json.loads(_read(os.path.join(fx.dir, "reviewer-leave-out.json"))) == {"schema": "leave-out/1", "files": []}
    assert RD.unread_surface(state, fx.diff, []) == cl.unread_surface(fx.diff, [])


@pytest.mark.parametrize("stored", [
    "junk",
    [None, "x", 3, {}],
    [{"file": COPY}],
    [{"file": 3, "source": "s", "sha256": HEX, "section": "x"}],
    [{"file": COPY, "source": None, "sha256": HEX, "section": "x"}],
    [{"file": COPY, "source": "s", "sha256": HEX, "section": None}],
])
def test_malformed_stored_copies_are_skipped_and_never_raise(fx, stored):
    # axis: a malformed stored entry leaves its file in the diff, whatever else the state holds
    state = {"reviewedDiff": fx.diff, "provenCopies": stored}
    assert RD._left_out(state, fx.diff) == []
    os.makedirs(os.path.join(fx.dir, "round-2"))
    assert _read(RD._ensure_round_diff(fx.dir, 2, state)) == fx.diff
    assert cl.still_proven(stored, None) == []


def test_a_copy_whose_section_changed_is_not_still_proven():
    # axis: still_proven keeps a copy only while its file's section digest equals the stored one
    one = ("diff --git a/c.py b/c.py\nnew file mode 100644\nindex 0000000..1111111\n--- /dev/null\n+++ b/c.py\n"
           "@@ -0,0 +1 @@\n+x\n")
    two = ("diff --git a/d.py b/d.py\nnew file mode 100644\nindex 0000000..2222222\n--- /dev/null\n+++ b/d.py\n"
           "@@ -0,0 +1 @@\n+y\n")
    edited = one.replace("+x", "+z")
    entries = [{"file": "c.py", "source": "s.py", "sha256": HEX, "section": cl.section_digest(one + two, "c.py")},
               {"file": "d.py", "source": "t.py", "sha256": "b" * 64, "section": cl.section_digest(one + two, "d.py")}]
    both = [{"file": "c.py", "source": "s.py", "sha256": HEX}, {"file": "d.py", "source": "t.py", "sha256": "b" * 64}]
    assert cl.still_proven(entries, one + two) == both
    assert cl.still_proven(entries, edited + two) == both[1:]
    assert cl.still_proven(entries, one) == both[:1]
    assert cl.section_digest(one, "c.py") == hashlib.sha256(one.encode("utf-8")).hexdigest()
    assert cl.section_digest(one, "nope.py") is None


# --- the session account and the record ---------------------------------------------------------------

DIFF_C = ("diff --git a/src/payments/copy.py b/src/payments/copy.py\nnew file mode 100644\nindex 0000000..1111111\n"
          "--- /dev/null\n+++ b/src/payments/copy.py\n@@ -0,0 +1 @@\n+x\n")
ENTRY = {"file": COPY, "source": COPY_SOURCE, "sha256": HEX, "section": cl.section_digest(DIFF_C, COPY)}
LISTED = {"file": COPY, "source": COPY_SOURCE, "sha256": HEX}


def _account(session):
    return rs.account_from_session(session, extras(), Fake().readers())


def test_the_account_carries_the_copies_still_proven_in_the_head_diff(tmp_path):
    # axis: the account lists the copies whose section is unchanged in the head diff, and only those
    kept = Session(tmp_path, provenCopies=[ENTRY], reviewedDiff=DIFF_C, headDiff=DIFF_C).seat("code-reviewer").save()
    assert _account(kept)["provenCopies"] == [LISTED]
    other = tmp_path / "b"
    other.mkdir()
    changed = Session(other, provenCopies=[ENTRY], reviewedDiff=DIFF_C,
                      headDiff=DIFF_C.replace("+x", "+y")).seat("code-reviewer").save()
    assert "provenCopies" not in _account(changed)
    plain = tmp_path / "c"
    plain.mkdir()
    assert "provenCopies" not in _account(Session(plain, reviewedDiff=DIFF_C).seat("code-reviewer").save())


def test_the_record_writes_and_summarizes_the_proven_copies(tmp_path):
    # axis: a proven copy reaches the record's JSON and its summary line from the session
    session = Session(tmp_path, provenCopies=[ENTRY], reviewedDiff=DIFF_C).seat("code-reviewer").save()
    fake = Fake()
    out = rs.write_from_session(session, put_extras(tmp_path, extras()), str(tmp_path), fake.readers())
    assert out["ok"], out
    record = rr.read(7, readers=fake.readers())
    assert record["provenCopies"] == [LISTED]
    body = fake.marked()[-1]["body"]
    assert "Proven copies, given to no reviewer: 1 file — %s (copy of %s)." % (COPY, COPY_SOURCE) in body


GOOD = {"file": "a.py", "source": "vendor/a.py", "sha256": HEX}


@pytest.mark.parametrize("value,detail", [
    ([], "provenCopies"),
    ("a.py", "provenCopies"),
    ({"file": "a.py"}, "provenCopies"),
    ([None], "provenCopies[0]"),
    ([{"file": "a.py", "source": "s"}], "provenCopies[0]"),
    ([dict(GOOD, extra=1)], "provenCopies[0]"),
    ([dict(GOOD, file=" ")], "provenCopies[0].file"),
    ([dict(GOOD, file=3)], "provenCopies[0].file"),
    ([dict(GOOD, source="")], "provenCopies[0].source"),
    ([GOOD, dict(GOOD, source="other")], "provenCopies[1].file"),
])
def test_a_malformed_proven_copies_list_refuses(tmp_path, value, detail):
    # axis: the account's provenCopies is a non-empty list of exact {file, source, sha256} entries, each file once
    fake = RecordFake()
    path = tmp_path / "account.json"
    path.write_text(json.dumps(record_account(provenCopies=value)))
    out = rr.write(str(path), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"], out["detail"]) == (False, "review-account-invalid", detail)
    assert fake.writes == []


@pytest.mark.parametrize("digest", ["a" * 63, "a" * 65, "A" * 64, "g" * 64, "", None, 7])
def test_a_proven_copy_checksum_that_is_not_64_lowercase_hex_refuses(tmp_path, digest):
    # axis: a proven copy's checksum is 64 lowercase hex, the form the advisor's vet can check against the source
    fake = RecordFake()
    path = tmp_path / "account.json"
    path.write_text(json.dumps(record_account(provenCopies=[dict(GOOD, sha256=digest)])))
    out = rr.write(str(path), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"], out["detail"]) == (False, "review-account-invalid", "provenCopies[0].sha256")
    assert fake.writes == []


def test_the_summary_lists_the_proven_copies_and_is_absent_without_them(tmp_path):
    # axis: the summary line shows exactly when the account carries the copies, in full at level 0 and as a count when compact
    two = [GOOD, {"file": "b.py", "source": "vendor/b.py", "sha256": "b" * 64}]
    fake = RecordFake()
    record_send(tmp_path, fake, provenCopies=two)
    body = fake.marked()[-1]["body"]
    assert "Proven copies, given to no reviewer: 2 files — a.py (copy of vendor/a.py), b.py (copy of vendor/b.py)." in body
    record = rr.build_record(record_account(provenCopies=two), RecordFake().readers())
    assert record["provenCopies"] == two
    assert "Proven copies, given to no reviewer: 2 files (listed in the full record)." in rr._summary(record, 1)
    assert "Proven copies, given to no reviewer: 2 files (listed in the full record)." in rr._summary(record, 2)
    plain = RecordFake()
    other = tmp_path / "plain"
    other.mkdir()
    record_send(other, plain)
    assert "Proven copies" not in plain.marked()[-1]["body"]
    assert "provenCopies" not in rr.build_record(record_account(), RecordFake().readers())
