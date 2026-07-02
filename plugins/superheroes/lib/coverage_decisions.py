#!/usr/bin/env python3
"""Record visible, challengeable review coverage decisions."""
import argparse
import hashlib
import json
import os
import re
import tempfile

SECTION = "## Review coverage decisions"


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _atomic_write(path, text):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".coverage-decisions-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        return {"ok": True}
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return {"ok": False, "reason": "replace-failed", "detail": str(exc)}


def _entry(decision):
    did = decision.get("id") or "RCD-unknown"
    kind = decision.get("kind") or "coverage"
    key = decision.get("classKey") or ""
    text = decision.get("text") or ""
    source = decision.get("sourceRound")
    payload = json.dumps(decision, sort_keys=True)
    return f"- **{did}** ({kind}; round {source}; class `{key}`): {text}\n  `review-coverage-decision-json:{payload}`\n"


def _insert_section_entry(original, entry):
    """Append entry inside ## Review coverage decisions, before the next ## heading."""
    lines = original.split("\n")
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == SECTION)
    except StopIteration:
        return original.rstrip() + "\n\n" + SECTION + "\n\n" + entry
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    body = "\n".join(lines[start + 1:end]).rstrip()
    if entry.strip() in body:
        return original
    new_section = SECTION + "\n\n" + (body + "\n" if body else "") + entry.rstrip("\n")
    return "\n".join(lines[:start] + [new_section] + lines[end:]).rstrip() + "\n"


def _with_fence(decision, run_id, lease=None):
    if not run_id:
        return None
    out = dict(decision)
    out["runId"] = run_id
    if lease:
        out["lease"] = lease
    return out


def record_doc_decision(path, decision, expected_hash=None, run_id=None, lease=None):
    decision = _with_fence(decision, run_id, lease)
    if decision is None:
        return {"ok": False, "reason": "missing-run-id"}
    with open(path, encoding="utf-8") as fh:
        original = fh.read()
    if expected_hash and content_hash(original) != expected_hash:
        return {"ok": False, "reason": "stale"}
    entry = _entry(decision)
    if SECTION in original:
        updated = _insert_section_entry(original, entry)
    else:
        updated = original.rstrip() + "\n\n" + SECTION + "\n\n" + entry
    result = _atomic_write(path, updated)
    if not result["ok"]:
        return result
    return {"ok": True, "id": decision.get("id")}


def record_code_decision(path, decision, expected_hash=None, run_id=None, lease=None):
    decision = _with_fence(decision, run_id, lease)
    if decision is None:
        return {"ok": False, "reason": "missing-run-id"}
    try:
        with open(path, encoding="utf-8") as fh:
            original = fh.read()
        if expected_hash and content_hash(original) != expected_hash:
            return {"ok": False, "reason": "stale"}
        existing = json.loads(original)
        if not isinstance(existing, list):
            existing = []
    except FileNotFoundError:
        original = ""
        if expected_hash and content_hash(original) != expected_hash:
            return {"ok": False, "reason": "stale"}
        existing = []
    except (OSError, ValueError):
        if expected_hash:
            return {"ok": False, "reason": "stale"}
        existing = []
    existing.append(decision)
    result = _atomic_write(path, json.dumps(existing, indent=2) + "\n")
    if not result["ok"]:
        return result
    return {"ok": True, "id": decision.get("id")}


# the doc-section parse twins the append format _entry() writes (and the retired JS
# parseDocCoverageDecisions): a JSON trailer line when present, else the markdown line shape.
_DOC_JSON_RE = re.compile(r"review-coverage-decision-json:(\{.*\})`?$")
_DOC_LINE_RE = re.compile(r"^- \*\*([^*]+)\*\* .*class `([^`]+)`\): (.*)$")


def parse_doc_decisions(text):
    out = []
    in_section = False
    for line in str(text or "").split("\n"):
        if re.match(r"^##\s+", line):
            in_section = line.strip() == SECTION
        if not in_section:
            continue
        m = _DOC_JSON_RE.search(line)
        if m:
            try:
                out.append(json.loads(m.group(1)))
                continue
            except ValueError:
                pass
        m = _DOC_LINE_RE.match(line)
        if m:
            out.append({"id": m.group(1), "classKey": m.group(2), "text": m.group(3)})
    return out


def load_decisions(path, mode):
    """The loop's coverage read, computed entirely PYTHON-SIDE (decisions + the fence hash of
    the exact on-disk bytes). In the Workflow sandbox a raw courier read of a missing/odd file
    answers PROSE (live 2026-07-02) — hashing or parsing that prose runtime-side poisons the
    fence / the decisions. Missing file -> ok with no decisions (the normal first-round case);
    corrupt/unreadable -> fail closed."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except FileNotFoundError:
        return {"ok": True, "decisions": [], "contentHash": content_hash("")}
    except OSError as exc:
        return {"ok": False, "state": "unreadable", "reason": str(exc)}
    if mode == "doc":
        return {"ok": True, "decisions": parse_doc_decisions(text), "contentHash": content_hash(text)}
    try:
        decisions = json.loads(text or "[]")
    except ValueError:
        return {"ok": False, "state": "corrupt"}
    if not isinstance(decisions, list):
        return {"ok": False, "state": "corrupt"}
    return {"ok": True, "decisions": decisions, "contentHash": content_hash(text)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["record-doc", "record-code", "load"])
    parser.add_argument("--path", required=True)
    parser.add_argument("--decision-json")
    parser.add_argument("--mode", choices=["doc", "code"], default="code")
    parser.add_argument("--expected-hash")
    parser.add_argument("--run-id")
    parser.add_argument("--lease")
    args = parser.parse_args(argv)
    if args.cmd == "load":
        result = load_decisions(args.path, args.mode)
        print(json.dumps(result))
        return 0 if result.get("ok") else 1
    if args.decision_json is None or not args.run_id:
        print(json.dumps({"ok": False, "reason": "missing-decision-or-run-id"}))
        return 1
    decision = json.loads(args.decision_json)
    if args.cmd == "record-doc":
        result = record_doc_decision(args.path, decision, expected_hash=args.expected_hash, run_id=args.run_id, lease=args.lease)
    else:
        result = record_code_decision(args.path, decision, expected_hash=args.expected_hash, run_id=args.run_id, lease=args.lease)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
