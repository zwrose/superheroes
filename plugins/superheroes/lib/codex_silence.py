"""#2370: the one silence predicate, and the read-only sample extractor built on it.

One function decides "this attempt is silent with no command in flight": `silent_and_idle`. The
offline extractor in this module (`profile_run`, `sample`) and the live watchdog (a later order) both
call it. Silence means neither stdout nor stderr grew. "No command in flight" means no codex action
item is open in the stdout stream. A stream whose state cannot be read is `unknown`, and `unknown` is
never idle.

The foreign contract (codex-cli 0.166.0 `codex exec --json`, measured): stdout is one JSON object per
line with no timestamps; item events look like {"type": "item.started" | "item.completed",
"item": {"id": "...", "type": "...", ...}}. The action item types are
`engine_adapter._CODEX_ACTION_ITEM_TYPES`, imported, not copied.

The runner's heartbeat file has one JSON line per 10 s per attempt:
{"alive": true, "attempt": 1, "elapsed_s": 10.0, "stdout_bytes": 10014, "stderr_bytes": 0}.
That is the timing resolution of everything measured here (HEARTBEAT_RESOLUTION_SECONDS).

This module only reads. It never writes and never spawns.

CLI: python3 -B codex_silence.py sample <path> [<path> ...]
"""
import json
import math
import os
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import engine_adapter  # noqa: E402  the one home of the action item types

FEED_CHUNK_BYTES = 262144
MAX_PARTIAL_LINE_BYTES = 1048576
OVERLONG_HEAD_BYTES = 4096  # same keep size as engine_adapter._CMD_HEAD_KEEP
HEARTBEAT_RESOLUTION_SECONDS = 10
HEARTBEAT_GAP_LIMIT_SECONDS = 3 * HEARTBEAT_RESOLUTION_SECONDS

SCHEMA = "codex-silence-sample/1"
JOURNAL_NAME = "journal.jsonl"
JOURNAL_ROOT_POINTER = "journal-root.txt"
PROGRESS_NAME = "progress.jsonl"

STATE_IDLE = "idle"
STATE_BUSY = "busy"
STATE_UNKNOWN = "unknown"

OUTCOMES = ("answered", "hit-bound", "silence-watchdog", "other")

# An over-long line is classified by its head with anchored prefix matches, never a search: the event
# type, then (for an item event) the item id and item type, which codex writes before the payload.
_NO_EFFECT = ()
_EVENT_HEAD_RE = re.compile(rb'\s*\{"type":\s*"([^"\\]*)"')
_ITEM_HEAD_RE = re.compile(rb',\s*"item":\s*\{"id":\s*"([^"\\]*)",\s*"type":\s*"([^"\\]*)"')


def _classify_head(head):
    """None when the head matches no recognized prefix; () when it is recognized and changes nothing;
    else (kind, item_id) for an action item event."""
    event = _EVENT_HEAD_RE.match(head)
    if event is None:
        return None
    try:
        kind = event.group(1).decode("utf-8")
    except UnicodeDecodeError:
        return None
    if kind not in ("item.started", "item.completed"):
        return _NO_EFFECT
    item = _ITEM_HEAD_RE.match(head, event.end())
    if item is None:
        return None
    try:
        item_id = item.group(1).decode("utf-8")
        item_type = item.group(2).decode("utf-8")
    except UnicodeDecodeError:
        return None
    if item_type not in engine_adapter._CODEX_ACTION_ITEM_TYPES:
        return _NO_EFFECT
    return (kind, item_id)


class StreamTracker:
    """Reads a codex `--json` stdout stream a chunk at a time and tracks open action items.

    `state` is "idle" (no open action item), "busy" (one or more open) or "unknown". `unknown` is
    sticky when a non-empty line is not a JSON object, or when a line longer than
    MAX_PARTIAL_LINE_BYTES has a head that classifies no event. Never raises.

    A line longer than MAX_PARTIAL_LINE_BYTES (complete, or still partial) is not parsed. Its first
    OVERLONG_HEAD_BYTES are kept, the rest is discarded as it arrives, and when its newline arrives
    the head is classified by an anchored prefix match (the event type, then the item id and item
    type, which codex writes before the large payload). A head that classifies is applied to the open
    items exactly as the same line would be if it were short. While such a line is being skipped,
    `state` reads "unknown" (never idle), and that unknown ends when the line ends. A head that
    matches no recognized prefix makes `unknown` sticky. At most MAX_PARTIAL_LINE_BYTES are buffered.

    `on_item`, when given, is called as on_item("open" | "close", item_id, line_end_offset) for each
    action item opened and for each close that matched an open id; line_end_offset is the byte offset
    just past the line's newline, counted from the first byte ever fed, skipped bytes included.
    """

    def __init__(self, on_item=None):
        self._buf = bytearray()
        self._open = set()
        self._unknown = False
        self._skipping = False
        self._fed = 0
        self.on_item = on_item

    @property
    def state(self):
        if self._unknown or self._skipping:
            return STATE_UNKNOWN
        return STATE_BUSY if self._open else STATE_IDLE

    @property
    def unreadable(self):
        """True once the stream is sticky unknown (a line whose head or body could not be read)."""
        return self._unknown

    def feed(self, data):
        try:
            self._feed(data)
        except Exception:
            self._unknown = True

    def _feed(self, data):
        if self._unknown:
            return
        if not isinstance(data, (bytes, bytearray)):
            self._unknown = True
            return
        base = self._fed
        self._fed += len(data)
        view = memoryview(data)
        size = len(data)
        pos = 0
        while pos < size:
            nl = data.find(b"\n", pos)
            end = size if nl < 0 else nl
            seg = view[pos:end]
            if self._skipping:
                if nl < 0:
                    return
                self._finish_overlong(base + nl + 1)
            elif len(self._buf) + len(seg) > MAX_PARTIAL_LINE_BYTES:
                head = (bytes(self._buf[:OVERLONG_HEAD_BYTES])
                        + bytes(seg[:OVERLONG_HEAD_BYTES]))[:OVERLONG_HEAD_BYTES]
                self._buf = bytearray(head)
                self._skipping = True
                if nl < 0:
                    return
                self._finish_overlong(base + nl + 1)
            elif nl < 0:
                self._buf.extend(seg)
                return
            else:
                line = bytes(self._buf) + bytes(seg)
                self._buf = bytearray()
                self._line(line, base + nl + 1)
            if self._unknown:
                self._buf = bytearray()
                self._skipping = False
                return
            pos = nl + 1

    def _finish_overlong(self, line_end):
        head = bytes(self._buf)
        self._buf = bytearray()
        self._skipping = False
        self._head_line(head, line_end)

    def _head_line(self, head, line_end):
        verdict = _classify_head(head)
        if verdict is None:
            self._unknown = True
            return
        if verdict:
            self._apply(verdict[0], verdict[1], line_end)

    def _line(self, line, line_end):
        text = line.strip()
        if not text:
            return
        try:
            obj = json.loads(text.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._unknown = True
            return
        if not isinstance(obj, dict):
            self._unknown = True
            return
        kind = obj.get("type")
        if kind not in ("item.started", "item.completed"):
            return
        item = obj.get("item")
        if not isinstance(item, dict):
            return
        if item.get("type") not in engine_adapter._CODEX_ACTION_ITEM_TYPES:
            return
        item_id = item.get("id")
        if isinstance(item_id, bool) or not isinstance(item_id, (str, int)):
            return
        self._apply(kind, item_id, line_end)

    def _apply(self, kind, item_id, line_end):
        if kind == "item.started":
            if item_id not in self._open:
                self._open.add(item_id)
                self._notify("open", item_id, line_end)
        elif item_id in self._open:
            self._open.discard(item_id)
            self._notify("close", item_id, line_end)

    def _notify(self, what, item_id, line_end):
        callback = self.on_item
        if callback is None:
            return
        try:
            callback(what, item_id, line_end)
        except Exception:
            pass


def silent_and_idle(stdout_grew, stderr_grew, tracker_state):
    """The one predicate: True only when neither stream grew and the state is exactly "idle"."""
    return (not stdout_grew) and (not stderr_grew) and tracker_state == STATE_IDLE


def read_increment(path, offset, max_bytes=FEED_CHUNK_BYTES):
    """Read at most max_bytes from offset. Returns (bytes, new_offset).

    On any read error returns (None, offset) — None, never b"", so a caller can tell an unreadable
    stream from no growth; a live caller treats None as `unknown`. Never raises."""
    try:
        with open(path, "rb") as fh:
            fh.seek(offset)
            data = fh.read(max(0, int(max_bytes)))
        return data, offset + len(data)
    except (OSError, ValueError, TypeError, OverflowError):
        return None, offset


# --- offline profiling ----------------------------------------------------------------------------


def _is_num(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _round(value):
    return round(value + 0.0, 1)


def _run_dir_name(run_dir):
    return os.path.basename(os.path.normpath(os.path.abspath(str(run_dir))))


def _is_run_dir(path):
    return (os.path.isfile(os.path.join(path, JOURNAL_NAME))
            or os.path.isfile(os.path.join(path, JOURNAL_ROOT_POINTER)))


def _journal_path_for(run_dir):
    local = os.path.join(run_dir, JOURNAL_NAME)
    if os.path.isfile(local):
        return local
    try:
        import engine_dispatch
        return engine_dispatch._journal_path(os.path.realpath(run_dir))
    except Exception:
        return None


def _read_journal(run_dir):
    """The journal's JSON-object records, or None when the journal cannot be read. A line that is not
    a JSON object is skipped."""
    path = _journal_path_for(run_dir)
    if not path:
        return None
    records = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    records.append(obj)
    except OSError:
        return None
    return records


def _attempt_rows(progress_path, attempt):
    """Heartbeat rows (elapsed, stdout_bytes, stderr_bytes) for one attempt, in file order; None when
    the file cannot be read."""
    rows = []
    try:
        with open(progress_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(obj, dict) or obj.get("attempt") != attempt:
                    continue
                elapsed = obj.get("elapsed_s")
                out_bytes = obj.get("stdout_bytes")
                err_bytes = obj.get("stderr_bytes", 0)
                if not (_is_num(elapsed) and _is_num(out_bytes) and _is_num(err_bytes)):
                    continue
                rows.append((float(elapsed), int(out_bytes), int(err_bytes)))
    except OSError:
        return None
    return rows


def _outcome(ended):
    if ended.get("signalSource") == "silence-watchdog":
        return "silence-watchdog"
    if ended.get("timedOut") is True:
        return "hit-bound"
    if ended.get("exit") == 0 and ended.get("timedOut") is False:
        return "answered"
    return "other"


def _measure(stdout_path, stderr_path, rows, wall):
    """Walk one attempt's heartbeats. Returns (measurements, reason); measurements is None when the
    attempt cannot be measured."""
    starts = {}
    clock = [0.0]
    longest_command = [0.0]

    def on_item(what, item_id, _line_end):
        if what == "open":
            starts[item_id] = clock[0]
        else:
            began = starts.pop(item_id, clock[0])
            longest_command[0] = max(longest_command[0], clock[0] - began)

    tracker = StreamTracker(on_item=on_item)
    offset = 0
    prev_t, prev_out, prev_err = 0.0, 0, 0
    gap = 0.0
    longest_gap = 0.0
    heartbeat_gap = False

    def feed_to(target):
        nonlocal offset
        while offset < target:
            data, new_offset = read_increment(stdout_path, offset, min(FEED_CHUNK_BYTES, target - offset))
            if data is None:
                return "stdout-missing"
            if not data:
                return "stdout-capture-truncated"
            tracker.feed(data)
            offset = new_offset
            if tracker.unreadable:
                return "stream-unknown"
        return None

    for elapsed, out_bytes, err_bytes in rows:
        if elapsed < prev_t or elapsed > wall:
            continue
        out_bytes = max(out_bytes, prev_out)
        err_bytes = max(err_bytes, prev_err)
        if elapsed - prev_t > HEARTBEAT_GAP_LIMIT_SECONDS:
            heartbeat_gap = True
        if silent_and_idle(out_bytes > prev_out, err_bytes > prev_err, tracker.state):
            gap += elapsed - prev_t
        else:
            gap = 0.0
        longest_gap = max(longest_gap, gap)
        clock[0] = elapsed
        failed = feed_to(out_bytes)
        if failed:
            return None, failed
        prev_t, prev_out, prev_err = elapsed, out_bytes, err_bytes

    if wall - prev_t > HEARTBEAT_GAP_LIMIT_SECONDS:
        heartbeat_gap = True
    try:
        final_out = os.path.getsize(stdout_path)
    except OSError:
        return None, "stdout-missing"
    try:
        final_err = os.path.getsize(stderr_path)
    except OSError:
        final_err = prev_err
    if silent_and_idle(final_out > prev_out, final_err > prev_err, tracker.state):
        gap += wall - prev_t
    else:
        gap = 0.0
    longest_gap = max(longest_gap, gap)
    clock[0] = wall
    failed = feed_to(final_out)
    if failed:
        return None, failed
    if tracker.state == STATE_UNKNOWN:
        # the stream ended while an over-long line was still being skipped
        return None, "stream-unknown"
    for began in starts.values():
        longest_command[0] = max(longest_command[0], wall - began)
    return {
        "longestIdleSilenceSeconds": _round(longest_gap),
        "longestCommandSeconds": _round(longest_command[0]),
        "commandOpenAtEnd": bool(starts),
    }, ("heartbeat-gap" if heartbeat_gap else None)


def _row(run_dir, opened, attempt, ended):
    resolved = opened.get("resolvedInputs") if isinstance(opened, dict) else None
    seat = resolved.get("role") if isinstance(resolved, dict) else None
    wall = ended.get("wallSeconds") if isinstance(ended, dict) else None
    return {
        "runDir": _run_dir_name(run_dir),
        "orderId": opened.get("orderId") if isinstance(opened, dict) else None,
        "seat": seat,
        "attempt": attempt,
        "outcome": _outcome(ended) if isinstance(ended, dict) else "other",
        "wallSeconds": wall if _is_num(wall) else None,
        "longestIdleSilenceSeconds": None,
        "longestCommandSeconds": None,
        "commandOpenAtEnd": None,
        "measured": False,
        "reason": None,
    }


def _unmeasured(row, reason):
    row["measured"] = False
    row["reason"] = reason
    row["longestIdleSilenceSeconds"] = None
    row["longestCommandSeconds"] = None
    row["commandOpenAtEnd"] = None
    return row


def _profile_attempt(run_dir, opened, attempt, ended):
    row = _row(run_dir, opened, attempt, ended)
    wall = ended.get("wallSeconds")
    if not _is_num(wall):
        return _unmeasured(row, "wall-missing")
    progress_path = opened.get("progressPath")
    rows = None
    if isinstance(progress_path, str) and progress_path:
        rows = _attempt_rows(progress_path, attempt)
    if rows is None:
        # A copied run record keeps the original absolute progressPath; the copy's own file is next
        # to the journal.
        rows = _attempt_rows(os.path.join(run_dir, PROGRESS_NAME), attempt)
    if not rows:
        return _unmeasured(row, "progress-missing")
    stdout_path = os.path.join(run_dir, "attempt-%d.stdout" % attempt)
    stderr_path = os.path.join(run_dir, "attempt-%d.stderr" % attempt)
    try:
        stdout_size = os.path.getsize(stdout_path)
    except OSError:
        return _unmeasured(row, "stdout-missing")
    captured = ended.get("stdoutBytes")
    if _is_num(captured) and captured > stdout_size:
        return _unmeasured(row, "stdout-capture-truncated")
    measurements, reason = _measure(stdout_path, stderr_path, rows, float(wall))
    if measurements is None:
        return _unmeasured(row, reason)
    row.update(measurements)
    row["measured"] = True
    row["reason"] = reason
    return row


def _profile(run_dir):
    """Returns {"rows": [...], "skipped": bool, "unended": int}. Never raises."""
    run_dir = str(run_dir)
    result = {"rows": [], "skipped": False, "unended": 0}
    try:
        records = _read_journal(run_dir)
        opened = None
        if records is not None:
            for record in records:
                if record.get("kind") == "run-opened":
                    opened = record
                    break
        if opened is None:
            row = _row(run_dir, None, None, None)
            result["rows"].append(_unmeasured(row, "journal-unreadable"))
            return result
        if opened.get("engine") != "codex" or opened.get("runKind") != "review":
            result["skipped"] = True
            return result
        ended_by_attempt = {}
        seen = set()
        for record in records:
            attempt = record.get("attempt")
            if isinstance(attempt, bool) or not isinstance(attempt, int):
                continue
            if record.get("kind") == "attempt-ended":
                ended_by_attempt[attempt] = record
                seen.add(attempt)
            elif record.get("kind") == "engine-launching":
                seen.add(attempt)
        if not seen:
            progress_path = opened.get("progressPath")
            for path in (progress_path, os.path.join(run_dir, PROGRESS_NAME)):
                if isinstance(path, str) and path:
                    for beat_attempt in _beat_attempts(path):
                        seen.add(beat_attempt)
        result["unended"] = len(seen - set(ended_by_attempt))
        for attempt in sorted(ended_by_attempt):
            try:
                row = _profile_attempt(run_dir, opened, attempt, ended_by_attempt[attempt])
            except Exception:
                row = _unmeasured(_row(run_dir, opened, attempt, ended_by_attempt[attempt]),
                                  "internal-error")
            result["rows"].append(row)
    except Exception:
        result["rows"].append(_unmeasured(_row(run_dir, None, None, None), "internal-error"))
    return result


def _beat_attempts(progress_path):
    found = set()
    try:
        with open(progress_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                attempt = obj.get("attempt") if isinstance(obj, dict) else None
                if isinstance(attempt, int) and not isinstance(attempt, bool):
                    found.add(attempt)
    except OSError:
        pass
    return found


def profile_run(run_dir):
    """One row per codex review attempt in the run; [] for a run that is not a codex review run."""
    return _profile(run_dir)["rows"]


def _find_run_dirs(path):
    if _is_run_dir(path):
        return [path]
    found = []
    for root, dirs, _files in os.walk(path):
        dirs.sort()
        if _is_run_dir(root):
            found.append(root)
    return found


def _sort_key(row):
    attempt = row.get("attempt")
    return (row["runDir"], attempt if isinstance(attempt, int) else -1)


def sample(paths):
    """Profile every run dir under paths. Read-only. A path that does not exist is listed in
    summary.badPaths and contributes no rows."""
    attempts = []
    skipped = 0
    unended = 0
    bad_paths = []
    seen = set()
    for path in paths:
        path = str(path)
        if not os.path.isdir(path):
            bad_paths.append(path)
            continue
        for run_dir in _find_run_dirs(path):
            real = os.path.realpath(run_dir)
            if real in seen:
                continue
            seen.add(real)
            profiled = _profile(run_dir)
            attempts.extend(profiled["rows"])
            skipped += 1 if profiled["skipped"] else 0
            unended += profiled["unended"]
    attempts.sort(key=_sort_key)
    by_outcome = {}
    for row in attempts:
        by_outcome[row["outcome"]] = by_outcome.get(row["outcome"], 0) + 1
    answered = [r["longestIdleSilenceSeconds"] for r in attempts
                if r["measured"] and r["outcome"] == "answered"]
    hit_bound = [r["longestIdleSilenceSeconds"] for r in attempts
                 if r["measured"] and r["outcome"] == "hit-bound"]
    return {
        "schema": SCHEMA,
        "resolutionSeconds": HEARTBEAT_RESOLUTION_SECONDS,
        "attempts": attempts,
        "skippedRuns": skipped,
        "summary": {
            "attempts": len(attempts),
            "measured": sum(1 for r in attempts if r["measured"]),
            "unended": unended,
            "badPaths": bad_paths,
            "byOutcome": by_outcome,
            "longestIdleSilenceAnswered": max(answered) if answered else None,
            "shortestIdleSilenceHitBound": min(hit_bound) if hit_bound else None,
        },
    }


_USAGE = "usage: codex_silence.py sample <path> [<path> ...]\n"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2 or argv[0] != "sample":
        sys.stderr.write(_USAGE)
        return 2
    sys.stdout.write(json.dumps(sample(argv[1:]), indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
