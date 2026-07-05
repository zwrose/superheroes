#!/usr/bin/env python3
"""Result record writer + verdict-report renderer for the acceptance harness (FR-5 / FR-6).

Two mechanical I/O surfaces the orchestrator calls once per invocation:

- `write_record(result, dest_dir)` — durably persists exactly ONE `acceptance-result.json`
  under the harness namespace. It first enforces FR-5's "all listed elements": a record
  missing any REQUIRED key is rejected with `ValueError` (the writer is the single choke-point
  so a partial record can never reach disk). The write is atomic (temp file + `os.replace`) and
  the record is stamped `schemaVersion` for forward-compat. Overwriting is not part of the
  contract — one record per invocation — the orchestrator writes it once.
- `read_record(dest_dir)` — mirrors `loop_readout`: NEVER raises. A missing / older-schema /
  corrupt record returns `None` rather than throwing, so a downstream reader (e.g. the UFR-8
  orphan-record path) can probe for a prior record without a try/except everywhere.
- `render_report(result)` — the plain-language verdict report with exactly the four FR-6
  elements: the verdict, the reason, where the record lives, and what was cleaned up / left
  behind. Appends a "spend is partial" note when `spend_partial` is true (engine-dispatched
  leaf spend is outside the sampled stream). The renderer never raises.

Privacy (NFR): the record + report are local-only artifacts under the control-plane store —
nothing here reaches the network. stdlib only.
"""
import json
import os

SCHEMA_VERSION = 1

RECORD_NAME = "acceptance-result.json"

# FR-5: every element the record MUST carry. write_record rejects a record missing any of
# these so "all listed elements" is enforced at the writer, not left to callers.
REQUIRED_KEYS = (
    "verdict",
    "reason",
    "pr_link",
    "phases",
    "spend",
    "spend_partial",
    "elapsed_sec",
    "launched_at",
    "terminated_at",
    "retried",
    "attempts",
    "cleaned_up",
    "left_behind",
)


def write_record(result, dest_dir):
    """Validate the FR-5 required elements, stamp schemaVersion, and atomically write
    exactly one acceptance-result.json into dest_dir. Returns the record path.

    Raises ValueError when result is not a dict or is missing any required element.
    """
    if not isinstance(result, dict):
        raise ValueError("acceptance result record must be a dict")
    missing = [k for k in REQUIRED_KEYS if k not in result]
    if missing:
        raise ValueError(
            "acceptance result record is missing required element(s): %s"
            % ", ".join(missing)
        )
    record = dict(result)
    record["schemaVersion"] = SCHEMA_VERSION
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, RECORD_NAME)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(record, fh, sort_keys=True, indent=2)
    os.replace(tmp, path)
    return path


def read_record(dest_dir):
    """Read the record from dest_dir. Returns the dict only when its schemaVersion matches
    SCHEMA_VERSION; a missing / older / corrupt record returns None. Never raises."""
    path = os.path.join(dest_dir, RECORD_NAME)
    try:
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("schemaVersion") != SCHEMA_VERSION:
        return None
    return record


def render_report(result):
    """Emit the four FR-6 elements as plain text; append a partial-spend note when flagged.
    Never raises — a non-dict result is reported as an unreadable record."""
    if not isinstance(result, dict):
        return (
            "## Acceptance harness — unreadable result\n\n"
            "(no result record was provided)\n"
        )

    verdict = result.get("verdict", "unknown")
    reason = result.get("reason", "")
    record_path = result.get("record_path") or result.get("recordPath")

    lines = ["## Acceptance harness — verdict: %s" % verdict, ""]
    if reason:
        lines += ["Reason: %s" % reason, ""]

    if record_path:
        lines += ["Record: the durable result record lives at %s" % record_path, ""]
    else:
        lines += [
            "Record: the durable result record (%s) lives in the harness namespace under "
            "the control-plane store." % RECORD_NAME,
            "",
        ]
    orphan_record_path = result.get("orphan_record_path") or result.get("orphanRecordPath")
    if orphan_record_path:
        lines += [
            "Reclaimed prior-run orphan record: %s" % orphan_record_path,
            "",
        ]

    # #235 pre-release gate: name WHICH spine this verdict validated, so a pre-release pass
    # is attributable to the exact bundle it ran (present only on a `--spine-lib` run).
    provenance = result.get("spine_provenance")
    if isinstance(provenance, dict):
        lines += [
            "### Spine under test",
            "- lib path: %s" % (provenance.get("lib_path") or "(unknown)"),
            "- bundle SHA-256: %s" % (provenance.get("bundle_sha256") or "(unreadable)"),
            "- version.txt: %s" % (provenance.get("version") or "(none)"),
            "",
        ]

    cleaned = result.get("cleaned_up") or []
    left = result.get("left_behind") or []
    lines.append("### Cleaned up")
    lines += (["- %s" % c for c in cleaned] if cleaned else ["- (nothing)"])
    lines.append("")
    lines.append("### Left behind")
    lines += (["- %s" % l for l in left] if left else ["- (nothing)"])
    lines.append("")

    if result.get("spend_partial"):
        lines += [
            "> Note: spend is partial — an external engine handled at least one leaf, so its "
            "spend is outside the sampled stream and not reflected in the reported total.",
            "",
        ]

    return "\n".join(lines)
