"""Tests for lib/canon.py, the Canon write helper (#1820)."""
import json
import os
import subprocess
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import canon  # noqa: E402
import definition_doc  # noqa: E402

REPO_CANON = os.path.join(_LIB, "..", "..", "..", "docs", "superheroes", "canon.md")
WRITTEN = "2026-10-12"
SID = "abcd1234-ffff"


def _git(cwd, *args):
    subprocess.run(["git", "-C", cwd, *args], check=True, capture_output=True, text=True)


def _entry(n, sid="abcd1234"):
    return ("- **%s-%s-%d** · %s · standing · A ruling. · owner's words: none recorded · "
            "where: s, time not recorded" % (WRITTEN, sid, n, WRITTEN))


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A repo whose default branch (origin/main) holds Canon entry -3 and whose working branch
    holds entry -1 only; the lookup is pinned to the repo home with that default ref."""
    origin, work = str(tmp_path / "origin.git"), str(tmp_path / "work")
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", origin], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", work], check=True)
    _git(work, "config", "user.email", "t@t")
    _git(work, "config", "user.name", "t")
    path = os.path.join(work, "docs", "superheroes", "canon.md")
    os.makedirs(os.path.dirname(path))
    with open(path, "w") as fh:
        fh.write(canon.HEADER + _entry(3) + "\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "canon")
    _git(work, "remote", "add", "origin", origin)
    _git(work, "push", "-q", "origin", "main")
    _git(work, "remote", "set-head", "origin", "main")
    _git(work, "checkout", "-qb", "work")
    with open(path, "w") as fh:
        fh.write(canon.HEADER + _entry(1) + "\n")
    loc = {"path": path, "home": "repo", "gitRoot": work, "exists": True,
           "defaultRef": "origin/main"}
    monkeypatch.setattr(definition_doc, "resolve_canon", lambda root: dict(loc))
    return loc


def _run(capsys, *argv):
    code = canon.main(["canon.py", *argv])
    return code, json.loads(capsys.readouterr().out)


def _fields(ground="owner-call", ruling="A failed import keeps the previous data.", **extra):
    argv = ["--root", ".", "--session-id", SID, "--written", WRITTEN, "--ground", ground,
            "--date", WRITTEN, "--scope", extra.pop("scope", "standing"), "--ruling", ruling,
            "--where", "advisor session abcd1234, 14:05 UTC"]
    for k, v in extra.items():
        argv += ["--" + k.replace("_", "-"), v]
    return argv


def _contract_homes():
    with open(canon.CONTRACT, encoding="utf-8") as fh:
        return canon._homes(fh.read())


# axis: the homes are read from § What stays out itself; every kind the helper refuses has one.
def test_homes_read_from_the_contract_cover_every_kind():
    homes = _contract_homes()
    assert set(homes) == {"act", "merge", "disposition", "board"}
    assert "collector" in homes["disposition"].lower()
    assert "owner half" in homes["merge"]
    assert "STATE block" in homes["act"]
    assert homes["board"] == "the board"


# axis: every declared stays-out ground is refused with the record's home named.
@pytest.mark.parametrize("ground", sorted(canon.STAY_OUT_GROUNDS))
def test_declared_stays_out_ground_refused_with_home(project, capsys, ground):
    code, out = _run(capsys, "append", *_fields(ground=ground))
    assert code == 1 and out["reason"] == "canon-stays-out"
    assert out["home"] == _contract_homes()[canon.STAY_OUT_GROUNDS[ground]]
    assert canon.STAYS_OUT in out["detail"]


# axis: the closed shapes beyond a declared ground: a disposition ruling, bare go-word owner's
# words, and bookkeeping are refused with the record's home, whatever ground was declared.
@pytest.mark.parametrize("ruling,words,kind", [
    ("116 - a", None, "disposition"),
    ("The importer keeps old data.", "a - launch it now in the cloud", "act"),
    ("The importer keeps old data.", "merge #1810", "merge"),
    ("The importer keeps old data.", "ship it", "act"),
    ("The importer keeps old data.", "tier full", "act"),
    ("The importer keeps old data.", "force-push it", "act"),
    ("The importer keeps old data.", "release v0.43.0 please.", "merge"),
    ("The importer keeps old data; filed as #1820.", None, "board"),
    ("The importer keeps old data, scheduled for phase 2.", None, "board"),
])
def test_recognized_stays_out_refused_with_home(project, capsys, ruling, words, kind):
    extra = {"owners_words": words} if words else {}
    code, out = _run(capsys, "append", *_fields(ruling=ruling, **extra))
    assert code == 1 and out["reason"] == "canon-stays-out" and out["kind"] == kind
    assert out["home"] == _contract_homes()[kind]


# axis: accepted gap, pinned so nobody widens recognition: a full ruling sentence under a valid
# ground is not caught (canon-contract.md, "Every session writes through the helper").
def test_full_ruling_sentence_with_valid_ground_is_not_refused_accepted_gap(project, capsys):
    ruling = "Merge the stack once CI is green and the vet receipt is posted."
    code, out = _run(capsys, "append", *_fields(ruling=ruling, owners_words="none recorded"))
    assert code == 0 and out["appended"][0].split(canon.SEP)[3] == ruling


# axis: a sentence that merely begins with a go-verb is a ruling, not a bare go-word.
@pytest.mark.parametrize("words", ["Force-push is never permitted on shared branches.",
                                   "Merge failures keep the previous branch unchanged.",
                                   "Merge PR branches only after CI passes."])
def test_standing_sentence_starting_with_go_verb_is_not_refused(project, capsys, words):
    code, out = _run(capsys, "append", *_fields(ruling=words, owners_words=words))
    assert code == 0 and out["appended"][0].split(canon.SEP)[3] == words


# axis: a generated entry the reader would refuse is refused before Canon is written.
def test_leading_blank_cedes_refused_before_write(project, capsys):
    before = open(project["path"]).read()
    code, out = _run(capsys, "append", *_fields(ground="ceded-call", cedes=" naming",
                                                example="fixture_old"))
    assert code == 1 and out["reason"] == "canon-bad-field"
    assert open(project["path"]).read() == before


# axis: a held comment with a wrapped entry is refused, not returned with the tail dropped.
def test_hold_refuses_wrapped_held_entry(project, capsys, tmp_path):
    held = tmp_path / "held.md"
    held.write_text(canon.HELD_MARKER + "\n" + _entry(7).replace(" · owner's", "\nowner's") + "\n")
    code, out = _run(capsys, "hold", *_fields(), "--held-file", str(held))
    assert code == 1 and out["reason"] == "canon-bad-line"


# axis: recognition is narrow: no real entry in this repo's Canon reads as a stays-out record.
def test_repo_canon_has_no_false_positive():
    with open(REPO_CANON, encoding="utf-8") as fh:
        lines = [l.rstrip("\n") for l in fh if canon._ID_RE.match(l)]
    assert len(lines) > 100
    for line in lines:
        canon._check_held_line(line)


def test_unknown_ground_refused(project, capsys):
    code, out = _run(capsys, "append", *_fields(ground="vibe"))
    assert code == 1 and out["reason"] == "canon-unknown-ground"


def test_separator_in_a_field_refused(project, capsys):
    code, out = _run(capsys, "append", *_fields(ruling="One · two"))
    assert code == 1 and out["reason"] == "canon-bad-field"


# axis: a valid owner-call, principle and ceded-call line is held, then appended byte for byte.
@pytest.mark.parametrize("ground,extra", [
    ("owner-call", {"scope": "piece importer-1a2b3c", "owners_words": "keep the old data"}),
    ("principle", {}),
    ("ceded-call", {"cedes": "test-fixture naming", "example": "fixture_old_data"}),
])
def test_held_line_appended_byte_for_byte(project, capsys, tmp_path, ground, extra):
    code, held = _run(capsys, "hold", *_fields(ground=ground, **extra))
    assert code == 0 and held["comment"].splitlines()[0] == canon.HELD_MARKER
    comment = tmp_path / "held.md"
    comment.write_text(held["comment"])
    before = open(project["path"]).read()
    code, out = _run(capsys, "append", "--root", ".", "--lines-file", str(comment))
    assert code == 0 and out["appended"] == [held["line"]]
    assert open(project["path"]).read() == before + held["line"] + "\n"
    code, again = _run(capsys, "append", "--root", ".", "--lines-file", str(comment))
    assert again["appended"] == [] and again["skipped"] == [held["line"]]


# axis: the delegation field is emitted as written, independent of the helper's own output.
def test_ceded_call_line_carries_cedes_and_example(project, capsys):
    code, held = _run(capsys, "hold", *_fields(
        ground="ceded-call", cedes="test-fixture naming", example="fixture_old_data"))
    assert code == 0
    assert "cedes: test-fixture naming; example: fixture_old_data" in held["line"].split(canon.SEP)


# axis: a take-back persists exactly its supersedes field and keeps the earlier ceded entry.
def test_take_back_line_supersedes_ceded_entry(project, capsys):
    ceded_id = "%s-abcd1234-2" % WRITTEN
    ceded = _entry(2).replace("A ruling.", "Fixture naming is ceded.")
    with open(project["path"], "a") as fh:
        fh.write(ceded + "\n")
    code, out = _run(capsys, "append", *_fields(ground="take-back", supersedes=ceded_id))
    assert code == 0
    line = out["appended"][0]
    assert ("supersedes: " + ceded_id) in line.split(canon.SEP)
    text = open(project["path"]).read().splitlines()
    assert ceded in text and line in text


# axis: the id continues past the default-branch copy, the working copy, and the held lines.
def test_id_counts_default_copy(project, capsys):
    assert _run(capsys, "hold", *_fields())[1]["id"] == "%s-abcd1234-4" % WRITTEN


def test_id_counts_working_copy(project, capsys):
    with open(project["path"], "a") as fh:
        fh.write(_entry(5) + "\n")
    assert _run(capsys, "append", *_fields())[1]["appended"][0].startswith(
        "- **%s-abcd1234-6**" % WRITTEN)


def test_id_counts_held_lines(project, capsys, tmp_path):
    held = tmp_path / "held.md"
    held.write_text(canon.HELD_MARKER + "\n" + _entry(7) + "\n")
    code, out = _run(capsys, "hold", *_fields(), "--held-file", str(held))
    assert out["id"] == "%s-abcd1234-8" % WRITTEN
    assert out["comment"] == canon.HELD_MARKER + "\n" + _entry(7) + "\n" + out["line"] + "\n"


# axis: a malformed --written never mints an id the replay cannot recognize; Canon stays unchanged.
@pytest.mark.parametrize("command", ["append", "hold"])
@pytest.mark.parametrize("written", ["2026/10/12", "2026-10-12T14:05:00Z"])
def test_malformed_written_refused_canon_unchanged(project, capsys, command, written):
    before = open(project["path"], "rb").read()
    code, out = _run(capsys, command, *_fields(written=written))
    assert code == 1 and out["reason"] == "canon-bad-field"
    assert open(project["path"], "rb").read() == before


# axis: a hold followed by an append of a new entry never mints the held id twice.
def test_append_new_entry_counts_held_lines(project, capsys, tmp_path):
    code, held = _run(capsys, "hold", *_fields(ruling="The first ruling."))
    assert code == 0 and held["id"] == "%s-abcd1234-4" % WRITTEN
    comment = tmp_path / "held.md"
    comment.write_text(held["comment"])
    code, out = _run(capsys, "append", *_fields(ruling="The second ruling."),
                     "--held-file", str(comment))
    assert code == 0 and out["appended"][0].startswith("- **%s-abcd1234-5**" % WRITTEN)
    code, drained = _run(capsys, "append", "--root", ".", "--lines-file", str(comment))
    assert code == 0 and drained["appended"] == [held["line"]] and drained["skipped"] == []
    text = open(project["path"]).read()
    assert out["appended"][0] in text.splitlines() and held["line"] in text.splitlines()


def test_append_held_file_without_marker_refused(project, capsys, tmp_path):
    held = tmp_path / "held.md"
    held.write_text("some other comment\n" + _entry(7) + "\n")
    before = open(project["path"]).read()
    code, out = _run(capsys, "append", *_fields(), "--held-file", str(held))
    assert code == 1 and out["reason"] == "canon-held-not-marked"
    assert open(project["path"]).read() == before


def test_held_comment_without_marker_refused(project, capsys, tmp_path):
    held = tmp_path / "held.md"
    held.write_text("some other comment\n" + _entry(7) + "\n")
    code, out = _run(capsys, "hold", *_fields(), "--held-file", str(held))
    assert code == 1 and out["reason"] == "canon-held-not-marked"


# axis: a held line that reads as stays-out is refused at append too.
def test_held_go_word_refused_at_append(project, capsys, tmp_path):
    bad = _entry(9).replace("owner's words: none recorded", "owner's words: \"Merge #1810 now.\"")
    (tmp_path / "held.md").write_text(canon.HELD_MARKER + "\n" + bad + "\n")
    code, out = _run(capsys, "append", "--root", ".", "--lines-file", str(tmp_path / "held.md"))
    assert code == 1 and out["reason"] == "canon-stays-out"


def _conflict(capsys, project, tmp_path, *lines):
    """Append the lines as a held batch; the Canon file and .gitattributes must stay as they were."""
    attrs = os.path.join(os.path.dirname(project["path"]), ".gitattributes")

    def snap():
        return (open(project["path"], "rb").read(),
                os.path.exists(attrs) and open(attrs, "rb").read())

    before = snap()
    batch = tmp_path / "held.md"
    batch.write_text(canon.HELD_MARKER + "\n" + "".join(l + "\n" for l in lines))
    code, out = _run(capsys, "append", "--root", ".", "--lines-file", str(batch))
    assert snap() == before
    return code, out


# axis: a same-id line with different text refuses the whole batch and writes nothing.
def test_conflict_against_working_copy_refused(project, capsys, tmp_path):
    other = _entry(1).replace("A ruling.", "A different ruling.")
    code, out = _conflict(capsys, project, tmp_path, _entry(8), other)
    assert code == 1 and out["reason"] == "canon-id-conflict"
    assert "%s-abcd1234-1" % WRITTEN in out["detail"] and "owner decides" in out["detail"]


def test_conflict_against_default_copy_refused(project, capsys, tmp_path):
    other = _entry(3).replace("A ruling.", "A different ruling.")
    assert _entry(3) not in open(project["path"]).read()
    code, out = _conflict(capsys, project, tmp_path, other)
    assert code == 1 and out["reason"] == "canon-id-conflict"
    assert "%s-abcd1234-3" % WRITTEN in out["detail"]


def test_conflict_within_one_batch_refused(project, capsys, tmp_path):
    other = _entry(8).replace("A ruling.", "A different ruling.")
    code, out = _conflict(capsys, project, tmp_path, _entry(8), other)
    assert code == 1 and out["reason"] == "canon-id-conflict"
    assert "%s-abcd1234-8" % WRITTEN in out["detail"]


def test_identical_repeat_of_a_default_copy_line_is_skipped(project, capsys, tmp_path):
    code, out = _conflict(capsys, project, tmp_path, _entry(3))
    assert code == 0 and out["appended"] == [] and out["skipped"] == [_entry(3)]


# axis: the file shape and the union-merge attribute are created with the first entry.
def test_new_file_gets_shape_and_union_attribute(project, capsys):
    os.remove(project["path"])
    code, out = _run(capsys, "append", *_fields())
    assert code == 0
    assert open(project["path"]).read() == canon.HEADER + out["appended"][0] + "\n"
    attrs = os.path.join(os.path.dirname(project["path"]), ".gitattributes")
    assert open(attrs).read() == "canon.md merge=union\n"
    assert out["commitPaths"] == [project["path"], attrs]


def test_project_store_canon_is_never_held(project, capsys, monkeypatch):
    monkeypatch.setattr(definition_doc, "resolve_canon",
                        lambda root: dict(project, home="project-store", defaultRef=None))
    code, out = _run(capsys, "hold", *_fields())
    assert code == 1 and out["reason"] == "canon-store-never-held"


def test_ruling_record_quotes_the_owner_and_posts(capsys, tmp_path, monkeypatch):
    words = tmp_path / "w.txt"
    words.write_text("a - launch it now\nin the cloud\n")
    seen = {}

    def fake_run(cmd, capture_output, text):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "https://x/issues/695#issuecomment-1\n", "")

    monkeypatch.setattr(canon.subprocess, "run", fake_run)
    code, out = _run(capsys, "ruling-record", "--date", WRITTEN, "--time", "14:05",
                     "--words-file", str(words), "--context", "collector item 116", "--post",
                     "--repo", "o/r", "--collector", "695")
    assert code == 0 and out["permalink"] == "https://x/issues/695#issuecomment-1"
    assert out["body"].startswith(canon.RULING_MARKER + "\n")
    assert "2026-10-12 14:05 UTC" in out["body"]
    assert "> a - launch it now\n> in the cloud" in out["body"]
    assert seen["cmd"] == ["gh", "api", "repos/o/r/issues/695/comments", "-f",
                           "body=" + out["body"], "--jq", ".html_url"]


def test_ruling_record_needs_a_utc_time(capsys, tmp_path):
    words = tmp_path / "w.txt"
    words.write_text("yes")
    code, out = _run(capsys, "ruling-record", "--date", WRITTEN, "--time", "2pm",
                     "--words-file", str(words), "--context", "c")
    assert code == 1 and out["reason"] == "canon-bad-field"


def _bare_project(path):
    os.makedirs(os.path.join(path, "docs", "superheroes"))
    subprocess.run(["git", "init", "-q", "-b", "main", path], check=True)
    _git(path, "config", "user.email", "t@t")
    _git(path, "config", "user.name", "t")
    canon_path = os.path.join(path, "docs", "superheroes", "canon.md")
    with open(canon_path, "w") as fh:
        fh.write(canon.HEADER + _entry(1) + "\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "canon")
    return canon_path


# axis: the write goes to the Canon of the project --root names, through the real lookup.
def test_append_uses_the_real_lookup_for_the_named_root(tmp_path):
    a_canon, b_canon = _bare_project(str(tmp_path / "a")), _bare_project(str(tmp_path / "b"))
    before_a = open(a_canon).read()
    env = dict(os.environ, SUPERHEROES_STORE_ROOT=str(tmp_path / "store"))
    got = subprocess.run(
        [sys.executable, os.path.join(_LIB, "canon.py"), "append", "--root", str(tmp_path / "b"),
         *_fields()[2:]], cwd=str(tmp_path / "a"), env=env, capture_output=True, text=True)
    out = json.loads(got.stdout)
    assert got.returncode == 0 and os.path.realpath(out["path"]) == os.path.realpath(b_canon)
    assert os.path.realpath(out["gitRoot"]) == os.path.realpath(str(tmp_path / "b"))
    assert out["appended"][0] in open(b_canon).read().splitlines()
    assert open(a_canon).read() == before_a


# axis: an existing Canon is appended to, never reopened from the start, so its entries survive.
def test_existing_canon_is_opened_for_append_only(project, capsys, monkeypatch):
    modes = []
    real_open = open

    def spy(path, mode="r", *args, **kwargs):
        if os.path.abspath(str(path)) == project["path"]:
            modes.append(mode)
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", spy)
    before = real_open(project["path"]).read()
    code, out = _run(capsys, "append", *_fields())
    assert code == 0 and "w" not in modes and "a" in modes
    assert real_open(project["path"]).read() == before + out["appended"][0] + "\n"


def test_write_failure_is_a_structured_refusal(project, capsys, monkeypatch):
    def boom(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(canon, "_write", boom)
    code, out = _run(capsys, "append", *_fields())
    assert code == 1 and out["reason"] == "canon-write-failed" and "last line" in out["detail"]


def test_partial_entry_fences_further_writes(project, capsys):
    with open(project["path"], "a", encoding="utf-8") as fh:
        fh.write("- **2026-01-01-abcd1234-1** · 2026-01-01 · standing · A cut rul")
    before = open(project["path"]).read()
    code, out = _run(capsys, "append", *_fields())
    assert code == 1 and out["reason"] == "canon-partial-entry"
    assert open(project["path"]).read() == before


# axis: a held line is validated like a fresh entry: a cut or malformed line is refused before any
# byte is written.
@pytest.mark.parametrize("damage", [
    lambda l: l[:-len("here: s, time not recorded") + 1].rstrip() + " wher",
    lambda l: l.replace(" · where: s, time not recorded", ""),
    lambda l: l.replace("where: s, time not recorded", "where: "),
    lambda l: l.replace("owner's words: none recorded", "owner's words: "),
    lambda l: l.replace(" · standing · ", " · whenever · "),
    lambda l: l.replace(" · A ruling. · ", " ·  · "),
    lambda l: l.replace(" · owner's words", " · supersedes: x · cedes: y · owner's words"),
])
def test_malformed_held_line_refused_before_writing(project, capsys, tmp_path, damage):
    bad = damage(_entry(9))
    assert bad != _entry(9)
    (tmp_path / "held.md").write_text(canon.HELD_MARKER + "\n" + bad + "\n")
    before = open(project["path"], "rb").read()
    code, out = _run(capsys, "append", "--root", ".", "--lines-file", str(tmp_path / "held.md"))
    assert code == 1 and out["reason"] == "canon-bad-line"
    assert open(project["path"], "rb").read() == before


# axis: a write cut inside the entry id still fences further writes and leaves the bytes alone.
def test_partial_entry_cut_inside_the_id_fences_further_writes(project, capsys):
    with open(project["path"], "a", encoding="utf-8") as fh:
        fh.write("- **2026-10-12-abcd")
    before = open(project["path"], "rb").read()
    code, out = _run(capsys, "append", *_fields())
    assert code == 1 and out["reason"] == "canon-partial-entry"
    assert open(project["path"], "rb").read() == before


# axis: a drained batch is checked whole: a wrapped or indented entry is refused, not dropped.
@pytest.mark.parametrize("damage", [lambda l: l.replace("s, time", "s,\ntime"),
                                    lambda l: "  " + l])
def test_lines_file_with_damaged_entry_refused_before_writing(project, capsys, tmp_path, damage):
    batch = tmp_path / "batch.md"
    batch.write_text(_entry(8) + "\n" + damage(_entry(9)) + "\n")
    before = open(project["path"], "rb").read()
    code, out = _run(capsys, "append", "--root", ".", "--lines-file", str(batch))
    assert code == 1 and out["reason"] == "canon-bad-line"
    assert open(project["path"], "rb").read() == before


# axis: an unterminated final entry, even one cut inside its last field, fences further writes.
def test_entry_cut_inside_final_field_fences_further_writes(project, capsys):
    with open(project["path"], "a", encoding="utf-8") as fh:
        fh.write(_entry(5)[:-5])
    before = open(project["path"], "rb").read()
    code, out = _run(capsys, "append", *_fields())
    assert code == 1 and out["reason"] == "canon-partial-entry"
    assert open(project["path"], "rb").read() == before
