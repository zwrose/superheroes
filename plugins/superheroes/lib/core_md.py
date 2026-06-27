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


_VERIFY_CMD_RE = re.compile(r"^command:\s*(.+?)\s*$", re.MULTILINE)


def _split_sections(text):
    """Split a profile into (preamble, [(heading_lower, raw_block), ...]) where each raw_block
    is the heading line + its body verbatim, up to the next `## ` heading."""
    lines = text.splitlines(keepends=True)
    preamble, sections, cur_head, cur = [], [], None, []
    for line in lines:
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if cur_head is not None:
                sections.append((cur_head, "".join(cur)))
            elif cur:
                preamble.extend(cur)
            cur_head, cur = m.group(1).strip().lower(), [line]
        else:
            cur.append(line)
    if cur_head is not None:
        sections.append((cur_head, "".join(cur)))
    else:
        preamble.extend(cur)
    return "".join(preamble), sections


def split_profile(profile_text, hero):
    """Content-preserving split → (core_facts, layer_text). Shared facts (verify/threat/
    patterns/stack) go to core_facts; recognized hero sections + any hero machine block go to
    the layer verbatim; any unrecognized section is carried into the layer verbatim (FR-8)."""
    shared = _SHARED_HEADINGS.get(hero, set())
    _preamble, sections = _split_sections(profile_text)
    core_facts = {"verifyCommand": None, "stackTags": [], "threatModel": "", "patterns": ""}
    layer_blocks = []
    for head, block in sections:
        if head in shared:
            body = block.split("\n", 1)[1] if "\n" in block else ""
            body = body.strip()
            if head == "verify":
                m = _VERIFY_CMD_RE.search(block)
                core_facts["verifyCommand"] = m.group(1).strip() if m else None
            elif head == "threat model":
                core_facts["threatModel"] = body
            elif head == "canonical patterns":
                core_facts["patterns"] = body
            # "project" prose informs stackTags loosely; left empty here (detection fills it)
            continue
        layer_blocks.append(block.rstrip("\n"))
    # carry any hero machine block (already inside its `## Machine-readable config` section, so
    # it rides along verbatim in layer_blocks above).
    layer_text = "\n\n".join(b for b in layer_blocks if b.strip()) + "\n"
    return core_facts, layer_text


def _legacy_path(cwd, hero):
    """The hero's pre-existing single-file profile path, MODE-AWARE. A global-mode legacy
    profile lives under the hero's own global store, not in the repo, so resolve it through
    each hero's own resolver first (the hero owns where its profile lives); fall back to the
    in-repo `_HERO_INREPO` subpath (anchored at the repo root) when no global profile exists.
    Returns None for an unknown hero."""
    sub = mode_registry._HERO_INREPO.get(hero)
    if sub is None:
        return None
    try:
        if hero == "review-crew":
            import review_store
            res = review_store.resolve(cwd, "profile", review_store.store_root())
            if res.get("exists") and res.get("path"):
                return res["path"]
        elif hero == "test-pilot":
            import store as test_pilot_store
            res = test_pilot_store.resolve(cwd, test_pilot_store.store_root())
            if res.get("exists") and res.get("profile"):
                return res["profile"]
    except Exception:
        pass  # fail-open: fall back to the in-repo anchored path
    return os.path.join(_repo_root(cwd), sub)


def _layer_path(cwd, hero, root=None):
    """The hero layer path, co-located with core.md (same mode-aware dir)."""
    return os.path.join(os.path.dirname(core_path(cwd, root)), hero + ".md")


def _render_layer(layer_text, hero, status, stamp):
    """Wrap the split hero sections in the §2.2 provenance line for a layer file."""
    return ("<!-- %s: schemaVersion=%d status=%s created=%s updated=%s nudge-ack={} -->\n\n%s"
            % (hero, SCHEMA_VERSION, status, stamp, stamp, layer_text))


def _in_repo_mode(cwd, root):
    """True when this migration must commit (in-repo): the resolved mode is in-repo AND the
    project is a git repo. A nongit/global project never commits."""
    if mode_registry.resolve(cwd, root)["mode"] != mode_registry.IN_REPO:
        return False
    return store_core.run_git(cwd, "rev-parse", "--show-toplevel") is not None


def migrate_on_read(cwd, hero, *, root=None, now=None):
    """Convert a hero's legacy profile to core.md + a layer, all-or-nothing, under the lock.
    Only acts when a legacy profile exists and no usable core.md exists. Ordered for
    crash-safety: (1) write core.md, (2) write layer, (3) remove legacy, (4) in-repo commit.
    The legacy file is removed only after both new files exist (UFR-5). In-repo mode records
    the two adds + the deletion in ONE `git commit --only` (no sweep)."""
    stamp = now or _today()
    legacy = _legacy_path(cwd, hero)
    if not legacy or not os.path.isfile(legacy):
        return {"action": "noop"}
    if read(cwd, root) is not None:
        return {"action": "noop"}  # usable core.md already present (resume handled in Task 9)
    if mode_registry.ensure_project_store(cwd, root) is None:
        mark_pending(cwd, root, detail={"hero": hero, "reason": "store-unwritable"})
        return {"action": "deferred"}
    core_p = core_path(cwd, root)
    layer_p = _layer_path(cwd, hero, root)
    with mode_registry.config_lock(cwd, root) as got:
        if not got:
            mark_pending(cwd, root, detail={"hero": hero, "reason": "lock-contended"})
            return {"action": "deferred"}
        # re-check under the lock (Task 9 adds the full resume rule)
        if read(cwd, root) is not None:
            return {"action": "noop"}
        try:
            with open(legacy, encoding="utf-8") as fh:
                legacy_text = fh.read()
        except OSError:
            mark_pending(cwd, root, detail={"hero": hero, "reason": "legacy-unreadable"})
            return {"action": "deferred"}
        if classify(legacy_text, hero) != "standard":
            return {"action": "ambiguous"}
        core_facts, layer_text = split_profile(legacy_text, hero)
        try:
            # (1) core.md
            store_core.atomic_write(core_p, render_core(core_facts, "provisional", stamp, stamp))
            # (2) hero layer
            store_core.atomic_write(layer_p, _render_layer(layer_text, hero, "provisional", stamp))
            # (3) remove the legacy file (only now that both new files exist)
            os.unlink(legacy)
        except OSError:
            mark_pending(cwd, root, detail={"hero": hero, "reason": "write-failed"})
            return {"action": "deferred"}
        # (4) in-repo commit — record the two adds + the deletion in ONE commit, no sweep.
        if _in_repo_mode(cwd, root):
            repo = _repo_root(cwd)
            msg = "chore(superheroes): migrate %s profile to core.md + layer" % hero
            # `git commit --only -- <pathspec>` only commits the working-tree state of paths
            # already KNOWN to git; the two brand-new files are untracked, so stage them first
            # (just those two paths — never the legacy, whose DELETION --only records). This keeps
            # the commit to exactly the three calibration paths and sweeps in nothing else.
            store_core.run_git(repo, "add", "--", core_p, layer_p)
            out = store_core.run_git(repo, "commit", "--only", "-m", msg, "--",
                                     core_p, layer_p, legacy)
            if out is None:
                # the files are in place; report deferred so a stray-legacy diagnosis fires
                mark_pending(cwd, root, detail={"hero": hero, "reason": "migrate-commit-failed"})
                return {"action": "deferred"}
        clear_pending(cwd, root)
        return {"action": "migrated"}
