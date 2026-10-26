#!/usr/bin/env python3
"""The configuration items: one registry, one read contract, one setter per home.

Stdlib only. Every item's value is read and written only through this module and the
``core_md`` writers it routes to."""
import argparse
import datetime
import json
import math
import os
import re
import secrets
import subprocess
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import canon  # noqa: E402
import core_md  # noqa: E402
import guardian_sweep  # noqa: E402

HOME_PROJECT_CONFIGURATION = "projectConfiguration"
HOME_RISK_AND_TRUST = "riskAndTrust"
HOME_GUARDIAN_CADENCE = "guardianCadence"

BUDGET_DERIVATION_PROSE = (
    "floor of the effective dial's share of the lane count, never below one"
)

REASON_UNKNOWN_SLUG = "unknown-slug"
REASON_MALFORMED_VALUE = "malformed-value"
REASON_LADDER_CITATION_REQUIRED = "ladder-example-citation-required"
REASON_PROFILE_ABSENT = "profile-absent"
REASON_PROFILE_UNPARSEABLE = "profile-unparseable"
REASON_SET_MISMATCH = "set-read-mismatch"
REASON_MATERIAL_LINE_IN_CANON = "material-line-in-canon"
REASON_SETUP_COMMANDS_NOT_A_LIST = "setup-commands-not-a-list"
REASON_SETUP_COMMAND_EMPTY = "setup-command-empty"
REASON_SETUP_COMMAND_MULTI_LINE = "setup-command-multi-line"
REASON_SETUP_COMMAND_SECRET_SHAPED = "setup-command-secret-shaped"
REASON_SETUP_INPUT_UNSAFE_PATH = "setup-input-unsafe-path"
REASON_SETUP_INPUT_SECRET_SHAPED = "setup-input-secret-shaped"
REASON_DEPENDENCY_HOOK_UNWRITABLE = "dependency-hook-unwritable"

MATERIAL_LINE_SLUG = "materialConsequenceLine"
CLOUD_BUILDS_SLUG = "cloudBuilds"
CI_WORKFLOW_SLUG = "ciWorkflow"
CLOUD_SETUP_COMMANDS_SLUG = "cloudSetupCommands"
CLOUD_SETUP_INPUTS_SLUG = "cloudSetupInputs"
CLOUD_DEPENDENCY_HOOK_SLUG = "cloudDependencyHook"
MATERIAL_LINE_MARKER_CANON = "standing-rulings"
_MATERIAL_LINE_POINTER_EFFECTIVE = "the project's Canon standing rulings"

_DEPENDENCY_FALLBACKS = {
    "launchLedger": "lanes are counted by hand beside the launch word",
    "collector": (
        "any durable, owner-visible issue is designated as both at calibration"
    ),
    "keepOrRetireBackfill": (
        "back-fill is opportunistic, each guard getting its condition when its "
        "surface is next touched, and never a mass retroactive sweep"
    ),
    "detectorTestBoundary": (
        "the boundary is undeclared and birth duties are unbounded, which is a "
        "calibration defect to fix"
    ),
}
DEPENDENCY_ORDER = tuple(_DEPENDENCY_FALLBACKS)

ITEMS = (
    {
        "number": 1,
        "slug": "severityLadder",
        "name": "Severity ladder",
        "home": HOME_PROJECT_CONFIGURATION,
        "shape": "severityLadder",
        "plugin_default": None,
    },
    {
        "number": 2,
        "slug": "p0Definition",
        "name": "P0 definition",
        "home": HOME_PROJECT_CONFIGURATION,
        "shape": "prose",
        "plugin_default": None,
    },
    {
        "number": 3,
        "slug": "dial",
        "name": "Dial",
        "home": HOME_PROJECT_CONFIGURATION,
        "shape": "dial",
        "plugin_default": {"min": 20, "max": 30},
    },
    {
        "number": 4,
        "slug": "budgetN",
        "name": "Budget N",
        "home": HOME_PROJECT_CONFIGURATION,
        "shape": "budgetN",
        "plugin_default": "derived",
    },
    {
        "number": 5,
        "slug": "groundTruthSources",
        "name": "Ground-truth sources",
        "home": HOME_PROJECT_CONFIGURATION,
        "shape": "proseList",
        "plugin_default": None,
    },
    {
        "number": 6,
        "slug": "digestFloor",
        "name": "Digest floor",
        "home": HOME_PROJECT_CONFIGURATION,
        "shape": "prose",
        "plugin_default": None,
    },
    {
        "number": 7,
        "slug": "conditionWindows",
        "name": "Condition windows",
        "home": HOME_PROJECT_CONFIGURATION,
        "shape": "conditionWindows",
        "plugin_default": {"catch": 45, "citation": 45, "usage": 60},
    },
    {
        "number": 8,
        "slug": "stackingTool",
        "name": "Stacking tool",
        "home": HOME_PROJECT_CONFIGURATION,
        "shape": "prose",
        "plugin_default": None,
    },
    {
        "number": 9,
        "slug": "keepOrRetireReporting",
        "name": "Keep-or-retire reporting",
        "home": HOME_PROJECT_CONFIGURATION,
        "shape": "boolean",
        "plugin_default": False,
    },
    {
        "number": 10,
        "slug": "riskAndTrust",
        "name": "Risk and trust",
        "home": HOME_RISK_AND_TRUST,
        "shape": "riskAndTrust",
        "plugin_default": None,
    },
    {
        "number": 14,
        "slug": "whoItsFor",
        "name": "Who it's for and what it's for",
        "home": HOME_PROJECT_CONFIGURATION,
        "shape": "nonEmptyProse",
        "plugin_default": None,
    },
    {
        "number": 11,
        "slug": "guardianStaleness",
        "name": "Guardian staleness",
        "home": HOME_GUARDIAN_CADENCE,
        "shape": "guardianCadence",
        "plugin_default": dict(guardian_sweep.CADENCE_DEFAULTS),
    },
    {
        "number": 12,
        "slug": "keepList",
        "name": "Keep list",
        "home": HOME_PROJECT_CONFIGURATION,
        "shape": "pathList",
        "plugin_default": None,
    },
    {
        "number": 13,
        "slug": "materialConsequenceLine",
        "name": "Material consequence line",
        "home": HOME_PROJECT_CONFIGURATION,
        "shape": "prose",
        "plugin_default": None,
    },
    {
        "number": 15,
        "slug": "cloudBuilds",
        "name": "Cloud builds",
        "home": HOME_PROJECT_CONFIGURATION,
        "shape": "boolean",
        "plugin_default": False,
    },
    {
        "number": 16,
        "slug": "ciWorkflow",
        "name": "CI workflow",
        "home": HOME_PROJECT_CONFIGURATION,
        "shape": "nonEmptyProse",
        "plugin_default": None,
    },
    {
        "number": 17,
        "slug": "cloudSetupCommands",
        "name": "Cloud setup commands",
        "home": HOME_PROJECT_CONFIGURATION,
        "shape": "commandList",
        "plugin_default": None,
    },
    {
        "number": 18,
        "slug": "cloudSetupInputs",
        "name": "Cloud setup inputs",
        "home": HOME_PROJECT_CONFIGURATION,
        "shape": "inputPathList",
        "plugin_default": None,
    },
    {
        "number": 19,
        "slug": "cloudDependencyHook",
        "name": "Cloud dependency hook",
        "home": HOME_PROJECT_CONFIGURATION,
        "shape": "boolean",
        "plugin_default": None,
    },
)

_SLUG_INDEX = {item["slug"]: item for item in ITEMS}


def _positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _positive_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _validate_prose(value):
    if not isinstance(value, str):
        return REASON_MALFORMED_VALUE
    return None


def _validate_non_empty_prose(value):
    # axis: item 14 refuses an empty or whitespace-only value — see bite-proof record wo_a_1618_who-its-for-non-empty
    if not isinstance(value, str):
        return REASON_MALFORMED_VALUE
    if not value.strip():
        return REASON_MALFORMED_VALUE
    return None


def is_material_line_marker(raw):
    """True when ``raw`` is exactly the item-13 Canon pointer: two keys, a valid ISO ``migratedOn``."""
    # axis: only the exact two-key marker counts as adopted — see bite-proof record wo_a_1618_marker-shape
    if not isinstance(raw, dict) or set(raw) != {"canon", "migratedOn"}:
        return False
    if raw["canon"] != MATERIAL_LINE_MARKER_CANON:
        return False
    stamp = raw["migratedOn"]
    if not isinstance(stamp, str):
        return False
    try:
        return datetime.date.fromisoformat(stamp).isoformat() == stamp
    except ValueError:
        return False


def _validate_threat_model(value):
    if not isinstance(value, str):
        return REASON_MALFORMED_VALUE
    if not value.strip():
        return REASON_MALFORMED_VALUE
    for line in value.splitlines():
        if line.lstrip().startswith("## "):
            return REASON_MALFORMED_VALUE
    return None


def _validate_risk_and_trust(value):
    # axis: a set carries exactly one half, the threat model or the risk areas — see bite-proof record wo_a_1712_risk-areas
    if not isinstance(value, dict) or len(value) != 1:
        return REASON_MALFORMED_VALUE
    if "threatModel" in value:
        return _validate_threat_model(value["threatModel"])
    if "riskAreas" in value:
        if core_md.validate_risk_areas(value["riskAreas"]):
            return REASON_MALFORMED_VALUE
        return None
    return REASON_MALFORMED_VALUE


def _validate_prose_list(value):
    if not isinstance(value, list):
        return REASON_MALFORMED_VALUE
    for entry in value:
        if not isinstance(entry, str):
            return REASON_MALFORMED_VALUE
    return None


def _validate_path_list(value):
    if not isinstance(value, list):
        return REASON_MALFORMED_VALUE
    for entry in value:
        if not isinstance(entry, str) or not entry.strip():
            return REASON_MALFORMED_VALUE
    return None


def _validate_command_list(value):
    """The first failing reason for a list of one-line setup commands, else None."""
    if not isinstance(value, list):
        return REASON_SETUP_COMMANDS_NOT_A_LIST
    # axis: an entry that is not a string, or is blank, is refused as empty
    if any(not isinstance(entry, str) or not entry.strip() for entry in value):
        return REASON_SETUP_COMMAND_EMPTY
    # axis: an entry that spans lines is refused, so one entry is one command
    if any("\n" in entry or "\r" in entry for entry in value):
        return REASON_SETUP_COMMAND_MULTI_LINE
    import cloud_setup_text  # imports this module at load, so it is imported here

    # axis: an entry shaped like a secret is refused, because the setup text carries it in the clear
    if any(cloud_setup_text._scan(entry) is not None for entry in value):
        return REASON_SETUP_COMMAND_SECRET_SHAPED
    return None


def _validate_input_path_list(value):
    """The first failing reason for a list of repo-relative input file paths, else None."""
    if not isinstance(value, list):
        return REASON_MALFORMED_VALUE
    import cloud_setup_text  # imports this module at load, so it is imported here

    # axis: an entry that is not a plain repo-relative path is refused, since the setup stamp reads it
    if any(not cloud_setup_text._plain_relative(entry) for entry in value):
        return REASON_SETUP_INPUT_UNSAFE_PATH
    return None


def _validate_inputs_not_secret_shaped(inputs):
    """REASON_SETUP_INPUT_SECRET_SHAPED when an input path is shaped like a secret, else None."""
    import cloud_setup_text

    if any(cloud_setup_text._scan(entry) is not None for entry in inputs):
        return REASON_SETUP_INPUT_SECRET_SHAPED
    return None


def _validate_boolean(value):
    if not isinstance(value, bool):
        return REASON_MALFORMED_VALUE
    return None


def _validate_dial(value):
    if isinstance(value, dict):
        min_val = value.get("min")
        max_val = value.get("max")
        if not _positive_number(min_val) or not _positive_number(max_val):
            return REASON_MALFORMED_VALUE
        if min_val > max_val:
            return REASON_MALFORMED_VALUE
        return None
    if _positive_number(value):
        return None
    return REASON_MALFORMED_VALUE


def _validate_budget_n(value):
    if value == "derived":
        return None
    if _positive_int(value):
        return None
    return REASON_MALFORMED_VALUE


def _validate_condition_windows(value):
    if not isinstance(value, dict):
        return REASON_MALFORMED_VALUE
    for key in ("catch", "citation", "usage"):
        if not _positive_int(value.get(key)):
            return REASON_MALFORMED_VALUE
    return None


def _validate_guardian_cadence(value):
    if not isinstance(value, dict):
        return REASON_MALFORMED_VALUE
    for key in ("minMerges", "minDays"):
        if not _positive_int(value.get(key)):
            return REASON_MALFORMED_VALUE
    return None


def _validate_severity_ladder(value):
    # axis: every band example carries a citation — see bite-proof record wo_b_1276_citation-required
    if not isinstance(value, list) or not value:
        return REASON_MALFORMED_VALUE
    for band in value:
        if not isinstance(band, dict):
            return REASON_MALFORMED_VALUE
        if not isinstance(band.get("name"), str) or not band.get("name").strip():
            return REASON_MALFORMED_VALUE
        examples = band.get("examples")
        if not isinstance(examples, list) or not examples:
            return REASON_MALFORMED_VALUE
        for example in examples:
            if not isinstance(example, dict):
                return REASON_MALFORMED_VALUE
            text = example.get("text")
            if not isinstance(text, str) or not text.strip():
                return REASON_MALFORMED_VALUE
            citation = example.get("citation")
            if not isinstance(citation, str) or not citation.strip():
                return REASON_LADDER_CITATION_REQUIRED
    return None


_VALIDATORS = {
    "prose": _validate_prose,
    "nonEmptyProse": _validate_non_empty_prose,
    "proseList": _validate_prose_list,
    "pathList": _validate_path_list,
    "commandList": _validate_command_list,
    "inputPathList": _validate_input_path_list,
    "boolean": _validate_boolean,
    "dial": _validate_dial,
    "budgetN": _validate_budget_n,
    "conditionWindows": _validate_condition_windows,
    "guardianCadence": _validate_guardian_cadence,
    "severityLadder": _validate_severity_ladder,
    "riskAndTrust": _validate_risk_and_trust,
}


def validate_item_value(item, value):
    """Return a refusal reason when ``value`` does not match ``item``'s shape."""
    validator = _VALIDATORS.get(item["shape"])
    if validator is None:
        return REASON_MALFORMED_VALUE
    return validator(value)


def _dial_share_percent(dial):
    if isinstance(dial, dict):
        min_val = dial.get("min")
        if _positive_number(min_val):
            return min_val
        max_val = dial.get("max")
        if _positive_number(max_val):
            return max_val
        return None
    if _positive_number(dial):
        return dial
    return None


def derive_budget(dial, lane_count):
    """Return the derived budget for ``lane_count`` using ``dial``'s share, floored at one."""
    share = _dial_share_percent(dial)
    if share is None:
        return 1
    try:
        lanes = int(lane_count)
    except (TypeError, ValueError):
        return 1
    if lanes < 1:
        return 1
    return max(1, int(math.floor(lanes * share / 100.0)))


def _item_by_slug(slug):
    return _SLUG_INDEX.get(slug)


def _guardian_cadence_raw(cwd, root, *, persist_backfill=True):
    import guardian_store

    try:
        layer_p = guardian_store.guardian_layer_path(
            cwd, root, persist_backfill=persist_backfill
        )
    except Exception:
        return None
    if core_md._layer_is_empty(layer_p):
        return None
    try:
        with open(layer_p, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    inner = core_md._guardian_config_inner_text(text)
    if inner is None:
        return None
    try:
        block = json.loads(inner)
    except ValueError:
        return None
    if not isinstance(block, dict):
        return None
    cadence = block.get("cadence")
    if cadence is None:
        return None
    return cadence


def _project_config_mapping(facts):
    if not isinstance(facts, dict):
        return {}
    mapping = facts.get("projectConfiguration")
    if mapping is None:
        return {}
    if not isinstance(mapping, dict):
        return {}
    return mapping


def _read_project_config_raw(mapping, slug):
    if slug not in mapping:
        return None
    return mapping[slug]


def _resolve_item_entry(item, raw, *, dial_effective=None, guardian_cfg=None,
                        risk_areas_read=None):
    slug = item["slug"]
    malformed = False
    if slug == "budgetN":
        if _positive_int(raw):
            return {
                "raw": raw,
                "effective": raw,
                "source": "stamped",
                "malformed": False,
            }
        if raw == "derived" or raw is None:
            return {
                "raw": raw,
                "effective": BUDGET_DERIVATION_PROSE,
                "source": "derived",
                "malformed": False,
            }
        malformed = True
        return {
            "raw": raw,
            "effective": None,
            "source": "unset",
            "malformed": True,
        }

    if slug == "guardianStaleness":
        guardian_cfg = guardian_cfg or {}
        cadence = guardian_cfg.get("cadence")
        cadence_tuned = guardian_cfg.get("cadenceTuned") or {}
        if raw is not None and _validate_guardian_cadence(raw) is not None:
            return {
                "raw": raw,
                "effective": None,
                "source": "unset",
                "malformed": True,
            }
        if cadence_tuned:
            return {
                "raw": raw,
                "effective": dict(cadence) if isinstance(cadence, dict) else None,
                "source": "stamped",
                "malformed": False,
            }
        return {
            "raw": None,
            "effective": dict(guardian_sweep.CADENCE_DEFAULTS),
            "source": "plugin-default",
            "malformed": False,
        }

    if slug == "riskAndTrust":
        raw = raw if isinstance(raw, dict) else {}
        threat = raw.get("threatModel")
        areas = raw.get("riskAreas")
        threat_set = isinstance(threat, str) and bool(threat.strip())
        # axis: the risk-areas half is derived only from core_md.read_risk_areas — see bite-proof record wo_a_1712_risk-areas
        areas_read = risk_areas_read or {}
        areas_malformed = areas_read.get("reason") in (
            core_md.RISK_AREAS_REASON_MALFORMED, core_md.RISK_AREAS_REASON_UNREADABLE)
        if areas_malformed:
            effective_areas = None
        elif areas_read.get("declared"):
            effective_areas = areas_read.get("areas")
        else:
            effective_areas = []
        stamped = threat_set or bool(effective_areas)
        return {
            "raw": {"threatModel": threat, "riskAreas": areas},
            "effective": {
                "threatModel": threat if threat_set else None,
                "riskAreas": effective_areas,
            },
            "source": "stamped" if stamped else "unset",
            "malformed": areas_malformed or (threat is not None and not isinstance(threat, str)),
        }

    if slug == MATERIAL_LINE_SLUG and is_material_line_marker(raw):
        return {
            "raw": raw,
            "effective": _MATERIAL_LINE_POINTER_EFFECTIVE,
            "source": "canon-pointer",
            "malformed": False,
        }

    if raw is None:
        default = item["plugin_default"]
        if default is not None:
            return {
                "raw": None,
                "effective": default if not isinstance(default, dict) else dict(default),
                "source": "plugin-default",
                "malformed": False,
            }
        return {
            "raw": None,
            "effective": None,
            "source": "unset",
            "malformed": False,
        }

    reason = validate_item_value(item, raw)
    if reason is not None:
        return {
            "raw": raw,
            "effective": None,
            "source": "unset",
            "malformed": True,
        }

    return {
        "raw": raw,
        "effective": raw,
        "source": "stamped",
        "malformed": False,
    }


def read(cwd, root=None, *, persist_backfill=True):
    """Return every configuration item with ``raw``, ``effective``, and ``source``."""
    keyword = {} if persist_backfill else {"persist_backfill": False}
    facts = core_md.read(cwd, root, **keyword)
    guardian_cfg = guardian_sweep.read_config(cwd, root, **keyword)
    risk_areas_read = core_md.read_risk_areas(cwd, root)
    if facts is None:
        absent_items = []
        dial_entry = _resolve_item_entry(_SLUG_INDEX["dial"], None)
        for item in ITEMS:
            slug = item["slug"]
            if item["home"] == HOME_RISK_AND_TRUST:
                raw = {"threatModel": None, "riskAreas": None}
            elif item["home"] == HOME_GUARDIAN_CADENCE:
                raw = _guardian_cadence_raw(cwd, root, **keyword)
            else:
                raw = None
            entry = _resolve_item_entry(
                item,
                raw,
                dial_effective=dial_entry["effective"],
                guardian_cfg=guardian_cfg,
                risk_areas_read=risk_areas_read,
            )
            absent_items.append({"slug": slug, **entry})
        return {
            "profileAbsent": True,
            "profileUnparseable": True,
            "behind": False,
            "items": absent_items,
        }
    mapping = _project_config_mapping(facts)
    dial_raw = _read_project_config_raw(mapping, "dial")
    dial_entry = _resolve_item_entry(_SLUG_INDEX["dial"], dial_raw)
    items = []
    for item in ITEMS:
        slug = item["slug"]
        if item["home"] == HOME_RISK_AND_TRUST:
            threat = facts.get("threatModel")
            if isinstance(threat, str) and not threat.strip():
                threat = None
            raw = {"threatModel": threat,
                   "riskAreas": _read_project_config_raw(mapping, core_md.RISK_AREAS_KEY)}
        elif item["home"] == HOME_GUARDIAN_CADENCE:
            raw = _guardian_cadence_raw(cwd, root, **keyword)
        else:
            raw = _read_project_config_raw(mapping, slug)
        entry = _resolve_item_entry(
            item,
            raw,
            dial_effective=dial_entry["effective"],
            guardian_cfg=guardian_cfg,
            risk_areas_read=risk_areas_read,
        )
        items.append({
            "slug": slug,
            **entry,
        })
    return {
        "profileAbsent": False,
        "profileUnparseable": False,
        "behind": bool(facts.get("behind")),
        "items": items,
    }


def view(cwd, root=None):
    """Return every item in registry order for display."""
    payload = read(cwd, root)
    items = []
    for item_def, item_read in zip(ITEMS, payload["items"]):
        items.append({
            "number": item_def["number"],
            "slug": item_def["slug"],
            "name": item_def["name"],
            "raw": item_read["raw"],
            "effective": item_read["effective"],
            "source": item_read["source"],
            "malformed": item_read.get("malformed", False),
        })
    return {
        "behind": payload["behind"],
        "profileAbsent": payload["profileAbsent"],
        "profileUnparseable": payload["profileUnparseable"],
        "items": items,
    }


def get_item(cwd, slug, root=None, *, persist_backfill=True):
    """Return one item's read contract, or a refusal when the slug is unknown."""
    item = _item_by_slug(slug)
    if item is None:
        return {"action": "refused", "reason": REASON_UNKNOWN_SLUG}
    keyword = {} if persist_backfill else {"persist_backfill": False}
    payload = read(cwd, root, **keyword)
    for entry in payload["items"]:
        if entry["slug"] == slug:
            return {
                "slug": slug,
                "raw": entry["raw"],
                "effective": entry["effective"],
                "source": entry["source"],
                "malformed": entry.get("malformed", False),
                "behind": payload["behind"],
            }
    return {"action": "refused", "reason": REASON_UNKNOWN_SLUG}


def _values_equal(stored, expected):
    return json.dumps(stored, sort_keys=True) == json.dumps(expected, sort_keys=True)


def _material_line_in_canon_refusal():
    return {
        "action": "refused",
        "reason": REASON_MATERIAL_LINE_IN_CANON,
        "detail": (
            "Item 13 now points to the project's Canon standing rulings and holds no "
            "value of its own. Record a new example in Canon as a standing ruling, "
            "by Canon's write procedure."
        ),
    }


def _risk_and_trust_raw(cwd, root):
    """Item 10's two stored halves, or None when they cannot be read."""
    reread = get_item(cwd, "riskAndTrust", root=root)
    raw = reread.get("raw")
    return raw if isinstance(raw, dict) else None


def _set_risk_and_trust(cwd, value, root):
    """Write one half of item 10 to its own home, then read both halves back."""
    half = "threatModel" if "threatModel" in value else "riskAreas"
    other = "riskAreas" if half == "threatModel" else "threatModel"
    before = _risk_and_trust_raw(cwd, root)
    if half == "threatModel":
        write_result = core_md.write_threat_model(cwd, value["threatModel"], root=root)
    else:
        write_result = core_md.write_project_config_item(
            cwd, core_md.RISK_AREAS_KEY, value["riskAreas"], root=root)
    if write_result.get("action") not in ("written", "noop"):
        return write_result

    after = _risk_and_trust_raw(cwd, root)
    # write_threat_model stores the prose stripped, so the stripped text is what reads back
    submitted = value[half].strip() if half == "threatModel" else value[half]
    # axis: the read-back compares only the half that was written — see bite-proof record wo_a_1712_risk-areas
    if after is None or not _values_equal(after.get(half), submitted):
        return {
            "action": "refused",
            "reason": REASON_SET_MISMATCH,
            "expected": {half: submitted},
            "observed": {half: None if after is None else after.get(half)},
        }
    # axis: a set that moved the other half is refused, since each half has one home — see bite-proof record wo_a_1712_risk-areas
    if before is not None and not _values_equal(after.get(other), before.get(other)):
        return {
            "action": "refused",
            "reason": REASON_SET_MISMATCH,
            "expected": {other: before.get(other)},
            "observed": {other: after.get(other)},
        }
    return write_result


def _detected_inputs(repo_root):
    """The lockfile names at `repo_root` that item 18 accepts."""
    import cloud_setup_text

    item = _item_by_slug(CLOUD_SETUP_INPUTS_SLUG)
    # axis: a detected name item 18 would refuse is never stored, so the list stays valid
    return [name for name in cloud_setup_text.detect_inputs(repo_root)
            if validate_item_value(item, [name]) is None]


def _fill_setup_inputs(cwd, root, write_result, filled):
    """Stores the detected `filled` list as item 18, after item 17 is stored. The fill never turns
    a stored item 17 into a refusal: when the write or its read-back fails, item 17's result is
    returned with `inputsFillFailed` carrying the reason (and no `inputsFilled`), leaving item 18
    unset when the write failed. Returns (result, committed): `committed` is True once the write
    went through, even when the read-back then failed."""
    stored = core_md.write_project_config_item(cwd, CLOUD_SETUP_INPUTS_SLUG, filled, root=root)
    if stored.get("action") not in ("written", "noop"):
        return {**write_result, "inputsFillFailed": stored.get("reason")}, False
    reread = get_item(cwd, CLOUD_SETUP_INPUTS_SLUG, root=root)
    if reread.get("action") == "refused":
        return {**write_result, "inputsFillFailed": reread.get("reason")}, True
    if not _values_equal(reread.get("raw"), filled):
        return {**write_result, "inputsFillFailed": REASON_SET_MISMATCH}, True
    return {**write_result, "inputsFilled": list(filled)}, True


_DEPENDENCY_HOOK_SLUGS = (
    CLOUD_SETUP_COMMANDS_SLUG, CLOUD_SETUP_INPUTS_SLUG, CLOUD_DEPENDENCY_HOOK_SLUG)


def _string_list_or_empty(value):
    return list(value) if isinstance(value, list) and all(isinstance(v, str) for v in value) else []


def _hook_triple(mapping):
    """(commands, inputs, enabled) as the stored items 17, 18 and 19 give them to the hook."""
    return (_string_list_or_empty(mapping.get(CLOUD_SETUP_COMMANDS_SLUG)),
            _string_list_or_empty(mapping.get(CLOUD_SETUP_INPUTS_SLUG)),
            mapping.get(CLOUD_DEPENDENCY_HOOK_SLUG) is True)


def _hook_desired(triple):
    return triple[2] and bool(triple[0])


def _hook_refusal(detail):
    return {"action": "refused", "reason": REASON_DEPENDENCY_HOOK_UNWRITABLE, "detail": detail}


def _plan_fill(repo_root):
    """The item 18 fill for a set that would fill it: (filled, None), or (None, reason) when the
    fill is skipped. A root that cannot be resolved (git failing), that is not itself a git
    checkout, or that cannot be listed gets no fill and is reported, never silent."""
    import store_core

    # axis: an unresolved root is reported, never silent — a transient git failure would otherwise leave item 18 unset unnoticed
    if repo_root is None:
        return None, "repo-root-unavailable"
    try:
        # a checkout answers its real git directory (wherever the metadata lives); the greenfield
        # fallback answers the directory itself
        git_dir = store_core.get_worktree_gitdir(repo_root)
    except store_core.RepoRootUnavailable:
        return None, "repo-root-unavailable"
    if git_dir == os.path.realpath(repo_root):
        # axis: a configured directory that is not a git checkout gets no fill — the root fallback names the directory itself, and scanning it would store a list for the wrong tree
        return None, "not-a-git-checkout"
    try:
        return _detected_inputs(repo_root), None
    except OSError as exc:
        # axis: a root that could not be listed is a failed scan, never "found none" — storing []
        # would freeze input tracking off for good
        return None, ("the repository root could not be read (%s)"
                      % (exc.strerror or type(exc).__name__))


def _plan_dependency_hook(cwd, slug, value, facts, root=None):
    """Works out, before anything is written, the item 18 fill and the hook state this set leads
    to, and brings the hook files to that state. Returns {"refusal": result} when it cannot, else
    the plan: the stored `old` triple, the `new` triple (with the fill), the `filled` item 18 (or
    None), the `fillFailed` reason when a fill was skipped (or None), the sync result
    (`hookResult`, or None when none ran) and the `repoRoot`."""
    import cloud_dependency_hook as hook
    import store_core

    mapping = _project_config_mapping(facts)
    old = _hook_triple(mapping)
    after = dict(mapping)
    after[slug] = value
    try:
        repo_root = store_core.repo_root(cwd)
    except store_core.RepoRootUnavailable:
        repo_root = None
    filled = fill_failed = None
    # axis: item 18 is filled only when it was never stored, so an edited list survives
    if slug == CLOUD_SETUP_COMMANDS_SLUG and value and CLOUD_SETUP_INPUTS_SLUG not in mapping:
        filled, fill_failed = _plan_fill(repo_root)
        if filled is not None:
            after[CLOUD_SETUP_INPUTS_SLUG] = filled
    new = _hook_triple(after)
    plan = {"old": old, "new": new, "filled": filled, "fillFailed": fill_failed,
            "hookResult": None, "repoRoot": repo_root, "slug": slug,
            "oldValue": mapping.get(slug), "newValue": value, "deferred": False}
    if repo_root is None:
        # axis: with no root a sync is impossible, so it refuses only when one is needed
        if _hook_desired(new) or _hook_desired(old):
            return {"refusal": _hook_refusal("repo-root-unavailable")}
        return plan
    script = os.path.join(repo_root, *hook.SCRIPT_REL.split("/"))
    # axis: a project that never opted in has no script, so its settings file is never read
    if _hook_desired(old) and not _hook_desired(new):
        # axis: a set that removes the hook writes the config first and removes the files after it, so a kill between the two never leaves "on" stored with the files gone
        plan["deferred"] = True
        return plan
    if _hook_desired(new) or _hook_desired(old) or os.path.lexists(script):
        # axis: a hook about to be written never carries a command the setup text would refuse — a stored command with a credential in it is not committed
        if _hook_desired(new):
            reason = _validate_command_list(new[0])
            if reason is None:
                reason = _validate_inputs_not_secret_shaped(new[1])
            if reason is not None:
                return {"refusal": {"action": "refused", "reason": reason}}
        result = hook.sync(repo_root, *new)
        if result.get("action") == "refused":
            # axis: a refused sync that already changed files puts them back to the stored state, by reconciling to the stored items — never from a snapshot
            refusal = _hook_refusal(result.get("reason"))
            if result.get("changed"):
                # axis: another set may have stored items since `old` was read, so recovery reads them afresh
                fresh = core_md.read(cwd, root)
                if not fresh:
                    refusal["dependencyHookResyncFailed"] = "stored-config-unreadable"
                else:
                    refusal.update(_reconcile_dependency_hook(
                        repo_root, _hook_triple(_project_config_mapping(fresh))))
            return {"refusal": refusal}
        plan["hookResult"] = result
    return plan


def _reconcile_dependency_hook(repo_root, stored):
    """Brings the hook files to the stored (commands, inputs, enabled) triple, the one way every
    failure after a sync ends: a triple a hook-writing sync would accept is synced as stored; one it
    would refuse (a secret-shaped command or input) gets the hook turned off, which removes the
    files, so no stored credential reaches a script. Returns {"dependencyHookResynced": result} or
    {"dependencyHookResyncFailed": reason}, and adds `dependencyHookRemovedInvalid` with the reason
    when the stored triple was invalid."""
    import cloud_dependency_hook as hook

    target = stored
    extra = {}
    if _hook_desired(stored):
        reason = _validate_command_list(stored[0])
        if reason is None:
            reason = _validate_inputs_not_secret_shaped(stored[1])
        if reason is not None:
            target = (stored[0], stored[1], False)
            extra = {"dependencyHookRemovedInvalid": reason}
    try:
        again = hook.sync(repo_root, *target)
    except Exception as exc:
        return {**extra, "dependencyHookResyncFailed": str(exc)}
    if again.get("action") == "refused":
        return {**extra, "dependencyHookResyncFailed": again.get("reason")}
    return {**extra, "dependencyHookResynced": again}


def _finish_dependency_hook(cwd, root, plan, write_result):
    """Stores the filled item 18 (after item 17) and attaches what the sync did to the result.
    After any failure here the stored items and the files on disk agree: a fill whose write held
    keeps its script (inputs and item 18 both filled); a fill whose write failed gets the script
    for the stored (unset) item 18."""
    hook_result = plan["hookResult"]
    recovery_failed = False
    if plan.get("fillFailed") is not None:
        # axis: a skipped fill is reported on item 17's result, never silent
        write_result = {**write_result, "inputsFillFailed": plan["fillFailed"]}
    if plan["filled"] is not None:
        write_result, committed = _fill_setup_inputs(cwd, root, write_result, plan["filled"])
        if "inputsFillFailed" in write_result and not committed and _hook_desired(plan["new"]):
            import cloud_dependency_hook as hook

            try:
                # the commands were validated before the first sync; the old inputs are unset here
                again = hook.sync(plan["repoRoot"], plan["new"][0], plan["old"][1], plan["new"][2])
            except Exception:
                again = None
            if again is not None and again.get("action") == "refused":
                again = None
            if again is not None:
                # axis: the paths the first sync changed stay reported beside the recovery's
                changed = sorted(set(hook_result.get("changed") or []) | set(again.get("changed") or []))
                hook_result = {**again, "changed": changed}
            else:
                # axis: a recovery that did not land leaves the first sync's files, never the old inputs
                recovery_failed = True
    if hook_result is not None:
        write_result = {**write_result, "dependencyHook": hook_result}
        if recovery_failed:
            facts = core_md.read(cwd, root)
            if not facts:
                return {**write_result, "dependencyHookResyncFailed": "stored-config-unreadable"}
            return {**write_result, **_reconcile_dependency_hook(
                plan["repoRoot"], _hook_triple(_project_config_mapping(facts)))}
        write_result = _converge_dependency_hook(cwd, root, plan, write_result)
    elif plan.get("repoRoot") is not None and not plan.get("deferred"):
        # axis: a set that planned no sync may have been overtaken by an enable between its plan and its write, so the stored triple is re-read and the hook reconciled when it is wanted or its script exists; a project that never opted in has neither, so its settings file is never read
        import cloud_dependency_hook as hook

        facts = core_md.read(cwd, root)
        if facts:
            stored = _hook_triple(_project_config_mapping(facts))
            script = os.path.join(plan["repoRoot"], *hook.SCRIPT_REL.split("/"))
            if _hook_desired(stored) or os.path.lexists(script):
                write_result = _converge_dependency_hook(cwd, root, plan, write_result)
    return write_result


def _run_deferred_removal(cwd, root, plan):
    """Removes the files after the config write that turned the hook off. Returns None once they
    are removed (the sync result is in the plan); a refusal puts the old value back and reconciles
    the files to what is stored."""
    import cloud_dependency_hook as hook

    try:
        result = hook.sync(plan["repoRoot"], *plan["new"])
    except Exception:
        result = {"action": "refused", "reason": "hook-files-unwritable"}
    if result.get("action") != "refused":
        plan["hookResult"] = result
        return None
    refusal = _hook_refusal(result.get("reason"))
    # only while the slug still holds the value this set wrote: a newer stored value stays, and the
    # files are reconciled to it below
    restored = core_md.write_project_config_item_if(
        cwd, plan["slug"], plan["oldValue"], expected=plan["newValue"], root=root)
    if (restored.get("action") not in ("written", "noop")
            and restored.get("reason") != "item-changed"):
        refusal["dependencyHookRestoreFailed"] = restored.get("reason")
    fresh = core_md.read(cwd, root)
    if not fresh:
        refusal["dependencyHookResyncFailed"] = "stored-config-unreadable"
    else:
        refusal.update(_reconcile_dependency_hook(
            plan["repoRoot"], _hook_triple(_project_config_mapping(fresh))))
    return refusal


def _with_dependency_hook(cwd, root, plan, result):
    """Attaches the sync's result to a read-back failure and runs the convergence step, keeping the
    synced files."""
    if plan is not None and plan.get("deferred"):
        facts = core_md.read(cwd, root)
        if not facts:
            return {**result, "dependencyHookResyncFailed": "stored-config-unreadable"}
        return {**result, **_reconcile_dependency_hook(
            plan["repoRoot"], _hook_triple(_project_config_mapping(facts)))}
    if plan is None:
        return result
    if plan.get("hookResult") is None:
        if plan.get("repoRoot") is None:
            return result
        # axis: a plan that ran no sync may have been overtaken by an enable between its plan and its write, so the stored triple is re-read and the hook reconciled when it is wanted or its script exists
        import cloud_dependency_hook as hook

        facts = core_md.read(cwd, root)
        if facts:
            stored = _hook_triple(_project_config_mapping(facts))
            script = os.path.join(plan["repoRoot"], *hook.SCRIPT_REL.split("/"))
            if _hook_desired(stored) or os.path.lexists(script):
                return _converge_dependency_hook(cwd, root, plan, result)
        else:
            return {**result, "dependencyHookResyncFailed": "stored-config-unreadable"}
        return result
    result = {**result, "dependencyHook": plan["hookResult"]}
    return _converge_dependency_hook(cwd, root, plan, result)


def _converge_dependency_hook(cwd, root, plan, write_result):
    """Brings the hook files to the stored items 17, 18 and 19 when a set that landed between this
    set's sync and its write left them differing from the triple the sync used (the writers each
    lock internally, so no lock can span the sync). One more sync runs with the stored triple,
    validated as before a hook-writing sync, and the result reports it under `dependencyHookResynced`
    (only when that sync changed a path) or `dependencyHookResyncFailed`. The sync runs even when the
    stored triple equals the one this set used: only the files say what they carry."""
    # accepted under the single-owner threat model: two sets interleaving after this re-read
    facts = core_md.read(cwd, root)
    if not facts:
        return {**write_result, "dependencyHookResyncFailed": "stored-config-unreadable"}
    stored = _hook_triple(_project_config_mapping(facts))
    # axis: equal triples do not prove the files carry them (another set may have synced other inputs between this set's sync and its write), so the idempotent sync always runs
    got = _reconcile_dependency_hook(plan["repoRoot"], stored)
    synced = got.get("dependencyHookResynced")
    if isinstance(synced, dict) and not synced.get("changed"):
        got = {k: v for k, v in got.items() if k != "dependencyHookResynced"}
    return {**write_result, **got}


def set_item(cwd, slug, value, root=None, *, account=None, project_name=None):
    """Validate and write one item to its home only."""
    item = _item_by_slug(slug)
    if item is None:
        return {"action": "refused", "reason": REASON_UNKNOWN_SLUG}

    if slug == MATERIAL_LINE_SLUG:
        # axis: an adopted item 13 refuses a set before the value is looked at — see bite-proof record wo_a_1618_adopted-set-refusal
        current = core_md.read(cwd, root)
        stored = _read_project_config_raw(_project_config_mapping(current), slug)
        if is_material_line_marker(stored):
            return _material_line_in_canon_refusal()

    reason = validate_item_value(item, value)
    if reason is not None:
        return {"action": "refused", "reason": reason}

    facts = core_md.read(cwd, root)
    if facts is None:
        if core_md.gate_config_profile_is_absent(cwd, root):
            return {"action": "refused", "reason": REASON_PROFILE_ABSENT}
        return {"action": "refused", "reason": REASON_PROFILE_UNPARSEABLE}
    if facts.get("behind"):
        return {"action": "behind", "record": facts}

    paused, paused_parts = False, None
    if slug == CLOUD_BUILDS_SLUG:
        import cloud_setup

        if project_name is None:
            project_name = os.path.basename(os.path.abspath(cwd))
        if value is True:
            # axis: cloud builds switch on only when the reader finds a ready setup record for this account — see bite-proof record wo_a_cloud-setup_switch-on-guard
            if cloud_setup.read(cwd, account, root=root).get("ready") is not True:
                return {
                    "action": "refused",
                    "reason": cloud_setup.REASON_MISSING,
                    "message": cloud_setup.switch_message("refused", project_name),
                }
            # axis: a failed-check marker never refuses the switch-on: the setting is the owner's intent, the marker only pauses the account, and the message says so
            try:
                marker = cloud_setup.read_failed_check(cwd, account, root=root)
                if marker is not None:
                    paused = True
                    parts = marker.get("failedParts")
                    if (not marker.get("damaged") and isinstance(parts, list)
                            and all(isinstance(p, str) for p in parts)):
                        paused_parts = parts
            except Exception:
                # axis: a marker read that raises counts as a damaged marker, so the switch-on says paused, never plain on
                paused, paused_parts = True, None

    plan = None
    if slug in _DEPENDENCY_HOOK_SLUGS:
        plan = _plan_dependency_hook(cwd, slug, value, facts, root)
        if plan.get("refusal") is not None:
            return plan["refusal"]

    if item["home"] == HOME_RISK_AND_TRUST:
        return _set_risk_and_trust(cwd, value, root)
    if item["home"] == HOME_GUARDIAN_CADENCE:
        write_result = core_md.write_guardian_cadence(cwd, value, root=root)
    elif slug == MATERIAL_LINE_SLUG:
        # axis: the adoption check and the write share one lock, so a set never undoes a migration — see bite-proof record wo_a_1618_set-cas
        write_result = core_md.write_project_config_item_if(
            cwd, slug, value, expected=stored, root=root)
        if write_result.get("reason") == "item-changed":
            if is_material_line_marker(write_result.get("observed")):
                return _material_line_in_canon_refusal()
            return write_result
    else:
        # axis: sibling keys in projectConfiguration survive a single-item set — wo_b_1276_one-home
        write_result = core_md.write_project_config_item(cwd, slug, value, root=root)

    if write_result.get("action") not in ("written", "noop"):
        # axis: a failed write reconciles the hook files to what is stored now, so it never undoes another set's stored update and never writes a stored credential
        if plan is not None and plan.get("hookResult") is not None:
            write_result = _converge_dependency_hook(cwd, root, plan, dict(write_result))
        return write_result

    # axis: the write went through here, so a failed or mismatched read-back keeps the synced
    # files (they match what was written) and converges them; only an uncommitted write rolls back
    reread = get_item(cwd, slug, root=root)
    if reread.get("action") == "refused":
        return _with_dependency_hook(cwd, root, plan, dict(reread))
    if not _values_equal(reread.get("raw"), value):
        return _with_dependency_hook(cwd, root, plan, {
            "action": "refused",
            "reason": REASON_SET_MISMATCH,
            "expected": value,
            "observed": reread.get("raw"),
        })
    if plan is not None and plan["deferred"]:
        refusal = _run_deferred_removal(cwd, root, plan)
        if refusal is not None:
            return refusal
    if plan is not None:
        # a failed fill never refuses the set: item 17's result carries `inputsFillFailed`
        return _finish_dependency_hook(cwd, root, plan, write_result)
    if slug == CLOUD_BUILDS_SLUG:
        if value and paused:
            return {**write_result, "message": cloud_setup.switch_message(
                "on-paused", project_name, parts=paused_parts)}
        kind = "on" if value else "off"
        return {**write_result, "message": cloud_setup.switch_message(kind, project_name)}
    return write_result


_MIGRATION_COMMIT_MESSAGE = "docs: record configure item 13 in Canon as standing rulings"
_MIGRATION_ORIGIN_PHRASE = "migrated from configure item 13"
_SESSION_PATTERN = re.compile(r"^[0-9a-z]{8}$")
_ENTRY_ID_PATTERN = re.compile(r"^- \*\*(.+?)\*\* · ")


class _MigrationRefusal(Exception):
    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _migration_result():
    return {
        "action": "refused",
        "reason": None,
        "detail": None,
        "entries": [],
        "skipped": [],
        "canonPath": None,
        "canonHome": None,
        "commit": None,
        "fetch": "not-needed",
        "sanitized": False,
    }


def _git_run(root, reason, *args, timeout=10):
    """Run ``git -C root args``; a git that cannot run is a refusal named ``reason``."""
    try:
        return subprocess.run(["git", "-C", root, *args], capture_output=True,
                              encoding="utf-8", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise _MigrationRefusal(
            reason, "git %s timed out after %ss" % (args[0], timeout))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise _MigrationRefusal(
            reason, "git could not be run (%s: %s)" % (type(exc).__name__, exc))


def _first_line(text, fallback):
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return fallback


def _split_rulings(raw):
    """Item 13's prose as one ruling per paragraph, ` · ` replaced; returns (rulings, sanitized)."""
    if not isinstance(raw, str) or not raw.strip():
        return [], False
    paragraphs = []
    current = []
    for line in raw.splitlines():
        if line.strip():
            current.append(line.strip())
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    sanitized = False
    rulings = []
    for text in paragraphs:
        while " · " in text:
            text = text.replace(" · ", "; ")
            sanitized = True
        if text.strip():
            rulings.append(text.strip())
    return rulings, sanitized


def _canon_copy_at(git_root, ref, rel):
    """Canon's text at ``ref``; empty when the path is not in that tree."""
    reason = "canon-default-probe-failed"
    tree = _git_run(git_root, reason, "ls-tree", ref, "--", rel)
    if tree.returncode != 0:
        raise _MigrationRefusal(reason, _first_line(tree.stderr, "git exit %d" % tree.returncode))
    if not tree.stdout.strip():
        return ""
    shown = _git_run(git_root, reason, "show", "%s:%s" % (ref, rel))
    if shown.returncode != 0:
        raise _MigrationRefusal(reason, _first_line(shown.stderr, "git exit %d" % shown.returncode))
    return shown.stdout


def _canon_head_copy(git_root, rel):
    """Canon's text at HEAD; empty when HEAD is unborn or the path is not in HEAD."""
    unborn = _git_run(git_root, "canon-default-probe-failed",
                      "rev-parse", "--verify", "--quiet", "HEAD")
    if unborn.returncode != 0:
        return ""
    return _canon_copy_at(git_root, "HEAD", rel)


def _entry_fields(line):
    """One Canon entry line's id, scope, ruling, migration origin and whole line; None if not one.

    The ruling is the field after the scope, exactly: Canon's rule is that a ruling never holds
    ` · `, so the fields split cleanly on it.
    """
    found = _ENTRY_ID_PATTERN.match(line)
    if not found:
        return None
    parts = canon.entry_fields(line)
    if parts is None:
        return None
    return {
        "id": found.group(1),
        "scope": parts["scope"],
        "ruling": parts["ruling"],
        "migrated": parts["where"].startswith("where: " + _MIGRATION_ORIGIN_PHRASE),
        "line": line.strip(),
    }


def _canon_entries(committed_text):
    """Every entry line in the text, migrated or not; a line too short to split keeps its id."""
    entries = []
    for line in committed_text.splitlines():
        if not line.startswith("- **"):
            continue
        fields = _entry_fields(line)
        if fields is None:
            found = _ENTRY_ID_PATTERN.match(line)
            if found:
                fields = {"id": found.group(1), "scope": None, "ruling": line, "migrated": False,
                          "line": line.strip()}
        if fields is not None:
            entries.append(fields)
    return entries


def _migrated_entries(committed_text):
    """The entries in the text that carry the migration marker."""
    return [entry for entry in _canon_entries(committed_text) if entry["migrated"]]


def _refuse_conflicting_ids(entries):
    """Refuse when an id a migrated entry carries is shared by a different entry of any kind.

    The same entry line repeated across the HEAD and default-branch copies is one entry. Entries
    that share an id and differ in any field (ruling, scope, supersession, provenance), or a
    migrated and an ordinary entry that share one, resolve for no reader
    (``rubric/canon-contract.md``), so the move never retires item 13's prose on top of them.
    """
    migrated_ids = {entry["id"] for entry in entries if entry["migrated"]}
    seen = {}
    for entry in entries:
        if entry["id"] not in migrated_ids:
            continue
        held = seen.setdefault(entry["id"], [])
        if entry["line"] not in {other["line"] for other in held}:
            held.append(entry)
    for entry_id, held in seen.items():
        if len(held) > 1:
            raise _MigrationRefusal(
                "canon-id-conflict",
                "Canon holds entries sharing the id %s, at least one of them migrated, with "
                "different fields: %s. Entries sharing one id resolve for no reader, "
                "and the duplicate goes to the owner; item 13 keeps its value until the owner has "
                "settled it."
                % (entry_id, ", ".join(
                    '"%s" (%s) scoped %s' % (
                        entry["ruling"], "migrated" if entry["migrated"] else "ordinary",
                        entry["scope"] or "unreadable")
                    for entry in held)))


def _refuse_unless_recorded_set(rulings, canon_text):
    """Refuse when migrated entries are recorded and ``rulings`` is not exactly their set.

    The move accepts one recorded state: no migrated entry yet, or migrated entries whose rulings
    are item 13's rulings, no more and no fewer. Anything else is item 13 changed after an earlier
    run, which the move never reconciles: Canon's other entries are read only for an id a migrated
    entry carries, and an entry sharing one refuses first. Returns the migrated entries.
    """
    # axis: an entry sharing a migrated entry's id, migrated or not, refuses before any adoption — see bite-proof record wo_a_1646_id-conflict
    _refuse_conflicting_ids(_canon_entries(canon_text))
    entries = _migrated_entries(canon_text)
    recorded = []
    for entry in entries:
        if entry["ruling"] not in recorded:
            recorded.append(entry["ruling"])
    if recorded and set(recorded) != set(rulings):
        raise _MigrationRefusal(
            "material-line-changed-since-migration",
            "Item 13 changed after an earlier run of the move recorded these entries: %s. Set "
            "item 13 back to exactly this text, finish the move, then record any change in Canon "
            "as a new ruling." % ", ".join('"%s"' % ruling for ruling in recorded))
    return entries


def _refuse_recorded_in_canon_for_no_rulings(cwd, root, result):
    """The recorded-set guard for an item 13 holding no ruling, which writes nothing to Canon.

    Emptying item 13 drops every ruling an earlier run recorded, so those entries stay in Canon
    while the move would retire the prose. A project with no earlier run has no migrated entry in
    either copy of Canon, so it adopts at once. Returns where Canon lives, for the readiness check.
    """
    import definition_doc
    import store_core

    try:
        repo_root = store_core.repo_root(cwd)
    except Exception as exc:
        raise _MigrationRefusal("canon-lookup-refused", str(exc))
    _fetch_default_branch(repo_root, result)
    try:
        info = definition_doc.resolve_canon(root=repo_root, cwd=cwd, store_root=root)
    except Exception as exc:
        raise _MigrationRefusal("canon-lookup-refused", str(exc))
    git_root = info["gitRoot"]
    rel = os.path.relpath(os.path.realpath(info["path"]), os.path.realpath(git_root))
    rel = rel.replace(os.sep, "/")
    default_text = ""
    if info["home"] == "repo" and info["defaultRef"]:
        default_text = _canon_copy_at(git_root, info["defaultRef"], rel)
    # axis: an emptied item 13 meets the same recorded-set refusal as a changed one — see bite-proof record wo_a_1646_replaced-ruling
    head_text = _canon_head_copy(git_root, rel)
    _refuse_unless_recorded_set([], head_text + "\n" + default_text)
    return {"gitRoot": git_root, "rel": rel, "home": info["home"], "defaultRef": info["defaultRef"],
            "defaultText": default_text}


def _ensure_gitattributes(path):
    canon.ensure_attributes(path)


def _left_as_they_are(detail):
    """``detail`` with the standing instruction for a failure after Canon's files were touched."""
    return ("%s; Canon's files are left as they are; check `git status` and `git log`, then run "
            "the move again." % detail)


def _head_sha(git_root):
    """HEAD's commit id; None when HEAD is unborn; a probe that failed otherwise is a refusal."""
    head = _git_run(git_root, "canon-commit-failed", "rev-parse", "--verify", "--quiet", "HEAD")
    if head.returncode == 0:
        return head.stdout.strip()
    # an unborn HEAD is `--quiet`'s exit 1 with nothing said; any other failure is a read error
    if head.returncode == 1 and not head.stderr.strip():
        return None
    raise _MigrationRefusal(
        "canon-commit-failed", _first_line(head.stderr, "git exit %d" % head.returncode))


def _commit_landed(git_root, rel, before_head, lines):
    """Whether the commit this run made is in HEAD: True, False, or None when git cannot say.

    A commit that errored or timed out may still have landed, since a hook after it can outlast the
    timeout. It landed when HEAD moved off ``before_head`` and the committed Canon holds ``lines``.
    A git read that fails is no evidence either way, so it is None, never False.
    """
    try:
        if _head_sha(git_root) == before_head:
            return False
        committed = _canon_copy_at(git_root, "HEAD", rel)
    except _MigrationRefusal:
        return None
    return set(lines) <= set(committed.splitlines())


def _fetch_default_branch(repo_root, result):
    """Refresh the remote refs before Canon is read; records the outcome in ``result["fetch"]``."""
    origin = _git_run(repo_root, "canon-lookup-refused", "remote", "get-url", "origin")
    if origin.returncode != 0:
        result["fetch"] = "no-origin"
    else:
        try:
            fetched = _git_run(repo_root, "canon-lookup-refused", "fetch", "origin", timeout=60)
            if fetched.returncode == 0:
                result["fetch"] = "ok"
            else:
                result["fetch"] = "failed: %s" % _first_line(
                    fetched.stderr, "git exit %d" % fetched.returncode)
        except _MigrationRefusal as exc:
            result["fetch"] = "failed: %s" % (exc.detail or exc.reason)


def _is_git_top_level(git_root):
    """True when ``git_root`` is the top level of a git repository; any failure is False.

    ``store_core.repo_root`` answers ``realpath(cwd)`` for a plain directory (greenfield), so a
    ``.git`` entry at or above ``git_root`` — or ``GIT_DIR``/``GIT_WORK_TREE`` pointing git at an
    external git directory — is required as well.
    """
    import store_core

    try:
        git_root_real = os.path.realpath(git_root)
        if store_core.repo_root(git_root) != git_root_real:
            return False
        return (store_core.git_dot_entry_ancestor(git_root) is not None
                or bool(os.environ.get("GIT_DIR") or os.environ.get("GIT_WORK_TREE")))
    except Exception:
        return False


def _write_canon_rulings(cwd, root, rulings, raw, date, session, result):
    """Canon's write procedure for ``rulings``; fills ``result`` and raises _MigrationRefusal.

    ``raw`` is the item 13 value the rulings were split from; it is read again under the lock.
    """
    import definition_doc
    import store_core

    try:
        repo_root = store_core.repo_root(cwd)
    except Exception as exc:
        raise _MigrationRefusal("canon-lookup-refused", str(exc))

    _fetch_default_branch(repo_root, result)

    try:
        info = definition_doc.resolve_canon(root=repo_root, cwd=cwd, store_root=root)
    except Exception as exc:
        raise _MigrationRefusal("canon-lookup-refused", str(exc))
    canon_path = info["path"]
    git_root = info["gitRoot"]
    result["canonPath"] = canon_path
    result["canonHome"] = info["home"]

    if not _is_git_top_level(git_root):
        raise _MigrationRefusal(
            "canon-git-root-not-a-repo",
            "%s is not the top level of a git repository" % git_root)

    rel = os.path.relpath(os.path.realpath(canon_path), os.path.realpath(git_root))
    rel = rel.replace(os.sep, "/")
    paths = [rel]
    attributes_rel = None
    if info["home"] == "repo":
        attributes_rel = "/".join(rel.split("/")[:-1] + [".gitattributes"])
        paths.append(attributes_rel)

    # axis: one writer at a time owns the Canon from baseline read through commit — see bite-proof record wo_a_1618_canon-lock
    with core_md.mode_registry.config_lock(cwd, root) as got:
        if not got:
            raise _MigrationRefusal(
                "canon-lock-contended",
                "another writer holds the project store's configuration lock; run the move again")
        # axis: item 13 is read again under the lock, so a set that landed during the fetch is never recorded as a standing ruling — see bite-proof record wo_a_1646_locked-recheck
        facts = core_md.read(cwd, root)
        current = _read_project_config_raw(_project_config_mapping(facts), MATERIAL_LINE_SLUG)
        if current != raw:
            raise _MigrationRefusal("material-line-changed-during-migration")
        return _append_canon_rulings(
            result, info, git_root, rel, paths, attributes_rel, rulings, date, session)


def _append_canon_rulings(result, info, git_root, rel, paths, attributes_rel, rulings, date,
                          session):
    """The locked half of Canon's write procedure: baseline, append, commit, prefix check."""
    canon_path = info["path"]
    # axis: a Canon with uncommitted changes is never built on — see bite-proof record wo_a_1618_clean-baseline
    status = _git_run(git_root, "canon-dirty", "status", "--porcelain",
                      "--untracked-files=all", "--", *paths, timeout=60)
    if status.returncode != 0:
        raise _MigrationRefusal("canon-dirty", _first_line(status.stderr, "git status failed"))
    if status.stdout.strip():
        raise _MigrationRefusal("canon-dirty", status.stdout.rstrip("\n"))

    default_text = ""
    if info["home"] == "repo" and info["defaultRef"]:
        default_text = _canon_copy_at(git_root, info["defaultRef"], rel)
    head_text = _canon_head_copy(git_root, rel)

    # axis: only a committed entry counts as already recorded — see bite-proof record wo_a_1618_committed-only-dedupe
    # axis: migrated entries an earlier run recorded refuse the move unless they are exactly item 13's rulings — see bite-proof record wo_a_1646_replaced-ruling
    recorded = _refuse_unless_recorded_set(rulings, head_text + "\n" + default_text)
    result["skipped"] = list(dict.fromkeys(entry["id"] for entry in recorded))
    # axis: nothing new to append means no commit at all — see bite-proof record wo_a_1618_never-commit-empty
    if recorded:
        return {"gitRoot": git_root, "rel": rel, "home": info["home"],
                "defaultRef": info["defaultRef"], "defaultText": default_text}

    attributes_path = None
    if attributes_rel is not None:
        attributes_path = os.path.join(os.path.realpath(git_root), *attributes_rel.split("/"))

    prefix = "%s-%s-" % (date, session)
    before_head = _head_sha(git_root)
    # axis: once the move begins writing, no Canon file is rewritten, truncated or removed; a failure leaves them as the failure left them and the clean-baseline guard stops the next run — see bite-proof record wo_a_1646_canon-no-rollback
    try:
        os.makedirs(os.path.dirname(canon_path), exist_ok=True)
        # the attributes line goes in before canon.md exists, so an unwritable one fails with no Canon created
        if attributes_path is not None:
            _ensure_gitattributes(attributes_path)
        working_text = ""
        if os.path.isfile(canon_path):
            with open(canon_path, encoding="utf-8") as fh:
                working_text = fh.read()
        else:
            with open(canon_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(canon.HEADER)

        first = canon.next_seq(prefix, working_text, default_text)
        ids = ["%s%d" % (prefix, first + i) for i in range(len(rulings))]
        lines = [
            canon.entry_line(
                entry_id, date, "standing", ruling, "owner's words: none recorded",
                "%s on %s (original session unknown), time not recorded"
                % (_MIGRATION_ORIGIN_PHRASE, date))
            for entry_id, ruling in zip(ids, rulings)
        ]
        with open(canon_path, "a", encoding="utf-8", newline="\n") as fh:
            if working_text and not working_text.endswith("\n"):
                fh.write("\n")
            fh.write("\n".join(lines) + "\n")
    except OSError as exc:
        raise _MigrationRefusal(
            "canon-write-failed", _left_as_they_are("%s: %s" % (type(exc).__name__, exc)))

    try:
        added = _git_run(git_root, "canon-commit-failed", "add", "--", *paths)
    except _MigrationRefusal as exc:
        raise _MigrationRefusal(
            "canon-commit-failed", _left_as_they_are(exc.detail or exc.reason))
    if added.returncode != 0:
        raise _MigrationRefusal(
            "canon-commit-failed",
            _left_as_they_are(_first_line(added.stderr, "git add exit %d" % added.returncode)))
    commit_failure = None
    try:
        committed = _git_run(git_root, "canon-commit-failed", "commit", "-m",
                             _MIGRATION_COMMIT_MESSAGE, "--", *paths)
        if committed.returncode != 0:
            commit_failure = (committed.stderr or committed.stdout).strip()
    except _MigrationRefusal as exc:
        commit_failure = exc.detail or exc.reason
    if commit_failure is not None:
        # axis: a commit that errored or timed out continues only when HEAD shows it landed — see bite-proof record wo_a_1646_commit-landed
        outcome = _commit_landed(git_root, rel, before_head, lines)
        if outcome is not True:
            if outcome is None:
                commit_failure = "%s; git could not say whether the commit landed" % commit_failure
            raise _MigrationRefusal("canon-commit-failed", _left_as_they_are(commit_failure))
    result["entries"] = ids

    shown = _git_run(git_root, "canon-commit-failed", "show", "HEAD:%s" % rel)
    new_text = shown.stdout if shown.returncode == 0 else ""
    # axis: the commit extends the prior HEAD copy and holds every appended line — see bite-proof record wo_a_1618_prefix-check
    if not new_text.startswith(head_text) or not set(lines) <= set(new_text.splitlines()):
        raise _MigrationRefusal(
            "canon-commit-failed", "the committed Canon does not hold the appended entries")
    head = _git_run(git_root, "canon-commit-failed", "rev-parse", "HEAD")
    result["commit"] = head.stdout.strip() or None
    return {"gitRoot": git_root, "rel": rel, "home": info["home"],
            "defaultRef": info["defaultRef"], "defaultText": default_text}


def _rulings_unreachable_from_default(rulings, canon):
    """True when the default branch's Canon does not yet hold every migrated ruling.

    Only a Canon in the repository rides a branch; the project store's Canon is one shared copy,
    so it adopts in one step. The marker is written when every ruling is in the default-branch
    copy, wherever core.md lives. With no default ref (no origin remote) nothing shows that
    another branch or worktree reads the entries, so the move stays pending.
    """
    if canon["home"] != "repo":
        return False
    if not canon["defaultRef"]:
        return bool(rulings)
    # axis: the readiness check reads the default-branch copy the recorded-set check read, never a second one — see bite-proof record wo_a_1646_single-default-read
    held = {entry["ruling"] for entry in _migrated_entries(canon["defaultText"])}
    return not set(rulings) <= held


def migrate_material_line(cwd, *, root=None, session=None, date=None):
    """Move item 13's rulings into committed Canon, then swap item 13 for the Canon pointer."""
    result = _migration_result()
    try:
        _migrate_material_line(cwd, root, session, date, result)
    except _MigrationRefusal as refusal:
        result["action"] = "refused"
        result["reason"] = refusal.reason
        result["detail"] = refusal.detail
    except OSError as exc:
        result["action"] = "refused"
        result["reason"] = "canon-write-failed"
        result["detail"] = "%s: %s" % (type(exc).__name__, exc)
    return result


def _migrate_material_line(cwd, root, session, date, result):
    facts = core_md.read(cwd, root)
    if facts is None:
        if core_md.gate_config_profile_is_absent(cwd, root):
            raise _MigrationRefusal(REASON_PROFILE_ABSENT)
        raise _MigrationRefusal(REASON_PROFILE_UNPARSEABLE)
    if facts.get("behind"):
        raise _MigrationRefusal("behind")

    # axis: an ambiguous profile refuses before the marker is believed or Canon is touched, since core_md.read picked this item 13 value out of it — see bite-proof record wo_a_1646_structural-before-canon
    structural = core_md.profile_structural_refusal(cwd, root)
    if structural is not None:
        raise _MigrationRefusal("profile-structurally-ambiguous", structural)

    raw = _read_project_config_raw(_project_config_mapping(facts), MATERIAL_LINE_SLUG)
    if is_material_line_marker(raw):
        result["action"] = "already-adopted"
        return
    if raw is not None and not isinstance(raw, str):
        raise _MigrationRefusal(REASON_MALFORMED_VALUE)

    if session is None:
        session = secrets.token_hex(4)
    else:
        session = str(session).strip().lower()[:8]
        if not _SESSION_PATTERN.match(session):
            raise _MigrationRefusal("session-id-malformed")
    if date is None:
        date = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    else:
        try:
            if datetime.date.fromisoformat(date).isoformat() != date:
                raise ValueError(date)
        except (TypeError, ValueError):
            raise _MigrationRefusal("date-malformed")

    rulings, result["sanitized"] = _split_rulings(raw)
    if rulings:
        canon = _write_canon_rulings(cwd, root, rulings, raw, date, session, result)
    else:
        canon = _refuse_recorded_in_canon_for_no_rulings(cwd, root, result)
    # axis: a shared item 13 keeps its examples until Canon's entries reach the default branch — see bite-proof record wo_a_1618_pending-default-branch
    if _rulings_unreachable_from_default(rulings, canon):
        result["action"] = "pending-default-branch"
        if canon["defaultRef"]:
            result["detail"] = (
                "Canon on this branch holds entries the default branch does not (the recorded "
                "rulings), and item 13 keeps its value until they reach the default branch. "
                "Run the move again after the branch lands to finish it.")
        else:
            result["detail"] = (
                "The Canon entries are committed on this branch, but this repository has no "
                "origin remote, so nothing shows that other branches and worktrees can read "
                "them. Item 13 keeps its value; the move finishes once the repository has an "
                "origin default branch holding them. Add an origin remote, land the entries, "
                "and run the move again.")
        return

    marker = {"canon": MATERIAL_LINE_MARKER_CANON, "migratedOn": date}
    # axis: the marker lands only if item 13 still equals the snapshot — see bite-proof record wo_a_1618_cas-compare
    written = core_md.write_project_config_item_if(
        cwd, MATERIAL_LINE_SLUG, marker, expected=raw, root=root)
    if written.get("action") not in ("written", "noop"):
        if written.get("reason") == "item-changed":
            raise _MigrationRefusal("material-line-changed-during-migration")
        raise _MigrationRefusal(
            "marker-write-failed", str(written.get("reason") or written.get("action")))
    result["action"] = "migrated"


def _detect_launch_ledger(cwd, root):
    try:
        import launch_ledger as ll
        import store_core

        repo_root = store_core.repo_root(cwd)
        info = ll.ledger_path(repo_root)
        if info.get("ok") and info.get("path") and os.path.isfile(info["path"]):
            with open(info["path"], encoding="utf-8") as fh:
                fh.read(1)
            return "detected"
    except Exception:
        pass
    return None


def _declared_dependencies_mapping(facts):
    if not isinstance(facts, dict):
        return {}
    declared = facts.get("declaredDependencies")
    if declared is None:
        return {}
    if not isinstance(declared, dict):
        return {}
    return dict(declared)


def _validate_dependency_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        if not value.strip():
            return REASON_MALFORMED_VALUE
        return None
    if isinstance(value, dict):
        return None
    return REASON_MALFORMED_VALUE


def declare_dependency(cwd, slug, value, root=None):
    """Declare or withdraw one dependency in ``declaredDependencies`` only."""
    if slug not in _DEPENDENCY_FALLBACKS:
        return {"action": "refused", "reason": REASON_UNKNOWN_SLUG}

    reason = _validate_dependency_value(value)
    if reason is not None:
        return {"action": "refused", "reason": reason}

    facts = core_md.read(cwd, root)
    if facts is None:
        if core_md.gate_config_profile_is_absent(cwd, root):
            return {"action": "refused", "reason": REASON_PROFILE_ABSENT}
        return {"action": "refused", "reason": REASON_PROFILE_UNPARSEABLE}
    if facts.get("behind"):
        return {"action": "behind", "record": facts}

    # axis: sibling declarations survive a single dependency declare — wo_h_1276_sibling-declarations
    if value is None and slug not in _declared_dependencies_mapping(facts):
        return {"action": "noop"}
    write_result = core_md.write_declared_dependency_item(cwd, slug, value, root=root)
    if write_result.get("action") not in ("written", "noop"):
        return write_result

    reread = _declared_dependencies_mapping(core_md.read(cwd, root))
    if value is None:
        if slug in reread:
            return {
                "action": "refused",
                "reason": REASON_SET_MISMATCH,
                "expected": None,
                "observed": reread.get(slug),
            }
    elif not _values_equal(reread.get(slug), value):
        return {
            "action": "refused",
            "reason": REASON_SET_MISMATCH,
            "expected": value,
            "observed": reread.get(slug),
        }
    return write_result


def dependencies(cwd, root=None):
    """Report the four declared dependencies and their status. Never blocks."""
    facts = core_md.read(cwd, root) or {}
    declared = facts.get("declaredDependencies") or {}
    if not isinstance(declared, dict):
        declared = {}

    out = {}
    launch = _detect_launch_ledger(cwd, root)
    if launch:
        out["launchLedger"] = {"status": "detected"}
    elif "launchLedger" in declared:
        out["launchLedger"] = {"status": "declared"}
    else:
        out["launchLedger"] = {
            "status": "absent",
            "fallback": _DEPENDENCY_FALLBACKS["launchLedger"],
        }

    if "collector" in declared:
        out["collector"] = {"status": "declared"}
    else:
        out["collector"] = {
            "status": "absent",
            "fallback": _DEPENDENCY_FALLBACKS["collector"],
        }

    if "keepOrRetireBackfill" in declared:
        out["keepOrRetireBackfill"] = {"status": "declared"}
    else:
        out["keepOrRetireBackfill"] = {
            "status": "absent",
            "fallback": _DEPENDENCY_FALLBACKS["keepOrRetireBackfill"],
        }

    if "detectorTestBoundary" in declared:
        out["detectorTestBoundary"] = {"status": "declared"}
    else:
        out["detectorTestBoundary"] = {
            "status": "absent",
            "fallback": _DEPENDENCY_FALLBACKS["detectorTestBoundary"],
        }

    return out


def main(argv):
    ap = argparse.ArgumentParser(prog="project_config")
    sub = ap.add_subparsers(dest="cmd", required=True)

    vp = sub.add_parser("view")
    vp.add_argument("--cwd", default=".")
    vp.add_argument("--root", default=None)

    gp = sub.add_parser("get")
    gp.add_argument("--item", required=True)
    gp.add_argument("--cwd", default=".")
    gp.add_argument("--root", default=None)

    sp = sub.add_parser("set")
    sp.add_argument("--item", required=True)
    sp.add_argument("--cwd", default=".")
    sp.add_argument("--root", default=None)
    sp.add_argument("--account", default=None)
    sp.add_argument("--project-name", default=None)

    dp = sub.add_parser("dependencies")
    dp.add_argument("--cwd", default=".")
    dp.add_argument("--root", default=None)

    mp = sub.add_parser("migrate-material-line")
    mp.add_argument("--cwd", default=".")
    mp.add_argument("--root", default=None)
    mp.add_argument("--session", default=None)
    mp.add_argument("--date", default=None)

    decl = sub.add_parser("declare")
    decl.add_argument("--dependency", required=True)
    decl.add_argument("--cwd", default=".")
    decl.add_argument("--root", default=None)

    args = ap.parse_args(argv)

    if args.cmd == "view":
        out = view(args.cwd, root=args.root)
    elif args.cmd == "get":
        out = get_item(args.cwd, args.item, root=args.root)
    elif args.cmd == "set":
        raw = sys.stdin.read()
        try:
            value = json.loads(raw) if raw.strip() else None
        except ValueError:
            out = {"action": "refused", "reason": "input-unparseable"}
        else:
            account = args.account
            if args.item == CLOUD_BUILDS_SLUG and account is None:
                import cloud_setup

                account = cloud_setup.launching_account(cwd=os.path.abspath(args.cwd))
            out = set_item(
                args.cwd, args.item, value, root=args.root,
                account=account, project_name=args.project_name)
    elif args.cmd == "migrate-material-line":
        out = migrate_material_line(
            args.cwd, root=args.root, session=args.session, date=args.date)
    elif args.cmd == "declare":
        raw = sys.stdin.read()
        try:
            value = json.loads(raw) if raw.strip() else None
        except ValueError:
            out = {"action": "refused", "reason": "input-unparseable"}
        else:
            out = declare_dependency(
                args.cwd, args.dependency, value, root=args.root)
    else:
        out = dependencies(args.cwd, root=args.root)

    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
