"""#2587 WO-1 - the leftover-settings detector: find, retire, restore.

Every repository is a real `git init` repository under tmp_path (never committed to); every store
root is under tmp_path and passed explicitly (the registry store root from the conftest fixture, the
two legacy store roots as `review_root` and `test_pilot_root`). A "leftover" is simply a file in the
working tree or in a store directory. Nothing here touches a real home path.

Bite-proof record: wo1_2587_leftover_settings
"""
import datetime
import hashlib
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import calibration_resolve  # noqa: E402
import core_md as cm  # noqa: E402
import leftover_settings as ls  # noqa: E402
import mode_registry as mr  # noqa: E402
import review_store  # noqa: E402
import store  # noqa: E402
import store_core  # noqa: E402

ORIGIN = "https://github.com/acme/corner-shop.git"
NOW = datetime.datetime(2026, 10, 10, 12, 0, 0, tzinfo=datetime.timezone.utc)
STAMP = "20261010T120000Z"

_CORE = cm.render_core(
    {"verifyCommand": "npm test", "stackTags": [], "threatModel": "t", "patterns": ""},
    "confirmed", "2026-01-01", "2026-01-01")
_EMPTY_CORE = cm.render_core({}, "confirmed", "2026-01-01", "2026-01-01")
_PILOT = "## Config\n```json test-pilot-config\n{}\n```\n"
_EMPTY_DIGEST = hashlib.sha256(b"").hexdigest()


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _repo(tmp_path, name="repo", remote=ORIGIN):
    path = tmp_path / name
    path.mkdir()
    _git(path, "init", "-q")
    if remote:
        _git(path, "remote", "add", "origin", remote)
    return str(path)


def _put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


class W:
    """One project: its repo, its three store roots and the path spellers."""

    def __init__(self, tmp_path, root):
        self.tmp = tmp_path
        self.cwd = _repo(tmp_path)
        self.repo = os.path.realpath(self.cwd)
        self.root = root
        self.rr = str(tmp_path / "review-store")
        self.tr = str(tmp_path / "tp-store")

    def register(self, mode):
        rec = mr.write_registry(
            self.cwd, mode, store_core.derive_identifiers(self.cwd)["remote_hash"], root=self.root)
        assert rec is not None and rec["storageMode"] == mode
        return rec

    def d_in(self, name):
        return os.path.join(self.repo, ".claude", "superheroes", name)

    def d_gl(self, name):
        return os.path.join(mr.project_store_dir(self.cwd, self.root), "config", name)

    def inrepo(self, *rel):
        return os.path.join(self.repo, ".claude", *rel)

    def entry(self, legacy_root):
        """A legacy store entry that resolve_global finds; returns its directory."""
        ident = store_core.derive_identifiers(self.cwd)
        entry_dir = os.path.join(legacy_root, "entries", ident["gitdir_hash"])
        os.makedirs(entry_dir, exist_ok=True)
        store_core.write_keys_json(entry_dir, ident)
        store_core.write_pointer(legacy_root, ident["gitdir_hash"], ident["gitdir_hash"])
        if ident["remote_hash"]:
            store_core.write_pointer(legacy_root, ident["remote_hash"], ident["gitdir_hash"])
        return entry_dir

    def find(self):
        return ls.find(self.cwd, self.root, review_root=self.rr, test_pilot_root=self.tr)

    def paths(self):
        return [f["path"] for f in self.find()["files"]]

    def retire(self, digest, **kw):
        kw.setdefault("owner_authorized", True)
        return ls.retire(self.cwd, list_digest=digest, root=self.root, review_root=self.rr,
                         test_pilot_root=self.tr, now=NOW, **kw)

    def store_dir(self):
        return mr.project_store_dir(self.cwd, self.root)


@pytest.fixture
def w(tmp_path, isolated_default_store_root):
    return W(tmp_path, os.path.realpath(isolated_default_store_root))


def _everything_left_behind(w):
    """Registry global; the selected copies on the global side, five stale copies in the repo."""
    w.register(mr.GLOBAL)
    _put(w.d_gl("core.md"), _CORE)
    _put(w.d_gl("review-crew.md"), "## Focus hints\n- global\n")
    _put(w.d_gl("test-pilot.md"), _PILOT)
    _put(w.d_gl("review-decisions.json"), '{"global": true}\n')
    left = [
        _put(w.d_in("core.md"), _CORE + "\n<!-- stale in-repo core -->\n"),
        _put(w.d_in("review-crew.md"), "## Focus hints\n- stale\n"),
        _put(w.inrepo("review-profile.md"), "## Threat model\nold profile\n"),
        _put(w.inrepo("test-pilot", "profile.md"), _PILOT + "stale\n"),
        _put(w.inrepo("review-decisions.json"), '{"stale": true}\n'),
    ]
    return sorted(left)


# --- 1. global, everything left behind -----------------------------------------------------------

def test_global_everything_left_behind(w):
    # axis: a recorded global project lists exactly the five stale in-repo copies and the notice names each
    left = _everything_left_behind(w)
    result = w.find()
    assert result["mode"] == mr.GLOBAL
    assert [f["path"] for f in result["files"]] == left
    by_path = {f["path"]: f for f in result["files"]}
    assert by_path[w.d_in("core.md")]["family"] == "core"
    assert by_path[w.d_in("core.md")]["reads"] == w.d_gl("core.md")
    assert by_path[w.d_in("review-crew.md")]["family"] == "review-crew"
    assert by_path[w.inrepo("review-profile.md")]["reads"] == w.d_gl("review-crew.md")
    assert by_path[w.inrepo("test-pilot", "profile.md")]["family"] == "test-pilot"
    assert by_path[w.inrepo("test-pilot", "profile.md")]["reads"] == w.d_gl("test-pilot.md")
    assert by_path[w.inrepo("review-decisions.json")]["family"] == "decisions"
    assert by_path[w.inrepo("review-decisions.json")]["reads"] == w.d_gl("review-decisions.json")
    assert result["digest"] == hashlib.sha256("\n".join(left).encode("utf-8")).hexdigest()
    text = ls.notice(result)
    assert "storage setting is out-of-repo, and 5 old settings copies" in text
    for path in left:
        assert "- " + path in text
    assert "Retire leftover settings copies" in text


# --- 2. in-repo direction ------------------------------------------------------------------------

def test_in_repo_direction_lists_the_global_copies(w):
    # axis: a recorded in-repo project lists exactly the global copies, the legacy store entry included
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- in-repo\n")
    _put(w.d_in("test-pilot.md"), _PILOT)
    _put(w.inrepo("review-decisions.json"), '{"in": true}\n')
    review_entry = w.entry(w.rr)
    tp_entry = w.entry(w.tr)
    left = sorted([
        _put(w.d_gl("core.md"), _CORE + "\n<!-- stale global core -->\n"),
        _put(w.d_gl("review-crew.md"), "## Focus hints\n- stale\n"),
        _put(w.d_gl("test-pilot.md"), _PILOT + "stale\n"),
        _put(w.d_gl("review-decisions.json"), '{"stale": 1}\n'),
        _put(os.path.join(review_entry, "review-profile.md"), "## Threat model\nold\n"),
        _put(os.path.join(review_entry, "review-decisions.json"), '{"stale": 2}\n'),
        _put(os.path.join(tp_entry, "profile.md"), _PILOT + "old\n"),
    ])
    result = w.find()
    assert result["mode"] == mr.IN_REPO
    assert [f["path"] for f in result["files"]] == left
    assert "storage setting is in-repo, and 7 old settings copies" in ls.notice(result)


# --- 3. none -------------------------------------------------------------------------------------

def test_one_copy_of_everything_lists_nothing(w):
    # axis: a recorded project with one copy of each setting has no leftovers and no notice
    w.register(mr.GLOBAL)
    for name in ("core.md", "patterns.md", "guardian.md", "review-crew.md", "test-pilot.md"):
        _put(w.d_gl(name), _CORE if name == "core.md" else _PILOT)
    _put(w.d_gl("review-decisions.json"), "{}\n")
    result = w.find()
    assert result == {"mode": mr.GLOBAL, "files": [], "digest": _EMPTY_DIGEST}
    assert ls.notice(result) == ""


def test_unrecorded_project_lists_nothing(w):
    # axis: no recorded storage mode means no leftovers, however many copies sit on both sides
    for name in ("core.md", "review-crew.md"):
        _put(w.d_gl(name), _CORE)
        _put(w.d_in(name), _CORE)
    _put(w.inrepo("review-profile.md"), "old\n")
    assert mr.read_registry(w.cwd, w.root) is None
    result = w.find()
    assert result == {"mode": None, "files": [], "digest": _EMPTY_DIGEST}
    assert ls.notice(result) == ""


def test_corrupt_registry_lists_nothing(w):
    # axis: a corrupt registry reads as no record, so nothing is listed
    _put(w.d_gl("core.md"), _CORE)
    _put(w.d_in("core.md"), _CORE)
    _put(mr.registry_path(w.cwd, w.root), "{not json")
    assert w.find()["files"] == []
    assert w.find()["mode"] is None


def test_newer_registry_schema_propagates(w):
    # axis: a registry from a newer plugin fails closed, the exception reaching the caller
    _put(mr.registry_path(w.cwd, w.root), json.dumps({"schemaVersion": 99}))
    with pytest.raises(mr.UnknownSchemaVersion):
        w.find()


# --- 4. only copy kept ---------------------------------------------------------------------------

def test_only_copy_is_never_listed(w):
    # axis: a family with no copy in the picked slot lists nothing, so the only copy is never retired
    w.register(mr.GLOBAL)
    _put(w.d_gl("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- only copy\n")
    _put(w.d_in("test-pilot.md"), _PILOT)
    _put(w.inrepo("review-profile.md"), "old\n")
    _put(w.inrepo("review-decisions.json"), "{}\n")
    _put(w.d_in("guardian.md"), "guardian\n")
    assert w.find()["files"] == []


# --- 5. alias (B1) -------------------------------------------------------------------------------

def test_alias_core_symlink_is_not_listed(w):
    # axis: a global core.md that is a link to the in-repo core.md is one file, never a leftover; retire leaves it readable
    w.register(mr.GLOBAL)
    in_core = _put(w.d_in("core.md"), _CORE)
    os.makedirs(os.path.dirname(w.d_gl("core.md")), exist_ok=True)
    os.symlink(in_core, w.d_gl("core.md"))
    _put(w.d_in("guardian.md"), "stale guardian\n")
    _put(w.d_gl("guardian.md"), "guardian\n")
    result = w.find()
    assert [f["path"] for f in result["files"]] == [w.d_in("guardian.md")]
    done = w.retire(result["digest"])
    assert done["status"] == "retired"
    assert os.path.islink(w.d_gl("core.md")) and os.path.isfile(in_core)
    assert cm.read(w.cwd, w.root)["verifyCommand"] == "npm test"


def test_alias_linked_directory_is_not_listed(w):
    # axis: a .claude/superheroes directory that links to the global config directory is one place, never a leftover
    w.register(mr.GLOBAL)
    _put(w.d_gl("core.md"), _CORE)
    _put(w.d_gl("review-crew.md"), "## Focus hints\n- global\n")
    os.makedirs(w.inrepo(), exist_ok=True)
    os.symlink(os.path.dirname(w.d_gl("core.md")), w.inrepo("superheroes"))
    assert os.path.isfile(w.d_in("core.md")) and os.path.isfile(w.d_in("review-crew.md"))
    assert w.find()["files"] == []


# --- 6. alignment (B2) ---------------------------------------------------------------------------

def test_alignment_core_on_the_other_side_lists_nothing(w):
    # axis: with the only core.md on the other side, the co-located families list nothing
    w.register(mr.GLOBAL)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("guardian.md"), "in-repo guardian\n")
    _put(w.d_gl("guardian.md"), "global guardian\n")
    _put(w.d_in("test-pilot.md"), _PILOT)
    _put(w.d_gl("test-pilot.md"), _PILOT)
    assert w.find()["files"] == []


# --- 7. legacy safeguard (B3) --------------------------------------------------------------------

@pytest.mark.parametrize("core,listed", [
    pytest.param(None, False, id="no-core"),
    pytest.param(_EMPTY_CORE, False, id="empty-core"),
    pytest.param(_CORE, True, id="populated-core"),
])
def test_legacy_profile_needs_a_populated_core(w, core, listed):
    # axis: the legacy review profile is listed only when the core that replaces it is populated
    w.register(mr.GLOBAL)
    _put(w.d_gl("review-crew.md"), "## Focus hints\n- global\n")
    legacy = _put(w.inrepo("review-profile.md"), "## Threat model\nold\n")
    if core is not None:
        _put(w.d_gl("core.md"), core)
    assert w.paths() == ([legacy] if listed else [])


def test_legacy_file_that_is_read_is_not_listed(w):
    # axis: when the family reads the legacy file itself, the other legacy file is kept; the stale layer is listed
    w.register(mr.GLOBAL)
    _put(w.d_gl("core.md"), _CORE)
    review_entry = w.entry(w.rr)
    _put(os.path.join(review_entry, "review-profile.md"), "## Threat model\nread\n")
    stale_layer = _put(w.d_in("review-crew.md"), "## Focus hints\n- stale\n")
    _put(w.inrepo("review-profile.md"), "## Threat model\nold\n")
    assert w.paths() == [stale_layer]


# --- 8. broken picked copy -----------------------------------------------------------------------

@pytest.mark.parametrize("shape", ["directory", "dangling-link"])
def test_broken_picked_copy_still_is_the_read_slot(w, shape):
    # axis: a picked copy that is a directory or a dangling link is present, so it is the slot read and the stale copy is listed
    w.register(mr.GLOBAL)
    _put(w.d_gl("core.md"), _CORE)
    picked = w.d_gl("review-crew.md")
    if shape == "directory":
        os.makedirs(picked)
    else:
        os.symlink(str(w.tmp / "no-such-layer.md"), picked)
    stale = _put(w.d_in("review-crew.md"), "## Focus hints\n- stale\n")
    result = w.find()
    assert [f["path"] for f in result["files"]] == [stale]
    assert result["files"][0]["reads"] == picked


# --- 9. retire and restore -----------------------------------------------------------------------

def _selected(w):
    return [w.d_gl(n) for n in ("core.md", "review-crew.md", "test-pilot.md", "review-decisions.json")]


def test_retire_moves_exactly_the_listed_files_and_restore_puts_them_back(w):
    # axis: retire moves the listed files into a dated folder, leaves the selected copies untouched, and restore undoes it
    left = _everything_left_behind(w)
    before = {p: _read(p) for p in left}
    selected_before = {p: _read(p) for p in _selected(w)}
    listed = w.find()
    done = w.retire(listed["digest"])
    assert done["status"] == "retired"
    backup = os.path.join(w.store_dir(), "leftover-backups", STAMP)
    assert done["backup"] == backup
    assert done["manifest"] == os.path.join(backup, "retired.json")
    assert [m["from"] for m in done["moved"]] == left
    assert backup in done["undo"] and "restore" in done["undo"]
    for index, move in enumerate(done["moved"], start=1):
        assert move["to"] == os.path.join(backup, "%02d-%s" % (index, os.path.basename(move["from"])))
        assert not os.path.lexists(move["from"])
        assert _read(move["to"]) == before[move["from"]]
    for path, data in selected_before.items():
        assert _read(path) == data
    with open(done["manifest"], encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert manifest["schema"] == 1 and manifest["mode"] == mr.GLOBAL
    assert [(e["from"], e["to"]) for e in manifest["entries"]] == [(m["from"], m["to"]) for m in done["moved"]]
    assert {e["family"] for e in manifest["entries"]} == {
        "core", "review-crew", "test-pilot", "decisions"}
    assert w.find()["files"] == []
    assert w.retire(listed["digest"])["reason"] == "nothing-to-retire"

    # an occupied slot is skipped, never overwritten; the rest come back byte for byte
    occupied = w.d_in("core.md")
    _put(occupied, "the owner wrote this meanwhile\n")
    back = ls.restore(w.cwd, backup, root=w.root)
    assert back["status"] == "restored"
    assert back["skipped"] == [{"from": occupied, "why": "occupied"}]
    assert sorted(r["from"] for r in back["restored"]) == [p for p in left if p != occupied]
    assert _read(occupied) == b"the owner wrote this meanwhile\n"
    for path in left:
        if path != occupied:
            assert _read(path) == before[path]
    assert os.path.isfile(done["manifest"]) and os.path.isdir(backup)
    for path, data in selected_before.items():
        assert _read(path) == data


def test_restore_skips_a_missing_backup_file(w):
    # axis: an entry whose backed-up file is gone is skipped as missing, and the others still come back
    left = _everything_left_behind(w)
    done = w.retire(w.find()["digest"])
    gone = done["moved"][0]
    os.rename(gone["to"], gone["to"] + ".elsewhere")
    back = ls.restore(w.cwd, done["backup"], root=w.root)
    assert back["skipped"] == [{"from": gone["from"], "why": "missing"}]
    assert len(back["restored"]) == len(left) - 1


def test_restore_never_overwrites_a_dangling_link(w):
    # axis: restore treats a dangling link at the old path as occupied
    _everything_left_behind(w)
    done = w.retire(w.find()["digest"])
    target = done["moved"][0]["from"]
    os.symlink(str(w.tmp / "no-such-file"), target)
    back = ls.restore(w.cwd, done["backup"], root=w.root)
    assert {"from": target, "why": "occupied"} in back["skipped"]
    assert os.readlink(target) == str(w.tmp / "no-such-file")


def test_retire_without_owner_authorization_moves_nothing(w):
    # axis: anything but a literal True moves nothing
    left = _everything_left_behind(w)
    digest = w.find()["digest"]
    for value in (False, None, "true", 1):
        assert w.retire(digest, owner_authorized=value) == {
            "status": "blocked", "reason": "owner-authorization-required"}
    assert all(os.path.isfile(p) for p in left)
    assert not os.path.exists(os.path.join(w.store_dir(), "leftover-backups"))


def test_retire_with_a_stale_digest_moves_nothing(w):
    # axis: a digest from before a new leftover appeared moves nothing and returns the new list
    left = _everything_left_behind(w)
    stale_digest = w.find()["digest"]
    newcomer = _put(w.d_in("guardian.md"), "new in-repo guardian\n")
    _put(w.d_gl("guardian.md"), "guardian\n")
    done = w.retire(stale_digest)
    assert done["status"] == "blocked" and done["reason"] == "list-changed"
    assert [f["path"] for f in done["files"]] == sorted(left + [newcomer])
    assert done["digest"] == w.find()["digest"] != stale_digest
    assert all(os.path.isfile(p) for p in left + [newcomer])
    assert not os.path.exists(os.path.join(w.store_dir(), "leftover-backups"))


def test_retire_in_a_cloud_session_moves_nothing(w, monkeypatch):
    # axis: a cloud session never moves or restores calibration files
    left = _everything_left_behind(w)
    digest = w.find()["digest"]
    done = w.retire(digest)
    assert done["status"] == "retired"
    for move in done["moved"]:
        os.rename(move["to"], move["from"])
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    refusal = {"status": "blocked", "reason": store_core.CLOUD_REFUSAL_REASON}
    assert w.retire(digest) == refusal
    assert all(os.path.isfile(p) for p in left)
    for move in done["moved"]:
        os.rename(move["from"], move["to"])
    assert ls.restore(w.cwd, done["backup"], root=w.root) == refusal
    assert not any(os.path.lexists(p) for p in left)


def test_retire_and_restore_with_the_lock_held_are_busy(w):
    # axis: another holder of the config lock means busy and nothing moves
    left = _everything_left_behind(w)
    digest = w.find()["digest"]
    mr.ensure_project_store(w.cwd, w.root)
    with mr.config_lock(w.cwd, w.root) as got:
        assert got
        assert w.retire(digest) == {"status": "busy"}
    assert all(os.path.isfile(p) for p in left)
    done = w.retire(digest)
    assert done["status"] == "retired"
    with mr.config_lock(w.cwd, w.root) as got:
        assert got
        assert ls.restore(w.cwd, done["backup"], root=w.root) == {"status": "busy"}
    assert not any(os.path.lexists(p) for p in left)


def test_retire_twice_in_one_second_gets_a_new_folder(w):
    # axis: a backup folder that exists is never reused; the next gets -2
    _everything_left_behind(w)
    first = w.retire(w.find()["digest"])
    _put(w.d_in("guardian.md"), "later in-repo guardian\n")
    _put(w.d_gl("guardian.md"), "guardian\n")
    second = w.retire(w.find()["digest"])
    assert second["status"] == "retired"
    assert os.path.basename(first["backup"]) == STAMP
    assert os.path.basename(second["backup"]) == STAMP + "-2"
    assert os.path.isfile(os.path.join(first["backup"], "retired.json"))


def test_retire_partial_reports_what_moved(w, monkeypatch):
    # axis: a move that raises stops the run, reports what was done and moves nothing back
    left = _everything_left_behind(w)
    real_move = ls.shutil.move
    calls = []

    def flaky(src, dst):
        calls.append(src)
        if len(calls) == 2:
            raise OSError("disk full")
        return real_move(src, dst)

    monkeypatch.setattr(ls.shutil, "move", flaky)
    done = w.retire(w.find()["digest"])
    assert done["status"] == "partial"
    assert [m["from"] for m in done["moved"]] == left[:1]
    assert done["failed"]["from"] == left[1] and "disk full" in done["failed"]["detail"]
    assert not os.path.lexists(left[0]) and os.path.isfile(left[1])
    assert os.path.isfile(done["manifest"])


def test_restore_refuses_a_foreign_or_unreadable_backup(w, tmp_path):
    # axis: restore reads only a manifest inside the project's leftover-backups folder
    _everything_left_behind(w)
    done = w.retire(w.find()["digest"])
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "retired.json").write_text(_read(done["manifest"]).decode("utf-8"), encoding="utf-8")
    assert ls.restore(w.cwd, str(outside), root=w.root) == {
        "status": "blocked", "reason": "backup-outside-store"}
    assert ls.restore(w.cwd, str(tmp_path / "no-such-backup"), root=w.root) == {
        "status": "blocked", "reason": "manifest-unreadable"}
    broken = os.path.join(w.store_dir(), "leftover-backups", "broken")
    _put(os.path.join(broken, "retired.json"), "{not json")
    assert ls.restore(w.cwd, broken, root=w.root) == {
        "status": "blocked", "reason": "manifest-unreadable"}
    assert not os.path.lexists(done["moved"][0]["from"])


# --- 10. V994's three stale-copy reads, before and after retire ----------------------------------

def test_fu1_decisions_reader_follows_the_unified_copy_after_retire(w):
    # axis: FU1 - the review decisions reader stops preferring the legacy review-store copy once it is retired
    w.register(mr.GLOBAL)
    _put(w.d_gl("core.md"), _CORE)
    _put(w.d_gl("review-crew.md"), "## Focus hints\n- global\n")
    dec_gl = _put(w.d_gl("review-decisions.json"), '{"unified": true}\n')
    dec_legacy = _put(os.path.join(w.entry(w.rr), "review-decisions.json"), '{"legacy": true}\n')

    def read_path():
        return review_store.resolve(w.cwd, "decisions", legacy_root=w.rr,
                                    registry_root=w.root)["path"]

    assert read_path() == dec_legacy
    listed = w.find()
    assert [f["path"] for f in listed["files"]] == [dec_legacy]
    assert listed["files"][0]["reads"] == dec_gl
    assert w.retire(listed["digest"])["status"] == "retired"
    assert read_path() == dec_gl
    assert _read(dec_gl) == b'{"unified": true}\n'


def test_fu3_review_layer_ignores_the_stale_in_repo_layer_after_retire(w):
    # axis: FU3 - with a broken global review-crew layer a review no longer reads a stale in-repo layer once it is retired
    w.register(mr.GLOBAL)
    _put(w.d_gl("core.md"), _CORE)
    os.makedirs(w.d_gl("review-crew.md"))
    stale = _put(w.d_in("review-crew.md"), "## Focus hints\n- stale\n")

    def dispatch_layer():
        return calibration_resolve.resolve(
            w.cwd, root=w.root, legacy_root=w.rr)["dispatch_layer"]

    assert dispatch_layer() == stale
    listed = w.find()
    assert [f["path"] for f in listed["files"]] == [stale]
    assert w.retire(listed["digest"])["status"] == "retired"
    assert dispatch_layer() != stale


def test_fu4_test_pilot_reads_the_global_layer_after_retire(w):
    # axis: FU4 - test-pilot's resolver stops reading in-repo copies ahead of the global layer once they are retired
    w.register(mr.GLOBAL)
    _put(w.d_gl("core.md"), _CORE)
    global_layer = _put(w.d_gl("test-pilot.md"), _PILOT)
    stale_profile = _put(w.inrepo("test-pilot", "profile.md"), _PILOT + "stale profile\n")
    stale_layer = _put(w.d_in("test-pilot.md"), _PILOT + "stale layer\n")

    def profile():
        return store.resolve(w.cwd, w.tr)["profile"]

    assert profile() == stale_profile
    listed = w.find()
    assert [f["path"] for f in listed["files"]] == sorted([stale_profile, stale_layer])
    assert w.retire(listed["digest"])["status"] == "retired"
    assert profile() == global_layer


# --- 11. find is read-only and cheap (B6) --------------------------------------------------------

def _tree(*roots):
    out = []
    for top in roots:
        for here, dirs, files in os.walk(top):
            out += [os.path.join(here, n) for n in dirs + files]
    return sorted(out)


GIT_CALLS_CLEAN = 3
GIT_CALLS_LEFTOVERS = 3


@pytest.mark.parametrize("leftovers", [False, True])
def test_find_is_read_only_and_makes_few_git_calls(w, monkeypatch, leftovers):
    # axis: find writes nothing under any store root and makes a small fixed number of git calls
    if leftovers:
        _everything_left_behind(w)
        w.entry(w.rr)
        w.entry(w.tr)
    else:
        w.register(mr.GLOBAL)
        _put(w.d_gl("core.md"), _CORE)
        _put(w.d_gl("review-crew.md"), "## Focus hints\n- global\n")
        w.entry(w.rr)
        w.entry(w.tr)
    calls = []
    real = store_core.run_git_result

    def counting(cwd, *args, **kw):
        calls.append(args)
        return real(cwd, *args, **kw)

    monkeypatch.setattr(store_core, "run_git_result", counting)
    before = _tree(w.root, w.rr, w.tr)
    result = w.find()
    after = _tree(w.root, w.rr, w.tr)
    assert bool(result["files"]) is leftovers
    assert after == before
    assert len(calls) == (GIT_CALLS_LEFTOVERS if leftovers else GIT_CALLS_CLEAN), calls


# --- notice and the command line -----------------------------------------------------------------

def test_notice_wording_truncation_and_home(monkeypatch, tmp_path):
    # axis: one shared wording - singular and plural, ~ for the home, at most ten paths
    monkeypatch.setenv("HOME", str(tmp_path))
    one = {"mode": mr.IN_REPO, "digest": "x", "files": [
        {"path": str(tmp_path / ".claude" / "a.md"), "family": "core", "reads": "r"}]}
    text = ls.notice(one)
    assert text.splitlines()[0] == (
        "This project's storage setting is in-repo, and 1 old settings copy sit where it does not "
        "read first, so a later read could pick one up by mistake:")
    assert text.splitlines()[1] == "- ~/.claude/a.md"
    assert text.splitlines()[-1].startswith("To retire them, run /superheroes:configure and say yes at")
    many = {"mode": mr.GLOBAL, "digest": "x", "files": [
        {"path": "/x/%02d.md" % i, "family": "core", "reads": "r"} for i in range(12)]}
    lines = ls.notice(many).splitlines()
    assert "12 old settings copies" in lines[0]
    assert lines[1:11] == ["- /x/%02d.md" % i for i in range(10)]
    assert lines[11] == "- and 2 more (configure lists them all)"
    assert ls.notice({"mode": None, "files": [], "digest": "x"}) == ""


def test_cli_list_retire_restore_and_usage(w, monkeypatch, capsys):
    # axis: the command line prints one JSON object per result, exit 0, and exit 2 for bad usage
    monkeypatch.setenv("HOME", str(w.tmp / "home"))
    monkeypatch.setenv("TEST_PILOT_STORE_ROOT", w.tr)
    left = _everything_left_behind(w)
    base = ["--cwd", w.cwd, "--root", w.root]
    assert ls.main(["list", *base]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert [f["path"] for f in listed["files"]] == left
    assert listed["notice"].startswith("This project's storage setting is out-of-repo")
    assert ls.main(["retire", *base, "--owner-authorized", "false",
                    "--list-digest", listed["digest"]]) == 0
    assert json.loads(capsys.readouterr().out)["reason"] == "owner-authorization-required"
    assert ls.main(["retire", *base, "--owner-authorized", "true",
                    "--list-digest", listed["digest"]]) == 0
    done = json.loads(capsys.readouterr().out)
    assert done["status"] == "retired"
    assert ls.main(["restore", *base, "--backup", done["backup"]]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "restored"
    assert all(os.path.isfile(p) for p in left)
    assert ls.main([]) == 2
    assert ls.main(["retire", *base, "--owner-authorized", "maybe", "--list-digest", "x"]) == 2
    assert ls.main(["list"]) == 2
    capsys.readouterr()
