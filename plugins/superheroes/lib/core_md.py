#!/usr/bin/env python3
# plugins/superheroes/lib/core_md.py
"""Shared core.md calibration brain (CONVENTIONS §2.1/§2.2/§4.2/§4.4) + the legacy-profile
migrator. Stdlib-only, mirrors architect_config.py. The format (parse/render) and pure read
are side-effect-free; write/migrate_on_read are lock-guarded (mode_registry.config_lock) and
fail-open (return a `deferred` action, never raise, never block)."""
import datetime
import json
import os
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import mode_registry  # noqa: E402  (sibling)
import store_core      # noqa: E402  (sibling)

SCHEMA_VERSION = 1

_PROV = re.compile(
    r"<!--\s*superheroes-core:\s*schemaVersion=(\d+)\s+status=(\w+)\s+"
    r"created=(\S+)\s+updated=(\S+)\s*-->")
_JSON_BLOCK = re.compile(r"```json superheroes-core\s*\n(.*?)\n```", re.DOTALL)


def render_core(facts, status, created, updated):
    """Render the §2.2 core.md: provenance comment + prose sections + the json block."""
    block = {
        "schemaVersion": SCHEMA_VERSION,
        "verifyCommand": facts.get("verifyCommand"),
        "stackTags": list(facts.get("stackTags") or []),
    }
    return (
        "<!-- superheroes-core: schemaVersion=%d status=%s created=%s updated=%s -->\n\n"
        "## Threat model\n\n%s\n\n"
        "## Canonical patterns\n\n%s\n\n"
        "```json superheroes-core\n%s\n```\n"
        % (SCHEMA_VERSION, status, created, updated,
           (facts.get("threatModel") or "").strip(),
           (facts.get("patterns") or "").strip(),
           json.dumps(block, indent=2))
    )


def _section(text, heading):
    """Prose under `## <heading>` up to the next `## ` or the json fence — stripped."""
    lines = text.splitlines()
    out, capturing = [], False
    for line in lines:
        s = line.strip()
        if s.startswith("## "):
            capturing = (s[3:].strip().lower() == heading.lower())
            continue
        if s.startswith("```json superheroes-core"):
            capturing = False
            continue
        if capturing:
            out.append(line)
    return "\n".join(out).strip()


def parse_core(text):
    """Parse a core.md document → the fact dict, or None when the json block is
    missing/corrupt (UFR-1 — never a half-read value). verifyCommand+stackTags are
    authoritative from the json block; threatModel+patterns come from prose."""
    mb = _JSON_BLOCK.search(text or "")
    if not mb:
        return None
    try:
        block = json.loads(mb.group(1))
    except ValueError:
        return None
    if not isinstance(block, dict):
        return None
    # UFR-2 fixture safety: schemaVersion MUST be an int. Any integer (including 0) is an
    # older-or-current schema → upgrade-in-memory in read(); ONLY a missing/non-int schemaVersion
    # makes the block corrupt → None. This keeps the schemaVersion=0 older-schema fixture distinct
    # from the corrupt-block fixture (they can never collapse into one another).
    if not isinstance(block.get("schemaVersion"), int):
        return None
    prov = _PROV.search(text)
    if prov:
        status = prov.group(2)
        created, updated = prov.group(3), prov.group(4)
    else:
        status, created, updated = "provisional", "", ""
    tags = block.get("stackTags")
    return {
        "schemaVersion": int(block["schemaVersion"]),
        "status": status,
        "verifyCommand": block.get("verifyCommand"),
        "stackTags": list(tags) if isinstance(tags, list) else [],
        "threatModel": _section(text, "Threat model"),
        "patterns": _section(text, "Canonical patterns"),
        "created": created,
        "updated": updated,
    }


def _repo_root(cwd):
    out = store_core.run_git(cwd, "rev-parse", "--show-toplevel")
    return os.path.realpath(out) if out else os.path.realpath(cwd)


def core_path(cwd, root=None):
    """Mode-aware path to core.md (FR-1): in-repo .claude/superheroes/core.md, else the
    project store's config/core.md. An EXISTING file resolves to where it physically lives;
    a new one resolves by the recorded mode (mode_registry.resolve_artifact)."""
    in_repo = os.path.join(_repo_root(cwd), ".claude", "superheroes", "core.md")
    global_path = os.path.join(mode_registry.project_store_dir(cwd, root), "config", "core.md")
    return mode_registry.resolve_artifact(cwd, in_repo, global_path, root)


def read(cwd, root=None):
    """Pure read of core.md → the fact dict + `behind`, or None (absent/corrupt — UFR-1).
    Older schemaVersion is upgraded IN MEMORY only (no write-back; at v1 there are no
    migration steps, so the record is stamped current) — UFR-2. A NEWER schemaVersion
    returns the understood fields with behind=True and never rewrites — UFR-3. parse_core
    already guarantees schemaVersion is a real int (else corrupt → None), so any integer
    < SCHEMA_VERSION here is unambiguously an older schema, never a corrupt one."""
    try:
        with open(core_path(cwd, root), encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    facts = parse_core(text)
    if facts is None:
        return None
    ver = facts["schemaVersion"]
    behind = ver > SCHEMA_VERSION
    effective = ver if behind else SCHEMA_VERSION  # UFR-2: older stamped current in memory
    return {
        "schemaVersion": effective,
        "status": facts["status"],
        "verifyCommand": facts["verifyCommand"],
        "stackTags": facts["stackTags"],
        "threatModel": facts["threatModel"],
        "patterns": facts["patterns"],
        "behind": behind,
        "created": facts["created"],
        "updated": facts["updated"],
    }


def _today():
    return datetime.date.today().strftime("%Y-%m-%d")


def _pending_path(cwd, root=None):
    """The UFR-4 PENDING MARKER path in the machine-local project store. This store stays
    writable even when the in-repo calibration dir or the config lock is unavailable, so it
    can record that a calibration write/migration was DEFERRED (the calibration-not-saved
    signal in mode_reconcile reads it back)."""
    return os.path.join(mode_registry.project_store_dir(cwd, root), "calibration-pending.json")


def mark_pending(cwd, root=None, detail=None):
    """Best-effort write of the pending marker — swallows OSError (never the reason a deferred
    path raises). Records {"pending": true, "detail": detail}."""
    try:
        store_core.atomic_write(_pending_path(cwd, root),
                                json.dumps({"pending": True, "detail": detail}, indent=2) + "\n")
    except OSError:
        pass


def clear_pending(cwd, root=None):
    """Best-effort removal of the pending marker on a successful write/migration — swallows
    OSError (including FileNotFoundError when no marker exists)."""
    try:
        os.remove(_pending_path(cwd, root))
    except OSError:
        pass


def _diff_proposals(detected, recorded):
    """Per-field proposals where the detected value DIFFERS from the recorded one.
    A detected value equal to or absent (None / empty) is a reuse, not a proposal (FR-6)."""
    proposals = []
    for field in ("verifyCommand", "stackTags", "threatModel", "patterns"):
        det = detected.get(field)
        if det is None or det == "" or det == []:
            continue  # detection yielded nothing → reuse, propose nothing
        if det != recorded.get(field):
            proposals.append({"field": field, "detected": det, "recorded": recorded.get(field)})
    return proposals


def write(cwd, facts, status, *, root=None, now=None):
    """Lock-guarded atomic write of core.md. Returns a structured result (never a bare None):
      - new core.md            → {action: "written"}
      - existing, all detected facts equal/absent → {action: "reused"}
      - existing, a detected fact DIFFERS         → {action: "proposed"} (NOT applied;
                                                     the differing fields are in `proposals`)
      - lock contended / store unwritable         → {action: "deferred"} (UFR-4)
    Reuse-not-clobber (FR-6) is enforced HERE under the same lock that serializes a concurrent
    second-hero setup (FR-7). A `deferred` return drops a best-effort pending marker; a
    `written` clears it (the UFR-4 calibration-not-saved signal)."""
    stamp = now or _today()
    if mode_registry.ensure_project_store(cwd, root) is None:
        mark_pending(cwd, root, detail={"reason": "store-unwritable"})
        return {"action": "deferred", "record": None, "proposals": []}
    with mode_registry.config_lock(cwd, root) as got:
        if not got:
            mark_pending(cwd, root, detail={"reason": "lock-contended"})
            return {"action": "deferred", "record": None, "proposals": []}
        existing = read(cwd, root)
        if existing is not None:
            proposals = _diff_proposals(facts, existing)
            if proposals:
                return {"action": "proposed", "record": existing, "proposals": proposals}
            return {"action": "reused", "record": existing, "proposals": []}
        created = facts.get("created") or stamp
        text = render_core(facts, status, created, stamp)
        store_core.atomic_write(core_path(cwd, root), text)
        record = read(cwd, root)
        clear_pending(cwd, root)
        return {"action": "written", "record": record, "proposals": []}


# Recognized headings per hero. Shared-fact headings live in core.md; hero headings → the
# layer. Anything not listed (and not a recognized shared/hero heading) is an "extra" section
# carried verbatim into the layer — it does not by itself make a profile ambiguous.
_SHARED_HEADINGS = {
    "review-crew": {"project", "threat model", "verify", "canonical patterns"},
    "test-pilot": set(),  # test-pilot's profile carries no shared prose; its facts live in its json block
}
# The shared facts that MUST be locatable for a `standard` classification.
_REQUIRED_SHARED = {
    "review-crew": {"threat model", "verify"},
    "test-pilot": set(),  # verify/stack come from the test-pilot-config json block when present
}
_HERO_HEADINGS = {
    "review-crew": {"scope exclusions", "focus hints", "conventions"},
    "test-pilot": {"app launch", "auth strategy", "seed surfaces", "browser tool order",
                   "machine-readable config"},
}

_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _headings(text):
    return [m.group(1).strip().lower() for m in _HEADING_RE.finditer(text or "")]


def classify(profile_text, hero):
    """`standard` (all required shared facts locatable under recognized headings, and every
    other section is a recognized hero section or an extra section bearing on no shared fact)
    or `ambiguous` (a shared fact unlocatable, or a section genuinely ambiguous). Conservative:
    anything that is not clearly placeable is `ambiguous` so content never lands in the wrong
    layer (FR-8/FR-9 boundary)."""
    heads = set(_headings(profile_text))
    required = _REQUIRED_SHARED.get(hero, set())
    if not required.issubset(heads):
        return "ambiguous"  # a required shared fact has no recognized heading
    return "standard"
