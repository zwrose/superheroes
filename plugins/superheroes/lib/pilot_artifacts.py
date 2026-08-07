"""External per-slot artifact store — evidence a pilot run produces.

Step logs and failure screenshots persist by default; full traces are opt-in.
Restrictive permissions, retention deadlines, and fail-closed redaction.
"""
import hashlib
import io
import json
import os
import stat
import tempfile
import zipfile
from datetime import datetime, timedelta

import pilot_conformance
import pr_comment
import store
import store_core

SCHEMA = 1

CLASS_FAILURE_SCREENSHOT = "failure-screenshot"
CLASS_STEP_LOG = "step-log"
CLASS_TRACE = "trace"
CLASSES = (CLASS_FAILURE_SCREENSHOT, CLASS_STEP_LOG, CLASS_TRACE)
DEFAULT_CLASSES = frozenset({CLASS_STEP_LOG, CLASS_FAILURE_SCREENSHOT})
OPT_IN_CLASSES = frozenset({CLASS_TRACE})

BASIS_SCRUBBED = "scrubbed"
BASIS_CAPTURE_SCOPE = "capture-scope"
BASIS_ARCHIVE_MEMBER_SCRUB = "archive-member-scrub"
CLASS_BASIS = {
    CLASS_STEP_LOG: BASIS_SCRUBBED,
    CLASS_FAILURE_SCREENSHOT: BASIS_CAPTURE_SCOPE,
    CLASS_TRACE: BASIS_ARCHIVE_MEMBER_SCRUB,
}

DEFAULT_RETENTION_HOURS = {CLASS_STEP_LOG: 168, CLASS_FAILURE_SCREENSHOT: 168, CLASS_TRACE: 24}
MAX_RETENTION_HOURS = 720

PERMITTED_CAPTURE_SCOPE = "viewport"
MAX_ARCHIVE_MEMBERS = 2000
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_TEXT_BYTES = 4 * 1024 * 1024
_DIR_MODE = 0o700
_FILE_MODE = 0o600
SIDECAR_SUFFIX = ".meta.json"

REASON_CLASS_UNKNOWN = "artifact-class-unknown"
REASON_CLASS_NOT_OPTED_IN = "artifact-class-not-opted-in"
REASON_SLOT_INVALID = "artifact-slot-invalid"
REASON_BRANCH_INVALID = "artifact-branch-invalid"
REASON_RETENTION_INVALID = "artifact-retention-invalid"
REASON_NOW_INVALID = "artifact-now-invalid"
REASON_MATERIAL_INVALID = "artifact-material-invalid"
REASON_PAYLOAD_INVALID = "artifact-payload-invalid"
REASON_PAYLOAD_UNREADABLE = "artifact-payload-unreadable"
REASON_PAYLOAD_FORMAT_INVALID = "artifact-payload-format-invalid"
REASON_PAYLOAD_OVERSIZE = "artifact-payload-oversize"
REASON_CAPTURE_RECEIPT_INVALID = "artifact-capture-receipt-invalid"
REASON_REDACTION_UNESTABLISHED = "artifact-redaction-unestablished"
REASON_STORE_PATH_UNSAFE = "artifact-store-path-unsafe"
REASON_STORE_PERMISSIONS_UNSAFE = "artifact-store-permissions-unsafe"
REASON_WRITE_FAILED = "artifact-write-failed"
REASON_SIDECAR_UNRECOVERABLE = "artifact-sidecar-unrecoverable"
REASON_RETENTION_EXPIRED = "artifact-retention-expired"
REASON_SWEEP_FAILED = "artifact-sweep-failed"

_SIDECAR_REQUIRED_KEYS = frozenset({
    "schemaVersion", "class", "branch", "slot", "artifactKey", "basis",
    "writtenAt", "expiresAt", "retentionHours", "payload", "bytes", "sha256",
})

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"


class PilotArtifactsError(Exception):
    """Programmer-error paths only."""

    def __init__(self, message):
        super().__init__(message)


def _ok(**extra):
    out = {"ok": True, "reason": None}
    out.update(extra)
    return out


def _fail(reason, **extra):
    out = {"ok": False, "reason": reason}
    out.update(extra)
    return out


def _is_iso8601_utc(value):
    if not isinstance(value, str) or not value:
        return False
    text = value.strip()
    if not text.endswith("Z"):
        return False
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            datetime.strptime(text, fmt)
            return True
        except ValueError:
            continue
    return False


def _parse_iso8601_utc(value):
    text = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError("unparseable timestamp")


def _add_hours_iso8601(now, hours):
    dt = _parse_iso8601_utc(now)
    return (dt + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def _is_exact_int(value, minimum=None, maximum=None):
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    if minimum is not None and value < minimum:
        return False
    if maximum is not None and value > maximum:
        return False
    return True


def _assert_safe_dir(path):
    """Refuse unsafe store directories (symlink, non-dir, loose mode)."""
    try:
        st = os.lstat(path)
    except OSError:
        return _fail(REASON_STORE_PATH_UNSAFE)
    if stat.S_ISLNK(st.st_mode):
        return _fail(REASON_STORE_PATH_UNSAFE)
    if not stat.S_ISDIR(st.st_mode):
        return _fail(REASON_STORE_PATH_UNSAFE)
    # bite-axis: permission floor — group/other bits must be zero.
    if stat.S_IMODE(st.st_mode) & 0o077:
        return _fail(REASON_STORE_PERMISSIONS_UNSAFE)
    return None


def _ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path, mode=_DIR_MODE, exist_ok=True)
        os.chmod(path, _DIR_MODE)
    refused = _assert_safe_dir(path)
    if refused is not None:
        return refused
    return None


def _path_contained_in(path, container):
    try:
        real_path = os.path.realpath(path)
        real_container = os.path.realpath(container)
    except OSError:
        return False
    if real_path == real_container:
        return True
    try:
        common = os.path.commonpath([real_path, real_container])
    except ValueError:
        return False
    return common == real_container


def _validate_material(material):
    if not isinstance(material, (list, tuple)) or not material:
        return _fail(REASON_MATERIAL_INVALID)
    for item in material:
        if not isinstance(item, str) or not item:
            return _fail(REASON_MATERIAL_INVALID)
    return None


def _residue_scan(text, material):
    for needle in material:
        # bite-axis: residue scan is substring-based — embedded secrets refuse.
        if needle in text:
            return _fail(REASON_REDACTION_UNESTABLISHED)
    return None


def _scrub_text(text, material):
    try:
        scrubbed = pr_comment.scrub(text)
    except Exception:
        return _fail(REASON_REDACTION_UNESTABLISHED)
    refused = _residue_scan(scrubbed, material)
    if refused is not None:
        return refused
    return scrubbed


def _establish_scrubbed(text, material):
    result = _scrub_text(text, material)
    if isinstance(result, dict) and not result.get("ok", True):
        return result
    return result


def _establish_capture(payload_bytes, capture):
    if not isinstance(capture, dict) or set(capture.keys()) != {"scope", "sha256"}:
        return _fail(REASON_CAPTURE_RECEIPT_INVALID)
    if capture["scope"] != PERMITTED_CAPTURE_SCOPE:
        return _fail(REASON_CAPTURE_RECEIPT_INVALID)
    digest = capture["sha256"]
    if not isinstance(digest, str) or len(digest) != 64:
        return _fail(REASON_CAPTURE_RECEIPT_INVALID)
    try:
        int(digest, 16)
    except ValueError:
        return _fail(REASON_CAPTURE_RECEIPT_INVALID)
    if digest != digest.lower():
        return _fail(REASON_CAPTURE_RECEIPT_INVALID)
    actual = hashlib.sha256(payload_bytes).hexdigest()
    # bite-axis: capture receipt bound to payload bytes via sha256 equality.
    if digest != actual:
        return _fail(REASON_CAPTURE_RECEIPT_INVALID)
    if payload_bytes.startswith(_PNG_MAGIC) or payload_bytes.startswith(_JPEG_MAGIC):
        return payload_bytes
    return _fail(REASON_PAYLOAD_FORMAT_INVALID)


def _zip_member_name_safe(name):
    if not name or name.startswith("/"):
        return False
    if "\\" in name:
        return False
    parts = name.split("/")
    return ".." not in parts


def _establish_archive(payload_bytes, material):
    try:
        zf = zipfile.ZipFile(io.BytesIO(payload_bytes), "r")
    except zipfile.BadZipFile:
        return _fail(REASON_PAYLOAD_FORMAT_INVALID)
    except Exception:
        return _fail(REASON_PAYLOAD_FORMAT_INVALID)

    try:
        infos = zf.infolist()
        if len(infos) > MAX_ARCHIVE_MEMBERS:
            return _fail(REASON_PAYLOAD_OVERSIZE)
        total = 0
        for info in infos:
            total += info.file_size
            if total > MAX_ARCHIVE_BYTES:
                return _fail(REASON_PAYLOAD_OVERSIZE)
            if not _zip_member_name_safe(info.filename):
                return _fail(REASON_PAYLOAD_FORMAT_INVALID)

        out_buf = io.BytesIO()
        out_zip = zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED)
        for info in infos:
            raw = zf.read(info.filename)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                # bite-axis: binary archive members cannot be scrubbed — refuse.
                return _fail(REASON_REDACTION_UNESTABLISHED)
            scrubbed = _scrub_text(text, material)
            if isinstance(scrubbed, dict) and not scrubbed.get("ok", True):
                return scrubbed
            out_zip.writestr(info, scrubbed)
        out_zip.close()
        return out_buf.getvalue()
    finally:
        zf.close()


def _write_binary_atomic(path, data):
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".pilot-artifact.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        os.chmod(path, _FILE_MODE)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_regular_file(path):
    if not isinstance(path, str) or not path:
        return _fail(REASON_PAYLOAD_UNREADABLE)
    if os.path.islink(path):
        return _fail(REASON_PAYLOAD_UNREADABLE)
    try:
        st = os.lstat(path)
    except OSError:
        return _fail(REASON_PAYLOAD_UNREADABLE)
    if not stat.S_ISREG(st.st_mode):
        return _fail(REASON_PAYLOAD_UNREADABLE)
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return _fail(REASON_PAYLOAD_UNREADABLE)


def _load_sidecar(sidecar_path):
    try:
        with open(sidecar_path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(obj, dict):
        return None
    if set(obj.keys()) != _SIDECAR_REQUIRED_KEYS:
        return None
    if obj.get("schemaVersion") != SCHEMA:
        return None
    if not _is_iso8601_utc(obj.get("expiresAt")):
        return None
    return obj


def _list_entry(artifact_key, artifact_class, artifact_id, reason):
    return {
        "artifactKey": artifact_key,
        "class": artifact_class,
        "artifactId": artifact_id,
        "reason": reason,
    }


def _safe_unlink(path, artifacts_dir, warnings, artifact_key="", artifact_class="", artifact_id=""):
    if os.path.islink(path):
        warnings.append(_list_entry(artifact_key, artifact_class, artifact_id, REASON_SWEEP_FAILED))
        return
    if not _path_contained_in(path, artifacts_dir):
        warnings.append(_list_entry(artifact_key, artifact_class, artifact_id, REASON_SWEEP_FAILED))
        return
    try:
        os.unlink(path)
    except OSError:
        warnings.append(_list_entry(artifact_key, artifact_class, artifact_id, REASON_SWEEP_FAILED))


def _remove_artifact(payload_path, sidecar_path, artifacts_dir, artifact_key,
                     artifact_class, artifact_id, reason, removed, warnings):
    if payload_path and os.path.isfile(payload_path):
        _safe_unlink(payload_path, artifacts_dir, warnings,
                     artifact_key, artifact_class, artifact_id)
    if sidecar_path and os.path.isfile(sidecar_path):
        _safe_unlink(sidecar_path, artifacts_dir, warnings,
                     artifact_key, artifact_class, artifact_id)
    removed.append(_list_entry(artifact_key, artifact_class, artifact_id, reason))


def sweep(artifacts_dir, *, now):
    """Remove expired or unrecoverable artifacts."""
    if not _is_iso8601_utc(now):
        return _fail(REASON_NOW_INVALID, removed=[], retained=[], warnings=[])

    if not os.path.exists(artifacts_dir):
        return _ok(removed=[], retained=[], warnings=[])

    refused = _assert_safe_dir(artifacts_dir)
    if refused is not None:
        refused.update({"removed": [], "retained": [], "warnings": []})
        return refused

    removed = []
    retained = []
    warnings = []

    try:
        keys = os.listdir(artifacts_dir)
    except OSError:
        return _ok(removed=removed, retained=retained, warnings=warnings)

    for key_name in keys:
        key_dir = os.path.join(artifacts_dir, key_name)
        if not os.path.isdir(key_dir) or os.path.islink(key_dir):
            continue
        try:
            classes = os.listdir(key_dir)
        except OSError:
            continue
        for class_name in classes:
            class_dir = os.path.join(key_dir, class_name)
            if not os.path.isdir(class_dir) or os.path.islink(class_dir):
                continue
            try:
                names = os.listdir(class_dir)
            except OSError:
                continue
            sidecars = {}
            payloads = set()
            for name in names:
                full = os.path.join(class_dir, name)
                if name.endswith(SIDECAR_SUFFIX) and os.path.isfile(full) and not os.path.islink(full):
                    artifact_id = name[:-len(SIDECAR_SUFFIX)]
                    sidecars[artifact_id] = full
                elif os.path.isfile(full) and not os.path.islink(full) and not name.endswith(SIDECAR_SUFFIX):
                    payloads.add(name)

            for artifact_id in sorted(payloads):
                payload_path = os.path.join(class_dir, artifact_id)
                sidecar_path = sidecars.get(artifact_id)
                if sidecar_path is None:
                    # bite-axis: unrecoverable sidecar removes payload — no indefinite retention.
                    _remove_artifact(
                        payload_path, None, artifacts_dir, key_name, class_name,
                        artifact_id, REASON_SIDECAR_UNRECOVERABLE, removed, warnings,
                    )
                    continue
                sidecar = _load_sidecar(sidecar_path)
                if sidecar is None:
                    _remove_artifact(
                        payload_path, sidecar_path, artifacts_dir, key_name, class_name,
                        artifact_id, REASON_SIDECAR_UNRECOVERABLE, removed, warnings,
                    )
                    continue
                expires_at = sidecar["expiresAt"]
                # bite-axis: retention removes on deadline — readership is irrelevant.
                if expires_at <= now:
                    _remove_artifact(
                        payload_path, sidecar_path, artifacts_dir, key_name, class_name,
                        artifact_id, REASON_RETENTION_EXPIRED, removed, warnings,
                    )
                else:
                    retained.append(_list_entry(key_name, class_name, artifact_id, None))

            for artifact_id, sidecar_path in sidecars.items():
                if artifact_id not in payloads:
                    _remove_artifact(
                        None, sidecar_path, artifacts_dir, key_name, class_name,
                        artifact_id, REASON_SIDECAR_UNRECOVERABLE, removed, warnings,
                    )

    return _ok(removed=removed, retained=retained, warnings=warnings)


def retain(artifacts_dir, *, branch, slot, artifact_class, payload_text=None,
           payload_path=None, material, now, capture=None, retention_hours=None,
           opted_in=False):
    """Retain one artifact in the external per-slot store."""
    if artifact_class not in CLASSES:
        return _fail(REASON_CLASS_UNKNOWN)

    if not isinstance(branch, str) or not branch:
        return _fail(REASON_BRANCH_INVALID)
    if not isinstance(slot, str) or not slot or not store.SLOT_RE.match(slot):
        return _fail(REASON_SLOT_INVALID)
    try:
        artifact_key = store.artifact_key(branch, slot)
    except ValueError:
        return _fail(REASON_BRANCH_INVALID)

    if not _is_iso8601_utc(now):
        return _fail(REASON_NOW_INVALID)

    if retention_hours is None:
        retention_hours = DEFAULT_RETENTION_HOURS[artifact_class]
    if not _is_exact_int(retention_hours, minimum=1, maximum=MAX_RETENTION_HOURS):
        return _fail(REASON_RETENTION_INVALID)

    # bite-axis: opt-in classes require opted_in is True (identity, not truthiness).
    if artifact_class in OPT_IN_CLASSES and opted_in is not True:
        return _fail(REASON_CLASS_NOT_OPTED_IN)

    refused = _validate_material(material)
    if refused is not None:
        return refused

    if artifact_class == CLASS_STEP_LOG:
        if not isinstance(payload_text, str) or payload_path is not None:
            return _fail(REASON_PAYLOAD_INVALID)
        if len(payload_text.encode("utf-8")) > MAX_TEXT_BYTES:
            return _fail(REASON_PAYLOAD_OVERSIZE)
        payload_bytes = payload_text.encode("utf-8")
    else:
        if payload_text is not None or not isinstance(payload_path, str):
            return _fail(REASON_PAYLOAD_INVALID)
        payload_bytes = _read_regular_file(payload_path)
        if isinstance(payload_bytes, dict) and not payload_bytes.get("ok", True):
            return payload_bytes

    sweep_result = sweep(artifacts_dir, now=now)
    if not sweep_result["ok"]:
        return sweep_result
    swept = sweep_result.get("removed", [])

    basis = CLASS_BASIS[artifact_class]
    if basis == BASIS_SCRUBBED:
        established = _establish_scrubbed(payload_text, material)
        if isinstance(established, dict) and not established.get("ok", True):
            return established
        payload_bytes = established.encode("utf-8")
    elif basis == BASIS_CAPTURE_SCOPE:
        established = _establish_capture(payload_bytes, capture)
        if isinstance(established, dict) and not established.get("ok", True):
            return established
        payload_bytes = established
    else:
        established = _establish_archive(payload_bytes, material)
        if isinstance(established, dict) and not established.get("ok", True):
            return established
        payload_bytes = established

    refused = _assert_safe_dir(artifacts_dir) if os.path.exists(artifacts_dir) else None
    if refused is not None:
        return refused

    slot_root = os.path.join(artifacts_dir, artifact_key)
    class_dir = os.path.join(slot_root, artifact_class)
    for path in (artifacts_dir, slot_root, class_dir):
        refused = _ensure_dir(path)
        if refused is not None:
            return refused

    artifact_id = os.urandom(16).hex()
    payload_out = os.path.join(class_dir, artifact_id)
    sidecar_out = payload_out + SIDECAR_SUFFIX
    expires_at = _add_hours_iso8601(now, retention_hours)
    digest = hashlib.sha256(payload_bytes).hexdigest()

    try:
        _write_binary_atomic(payload_out, payload_bytes)
        sidecar_obj = {
            "schemaVersion": SCHEMA,
            "class": artifact_class,
            "branch": branch,
            "slot": slot,
            "artifactKey": artifact_key,
            "basis": basis,
            "writtenAt": now,
            "expiresAt": expires_at,
            "retentionHours": retention_hours,
            "payload": artifact_id,
            "bytes": len(payload_bytes),
            "sha256": digest,
        }
        store_core.atomic_write(sidecar_out, json.dumps(sidecar_obj, separators=(",", ":")))
        os.chmod(sidecar_out, _FILE_MODE)
    except OSError:
        for path in (payload_out, sidecar_out):
            try:
                if os.path.isfile(path):
                    os.unlink(path)
            except OSError:
                pass
        return _fail(REASON_WRITE_FAILED)

    out = _ok(
        artifactKey=artifact_key,
        artifactId=artifact_id,
        path=payload_out,
        sidecar=sidecar_out,
        basis=basis,
        writtenAt=now,
        expiresAt=expires_at,
        bytes=len(payload_bytes),
        sha256=digest,
        swept=swept,
    )
    out["class"] = artifact_class
    return out


@pilot_conformance.register("artifact-store",
                            surfaces=["pilot_artifacts.retain", "pilot_artifacts.sweep"])
def conformance_exercise(*, inputs, now):
    """Exercise retain + sweep on a real artifact store."""
    if not isinstance(inputs, dict):
        return pilot_conformance.exercise_record(
            exercise="artifact-store",
            surfaces=["pilot_artifacts.retain", "pilot_artifacts.sweep"],
            result=pilot_conformance.RESULT_SKIPPED,
            reason=REASON_MATERIAL_INVALID,
            evidence="inputs missing or malformed",
            exercised_at=now,
        )

    artifacts = inputs.get("artifacts")
    if not isinstance(artifacts, dict):
        return pilot_conformance.exercise_record(
            exercise="artifact-store",
            surfaces=["pilot_artifacts.retain", "pilot_artifacts.sweep"],
            result=pilot_conformance.RESULT_SKIPPED,
            reason=REASON_MATERIAL_INVALID,
            evidence="artifacts input missing or malformed",
            exercised_at=now,
        )

    artifacts_dir = artifacts.get("artifacts_dir")
    branch = artifacts.get("branch")
    slot = artifacts.get("slot")
    material = artifacts.get("material")
    if (
        not isinstance(artifacts_dir, str)
        or not isinstance(branch, str)
        or not isinstance(slot, str)
        or not isinstance(material, (list, tuple))
        or not material
    ):
        return pilot_conformance.exercise_record(
            exercise="artifact-store",
            surfaces=["pilot_artifacts.retain", "pilot_artifacts.sweep"],
            result=pilot_conformance.RESULT_SKIPPED,
            reason=REASON_MATERIAL_INVALID,
            evidence="artifacts fields missing or malformed",
            exercised_at=now,
        )

    held = 0
    first_fail = None

    clean = retain(
        artifacts_dir,
        branch=branch,
        slot=slot,
        artifact_class=CLASS_STEP_LOG,
        payload_text="step ok",
        material=material,
        now=now,
    )
    if clean.get("ok"):
        payload_path = clean["path"]
        sidecar_path = clean["sidecar"]
        if (
            os.path.isfile(payload_path)
            and os.path.isfile(sidecar_path)
            and stat.S_IMODE(os.stat(payload_path).st_mode) == _FILE_MODE
            and stat.S_IMODE(os.stat(sidecar_path).st_mode) == _FILE_MODE
        ):
            held += 1
        else:
            first_fail = first_fail or REASON_WRITE_FAILED
    else:
        first_fail = first_fail or clean.get("reason")

    dirty_before = 0
    class_dir = os.path.join(artifacts_dir, store.artifact_key(branch, slot), CLASS_STEP_LOG)
    if os.path.isdir(class_dir):
        dirty_before = sum(
            1 for name in os.listdir(class_dir)
            if not name.endswith(SIDECAR_SUFFIX) and os.path.isfile(os.path.join(class_dir, name))
        )
    dirty = retain(
        artifacts_dir,
        branch=branch,
        slot=slot,
        artifact_class=CLASS_STEP_LOG,
        payload_text="failed connecting to %s" % material[0],
        material=material,
        now=now,
    )
    dirty_after = 0
    if os.path.isdir(class_dir):
        dirty_after = sum(
            1 for name in os.listdir(class_dir)
            if not name.endswith(SIDECAR_SUFFIX) and os.path.isfile(os.path.join(class_dir, name))
        )
    if (
        not dirty.get("ok")
        and dirty.get("reason") == REASON_REDACTION_UNESTABLISHED
        and dirty_after == dirty_before
    ):
        held += 1
    else:
        first_fail = first_fail or dirty.get("reason") or REASON_REDACTION_UNESTABLISHED

    trace_fd, trace_zip = tempfile.mkstemp(suffix=".zip")
    os.close(trace_fd)
    try:
        with zipfile.ZipFile(trace_zip, "w") as zf:
            zf.writestr("log.txt", "trace line")
        trace_refused = retain(
            artifacts_dir,
            branch=branch,
            slot=slot,
            artifact_class=CLASS_TRACE,
            payload_path=trace_zip,
            material=material,
            now=now,
            opted_in=False,
        )
    finally:
        try:
            os.unlink(trace_zip)
        except OSError:
            pass
    if not trace_refused.get("ok") and trace_refused.get("reason") == REASON_CLASS_NOT_OPTED_IN:
        held += 1
    else:
        first_fail = first_fail or trace_refused.get("reason") or REASON_CLASS_NOT_OPTED_IN

    short_now = now
    short = retain(
        artifacts_dir,
        branch=branch,
        slot=slot,
        artifact_class=CLASS_STEP_LOG,
        payload_text="expires soon",
        material=material,
        now=short_now,
        retention_hours=1,
    )
    if short.get("ok"):
        later = _add_hours_iso8601(short_now, 2)
        sweep_out = sweep(artifacts_dir, now=later)
        removed = sweep_out.get("removed", [])
        expired = [
            entry for entry in removed
            if entry.get("reason") == REASON_RETENTION_EXPIRED
            and entry.get("artifactId") == short.get("artifactId")
        ]
        if expired:
            held += 1
        else:
            first_fail = first_fail or REASON_RETENTION_EXPIRED
    else:
        first_fail = first_fail or short.get("reason")

    if held == 4:
        return pilot_conformance.exercise_record(
            exercise="artifact-store",
            surfaces=["pilot_artifacts.retain", "pilot_artifacts.sweep"],
            result=pilot_conformance.RESULT_PASS,
            reason=None,
            evidence="4/4 expectations held",
            exercised_at=now,
        )

    return pilot_conformance.exercise_record(
        exercise="artifact-store",
        surfaces=["pilot_artifacts.retain", "pilot_artifacts.sweep"],
        result=pilot_conformance.RESULT_FAIL,
        reason=first_fail or REASON_WRITE_FAILED,
        evidence="%d/4 expectations held" % held,
        exercised_at=now,
    )
