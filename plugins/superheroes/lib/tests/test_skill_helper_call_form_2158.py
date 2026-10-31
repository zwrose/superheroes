"""The skills call the nine hook-approved scripts in the one form the hook approves (#2158).

Invariant: every place under `skills/review-code/`, `skills/workhorse/` and `rubric/orders/` that
tells an agent to RUN one of the nine scripts on the hook's `APPROVED_SCRIPTS` shows the call as one
physical line, `python3 -B <plugin root>/lib/<script>.py <verb> <args…>`: no `$` (no `$ROOT_DIR`,
`$SESSION_DIR`, `${…}`, `$(…)`), no trailing `\\`, no operator, and no unquoted `[ ] { } * ? ~` or
`<`/`>` beyond the `<…>` placeholders an agent replaces. The session folder is written `<session dir>`
and the plugin root `<plugin root>`.

The oracle is the hook's own `decide` (`hooks/plugin_scripts_allow.py`): each call form found in the
skill text is rendered with real paths and handed to `decide`. It must be approved, except the
round driver's `run-verify` and `rule` verbs and any `round_driver.py` call carrying
`--verify-command`, `--break-it-interpreter` or `--records-path`, which the hook leaves to the normal
permission check on purpose and which this module asserts are NOT approved.

Detectors here (each has a synthetic test that goes red when its check is neutralized, plus the real
census over the shipped text): the call-form shape check, the forbidden-form check, the population
check (non-empty, floor, a `run-verify` and a `rule` form present), the unreplaced-placeholder check
before `decide`, and the approve / not-approve comparison in both directions.
"""
import importlib.util
import os
import re
from collections import namedtuple

import pytest

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HOOK = os.path.join(_PLUGIN, "hooks", "plugin_scripts_allow.py")

_spec = importlib.util.spec_from_file_location("plugin_scripts_allow_2158", _HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

_NINE = tuple(sorted(name[: -len(".py")] for name in hook.APPROVED_SCRIPTS))
_NINE_ALT = "|".join(_NINE)
_ROOTS = (
    os.path.join(_PLUGIN, "skills", "review-code"),
    os.path.join(_PLUGIN, "skills", "workhorse"),
    os.path.join(_PLUGIN, "rubric", "orders"),
)

# Measured at the 2158 fix: 35 call forms across the three trees (fenced lines plus inline spans).
POPULATION_FLOOR = 32  # the grounding stage's call forms left with it (C1-L2)

_SCRIPT_IN_FORM = re.compile(r"(?<![A-Za-z0-9_])lib/(%s)\.py(?![A-Za-z0-9_])" % _NINE_ALT)
_FORM_HEAD = re.compile(r"^python3 -B <plugin root>/lib/(%s)\.py(?: (.*))?$" % _NINE_ALT)
# Only these named documentation placeholders (besides `<plugin root>` and `<session dir>`) are
# replaced by an argument. Any other `<…>` is left in place and refused, so a shell redirect pair
# (`< f >`, `<input.txt>output.txt`) is never erased. Syntax alone cannot tell the two apart.
_PLACEHOLDER_NAMES = frozenset((
    "phase", "N", "phase from next", "verify command, or none", "engine or native",
    "attempt from next", "expectedStateHash from next", "vendor", "id",
    "in-repo or global, the LOC value", "vendors JSON list", "implementation engine", "attempt",
    "expectedStateHash", "build base", "path from table above", "tripwire, park or held", "seat",
    "round from next", "rulings file", "who", "effort or null", "sha",
    "the brief-check seat JSON, written out", "claude or codex", "the order file",
    "the build worktree", "the build worktree's plugin root, in this repository",
    "each declared item", "str-or-null", "role", "value", "records file",
))
_PLACEHOLDER = re.compile(r"<([^<>]*)>")


def _erase_placeholder(match):
    return "x" if match.group(1) in _PLACEHOLDER_NAMES else match.group(0)
_INLINE_SPAN = re.compile(r"`([^`\n]+)`")
_FORBIDDEN_ROOT_DIR = re.compile(
    r"\$(?:\{ROOT_DIR\}|ROOT_DIR)/lib/(?:%s)\.py" % _NINE_ALT
)
_NAMES_NINE = re.compile(r"(?<![A-Za-z0-9_])(?:%s)\.py" % _NINE_ALT)
_SESSION_DIR_VAR = re.compile(r"--session-dir[ =]\"?\$\{?SESSION_DIR\}?\"?")
_UNAPPROVED_DRIVER_VERBS = ("run-verify", "rule")
_UNAPPROVED_DRIVER_FLAGS = ("--verify-command", "--break-it-interpreter", "--records-path")

Form = namedtuple("Form", "rel line nth text")


def _form_id(form):
    return "%s:%d" % (form.rel, form.line) + (".%d" % form.nth if form.nth else "")


def _is_call_text(text):
    return "python3" in text and _SCRIPT_IN_FORM.search(text) is not None


def _call_forms_in_text(rel, text):
    """Every call form in one file: a fenced-code line, or an inline backtick span, that holds
    `python3` and `lib/<one of the nine>.py`."""
    forms = []
    in_fence = False
    pending = []  # physical lines of a fenced command continued with a trailing backslash
    pending_start = 0

    def flush():
        # A pending command is collected whenever it ends: a closing fence and EOF end it too.
        nonlocal pending
        joined = "\n".join(pending)
        pending = []
        if joined and _is_call_text(joined):
            forms.append(Form(rel, pending_start, 0, joined))

    for lineno, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            flush()
            in_fence = not in_fence
            continue
        if in_fence:
            if not pending:
                pending_start = lineno
            pending.append(line.strip())
            if line.rstrip().endswith("\\"):
                continue
            flush()
            continue
        nth = 0
        for match in _INLINE_SPAN.finditer(line):
            if _is_call_text(match.group(1)):
                forms.append(Form(rel, lineno, nth, match.group(1).strip()))
                nth += 1
    flush()
    return forms


def _markdown_files(roots=_ROOTS):
    files = []
    for root in roots:
        for dirpath, _dirs, names in os.walk(root):
            files.extend(os.path.join(dirpath, n) for n in names if n.endswith(".md"))
    return sorted(files)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def collect_call_forms(roots=_ROOTS):
    forms = []
    for path in _markdown_files(roots):
        forms.extend(_call_forms_in_text(os.path.relpath(path, _PLUGIN), _read(path)))
    return forms


def _logical_lines(text):
    """(first physical line number, merged text) with trailing-backslash continuations merged."""
    logical = []
    current = None
    start = 0
    for lineno, line in enumerate(text.splitlines(), 1):
        if current is None:
            current, start = line, lineno
        else:
            current = current.rstrip().rstrip("\\").rstrip() + " " + line.lstrip()
        if not line.rstrip().endswith("\\"):
            logical.append((start, current))
            current = None
    if current is not None:
        logical.append((start, current))
    return logical


def _forbidden_hits(rel, text):
    """Shell-variable forms of the nine scripts, anywhere in the text, on logical lines."""
    hits = []
    for lineno, line in _logical_lines(text):
        if _FORBIDDEN_ROOT_DIR.search(line):
            hits.append("%s:%d: $ROOT_DIR form of a hook-approved script" % (rel, lineno))
        if _NAMES_NINE.search(line) and _SESSION_DIR_VAR.search(line):
            hits.append("%s:%d: hook-approved script with --session-dir $SESSION_DIR" % (rel, lineno))
    return hits


def _shape_problems(text):
    """Problems with one call form's own text (the hook is the oracle for the rest)."""
    problems = []
    if "$" in text:
        problems.append("contains $")
    if "\n" in text:
        problems.append("spans more than one physical line")
    if text.rstrip().endswith("\\"):
        problems.append("ends in a backslash continuation")
    if _FORM_HEAD.match(text) is None:
        problems.append("script token is not exactly `python3 -B <plugin root>/lib/<name>.py`")
    return problems


def _population_problems(forms):
    problems = []
    if not forms:
        problems.append("empty population: no call form found")
        return problems
    if len(forms) < POPULATION_FLOOR:
        problems.append("population %d is below the floor %d" % (len(forms), POPULATION_FLOOR))
    verbs = {_driver_verb(f.text) for f in forms}
    for verb in _UNAPPROVED_DRIVER_VERBS:
        if verb not in verbs:
            problems.append("no round_driver.py %s form in the population" % verb)
    return problems


def _driver_verb(text):
    match = _FORM_HEAD.match(text)
    if match is None or match.group(1) != "round_driver" or not match.group(2):
        return None
    return match.group(2).split()[0]


def _expected_approved(text):
    if _driver_verb(text) in _UNAPPROVED_DRIVER_VERBS:
        return False
    if _FORM_HEAD.match(text) and _FORM_HEAD.match(text).group(1) == "round_driver":
        if any(flag in text for flag in _UNAPPROVED_DRIVER_FLAGS):
            return False
    return True


def _render(text, plugin_root, session_dir):
    rendered = text.replace("<plugin root>", plugin_root).replace("<session dir>", session_dir)
    return _PLACEHOLDER.sub(_erase_placeholder, rendered)


def _judge(form_text, plugin_root, session_dir, cwd, decide=None):
    """None when the hook's decision matches the expectation, else the miss, in words."""
    decide = hook.decide if decide is None else decide
    rendered = _render(form_text, plugin_root, session_dir)
    if "<" in rendered or ">" in rendered:
        return "unreplaced placeholder left in %r" % rendered
    payload = {"tool_name": "Bash", "tool_input": {"command": rendered}, "cwd": cwd}
    approved = decide(payload, [plugin_root]) is True
    expected = _expected_approved(form_text)
    if expected and not approved:
        return "not approved but must be: %s" % rendered
    if not expected and approved:
        return "approved but must NOT be: %s" % rendered
    return None


@pytest.fixture
def scene(tmp_path):
    session = tmp_path / "session"
    session.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    return str(session), str(repo)


_FORMS = collect_call_forms()
_IDS = [_form_id(f) for f in _FORMS]


# --- the census over the shipped text ---------------------------------------------------------


def test_census_population_is_not_vacuous():
    problems = _population_problems(_FORMS)
    assert not problems, "call-form census population: " + "; ".join(problems)


@pytest.mark.parametrize("form", _FORMS, ids=_IDS)
def test_call_form_shape(form):
    problems = _shape_problems(form.text)
    assert not problems, "%s: %s: %s" % (_form_id(form), "; ".join(problems), form.text)


def test_no_forbidden_forms_in_the_skill_text():
    hits = []
    for path in _markdown_files():
        hits.extend(_forbidden_hits(os.path.relpath(path, _PLUGIN), _read(path)))
    assert not hits, "shell-variable forms of the nine scripts (#2158):\n" + "\n".join(hits)


def test_rendered_call_forms_get_the_hooks_decision(scene):
    session, repo = scene
    misses = []
    for form in _FORMS:
        miss = _judge(form.text, _PLUGIN, session, repo)
        if miss is not None:
            misses.append("%s: %s" % (_form_id(form), miss))
    assert not misses, "hook decisions that differ from the contract:\n" + "\n".join(misses)


@pytest.mark.parametrize("form", _FORMS, ids=_IDS)
def test_each_rendered_call_form_gets_the_hooks_decision(form, scene):
    session, repo = scene
    miss = _judge(form.text, _PLUGIN, session, repo)
    assert miss is None, "%s: %s" % (_form_id(form), miss)


# --- the detectors bite (synthetic inputs; each goes red when its check is neutralized) -------


def test_shape_check_flags_variable_and_continuation_forms():
    bad = 'python3 -B "$ROOT_DIR/lib/round_driver.py" next \\'
    problems = _shape_problems(bad)
    assert "contains $" in problems
    assert "ends in a backslash continuation" in problems
    assert any("script token" in p for p in problems)
    assert _shape_problems("python3 -B <plugin root>/lib/round_driver.py next --session-dir <session dir>") == []


def test_forbidden_form_check_flags_a_reintroduced_multiline_block():
    text = (
        "```bash\n"
        'python3 -B "$ROOT_DIR/lib/round_driver.py" next \\\n'
        '  --session-dir "$SESSION_DIR"\n'
        "```\n"
    )
    hits = _forbidden_hits("fake.md", text)
    assert any("fake.md:2: $ROOT_DIR form" in h for h in hits), hits
    assert any("fake.md:2: hook-approved script with --session-dir" in h for h in hits), hits
    assert _forbidden_hits("fake.md", "run `python3 -B <plugin root>/lib/round_driver.py next --session-dir <session dir>`\n") == []
    assert _forbidden_hits("fake.md", 'python3 -B "$ROOT_DIR/lib/review_record_session.py" write --session-dir "$SESSION_DIR"\n') == []


def test_every_approved_script_is_matched_by_the_census():
    assert _NINE
    assert all(_SCRIPT_IN_FORM.search("lib/" + name) for name in hook.APPROVED_SCRIPTS)


def test_census_collects_and_flags_a_command_split_before_the_script_path():
    split = (
        "```bash\n"
        "python3 -B \\\n"
        "  <plugin root>/lib/review_store.py stage --session-dir <session dir>\n"
        "```\n"
    )
    forms = _call_forms_in_text("fake.md", split)
    assert len(forms) == 1, forms
    assert "spans more than one physical line" in _shape_problems(forms[0].text)
    single = "```bash\npython3 -B <plugin root>/lib/review_store.py stage --session-dir <session dir>\n```\n"
    one = _call_forms_in_text("fake.md", single)
    assert len(one) == 1 and _shape_problems(one[0].text) == []


def test_a_shell_redirect_is_not_erased_as_a_placeholder(scene):
    session, repo = scene
    base = "python3 -B <plugin root>/lib/review_store.py stage --session-dir <session dir>"
    assert _judge(base, _PLUGIN, session, repo) is None
    for redirect in (" < /tmp/input > /tmp/output", " </tmp/input>/tmp/output", " </tmp/in >/tmp/out",
                     " <input.txt>output.txt", " <input.txt> output.txt", " <in>out"):
        miss = _judge(base + redirect, _PLUGIN, session, repo)
        assert miss is not None and "unreplaced placeholder" in miss, (redirect, miss)


@pytest.mark.parametrize("boundary", ["\\\n```\n", "\\\n"])
def test_a_trailing_backslash_at_a_fence_or_eof_boundary_is_collected_and_flagged(boundary):
    text = "```bash\npython3 -B <plugin root>/lib/review_store.py stage --session-dir <session dir> " + boundary
    forms = _call_forms_in_text("fake.md", text)
    assert len(forms) == 1, forms
    assert "ends in a backslash continuation" in _shape_problems(forms[0].text)


def test_population_check_fails_an_empty_population(tmp_path):
    forms = collect_call_forms(roots=(str(tmp_path),))
    assert forms == []
    problems = _population_problems(forms)
    assert any("empty population" in p for p in problems), problems


def test_population_check_needs_a_run_verify_and_a_rule_form():
    only_next = [
        Form("fake.md", n, 0, "python3 -B <plugin root>/lib/round_driver.py next --session-dir <session dir>")
        for n in range(1, POPULATION_FLOOR + 1)
    ]
    problems = _population_problems(only_next)
    assert any("run-verify" in p for p in problems), problems
    assert any("rule" in p for p in problems), problems
    complete = only_next + [
        Form("fake.md", 99, 0, "python3 -B <plugin root>/lib/round_driver.py run-verify --session-dir <session dir>"),
        Form("fake.md", 100, 0, "python3 -B <plugin root>/lib/round_driver.py rule --session-dir <session dir>"),
    ]
    assert _population_problems(complete) == []


def test_an_unreplaced_placeholder_is_never_approved(scene):
    session, repo = scene
    broken = "python3 -B <plugin root>/lib/round_driver.py next --session-dir <session dir> --note <unclosed"
    miss = _judge(broken, _PLUGIN, session, repo, decide=lambda payload, roots: True)
    assert miss is not None and "unreplaced placeholder" in miss, miss


def test_judge_reports_a_form_the_hook_does_not_approve(scene):
    session, repo = scene
    form = "python3 -B <plugin root>/lib/round_driver.py next --session-dir <session dir>"
    assert _judge(form, _PLUGIN, session, repo) is None
    miss = _judge(form, _PLUGIN, session, repo, decide=lambda payload, roots: False)
    assert miss is not None and "not approved but must be" in miss, miss
    piped = "python3 -B <plugin root>/lib/round_driver.py next --session-dir <session dir> | tee x"
    miss = _judge(piped, _PLUGIN, session, repo)
    assert miss is not None and "not approved but must be" in miss, miss


@pytest.mark.parametrize("tail", [
    "run-verify --session-dir <session dir>",
    "rule --session-dir <session dir> --ruling-file <rulings file> --by '<who>'",
    "next --session-dir <session dir> --verify-command '<verify command, or none>'",
    "next --session-dir <session dir> --break-it-interpreter=<value>",
    "next --session-dir <session dir> --records-path <records file>",
])
def test_excluded_driver_forms_are_asserted_unapproved(tail, scene):
    session, repo = scene
    form = "python3 -B <plugin root>/lib/round_driver.py " + tail
    assert _expected_approved(form) is False
    assert _judge(form, _PLUGIN, session, repo) is None, "the hook must leave this form to the normal permission check"
    miss = _judge(form, _PLUGIN, session, repo, decide=lambda payload, roots: True)
    assert miss is not None and "approved but must NOT be" in miss, miss
