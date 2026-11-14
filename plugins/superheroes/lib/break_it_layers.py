"""The break-it kept check across the layers above the reviewed one in a stack (#2463).

A break-it run happens in the session's own working copy (``break_it`` holds no checkout or link machinery:
FR-50). A higher stack layer's head is not that working copy, so searching the layers above the reviewed one
lives here: each layer is checked out clean (a detached worktree outside every repository), gets the reviewed
checkout's installed dependency folders through the one guarded link (``dependency_links``), and is run through
``break_it.check_kept``. Every ``break_it`` name is read through the module at call time, never imported by
name, so a test that patches ``break_it`` reaches this code too.
"""
import hashlib
import os
import re
import uuid

import break_it
import dependency_links

NOT_RUN = "not-run"  # a layer ``searched`` outcome only (never a ``check_kept`` outcome): the test could not run there
REASON_DEPENDENCY_MISSING = "dependency-missing:"

_HEX40 = re.compile(r"[0-9a-f]{40}")


def _layer_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _layer_valid(layer):
    if not isinstance(layer, dict):
        return False
    oid, ref = layer.get("headRefOid"), layer.get("headRefName")
    return (isinstance(oid, str) and bool(_HEX40.fullmatch(oid.lower()))
            and isinstance(ref, str) and bool(ref) and not ref.startswith("-")
            and _layer_int(layer.get("position")) and _layer_int(layer.get("number")))


def _layer_present(repo_root, layer):
    """Whether the layer's exact commit is in the repository, fetched from origin by branch when it is not."""
    oid = layer["headRefOid"]
    if break_it._git(repo_root, "cat-file", "-e", oid + "^{commit}").returncode == 0:
        return True
    break_it._git(repo_root, "fetch", "--no-tags", "--quiet", "origin", layer["headRefName"])
    return break_it._git(repo_root, "cat-file", "-e", oid + "^{commit}").returncode == 0


def _layer_remove(repo_root, path):
    try:
        if break_it._git(repo_root, "worktree", "remove", "--force", path).returncode != 0:
            break_it._remove_folder(path)
            break_it._git(repo_root, "worktree", "prune")
    except Exception:  # a failed removal never changes the result
        pass


def _extra_name(interpreter):
    """The interpreter's own folder to link: the first path component of a relative interpreter of more than one
    component, after any leading ``./`` (``.venv`` for ``.venv/bin/python`` and ``./.venv/bin/python``), else None
    (a bare name, an absolute path, ``..`` first, no interpreter)."""
    value = interpreter[0] if isinstance(interpreter, list) and interpreter else interpreter
    if not isinstance(value, str) or not value or os.path.isabs(value):
        return None
    # axis: a harmless leading ./ is stripped before the first folder is read, so ./.venv/bin/python links .venv — see bite-proof record wo_e_2463_layer_dependencies
    parts = [part for part in value.replace(os.sep, "/").split("/") if part and part != "."]
    if len(parts) < 2 or parts[0] == "..":
        return None
    return parts[0]


def _held(repo_root, oid, record):
    """Whether the layer commit holds a regular blob at the record's exact path whose bytes hash to the record's
    sha256. A git read that fails reads False, never True."""
    try:
        path, sha = record.get("path"), record.get("sha256")
        if not isinstance(path, str) or not path or not isinstance(sha, str) or break_it._path_unsafe(path):
            return False
        tree = break_it._git(repo_root, "ls-tree", "-z", oid, "--", path)
        if tree.returncode != 0:
            return False
        entry = tree.stdout.decode("utf-8", errors="replace").split("\0", 1)[0]
        head, _, name = entry.partition("\t")
        meta = head.split()
        if name != path or len(meta) != 3 or meta[0] not in break_it._REGULAR_MODES or meta[1] != "blob":
            return False
        blob = break_it._git(repo_root, "cat-file", "blob", meta[2])
        return blob.returncode == 0 and hashlib.sha256(blob.stdout).hexdigest() == sha
    except Exception:
        return False


def check_kept_in_layers(repo_root, base, layers, record, *, runner=break_it.run_one, interpreter=break_it._UNSET,
                         scratch=None):
    """Whether a break-it test missing from the reviewed head is kept in a layer ABOVE it in the stack.
    ``layers`` is the layers above the reviewed one, lowest first, each ``{"position", "number", "headRefName",
    "headRefOid"}``; each is checked out clean (a detached worktree outside every repository), gets the reviewed
    checkout's installed dependency folders linked in, and is run through ``check_kept``. Returns
    ``{"read": "ok"|"failed", "reason", "foundIn", "result", "searched"}``; never raises. A ``searched`` entry
    carries the layer's ``outcome`` (a ``check_kept`` outcome, or ``not-run`` when a needed dependency folder
    was missing or would not link, with ``held`` saying whether the layer holds the exact test), its ``reason``
    and the ``runOutcome`` of the run, if any."""
    searched = []

    def out(read, reason=None, found=None, result=None):
        return {"read": read, "reason": reason, "foundIn": found, "result": result, "searched": searched}

    try:
        # axis: a layer list that is not a list, or an entry without a full commit id, a safe branch name and int position/number, fails the read — see bite-proof record wo_a_2463_stack_layers
        if not isinstance(layers, list) or not all(_layer_valid(layer) for layer in layers):
            return out("failed", "layer-malformed")
        for layer in layers:
            oid = layer["headRefOid"]
            # axis: a layer head absent after the fetch fails the read, never reads as not held there — see bite-proof record wo_a_2463_stack_layers
            if not _layer_present(repo_root, layer):
                return out("failed", "layer-head-unreadable")
            folder, why = break_it._scratch_folder(repo_root, scratch)
            if why:
                return out("failed", "scratch-unresolved")
            path = os.path.join(folder, "break-it-layer-" + uuid.uuid4().hex)
            names = dependency_links.DEPENDENCY_DIRS
            before = {}
            skipped = None
            got = None
            try:
                if break_it._git(repo_root, "worktree", "add", "--detach", "--quiet", path, oid).returncode != 0:
                    return out("failed", "layer-checkout-failed")
                extra = _extra_name(interpreter)
                if extra:
                    names = names + (extra,)
                # axis: a needed interpreter folder present neither in the layer checkout nor in the reviewed checkout means the layer's test is not run and not credited, never run under a missing interpreter — see bite-proof record wo_e_2463_layer_dependencies
                if (extra and not os.path.lexists(os.path.join(path, extra))
                        and not os.path.isdir(os.path.join(repo_root, extra))):
                    skipped = REASON_DEPENDENCY_MISSING + extra
                else:
                    before = {name: os.path.lexists(os.path.join(path, name)) for name in names}
                    # axis: the reviewed checkout's installed dependency folders (and the interpreter's own folder) are linked into the layer checkout through the one guarded helper before the test runs, so a layer is not judged without the dependencies — see bite-proof record wo_e_2463_layer_dependencies
                    skipped = dependency_links._link_dependencies(repo_root, path, names=names)
                if not skipped:
                    got = break_it.check_kept(path, base, oid, record, runner=runner, interpreter=interpreter,
                                              scratch=scratch)
            finally:
                # axis: the links this layer created are removed on every exit path before its worktree is, so a removal never reaches the reviewed checkout's folders through a link — see bite-proof record wo_e_2463_layer_dependencies
                for name, existed in before.items():
                    target = os.path.join(path, name)
                    if not existed and os.path.islink(target):
                        try:
                            os.unlink(target)
                        except OSError:
                            pass
                _layer_remove(repo_root, path)
            if skipped:
                searched.append({"position": layer["position"], "pr": layer["number"], "commit": oid,
                                 "outcome": NOT_RUN, "reason": skipped, "held": _held(repo_root, oid, record),
                                 "runOutcome": None})
                continue
            run = got.get("run")
            searched.append({"position": layer["position"], "pr": layer["number"], "commit": oid,
                             "outcome": got["outcome"], "reason": got["reason"],
                             "runOutcome": run.get("outcome") if isinstance(run, dict) else None})
            # axis: only a kept result credits a layer; a changed, failing or not-regular copy is not the test held — see bite-proof record wo_a_2463_stack_layers
            if got["outcome"] == break_it.KEPT:
                found = {"position": layer["position"], "pr": layer["number"],
                         "branch": layer["headRefName"], "commit": oid}
                return out("ok", None, found, got)
            # axis: a layer whose git read failed ends the search as failed, so no later layer is credited over an unread one — see bite-proof record wo_a_2463_stack_layers
            if got["outcome"] == break_it.KEPT_UNRESOLVED:
                return out("failed", "layer-read-failed:" + str(got["reason"]))
        return out("ok")
    # axis: the search never raises; any error reads as a failed stack read, never a credit — see bite-proof record wo_a_2463_stack_layers
    except Exception:
        return out("failed", "layer-search-error")
