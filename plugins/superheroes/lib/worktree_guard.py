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
    "!", "then", "do", "else", "elif", "if", "while", "until", "(", ";;",
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
    "`GIT_DIR`/`GIT_WORK_TREE`). A lone `git checkout` sent to another repository "
    "can instead be written `git -C <dir> switch <branch>` or "
    "`git -C <dir> switch --detach <commit>`. "
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
    "the same kind as the one enclosing it, either backslash-escaped or nested inside a "
    "`$(...)` substitution. "
    "A heredoc with a quoted delimiter (`<<'EOF'`) that is the whole command and is fed to "
    "`cat >`/`cat >>`/`tee` writing a file, to `gh issue|pr ... --body-file -`, or to "
    "`git commit -F -`, or that is the whole `-m \"$(cat <<'EOF'` ... `)\"` / "
    "`--body \"$(cat <<'EOF'` ... `)\"` argument, is read as text; any other heredoc is "
    "read as command text. "
    "Next step: write the text with the Write tool and pass the file "
    "(`gh ... --body-file <path>`, `git commit -F <path>`), or re-issue an intended "
    "discard as a plain `git ...` command this guard can parse. "
    "If a discard is intended, note that this refusal does not depend on what your tree "
    "holds, so committing or stashing alone will not clear it. Keep the work you care "
    "about by committing or `git stash push -u` first, and revert a probe edit with an "
    "inverse Edit rather than a git discard."
)

_UNREADABLE_PROGRAM_TEMPLATE = (
    "superheroes worktree guard: this command runs a `bash`/`sh`/`zsh -c` or `eval` program "
    "this guard cannot read — the program holds a variable, a substitution, an escape, a "
    "nested quote, or a second level of `-c`/`eval` — so it is refused (fail-closed) "
    "whatever your tree holds. The guard reads such a program as commands only when it is "
    "one plain quoted string, one level in. "
    "Next step: run the program's commands as plain commands, or pass the program as one "
    "single-quoted string with no variable, substitution or nested shell. To keep work you "
    "care about, commit it or run `git stash push -u` first."
)

_GIT_TIMEOUT = 5

_TRACKED_ONLY_PROBE_ACTIONS = frozenset({
    "checkout-path", "restore", "rm-force", "checkout-index-force",
})


def _is_git_token(token):
    """True when token invokes git by basename (path-spelled or bare), not gitk/git-foo/mygit."""
    base = os.path.basename(token)
    return base == "git" or base == "git.exe"


_SAFE_CHARS = "A-Za-z0-9_@%+=:,./~"
_WORD = rf"""(?:[{_SAFE_CHARS}-]+|'[^']*'|"[^"$`\\]*")"""
_PATH = rf"[{_SAFE_CHARS}][{_SAFE_CHARS}-]*"
_DELIMITER = "[A-Za-z_][A-Za-z0-9_]*"
_HEREDOC_OPERATOR = re.compile(rf"""<<[ ]*(['"])({_DELIMITER})\1""")
_MESSAGE_SUBSTITUTION = re.compile(rf"""[ \t]*"\$\(cat <<(')({_DELIMITER})'[ \t]*$""")
_CAT_TO_FILE = re.compile(rf"[ \t]*cat[ \t]+>>?[ \t]*{_PATH}[ \t]*")
_TEE_TO_FILE = re.compile(rf"[ \t]*tee(?:[ \t]+-a)?[ \t]+{_PATH}(?:[ \t]*>[ \t]*/dev/null)?[ \t]*")
_WORD_LIST = re.compile(rf"[ \t]*(?:{_WORD}(?:[ \t]+{_WORD})*[ \t]*)?")


def _words_take_text(words, message):
    """True when the safe `words` are a `git commit` or `gh issue|pr` that reads the heredoc as text.

    Without `message`: the stdin flag is present (`-F -`, `--file -`, `--body-file -`).
    With it: the last word is the flag the `"$(cat <<'D'` substitution is the value of.
    """
    if words is None or len(words) < 2:
        return False
    gh = words[0] == "gh" and words[1] in ("issue", "pr")
    if not gh and words[:2] != ["git", "commit"]:
        return False
    if message:
        return words[-1] in (("--body", "-b") if gh else ("-m", "--message"))
    stdin_flags = (("--body-file", "-"), ("-F", "-")) if gh else (("-F", "-"), ("--file", "-"))
    return any(pair in stdin_flags for pair in zip(words, words[1:])) or (
        ("--body-file=-" if gh else "--file=-") in words
    )


def _mask_data_heredoc(command):
    """Blank the body lines of a command that is exactly one text-only heredoc shape.

    The shapes (first line holds the one `<<'D'` or `<<"D"`; the first line equal to `D` ends the
    body): `cat > f`, `cat >> f` or `tee [-a] f [> /dev/null]` writing a file; `gh issue|pr ...
    --body-file -` or `git commit -F -`; and `-m "$(cat <<'D'` / `--body "$(cat <<'D'` closed by a
    `)"` line. Nothing but blank lines may follow. Any other command is returned unchanged.
    """
    lines = command.split("\n")
    first = lines[0]
    if first.count("<<") != 1:
        return command
    message = _MESSAGE_SUBSTITUTION.search(first)
    operator = message or _HEREDOC_OPERATOR.search(first)
    if operator is None:
        return command
    before = first[:operator.start()]
    if message:
        taken = _words_take_text(_words(before), True)
    else:
        rest = before + " " + first[operator.end():]
        taken = (
            _CAT_TO_FILE.fullmatch(rest) or _TEE_TO_FILE.fullmatch(rest)
            or _words_take_text(_words(rest), False)
        )
    end = next((k for k in range(1, len(lines)) if lines[k] == operator.group(2)), None)
    if not taken or end is None:
        return command
    after = lines[end + 1:]
    if message:
        if not after or after[0].rstrip() != ')"':
            return command
        after = after[1:]
    if any(line.strip() for line in after):
        return command
    return "\n".join([first] + [""] * (end - 1) + lines[end:])


def _words(text):
    """The words of `text` when every word is a safe word, else None."""
    if not _WORD_LIST.fullmatch(text):
        return None
    return re.findall(_WORD, text)


def _split_segments(command):
    """Split a command string into segments at unquoted boundaries."""
    return [segment for segment, _ in _split_segments_with_ends(command)]


def _split_segments_with_ends(command):
    """Split into (segment, end) pairs; end is the unquoted boundary character that flushed the
    segment (`;`, newline, `(`, `)`, backtick, `|`, `&`), or "" at the end of the text."""
    command = _mask_data_heredoc(command)
    segments = []
    current = []
    i = 0
    n = len(command)
    in_single = False
    in_double = False

    def flush(end=""):
        seg = "".join(current).strip()
        if seg:
            segments.append((seg, end))
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
            current.append(ch)
            if ch == '"':
                in_double = False
            i += 1
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
            flush(";")
            i += 1
            continue
        if ch == "\n":
            flush("\n")
            i += 1
            continue
        if ch == "(":
            flush("(")
            i += 1
            continue
        if ch == ")":
            flush(")")
            i += 1
            continue
        if ch == "`":
            flush("`")
            i += 1
            continue
        if ch == "|":
            if i + 1 < n and command[i + 1] == "|":
                flush("|")
                i += 2
                continue
            flush("|")
            i += 1
            continue
        if ch == "&":
            if i + 1 < n and command[i + 1] == "&":
                flush("&")
                i += 2
                continue
            # An `&` that belongs to a redirection (`>&`, `<&`, `2>&1`, `&>`, `&>>`) is no boundary.
            if (i > 0 and command[i - 1] in "<>" and (i < 2 or command[i - 2] != "\\")) or (i + 1 < n and command[i + 1] == ">"):
                if (i + 1 < n and command[i + 1] == ">" and current
                        and not current[-1].isspace() and command[i - 1] not in "<>"):
                    current.append(" ")  # `&>` starts its own word, never glues to a flag
                current.append(ch)
                i += 1
                continue
            flush("&")
            i += 1
            continue
        current.append(ch)
        i += 1
    flush()
    return segments


def _tokenize_segment(segment, keep_quotes=False):
    """Tokenize one segment, respecting quotes; strip surrounding quotes from tokens unless
    keep_quotes, which returns each token raw."""
    tokens = []
    current = []
    i = 0
    n = len(segment)
    in_single = False
    in_double = False

    def flush():
        if current:
            tok = "".join(current)
            if not keep_quotes and len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "'\"":
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
            current.append(ch)
            if ch == '"':
                in_double = False
            i += 1
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


_EXECUTION_BUILTINS = frozenset({"exec", "command", "builtin"})

_WRAPPER_WORDS = frozenset({
    "timeout", "env", "nohup", "nice", "ionice", "sudo", "time", "stdbuf", "xargs", "setsid",
})

_REDIRECTION_WORD = re.compile(r"^[0-9]*(?:<|>|>>|<<<|<<-?|&>|&>>|>&|<&)")  # a quoted target with a space stays one raw token (`2>"/tmp/error log"`)
_REDIRECTION_OPERATOR = re.compile(r"^[0-9]*(?:<|>|>>|<<<|<<-?|&>|&>>|>&|<&)$")


def _redirection_width(tokens, i):
    """How many tokens a redirection at tokens[i] spans (0 when it is not one): the word
    itself, plus the next word when the operator has no attached target."""
    if i >= len(tokens) or not _REDIRECTION_WORD.match(tokens[i]):
        return 0
    if _REDIRECTION_OPERATOR.match(tokens[i]) and i + 1 < len(tokens):
        return 2
    return 1


def _drop_redirections(tokens, raw=None):
    """The tokens with every redirection word (and its detached target) removed. With `raw`
    (the index-aligned quote-keeping tokens) the decision is made on those, so a quoted
    `'>notes'` operand is kept."""
    raw = tokens if raw is None or len(raw) != len(tokens) else raw
    kept, i = [], 0
    while i < len(tokens):
        width = _redirection_width(raw, i)
        if width:
            i += width
            continue
        kept.append(tokens[i])
        i += 1
    return kept


def _command_tokens(tokens):
    """The shared normalizer: (assignment_keys, tokens) once leading shell prefixes,
    redirection words and `NAME=value` assignments are stripped, alternating until none moves
    (so `then LC_ALL=C bash -c ...` and `2>/dev/null bash -c ...` reach `bash`)."""
    keys = []
    while True:
        stripped = _strip_shell_prefixes(tokens)
        start = 0
        while start < len(stripped):
            width = _redirection_width(stripped, start)
            if width:
                start += width
                continue
            if not ("=" in stripped[start] and not stripped[start].startswith("=")):
                break
            key = stripped[start].split("=", 1)[0]
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                break
            keys.append(key)
            start += 1
        rest = stripped[start:]
        if rest == tokens:
            return keys, tokens
        tokens = rest


def _iter_git_segments(command):
    """Yield parsed git invocations from each command-position segment."""
    if not isinstance(command, str):
        return
    for segment in _split_segments(command):
        tokens = _tokenize_segment(segment)
        if not tokens:
            continue
        _, tokens = _command_tokens(_drop_redirections(tokens, _tokenize_segment(segment, keep_quotes=True)))
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
    "--orphan": 1, "--conflict": 1, "--detach": 0,
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
    if _flag_present(args, (), ("--detach",), _CHECKOUT_OPTS):  # git takes no path after --detach
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


_OTHER_REPO_OPTS = ("--git-dir", "--work-tree")


def _targets_other_repo(keys, tokens):
    """True when a git segment names another repository or work tree (no cwd resolves it)."""
    opts = tokens[1:_skip_git_globals(tokens) or 1]
    return "GIT_DIR" in keys or "GIT_WORK_TREE" in keys or any(
        o.split("=", 1)[0] in _OTHER_REPO_OPTS or o == "-C" and v not in (".", "./")
        for o, v in zip(opts, opts[1:] + [None]))


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


def _plain_word(raw):
    """A raw token without its surrounding quotes."""
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        return raw[1:-1]
    return raw


# Axis: a quoted bash|sh|zsh -c or eval program is checked as commands one level in; an unreadable one is refused.
def _shell_program(raw_tokens):
    """The `bash|sh|zsh -c` or `eval` program in normalized raw tokens: None when the segment is
    not a program shape, ("unreadable", None), or ("program", <text>)."""
    if not raw_tokens:
        return None
    if _plain_word(raw_tokens[0]) == "eval":
        args = _drop_redirections(raw_tokens[1:])
        if args and _plain_word(args[0]) == "--":
            args = args[1:]
        if not args or not all(re.fullmatch(_WORD, arg) for arg in args):
            return ("unreadable", None)
        joined = " ".join(_plain_word(arg) for arg in args)
        if "`" in joined or "$(" in joined or "\\" in joined:
            return ("unreadable", None)
        return ("program", joined)
    if os.path.basename(_plain_word(raw_tokens[0])) not in ("bash", "sh", "zsh"):
        return None
    saw_c = False
    ended_options = False
    i = 1
    while i < len(raw_tokens):
        width = _redirection_width(raw_tokens, i)
        if width:
            i += width
            continue
        tok = _plain_word(raw_tokens[i])
        if tok == "--":
            ended_options = True
            i += 1
            break
        takes_value = tok in ("--rcfile", "--init-file") or (
            len(tok) > 1 and tok[0] in "-+" and tok[1] != "-" and ("o" in tok or "O" in tok))
        if takes_value and i + 1 < len(raw_tokens) and (
                not re.fullmatch(_WORD, raw_tokens[i + 1]) or "$" in raw_tokens[i + 1]):
            return ("unreadable", None)
        if tok in ("--rcfile", "--init-file"):
            i += 2
            continue
        if tok.startswith("--"):
            i += 1
            continue
        if len(tok) > 1 and tok[0] in "-+":
            # An expansion, redirection or attached `-o` value inside an option word hides `-c`.
            if not re.fullmatch(r"[-+][A-Za-z]+", tok) or re.search("[oO].", tok):
                return ("unreadable", None)
            saw_c = saw_c or "c" in tok
            i += 2 if ("o" in tok or "O" in tok) else 1
            continue
        break
    if i >= len(raw_tokens):
        return ("unreadable", None) if saw_c else None
    if not saw_c:
        # `--` ends options, so what follows is a script path, never `-c`.
        if ended_options:
            return None
        # A script-file operand is not read; a bare leading expansion could itself be `-c`,
        # and an unreadable word followed by a `c` cluster could hide where `-c` sits.
        if raw_tokens[i][:1] in ("$", "`"):
            return ("unreadable", None)
        # A quoted word that is exactly one expansion (`"$OPT"`) is just as able to be `-c`.
        if re.fullmatch(r"\$(?:\w+|\{[^}]*\}|[@*#?$!0-9-])", _plain_word(raw_tokens[i])):
            return ("unreadable", None)
        if any(c in raw_tokens[i] for c in "$`") and any(
                len(t) > 1 and t[0] in "-+" and not t.startswith("--") and "c" in t
                for t in (_plain_word(r) for r in raw_tokens[i + 1:])):
            return ("unreadable", None)
        return None
    if not re.fullmatch(_WORD, raw_tokens[i]):
        return ("unreadable", None)
    program = _plain_word(raw_tokens[i])
    # Operands after the program are its positional parameters: `exec "$@"` would run them.
    if i + 1 < len(raw_tokens) and "$" in program:
        return ("unreadable", None)
    # A substitution inside the program hides the command it produces from the one-level read.
    if "`" in program or "$(" in program or "\\" in program:
        return ("unreadable", None)
    return ("program", program)


def _only_wrapper_words(before):
    """Whether every raw token is a redirection, a `NAME=value` assignment, a shell prefix or
    execution builtin, a known wrapper word, or an option/bare-number argument of one."""
    i = 0
    while i < len(before):
        width = _redirection_width(before, i)
        if width:
            i += width
            continue
        plain = _plain_word(before[i])
        # A wrapper or execution builtin owns every later word up to the shell word (option
        # operands such as `env -u FOO` or `exec -a name`), so the rest is its argument.
        if (not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", plain) and plain not in _SHELL_PREFIXES
                and (plain in _EXECUTION_BUILTINS
                     or os.path.basename(plain) in _WRAPPER_WORDS)):
            return True
        if (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", plain)
                or plain in _SHELL_PREFIXES
                or plain[:1] in ("-", "+") or plain.isdigit()):
            i += 1
            continue
        return False
    return True


def _hidden_shell_c(raw_tokens):
    """Fail-closed backstop: a bare bash|sh|zsh word with a later short `-`/`+` cluster holding
    `c`, in a segment `_shell_program` did not read. It fires only when the shell word is not
    the segment's command word and everything before it is a redirection, an assignment, a
    known wrapper word or an option/number argument of one (a wrapper in front)."""
    command_index = len(raw_tokens) - len(_command_tokens(raw_tokens)[1])
    for k, raw in enumerate(raw_tokens):
        if os.path.basename(_plain_word(raw)) not in ("bash", "sh", "zsh", "eval"):
            continue
        if k == command_index or not _only_wrapper_words(raw_tokens[:k]):
            continue
        if _shell_program(raw_tokens[k:]) is not None:
            return True
    return False


def _inner_git_unreadable(tokens, parsed):
    """Whether a git segment inside a program hides its action: an expansion or escape in the
    subcommand word, or in any word once the subcommand is destructive (or unparsed)."""
    hidden = "$`\\"
    if parsed is None or parsed["subcommand"] in _DESTRUCTIVE_SUBCOMMANDS:
        return any(c in tok for tok in tokens[1:] for c in hidden)
    return any(c in parsed["subcommand"] for c in hidden)


def segment_accounting(command, cwd=None, _depth=0):
    """Account for every command-position segment. Returns one record per segment:

    {"segment": <the segment text>, "kind": "safe"|"destructive"|"unaccounted"|"unreadable-program",
     "action": <str|None>}

    A `bash|sh|zsh -c` or `eval` program is accounted one level in (its records replace the
    segment's), via _depth.

    kind is:
      "unreadable-program" — the segment runs a `-c`/`eval` program the guard cannot read (a
                       variable, substitution, escape, nested quote, a second level, or a cut
                       at a substitution boundary). "action" is None. FAIL-CLOSED, like
                       "unaccounted".
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
    for segment, end in _split_segments_with_ends(command):
        tokens = _tokenize_segment(segment)
        if not tokens:
            continue
        all_raw = _tokenize_segment(segment, keep_quotes=True)
        _, raw_tokens = _command_tokens(all_raw)
        shape = _shell_program(raw_tokens)
        if shape is None and _depth <= 1 and _hidden_shell_c(all_raw):
            shape = ("unreadable", None)
        if shape is not None:
            if (shape[0] == "unreadable" or end in ("`", "(") or _depth >= 1
                    or any("$(" in raw or "`" in raw for raw in all_raw)):
                records.append({"segment": segment, "kind": "unreadable-program", "action": None})
            else:
                records.extend(segment_accounting(shape[1], cwd, _depth + 1))
            continue
        keys, tokens = _command_tokens(_drop_redirections(tokens, all_raw))
        parsed =_parse_git_invocation(tokens) if tokens and _is_git_token(tokens[0]) else None
        wrapped = (core := _skip_builtins(tokens)) != tokens and core and _is_git_token(core[0]) and (_parse_git_invocation(core) or {}).get("subcommand") in _DESTRUCTIVE_SUBCOMMANDS
        mentions = wrapped or _segment_mentions_destructive_git(segment)
        # A raw word still holding < or > outside its quoted spans after the real redirections
        # went hides what Bash consumes.
        attached = (mentions or parsed is not None) and (any(
            len(re.findall("[<>]+", re.sub(r"'[^']*'|\"[^\"]*\"", "", w))) > 1 for w in all_raw) or any(
            re.search("[<>]", re.sub(r"'[^']*'|\"[^\"]*\"", "", w)) for w in _drop_redirections(all_raw)))
        if _depth >= 1 and (attached or wrapped or tokens and (
                any(c in tokens[0] for c in "$`\\")
                or (os.path.basename(tokens[0]) in _WRAPPER_WORDS | _EXECUTION_BUILTINS
                    and any(c in tok for tok in tokens[1:] for c in "$`\\"))
                or (_is_git_token(tokens[0]) and _inner_git_unreadable(tokens, parsed)))):
            records.append({"segment": segment, "kind": "unreadable-program", "action": None})
            continue
        if parsed is not None and parsed["subcommand"] in _DESTRUCTIVE_SUBCOMMANDS and not attached:
            action = _segment_destructive_action(parsed, None if _targets_other_repo(keys, tokens) else cwd)
            if action is not None:
                records.append({
                    "segment": segment,
                    "kind": "destructive",
                    "action": action,
                })
            else:
                records.append({"segment": segment, "kind": "safe", "action": None})
        elif mentions or attached:
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


def _segment_mentions_destructive_git(text):
    """Crude per-segment scan for destructive git subcommand mentions."""
    if not isinstance(text, str):
        return False
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
            if ch == '"':
                in_double = False
            i += 1
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


def _skip_builtins(tokens, wide=True):
    """Detection only: past exec/command/builtin (wide: env) words; wide never parses an option's value, returns the first later git suffix naming a discard."""
    while tokens and (tokens[0] in _EXECUTION_BUILTINS or wide and tokens[0] == "env"):
        builtin, tokens = tokens[0], _command_tokens(tokens[1:])[1] if wide else tokens[1:]
        while tokens and tokens[0].startswith("-"):
            if builtin == "command" and ("v" in tokens[0] or "V" in tokens[0]):
                return []
            if wide:  # an option's value is never parsed: a later git word naming a discard is the command
                gits = [tokens[i:] for i in range(1, len(tokens)) if _is_git_token(tokens[i])]
                return next((g for g in gits if (_parse_git_invocation(g) or {}).get("subcommand")
                             in _DESTRUCTIVE_SUBCOMMANDS), tokens[1:])
            tokens = tokens[1:]
    return tokens


def _segment_has_unresolvable_target(tokens):
    """True when segment may act outside payload cwd."""
    keys, tokens = _command_tokens(tokens)
    if "GIT_DIR" in keys or "GIT_WORK_TREE" in keys:
        return True
    tokens = _skip_builtins(tokens, wide=False)
    if tokens and tokens[0] in ("cd", "pushd"):
        return True
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


def target_is_resolvable(command, _depth=0):
    """False when the command may act on a worktree other than the payload cwd; a readable
    `bash|sh|zsh -c` or `eval` program is read one level in."""
    if not isinstance(command, str):
        return True
    for segment, end in _split_segments_with_ends(command):
        _, raw_tokens = _command_tokens(_tokenize_segment(segment, keep_quotes=True))
        shape = _shell_program(raw_tokens)
        if (shape is not None and shape[0] == "program" and _depth < 1
                and end not in ("`", "(")
                and not target_is_resolvable(shape[1], _depth + 1)):
            return False
        tokens = _drop_redirections(_tokenize_segment(segment), _tokenize_segment(segment, keep_quotes=True))
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
_MERGE_CHECKOUT_OPTS = frozenset({"--ours", "--theirs", "-q", "--quiet"})
_MERGE_RESTORE_OPTS = frozenset({"--ours", "--theirs", "-W", "--worktree", "-q", "--quiet"})
# Path-count ceiling for one merge-branch call (each path costs a git call); over it -> indeterminate.
_MERGE_PATH_LIMIT = 200


def _merge_side_form(action, command):
    """Parse a merge-side checkout/restore this branch judges, or None when it does not apply.

    Returns {"operands": [...], "source": bool}. Requires exactly `git checkout|restore ...` (no
    git globals, no VAR= prefix). Options are an allowlist, so --staged, --patch and
    --pathspec-from-file* never pass. With --ours/--theirs git takes no tree-ish, so without a
    ``--`` every checkout operand is a path; a checkout naming a tree-ish before ``--`` does
    not apply.
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
        if has_sep:
            if operands:
                return None
            operands = list(post)
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


def _merge_content_matches(written, expected, ours, theirs, resolve):
    """True when the worktree bytes equal the recomputed merge, up to conflict-marker labels.

    ``expected`` was written with the full commit ids ``ours`` and ``theirs`` as its labels, so a
    start or end marker line is recognised by that exact id, never by its look. Compared by
    position: equal line counts, each generated marker line matched by a worktree line carrying
    the same marker run and a label that ``resolve`` maps to the commit the recomputed line names
    (open: ``ours``, close: ``theirs``), every other line byte for byte. The label is the whole
    text after the run and one space: it is accepted when it resolves as a whole, or as
    ``<name>:<suffix>`` when ``<name>`` resolves and ``<suffix>`` equals the recomputed line's own
    ``:<suffix>`` byte for byte (only a rename conflict carries one). A label that is empty,
    does not resolve or resolves elsewhere, or carries any other suffix, is a mismatch, so text
    appended to a marker line is never taken for git's own label. One trailing carriage return is ignored on a marker line, but
    the recomputed line and the worktree line must both carry it or both lack it. A ``|||||||``
    base-marker line is not relaxed: git writes it identically in the real merge and in the
    recomputed one (the label is an abbreviated base id), so it is compared like any other line.
    An unexpected shape is a mismatch (fail closed).
    """
    written_lines = written.split(b"\n")
    expected_lines = expected.split(b"\n")
    if len(written_lines) != len(expected_lines):
        return False
    markers = _merge_generated_markers(expected_lines, ours.encode(), theirs.encode())
    if markers is None:
        return False
    for index, (got, want) in enumerate(zip(written_lines, expected_lines)):
        marker = markers.get(index)
        if marker is None:
            if got != want:
                return False
            continue
        kind, run, suffix = marker
        if got.endswith(b"\r") != want.endswith(b"\r"):
            return False
        got = got[:-1] if got.endswith(b"\r") else got
        if not got.startswith(run + b" "):
            return False
        label = got[len(run) + 1:]
        try:
            label = label.decode("utf-8")
            suffix = suffix.decode("utf-8")
        except UnicodeDecodeError:
            return False
        commit = ours if kind == "open" else theirs
        if resolve(label) == commit:
            continue
        # ``<name>:<suffix>``: the suffix is git's own only when the recomputed line carries the
        # same one (a rename conflict); a suffix is never discarded unchecked.
        name, colon, tail = label.partition(":")
        if not (colon and suffix and tail == suffix[1:] and resolve(name) == commit):
            return False
    return True


def _merge_generated_markers(lines, ours, theirs):
    """{line index: (kind, marker run, ``:<path>`` suffix or b"")} for the marker lines, or None.

    A generated conflict opens with exactly ``<<<<<<< <ours>`` and closes with exactly
    ``>>>>>>> <theirs>`` (either optionally followed by ``:<path>``, and by one carriage return
    when the merged file uses CRLF). Only those two lines may differ in label; the ``|||||||``
    base marker and the ``=======`` separator stay ordinary lines. An open that never closes,
    or opens again before closing, is an unexpected shape (None).
    """
    open_re = re.compile(rb"^(<{7,}) " + re.escape(ours) + rb"((?::[^\r]*)?)\r?$")
    close_re = re.compile(rb"^(>{7,}) " + re.escape(theirs) + rb"((?::[^\r]*)?)\r?$")
    markers = {}
    index = 0
    while index < len(lines):
        opened = open_re.match(lines[index])
        if opened is None:
            index += 1
            continue
        markers[index] = ("open", opened.group(1), opened.group(2))
        index += 1
        while True:
            if index >= len(lines):
                return None
            closed = close_re.match(lines[index])
            if closed:
                markers[index] = ("close", closed.group(1), closed.group(2))
                break
            if open_re.match(lines[index]):
                return None
            index += 1
        index += 1
    return markers


def _merge_label_resolver(cwd):
    """A function mapping a marker label to the commit id it names (or None), cached per call."""
    cache = {}

    def resolve(label):
        if label in cache:
            return cache[label]
        commit = None
        if label and not label.startswith("-"):
            result = _run_git(cwd, "rev-parse", "--verify", "--quiet", label + "^{commit}")
            out = result.stdout.strip() if result.returncode == 0 else ""
            commit = out if _MERGE_OBJECT_ID_RE.match(out) else None
        cache[label] = commit
        return commit

    return resolve


def _merge_checkout_transforms(cwd, paths):
    """True when git may rewrite a path's bytes between index and worktree, or that cannot be read.

    ``text``, ``eol``, ``ident``, ``filter``, ``working-tree-encoding`` and the legacy ``crlf``
    attributes, any ``core.eol``, and any ``core.autocrlf`` git does not parse as false (``true``,
    ``yes``, ``1``, ``input``, ...), can make a clean ``git diff`` hide an edit.
    """
    autocrlf = _run_git(cwd, "config", "--type=bool", "--get", "core.autocrlf")
    if autocrlf.returncode != 1 and (
        autocrlf.returncode != 0 or autocrlf.stdout.strip() != "false"
    ):
        return True
    eol = _run_git(cwd, "config", "--get", "core.eol")
    if eol.returncode != 1:
        return True
    attrs = _run_git(
        cwd, "check-attr", "-z", "text", "eol", "ident", "filter", "working-tree-encoding", "crlf",
        "--", *paths,
    )
    if attrs.returncode != 0:
        return True
    fields = attrs.stdout.split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    if len(fields) != len(paths) * 18:
        return True
    return any(value != "unspecified" for value in fields[2::3])


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
        import store_core
        top = store_core.repo_root(cwd)
        if not isinstance(top, str) or not top or not os.path.isdir(top):
            return ("indeterminate", 0)
        # store_core strips all surrounding whitespace, so a root whose name ends in a space
        # resolves to a sibling: the root must contain cwd and be a checkout root itself.
        real_cwd = os.path.realpath(cwd)
        if os.path.commonpath([top, real_cwd]) != top:
            return ("indeterminate", 0)
        dot_git = os.path.join(top, ".git")
        if not (os.path.isdir(dot_git) or os.path.isfile(dot_git)):
            return ("indeterminate", 0)
        if _merge_checkout_transforms(top, list(entries)):
            return ("indeterminate", 0)

        tree = None
        resolve = _merge_label_resolver(top)
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
                    top, "--literal-pathspecs", "diff", "--no-ext-diff", "--no-textconv",
                    "--quiet", "--ignore-submodules=none", "--", path,
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
            if not _merge_content_matches(
                written, blob.stdout, ours, theirs, resolve,
            ):
                risky += 1
                continue
            # Bytes alone miss a mode-only edit: the executable bit is the builder's too.
            # core.filemode does not matter: a checkout rewrites the file's mode either way.
            merged_mode = _merge_tree_mode(top, tree, path)
            if merged_mode not in ("100644", "100755"):
                # A symlink (120000) or gitlink (160000) resolution is a file-type choice.
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


def unreadable_program_message():
    """Verbatim fail-closed refusal when a `-c`/`eval` program could not be read."""
    return _UNREADABLE_PROGRAM_TEMPLATE


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
        if any(record["kind"] == "unreadable-program" for record in records):
            return ("deny", unreadable_program_message())
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
