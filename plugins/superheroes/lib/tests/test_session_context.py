# plugins/superheroes/lib/tests/test_session_context.py
"""Unit tests for the SessionStart context assembler (lib/session_context.py).

The assembler is best-effort: every source is gathered independently, a failed/
absent source is omitted with a one-line stderr breadcrumb (never the file
contents), and it must never raise. These tests pin the slim two-record injection
set (resolved roots + covenant), the breadcrumb-but-not-leaky guard, and the
budget-omit accounting (C2).
"""
import os

import session_context as sc

# The real plugin root (…/plugins/superheroes) — its `rubric/covenant.md` is the file the
# covenant injection reads. Tests point plugin_root here so they exercise the real covenant
# text (single source of truth), not a fixture copy that could drift from it.
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(sc.__file__)))

# The covenant header decides WHICH document wins when the covenant and PHILOSOPHY.md disagree.
# Pinned by exact match (whitespace-normalized) rather than substring: a substring guard is
# defeatable by appending a contradicting sentence after it (#706 review round 5).
_EXPECTED_COVENANT_HEADER = (
    "The short, imperative form of PHILOSOPHY.md — the operating discipline every superheroes "
    "session carries. PHILOSOPHY.md (in-repo) remains the constitution and the authority; if the "
    "two ever disagree, one of them has drifted — say so and park the difference with the owner; "
    "until the owner rules, PHILOSOPHY.md governs."
)


# ---------------------------------------------------------------- helpers
def _mk_repo(d, claude_md=None):
    """A directory that looks like a git repo root (a `.git` dir stops the walk)."""
    os.makedirs(os.path.join(d, ".git"), exist_ok=True)
    if claude_md is not None:
        with open(os.path.join(d, "CLAUDE.md"), "w") as fh:
            fh.write(claude_md)
    return d


# ---------------------------------------------------------------- resolved_roots
def test_resolved_roots_states_absolute_host_map_path(tmp_path):
    root = str(tmp_path / "plugins" / "superheroes")
    note = sc.resolved_roots(root, "claude")
    assert os.path.join(os.path.abspath(root), "hosts", "claude-tools.md") in note
    assert os.path.abspath(root) in note
    # no shell-export instruction — context injection only
    assert "export" not in note.lower()


# ---------------------------------------------------------------- assemble
def test_assemble_never_raises_on_garbage():
    # No exception for missing/None inputs; always returns a string.
    out = sc.assemble(None, None, "/nonexistent/plugin", "claude")
    assert isinstance(out, str)


def test_assemble_injects_slim_set(tmp_path, monkeypatch):
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo"})
    main = str(tmp_path)
    out = sc.assemble(main, None, _PLUGIN_ROOT, "claude")
    assert "Resolved plugin roots" in out
    assert "Covenant" in out
    assert "Never merge" in out
    for marker in ("Project CLAUDE.md", "Environment", "User CLAUDE.md", "Auto-memory"):
        assert marker not in out, marker


def test_assemble_budget_truncates_and_accounts_omitted(tmp_path, monkeypatch, capsys):
    # finding C2: an oversized source is truncated with a marker; a present source
    # dropped entirely by the budget stop is named in an in-block omitted-line AND
    # breadcrumbed — never silently indistinguishable from an absent file.
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo"})
    monkeypatch.setattr(sc, "covenant", lambda cwd, plugin_root: "C" * 6000)
    out = sc.assemble(str(tmp_path), None, "/p", "claude", char_budget=1000)
    assert "truncated" in out
    assert len(out) <= 1000 + 250


# ---------------------------------------------------------------- covenant (#470)
def test_covenant_injected_for_calibrated_project(tmp_path, monkeypatch):
    # A registry entry marks the project calibrated → the covenant (rubric/covenant.md,
    # read from the plugin install) is injected verbatim.
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo"})
    note = sc.covenant(str(tmp_path), _PLUGIN_ROOT)
    assert "The superheroes covenant" in note
    assert "Never merge" in note                       # a hard line
    assert "Review before handback" in note            # subsumes the review-discipline note
    assert "superheroes:showrunner" in note and "superheroes:workhorse" in note  # charter pointer
    # The covenant subsumed the old note: it no longer carries the review-code command string.
    assert "/superheroes:review-code" not in note


def test_covenant_pins_the_approval_execution_distinction(tmp_path, monkeypatch):
    # #706: the covenant ships into every calibrated session, so WHICH act never delegates
    # is load-bearing runtime guidance. The generic "Never merge" marker above survives
    # edits that would gut the distinction, so pin the distinction itself — and pin the
    # ABSENCE of the 2026-07-26 divergence note, whose stated condition ("until the owner
    # amends it") the owner's PHILOSOPHY amendment satisfied.
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo"})
    note = sc.covenant(str(tmp_path), _PLUGIN_ROOT)
    assert "The never-delegable act is **approval**" in note
    assert "mechanical per-merge approval checkpoint" in note
    # the EPISTEMIC half of the fail-closed default: "where none exists" alone would keep the
    # trailing clause passing, so pin the can't-establish-it branch by name (#706 review round 3).
    assert "you cannot establish that it fires on this host and path" in note
    assert "execution stays in the owner's hands" in note
    # The drift clause this change rewrote decides which document wins when the two disagree, so
    # it is pinned by EXACT MATCH on the whole header, not by substring. A substring pin is
    # defeatable by APPENDING: "…PHILOSOPHY.md governs. When the covenant is stricter, follow it
    # instead." keeps every substring assertion green while reversing the precedence (#706 review
    # rounds 4-5 each found one more way past a substring guard; equality ends that class).
    # Whitespace is normalized first so a pure re-wrap of the source is not a false failure.
    flat = " ".join(note.split())
    header = flat[flat.index("The short, imperative form"):flat.index("## The six promises")].strip()
    assert header == _EXPECTED_COVENANT_HEADER
    assert "known, disclosed divergence" not in note


def test_covenant_via_hero_evidence_when_registry_absent(tmp_path, monkeypatch):
    # No registry record, but hero calibration evidence exists → still calibrated.
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)
    monkeypatch.setattr(mode_registry, "hero_evidence",
                        lambda cwd, root=None, hero_roots=None: {"review-crew": "global"})
    note = sc.covenant(str(tmp_path), _PLUGIN_ROOT)
    assert "The superheroes covenant" in note


def test_covenant_absent_for_uncalibrated_project(tmp_path, monkeypatch):
    # No registry, no hero evidence → no covenant (it never leaks into non-superheroes
    # projects).
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)
    monkeypatch.setattr(mode_registry, "hero_evidence",
                        lambda cwd, root=None, hero_roots=None: {"review-crew": "none"})
    assert sc.covenant(str(tmp_path), _PLUGIN_ROOT) == ""


def test_covenant_probe_is_read_only(tmp_path, monkeypatch):
    # The calibration probe must never invoke write-capable registry paths.
    import mode_registry

    def _write_tripwire(*a, **k):
        raise AssertionError("write-capable registry path must not be called")

    monkeypatch.setattr(mode_registry, "resolve", _write_tripwire)
    monkeypatch.setattr(mode_registry, "write_registry", _write_tripwire)
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo"})
    note = sc.covenant(str(tmp_path), _PLUGIN_ROOT)
    assert note


def test_covenant_probe_is_read_only_via_hero_evidence(tmp_path, monkeypatch):
    # Same write-tripwire guard, but through the absent-registry branch
    # (read_registry → None, then hero_evidence / evidence_verdict).
    import mode_registry

    def _write_tripwire(*a, **k):
        raise AssertionError("write-capable resolver invoked from the read-only probe")

    monkeypatch.setattr(mode_registry, "resolve", _write_tripwire)
    monkeypatch.setattr(mode_registry, "write_registry", _write_tripwire)
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)
    monkeypatch.setattr(mode_registry, "hero_evidence",
                        lambda cwd, root=None, hero_roots=None: {"review-crew": "in-repo"})
    note = sc.covenant(str(tmp_path), _PLUGIN_ROOT)
    assert note


def test_covenant_probe_error_skips_with_breadcrumb(tmp_path, monkeypatch, capsys):
    # The probe is best-effort: an erroring registry read skips the covenant (absence is
    # the status quo) and breadcrumbs to stderr without leaking content.
    import mode_registry
    def _boom(cwd, root=None):
        raise OSError("store unreadable")
    monkeypatch.setattr(mode_registry, "read_registry", _boom)
    assert sc.covenant(str(tmp_path), _PLUGIN_ROOT) == ""
    err = capsys.readouterr().err
    assert "Covenant" in err and "OSError" in err


def test_covenant_unreadable_on_calibrated_project_is_noted_in_block(tmp_path, monkeypatch):
    # F5: the covenant is a real file read, so on a CALIBRATED project an unreadable
    # covenant.md (broken install) is a genuine failure — _note_failure'd so it lands in
    # the in-block diagnostics the owner's agent can read back, not a silent absence.
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo"})
    main = str(tmp_path)
    _mk_repo(main, claude_md="PROJECT\n")
    noplugin = str(tmp_path / "noplugin")               # no rubric/covenant.md here
    out = sc.assemble(main, None, noplugin, "claude")
    assert "### Covenant" not in out                    # empty covenant → section omitted
    assert "### Bootstrap diagnostics" in out           # ...but the failure is surfaced
    assert "Covenant" in out and "read error" in out    # named in-block, no file contents


def test_covenant_injection_writes_nothing_to_repo(tmp_path, monkeypatch):
    # Zero repo traces: the covenant is read from the plugin install, never the project;
    # a full assemble on a calibrated project leaves the repo's file set unchanged.
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo"})
    main = str(tmp_path)
    _mk_repo(main, claude_md="PROJECT\n")

    def _snapshot(root):
        # path -> content, so an in-place overwrite is caught too (not just create/delete).
        snap = {}
        for dp, _, fs in os.walk(root):
            for f in fs:
                p = os.path.join(dp, f)
                with open(p, "rb") as fh:
                    snap[p] = fh.read()
        return snap

    before = _snapshot(main)
    out = sc.assemble(main, None, _PLUGIN_ROOT, "claude")
    after = _snapshot(main)
    assert before == after                              # nothing written/overwritten in the project
    assert "### Covenant" in out                        # ...and the covenant did inject


def test_assemble_includes_covenant_section_when_calibrated(tmp_path, monkeypatch):
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "global"})
    main = str(tmp_path)
    _mk_repo(main, claude_md="PROJECT\n")
    out = sc.assemble(main, None, _PLUGIN_ROOT, "claude")
    assert "### Covenant" in out
    assert "Never merge" in out and "superheroes:workhorse" in out
    assert "/superheroes:review-code" not in out        # covenant replaced the old note
