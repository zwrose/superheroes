"""Census: no direct gate-config ``.status`` comparisons outside ``core_md.py``.

Adding a new ``engine_preferences_for_gate`` status must go through the ``core_md`` chokepoint
(``gate_config_refusal``, ``gate_config_is_refusal``, ``gate_config_is_absent``,
``gate_config_usable_prefs``) — never a bare ``cfg.status == CONFIG_*`` check in a consumer."""
import os
import re

_LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
_STATUS_CMP = re.compile(
    r"\.status\s*==\s*(?:core_md\.)?CONFIG_[A-Z_]+",
)

# Legitimate allowlist — each entry is ``<filename>:<line>`` with a one-line justification.
_ALLOWLIST = frozenset()


def _gate_status_comparisons_outside_core_md():
    hits = []
    for name in sorted(os.listdir(_LIB)):
        if not name.endswith(".py") or name == "core_md.py":
            continue
        path = os.path.join(_LIB, name)
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                if _STATUS_CMP.search(line):
                    key = "%s:%d" % (name, lineno)
                    if key not in _ALLOWLIST:
                        hits.append("%s:%d: %s" % (name, lineno, line.rstrip()))
    return hits


def test_no_direct_gate_status_comparisons_outside_core_md():
    hits = _gate_status_comparisons_outside_core_md()
    assert hits == [], (
        "Direct gate-config .status comparisons found outside core_md.py — "
        "use the core_md chokepoint (gate_config_refusal / gate_config_is_refusal / "
        "gate_config_is_absent / gate_config_usable_prefs) instead:\n"
        + "\n".join(hits)
    )
