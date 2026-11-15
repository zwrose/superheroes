"""The calibration a review session reads, captured once when the session is created (#2502).

Stdlib plus sibling lib modules only. ``capture`` copies the project's core.md, review-crew layer and
CLAUDE.md into ``<session>/calibration-pin/`` and reads the risk areas, engine preferences and store-mode
ratified residuals from those copies; the driver keeps the result in its state and reads only it for the
rest of the session. A file that cannot be copied is recorded ``unreadable``, never replaced by its live
path. ``capture`` and ``load`` never raise.
"""
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import calibration_read  # noqa: E402
import core_md  # noqa: E402
import engine_pref  # noqa: E402
import mode_registry  # noqa: E402
import round_orders  # noqa: E402

PIN_DIR = "calibration-pin"
MANIFEST = "pin.json"
SCHEMA = "calibration-pin/1"
LABEL_CORE = "core"
LABEL_LAYER = "layer"
LABEL_CLAUDE_MD = "claudeMd"
REASON_ABSENT = "absent"
REASON_NO_SESSION_FOLDER = "no-session-folder"
REASON_UNREADABLE = "unreadable"
_PREFIX = "calibration-pin: "


def load(session_dir):
    """The parsed manifest under ``session_dir`` when it is a dict of this schema, else None."""
    try:
        with open(os.path.join(session_dir, PIN_DIR, MANIFEST), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) and data.get("schema") == SCHEMA else None
    except Exception:
        return None


def manifest_for(path):
    """The manifest of the session whose ``calibration-pin`` folder holds ``path``, else None."""
    try:
        parent = os.path.dirname(path)
        while parent and parent != os.path.dirname(parent):
            if os.path.basename(parent) == PIN_DIR and os.path.isfile(os.path.join(parent, MANIFEST)):
                return load(os.path.dirname(parent))
            parent = os.path.dirname(parent)
    except Exception:
        pass
    return None


def _entry(path, file, source, sha, reason, detail):
    return {"path": path, "file": file, "source": source, "sha256": sha, "reason": reason, "detail": detail}


def _copy(label, src, session_dir):
    """One pin entry: the bytes of ``src`` read once and written under the session folder."""
    base = os.path.basename(src)
    try:
        with open(src, "rb") as fh:
            data = fh.read()
        folder = os.path.join(session_dir, PIN_DIR, label)
        os.makedirs(folder, exist_ok=True)
        dest = os.path.join(folder, base)
        with open(dest, "wb") as fh:
            fh.write(data)
        # axis: the pin holds a copy of the bytes read, never a link to the live path — see bite-proof record wo1_2502_calibration_pin
        return _entry(dest, base, src, hashlib.sha256(data).hexdigest(), None, None)
    except OSError as exc:
        # the detail names the exception and its reason, never a filename, so no placeholder repeats a path
        return _entry(None, base, src, None, REASON_UNREADABLE, "%s: %s" % (type(exc).__name__, exc.strerror or ""))


def _absent(detail=None):
    return _entry(None, None, None, None, REASON_ABSENT, detail)


def _derive(repo_root, core):
    """(riskAreas, enginePrefs, residuals) read from the core entry's copy, never from the live store."""
    path, reason, detail = core["path"], core["reason"], core["detail"]
    if path:
        risk = core_md.read_risk_areas(repo_root, path=path)
        prefs = engine_pref.load_engine_prefs(repo_root, profile_path=path)
    elif reason == REASON_ABSENT:
        risk = core_md.read_risk_areas(repo_root)
        prefs = engine_pref.load_engine_prefs(repo_root)
    else:
        risk = {"declared": False, "areas": None, "malformed": [], "reason": core_md.RISK_AREAS_REASON_UNREADABLE,
                "detail": _PREFIX + str(detail), "behind": False}
        prefs = engine_pref.refusal_engine_prefs(_PREFIX + str(detail))
    try:
        mode = mode_registry.resolve(repo_root, persist_backfill=False).get("mode")
    except Exception:
        mode = None
    if mode == mode_registry.IN_REPO:
        return risk, prefs, {"storage": "in-repo"}
    if path:
        text, prov, failure = round_orders.resolve_order_residuals(repo_root, None, core_path=path)
    elif reason == REASON_ABSENT:
        text, prov, failure = round_orders.resolve_order_residuals(repo_root, None)
    else:
        text, prov, failure = "", None, _PREFIX + str(detail)
    return risk, prefs, {"storage": "store", "text": text, "provenance": prov, "failure": failure}


def _write_manifest(session_dir, pin):
    folder = os.path.join(session_dir, PIN_DIR)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".pin.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(pin, fh, indent=2)
        os.replace(tmp, os.path.join(folder, MANIFEST))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def capture(repo_root, session_dir):
    """The calibration pin for the session at ``session_dir``; the manifest already on disk when there is one.

    Never raises. A manifest that cannot be written leaves the returned pin intact."""
    try:
        first = load(session_dir)
        if first is not None:
            return first
        core_src, layer_src, refusal = calibration_read.resolved_paths(repo_root)
        claude = os.path.join(repo_root, "CLAUDE.md")
        claude_src = claude if os.path.isfile(claude) else None
        files = {}
        for label, src in ((LABEL_CORE, core_src), (LABEL_LAYER, layer_src), (LABEL_CLAUDE_MD, claude_src)):
            absent_detail = refusal if label != LABEL_CLAUDE_MD else None
            files[label] = _copy(label, src, session_dir) if src else _absent(absent_detail)
        risk, prefs, residuals = _derive(repo_root, files[LABEL_CORE])
        pin = {"schema": SCHEMA, "capturedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "repoRoot": repo_root, "rootRefusal": refusal, "files": files, "riskAreas": risk,
               "enginePrefs": prefs, "residuals": residuals}
        try:
            _write_manifest(session_dir, pin)
        except Exception:
            pass
        return pin
    except Exception as exc:
        detail = "%s: %s" % (type(exc).__name__, getattr(exc, "strerror", None) or "")
        entry = lambda: _entry(None, None, None, None, REASON_UNREADABLE, detail)  # noqa: E731
        return {"schema": SCHEMA, "capturedAt": None, "repoRoot": repo_root, "rootRefusal": None,
                "files": {LABEL_CORE: entry(), LABEL_LAYER: entry(), LABEL_CLAUDE_MD: entry()},
                "riskAreas": {"declared": False, "areas": None, "malformed": [], "behind": False,
                              "reason": core_md.RISK_AREAS_REASON_UNREADABLE, "detail": _PREFIX + detail},
                "enginePrefs": engine_pref.refusal_engine_prefs(_PREFIX + detail),
                "residuals": {"storage": "store", "text": "", "provenance": None, "failure": _PREFIX + detail}}
