#!/usr/bin/env python3
# plugins/superheroes/lib/core_md.py
"""Shared core.md calibration brain (CONVENTIONS §2.1/§2.2/§4.2/§4.4). Stdlib-only, mirrors
architect_config.py. The format (parse/render) and pure read are side-effect-free;
write/write_layer/confirm*/write_show_it_surface are the lock-guarded fail-open writers
(mode_registry.config_lock; return a `deferred` action, never raise, never block). The
legacy-profile migration path was removed in favour of a named refusal (issue #724)."""
import collections
import datetime
import json
import os
import re
import stat
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import mode_registry  # noqa: E402  (sibling)
import store_core      # noqa: E402  (sibling)

SCHEMA_VERSION = 2

CONFIG_ABSENT = "absent"
CONFIG_OK = "ok"
CONFIG_UNREADABLE = "unreadable"
CONFIG_ROOT_UNAVAILABLE = "root-unavailable"
GATE_REASON_UNREADABLE = "core-md-unreadable"
GATE_REASON_ROOT_UNAVAILABLE = "repo-root-unavailable"


# Lives in store_core (lowest layer); alias kept so existing ``except RepoRootUnavailable``
# catch sites in this module and siblings keep working without import churn.
RepoRootUnavailable = store_core.RepoRootUnavailable


_GATE_USABLE_STATUSES = frozenset({CONFIG_OK, CONFIG_ABSENT})
_GATE_REFUSAL_REASONS = {
    CONFIG_UNREADABLE: GATE_REASON_UNREADABLE,
    CONFIG_ROOT_UNAVAILABLE: GATE_REASON_ROOT_UNAVAILABLE,
}

GATE_REASON_EVALUATION_FAILED = "dispatch-gate-evaluation-failed"
LEGACY_PROFILE_REASON = "legacy-profile-unsupported"
LEGACY_PROFILE_REMEDY = (
    "run superheroes:configure to re-calibrate this project; "
    "the pre-core.md single-file profile is no longer read"
)
SHOW_IT_REASON_ABSENT = "core-md-absent"
SHOW_IT_REASON_UNPARSEABLE = "core-md-unparseable"
SHOW_IT_REASON_PROSE_FORBIDDEN = "show-it-prose-forbidden"
SHOW_IT_REASON_ROUND_TRIP = "show-it-round-trip-refused"
BUILDER_DISPATCH_REASON_ABSENT = "core-md-absent"
BUILDER_DISPATCH_REASON_UNPARSEABLE = "core-md-unparseable"
BUILDER_DISPATCH_REASON_ROUND_TRIP = "builder-dispatch-round-trip-refused"
BUILDER_DISPATCH_DEFER_STORE_UNWRITABLE = "store-unwritable"
BUILDER_DISPATCH_DEFER_LOCK_CONTENDED = "lock-contended"
BUILDER_DISPATCH_DEFER_SCHEMA_BEHIND = "core-schema-behind"
BUILDER_DISPATCH_DEFER_WRITE_FAILED = "builder-tier-write-failed"
BUILDER_DISPATCH_DEFER_CLI_FAILED = "builder-tier-cli-failed"

CoreGateConfig = collections.namedtuple("CoreGateConfig", "prefs status detail")

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
        "enginePreferences": dict(facts.get("enginePreferences") or {}),
    }
    show_it = (facts.get("showItSurface") or "").strip()
    show_it_block = ""
    if show_it:
        show_it_block = "## Show-it surface\n\n%s\n\n" % show_it
    return (
        "<!-- superheroes-core: schemaVersion=%d status=%s created=%s updated=%s -->\n\n"
        "## Threat model\n\n%s\n\n"
        "## Canonical patterns\n\n%s\n\n"
        "%s"
        "```json superheroes-core\n%s\n```\n"
        % (SCHEMA_VERSION, status, created, updated,
           (facts.get("threatModel") or "").strip(),
           (facts.get("patterns") or "").strip(),
           show_it_block,
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
    prefs = block.get("enginePreferences")
    return {
        "schemaVersion": int(block["schemaVersion"]),
        "status": status,
        "verifyCommand": block.get("verifyCommand"),
        "stackTags": list(tags) if isinstance(tags, list) else [],
        "enginePreferences": dict(prefs) if isinstance(prefs, dict) else {},
        "threatModel": _section(text, "Threat model"),
        "patterns": _section(text, "Canonical patterns"),
        "showItSurface": _section(text, "Show-it surface"),
        "created": created,
        "updated": updated,
    }


def _repo_root(cwd):
    return store_core.repo_root(cwd)


def relocate_file(src, dst):
    """The single relocate primitive (copy-then-unlink, atomic on the destination) that
    mode_migrate reuses for the cross-mode move (the plan's "one mover, no second engine").
    Mirrors the atomic-write discipline the rest of this module uses."""
    with open(src, encoding="utf-8") as fh:
        store_core.atomic_write(dst, fh.read())
    os.remove(src)


def _core_candidates(cwd, root=None):
    in_repo = os.path.join(_repo_root(cwd), ".claude", "superheroes", "core.md")
    global_path = os.path.join(mode_registry.project_store_dir(cwd, root), "config", "core.md")
    return in_repo, global_path


def core_path(cwd, root=None):
    """Mode-aware path to core.md (FR-1): in-repo .claude/superheroes/core.md, else the
    project store's config/core.md. An EXISTING file resolves to where it physically lives;
    a new one resolves by the recorded mode (mode_registry.resolve_artifact)."""
    in_repo, global_path = _core_candidates(cwd, root)
    return mode_registry.resolve_artifact(cwd, in_repo, global_path, root)


def _classify_core_md_at_path(path):
    """Classify a single core.md path for gate purposes. Never raises."""
    try:
        st = os.stat(path)
    except FileNotFoundError:
        try:
            os.lstat(path)
        except FileNotFoundError:
            return CoreGateConfig({}, CONFIG_ABSENT, None)
        except OSError as exc:
            return CoreGateConfig(
                {},
                CONFIG_UNREADABLE,
                "lstat failed at %s: %s" % (path, exc),
            )
        return CoreGateConfig(
            {},
            CONFIG_UNREADABLE,
            "dangling symlink at %s" % path,
        )
    except OSError as exc:
        return CoreGateConfig(
            {},
            CONFIG_UNREADABLE,
            gate_refusal_detail(exc, at=path),
        )

    if not stat.S_ISREG(st.st_mode):
        return CoreGateConfig(
            {},
            CONFIG_UNREADABLE,
            "not a regular file at %s" % path,
        )

    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except FileNotFoundError:
        return CoreGateConfig(
            {},
            CONFIG_UNREADABLE,
            "core.md existed at stat but was missing at open (read race) at %s" % path,
        )
    except OSError as exc:
        return CoreGateConfig(
            {},
            CONFIG_UNREADABLE,
            gate_refusal_detail(exc, at=path, verb="opening"),
        )
    except UnicodeDecodeError as exc:
        return CoreGateConfig(
            {},
            CONFIG_UNREADABLE,
            "UTF-8 decode failed at %s: %s" % (path, exc),
        )

    facts = parse_core(text)
    if facts is None:
        return CoreGateConfig(
            {},
            CONFIG_UNREADABLE,
            "corrupt or unreadable core.md at %s" % path,
        )
    prefs = facts.get("enginePreferences")
    if not isinstance(prefs, dict):
        prefs = {}
    else:
        prefs = dict(prefs)
    return CoreGateConfig(prefs, CONFIG_OK, None)


def _merge_candidate_gate_configs(in_cls, gl_cls, cwd, root):
    in_absent = in_cls.status == CONFIG_ABSENT
    gl_absent = gl_cls.status == CONFIG_ABSENT
    if in_absent and gl_absent:
        return CoreGateConfig({}, CONFIG_ABSENT, None)
    if in_absent:
        return gl_cls
    if gl_absent:
        return in_cls
    if mode_registry.resolve(cwd, root)["mode"] == mode_registry.IN_REPO:
        return in_cls
    return gl_cls


def engine_preferences_for_gate(*, cwd=None, root=None, profile_path=None):
    """Readable core.md gate accessor — single owner of the existence/readability decision.

    When ``profile_path`` is given (wins over ``cwd``/``root``), the target is ``core.md`` in
    the directory of ``os.path.realpath(profile_path)``. Otherwise both in-repo and global
    candidate paths are classified and merged so a present-but-unreadable candidate is never
    skipped as absent. Never raises."""
    try:
        if profile_path:
            layer = os.path.realpath(profile_path)
            core_beside = os.path.join(os.path.dirname(layer), "core.md")
            return _classify_core_md_at_path(core_beside)

        cwd = cwd or os.getcwd()
        in_repo, global_path = _core_candidates(cwd, root)
        in_cls = _classify_core_md_at_path(in_repo)
        gl_cls = _classify_core_md_at_path(global_path)
        return _merge_candidate_gate_configs(in_cls, gl_cls, cwd, root)
    except RepoRootUnavailable as exc:
        return CoreGateConfig({}, CONFIG_ROOT_UNAVAILABLE, gate_refusal_detail(exc))
    except Exception as exc:
        return CoreGateConfig(
            {},
            CONFIG_UNREADABLE,
            "gate evaluation failed before core.md could be classified: "
            + gate_refusal_detail(exc),
        )


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
    except RepoRootUnavailable:
        # UFR-1: read() still returns None for absent/corrupt — but repo-root-unknown is NOT
        # "absent"; authoritative status lives on engine_preferences_for_gate (C2).
        return None
    except (OSError, UnicodeDecodeError):
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
        "enginePreferences": facts["enginePreferences"],
        "threatModel": facts["threatModel"],
        "patterns": facts["patterns"],
        "showItSurface": facts["showItSurface"],
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
    # Show-it surface is owner-declared prose only — never auto-detected from a repo.
    for field in ("verifyCommand", "stackTags", "threatModel", "patterns", "enginePreferences"):
        det = detected.get(field)
        if det is None or det == "" or det == []:
            continue  # detection yielded nothing → reuse, propose nothing
        if det != recorded.get(field):
            proposals.append({"field": field, "detected": det, "recorded": recorded.get(field)})
    return proposals


def _facts_include_engine_preferences(facts):
    det = facts.get("enginePreferences") if isinstance(facts, dict) else None
    return isinstance(det, dict) and det != {}


def _candidate_engine_preferences(facts, existing):
    """Incoming enginePreferences merged over the recorded block (incoming wins on keys)."""
    recorded = {}
    if isinstance(existing, dict):
        rec_prefs = existing.get("enginePreferences")
        if isinstance(rec_prefs, dict):
            recorded = dict(rec_prefs)
    incoming = facts.get("enginePreferences") if isinstance(facts, dict) else None
    if not isinstance(incoming, dict):
        return recorded
    merged = dict(recorded)
    merged.update(incoming)
    return merged


def gate_config_is_refusal(cfg):
    """True when ``engine_preferences_for_gate`` status refuses usable configuration.

    ``CONFIG_OK`` and ``CONFIG_ABSENT`` are not refusals; every other registered status is."""
    return cfg.status not in _GATE_USABLE_STATUSES


def gate_config_is_absent(cfg):
    """True when no core.md is present at the resolved gate path."""
    return cfg.status == CONFIG_ABSENT


def gate_config_usable_prefs(cfg):
    """Return ``enginePreferences`` when status is ``CONFIG_OK``; ``{}`` otherwise (incl. absent)."""
    if cfg.status == CONFIG_OK:
        return cfg.prefs if isinstance(cfg.prefs, dict) else {}
    return {}


def gate_config_refusal(cfg):
    """Return the ``gate_refusal`` payload for a refusal status, or ``None`` when usable/absent.

    An unregistered status raises ``KeyError`` — fail-closed, never silently treated as usable."""
    if not gate_config_is_refusal(cfg):
        return None
    return gate_refusal(_GATE_REFUSAL_REASONS[cfg.status], cfg.detail)


def gate_refusal(reason, detail):
    """The ONE dict shape for a named configuration-gate refusal: {"reason", "detail"}.
    Every producer of that payload goes through here so the shape cannot drift (rider 9 of #699)."""
    return {"reason": reason, "detail": detail}


def profile_structural_refusal(cwd=None, root=None):
    """Structural soundness of the project's core.md candidates — the fail-closed guard for a
    configuration value whose WRONG value is costly rather than merely inconvenient (#755).

    Returns None when every EXISTING candidate is structurally unambiguous, else a reason string
    naming the first problem found. Never raises.

    `parse_core` takes the FIRST `superheroes-core` block and uses a plain `json.loads` (last
    duplicate key wins). That is fine for a knob whose fallback is free; it is not fine for a
    launch tier, where an ambiguous profile must fail closed rather than pick a value out of a
    file we cannot fully trust."""
    try:
        cwd = cwd or os.getcwd()
        in_repo, global_path = _core_candidates(cwd, root)
        for path in (in_repo, global_path):
            if not os.path.exists(path):
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except (OSError, UnicodeDecodeError):
                return "core-md-unreadable:%s" % path
            blocks = _JSON_BLOCK.findall(text)
            if len(blocks) > 1:
                return "multiple-core-blocks:%s" % path
            if not blocks:
                continue
            dup_key = [None]

            def _reject_dupes(pairs):
                seen = {}
                for key, value in pairs:
                    if key in seen:
                        dup_key[0] = key
                        raise ValueError("duplicate-core-key")
                    seen[key] = value
                return seen

            try:
                json.loads(blocks[0], object_pairs_hook=_reject_dupes)
            except ValueError as exc:
                if dup_key[0] is not None:
                    return "duplicate-core-key:%s" % dup_key[0]
                # corrupt block — upstream's job, not this guard's
            except TypeError:
                pass
        return None
    except Exception as exc:
        return "core-md-structural-check-failed: %s" % gate_refusal_detail(exc)


def gate_refusal_detail(exc, *, at=None, verb="at"):
    """The type-name-carrying detail string for an exception-caused gate refusal.

    Formats the exception's class name into the detail. Operation-specific strings that omit the
    exception type (e.g. ``"lstat failed at %s: %s"`` and ``"UTF-8 decode failed at %s: %s"``
    in ``_classify_core_md_at_path``) are deliberately outside this helper.

    ``gate_refusal_detail(exc)``                        -> "ExcName: message"
    ``gate_refusal_detail(exc, at=path)``               -> "ExcName at path: message"
    ``gate_refusal_detail(exc, at=path, verb="opening")`` -> "ExcName opening path: message"
    """
    exc_name = type(exc).__name__
    if at is None:
        return "%s: %s" % (exc_name, exc)
    return "%s %s %s: %s" % (exc_name, verb, at, exc)


def gate_refusal_line(payload):
    """The ONE flattened "reason: detail" form, DERIVED FROM the payload rather than rebuilt, so the
    dict form and the flattened form can never disagree."""
    return "%s: %s" % (payload["reason"], payload["detail"])


def _evaluate_configured_dispatch_gate(cwd, root, facts, existing):
    """Evaluate fable×external gate. Returns (violations, evaluation_error).

    ``violations`` is a list when evaluation succeeded (possibly empty). ``evaluation_error`` is a
    ``{"reason", "detail"}`` dict when the gate itself failed (distinct from a clean pass)."""
    try:
        import engine_pref
        import model_tier_overrides

        gate_cfg = engine_preferences_for_gate(cwd=cwd, root=root)
        # Deliberately a second gate read: closes the gate→read TOCTOU window so a core.md that
        # was valid at write()'s first gate but unreadable by the time read() runs fails closed
        # instead of falling through to create/clobber.
        if gate_cfg.status == CONFIG_ROOT_UNAVAILABLE:
            return None, gate_refusal(GATE_REASON_ROOT_UNAVAILABLE, gate_cfg.detail)
        if gate_cfg.status == CONFIG_UNREADABLE:
            return None, gate_refusal(GATE_REASON_UNREADABLE, gate_cfg.detail)

        if existing is not None and not _facts_include_engine_preferences(facts):
            return [], None
        prefs = _candidate_engine_preferences(facts, existing)
        tiers = model_tier_overrides.effective_tiers(
            model_tier_overrides.resolve_profile_path(cwd, root))
        return engine_pref.configured_dispatch_violations(prefs, tiers), None
    except Exception as exc:
        return None, gate_refusal(GATE_REASON_EVALUATION_FAILED, gate_refusal_detail(exc))


def _refused_dispatch_gate(violations=None, *, evaluation_error=None, record=None):
    if evaluation_error:
        reason = evaluation_error.get("reason", GATE_REASON_EVALUATION_FAILED)
        detail = evaluation_error.get("detail", "")
        violations = [gate_refusal(reason, detail)]
    return {
        "action": "refused",
        "record": record,
        "proposals": [],
        "violations": violations,
    }


def write(cwd, facts, status, *, root=None, now=None):
    """Lock-guarded atomic write of core.md. Returns a structured result (never a bare None):
      - new core.md            → {action: "written"}
      - existing, all detected facts equal/absent → {action: "reused"}
      - existing, a detected fact DIFFERS         → {action: "proposed"} (NOT applied;
                                                     the differing fields are in `proposals`)
      - fable tier on external engine with current tiers → {action: "refused"} (NOT applied)
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
        gate_cfg = engine_preferences_for_gate(cwd=cwd, root=root)
        if gate_cfg.status == CONFIG_ROOT_UNAVAILABLE:
            return _refused_dispatch_gate(
                evaluation_error=gate_refusal(GATE_REASON_ROOT_UNAVAILABLE, gate_cfg.detail),
                record=None,
            )
        if gate_cfg.status == CONFIG_UNREADABLE:
            return _refused_dispatch_gate(
                evaluation_error=gate_refusal(GATE_REASON_UNREADABLE, gate_cfg.detail),
                record=None,
            )
        existing = read(cwd, root)
        violations, gate_err = _evaluate_configured_dispatch_gate(cwd, root, facts, existing)
        if gate_err is not None:
            return _refused_dispatch_gate(evaluation_error=gate_err, record=existing)
        if violations:
            if existing is None or _facts_include_engine_preferences(facts):
                return _refused_dispatch_gate(violations=violations, record=existing)
        if existing is not None:
            proposals = _diff_proposals(facts, existing)
            if proposals:
                return {"action": "proposed", "record": existing, "proposals": proposals}
            return {"action": "reused", "record": existing, "proposals": []}
        created = facts.get("created") or stamp
        text = render_core(facts, status, created, stamp)
        try:
            store_core.atomic_write(core_path(cwd, root), text)
        except RepoRootUnavailable as exc:
            return {"action": "deferred", "record": None, "proposals": [],
                    "reason": GATE_REASON_ROOT_UNAVAILABLE,
                    "detail": gate_refusal_detail(exc)}
        except OSError:
            # Fail-open (UFR-4): honor this function's "never raise, never block" contract —
            # an unwritable store defers (best-effort marker) rather than propagating, exactly
            # as write_layer() does.
            mark_pending(cwd, root, detail={"reason": "store-unwritable"})
            return {"action": "deferred", "record": None, "proposals": []}
        record = read(cwd, root)
        clear_pending(cwd, root)
        return {"action": "written", "record": record, "proposals": []}


_SHOW_IT_HEADING = re.compile(r"^\s*##\s+Show-it surface\s*$", re.IGNORECASE)
_TOP_LEVEL_SECTION = re.compile(r"^\s*##\s+")
_JSON_FENCE_LINE = re.compile(r"^\s*```json superheroes-core\s*$")


def _render_show_it_surface_block(prose):
    body = (prose or "").strip()
    if not body:
        return ""
    return "## Show-it surface\n\n" + body + "\n\n"


def _show_it_prose_forbidden(prose):
    """Prose must not carry its own top-level section or json fence (parse_core safety)."""
    for line in (prose or "").splitlines():
        if _TOP_LEVEL_SECTION.match(line) or _JSON_FENCE_LINE.match(line):
            return True
    return False


def _json_block_regions(text):
    """Every ```json superheroes-core``` fenced region, including fences (round-trip guard)."""
    return [m.group(0) for m in _JSON_BLOCK.finditer(text or "")]


def _show_it_json_blocks_unchanged(orig_text, new_text):
    """True when the candidate leaves every json block byte-identical (count + content)."""
    return _json_block_regions(orig_text) == _json_block_regions(new_text)


def replace_show_it_surface_section(text, prose):
    """Create, replace, or clear only the `## Show-it surface` section; preserve all else."""
    new_block = _render_show_it_surface_block(prose)
    lines = (text or "").splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if _SHOW_IT_HEADING.match(line):
            start = i
            break
    if start is None:
        if not new_block:
            return text
        insert_at = len(lines)
        for i, line in enumerate(lines):
            if _JSON_FENCE_LINE.match(line):
                insert_at = i
                break
        return "".join(lines[:insert_at]) + new_block + "".join(lines[insert_at:])
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if _TOP_LEVEL_SECTION.match(lines[j]) or _JSON_FENCE_LINE.match(lines[j]):
            end = j
            break
    if not new_block:
        return "".join(lines[:start]) + "".join(lines[end:])
    return "".join(lines[:start]) + new_block + "".join(lines[end:])


def write_show_it_surface(cwd, prose, *, root=None):
    """Lock-guarded surgical write of the Show-it surface prose section only. Fail-closed on
    corrupt core, forbidden prose, or a round-trip that would change any other parsed field."""
    if mode_registry.ensure_project_store(cwd, root) is None:
        mark_pending(cwd, root, detail={"reason": "store-unwritable"})
        return {"action": "deferred"}
    gate_cfg = engine_preferences_for_gate(cwd=cwd, root=root)
    if gate_cfg.status == CONFIG_ROOT_UNAVAILABLE:
        return {"action": "deferred",
                "reason": GATE_REASON_ROOT_UNAVAILABLE, "detail": gate_cfg.detail}
    with mode_registry.config_lock(cwd, root) as got:
        if not got:
            mark_pending(cwd, root, detail={"reason": "lock-contended"})
            return {"action": "deferred"}
        record = read(cwd, root)
        if record is None:
            cls = _classify_core_md_at_path(core_path(cwd, root))
            if cls.status == CONFIG_ABSENT:
                return {"action": "refused", "reason": SHOW_IT_REASON_ABSENT}
            return {"action": "refused", "reason": SHOW_IT_REASON_UNPARSEABLE}
        if record.get("behind"):
            return {"action": "behind", "record": record}
        try:
            path = core_path(cwd, root)
        except RepoRootUnavailable as exc:
            return {"action": "deferred",
                    "reason": GATE_REASON_ROOT_UNAVAILABLE,
                    "detail": gate_refusal_detail(exc)}
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            mark_pending(cwd, root, detail={"reason": "store-unwritable"})
            return {"action": "deferred"}
        orig = parse_core(text)
        if orig is None:
            return {"action": "refused", "reason": SHOW_IT_REASON_UNPARSEABLE}
        body = prose if prose is not None else ""
        if body.strip() and _show_it_prose_forbidden(body):
            return {"action": "refused", "reason": SHOW_IT_REASON_PROSE_FORBIDDEN}
        new_text = replace_show_it_surface_section(text, body)
        if new_text == text:
            return {"action": "noop"}
        new_parsed = parse_core(new_text)
        if new_parsed is None or not _show_it_json_blocks_unchanged(text, new_text):
            return {"action": "refused", "reason": SHOW_IT_REASON_ROUND_TRIP}
        try:
            store_core.atomic_write(path, new_text)
        except OSError:
            mark_pending(cwd, root, detail={"reason": "store-unwritable"})
            return {"action": "deferred"}
        clear_pending(cwd, root)
        return {"action": "written"}


def _builder_dispatch_round_trip_ok(orig, new_parsed):
    """True when the candidate changes only enginePreferences.builderDispatchTier."""
    if new_parsed is None:
        return False
    for key in ("schemaVersion", "status", "verifyCommand", "stackTags", "threatModel",
                "patterns", "showItSurface", "created"):
        if orig.get(key) != new_parsed.get(key):
            return False
    orig_prefs = orig.get("enginePreferences") or {}
    new_prefs = new_parsed.get("enginePreferences") or {}
    for key in set(orig_prefs) | set(new_prefs):
        if key == "builderDispatchTier":
            continue
        if orig_prefs.get(key) != new_prefs.get(key):
            return False
    return True


def _splice_single_json_block(text, new_body):
    """Replace the body of the sole ```json superheroes-core``` block, or None if not exactly one."""
    matches = list(_JSON_BLOCK.finditer(text or ""))
    if len(matches) != 1:
        return None
    m = matches[0]
    return text[:m.start(1)] + new_body + text[m.end(1):]


def write_builder_dispatch_tier(cwd, tier, *, root=None):
    """Lock-guarded surgical write of enginePreferences.builderDispatchTier only — the ONE writer
    of that key. Every other enginePreferences key, every other core fact, and every prose section
    survive byte-identical. Never raises."""
    if mode_registry.ensure_project_store(cwd, root) is None:
        mark_pending(cwd, root, detail={"reason": BUILDER_DISPATCH_DEFER_STORE_UNWRITABLE})
        return {"action": "deferred", "reason": BUILDER_DISPATCH_DEFER_STORE_UNWRITABLE}
    gate_cfg = engine_preferences_for_gate(cwd=cwd, root=root)
    if gate_cfg.status == CONFIG_ROOT_UNAVAILABLE:
        return {"action": "deferred",
                "reason": GATE_REASON_ROOT_UNAVAILABLE, "detail": gate_cfg.detail}
    import engine_pref
    classified = engine_pref.classify_builder_dispatch_tier(tier)
    if classified["state"] == "invalid":
        return {"action": "refused", "reason": classified["reason"]}
    structural = profile_structural_refusal(cwd, root=root)
    if structural is not None:
        return {"action": "refused", "reason": structural}
    with mode_registry.config_lock(cwd, root) as got:
        if not got:
            mark_pending(cwd, root, detail={"reason": BUILDER_DISPATCH_DEFER_LOCK_CONTENDED})
            return {"action": "deferred", "reason": BUILDER_DISPATCH_DEFER_LOCK_CONTENDED}
        record = read(cwd, root)
        if record is None:
            cls = _classify_core_md_at_path(core_path(cwd, root))
            if cls.status == CONFIG_ABSENT:
                return {"action": "refused", "reason": BUILDER_DISPATCH_REASON_ABSENT}
            return {"action": "refused", "reason": BUILDER_DISPATCH_REASON_UNPARSEABLE}
        if record.get("behind"):
            return {
                "action": "behind",
                "reason": BUILDER_DISPATCH_DEFER_SCHEMA_BEHIND,
                "record": record,
            }
        try:
            path = core_path(cwd, root)
        except RepoRootUnavailable as exc:
            return {"action": "deferred",
                    "reason": GATE_REASON_ROOT_UNAVAILABLE,
                    "detail": gate_refusal_detail(exc)}
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            mark_pending(cwd, root, detail={"reason": BUILDER_DISPATCH_DEFER_STORE_UNWRITABLE})
            return {
                "action": "deferred",
                "reason": BUILDER_DISPATCH_DEFER_STORE_UNWRITABLE,
            }
        orig = parse_core(text)
        if orig is None:
            return {"action": "refused", "reason": BUILDER_DISPATCH_REASON_UNPARSEABLE}
        blocks = list(_JSON_BLOCK.finditer(text))
        if len(blocks) != 1:
            return {"action": "refused", "reason": BUILDER_DISPATCH_REASON_UNPARSEABLE}
        try:
            block = json.loads(blocks[0].group(1))
        except ValueError:
            return {"action": "refused", "reason": BUILDER_DISPATCH_REASON_UNPARSEABLE}
        if not isinstance(block, dict):
            return {"action": "refused", "reason": BUILDER_DISPATCH_REASON_UNPARSEABLE}
        prefs = block.get("enginePreferences")
        if not isinstance(prefs, dict):
            prefs = {}
            block["enginePreferences"] = prefs
        if classified["state"] == "unset":
            if "builderDispatchTier" in prefs:
                del prefs["builderDispatchTier"]
        else:
            prefs["builderDispatchTier"] = classified["tier"]
        new_body = json.dumps(block, indent=2)
        new_text = _splice_single_json_block(text, new_body)
        if new_text is None:
            return {"action": "refused", "reason": BUILDER_DISPATCH_REASON_UNPARSEABLE}
        if new_text == text:
            return {"action": "noop"}
        new_parsed = parse_core(new_text)
        if not _builder_dispatch_round_trip_ok(orig, new_parsed):
            return {"action": "refused", "reason": BUILDER_DISPATCH_REASON_ROUND_TRIP}
        try:
            store_core.atomic_write(path, new_text)
        except OSError as exc:
            mark_pending(cwd, root, detail={"reason": BUILDER_DISPATCH_DEFER_STORE_UNWRITABLE})
            return {
                "action": "deferred",
                "reason": BUILDER_DISPATCH_DEFER_WRITE_FAILED,
            }
        clear_pending(cwd, root)
        return {"action": "written"}


def layer_path(cwd, hero, root=None):
    """Mode-aware path to a hero layer file, co-located with core.md."""
    return os.path.join(os.path.dirname(core_path(cwd, root)), hero + ".md")


def _layer_path(cwd, hero, root=None):
    """Back-compat alias used within this module."""
    return layer_path(cwd, hero, root)


def _render_layer(layer_text, hero, status, stamp, rubric_version=None):
    """Wrap the split hero sections in the §2.2 provenance line for a layer file. Always ends in a
    single trailing newline (#121 Part I — never write a "No newline at end of file" layer)."""
    rubric_part = (" rubric-version=%d" % rubric_version) if rubric_version is not None else ""
    rendered = ("<!-- %s: schemaVersion=%d status=%s created=%s updated=%s%s nudge-ack={} -->\n\n%s"
                % (hero, SCHEMA_VERSION, status, stamp, stamp, rubric_part, layer_text))
    return rendered if rendered.endswith("\n") else rendered + "\n"


def _layer_is_empty(layer_p):
    """True when the layer file is absent or carries only its provenance line (no body sections)."""
    try:
        with open(layer_p, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return True
    lines = text.splitlines()
    if lines and lines[0].lstrip().startswith("<!--"):
        lines = lines[1:]  # drop the §2.2 provenance comment line
    return "\n".join(lines).strip() == ""


def _legacy_candidates(cwd, hero, root=None):
    """Both legacy single-file profile paths for a hero — in-repo and global — enumerated
    WITHOUT healing. Detection must never repair a store pointer, so the global leg passes
    heal=False. Mirrors mode_registry.hero_evidence's legacy leg exactly (same tables, same
    heal=False), so there is ONE shape for 'where a legacy profile could be', not a new one.
    Only ever names a LEGACY filename, so it can never return the unified hero layer (#428)."""
    sub = mode_registry._HERO_LEGACY_INREPO.get(hero)
    if sub is None:
        return []
    out = [os.path.join(_repo_root(cwd), sub)]
    g = store_core.resolve_global(
        cwd, mode_registry._hero_global_root(hero), heal=False)
    if g is not None:
        out.append(os.path.join(g["dir"], mode_registry._HERO_GLOBAL_FILENAME[hero]))
    return out


def _legacy_presence(path):
    """(present, error_detail) for one candidate path, via os.lstat.

    lstat does NOT follow symlinks, so a dangling symlink and a directory both read as PRESENT —
    something unexpected sitting at a legacy path must never be concluded 'absent'. Only
    FileNotFoundError means absent; any other OSError is PRESENT-indeterminate with its text
    returned, because a state we could not read is never a clean bill of health."""
    try:
        os.lstat(path)
    except FileNotFoundError:
        return False, None
    except OSError as exc:
        return True, gate_refusal_detail(exc)
    return True, None


def legacy_profile_refusal(cwd, root=None):
    """Named refusal when a hero still carries a pre-core.md single-file legacy profile.

    Returns None when no hero does. Detection only — this never reads, rewrites, unlinks, or
    commits a legacy profile, and never writes anything at all (issue #724: the migration path
    was removed because its only observed behaviour was destructive). Never raises."""
    try:
        heroes_refused = []
        paths = []
        detail = {}
        for hero in mode_registry._HERO_LEGACY_INREPO:
            try:
                refused = False
                hero_path = None
                hero_detail = None
                for candidate in _legacy_candidates(cwd, hero, root):
                    present, err = _legacy_presence(candidate)
                    if present:
                        refused = True
                        hero_path = candidate
                        hero_detail = err if err else candidate
                        break
                if refused:
                    heroes_refused.append(hero)
                    if hero_path is not None:
                        paths.append(hero_path)
                    detail[hero] = hero_detail
            except RepoRootUnavailable as exc:
                return {
                    "action": "refused",
                    "reason": GATE_REASON_ROOT_UNAVAILABLE,
                    "detail": gate_refusal_detail(exc),
                }
            except Exception as exc:
                heroes_refused.append(hero)
                detail[hero] = gate_refusal_detail(exc)
        if not heroes_refused:
            return None
        return {
            "action": "refused",
            "reason": LEGACY_PROFILE_REASON,
            "heroes": heroes_refused,
            "paths": paths,
            "remedy": LEGACY_PROFILE_REMEDY,
            "detail": detail,
        }
    except RepoRootUnavailable as exc:
        return {
            "action": "refused",
            "reason": GATE_REASON_ROOT_UNAVAILABLE,
            "detail": gate_refusal_detail(exc),
        }
    except Exception as exc:
        return {
            "action": "refused",
            "reason": LEGACY_PROFILE_REASON,
            "heroes": [],
            "paths": [],
            "remedy": LEGACY_PROFILE_REMEDY,
            "detail": {"*": gate_refusal_detail(exc)},
        }


import argparse

# Unified-layer hero roster for confirm/write-layer and configure's offerable set.
# Deliberately NOT mirrored in mode_registry's per-hero dicts: guardian has no legacy profile
# (_HERO_LEGACY_INREPO has no entry), and mode_registry._hero_global_root falls through to
# test-pilot's store for unknown names — adding guardian there would mis-route it.
_HEROES = ("review-crew", "test-pilot", "guardian")


def core_facts_are_empty(rec):
    """True when a core.md record PARSES but carries no real shared facts (no verify command,
    threat model, canonical patterns, or stack tags) — an empty placeholder. Restores the
    READ-ONLY half of the #121 Part D belt that went with migrate_on_read (#724): presence of
    such a record must never be read as a populated calibration when advising an owner whether a
    legacy profile is safe to remove. A non-mapping input is treated as empty (fail-closed toward
    the cautious advice). Pure; no I/O; never raises."""
    if rec is None or not isinstance(rec, dict):
        return True
    if rec.get("verifyCommand"):
        return False
    if (rec.get("threatModel") or "").strip():
        return False
    if (rec.get("patterns") or "").strip():
        return False
    if rec.get("stackTags"):
        return False
    return True


def resolve_shared(cwd, *, root=None):
    """The shared facts (FR-2). A legacy single-file profile is NO LONGER migrated on read: when
    core.md supplies the facts the legacy file is simply never consulted, and when it does not,
    a legacy profile is a named refusal pointing at superheroes:configure (issue #724). Never
    migrates, unlinks, or commits, and the detection half writes nothing — but it calls read(),
    which inherits mode_registry.resolve's pre-existing project-store backfill, so it is not
    write-free."""
    rec = read(cwd, root)
    if rec is not None:
        return rec
    refusal = legacy_profile_refusal(cwd, root=root)
    if refusal is not None:
        if refusal.get("reason") == GATE_REASON_ROOT_UNAVAILABLE:
            return refusal
        refusal = dict(refusal)
        refusal["detail"] = dict(refusal.get("detail") or {})
        refusal["detail"]["coreMd"] = engine_preferences_for_gate(cwd=cwd, root=root).status
        return refusal
    return None


def write_layer(cwd, hero, layer_text, status, *, root=None, now=None, rubric_version=None):
    """Lock-guarded atomic write of a hero LAYER file (FR-3 create path), co-located with
    core.md and wrapped in the §2.2 layer provenance line. Returns a structured result:
      - written  → {action: "written", "path": layer_p}
      - lock contended / store unwritable → {action: "deferred"} (UFR-4; never raises)."""
    stamp = now or _today()
    if mode_registry.ensure_project_store(cwd, root) is None:
        return {"action": "deferred"}
    with mode_registry.config_lock(cwd, root) as got:
        if not got:
            return {"action": "deferred"}
        try:
            layer_p = _layer_path(cwd, hero, root)
        except RepoRootUnavailable as exc:
            return {"action": "deferred",
                    "reason": GATE_REASON_ROOT_UNAVAILABLE,
                    "detail": gate_refusal_detail(exc)}
        try:
            store_core.atomic_write(
                layer_p, _render_layer(layer_text, hero, status, stamp, rubric_version))
        except OSError:
            return {"action": "deferred"}
        return {"action": "written", "path": layer_p}


def confirm(cwd, *, root=None, now=None):
    """FR-18 owner-confirm for the shared core: flip an existing PROVISIONAL core.md to confirmed
    IN PLACE. write() (reuse-not-clobber, FR-6) cannot do this on an existing file — it returns
    `reused`/`proposed` and never re-renders — so confirmation needs its own path. Preserves
    `created`, bumps `updated`, re-renders through render_core under the config lock. Fail-open
    like write(). Returns one of:
      - {action: "confirmed"}  flipped provisional → confirmed
      - {action: "noop"}       already confirmed (idempotent)
      - {action: "absent"}     no core.md to confirm
      - {action: "behind"}     core.md is a NEWER schema — refuse to rewrite (UFR-3)
      - {action: "deferred"}   lock contended / store unwritable (UFR-4), or core.md unreadable
        (includes reason/detail when unreadable — not retryable)"""
    with store_core.repo_identity_memo():
        stamp = now or _today()
        existing = read(cwd, root)
        if existing is None:
            gate_cfg = engine_preferences_for_gate(cwd=cwd, root=root)
            if gate_cfg.status == CONFIG_ROOT_UNAVAILABLE:
                return {"action": "deferred", "record": None,
                        "reason": GATE_REASON_ROOT_UNAVAILABLE, "detail": gate_cfg.detail}
            if gate_cfg.status == CONFIG_UNREADABLE:
                return {"action": "deferred", "record": None,
                        "reason": GATE_REASON_UNREADABLE, "detail": gate_cfg.detail}
            return {"action": "absent", "record": None}
        if existing.get("behind"):
            return {"action": "behind", "record": existing}
        if existing.get("status") == "confirmed":
            return {"action": "noop", "record": existing}
        if mode_registry.ensure_project_store(cwd, root) is None:
            mark_pending(cwd, root, detail={"reason": "store-unwritable"})
            return {"action": "deferred", "record": None}
        with mode_registry.config_lock(cwd, root) as got:
            if not got:
                mark_pending(cwd, root, detail={"reason": "lock-contended"})
                return {"action": "deferred", "record": None}
            existing = read(cwd, root)  # re-read under the lock
            if existing is None:
                gate_cfg = engine_preferences_for_gate(cwd=cwd, root=root)
                if gate_cfg.status == CONFIG_ROOT_UNAVAILABLE:
                    return {"action": "deferred", "record": None,
                            "reason": GATE_REASON_ROOT_UNAVAILABLE, "detail": gate_cfg.detail}
                if gate_cfg.status == CONFIG_UNREADABLE:
                    return {"action": "deferred", "record": None,
                            "reason": GATE_REASON_UNREADABLE, "detail": gate_cfg.detail}
                return {"action": "absent", "record": None}
            # UFR-3: never rewrite a forward-schema core — render_core would downgrade it to
            # SCHEMA_VERSION and drop fields this version doesn't understand. Surface, don't write.
            if existing.get("behind"):
                return {"action": "behind", "record": existing}
            if existing.get("status") == "confirmed":
                return {"action": "noop", "record": existing}
            facts = {k: existing[k] for k in (
                "verifyCommand", "stackTags", "threatModel", "patterns", "showItSurface")}
            created = existing.get("created") or stamp
            try:
                store_core.atomic_write(core_path(cwd, root),
                                        render_core(facts, "confirmed", created, stamp))
            except OSError:
                mark_pending(cwd, root, detail={"reason": "store-unwritable"})
                return {"action": "deferred", "record": None}
            record = read(cwd, root)
            clear_pending(cwd, root)
            return {"action": "confirmed", "record": record}


def confirm_layer(cwd, hero, *, root=None, now=None):
    """FR-18 owner-confirm for a hero LAYER: flip a PROVISIONAL layer to confirmed via a surgical
    provenance edit — only `status` and `updated` change; `created`, `nudge-ack`, and the body are
    preserved byte-for-byte (never rewrite a hand-edited layer, FR-11). Fail-open like write_layer.
    Returns {action: "confirmed"|"noop"|"absent"|"deferred"}."""
    stamp = now or _today()
    try:
        layer_p = _layer_path(cwd, hero, root)
    except RepoRootUnavailable as exc:
        return {"action": "deferred",
                "reason": GATE_REASON_ROOT_UNAVAILABLE,
                "detail": gate_refusal_detail(exc)}
    if not os.path.isfile(layer_p):
        return {"action": "absent"}
    if mode_registry.ensure_project_store(cwd, root) is None:
        return {"action": "deferred"}
    with mode_registry.config_lock(cwd, root) as got:
        if not got:
            return {"action": "deferred"}
        # Read UNDER the lock (never from a stale pre-lock read) so a concurrent write_layer that
        # landed while we waited for the lock is not clobbered (/code-review #1).
        try:
            with open(layer_p, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            return {"action": "absent"}
        # DOTALL so a hand-wrapped multi-line provenance comment still matches.
        m = re.match(r"^<!--\s*%s:.*?-->" % re.escape(hero), text, re.DOTALL)
        if not m:
            return {"action": "absent"}  # no §2.2 provenance line — not a managed layer
        if "status=confirmed" in m.group(0):
            return {"action": "noop", "path": layer_p}
        # Surgical, anchored to the FIRST status=/updated= field only (count=1) so a status=/
        # updated= substring inside the nudge-ack map is never rewritten (/code-review #3).
        prov = re.sub(r"status=\S+", "status=confirmed", m.group(0), count=1)
        prov = re.sub(r"updated=\S+", "updated=%s" % stamp, prov, count=1)
        if "status=confirmed" not in prov:
            # the provenance carried no status= field to flip — not a flippable managed layer;
            # never report a false 'confirmed' for a no-op edit (/code-review #3).
            return {"action": "absent"}
        try:
            store_core.atomic_write(layer_p, prov + text[m.end(0):])
        except OSError:
            return {"action": "deferred"}
        return {"action": "confirmed", "path": layer_p}


def confirm_all(cwd, *, root=None, now=None):
    """FR-18 owner-confirm for the WHOLE calibration: the shared core + every present hero layer.
    The entry point the configure fix-path calls once the owner confirms. Returns
    {core: <confirm result>, layers: {hero: <confirm_layer result>}}."""
    with store_core.repo_identity_memo():
        core_res = confirm(cwd, root=root, now=now)
        layers = {}
        # Only flip layers when the shared core is (now) confirmed — a deferred/behind/absent core must
        # not leave layers advertising 'confirmed' over an unconfirmed core, a split state (/code-review
        # #5). `noop` means the core was already confirmed, so layers may still flip.
        if core_res.get("action") in ("confirmed", "noop"):
            for hero in _HEROES:
                try:
                    layer_p = _layer_path(cwd, hero, root)
                except RepoRootUnavailable:
                    break
                if os.path.isfile(layer_p):
                    layers[hero] = confirm_layer(cwd, hero, root=root, now=now)
        return {"core": core_res, "layers": layers}


def main(argv):
    ap = argparse.ArgumentParser(prog="core_md")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("resolve")
    rp.add_argument("--cwd", default=".")
    rp.add_argument("--root", default=None)
    wp = sub.add_parser("write")  # FR-5 create path: shared facts → core.md
    wp.add_argument("--cwd", default=".")
    wp.add_argument("--root", default=None)
    wp.add_argument("--status", choices=("provisional", "confirmed"), default="provisional")
    lp = sub.add_parser("write-layer")  # FR-3: hero's own sections → its layer
    lp.add_argument("--cwd", default=".")
    lp.add_argument("--root", default=None)
    lp.add_argument("--hero", choices=_HEROES, required=True)
    lp.add_argument("--status", choices=("provisional", "confirmed"), default="provisional")
    lp.add_argument("--rubric-version", type=int, default=None)
    cp = sub.add_parser("confirm")  # FR-18 owner-confirm: core + every present hero layer
    cp.add_argument("--cwd", default=".")
    cp.add_argument("--root", default=None)
    sip = sub.add_parser("write-show-it")  # Show-it surface prose section only
    sip.add_argument("--cwd", default=".")
    sip.add_argument("--root", default=None)
    btp = sub.add_parser("write-builder-tier")  # enginePreferences.builderDispatchTier only
    btp.add_argument("--cwd", default=".")
    btp.add_argument("--root", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "resolve":
        try:
            rec = read(args.cwd, args.root)
        except Exception:  # fail-open like review_store.py — never crash a consumer
            rec = None
        out = {"verifyCommand": rec["verifyCommand"] if rec else None,
               "stackTags": rec["stackTags"] if rec else [],
               "status": rec["status"] if rec else None,
               "behind": rec["behind"] if rec else False}
    elif args.cmd == "write":
        try:
            facts = json.loads(sys.stdin.read() or "{}")
            if not isinstance(facts, dict):
                facts = {}
            out = write(args.cwd, facts, args.status, root=args.root)
        except RepoRootUnavailable as exc:
            out = {"action": "deferred", "record": None, "proposals": [],
                    "reason": GATE_REASON_ROOT_UNAVAILABLE,
                    "detail": gate_refusal_detail(exc)}
        except Exception:
            out = {"action": "deferred", "record": None, "proposals": []}
    elif args.cmd == "write-layer":
        try:
            out = write_layer(args.cwd, args.hero, sys.stdin.read(), args.status,
                              root=args.root, rubric_version=args.rubric_version)
        except RepoRootUnavailable as exc:
            out = {"action": "deferred",
                    "reason": GATE_REASON_ROOT_UNAVAILABLE,
                    "detail": gate_refusal_detail(exc)}
        except Exception:
            out = {"action": "deferred"}
    elif args.cmd == "write-show-it":
        try:
            out = write_show_it_surface(args.cwd, sys.stdin.read(), root=args.root)
        except RepoRootUnavailable as exc:
            out = {"action": "deferred",
                    "reason": GATE_REASON_ROOT_UNAVAILABLE,
                    "detail": gate_refusal_detail(exc)}
        except Exception:
            out = {"action": "deferred"}
    elif args.cmd == "write-builder-tier":
        try:
            raw = sys.stdin.read().strip()
            tier = None if raw == "" else raw
            out = write_builder_dispatch_tier(args.cwd, tier, root=args.root)
        except RepoRootUnavailable as exc:
            out = {"action": "deferred",
                    "reason": GATE_REASON_ROOT_UNAVAILABLE,
                    "detail": gate_refusal_detail(exc)}
        except Exception as exc:
            out = {
                "action": "deferred",
                "reason": BUILDER_DISPATCH_DEFER_CLI_FAILED,
            }
    else:  # confirm
        try:
            out = confirm_all(args.cwd, root=args.root)
        except RepoRootUnavailable as exc:
            out = {"core": {"action": "deferred",
                            "reason": GATE_REASON_ROOT_UNAVAILABLE,
                            "detail": gate_refusal_detail(exc)},
                   "layers": {}}
        except Exception:
            out = {"core": {"action": "deferred"}, "layers": {}}
    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
