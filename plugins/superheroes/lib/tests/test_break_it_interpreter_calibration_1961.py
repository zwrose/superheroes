# plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py
"""breakItInterpreter calibration key (#1961 WO-2): core.md storage, read/write CLI, carry on
every rewrite, the review-code config emission, and the configure view.

Token literals are spelled out as strings on purpose: a test that reaches them through the
module constants stays green under any value (rubric/bite-proof.md, external-contract constant).

Detector axes (bite-proof):
- test_c1_* — the key is offered and written, other keys untouched
- test_c2_* — refusals leave core.md bytes unchanged; clear removes the key
- test_c3_* — the suggestion and the configure view offer the key
- test_c4_* — every core.md rewrite carries the stored value raw, malformed included
- test_c5_* — review_code_config emits faithfully and the documented handoff fails closed
- test_c6_* — one validator
"""
import importlib.util
import json
import os
import re
import subprocess
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_LIB = os.path.join(_REPO_ROOT, "plugins/superheroes/lib")
_CORE_MD = os.path.join(_LIB, "core_md.py")

_KEY = "breakItInterpreter"

if _LIB not in sys.path:
    sys.path.insert(0, _LIB)


def _load(name):
    path = os.path.join(_LIB, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CM = _load("core_md")
CV = _load("configure_view")
MR = _load("mode_registry")

import break_it  # noqa: E402
import review_code_config  # noqa: E402
import round_driver  # noqa: E402

_CORE_FACTS = {
    "verifyCommand": "pytest -q",
    "stackTags": ["python"],
    "threatModel": "single-user",
    "patterns": "- x: a.py:1",
}

_SUGGESTION = "scripts/pinned-python"


@pytest.fixture(autouse=True)
def _pin_git(monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _init_repo(d):
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)
    subprocess.run(
        ["git", "-C", str(d), "remote", "add", "origin", "git@github.com:o/r.git"],
        check=True,
    )


def _patch_block(repo, store, updates):
    path = CM.core_path(repo, store)
    text = open(path).read()
    inner = CM._JSON_BLOCK.search(text).group(1)
    block = json.loads(inner)
    block.update(updates)
    open(path, "w").write(text.replace(inner, json.dumps(block, indent=2)))
    return path


def _setup_repo(tmp_path, extra_block=None, status="confirmed"):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _init_repo(tmp_path)
    MR.write_registry(repo, MR.IN_REPO, "rk", root=store)
    CM.write(repo, dict(_CORE_FACTS), status, root=store, now="2026-06-26")
    if extra_block:
        _patch_block(repo, store, extra_block)
    return repo, store


def _setup_core_absent(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _init_repo(tmp_path)
    MR.write_registry(repo, MR.IN_REPO, "rk", root=store)
    return repo, store


def _parsed(repo, store):
    text = open(CM.core_path(repo, store)).read()
    return json.loads(CM._JSON_BLOCK.search(text).group(1))


def _core_bytes(repo, store):
    with open(CM.core_path(repo, store), "rb") as fh:
        return fh.read()


def _cli(verb, repo, store, stdin="", *flags):
    proc = subprocess.run(
        [sys.executable, "-B", _CORE_MD, verb, "--cwd", repo, "--root", store, *flags],
        input=stdin, capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def _make_launcher(repo, mode=0o755):
    path = os.path.join(repo, "scripts", "pinned-python")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("#!/bin/sh\nexec python3 \"$@\"\n")
    os.chmod(path, mode)
    return path


def _section(screen):
    start = screen.index("### Break-it interpreter")
    return screen[start:].split("\n\n", 1)[0]


_NOT_SET_LINE = ("(not set — Python break-it tests take their launcher from the verify command, "
                 "and do not run when it names none)")
_TUNE_LINE = 'set it: /superheroes:configure → "Name the Python launcher for break-it tests"'


# --- literal pins -----------------------------------------------------------------------------

def test_literal_pins():
    # axis: the external-contract literals the docs, the driver and core.md readers match on
    assert CM.BREAK_IT_INTERPRETER_KEY == "breakItInterpreter"
    assert CM.BREAK_IT_INTERPRETER_REASON_MALFORMED == "break-it-interpreter-malformed"
    assert CM.BREAK_IT_INTERPRETER_REASON_INPUT_EMPTY == "break-it-interpreter-input-empty"
    assert CM.BREAK_IT_INTERPRETER_REASON_ROUND_TRIP == "break-it-interpreter-round-trip-refused"
    assert CM.BREAK_IT_INTERPRETER_REASON_UNREADABLE == "break-it-interpreter-unreadable"


# --- C1: written and read ---------------------------------------------------------------------

def test_c1_written_then_read_leaves_other_keys_untouched(tmp_path):
    # axis: C1 the CLI writes the key, the read verb reports it, no other key moves
    repo, store = _setup_repo(tmp_path)
    before = {k: v for k, v in _parsed(repo, store).items() if k != _KEY}
    out = _cli("write-break-it-interpreter", repo, store, "scripts/pinned-python\n")
    assert out == {"action": "written"}
    read = _cli("break-it-interpreter", repo, store)
    assert read["declared"] is True
    assert read["value"] == "scripts/pinned-python"
    assert read["argv"] == ["scripts/pinned-python"]
    assert read["reason"] is None
    after = _parsed(repo, store)
    assert after[_KEY] == "scripts/pinned-python"
    assert {k: v for k, v in after.items() if k != _KEY} == before


def test_c1_multi_word_launcher_round_trips_and_a_repeat_is_noop(tmp_path):
    # axis: C1 a multi-word launcher is stored as typed and parses to its words; same value is noop
    repo, store = _setup_repo(tmp_path)
    assert _cli("write-break-it-interpreter", repo, store, "  uv run python \n") == {
        "action": "written"}
    read = _cli("break-it-interpreter", repo, store)
    assert read["value"] == "uv run python"
    assert read["argv"] == ["uv", "run", "python"]
    assert _cli("write-break-it-interpreter", repo, store, "uv run python\n") == {
        "action": "noop"}


# --- C2: refusals and clear -------------------------------------------------------------------

def test_c2_empty_stdin_is_refused(tmp_path):
    # axis: C2 empty stdin without --clear is a named refusal, never a silent clear
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: "scripts/pinned-python"})
    before = _core_bytes(repo, store)
    out = _cli("write-break-it-interpreter", repo, store, "  \n")
    assert out == {"action": "refused", "reason": "break-it-interpreter-input-empty"}
    assert _core_bytes(repo, store) == before


@pytest.mark.parametrize("text", ["-x", "'unterminated"], ids=repr)
def test_c2_malformed_write_is_refused_and_core_bytes_unchanged(tmp_path, text):
    # axis: C2 a launcher that does not validate is refused before any write — core.md bytes equal
    repo, store = _setup_repo(tmp_path)
    before = _core_bytes(repo, store)
    out = _cli("write-break-it-interpreter", repo, store, text + "\n")
    assert out == {"action": "refused", "reason": "break-it-interpreter-malformed"}
    assert _core_bytes(repo, store) == before


def test_c2_no_core_md_is_refused_core_md_absent(tmp_path):
    # axis: C2 a write with no core.md refuses core-md-absent
    repo, store = _setup_core_absent(tmp_path)
    out = _cli("write-break-it-interpreter", repo, store, "scripts/pinned-python\n")
    assert out == {"action": "refused", "reason": "core-md-absent"}


def test_c2_clear_removes_the_key(tmp_path):
    # axis: C2 --clear removes the key (cleared True) and the read then says not declared
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: "scripts/pinned-python"})
    out = _cli("write-break-it-interpreter", repo, store, "", "--clear")
    assert out == {"action": "written", "cleared": True}
    assert _KEY not in _parsed(repo, store)
    read = _cli("break-it-interpreter", repo, store)
    assert read["declared"] is False
    assert read["value"] is None
    assert read["argv"] is None


# --- the reader: total, read-only, fail-closed -------------------------------------------------

@pytest.mark.parametrize("raw", [5, [], {"a": 1}, True, "-x", "", "'unterminated"], ids=repr)
def test_read_reports_a_stored_malformed_value_as_malformed_never_unset(tmp_path, raw):
    # axis: fail-closed edge 1 — a malformed stored value reads declared, value raw, argv None
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: raw})
    read = CM.read_break_it_interpreter(repo, store)
    assert read["declared"] is True
    assert read["value"] == raw
    assert read["argv"] is None
    assert read["reason"] == "break-it-interpreter-malformed"


def test_read_null_and_absent_are_not_declared(tmp_path):
    # axis: an absent key and a stored null both read not declared
    repo, store = _setup_repo(tmp_path)
    absent = CM.read_break_it_interpreter(repo, store)
    assert (absent["declared"], absent["value"], absent["argv"], absent["reason"]) == (
        False, None, None, None)
    _patch_block(repo, store, {_KEY: None})
    null = CM.read_break_it_interpreter(repo, store)
    assert (null["declared"], null["value"], null["argv"], null["reason"]) == (
        False, None, None, None)


def test_read_core_absent_writes_nothing(tmp_path):
    # axis: fail-closed edge 4 — the reader never writes (no mode-registry backfill) and names core-md-absent
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _init_repo(tmp_path)
    before = sorted(os.path.join(d, n) for d, ds, fs in os.walk(tmp_path) for n in ds + fs
                    if os.sep + ".git" not in os.path.join(d, n))
    read = CM.read_break_it_interpreter(repo, store)
    after = sorted(os.path.join(d, n) for d, ds, fs in os.walk(tmp_path) for n in ds + fs
                   if os.sep + ".git" not in os.path.join(d, n))
    assert read["reason"] == "core-md-absent"
    assert read["suggestion"] is None
    assert after == before
    assert not os.path.exists(store)


def test_read_unparseable_core_md_is_unreadable_with_detail_and_suggestion(tmp_path):
    # axis: fail-closed edge 4 — the reader never raises; an unparseable core.md is a named reason
    repo, store = _setup_repo(tmp_path)
    _make_launcher(repo)
    with open(CM.core_path(repo, store), "w") as fh:
        fh.write("not a core.md at all\n")
    read = CM.read_break_it_interpreter(repo, store)
    assert read["declared"] is False
    assert read["reason"] == "break-it-interpreter-unreadable"
    assert isinstance(read["detail"], str) and read["detail"]
    assert read["suggestion"] == _SUGGESTION


def test_read_never_raises_when_the_path_helper_raises(tmp_path, monkeypatch):
    # axis: fail-closed edge 4 — any unexpected failure is the unreadable reason, never a raise
    repo, store = _setup_repo(tmp_path)

    def boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(CM, "_size_exclude_core_path", boom)
    read = CM.read_break_it_interpreter(repo, store)
    assert read["reason"] == "break-it-interpreter-unreadable"
    assert "suggestion" in read


# --- C3: offered ------------------------------------------------------------------------------

def test_c3_suggestion_follows_the_executable_file(tmp_path):
    # axis: C3 the suggestion is scripts/pinned-python only for an executable regular file
    repo, store = _setup_repo(tmp_path)
    assert _cli("break-it-interpreter", repo, store)["suggestion"] is None
    _make_launcher(repo, mode=0o644)
    assert _cli("break-it-interpreter", repo, store)["suggestion"] is None
    _make_launcher(repo, mode=0o755)
    assert _cli("break-it-interpreter", repo, store)["suggestion"] == _SUGGESTION


def test_c3_suggestion_is_present_on_the_failure_returns(tmp_path):
    # axis: C3 the suggestion key is in every return, core-md-absent included
    repo, store = _setup_core_absent(tmp_path)
    _make_launcher(repo)
    read = CM.read_break_it_interpreter(repo, store)
    assert read["reason"] == "core-md-absent"
    assert read["suggestion"] == _SUGGESTION


def test_c3_view_offers_the_suggestion_when_unset(tmp_path):
    # axis: C3 the view shows the not-set line, the suggestion and the tune action (core branch)
    repo, store = _setup_repo(tmp_path)
    _make_launcher(repo)
    assert _section(CV.render(repo, root=store)).splitlines() == [
        "### Break-it interpreter", _NOT_SET_LINE, "suggested: scripts/pinned-python", _TUNE_LINE]


def test_c3_view_without_a_launcher_file_has_no_suggestion(tmp_path):
    # axis: C3 no executable file, no suggested line
    repo, store = _setup_repo(tmp_path)
    assert _section(CV.render(repo, root=store)).splitlines() == [
        "### Break-it interpreter", _NOT_SET_LINE, _TUNE_LINE]


def test_c3_view_no_core_branch_shows_the_block(tmp_path):
    # axis: C3 the no-core branch renders the block too
    repo, store = _setup_core_absent(tmp_path)
    _make_launcher(repo)
    assert _section(CV.render(repo, root=store)).splitlines() == [
        "### Break-it interpreter", _NOT_SET_LINE, "suggested: scripts/pinned-python", _TUNE_LINE]


def test_c3_view_shows_the_set_value(tmp_path):
    # axis: C3 a stored valid launcher shows as set: <value>
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: "uv run python"})
    assert _section(CV.render(repo, root=store)).splitlines() == [
        "### Break-it interpreter", "set: uv run python", _TUNE_LINE]


def test_c3_view_flags_a_malformed_value(tmp_path):
    # axis: C3 / edge 1 — a stored 5 shows the warning line with the JSON of the value
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: 5})
    assert _section(CV.render(repo, root=store)).splitlines() == [
        "### Break-it interpreter",
        "⚠ malformed: 5 — Python break-it tests will not run until it is fixed or cleared",
        _TUNE_LINE]


def test_c3_view_read_failure_names_the_reason(tmp_path, monkeypatch):
    # axis: C3 a read that raises renders the unreadable line with its reason, never a crash
    repo, store = _setup_repo(tmp_path)

    def boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(CV.core_md, "read_break_it_interpreter", boom)
    assert _section(CV.render(repo, root=store)).splitlines() == [
        "### Break-it interpreter",
        "⚠ break-it interpreter unreadable: break-it-interpreter-read-failed",
        _TUNE_LINE]


def test_c3_view_collect_carries_the_read(tmp_path):
    # axis: C3 collect() returns the read under breakItInterpreter
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: "scripts/pinned-python"})
    data = CV.collect(repo, store)
    assert data["breakItInterpreter"]["value"] == "scripts/pinned-python"


# --- C4: carried on rewrite -------------------------------------------------------------------

_CARRIED = {"valid": "scripts/pinned-python", "malformed-int": 5, "null": None,
            "malformed-dash": "-x"}


@pytest.mark.parametrize("raw", list(_CARRIED.values()), ids=list(_CARRIED))
def test_c4_confirm_carries_the_value(tmp_path, raw):
    # axis: C4 confirm (provisional to confirmed) re-renders core.md and keeps the key raw
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: raw}, status="provisional")
    assert CM.confirm_all(repo, root=store)["core"]["action"] == "confirmed"
    parsed = _parsed(repo, store)
    assert _KEY in parsed
    assert parsed[_KEY] == raw


@pytest.mark.parametrize("raw", list(_CARRIED.values()), ids=list(_CARRIED))
def test_c4_parse_then_render_carries_the_value(raw):
    # axis: C4 parse_core then render_core keeps the key raw, malformed and null included
    text = CM.render_core(dict(_CORE_FACTS, **{_KEY: raw}), "confirmed", "2026-06-26",
                          "2026-06-26")
    facts = CM.parse_core(text)
    assert _KEY in facts
    assert facts[_KEY] == raw
    again = CM.parse_core(CM.render_core(facts, "confirmed", "2026-06-26", "2026-06-26"))
    assert _KEY in again
    assert again[_KEY] == raw


def test_c4_absent_stays_absent(tmp_path):
    # axis: C4 a core.md without the key gains none on parse/render/read/confirm
    text = CM.render_core(dict(_CORE_FACTS), "confirmed", "2026-06-26", "2026-06-26")
    assert _KEY not in CM.parse_core(text)
    repo, store = _setup_repo(tmp_path, status="provisional")
    assert _KEY not in CM.read(repo, store)
    CM.confirm_all(repo, root=store)
    assert _KEY not in _parsed(repo, store)


@pytest.mark.parametrize("raw", [5, "scripts/pinned-python"], ids=repr)
def test_c4_read_exposes_the_raw_value(tmp_path, raw):
    # axis: C4 read() carries the stored value raw
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: raw})
    assert CM.read(repo, store)[_KEY] == raw


def test_c4_sibling_writers_leave_the_key_intact(tmp_path):
    # axis: C4 / edge 3 — the other surgical writers keep the key byte-for-byte
    repo, store = _setup_repo(tmp_path, extra_block={_KEY: 5})
    checks = [{"name": "A", "evidence": "e", "records": "r"}]
    assert CM.write_vet_checks(repo, checks, root=store)["action"] == "written"
    assert _parsed(repo, store)[_KEY] == 5
    assert CM.write_size_exclude(repo, ["docs/**"], root=store)["action"] == "written"
    assert _parsed(repo, store)[_KEY] == 5


def test_c4_the_launcher_writer_leaves_sibling_keys_intact(tmp_path):
    # axis: C4 writing the key moves no sibling key (size exclusion, vet checks)
    repo, store = _setup_repo(tmp_path, extra_block={"sizeExclude": ["docs/**"]})
    before = {k: v for k, v in _parsed(repo, store).items() if k != _KEY}
    assert CM.write_break_it_interpreter(repo, "uv run python", root=store)["action"] == "written"
    assert CM.clear_break_it_interpreter(repo, root=store)["action"] == "written"
    assert _parsed(repo, store) == before


# --- C5: config emission and the documented handoff -------------------------------------------

_SETUP_MD = os.path.join(_REPO_ROOT, "plugins/superheroes/skills/review-code/reference/setup.md")


def _shipped_handoff_script():
    """The fenced bash block of skills/review-code/reference/setup.md that builds BREAK_IT_ARGS,
    minus its `VERIFY_JSON=$(...)` assignment (the test supplies VERIFY_JSON in the environment)."""
    text = open(_SETUP_MD).read()
    blocks = [m.group(1) for m in re.finditer(r"```bash\n(.*?)```", text, re.S)]
    hits = [b for b in blocks if "BREAK_IT_ARGS" in b]
    assert len(hits) == 1
    lines = [ln for ln in hits[0].splitlines() if not ln.startswith("VERIFY_JSON=$(")]
    assert any(ln.startswith("BREAK_IT_ARGS=(") for ln in lines)
    return "\n".join(lines) + "\nif [ ${#BREAK_IT_ARGS[@]} -gt 0 ]; then printf '%s\\0' \"${BREAK_IT_ARGS[@]}\"; fi\n"


def _break_it_args(verify_json):
    """Run the SHIPPED setup.md shell with VERIFY_JSON and return the argv it hands the driver."""
    env = dict(os.environ, VERIFY_JSON=verify_json, CLAUDE_PLUGIN_ROOT=os.path.join(_REPO_ROOT, "plugins/superheroes"))
    proc = subprocess.run(["bash", "-c", _shipped_handoff_script()], env=env,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return [a for a in proc.stdout.split("\0")][:-1]


@pytest.mark.parametrize("value,expected", [
    (None, []),
    ("", ["--break-it-interpreter="]),
    ("-x", ["--break-it-interpreter=-x"]),
    ("uv run python", ["--break-it-interpreter=uv run python"]),
])
def test_c5_the_shipped_shell_builds_the_handoff_argv(value, expected):
    # axis: C5 the setup.md snippet itself passes the flag on presence (not non-empty), as one argv element
    resolved = {"verifyCommand": "pytest -q", "verifyRefusal": None}
    assert _break_it_args(json.dumps({**resolved, _KEY: value})) == expected
    assert _break_it_args(json.dumps(resolved)) == []


def _driver_state(tmp_path, next_args):
    """Run the real `round_driver next` on a fresh session with the handoff args and return the
    saved state's config."""
    import test_break_it_interpreter_key_1961 as K
    d = str(tmp_path / "s")
    os.makedirs(d)
    assert round_driver.main(["next", "--session-dir", d] + list(next_args) + K._guard_argv(d)) == 0
    ok, state = round_driver.load_state(d)
    assert ok
    return state["config"]


_EMISSIONS = {
    "absent": (None, None, None),
    "null": ({_KEY: None}, None, None),
    "valid": ({_KEY: "scripts/pinned-python"}, "scripts/pinned-python", ["scripts/pinned-python"]),
    "invalid-string": ({_KEY: "-x"}, "-x", []),
    "non-string": ({_KEY: 5}, "", []),
}


@pytest.mark.parametrize("case", list(_EMISSIONS), ids=list(_EMISSIONS))
def test_c5_emission_then_handoff_fails_closed(tmp_path, monkeypatch, case):
    # axis: C5 resolve emits null / verbatim string / "" faithfully and the setup handoff turns each into the driver's answer
    block, emitted, launcher = _EMISSIONS[case]
    repo, store = _setup_repo(tmp_path, extra_block=block)
    import calibration_resolve
    monkeypatch.setattr(calibration_resolve, "resolve",
                        lambda cwd, root=None, **kw: {"exists": False, "dispatch_layer": None,
                                                      "legacy_path": None})
    out = review_code_config.resolve(repo, root=store)
    assert out["verifyCommand"] == "pytest -q"
    assert out[_KEY] == emitted
    assert (out[_KEY] is None) == (emitted is None)
    cfg = _driver_state(tmp_path, _break_it_args(json.dumps(out)))
    assert (_KEY in cfg) == (emitted is not None)
    if emitted is not None:
        assert cfg[_KEY] == emitted
    assert break_it.resolve_interpreter(cfg) == launcher


def test_c5_no_core_md_emits_null(tmp_path):
    # axis: C5 no core record means the key is not set (null)
    repo, store = _setup_core_absent(tmp_path)
    assert review_code_config.resolve(repo, root=store)[_KEY] is None


def test_c5_a_refusal_emits_null(tmp_path):
    # axis: C5 a calibration refusal (legacy profile only) carries no key
    repo, store = _setup_core_absent(tmp_path)
    prof = os.path.join(repo, ".claude", "review-profile.md")
    os.makedirs(os.path.dirname(prof), exist_ok=True)
    open(prof, "w").write("## Verify\ncommand: make test\n")
    out = review_code_config.resolve(repo, root=store)
    assert out["calibrationRefusal"]["reason"] == "legacy-profile-unsupported"
    assert out[_KEY] is None


def test_c5_the_other_output_keys_are_unchanged(tmp_path):
    # axis: C5 resolve adds exactly one key
    repo, store = _setup_repo(tmp_path)
    assert set(review_code_config.resolve(repo, root=store)) == {
        "verifyCommand", "verifyRefusal", "tiers", "calibrationRefusal", "breakItInterpreter"}


# --- C6: one validator ------------------------------------------------------------------------

def test_c6_one_validator():
    # axis: C6 core_md's key and validator are break_it's
    assert CM.BREAK_IT_INTERPRETER_KEY is break_it.INTERPRETER_KEY
    for value in ["scripts/pinned-python", "uv run python", "  python3  ", "-x", "'unterminated",
                  "", "   ", None, 5, ["a"], {"a": 1}, True, "a 'b c' d"]:
        assert CM.break_it_interpreter_argv(value) == break_it.launcher_argv(value), repr(value)
