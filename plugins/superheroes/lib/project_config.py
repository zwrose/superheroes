#!/usr/bin/env python3
"""The thirteen configuration items: one registry, one read contract, one setter per home.

Stdlib only. Every item's value is read and written only through this module and the
``core_md`` writers it routes to."""
import argparse
import json
import math
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import core_md  # noqa: E402
import guardian_sweep  # noqa: E402

HOME_PROJECT_CONFIGURATION = "projectConfiguration"
HOME_THREAT_MODEL = "threatModel"
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
        "slug": "threatModel",
        "name": "Threat model",
        "home": HOME_THREAT_MODEL,
        "shape": "prose",
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
    if not isinstance(value, list):
        return REASON_MALFORMED_VALUE
    for band in value:
        if not isinstance(band, dict):
            return REASON_MALFORMED_VALUE
        if not isinstance(band.get("name"), str) or not band.get("name").strip():
            return REASON_MALFORMED_VALUE
        examples = band.get("examples")
        if not isinstance(examples, list):
            return REASON_MALFORMED_VALUE
        for example in examples:
            if not isinstance(example, dict):
                return REASON_MALFORMED_VALUE
            if not isinstance(example.get("text"), str):
                return REASON_MALFORMED_VALUE
            citation = example.get("citation")
            if not isinstance(citation, str) or not citation.strip():
                return REASON_LADDER_CITATION_REQUIRED
    return None


_VALIDATORS = {
    "prose": _validate_prose,
    "proseList": _validate_prose_list,
    "pathList": _validate_path_list,
    "boolean": _validate_boolean,
    "dial": _validate_dial,
    "budgetN": _validate_budget_n,
    "conditionWindows": _validate_condition_windows,
    "guardianCadence": _validate_guardian_cadence,
    "severityLadder": _validate_severity_ladder,
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


def _guardian_cadence_raw(cwd, root):
    import guardian_store

    try:
        layer_p = guardian_store.guardian_layer_path(cwd, root)
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


def _resolve_item_entry(item, raw, *, dial_effective=None, guardian_cfg=None):
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

    if slug == "threatModel":
        if isinstance(raw, str) and raw.strip():
            return {
                "raw": raw,
                "effective": raw,
                "source": "stamped",
                "malformed": False,
            }
        if raw is not None and not isinstance(raw, str):
            malformed = True
        return {
            "raw": raw if raw is not None else None,
            "effective": None,
            "source": "unset",
            "malformed": malformed,
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


def read(cwd, root=None):
    """Return every configuration item with ``raw``, ``effective``, and ``source``."""
    facts = core_md.read(cwd, root)
    guardian_cfg = guardian_sweep.read_config(cwd, root)
    if facts is None:
        absent_items = []
        dial_entry = _resolve_item_entry(_SLUG_INDEX["dial"], None)
        for item in ITEMS:
            slug = item["slug"]
            if item["home"] == HOME_THREAT_MODEL:
                raw = None
            elif item["home"] == HOME_GUARDIAN_CADENCE:
                raw = _guardian_cadence_raw(cwd, root)
            else:
                raw = None
            entry = _resolve_item_entry(
                item,
                raw,
                dial_effective=dial_entry["effective"],
                guardian_cfg=guardian_cfg,
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
        if item["home"] == HOME_THREAT_MODEL:
            raw = facts.get("threatModel")
            if isinstance(raw, str) and not raw.strip():
                raw = None
        elif item["home"] == HOME_GUARDIAN_CADENCE:
            raw = _guardian_cadence_raw(cwd, root)
        else:
            raw = _read_project_config_raw(mapping, slug)
        entry = _resolve_item_entry(
            item,
            raw,
            dial_effective=dial_entry["effective"],
            guardian_cfg=guardian_cfg,
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
    """Return all thirteen items in registry order for display."""
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


def get_item(cwd, slug, root=None):
    """Return one item's read contract, or a refusal when the slug is unknown."""
    item = _item_by_slug(slug)
    if item is None:
        return {"action": "refused", "reason": REASON_UNKNOWN_SLUG}
    payload = read(cwd, root)
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


def set_item(cwd, slug, value, root=None):
    """Validate and write one item to its home only."""
    item = _item_by_slug(slug)
    if item is None:
        return {"action": "refused", "reason": REASON_UNKNOWN_SLUG}

    reason = validate_item_value(item, value)
    if reason is not None:
        return {"action": "refused", "reason": reason}

    facts = core_md.read(cwd, root)
    if facts is None:
        try:
            path = core_md.core_path(cwd, root)
            cls = core_md._classify_core_md_at_path(path)
            if cls.status == core_md.CONFIG_ABSENT:
                return {"action": "refused", "reason": REASON_PROFILE_ABSENT}
        except Exception:
            pass
        return {"action": "refused", "reason": REASON_PROFILE_UNPARSEABLE}
    if facts.get("behind"):
        return {"action": "behind", "record": facts}

    if item["home"] == HOME_THREAT_MODEL:
        write_result = core_md.write_threat_model(cwd, value, root=root)
    elif item["home"] == HOME_GUARDIAN_CADENCE:
        write_result = core_md.write_guardian_cadence(cwd, value, root=root)
    else:
        # axis: sibling keys in projectConfiguration survive a single-item set — wo_b_1276_one-home
        mapping = dict(_project_config_mapping(facts))
        mapping[slug] = value
        write_result = core_md.write_project_config(cwd, mapping, root=root)

    if write_result.get("action") not in ("written", "noop"):
        return write_result

    reread = get_item(cwd, slug, root=root)
    if reread.get("action") == "refused":
        return reread
    if not _values_equal(reread.get("raw"), value):
        return {
            "action": "refused",
            "reason": REASON_SET_MISMATCH,
            "expected": value,
            "observed": reread.get("raw"),
        }
    return write_result


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


def _detect_detector_test_boundary():
    path = os.path.normpath(os.path.join(_LIB_DIR, "..", "rubric", "bite-proof.md"))
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                fh.read(1)
            return "detected"
        except OSError:
            pass
    return None


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

    detector = _detect_detector_test_boundary()
    if detector:
        out["detectorTestBoundary"] = {"status": "detected"}
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

    dp = sub.add_parser("dependencies")
    dp.add_argument("--cwd", default=".")
    dp.add_argument("--root", default=None)

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
            out = set_item(args.cwd, args.item, value, root=args.root)
    else:
        out = dependencies(args.cwd, root=args.root)

    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
