"""§11 drift guard: review-code path tables ↔ round_records / round_driver builders.

Copy-holders (CONVENTIONS §11.2):
  - plugins/superheroes/skills/review-code/SKILL.md — emitted-order path table
  - plugins/superheroes/skills/review-code/reference/round-driver.md — order + landing +
    durable-record tables
Authoritative homes (code builders, derived at runtime — never retyped as literals):
  - round_records.order_prompt_path
  - round_records.envelope_stub_path
  - round_records.landing_path
  - round_records.bare_payload_path
  - round_driver._orders_manifest_path
  - round_records.dispatch_manifest_path
  - round_records.canary_path
  - round_records.store_path
  - round_records.head_diff_store_path
  - round_adapters.missing_policy (refuse-fold phase recovery row)
"""
import os
import re

import round_adapters as RA
import round_driver as RD
import round_phases as RP
import round_records as RR

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILL = os.path.join(_PLUGIN_ROOT, "skills", "review-code", "SKILL.md")
_REF = os.path.join(_PLUGIN_ROOT, "skills", "review-code", "reference", "round-driver.md")

_TEST_SESSION = "/tmp/review-code-order-path-sync"
_TEST_RND = 2
_TEST_PHASE = RP.P_PANEL
_TEST_SKEY = RR.storage_key("code-reviewer", 0)
_TEST_ATTEMPT = 0
_TEST_VENDOR = "codex"

# Binding only — path strings come from docs (parsed) or builders (called).
_BUILDER_KEYS = frozenset({
    "order",
    "envelope_stub",
    "manifest",
    "landing_engine",
    "landing_host",
})

_DURABLE_BUILDER_KEYS = frozenset({
    "dispatch_manifest",
    "canary",
    "store",
    "head_diff_store",
})

_SKILL_ARTIFACT_TO_BUILDER = {
    "Order (dispatch this)": "order",
    "Envelope stub (header fields the seat must copy verbatim)": "envelope_stub",
    "Orders manifest (every slot's `orderPath`, `envelopeStubPath`, hashes)": "manifest",
    "Landing — **engine** seat (`codex`/`cursor`)": "landing_engine",
    "Landing — **host** seat (`claude` native subagent)": "landing_host",
}

_REF_ORDER_ARTIFACT_TO_BUILDER = {
    "Order": "order",
    "Envelope stub": "envelope_stub",
    "Manifest": "manifest",
}

_REF_LANDING_ARTIFACT_TO_BUILDER = {
    "**Engine** (`codex`/`cursor`)": "landing_engine",
    "**Host** (`claude` native subagent)": "landing_host",
}

_REF_DURABLE_ARTIFACT_TO_BUILDER = {
    "Dispatch manifest": "dispatch_manifest",
    "Canary probe": "canary",
    "Seat store": "store",
    "Head-diff store": "head_diff_store",
}


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _parse_two_column_table(text, after_marker):
    """Return {artifact_label: path_cell} for a markdown | Artifact | Path | table."""
    idx = text.index(after_marker)
    chunk = text[idx:]
    rows = {}
    in_table = False
    for line in chunk.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table and rows:
                break
            continue
        if re.match(r"^\|\s*---", stripped):
            in_table = True
            continue
        if not in_table:
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        artifact, path = cells[0], cells[1]
        if artifact.lower() in ("artifact", "seat kind"):
            continue
        rows[artifact] = path
    if not rows:
        raise RuntimeError("no table rows parsed after marker %r" % after_marker)
    return rows


def _parse_three_column_landing_table(text):
    """Return {seat_kind: landing_path_cell} from the landing-shapes table."""
    idx = text.index("**Landing shapes**")
    chunk = text[idx:]
    rows = {}
    in_table = False
    for line in chunk.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table and rows:
                break
            continue
        if re.match(r"^\|\s*---", stripped):
            in_table = True
            continue
        if not in_table:
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        seat_kind, landing_path = cells[0], cells[1]
        if seat_kind.lower() == "seat kind":
            continue
        rows[seat_kind] = landing_path
    if not rows:
        raise RuntimeError("landing-shapes table not parsed from round-driver.md")
    return rows


def _parse_durable_record_table(text):
    """Return {artifact_label: path_cell} from the durable-record artifacts table."""
    idx = text.index("**Durable-record artifacts**")
    chunk = text[idx:]
    rows = {}
    in_table = False
    for line in chunk.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table and rows:
                break
            continue
        if re.match(r"^\|\s*---", stripped):
            in_table = True
            continue
        if not in_table:
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        artifact, path = cells[0], cells[1]
        if artifact.lower() == "artifact":
            continue
        rows[artifact] = path
    if not rows:
        raise RuntimeError("durable-record artifacts table not parsed from round-driver.md")
    return rows


def _strip_path_prose(path_cell):
    """Drop trailing em-dash prose from a SKILL path cell."""
    return path_cell.split(" — ")[0].strip().strip("`")


def _instantiate_skill_pattern(pattern, session, rnd, phase, skey, attempt):
    path = _strip_path_prose(pattern)
    return (path.replace("$SESSION_DIR", session)
                .replace("<N>", str(rnd))
                .replace("<phase>", phase)
                .replace("<skey>", skey)
                .replace("<K>", str(attempt)))


def _instantiate_ref_order_pattern(pattern, session, rnd, phase, skey, attempt):
    path = pattern.strip().strip("`")
    return (path.replace("$SESSION_DIR", session)
                .replace("round-N", "round-%d" % rnd)
                .replace("/P/", "/%s/" % phase)
                .replace("/skey.", "/%s." % skey)
                .replace(".aK.", ".a%d." % attempt))


def _instantiate_ref_landing_suffix(pattern, phase, skey, attempt):
    """`.../landing/P/skey.aK.json` → `/landing/<phase>/<skey>.a<attempt>.json`."""
    suffix = pattern.strip().strip("`")
    if suffix.startswith("..."):
        suffix = suffix[3:]
    return (suffix.replace("/P/", "/%s/" % phase)
                .replace("/skey.", "/%s." % skey)
                .replace(".aK.", ".a%d." % attempt))


def _instantiate_ref_durable_pattern(pattern, session, rnd, phase, skey, attempt, vendor):
    path = pattern.strip().strip("`")
    return (path.replace("$SESSION_DIR", session)
                .replace("round-N", "round-%d" % rnd)
                .replace("/P/", "/%s/" % phase)
                .replace("/skey.", "/%s." % skey)
                .replace("/vendor.", "/%s." % vendor)
                .replace(".aK.", ".a%d." % attempt))


def _code_paths(session=_TEST_SESSION, rnd=_TEST_RND, phase=_TEST_PHASE,
                skey=_TEST_SKEY, attempt=_TEST_ATTEMPT, vendor=_TEST_VENDOR):
    return {
        "order": RR.order_prompt_path(session, rnd, phase, skey, attempt),
        "envelope_stub": RR.envelope_stub_path(session, rnd, phase, skey, attempt),
        "manifest": RD._orders_manifest_path(session, rnd, phase, attempt),
        "landing_engine": RR.landing_path(session, rnd, phase, skey, attempt),
        "landing_host": RR.bare_payload_path(session, rnd, phase, skey, attempt),
        "dispatch_manifest": RR.dispatch_manifest_path(session, rnd, phase, attempt),
        "canary": RR.canary_path(session, rnd, vendor, attempt),
        "store": RR.store_path(session, rnd, phase, skey, attempt),
        "head_diff_store": RR.head_diff_store_path(session, rnd, phase, "code-reviewer", attempt),
    }


def _refuse_fold_phases_from_code():
    """Phases whose ``missing_policy`` is ``refuse-fold`` — derived, never hand-typed."""
    return sorted(phase for phase in RA._MISSING_POLICY
                  if RA.missing_policy(phase) == RA.MISSING_REFUSE_FOLD)


def _refuse_fold_phases_from_doc(text):
    idx = text.index("refuse-fold phase (")
    chunk = text[idx:]
    end = chunk.index(")")
    inner = chunk[len("refuse-fold phase ("):end]
    listed = re.findall(r"`([^`]+)`", inner)
    if not listed:
        raise RuntimeError("refuse-fold phase list not parsed from round-driver.md")
    return sorted(listed)


def _round_suffix(path, session, rnd):
    prefix = RR.round_dir(session, rnd)
    assert path.startswith(prefix), "path %r not under round dir %r" % (path, prefix)
    return path[len(prefix):]


def test_skill_path_table_matches_code_builders():
    """SKILL.md emitted-order table ↔ path builders (both directions, fail-closed)."""
    skill_rows = _parse_two_column_table(
        _read(_SKILL), "**Where the files are (round `<N>`, phase `<phase>`")
    mapped_builders = set()
    homes = _code_paths()
    for artifact, pattern in skill_rows.items():
        builder_key = _SKILL_ARTIFACT_TO_BUILDER.get(artifact)
        assert builder_key is not None, (
            "SKILL.md path table row %r has no builder binding — add mapping or remove row"
            % artifact)
        mapped_builders.add(builder_key)
        expected = _instantiate_skill_pattern(
            pattern, _TEST_SESSION, _TEST_RND, _TEST_PHASE, _TEST_SKEY, _TEST_ATTEMPT)
        actual = homes[builder_key]
        assert actual == expected, (
            "SKILL.md %r drifted from %s\n  documented: %r\n  code home:   %r"
            % (artifact, builder_key, expected, actual))
    unmapped = _BUILDER_KEYS - mapped_builders
    assert not unmapped, (
        "code builder(s) with no SKILL.md table row: %s" % sorted(unmapped))


def test_round_driver_order_table_matches_code_builders():
    """round-driver.md order table ↔ path builders (both directions, fail-closed)."""
    ref_rows = _parse_two_column_table(_read(_REF), "Paths (round `N`, phase `P`")
    mapped_builders = set()
    homes = _code_paths()
    for artifact, pattern in ref_rows.items():
        builder_key = _REF_ORDER_ARTIFACT_TO_BUILDER.get(artifact)
        assert builder_key is not None, (
            "round-driver.md order row %r has no builder binding" % artifact)
        mapped_builders.add(builder_key)
        expected = _instantiate_ref_order_pattern(
            pattern, _TEST_SESSION, _TEST_RND, _TEST_PHASE, _TEST_SKEY, _TEST_ATTEMPT)
        actual = homes[builder_key]
        assert actual == expected, (
            "round-driver.md order %r drifted from %s\n  documented: %r\n  code home:   %r"
            % (artifact, builder_key, expected, actual))
    order_builders = frozenset(_REF_ORDER_ARTIFACT_TO_BUILDER.values())
    unmapped = order_builders - mapped_builders
    assert not unmapped, (
        "code order builder(s) with no round-driver.md order row: %s" % sorted(unmapped))


def test_round_driver_landing_table_matches_code_builders():
    """round-driver.md landing-shapes table ↔ landing builders (suffix match)."""
    ref_rows = _parse_three_column_landing_table(_read(_REF))
    mapped_builders = set()
    homes = _code_paths()
    for seat_kind, pattern in ref_rows.items():
        builder_key = _REF_LANDING_ARTIFACT_TO_BUILDER.get(seat_kind)
        assert builder_key is not None, (
            "round-driver.md landing row %r has no builder binding" % seat_kind)
        mapped_builders.add(builder_key)
        expected_suffix = _instantiate_ref_landing_suffix(
            pattern, _TEST_PHASE, _TEST_SKEY, _TEST_ATTEMPT)
        actual_suffix = _round_suffix(homes[builder_key], _TEST_SESSION, _TEST_RND)
        assert actual_suffix == expected_suffix, (
            "round-driver.md landing %r drifted from %s\n  documented suffix: %r\n  code suffix:       %r"
            % (seat_kind, builder_key, expected_suffix, actual_suffix))
    landing_builders = frozenset(_REF_LANDING_ARTIFACT_TO_BUILDER.values())
    unmapped = landing_builders - mapped_builders
    assert not unmapped, (
        "code landing builder(s) with no round-driver.md landing row: %s" % sorted(unmapped))


def test_round_driver_durable_record_table_matches_code_builders():
    """round-driver.md durable-record table ↔ store/manifest builders (both directions)."""
    ref_rows = _parse_durable_record_table(_read(_REF))
    mapped_builders = set()
    homes = _code_paths()
    for artifact, pattern in ref_rows.items():
        builder_key = _REF_DURABLE_ARTIFACT_TO_BUILDER.get(artifact)
        assert builder_key is not None, (
            "round-driver.md durable-record row %r has no builder binding" % artifact)
        mapped_builders.add(builder_key)
        expected = _instantiate_ref_durable_pattern(
            pattern, _TEST_SESSION, _TEST_RND, _TEST_PHASE, _TEST_SKEY, _TEST_ATTEMPT,
            _TEST_VENDOR)
        actual = homes[builder_key]
        assert actual == expected, (
            "round-driver.md durable-record %r drifted from %s\n  documented: %r\n  code home:   %r"
            % (artifact, builder_key, expected, actual))
    unmapped = _DURABLE_BUILDER_KEYS - mapped_builders
    assert not unmapped, (
        "code durable builder(s) with no round-driver.md durable-record row: %s"
        % sorted(unmapped))


def test_round_driver_refuse_fold_recovery_row_matches_missing_policy():
    """round-driver.md refuse-fold recovery row ↔ round_adapters.missing_policy (both directions)."""
    doc_phases = _refuse_fold_phases_from_doc(_read(_REF))
    code_phases = _refuse_fold_phases_from_code()
    assert doc_phases == code_phases, (
        "round-driver.md refuse-fold list drifted from round_adapters.missing_policy\n"
        "  documented: %r\n  code home:   %r" % (doc_phases, code_phases))
    assert doc_phases, "expected at least one refuse-fold phase"
