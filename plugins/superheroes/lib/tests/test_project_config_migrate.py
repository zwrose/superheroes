# plugins/superheroes/lib/tests/test_project_config_migrate.py
"""Configure item 13 moving into Canon: the migration, its fail-closed edges, and its invariants."""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_LIB = os.path.join(_REPO_ROOT, "plugins/superheroes/lib")


def _load(name):
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    path = os.path.join(_LIB, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PC = _load("project_config")
CM = _load("core_md")
MR = _load("mode_registry")
AC = _load("architect_config")

_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}

# Measured from this repo's own configuration with `project_config.py get --item materialConsequenceLine`.
_REAL_ITEM_13 = json.loads(r'''"The plugin default, plus this project's own examples. Tie-breaker, read first: material if the owner, reading the pull request at the word, would have wanted to know it before saying yes. Doubt is an owner call.\n\nMaterial: a change of a mechanism's fail direction; a new token or disposition in a hard shell; a change to what the sanitized view strips or delivers; any edit to a covenant hard line; any change to how approval, merging, releasing, or publishing works; a deviation from what the issue or spec says the change does, however small; a degradation that costs something promised, such as a skipped check or a downgraded or substituted seat; a change in what the work costs to run, whether model tier, seat count, or engine.\n\nCraft: a disclosed integration commit that closes a merge train's coverage-race red; a base update with no conflict; a check identifier or heading rename under the pin rule; a test fixture pinned to a scratch path; formatting and lint; typo and comment fixes; a test that pins existing behavior; a same-major dependency bump that CI proves.\n\nThe owner adds examples at any walk."''')

_TWO_RULINGS = "First ruling, kept whole.\n\nSecond ruling,\nspread over two lines."
_DATE = "2026-10-05"
_SESSION = "abcdef12"
_REL = "docs/superheroes/canon.md"
_MARKER = {"canon": "standing-rulings", "migratedOn": _DATE}
_ENTRY_LINE = re.compile(
    r"^- \*\*2026-10-05-abcdef12-\d+\*\* · 2026-10-05 · standing · .+ · owner's words: none "
    r"recorded · where: migrated from configure item 13 on 2026-10-05 "
    r"\(original session unknown\), time not recorded$")
_UNSET = object()


@pytest.fixture(autouse=True)
def _git_identity(monkeypatch):
    # The code under test never passes -c user.*; its own commit takes its identity from here.
    for key in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(key, "t")
    for key in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(key, "t@t")


def _git(repo, *args, check=True):
    return subprocess.run(
        ["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=check, capture_output=True, text=True)


def _out(repo, *args):
    return _git(repo, *args).stdout.strip()


class World:
    def __init__(self, repo, store, origin):
        self.repo = repo
        self.store = store
        self.origin = origin
        self.canon = os.path.join(repo, *_REL.split("/"))

    def migrate(self, **kw):
        kw.setdefault("session", _SESSION)
        kw.setdefault("date", _DATE)
        return PC.migrate_material_line(self.repo, root=self.store, **kw)

    def item13(self):
        return PC.get_item(self.repo, "materialConsequenceLine", root=self.store)

    def core_bytes(self):
        return open(CM.core_path(self.repo, self.store), "rb").read()

    def head(self):
        return _out(self.repo, "rev-parse", "HEAD")

    def head_canon(self):
        return _out(self.repo, "show", "HEAD:%s" % _REL) + "\n"

    def commit_files(self, ref="HEAD"):
        return _out(self.repo, "show", "--name-only", "--format=", ref).splitlines()

    def commit_canon(self, text):
        os.makedirs(os.path.dirname(self.canon), exist_ok=True)
        with open(self.canon, "w", encoding="utf-8") as fh:
            fh.write(text)
        _git(self.repo, "add", "--", _REL)
        _git(self.repo, "commit", "-q", "-m", "seed canon", "--", _REL)


def _world(tmp_path, raw=_TWO_RULINGS, *, origin=True, visibility="committed", profile=True,
           set_head=True):
    repo = os.path.realpath(str(tmp_path / "repo"))
    store = os.path.realpath(str(tmp_path)) + "/store"
    os.makedirs(repo)
    _git(repo, "init", "-q", "-b", "main")
    with open(os.path.join(repo, "README.md"), "w") as fh:
        fh.write("x\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "first")
    bare = os.path.join(os.path.realpath(str(tmp_path)), "origin.git")
    if origin:
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", bare], check=True)
        _git(repo, "remote", "add", "origin", bare)
        _git(repo, "push", "-q", "-u", "origin", "main")
        if set_head:
            _git(repo, "remote", "set-head", "origin", "--auto")
    MR.write_registry(repo, MR.IN_REPO, "rk", root=store)
    AC.write_policy(repo, {"location": "docs/superheroes", "visibility": visibility,
                           "confirmed": True}, root=store)
    if profile:
        CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
        if raw is not _UNSET and raw is not None:
            assert PC.set_item(repo, "materialConsequenceLine", raw, root=store)["action"] == "written"
    return World(repo, store, bare)


def _shape(result):
    assert set(result) == {"action", "reason", "detail", "entries", "skipped", "canonPath",
                           "canonHome", "commit", "fetch", "sanitized"}
    return result


def _entry_lines(text):
    return [ln for ln in text.splitlines() if ln.startswith("- **")]


# --- E1-E3: the profile gate ---

def test_e1_profile_absent_refused(tmp_path):
    w = _world(tmp_path, profile=False)
    got = _shape(w.migrate())
    assert (got["action"], got["reason"]) == ("refused", "profile-absent")
    assert not os.path.exists(w.canon)


def test_e2_profile_unparseable_refused(tmp_path):
    w = _world(tmp_path)
    open(CM.core_path(w.repo, w.store), "w").write("not core\n")
    got = _shape(w.migrate())
    assert (got["action"], got["reason"]) == ("refused", "profile-unparseable")
    assert not os.path.exists(w.canon)


def test_e3_schema_behind_refused(tmp_path):
    w = _world(tmp_path)
    path = CM.core_path(w.repo, w.store)
    text = open(path).read()
    text = text.replace("schemaVersion=%d" % CM.SCHEMA_VERSION, "schemaVersion=%d" % (CM.SCHEMA_VERSION + 1))
    text = text.replace('"schemaVersion": %d' % CM.SCHEMA_VERSION, '"schemaVersion": %d' % (CM.SCHEMA_VERSION + 1))
    open(path, "w").write(text)
    assert PC.read(w.repo, root=w.store)["behind"] is True
    before = w.core_bytes()
    got = _shape(w.migrate())
    assert (got["action"], got["reason"]) == ("refused", "behind")
    assert w.core_bytes() == before
    assert not os.path.exists(w.canon)


# --- E4-E8: the item-13 and input gates ---

def test_e4_already_adopted_touches_no_canon(tmp_path, monkeypatch):
    w = _world(tmp_path, raw=_UNSET)
    CM.write_project_config_item(w.repo, "materialConsequenceLine", dict(_MARKER), root=w.store)

    def _no_git(*a, **k):
        raise AssertionError("an adopted project must not reach git")

    monkeypatch.setattr(PC, "_git_run", _no_git)
    got = _shape(w.migrate())
    assert got["action"] == "already-adopted"
    assert got["reason"] is None
    assert (got["entries"], got["skipped"], got["canonPath"], got["commit"]) == ([], [], None, None)
    assert got["fetch"] == "not-needed"


@pytest.mark.parametrize("bad", [
    {"canon": "standing-rulings"}, ["a ruling"], 7, True,
], ids=["dict", "list", "number", "bool"])
def test_e5_malformed_item_13_refused(tmp_path, bad):
    w = _world(tmp_path, raw=_UNSET)
    CM.write_project_config_item(w.repo, "materialConsequenceLine", bad, root=w.store)
    before = w.core_bytes()
    got = _shape(w.migrate())
    assert (got["action"], got["reason"]) == ("refused", "malformed-value")
    assert w.core_bytes() == before
    assert not os.path.exists(w.canon)


@pytest.mark.parametrize("raw", [None, "", "  \n \n"], ids=["absent", "empty", "blank"])
def test_e6_absent_or_blank_item_13_writes_marker_and_touches_no_canon(tmp_path, raw):
    w = _world(tmp_path, raw=raw)
    head = w.head()
    got = _shape(w.migrate())
    assert got["action"] == "migrated"
    assert (got["entries"], got["skipped"], got["canonPath"], got["commit"]) == ([], [], None, None)
    assert got["fetch"] == "not-needed"
    assert w.item13()["raw"] == _MARKER
    assert not os.path.exists(w.canon)
    assert w.head() == head


@pytest.mark.parametrize("session", ["bad!", "short", "", "zzzzzz!z"])
def test_e7_malformed_session_refused(tmp_path, session):
    w = _world(tmp_path)
    before = w.core_bytes()
    got = _shape(w.migrate(session=session))
    assert (got["action"], got["reason"]) == ("refused", "session-id-malformed")
    assert w.core_bytes() == before
    assert not os.path.exists(w.canon)


@pytest.mark.parametrize("date", ["2026-13-45", "20261005", "yesterday", ""])
def test_e8_malformed_date_refused(tmp_path, date):
    w = _world(tmp_path)
    before = w.core_bytes()
    got = _shape(w.migrate(date=date))
    assert (got["action"], got["reason"]) == ("refused", "date-malformed")
    assert w.core_bytes() == before
    assert not os.path.exists(w.canon)


def test_session_is_lowercased_stripped_and_cut_to_eight(tmp_path):
    w = _world(tmp_path)
    got = w.migrate(session="  ABCDEF12-3456-7890  ")
    assert got["entries"] == ["2026-10-05-abcdef12-1", "2026-10-05-abcdef12-2"]


def test_session_and_date_default_when_omitted(tmp_path):
    w = _world(tmp_path)
    got = PC.migrate_material_line(w.repo, root=w.store)
    assert got["action"] == "migrated"
    assert re.match(r"^\d{4}-\d\d-\d\d-[0-9a-f]{8}-1$", got["entries"][0])
    assert w.item13()["raw"]["migratedOn"] == got["entries"][0][:10]


# --- E9-E12: the Canon lookup ---

def test_e9_no_origin_remote_reports_no_origin_and_migrates(tmp_path):
    w = _world(tmp_path, origin=False)
    got = _shape(w.migrate())
    assert got["action"] == "migrated"
    assert got["fetch"] == "no-origin"
    assert got["commit"] == w.head()
    assert len(got["entries"]) == 2


def test_e10_failed_fetch_is_reported_not_fatal(tmp_path):
    w = _world(tmp_path)
    _git(w.repo, "remote", "set-url", "origin", os.path.join(str(tmp_path), "missing.git"))
    got = _shape(w.migrate())
    assert got["action"] == "migrated"
    assert got["fetch"].startswith("failed: ")
    assert len(got["fetch"]) > len("failed: ")
    assert len(got["entries"]) == 2


def test_fetch_ok_when_origin_reachable(tmp_path):
    w = _world(tmp_path)
    assert w.migrate()["fetch"] == "ok"


def test_e11_canon_lookup_raising_is_refused_and_writes_nothing(tmp_path):
    w = _world(tmp_path)
    _git(w.repo, "remote", "set-head", "origin", "-d")
    before = w.core_bytes()
    got = _shape(w.migrate())
    assert (got["action"], got["reason"]) == ("refused", "canon-lookup-refused")
    assert "origin/HEAD" in got["detail"]
    assert w.core_bytes() == before
    assert not os.path.exists(w.canon)


def test_e12_git_root_not_a_repo_refused_and_never_inits(tmp_path):
    w = _world(tmp_path, visibility="gitignored", origin=False)
    store_dir = MR.project_store_dir(w.repo, w.store)
    shutil.rmtree(os.path.join(store_dir, ".git"))
    before = w.core_bytes()
    got = _shape(w.migrate())
    assert (got["action"], got["reason"]) == ("refused", "canon-git-root-not-a-repo")
    assert got["canonHome"] == "project-store"
    assert not os.path.exists(os.path.join(store_dir, ".git"))
    assert w.core_bytes() == before


# --- E13-E14: the clean baseline ---

_SEED = "# Canon\n\nheader\n\n## Entries\n\n- **2026-09-01-11111111-1** · 2026-09-01 · standing · Seeded. · owner's words: none recorded · where: s, time not recorded\n"


# axis: an unstaged edit to Canon is never committed along with the migration — wo_a_1618_clean-baseline
def test_e13_unstaged_edit_to_canon_refused_canon_dirty(tmp_path):
    w = _world(tmp_path)
    w.commit_canon(_SEED)
    with open(w.canon, "a") as fh:
        fh.write("- **2026-09-02-22222222-1** · 2026-09-02 · standing · Unsaved. · owner's words: none recorded · where: s, time not recorded\n")
    head, canon_before, core_before = w.head(), open(w.canon, "rb").read(), w.core_bytes()
    got = _shape(w.migrate())
    assert (got["action"], got["reason"]) == ("refused", "canon-dirty")
    assert "docs/superheroes/canon.md" in got["detail"]
    assert (w.head(), open(w.canon, "rb").read(), w.core_bytes()) == (head, canon_before, core_before)


def test_e13_staged_edit_to_canon_refused_canon_dirty(tmp_path):
    w = _world(tmp_path)
    w.commit_canon(_SEED)
    with open(w.canon, "a") as fh:
        fh.write("staged line\n")
    _git(w.repo, "add", "--", _REL)
    head = w.head()
    got = _shape(w.migrate())
    assert (got["action"], got["reason"]) == ("refused", "canon-dirty")
    assert w.head() == head


def test_e13_existing_untracked_canon_refused_canon_dirty(tmp_path):
    w = _world(tmp_path)
    os.makedirs(os.path.dirname(w.canon))
    open(w.canon, "w").write(_SEED)
    head = w.head()
    got = _shape(w.migrate())
    assert (got["action"], got["reason"]) == ("refused", "canon-dirty")
    assert "??" in got["detail"]
    assert open(w.canon).read() == _SEED
    assert w.head() == head


def test_e14_dirty_gitattributes_refused_canon_dirty(tmp_path):
    w = _world(tmp_path)
    attrs = os.path.join(os.path.dirname(w.canon), ".gitattributes")
    os.makedirs(os.path.dirname(attrs))
    open(attrs, "w").write("*.png binary\n")
    head = w.head()
    got = _shape(w.migrate())
    assert (got["action"], got["reason"]) == ("refused", "canon-dirty")
    assert ".gitattributes" in got["detail"]
    assert open(attrs).read() == "*.png binary\n"
    assert not os.path.exists(w.canon)
    assert w.head() == head


# --- E15: the default-branch probe ---

def test_e15_default_branch_probe_failure_refused(tmp_path, monkeypatch):
    w = _world(tmp_path)
    real = PC._git_run

    def _probe_fails(root, reason, *args, **kw):
        if args[:2] == ("ls-tree", "origin/main"):
            return subprocess.CompletedProcess(args, 128, "", "fatal: boom\n")
        return real(root, reason, *args, **kw)

    monkeypatch.setattr(PC, "_git_run", _probe_fails)
    before = w.core_bytes()
    got = _shape(w.migrate())
    assert (got["action"], got["reason"]) == ("refused", "canon-default-probe-failed")
    assert got["detail"] == "fatal: boom"
    assert w.core_bytes() == before
    assert not os.path.exists(w.canon)


def test_default_branch_canon_is_read_for_ids_and_dedupe(tmp_path):
    w = _world(tmp_path)
    line = ("- **2026-10-05-abcdef12-1** · 2026-10-05 · standing · First ruling, kept whole. · "
            "owner's words: none recorded · where: migrated from configure item 13 on 2026-10-05 "
            "(original session unknown), time not recorded\n")
    w.commit_canon("# Canon\n\nheader\n\n## Entries\n\n" + line)
    _git(w.repo, "push", "-q", "origin", "main")
    _git(w.repo, "fetch", "-q", "origin")
    _git(w.repo, "checkout", "-q", "-b", "work", "HEAD~1")
    assert not os.path.exists(w.canon)
    got = _shape(w.migrate())
    assert got["action"] == "migrated"
    assert got["skipped"] == ["2026-10-05-abcdef12-1"]
    assert got["entries"] == ["2026-10-05-abcdef12-2"]
    text = open(w.canon).read()
    assert text.startswith("# Canon\n\n")
    assert len(_entry_lines(text)) == 1


# --- E16-E17: the committed-only dedupe and the never-commit-empty branch ---

# axis: with every ruling already committed the migration makes no commit and leaves other staged work alone — wo_a_1618_never-commit-empty
def test_e16_every_ruling_committed_makes_no_commit(tmp_path):
    w = _world(tmp_path)
    first = _shape(w.migrate())
    assert first["action"] == "migrated"
    commit = w.head()
    CM.write_project_config_item(w.repo, "materialConsequenceLine", _TWO_RULINGS, root=w.store)
    open(os.path.join(w.repo, "other.txt"), "w").write("unrelated\n")
    _git(w.repo, "add", "other.txt")
    canon_before = open(w.canon, "rb").read()
    got = _shape(w.migrate())
    assert got["action"] == "migrated"
    assert got["entries"] == []
    assert got["skipped"] == first["entries"]
    assert got["commit"] is None
    assert w.head() == commit
    assert open(w.canon, "rb").read() == canon_before
    assert _out(w.repo, "diff", "--cached", "--name-only") == "other.txt"
    assert w.item13()["raw"] == _MARKER


def test_e17_some_committed_appends_only_the_rest(tmp_path):
    w = _world(tmp_path, raw="First ruling, kept whole.")
    first = _shape(w.migrate())
    assert first["entries"] == ["2026-10-05-abcdef12-1"]
    CM.write_project_config_item(w.repo, "materialConsequenceLine", _TWO_RULINGS, root=w.store)
    before = open(w.canon, "rb").read()
    got = _shape(w.migrate())
    assert got["action"] == "migrated"
    assert got["skipped"] == ["2026-10-05-abcdef12-1"]
    assert got["entries"] == ["2026-10-05-abcdef12-2"]
    after = open(w.canon, "rb").read()
    assert after.startswith(before)
    assert after[len(before):].decode().count("\n") == 1
    assert "Second ruling, spread over two lines." in after.decode()
    assert w.head_canon() == after.decode()


# axis: an entry that exists only in an ignored on-disk Canon is not "already committed" — wo_a_1618_committed-only-dedupe
def test_working_copy_only_match_is_not_already_committed(tmp_path):
    w = _world(tmp_path, raw="First ruling, kept whole.")
    os.makedirs(os.path.dirname(w.canon))
    line = ("- **2026-10-05-abcdef12-1** · 2026-10-05 · standing · First ruling, kept whole. · "
            "owner's words: none recorded · where: migrated from configure item 13 on 2026-10-05 "
            "(original session unknown), time not recorded\n")
    open(w.canon, "w").write("# Canon\n\n## Entries\n\n" + line)
    with open(os.path.join(w.repo, ".git", "info", "exclude"), "a") as fh:
        fh.write("docs/superheroes/canon.md\n")
    assert _out(w.repo, "status", "--porcelain", "--untracked-files=all", "--", _REL) == ""
    before = w.core_bytes()
    got = _shape(w.migrate())
    assert got["action"] == "refused"
    assert got["reason"] == "canon-commit-failed"
    assert got["skipped"] == []
    assert w.core_bytes() == before
    assert w.item13()["raw"] == "First ruling, kept whole."


# --- E18-E19: the commit ---

def test_e18_commit_failure_refused_and_item_13_unchanged(tmp_path):
    w = _world(tmp_path)
    hook = os.path.join(w.repo, ".git", "hooks", "pre-commit")
    open(hook, "w").write("#!/bin/sh\necho rejected by hook >&2\nexit 1\n")
    os.chmod(hook, 0o755)
    head = w.head()
    got = _shape(w.migrate())
    assert (got["action"], got["reason"]) == ("refused", "canon-commit-failed")
    assert "rejected by hook" in got["detail"]
    assert got["commit"] is None
    assert w.head() == head
    assert w.item13()["raw"] == _TWO_RULINGS


# axis: a commit whose Canon does not extend the prior copy is refused — wo_a_1618_prefix-check
def test_e19_post_commit_prefix_check_refuses(tmp_path, monkeypatch):
    w = _world(tmp_path)
    w.commit_canon(_SEED)
    real = PC._git_run

    def _rewritten(root, reason, *args, **kw):
        got = real(root, reason, *args, **kw)
        if args[:1] == ("show",) and args[1] == "HEAD:%s" % _REL and _out(root, "rev-list", "--count", "HEAD") == "3":
            return subprocess.CompletedProcess(args, 0, "# Rewritten\n" + got.stdout[1:], "")
        return got

    monkeypatch.setattr(PC, "_git_run", _rewritten)
    got = _shape(w.migrate())
    assert (got["action"], got["reason"]) == ("refused", "canon-commit-failed")
    assert got["commit"] is None
    assert len(got["entries"]) == 2
    assert w.item13()["raw"] == _TWO_RULINGS


# --- E20-E21: the marker write ---

# axis: the marker never overwrites an item 13 that changed after the snapshot — wo_a_1618_cas-compare
def test_e20_item_13_changed_between_read_and_marker_write(tmp_path, monkeypatch):
    w = _world(tmp_path)
    real = PC.core_md.write_project_config_item_if

    def _race(cwd, slug, value, *, expected, root=None):
        PC.core_md.write_project_config_item(cwd, slug, "an example added at the walk", root=root)
        return real(cwd, slug, value, expected=expected, root=root)

    monkeypatch.setattr(PC.core_md, "write_project_config_item_if", _race)
    got = _shape(w.migrate())
    assert (got["action"], got["reason"]) == ("refused", "material-line-changed-during-migration")
    assert len(got["entries"]) == 2
    assert got["commit"] == w.head()
    assert w.item13()["raw"] == "an example added at the walk"
    assert len(_entry_lines(w.head_canon())) == 2


def test_e21_marker_writer_deferring_is_refused(tmp_path, monkeypatch):
    w = _world(tmp_path)
    monkeypatch.setattr(
        PC.core_md, "write_project_config_item_if",
        lambda *a, **k: {"action": "deferred", "reason": "lock-contended"})
    got = _shape(w.migrate())
    assert (got["action"], got["reason"], got["detail"]) == (
        "refused", "marker-write-failed", "lock-contended")
    assert len(got["entries"]) == 2
    assert w.item13()["raw"] == _TWO_RULINGS


def test_marker_failed_then_rerun_skips_the_committed_entries(tmp_path, monkeypatch):
    w = _world(tmp_path)
    real = PC.core_md.write_project_config_item_if
    calls = []

    def _once(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            return {"action": "deferred"}
        return real(*a, **k)

    monkeypatch.setattr(PC.core_md, "write_project_config_item_if", _once)
    first = _shape(w.migrate())
    assert (first["action"], first["reason"]) == ("refused", "marker-write-failed")
    assert len(first["entries"]) == 2
    commit = w.head()
    assert first["commit"] == commit
    second = _shape(w.migrate(session="99999999"))
    assert second["action"] == "migrated"
    assert second["entries"] == []
    assert second["skipped"] == first["entries"]
    assert second["commit"] is None
    assert w.head() == commit
    assert w.item13()["raw"] == _MARKER


# --- E22-E24 and the shape of what is written ---

def test_e22_a_ruling_containing_the_field_separator_is_sanitized(tmp_path):
    w = _world(tmp_path, raw="Alpha · Beta · · Gamma\n\nPlain ruling.")
    got = _shape(w.migrate())
    assert got["action"] == "migrated"
    assert got["sanitized"] is True
    lines = _entry_lines(w.head_canon())
    assert " · Alpha; Beta; ; Gamma · " in lines[0]
    for line in lines:
        assert line.count(" · ") == 5
        assert _ENTRY_LINE.match(line)


def test_sanitized_false_when_nothing_replaced(tmp_path):
    w = _world(tmp_path)
    assert w.migrate()["sanitized"] is False


def test_e23_unrelated_staged_file_stays_staged_and_uncommitted(tmp_path):
    w = _world(tmp_path)
    open(os.path.join(w.repo, "other.txt"), "w").write("unrelated\n")
    _git(w.repo, "add", "other.txt")
    got = _shape(w.migrate())
    assert got["action"] == "migrated"
    assert sorted(w.commit_files()) == ["docs/superheroes/.gitattributes", _REL]
    assert _out(w.repo, "diff", "--cached", "--name-only") == "other.txt"


def test_e24_store_home_has_no_gitattributes_and_commits_to_the_store_repo(tmp_path):
    w = _world(tmp_path, visibility="gitignored")
    store_dir = MR.project_store_dir(w.repo, w.store)
    got = _shape(w.migrate())
    assert got["action"] == "migrated"
    assert got["canonHome"] == "project-store"
    canon = os.path.join(store_dir, "docs", "canon.md")
    assert got["canonPath"] == canon
    assert not os.path.exists(os.path.join(store_dir, "docs", ".gitattributes"))
    assert _out(store_dir, "show", "--name-only", "--format=", "HEAD").splitlines() == ["docs/canon.md"]
    assert got["commit"] == _out(store_dir, "rev-parse", "HEAD")
    assert len(_entry_lines(open(canon).read())) == 2
    assert not os.path.exists(w.canon)


def test_created_canon_has_the_file_shape_and_the_header_from_this_repos_canon(tmp_path):
    w = _world(tmp_path)
    assert w.migrate()["action"] == "migrated"
    repo_canon = open(os.path.join(_REPO_ROOT, "docs", "superheroes", "canon.md")).read().splitlines()
    header = "\n".join(repo_canon[2:5])
    assert PC._CANON_HEADER == header
    text = open(w.canon).read()
    assert text.startswith("# Canon\n\n%s\n\n## Entries\n\n- **" % header)
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert open(os.path.join(os.path.dirname(w.canon), ".gitattributes")).read() == "canon.md merge=union\n"
    assert sorted(w.commit_files()) == ["docs/superheroes/.gitattributes", _REL]
    assert _out(w.repo, "log", "-1", "--format=%s") == "docs: record configure item 13 in Canon as standing rulings"


def test_gitattributes_line_appended_when_the_file_lacks_a_trailing_newline(tmp_path):
    w = _world(tmp_path)
    attrs = os.path.join(os.path.dirname(w.canon), ".gitattributes")
    os.makedirs(os.path.dirname(attrs))
    open(attrs, "w").write("*.png binary")
    _git(w.repo, "add", "--", "docs/superheroes/.gitattributes")
    _git(w.repo, "commit", "-q", "-m", "attrs", "--", "docs/superheroes/.gitattributes")
    assert w.migrate()["action"] == "migrated"
    assert open(attrs).read() == "*.png binary\ncanon.md merge=union\n"


def test_existing_gitattributes_line_is_left_alone(tmp_path):
    w = _world(tmp_path)
    attrs = os.path.join(os.path.dirname(w.canon), ".gitattributes")
    os.makedirs(os.path.dirname(attrs))
    open(attrs, "w").write("canon.md merge=union\n")
    _git(w.repo, "add", "--", "docs/superheroes/.gitattributes")
    _git(w.repo, "commit", "-q", "-m", "attrs", "--", "docs/superheroes/.gitattributes")
    assert w.migrate()["action"] == "migrated"
    assert open(attrs).read() == "canon.md merge=union\n"
    assert w.commit_files() == [_REL]


def test_entry_lines_have_the_exact_shape(tmp_path):
    w = _world(tmp_path)
    got = _shape(w.migrate())
    lines = _entry_lines(w.head_canon())
    assert len(lines) == 2
    for line in lines:
        assert _ENTRY_LINE.match(line), line
    assert lines[0] == (
        "- **2026-10-05-abcdef12-1** · 2026-10-05 · standing · First ruling, kept whole. · "
        "owner's words: none recorded · where: migrated from configure item 13 on 2026-10-05 "
        "(original session unknown), time not recorded")
    assert "Second ruling, spread over two lines." in lines[1]
    assert got["entries"] == ["2026-10-05-abcdef12-1", "2026-10-05-abcdef12-2"]
    assert got["canonHome"] == "repo"
    assert got["canonPath"] == w.canon
    assert got["commit"] == w.head()
    assert got["reason"] is None and got["detail"] is None
    assert w.item13()["raw"] == _MARKER


def test_ids_continue_the_sequence_for_the_same_session_prefix_and_date(tmp_path):
    w = _world(tmp_path)
    seeded = ("- **2026-10-05-abcdef12-1** · 2026-10-05 · standing · Another session's call. · "
              "owner's words: none recorded · where: s, time not recorded\n"
              "- **2026-10-05-abcdef12-4** · 2026-10-05 · standing · A later call. · "
              "owner's words: none recorded · where: s, time not recorded\n"
              "- **2026-10-04-abcdef12-9** · 2026-10-04 · standing · Another day. · "
              "owner's words: none recorded · where: s, time not recorded\n")
    w.commit_canon("# Canon\n\nheader\n\n## Entries\n\n" + seeded)
    got = _shape(w.migrate())
    assert got["entries"] == ["2026-10-05-abcdef12-5", "2026-10-05-abcdef12-6"]
    ids = [re.match(r"^- \*\*(.+?)\*\*", ln).group(1) for ln in _entry_lines(w.head_canon())]
    assert len(ids) == len(set(ids))


def test_appended_to_a_file_without_a_trailing_newline_never_rewrites_earlier_bytes(tmp_path):
    w = _world(tmp_path)
    seed = "# Canon\n\nheader\n\n## Entries\n\n- **2026-09-01-11111111-1** · 2026-09-01 · standing · Seeded. · owner's words: none recorded · where: s, time not recorded"
    w.commit_canon(seed)
    got = _shape(w.migrate())
    assert got["action"] == "migrated"
    new = w.head_canon()
    assert new.startswith(seed + "\n- **2026-10-05-abcdef12-1**")


def test_run_twice_second_run_is_already_adopted_and_canon_unchanged(tmp_path):
    w = _world(tmp_path)
    first = _shape(w.migrate())
    assert first["action"] == "migrated"
    commit, canon = w.head(), open(w.canon, "rb").read()
    second = _shape(w.migrate())
    assert second["action"] == "already-adopted"
    assert second["entries"] == []
    assert w.head() == commit
    assert open(w.canon, "rb").read() == canon


def test_this_repos_real_item_13_text_produces_exactly_four_entries(tmp_path):
    w = _world(tmp_path, raw=_REAL_ITEM_13)
    got = _shape(w.migrate())
    assert got["action"] == "migrated"
    assert len(got["entries"]) == 4
    lines = _entry_lines(w.head_canon())
    assert len(lines) == 4
    assert " · The plugin default, plus this project's own examples." in lines[0]
    assert " · Material: a change of a mechanism's fail direction;" in lines[1]
    assert " · Craft: a disclosed integration commit" in lines[2]
    assert " · The owner adds examples at any walk. · " in lines[3]
    for line in lines:
        assert _ENTRY_LINE.match(line), line
    assert got["sanitized"] is False


def test_migration_never_changes_an_existing_canon_line(tmp_path):
    w = _world(tmp_path)
    w.commit_canon(_SEED)
    before = w.head_canon()
    assert w.migrate()["action"] == "migrated"
    after = w.head_canon()
    assert after.startswith(before)
    assert after[:len(before)] == before


# --- the CLI verb ---

def test_cli_verb_prints_one_json_object_and_exits_zero(tmp_path, capsys):
    w = _world(tmp_path)
    rc = PC.main(["migrate-material-line", "--cwd", w.repo, "--root", w.store,
                  "--session", _SESSION, "--date", _DATE])
    assert rc == 0
    got = _shape(json.loads(capsys.readouterr().out))
    assert got["action"] == "migrated"
    assert got["entries"] == ["2026-10-05-abcdef12-1", "2026-10-05-abcdef12-2"]


def test_cli_verb_exits_zero_on_a_refusal(tmp_path, capsys):
    w = _world(tmp_path)
    rc = PC.main(["migrate-material-line", "--cwd", w.repo, "--root", w.store,
                  "--session", "bad!", "--date", _DATE])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["reason"] == "session-id-malformed"


# --- the compare-and-swap writer ---

def test_cas_writer_refuses_when_the_stored_value_differs(tmp_path):
    w = _world(tmp_path, raw="mine")
    before = w.core_bytes()
    got = CM.write_project_config_item_if(
        w.repo, "materialConsequenceLine", dict(_MARKER), expected="not mine", root=w.store)
    assert got == {"action": "refused", "reason": "item-changed", "observed": "mine"}
    assert w.core_bytes() == before


def test_cas_writer_writes_when_the_stored_value_matches_and_absent_equals_none(tmp_path):
    w = _world(tmp_path, raw=_UNSET)
    got = CM.write_project_config_item_if(
        w.repo, "materialConsequenceLine", dict(_MARKER), expected=None, root=w.store)
    assert got["action"] == "written"
    assert w.item13()["raw"] == _MARKER


def test_plain_item_writer_is_unchanged_without_expected(tmp_path):
    w = _world(tmp_path, raw="mine")
    got = CM.write_project_config_item(w.repo, "materialConsequenceLine", "yours", root=w.store)
    assert got["action"] == "written"
    assert w.item13()["raw"] == "yours"
