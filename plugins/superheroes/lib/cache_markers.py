#!/usr/bin/env python3
"""Sweep stale `.in_use/<pid>` session markers from a plugin install cache dir."""
import os
import re
import stat
import time

# \Z not $ — $ also matches before a trailing newline; this regex feeds the deleting sweep.
_PID_NAME_RE = re.compile(r"^([0-9]+)(?:\.tmp\.[0-9a-fA-F]+)?\Z")
_VERSION_DIR_RE = re.compile(r"^[0-9]+(\.[0-9]+)*\Z")
SIBLING_SCAN_DIR_LIMIT = 64
SIBLING_IN_USE_ENTRY_LIMIT = 256
_STAT = os.stat
_UNLINK = os.unlink


def cache_parent(plugin_root):
    """The plugin-cache dir that holds sibling version dirs — ONE definition, so the
    bootstrap's hint and the sibling scan can never disagree about where it is."""
    return os.path.dirname(os.path.abspath(plugin_root or "."))


def _marker_pid(name):
    """Parse a ``.in_use`` entry basename into a PID, or ``None`` if it is not a marker name."""
    m = _PID_NAME_RE.match(name)
    if not m:
        return None
    try:
        pid = int(m.group(1))
    except ValueError:
        return None
    if pid == 0:
        return None
    return pid


def _marker_is_dead(st, pid, now, grace_seconds):
    """``st`` MUST come from a ``follow_symlinks=False`` stat — the ``S_ISREG`` check is the symlink guard for the deleting sweep."""
    if not stat.S_ISREG(st.st_mode):
        return False
    if now - st.st_mtime < grace_seconds:
        return False
    try:
        os.kill(pid, 0)
        return False
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    except OSError:
        return False


def _stale_marker_count(in_use_path, now, grace_seconds):
    """Count provably-dead stale markers under in_use_path. Read-only; never deletes."""
    count = 0
    try:
        with os.scandir(in_use_path) as it:
            examined = 0
            while examined < SIBLING_IN_USE_ENTRY_LIMIT:
                try:
                    entry = next(it)
                except StopIteration:
                    break
                except OSError:
                    return count
                examined += 1
                name = entry.name
                try:
                    pid = _marker_pid(name)
                    if pid is None:
                        continue

                    marker_path = os.path.join(in_use_path, name)
                    st = os.stat(marker_path, follow_symlinks=False)
                    if _marker_is_dead(st, pid, now, grace_seconds):
                        count += 1
                except Exception:
                    continue
    except OSError:
        return 0
    return count


def scan_stale_siblings(plugin_root, now=None, grace_seconds=3600):
    """READ-ONLY sibling scan: which other plugin-version dirs hold stale `.in_use`
    markers. Deletes NOTHING — ever. Returns {"dirs": [name, ...], "markers": int}.
    NEVER raises; on any error returns the empty result."""
    empty = {"dirs": [], "markers": 0}
    try:
        if os.environ.get("SUPERHEROES_NO_CACHE_SWEEP", ""):
            return empty

        root = os.path.abspath(plugin_root or ".")
        parent = cache_parent(plugin_root)
        running_name = os.path.basename(root)

        if not os.path.isdir(parent):
            return empty

        if now is None:
            now = time.time()

        dirs_with_stale = []
        total_markers = 0

        try:
            scandir_it = os.scandir(parent)
        except OSError:
            return empty

        with scandir_it:
            examined_siblings = 0
            while examined_siblings < SIBLING_SCAN_DIR_LIMIT:
                try:
                    entry = next(scandir_it)
                except StopIteration:
                    break
                examined_siblings += 1
                name = entry.name
                if name == running_name:
                    continue
                if not _VERSION_DIR_RE.match(name):
                    continue
                sibling_path = entry.path
                if entry.is_symlink():
                    continue
                if not entry.is_dir(follow_symlinks=False):
                    continue

                in_use_path = os.path.join(sibling_path, ".in_use")
                if not os.path.exists(in_use_path):
                    continue
                if os.path.islink(in_use_path):
                    continue
                if not os.path.isdir(in_use_path):
                    continue

                n = _stale_marker_count(in_use_path, now, grace_seconds)
                if n > 0:
                    dirs_with_stale.append(name)
                    total_markers += n

        return {"dirs": sorted(dirs_with_stale), "markers": total_markers}
    except Exception:
        return empty


def sweep_stale(plugin_root, now=None, grace_seconds=3600):
    """Remove <plugin_root>/.in_use/<pid> markers whose PID is provably dead. Returns the
    number removed. NEVER raises.

    Set environment variable ``SUPERHEROES_NO_CACHE_SWEEP`` to any non-empty value to skip
    the sweep (returns 0 without touching the filesystem)."""
    try:
        if os.environ.get("SUPERHEROES_NO_CACHE_SWEEP", ""):
            return 0

        if _UNLINK not in os.supports_dir_fd or _STAT not in os.supports_dir_fd:
            return 0

        in_use_path = os.path.join(plugin_root, ".in_use")

        if not os.path.exists(in_use_path):
            return 0

        if os.path.islink(in_use_path):
            return 0

        if not os.path.isdir(in_use_path):
            return 0

        dir_fd = os.open(in_use_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if now is None:
                now = time.time()

            try:
                names = os.listdir(dir_fd)
            except OSError:
                return 0

            removed = 0
            for name in names:
                try:
                    pid = _marker_pid(name)
                    if pid is None:
                        continue

                    st = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
                    if not _marker_is_dead(st, pid, now, grace_seconds):
                        continue

                    ino, dev = st.st_ino, st.st_dev
                    try:
                        st2 = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
                    except OSError:
                        continue
                    if st2.st_ino != ino or st2.st_dev != dev:
                        continue

                    try:
                        os.unlink(name, dir_fd=dir_fd)
                        removed += 1
                    except OSError:
                        pass
                except Exception:
                    continue
            return removed
        finally:
            os.close(dir_fd)
    except Exception:
        return 0
