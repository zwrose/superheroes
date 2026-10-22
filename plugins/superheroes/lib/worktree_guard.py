#!/usr/bin/env python3
"""PreToolUse(Bash) worktree guard — deny destructive git discard on dirty trees (#682).

Best-effort classifier over literal `git` invocations at command position in Bash command
text. Does not resolve shell aliases, git aliases, or dynamic shell expansion.

Stdlib-only.
"""
import os
import re
import stat
import subprocess

# Git global options consumed before the subcommand (value-taking forms accept =value).
_GIT_GLOBAL_OPTS = frozenset({
    "-p", "--paginate", "--no-pager", "--no-optional-locks",
    "--literal-pathspecs", "--bare",
})
_GIT_GLOBAL_OPT_WITH_VALUE = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
}

_DESTRUCTIVE_SUBCOMMANDS = frozenset({
    "checkout", "checkout-index", "restore", "reset", "clean", "switch", "rm", "worktree",
})

_SHELL_PREFIXES = frozenset({
    "!", "then", "do", "else", "elif", "(", ";;",
})

# Sentences carried word for word by more than one template below; no braces, so each
# template stays usable with str.format.
_NEXT_STEP_COMMIT_OR_STASH = (
    "Next step: commit the work (`git add <path>` then `git commit`) or run "
    "`git stash push -u`, then re-run"
)
_DURING_A_MERGE = (
    "During a merge: `git checkout --theirs <path>` or "
    "`git checkout --ours <path>` takes one side of a conflicted path you have not "
    "edited since the merge; a path you have edited is finished with the Edit tool and "
    "then `git add <path>`."
)

_REFUSAL_TEMPLATE = (
    "superheroes worktree guard: this `git {action}` would discard {count} uncommitted "
    "change(s) in this worktree, and git keeps no copy of them. This is the checkout-revert "
    "wipe (issue #682): the command that reverts a probe edit also erases a prior order's "
    "uncommitted delivery at the same path. Recover the intent instead — commit the work "
    "first, `git stash -u` it (add `-a` to include ignored files; in a conflicted tree "
    "`git add` the unmerged paths first), or revert a probe edit with an inverse Edit "
    "rather than a git discard. "
    + _NEXT_STEP_COMMIT_OR_STASH
    + " this command; revert a probe edit with the Edit tool's inverse edit. "
    + _DURING_A_MERGE
)

_INDETERMINATE_TEMPLATE = (
    "superheroes worktree guard: could not determine whether this `git {action}` would "
    "destroy uncommitted work — it may target another worktree, or the repository could "
    "not be inspected — so it is refused (fail-closed). Commit or `git stash -u` your "
    "work first, or revert a probe edit with an inverse Edit rather than a git discard. "
    + _NEXT_STEP_COMMIT_OR_STASH
    + " it as a plain `git ...` command from inside the "
    "worktree it targets (no `-C`, `--git-dir`, `--work-tree`, `cd`, or "
    "`GIT_DIR`/`GIT_WORK_TREE`). "
    + _DURING_A_MERGE
)

_UNPARSED_TEMPLATE = (
    "superheroes worktree guard: could not confidently parse this command's git "
    "invocation — it may include a destructive discard subcommand — so it is refused "
    "(fail-closed) rather than risk wiping uncommitted work. If this command runs no "
    "git discard and only mentions one in prose — a PR or issue comment body, a commit "
    "message — that prose is the trigger: text naming a destructive git subcommand "
    "(`checkout`, `restore`, `reset`, `clean`, `switch`, `rm`, `checkout-index`, "
    "`worktree`) reads as a command wherever this guard loses track of the quoting "
    "around it — a heredoc body this guard cannot show is only text, or a quote of "
    "the same kind as the one enclosing it nested inside a `$(...)` substitution. "
    "A heredoc fed to `cat`, `tee`, `gh issue|pr|release|api` or `git commit` with a "
    "quoted delimiter (`<<'EOF'`) is read as text; a heredoc fed to anything else, or "
    "left unterminated, is read as command text. Heredoc masking is also off for the "
    "rest of the command once any earlier line holds a `$(`, backtick, `(`, `{` or `|` "
    "(even a completed or quoted one), so there the text route is the Write tool and "
    "`--body-file`/`-F`. "
    "Next step: write the text with the Write tool and pass the file "
    "(`gh ... --body-file <path>`, `git commit -F <path>`), or re-issue an intended "
    "discard as a plain `git ...` command this guard can parse. "
    "If a discard is intended, note that this refusal does not depend on what your tree "
    "holds, so committing or stashing alone will not clear it. Keep the work you care "
    "about by committing or `git stash push -u` first, and revert a probe edit with an "
    "inverse Edit rather than a git discard."
)

_GIT_TIMEOUT = 5

_TRACKED_ONLY_PROBE_ACTIONS = frozenset({
    "checkout-path", "restore", "rm-force", "checkout-index-force",
})


def _is_git_token(token):
    """True when token invokes git by basename (path-spelled or bare), not gitk/git-foo/mygit."""
    base = os.path.basename(token)
    return base == "git" or base == "git.exe"


_HEREDOC_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")
_ASSIGNMENT_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_PIECE_SKIP_WORDS = frozenset({"!", "{", "then", "do", "else", "elif", "time"})
_GH_DATA_SUBCOMMANDS = frozenset({"issue", "pr", "release", "api"})
_HEREDOC_DELIMITER_END = " \t;|&()<>"
_COMMENT_PRECEDERS = " \t;|&()`"
_NESTING_MARKS = ("`", "{", "(", "|")
_CONTINUING_LINE_ENDINGS = ("\\", "&&")
_DATA_SUBSTITUTION = re.compile(r"(\"?)\$\(cat <<'[A-Za-z_][A-Za-z0-9_.-]*'\s*$")


def _piece_is_data_consumer(piece):
    """True when the piece's command word is a program that reads stdin as data, never runs it."""
    words = piece.split()
    k = 0
    while k < len(words) and (_ASSIGNMENT_WORD.match(words[k]) or words[k] in _PIECE_SKIP_WORDS):
        k += 1
    if k >= len(words):
        return False
    base = os.path.basename(words[k])
    following = words[k + 1] if k + 1 < len(words) else None
    if base in ("cat", "tee"):
        return True
    if base == "gh":
        return following in _GH_DATA_SUBCOMMANDS
    if base == "git":
        return following == "commit"
    return False


def _line_opens_context(line):
    """True when a line may leave a group, substitution, pipe or continuation open for the next.

    Tests the whole line, not its ending: a trailing comment or a later word must not hide an
    opener (`$(`, `<(` and `>(` hold a `(`).
    """
    return line.rstrip().endswith(_CONTINUING_LINE_ENDINGS) or any(mark in line for mark in _NESTING_MARKS)


def _read_heredoc_delimiter(line, q):
    """Read a heredoc delimiter word at line[q:]. Returns (word, quoted, end) or None."""
    n = len(line)
    if q >= n:
        return None
    ch = line[q]
    if ch in "'\"":
        r = line.find(ch, q + 1)
        if r < 0 or not _HEREDOC_WORD.fullmatch(line[q + 1:r]):
            return None
        word, quoted, end = line[q + 1:r], True, r + 1
    else:
        quoted = ch == "\\"
        m = _HEREDOC_WORD.match(line, q + 1 if quoted else q)
        if not m:
            return None
        word, end = m.group(), m.end()
    if end < n and line[end] not in _HEREDOC_DELIMITER_END:
        return None
    return word, quoted, end


def _scan_operator_line(line, stack):
    """Read one command line the way bash reads quoting, for the heredoc pre-pass.

    `stack` carries open `$(` contexts across lines: each frame is
    [mode, paren_depth, is_substitution, command_position], mode one of u/d/s (unquoted,
    double-quoted, single-quoted). Returns (ops, pieces, stop, bad, pipe):

    ops     — heredoc operators outside quotes, as (dash, delimiter, quoted)
    pieces  — the command-word candidates: the line split at `;` `|` `||` `&` `&&` `(` `)`,
              a backtick, `$(` `<(` `>(` (a `&` inside `>&` `<&` `&>` is a redirection)
    stop    — the line cannot be read reliably (open quote, backslash continuation, `$'`,
              `((`, an unreadable delimiter): the pre-pass masks nothing from here on
    bad     — a command substitution sits where a command word goes, so its output is run
    pipe    — the line ends in a pipe, so the heredoc consumer's output feeds a later line
    """
    ops = []
    pieces = []
    cur = []
    state = {"stop": False, "bad": False, "pipe": False}
    n = len(line)
    p = 0

    def put(text):
        cur.append(text)
        if text.strip():
            state["pipe"] = False

    def flush():
        text = "".join(cur)
        cur.clear()
        if text.strip():
            pieces.append(text)

    def open_substitution():
        command_position = not "".join(cur).strip()
        if command_position:
            state["bad"] = True
        flush()
        stack.append(["u", 0, True, command_position])

    while p < n:
        frame = stack[-1]
        mode = frame[0]
        c = line[p]
        if mode == "s":
            put(c)
            if c == "'":
                frame[0] = "u"
            p += 1
            continue
        if mode == "d":
            if c == "\\" and p + 1 < n and line[p + 1] in '"\\$`':
                put(line[p:p + 2])
                p += 2
                continue
            if c == "$" and line.startswith("$(", p):
                if line.startswith("$((", p):
                    state["stop"] = True
                    break
                open_substitution()
                p += 2
                continue
            put(c)
            if c == '"':
                frame[0] = "u"
            p += 1
            continue
        if c == "\\":
            if p + 1 >= n:
                state["stop"] = True
                break
            put(line[p:p + 2])
            p += 2
            continue
        if c == "'" or c == '"':
            frame[0] = "s" if c == "'" else "d"
            put(c)
            p += 1
            continue
        if c == "$":
            if line.startswith("$'", p) or line.startswith("$((", p):
                state["stop"] = True
                break
            if line.startswith("$(", p):
                open_substitution()
                p += 2
                continue
            put(c)
            p += 1
            continue
        if c == "#" and (p == 0 or line[p - 1] in _COMMENT_PRECEDERS):
            break
        if c == "(":
            if line.startswith("((", p):
                state["stop"] = True
                break
            frame[1] += 1
            flush()
            p += 1
            continue
        if c == ")":
            if frame[1] > 0:
                frame[1] -= 1
            elif frame[2]:
                stack.pop()
            flush()
            p += 1
            continue
        if c == "`" or c == ";":
            flush()
            state["pipe"] = False
            p += 1
            continue
        if c == "|":
            flush()
            if line.startswith("||", p):
                state["pipe"] = False
                p += 2
            else:
                state["pipe"] = True
                p += 1
            continue
        if c == "&":
            if line.startswith("&&", p):
                flush()
                state["pipe"] = False
                p += 2
                continue
            if (p > 0 and line[p - 1] in "<>") or line.startswith("&>", p):
                put(c)
                p += 1
                continue
            flush()
            if not (p > 0 and line[p - 1] == "|"):
                state["pipe"] = False
            p += 1
            continue
        if c == "<" or c == ">":
            if line.startswith("<<<", p):
                put("<<<")
                p += 3
                continue
            if line.startswith("<(", p) or line.startswith(">(", p):
                open_substitution()
                p += 2
                continue
            if line.startswith("<<", p):
                q = p + 2
                dash = q < n and line[q] == "-"
                if dash:
                    q += 1
                while q < n and line[q] in " \t":
                    q += 1
                delimiter = _read_heredoc_delimiter(line, q)
                if delimiter is None:
                    state["stop"] = True
                    break
                word, quoted, end = delimiter
                if any(f[3] for f in stack):
                    state["bad"] = True
                ops.append((dash, word, quoted))
                put(line[p:end])
                p = end
                continue
        put(c)
        p += 1
    flush()
    if stack[-1][0] != "u":
        state["stop"] = True
    return ops, pieces, state["stop"], state["bad"], state["pipe"]


def _mask_heredoc_bodies(command):
    """Blank the body lines of heredocs that provably feed data to a program that does not run it.

    A body is blanked only when all hold (fail closed, no deeper parsing; otherwise it is scanned as
    always): the operator sits outside quotes; the body is terminated; every command word on the
    operator line is a data consumer (`cat`, `tee`, `gh issue|pr|release|api`, `git commit`); the
    operator line has no backtick, `{` or `(` and does not hand the consumer's output on (a trailing
    pipe) — except one `"$(cat <<'DELIM'` that follows consumers only, whose terminator is followed
    by a lone `)"` or `)` that ends the command; no earlier line (outside masked bodies) holds a
    backtick, `{`, `(` or `|` anywhere, or ends in a backslash or `&&`; the operator line carries
    exactly one heredoc operator; and an unquoted delimiter's body has no `$(`, backtick or
    trailing backslash (bash folds backslash-newline before it matches the terminator). Anything
    the scan cannot read, and any body that cannot be masked, stops masking for the rest of the
    command, never to resume after it. Terminator lines are kept.
    """
    if "\n" not in command:
        return command
    lines = command.split("\n")
    stack = [["u", 0, False, False]]
    i = 0
    opened = False
    checked = 0
    while i < len(lines):
        ops, pieces, stop, bad, pipe = _scan_operator_line(lines[i], stack)
        if stop:
            break
        while checked < i and not opened:
            opened = _line_opens_context(lines[checked])
            checked += 1
        substitution = _DATA_SUBSTITUTION.search(lines[i])
        plain_part = lines[i][:substitution.start()] if substitution else lines[i]
        if len(ops) > 1:
            break
        consumed = bool(ops) and not bad and not pipe and not opened and bool(pieces) and all(
            _piece_is_data_consumer(piece) for piece in pieces
        ) and not any(mark in plain_part for mark in ("`", "{", "("))
        following = i + 1
        for dash, word, quoted in ops:
            end = None
            for k in range(following, len(lines)):
                candidate = lines[k].lstrip("\t") if dash else lines[k]
                if candidate == word:
                    end = k
                    break
            if end is None:
                return "\n".join(lines)
            body = lines[following:end]
            maskable = consumed and (
                quoted or not any("$(" in ln or "`" in ln or ln.endswith("\\") for ln in body)
            )
            if maskable and substitution:
                closer = ')"' if substitution.group(1) else ")"
                after = lines[end + 1:]
                maskable = bool(after) and after[0].rstrip() == closer and not any(
                    ln.strip() for ln in after[1:]
                )
            if not maskable:
                break
            for k in range(following, end):
                lines[k] = ""
            following = end + 1
        else:
            i = following
            continue
        break
    return "\n".join(lines)


def _split_segments(command):
    """Split a command string into segments at unquoted boundaries."""
    command = _mask_heredoc_bodies(command)
    segments = []
    current = []
    i = 0
    n = len(command)
    in_single = False
    in_double = False

    def flush():
        seg = "".join(current).strip()
        if seg:
            segments.append(seg)
        current.clear()

    while i < n:
        ch = command[i]
        if in_single:
            current.append(ch)
            if ch == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            if ch == "\\" and i + 1 < n and command[i + 1] in '"\\$`':
                current.append(command[i:i + 2])
                i += 2
                continue
            current.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue
        if ch == "\\" and i + 1 < n and command[i + 1] != "\n":
            current.append(command[i:i + 2])
            i += 2
            continue
        if ch == "'":
            in_single = True
            current.append(ch)
            i += 1
            continue
        if ch == '"':
            in_double = True
            current.append(ch)
            i += 1
            continue
        if ch == "\\" and i + 1 < n and command[i + 1] == "\n":
            i += 2
            continue
        if ch == ";":
            flush()
            i += 1
            continue
        if ch == "\n":
            flush()
            i += 1
            continue
        if ch == "(":
            flush()
            i += 1
            continue
        if ch == ")":
            flush()
            i += 1
            continue
        if ch == "`":
            flush()
            i += 1
            continue
        if ch == "|":
            if i + 1 < n and command[i + 1] == "|":
                flush()
                i += 2
                continue
            flush()
            i += 1
            continue
        if ch == "&":
            if i + 1 < n and command[i + 1] == "&":
                flush()
                i += 2
                continue
            flush()
            i += 1
            continue
        current.append(ch)
        i += 1
    flush()
    return segments


def _tokenize_segment(segment):
    """Tokenize one segment, respecting quotes; strip surrounding quotes from tokens."""
    tokens = []
    current = []
    i = 0
    n = len(segment)
    in_single = False
    in_double = False

    def flush():
        if current:
            tok = "".join(current)
            if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "'\"":
                tok = tok[1:-1]
            tokens.append(tok)
            current.clear()

    while i < n:
        ch = segment[i]
        if in_single:
            current.append(ch)
            if ch == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            if ch == "\\" and i + 1 < n and segment[i + 1] in '"\\$`':
                current.append(segment[i:i + 2])
                i += 2
                continue
            current.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue
        if ch == "\\" and i + 1 < n:
            current.append(segment[i:i + 2])
            i += 2
            continue
        if ch in " \t":
            flush()
            i += 1
            continue
        if ch == "'":
            current.append(ch)
            in_single = True
            i += 1
            continue
        if ch == '"':
            current.append(ch)
            in_double = True
            i += 1
            continue
        current.append(ch)
        i += 1
    flush()
    return tokens


def _expand_clustered_flags(token, option_specs=None):
    """Return (flags, inline_value, expects_value).

    flags         — the option tokens this argument contributes, in order
    inline_value  — a value carried INSIDE the token (the cluster remainder following a
                    value-taking short option), or None
    expects_value — True when the final flag takes a value that was NOT supplied inline, so the
                    caller must consume the NEXT argv token as that value
    """
    if not token.startswith("-"):
        return ([token], None, False)
    if token.startswith("--"):
        expects = False
        if option_specs and "=" not in token:
            base = token.split("=", 1)[0]
            if base in option_specs and option_specs[base]:
                expects = True
            else:
                for key, need in option_specs.items():
                    if key.startswith("--") and key == base and need:
                        expects = True
                        break
        return ([token], None, expects)
    letters = token[1:]
    if not letters:
        return ([token], None, False)
    specs = option_specs or {}
    if not specs:
        if not letters.isalpha():
            return ([token], None, False)
        return (["-" + c for c in letters], None, False)
    flags = []
    i = 0
    while i < len(letters):
        c = letters[i]
        if not c.isalpha():
            return ([token], None, False)
        opt = f"-{c}"
        flags.append(opt)
        if opt in specs and specs[opt]:
            rest = letters[i + 1:]
            if rest:
                return (flags, rest, False)
            return (flags, None, True)
        i += 1
    return (flags, None, False)


def _option_value(tokens, idx):
    """Return (value, consumed) for a value-taking option at tokens[idx]."""
    tok = tokens[idx]
    if "=" in tok:
        return tok.split("=", 1)[1], 0
    if idx + 1 < len(tokens):
        return tokens[idx + 1], 1
    return None, 0


def _skip_git_globals(tokens):
    """Return index of subcommand after leading `git` and global options."""
    if not tokens or not _is_git_token(tokens[0]):
        return None
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--":
            return i + 1 if i + 1 < len(tokens) else None
        if not tok.startswith("-"):
            return i
        base = tok.split("=", 1)[0]
        if base in _GIT_GLOBAL_OPTS:
            i += 1
            continue
        if base in _GIT_GLOBAL_OPT_WITH_VALUE:
            _, consumed = _option_value(tokens, i)
            i += 1 + consumed
            continue
        i += 1
    return None


def _parse_git_invocation(tokens):
    """Parse one tokenized segment that starts with `git`. Returns dict or None."""
    sub_idx = _skip_git_globals(tokens)
    if sub_idx is None or sub_idx >= len(tokens):
        return None
    subcommand = tokens[sub_idx]
    rest = tokens[sub_idx + 1:]
    return {
        "subcommand": subcommand,
        "args": rest,
    }


def _strip_shell_prefixes(tokens):
    """Strip leading shell reserved words so `! git` and `{ git` are visible."""
    while tokens:
        tok = tokens[0]
        if tok in _SHELL_PREFIXES or tok.startswith(";;"):
            tokens = tokens[1:]
            continue
        if tok == "{":
            tokens = tokens[1:]
            continue
        if tok.startswith("{") and len(tok) > 1:
            tokens = [tok[1:]] + tokens[1:]
            continue
        if tok.startswith("(") and len(tok) > 1:
            tokens = [tok[1:]] + tokens[1:]
            continue
        break
    return tokens


def _iter_git_segments(command):
    """Yield parsed git invocations from each command-position segment."""
    if not isinstance(command, str):
        return
    for segment in _split_segments(command):
        tokens = _tokenize_segment(segment)
        if not tokens:
            continue
        start = 0
        while start < len(tokens) and "=" in tokens[start] and not tokens[start].startswith("="):
            key = tokens[start].split("=", 1)[0]
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                start += 1
                continue
            break
        tokens = _strip_shell_prefixes(tokens[start:])
        if tokens and _is_git_token(tokens[0]):
            parsed = _parse_git_invocation(tokens)
            if parsed is not None:
                yield parsed


def _args_before_separator(args):
    """Split args at bare `--`; return (pre_separator, has_separator, post_separator)."""
    for i, tok in enumerate(args):
        if tok == "--":
            return args[:i], True, args[i + 1:]
    return args, False, []


def _flag_present(args, short_flags, long_flags=(), option_specs=None):
    """True if any short/long flag appears before a bare `--`."""
    pre, _, _ = _args_before_separator(args)
    long_bases = {lf.split("=", 1)[0] for lf in long_flags}
    specs = option_specs or {}
    i = 0
    while i < len(pre):
        tok = pre[i]
        if not tok.startswith("-"):
            i += 1
            continue
        flags, _inline_value, expects_value = _expand_clustered_flags(tok, specs)
        for part in flags:
            if part in short_flags:
                return True
            base = part.split("=", 1)[0]
            if base in long_bases:
                return True
        if expects_value:
            i += 2
        else:
            i += 1
    return False


def _consume_options(pre_args, option_specs):
    """Walk pre-`--` args, returning set of matched flag letters/names and operand count."""
    matched = set()
    operands = []
    i = 0
    while i < len(pre_args):
        tok = pre_args[i]
        flags, _inline_value, expects_value = _expand_clustered_flags(tok, option_specs)
        if len(flags) == 1 and not flags[0].startswith("-"):
            operands.append(flags[0])
            i += 1
            continue
        advance = 1
        for part in flags:
            base = part.split("=", 1)[0]
            if part in option_specs:
                matched.add(part)
            elif base in option_specs:
                matched.add(base)
            elif part.startswith("--"):
                name = base[2:]
                found = False
                for key in option_specs:
                    if key.startswith("--") and key[2:] == name:
                        matched.add(key)
                        found = True
                        break
        if expects_value:
            advance = max(advance, 2)
        i += advance
    return matched, operands


_CHECKOUT_OPTS = {
    "-b": 1, "-B": 1, "-f": 0, "--force": 0,
    "--pathspec-from-file": 1, "--pathspec-from-file-nul": 0,
    "-u": 0, "--ours": 0, "--theirs": 0, "-q": 0, "--quiet": 0,
    "--recurse-submodules": 0, "--no-recurse-submodules": 0,
    "--progress": 0, "--no-progress": 0, "--overlay": 0, "--no-overlay": 0,
    "--ignore-skip-worktree-bits": 0,
    "--orphan": 1, "--conflict": 1,
}

_CLEAN_OPTS = {
    "-d": 0, "-f": 0, "-i": 0, "-n": 0, "--dry-run": 0,
    "-e": 1, "--exclude": 1,
    "-x": 0, "-X": 0, "-q": 0, "--quiet": 0,
}

_RESTORE_OPTS = {
    "-s": 1, "--source": 1,
    "-S": 0, "--staged": 0,
    "-W": 0, "--worktree": 0,
    "-q": 0, "--quiet": 0,
    "--ours": 0, "--theirs": 0,
    "-p": 0, "--patch": 0,
    "--overlay": 0, "--no-overlay": 0,
}


def _checkout_path_has_treeish_operand(args):
    """True when checkout-path reads paths from another tree-ish (`git checkout <rev> -- <paths>`)."""
    pre, has_sep, post = _args_before_separator(args)
    has_pathspec_from_file = _flag_present(
        args, (), ("--pathspec-from-file", "--pathspec-from-file-nul"), _CHECKOUT_OPTS,
    )
    _, operands = _consume_options(pre, _CHECKOUT_OPTS)
    if has_pathspec_from_file:
        return len(operands) >= 1
    if has_sep:
        return len(operands) > 0
    if len(operands) >= 2:
        return True
    return False


def _checkout_path_match(args):
    pre, has_sep, post = _args_before_separator(args)
    if has_sep:
        return True
    if _flag_present(args, (), ("--pathspec-from-file", "--pathspec-from-file-nul"), _CHECKOUT_OPTS):
        return True
    _, operands = _consume_options(pre, _CHECKOUT_OPTS)
    if len(operands) >= 2:
        return True
    if post:
        return True
    return False


def _single_checkout_operand(args):
    """Return the lone operand for `git checkout <one>`, or None."""
    pre, has_sep, post = _args_before_separator(args)
    if has_sep or post:
        return None
    if _flag_present(args, ("-b", "-B", "-f"), ("--force",), _CHECKOUT_OPTS):
        if _flag_present(args, ("-f",), ("--force",), _CHECKOUT_OPTS):
            return None
        if _flag_present(args, ("-b", "-B"), (), _CHECKOUT_OPTS):
            return None
    _, operands = _consume_options(pre, _CHECKOUT_OPTS)
    if len(operands) == 1:
        return operands[0]
    return None


def _restore_match(args):
    pre, _, _ = _args_before_separator(args)
    has_staged = _flag_present(args, ("-S",), ("--staged",), _RESTORE_OPTS)
    has_worktree = _flag_present(args, ("-W",), ("--worktree",), _RESTORE_OPTS)
    if has_staged and not has_worktree:
        return False
    return True


def _restore_has_source_treeish_operand(args):
    """True when restore reads paths from another tree-ish (`git restore --source=<rev> <paths>`)."""
    pre, _, _ = _args_before_separator(args)
    has_staged = _flag_present(args, ("-S",), ("--staged",), _RESTORE_OPTS)
    has_worktree = _flag_present(args, ("-W",), ("--worktree",), _RESTORE_OPTS)
    if has_staged and not has_worktree:
        return False
    return _flag_present(args, ("-s",), ("--source",), _RESTORE_OPTS)


def _clean_match(args):
    if _flag_present(args, (), ("--no-dry-run",), _CLEAN_OPTS):
        return True
    pre, _, _ = _args_before_separator(args)
    matched, _ = _consume_options(pre, _CLEAN_OPTS)
    if "-n" in matched or "--dry-run" in matched:
        return False
    return True


def _rm_force_match(args):
    return _flag_present(args, ("-f",), ("--force",))


def _force_match(args, option_specs=None):
    return _flag_present(args, ("-f",), ("--force",), option_specs)


def _switch_force_match(args):
    return _flag_present(
        args, ("-f",), ("--force", "--discard-changes"),
    )


def _reset_hard_match(args):
    return _flag_present(args, (), ("--hard",))


def _worktree_remove_force_match(args):
    if len(args) < 2 or args[0] != "remove":
        return False
    return _force_match(args[1:])


def _segment_action(parsed):
    """Classify one parsed git invocation."""
    sub = parsed["subcommand"]
    args = parsed["args"]
    if sub == "checkout":
        if _checkout_path_match(args):
            return "checkout-path"
        if _force_match(args, _CHECKOUT_OPTS):
            return "checkout-force"
        if _single_checkout_operand(args) is not None:
            return "checkout-single"
        return None
    if sub == "switch":
        if _switch_force_match(args):
            return "switch-force"
        return None
    if sub == "restore":
        if _restore_match(args):
            return "restore"
        return None
    if sub == "reset":
        if _reset_hard_match(args):
            return "reset-hard"
        return None
    if sub == "clean":
        if _clean_match(args):
            return "clean"
        return None
    if sub == "checkout-index":
        if _force_match(args):
            return "checkout-index-force"
        return None
    if sub == "rm":
        if _rm_force_match(args):
            return "rm-force"
        return None
    if sub == "worktree":
        if _worktree_remove_force_match(args):
            return "worktree-remove-force"
        return None
    return None


def _operand_is_existing_path(cwd, operand):
    if operand in (".", "./"):
        return True
    path = os.path.join(cwd, operand)
    return os.path.exists(path)


def _operand_resolves_as_commit(cwd, operand):
    result = _run_git(cwd, "rev-parse", "--verify", "--quiet", f"{operand}^{{commit}}")
    return result.returncode == 0


def _resolve_single_operand_checkout(cwd, operand):
    """Resolve single-operand checkout against the repository. Fail-closed."""
    git_dir = _find_git_dir(cwd)
    if git_dir == "indeterminate":
        return "indeterminate"
    if git_dir is None:
        return None
    if _operand_is_existing_path(cwd, operand):
        return "checkout-path"
    if not _operand_resolves_as_commit(cwd, operand):
        return "checkout-path"
    return None


def _segment_destructive_action(parsed, cwd=None):
    """Resolve one parsed git invocation to a destructive action, or None if safe."""
    action = _segment_action(parsed)
    if action == "checkout-single":
        operand = _single_checkout_operand(parsed["args"])
        if operand is None:
            return None
        if cwd is None:
            return "checkout-path"
        resolved = _resolve_single_operand_checkout(cwd, operand)
        if resolved == "checkout-path":
            return "checkout-path"
        if resolved == "indeterminate":
            return "checkout-path"
        return None
    return action


def segment_accounting(command, cwd=None):
    """Account for every command-position segment. Returns one record per segment:

    {"segment": <the segment text>, "kind": "safe"|"destructive"|"unaccounted", "action": <str|None>}

    kind is:
      "destructive"  — parsed as a git invocation whose subcommand is destructive AND whose
                       resolved action is not None. "action" carries that action name.
      "unaccounted"  — the crude scanner sees a destructive git mention in this segment, but the
                       segment was not parsed into a git invocation with a destructive subcommand.
                       "action" is None. THIS IS THE FAIL-CLOSED VERDICT.
      "safe"         — everything else: no destructive mention, or parsed and proven harmless.
    """
    if not isinstance(command, str):
        return []
    records = []
    for segment in _split_segments(command):
        tokens = _tokenize_segment(segment)
        if not tokens:
            continue
        start = 0
        while start < len(tokens) and "=" in tokens[start] and not tokens[start].startswith("="):
            key = tokens[start].split("=", 1)[0]
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                start += 1
                continue
            break
        tokens = _strip_shell_prefixes(tokens[start:])
        parsed = _parse_git_invocation(tokens) if tokens and _is_git_token(tokens[0]) else None
        mentions = _segment_mentions_destructive_git(segment)
        if _double_quoted_substitution_mention(segment):
            # Checked before the parsed-git branch: whatever the outer command parses as (a
            # branch-creating checkout included), the substitution inside it still runs.
            records.append({"segment": segment, "kind": "unaccounted", "action": None})
        elif parsed is not None and parsed["subcommand"] in _DESTRUCTIVE_SUBCOMMANDS:
            action = _segment_destructive_action(parsed, cwd)
            if action is not None:
                records.append({
                    "segment": segment,
                    "kind": "destructive",
                    "action": action,
                })
            else:
                records.append({"segment": segment, "kind": "safe", "action": None})
        elif mentions:
            records.append({"segment": segment, "kind": "unaccounted", "action": None})
        else:
            records.append({"segment": segment, "kind": "safe", "action": None})
    return records


def destructive_discard_actions(command, cwd=None):
    """Return every destructive-discard action across all command-position git segments."""
    if not isinstance(command, str):
        return []
    return [
        record["action"]
        for record in segment_accounting(command, cwd)
        if record["kind"] == "destructive"
    ]


def destructive_discard_action(command):
    """Return the first destructive-discard action, or None."""
    actions = destructive_discard_actions(command)
    return actions[0] if actions else None


_DESTRUCTIVE_WORD = re.compile(
    r"(?<![\w-])(?:" + "|".join(sorted(_DESTRUCTIVE_SUBCOMMANDS, key=len, reverse=True)) + r")(?![\w-])"
)


def _double_quoted_substitution_mention(text):
    """True when a double-quoted span holds `$(` or a backtick and the raw text has a destructive word.

    Bash runs a `$(...)` or backtick substitution inside double quotes, and no quote or boundary
    parsing of its body is trusted: the test is blunt. Any destructive subcommand word anywhere in
    the segment's raw text counts. Double-quoted prose with neither `$(` nor a backtick is not
    caught here.
    """
    if not isinstance(text, str) or not _DESTRUCTIVE_WORD.search(text):
        return False
    i = 0
    n = len(text)
    in_single = False
    in_double = False
    while i < n:
        ch = text[i]
        if in_single:
            in_single = ch != "'"
        elif in_double:
            if ch == "\\" and i + 1 < n and text[i + 1] in '"\\$`':
                i += 2
                continue
            if ch == "`" or text.startswith("$(", i):
                return True
            in_double = ch != '"'
        elif ch == "\\":
            i += 2 if i + 1 < n and text[i + 1] in "'\"\\" else 1
            continue
        elif ch == "'":
            in_single = True
        elif ch == '"':
            in_double = True
        i += 1
    return False


def _segment_mentions_destructive_git(text):
    """Crude per-segment scan for destructive git subcommand mentions.

    A double-quoted span holding `$(` or a backtick makes the segment a mention whenever its raw
    text holds any destructive subcommand word (see `_double_quoted_substitution_mention`).
    Double-quoted prose with neither stays allowed.
    """
    if not isinstance(text, str):
        return False
    if _double_quoted_substitution_mention(text):
        return True
    i = 0
    n = len(text)
    in_single = False
    in_double = False
    while i < n:
        ch = text[i]
        if in_single:
            if ch == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            if ch == "\\" and i + 1 < n and text[i + 1] in '"\\$`':
                i += 2
                continue
            if ch == '"':
                in_double = False
            i += 1
            continue
        if ch == "\\":
            # An escaped quote or backslash is literal text; any other escaped character is left
            # in view so `\git` still reads as a git word.
            i += 2 if i + 1 < n and text[i + 1] in "'\"\\" else 1
            continue
        if ch == "'":
            in_single = True
            i += 1
            continue
        if ch == '"':
            in_double = True
            i += 1
            continue
        if ch.isalpha() or ch == "-" or (ch == "." and i + 1 < n):
            start = i
            while i < n and not text[i].isspace() and text[i] not in ";|&()":
                i += 1
            word = text[start:i]
            if _is_git_token(word):
                j = i
                while j < n:
                    while j < n and text[j].isspace():
                        j += 1
                    if j >= n or text[j] in ";|&()":
                        break
                    tok_start = j
                    while j < n and not text[j].isspace() and text[j] not in ";|&()":
                        j += 1
                    token = text[tok_start:j]
                    if not token.startswith("-"):
                        if token in _DESTRUCTIVE_SUBCOMMANDS:
                            return True
                        break
                    base = token.split("=", 1)[0]
                    if base in _GIT_GLOBAL_OPT_WITH_VALUE and "=" not in token:
                        while j < n and text[j].isspace():
                            j += 1
                        if j >= n or text[j] in ";|&()":
                            break
                        tok_start = j
                        while j < n and not text[j].isspace() and text[j] not in ";|&()":
                            j += 1
                        continue
            continue
        i += 1
    return False


def mentions_destructive_git(command):
    """True when the command text plausibly invokes a destructive git subcommand.

    Deliberately CRUDE and over-inclusive: it exists to catch what the precise parser misses.
    Quote-aware only to the extent needed to not fire on `git commit -m 'git checkout -- f'`.
    """
    if not isinstance(command, str):
        return False
    return any(_segment_mentions_destructive_git(seg) for seg in _split_segments(command))


def _segment_has_unresolvable_target(tokens):
    """True when segment may act outside payload cwd."""
    if not tokens:
        return False
    start = 0
    while start < len(tokens) and "=" in tokens[start] and not tokens[start].startswith("="):
        key, _, val = tokens[start].partition("=")
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            if key in ("GIT_DIR", "GIT_WORK_TREE"):
                return True
            start += 1
            continue
        break
    if start < len(tokens) and tokens[start] in ("cd", "pushd"):
        return True
    tokens = tokens[start:]
    tokens = _strip_shell_prefixes(tokens)
    if tokens and _is_git_token(tokens[0]):
        i = 1
        while i < len(tokens):
            tok = tokens[i]
            if tok == "--":
                return False
            base = tok.split("=", 1)[0]
            if base in ("-C", "--git-dir", "--work-tree"):
                return True
            if not tok.startswith("-"):
                return False
            if base in _GIT_GLOBAL_OPTS:
                i += 1
                continue
            if base in _GIT_GLOBAL_OPT_WITH_VALUE:
                _, consumed = _option_value(tokens, i)
                i += 1 + consumed
                continue
            i += 1
    return False


def target_is_resolvable(command):
    """False when the command may act on a worktree other than the payload cwd."""
    if not isinstance(command, str):
        return True
    for segment in _split_segments(command):
        tokens = _tokenize_segment(segment)
        if _segment_has_unresolvable_target(tokens):
            return False
    return True


def _find_git_dir(cwd):
    """Nearest ancestor ``.git`` entry for cwd — delegates to the store_core chokepoint
    (issue #742) instead of hand-rolling a ``.git`` ancestor walk.

    Tri-state, never raises:
    - a truthy ancestor directory path when a ``.git`` entry is found (in cwd or an
      ancestor) — callers only test this for truthiness, never the value itself;
    - ``None`` when no ``.git`` entry exists anywhere up to the filesystem root
      (proven not a repository);
    - the string ``"indeterminate"`` when the probe could not complete (an
      untraversable path component, an unresolvable cwd) or the store_core
      chokepoint could not be imported or called. This module is a safety floor:
      an unknown answer must never collapse to ``None`` (which means "allow").
    """
    try:
        import store_core
        return store_core.git_dot_entry_ancestor(cwd)
    except Exception:
        return "indeterminate"


def _run_git(cwd, *args):
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return subprocess.run(
        ["git", "-C", cwd, *args],
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT,
        env=env,
    )


def _run_git_bytes(cwd, *args):
    """``_run_git`` without text decoding, for reading blob bytes."""
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return subprocess.run(
        ["git", "-C", cwd, *args],
        capture_output=True,
        timeout=_GIT_TIMEOUT,
        env=env,
    )


def _clean_has_flag(command, flag):
    for parsed in _iter_git_segments(command):
        if parsed["subcommand"] == "clean":
            pre, _, _ = _args_before_separator(parsed["args"])
            matched, _ = _consume_options(pre, _CLEAN_OPTS)
            if flag in matched:
                return True
    return False


def _checkout_path_treeish_in_command(command):
    """True when any parsed checkout-path segment carries a tree-ish operand."""
    if not isinstance(command, str):
        return False
    for parsed in _iter_git_segments(command):
        if parsed["subcommand"] != "checkout":
            continue
        if _checkout_path_match(parsed["args"]) and _checkout_path_has_treeish_operand(
            parsed["args"],
        ):
            return True
    return False


def _restore_source_treeish_in_command(command):
    """True when any parsed restore segment carries a --source tree-ish."""
    if not isinstance(command, str):
        return False
    for parsed in _iter_git_segments(command):
        if parsed["subcommand"] != "restore":
            continue
        if _restore_match(parsed["args"]) and _restore_has_source_treeish_operand(
            parsed["args"],
        ):
            return True
    return False


def _has_assume_unchanged_marked_files(cwd):
    """True when git ls-files -v reports assume-unchanged (lowercase h/s prefix)."""
    result = _run_git(cwd, "ls-files", "-v")
    if result.returncode != 0:
        return "indeterminate"
    for line in result.stdout.splitlines():
        if line and line[0] in ("h", "s"):
            return True
    return False


def _worktree_remove_target(command):
    """Resolve the worktree path from a `git worktree remove --force` invocation."""
    for parsed in _iter_git_segments(command):
        if parsed["subcommand"] != "worktree":
            continue
        args = parsed["args"]
        if not args or args[0] != "remove":
            continue
        rest = args[1:]
        pre, has_sep, post = _args_before_separator(rest)
        matched, operands = _consume_options(
            pre,
            {"-f": 0, "--force": 0},
        )
        if "-f" not in matched and "--force" not in matched:
            continue
        if has_sep and post:
            return post[0]
        if operands:
            return operands[-1]
    return None


_MERGE_OBJECT_ID_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_MERGE_BASE_MARKER_RE = re.compile(rb"^(\|{7,})(?: .*)?$")
_MERGE_SEPARATOR_RE = re.compile(rb"^={7,}$")
_MERGE_CHECKOUT_OPTS = frozenset({"--ours", "--theirs", "-q", "--quiet"})
_MERGE_RESTORE_OPTS = frozenset({"--ours", "--theirs", "-W", "--worktree", "-q", "--quiet"})
# Path-count ceiling for one merge-branch call (each path costs a git call); over it -> indeterminate.
_MERGE_PATH_LIMIT = 200


def _merge_side_form(action, command):
    """Parse a merge-side checkout/restore this branch judges, or None when it does not apply.

    Returns {"operands": [...], "source": bool}. Requires exactly `git checkout|restore ...` (no
    git globals, no VAR= prefix). Options are an allowlist, so --staged, --patch and
    --pathspec-from-file* never pass; a checkout carrying a tree-ish operand does not apply.
    """
    if action not in ("checkout-path", "restore") or not isinstance(command, str):
        return None
    subcommand = "checkout" if action == "checkout-path" else "restore"
    parsed = list(_iter_git_segments(command))
    if len(parsed) != 1 or parsed[0]["subcommand"] != subcommand:
        return None
    args = parsed[0]["args"]
    tokens = _tokenize_segment(command)
    if len(tokens) < 2 or not _is_git_token(tokens[0]) or tokens[1] != subcommand:
        return None
    if tokens[2:] != args:
        return None
    pre, has_sep, post = _args_before_separator(args)
    allowed = _MERGE_CHECKOUT_OPTS if subcommand == "checkout" else _MERGE_RESTORE_OPTS
    merge_side = False
    source = False
    operands = []
    i = 0
    while i < len(pre):
        tok = pre[i]
        if len(tok) > 1 and tok.startswith("-"):
            if tok in ("--ours", "--theirs"):
                merge_side = True
            elif subcommand == "restore" and tok in ("-s", "--source"):
                if i + 1 >= len(pre):
                    return None
                merge_side = source = True
                i += 1
            elif subcommand == "restore" and tok.startswith("--source="):
                merge_side = source = True
            elif tok not in allowed:
                return None
        else:
            operands.append(tok)
        i += 1
    if not merge_side:
        return None
    if subcommand == "checkout":
        if _checkout_path_has_treeish_operand(args):
            return None
        operands = list(post) if has_sep else operands
    else:
        operands = operands + list(post)
    if not operands:
        return None
    return {"operands": operands, "source": source}


def _merge_head_file(cwd):
    """The MERGE_HEAD file path when a merge is in progress, else None. Raises when git fails."""
    result = _run_git(cwd, "rev-parse", "--git-path", "MERGE_HEAD")
    if result.returncode != 0:
        raise OSError("git rev-parse --git-path MERGE_HEAD failed")
    path = result.stdout.rstrip("\n")
    if not path:
        raise OSError("git rev-parse --git-path MERGE_HEAD printed nothing")
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    return path if os.path.exists(path) else None


def _merge_state_valid(cwd, head_file):
    """True when MERGE_HEAD resolves to a commit and the file holds exactly one commit line."""
    verify = _run_git(cwd, "rev-parse", "-q", "--verify", "MERGE_HEAD^{commit}")
    if verify.returncode != 0:
        return False
    with open(head_file) as f:
        lines = [ln.strip() for ln in f.read().splitlines() if ln.strip()]
    return len(lines) == 1 and _MERGE_OBJECT_ID_RE.match(lines[0]) is not None


def _merge_commit_ids(cwd):
    """(HEAD, MERGE_HEAD) as full commit ids, or None when either does not resolve."""
    ids = []
    for ref in ("HEAD", "MERGE_HEAD"):
        result = _run_git(cwd, "rev-parse", "-q", "--verify", ref + "^{commit}")
        commit = result.stdout.strip() if result.returncode == 0 else ""
        if not _MERGE_OBJECT_ID_RE.match(commit):
            return None
        ids.append(commit)
    return tuple(ids)


def _merge_tree_id(cwd, ours, theirs):
    """Tree id of the recomputed merge (exit 0 clean, 1 conflicted), or None.

    The branches are passed as full commit ids so the conflict labels git writes are those ids,
    never text a file could hold.
    """
    result = _run_git(cwd, "merge-tree", "--write-tree", ours, theirs)
    if result.returncode not in (0, 1):
        return None
    first = result.stdout.splitlines()[0] if result.stdout.splitlines() else ""
    return first if _MERGE_OBJECT_ID_RE.match(first) else None


def _merge_index_entries(cwd, operands):
    """{repo-relative path: {stage: index mode string}} for the operands; None when one matches no entry."""
    entries = {}
    for operand in operands:
        result = _run_git(cwd, "ls-files", "--stage", "-z", "--full-name", "--", operand)
        if result.returncode != 0:
            raise OSError("git ls-files --stage failed")
        found = [entry for entry in result.stdout.split("\0") if entry]
        if not found:
            return None
        for entry in found:
            meta, _, path = entry.partition("\t")
            fields = meta.split()
            entries.setdefault(path, {})[int(fields[2])] = fields[0]
    return entries


def _merge_source_operands_exact(cwd, operands):
    """True when every operand is exactly one indexed file (no directory, glob or pathspec magic)."""
    result = _run_git(cwd, "rev-parse", "--show-prefix")
    if result.returncode != 0:
        return False
    prefix = result.stdout.rstrip("\n")
    for operand in operands:
        if operand.startswith(":") or any(ch in operand for ch in "*?[\\"):
            return False
        expected = os.path.normpath(prefix + operand).replace(os.sep, "/")
        if expected == "." or expected == ".." or expected.startswith("../"):
            return False
        listed = _run_git(cwd, "ls-files", "--stage", "-z", "--full-name", "--", operand)
        if listed.returncode != 0:
            return False
        paths = {e.partition("\t")[2] for e in listed.stdout.split("\0") if e}
        if paths != {expected}:
            return False
    return True


def _merge_has_base_markers(cwd):
    """True when ``merge.conflictStyle`` writes a base marker, False when it never does, None when unreadable.

    Only ``diff3`` and ``zdiff3`` write one; an absent value or ``merge`` writes none. Any other
    value, or a config read that fails, cannot be established (None).
    """
    result = _run_git(cwd, "config", "--get", "merge.conflictStyle")
    if result.returncode == 1 and not result.stdout.strip():
        return False
    if result.returncode != 0:
        return None
    style = result.stdout.rstrip("\n")
    if style == "merge":
        return False
    if style in ("diff3", "zdiff3"):
        return True
    return None


def _merge_content_matches(written, expected, ours, theirs, base_markers):
    """True when the worktree bytes equal the recomputed merge, up to conflict-marker labels.

    ``expected`` was written with the full commit ids ``ours`` and ``theirs`` as its labels, so a
    start or end marker line is recognised by that exact id, never by its look. Compared by
    position: equal line counts, each generated marker line matched by a worktree line carrying
    the same marker run (any label), every other line byte for byte. ``base_markers`` says
    whether the conflict style writes a base marker at all. An unexpected shape is a mismatch
    (fail closed).
    """
    written_lines = written.split(b"\n")
    expected_lines = expected.split(b"\n")
    if len(written_lines) != len(expected_lines):
        return False
    markers = _merge_generated_markers(
        expected_lines, ours.encode(), theirs.encode(), base_markers,
    )
    if markers is None:
        return False
    for index, (got, want) in enumerate(zip(written_lines, expected_lines)):
        run = markers.get(index)
        if run is None:
            if got != want:
                return False
        elif not got.startswith(run) or got[len(run):len(run) + 1] not in (b"", b" "):
            return False
    return True


def _merge_generated_markers(lines, ours, theirs, base_markers):
    """{line index: marker run} for the generated marker lines of ``lines``, or None.

    A generated conflict opens with exactly ``<<<<<<< <ours>`` and closes with exactly
    ``>>>>>>> <theirs>`` (either optionally followed by ``:<path>``). When ``base_markers`` is
    set (diff3/zdiff3), the first ``|||||||`` line after the open and before the first
    ``=======`` is generated too (any label); every other ``|||||||`` line, and every one when
    the style writes no base marker, is ordinary content. The ``=======`` separator carries no
    label and stays an ordinary line. An open that never closes, or opens again before
    closing, is an unexpected shape (None).
    """
    open_re = re.compile(rb"^(<{7,}) " + re.escape(ours) + rb"(?::.*)?$")
    close_re = re.compile(rb"^(>{7,}) " + re.escape(theirs) + rb"(?::.*)?$")
    markers = {}
    index = 0
    while index < len(lines):
        opened = open_re.match(lines[index])
        if opened is None:
            index += 1
            continue
        markers[index] = opened.group(1)
        base_open = base_markers
        index += 1
        while True:
            if index >= len(lines):
                return None
            closed = close_re.match(lines[index])
            if closed:
                markers[index] = closed.group(1)
                break
            if open_re.match(lines[index]):
                return None
            if _MERGE_SEPARATOR_RE.match(lines[index]):
                base_open = False
            elif base_open:
                base = _MERGE_BASE_MARKER_RE.match(lines[index])
                if base:
                    markers[index] = base.group(1)
                    base_open = False
            index += 1
        index += 1
    return markers


def _merge_tree_mode(cwd, tree, path):
    """Octal mode string of ``path`` in the merge tree, or None when unreadable."""
    result = _run_git(cwd, "ls-tree", "-z", tree, "--", path)
    if result.returncode != 0:
        return None
    meta, _, entry_path = result.stdout.rstrip("\0").partition("\t")
    fields = meta.split()
    return fields[0] if fields and entry_path == path else None


def _merge_side_probe(cwd, action, command):
    """Per-path probe for a merge-side checkout/restore during a merge in progress.

    Returns None when this branch does not apply (the whole-tree probe decides), else
    (state, count). Never raises: any error is ("indeterminate", 0).
    Axis: each named path is judged by whether it holds anything the builder wrote (refusal);
    every read this decision rests on that fails or cannot be established is a refusal.
    """
    try:
        form = _merge_side_form(action, command)
        if form is None:
            return None
        head_file = _merge_head_file(cwd)
        if head_file is None:
            return None
        if form["source"] and not _merge_source_operands_exact(cwd, form["operands"]):
            return None

        if not _merge_state_valid(cwd, head_file):
            return ("indeterminate", 0)
        entries = _merge_index_entries(cwd, form["operands"])
        if entries is None:
            return ("indeterminate", 0)
        if len(entries) > _MERGE_PATH_LIMIT:
            return ("indeterminate", 0)
        top = _run_git(cwd, "rev-parse", "--show-toplevel")
        if top.returncode != 0:
            return ("indeterminate", 0)
        top = top.stdout.rstrip("\n")

        tree = None
        base_markers = None
        risky = 0
        for path, modes in entries.items():
            if set(modes) == {0}:
                listed = _run_git(top, "--literal-pathspecs", "ls-files", "-v", "-z", "--", path)
                if listed.returncode != 0:
                    return ("indeterminate", 0)
                for entry in listed.stdout.split("\0"):
                    if entry and (entry[0].islower() or entry[0] == "S"):
                        return ("indeterminate", 0)
                diff = _run_git(
                    top, "--literal-pathspecs", "diff", "--quiet",
                    "--ignore-submodules=none", "--", path,
                )
                if diff.returncode == 1:
                    risky += 1
                    continue
                if diff.returncode != 0:
                    return ("indeterminate", 0)
                # core.filemode=false hides a mode-only edit from git diff: compare the bit here.
                index_mode = modes[0]
                if index_mode not in ("100644", "100755"):
                    return ("indeterminate", 0)
                worktree_mode = os.lstat(os.path.join(top, path)).st_mode
                if not stat.S_ISREG(worktree_mode):
                    return ("indeterminate", 0)
                if bool(worktree_mode & stat.S_IXUSR) != (index_mode == "100755"):
                    risky += 1
                continue

            worktree_path = os.path.join(top, path)
            if os.path.islink(worktree_path):
                return ("indeterminate", 0)
            if not os.path.lexists(worktree_path):
                continue
            if not os.path.isfile(worktree_path):
                return ("indeterminate", 0)
            if tree is None:
                ids = _merge_commit_ids(top)
                if ids is None:
                    return ("indeterminate", 0)
                ours, theirs = ids
                tree = _merge_tree_id(top, ours, theirs)
                if tree is None:
                    return ("indeterminate", 0)
            blob = _run_git_bytes(top, "cat-file", "blob", f"{tree}:{path}")
            if blob.returncode != 0:
                return ("indeterminate", 0)
            with open(worktree_path, "rb") as f:
                written = f.read()
            if base_markers is None:
                base_markers = _merge_has_base_markers(top)
                if base_markers is None:
                    return ("indeterminate", 0)
            if not _merge_content_matches(written, blob.stdout, ours, theirs, base_markers):
                risky += 1
                continue
            # Bytes alone miss a mode-only edit: the executable bit is the builder's too.
            # core.filemode does not matter: a checkout rewrites the file's mode either way.
            merged_mode = _merge_tree_mode(top, tree, path)
            if merged_mode is None:
                return ("indeterminate", 0)
            if bool(os.stat(worktree_path).st_mode & stat.S_IXUSR) != (merged_mode == "100755"):
                risky += 1
        if risky:
            return ("at-risk", risky)
        return ("clean", 0)
    except Exception:
        return ("indeterminate", 0)


def at_risk(cwd, action, command):
    """Read-only worktree probe. Returns (state, count). Never raises."""
    if not isinstance(cwd, str) or not cwd:
        return ("indeterminate", 0)
    if not os.path.isdir(cwd):
        return ("indeterminate", 0)

    probe_cwd = cwd
    if action == "worktree-remove-force":
        target = _worktree_remove_target(command)
        if target is None:
            return ("indeterminate", 0)
        probe_cwd = target if os.path.isabs(target) else os.path.join(cwd, target)
        if not os.path.isdir(probe_cwd):
            return ("indeterminate", 0)

    git_dir = _find_git_dir(probe_cwd)
    if git_dir == "indeterminate":
        return ("indeterminate", 0)
    if git_dir is None:
        return ("not-a-repo", 0)

    merge_state = _merge_side_probe(probe_cwd, action, command)
    if merge_state is not None:
        return merge_state

    try:
        checkout_path_treeish = (
            action == "checkout-path"
            and _checkout_path_treeish_in_command(command)
        )
        restore_source_treeish = (
            action == "restore"
            and _restore_source_treeish_in_command(command)
        )
        treeish_untracked_probe = checkout_path_treeish or restore_source_treeish
        if action in _TRACKED_ONLY_PROBE_ACTIONS and not treeish_untracked_probe:
            result = _run_git(
                probe_cwd, "status", "--porcelain",
                "--untracked-files=no", "--ignore-submodules=none",
            )
        elif action == "worktree-remove-force":
            # Ignored content is declared-reproducible build output; including it here deadlocks
            # the standard reap path on any worktree that has run the test suite, and the guard
            # exists to protect uncommitted work, not build artifacts. Tracked modifications
            # and non-ignored untracked files still deny.
            result = _run_git(
                probe_cwd, "status", "--porcelain",
                "--untracked-files=normal", "--ignore-submodules=none",
            )
        elif action in ("checkout-force", "switch-force"):
            # checkout-force / switch-force can overwrite ignored paths the target tracks.
            result = _run_git(
                probe_cwd, "status", "--porcelain",
                "--untracked-files=normal", "--ignore-submodules=none",
                "--ignored=matching",
            )
        elif action == "reset-hard":
            # reset --hard leaves ignored files alone; do not probe them (false denial).
            result = _run_git(
                probe_cwd, "status", "--porcelain",
                "--untracked-files=normal", "--ignore-submodules=none",
            )
        elif treeish_untracked_probe:
            result = _run_git(
                probe_cwd, "status", "--porcelain",
                "--untracked-files=normal", "--ignore-submodules=none",
            )
        elif action == "clean":
            clean_args = ["clean", "--dry-run", "-d"]
            if isinstance(command, str):
                if _clean_has_flag(command, "-x"):
                    clean_args.append("-x")
                if _clean_has_flag(command, "-X"):
                    clean_args.append("-X")
            result = _run_git(probe_cwd, *clean_args)
        else:
            return ("indeterminate", 0)

        if result.returncode != 0:
            return ("indeterminate", 0)
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        count = len(lines)
        if count > 0:
            return ("at-risk", count)
        if action in _TRACKED_ONLY_PROBE_ACTIONS and not treeish_untracked_probe:
            assume_state = _has_assume_unchanged_marked_files(probe_cwd)
            if assume_state == "indeterminate":
                return ("indeterminate", 0)
            if assume_state:
                return ("indeterminate", 0)
        return ("clean", 0)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ("indeterminate", 0)
    except Exception:
        return ("indeterminate", 0)


def refusal_message(action, count):
    """Verbatim user-read refusal when uncommitted changes would be discarded."""
    return _REFUSAL_TEMPLATE.format(action=action, count=count)


def indeterminate_message(action):
    """Verbatim fail-closed refusal when risk cannot be determined."""
    return _INDETERMINATE_TEMPLATE.format(action=action)


def unparsed_message():
    """Verbatim fail-closed refusal when the command could not be confidently parsed."""
    return _UNPARSED_TEMPLATE


def classify(command, cwd):
    """('deny'|'allow', reason) for a candidate Bash command. Fails closed on errors."""
    try:
        try:
            import mode_registry
            state = mode_registry.calibration_state(cwd)
        except Exception:
            state = "indeterminate"
        if state == "uncalibrated":
            return ("allow", "")

        records = segment_accounting(command, cwd)
        if any(record["kind"] == "unaccounted" for record in records):
            return ("deny", unparsed_message())
        actions = [record["action"] for record in records if record["kind"] == "destructive"]
        if not actions:
            return ("allow", "")

        if not target_is_resolvable(command):
            return ("deny", indeterminate_message(actions[0]))

        for record in records:
            if record["kind"] != "destructive":
                continue
            action = record["action"]
            risk_state, count = at_risk(cwd, action, record["segment"])
            if risk_state == "at-risk":
                return ("deny", refusal_message(action, count))
            if risk_state == "indeterminate":
                return ("deny", indeterminate_message(action))
            if risk_state not in ("clean", "not-a-repo"):
                return ("deny", indeterminate_message(action))

        return ("allow", "")
    except Exception:
        actions = destructive_discard_actions(command, cwd) if isinstance(command, str) else []
        action = actions[0] if actions else "discard"
        return ("deny", indeterminate_message(action))
