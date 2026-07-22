"""guardian_lens_docs: the doc-freshness lens (genuinely tool-free).

The lens spawns nothing: the repo root is `ctx["cwd"]` and the calibrated verify command
is `ctx["verifyCommand"]`, both handed in by the sweep — collect() reads no core.md and
runs no git. These unit tests mirror the sweep by resolving the calibration once (via
`core_md.read`, which the TEST is free to do) and threading the result onto ctx, exactly
as `guardian_sweep.collect` does. The `run` in ctx is a no-op the lens never calls; it is
kept only so the never-execute safety test can prove the lens spawns nothing at all.
"""
import os
import subprocess

import pytest

import core_md as cm
import guardian_lens as gl
import guardian_lens_docs as m
from guardian_fixtures import init_calibrated_repo


class _R(object):
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class Recorder(object):
    """Injectable `run` the tool-free lens must NEVER call.

    Every argv is recorded and refused, so a test can assert what the lens tried to run —
    in particular, that it ran nothing at all (the lens is tool-free) and never the verify
    command.
    """

    def __init__(self, repo):
        self.repo = repo
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        return _R(127, "", "not stubbed")


def _ctx(repo, tmp_path, prev=None):
    """Build the lens ctx the way `guardian_sweep.collect` does.

    The calibrated verify command is resolved ONCE from core.md here (the sweep does this
    in `verify_config`) and threaded onto ctx as `verifyCommand`; the lens itself reads no
    core.md and spawns no git. A removed/empty core.md yields a None/empty verifyCommand,
    which the lens treats as "no calibration".
    """
    run = Recorder(repo)
    core = cm.read(repo, str(tmp_path / "store"))
    return {
        "cwd": repo,
        "root": str(tmp_path / "store"),
        "config": {},
        "run": run,
        "prevDigest": prev,
        "verifyCommand": (core or {}).get("verifyCommand"),
    }, run


def _write(repo, name, text):
    path = os.path.join(repo, name)
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


# --------------------------------------------------------------------------- contract


def test_lens_satisfies_the_contract():
    ok, reasons = gl.validate_lens(m.LENS)
    assert ok is True, reasons


def test_lens_identity_and_facts():
    assert m.LENS.name == "docs"
    assert m.LENS.collector_version == "1.0.0"
    assert m.LENS.required_facts == ()
    assert isinstance(m.LENS.cost.get("collectorSeconds"), float)


def test_degrade_shape():
    assert m.LENS.degrade("why") == {
        "lens": "docs", "degraded": True, "reason": "why"}


def test_red_lines_is_always_empty():
    assert m.LENS.red_lines([{"id": "docs:ref:CLAUDE.md:gone.py", "metric": 9}]) == []


def test_docstring_states_the_no_execution_boundary():
    doc = m.__doc__
    assert "NEVER RUNS the verify command" in doc
    assert "guardian_sweep.verify_config" in doc
    assert "#539" in doc


def test_relative_to_what_ambiguity_named_in_validation_guidance():
    """The validation pass must name this candidate class — guidance drift is a defect."""
    assert "relative-to-what ambiguity" in m.LENS.validation_guidance


# ------------------------------------------------------------- mechanical filter


@pytest.mark.parametrize("token", [
    "https://example.com/a/b.md",
    "http://example.com",
    "mailto:someone@example.com",
    "//cdn.example.com/x.js",
    "www.example.com/docs.md",
])
def test_mechanical_filter_drops_urls(token):
    path, drop = m.normalize_candidate(token)
    assert path is None
    assert drop == "url"


def test_mechanical_filter_drops_bare_anchor():
    assert m.normalize_candidate("#section-7") == (None, "anchor")


@pytest.mark.parametrize("token", [
    "docs/<work-item>/plan.md",
    "lib/${MODULE}.py",
    "plugins/superheroes/**",
    "src/*.ts",
    "path/to/…/file.md",
    "a/b/....md",
])
def test_mechanical_filter_drops_placeholders_and_globs(token):
    path, drop = m.normalize_candidate(token)
    assert path is None
    assert drop == "placeholder"


@pytest.mark.parametrize("token", ["and", "the", "reviewer", "well-scoped"])
def test_mechanical_filter_drops_prose_words(token):
    path, drop = m.normalize_candidate(token)
    assert path is None
    assert drop == "prose-token"


@pytest.mark.parametrize("token", ["issue/PR", "UI/UX", "merge/release/force-push"])
def test_mechanical_filter_drops_slash_as_or(token):
    path, drop = m.normalize_candidate(token)
    assert path is None
    assert drop == "prose-alternative"


@pytest.mark.parametrize("token", ["/etc/hosts", "~/.claude/settings.json", "C:\\repo\\a.md"])
def test_mechanical_filter_drops_out_of_repo_paths(token):
    path, drop = m.normalize_candidate(token)
    assert path is None
    assert drop == "outside-repo"


@pytest.mark.parametrize("token", ["§4.1/§4.3", "spec↔spec.md"])
def test_mechanical_filter_drops_typography(token):
    path, drop = m.normalize_candidate(token)
    assert path is None
    assert drop == "typographic"


@pytest.mark.parametrize("token,expected", [
    ("lib/store_core.py", "lib/store_core.py"),
    ("**README.md**", "README.md"),
    ("(CONVENTIONS.md)", "CONVENTIONS.md"),
    ("./scripts/run.sh", "scripts/run.sh"),
    ("CONVENTIONS.md#7.4", "CONVENTIONS.md"),
    ("lib/tests/test_x.py::test_case", "lib/tests/test_x.py"),
    ("plugins/superheroes/", "plugins/superheroes/"),
])
def test_mechanical_filter_keeps_real_paths(token, expected):
    path, drop = m.normalize_candidate(token)
    assert drop is None
    assert path == expected


@pytest.mark.parametrize("token", [".gitignore", ".env", ".claude/settings.json"])
def test_mechanical_filter_keeps_recognized_dotfiles(token):
    """KNOWN_EXTENSIONS lists .gitignore/.env — bare dotfiles must not drop as prose-token.

    os.path.splitext('.gitignore') yields ('', '') / ('.gitignore', '') so a naive
    extension check falsely classifies them as prose words.
    """
    path, drop = m.normalize_candidate(token)
    assert drop is None, "dotfile %r dropped as %r" % (token, drop)
    assert path == token


def test_every_drop_class_is_declared():
    """A new drop class must be declared in DROP_CLASSES so the funnel stays auditable."""
    tokens = [
        "", "#a", "http://x", "<x>", "/abs", "§", "word", "a/B", "a/b.py"]
    for tok in tokens:
        _p, drop = m.normalize_candidate(tok)
        assert drop is None or drop in m.DROP_CLASSES


def test_anchoring_drops_context_relative_shorthand(tmp_path):
    repo = str(tmp_path)
    os.makedirs(os.path.join(repo, "plugins"))
    # `plugins` exists at the root, `lib` does not.
    assert m.is_anchored(repo, "plugins/superheroes/lib/x.py") is True
    assert m.is_anchored(repo, "lib/store_core.py") is False
    assert m.is_anchored(repo, "plugin.json") is False


# ------------------------------------------------------------------ reference collect


def test_broken_reference_becomes_a_candidate(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    os.makedirs(os.path.join(repo, "lib"))
    _write(repo, "lib/present.py", "x = 1\n")
    _write(repo, "CLAUDE.md",
           "# Guide\n\nRead `lib/gone.py` before building.\n")
    ctx, _run = _ctx(repo, tmp_path)

    out = m.LENS.collect(ctx)
    ids = [c["id"] for c in out["candidates"]]
    assert "docs:ref:CLAUDE.md:lib/gone.py" in ids
    cand = [c for c in out["candidates"] if c["path"] == "lib/gone.py"][0]
    assert cand["metric"] == 1
    assert "lib/gone.py" in cand["receipt"]
    assert "CLAUDE.md:3" in cand["receipt"]


def test_resolved_reference_is_not_a_candidate(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    os.makedirs(os.path.join(repo, "lib"))
    _write(repo, "lib/present.py", "x = 1\n")
    _write(repo, "CLAUDE.md", "Read `lib/present.py`.\n")
    ctx, _run = _ctx(repo, tmp_path)

    out = m.LENS.collect(ctx)
    assert [c["id"] for c in out["candidates"]] == []


def test_digest_records_both_resolution_states(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    os.makedirs(os.path.join(repo, "lib"))
    _write(repo, "lib/present.py", "x = 1\n")
    _write(repo, "CLAUDE.md", "Read `lib/present.py` and `lib/gone.py`.\n")
    ctx, _run = _ctx(repo, tmp_path)

    refs = m.LENS.collect(ctx)["digest"]["references"]
    assert refs["docs:ref:CLAUDE.md:lib/present.py"]["resolved"] is True
    assert refs["docs:ref:CLAUDE.md:lib/gone.py"]["resolved"] is False


def test_occurrences_are_aggregated_into_one_candidate(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    os.makedirs(os.path.join(repo, "lib"))
    _write(repo, "lib/keep.py", "x = 1\n")
    _write(repo, "CLAUDE.md",
           "See `lib/gone.py`.\n\nAlso `lib/gone.py`.\n\nAnd again `lib/gone.py`.\n")
    ctx, _run = _ctx(repo, tmp_path)

    out = m.LENS.collect(ctx)
    assert len(out["candidates"]) == 1
    assert out["candidates"][0]["metric"] == 3
    assert out["candidates"][0]["lines"] == [1, 3, 5]


def test_candidate_id_is_line_independent(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    os.makedirs(os.path.join(repo, "lib"))
    _write(repo, "lib/keep.py", "x = 1\n")
    _write(repo, "CLAUDE.md", "Read `lib/gone.py`.\n")
    ctx, _run = _ctx(repo, tmp_path)
    first = m.LENS.collect(ctx)

    _write(repo, "CLAUDE.md", ("filler\n" * 40) + "Read `lib/gone.py`.\n")
    ctx2, _run2 = _ctx(repo, tmp_path)
    second = m.LENS.collect(ctx2)

    assert [c["id"] for c in first["candidates"]] == [c["id"] for c in second["candidates"]]
    assert first["candidates"][0]["lines"] != second["candidates"][0]["lines"]


def test_markdown_link_target_is_extracted(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    os.makedirs(os.path.join(repo, "docs"))
    _write(repo, "docs/keep.md", "ok\n")
    _write(repo, "README.md", "See [the plan](docs/plan.md) for details.\n")
    ctx, _run = _ctx(repo, tmp_path)

    ids = [c["id"] for c in m.LENS.collect(ctx)["candidates"]]
    assert "docs:ref:README.md:docs/plan.md" in ids


def test_funnel_counts_are_recorded(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    os.makedirs(os.path.join(repo, "lib"))
    _write(repo, "lib/keep.py", "x = 1\n")
    _write(repo, "CLAUDE.md",
           "Read `lib/gone.py` at https://example.com/x.md for <the-thing>.\n")
    ctx, _run = _ctx(repo, tmp_path)

    funnel = m.LENS.collect(ctx)["digest"]["funnel"]
    assert funnel["extracted"] > funnel["afterMechanical"]
    assert funnel["drops"]["url"] >= 1
    assert funnel["drops"]["placeholder"] >= 1
    assert funnel["unresolved"] == 1


def test_funnel_separates_doc_refs_from_verify_paths(tmp_path):
    """The mechanical-filter stage count must not absorb rows that never went through it."""
    repo = init_calibrated_repo(tmp_path, verify_command="python3 scripts/check.py")
    os.makedirs(os.path.join(repo, "scripts"))
    _write(repo, "scripts/check.py", "print(1)\n")
    _write(repo, "CLAUDE.md", "Read `scripts/check.py` and `scripts/gone.py`.\n")
    ctx, _run = _ctx(repo, tmp_path)

    out = m.LENS.collect(ctx)
    f = out["digest"]["funnel"]
    assert f["uniqueReferences"] == 2          # two doc references
    assert f["unresolvedReferences"] == 1      # one of them broken
    assert f["verifyPathsChecked"] == 1        # one verify path, counted separately
    assert f["unresolved"] == len(out["candidates"])
    assert len(out["digest"]["references"]) == 3


def test_verify_command_same_script_in_two_steps_is_one_candidate(tmp_path):
    repo = init_calibrated_repo(
        tmp_path,
        verify_command="python3 scripts/gone.py --a && python3 scripts/gone.py --b")
    os.makedirs(os.path.join(repo, "scripts"))
    _write(repo, "scripts/keep.py", "x = 1\n")
    _write(repo, "README.md", "hi\n")
    ctx, _run = _ctx(repo, tmp_path)

    ids = [c["id"] for c in m.LENS.collect(ctx)["candidates"]]
    assert ids.count("docs:verify-cmd:scripts/gone.py") == 1


def test_docs_read_and_absent_are_recorded(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    _write(repo, "CLAUDE.md", "hi\n")
    ctx, _run = _ctx(repo, tmp_path)

    digest = m.LENS.collect(ctx)["digest"]
    assert digest["docsRead"] == ["CLAUDE.md"]
    assert digest["docsAbsent"] == ["README.md", "CONVENTIONS.md"]


# -------------------------------------------------------------------- fail-closed


def test_all_three_docs_absent_but_verify_collectable_is_partial(tmp_path):
    """Reference subcheck cannot run, but verify-command still can — that is partial,
    never whole-lens not-collected. The missing-docs reason must still land in
    degradedLenses (via partial), so 'never silently clean' survives.
    """
    repo = init_calibrated_repo(
        tmp_path, verify_command="python3 scripts/check.py")
    ctx, _run = _ctx(repo, tmp_path)

    out = m.LENS.collect(ctx)
    assert out["status"] == "partial"
    assert "CLAUDE.md" in out["reason"] and "CONVENTIONS.md" in out["reason"]
    assert out["digest"] is not None
    assert out["digest"]["docsRead"] == []
    assert out["digest"]["verifyCommand"]["status"] == "collected"
    assert "docs:verify-cmd:scripts/check.py" in out["digest"]["references"]
    # Path does not exist → candidate kept, not discarded with the missing docs.
    assert any(c["id"] == "docs:verify-cmd:scripts/check.py" for c in out["candidates"])


def test_neither_subcheck_collectable_is_not_collected_never_clean(tmp_path):
    repo = init_calibrated_repo(tmp_path, verify_command="")
    os.remove(os.path.join(repo, ".claude", "superheroes", "core.md"))
    ctx, _run = _ctx(repo, tmp_path)

    out = m.LENS.collect(ctx)
    assert out["status"] == "not-collected"
    assert out["candidates"] == []
    assert "CLAUDE.md" in out["reason"] and "CONVENTIONS.md" in out["reason"]
    assert out.get("status") != "collected"


def test_unreadable_doc_degrades_to_partial(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    _write(repo, "README.md", "fine\n")
    with open(os.path.join(repo, "CLAUDE.md"), "wb") as fh:
        fh.write(b"\xff\xfe not utf-8")
    ctx, _run = _ctx(repo, tmp_path)

    out = m.LENS.collect(ctx)
    assert out["status"] == "partial"
    assert "CLAUDE.md" in out["reason"]
    assert out["digest"]["docsUnreadable"] == ["CLAUDE.md"]


def test_unreadable_doc_produces_no_false_resolved_and_carries_prev_forward(tmp_path):
    """The core drift-honesty property: a doc we could not read this run must not make
    its previously-broken references look fixed."""
    repo = init_calibrated_repo(tmp_path)
    os.makedirs(os.path.join(repo, "lib"))
    _write(repo, "lib/keep.py", "x = 1\n")
    _write(repo, "README.md", "fine\n")
    _write(repo, "CLAUDE.md", "Read `lib/gone.py`.\n")
    ctx, _run = _ctx(repo, tmp_path)
    first = m.LENS.collect(ctx)
    assert first["status"] == "collected"
    broken_id = "docs:ref:CLAUDE.md:lib/gone.py"
    assert first["digest"]["references"][broken_id]["resolved"] is False

    with open(os.path.join(repo, "CLAUDE.md"), "wb") as fh:
        fh.write(b"\xff\xfe not utf-8")
    ctx2, _run2 = _ctx(repo, tmp_path, prev=first["digest"])
    second = m.LENS.collect(ctx2)

    assert second["status"] == "partial"
    carried = second["digest"]["references"][broken_id]
    assert carried["resolved"] is False
    assert carried["carriedForward"] is True
    d = m.LENS.diff(first["digest"], second["digest"])
    assert broken_id not in d["resolved"]
    assert broken_id not in d["new"]


# ------------------------------------------------------------- verify-command subcheck


def test_verify_command_dangling_script_is_a_candidate(tmp_path):
    repo = init_calibrated_repo(
        tmp_path, verify_command="python3 .github/scripts/gone.py --strict")
    _write(repo, "README.md", "hi\n")
    ctx, run = _ctx(repo, tmp_path)

    out = m.LENS.collect(ctx)
    ids = [c["id"] for c in out["candidates"]]
    assert "docs:verify-cmd:.github/scripts/gone.py" in ids
    cand = [c for c in out["candidates"] if c["id"].startswith("docs:verify-cmd:")][0]
    assert "python3 .github/scripts/gone.py --strict" in cand["receipt"]
    assert "NOT" in cand["receipt"]
    assert cand["metric"] == 1
    assert out["status"] == "collected"


def test_verify_command_live_script_is_recorded_resolved(tmp_path):
    repo = init_calibrated_repo(
        tmp_path, verify_command="python3 scripts/check.py")
    os.makedirs(os.path.join(repo, "scripts"))
    _write(repo, "scripts/check.py", "print(1)\n")
    _write(repo, "README.md", "hi\n")
    ctx, _run = _ctx(repo, tmp_path)

    out = m.LENS.collect(ctx)
    rec = out["digest"]["references"]["docs:verify-cmd:scripts/check.py"]
    assert rec["resolved"] is True
    assert [c["id"] for c in out["candidates"]] == []


def test_verify_command_is_never_executed(tmp_path, monkeypatch):
    """Reads verifyCommand paths; must never execute the command — and, being tool-free,
    must spawn NOTHING at all during collect().

    Spies on the real subprocess channel (set AFTER fixture + calibration read, so the
    test's own git/core.md reads are not counted) and on ctx["run"]. The lens now resolves
    the repo root from ctx["cwd"] and the verify command from ctx["verifyCommand"], so a
    correct collect() records zero calls on either channel. Asserting the set is EMPTY is a
    strictly stronger guarantee than "did not run the verify command", and it cannot pass
    vacuously — a regression that reintroduced any spawn would make the set non-empty.
    """
    verify_script = ".github/scripts/gone.py"
    verify_cmd = "python3 " + verify_script
    repo = init_calibrated_repo(tmp_path, verify_command=verify_cmd)
    _write(repo, "README.md", "hi\n")
    ctx, run = _ctx(repo, tmp_path)

    recorded = []
    real_run = subprocess.run

    def spy_run(argv, *args, **kwargs):
        recorded.append(argv)
        return real_run(argv, *args, **kwargs)

    # Capture real invocations after fixture setup + calibration read (both use subprocess).
    monkeypatch.setattr(subprocess, "run", spy_run)

    out = m.LENS.collect(ctx)

    # Positive: path resolution still happens ("reads, never runs" — not "ignores").
    assert "docs:verify-cmd:" + verify_script in [c["id"] for c in out["candidates"]]

    all_calls = list(recorded) + list(run.calls)
    assert all_calls == [], (
        "the tool-free docs lens must spawn nothing during collect() (no git, no "
        "subprocess, and it must never call ctx['run']); observed: %r" % (all_calls,))


def test_absent_verify_command_is_partial_with_reason(tmp_path):
    repo = init_calibrated_repo(tmp_path, verify_command="")
    _write(repo, "README.md", "hi\n")
    ctx, _run = _ctx(repo, tmp_path)

    out = m.LENS.collect(ctx)
    assert out["status"] == "partial"
    assert "verifyCommand" in out["reason"]
    assert out["digest"]["verifyCommand"]["status"] == "not-collected"


def test_absent_calibration_is_partial_not_clean(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    os.remove(os.path.join(repo, ".claude", "superheroes", "core.md"))
    _write(repo, "README.md", "hi\n")
    ctx, _run = _ctx(repo, tmp_path)

    out = m.LENS.collect(ctx)
    assert out["status"] == "partial"
    assert "no calibration" in out["reason"]


def test_uncollected_verify_subcheck_carries_prev_digest_forward(tmp_path):
    repo = init_calibrated_repo(
        tmp_path, verify_command="python3 .github/scripts/gone.py")
    _write(repo, "README.md", "hi\n")
    ctx, _run = _ctx(repo, tmp_path)
    first = m.LENS.collect(ctx)
    vid = "docs:verify-cmd:.github/scripts/gone.py"
    assert first["digest"]["references"][vid]["resolved"] is False

    os.remove(os.path.join(repo, ".claude", "superheroes", "core.md"))
    ctx2, _run2 = _ctx(repo, tmp_path, prev=first["digest"])
    second = m.LENS.collect(ctx2)

    assert second["status"] == "partial"
    assert second["digest"]["references"][vid]["carriedForward"] is True
    assert vid not in m.LENS.diff(first["digest"], second["digest"])["resolved"]


def test_verify_command_paths_ignores_flags_and_executables():
    paths = [p for p, _step in m.verify_command_paths(
        "python3 -m pytest -q plugins/lib/tests/ && node scripts/smoke.js")]
    assert "plugins/lib/tests/" in paths
    assert "scripts/smoke.js" in paths
    assert "pytest" not in paths
    assert "-q" not in paths


# --------------------------------------------------------------------------- drift


def _digest(refs):
    return {"schemaVersion": m.DIGEST_SCHEMA_VERSION, "references": refs}


def test_diff_none_cur_never_resolves_prior_refs():
    """A3(i): a degraded sweep returns digest=None. diff(prev_with_refs, None) must claim
    no movement (the sibling guard deps/deadcode already have). Without it, `_refs_of(None)`
    is {} and every prior unresolved reference reads as `resolved` — a false clean for
    findings this sweep never re-measured. A cur dict with no references map is treated the
    same way. Reverting the guard makes both diffs resolve the prior ref → this bites."""
    prev = _digest({"docs:ref:CLAUDE.md:lib/gone.py":
                    {"resolved": False, "occurrences": 1}})
    assert m.LENS.diff(prev, None) == {"new": [], "worsened": [], "resolved": []}
    assert m.LENS.diff(prev, {"schemaVersion": m.DIGEST_SCHEMA_VERSION}) == {
        "new": [], "worsened": [], "resolved": []}


def test_all_docs_absent_carries_prior_ref_forward_no_false_resolved(tmp_path):
    """A3(ii): a prior broken CLAUDE.md reference, then ALL root docs absent while the
    verify subcheck still collects → `partial`; the CLAUDE.md reference is CARRIED FORWARD
    (never `resolved`). A doc not read this sweep was not re-measured, so its references
    must survive rather than read as fixed. Reverting the absent-doc carry-forward drops the
    reference from the digest and diff() resolves it → both the carry and the no-resolve
    assertions bite."""
    repo = init_calibrated_repo(tmp_path, verify_command="python3 scripts/check.py")
    os.makedirs(os.path.join(repo, "lib"))
    _write(repo, "lib/keep.py", "x = 1\n")
    os.makedirs(os.path.join(repo, "scripts"))
    _write(repo, "scripts/check.py", "print(1)\n")
    _write(repo, "CLAUDE.md", "Read `lib/gone.py`.\n")
    ctx, _run = _ctx(repo, tmp_path)
    first = m.LENS.collect(ctx)
    broken_id = "docs:ref:CLAUDE.md:lib/gone.py"
    assert first["digest"]["references"][broken_id]["resolved"] is False

    # All root instruction docs vanish this sweep; verify command still collects.
    for name in ("CLAUDE.md", "README.md", "CONVENTIONS.md"):
        p = os.path.join(repo, name)
        if os.path.isfile(p):
            os.remove(p)
    ctx2, _run2 = _ctx(repo, tmp_path, prev=first["digest"])
    second = m.LENS.collect(ctx2)

    assert second["status"] == "partial"
    assert second["digest"]["docsRead"] == []
    assert second["digest"]["verifyCommand"]["status"] == "collected"
    carried = second["digest"]["references"][broken_id]
    assert carried["resolved"] is False
    assert carried.get("carriedForward") is True
    d = m.LENS.diff(first["digest"], second["digest"])
    assert broken_id not in d["resolved"]
    assert broken_id not in d["new"]


def test_diff_resolved_then_broken_is_new():
    prev = _digest({"docs:ref:CLAUDE.md:a.md": {"resolved": True, "occurrences": 1}})
    cur = _digest({"docs:ref:CLAUDE.md:a.md": {"resolved": False, "occurrences": 1}})
    assert m.LENS.diff(prev, cur) == {
        "new": ["docs:ref:CLAUDE.md:a.md"], "worsened": [], "resolved": []}


def test_diff_newly_present_and_already_broken_is_new():
    prev = _digest({})
    cur = _digest({"docs:ref:CLAUDE.md:a.md": {"resolved": False, "occurrences": 1}})
    assert m.LENS.diff(prev, cur)["new"] == ["docs:ref:CLAUDE.md:a.md"]


def test_diff_broken_then_fixed_is_resolved():
    prev = _digest({"docs:ref:CLAUDE.md:a.md": {"resolved": False, "occurrences": 1}})
    cur = _digest({"docs:ref:CLAUDE.md:a.md": {"resolved": True, "occurrences": 1}})
    assert m.LENS.diff(prev, cur)["resolved"] == ["docs:ref:CLAUDE.md:a.md"]


def test_diff_disappeared_reference_is_resolved():
    prev = _digest({"docs:ref:CLAUDE.md:a.md": {"resolved": False, "occurrences": 1}})
    cur = _digest({})
    assert m.LENS.diff(prev, cur)["resolved"] == ["docs:ref:CLAUDE.md:a.md"]


def test_diff_more_occurrences_is_worsened():
    prev = _digest({"docs:ref:CLAUDE.md:a.md": {"resolved": False, "occurrences": 1}})
    cur = _digest({"docs:ref:CLAUDE.md:a.md": {"resolved": False, "occurrences": 4}})
    d = m.LENS.diff(prev, cur)
    assert d["worsened"] == ["docs:ref:CLAUDE.md:a.md"]
    assert d["new"] == []


def test_diff_steady_broken_reference_is_quiet():
    prev = _digest({"docs:ref:CLAUDE.md:a.md": {"resolved": False, "occurrences": 2}})
    cur = _digest({"docs:ref:CLAUDE.md:a.md": {"resolved": False, "occurrences": 2}})
    assert m.LENS.diff(prev, cur) == {"new": [], "worsened": [], "resolved": []}


def test_diff_tolerates_missing_and_malformed_digests():
    assert m.LENS.diff(None, None) == {"new": [], "worsened": [], "resolved": []}
    assert m.LENS.diff("junk", {"references": "junk"}) == {
        "new": [], "worsened": [], "resolved": []}


def test_end_to_end_drift_resolved_then_broken(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    os.makedirs(os.path.join(repo, "lib"))
    _write(repo, "lib/target.py", "x = 1\n")
    _write(repo, "CLAUDE.md", "Read `lib/target.py`.\n")
    ctx, _run = _ctx(repo, tmp_path)
    first = m.LENS.collect(ctx)
    rid = "docs:ref:CLAUDE.md:lib/target.py"
    assert first["digest"]["references"][rid]["resolved"] is True

    os.remove(os.path.join(repo, "lib", "target.py"))
    ctx2, _run2 = _ctx(repo, tmp_path, prev=first["digest"])
    second = m.LENS.collect(ctx2)

    assert rid in [c["id"] for c in second["candidates"]]
    assert m.LENS.diff(first["digest"], second["digest"])["new"] == [rid]


def test_previously_resolved_reference_survives_losing_its_anchor(tmp_path):
    """`docs/x.md` resolved last sweep; deleting all of `docs/` makes it unanchored —
    it must still surface as drift rather than vanishing from the digest."""
    repo = init_calibrated_repo(tmp_path)
    os.makedirs(os.path.join(repo, "docs"))
    _write(repo, "docs/design.md", "d\n")
    _write(repo, "CLAUDE.md", "Read `docs/design.md`.\n")
    ctx, _run = _ctx(repo, tmp_path)
    first = m.LENS.collect(ctx)
    rid = "docs:ref:CLAUDE.md:docs/design.md"
    assert first["digest"]["references"][rid]["resolved"] is True

    os.remove(os.path.join(repo, "docs", "design.md"))
    os.rmdir(os.path.join(repo, "docs"))
    ctx2, _run2 = _ctx(repo, tmp_path, prev=first["digest"])
    second = m.LENS.collect(ctx2)

    assert rid in [c["id"] for c in second["candidates"]]
    assert m.LENS.diff(first["digest"], second["digest"])["new"] == [rid]


def test_already_broken_reference_survives_losing_its_anchor(tmp_path):
    """A reference that was already unresolved must keep its id when its top-level
    anchor disappears — not vanish silently (R5.4)."""
    repo = init_calibrated_repo(tmp_path)
    os.makedirs(os.path.join(repo, "docs"))
    _write(repo, "docs/keep.md", "k\n")
    _write(repo, "CLAUDE.md", "Read `docs/gone.md`.\n")
    ctx, _run = _ctx(repo, tmp_path)
    first = m.LENS.collect(ctx)
    rid = "docs:ref:CLAUDE.md:docs/gone.md"
    assert first["digest"]["references"][rid]["resolved"] is False
    assert rid in [c["id"] for c in first["candidates"]]

    os.remove(os.path.join(repo, "docs", "keep.md"))
    os.rmdir(os.path.join(repo, "docs"))
    ctx2, _run2 = _ctx(repo, tmp_path, prev=first["digest"])
    second = m.LENS.collect(ctx2)

    assert rid in second["digest"]["references"]
    assert rid in [c["id"] for c in second["candidates"]]
    assert rid not in m.LENS.diff(first["digest"], second["digest"])["resolved"]


def test_docstring_states_absent_vs_unreadable_carry_forward():
    """A doc NOT READ this sweep — absent OR unreadable — carries its prior references
    forward and is never `resolved`; only a re-measured reference may resolve."""
    doc = m.__doc__
    assert "absent" in doc.lower() and "unreadable" in doc.lower()
    assert "resolved" in doc.lower()
    assert "carried forward" in doc.lower()
    assert "doc is gone" in doc.lower() or "instruction docs are absent" in doc.lower()


def test_no_duplicate_candidate_ids(tmp_path):
    repo = init_calibrated_repo(
        tmp_path, verify_command="python3 lib/gone.py")
    os.makedirs(os.path.join(repo, "lib"))
    _write(repo, "lib/keep.py", "x = 1\n")
    _write(repo, "CLAUDE.md", "Read `lib/gone.py` and `lib/gone.py`.\n")
    _write(repo, "README.md", "Read `lib/gone.py`.\n")
    ctx, _run = _ctx(repo, tmp_path)

    ids = [c["id"] for c in m.LENS.collect(ctx)["candidates"]]
    assert len(ids) == len(set(ids))


def test_calibration_fixture_writes_the_verify_command(tmp_path):
    """Guard the fixture assumption the verify-subcheck tests rest on."""
    repo = init_calibrated_repo(tmp_path, verify_command="python3 x/y.py")
    rec = cm.read(repo, str(tmp_path / "store"))
    assert rec["verifyCommand"] == "python3 x/y.py"
