#!/usr/bin/env python3
"""Load model-tier overrides from the review-crew profile.

Reads the optional `## Model tiers` block out of the resolved review-crew profile and
emits a {role: model} JSON map for `model_tier_resolve.py`'s --overrides seam. The block
is plain `role: model` lines under a `## Model tiers` heading, e.g.:

    ## Model tiers
    reviewer-deep: opus
    mechanical: sonnet

Fail-OPEN: a missing profile, missing block, malformed line, or unknown role yields {}
(or drops the bad key) — the knob then uses its band defaults. A wrong/absent override is
a cost concern, never a safety one. stdlib only.
"""
import json
import os
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

# Mirrors the core's DEFAULT_TIERS keys (the-architect/lib/model_tier.py); a role not in
# this set is an owner typo and is dropped (fail-open to the default).
KNOWN_ROLES = ("orchestrator", "reviewer", "reviewer-deep", "mechanical", "synthesis", "fixer", "author")
KNOWN_MODELS = ("haiku", "sonnet", "opus", "fable")

_HEADING = re.compile(r"^\s*##\s+[Mm]odel tiers\s*$")
_NEXT_HEADING = re.compile(r"^\s*##\s+")
_ENTRY = re.compile(r"^\s*([A-Za-z][A-Za-z-]*)\s*:\s*(\S+)\s*$")


def load_overrides(profile_path):
    """Return {role: model} from the profile's `## Model tiers` block, or {}. Never raises."""
    if not profile_path:
        return {}
    try:
        with open(profile_path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return {}
    out = {}
    in_block = False
    for line in text.splitlines():
        if _HEADING.match(line):
            in_block = True
            continue
        if in_block and _NEXT_HEADING.match(line):
            break
        if in_block:
            m = _ENTRY.match(line)
            if m and m.group(1) in KNOWN_ROLES:
                out[m.group(1)] = m.group(2)
    return out


def _read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _write_text(path, text):
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, f".{os.path.basename(path)}.tmp.{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def effective_tiers(profile_path):
    """Return DEFAULT_TIERS merged with the profile override block, keyed by public role name."""
    import model_tier
    overrides = load_overrides(profile_path)
    return {role: model_tier.resolve_model(role, overrides) for role in KNOWN_ROLES}


def _normalize_updates(updates):
    out = {}
    warnings = []
    for role, model in (updates or {}).items():
        if role not in KNOWN_ROLES:
            warnings.append(f"unknown role: {role} (dropped)")
            continue
        if model is None:
            continue
        if not isinstance(model, str) or not model.strip():
            warnings.append(f"empty model for {role} (cleared)")
            continue
        model = model.strip()
        if model not in KNOWN_MODELS:
            warnings.append(f"unknown model for {role}: {model} (kept)")
        out[role] = model
    return out, warnings


def _render_block(overrides):
    lines = ["## Model tiers"]
    for role in KNOWN_ROLES:
        if role in overrides:
            lines.append(f"{role}: {overrides[role]}")
    return "\n".join(lines) + "\n"


def replace_model_tiers_block(text, overrides):
    """Create or replace only the `## Model tiers` block, preserving all other sections."""
    block = _render_block(overrides)
    lines = text.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if _HEADING.match(line):
            start = i
            break
    if start is None:
        if not text:
            return block
        sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
        return text + sep + block
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if _NEXT_HEADING.match(lines[j]):
            end = j
            break
    return "".join(lines[:start]) + block + "".join(lines[end:])


def update_overrides(profile_path, set_overrides=None, clear_roles=None):
    """Mutate the resolved profile's model-tier block and return the new effective state.

    Unknown roles are dropped. Unknown model strings are kept with a warning so newly available
    models, including owner-approved experiments, do not require a plugin release before use.
    """
    if not profile_path:
        raise ValueError("profile_path is required")
    current = load_overrides(profile_path)
    warnings = []
    for role in clear_roles or []:
        if role not in KNOWN_ROLES:
            warnings.append(f"unknown role: {role} (dropped)")
            continue
        current.pop(role, None)
    normalized, update_warnings = _normalize_updates(set_overrides)
    warnings.extend(update_warnings)
    current.update(normalized)
    text = _read_text(profile_path)
    _write_text(profile_path, replace_model_tiers_block(text, current))
    return {
        "ok": True,
        "path": profile_path,
        "overrides": load_overrides(profile_path),
        "effective": effective_tiers(profile_path),
        "warnings": warnings,
        "knownRoles": list(KNOWN_ROLES),
        "knownModels": list(KNOWN_MODELS),
    }


def resolve_profile_path(cwd=None):
    return _resolve_profile_path(cwd)


def _resolve_profile_path(cwd=None):
    """Auto-resolve the project's review-crew profile path when no --profile was given.

    Uses the same sibling resolver review-crew uses (review_store.resolve --kind profile);
    returns the resolved path only when one actually exists on disk, else None. Fail-SAFE:
    ANY error (import failure, resolver exception, location:none, missing file) yields None
    so the caller degrades to {} — this MUST NOT crash startup, and a throwaway run with no
    profile correctly stays a no-op. An explicit --profile bypasses this entirely.
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import review_store  # sibling lib; in-process resolve (no extra subprocess/exec)
        info = review_store.resolve(cwd or os.getcwd(), "profile", review_store.store_root())
        path = info.get("path")
        if path and info.get("exists") and os.path.isfile(path):
            return path
    except Exception:
        return None
    return None


def main(argv):
    import argparse
    raw = argv[1:]
    if raw and raw[0] in ("show", "write"):
        cmd = raw[0]
        ap = argparse.ArgumentParser(description="review-crew model-tier override configurator")
        ap.add_argument("--profile", default=None)
        if cmd == "write":
            ap.add_argument("--set", action="append", default=[], metavar="ROLE=MODEL")
            ap.add_argument("--clear", action="append", default=[], metavar="ROLE")
        args = ap.parse_args(raw[1:])
        profile = args.profile if args.profile is not None else _resolve_profile_path()
        if not profile:
            sys.stdout.write(json.dumps({"ok": False, "reason": "profile-not-resolved"}) + "\n")
            return 1
        if cmd == "show":
            sys.stdout.write(json.dumps({
                "ok": True,
                "path": profile,
                "overrides": load_overrides(profile),
                "effective": effective_tiers(profile),
                "knownRoles": list(KNOWN_ROLES),
                "knownModels": list(KNOWN_MODELS),
            }) + "\n")
            return 0
        updates = {}
        warnings = []
        for item in args.set:
            if "=" not in item:
                warnings.append(f"malformed set item: {item} (expected role=model)")
                continue
            role, model = item.split("=", 1)
            updates[role.strip()] = model.strip()
        result = update_overrides(profile, updates, [r.strip() for r in args.clear])
        result["warnings"] = warnings + result["warnings"]
        sys.stdout.write(json.dumps(result) + "\n")
        return 0

    ap = argparse.ArgumentParser(description="review-crew model-tier override loader")
    ap.add_argument("--profile", default=None)
    args = ap.parse_args(raw)
    try:
        # An explicit --profile always wins; otherwise self-resolve the session's
        # review-crew profile (so the override feature actually LOADS in production
        # without the startup site having to add a second exec to find the path).
        profile = args.profile if args.profile is not None else _resolve_profile_path()
        ov = load_overrides(profile)
    except Exception:
        ov = {}  # belt-and-suspenders fail-open
    sys.stdout.write(json.dumps(ov) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
