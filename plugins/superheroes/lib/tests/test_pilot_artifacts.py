"""Tests for pilot_artifacts.py — external per-slot artifact store."""
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import time
import zipfile

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_artifacts as pa  # noqa: E402
import store  # noqa: E402

_NOW = "2026-08-07T12:00:00Z"
_BRANCH = "feat/x"
_SLOT = "admin"
_MATERIAL = ["secret-token-xyz"]
_BEARER_SECRET = "Bearer abcdefgh12345678"


def _artifacts_dir(tmp_path):
    path = os.path.join(str(tmp_path), "artifacts")
    os.makedirs(path, mode=0o700)
    os.chmod(path, 0o700)
    return path


def _retain_step_log(artifacts_dir, text="clean step", **kwargs):
    base = {
        "branch": _BRANCH,
        "slot": _SLOT,
        "artifact_class": pa.CLASS_STEP_LOG,
        "payload_text": text,
        "material": _MATERIAL,
        "now": _NOW,
    }
    base.update(kwargs)
    return pa.retain(artifacts_dir, **base)


def _minimal_png():
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _write_file(path, data, mode=0o644):
    with open(path, "wb") as fh:
        fh.write(data)
    os.chmod(path, mode)
    return path


def _write_zip(path, members):
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in members:
            zf.writestr(name, content)
    os.chmod(path, 0o644)
    return path


def _write_duplicate_name_zip(path, name, contents):
    with zipfile.ZipFile(path, "w") as zf:
        for content in contents:
            zf.writestr(zipfile.ZipInfo(name), content)
    os.chmod(path, 0o644)
    return path


def _write_declared_oversize_zip(path):
    """Zip whose declared uncompressed size exceeds MAX_ARCHIVE_BYTES but content is tiny."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("x.txt", b"x")
    with open(path, "r+b") as fh:
        data = bytearray(fh.read())
    huge = pa.MAX_ARCHIVE_BYTES + 1
    local = data.index(b"PK\x03\x04")
    data[local + 18:local + 22] = huge.to_bytes(4, "little")
    central = data.index(b"PK\x01\x02")
    data[central + 24:central + 28] = huge.to_bytes(4, "little")
    with open(path, "wb") as fh:
        fh.write(data)
    os.chmod(path, 0o644)
    return path


def _oversize_payload_file(tmp_path, name):
    path = os.path.join(str(tmp_path), name)
    with open(path, "wb") as fh:
        fh.truncate(pa.MAX_PAYLOAD_BYTES + 1)
    os.chmod(path, 0o644)
    return path


def _run_cli(*args):
    script = os.path.join(_LIB, "pilot_artifacts.py")
    return subprocess.run(
        [sys.executable, "-B", script, *args],
        capture_output=True,
        text=True,
    )


# --- fail-closed edges --------------------------------------------------------


@pytest.mark.parametrize("slot", [None, "", "../evil", "bad slot"])
def test_edge_invalid_slot_refuses(slot):
    result = pa.retain(
        "/tmp/artifacts",
        branch=_BRANCH,
        slot=slot,
        artifact_class=pa.CLASS_STEP_LOG,
        payload_text="x",
        material=_MATERIAL,
        now=_NOW,
    )
    assert result == {"ok": False, "reason": pa.REASON_SLOT_INVALID}


@pytest.mark.parametrize("artifact_class", [None, "bogus", ""])
def test_edge_unknown_class_refuses(artifact_class):
    result = pa.retain(
        "/tmp/artifacts",
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=artifact_class,
        payload_text="x",
        material=_MATERIAL,
        now=_NOW,
    )
    assert result == {"ok": False, "reason": pa.REASON_CLASS_UNKNOWN}


@pytest.mark.parametrize("opted_in", [1, "yes"])
def test_edge_trace_opt_in_requires_identity_true(tmp_path, opted_in):
    artifacts = _artifacts_dir(tmp_path)
    zpath = os.path.join(str(tmp_path), "trace.zip")
    _write_zip(zpath, [("log.txt", "line")])
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_TRACE,
        payload_path=zpath,
        material=_MATERIAL,
        now=_NOW,
        opted_in=opted_in,
    )
    assert result["ok"] is False
    assert result["reason"] == pa.REASON_CLASS_NOT_OPTED_IN


@pytest.mark.parametrize("hours", [True, 0, -1, 1.5, "24", pa.MAX_RETENTION_HOURS + 1])
def test_edge_invalid_retention_hours_refuses(tmp_path, hours):
    artifacts = _artifacts_dir(tmp_path)
    result = _retain_step_log(artifacts, retention_hours=hours)
    assert result["ok"] is False
    assert result["reason"] == pa.REASON_RETENTION_INVALID


@pytest.mark.parametrize("material", [[], None, ["", None]])
def test_edge_invalid_material_refuses(tmp_path, material):
    artifacts = _artifacts_dir(tmp_path)
    result = _retain_step_log(artifacts, material=material)
    assert result["ok"] is False
    assert result["reason"] == pa.REASON_MATERIAL_INVALID


def test_edge_step_log_rejects_payload_path(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    p = _write_file(os.path.join(str(tmp_path), "x.txt"), b"x")
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_STEP_LOG,
        payload_text="x",
        payload_path=p,
        material=_MATERIAL,
        now=_NOW,
    )
    assert result["reason"] == pa.REASON_PAYLOAD_INVALID


def test_edge_screenshot_rejects_payload_text(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_FAILURE_SCREENSHOT,
        payload_text="not-bytes",
        material=_MATERIAL,
        now=_NOW,
        capture={"scope": pa.PERMITTED_CAPTURE_SCOPE, "sha256": "a" * 64},
    )
    assert result["reason"] == pa.REASON_PAYLOAD_INVALID


def test_edge_payload_path_missing_refuses(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_FAILURE_SCREENSHOT,
        payload_path=str(tmp_path / "missing.png"),
        material=_MATERIAL,
        now=_NOW,
        capture={"scope": pa.PERMITTED_CAPTURE_SCOPE, "sha256": "a" * 64},
    )
    assert result["reason"] == pa.REASON_PAYLOAD_UNREADABLE


def test_edge_payload_path_directory_refuses(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    dir_path = os.path.join(str(tmp_path), "adir")
    os.makedirs(dir_path)
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_FAILURE_SCREENSHOT,
        payload_path=dir_path,
        material=_MATERIAL,
        now=_NOW,
        capture={"scope": pa.PERMITTED_CAPTURE_SCOPE, "sha256": "a" * 64},
    )
    assert result["reason"] == pa.REASON_PAYLOAD_UNREADABLE


def test_edge_payload_path_symlink_refuses(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    target = _write_file(os.path.join(str(tmp_path), "real.png"), _minimal_png())
    link = os.path.join(str(tmp_path), "link.png")
    os.symlink(target, link)
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_FAILURE_SCREENSHOT,
        payload_path=link,
        material=_MATERIAL,
        now=_NOW,
        capture={"scope": pa.PERMITTED_CAPTURE_SCOPE,
                  "sha256": hashlib.sha256(_minimal_png()).hexdigest()},
    )
    assert result["reason"] == pa.REASON_PAYLOAD_UNREADABLE


def test_edge_screenshot_digest_mismatch_refuses(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    png = _write_file(os.path.join(str(tmp_path), "shot.png"), _minimal_png())
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_FAILURE_SCREENSHOT,
        payload_path=png,
        material=_MATERIAL,
        now=_NOW,
        capture={"scope": pa.PERMITTED_CAPTURE_SCOPE, "sha256": "0" * 64},
    )
    assert result["reason"] == pa.REASON_CAPTURE_RECEIPT_INVALID
    key_dir = os.path.join(artifacts, store.artifact_key(_BRANCH, _SLOT), pa.CLASS_FAILURE_SCREENSHOT)
    assert not os.path.exists(key_dir)


def test_edge_screenshot_zip_payload_format_invalid(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    zpath = _write_zip(os.path.join(str(tmp_path), "not-image.zip"), [("x", "y")])
    digest = hashlib.sha256(open(zpath, "rb").read()).hexdigest()
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_FAILURE_SCREENSHOT,
        payload_path=zpath,
        material=_MATERIAL,
        now=_NOW,
        capture={"scope": pa.PERMITTED_CAPTURE_SCOPE, "sha256": digest},
    )
    assert result["reason"] == pa.REASON_PAYLOAD_FORMAT_INVALID


def test_edge_trace_binary_member_refuses(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    zpath = _write_zip(os.path.join(str(tmp_path), "trace.zip"), [("bin.dat", b"\xff\xfe")])
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_TRACE,
        payload_path=zpath,
        material=_MATERIAL,
        now=_NOW,
        opted_in=True,
    )
    assert result["reason"] == pa.REASON_REDACTION_UNESTABLISHED


@pytest.mark.parametrize("member", ["../escape.txt", "/abs.txt"])
def test_edge_trace_unsafe_member_name_refuses(tmp_path, member):
    artifacts = _artifacts_dir(tmp_path)
    zpath = os.path.join(str(tmp_path), "bad.zip")
    with zipfile.ZipFile(zpath, "w") as zf:
        info = zipfile.ZipInfo(member)
        zf.writestr(info, "text")
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_TRACE,
        payload_path=zpath,
        material=_MATERIAL,
        now=_NOW,
        opted_in=True,
    )
    assert result["reason"] == pa.REASON_PAYLOAD_FORMAT_INVALID


def test_edge_trace_declared_oversize_refuses_without_expanding(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    zpath = os.path.join(str(tmp_path), "huge.zip")
    with zipfile.ZipFile(zpath, "w") as zf:
        for i in range(pa.MAX_ARCHIVE_MEMBERS + 1):
            zf.writestr("member-%d.txt" % i, "x")
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_TRACE,
        payload_path=zpath,
        material=_MATERIAL,
        now=_NOW,
        opted_in=True,
    )
    assert result["reason"] == pa.REASON_PAYLOAD_OVERSIZE


def test_edge_trace_byte_budget_declared_oversize_refuses_without_expanding(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    zpath = _write_declared_oversize_zip(os.path.join(str(tmp_path), "budget.zip"))
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_TRACE,
        payload_path=zpath,
        material=_MATERIAL,
        now=_NOW,
        opted_in=True,
    )
    assert result["reason"] == pa.REASON_PAYLOAD_OVERSIZE
    assert os.path.getsize(zpath) < 1024


def test_edge_loose_artifacts_dir_permissions_refused(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    os.chmod(artifacts, 0o755)
    result = _retain_step_log(artifacts)
    assert result["reason"] == pa.REASON_STORE_PERMISSIONS_UNSAFE
    sweep = pa.sweep(artifacts, now=_NOW)
    assert sweep["reason"] == pa.REASON_STORE_PERMISSIONS_UNSAFE


def test_edge_symlink_artifacts_dir_refused(tmp_path):
    target = os.path.join(str(tmp_path), "real")
    os.makedirs(target, mode=0o700)
    link = os.path.join(str(tmp_path), "artifacts-link")
    os.symlink(target, link)
    result = _retain_step_log(link)
    assert result["reason"] == pa.REASON_STORE_PATH_UNSAFE


def test_edge_sidecarless_payload_swept_when_past_grace(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    key = store.artifact_key(_BRANCH, _SLOT)
    class_dir = os.path.join(artifacts, key, pa.CLASS_STEP_LOG)
    os.makedirs(class_dir, mode=0o700)
    orphan = os.path.join(class_dir, "a" * 32)
    _write_file(orphan, b"orphan", mode=0o600)
    old = time.time() - 36000
    os.utime(orphan, (old, old))
    out = pa.sweep(artifacts, now=_NOW)
    assert not os.path.exists(orphan)
    assert any(
        e["reason"] == pa.REASON_SIDECAR_UNRECOVERABLE and e["artifactId"] == "a" * 32
        for e in out["removed"]
    )


def test_edge_sidecarless_young_payload_retained_with_pending_warning(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    key = store.artifact_key(_BRANCH, _SLOT)
    class_dir = os.path.join(artifacts, key, pa.CLASS_STEP_LOG)
    os.makedirs(class_dir, mode=0o700)
    orphan = os.path.join(class_dir, "c" * 32)
    _write_file(orphan, b"young", mode=0o600)
    out = pa.sweep(artifacts, now=_NOW)
    assert os.path.exists(orphan)
    assert any(
        e["artifactId"] == "c" * 32 and e["reason"] == pa.REASON_SIDECAR_PENDING
        for e in out["warnings"]
    )
    assert any(e["artifactId"] == "c" * 32 for e in out["retained"])
    assert not any(e["artifactId"] == "c" * 32 for e in out["removed"])


def test_edge_orphan_sidecar_swept(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    key = store.artifact_key(_BRANCH, _SLOT)
    class_dir = os.path.join(artifacts, key, pa.CLASS_STEP_LOG)
    os.makedirs(class_dir, mode=0o700)
    sidecar = os.path.join(class_dir, "b" * 32 + pa.SIDECAR_SUFFIX)
    with open(sidecar, "w", encoding="utf-8") as fh:
        json.dump({"schemaVersion": 1}, fh)
    out = pa.sweep(artifacts, now=_NOW)
    assert not os.path.exists(sidecar)
    assert any(e["artifactId"] == "b" * 32 for e in out["removed"])


def test_edge_truncated_sidecar_swept(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    kept = _retain_step_log(artifacts)
    with open(kept["sidecar"], "w", encoding="utf-8") as fh:
        fh.write("{")
    out = pa.sweep(artifacts, now=_NOW)
    assert not os.path.exists(kept["path"])
    assert any(e["reason"] == pa.REASON_SIDECAR_UNRECOVERABLE for e in out["removed"])


def test_edge_missing_artifacts_dir_sweep_ok(tmp_path):
    missing = os.path.join(str(tmp_path), "nope")
    out = pa.sweep(missing, now=_NOW)
    assert out == {"ok": True, "reason": None, "removed": [], "retained": [], "warnings": []}


def test_edge_expires_at_equal_now_removed(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    kept = _retain_step_log(artifacts, retention_hours=1)
    expires = kept["expiresAt"]
    out = pa.sweep(artifacts, now=expires)
    assert any(
        e["artifactId"] == kept["artifactId"] and e["reason"] == pa.REASON_RETENTION_EXPIRED
        for e in out["removed"]
    )


def test_edge_retain_aborts_when_sweep_refuses(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    kept = _retain_step_log(artifacts)
    os.chmod(artifacts, 0o755)
    result = _retain_step_log(artifacts, payload_text="another")
    assert result["reason"] == pa.REASON_STORE_PERMISSIONS_UNSAFE
    assert os.path.exists(kept["path"])


def test_edge_embedded_material_substring_refuses(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    result = _retain_step_log(artifacts, text="prefix %s suffix" % _MATERIAL[0])
    assert result["reason"] == pa.REASON_REDACTION_UNESTABLISHED


# --- happy paths --------------------------------------------------------------


def test_step_log_happy_path_modes_and_sidecar(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    result = _retain_step_log(artifacts)
    assert result["ok"] is True
    assert os.path.isfile(result["path"])
    assert os.path.isfile(result["sidecar"])
    assert stat.S_IMODE(os.stat(result["path"]).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(result["sidecar"]).st_mode) == 0o600
    with open(result["sidecar"], encoding="utf-8") as fh:
        meta = json.load(fh)
    assert meta["class"] == pa.CLASS_STEP_LOG
    assert meta["basis"] == pa.BASIS_SCRUBBED
    assert meta["artifactKey"] == store.artifact_key(_BRANCH, _SLOT)


def test_screenshot_happy_path(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    png = _write_file(os.path.join(str(tmp_path), "shot.png"), _minimal_png())
    digest = hashlib.sha256(_minimal_png()).hexdigest()
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_FAILURE_SCREENSHOT,
        payload_path=png,
        material=_MATERIAL,
        now=_NOW,
        capture={"scope": pa.PERMITTED_CAPTURE_SCOPE, "sha256": digest},
    )
    assert result["ok"] is True
    assert open(result["path"], "rb").read().startswith(pa._PNG_MAGIC)


def test_trace_happy_path_scrubs_and_rewrites(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    zpath = _write_zip(os.path.join(str(tmp_path), "trace.zip"), [
        ("log.txt", "trace line one"),
    ])
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_TRACE,
        payload_path=zpath,
        material=_MATERIAL,
        now=_NOW,
        opted_in=True,
    )
    assert result["ok"] is True
    with zipfile.ZipFile(result["path"], "r") as zf:
        text = zf.read("log.txt").decode("utf-8")
    assert "trace line one" in text
    assert result["bytes"] == os.path.getsize(result["path"])


def test_payload_written_before_sidecar(tmp_path, monkeypatch):
    artifacts = _artifacts_dir(tmp_path)
    order = []
    real_atomic = __import__("store_core").atomic_write
    real_binary = pa._write_binary_atomic

    def track_binary(path, data):
        order.append(("payload", path))
        return real_binary(path, data)

    def track_atomic(path, text, tmp_prefix=".store-core."):
        order.append(("sidecar", path))
        return real_atomic(path, text, tmp_prefix=tmp_prefix)

    monkeypatch.setattr(pa, "_write_binary_atomic", track_binary)
    monkeypatch.setattr(__import__("store_core"), "atomic_write", track_atomic)
    result = _retain_step_log(artifacts)
    assert result["ok"] is True
    assert order[0][0] == "payload"
    assert order[1][0] == "sidecar"


def test_sweep_retention_expired(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    kept = _retain_step_log(artifacts, retention_hours=1)
    later = pa._add_hours_iso8601(_NOW, 2)
    out = pa.sweep(artifacts, now=later)
    assert not os.path.exists(kept["path"])
    assert any(e["reason"] == pa.REASON_RETENTION_EXPIRED for e in out["removed"])


def test_step_log_scrubbed_payload_read_back_from_disk(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    result = _retain_step_log(artifacts, text="auth header: %s" % _BEARER_SECRET)
    assert result["ok"] is True
    on_disk = open(result["path"], encoding="utf-8").read()
    assert _BEARER_SECRET not in on_disk
    assert "Bearer [REDACTED]" in on_disk


def test_screenshot_oversize_payload_refused(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    huge = _oversize_payload_file(tmp_path, "huge.png")
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_FAILURE_SCREENSHOT,
        payload_path=huge,
        material=_MATERIAL,
        now=_NOW,
        capture={"scope": pa.PERMITTED_CAPTURE_SCOPE, "sha256": "0" * 64},
    )
    assert result["reason"] == pa.REASON_PAYLOAD_OVERSIZE


def test_trace_oversize_payload_refused(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    huge = _oversize_payload_file(tmp_path, "huge.zip")
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_TRACE,
        payload_path=huge,
        material=_MATERIAL,
        now=_NOW,
        opted_in=True,
    )
    assert result["reason"] == pa.REASON_PAYLOAD_OVERSIZE


def test_trace_material_in_member_name_refuses(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    zpath = _write_zip(os.path.join(str(tmp_path), "named.zip"), [
        (_MATERIAL[0] + ".txt", "safe content"),
    ])
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_TRACE,
        payload_path=zpath,
        material=_MATERIAL,
        now=_NOW,
        opted_in=True,
    )
    assert result["reason"] == pa.REASON_REDACTION_UNESTABLISHED


def test_trace_duplicate_member_names_retain_both_contents(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    zpath = _write_duplicate_name_zip(
        os.path.join(str(tmp_path), "dup.zip"), "dup.txt", [b"FIRST", b"SECOND"])
    result = pa.retain(
        artifacts,
        branch=_BRANCH,
        slot=_SLOT,
        artifact_class=pa.CLASS_TRACE,
        payload_path=zpath,
        material=_MATERIAL,
        now=_NOW,
        opted_in=True,
    )
    assert result["ok"] is True
    with zipfile.ZipFile(result["path"], "r") as zf:
        bodies = [zf.read(info) for info in zf.infolist()]
    assert b"FIRST" in bodies
    assert b"SECOND" in bodies


def test_sweep_unknown_sidecar_schema_retains_with_warning(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    kept = _retain_step_log(artifacts)
    with open(kept["sidecar"], encoding="utf-8") as fh:
        meta = json.load(fh)
    meta["schemaVersion"] = 2
    with open(kept["sidecar"], "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    out = pa.sweep(artifacts, now=_NOW)
    assert os.path.exists(kept["path"])
    assert os.path.exists(kept["sidecar"])
    assert any(
        e["artifactId"] == kept["artifactId"]
        and e["reason"] == pa.REASON_SIDECAR_SCHEMA_UNKNOWN
        for e in out["warnings"]
    )
    assert any(e["artifactId"] == kept["artifactId"] for e in out["retained"])


def test_sweep_fractional_expires_at_compares_by_instant(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    kept = _retain_step_log(artifacts, retention_hours=24)
    with open(kept["sidecar"], encoding="utf-8") as fh:
        meta = json.load(fh)
    meta["expiresAt"] = "2026-08-07T12:00:00.123456Z"
    with open(kept["sidecar"], "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    out = pa.sweep(artifacts, now="2026-08-07T12:00:00.500000Z")
    assert any(
        e["artifactId"] == kept["artifactId"] and e["reason"] == pa.REASON_RETENTION_EXPIRED
        for e in out["removed"]
    )


def test_sweep_listdir_failure_warns(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    key = store.artifact_key(_BRANCH, _SLOT)
    class_dir = os.path.join(artifacts, key, pa.CLASS_STEP_LOG)
    os.makedirs(class_dir, mode=0o700)
    os.chmod(class_dir, 0o000)
    try:
        out = pa.sweep(artifacts, now=_NOW)
    finally:
        os.chmod(class_dir, 0o700)
    assert any(
        e["artifactKey"] == key and e["class"] == pa.CLASS_STEP_LOG
        and e["reason"] == pa.REASON_SWEEP_FAILED
        for e in out["warnings"]
    )


def test_sweep_failed_unlink_warns_and_retains_not_removed(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    kept = _retain_step_log(artifacts, retention_hours=1)
    later = pa._add_hours_iso8601(_NOW, 2)
    class_dir = os.path.dirname(kept["path"])
    os.chmod(class_dir, 0o500)
    try:
        out = pa.sweep(artifacts, now=later)
    finally:
        os.chmod(class_dir, 0o700)
    assert os.path.exists(kept["path"])
    assert any(
        e["artifactId"] == kept["artifactId"] and e["reason"] == pa.REASON_SWEEP_FAILED
        for e in out["warnings"]
    )
    assert any(e["artifactId"] == kept["artifactId"] for e in out["retained"])
    assert not any(e["artifactId"] == kept["artifactId"] for e in out["removed"])


def test_retain_scoped_sweep_leaves_other_key_untouched(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    other_key = store.artifact_key("other-branch", "other")
    other_dir = os.path.join(artifacts, other_key, pa.CLASS_STEP_LOG)
    os.makedirs(other_dir, mode=0o700)
    orphan = os.path.join(other_dir, "d" * 32)
    _write_file(orphan, b"other", mode=0o600)
    old = time.time() - 36000
    os.utime(orphan, (old, old))
    _retain_step_log(artifacts)
    assert os.path.exists(orphan)
    key_dir = os.path.join(artifacts, store.artifact_key(_BRANCH, _SLOT), pa.CLASS_STEP_LOG)
    assert os.path.isdir(key_dir)


def test_cli_retain_success_exit_zero(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    mat_file = os.path.join(str(tmp_path), "mat.json")
    with open(mat_file, "w", encoding="utf-8") as fh:
        json.dump(_MATERIAL, fh)
    text_file = os.path.join(str(tmp_path), "log.txt")
    with open(text_file, "w", encoding="utf-8") as fh:
        fh.write("clean step")
    out = _run_cli(
        "retain",
        "--artifacts-dir", artifacts,
        "--branch", _BRANCH,
        "--slot", _SLOT,
        "--class", pa.CLASS_STEP_LOG,
        "--material-file", mat_file,
        "--now", _NOW,
        "--payload-text-file", text_file,
    )
    assert out.returncode == 0
    result = json.loads(out.stdout)
    assert result["ok"] is True


def test_cli_retain_refusal_exit_one(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    mat_file = os.path.join(str(tmp_path), "mat.json")
    with open(mat_file, "w", encoding="utf-8") as fh:
        json.dump(_MATERIAL, fh)
    text_file = os.path.join(str(tmp_path), "log.txt")
    with open(text_file, "w", encoding="utf-8") as fh:
        fh.write("has %s" % _MATERIAL[0])
    out = _run_cli(
        "retain",
        "--artifacts-dir", artifacts,
        "--branch", _BRANCH,
        "--slot", _SLOT,
        "--class", pa.CLASS_STEP_LOG,
        "--material-file", mat_file,
        "--now", _NOW,
        "--payload-text-file", text_file,
    )
    assert out.returncode == 1
    result = json.loads(out.stdout)
    assert result["ok"] is False
    assert result["reason"] == pa.REASON_REDACTION_UNESTABLISHED


def test_cli_usage_error_exit_two():
    out = _run_cli("retain")
    assert out.returncode == 2


def test_cli_sweep_success_exit_zero(tmp_path):
    artifacts = _artifacts_dir(tmp_path)
    out = _run_cli("sweep", "--artifacts-dir", artifacts, "--now", _NOW)
    assert out.returncode == 0
    result = json.loads(out.stdout)
    assert result["ok"] is True
