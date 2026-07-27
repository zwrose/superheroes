#!/usr/bin/env python3
"""Sweep stale `.in_use/<pid>` session markers from a plugin install cache dir."""
import os
import re
import stat
import time

_PID_NAME_RE = re.compile(r"^([0-9]+)(?:\.tmp\.[0-9a-fA-F]+)?$")
_STAT = os.stat
_UNLINK = os.unlink


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
                    m = _PID_NAME_RE.match(name)
                    if not m:
                        continue
                    try:
                        pid = int(m.group(1))
                    except ValueError:
                        continue
                    if pid == 0:
                        continue

                    st = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
                    if not stat.S_ISREG(st.st_mode):
                        continue

                    if now - st.st_mtime < grace_seconds:
                        continue

                    try:
                        os.kill(pid, 0)
                        continue
                    except ProcessLookupError:
                        pass
                    except PermissionError:
                        continue
                    except OSError:
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
