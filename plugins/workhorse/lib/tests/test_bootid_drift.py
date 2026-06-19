"""Anti-drift guard: the vendored boot-id probe must behave IDENTICALLY to its source.

CONVENTIONS §4.4's per-boot identity lives in workhorse's `hostinfo.boot_id` (the
canonical source). test-pilot CANNOT import workhorse, so `test-pilot/lib/lock._boot_id`
is a vendored copy with a "keep in sync" note. This test makes that vendoring SAFE
(mirroring the eval/lib/identifiers ↔ the-architect/lib/identifiers drift guard): both
functions query the SAME OS, so on this machine they MUST return the same value — if the
parse logic (the `/proc/stat btime` line or the `sysctl kern.boottime` fallback) ever
drifts between the copies, the two locks would disagree about holder-liveness and this
test fails loudly.

The two functions live in modules that collide on basename (`lock`), so we load them
from explicit paths under distinct names rather than importing.
"""
import importlib.util
import os

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def _load(rel_path, mod_name):
    path = os.path.join(_REPO_ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SOURCE = _load("plugins/workhorse/lib/hostinfo.py", "wh_hostinfo_bootid")
VENDORED = _load("plugins/test-pilot/lib/lock.py", "tp_lock_bootid")


def test_bootid_vendored_copy_behaves_identically():
    # Same machine, same OS probe -> identical value (or both None). Divergence = drift.
    assert SOURCE.boot_id() == VENDORED._boot_id()


def test_bootid_is_str_or_none_and_stable():
    a = SOURCE.boot_id()
    b = VENDORED._boot_id()
    assert a is None or (isinstance(a, str) and a)
    assert b is None or (isinstance(b, str) and b)
    assert SOURCE.boot_id() == SOURCE.boot_id()        # stable within a boot
    assert VENDORED._boot_id() == VENDORED._boot_id()
