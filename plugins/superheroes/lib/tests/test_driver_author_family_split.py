"""The driver judges a seat map against the original author, not the host-derived fix maker."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_driver as RD  # noqa: E402
import seat_map  # noqa: E402


def _split_state(author_family, host_family):
    smap = {"authorFamily": author_family, "hostFamily": host_family}
    overrides = RD._with_build_session_vendor({"seatMap": smap})
    return RD.new_state(overrides), smap


def test_split_family_keeps_original_author_for_the_driver():
    state, smap = _split_state("anthropic", "openai")
    # the fix maker is the host's vendor, but the author the map is judged against is the original
    assert RD.author_family(state) == "openai"
    assert RD._driver_author_family(state) == "anthropic"
    constraints = [v.get("constraint")
                   for v in seat_map.derived_violations(smap, RD._driver_author_family(state))]
    assert "author-family-mismatch" not in constraints


def test_same_family_host_is_unchanged():
    state, _ = _split_state("anthropic", "anthropic")
    assert RD._driver_author_family(state) == RD.author_family(state) == "anthropic"
