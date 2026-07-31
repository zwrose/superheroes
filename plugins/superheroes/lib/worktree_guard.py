#!/usr/bin/env python3
"""PreToolUse(Bash) worktree guard — deny destructive git discard on dirty trees (#682).

Best-effort classifier over literal `git` invocations at command position in Bash command
text. Does not resolve shell aliases, git aliases, or dynamic shell expansion.

Stdlib-only.
"""
import os
import re
import subprocess

# Git global options consumed before the subcommand (value-taking forms accept =value).
_GIT_GLOBAL_OPTS = frozenset({
    "-p", "--paginate", "--no-pager", "--no-optional-locks",
    "--literal-pathspecs", "--bare",
    "--icase-pathspecs", "--glob-pathspecs", "--noglob-pathspecs",
})

_PATHSPEC_MODE_GLOBALS = frozenset({
    "--literal-pathspecs", "--icase-pathspecs", "--glob-pathspecs", "--noglob-pathspecs",
})

WHOLE_TREE = object()
_GIT_GLOBAL_OPT_WITH_VALUE = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
}

_DESTRUCTIVE_SUBCOMMANDS = frozenset({
    "checkout", "checkout-index", "restore", "reset", "clean", "switch", "rm", "worktree",
})

_SHELL_PREFIXES = frozenset({
    "!", "then", "do", "else", "elif", "(", ";;",
})

_REFUSAL_TEMPLATE = (
    "superheroes worktree guard: this `git {action}` would discard {count} uncommitted "
    "change(s) in this worktree, and git keeps no copy of them. This is the checkout-revert "
    "wipe (issue #682): the command that reverts a probe edit also erases a prior order's "
    "uncommitted delivery at the same path. Recover the intent instead — commit the work "
    "first, `git stash -u` it (add `-a` to include ignored files; in a conflicted tree "
    "`git add` the unmerged paths first), or revert a probe edit with an inverse Edit "
    "rather than a git discard."
)

_INDETERMINATE_TEMPLATE = (
    "superheroes worktree guard: could not determine whether this `git {action}` would "
    "destroy uncommitted work — it may target another worktree, or the repository could "
    "not be inspected — so it is refused (fail-closed). Commit or `git stash -u` your "
    "work first, or revert a probe edit with an inverse Edit rather than a git discard."
)

_UNPARSED_TEMPLATE = (
    "superheroes worktree guard: could not confidently parse this command's git "
    "invocation — it may include a destructive discard subcommand — so it is refused "
    "(fail-closed) rather than risk wiping uncommitted work. Commit or `git stash -u` "
    "your work first, or revert a probe edit with an inverse Edit rather than a git "
    "discard."
)

_GIT_TIMEOUT = 5

_TRACKED_ONLY_PROBE_ACTIONS = frozenset({
    "checkout-path", "restore", "rm-force", "checkout-index-force",
})


def _is_git_token(token):
    """True when token invokes git by basename (path-spelled or bare), not gitk/git-foo/mygit."""
    base = os.path.basename(token)
    return base == "git" or base == "git.exe"


def _split_segments(command):
    """Split a command string into segments at unquoted boundaries."""
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

_RM_OPTS = {
    "-f": 0, "--force": 0,
    "-r": 0, "--cached": 0,
    "-q": 0, "--quiet": 0,
}

_SWITCH_OPTS = {
    "-f": 0, "--force": 0, "--discard-changes": 0,
    "-c": 1, "-C": 1, "--create": 1,
    "-q": 0, "--quiet": 0,
    "--orphan": 1, "--conflict": 1,
}

_RESET_OPTS = {
    "--hard": 0, "--soft": 0, "--mixed": 0,
    "-q": 0, "--quiet": 0,
}

_CHECKOUT_INDEX_OPTS = {
    "-f": 0, "--force": 0,
    "-a": 0, "--all": 0,
    "-q": 0, "--quiet": 0,
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


def _operand_resolves_as_commit(cwd, operand, forwarded_globals=()):
    result = _run_git(
        cwd, "rev-parse", "--verify", "--quiet", f"{operand}^{{commit}}",
        forwarded_globals=forwarded_globals,
    )
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
        if parsed is not None and parsed["subcommand"] in _DESTRUCTIVE_SUBCOMMANDS:
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


def _run_git(cwd, *args, forwarded_globals=()):
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return subprocess.run(
        ["git", "-C", cwd, *forwarded_globals, *args],
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT,
        env=env,
    )


def _parse_segment_tokens(segment):
    """Tokenize a segment, stripping env-assignment prefixes."""
    tokens = _tokenize_segment(segment)
    start = 0
    while start < len(tokens) and "=" in tokens[start] and not tokens[start].startswith("="):
        key = tokens[start].split("=", 1)[0]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            start += 1
            continue
        break
    env_prefix_present = start > 0
    tokens = _strip_shell_prefixes(tokens[start:])
    return tokens, env_prefix_present


def _extract_forwarded_globals(tokens):
    """Git global options between `git` and the subcommand, for probe forwarding."""
    if not tokens or not _is_git_token(tokens[0]):
        return []
    globals_list = []
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--":
            break
        if not tok.startswith("-"):
            break
        base = tok.split("=", 1)[0]
        if base in ("-C", "--git-dir", "--work-tree"):
            break
        globals_list.append(tok)
        if base in _GIT_GLOBAL_OPT_WITH_VALUE and "=" not in tok:
            _, consumed = _option_value(tokens, i)
            if consumed:
                globals_list.append(tokens[i + 1])
            i += 1 + consumed
        else:
            i += 1
    return globals_list


def _segment_has_pathspec_mode_global(tokens):
    """True when a pathspec-mode git global appears before the subcommand."""
    if not tokens or not _is_git_token(tokens[0]):
        return False
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--":
            break
        if not tok.startswith("-"):
            break
        base = tok.split("=", 1)[0]
        if base in _PATHSPEC_MODE_GLOBALS:
            return True
        if base in _GIT_GLOBAL_OPT_WITH_VALUE:
            _, consumed = _option_value(tokens, i)
            i += 1 + consumed
        else:
            i += 1
    return False


def _option_known(tok, option_specs):
    """True when tok is a recognized option in option_specs."""
    if not tok.startswith("-"):
        return True
    flags, _, _ = _expand_clustered_flags(tok, option_specs)
    for part in flags:
        if not part.startswith("-"):
            continue
        base = part.split("=", 1)[0]
        if part in option_specs or base in option_specs:
            continue
        for key in option_specs:
            if key.startswith("--") and key == base:
                continue
            if key.startswith("--") and key[2:] == base[2:] if base.startswith("--") else False:
                continue
        else:
            for key in option_specs:
                if part == key or base == key:
                    break
                if key.startswith("--") and base.startswith("--") and key[2:] == base[2:]:
                    break
            else:
                return False
    return True


def _has_unknown_option_in_args(args, option_specs):
    """True when an option token is absent from the subcommand's option table."""
    pre, _, _ = _args_before_separator(args)
    i = 0
    while i < len(pre):
        tok = pre[i]
        if not tok.startswith("-"):
            i += 1
            continue
        flags, _, expects_value = _expand_clustered_flags(tok, option_specs)
        if len(flags) == 1 and not flags[0].startswith("-"):
            i += 1
            continue
        if not _option_known(tok, option_specs):
            return True
        i += 2 if expects_value else 1
    return False


def _extract_option_value(pre_args, option_specs, short_flags, long_flags):
    """Return the value for the first matching short/long option, or None."""
    long_bases = {lf.split("=", 1)[0] for lf in long_flags}
    i = 0
    while i < len(pre_args):
        tok = pre_args[i]
        if not tok.startswith("-"):
            i += 1
            continue
        flags, _, expects_value = _expand_clustered_flags(tok, option_specs)
        for part in flags:
            base = part.split("=", 1)[0]
            if part in short_flags or base in long_bases:
                val, _ = _option_value(pre_args, i)
                return val
        i += 2 if expects_value else 1
    return None


def _normalize_scope(scope):
    """Empty scope lists must never mean probe nothing."""
    if scope is WHOLE_TREE:
        return WHOLE_TREE
    if not scope:
        return WHOLE_TREE
    return scope


def _scope_status_suffix(scope):
    """Return ['--', *scope] when scoped, else []."""
    if scope is WHOLE_TREE:
        return []
    return ["--", *scope]


def _split_nul(output):
    """Split NUL-terminated git -z output, dropping trailing empty element."""
    if not output:
        return set()
    parts = output.split("\0")
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return {p for p in parts if p}


def _plan_checkout_path(args, probe_cwd, forwarded_globals):
    pre, has_sep, post = _args_before_separator(args)
    has_psff = _flag_present(
        args, (), ("--pathspec-from-file", "--pathspec-from-file-nul"), _CHECKOUT_OPTS,
    )
    if _has_unknown_option_in_args(args, _CHECKOUT_OPTS):
        return {"scope": WHOLE_TREE, "source": "index"}
    matched, pre_operands = _consume_options(pre, _CHECKOUT_OPTS)
    treeish_operands = []
    if has_psff:
        scope = WHOLE_TREE
        treeish_operands = pre_operands
    elif has_sep:
        if len(pre_operands) > 1:
            scope = WHOLE_TREE
        else:
            scope = post if post else WHOLE_TREE
            treeish_operands = pre_operands
    elif len(pre_operands) >= 2:
        treeish_operands = [pre_operands[0]]
        scope = pre_operands[1:]
    elif len(pre_operands) == 1:
        scope = [pre_operands[0]]
    else:
        scope = WHOLE_TREE
    source = "index"
    if treeish_operands:
        candidate = treeish_operands[0]
        if _operand_resolves_as_commit(probe_cwd, candidate, forwarded_globals):
            source = candidate
    return {"scope": _normalize_scope(scope), "source": source}


def _plan_restore(args, probe_cwd, forwarded_globals):
    pre, has_sep, post = _args_before_separator(args)
    if _has_unknown_option_in_args(args, _RESTORE_OPTS):
        scope = WHOLE_TREE
    else:
        _, operands = _consume_options(pre, _RESTORE_OPTS)
        scope = operands + post
        scope = _normalize_scope(scope)
    source_val = _extract_option_value(pre, _RESTORE_OPTS, ("-s",), ("--source",))
    source = source_val if source_val else "index"
    return {"scope": scope, "source": source}


def _plan_checkout_force(args, probe_cwd, forwarded_globals):
    pre, _, _ = _args_before_separator(args)
    if _has_unknown_option_in_args(args, _CHECKOUT_OPTS):
        return {"scope": WHOLE_TREE, "source": "HEAD"}
    _, operands = _consume_options(pre, _CHECKOUT_OPTS)
    source = operands[0] if operands else "HEAD"
    return {"scope": WHOLE_TREE, "source": source}


def _plan_switch_force(args, probe_cwd, forwarded_globals):
    pre, _, _ = _args_before_separator(args)
    if _has_unknown_option_in_args(args, _SWITCH_OPTS):
        return {"scope": WHOLE_TREE, "source": "HEAD"}
    _, operands = _consume_options(pre, _SWITCH_OPTS)
    source = operands[0] if operands else "HEAD"
    return {"scope": WHOLE_TREE, "source": source}


def _plan_reset_hard(args, probe_cwd, forwarded_globals):
    pre, _, _ = _args_before_separator(args)
    if _has_unknown_option_in_args(args, _RESET_OPTS):
        return {"scope": WHOLE_TREE, "source": "HEAD"}
    _, operands = _consume_options(pre, _RESET_OPTS)
    source = operands[0] if operands else "HEAD"
    return {"scope": WHOLE_TREE, "source": source}


def _plan_rm_force(args, probe_cwd, forwarded_globals):
    pre, has_sep, post = _args_before_separator(args)
    if _has_unknown_option_in_args(args, _RM_OPTS):
        scope = WHOLE_TREE
    else:
        _, operands = _consume_options(pre, _RM_OPTS)
        scope = operands + post
        scope = _normalize_scope(scope)
    return {"scope": scope, "source": None}


def _plan_checkout_index_force(args, probe_cwd, forwarded_globals):
    pre, has_sep, post = _args_before_separator(args)
    if _has_unknown_option_in_args(args, _CHECKOUT_INDEX_OPTS):
        scope = WHOLE_TREE
    elif _flag_present(args, ("-a",), ("--all",), _CHECKOUT_INDEX_OPTS):
        scope = WHOLE_TREE
    else:
        _, operands = _consume_options(pre, _CHECKOUT_INDEX_OPTS)
        scope = operands + post
        scope = _normalize_scope(scope)
    return {"scope": scope, "source": "index"}


def _plan_clean_scope(args):
    pre, has_sep, post = _args_before_separator(args)
    unknown = _has_unknown_option_in_args(args, _CLEAN_OPTS)
    _, operands = _consume_options(pre, _CLEAN_OPTS)
    if unknown:
        return WHOLE_TREE
    scope = operands + post
    return _normalize_scope(scope)


def _resolve_probe_plan(action, segment, probe_cwd, forwarded_globals):
    """Return probe plan dict, or 'indeterminate' when parsing fails."""
    tokens, env_prefix = _parse_segment_tokens(segment)
    if not tokens or not _is_git_token(tokens[0]):
        return "indeterminate"
    degrade = (
        env_prefix
        or "\\" in segment
        or "$" in segment
        or _segment_has_pathspec_mode_global(tokens)
    )
    parsed = _parse_git_invocation(tokens)
    if parsed is None:
        return "indeterminate"
    args = parsed["args"]
    if action == "checkout-path":
        plan = _plan_checkout_path(args, probe_cwd, forwarded_globals)
    elif action == "restore":
        plan = _plan_restore(args, probe_cwd, forwarded_globals)
    elif action == "checkout-force":
        plan = _plan_checkout_force(args, probe_cwd, forwarded_globals)
    elif action == "switch-force":
        plan = _plan_switch_force(args, probe_cwd, forwarded_globals)
    elif action == "reset-hard":
        plan = _plan_reset_hard(args, probe_cwd, forwarded_globals)
    elif action == "rm-force":
        plan = _plan_rm_force(args, probe_cwd, forwarded_globals)
    elif action == "checkout-index-force":
        plan = _plan_checkout_index_force(args, probe_cwd, forwarded_globals)
    elif action == "clean":
        plan = {"scope": _plan_clean_scope(args), "source": None}
    else:
        return "indeterminate"
    if degrade:
        plan["scope"] = WHOLE_TREE
    plan["scope"] = _normalize_scope(plan["scope"])
    return plan


def _probe_arm_a(probe_cwd, scope, forwarded_globals):
    """Tracked modifications inside scope."""
    args = [
        "status", "--porcelain", "--untracked-files=no", "--ignore-submodules=none",
        *_scope_status_suffix(scope),
    ]
    result = _run_git(probe_cwd, *args, forwarded_globals=forwarded_globals)
    if result.returncode != 0:
        return "indeterminate"
    return len([ln for ln in result.stdout.splitlines() if ln.strip()])


def _probe_arm_b(probe_cwd, scope, source, forwarded_globals):
    """Source-tree writes over untracked/ignored content inside scope."""
    if source in ("index", None):
        return 0
    verify = _run_git(
        probe_cwd, "rev-parse", "--verify", "--quiet", f"{source}^{{commit}}",
        forwarded_globals=forwarded_globals,
    )
    if verify.returncode != 0:
        return "indeterminate"
    if scope is WHOLE_TREE:
        ls_args = ["ls-tree", "-r", "-z", "--full-tree", "--name-only", source]
    else:
        ls_args = [
            "ls-tree", "-r", "-z", "--full-name", "--name-only", source,
            "--", *scope,
        ]
    result = _run_git(probe_cwd, *ls_args, forwarded_globals=forwarded_globals)
    if result.returncode != 0:
        return "indeterminate"
    destinations = _split_nul(result.stdout)
    status_args = [
        "status", "--porcelain", "-z", "--untracked-files=all",
        "--ignored=matching", "--ignore-submodules=none",
        *_scope_status_suffix(scope),
    ]
    result = _run_git(probe_cwd, *status_args, forwarded_globals=forwarded_globals)
    if result.returncode != 0:
        return "indeterminate"
    untracked_or_ignored = set()
    for entry in _split_nul(result.stdout):
        if len(entry) < 2:
            continue
        xy = entry[:2]
        if xy in ("??", "!!"):
            path = entry[3:] if len(entry) > 3 and entry[2] == " " else entry[2:]
            untracked_or_ignored.add(path)
    return len(destinations & untracked_or_ignored)


def _check_assume_unchanged_scoped(probe_cwd, scope, forwarded_globals):
    """Fail-closed when assume-unchanged or skip-worktree bits are invisible to status."""
    args = ["ls-files", "-v", *_scope_status_suffix(scope)]
    result = _run_git(probe_cwd, *args, forwarded_globals=forwarded_globals)
    if result.returncode != 0:
        return "indeterminate"
    for line in result.stdout.splitlines():
        if line and (line[0].islower() or line[0] == "S"):
            return "indeterminate"
    return "clean"


def _probe_clean(probe_cwd, segment, scope, forwarded_globals):
    """Clean uses git's own --dry-run with the command's real flags."""
    tokens, env_prefix = _parse_segment_tokens(segment)
    degrade = (
        env_prefix
        or "\\" in segment
        or "$" in segment
        or _segment_has_pathspec_mode_global(tokens)
    )
    parsed = _parse_git_invocation(tokens)
    if parsed is None:
        return "indeterminate"
    args = parsed["args"]
    pre, _, _ = _args_before_separator(args)
    unknown = _has_unknown_option_in_args(args, _CLEAN_OPTS)
    if degrade or unknown:
        scope = WHOLE_TREE
    scope = _normalize_scope(scope)
    clean_args = ["clean", "--dry-run"]
    i = 0
    while i < len(pre):
        tok = pre[i]
        if not tok.startswith("-"):
            i += 1
            continue
        flags, _, expects_value = _expand_clustered_flags(tok, _CLEAN_OPTS)
        for part in flags:
            base = part.split("=", 1)[0]
            if base in ("-d", "-x", "-X", "-f"):
                clean_args.append(part)
            elif base in ("-e", "--exclude"):
                val, _ = _option_value(pre, i)
                if val is not None:
                    if "=" in part:
                        clean_args.append(part)
                    else:
                        clean_args.extend([base, val])
        i += 2 if expects_value else 1
    suffix = _scope_status_suffix(scope)
    if suffix:
        clean_args.extend(suffix)
    result = _run_git(probe_cwd, *clean_args, forwarded_globals=forwarded_globals)
    if result.returncode != 0:
        return "indeterminate"
    count = len([ln for ln in result.stdout.splitlines() if ln.strip()])
    if count > 0:
        return ("at-risk", count)
    assume = _check_assume_unchanged_scoped(probe_cwd, scope, forwarded_globals)
    if assume == "indeterminate":
        return ("indeterminate", 0)
    return ("clean", 0)


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

    try:
        tokens, _ = _parse_segment_tokens(command)
        forwarded_globals = _extract_forwarded_globals(tokens)

        if action == "worktree-remove-force":
            result = _run_git(
                probe_cwd, "status", "--porcelain",
                "--untracked-files=normal", "--ignore-submodules=none",
                forwarded_globals=forwarded_globals,
            )
            if result.returncode != 0:
                return ("indeterminate", 0)
            count = len([ln for ln in result.stdout.splitlines() if ln.strip()])
            if count > 0:
                return ("at-risk", count)
            return ("clean", 0)

        plan = _resolve_probe_plan(action, command, probe_cwd, forwarded_globals)
        if plan == "indeterminate":
            return ("indeterminate", 0)

        if action == "clean":
            return _probe_clean(probe_cwd, command, plan["scope"], forwarded_globals)

        scope = plan["scope"]
        source = plan["source"]

        arm_a = _probe_arm_a(probe_cwd, scope, forwarded_globals)
        if arm_a == "indeterminate":
            return ("indeterminate", 0)

        arm_b = _probe_arm_b(probe_cwd, scope, source, forwarded_globals)
        if arm_b == "indeterminate":
            return ("indeterminate", 0)

        total = arm_a + arm_b
        if total > 0:
            return ("at-risk", total)

        assume = _check_assume_unchanged_scoped(probe_cwd, scope, forwarded_globals)
        if assume == "indeterminate":
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
            import owner_authority
            state = owner_authority.calibration_state(cwd)
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
