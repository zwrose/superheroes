# plugins/superheroes/lib/hostinfo.py
"""A portable per-boot identity. Used to corroborate that a recorded pid belongs to
THIS boot (a recycled PID after a reboot is not the same process). darwin:
`sysctl -n kern.boottime`; Linux: the `btime` line of /proc/stat. None when neither
is obtainable — callers MUST treat None as 'cannot corroborate' and degrade, never
as a match (design §8.1)."""
import subprocess


def boot_id():
    # Linux: /proc/stat carries `btime <epoch>`.
    try:
        with open("/proc/stat", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("btime "):
                    parts = line.split()
                    if len(parts) >= 2:
                        return "btime:" + parts[1]
    except OSError:
        pass
    # darwin/BSD: sysctl kern.boottime -> "{ sec = 171..., usec = ... } ..."
    try:
        r = subprocess.run(["sysctl", "-n", "kern.boottime"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return "boottime:" + r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None
