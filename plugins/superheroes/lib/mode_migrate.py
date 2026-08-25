#!/usr/bin/env python3
# plugins/superheroes/lib/mode_migrate.py
"""Cross-mode relocation + first-push rebind engine for superheroes:configure
(CONVENTIONS §2.3/§2.4; spec FR-9/FR-10/FR-11 + UFR-1/UFR-6/UFR-10). Stdlib-only,
fail-open. Journal-based and resumable: every flip/rebind writes a migration journal so
`recover` can finish or back out an interruption. It is NOT a second crash-recovery engine —
it reuses `core_md.relocate_file` (the one relocate primitive) and records the authoritative
mode by writing `registry.json` RAW under a held lock (`_commit_registry`), never the
self-locking `mode_registry.write_registry` (which, nested in a held config_lock, would
deadlock-to-None). The reconciler keeps owning mode *recording*; this module owns the move.
"""
import argparse
import datetime
import json
import os
import shutil
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import control_plane   # noqa: E402  (sibling)
import core_md         # noqa: E402  (sibling)
import mode_registry   # noqa: E402  (sibling)
import store_core      # noqa: E402  (sibling)

# The journal filename + rebind-kind sentinel are owned by mode_registry (the lower module
# mode_registry.resolve's backfill guard also reads), so both share one source of truth.
_JOURNAL = mode_registry.MIGRATION_JOURNAL
_REBIND = mode_registry.REBIND_KIND
_CAL_BASENAMES_PRESERVE = ("core.md", "patterns.md")  # plus any <plugin>.md layer
# The definition-doc basenames — the three docs that carry §3.1 frontmatter and gates.
# This is the *classification* set: it answers "is this a definition-doc?", nothing else.
# Kept in lock-step with definition_doc.DOC_TYPES (tested); a new doc type must be added here too.
_DEFINITION_DOCS = ("spec.md", "plan.md", "tasks.md")
# Per-work-item files that are NOT definition-docs but still live in the work-item folder.
# A findings record (Exit B of discovery) carries the owner's ratification and no gates —
# it must move with the folder, and it must never be *labelled* a definition-doc (§3.3).
_WORK_ITEM_RECORDS = ("findings.md",)
# Everything a storage-mode flip relocates out of a work-item folder. This is the *movement*
# set; keep it the union, so a new work-item file is moved by being added to one of the two
# sets above rather than to a third place.
_WORK_ITEM_DOCS = _DEFINITION_DOCS + _WORK_ITEM_RECORDS


class Migration:
    """An enumerated, not-yet-applied storage-mode move. `files` is a list of
    {"src","dst","done"} dicts; machine-local bookkeeping (registry.json/config.lock/run
    state) is deliberately NOT in `files` for a flip (FR-10)."""

    def __init__(self, *, kind="flip", target=None, files=None, cwd=None, root=None,
                 remote_key=None, blocked=False, reason=""):
        self.kind = kind
        self.target = target
        self.files = files or []
        self.cwd = cwd
        self.root = root
        self.remote_key = remote_key
        self.blocked = blocked
        self.reason = reason


# --------------------------------------------------------------------------- paths


def _repo_root(cwd):
    return store_core.repo_root(cwd)


def _in_repo_cal_dir(cwd):
    return os.path.join(_repo_root(cwd), ".claude", "superheroes")


def _global_cal_dir(cwd, root):
    return os.path.join(mode_registry.project_store_dir(cwd, root), "config")


def _in_repo_docs_base(cwd):
    return os.path.join(_repo_root(cwd), "docs", "superheroes")


def _global_docs_base(cwd, root):
    return os.path.join(mode_registry.project_store_dir(cwd, root), "docs")


def _common_dir_store(cwd, root):
    base = root if root is not None else control_plane.store_root()
    return os.path.join(base, "projects", store_core.derive_identifiers(cwd)["gitdir_hash"])


def _journal_path(store_dir):
    return os.path.join(store_dir, _JOURNAL)


# --------------------------------------------------------------------------- helpers


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _read_journal(store_dir):
    return _read_json(_journal_path(store_dir))


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def active_journal(cwd, *, root=None):
    """The migration journal at the ACTIVE config_key store, or None. (recover scans both
    the active store and the rebind-invariant common-dir store; this only reads the active one.)"""
    return _read_journal(mode_registry.project_store_dir(cwd, root))


def _commit_registry(cwd, target, remote_key, root=None):
    """Write registry.json RAW under a lock the CALLER already holds — never via the
    self-locking mode_registry.write_registry (nested config_lock → None). Preserves an
    existing createdAt. Returns True, or False on an unwritable store (UFR-6 abort signal)."""
    try:
        existing = mode_registry.read_registry(cwd, root)
        created = (existing["createdAt"] if existing and isinstance(existing.get("createdAt"), str)
                   and existing.get("createdAt") else _utc_now())
        rec = {"schemaVersion": mode_registry.SCHEMA_VERSION, "storageMode": target,
               "remoteKey": remote_key, "createdAt": created}
        store_core.atomic_write(mode_registry.registry_path(cwd, root), json.dumps(rec, indent=2))
        return True
    except (OSError, store_core.RepoRootUnavailable):
        return False


# --------------------------------------------------------------------------- plan / preview


def _enumerate(src_cal_dir, dst_cal_dir, src_docs_base, dst_docs_base):
    files = []
    if os.path.isdir(src_cal_dir):
        for name in sorted(os.listdir(src_cal_dir)):
            if name.endswith(".md"):
                files.append({"src": os.path.join(src_cal_dir, name),
                              "dst": os.path.join(dst_cal_dir, name), "done": False})
    if os.path.isdir(src_docs_base):
        for wi in sorted(os.listdir(src_docs_base)):
            wdir = os.path.join(src_docs_base, wi)
            if not os.path.isdir(wdir):
                continue
            for doc in _WORK_ITEM_DOCS:
                p = os.path.join(wdir, doc)
                if os.path.isfile(p):
                    files.append({"src": p,
                                  "dst": os.path.join(dst_docs_base, wi, doc), "done": False})
    return files


def plan(cwd, target_mode, *, root=None, owner_authorized):
    """Enumerate a flip to target_mode. Refuses without owner authorization (FR-14). Records
    cwd/root/remote_key on the Migration so execute()/recover() need no extra params."""
    if not owner_authorized:
        return Migration(blocked=True,
                         reason="storage migration requires owner authorization (FR-14)",
                         cwd=cwd, root=root, target=target_mode)
    current = mode_registry.resolve(cwd, root)["mode"]
    in_cal, gl_cal = _in_repo_cal_dir(cwd), _global_cal_dir(cwd, root)
    in_docs, gl_docs = _in_repo_docs_base(cwd), _global_docs_base(cwd, root)
    if current == mode_registry.IN_REPO:
        files = _enumerate(in_cal, gl_cal, in_docs, gl_docs)
    else:
        files = _enumerate(gl_cal, in_cal, gl_docs, in_docs)
    remote_key = store_core.derive_identifiers(cwd)["remote_hash"]
    return Migration(kind="flip", target=target_mode, files=files,
                     cwd=cwd, root=root, remote_key=remote_key)


def _is_calibration(path):
    b = os.path.basename(path)
    return b in _CAL_BASENAMES_PRESERVE or (b.endswith(".md") and b not in _WORK_ITEM_DOCS)


def _is_definition_doc(path):
    return os.path.basename(path) in _DEFINITION_DOCS


def preview(migration):
    """The plain-language 'exactly what will move' summary FR-10 requires before any confirm.
    Enumerates calibration, definition-docs, and non-definition-doc work-item records, with a
    one-line collaborator-visibility disclosure."""
    calibration, def_docs, work_item_records = [], [], []
    for f in migration.files:
        src = f["src"]
        if _is_calibration(src):
            calibration.append(src)
        elif _is_definition_doc(src):
            def_docs.append(src)
        else:
            work_item_records.append(src)
    if migration.target == mode_registry.IN_REPO:
        disclosure = ("Switching to repo-shared publishes the calibration, every definition "
                      "document, AND every work-item record (a discovery findings record "
                      "carries the owner's ratification) into the repo — visible to "
                      "collaborators.")
    else:
        disclosure = ("Switching to out-of-repo moves the calibration, the definition documents "
                      "and the work-item records out of the repo — the repo stays pristine.")
    return {"target": migration.target, "calibration": calibration,
            "definitionDocs": def_docs, "workItemRecords": work_item_records,
            "disclosure": disclosure}


# --------------------------------------------------------------------------- execute


def execute(migration, *, root=None):
    """Relocation as a working-tree move with one atomic commit point (the raw registry flip).
    journal → copy → commit → delete, all under config_lock. Aborts before any delete if the
    registry write fails (UFR-6). Returns {"status": "done"|"blocked"|"busy"}."""
    cwd = migration.cwd
    root = root if root is not None else migration.root
    if mode_registry.ensure_project_store(cwd, root) is None:
        return {"status": "blocked"}
    store_dir = mode_registry.project_store_dir(cwd, root)
    with mode_registry.config_lock(cwd, root) as got:
        if not got:
            return {"status": "busy"}
        jpath = _journal_path(store_dir)
        journal = {"kind": "flip", "target": migration.target, "phase": "copying",
                   "files": [{"src": f["src"], "dst": f["dst"], "done": False}
                             for f in migration.files]}
        store_core.atomic_write(jpath, json.dumps(journal, indent=2))
        for f in journal["files"]:
            with open(f["src"], encoding="utf-8") as fh:
                store_core.atomic_write(f["dst"], fh.read())
            f["done"] = True
        journal["phase"] = "committing"
        store_core.atomic_write(jpath, json.dumps(journal, indent=2))
        if not _commit_registry(cwd, migration.target, migration.remote_key, root):
            # abort before any delete (UFR-6): remove copied dsts, leave sources, clear journal
            for f in journal["files"]:
                if f["done"]:
                    _remove(f["dst"])
            _remove(jpath)
            return {"status": "blocked"}
        journal["phase"] = "deleting"
        store_core.atomic_write(jpath, json.dumps(journal, indent=2))
        for f in journal["files"]:
            _remove(f["src"])
        _remove(jpath)
        return {"status": "done"}


# --------------------------------------------------------------------------- recover


def _finish_flip(files):
    for f in files:
        if not os.path.exists(f["src"]):
            continue                      # source already gone — nothing to finish
        if os.path.exists(f["dst"]):
            os.remove(f["src"])           # dst already present — just drop the source
        else:
            core_md.relocate_file(f["src"], f["dst"])  # the one relocate primitive (copy + unlink)


def _backout_flip(files):
    for f in files:
        _remove(f["dst"])  # sources untouched


def recover(cwd, *, root=None):
    """Run first on every configure run. Detect a half-finished flip/rebind journal (scanning
    BOTH the active config_key store and the rebind-invariant common-dir store) and finish or
    back out to one consistent state. Idempotent; with no journal → noop (UFR-1/UFR-10).

    On a REAL run (no explicit root override) it first settles the one-time store-root rename
    (#121 Part B) — auto-migrating ~/.claude/workhorse → ~/.claude/superheroes before any store
    path is computed. Gated on `root is None` so the test suite (which always passes an explicit
    tmp root) never moves the real store; best-effort so it never blocks recovery. A FAILED rename
    is surfaced to stderr rather than silently swallowed (/code-review #7)."""
    if root is None:
        try:
            res = control_plane.migrate_store_root()
            if res.get("reason") == "failed":
                sys.stderr.write("superheroes: store-root migration deferred (%s) — back-compat "
                                 "resolution still active\n" % res.get("detail", "unknown error"))
        except Exception:
            pass
    active_dir = mode_registry.project_store_dir(cwd, root)
    common_dir = _common_dir_store(cwd, root)
    for store_dir in dict.fromkeys([active_dir, common_dir]):
        journal = _read_journal(store_dir)
        if journal is None:
            continue
        kind = journal.get("kind")
        jpath = _journal_path(store_dir)
        if kind == _REBIND:
            # An interrupted rebind: the store may be half-moved. Re-run the rebind to converge
            # (it is idempotent / merge-based and clears its own journal on success). Do NOT
            # pre-delete the journal — if the re-run can't complete (busy lock, or an
            # owner-decision conflict), the journal must survive so the next run can retry
            # (UFR-10). Only a terminal rebound/noop counts as recovered; anything else is
            # surfaced honestly with the journal left in place.
            res = rebind(cwd, root=root)
            status = res.get("status")
            if status in ("rebound", "noop"):
                return {"status": "recovered", "rebind": status}
            return {"status": status, "rebind": status, "detail": res.get("detail")}
        # flip
        with mode_registry.config_lock(cwd, root) as got:
            if not got:
                return {"status": "busy"}
            target = journal.get("target")
            files = journal.get("files", [])
            if mode_registry.resolve(cwd, root)["mode"] == target:
                _finish_flip(files)        # commit landed → finish the move
            else:
                _backout_flip(files)       # pre-commit → back out
            _remove(jpath)
            return {"status": "recovered"}
    return {"status": "noop"}


# --------------------------------------------------------------------------- rebind


def _merge_move(src_dir, dst_dir, _prefix=""):
    """Move src_dir's entries into dst_dir, merging: a missing dst entry is moved; a dir
    collision recurses; any other collision (file-vs-file, or a file-vs-dir type mismatch)
    keeps the dst (remote-keyed) copy — no clobber (FR-9). Returns the list of relative paths
    kept on the destination on a collision, so the caller can surface a merge that did NOT move
    everything (the src copy is left under the old key — nothing is silently stranded)."""
    os.makedirs(dst_dir, exist_ok=True)
    kept = []
    for name in os.listdir(src_dir):
        if name in (_JOURNAL, "config.lock"):
            continue
        src = os.path.join(src_dir, name)
        dst = os.path.join(dst_dir, name)
        rel = os.path.join(_prefix, name) if _prefix else name
        if not os.path.exists(dst):
            shutil.move(src, dst)
        elif os.path.isdir(src) and os.path.isdir(dst):
            kept += _merge_move(src, dst, rel)
        else:
            kept.append(rel)   # collision — kept the existing dst (no clobber, FR-9)
    return kept


def rebind(cwd, *, root=None):
    """FR-9 first-push re-keying: move the whole <common-dir-key> project store to the
    <remote-key> store (registry.json travels), merge, and surface a value conflict rather than
    clobber. Locked + journalled at the rebind-invariant <common-dir-key> so an interruption is
    recoverable regardless of the now-changed active config_key (UFR-10). Takes no `interactive`
    flag (unlike the destructive flip's plan/execute, which refuse unattended): a rebind is a
    mechanical re-key that runs even headless, and its one owner-decision part — a value conflict
    — is surfaced (applied=False) regardless of mode, satisfying FR-9 + FR-17 in both."""
    ident = store_core.derive_identifiers(cwd)
    rk, gh = ident["remote_hash"], ident["gitdir_hash"]
    if rk is None or rk == gh:
        return {"status": "noop"}
    base = root if root is not None else control_plane.store_root()
    common_dir = os.path.join(base, "projects", gh)
    remote_dir = os.path.join(base, "projects", rk)
    if not os.path.isdir(common_dir):
        return {"status": "noop"}      # nothing under the pre-remote key to rebind
    os.makedirs(common_dir, exist_ok=True)
    with mode_registry.config_lock_at(common_dir) as got:
        if not got:
            return {"status": "busy"}
        common_reg = _read_json(os.path.join(common_dir, "registry.json"))
        remote_reg = _read_json(os.path.join(remote_dir, "registry.json"))
        # Conflict check FIRST — before writing a journal or moving anything. A disagreement
        # is surfaced for the owner with the store left wholly untouched (FR-9); no journal is
        # written, so nothing needs recovery. (A journal stranded by an EARLIER interrupted
        # run, if any, is left in place so the next run retries once the conflict is resolved.)
        if (remote_reg is not None and common_reg is not None
                and remote_reg.get("storageMode") != common_reg.get("storageMode")):
            return {"status": "conflict", "applied": False,
                    "detail": {"common": common_reg.get("storageMode"),
                               "remote": remote_reg.get("storageMode")}}
        jpath = _journal_path(common_dir)
        store_core.atomic_write(jpath, json.dumps(
            {"kind": _REBIND, "phase": "copying", "files": []}, indent=2))
        kept = _merge_move(common_dir, remote_dir)
        # re-establish registry.json under the remote key (config_key is now remote_hash)
        target = (common_reg or remote_reg or {}).get("storageMode") \
            or mode_registry.resolve(cwd, root)["mode"]
        if not _commit_registry(cwd, target, rk, root):
            # the store moved but the mode record could not be written — leave the journal so
            # the next run's recover retries the (idempotent) rebind rather than reporting success
            return {"status": "deferred"}
        _remove(jpath)
        res = {"status": "rebound"}
        if kept:
            # the remote store already had these entries — kept them (no clobber, FR-9); the
            # owner is told so they know the merge did not move everything.
            res["keptExisting"] = kept
        return res


# --------------------------------------------------------------------------- CLI


def _b(v):
    return str(v).lower() in ("1", "true", "yes")


def main(argv):
    ap = argparse.ArgumentParser(prog="mode_migrate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("recover", "plan", "preview", "execute", "rebind"):
        sp = sub.add_parser(name)
        sp.add_argument("--cwd", default=".")
        sp.add_argument("--root", default=None)
        if name in ("plan", "preview", "execute"):
            sp.add_argument("--target", choices=(mode_registry.IN_REPO, mode_registry.GLOBAL),
                            required=True)
            sp.add_argument("--owner-authorized", default="false")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "recover":
            out = recover(args.cwd, root=args.root)
        elif args.cmd == "rebind":
            out = rebind(args.cwd, root=args.root)
        else:
            m = plan(args.cwd, args.target, root=args.root,
                     owner_authorized=_b(args.owner_authorized))
            if args.cmd == "plan":
                out = {"kind": m.kind, "target": m.target, "blocked": m.blocked,
                       "reason": m.reason, "files": m.files}
            elif args.cmd == "preview":
                out = ({"blocked": True, "reason": m.reason} if m.blocked else preview(m))
            else:  # execute
                out = ({"status": "blocked", "reason": m.reason} if m.blocked
                       else execute(m, root=args.root))
    except Exception as exc:  # fail-open like core_md.main — never crash a consumer
        out = {"status": "error", "detail": str(exc)}
    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
