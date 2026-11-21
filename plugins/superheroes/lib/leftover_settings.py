#!/usr/bin/env python3
"""Leftover project settings: name them (`find`), move them aside (`retire`), undo it (`restore`).

THE INVARIANT. A settings file is a leftover exactly when another copy of the SAME family sits in
the slot the project's RECORDED storage mode reads first, the two are not the same file on disk,
and the family's own gate admits it. `find` lists exactly the leftovers and nothing else; `retire`
moves exactly the files `find` lists, and nothing else, and only with the owner's authorization and
the digest of the list the owner saw. Nothing is ever deleted: a retired file moves into a dated
folder under the project store, with a manifest (`retired.json`) that `restore` reads back.

Families (ordered slots; the first present picked slot is the one the setting reads):
  * each other `*.md` in the in-repo calibration directory or its out-of-repo twin (core.md,
    patterns.md, guardian.md, every hero layer except review-crew.md and test-pilot.md), gated on the
    read core.md being on the recorded side (or no core.md anywhere);
  * review-crew: the layer, then the review-crew legacy profile (legacy files listed only while the
    layer is what is read, is a regular file (os.path.isfile) and the core is populated); when the read
    slot is the recorded side's legacy profile the family lists nothing, because readers do not let a
    legacy profile supersede the other side's layer;
  * test-pilot: the same shape, also gated on the read core.md being on the recorded side, and a legacy
    profile is never listed while a `blocks` or `manifests` directory beside it holds any entry
    (store.resolve puts them there, so retiring the profile would strand them);
  * decisions: review-decisions.json in the three places it lives; lists nothing unless the recorded
    side's review-crew layer is a regular file, because the decisions side follows the review
    calibration's location.

`find` writes nothing: it reads the registry without backfill, resolves the legacy store entries
without healing, and takes no lock. Stdlib only.

CLI: `leftover_settings.py list|retire|restore --cwd . [--root R] ...` prints one JSON object on
stdout and exits 0 for every result; exit 2 is bad usage.
"""
import argparse
import datetime
import errno
import hashlib
import json
import os
import shlex
import shutil
import sys
import uuid

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import calibration_paths  # noqa: E402
import core_md  # noqa: E402
import mode_registry  # noqa: E402
import review_store  # noqa: E402
import store  # noqa: E402
import store_core  # noqa: E402

BACKUPS_DIRNAME = "leftover-backups"
MANIFEST_FILENAME = "retired.json"
MANIFEST_SCHEMA = 1
MAX_NOTICE_PATHS = 10

REASON_OWNER_AUTHORIZATION = "owner-authorization-required"
REASON_STORE_UNWRITABLE = "store-unwritable"
REASON_NOTHING_TO_RETIRE = "nothing-to-retire"
REASON_LIST_CHANGED = "list-changed"
REASON_MANIFEST_UNREADABLE = "manifest-unreadable"
REASON_BACKUP_OUTSIDE_STORE = "backup-outside-store"

_LAYER_FAMILIES = {"core.md": "core", "patterns.md": "patterns"}
_PICKED_LAYERS = ("review-crew.md", "test-pilot.md")
_REVIEW_CREW = "review-crew.md"
_TEST_PILOT = "test-pilot.md"
_DECISIONS = review_store.FILENAMES["decisions"]
_DEC_IN_REL = os.path.join(".claude", _DECISIONS)
_LEGACY_TP_IN_REL = mode_registry._HERO_LEGACY_INREPO["test-pilot"]
_LEGACY_TP_STORE_FILENAME = "profile.md"


def _present(path):
    """Present means lexists: a directory or a dangling link counts as present."""
    return os.path.lexists(path)


def _digest(paths):
    return hashlib.sha256("\n".join(sorted(paths)).encode("utf-8")).hexdigest()


def _md_names(directory):
    try:
        return [n for n in os.listdir(directory) if n.endswith(".md")]
    except OSError:
        return []


def _legacy_entry_dir(cwd, legacy_root):
    """The legacy store entry directory for cwd, or None. heal=False: writes nothing."""
    g = store_core.resolve_global(cwd, legacy_root, heal=False)
    return g["dir"] if g else None


def _slots(*paths):
    """The slots whose path could be formed (a None path is a slot with no legacy entry)."""
    return [p for p in paths if p]


def _holds_entries(directory):
    """True when directory has a `blocks` or `manifests` subdirectory holding any entry. Fail closed:
    one that is present but cannot be listed (a file, a dangling link) cannot be shown empty."""
    for sub in ("blocks", "manifests"):
        path = os.path.join(directory, sub)
        if not _present(path):
            continue
        try:
            if os.listdir(path):
                return True
        except OSError:
            return True
    return False


def _tp_artifacts_beside(slot):
    """A legacy test-pilot profile's blocks and manifests sit beside it (store.resolve), so
    retiring the profile would make any that exist unreachable."""
    return _holds_entries(os.path.dirname(slot))


def _gather(picked, unpicked, family, *, aligned=True, admitted=True, layer_only=False, layer=None,
            legacy=(), populated=None, legacy_veto=None):
    """The leftovers of one family: [(path, family, reads)]."""
    # axis: a family whose gate refuses it lists nothing
    if not aligned or not admitted:
        return []
    reads = next((p for p in picked if _present(p)), None)
    if reads is None:
        # axis: a family with no present picked slot lists nothing, so the only copy is never retired
        return []
    # axis: a family whose read is a legacy profile lists nothing, since readers do not let it supersede the other side's layer
    if layer_only and reads != layer:
        return []
    real_reads = os.path.realpath(reads)
    out = []
    for slot in picked[picked.index(reads) + 1:] + unpicked:
        if not _present(slot):
            continue
        # axis: a copy that is the same file on disk as the slot read (a link either way, or a linked directory) is never listed
        if os.path.realpath(slot) == real_reads:
            continue
        # axis: a legacy file is listed only while the layer is a regular file that is what is read and the core is populated
        if slot in legacy and not (reads == layer and os.path.isfile(reads) and populated()):
            continue
        # axis: a legacy profile with blocks or manifests beside it is never listed, since retiring it would strand them
        if slot in legacy and legacy_veto is not None and legacy_veto(slot):
            continue
        out.append((slot, family, reads))
    return out


def find(cwd, root=None, *, review_root=None, test_pilot_root=None):
    """The leftover settings copies of the project at cwd. Writes nothing.

    Returns {"mode": mode or None, "files": [{"path", "family", "reads"}], "digest": sha256 hex}.
    No registry (or a corrupt one) lists nothing; a newer registry schema raises
    mode_registry.UnknownSchemaVersion (fail-closed; the callers catch it)."""
    with store_core.repo_identity_memo():
        rec = mode_registry.read_registry(cwd, root)
        if rec is None:
            return {"mode": None, "files": [], "digest": _digest([])}
        mode = rec["storageMode"]
        repo = store_core.repo_root(cwd)
        d_in = os.path.join(repo, calibration_paths.IN_REPO_DIR)
        d_gl = os.path.join(mode_registry.project_store_dir(cwd, root), mode_registry.CONFIG_DIRNAME)
        d_m, d_o = (d_in, d_gl) if mode == mode_registry.IN_REPO else (d_gl, d_in)

        review_entry = _legacy_entry_dir(cwd, review_root or review_store.store_root())
        tp_entry = _legacy_entry_dir(cwd, test_pilot_root or store.store_root())
        legacy_review = {
            mode_registry.IN_REPO: os.path.join(repo, calibration_paths.LEGACY_INREPO_REVIEW_PROFILE),
            mode_registry.GLOBAL: (os.path.join(review_entry, review_store.FILENAMES["profile"])
                                   if review_entry else None),
        }
        legacy_tp = {
            mode_registry.IN_REPO: os.path.join(repo, _LEGACY_TP_IN_REL),
            mode_registry.GLOBAL: (os.path.join(tp_entry, _LEGACY_TP_STORE_FILENAME)
                                   if tp_entry else None),
        }
        other = (mode_registry.GLOBAL if mode == mode_registry.IN_REPO else mode_registry.IN_REPO)

        # aligned: the read core.md sits on the recorded side, or there is no core.md on either side
        core_in = os.path.join(d_in, core_md.CORE_FILENAME)
        core_gl = os.path.join(d_gl, core_md.CORE_FILENAME)
        if not (_present(core_in) or _present(core_gl)):
            aligned = True
        else:
            aligned = os.path.dirname(core_md.core_path(cwd, root, persist_backfill=False)) == d_m

        state = {}

        def populated():
            # axis: a populated core is a core whose facts are not empty; an unreadable core counts as empty
            if "v" not in state:
                try:
                    rec_core = core_md.read(cwd, root, persist_backfill=False)
                except Exception:
                    rec_core = None
                state["v"] = not core_md.core_facts_are_empty(rec_core)
            return state["v"]

        found = []
        for name in sorted(set(_md_names(d_in)) | set(_md_names(d_gl))):
            if name in _PICKED_LAYERS:
                continue
            family = _LAYER_FAMILIES.get(name, "layer:" + name[:-len(".md")])
            found += _gather([os.path.join(d_m, name)], [os.path.join(d_o, name)], family,
                             aligned=aligned)

        layer = os.path.join(d_m, _REVIEW_CREW)
        found += _gather(
            _slots(layer, legacy_review[mode]),
            _slots(os.path.join(d_o, _REVIEW_CREW), legacy_review[other]),
            "review-crew", layer_only=True, layer=layer,
            legacy=_slots(legacy_review[mode], legacy_review[other]), populated=populated)

        layer = os.path.join(d_m, _TEST_PILOT)
        found += _gather(
            _slots(layer, legacy_tp[mode]),
            _slots(os.path.join(d_o, _TEST_PILOT), legacy_tp[other]),
            "test-pilot", aligned=aligned, layer_only=True, layer=layer,
            legacy=_slots(legacy_tp[mode], legacy_tp[other]), populated=populated,
            legacy_veto=_tp_artifacts_beside)

        dec_in = os.path.join(repo, _DEC_IN_REL)
        dec_gl = os.path.join(d_gl, _DECISIONS)
        dec_legacy = os.path.join(review_entry, _DECISIONS) if review_entry else None
        # the decisions side follows the review calibration's location, so they are admitted only
        # while the recorded side has a review-crew layer that is a regular file (a broken one, a
        # directory or a dangling link, may not be what is read, so the other side's decisions stay)
        has_layer = os.path.isfile(os.path.join(d_m, _REVIEW_CREW))
        if mode == mode_registry.GLOBAL:
            found += _gather(_slots(dec_gl, dec_legacy), [dec_in], "decisions", admitted=has_layer)
        else:
            found += _gather([dec_in], _slots(dec_gl, dec_legacy), "decisions", admitted=has_layer)

        files, seen = [], set()
        for path, family, reads in sorted(found):
            if path not in seen:
                seen.add(path)
                files.append({"path": path, "family": family, "reads": reads})
        return {"mode": mode, "files": files, "digest": _digest([f["path"] for f in files])}


def _home_short(path):
    home = os.path.expanduser("~")
    if home and home != os.sep and (path == home or path.startswith(home + os.sep)):
        return "~" + path[len(home):]
    return path


def notice(result):
    """The one shared wording for session start and configure; "" when nothing is left over."""
    files = result["files"]
    if not files:
        return ""
    count = len(files)
    side = "in-repo" if result.get("mode") == mode_registry.IN_REPO else "out-of-repo"
    noun = "copy" if count == 1 else "copies"
    lines = ["This project's storage setting is %s, and %d old settings %s sit where it does not "
             "read first, so a later read could pick one up by mistake:" % (side, count, noun)]
    for entry in files[:MAX_NOTICE_PATHS]:
        lines.append("- " + _home_short(entry["path"]))
    if count > MAX_NOTICE_PATHS:
        lines.append("- and %d more (configure lists them all)" % (count - MAX_NOTICE_PATHS))
    lines.append("To retire them, run /superheroes:configure and say yes at \"Retire leftover "
                 "settings copies\". They move to a dated backup folder (never deleted), and the "
                 "step says how to undo it.")
    return "\n".join(lines)


def _cloud_refusal():
    return {"status": "blocked", "reason": store_core.CLOUD_REFUSAL_REASON}


def _stamp(now):
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    elif isinstance(now, (int, float)):
        now = datetime.datetime.fromtimestamp(now, datetime.timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    return now.astimezone(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _make_backup_dir(store_dir, now):
    parent = os.path.join(store_dir, BACKUPS_DIRNAME)
    os.makedirs(parent, exist_ok=True)
    stamp = _stamp(now)
    n = 1
    while True:
        candidate = os.path.join(parent, stamp if n == 1 else "%s-%d" % (stamp, n))
        try:
            os.mkdir(candidate)
            return candidate
        except FileExistsError:
            n += 1


def _undo_sentence(cwd, backup, root=None):
    """The shell command that undoes a retire: every path shell-quoted, `--root` named when the
    retire was given a non-default root."""
    parts = ["python3", shlex.quote(os.path.abspath(__file__)), "restore",
             "--cwd", shlex.quote(cwd), "--backup", shlex.quote(backup)]
    if root is not None:
        parts += ["--root", shlex.quote(root)]
    return "To undo this, run: " + " ".join(parts)


def retire(cwd, *, owner_authorized, list_digest, root=None, review_root=None,
           test_pilot_root=None, now=None):
    """Move exactly the files `find` lists into <project store>/leftover-backups/<stamp>/.

    Moves nothing without the owner's authorization, in a cloud session, with the lock held, or
    when the list changed since the owner saw it (list_digest)."""
    if store_core.in_cloud_session():
        return _cloud_refusal()
    # axis: nothing moves without the owner's authorization
    if owner_authorized is not True:
        return {"status": "blocked", "reason": REASON_OWNER_AUTHORIZATION}
    with store_core.repo_identity_memo():
        store_dir = mode_registry.ensure_project_store(cwd, root)
        if store_dir is None:
            return {"status": "blocked", "reason": REASON_STORE_UNWRITABLE}
        with mode_registry.config_lock(cwd, root) as got:
            if not got:
                return {"status": "busy"}
            current = find(cwd, root, review_root=review_root, test_pilot_root=test_pilot_root)
            if not current["files"]:
                return {"status": "blocked", "reason": REASON_NOTHING_TO_RETIRE}
            # axis: the files moved are the files the owner saw, so a changed list moves nothing
            if current["digest"] != list_digest:
                return {"status": "blocked", "reason": REASON_LIST_CHANGED,
                        "files": current["files"], "digest": current["digest"]}
            backup = _make_backup_dir(store_dir, now)
            entries = []
            for index, entry in enumerate(current["files"], start=1):
                entries.append({
                    "from": entry["path"],
                    "to": os.path.join(backup, "%02d-%s" % (index, os.path.basename(entry["path"]))),
                    "family": entry["family"]})
            manifest = os.path.join(backup, MANIFEST_FILENAME)
            # the manifest is written first, so a move that dies half way is still undoable
            store_core.atomic_write(manifest, json.dumps(
                {"schema": MANIFEST_SCHEMA, "mode": current["mode"], "entries": entries}, indent=2))
            moved = []
            for entry in entries:
                try:
                    _staged_move(entry["from"], entry["to"])
                except Exception as exc:
                    return {"status": "partial", "backup": backup, "manifest": manifest,
                            "moved": moved,
                            "failed": {"from": entry["from"],
                                       "detail": "%s: %s" % (type(exc).__name__, exc)}}
                moved.append({"from": entry["from"], "to": entry["to"]})
            return {"status": "retired", "backup": backup, "manifest": manifest, "moved": moved,
                    "undo": _undo_sentence(cwd, backup, root)}


def _remove_object(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def _staged_move(src, dst):
    """Move src to dst, publishing dst only once it is complete. A rename on one filesystem; across
    filesystems, a copy staged beside dst and renamed into place, then the source removed. A failed
    copy removes its staging copy, so dst is either absent or whole; links and directories are kept."""
    try:
        os.rename(src, dst)
        return
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
    stage = os.path.join(os.path.dirname(dst), ".%s.staging-%s" % (os.path.basename(dst), uuid.uuid4().hex))
    try:
        if os.path.islink(src):
            os.symlink(os.readlink(src), stage)
        elif os.path.isdir(src):
            shutil.copytree(src, stage, symlinks=True)
        else:
            shutil.copy2(src, stage)
        os.replace(stage, dst)
    except BaseException:
        # axis: an interrupted cross-filesystem copy leaves no partial file at dst
        if os.path.lexists(stage):
            _remove_object(stage)
        raise
    _remove_object(src)


def _inside(path, directory):
    real, base = os.path.realpath(path), os.path.realpath(directory)
    return real != base and real.startswith(base + os.sep)


def restore(cwd, backup, *, root=None):
    """Put a retired backup's files back where they came from; never overwrites a present path
    and never deletes the manifest or the folder. Each backed-up file is read as
    <backup>/<basename of the stored `to`>, so a folder that moved with its store still restores; an
    entry whose basename is empty, `.`, `..` or the manifest itself is skipped as entry-invalid."""
    if store_core.in_cloud_session():
        return _cloud_refusal()
    with store_core.repo_identity_memo():
        store_dir = mode_registry.ensure_project_store(cwd, root)
        if store_dir is None:
            return {"status": "blocked", "reason": REASON_STORE_UNWRITABLE}
        with mode_registry.config_lock(cwd, root) as got:
            if not got:
                return {"status": "busy"}
            try:
                with open(os.path.join(backup, MANIFEST_FILENAME), encoding="utf-8") as fh:
                    manifest = json.load(fh)
                entries = manifest["entries"]
                pairs = [(e["from"], e["to"]) for e in entries]
            except (OSError, ValueError, KeyError, TypeError):
                return {"status": "blocked", "reason": REASON_MANIFEST_UNREADABLE}
            if not _inside(backup, os.path.join(store_dir, BACKUPS_DIRNAME)):
                return {"status": "blocked", "reason": REASON_BACKUP_OUTSIDE_STORE}
            restored, skipped = [], []
            for src, stored_to in pairs:
                # axis: the backed-up file is read from the folder given, by its basename alone, so a
                # moved folder still restores and a crafted `to` can name nothing outside the folder
                name = os.path.basename(stored_to) if isinstance(stored_to, str) else ""
                if not isinstance(src, str) or name in ("", ".", "..", MANIFEST_FILENAME):
                    skipped.append({"from": src, "why": "entry-invalid"})
                    continue
                dst = os.path.join(backup, name)
                # axis: a path that is present (a dangling link included) is never overwritten
                if _present(src):
                    skipped.append({"from": src, "why": "occupied"})
                    continue
                if not _present(dst):
                    skipped.append({"from": src, "why": "missing"})
                    continue
                try:
                    os.makedirs(os.path.dirname(src), exist_ok=True)
                    _staged_move(dst, src)
                except Exception as exc:
                    skipped.append({"from": src, "why": "move-failed: %s: %s"
                                    % (type(exc).__name__, exc)})
                    continue
                restored.append({"from": src, "to": dst})
            return {"status": "restored", "restored": restored, "skipped": skipped}


def _bool_word(text):
    if text not in ("true", "false"):
        raise argparse.ArgumentTypeError("expected true or false")
    return text == "true"


def _parser():
    parser = argparse.ArgumentParser(prog="leftover_settings.py", add_help=True)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("list", "retire", "restore"):
        p = sub.add_parser(name)
        p.add_argument("--cwd", required=True)
        p.add_argument("--root", default=None)
        if name == "retire":
            p.add_argument("--owner-authorized", required=True, type=_bool_word)
            p.add_argument("--list-digest", required=True)
        if name == "restore":
            p.add_argument("--backup", required=True)
    return parser


def main(argv):
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    cwd = os.path.abspath(args.cwd)
    try:
        if args.command == "list":
            result = find(cwd, args.root)
            result["notice"] = notice(result)
        elif args.command == "retire":
            result = retire(cwd, owner_authorized=args.owner_authorized,
                            list_digest=args.list_digest, root=args.root)
        else:
            result = restore(cwd, args.backup, root=args.root)
    except mode_registry.UnknownSchemaVersion as exc:
        result = {"status": "blocked", "reason": "registry-schema-newer", "detail": str(exc)}
    except store_core.RepoRootUnavailable as exc:
        result = {"status": "blocked", "reason": "repo-root-unavailable", "detail": str(exc)}
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
