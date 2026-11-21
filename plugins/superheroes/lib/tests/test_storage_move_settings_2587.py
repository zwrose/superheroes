"""#2587 WO-2 - a storage move leaves no settings copy behind.

A flip (in-repo <-> global) carries the review decisions file to the new side, sets the legacy
review / test-pilot profiles and the stale decisions copies aside in one dated backup folder
(undoable with `leftover_settings.restore`), and names every copy it does not move in the preview.
Every repository is a real `git init` repository under tmp_path; every store root is under tmp_path
and passed explicitly. Nothing here touches a real home path.

Bite-proof record: wo2_2587_storage_move_settings
"""
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import core_md as cm  # noqa: E402
import leftover_settings as ls  # noqa: E402
import mode_migrate as mm  # noqa: E402
import mode_registry as mr  # noqa: E402
import store_core  # noqa: E402

ORIGIN = "https://github.com/acme/corner-shop.git"

_CORE = cm.render_core(
    {"verifyCommand": "npm test", "stackTags": [], "threatModel": "t", "patterns": ""},
    "confirmed", "2026-01-01", "2026-01-01")
_PILOT = "## Config\n```json test-pilot-config\n{}\n```\n"
_DEC = "review-decisions.json"


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


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class W:
    """One project: its repo, its store roots and the path spellers."""

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

    def plan(self, target):
        return mm.plan(self.cwd, target, root=self.root, owner_authorized=True,
                       review_root=self.rr, test_pilot_root=self.tr)

    def enumerate(self, target):
        return mm.enumerate_flip(self.cwd, target, root=self.root, review_root=self.rr,
                                 test_pilot_root=self.tr)

    def store_dir(self):
        return mr.project_store_dir(self.cwd, self.root)

    def backup_folders(self):
        base = os.path.join(self.store_dir(), ls.BACKUPS_DIRNAME)
        return sorted(os.path.join(base, n) for n in os.listdir(base)) if os.path.isdir(base) else []


@pytest.fixture
def w(tmp_path, isolated_default_store_root):
    return W(tmp_path, os.path.realpath(isolated_default_store_root))


def _seed_in_repo(w):
    """Recorded in-repo, with every kind of settings copy present on both sides."""
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- in-repo\n")
    _put(w.d_in("test-pilot.md"), _PILOT)
    _put(w.inrepo("review-profile.md"), "## Threat model\nold profile\n")
    _put(w.inrepo("test-pilot", "profile.md"), _PILOT + "old\n")
    _put(w.inrepo(_DEC), '{"in": true}\n')
    review_entry = w.entry(w.rr)
    tp_entry = w.entry(w.tr)
    _put(os.path.join(review_entry, _DEC), '{"stale": "entry"}\n')
    _put(os.path.join(review_entry, "review-profile.md"), "## Threat model\nentry profile\n")
    _put(os.path.join(tp_entry, "profile.md"), _PILOT + "entry\n")
    return review_entry, tp_entry


def _seed_global(w):
    """Recorded global, with every kind of settings copy present on both sides."""
    w.register(mr.GLOBAL)
    _put(w.d_gl("core.md"), _CORE)
    _put(w.d_gl("review-crew.md"), "## Focus hints\n- global\n")
    _put(w.d_gl("test-pilot.md"), _PILOT)
    _put(w.d_gl(_DEC), '{"global": true}\n')
    review_entry = w.entry(w.rr)
    tp_entry = w.entry(w.tr)
    _put(os.path.join(review_entry, _DEC), '{"stale": "entry"}\n')
    _put(os.path.join(review_entry, "review-profile.md"), "## Threat model\nentry profile\n")
    _put(os.path.join(tp_entry, "profile.md"), _PILOT + "entry\n")
    _put(w.inrepo("review-profile.md"), "## Threat model\nrepo profile\n")
    _put(w.inrepo("test-pilot", "profile.md"), _PILOT + "repo\n")
    return review_entry, tp_entry


# --- 1. in-repo -> global ------------------------------------------------------------------------

def test_in_repo_to_global_leaves_no_listed_kind_behind(w):
    # axis: a flip out of in-repo carries the decisions and sets every stale copy aside, so find lists nothing
    review_entry, tp_entry = _seed_in_repo(w)
    m = w.plan(mr.GLOBAL)
    assert m.blocked is False
    res = mm.execute(m, root=w.root)
    assert res == {"status": "done"}
    assert mr.resolve(w.cwd, root=w.root)["mode"] == mr.GLOBAL
    result = w.find()
    assert result["mode"] == mr.GLOBAL
    assert result["files"] == []
    # the carried decisions
    assert _text(w.d_gl(_DEC)) == '{"in": true}\n'
    assert not os.path.lexists(w.inrepo(_DEC))
    # the set-asides, in one dated folder, in entry order
    folders = w.backup_folders()
    assert len(folders) == 1 and folders[0].endswith("-storage-move")
    folder = folders[0]
    sources = {
        "01-review-decisions.json": os.path.join(review_entry, _DEC),
        "02-review-profile.md": w.inrepo("review-profile.md"),
        "03-review-profile.md": os.path.join(review_entry, "review-profile.md"),
        "04-profile.md": w.inrepo("test-pilot", "profile.md"),
        "05-profile.md": os.path.join(tp_entry, "profile.md"),
    }
    texts = {
        "01-review-decisions.json": '{"stale": "entry"}\n',
        "02-review-profile.md": "## Threat model\nold profile\n",
        "03-review-profile.md": "## Threat model\nentry profile\n",
        "04-profile.md": _PILOT + "old\n",
        "05-profile.md": _PILOT + "entry\n",
    }
    for name, src in sources.items():
        assert _text(os.path.join(folder, name)) == texts[name]
        assert not os.path.lexists(src)
    # restore puts every one back where it came from
    back = ls.restore(w.cwd, folder, root=w.root)
    assert back["status"] == "restored"
    assert back["skipped"] == []
    for name, src in sources.items():
        assert _text(src) == texts[name]


# --- 2. global -> in-repo ------------------------------------------------------------------------

def test_global_to_in_repo_leaves_no_listed_kind_behind(w):
    # axis: the mirror flip carries the decisions to the repo and sets every stale copy aside
    review_entry, tp_entry = _seed_global(w)
    res = mm.execute(w.plan(mr.IN_REPO), root=w.root)
    assert res == {"status": "done"}
    assert mr.resolve(w.cwd, root=w.root)["mode"] == mr.IN_REPO
    assert w.find()["files"] == []
    assert _text(w.inrepo(_DEC)) == '{"global": true}\n'
    assert not os.path.lexists(w.d_gl(_DEC))
    folder = w.backup_folders()[0]
    manifest = json.loads(_text(os.path.join(folder, ls.MANIFEST_FILENAME)))
    assert manifest["schema"] == ls.MANIFEST_SCHEMA
    assert manifest["mode"] == mr.GLOBAL
    assert sorted(e["from"] for e in manifest["entries"]) == sorted([
        os.path.join(review_entry, _DEC),
        os.path.join(review_entry, "review-profile.md"),
        w.inrepo("review-profile.md"),
        w.inrepo("test-pilot", "profile.md"),
        os.path.join(tp_entry, "profile.md"),
    ])
    assert sorted(os.listdir(folder)) == [
        "01-review-decisions.json", "02-review-profile.md", "03-review-profile.md",
        "04-profile.md", "05-profile.md", ls.MANIFEST_FILENAME]
    back = ls.restore(w.cwd, folder, root=w.root)
    assert back["status"] == "restored" and back["skipped"] == []
    assert _text(os.path.join(review_entry, _DEC)) == '{"stale": "entry"}\n'


# --- 3. preview ----------------------------------------------------------------------------------

def test_preview_names_set_asides_left_in_place_and_overwrites(w):
    # axis: the preview shows where each set-aside goes, what stays and why, and what is replaced
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- in-repo\n")
    _put(w.inrepo("review-profile.md"), "## Threat model\nold\n")        # layer moves: set aside
    _put(w.inrepo("test-pilot", "profile.md"), _PILOT + "old\n")         # no layer: only copy
    _put(w.inrepo(_DEC), '{"in": true}\n')                               # carried
    review_entry = w.entry(w.rr)
    os.makedirs(os.path.join(review_entry, "review-profile.md"))         # not a regular file
    _put(w.d_gl("core.md"), _CORE + "\n<!-- already there -->\n")        # replaced by the flip
    _put(w.d_gl(_DEC), '{"old": true}\n')                                # replaced by the carry
    m = w.enumerate(mr.GLOBAL)
    pv = mm.preview(m)
    folders_before = w.backup_folders()
    assert folders_before == []                                          # nothing is created
    assert len(pv["setAside"]) == 1
    aside = pv["setAside"][0]
    assert aside["from"] == w.inrepo("review-profile.md")
    folder = os.path.dirname(aside["to"])
    assert os.path.basename(aside["to"]) == "01-review-profile.md"
    assert os.path.dirname(folder) == os.path.join(w.store_dir(), ls.BACKUPS_DIRNAME)
    assert os.path.basename(folder).endswith("-storage-move")
    assert not os.path.exists(folder)
    assert sorted((e["path"], e["why"]) for e in pv["leftInPlace"]) == sorted([
        (w.inrepo("test-pilot", "profile.md"), "only-copy"),
        (os.path.join(review_entry, "review-profile.md"), "not-a-regular-file"),
    ])
    assert sorted(pv["overwrites"]) == sorted([w.d_gl("core.md"), w.d_gl(_DEC)])
    # a carried entry is calibration; a set-aside one is in none of the three existing lists
    assert w.inrepo(_DEC) in pv["calibration"]
    for key in ("calibration", "definitionDocs", "workItemRecords"):
        assert aside["from"] not in pv[key]
    assert w.inrepo("test-pilot", "profile.md") not in {f["src"] for f in m.files}


@pytest.mark.parametrize("case", [
    pytest.param("target-copy-stays", id="target-copy-stays"),
    pytest.param("only-legacy-copy", id="only-legacy-copy"),
    pytest.param("left-behind-in-repo", id="left-behind-in-repo"),
    pytest.param("named-once", id="named-once"),
    pytest.param("replaced-is-not-retained", id="replaced-is-not-retained"),
])
def test_preview_names_each_retained_decisions_copy(w, case):
    # axis: every decisions copy that remains after the move is in leftInPlace with why retained, once, and one a carry replaces is not
    entry_dec = None
    if case == "target-copy-stays":
        # in-repo -> global, no in-repo copy to carry: the global copy stays, the legacy copy is set aside over it
        w.register(mr.IN_REPO)
        _put(w.d_in("core.md"), _CORE)
        entry_dec = os.path.join(w.entry(w.rr), _DEC)
        _put(entry_dec, '{"stale": "entry"}\n')
        _put(w.d_gl(_DEC), '{"global": true}\n')
        target, expected = mr.GLOBAL, [(w.d_gl(_DEC), "retained")]
    elif case == "only-legacy-copy":
        # in-repo -> global with the legacy copy alone: nothing takes its slot, so it stays
        w.register(mr.IN_REPO)
        _put(w.d_in("core.md"), _CORE)
        entry_dec = _put(os.path.join(w.entry(w.rr), _DEC), '{"only": true}\n')
        target, expected = mr.GLOBAL, [(entry_dec, "retained")]
    elif case == "left-behind-in-repo":
        # global -> in-repo with the in-repo copy alone: nothing moves, and it stays
        w.register(mr.GLOBAL)
        _put(w.d_gl("core.md"), _CORE)
        target, expected = mr.IN_REPO, [(_put(w.inrepo(_DEC), '{"in": true}\n'), "retained")]
    elif case == "named-once":
        # a directory at the in-repo slot is named not-a-regular-file only; the global copy stays and is retained
        w.register(mr.IN_REPO)
        _put(w.d_in("core.md"), _CORE)
        os.makedirs(w.inrepo(_DEC))
        target, expected = mr.GLOBAL, [(w.inrepo(_DEC), "not-a-regular-file"),
                                       (_put(w.d_gl(_DEC), '{"global": true}\n'), "retained")]
    else:
        # in-repo -> global carrying over a present global copy: the copy is replaced, not retained
        w.register(mr.IN_REPO)
        _put(w.d_in("core.md"), _CORE)
        _put(w.inrepo(_DEC), '{"in": true}\n')
        _put(w.d_gl(_DEC), '{"old": true}\n')
        target, expected = mr.GLOBAL, []
    m = w.enumerate(target)
    pv = mm.preview(m)
    assert sorted((e["path"], e["why"]) for e in pv["leftInPlace"]) == sorted(expected)
    # the rows are the whole story: no decisions copy is both retained and moved
    moved = {p for f in m.files for p in (f["src"], f["dst"]) if f.get("family") == "decisions"}
    assert not ({e["path"] for e in pv["leftInPlace"]} & moved)
    if case == "target-copy-stays":
        assert [a["from"] for a in pv["setAside"]] == [entry_dec]


# --- edge 1: no shared path ----------------------------------------------------------------------

@pytest.mark.parametrize("direction", [mr.GLOBAL, mr.IN_REPO])
def test_no_entry_shares_a_path_with_another(w, direction):
    # axis: every src and dst across carry, set-aside and today's entries is a path of its own
    if direction == mr.GLOBAL:
        _seed_in_repo(w)
    else:
        _seed_global(w)
    m = w.enumerate(direction)
    roles = [f.get("role") for f in m.files]
    assert roles.count("carry") == 1 and roles.count("set-aside") == 5
    assert {f["family"] for f in m.files if f.get("role")} == {"decisions", "review-crew", "test-pilot"}
    paths = [p for f in m.files for p in (f["src"], f["dst"])]
    assert len(paths) == len(set(paths))
    assert m.left_in_place == []


# --- edge 2: a non-regular file is never in files ------------------------------------------------

def test_a_non_regular_path_is_never_moved(w, tmp_path):
    # axis: a directory or a link is named not-a-regular-file, never moved and never called an only copy
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- in-repo\n")
    os.makedirs(w.inrepo(_DEC))                                           # a directory
    target = _put(str(tmp_path / "elsewhere" / "p.md"), "linked\n")
    os.makedirs(w.inrepo("test-pilot"))
    os.symlink(target, w.inrepo("review-profile.md"))                     # a link, layer moves
    os.symlink(target, w.inrepo("test-pilot", "profile.md"))              # a link, no layer
    m = w.enumerate(mr.GLOBAL)
    moved = {p for f in m.files for p in (f["src"], f["dst"])}
    for path in (w.inrepo(_DEC), w.inrepo("review-profile.md"), w.inrepo("test-pilot", "profile.md")):
        assert path not in moved
    assert sorted((e["path"], e["why"]) for e in m.left_in_place) == sorted([
        (w.inrepo(_DEC), "not-a-regular-file"),
        (w.inrepo("review-profile.md"), "not-a-regular-file"),
        (w.inrepo("test-pilot", "profile.md"), "not-a-regular-file"),
    ])


# --- edge 3: a legacy profile with no moving layer stays -----------------------------------------

def test_a_legacy_profile_without_a_moving_layer_stays_put(w):
    # axis: a legacy profile whose hero has no unified layer to move is left in place as the only copy
    w.register(mr.GLOBAL)
    _put(w.d_gl("core.md"), _CORE)
    review_entry = w.entry(w.rr)
    tp_entry = w.entry(w.tr)
    legacy = [_put(w.inrepo("review-profile.md"), "r\n"),
              _put(os.path.join(review_entry, "review-profile.md"), "e\n"),
              _put(w.inrepo("test-pilot", "profile.md"), "t\n"),
              _put(os.path.join(tp_entry, "profile.md"), "u\n")]
    m = w.enumerate(mr.IN_REPO)
    moved = {f["src"] for f in m.files}
    assert not (set(legacy) & moved)
    assert sorted((e["path"], e["why"]) for e in m.left_in_place) == sorted(
        (p, "only-copy") for p in legacy)


def test_the_only_decisions_copy_is_not_set_aside(w):
    # axis: a legacy-entry decisions file with no copy to take over its slot is not moved
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- in-repo\n")
    review_entry = w.entry(w.rr)
    only = _put(os.path.join(review_entry, _DEC), '{"only": true}\n')
    m = w.enumerate(mr.GLOBAL)
    assert only not in {f["src"] for f in m.files}
    assert [f for f in m.files if f.get("role")] == []


# --- edge 4: the base shape is unchanged ---------------------------------------------------------

@pytest.mark.parametrize("direction", [mr.GLOBAL, mr.IN_REPO])
def test_files_are_the_base_shape_without_settings_copies(w, direction):
    # axis: with no decisions or legacy profile anywhere, files is exactly today's {src, dst, done} list
    if direction == mr.GLOBAL:
        w.register(mr.IN_REPO)
        _put(w.d_in("core.md"), _CORE)
        _put(w.d_in("review-crew.md"), "## Focus hints\n- in-repo\n")
        expected = [
            {"src": w.d_in("core.md"), "dst": w.d_gl("core.md"), "done": False},
            {"src": w.d_in("review-crew.md"), "dst": w.d_gl("review-crew.md"), "done": False},
        ]
    else:
        w.register(mr.GLOBAL)
        _put(w.d_gl("core.md"), _CORE)
        _put(w.d_gl("review-crew.md"), "## Focus hints\n- global\n")
        expected = [
            {"src": w.d_gl("core.md"), "dst": w.d_in("core.md"), "done": False},
            {"src": w.d_gl("review-crew.md"), "dst": w.d_in("review-crew.md"), "done": False},
        ]
    m = w.enumerate(direction)
    assert m.files == expected
    assert m.left_in_place == []
    pv = mm.preview(m)
    assert pv["setAside"] == [] and pv["leftInPlace"] == [] and pv["overwrites"] == []


# --- edge 5: an interrupted flip -----------------------------------------------------------------

def _stage_interrupted(w, copy_all=True):
    """Write the journal of a flip that died during/after the copy phase, as execute leaves it."""
    _seed_in_repo(w)
    m = w.plan(mr.GLOBAL)
    aside = [f for f in m.files if f.get("role") == "set-aside"]
    assert aside, "the fixture must produce set-asides"
    skipped = aside[-1]["dst"]
    for f in m.files:
        if not copy_all and f["dst"] == skipped:
            continue
        store_core.atomic_write(f["dst"], _text(f["src"]))
    journal = {"kind": "flip", "target": mr.GLOBAL, "phase": "committing",
               "files": [{"src": f["src"], "dst": f["dst"], "done": True} for f in m.files]}
    store_core.atomic_write(os.path.join(w.store_dir(), "migration-journal.json"),
                            json.dumps(journal))
    return m


def test_recover_backs_out_before_the_commit(w):
    # axis: a flip that died before the registry commit leaves every source and no set-aside destination
    m = _stage_interrupted(w)
    assert mr.resolve(w.cwd, root=w.root)["mode"] == mr.IN_REPO
    assert mm.recover(w.cwd, root=w.root) == {"status": "recovered"}
    for f in m.files:
        assert os.path.isfile(f["src"]), f["src"]
        assert not os.path.lexists(f["dst"]), f["dst"]
    assert not os.path.exists(os.path.join(w.store_dir(), "migration-journal.json"))


def test_recover_finishes_after_the_commit(w):
    # axis: a flip that died after the commit has every source gone and every set-aside destination present
    m = _stage_interrupted(w, copy_all=False)
    mr.write_registry(w.cwd, mr.GLOBAL, store_core.derive_identifiers(w.cwd)["remote_hash"],
                      root=w.root, allow_migration=True)
    assert mm.recover(w.cwd, root=w.root) == {"status": "recovered"}
    for f in m.files:
        assert not os.path.lexists(f["src"]), f["src"]
        assert os.path.isfile(f["dst"]), f["dst"]
    assert not os.path.exists(os.path.join(w.store_dir(), "migration-journal.json"))


def _alias_config_to_claude(w):
    """Make the project store's config directory a link to the repository's .claude directory."""
    claude = w.inrepo()
    os.makedirs(claude, exist_ok=True)
    config = os.path.dirname(w.d_gl("x"))
    os.makedirs(os.path.dirname(config), exist_ok=True)
    os.symlink(claude, config, target_is_directory=True)
    return claude


def test_aliased_primary_decisions_counts_as_carried(w):
    # axis: a decisions carry whose source and target are one file is already carried, so a second copy is set aside, never carried over it
    w.register(mr.GLOBAL)
    _alias_config_to_claude(w)
    primary = _put(w.inrepo("review-decisions.json"), '{"primary": true}\n')
    legacy = _put(os.path.join(w.entry(w.rr), "review-decisions.json"), '{"legacy": true}\n')
    m = w.plan(mr.IN_REPO)
    carried = [f for f in m.files if f.get("role") == "carry" and f.get("family") == "decisions"]
    assert carried == []
    assert [f["src"] for f in m.files if f.get("role") == "set-aside"] == [legacy]
    assert mm.execute(m, root=w.root)["status"] == "done"
    with open(primary, encoding="utf-8") as fh:
        assert fh.read() == '{"primary": true}\n'


def test_every_decisions_slot_aliased_keeps_the_file(w):
    # axis: with all three decisions slots naming one file, the flip neither carries nor sets it aside, and the file survives
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    claude = _alias_config_to_claude(w)
    entry = w.entry(w.rr)
    for name in os.listdir(entry):
        os.replace(os.path.join(entry, name), os.path.join(claude, name))
    os.rmdir(entry)
    os.symlink(claude, entry, target_is_directory=True)
    assert ls._legacy_entry_dir(w.cwd, w.rr) is not None
    decisions = _put(w.inrepo("review-decisions.json"), '{"only": true}\n')
    m = w.plan(mr.GLOBAL)
    assert [f for f in m.files if f.get("family") == "decisions"] == []
    assert mm.execute(m, root=w.root)["status"] == "done"
    with open(decisions, encoding="utf-8") as fh:
        assert fh.read() == '{"only": true}\n'
