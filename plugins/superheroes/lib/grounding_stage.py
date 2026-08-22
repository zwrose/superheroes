#!/usr/bin/env python3
"""Grounding-stage PR-body staging (#609).

Stages the PR body as a seat-readable input with content-derived tokens, region detection,
and claim enumeration. stdlib only."""
import argparse
import hashlib
import json
import os
import re
import sys
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import store_core  # noqa: E402
import stub_markers  # noqa: E402

STAGE_SCHEMA = "grounding-stage/1"
GROUNDING_DIR = "grounding"
STAGE_MANIFEST = "stage.json"
PR_BODY_STAGED = "pr-body.md"

_STUB_LABEL = "STUB"

REGION_MARKERS = {
    "dod-table": "<!-- superheroes:dod-table -->",
    "build-record": "<!-- superheroes:build-record -->",
    "degradations": "<!-- superheroes:degradations -->",
    "advisor-vet": "<!-- superheroes:advisor-vet -->",
}

VALID_VERDICTS = frozenset({"CONFIRMED", "PLAUSIBLE", "REFUTED"})

REFUSAL_REASONS = frozenset({
    "meta-unreadable",
    "meta-mode-unknown",
    "pr-json-unreadable",
    "pr-json-unparseable",
    "pr-body-absent",
    "pr-body-empty",
    "stage-unwritable",
    "stage-readback-mismatch",
    "stage-manifest-missing",
    "stage-manifest-invalid",
    "staged-file-unreadable",
    "staged-file-hash-mismatch",
    "attest-result-unreadable",
    "attest-token-missing",
    "attest-token-mismatch",
    "attest-claim-unanswered",
    "attest-verdict-out-of-enum",
})


def _iso8601_utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text):
    return _sha256_bytes(text.encode("utf-8"))


def _refuse(reason, detail=None):
    # axis: unproven staged input must refuse, never return a usable result.
    if reason not in REFUSAL_REASONS:
        raise ValueError("unregistered refusal reason: %r" % reason)
    return {"ok": False, "signal": "cannot-certify", "reason": reason, "detail": detail}


def _emit(result):
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")


def _read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _read_json(path):
    text = _read_text(path)
    return json.loads(text)


def _stage_token(body):
    digest = hashlib.sha256(body.encode("utf-8")).digest()
    groups = []
    for i in range(4):
        chunk = int.from_bytes(digest[i * 4:(i + 1) * 4], "big") % 10000
        groups.append("%04d" % chunk)
    return "-".join(groups)


def _claim_id(kind, text):
    short = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return "%s-%s" % (kind, short)


def _read_meta(session_dir):
    meta_path = os.path.join(session_dir, "meta.json")
    try:
        meta = _read_json(meta_path)
    except FileNotFoundError as exc:
        return _refuse("meta-unreadable", str(exc))
    except OSError as exc:
        return _refuse("meta-unreadable", str(exc))
    except json.JSONDecodeError as exc:
        return _refuse("meta-mode-unknown", str(exc))
    if not isinstance(meta, dict):
        return _refuse("meta-mode-unknown", "meta.json root is not an object")
    mode = meta.get("mode")
    if mode not in ("pr", "branch"):
        return _refuse("meta-mode-unknown", "mode absent or unknown: %r" % mode)
    return {"ok": True, "mode": mode}


def _extract_region(body, marker):
    idx = body.find(marker)
    if idx < 0:
        return None, 0
    start = idx + len(marker)
    rest = body[start:]
    if rest.startswith("\r\n"):
        start += 2
        rest = body[start:]
    elif rest.startswith("\n"):
        start += 1
        rest = body[start:]
    next_markers = [body.find(m, start) for m in REGION_MARKERS.values() if body.find(m, start) >= 0]
    end = min(next_markers) if next_markers else len(body)
    region_text = body[start:end]
    lines = region_text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    line_count = len(lines)
    return region_text, line_count


def _parse_dod_rows(body, marker):
    region_text, _ = _extract_region(body, marker)
    if region_text is None:
        return []
    rows = []
    for line in region_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if re.match(r"^\|[-:\s|]+\|$", stripped):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not any(cells):
            continue
        rows.append("|".join(cells))
    return rows


def _parse_degradation_bullets(body, marker):
    region_text, _ = _extract_region(body, marker)
    if region_text is None:
        return []
    bullets = []
    for line in region_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
        elif stripped.startswith("* "):
            bullets.append(stripped[2:].strip())
    return bullets


def _dod_row_verifiability(row_text):
    lowered = row_text.lower()
    if "deferred" in lowered:
        return "external"
    if "done" in lowered:
        return "repo"
    if re.search(r"#\d+", row_text):
        return "external"
    return "repo"


def _enumerate_claims(body, regions):
    claims = []
    for name, info in regions.items():
        present = info["present"]
        text = "region %s present=%s" % (name, present)
        claims.append({
            "claimId": _claim_id("region-present-%s" % name, text),
            "kind": "region-present",
            "text": text,
            "verifiability": "repo",
        })
    if regions.get("dod-table", {}).get("present"):
        for row in _parse_dod_rows(body, REGION_MARKERS["dod-table"]):
            claims.append({
                "claimId": _claim_id("dod-row", row),
                "kind": "dod-row",
                "text": row,
                "verifiability": _dod_row_verifiability(row),
            })
    if regions.get("degradations", {}).get("present"):
        for bullet in _parse_degradation_bullets(body, REGION_MARKERS["degradations"]):
            claims.append({
                "claimId": _claim_id("degradation", bullet),
                "kind": "degradation",
                "text": bullet,
                "verifiability": "repo",
            })
    for marker in stub_markers.find_markers(body):
        text = "%s(#%d): %s" % (_STUB_LABEL, marker["issue"], marker["description"])
        claims.append({
            "claimId": _claim_id("stub-marker", text),
            "kind": "stub-marker",
            "text": text,
            "verifiability": "repo",
        })
    return claims


def _detect_regions(body):
    regions = []
    for name, marker in REGION_MARKERS.items():
        region_text, line_count = _extract_region(body, marker)
        present = region_text is not None
        regions.append({
            "name": name,
            "present": present,
            "lines": line_count if present else None,
        })
    return regions


def _pr_body_header(token):
    return (
        "<!--\n"
        "stageToken: %s\n"
        "Echo this token exactly in a verdict row with id stage-token:%s.\n"
        "-->\n"
        % (token, token)
    )


def _grounding_dir(session_dir):
    return os.path.join(os.path.abspath(session_dir), GROUNDING_DIR)


def _atomic_write_text(path, text, tmp_prefix=".grounding-stage-"):
    store_core.atomic_write(path, text, tmp_prefix=tmp_prefix)


def _verify_written_file(path, expected_text):
    try:
        on_disk = _read_text(path)
    except OSError as exc:
        return _refuse("stage-readback-mismatch", "read-back failed: %s" % exc)
    if on_disk != expected_text:
        return _refuse("stage-readback-mismatch", "content mismatch for %s" % path)
    expected_hash = _sha256_text(expected_text)
    actual_hash = _sha256_text(on_disk)
    if actual_hash != expected_hash:
        return _refuse("stage-readback-mismatch", "hash mismatch for %s" % path)
    return {"ok": True, "sha256": actual_hash, "bytes": len(on_disk.encode("utf-8"))}


def stage(session_dir):
    meta = _read_meta(session_dir)
    if not meta.get("ok"):
        return meta
    if meta["mode"] == "branch":
        return {"ok": True, "applicable": False, "reason": "branch-mode-has-no-pr-body"}
    pr_path = os.path.join(session_dir, "pr.json")
    try:
        pr_data = _read_json(pr_path)
    except FileNotFoundError as exc:
        return _refuse("pr-json-unreadable", str(exc))
    except OSError as exc:
        return _refuse("pr-json-unreadable", str(exc))
    except json.JSONDecodeError as exc:
        return _refuse("pr-json-unparseable", str(exc))
    if not isinstance(pr_data, dict):
        return _refuse("pr-json-unparseable", "pr.json root is not an object")
    body = pr_data.get("body")
    if body is None or not isinstance(body, str):
        return _refuse("pr-body-absent", "body absent or not a string")
    if not body.strip():
        return _refuse("pr-body-empty", "body empty or whitespace-only")
    token = _stage_token(body)
    regions = _detect_regions(body)
    region_map = {r["name"]: r for r in regions}
    claims = _enumerate_claims(body, region_map)
    staged_body = _pr_body_header(token) + body
    grounding = _grounding_dir(session_dir)
    pr_body_path = os.path.join(grounding, PR_BODY_STAGED)
    try:
        os.makedirs(grounding, exist_ok=True)
        _atomic_write_text(pr_body_path, staged_body)
    except OSError as exc:
        return _refuse("stage-unwritable", str(exc))
    verify = _verify_written_file(pr_body_path, staged_body)
    if not verify.get("ok"):
        return verify
    abs_session = os.path.abspath(session_dir)
    files = [{
        "name": PR_BODY_STAGED,
        "path": os.path.abspath(pr_body_path),
        "sha256": verify["sha256"],
        "bytes": verify["bytes"],
    }]
    manifest = {
        "schema": STAGE_SCHEMA,
        "mode": "pr",
        "stageToken": token,
        "stagedAt": _iso8601_utc(),
        "sessionDir": abs_session,
        "files": files,
        "regions": regions,
        "claims": claims,
    }
    manifest_path = os.path.join(grounding, STAGE_MANIFEST)
    manifest_text = json.dumps(manifest, sort_keys=True) + "\n"
    try:
        _atomic_write_text(manifest_path, manifest_text)
    except OSError as exc:
        return _refuse("stage-unwritable", str(exc))
    verify_manifest = _verify_written_file(manifest_path, manifest_text)
    if not verify_manifest.get("ok"):
        return verify_manifest
    return {
        "ok": True,
        "applicable": True,
        "stageToken": token,
        "claims": claims,
        "files": files,
    }


def _load_manifest(session_dir):
    manifest_path = os.path.join(_grounding_dir(session_dir), STAGE_MANIFEST)
    if not os.path.isfile(manifest_path):
        return _refuse("stage-manifest-missing", manifest_path)
    try:
        manifest = _read_json(manifest_path)
    except OSError as exc:
        return _refuse("stage-manifest-invalid", str(exc))
    except json.JSONDecodeError as exc:
        return _refuse("stage-manifest-invalid", str(exc))
    if not isinstance(manifest, dict) or manifest.get("schema") != STAGE_SCHEMA:
        return _refuse("stage-manifest-invalid", "schema mismatch")
    return {"ok": True, "manifest": manifest}


def check(session_dir):
    meta = _read_meta(session_dir)
    if not meta.get("ok"):
        return meta
    if meta["mode"] == "branch":
        return {"ok": True, "applicable": False, "reason": "branch-mode-has-no-pr-body"}
    loaded = _load_manifest(session_dir)
    if not loaded.get("ok"):
        return loaded
    manifest = loaded["manifest"]
    for entry in manifest.get("files") or []:
        if not isinstance(entry, dict):
            return _refuse("stage-manifest-invalid", "files entry not an object")
        path = entry.get("path")
        expected_hash = entry.get("sha256")
        if not path or not expected_hash:
            return _refuse("stage-manifest-invalid", "file entry missing path or sha256")
        try:
            on_disk = _read_text(path)
        except OSError as exc:
            return _refuse("staged-file-unreadable", str(exc))
        actual_hash = _sha256_text(on_disk)
        if actual_hash != expected_hash:
            return _refuse("staged-file-hash-mismatch", path)
    repo_claims = [
        c for c in (manifest.get("claims") or [])
        if isinstance(c, dict) and c.get("verifiability") == "repo"
    ]
    return {
        "ok": True,
        "applicable": True,
        "stageToken": manifest.get("stageToken"),
        "claims": repo_claims,
        "files": manifest.get("files") or [],
    }


def _token_rows(verdicts):
    rows = []
    for row in verdicts:
        if not isinstance(row, dict):
            continue
        vid = row.get("id")
        if isinstance(vid, str) and vid.startswith("stage-token:"):
            rows.append(row)
    return rows


def attest(session_dir, result_path):
    loaded = _load_manifest(session_dir)
    if not loaded.get("ok"):
        return loaded
    manifest = loaded["manifest"]
    stage_token = manifest.get("stageToken")
    try:
        result = _read_json(result_path)
    except FileNotFoundError as exc:
        return _refuse("attest-result-unreadable", str(exc))
    except OSError as exc:
        return _refuse("attest-result-unreadable", str(exc))
    except json.JSONDecodeError as exc:
        return _refuse("attest-result-unreadable", str(exc))
    verdicts = result.get("verdicts") if isinstance(result, dict) else None
    if not isinstance(verdicts, list):
        return _refuse("attest-result-unreadable", "verdicts missing or not a list")
    token_rows = _token_rows(verdicts)
    if len(token_rows) != 1:
        return _refuse("attest-token-missing", "expected exactly one stage-token row")
    token_id = token_rows[0].get("id", "")
    if not isinstance(token_id, str) or not token_id.startswith("stage-token:"):
        return _refuse("attest-token-missing", "malformed stage-token id")
    echoed = token_id[len("stage-token:"):]
    if echoed != stage_token:
        return _refuse("attest-token-mismatch", "token %r != stage %r" % (echoed, stage_token))
    repo_claim_ids = [
        c.get("claimId") for c in (manifest.get("claims") or [])
        if isinstance(c, dict) and c.get("verifiability") == "repo" and c.get("claimId")
    ]
    verdict_by_id = {}
    for row in verdicts:
        if not isinstance(row, dict):
            continue
        vid = row.get("id")
        verdict = row.get("verdict")
        if not isinstance(vid, str):
            continue
        if vid in verdict_by_id:
            continue
        verdict_by_id[vid] = verdict
    for claim_id in repo_claim_ids:
        if claim_id not in verdict_by_id:
            return _refuse("attest-claim-unanswered", claim_id)
    refuted = []
    plausible = []
    confirmed = []
    for claim_id in repo_claim_ids:
        verdict = verdict_by_id.get(claim_id)
        if verdict not in VALID_VERDICTS:
            return _refuse("attest-verdict-out-of-enum", "%s: %r" % (claim_id, verdict))
        if verdict == "REFUTED":
            refuted.append(claim_id)
        elif verdict == "PLAUSIBLE":
            plausible.append(claim_id)
        elif verdict == "CONFIRMED":
            confirmed.append(claim_id)
    for row in verdicts:
        if not isinstance(row, dict):
            continue
        verdict = row.get("verdict")
        if verdict is not None and verdict not in VALID_VERDICTS:
            return _refuse("attest-verdict-out-of-enum", str(verdict))
    return {
        "ok": True,
        "attested": True,
        "refuted": refuted,
        "plausible": plausible,
        "confirmed": confirmed,
    }


def main(argv):
    ap = argparse.ArgumentParser(description="grounding stage PR-body staging")
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("stage")
    st.add_argument("--session-dir", required=True)
    ck = sub.add_parser("check")
    ck.add_argument("--session-dir", required=True)
    at = sub.add_parser("attest")
    at.add_argument("--session-dir", required=True)
    at.add_argument("--result-path", required=True)
    args = ap.parse_args(argv[1:])
    if args.cmd == "stage":
        result = stage(args.session_dir)
        _emit(result)
        if not result.get("ok"):
            return 1
        return 0
    if args.cmd == "check":
        result = check(args.session_dir)
        _emit(result)
        if not result.get("ok"):
            return 1
        return 0
    result = attest(args.session_dir, args.result_path)
    _emit(result)
    if not result.get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
