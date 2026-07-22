"""Test-only helpers for Guardian lib tests — NOT shipped to production."""
import json
import os
import subprocess

import core_md as cm
import guardian_lens as gl
import mode_registry as mr
import store_core as sc


class FixtureLens:
    """Parameterizable test lens implementing the full Guardian lens protocol."""

    def __init__(
        self,
        name="fixture",
        collector_version="0.0.0-test",
        *,
        emit_red_line=False,
        emit_normal=False,
        digest=None,
        diff_new=None,
        diff_worsened=None,
        diff_resolved=None,
        required_facts=(),
        metric=1,
        candidate_fields=None,
        collect_status=None,
        collect_reason=None,
        collect_raises=None,
    ):
        self.name = name
        self.collector_version = collector_version
        self.cost = {"collectorSeconds": 0.01, "note": "test fixture"}
        self.required_facts = tuple(required_facts)
        self.validation_guidance = "Validate fixture candidates against repo conventions."
        self.consequence_template = "Describe the consequence in plain language."
        self._emit_red_line = emit_red_line
        self._emit_normal = emit_normal
        self._digest = digest if digest is not None else {"v": 1}
        self._diff_new = diff_new if diff_new is not None else []
        self._diff_worsened = diff_worsened if diff_worsened is not None else []
        self._diff_resolved = diff_resolved if diff_resolved is not None else []
        self._metric = metric
        self._candidate_fields = dict(candidate_fields or {})
        self._collect_status = collect_status
        self._collect_reason = collect_reason
        self._collect_raises = collect_raises
        self.last_prev_digest = object()

    def collect(self, ctx):
        self.last_prev_digest = ctx.get("prevDigest")
        if self._collect_raises is not None:
            raise self._collect_raises
        candidates = []
        if self._emit_red_line:
            cand = {
                "id": "%s:red-line" % self.name,
                "complexity": gl.RED_LINE_THRESHOLDS["complexity"],
                "metric": self._metric,
            }
            cand.update(self._candidate_fields)
            candidates.append(cand)
        if self._emit_normal:
            cand = {
                "id": "%s:normal" % self.name,
                "complexity": 5,
                "metric": self._metric,
            }
            cand.update(self._candidate_fields)
            candidates.append(cand)
        out = {"candidates": candidates, "digest": self._digest}
        if self._collect_status is not None:
            out["status"] = self._collect_status
            if self._collect_reason is not None:
                out["reason"] = self._collect_reason
        return out

    def diff(self, prev_digest, cur_digest):
        return {
            "new": list(self._diff_new),
            "worsened": list(self._diff_worsened),
            "resolved": list(self._diff_resolved),
        }

    def red_lines(self, candidates):
        out = []
        for c in candidates:
            if c.get("complexity", 0) >= gl.RED_LINE_THRESHOLDS["complexity"]:
                out.append({
                    "kind": "new-high-complexity",
                    "id": c["id"],
                    "detail": "complexity=%d" % c["complexity"],
                })
            elif c.get("cloneLines", 0) >= gl.RED_LINE_THRESHOLDS["cloneLines"]:
                out.append({
                    "kind": "large-fresh-clone",
                    "id": c["id"],
                    "detail": "cloneLines=%d" % c["cloneLines"],
                })
        return out

    def degrade(self, reason):
        return {"lens": self.name, "degraded": True, "reason": reason}


def init_calibrated_repo(tmp_path, *, verify_command="true", stack_tags=None, remote=None):
    """Git-init a repo and write in-repo core.md calibration."""
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    if remote:
        subprocess.run(
            ["git", "-C", str(tmp_path), "remote", "add", "origin", remote], check=True)
    cal_dir = tmp_path / ".claude" / "superheroes"
    cal_dir.mkdir(parents=True)
    core = cal_dir / "core.md"
    core.write_text(cm.render_core(
        {
            "verifyCommand": verify_command,
            "stackTags": stack_tags or [],
            "threatModel": "test",
            "patterns": "",
        },
        "confirmed", "2026-01-01", "2026-01-01"))
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path),
         "-c", "user.email=guardian@test.local", "-c", "user.name=guardian-test",
         "commit", "-q", "-m", "init"], check=True)
    return str(tmp_path)


def write_guardian_layer(tmp_path, config_block=None):
    """Write guardian.md with an optional guardian-config json block."""
    layer = tmp_path / ".claude" / "superheroes" / "guardian.md"
    layer.parent.mkdir(parents=True, exist_ok=True)
    body = "<!-- guardian: schemaVersion=1 status=confirmed -->\n\n"
    if config_block is not None:
        body += "```json guardian-config\n%s\n```\n" % json.dumps(config_block, indent=2)
    layer.write_text(body)
    return str(layer)


def write_ledger(tmp_path, records, schema_version=1, root=None):
    """Write ledger.md with a guardian-ledger fenced block."""
    import guardian_store as gs
    cwd = str(tmp_path)
    text = (
        "# Guardian ledger\n\n"
        "```json %s\n%s\n```\n"
        % (gs.LEDGER_FENCE, json.dumps({"schemaVersion": schema_version, "records": records},
                                       indent=2))
    )
    sc.atomic_write(gs.ledger_path(cwd, root), text)
    return gs.ledger_path(cwd, root)


def benched_fixture_ledger(n_against=10, sweeps=3, lens="fixture"):
    """Enough adjudicated-against records to bench `lens` under report-card defaults."""
    records = []
    for i in range(n_against):
        records.append({
            "id": "%s:tool:loc-%d" % (lens, i),
            "disposition": "triaged-out",
            "date": "2026-07-01",
            "issue": None,
            "metricAtDisposition": None,
            "reason": None,
            "reraiseWhen": None,
            "adjudicatedIn": "s%d" % (i % sweeps),
        })
    return records


def ensure_store(cwd, root):
    """Ensure project store exists and return store root path."""
    mr.ensure_project_store(cwd, root=root)
    return root


def funnel_conserved(bundle):
    """raised == malformed + killed* + tracked + surfaced (match notes are breadcrumbs)."""
    funnel = bundle["funnel"]
    raised = sum(funnel["raised"].values())
    return raised == (
        len(funnel.get("malformed") or [])
        + len(funnel.get("killedByDrift") or [])
        + len(funnel.get("killedByLedger") or [])
        + len(funnel.get("killedByBench") or [])
        + len(funnel.get("trackedFiled") or [])
        + len(bundle.get("surfaced") or [])
    )
