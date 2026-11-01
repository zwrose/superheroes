"""Whether an external review seat read the calibration files its order named (#2311).

Stdlib plus the plugin's ``calibration_resolve``, ``core_md`` and ``engine_adapter`` recognizers. Two jobs:

* ``stamp`` runs once when a review run opens. For each calibration file (core, review-crew layer,
  the project CLAUDE.md) whose absolute path the order text names, it records the file's content
  hash and ``Policy version:`` line as they stood at that moment.
* ``read_states`` runs when the run's engine record is built. It reads the engine's own event
  stream and reports, per stamped file, ``read`` only on positive evidence (a completed, successful
  tool call naming the file's path), ``not-read`` when the stream is readable and no such call
  exists, and ``unknown`` whenever the stream cannot tell.

``resolved_paths`` is the one home of calibration path resolution for the round driver.
``stamp`` and ``read_states`` never raise. No absolute path is ever put in the observation.
"""
import hashlib
import json
import os
import re
import shlex
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import calibration_resolve  # noqa: E402
import core_md  # noqa: E402
import engine_adapter  # noqa: E402  the stream recognizers the tool-call counters use
from calibration_vocab import (  # noqa: E402,F401  the one home of the label and read-state vocabulary
    LABEL_CORE, LABEL_REVIEW_CREW, LABEL_CLAUDE_MD, LABELS, READ, NOT_READ, UNKNOWN)

_OK = "ok"
_FAILED = "failed"
_INDETERMINATE = "indeterminate"

# Leading markdown decoration, the words, optional bold/code around the words, the colon.
_POLICY_VERSION_RE = re.compile(
    r"^[ \t\-*>#|`]*policy version[ \t*`]*:(?P<rest>[^\n]*)", re.IGNORECASE | re.MULTILINE)


def resolved_paths(repo_root):
    """(core_path_or_None, layer_path_or_None, root_refusal_or_None) from calibration_resolve."""
    cwd = repo_root if isinstance(repo_root, str) and repo_root else os.getcwd()
    try:
        info = calibration_resolve.resolve(cwd)
    except calibration_resolve.UnresolvableRootError as exc:
        refusal = core_md.gate_refusal_line(
            core_md.gate_refusal(exc.reason, str(exc.root)))
        return None, None, refusal
    core = info.get("dispatch_core")
    layer = info.get("dispatch_layer")
    core_path = core if isinstance(core, str) and os.path.isfile(core) else None
    layer_path = layer if isinstance(layer, str) and os.path.isfile(layer) else None
    return core_path, layer_path, None


def _policy_version(text):
    """First ``Policy version:`` value in ``text``, or None. Never raises."""
    try:
        for match in _POLICY_VERSION_RE.finditer(text):
            rest = match.group("rest").lstrip(" \t*`")
            token = rest.split(None, 1)[0] if rest.strip() else ""
            value = token.strip("*`")
            if value:
                return value
    except Exception:
        pass
    return None


def _hash_and_policy(path):
    """(sha256 hex or None, policyVersion or None) from ONE read of ``path``. Never raises."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except Exception:
        return None, None
    try:
        digest = hashlib.sha256(data).hexdigest()
    except Exception:
        return None, None
    return digest, _policy_version(data.decode("utf-8", errors="replace"))


def stamp(repo_root, order_text):
    """Calibration files the order names, with the hash and policy version they have now.

    A list of {"label", "file", "path", "sha256", "policyVersion"} in the fixed order core,
    review-crew, CLAUDE.md. A file is kept only when its absolute path string occurs in
    ``order_text``. Never raises: any failure gives []."""
    try:
        if not isinstance(order_text, str) or not order_text:
            return []
        try:
            core_path, layer_path, _refusal = resolved_paths(repo_root)
        except Exception:
            core_path, layer_path = None, None
        candidates = [(LABEL_CORE, core_path), (LABEL_REVIEW_CREW, layer_path)]
        if isinstance(repo_root, str) and repo_root:
            claude_md = os.path.join(repo_root, "CLAUDE.md")
            candidates.append(
                (LABEL_CLAUDE_MD, claude_md if os.path.isfile(claude_md) else None))
        else:
            candidates.append((LABEL_CLAUDE_MD, None))
        out = []
        for label, path in candidates:
            if not isinstance(path, str) or not path or path not in order_text:
                continue
            digest, policy = _hash_and_policy(path)
            out.append({
                "label": label,
                "file": os.path.basename(path),
                "path": path,
                "sha256": digest,
                "policyVersion": policy,
            })
        return out
    except Exception:
        return []


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _exit_outcome(code):
    # axis: a codex command counts as successful only on an integer exit code of exactly 0.
    if _is_int(code):
        return _OK if code == 0 else _FAILED
    return _INDETERMINATE


def _call(outcome, paths=(), texts=()):
    return {"outcome": outcome, "paths": list(paths), "texts": list(texts)}


def _string_values(value, depth=0):
    """Every string value in a JSON-like structure (bounded depth)."""
    if isinstance(value, str):
        return [value]
    if depth > 6:
        return []
    if isinstance(value, dict):
        children = value.values()
    elif isinstance(value, list):
        children = value
    else:
        return []
    out = []
    for child in children:
        out.extend(_string_values(child, depth + 1))
    return out


def _codex_item_call(item, completed):
    """A normalized call for a codex action item, or None for any other item. Never raises."""
    kind = item.get("type")
    if kind == "command_execution":
        command = item.get("command")
        if isinstance(command, list):
            command = " ".join(str(part) for part in command)
        if not isinstance(command, str):
            return None
        outcome = _exit_outcome(item.get("exit_code")) if completed else _INDETERMINATE
        return _call(outcome, texts=[command])
    if kind == "mcp_tool_call":
        # an argument value that is exactly a path is a path; a substring of some other value is not
        values = _string_values(item.get("arguments"))
        if not completed:
            outcome = _INDETERMINATE
        elif item.get("status") == "completed" and not item.get("error"):
            outcome = _OK
        elif item.get("status") == "failed" or item.get("error"):
            outcome = _FAILED
        else:
            outcome = _INDETERMINATE
        return _call(outcome, paths=values)
    return None


def _codex_calls(stdout):
    """(recognized, calls) from a codex JSONL stream."""
    recognized = False
    calls = []
    started = {}
    for obj in engine_adapter._iter_jsonl_dict_lines(stdout):
        if not engine_adapter._is_codex_event_object(obj):
            continue
        recognized = True
        item = obj.get("item")
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        if obj.get("type") == "item.started":
            call = _codex_item_call(item, False)
            if call is not None:
                started[item_id if isinstance(item_id, str) else id(call)] = call
        elif obj.get("type") == "item.completed":
            call = _codex_item_call(item, True)
            if call is not None:
                started.pop(item_id, None)
                calls.append(call)
    # A call that started and never completed has an outcome the stream cannot give.
    calls.extend(started.values())
    return recognized, calls


def _claude_calls(stdout):
    recognized = False
    calls = []
    pending = {}
    for obj in engine_adapter._iter_jsonl_dict_lines(stdout):
        if not engine_adapter._is_claude_event_object(obj):
            continue
        recognized = True
        message = obj.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if obj.get("type") == "assistant" and block.get("type") == "tool_use":
                tool_input = block.get("input")
                if not isinstance(tool_input, dict):
                    continue
                if block.get("name") == "Read":
                    call = _call(_INDETERMINATE, paths=[tool_input.get("file_path")])
                elif block.get("name") == "Bash":
                    call = _call(_INDETERMINATE, texts=[tool_input.get("command")])
                else:
                    continue
                calls.append(call)
                block_id = block.get("id")
                if isinstance(block_id, str) and block_id:
                    pending[block_id] = call
            elif obj.get("type") == "user" and block.get("type") == "tool_result":
                call = pending.get(block.get("tool_use_id"))
                if call is not None:
                    # axis: a claude call is successful only when its tool_result is not an error.
                    call["outcome"] = _FAILED if block.get("is_error") is True else _OK
    return recognized, calls


def _cursor_result_outcome(kind, result):
    """Outcome of one cursor ``<kind>ToolCall`` result dict."""
    if not isinstance(result, dict):
        return _INDETERMINATE
    if "success" in result:
        # axis: a cursor call is successful only when its result holds a success.
        if kind == "shellToolCall":
            success = result.get("success")
            if isinstance(success, dict) and "exitCode" in success:
                return _exit_outcome(success.get("exitCode"))
        return _OK
    if "error" in result or "failure" in result:
        return _FAILED
    return _INDETERMINATE


def _cursor_event_calls(obj, completed):
    calls = []
    tool_call = obj.get("tool_call")
    if not isinstance(tool_call, dict):
        return calls
    for kind, body in tool_call.items():
        if not isinstance(kind, str) or not isinstance(body, dict):
            continue
        args = body.get("args")
        if not isinstance(args, dict):
            continue
        outcome = _cursor_result_outcome(kind, body.get("result")) if completed else _INDETERMINATE
        if kind == "readToolCall":
            paths = [args.get(key) for key in ("path", "file_path", "target_file")]
            calls.append(_call(outcome, paths=paths))
        elif kind == "shellToolCall":
            calls.append(_call(outcome, texts=[args.get("command")]))
    return calls


def _cursor_calls(stdout):
    recognized = False
    calls = []
    started = {}
    for obj in engine_adapter._iter_jsonl_dict_lines(stdout):
        if obj.get("type") != "tool_call":
            continue
        recognized = True
        call_id = obj.get("call_id")
        if obj.get("subtype") == "started":
            if isinstance(call_id, str) and call_id:
                started[call_id] = _cursor_event_calls(obj, False)
        elif obj.get("subtype") == "completed":
            if isinstance(call_id, str):
                started.pop(call_id, None)
            calls.extend(_cursor_event_calls(obj, True))
    for pending in started.values():
        calls.extend(pending)
    return recognized, calls


_STREAM_PARSERS = {
    "codex": _codex_calls,
    "claude": _claude_calls,
    "cursor": _cursor_calls,
}


# What a shell command does with a file argument it names.
_HIT_READ = "read"            # a program that prints or scans the file's content
_HIT_NONREAD = "non-read"     # a program that only inspects the file's existence or metadata
_HIT_AMBIGUOUS = "ambiguous"  # the file is named but what the command does with it is not clear

_NONREAD_PROGRAMS = frozenset((
    "test", "[", "[[", "ls", "stat", "file", "wc", "realpath", "readlink", "basename", "dirname",
    "touch", "chmod", "chown", "du", "find", "cd", "mkdir", "rm", "mv", "cp", "sha256sum",
    "shasum", "md5sum", "cksum", "git",
))
_SHELL_PROGRAMS = frozenset(("sh", "bash", "zsh", "dash", "ksh"))
_WRAPPER_PROGRAMS = frozenset(("sudo", "env", "command", "time", "nice", "nohup", "exec"))
# grep-family options known to leave the matched content printed; any other option grades unknown.
_GREP_PROGRAMS = ("grep", "egrep", "fgrep", "rg")
_CONTENT_SHORT_FLAGS = frozenset("niHheFEwx")
_CONTENT_LONG_FLAGS = frozenset((
    "--line-number", "--ignore-case", "--with-filename", "--no-filename", "--regexp",
    "--fixed-strings", "--extended-regexp", "--word-regexp", "--line-regexp",
))
_NR =r"NR\s*(==|>=|<=|>|<)\s*\d+"
_NO_OPTION = "(?!)"
# program: (an option word it allows, the option words that take the next argument, what that argument must be)
_OPERAND_SPECS = {
    **dict.fromkeys(("cat", "nl", "less", "more"), (_NO_OPTION, _NO_OPTION, _NO_OPTION)),
    "head": (r"-n|-n\d+|-\d+|--lines=\d+", "-n", r"\d+"),
    "tail": (r"-n|-n\+?\d+|-\d+|--lines=\+?\d+", "-n", r"\+?\d+"),
    "sed": ("-n|-e", "-e", r"\s*(\d+|\$)?(\s*,\s*(\d+|\$))?\s*p\s*"),
    "awk": (_NO_OPTION, _NO_OPTION, r"1|\s*(%s(\s*&&\s*%s)?\s*)?\{\s*print(\s+\$0)?\s*;?\s*\}\s*" % (_NR, _NR)),
    **dict.fromkeys(_GREP_PROGRAMS, (
        r"-(?=.)[%s]*e?|--regexp=.*|%s" % ("".join(sorted(_CONTENT_SHORT_FLAGS - {"e"})),
                                           "|".join(sorted(_CONTENT_LONG_FLAGS))),
        r"-\w*e|--regexp", r"(?s).*")),
}


def _file_operands(program, args):
    """The file operands of an allowlisted content-printing command; None for any other program, option or form."""
    # axis: a read is credited only for a FILE OPERAND found by position, never for any argument that equals the target
    spec = _OPERAND_SPECS.get(program)
    if spec is None:
        return None
    option, value_option, value = spec
    files, flags, values, it = [], [], [], iter(args)
    for arg in it:
        if not arg.startswith("-"):
            files.append(arg)
        elif not re.fullmatch(option, arg):
            return None
        else:
            flags.append(arg)
            if re.fullmatch(value_option, arg):
                values.append(next(it, None))
    scripted = program in ("sed", "awk")
    if scripted and not values:
        values, files = files[:1], files[1:]
    if not all(isinstance(v, str) and re.fullmatch(value, v) for v in values) or (
            scripted and (len(values) != 1 or (program == "sed" and "-n" not in flags))):
        return None
    if program in _GREP_PROGRAMS and not values and not any(f.startswith("--regexp=") for f in flags):
        files = files[1:]
    return files


_PATH_CHARS = r"[\w.\-/]"
_MAX_SHELL_DEPTH = 3
# A quoted word made only of separators and blanks, or a backslash before a separator.
_QUOTED_SEPARATOR_RE = re.compile(r"""['"][ \t]*[|&;()<>\n][ \t|&;()<>\n]*['"]|\\[|&;()<>\n]""")
# A path-like word of a command text: split at whitespace, quotes, redirections, operators and `=`.
_WORD_RE = re.compile(r"[^\s\"'`;&|()<>=]+")


def _segments(command):
    """The command split into simple commands (token lists) at ``|``, ``&&``, ``;``, ``&`` and an unquoted newline.

    Raises ValueError."""
    # axis: shlex drops quotes, so a quoted or escaped separator would read as a real one; doubt grades unknown
    if _QUOTED_SEPARATOR_RE.search(command):
        raise ValueError("quoted or escaped separator")
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>\n")
    lexer.whitespace_split = True
    # axis: a newline is a command boundary, not whitespace; a quoted newline stays inside its word
    lexer.whitespace = " \t\r"
    out, current = [], []
    for token in lexer:
        if token and all(ch in "|&;()\n" for ch in token):
            if current:
                out.append(current)
            current = []
        else:
            current.append(token)
    if current:
        out.append(current)
    return out


def _segment_program(tokens):
    """(program basename, argument tokens) of one simple command, past env assignments and wrappers."""
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", token) or os.path.basename(token) in _WRAPPER_PROGRAMS:
            index += 1
            continue
        break
    if index >= len(tokens):
        return None, []
    return os.path.basename(tokens[index]), tokens[index + 1:]


def _command_hit(command, targets, depth=0):
    """_HIT_READ, _HIT_NONREAD, _HIT_AMBIGUOUS or None for a shell command text and the target paths.

    A read is credited only when the path is a file operand of a content-printing command (``_file_operands``).
    A command that names the path in any other way is non-read or ambiguous, not a read."""
    if not any(re.search(re.escape(t) + "(?!" + _PATH_CHARS + ")", command) for t in targets):
        return None
    try:
        segments = _segments(command)
    except ValueError:
        return _HIT_AMBIGUOUS
    verdict = None
    for tokens in segments:
        program, args = _segment_program(tokens)
        if program is None:
            continue
        if program in _SHELL_PROGRAMS and depth < _MAX_SHELL_DEPTH:
            for position, arg in enumerate(args[:-1]):
                if arg.startswith("-") and "c" in arg:
                    inner = _command_hit(args[position + 1], targets, depth + 1)
                    if inner == _HIT_READ:
                        return _HIT_READ
                    verdict = inner or verdict
                    break
            continue
        if not any(arg in targets for arg in args):
            continue
        if any(operand in targets for operand in _file_operands(program, args) or ()):
            return _HIT_READ
        if program in _NONREAD_PROGRAMS:
            verdict = verdict or _HIT_NONREAD
        else:
            verdict = _HIT_AMBIGUOUS
    # The path occurs but no simple command takes it whole as an argument (a quoted script, a
    # substitution): what happens to it cannot be told.
    return verdict or _HIT_AMBIGUOUS


def _call_hit(call, targets):
    """How one normalized call touches the target paths: _HIT_READ, _HIT_NONREAD, _HIT_AMBIGUOUS or None."""
    if any(isinstance(p, str) and p in targets for p in call["paths"]):
        return _HIT_READ
    verdict = None
    for text in call["texts"]:
        if not isinstance(text, str):
            continue
        hit = _command_hit(text, targets)
        if hit == _HIT_READ:
            return _HIT_READ
        if hit == _HIT_AMBIGUOUS or (hit == _HIT_NONREAD and verdict is None):
            verdict = hit
    return verdict


def _names_basename(call, basename):
    """True when the call names a file called ``basename`` by something other than an absolute path.

    A relative or unresolvable argument (``./core.md``, ``core.md``, ``$DIR/core.md``) may be the stamped file;
    an absolute path to some other directory is not."""
    def names(word):
        return not word.startswith("/") and os.path.basename(word) == basename
    return (any(isinstance(p, str) and os.path.basename(p) == basename for p in call["paths"])
            or any(isinstance(t, str) and any(names(w) for w in _WORD_RE.findall(t)) for t in call["texts"]))


def _file_state(calls, path, truncated=False):
    """read | not-read | unknown for one file given the normalized calls.

    ``truncated`` says the stream lost its head to the capture cap: a positive read still counts, but
    the absence of one cannot show the file was not read."""
    targets = {path, os.path.realpath(path)}
    basename = os.path.basename(path)
    hits = [(call, _call_hit(call, targets)) for call in calls]
    hits = [(call, hit) for call, hit in hits if hit is not None]
    # axis: `read` only on a completed, successful content-reading call naming the whole path;
    # `unknown` whenever the stream cannot tell (an undeterminable outcome, an ambiguous command, a
    # basename-only success, or a truncated capture with no positive read).
    if any(hit == _HIT_READ and call["outcome"] == _OK for call, hit in hits):
        return READ
    if any(call["outcome"] == _INDETERMINATE and hit != _HIT_NONREAD for call, hit in hits):
        return UNKNOWN
    if any(call["outcome"] == _OK and hit == _HIT_AMBIGUOUS for call, hit in hits):
        return UNKNOWN
    if truncated:
        return UNKNOWN
    target_ids = {id(call) for call, _hit in hits}
    for call in calls:
        if id(call) in target_ids:
            continue
        if call["outcome"] == _OK and _names_basename(call, basename):
            return UNKNOWN
    return NOT_READ


def _observation_entry(entry, state):
    return {
        "label": entry.get("label"),
        "file": entry.get("file"),
        "sha256": entry.get("sha256"),
        "policyVersion": entry.get("policyVersion"),
        "read": state,
    }


def read_states(engine, stdout, stamped, truncated=False):
    """The observation's ``calibration`` list: the stamp minus ``path``, plus ``read``.

    ``truncated`` is True when ``stdout`` is only the tail of the engine's output: a file with no
    positive read in the retained events is then ``unknown``, never ``not-read``.
    Never raises; any failure gives ``unknown`` for every file."""
    try:
        if not isinstance(stamped, list):
            return []
        entries = [entry for entry in stamped if isinstance(entry, dict)]
        states = {}
        try:
            parser = _STREAM_PARSERS.get(engine)
            if parser is not None and isinstance(stdout, str) and stdout:
                recognized, calls = parser(stdout)
                if recognized:
                    for entry in entries:
                        path = entry.get("path")
                        states[id(entry)] = (
                            _file_state(calls, path, truncated is True)
                            if isinstance(path, str) and path else UNKNOWN)
        except Exception:
            states = {}
        return [_observation_entry(entry, states.get(id(entry), UNKNOWN)) for entry in entries]
    except Exception:
        return []
