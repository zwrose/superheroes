# plugins/superheroes/lib/tests/test_session_context.py
"""Unit tests for the SessionStart context assembler (lib/session_context.py).

The assembler is best-effort: every source is gathered independently, a failed/
absent source is omitted with a one-line stderr breadcrumb (never the file
contents), and it must never raise. These tests pin the source-presence parity
bar (Goal 1), the breadcrumb-but-not-leaky guard (Goal 3), the store_core git
routing (findings C1 / premortem-r2), the subprocess-free root walk
(premortem-r3), the projects-base fallback (C6), and the budget-omit accounting
(C2).
"""
import os

import session_context as sc

# The real plugin root (…/plugins/superheroes) — its `rubric/covenant.md` is the file the
# covenant injection reads. Tests point plugin_root here so they exercise the real covenant
# text (single source of truth), not a fixture copy that could drift from it.
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(sc.__file__)))


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


# ---------------------------------------------------------------- project_memory
def test_project_memory_present(tmp_path):
    _mk_repo(str(tmp_path), claude_md="# Proj rules\nSENTINEL_PROJECT\n")
    out = sc.project_memory(str(tmp_path))
    assert "SENTINEL_PROJECT" in out


def test_project_memory_accumulates_multi_file_chain(tmp_path):
    # The cwd→root walk must accumulate EVERY CLAUDE.md on the chain, not just one —
    # a break-early / last-file-only regression must fail here.
    _mk_repo(str(tmp_path), claude_md="SENTINEL_ROOT\n")        # repo root (.git here)
    sub = tmp_path / "a" / "b"
    os.makedirs(str(sub))
    (sub / "CLAUDE.md").write_text("SENTINEL_SUB\n")
    out = sc.project_memory(str(sub))
    assert "SENTINEL_SUB" in out and "SENTINEL_ROOT" in out


def test_project_memory_absent_is_empty_and_breadcrumbs(tmp_path, capsys):
    _mk_repo(str(tmp_path))  # repo root, no CLAUDE.md
    out = sc.project_memory(str(tmp_path))
    assert out == ""
    assert "Project CLAUDE.md" in capsys.readouterr().err


def test_project_memory_root_walk_is_subprocess_free(tmp_path, monkeypatch):
    # premortem-r3: the CLAUDE.md chain walk must not shell out to git (no third
    # unbounded-git path). Trip wires on store_core git helpers must stay untouched.
    calls = []
    monkeypatch.setattr(sc.store_core, "run_git",
                        lambda *a, **k: calls.append(("run_git", a)) or None)
    monkeypatch.setattr(sc.store_core, "get_gitdir",
                        lambda *a, **k: calls.append(("get_gitdir", a)) or "/x")
    sub = str(tmp_path / "a" / "b")
    os.makedirs(sub)
    _mk_repo(str(tmp_path), claude_md="root\n")
    sc.project_memory(sub)
    assert calls == []


# ---------------------------------------------------------------- user_memory
def test_user_memory_present(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    os.makedirs(str(tmp_path / ".claude"))
    (tmp_path / ".claude" / "CLAUDE.md").write_text("SENTINEL_USER\n")
    assert "SENTINEL_USER" in sc.user_memory()


def test_user_memory_absent_breadcrumbs(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))  # no ~/.claude/CLAUDE.md
    assert sc.user_memory() == ""
    assert "User CLAUDE.md" in capsys.readouterr().err


# ---------------------------------------------------------------- env_block
def test_env_block_routes_git_through_run_git(tmp_path, monkeypatch):
    # premortem-r2: the `git config user.email` call must go through the
    # store_core.run_git timeout wrapper, never a bare subprocess.
    seen = {}

    def fake_run_git(cwd, *args):
        seen["args"] = args
        return "dev@example.com"

    monkeypatch.setattr(sc.store_core, "run_git", fake_run_git)
    out = sc.env_block(str(tmp_path))
    assert seen["args"] == ("config", "user.email")
    assert "dev@example.com" in out
    assert "Today's date" in out


def test_env_block_no_email_breadcrumbs_without_leaking(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sc.store_core, "run_git", lambda *a, **k: None)
    out = sc.env_block(str(tmp_path))
    assert "Today's date" in out                 # date still present
    err = capsys.readouterr().err
    assert "Environment" in err                  # breadcrumb names the source
    assert "dev@example.com" not in err          # never leak a value


# ---------------------------------------------------------------- encoder
def test_encode_project_path_replaces_slash_and_dot():
    assert sc._encode_project_path("/Users/z/superheroes") == "-Users-z-superheroes"
    assert sc._encode_project_path("/a.b/c.d") == "-a-b-c-d"


# ---------------------------------------------------------------- memory path / resolution
def test_main_repo_resolution_goes_through_store_core(tmp_path, monkeypatch):
    # finding C1: main-repo root must resolve via store_core.get_gitdir (absolute
    # common-dir, timeout-guarded), not a bare `git rev-parse`. From a worktree the
    # common-dir is the MAIN repo's .git, so the encoded dir keys to the main repo.
    monkeypatch.setattr(sc.store_core, "get_gitdir", lambda cwd: "/main/repo/.git")
    transcript = "/Users/z/.claude/projects/-enc-worktree/abc.jsonl"
    path = sc._memory_md_path("/any/worktree", transcript)
    # base from transcript's /projects/ + encoded MAIN repo root (/main/repo)
    assert path == "/Users/z/.claude/projects/-main-repo/memory/MEMORY.md"


def test_main_repo_root_non_git_returns_gitdir_verbatim(monkeypatch):
    # store_core.get_gitdir falls back to realpath(cwd) for a non-git dir (basename
    # != ".git"); _main_repo_root must return that value as-is, not its parent.
    monkeypatch.setattr(sc.store_core, "get_gitdir", lambda cwd: "/main/repo")
    assert sc._main_repo_root("/anything") == "/main/repo"


def test_main_repo_root_falls_back_when_gitdir_raises(monkeypatch):
    # A raising get_gitdir is swallowed; the fallback is $CLAUDE_PROJECT_DIR, then cwd.
    def boom(cwd):
        raise RuntimeError("git exploded")
    monkeypatch.setattr(sc.store_core, "get_gitdir", boom)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/proj/dir")
    assert sc._main_repo_root("/x") == "/proj/dir"
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    assert sc._main_repo_root("/x/y") == os.path.abspath("/x/y")


def test_projects_base_from_transcript_marker(tmp_path):
    base = sc._projects_base("/Users/z/.claude/projects/-enc/sess.jsonl")
    assert base == "/Users/z/.claude/projects"


def test_projects_base_fallback_when_marker_absent(tmp_path, monkeypatch):
    # finding C6: fall back when transcript_path is None OR lacks a /projects/ segment.
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", "/home/u")
    assert sc._projects_base(None) == "/home/u/.claude/projects"
    assert sc._projects_base("/tmp/no-marker/sess.jsonl") == "/home/u/.claude/projects"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/cfg")
    assert sc._projects_base(None) == "/cfg/projects"


def test_auto_memory_head_reads_first_200_lines(tmp_path, monkeypatch):
    main = str(tmp_path / "main")
    os.makedirs(main)
    monkeypatch.setattr(sc.store_core, "get_gitdir", lambda cwd: os.path.join(main, ".git"))
    enc = sc._encode_project_path(os.path.abspath(main))
    mem_dir = tmp_path / "projects" / enc / "memory"
    os.makedirs(str(mem_dir))
    body = "".join("line %d\n" % i for i in range(500))
    (mem_dir / "MEMORY.md").write_text(body)
    transcript = str(tmp_path / "projects" / "-enc-worktree" / "s.jsonl")
    out = sc.auto_memory_head(main, transcript)
    assert "line 0" in out and "line 199" in out
    assert "line 200" not in out                 # capped at 200 lines


def test_auto_memory_head_absent_breadcrumbs(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sc.store_core, "get_gitdir", lambda cwd: str(tmp_path / ".git"))
    out = sc.auto_memory_head(str(tmp_path), None)
    assert out == ""
    assert "MEMORY.md" in capsys.readouterr().err


# ---------------------------------------------------------------- assemble
def test_assemble_never_raises_on_garbage():
    # No exception for missing/None inputs; always returns a string.
    out = sc.assemble(None, None, "/nonexistent/plugin", "claude")
    assert isinstance(out, str)


def test_assemble_parity_presence_all_sources(tmp_path, monkeypatch):
    # Goal-1 acceptance bar: with every source present, the block names each one.
    home = tmp_path / "home"
    os.makedirs(str(home / ".claude"))
    (home / ".claude" / "CLAUDE.md").write_text("USER_CLAUDE_SENTINEL\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(sc.store_core, "run_git", lambda *a, **k: "dev@example.com")

    main = str(tmp_path / "repo")
    _mk_repo(main, claude_md="PROJECT_CLAUDE_SENTINEL\n")
    monkeypatch.setattr(sc.store_core, "get_gitdir", lambda cwd: os.path.join(main, ".git"))
    enc = sc._encode_project_path(os.path.abspath(main))
    mem_dir = tmp_path / "projects" / enc / "memory"
    os.makedirs(str(mem_dir))
    (mem_dir / "MEMORY.md").write_text("MEMORY_SENTINEL\n")
    transcript = str(tmp_path / "projects" / "-enc" / "s.jsonl")

    out = sc.assemble(main, transcript, str(tmp_path / "plugins" / "superheroes"), "claude")
    for marker in ("Resolved plugin roots", "Project CLAUDE.md", "Environment",
                   "User CLAUDE.md", "Auto-memory"):
        assert marker in out, marker
    assert "PROJECT_CLAUDE_SENTINEL" in out
    assert "USER_CLAUDE_SENTINEL" in out
    assert "MEMORY_SENTINEL" in out


def test_assemble_omits_missing_source_without_error(tmp_path, monkeypatch):
    # A missing source (no user CLAUDE.md, no MEMORY.md) is simply absent — a
    # silently-dropped source would fail this by being neither present nor named.
    monkeypatch.setenv("HOME", str(tmp_path / "empty-home"))
    monkeypatch.setattr(sc.store_core, "run_git", lambda *a, **k: None)
    monkeypatch.setattr(sc.store_core, "get_gitdir", lambda cwd: str(tmp_path / ".git"))
    main = str(tmp_path)
    _mk_repo(main, claude_md="PROJECT_ONLY\n")
    out = sc.assemble(main, None, str(tmp_path / "plug"), "claude")
    assert "PROJECT_ONLY" in out
    assert "User CLAUDE.md" not in out           # absent file → section omitted
    assert "USER_CLAUDE_SENTINEL" not in out


def test_assemble_budget_truncates_and_accounts_omitted(tmp_path, monkeypatch, capsys):
    # finding C2: an oversized source is truncated with a marker; a present source
    # dropped entirely by the budget stop is named in an in-block omitted-line AND
    # breadcrumbed — never silently indistinguishable from an absent file.
    monkeypatch.setattr(sc.store_core, "run_git", lambda *a, **k: None)   # env=date only, still present
    monkeypatch.setattr(sc.store_core, "get_gitdir", lambda cwd: str(tmp_path / ".git"))
    monkeypatch.setenv("HOME", str(tmp_path / "no-home"))
    main = str(tmp_path)
    _mk_repo(main, claude_md="X" * 6000)         # large project CLAUDE.md
    # short plugin_root keeps the resolved-roots section small, leaving room to
    # truncate (not merely omit) the oversized project CLAUDE.md under the budget.
    out = sc.assemble(main, None, "/p", "claude", char_budget=1000)
    assert "truncated" in out                    # the oversized source carries a marker
    assert "omitted for space" in out            # the in-block accounting line
    assert "Environment" in out                  # the dropped present source is named
    assert "Environment" in capsys.readouterr().err   # ...and breadcrumbed
    # body stays within budget; the small omitted-line accounting note may follow it
    assert len(out) <= 1000 + 250


def test_assemble_covenant_survives_oversized_project_claude_md(tmp_path, monkeypatch):
    # The covenant is the second record (after constant-size resolved roots); every
    # variable-size source comes after, so an oversized project CLAUDE.md cannot
    # silently omit the ~50-line covenant.
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo"})
    monkeypatch.setattr(sc.store_core, "run_git", lambda *a, **k: None)
    monkeypatch.setattr(sc.store_core, "get_gitdir", lambda cwd: str(tmp_path / ".git"))
    monkeypatch.setenv("HOME", str(tmp_path / "no-home"))
    main = str(tmp_path)
    _mk_repo(main, claude_md="X" * 20000)
    out = sc.assemble(main, None, _PLUGIN_ROOT, "claude", char_budget=9000)
    assert "### Covenant" in out


def test_assemble_covenant_survives_oversized_memory_head(tmp_path, monkeypatch):
    # The covenant is the second record (constant-size); a large memory head comes
    # after all variable-size sources and cannot silently omit it.
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo"})
    monkeypatch.setattr(sc.store_core, "run_git", lambda *a, **k: None)
    monkeypatch.setattr(sc.store_core, "get_gitdir", lambda cwd: str(tmp_path / ".git"))
    monkeypatch.setattr(sc, "_read_memory_head", lambda path: "M" * 20000)
    monkeypatch.setenv("HOME", str(tmp_path / "no-home"))
    main = str(tmp_path)
    _mk_repo(main, claude_md="PROJECT\n")
    out = sc.assemble(main, None, _PLUGIN_ROOT, "claude", char_budget=9000)
    assert "### Covenant" in out
    assert "truncated" in out or "omitted for space" in out


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
    monkeypatch.setattr(sc.store_core, "run_git", lambda *a, **k: None)
    monkeypatch.setattr(sc.store_core, "get_gitdir", lambda cwd: str(tmp_path / ".git"))
    monkeypatch.setenv("HOME", str(tmp_path / "no-home"))
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
    monkeypatch.setattr(sc.store_core, "run_git", lambda *a, **k: None)
    monkeypatch.setattr(sc.store_core, "get_gitdir", lambda cwd: str(tmp_path / ".git"))
    monkeypatch.setenv("HOME", str(tmp_path / "no-home"))
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
    monkeypatch.setattr(sc.store_core, "run_git", lambda *a, **k: None)
    monkeypatch.setattr(sc.store_core, "get_gitdir", lambda cwd: str(tmp_path / ".git"))
    monkeypatch.setenv("HOME", str(tmp_path / "no-home"))
    main = str(tmp_path)
    _mk_repo(main, claude_md="PROJECT\n")
    out = sc.assemble(main, None, _PLUGIN_ROOT, "claude")
    assert "### Covenant" in out
    assert "Never merge" in out and "superheroes:workhorse" in out
    assert "/superheroes:review-code" not in out        # covenant replaced the old note
