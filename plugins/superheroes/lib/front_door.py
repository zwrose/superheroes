#!/usr/bin/env python3
"""Front-door grading: one helper path for tier claims against the severity ladder."""
import argparse
import json
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import core_md  # noqa: E402
import project_config  # noqa: E402

REASON_LADDER_UNSTAMPED = "ladder-unstamped"
REASON_BAND_UNKNOWN = "band-unknown"
REASON_EVIDENCE_ARGUED = "evidence-argued"
REASON_P0_BAND_EXCLUDED = "p0-band-excluded"
REASON_P0_DEFINITION_NAMES_NO_BAND = "p0-definition-names-no-band"
REASON_P0_EVIDENCE_EXCLUDED = "p0-evidence-excluded"
REASON_BAND_WITHOUT_LADDER = "band-without-ladder"
REASON_BAND_REQUIRED = "band-required"
REASON_CLAIM_NOT_OBJECT = "claim-not-object"
REASON_CLAIM_MISSING_TIER = "claim-missing-tier"
REASON_TIER_UNKNOWN = "tier-unknown"
REASON_EVIDENCE_UNKNOWN = "evidence-unknown"
REASON_INPUT_UNPARSEABLE = "input-unparseable"

_VALID_TIERS = frozenset({"P0", "P1", "P2", "declined"})
_PASSING_EVIDENCE = frozenset({"field", "lab"})
_AUTHORITY_TIERS = frozenset({"P0", "P1", "P2"})
_BANDED_TIERS = frozenset({"P0", "P1", "P2"})


def _item(payload, slug):
    for entry in payload["items"]:
        if entry["slug"] == slug:
            return entry
    return None


def _record(band, tier, evidence):
    return {"band": band, "tier": tier, "evidence": evidence}


def _result(outcome, tier, reason, band, claim_tier, evidence):
    return {
        "outcome": outcome,
        "tier": tier,
        "reason": reason,
        "record": _record(band, claim_tier, evidence),
    }


def _refused(reason, band, claim_tier, evidence):
    return _result("refused", None, reason, band, claim_tier, evidence)


def _queued(reason, band, claim_tier, evidence):
    return _result("queued", None, reason, band, claim_tier, evidence)


def _graded(granted_tier, band, evidence):
    return _result("graded", granted_tier, None, band, granted_tier, evidence)


def _profile_refusal(cwd, root, payload):
    if payload.get("behind"):
        return core_md.BUILDER_DISPATCH_DEFER_SCHEMA_BEHIND
    if payload.get("profileAbsent") or payload.get("profileUnparseable"):
        if core_md.gate_config_profile_is_absent(cwd, root):
            return project_config.REASON_PROFILE_ABSENT
        return project_config.REASON_PROFILE_UNPARSEABLE
    structural = core_md.profile_structural_refusal(cwd, root)
    if structural is not None:
        return structural
    return None


def _ladder_band_names(ladder):
    if not isinstance(ladder, list):
        return []
    names = []
    for band in ladder:
        if not isinstance(band, dict):
            continue
        name = band.get("name")
        if isinstance(name, str) and name.strip():
            names.append(name)
    return names


def _ladder_is_stamped(ladder_entry):
    if ladder_entry.get("malformed"):
        return False
    return ladder_entry.get("source") == "stamped" and ladder_entry.get("effective") is not None


def _band_reference_tokens(name):
    tokens = [name]
    if "," in name:
        prefix = name.split(",", 1)[0].strip()
        if prefix and prefix != name:
            tokens.append(prefix)
    return tokens


def _p0_bands_named_in_prose(prose, names):
    matched = set()
    for name in names:
        for token in _band_reference_tokens(name):
            if prose.startswith(token):
                matched.add(name)
                break
    return matched


def _p0_required_evidence(prose):
    lower = prose.lower()
    required = set()
    if "field evidence" in lower:
        required.add("field")
    if "lab evidence" in lower:
        required.add("lab")
    return required or None


def _p0_policy(ladder_entry, p0_entry):
    """Return (allowed_bands, required_evidence, refuse_reason)."""
    names = _ladder_band_names(ladder_entry.get("effective"))
    if not names:
        return None, None, project_config.REASON_MALFORMED_VALUE
    top = names[0]
    if p0_entry.get("malformed"):
        return None, None, project_config.REASON_MALFORMED_VALUE
    if p0_entry.get("source") != "stamped":
        return {top}, None, None
    prose = p0_entry.get("effective")
    if not isinstance(prose, str) or not prose.strip():
        return None, None, project_config.REASON_MALFORMED_VALUE
    allowed = _p0_bands_named_in_prose(prose, names)
    if not allowed:
        return None, None, REASON_P0_DEFINITION_NAMES_NO_BAND
    return allowed, _p0_required_evidence(prose), None


def _unstamped_ladder_outcome(tier, band, evidence):
    if evidence == "argued":
        return _refused(REASON_EVIDENCE_ARGUED, band, tier, evidence)
    if tier == "P2":
        return _queued(REASON_LADDER_UNSTAMPED, band, tier, evidence)
    return _refused(REASON_LADDER_UNSTAMPED, band, tier, evidence)


def grade(cwd, claim, root=None):
    """Grade one front-door claim against the project's configuration."""
    if not isinstance(claim, dict):
        return _refused(REASON_CLAIM_NOT_OBJECT, None, None, None)

    tier = claim.get("tier")
    if tier is None:
        return _refused(REASON_CLAIM_MISSING_TIER, claim.get("band"), None, claim.get("evidence"))
    if tier not in _VALID_TIERS:
        return _refused(REASON_TIER_UNKNOWN, claim.get("band"), tier, claim.get("evidence"))

    band = claim.get("band")
    evidence = claim.get("evidence")
    if evidence not in _PASSING_EVIDENCE and evidence != "argued":
        return _refused(REASON_EVIDENCE_UNKNOWN, band, tier, evidence)

    payload = project_config.read(cwd, root)
    profile_reason = _profile_refusal(cwd, root, payload)
    if profile_reason is not None:
        return _refused(profile_reason, band, tier, evidence)

    ladder_entry = _item(payload, "severityLadder")
    p0_entry = _item(payload, "p0Definition")
    ladder_stamped = _ladder_is_stamped(ladder_entry)

    if tier == "declined":
        if evidence == "argued":
            return _refused(REASON_EVIDENCE_ARGUED, band, tier, evidence)
        return _graded("declined", band, evidence)

    if ladder_entry.get("malformed") and ladder_entry.get("raw") is not None:
        return _refused(project_config.REASON_MALFORMED_VALUE, band, tier, evidence)

    if band is not None and not ladder_stamped:
        return _unstamped_ladder_outcome(tier, band, evidence)

    if not ladder_stamped:
        return _unstamped_ladder_outcome(tier, band, evidence)

    if tier in _BANDED_TIERS and band is None:
        return _refused(REASON_BAND_REQUIRED, band, tier, evidence)

    if evidence == "argued":
        return _refused(REASON_EVIDENCE_ARGUED, band, tier, evidence)

    if ladder_entry.get("malformed"):
        return _refused(project_config.REASON_MALFORMED_VALUE, band, tier, evidence)

    ladder = ladder_entry.get("effective")
    band_names = _ladder_band_names(ladder)
    if not band_names:
        return _refused(project_config.REASON_MALFORMED_VALUE, band, tier, evidence)

    if band not in band_names:
        return _refused(REASON_BAND_UNKNOWN, band, tier, evidence)

    if tier == "P0":
        allowed, required_evidence, refuse_reason = _p0_policy(ladder_entry, p0_entry)
        if refuse_reason is not None:
            return _refused(refuse_reason, band, tier, evidence)
        if band not in allowed:
            return _refused(REASON_P0_BAND_EXCLUDED, band, tier, evidence)
        if required_evidence is not None and evidence not in required_evidence:
            return _refused(REASON_P0_EVIDENCE_EXCLUDED, band, tier, evidence)
        return _graded("P0", band, evidence)

    if tier == "P1":
        return _graded("P1", band, evidence)

    return _graded("P2", band, evidence)


def main(argv):
    ap = argparse.ArgumentParser(prog="front_door")
    sub = ap.add_subparsers(dest="cmd", required=True)

    gp = sub.add_parser("grade")
    gp.add_argument("--cwd", default=".")
    gp.add_argument("--root", default=None)

    args = ap.parse_args(argv)

    if args.cmd == "grade":
        raw = sys.stdin.read()
        try:
            claim = json.loads(raw) if raw.strip() else None
        except ValueError:
            out = _refused(REASON_INPUT_UNPARSEABLE, None, None, None)
        else:
            out = grade(args.cwd, claim, root=args.root)
    else:
        out = _refused(REASON_CLAIM_NOT_OBJECT, None, None, None)

    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
