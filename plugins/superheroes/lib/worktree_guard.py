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
})
_GIT_GLOBAL_OPT_WITH_VALUE = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
}

_DESTRUCTIVE_SUBCOMMANDS = frozenset({
    "checkout", "checkout-index", "restore", "reset", "clean", "switch", "rm", "worktree",
})

_SHELL_PREFIXES = frozenset({"!", "then", "do", "else", "elif"})

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


def _expand_clustered_flags(flag_token, option_specs=None):
    """Expand a clustered short-option token like -fd or -SW into single-letter flags."""
    if not flag_token.startswith("-") or flag_token.startswith("--"):
        return [flag_token]
    if option_specs:
        for key, need in option_specs.items():
            if not need:
                continue
            if key.startswith("-") and not key.startswith("--") and len(key) == 2:
                letter = key[1]
                rest = flag_token[1:]
                if rest.startswith(letter) and len(rest) > 1:
                    return [key, rest[1:]]
    letters = flag_token[1:]
    if not letters or not letters.isalpha():
        return [flag_token]
    return ["-" + c for c in letters]


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
    if not tokens or tokens[0] != "git":
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
        if tok in _SHELL_PREFIXES:
            tokens = tokens[1:]
            continue
        if tok == "{":
            tokens = tokens[1:]
            continue
        if tok.startswith("{") and len(tok) > 1:
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
        if tokens and tokens[0] == "git":
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
        expanded = _expand_clustered_flags(tok, specs)
        if len(expanded) > 1:
            for part in expanded:
                if part in short_flags:
                    return True
                base = part.split("=", 1)[0]
                if base in long_bases:
                    return True
            i += 1
            continue
        part = expanded[0]
        base = part.split("=", 1)[0]
        if part in short_flags or base in long_bases:
            return True
        if base in specs and specs[base]:
            _, consumed = _option_value(pre, i)
            i += 1 + consumed
            continue
        if part.startswith("--") and "=" not in part and base[2:] in {lf[2:] for lf in long_flags if lf.startswith("--")}:
            return True
        i += 1
    return False


def _consume_options(pre_args, option_specs):
    """Walk pre-`--` args, returning set of matched flag letters/names and operand count."""
    matched = set()
    operands = []
    i = 0
    while i < len(pre_args):
        tok = pre_args[i]
        expanded = _expand_clustered_flags(tok, option_specs)
        consumed_extra = 0
        if len(expanded) > 1:
            for part in expanded:
                if part in option_specs:
                    matched.add(part)
                    spec = option_specs[part]
                    if spec:
                        consumed_extra = max(consumed_extra, spec)
            i += 1 + consumed_extra
            continue
        if len(expanded) == 2 and expanded[0] in option_specs:
            matched.add(expanded[0])
            need = option_specs[expanded[0]]
            if need:
                operands.append(expanded[1])
            i += 1
            continue
        part = expanded[0]
        base = part.split("=", 1)[0]
        if base in option_specs:
            matched.add(base)
            need = option_specs[base]
            if need and "=" not in part:
                consumed_extra = need
        elif part.startswith("--"):
            name = base[2:]
            for key, need in option_specs.items():
                if key.startswith("--") and key[2:] == name:
                    matched.add(key)
                    if need and "=" not in part:
                        consumed_extra = need
                    break
            else:
                if "=" not in part:
                    consumed_extra = 1
        elif part.startswith("-"):
            pass
        else:
            operands.append(part)
        i += 1 + consumed_extra
    return matched, operands


_CHECKOUT_OPTS = {
    "-b": 1, "-B": 1, "-f": 0, "--force": 0,
    "--pathspec-from-file": 1, "--pathspec-from-file-nul": 0,
    "-u": 0, "--ours": 0, "--theirs": 0, "-q": 0, "--quiet": 0,
    "--recurse-submodules": 0, "--no-recurse-submodules": 0,
    "--progress": 0, "--no-progress": 0, "--overlay": 0, "--no-overlay": 0,
    "--ignore-skip-worktree-bits": 0,
}

_CLEAN_OPTS = {
    "-d": 0, "-f": 0, "-i": 0, "-n": 0, "--dry-run": 0,
    "-e": 1, "--exclude": 1,
    "-x": 0, "-X": 0, "-q": 0, "--quiet": 0,
}


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
    has_staged = _flag_present(args, ("-S",), ("--staged",))
    has_worktree = _flag_present(args, ("-W",), ("--worktree",))
    if has_staged and not has_worktree:
        return False
    return True


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
            return None
        resolved = _resolve_single_operand_checkout(cwd, operand)
        if resolved == "checkout-path":
            return "checkout-path"
        if resolved == "indeterminate":
            return "checkout-path"
        return None
    return action


def destructive_discard_actions(command, cwd=None):
    """Return every destructive-discard action across all command-position git segments."""
    if not isinstance(command, str):
        return []
    actions = []
    for parsed in _iter_git_segments(command):
        action = _segment_destructive_action(parsed, cwd)
        if action is not None:
            actions.append(action)
    return actions


def _destructive_git_precisely_safe(command, cwd):
    """True when every parsed destructive git invocation is proven safe by the precise parser."""
    saw_destructive = False
    for parsed in _iter_git_segments(command):
        if parsed["subcommand"] not in _DESTRUCTIVE_SUBCOMMANDS:
            continue
        saw_destructive = True
        if _segment_destructive_action(parsed, cwd) is not None:
            return False
    return saw_destructive


def destructive_discard_action(command):
    """Return the first destructive-discard action, or None."""
    actions = destructive_discard_actions(command)
    return actions[0] if actions else None


def mentions_destructive_git(command):
    """True when the command text plausibly invokes a destructive git subcommand.

    Deliberately CRUDE and over-inclusive: it exists to catch what the precise parser misses.
    Quote-aware only to the extent needed to not fire on `git commit -m 'git checkout -- f'`.
    """
    if not isinstance(command, str):
        return False
    i = 0
    n = len(command)
    in_single = False
    in_double = False
    while i < n:
        ch = command[i]
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
            while i < n and not command[i].isspace() and command[i] not in ";|&()":
                i += 1
            word = command[start:i]
            if word == "git":
                j = i
                while j < n:
                    while j < n and command[j].isspace():
                        j += 1
                    if j >= n or command[j] in ";|&()":
                        break
                    tok_start = j
                    while j < n and not command[j].isspace() and command[j] not in ";|&()":
                        j += 1
                    token = command[tok_start:j]
                    if not token.startswith("-"):
                        if token in _DESTRUCTIVE_SUBCOMMANDS:
                            return True
                        break
            continue
        i += 1
    return False


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
    if tokens and tokens[0] == "git":
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
    """Walk cwd and ancestors for a .git entry via lstat. Returns path or None."""
    path = os.path.abspath(cwd)
    while True:
        git_entry = os.path.join(path, ".git")
        try:
            os.lstat(git_entry)
            return git_entry
        except FileNotFoundError:
            pass
        except OSError:
            return "indeterminate"
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


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


def _clean_has_flag(command, flag):
    for parsed in _iter_git_segments(command):
        if parsed["subcommand"] == "clean":
            pre, _, _ = _args_before_separator(parsed["args"])
            matched, _ = _consume_options(pre, _CLEAN_OPTS)
            if flag in matched:
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
        if action in (
            "checkout-path", "restore", "rm-force", "checkout-index-force",
        ):
            result = _run_git(
                probe_cwd, "status", "--porcelain",
                "--untracked-files=no", "--ignore-submodules=none",
            )
        elif action in ("checkout-force", "switch-force", "worktree-remove-force"):
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

        actions = destructive_discard_actions(command, cwd)
        if not actions:
            if mentions_destructive_git(command) and not _destructive_git_precisely_safe(
                command, cwd,
            ):
                return ("deny", unparsed_message())
            return ("allow", "")

        if not target_is_resolvable(command):
            return ("deny", indeterminate_message(actions[0]))

        for action in actions:
            risk_state, count = at_risk(cwd, action, command)
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
