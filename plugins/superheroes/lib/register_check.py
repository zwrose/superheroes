#!/usr/bin/env python3
"""Register-to-child exact-text check (#940).

Deterministic, stdlib-only machine check that register-to-child text agreement
holds: every quoted register block in a consumer body matches the register entry
byte-exactly (modulo line terminators), and every entry whose Consumers line names
the child is quoted. Call-site-agnostic — the caller names the register path.
"""
import argparse
import json
import re
import sys

# --- vocabulary: ONE authoritative home (CONVENTIONS §11) --------------------

SCHEMA = "register-check/1"

RESULT_PASS = "pass"
RESULT_FAIL = "fail"
RESULT_UNDECIDED = "undecided"
RESULTS = frozenset({RESULT_PASS, RESULT_FAIL, RESULT_UNDECIDED})

KIND_TEXT_DRIFT = "text-drift"
KIND_MISSING_QUOTE = "missing-quote"
KIND_UNKNOWN_ENTRY = "unknown-entry"
FINDING_KINDS = frozenset({KIND_TEXT_DRIFT, KIND_MISSING_QUOTE, KIND_UNKNOWN_ENTRY})

UNDECIDED_REGISTER_UNREADABLE = "register-unreadable"
UNDECIDED_BODY_UNREADABLE = "body-unreadable"
UNDECIDED_REGISTER_EMPTY = "register-empty"
UNDECIDED_REGISTER_MALFORMED = "register-malformed"
UNDECIDED_CHILD_UNRECOGNIZED = "child-unrecognized"
UNDECIDED_USAGE = "usage"
UNDECIDED_INTERNAL_ERROR = "internal-error"
UNDECIDED_REASONS = frozenset({
    UNDECIDED_REGISTER_UNREADABLE,
    UNDECIDED_BODY_UNREADABLE,
    UNDECIDED_REGISTER_EMPTY,
    UNDECIDED_REGISTER_MALFORMED,
    UNDECIDED_CHILD_UNRECOGNIZED,
    UNDECIDED_USAGE,
    UNDECIDED_INTERNAL_ERROR,
})

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNDECIDED = 2

RESULT_FIELDS = (
    "schema", "result", "ok", "reason", "detail", "child", "register", "body",
    "registerEntries", "requiredEntries", "quotedEntries", "duplicateQuoteIds",
    "entriesWithoutConsumers", "findings", "firstDifference",
)
FINDING_FIELDS = ("kind", "entry", "line", "column", "expected", "actual", "detail")

ENTRY_HEADER_RE = re.compile(r"^\*\*(R\d+)\s+—\s")
CONSUMERS_LINE_RE = re.compile(r"^\*Consumers:\*\s*(.*)")


def _read_lines(path):
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError):
        return None
    lines = text.split("\n")
    if text.endswith("\n"):
        lines = lines[:-1]
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def _parse_fence_marker(line):
    """If `line` is a fence marker, return (marker_char, run_length). Else None."""
    stripped = line.strip()
    if not stripped:
        return None
    if stripped[0] == "`":
        run = 0
        for ch in stripped:
            if ch == "`":
                run += 1
            else:
                break
        if run >= 3:
            return ("`", run)
    elif stripped[0] == "~":
        run = 0
        for ch in stripped:
            if ch == "~":
                run += 1
            else:
                break
        if run >= 3:
            return ("~", run)
    return None


def _is_italic_metadata_line(line):
    return line.startswith("*") and not line.startswith("**")


def _is_entry_header(line):
    return ENTRY_HEADER_RE.match(line) is not None


def _quotable_stop_line(line):
    # A register entry is a single paragraph; text after a blank line is trailer, not quotable.
    if not line.strip():
        return True
    if _is_entry_header(line):
        return True
    if _is_italic_metadata_line(line):
        return True
    if line.startswith("---"):
        return True
    if line.startswith("#"):
        return True
    return False


def _trailer_stop_line(line):
    if _is_entry_header(line):
        return True
    if line.startswith("---"):
        return True
    if line.startswith("#"):
        return True
    return False


def _advance_past_fence(lines, i, in_fence, fence_char, fence_len):
    line = lines[i]
    marker = _parse_fence_marker(line)
    if in_fence:
        if marker is not None and marker[0] == fence_char and marker[1] >= fence_len:
            return i + 1, False, None, 0
        return i + 1, True, fence_char, fence_len
    if marker is not None:
        return i + 1, True, marker[0], marker[1]
    return i + 1, False, None, 0


def _make_finding(kind, entry, line, column, expected, actual, detail):
    values = (kind, entry, line, column, expected, actual, detail)
    if len(values) != len(FINDING_FIELDS):
        raise ValueError("finding field count mismatch")
    finding = dict(zip(FINDING_FIELDS, values))
    assert set(finding) == set(FINDING_FIELDS)
    return finding


def _make_result(
    schema,
    result,
    ok,
    reason,
    detail,
    child,
    register_path,
    body_path,
    register_entries,
    required_entries,
    quoted_entries,
    duplicate_quote_ids,
    entries_without_consumers,
    findings,
    first_difference,
):
    values = (
        schema,
        result,
        ok,
        reason,
        detail,
        child,
        register_path,
        body_path,
        register_entries,
        required_entries,
        quoted_entries,
        duplicate_quote_ids,
        entries_without_consumers,
        findings,
        first_difference,
    )
    if len(values) != len(RESULT_FIELDS):
        raise ValueError("result field count mismatch")
    payload = dict(zip(RESULT_FIELDS, values))
    assert set(payload) == set(RESULT_FIELDS)
    return payload


def _quotable_has_substance(quotable):
    if not quotable:
        return False
    header = quotable[0]
    match = ENTRY_HEADER_RE.match(header)
    if match and header[match.end():].strip():
        return True
    return len(quotable) > 1


def parse_register_lines(lines):
    """Parse register lines into ordered entries or a malformed/empty error."""
    entries = []
    seen_ids = set()
    in_fence = False
    fence_char = None
    fence_len = 0
    fence_opener_line = None
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        line_no = i + 1
        if in_fence:
            i, in_fence, fence_char, fence_len = _advance_past_fence(
                lines, i, in_fence, fence_char, fence_len
            )
            continue

        fence_marker = _parse_fence_marker(line)
        if fence_marker is not None:
            in_fence = True
            fence_opener_line = line_no
            fence_char = fence_marker[0]
            fence_len = fence_marker[1]
            i += 1
            continue

        consumers_match = CONSUMERS_LINE_RE.match(line)
        if consumers_match and not entries:
            # axis: register shape is fail-closed — malformed lines block the run.
            return None, UNDECIDED_REGISTER_MALFORMED, line_no, (
                "*Consumers:* line appears before any entry header"
            )

        header_match = ENTRY_HEADER_RE.match(line)
        if header_match:
            entry_id = header_match.group(1)
            if entry_id in seen_ids:
                return None, UNDECIDED_REGISTER_MALFORMED, line_no, (
                    f"entry id {entry_id} opens twice"
                )
            seen_ids.add(entry_id)
            quotable = [line]
            i += 1
            while i < n:
                if in_fence:
                    i, in_fence, fence_char, fence_len = _advance_past_fence(
                        lines, i, in_fence, fence_char, fence_len
                    )
                    continue
                inner = lines[i]
                inner_fence = _parse_fence_marker(inner)
                if inner_fence is not None:
                    in_fence = True
                    fence_opener_line = i + 1
                    fence_char = inner_fence[0]
                    fence_len = inner_fence[1]
                    i += 1
                    continue
                if _quotable_stop_line(inner):
                    break
                quotable.append(inner)
                i += 1
            if not _quotable_has_substance(quotable):
                return None, UNDECIDED_REGISTER_MALFORMED, line_no, (
                    f"entry {entry_id} has empty quotable text"
                )
            consumers_lines = []
            while i < n:
                if in_fence:
                    i, in_fence, fence_char, fence_len = _advance_past_fence(
                        lines, i, in_fence, fence_char, fence_len
                    )
                    continue
                inner = lines[i]
                inner_fence = _parse_fence_marker(inner)
                if inner_fence is not None:
                    in_fence = True
                    fence_opener_line = i + 1
                    fence_char = inner_fence[0]
                    fence_len = inner_fence[1]
                    i += 1
                    continue
                if _trailer_stop_line(inner):
                    break
                cons = CONSUMERS_LINE_RE.match(inner)
                if cons:
                    consumers_lines.append((i + 1, cons.group(1)))
                i += 1
            if len(consumers_lines) >= 2:
                bad_line = consumers_lines[1][0]
                return None, UNDECIDED_REGISTER_MALFORMED, bad_line, (
                    f"entry {entry_id} trailer has multiple *Consumers:* lines"
                )
            consumers_text = consumers_lines[0][1] if consumers_lines else None
            entries.append({
                "id": entry_id,
                "quotable_lines": quotable,
                "consumers_text": consumers_text,
                "header_line": line_no,
            })
            continue
        i += 1

    if in_fence:
        return None, UNDECIDED_REGISTER_MALFORMED, fence_opener_line, (
            "unterminated code fence — entries after this line were not parsed"
        )
    if not entries:
        return None, UNDECIDED_REGISTER_EMPTY, None, "register contains no entries"
    return entries, None, None, None


def load_register(register_path):
    lines = _read_lines(register_path)
    if lines is None:
        return None, UNDECIDED_REGISTER_UNREADABLE, None, None
    return parse_register_lines(lines)


def _unprefix_blockquote(line):
    if not line.startswith(">"):
        return line
    rest = line[1:]
    if rest.startswith(" "):
        rest = rest[1:]
    return rest


def parse_quoted_blocks(lines):
    """Return quoted register blocks in body order: list of (entry_id, lines)."""
    blocks = []
    in_fence = False
    fence_char = None
    fence_len = 0
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        fence_marker = _parse_fence_marker(line)
        # axis: blockquotes inside fenced regions are ignored — fences are inert in the body scanner.
        if in_fence:
            if (
                fence_marker is not None
                and fence_marker[0] == fence_char
                and fence_marker[1] >= fence_len
            ):
                in_fence = False
                fence_char = None
                fence_len = 0
            i += 1
            continue
        if fence_marker is not None:
            in_fence = True
            fence_char = fence_marker[0]
            fence_len = fence_marker[1]
            i += 1
            continue

        if line.startswith(">"):
            raw_block = []
            while i < n:
                current = lines[i]
                current_fence = _parse_fence_marker(current)
                if current_fence is not None:
                    break
                if not current.startswith(">"):
                    break
                raw_block.append(current)
                i += 1
            unprefixed = [_unprefix_blockquote(bl) for bl in raw_block]
            if unprefixed and ENTRY_HEADER_RE.match(unprefixed[0]):
                entry_id = ENTRY_HEADER_RE.match(unprefixed[0]).group(1)
                blocks.append((entry_id, unprefixed))
            continue
        i += 1
    return blocks


def _child_matches_consumers(consumers_text, token):
    if consumers_text is None:
        return False
    pattern = r"(?<![0-9A-Za-z_])" + re.escape(token) + r"(?![0-9A-Za-z_])"
    return re.search(pattern, consumers_text) is not None


def _first_diff_column(expected, actual):
    limit = min(len(expected), len(actual))
    for idx in range(limit):
        if expected[idx] != actual[idx]:
            return idx + 1
    if len(expected) != len(actual):
        return limit + 1
    return None


def _compare_quotable(entry_id, expected_lines, actual_lines):
    # axis: byte-exact line agreement — interior bytes including trailing whitespace.
    max_len = max(len(expected_lines), len(actual_lines))
    for line_idx in range(max_len):
        if line_idx >= len(expected_lines):
            actual = actual_lines[line_idx]
            detail = (
                f"{entry_id}: quoted block has {len(actual_lines)} lines, "
                f"register entry has {len(expected_lines)} — "
                f"first differing line {line_idx + 1}"
            )
            return _make_finding(
                KIND_TEXT_DRIFT,
                entry_id,
                line_idx + 1,
                None,
                None,
                actual,
                detail,
            )
        if line_idx >= len(actual_lines):
            expected = expected_lines[line_idx]
            detail = (
                f"{entry_id}: quoted block has {len(actual_lines)} lines, "
                f"register entry has {len(expected_lines)} — "
                f"first differing line {line_idx + 1}"
            )
            return _make_finding(
                KIND_TEXT_DRIFT,
                entry_id,
                line_idx + 1,
                None,
                expected,
                None,
                detail,
            )
        expected = expected_lines[line_idx]
        actual = actual_lines[line_idx]
        if expected != actual:
            column = _first_diff_column(expected, actual)
            detail = (
                f"{entry_id}: first differing line {line_idx + 1}, column {column}"
            )
            return _make_finding(
                KIND_TEXT_DRIFT,
                entry_id,
                line_idx + 1,
                column,
                expected,
                actual,
                detail,
            )
    return None


def _base_result(
    result,
    reason,
    detail,
    child,
    register_path,
    body_path,
    register_entries,
    required_entries,
    quoted_entries,
    duplicate_quote_ids,
    entries_without_consumers,
    findings,
):
    first_difference = None
    for finding in findings:
        if finding["kind"] == KIND_TEXT_DRIFT:
            first_difference = finding
            break
    return _make_result(
        SCHEMA,
        result,
        result == RESULT_PASS,
        reason,
        detail,
        child,
        register_path,
        body_path,
        register_entries,
        required_entries,
        quoted_entries,
        duplicate_quote_ids,
        entries_without_consumers,
        findings,
        first_difference,
    )


def _undecided(
    reason,
    detail,
    child=None,
    register_path=None,
    body_path=None,
):
    return _base_result(
        RESULT_UNDECIDED,
        reason,
        detail,
        child,
        register_path,
        body_path,
        [],
        [],
        [],
        [],
        [],
        [],
    )


def check_body(register_path, body_path, child, allow_no_required_entries=False):
    """Compare a consumer body against a register for the named child token."""
    if child is None or not str(child).strip():
        return _undecided(
            UNDECIDED_USAGE,
            "child token must be a non-empty string",
            child=child,
            register_path=register_path,
            body_path=body_path,
        )

    entries, reg_reason, reg_line, reg_detail = load_register(register_path)
    if entries is None:
        if reg_reason == UNDECIDED_REGISTER_UNREADABLE:
            return _undecided(
                UNDECIDED_REGISTER_UNREADABLE,
                "register file is missing or not valid UTF-8",
                child=child,
                register_path=register_path,
                body_path=body_path,
            )
        if reg_reason == UNDECIDED_REGISTER_EMPTY:
            return _undecided(
                UNDECIDED_REGISTER_EMPTY,
                reg_detail,
                child=child,
                register_path=register_path,
                body_path=body_path,
            )
        detail = reg_detail
        if reg_line is not None:
            detail = f"register line {reg_line}: {reg_detail}"
        return _undecided(
            UNDECIDED_REGISTER_MALFORMED,
            detail,
            child=child,
            register_path=register_path,
            body_path=body_path,
        )

    body_lines = _read_lines(body_path)
    if body_lines is None:
        return _undecided(
            UNDECIDED_BODY_UNREADABLE,
            "body file is missing or not valid UTF-8",
            child=child,
            register_path=register_path,
            body_path=body_path,
        )

    register_entries = [entry["id"] for entry in entries]
    entry_by_id = {entry["id"]: entry for entry in entries}
    entries_without_consumers = [
        entry["id"] for entry in entries if entry["consumers_text"] is None
    ]

    required_entries = [
        entry["id"]
        for entry in entries
        if _child_matches_consumers(entry["consumers_text"], child)
    ]
    # axis: every Consumers match for the child token must appear quoted — completeness.
    if not required_entries and not allow_no_required_entries:
        # axis: an unmatched child token must not silently pass — child fail-closed.
        return _undecided(
            UNDECIDED_CHILD_UNRECOGNIZED,
            f"no register entry names child {child!r} on its Consumers line",
            child=child,
            register_path=register_path,
            body_path=body_path,
        )

    quoted_blocks = parse_quoted_blocks(body_lines)
    quoted_entries = []
    duplicate_quote_ids = []
    seen_quote_ids = set()
    for entry_id, _block in quoted_blocks:
        if entry_id not in seen_quote_ids:
            quoted_entries.append(entry_id)
            seen_quote_ids.add(entry_id)
        elif entry_id not in duplicate_quote_ids:
            duplicate_quote_ids.append(entry_id)

    findings = []
    quoted_ids_present = {entry_id for entry_id, _ in quoted_blocks}

    for entry_id, block_lines in quoted_blocks:
        if entry_id not in entry_by_id:
            # axis: quoted ids must exist in the register — unknown-entry is fail-closed.
            findings.append(_make_finding(
                KIND_UNKNOWN_ENTRY,
                entry_id,
                None,
                None,
                None,
                None,
                (
                    f"{entry_id}: quoted in the body but not defined in the register"
                ),
            ))
            continue
        drift = _compare_quotable(
            entry_id,
            entry_by_id[entry_id]["quotable_lines"],
            block_lines,
        )
        if drift is not None:
            findings.append(drift)

    for entry_id in register_entries:
        if entry_id not in required_entries:
            continue
        if entry_id not in quoted_ids_present:
            findings.append(_make_finding(
                KIND_MISSING_QUOTE,
                entry_id,
                None,
                None,
                None,
                None,
                (
                    f"{entry_id}: required by child {child} (named on its Consumers line) "
                    "but not quoted in the body"
                ),
            ))

    def _sort_key(finding):
        entry_id = finding["entry"]
        if entry_id in entry_by_id:
            entry_pos = register_entries.index(entry_id)
        else:
            entry_pos = len(register_entries)
        kind_order = {
            KIND_TEXT_DRIFT: 0,
            KIND_MISSING_QUOTE: 1,
            KIND_UNKNOWN_ENTRY: 2,
        }
        if entry_id not in entry_by_id:
            body_pos = next(
                (idx for idx, (qid, _) in enumerate(quoted_blocks) if qid == entry_id),
                len(quoted_blocks),
            )
            return (entry_pos, kind_order[finding["kind"]], body_pos)
        return (entry_pos, kind_order[finding["kind"]], 0)

    findings.sort(key=_sort_key)

    if findings:
        return _base_result(
            RESULT_FAIL,
            None,
            None,
            child,
            register_path,
            body_path,
            register_entries,
            required_entries,
            quoted_entries,
            duplicate_quote_ids,
            entries_without_consumers,
            findings,
        )
    return _base_result(
        RESULT_PASS,
        None,
        None,
        child,
        register_path,
        body_path,
        register_entries,
        required_entries,
        quoted_entries,
        duplicate_quote_ids,
        entries_without_consumers,
        findings,
    )


def _emit(result):
    assert set(result) == set(RESULT_FIELDS)
    sys.stdout.write(json.dumps(result, separators=(",", ": ")) + "\n")


class _RegisterCheckArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._usage_paths = {"child": None, "register": None, "body": None}

    def error(self, message):
        result = _undecided(
            UNDECIDED_USAGE,
            message,
            child=self._usage_paths["child"],
            register_path=self._usage_paths["register"],
            body_path=self._usage_paths["body"],
        )
        _emit(result)
        raise SystemExit(EXIT_UNDECIDED)

    def exit(self, status=0, message=None):
        if status != 0:
            detail = message or "invalid command-line arguments"
            result = _undecided(
                UNDECIDED_USAGE,
                detail,
                child=self._usage_paths["child"],
                register_path=self._usage_paths["register"],
                body_path=self._usage_paths["body"],
            )
            _emit(result)
            raise SystemExit(EXIT_UNDECIDED)
        raise SystemExit(status)


def _peek_argv_value(argv, flag):
    if argv is None:
        return None
    for i, arg in enumerate(argv):
        if arg == flag and i + 1 < len(argv):
            return argv[i + 1]
        prefix = flag + "="
        if arg.startswith(prefix):
            return arg[len(prefix):]
    return None


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    parser = _RegisterCheckArgumentParser(description=__doc__.splitlines()[0])
    parser._usage_paths["child"] = _peek_argv_value(argv, "--child")
    parser._usage_paths["register"] = _peek_argv_value(argv, "--register")
    parser._usage_paths["body"] = _peek_argv_value(argv, "--body-file")
    sub = parser.add_subparsers(dest="cmd")
    check = sub.add_parser("check", help="compare a consumer body against a register")
    check.add_argument("--register", required=True, help="path to register markdown")
    check.add_argument("--body-file", required=True, help="path to consumer body markdown")
    check.add_argument("--child", required=True, help="child token to match on Consumers lines")
    check.add_argument(
        "--allow-no-required-entries",
        action="store_true",
        help="proceed when no Consumers line names the child",
    )
    check.error = parser.error
    check.exit = parser.exit
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code in (0, None):
            return EXIT_PASS
        return EXIT_UNDECIDED

    if args.cmd != "check":
        parser._usage_paths["child"] = None
        parser._usage_paths["register"] = None
        parser._usage_paths["body"] = None
        parser.error("unknown subcommand")

    parser._usage_paths["child"] = args.child
    parser._usage_paths["register"] = args.register
    parser._usage_paths["body"] = args.body_file

    try:
        result = check_body(
            args.register,
            args.body_file,
            args.child,
            allow_no_required_entries=args.allow_no_required_entries,
        )
    except Exception as exc:
        result = _undecided(
            UNDECIDED_INTERNAL_ERROR,
            f"{type(exc).__name__}: {exc}",
            child=args.child,
            register_path=args.register,
            body_path=args.body_file,
        )
        _emit(result)
        return EXIT_UNDECIDED

    _emit(result)
    # axis: exit 1 is reserved for comparison failure — undecided paths must not use it.
    if result["result"] == RESULT_PASS:
        return EXIT_PASS
    if result["result"] == RESULT_FAIL:
        return EXIT_FAIL
    return EXIT_UNDECIDED


if __name__ == "__main__":
    sys.exit(main())
