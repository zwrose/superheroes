"""Shared source-scan helpers for config-key access guards in lib tests."""
import re

_KEY_CAPTURE = r'[^\'"]+'


def _obj(obj_names):
    return r'(?:%s)' % obj_names


def _quoted_key(key):
    if key is None:
        return r'[\'"](%s)[\'"]' % _KEY_CAPTURE
    return r'[\'"]%s[\'"]' % re.escape(key)


def _get_patterns(obj_names, key=None):
    obj = _obj(obj_names)
    qk = _quoted_key(key)
    yield r'%s\.get\s*\(\s*%s\s*(?:,|\))' % (obj, qk)


def _subscript_patterns(obj_names, key=None):
    obj = _obj(obj_names)
    qk = _quoted_key(key)
    yield r'%s\[%s\]' % (obj, qk)


def _all_patterns(obj_names, key=None):
    yield from _get_patterns(obj_names, key)
    yield from _subscript_patterns(obj_names, key)


def source_obj_access_keys(source, obj_names):
    """Keys read via .get(...) or [...] on the named object(s) in *source*."""
    keys = set()
    for pat in _all_patterns(obj_names, key=None):
        keys.update(m.group(1) for m in re.finditer(pat, source, re.DOTALL))
    return keys


def source_obj_accesses_key(source, obj_names, key):
    """True when *source* reads *key* from the named object(s)."""
    for pat in _all_patterns(obj_names, key=key):
        if re.search(pat, source, re.DOTALL):
            return True
    return False
