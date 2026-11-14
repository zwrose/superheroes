"""The one home of the guarded dependency-folder link a fresh checkout gets.

A fresh checkout of a commit (the native implementer's isolated worktree, a higher stack layer's clean
worktree) holds no installed dependencies, because those are untracked. ``_link_dependencies`` links the
reviewed checkout's installed dependency folders into such a copy, refusing every link that could let a test
write a tracked file of the reviewed checkout through it. Stdlib only, no sibling imports.
"""
import os

REASON_DEPENDENCY_LINK_FAILED = "dependency-link-failed"
REASON_DEPENDENCY_LINK_UNSAFE = "dependency-link-unsafe"
DEPENDENCY_DIRS = ("node_modules",)


def _scan_entries(directory):
    """The paths of every entry of ``directory`` and of each ``@``-prefixed scope directory and the ``.bin``
    directory beneath it."""
    found = []
    for name in sorted(os.listdir(directory)):
        entry = os.path.join(directory, name)
        found.append(entry)
        # axis: a ``.bin`` entry that links back into the reviewed checkout's tracked tree is scanned like a package link, so it is never linked
        if (name.startswith("@") or name == ".bin") and os.path.isdir(entry) and not os.path.islink(entry):
            found.extend(os.path.join(entry, sub) for sub in sorted(os.listdir(entry)))
    return found


def _link_dependencies(repo_root, copy, names=DEPENDENCY_DIRS):
    """Link the reviewed checkout's installed dependency directories (``names``) into ``copy``. None on success
    or when there is nothing to do, else the not-run reason."""
    root_real = os.path.realpath(repo_root)
    for name in names:
        source = os.path.join(os.path.abspath(repo_root), name)
        target = os.path.join(copy, name)
        # axis: a dependency directory the head tracks is already in the copy and is never replaced by a link
        if os.path.lexists(target) or not os.path.isdir(source):
            continue
        src_real = os.path.realpath(source)
        # axis: a dependency folder that is itself a link into another part of the reviewed checkout is never linked, so a test cannot write a tracked file through it
        if (src_real == root_real or src_real.startswith(root_real.rstrip(os.sep) + os.sep)) and src_real != os.path.join(root_real, name):
            return REASON_DEPENDENCY_LINK_UNSAFE
        try:
            for entry in _scan_entries(source):
                if not os.path.islink(entry):
                    continue
                real = os.path.realpath(entry)
                inside_root = real == root_real or real.startswith(root_real.rstrip(os.sep) + os.sep)
                inside_src = real == src_real or real.startswith(src_real.rstrip(os.sep) + os.sep)
                # axis: a package that links back into the reviewed checkout's tracked tree is never linked, so a test cannot write a tracked file through it
                if inside_root and not inside_src:
                    return REASON_DEPENDENCY_LINK_UNSAFE
            os.symlink(source, target, target_is_directory=True)
        except OSError:
            # axis: a scan or link that fails reads not-run, never a run without the dependencies
            return REASON_DEPENDENCY_LINK_FAILED
    return None
