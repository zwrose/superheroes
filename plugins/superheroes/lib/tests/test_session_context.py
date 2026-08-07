# plugins/superheroes/lib/tests/test_session_context.py
"""Unit tests for the SessionStart context assembler (lib/session_context.py).

The assembler is best-effort: every source is gathered independently, a failed/
absent source is omitted with a one-line stderr breadcrumb (never the file
contents), and it must never raise. These tests pin the three-record injection
set (resolved roots, cache hygiene nudge, covenant), the breadcrumb-but-not-leaky
guard, and the budget-omit accounting (C2).
"""
import json
import os
import re
import time

import pytest

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


# ---------------------------------------------------------------- cache hygiene nudge (rider 3)
def test_cache_hygiene_clean_scan_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "cache_markers.scan_stale_siblings",
        lambda plugin_root, now=None, grace_seconds=3600: {"dirs": [], "markers": 0},
    )
    assert sc.cache_hygiene("/any/plugin") == ""


def test_assemble_silent_when_cache_hygiene_clean(tmp_path, monkeypatch):
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)
    monkeypatch.setattr(
        "cache_markers.scan_stale_siblings",
        lambda plugin_root, now=None, grace_seconds=3600: {"dirs": [], "markers": 0},
    )
    out = sc.assemble(str(tmp_path), None, _PLUGIN_ROOT, "claude")
    assert "Plugin cache hygiene" not in out


def test_assemble_includes_cache_hygiene_nudge_when_stale(tmp_path, monkeypatch):
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)
    monkeypatch.setattr(
        "cache_markers.scan_stale_siblings",
        lambda plugin_root, now=None, grace_seconds=3600: {
            "dirs": ["0.10.0", "0.21.1"],
            "markers": 5,
        },
    )
    out = sc.assemble(str(tmp_path), None, _PLUGIN_ROOT, "claude")
    assert "0.10.0" in out and "0.21.1" in out
    assert "5 stale marker" in out
    assert "advisor: propose a manual review/cleanup with the owner" in out


def test_assemble_nudge_before_covenant_survives_tight_budget(tmp_path, monkeypatch):
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo"})
    monkeypatch.setattr(
        "cache_markers.scan_stale_siblings",
        lambda plugin_root, now=None, grace_seconds=3600: {
            "dirs": ["0.10.0"],
            "markers": 2,
        },
    )
    main = str(tmp_path)
    _mk_repo(main)

    out_room = sc.assemble(main, None, _PLUGIN_ROOT, "claude", char_budget=5000)
    assert "Plugin cache hygiene" in out_room
    assert "advisor: propose a manual review/cleanup with the owner" in out_room
    assert "### Covenant" in out_room

    monkeypatch.setattr(sc, "covenant", lambda cwd, plugin_root: "X" * 8000)
    out_tight = sc.assemble(main, None, _PLUGIN_ROOT, "claude", char_budget=1200)
    assert "Plugin cache hygiene" in out_tight
    assert "advisor: propose a manual review/cleanup with the owner" in out_tight
    assert "truncated" in out_tight or "omitted for space" in out_tight


def test_cache_hygiene_truncates_many_dirs_within_max_chars(monkeypatch):
    many = ["0.%d.0" % i for i in range(30)]
    monkeypatch.setattr(
        "cache_markers.scan_stale_siblings",
        lambda plugin_root, now=None, grace_seconds=3600: {"dirs": many, "markers": 99},
    )
    line = sc.cache_hygiene("/p")
    assert len(line) <= sc._NUDGE_MAX_CHARS
    assert line.endswith("advisor: propose a manual review/cleanup with the owner.")
    assert "99 stale marker" in line
    assert re.search(r"\+\d+ more", line)
    assert "0.0.0" in line


def test_cache_hygiene_single_very_long_version_dir_name(tmp_path, monkeypatch):
    long_name = "0." + ("9" * 250) + ".0"
    assert len(long_name) >= 200
    plugin_root = str(tmp_path / "0.1.0")
    os.makedirs(plugin_root, exist_ok=True)
    parent = tmp_path
    sibling = parent / long_name
    sibling.mkdir()
    in_use = sibling / ".in_use"
    in_use.mkdir()
    marker = in_use / "424242"
    marker.write_text("")
    old = time.time() - 7200
    os.utime(marker, (old, old))

    def kill(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "kill", kill)
    line = sc.cache_hygiene(plugin_root)
    assert line
    assert len(line) <= sc._NUDGE_MAX_CHARS
    assert line.endswith("advisor: propose a manual review/cleanup with the owner.")
    assert "1 stale marker" in line


def _cache_hygiene_single_dir_line(name, markers=1):
    head = "Stale plugin-cache markers found in 1 other version dir(s) ("
    count_part = ": %d stale marker(s)" % markers
    return head + name + ")" + count_part + sc._NUDGE_TAIL


def test_cache_hygiene_single_dir_just_under_max_chars(monkeypatch):
    markers = 7
    head = "Stale plugin-cache markers found in 1 other version dir(s) ("
    count_part = ": %d stale marker(s)" % markers
    fixed = len(head) + len(")") + len(count_part) + len(sc._NUDGE_TAIL)
    name_len = sc._NUDGE_MAX_CHARS - fixed - 1
    name = "0." + ("a" * (name_len - 2))
    assert len(_cache_hygiene_single_dir_line(name, markers)) == sc._NUDGE_MAX_CHARS - 1
    monkeypatch.setattr(
        "cache_markers.scan_stale_siblings",
        lambda plugin_root, now=None, grace_seconds=3600: {"dirs": [name], "markers": markers},
    )
    line = sc.cache_hygiene("/p")
    assert len(line) <= sc._NUDGE_MAX_CHARS
    assert line.endswith("advisor: propose a manual review/cleanup with the owner.")
    assert "%d stale marker" % markers in line
    assert "…" not in line.split("(")[1].split(")")[0]


def test_cache_hygiene_single_dir_exactly_at_max_chars(monkeypatch):
    markers = 8
    head = "Stale plugin-cache markers found in 1 other version dir(s) ("
    count_part = ": %d stale marker(s)" % markers
    fixed = len(head) + len(")") + len(count_part) + len(sc._NUDGE_TAIL)
    name_len = sc._NUDGE_MAX_CHARS - fixed
    name = "0." + ("b" * (name_len - 2))
    assert len(_cache_hygiene_single_dir_line(name, markers)) == sc._NUDGE_MAX_CHARS
    monkeypatch.setattr(
        "cache_markers.scan_stale_siblings",
        lambda plugin_root, now=None, grace_seconds=3600: {"dirs": [name], "markers": markers},
    )
    line = sc.cache_hygiene("/p")
    assert len(line) <= sc._NUDGE_MAX_CHARS
    assert line.endswith("advisor: propose a manual review/cleanup with the owner.")
    assert "%d stale marker" % markers in line
    assert "…" not in line.split("(")[1].split(")")[0]


def test_cache_hygiene_one_long_dir_among_many_uses_more_suffix(monkeypatch):
    markers = 42
    short_dirs = ["0.%d.0" % i for i in range(25)]
    long_name = "0." + ("z" * 220) + ".0"
    dirs = short_dirs + [long_name]
    monkeypatch.setattr(
        "cache_markers.scan_stale_siblings",
        lambda plugin_root, now=None, grace_seconds=3600: {"dirs": dirs, "markers": markers},
    )
    line = sc.cache_hygiene("/p")
    assert len(line) <= sc._NUDGE_MAX_CHARS
    assert line.endswith("advisor: propose a manual review/cleanup with the owner.")
    assert "%d stale marker" % markers in line
    assert re.search(r"\+\d+ more", line)


def test_cache_hygiene_degenerate_inner_budget_still_within_max_chars(monkeypatch):
    huge_markers = 10 ** 40
    name = "0.9.0"
    monkeypatch.setattr(
        "cache_markers.scan_stale_siblings",
        lambda plugin_root, now=None, grace_seconds=3600: {
            "dirs": [name],
            "markers": huge_markers,
        },
    )
    line = sc.cache_hygiene("/p")
    assert len(line) <= sc._NUDGE_MAX_CHARS
    assert line.endswith("advisor: propose a manual review/cleanup with the owner.")
    assert "stale marker" in line


def test_cache_hygiene_passes_plugin_root_to_scan_stale_siblings(monkeypatch):
    seen = []

    def spy(plugin_root, now=None, grace_seconds=3600):
        seen.append(plugin_root)
        return {"dirs": [], "markers": 0}

    monkeypatch.setattr("cache_markers.scan_stale_siblings", spy)
    root = "/abs/plugin/root"
    assert sc.cache_hygiene(root) == ""
    assert seen == [root]


def test_cache_parent_hint_matches_cache_markers(tmp_path):
    import cache_markers as cm

    anchor = tmp_path / "home" / "plugins"
    anchor.mkdir(parents=True)
    plugin_root = str(anchor / ".." / "plugin-cache" / "0.22.0")
    os.makedirs(os.path.normpath(plugin_root), exist_ok=True)
    assert sc._cache_parent_hint(plugin_root) == cm.cache_parent(plugin_root)


def test_assemble_survives_broken_cache_parent_hint(tmp_path, monkeypatch, capsys):
    import mode_registry

    monkeypatch.setattr(
        mode_registry,
        "read_registry",
        lambda cwd, root=None: {"storageMode": "in-repo"},
    )
    main = str(tmp_path)
    _mk_repo(main, claude_md="PROJECT\n")

    def boom(plugin_root):
        raise RuntimeError("cache_parent broken")

    monkeypatch.setattr("cache_markers.cache_parent", boom)

    out = sc.assemble(main, None, _PLUGIN_ROOT, "claude")
    assert "### Resolved plugin roots" in out
    assert "Plugin root (absolute):" in out
    assert "### Covenant" in out
    assert "assemble: source gather errored" not in out
    captured = capsys.readouterr()
    assert "Plugin cache hygiene" in captured.err
    assert "RuntimeError" in captured.err


# ---------------------------------------------------------------- charter recovery (#911)
def _write_transcript(path, records):
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


def _user_charter(charter, *, is_sidechain=False):
    content = (
        "<command-message>superheroes:%s</command-message>\n"
        "<command-name>/superheroes:%s</command-name>\n"
        "<command-args>Issue: #911</command-args>"
    ) % (charter, charter)
    return {
        "type": "user",
        "isSidechain": is_sidechain,
        "userType": "external",
        "message": {"role": "user", "content": content},
    }


def _workhorse_skill_path():
    return os.path.join(_PLUGIN_ROOT, "skills", "workhorse", "SKILL.md")


def _showrunner_skill_path():
    return os.path.join(_PLUGIN_ROOT, "skills", "showrunner", "SKILL.md")


def test_compact_workhorse_transcript_injects_charter_recovery(tmp_path, monkeypatch):
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("workhorse")])
    out = sc.assemble(str(tmp_path), str(path), _PLUGIN_ROOT, "claude", source="compact")
    assert "### Charter recovery" in out
    assert _workhorse_skill_path() in out
    assert "workhorse" in out


def test_compact_showrunner_transcript_injects_charter_recovery(tmp_path, monkeypatch):
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("showrunner")])
    out = sc.assemble(str(tmp_path), str(path), _PLUGIN_ROOT, "claude", source="compact")
    assert "### Charter recovery" in out
    assert _showrunner_skill_path() in out
    assert "showrunner" in out


def test_compact_no_charter_transcript_omits_charter_recovery(tmp_path, monkeypatch):
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [
        {"type": "user", "isSidechain": False, "message": {"role": "user", "content": "hello"}},
    ])
    out_compact = sc.assemble(
        str(tmp_path), str(path), _PLUGIN_ROOT, "claude", source="compact")
    out_default = sc.assemble(str(tmp_path), str(path), _PLUGIN_ROOT, "claude")
    assert "### Charter recovery" not in out_compact
    assert out_compact == out_default


def test_compact_subagent_transcript_omits_charter_recovery(tmp_path, monkeypatch):
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [
        _user_charter("workhorse", is_sidechain=True),
        _user_charter("showrunner", is_sidechain=True),
    ])
    out = sc.assemble(str(tmp_path), str(path), _PLUGIN_ROOT, "claude", source="compact")
    assert "### Charter recovery" not in out


@pytest.mark.parametrize("source", ["startup", "resume"])
def test_non_compact_source_omits_charter_recovery(tmp_path, monkeypatch, source):
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("workhorse")])
    out = sc.assemble(str(tmp_path), str(path), _PLUGIN_ROOT, "claude", source=source)
    assert "### Charter recovery" not in out


def test_assemble_without_source_omits_charter_recovery(tmp_path, monkeypatch):
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("workhorse")])
    out = sc.assemble(str(tmp_path), str(path), _PLUGIN_ROOT, "claude")
    assert "### Charter recovery" not in out


def test_charter_recovery_never_raises_on_garbage_transcript():
    assert sc.charter_recovery(None, "compact", _PLUGIN_ROOT) == ""
    assert sc.charter_recovery("/nonexistent/transcript.jsonl", "compact", _PLUGIN_ROOT) == ""
