#!/usr/bin/env python3
"""Self-healing reconcile engine + coalesced drift-nudge for the storage-mode registry
(CONVENTIONS §2.3/§2.4). Stdlib-only. The init skill drives reconcile(); tests drive it now.
Reconcile items are derived purely from current on-disk state; only dismissal (nudge-ack)
is durable."""
import argparse
import hashlib
import json
import os
import sys

import store_core
import mode_registry as mr


def _sig_id(*parts):
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def gather_signals(cwd, root=None):
    """Pure function of on-disk state → the outstanding reconcile items."""
    locs = mr.hero_evidence(cwd, root)
    verdict = mr.evidence_verdict(locs)
    rec = mr.read_registry(cwd, root)
    sigs = []
    if rec is None:
        if verdict == "disagree":
            # FR-10 identity stability: hash only PRESENT heroes so a future none-hero
            # cannot change the identity and re-surface a dismissed nudge (aligns with the
            # migration-pending branch, which already filters to off-heroes).
            facts = sorted(f"{k}={v}" for k, v in locs.items() if v != "none")
            sigs.append({"type": "disagreement",
                         "identity": _sig_id("disagreement", *facts), "detail": locs})
        elif verdict == "none":
            sigs.append({"type": "provisional-mode",
                         "identity": _sig_id("provisional-mode"), "detail": {}})
    else:
        off = {k: v for k, v in locs.items()
               if v != "none" and v != rec["storageMode"]}
        if off:
            facts = sorted(f"{k}={v}" for k, v in off.items())
            sigs.append({"type": "migration-pending",
                         "identity": _sig_id("migration-pending", rec["storageMode"], *facts),
                         "detail": {"recorded": rec["storageMode"], "off": off}})
    # I3 wiring obligation (#80): surface an in-repo provisional doc-policy through the one
    # coalesced nudge. Read-only deferred import (the mode_registry._hero_global_root precedent).
    if rec is not None and rec["storageMode"] == mr.IN_REPO:
        try:
            import architect_config
            pol = architect_config.read_policy(cwd, root)
        except (OSError, ImportError, ValueError):
            pol = None
        if pol is not None and not pol.get("confirmed", False):
            sigs.append({"type": "doc-policy-provisional",
                         "identity": _sig_id("doc-policy-provisional:" + str(pol.get("location"))),
                         "detail": {"location": pol.get("location")}})

    # --- #81: core.md calibration drift (all disk-derived; only dismissal is durable) ---
    try:
        import core_md
        core_p = core_md.core_path(cwd, root)
        core_exists = os.path.exists(core_p)
        core_rec = core_md.read(cwd, root)
    except (OSError, ImportError, ValueError):
        core_p, core_exists, core_rec = None, False, None

    if core_rec is not None:
        if core_rec.get("behind"):
            sigs.append({"type": "hero-behind",
                         "identity": _sig_id("hero-behind", str(core_rec["schemaVersion"])),
                         "detail": {"schemaVersion": core_rec["schemaVersion"]}})
        elif core_rec.get("status") == "provisional":
            sigs.append({"type": "core-md-provisional",
                         "identity": _sig_id("core-md-provisional"), "detail": {}})
    elif core_exists:
        # a core.md file is present but did not parse → corrupt (UFR-1); NOT a greenfield.
        sigs.append({"type": "core-md-unreadable",
                     "identity": _sig_id("core-md-unreadable"), "detail": {}})

    # per-hero legacy-profile drift: ambiguous-pending (no usable core.md) or stray (core.md exists)
    for hero in mr._HERO_INREPO:
        try:
            legacy = core_md._legacy_path(cwd, hero) if core_p is not None else None
        except Exception:
            legacy = None
        if not legacy or not os.path.isfile(legacy):
            continue
        if core_rec is not None:
            sigs.append({"type": "migration-incomplete",
                         "identity": _sig_id("migration-incomplete", hero),
                         "detail": {"hero": hero}})
            continue
        try:
            with open(legacy, encoding="utf-8") as fh:
                klass = core_md.classify(fh.read(), hero)
        except OSError:
            klass = "ambiguous"
        if klass == "ambiguous":
            sigs.append({"type": "legacy-migration-ambiguous",
                         "identity": _sig_id("legacy-migration-ambiguous", hero),
                         "detail": {"hero": hero}})

    # calibration-not-saved (UFR-4): the machine-local pending marker, read DIRECTLY (no
    # core_md import here — avoids an import cycle; the marker path is owned by mode_registry's
    # project_store_dir, the same dir this engine already uses).
    try:
        pending_path = os.path.join(mr.project_store_dir(cwd, root), "calibration-pending.json")
        with open(pending_path, encoding="utf-8") as fh:
            marker = json.load(fh)
    except (OSError, ValueError):
        marker = None
    if isinstance(marker, dict) and marker.get("pending"):
        sigs.append({"type": "calibration-not-saved",
                     "identity": _sig_id("calibration-not-saved"),
                     "detail": marker.get("detail") or {}})
    return sigs


def _ack_path(cwd, root=None):
    return os.path.join(mr.project_store_dir(cwd, root), "nudge-ack.json")


def read_acks(cwd, root=None):
    try:
        with open(_ack_path(cwd, root), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def ack_signal(cwd, identity, root=None):
    if mr.ensure_project_store(cwd, root) is None:
        return
    acks = read_acks(cwd, root)
    acks[identity] = True
    store_core.atomic_write(_ack_path(cwd, root), json.dumps(acks, indent=2))


def coalesce(cwd, root=None):
    """One combined reconcile prompt (FR-9) over the unacked signals (FR-10)."""
    acks = read_acks(cwd, root)
    items = [s for s in gather_signals(cwd, root) if s["identity"] not in acks]
    if not items:
        return None
    return {"count": len(items), "items": items,
            "message": f"this project has {len(items)} item(s) to reconcile — run init to settle it"}


def reconcile(cwd, chosen_mode=None, root=None):
    """The engine the init skill drives. Given an owner-chosen mode, record it
    authoritatively (FR-7), allowing migration of a prior mode; a disagreement is
    recorded now with the physical move deferred to I6 (a migration-pending signal
    remains). Without a chosen mode: backfill consistent evidence, else no-op."""
    mr.ensure_project_store(cwd, root)
    if chosen_mode is not None:
        if chosen_mode not in (mr.IN_REPO, mr.GLOBAL):
            raise ValueError(f"invalid mode: {chosen_mode!r}")
        remote_hash = store_core.derive_identifiers(cwd)["remote_hash"]
        written = mr.write_registry(cwd, chosen_mode, remote_hash, root, allow_migration=True)
        if written is None:
            sys.stderr.write(
                f"mode_reconcile: chosen mode {chosen_mode!r} could not be persisted "
                "(store contended or unwritable); deferring — owner will be asked again\n")
        # action is honest: "recorded" only when the write landed, else "deferred".
        return {"action": "recorded" if written is not None else "deferred",
                "mode": chosen_mode,
                "written": written is not None, "signals": gather_signals(cwd, root)}
    if mr.read_registry(cwd, root) is None:
        verdict = mr.evidence_verdict(mr.hero_evidence(cwd, root))
        if verdict in (mr.IN_REPO, mr.GLOBAL):
            remote_hash = store_core.derive_identifiers(cwd)["remote_hash"]
            wrote = mr.write_registry(cwd, verdict, remote_hash, root)
            if wrote is None:
                sys.stderr.write(
                    "mode_reconcile: backfill could not be persisted (store contended or unwritable)\n")
            return {"action": "backfilled" if wrote is not None else "deferred",
                    "mode": verdict, "written": wrote is not None,
                    "signals": gather_signals(cwd, root)}
    return {"action": "noop", "mode": None, "written": None, "signals": gather_signals(cwd, root)}


def main(argv):
    ap = argparse.ArgumentParser(prog="mode_reconcile")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("resolve", "signals", "reconcile"):
        sp = sub.add_parser(name)
        sp.add_argument("--cwd", default=".")
        sp.add_argument("--root", default=None)
        if name == "reconcile":
            sp.add_argument("--mode", choices=[mr.IN_REPO, mr.GLOBAL], default=None)
    args = ap.parse_args(argv)
    if args.cmd == "resolve":
        out = mr.resolve(args.cwd, args.root)
    elif args.cmd == "signals":
        out = coalesce(args.cwd, args.root)
    else:
        out = reconcile(args.cwd, args.mode, args.root)
    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
