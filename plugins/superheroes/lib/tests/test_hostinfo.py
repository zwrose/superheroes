# plugins/workhorse/lib/tests/test_hostinfo.py
import hostinfo


def test_boot_id_is_str_or_none_and_stable():
    a = hostinfo.boot_id()
    b = hostinfo.boot_id()
    assert a is None or (isinstance(a, str) and a)
    assert a == b   # stable within a boot
