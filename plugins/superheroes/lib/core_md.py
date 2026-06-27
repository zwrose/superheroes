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
