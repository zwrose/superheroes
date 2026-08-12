# plugins/superheroes/lib/hostinfo.py
"""A portable per-boot identity. Used to corroborate that a recorded pid belongs to
THIS boot (a recycled PID after a reboot is not the same process). darwin:
`sysctl -n kern.boottime`; Linux: the `btime` line of /proc/stat. None when neither
is obtainable — callers MUST treat None as 'cannot corroborate' and degrade, never
as a match (design §8.1).

Two reads of the SAME boot must compare equal, so boot ids are compared through
`same_boot`, never with `==` (#953): darwin renders `kern.boottime` as
`{ sec = S, usec = U } <date>` and the `usec` leg has been observed to shift between
reads of one boot, which made a live holder look rebooted."""
import re
import subprocess
import time

_UNSET = object()
_boot_id_cache = _UNSET
_boot_id_fail_until = 0.0
_NEGATIVE_CACHE_SECONDS = 60

# `sec = 1786231679` from a rendered kern.boottime. The lookbehind is what keeps
# this off the `usec = ...` leg, whose value is exactly what must not be compared.
_BOOTTIME_SEC_RE = re.compile(r"(?<![0-9a-z])sec\s*[=:]\s*(\d+)")


def boot_id():
    global _boot_id_cache, _boot_id_fail_until
    if _boot_id_cache is not _UNSET:
        return _boot_id_cache
    if time.monotonic() < _boot_id_fail_until:
        return None
    # Linux: /proc/stat carries `btime <epoch>`.
    try:
        with open("/proc/stat", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("btime "):
                    parts = line.split()
                    if len(parts) >= 2:
                        _boot_id_cache = "btime:" + parts[1]
                        return _boot_id_cache
    except OSError:
        pass
    # darwin/BSD: sysctl kern.boottime -> "{ sec = 171..., usec = ... } ..."
    try:
        r = subprocess.run(["sysctl", "-n", "kern.boottime"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            _boot_id_cache = _normalize("boottime:" + r.stdout.strip())
            return _boot_id_cache
    except (OSError, subprocess.SubprocessError):
        pass
    _boot_id_fail_until = time.monotonic() + _NEGATIVE_CACHE_SECONDS
    return None


def _normalize(value):
    """Fold a boot id to the form that is stable across reads of one boot.

    A rendered `kern.boottime` carries a `usec` leg and a human-readable date that can
    differ between two reads of the same boot; only the whole-second `sec` leg is
    comparable. Normalizing on the way OUT (what `boot_id` records) and again on the way
    IN (what `same_boot` reads back) is what keeps a lock file written by an older
    version, carrying the full rendered string, comparable to a freshly read id.
    Anything this does not recognize — Linux `btime:`, an unexpected render — is
    returned unchanged, so it still compares exactly.
    """
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    if value.startswith("boottime:"):
        m = _BOOTTIME_SEC_RE.search(value)
        if m:
            return "boottime:sec:" + m.group(1)
    return value


def same_boot(recorded, current):
    """Tri-state: True same boot, False a different boot, None cannot corroborate.

    None whenever either side is missing or unusable — callers MUST degrade on None,
    never read it as a match (design §8.1). Compare boot ids through this, never with
    `==`: `==` on two reads of one boot can be False (#953)."""
    a, b = _normalize(recorded), _normalize(current)
    if a is None or b is None:
        return None
    return a == b
