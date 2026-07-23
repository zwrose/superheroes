"""Guardian collector tool resolution, invocation seam, and the no-install red line.

The tool-literal depcruise-webpackConfig and import-linter-contractTypes RCE
regressions (with real depcruise / import-linter binaries) remain on the #538
branch and re-run there at rebase. This module reproduces that escape *class*
behaviorally through the generic seam but does not carry depcruise/import-linter argv.
"""
import ast
import json
import os
import shutil
import tempfile
import signal
import stat
import subprocess
import sys
import threading
import time

import pytest

_LIB = os.path.join(os.path.dirname(__file__), "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import guardian_tools as gt
from guardian_fixtures import init_calibrated_repo


_SRC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "guardian_tools.py")


def _make_repo(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".git").mkdir()
    return str(tmp_path)


def _make_node_modules_bin(tmp_path, tool):
    binp = tmp_path / "node_modules" / ".bin" / tool
    binp.parent.mkdir(parents=True, exist_ok=True)
    binp.write_text("#!/bin/sh\necho 0.0.0\n")
    binp.chmod(binp.stat().st_mode | stat.S_IXUSR)
    return str(binp)


def _make_external_tool(parent, tool, leaf="external"):
    """Executable outside any scanned repo — positive-control / version fixture."""
    bindir = parent / leaf / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    binp = bindir / tool
    binp.write_text("#!/bin/sh\necho 0.0.0\n")
    binp.chmod(binp.stat().st_mode | stat.S_IXUSR)
    return str(binp)


def _fs_is_case_sensitive(dirpath):
    """True when dirpath's filesystem distinguishes CaseSenseProbe from casesenseprobe."""
    probe = os.path.join(str(dirpath), "CaseSenseProbe")
    with open(probe, "w", encoding="utf-8") as fh:
        fh.write("x")
    try:
        return not os.path.exists(os.path.join(str(dirpath), "casesenseprobe"))
    finally:
        os.remove(probe)


class _FakeRun:
    """Records argv and replays a canned completed-process."""

    def __init__(self, stdout="", stderr="", returncode=0, raises=None):
        self.calls = []
        self._stdout = stdout
        self._stderr = stderr
        self._returncode = returncode
        self._raises = raises

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if self._raises is not None:
            raise self._raises
        outer = self

        class R:
            returncode = outer._returncode
            stdout = outer._stdout
            stderr = outer._stderr
        return R()


# --- install guidance is the one authoritative home -------------------------------

def test_install_commands_cover_the_collector_tools():
    assert gt.INSTALL_COMMANDS == {
        "jscpd": "npm install -g jscpd",
        "radon": "pip install radon",
        "lizard": "pip install lizard",
        "npm": "install Node.js, which bundles npm",
        "npm-check-updates": "npm install -g npm-check-updates",
        "knip": "npm install -g knip",
        "vulture": "pip install vulture",
        "pip-audit": "pip install pip-audit",
        "depcruise": "npm install -g dependency-cruiser typescript@5",
        "osv-scanner": (
            "brew install osv-scanner "
            "(or: go install github.com/google/osv-scanner/v2/cmd/osv-scanner@latest)"
        ),
    }


def test_version_args_cover_every_install_command_tool():
    """Every resolvable collector has a version-probe argv tail (keyed by argv[0])."""
    assert set(gt.VERSION_ARGS) == set(gt.INSTALL_COMMANDS)
    assert gt.VERSION_ARGS == {
        "jscpd": ("--version",),
        "radon": ("--version",),
        "lizard": ("--version",),
        "npm": ("--version",),
        "npm-check-updates": ("--version",),
        "knip": ("--version",),
        "vulture": ("--version",),
        "pip-audit": ("--version",),
        "depcruise": ("--version",),
        "osv-scanner": ("--version",),
    }


@pytest.mark.parametrize("tool", sorted(gt.INSTALL_COMMANDS))
def test_missing_tool_reason_names_the_exact_install_command(tool):
    reason = gt.missing_tool_reason(tool)
    assert tool in reason
    assert gt.INSTALL_COMMANDS[tool] in reason
    assert "not found on PATH" in reason


def test_missing_tool_reason_unknown_tool_does_not_invent_a_command():
    reason = gt.missing_tool_reason("not-a-tool")
    assert "not-a-tool" in reason
    assert "INSTALL_COMMANDS" in reason
    for cmd in gt.INSTALL_COMMANDS.values():
        assert cmd not in reason


# --- resolution -------------------------------------------------------------------

def test_resolve_finds_tool_on_path(tmp_path, monkeypatch):
    """Genuinely external executable (outside the repo) is still accepted."""
    repo = _make_repo(tmp_path / "repo")
    ext = _make_external_tool(tmp_path, "jscpd")
    monkeypatch.setenv("PATH", os.path.dirname(ext))
    out = gt.resolve("jscpd", repo)
    assert out == {
        "tool": "jscpd",
        "found": True,
        "path": os.path.realpath(ext),
        "source": "path",
    }


def test_resolve_ignores_repo_local_node_modules_bin(tmp_path, monkeypatch):
    """Repo-local node_modules/.bin on PATH must NOT resolve or be executed.

    Exercises the real condition: fake binary on PATH inside the scanned repo —
    do not mock which() away.
    """
    repo = _make_repo(tmp_path)
    binp = _make_node_modules_bin(tmp_path, "jscpd")
    bin_dir = str(tmp_path / "node_modules" / ".bin")
    # Only the repo-local bin dir on PATH — which() will find it; resolve must reject.
    monkeypatch.setenv("PATH", bin_dir)
    out = gt.resolve("jscpd", repo)
    assert out["found"] is False
    assert out["path"] is None
    assert out["source"] is None
    assert out.get("rejection") == gt.REJECTION_REPO_LOCAL
    reason = gt.missing_tool_reason("jscpd", rejection=out.get("rejection"))
    assert "repo-local executable ignored" in reason
    assert gt.INSTALL_COMMANDS["jscpd"] in reason
    # version() must not spawn the repo-local binary either
    run = _FakeRun(stdout="9.9.9\n")
    assert gt.version("jscpd", repo, run=run) is None
    assert run.calls == []
    assert os.path.isfile(binp)


def test_resolve_ignores_dot_path_entry(tmp_path, monkeypatch):
    """A '.' or empty PATH entry that resolves into the scanned repo is rejected."""
    repo = _make_repo(tmp_path)
    # Place the fake tool at repo root so PATH='.' finds it via cwd.
    tool_path = tmp_path / "jscpd"
    tool_path.write_text("#!/bin/sh\necho 0.0.0\n")
    tool_path.chmod(tool_path.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", ".")
    old = os.getcwd()
    try:
        os.chdir(str(tmp_path))
        out = gt.resolve("jscpd", repo)
    finally:
        os.chdir(old)
    assert out["found"] is False
    assert out.get("rejection") == gt.REJECTION_REPO_LOCAL

    # Empty PATH entry ≡ cwd on Unix
    monkeypatch.setenv("PATH", os.pathsep)  # leading empty entry
    old = os.getcwd()
    try:
        os.chdir(str(tmp_path))
        out2 = gt.resolve("jscpd", repo)
    finally:
        os.chdir(old)
    assert out2["found"] is False
    assert out2.get("rejection") == gt.REJECTION_REPO_LOCAL


def test_resolve_rejects_relative_path_entry_resolving_outside_repo(
        tmp_path, monkeypatch):
    """Relative PATH entries are cwd-unstable and must be refused even when they
    resolve outside the scanned repo.

    Deleting ``_resolved_via_relative_path_entry`` makes this test fail — the
    F5 fixture (``test_resolve_rejects_relative_path_when_process_cwd_differs``)
    cannot cover this because its relative entry resolves inside the repo and
    ``_is_under`` rejects first.
    """
    repo = tmp_path / "scanned"
    repo.mkdir()
    (repo / ".git").mkdir()
    proc = tmp_path / "proc"
    proc.mkdir()

    ext_bin = proc / "external" / "bin"
    ext_bin.mkdir(parents=True)
    proc_tool = proc / "jscpd"
    proc_tool.write_text("#!/bin/sh\necho external-ok\n")
    proc_tool.chmod(proc_tool.stat().st_mode | stat.S_IXUSR)

    monkeypatch.setenv("PATH", ".")
    old = os.getcwd()
    try:
        os.chdir(str(proc))
        assert not gt._is_under(str(proc_tool), str(repo))
        hit = shutil.which("jscpd")
        assert hit is not None
        assert os.path.samefile(hit, proc_tool)
        out = gt.resolve("jscpd", str(repo))
    finally:
        os.chdir(old)
    assert out["found"] is False
    assert out["path"] is None
    assert out.get("rejection") == gt.REJECTION_REPO_LOCAL


def test_resolve_rejects_relative_path_when_process_cwd_differs(tmp_path, monkeypatch):
    """Relative PATH hits must be judged against process cwd, not scanned-repo cwd.

    PR #553 round-4 fix: place distinct real executable identities at the two
    expansions. From process cwd the relative entry resolves repo-local (reject);
    from swept-repo cwd the same entry would resolve external (a wrong-cwd impl
    would accept). The correct impl must reject.
    """
    repo = tmp_path / "scanned"
    repo.mkdir()
    (repo / ".git").mkdir()
    proc = tmp_path / "proc"
    proc.mkdir()

    repo_bin = repo / "bin"
    repo_bin.mkdir()
    repo_tool = repo_bin / "jscpd"
    repo_tool.write_text("#!/bin/sh\necho repo-evil\n")
    repo_tool.chmod(repo_tool.stat().st_mode | stat.S_IXUSR)

    ext_bin = proc / "external" / "bin"
    ext_bin.mkdir(parents=True)
    ext_tool = ext_bin / "jscpd"
    ext_tool.write_text("#!/bin/sh\necho external-ok\n")
    ext_tool.chmod(ext_tool.stat().st_mode | stat.S_IXUSR)

    rel_name = "rel"
    os.symlink(os.path.join("..", "scanned", "bin"), proc / rel_name)
    os.symlink(os.path.join("..", "proc", "external", "bin"), repo / rel_name)

    monkeypatch.setenv("PATH", rel_name)
    old = os.getcwd()
    try:
        os.chdir(str(proc))
        assert os.path.samefile(
            os.path.join(str(proc), rel_name, "jscpd"), repo_tool)
        out = gt.resolve("jscpd", str(repo))
    finally:
        os.chdir(old)
    assert out["found"] is False
    assert out["path"] is None
    assert out.get("rejection") == gt.REJECTION_REPO_LOCAL

    try:
        os.chdir(str(repo))
        wrong_cwd_hit = shutil.which("jscpd")
        assert wrong_cwd_hit is not None
        assert os.path.samefile(wrong_cwd_hit, ext_tool)
    finally:
        os.chdir(old)

    monkeypatch.setenv("PATH", rel_name)
    try:
        os.chdir(str(proc))
        run = _FakeRun(stdout="9.9.9\n")
        assert gt.version("jscpd", str(repo), run=run) is None
        assert run.calls == []
    finally:
        os.chdir(old)


def test_resolve_ignores_nested_repo_local_bin(tmp_path, monkeypatch):
    """Scanning a nested cwd still rejects the repo-root node_modules/.bin."""
    _make_repo(tmp_path)
    _make_node_modules_bin(tmp_path, "jscpd")
    nested = tmp_path / "pkg" / "src"
    nested.mkdir(parents=True)
    bin_dir = str(tmp_path / "node_modules" / ".bin")
    monkeypatch.setenv("PATH", bin_dir)
    out = gt.resolve("jscpd", str(nested))
    assert out["found"] is False
    assert out["path"] is None
    assert out["source"] is None
    assert out.get("rejection") == gt.REJECTION_REPO_LOCAL


def test_resolve_rejects_case_variant_absolute_path_entry(tmp_path, monkeypatch):
    """Case-variant absolute PATH spelling of a repo-local dir must be rejected.

    On case-insensitive filesystems, lexical realpath containment misses when PATH
    spells the same directory with different casing. Skip on case-sensitive FS.
    """
    if _fs_is_case_sensitive(tmp_path):
        pytest.skip("filesystem is case-sensitive")

    repo = tmp_path / "CaseRepo"
    repo.mkdir()
    (repo / ".git").mkdir()
    scripts = repo / "Scripts"
    scripts.mkdir()
    tool = scripts / "jscpd"
    tool.write_text("#!/bin/sh\necho evil\n")
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)

    # Case-variant spelling of the SAME directory — lexical containment misses this.
    variant = str(tmp_path / "caserepo" / "scripts")
    monkeypatch.setenv("PATH", variant)

    out = gt.resolve("jscpd", str(repo))
    assert out["found"] is False
    assert out["path"] is None
    assert out["source"] is None
    assert out.get("rejection") == gt.REJECTION_REPO_LOCAL

    run = _FakeRun(stdout="9.9.9\n")
    assert gt.version("jscpd", str(repo), run=run) is None
    assert run.calls == []


def test_resolve_rejects_symlink_into_repo(tmp_path, monkeypatch):
    """A PATH hit that is a symlink whose target lives inside the repo is rejected."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    scripts = repo / "scripts"
    scripts.mkdir()
    tool = scripts / "jscpd"
    tool.write_text("#!/bin/sh\necho evil\n")
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)

    outside = tmp_path / "outside"
    outside.mkdir()
    link = outside / "jscpd"
    link.symlink_to(tool)

    monkeypatch.setenv("PATH", str(outside))
    out = gt.resolve("jscpd", str(repo))
    assert out["found"] is False
    assert out["path"] is None
    assert out["source"] is None
    assert out.get("rejection") == gt.REJECTION_REPO_LOCAL

    run = _FakeRun(stdout="9.9.9\n")
    assert gt.version("jscpd", str(repo), run=run) is None
    assert run.calls == []


def _make_depcruise_fake_install(tmp_path, *, typescript_version=None, manifest_body=None):
    """Fake global depcruise install: <tmp>/lib/node_modules/dependency-cruiser/bin/depcruise."""
    bin_dir = tmp_path / "lib" / "node_modules" / "dependency-cruiser" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    depcruise_bin = bin_dir / "depcruise"
    depcruise_bin.write_text("#!/bin/sh\necho 0.0.0\n")
    depcruise_bin.chmod(depcruise_bin.stat().st_mode | stat.S_IXUSR)
    (bin_dir / "dependency-cruise.mjs").write_text("// stub\n")
    nm = tmp_path / "lib" / "node_modules"
    if typescript_version is not None or manifest_body is not None:
        ts_pkg = nm / "typescript"
        ts_pkg.mkdir(parents=True, exist_ok=True)
        body = manifest_body if manifest_body is not None else json.dumps(
            {"version": typescript_version})
        (ts_pkg / "package.json").write_text(body)
    return str(bin_dir), str(nm)


# --- typescript_toolchain_node_path -----------------------------------------------

def test_typescript_toolchain_node_path_returns_dir_with_supported_typescript(
        tmp_path, monkeypatch):
    install_root = tmp_path / "install"
    repo = _make_repo(tmp_path / "repo")
    bin_dir, expected_nm = _make_depcruise_fake_install(
        install_root, typescript_version="5.9.3")
    monkeypatch.setenv("PATH", bin_dir)
    out = gt.typescript_toolchain_node_path(repo, supported_majors=("5",))
    assert out == expected_nm


def test_typescript_toolchain_node_path_none_when_typescript_absent(
        tmp_path, monkeypatch):
    install_root = tmp_path / "install"
    repo = _make_repo(tmp_path / "repo")
    bin_dir, _ = _make_depcruise_fake_install(install_root)
    monkeypatch.setenv("PATH", bin_dir)
    assert gt.typescript_toolchain_node_path(repo, supported_majors=("5",)) is None


def test_typescript_toolchain_node_path_none_when_unsupported_major(
        tmp_path, monkeypatch):
    install_root = tmp_path / "install"
    repo = _make_repo(tmp_path / "repo")
    bin_dir, _ = _make_depcruise_fake_install(
        install_root, typescript_version="6.0.3")
    monkeypatch.setenv("PATH", bin_dir)
    assert gt.typescript_toolchain_node_path(repo, supported_majors=("5",)) is None


def test_typescript_toolchain_node_path_none_when_depcruise_unresolved(
        tmp_path, monkeypatch):
    repo = _make_repo(tmp_path / "repo")
    monkeypatch.setenv("PATH", "")
    assert gt.typescript_toolchain_node_path(repo, supported_majors=("5",)) is None


def test_typescript_toolchain_node_path_rejects_typescript_symlinked_into_repo(
        tmp_path, monkeypatch):
    install_root = tmp_path / "install"
    repo = _make_repo(tmp_path / "repo")
    bin_dir, nm = _make_depcruise_fake_install(install_root)
    repo_ts = tmp_path / "repo" / "typescript"
    repo_ts.mkdir(parents=True)
    (repo_ts / "package.json").write_text(json.dumps({"version": "5.9.3"}))
    ts_link = os.path.join(nm, "typescript")
    try:
        os.symlink(str(repo_ts), ts_link)
    except OSError as exc:
        pytest.skip("platform cannot create symlinks: %s" % exc)
    monkeypatch.setenv("PATH", bin_dir)
    assert gt.typescript_toolchain_node_path(repo, supported_majors=("5",)) is None


def test_typescript_toolchain_node_path_none_when_manifest_unreadable(
        tmp_path, monkeypatch):
    install_root = tmp_path / "install"
    repo = _make_repo(tmp_path / "repo")
    bin_dir, _ = _make_depcruise_fake_install(
        install_root, manifest_body="{not valid json")
    monkeypatch.setenv("PATH", bin_dir)
    assert gt.typescript_toolchain_node_path(repo, supported_majors=("5",)) is None


def test_resolve_not_found(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    monkeypatch.setattr(gt.shutil, "which", lambda t: None)
    out = gt.resolve("lizard", repo)
    assert out == {"tool": "lizard", "found": False, "path": None, "source": None}


def test_resolve_never_spawns_a_process(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    monkeypatch.setattr(gt.shutil, "which", lambda t: None)
    run = _FakeRun()
    gt.resolve("jscpd", repo, run=run)
    assert run.calls == []


# --- version --------------------------------------------------------------------

def test_version_parses_bare_version_string(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path / "repo")
    ext = _make_external_tool(tmp_path, "jscpd")
    monkeypatch.setenv("PATH", os.path.dirname(ext))
    run = _FakeRun(stdout="3.5.10\n")
    assert gt.version("jscpd", repo, run=run) == "3.5.10"
    argv, kwargs = run.calls[0]
    assert argv[0] == os.path.realpath(ext)
    assert "--version" in argv
    assert os.path.realpath(kwargs["cwd"]) != os.path.realpath(repo)
    assert "NODE_OPTIONS" not in kwargs.get("env", {})


def test_version_parses_prefixed_version_string(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path / "repo")
    ext = _make_external_tool(tmp_path, "radon")
    monkeypatch.setenv("PATH", os.path.dirname(ext))
    run = _FakeRun(stdout="radon 6.0.1\n")
    assert gt.version("radon", repo, run=run) == "6.0.1"


def test_version_falls_back_to_stderr(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path / "repo")
    ext = _make_external_tool(tmp_path, "lizard")
    monkeypatch.setenv("PATH", os.path.dirname(ext))
    run = _FakeRun(stdout="", stderr="lizard 1.17.10\n")
    assert gt.version("lizard", repo, run=run) == "1.17.10"


def test_version_none_when_tool_missing(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    monkeypatch.setattr(gt.shutil, "which", lambda t: None)
    run = _FakeRun(stdout="3.5.10\n")
    assert gt.version("jscpd", repo, run=run) is None
    assert run.calls == []


def test_version_none_on_nonzero_exit(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path / "repo")
    ext = _make_external_tool(tmp_path, "jscpd")
    monkeypatch.setenv("PATH", os.path.dirname(ext))
    run = _FakeRun(stdout="3.5.10\n", returncode=1)
    assert gt.version("jscpd", repo, run=run) is None


def test_version_none_when_run_raises(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path / "repo")
    ext = _make_external_tool(tmp_path, "jscpd")
    monkeypatch.setenv("PATH", os.path.dirname(ext))
    run = _FakeRun(raises=OSError("boom"))
    assert gt.version("jscpd", repo, run=run) is None


def test_version_none_on_unparseable_output(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path / "repo")
    ext = _make_external_tool(tmp_path, "jscpd")
    monkeypatch.setenv("PATH", os.path.dirname(ext))
    run = _FakeRun(stdout="   \n\n")
    assert gt.version("jscpd", repo, run=run) is None


# --- the red line: this module NEVER installs or fetches ---------------------------

_INSTALLER_VERBS = (
    "npm install", "npm i ", "npm add", "npx", "yarn add", "pnpm add",
    "pip install", "pip3 install", "python -m pip", "brew install",
    "cargo install", "go install", "apt-get install", "curl ", "wget ",
)

_BANNED_CODE_TOKENS = ("npx", "urllib", "requests", "http", "ftplib", "socket")

# An argv list splits the verb across elements (["npm", "install", ...]), so a
# literal-substring scan alone is inert — the binary name itself is banned in code.
_PACKAGE_MANAGER_BINARIES = (
    "npm", "npx", "yarn", "pnpm", "pip", "pip3", "easy_install", "brew", "cargo",
    "go", "apt", "apt-get", "curl", "wget", "gem",
)


def _source_text():
    with open(_SRC_PATH, encoding="utf-8") as fh:
        return fh.read()


def _code_without_comments(src):
    """Source text with comment tokens stripped — comments may DISCUSS installers."""
    import io
    import tokenize
    kept = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            continue
        kept.append(tok.string)
    return "\n".join(kept)


def test_guard_scanner_is_not_vacuous():
    """Fail closed: the scanner must actually have source, strings, and calls to scan."""
    src = _source_text()
    assert src.strip(), "guardian_tools.py source is empty — guard would pass vacuously"
    tree = ast.parse(src)
    strings = [n for n in ast.walk(tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    assert len(strings) >= len(gt.INSTALL_COMMANDS), "no string literals found to scan"
    assert calls, "no call nodes found to scan — guard would pass vacuously"
    assert any(v in s.value for s in strings for v in _INSTALLER_VERBS), (
        "INSTALL_COMMANDS literals should be present — scanner sees the real source")


def _call_literals(call):
    """String literals in a call's subtree, in source order."""
    return [n.value for n in ast.walk(call)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def test_no_installer_verb_reaches_any_call_argument():
    """No call anywhere in the module may carry an installer command as literals.

    Checks each literal AND the joined argv — `["npm", "install", "-g", tool]` hides the
    verb across list elements, so a per-literal substring scan alone would be inert.
    """
    tree = ast.parse(_source_text())
    for call in [n for n in ast.walk(tree) if isinstance(n, ast.Call)]:
        literals = _call_literals(call)
        haystacks = list(literals) + [" ".join(literals)]
        for hay in haystacks:
            for verb in _INSTALLER_VERBS:
                assert verb not in hay, (
                    "installer verb %r reaches a call argument (%r) — guardian_tools "
                    "must never install or fetch anything" % (verb, hay))


def test_no_package_manager_binary_is_named_in_any_call():
    """A call may not name a package manager, however its argv is split."""
    tree = ast.parse(_source_text())
    for call in [n for n in ast.walk(tree) if isinstance(n, ast.Call)]:
        for lit in _call_literals(call):
            head = lit.strip().split()[0] if lit.strip() else ""
            assert head not in _PACKAGE_MANAGER_BINARIES, (
                "call literal %r names package manager %r — guardian_tools resolves "
                "what is already present and acquires nothing" % (lit, head))


def test_no_package_manager_binary_appears_in_executable_code():
    """Belt and braces: package-manager names live only in INSTALL_COMMANDS guidance
    or as a resolvable-tool KEY (`npm` is the argv[0] the deps lens resolves for
    `npm audit`). Tool-name keys are resolved-tool identities, never spawn literals —
    version()'s argv head derives from resolve()['path'] (proven separately)."""
    allowed = set(gt.INSTALL_COMMANDS.values()) | set(gt.INSTALL_COMMANDS)
    tree = ast.parse(_source_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in allowed:
                continue
            for word in node.value.replace("/", " ").split():
                assert word not in _PACKAGE_MANAGER_BINARIES, (
                    "string literal %r names package manager %r outside "
                    "INSTALL_COMMANDS" % (node.value, word))


def test_installer_verbs_only_appear_as_install_commands_guidance():
    """Every installer verb in a string literal must BE an INSTALL_COMMANDS value."""
    allowed = set(gt.INSTALL_COMMANDS.values())
    tree = ast.parse(_source_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if any(v in node.value for v in _INSTALLER_VERBS):
                assert node.value in allowed, (
                    "string literal %r mentions an installer verb but is not an "
                    "INSTALL_COMMANDS value" % node.value)


def test_no_fetch_machinery_in_executable_code():
    code = _code_without_comments(_source_text())
    for banned in _BANNED_CODE_TOKENS:
        if banned == "http":
            assert "import http" not in code and "from http" not in code
            continue
        assert banned not in code, (
            "%r appears in guardian_tools executable code — the module must never "
            "fetch or install" % banned)


def test_no_network_or_installer_imports():
    tree = ast.parse(_source_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imported.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported, "no imports parsed — guard would pass vacuously"
    for banned in ("urllib", "http", "requests", "socket", "ftplib", "pip", "ensurepip"):
        assert banned not in imported


def test_no_install_command_names_a_shell_pipeline():
    """Guidance stays a plain command the owner can read and run deliberately."""
    for tool, cmd in gt.INSTALL_COMMANDS.items():
        assert "|" not in cmd and "&&" not in cmd and ";" not in cmd, tool


def test_module_carries_the_no_autoinstall_constraint_comment():
    src = _source_text()
    assert "MESSAGE ONLY" in src
    assert "Never auto-install" in src
    assert "LEDGERS" in src


# --- allowlist: spawn sites, argv provenance, INSTALL_COMMANDS use --------------
# Blacklist guards above catch literal installer verbs in argv. They miss a
# runtime reassembly of INSTALL_COMMANDS (no banned literal reaches a call).
# These allowlist checks make that evasion unexpressible.

_SUBPROCESS_SPAWN_ATTRS = frozenset({
    "run", "Popen", "call", "check_call", "check_output",
})


def _is_subprocess_spawn_call(call):
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "subprocess"
        and func.attr in _SUBPROCESS_SPAWN_ATTRS
    )


def _is_os_spawn_call(call):
    func = call.func
    if not (isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "os"):
        return False
    attr = func.attr
    return (
        attr in ("system", "popen")
        or attr.startswith("exec")
        or attr.startswith("spawn")
    )


def _expr_mentions_subprocess_run(node):
    for n in ast.walk(node):
        if (isinstance(n, ast.Attribute)
                and n.attr == "run"
                and isinstance(n.value, ast.Name)
                and n.value.id == "subprocess"):
            return True
    return False


def _injectable_runner_names(func_node):
    """Names bound to `run or subprocess.run` (or any expr mentioning subprocess.run)."""
    names = set()
    for node in ast.walk(func_node):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if (isinstance(target, ast.Name)
                    and _expr_mentions_subprocess_run(node.value)):
                names.add(target.id)
    return names


def _function_defs(tree):
    return [n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _collect_spawn_sites(source):
    """Return [(enclosing_func_name, call_node), ...] for every process-spawn site.

    Covers subprocess.run/Popen/call/check_*/os.system/popen/exec*/spawn*, and
    calls to names bound as the injectable runner (`run or subprocess.run`).
    Module-level spawns are attributed to '<module>'.
    """
    tree = ast.parse(source)
    sites = []
    claimed = set()

    for func in _function_defs(tree):
        runners = _injectable_runner_names(func)
        for node in ast.walk(func):
            if not isinstance(node, ast.Call):
                continue
            if (_is_subprocess_spawn_call(node)
                    or _is_os_spawn_call(node)
                    or (isinstance(node.func, ast.Name)
                        and node.func.id in runners)):
                sites.append((func.name, node))
                claimed.add(id(node))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or id(node) in claimed:
            continue
        if _is_subprocess_spawn_call(node) or _is_os_spawn_call(node):
            sites.append(("<module>", node))
    return sites


_SEAM_SPAWN_FUNCTIONS = frozenset({
    "version", "_invoke", "_invoke_subprocess_bounded",
})


def check_spawn_sites_confined_to_seam(source):
    """Allowlist #1: spawns only inside the version probe and invoke seam."""
    sites = _collect_spawn_sites(source)
    funcs = {name for name, _ in sites}
    unexpected = funcs - _SEAM_SPAWN_FUNCTIONS
    if unexpected:
        raise AssertionError(
            "unexpected process-spawn site(s) in %s — must be confined to %s"
            % (sorted(unexpected), sorted(_SEAM_SPAWN_FUNCTIONS))
        )
    if "version" not in funcs:
        raise AssertionError("version() must retain an injectable spawn site")
    if "_invoke_subprocess_bounded" not in funcs:
        raise AssertionError("_invoke_subprocess_bounded must own production spawns")


def check_exactly_one_spawn_site(source):
    check_spawn_sites_confined_to_seam(source)


def _resolve_result_names(func_node):
    """Names assigned from a resolve(...) call inside func_node."""
    names = set()
    for node in ast.walk(func_node):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            val = node.value
            if (isinstance(val, ast.Call)
                    and isinstance(val.func, ast.Name)
                    and val.func.id == "resolve"):
                names.add(target.id)
    return names


def _is_res_path_subscript(node, resolve_names):
    """True if node is resolve_result[\"path\"] / resolve_result['path']."""
    if not isinstance(node, ast.Subscript):
        return False
    if not (isinstance(node.value, ast.Name) and node.value.id in resolve_names):
        return False
    sl = node.slice
    # py3.9+: slice is the index node directly; older ast wrapped Constant in Index
    if isinstance(sl, ast.Constant) and sl.value == "path":
        return True
    return False


def _list_first_elt(node):
    if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
        return node.elts[0]
    return None


def check_spawn_argv_head_from_resolve(source):
    """Allowlist #2: version()'s spawned argv head derives from resolve()['path']."""
    sites = [(n, c) for n, c in _collect_spawn_sites(source) if n == "version"]
    if len(sites) != 1:
        raise AssertionError(
            "expected exactly one spawn site in version(), found %d" % len(sites))
    func_name, call = sites[0]
    tree = ast.parse(source)
    func_node = None
    for func in _function_defs(tree):
        if func.name == func_name:
            func_node = func
            break
    if func_node is None:
        raise AssertionError("spawn site enclosing function %r not found" % func_name)
    if not call.args:
        raise AssertionError(
            "spawn site in %r has no argv argument" % func_name)
    argv_arg = call.args[0]
    resolve_names = _resolve_result_names(func_node)

    # Direct: runner([res["path"], ...], ...)
    head = _list_first_elt(argv_arg)
    if head is not None:
        if _is_res_path_subscript(head, resolve_names):
            return
        raise AssertionError(
            "spawn argv head in %r is not res['path'] from resolve()" % func_name)

    # Indirect: argv = [res["path"]] + ...; runner(argv, ...)
    if isinstance(argv_arg, ast.Name):
        for node in ast.walk(func_node):
            if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
                continue
            target = node.targets[0]
            if not (isinstance(target, ast.Name) and target.id == argv_arg.id):
                continue
            # BinOp: [res["path"]] + something
            val = node.value
            if isinstance(val, ast.BinOp) and isinstance(val.op, ast.Add):
                left_head = _list_first_elt(val.left)
                if left_head is not None and _is_res_path_subscript(
                        left_head, resolve_names):
                    return
                right_head = _list_first_elt(val.right)
                if right_head is not None and _is_res_path_subscript(
                        right_head, resolve_names):
                    return
            head = _list_first_elt(val)
            if head is not None and _is_res_path_subscript(head, resolve_names):
                return
            if _expr_involves_name(val, "INSTALL_COMMANDS"):
                raise AssertionError(
                    "spawn argv in %r is derived from INSTALL_COMMANDS, "
                    "not resolve()['path']" % func_name)
            raise AssertionError(
                "spawn argv %r in %r is not built from resolve()['path']"
                % (argv_arg.id, func_name))
        raise AssertionError(
            "could not find assignment of spawn argv %r in %r"
            % (argv_arg.id, func_name))

    if _expr_involves_name(argv_arg, "INSTALL_COMMANDS"):
        raise AssertionError(
            "spawn argv in %r is derived from INSTALL_COMMANDS, "
            "not resolve()['path']" % func_name)
    raise AssertionError(
        "spawn argv in %r is not built from resolve()['path']" % func_name)


def _expr_involves_name(node, name):
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and n.id == name:
            return True
    return False


def check_install_commands_message_path_only(source):
    """Allowlist #3: INSTALL_COMMANDS is only assigned or read in missing_tool_reason."""
    tree = ast.parse(source)
    offenders = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "missing_tool_reason":
                continue
            for child in ast.walk(node):
                if (isinstance(child, ast.Name)
                        and child.id == "INSTALL_COMMANDS"
                        and isinstance(child.ctx, ast.Load)):
                    offenders.append(node.name)
                    break
            continue
        # Module-level: allow the INSTALL_COMMANDS = {...} assignment only.
        if isinstance(node, ast.Assign):
            targets = []
            for t in node.targets:
                if isinstance(t, ast.Name):
                    targets.append(t.id)
            if targets == ["INSTALL_COMMANDS"]:
                continue
        for child in ast.walk(node):
            if (isinstance(child, ast.Name)
                    and child.id == "INSTALL_COMMANDS"
                    and isinstance(child.ctx, ast.Load)):
                offenders.append("<module>")
                break
    if offenders:
        raise AssertionError(
            "INSTALL_COMMANDS referenced outside missing_tool_reason / its "
            "assignment — offending function(s): %s" % sorted(set(offenders)))


def _is_install_commands_lookup(node):
    """INSTALL_COMMANDS.get(...) or INSTALL_COMMANDS[...]."""
    if isinstance(node, ast.Call):
        func = node.func
        return (
            isinstance(func, ast.Attribute)
            and func.attr == "get"
            and isinstance(func.value, ast.Name)
            and func.value.id == "INSTALL_COMMANDS"
        )
    if isinstance(node, ast.Subscript):
        return (
            isinstance(node.value, ast.Name)
            and node.value.id == "INSTALL_COMMANDS"
        )
    return False


def check_no_runtime_install_command_assembly(source):
    """Allowlist #4: no .split() on INSTALL_COMMANDS lookups; no spawn argv from them."""
    tree = ast.parse(source)
    for call in [n for n in ast.walk(tree) if isinstance(n, ast.Call)]:
        func = call.func
        if not (isinstance(func, ast.Attribute) and func.attr == "split"):
            continue
        # INSTALL_COMMANDS.get(...).split() or INSTALL_COMMANDS[x].split()
        if _is_install_commands_lookup(func.value):
            raise AssertionError(
                "INSTALL_COMMANDS lookup is .split() — runtime command assembly "
                "from the install map is forbidden")
        if _expr_involves_name(func.value, "INSTALL_COMMANDS"):
            raise AssertionError(
                "expression involving INSTALL_COMMANDS is .split() — runtime "
                "command assembly from the install map is forbidden")

    for func_name, spawn in _collect_spawn_sites(source):
        for arg in list(spawn.args) + [
                kw.value for kw in spawn.keywords]:
            if _expr_involves_name(arg, "INSTALL_COMMANDS"):
                raise AssertionError(
                    "spawn-site argv in %r derives from an INSTALL_COMMANDS "
                    "dict-lookup" % func_name)
            # Indirect: name bound to a split/lookup of INSTALL_COMMANDS
            if isinstance(arg, ast.Name):
                enclosing = None
                for func in _function_defs(tree):
                    if func.name == func_name:
                        enclosing = func
                        break
                if enclosing is None:
                    continue
                for node in ast.walk(enclosing):
                    if not (isinstance(node, ast.Assign)
                            and len(node.targets) == 1):
                        continue
                    target = node.targets[0]
                    if not (isinstance(target, ast.Name)
                            and target.id == arg.id):
                        continue
                    if _expr_involves_name(node.value, "INSTALL_COMMANDS"):
                        raise AssertionError(
                            "spawn-site argv in %r derives from an "
                            "INSTALL_COMMANDS dict-lookup (via %r)"
                            % (func_name, arg.id))
                    # BinOp involving a name that was split from INSTALL_COMMANDS
                    if isinstance(node.value, ast.BinOp):
                        for side in (node.value.left, node.value.right):
                            if isinstance(side, ast.Name):
                                if _name_bound_to_install_commands_split(
                                        enclosing, side.id):
                                    raise AssertionError(
                                        "spawn-site argv in %r derives from "
                                        "INSTALL_COMMANDS via .split() (via %r)"
                                        % (func_name, side.id))
                            if _expr_involves_name(side, "INSTALL_COMMANDS"):
                                raise AssertionError(
                                    "spawn-site argv in %r derives from an "
                                    "INSTALL_COMMANDS dict-lookup"
                                    % func_name)


def _name_bound_to_install_commands_split(func_node, name):
    for node in ast.walk(func_node):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        target = node.targets[0]
        if not (isinstance(target, ast.Name) and target.id == name):
            continue
        val = node.value
        if (isinstance(val, ast.Call)
                and isinstance(val.func, ast.Attribute)
                and val.func.attr == "split"
                and (_is_install_commands_lookup(val.func.value)
                     or _expr_involves_name(val.func.value, "INSTALL_COMMANDS"))):
            return True
    return False


_EVASION_AFTER_DEL_RUN = (
    "    _c = INSTALL_COMMANDS.get(tool, \"\").split()\n"
    "    if _c and not shutil.which(tool):\n"
    "        subprocess.run(_c + [tool], capture_output=True)\n"
)


def _source_with_install_commands_reassembly_evasion(source):
    """In-memory only: splice the proven INSTALL_COMMANDS-reassembly evasion into resolve."""
    needle = "    del run  # resolution never executes anything\n"
    if needle not in source:
        raise AssertionError(
            "cannot splice evasion — expected resolve() marker missing from source")
    return source.replace(needle, needle + _EVASION_AFTER_DEL_RUN, 1)


def test_exactly_one_process_spawn_site_in_version():
    check_exactly_one_spawn_site(_source_text())


def test_spawn_argv_head_comes_from_resolve_path():
    check_spawn_argv_head_from_resolve(_source_text())


def test_install_commands_read_only_by_missing_tool_reason():
    check_install_commands_message_path_only(_source_text())


def test_no_runtime_install_command_assembly():
    check_no_runtime_install_command_assembly(_source_text())


def test_allowlist_guards_reject_install_commands_reassembly_evasion():
    """Anti-vacuity: each allowlist check must fail closed on the proven evasion."""
    mutated = _source_with_install_commands_reassembly_evasion(_source_text())
    # Never write mutated source to disk — in-memory AST only.
    ast.parse(mutated)  # must remain parseable

    with pytest.raises(AssertionError) as e1:
        check_spawn_sites_confined_to_seam(mutated)
    assert "resolve" in str(e1.value)

    with pytest.raises(AssertionError) as e2:
        check_no_runtime_install_command_assembly(mutated)
    assert "INSTALL_COMMANDS" in str(e2.value)

    with pytest.raises(AssertionError) as e3:
        check_install_commands_message_path_only(mutated)
    assert "resolve" in str(e3.value)

    funcs = {n for n, _ in _collect_spawn_sites(mutated)}
    assert "resolve" in funcs, "evasion must add a spawn site in resolve()"


# --- invocation seam unit tests + RCE regressions ---------------------------------

RCE_MARKER_NAME = "GUARDIAN_RCE_REGRESSION_MARKER"
FAKE_COLLECTOR = "guardian-test-collector"


def _write_executable(path, body):
    path = str(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    return path


def _python_collector_shebang():
    return "#!" + sys.executable + "\n"


def _assert_hardened_argv(argv, expected_operands=None, repo=None):
    assert "--" in argv, "end-of-options separator missing"
    sep = argv.index("--")
    before = argv[:sep]
    assert "--config" not in before
    operands = argv[sep + 1:]
    assert operands
    if expected_operands is not None:
        expected = gt.absolute_repo_operands(os.path.realpath(repo), list(expected_operands))
        assert operands == expected, (operands, expected)
    for op in operands:
        assert os.path.isabs(op), op
        assert not op.startswith("-"), op
        if repo is not None:
            assert gt._realpath_is_under(op, os.path.realpath(repo)), op


def test_invoke_rejects_repo_local_tool_without_spawning(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    binp = _make_node_modules_bin(tmp_path, FAKE_COLLECTOR)
    monkeypatch.setenv("PATH", str(tmp_path / "node_modules" / ".bin"))
    run = _FakeRun(stdout="ok\n")
    out = gt.invoke(FAKE_COLLECTOR, ["--probe"], repo, ["src"])
    assert out["outcome"] == "tool-absent"
    assert out["argv"] is None
    assert out["cwd"] is None
    assert out["returncode"] is None
    assert out["stdout"] == ""
    assert out["stderr"] == ""
    assert out["truncated"] is False
    assert "reason" in out
    assert run.calls == []
    assert os.path.isfile(binp)


def test_invoke_raises_on_relative_repo(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    ext = _make_external_tool(tmp_path, FAKE_COLLECTOR)
    monkeypatch.setenv("PATH", os.path.dirname(ext))
    with pytest.raises(ValueError, match="repo must be an absolute path"):
        gt.invoke(FAKE_COLLECTOR, [], os.path.basename(repo), ["src"], run=_FakeRun())


def test_invoke_raises_when_explicit_cwd_inside_repo(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    ext = _make_external_tool(tmp_path, FAKE_COLLECTOR)
    monkeypatch.setenv("PATH", os.path.dirname(ext))
    os.makedirs(os.path.join(repo, "src"))
    inner = os.path.join(repo, "inner")
    os.makedirs(inner)
    with pytest.raises(ValueError, match="collector cwd must not be inside"):
        gt.invoke(
            FAKE_COLLECTOR, [], repo, ["src"],
            cwd=inner, run=_FakeRun())


def test_absolute_repo_operands_rejects_indeterminate_containment(tmp_path):
    repo = _init_repo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = os.path.join(repo, "operand-link")
    os.symlink(str(outside), link)
    with pytest.raises(ValueError, match="resolves outside the swept repo"):
        gt.absolute_repo_operands(repo, [link])


def test_invoke_rejects_executable_under_repo_despite_nested_git(
        tmp_path, monkeypatch):
    """Authoritative sweep root wins over a nested rogue ``.git`` in resolve."""
    repo = _init_repo(tmp_path)
    nested = os.path.join(repo, "nested")
    os.makedirs(nested)
    os.makedirs(os.path.join(nested, ".git"))
    ext = _make_external_tool(tmp_path, FAKE_COLLECTOR, leaf="outside")
    tool_in_repo = os.path.join(repo, FAKE_COLLECTOR)
    shutil.copy2(ext, tool_in_repo)
    os.chmod(tool_in_repo, os.stat(tool_in_repo).st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", os.path.dirname(tool_in_repo))
    # Without the invoke belt, resolve would accept (nested .git shrinks trust root).
    monkeypatch.setattr(gt, "_git_toplevel", lambda cwd: nested)
    out = gt.invoke(FAKE_COLLECTOR, [], repo, ["src"])
    assert out["outcome"] == "tool-absent"
    assert gt.REJECTION_REPO_LOCAL in out.get("reason", "")


def test_invoke_builds_argv_with_resolved_head_fixed_args_and_absolute_targets(
        tmp_path, monkeypatch):
    repo = _make_repo(tmp_path / "repo")
    ext = _make_external_tool(tmp_path, FAKE_COLLECTOR)
    monkeypatch.setenv("PATH", os.path.dirname(ext))
    captured = []

    def run(argv, **kwargs):
        captured.append(list(argv))
        class R:
            returncode = 0
            stdout = "ok\n"
            stderr = ""
        return R()

    out = gt.invoke(FAKE_COLLECTOR, ["--json"], str(repo), ["pkg/a", "pkg/b"], run=run)
    assert out["outcome"] == "ok"
    argv = captured[0]
    assert argv[0] == os.path.realpath(ext)
    assert argv[1:2] == ["--json"]
    sep = argv.index("--")
    assert argv[sep + 1:] == gt.absolute_repo_operands(str(repo), ["pkg/a", "pkg/b"])


def _init_repo(tmp_path, name="repo"):
    path = tmp_path / name
    path.mkdir(parents=True, exist_ok=True)
    return init_calibrated_repo(path)


def test_invoke_runs_from_neutral_cwd_with_sanitized_env(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    ext = _make_external_tool(tmp_path, FAKE_COLLECTOR)
    monkeypatch.setenv("PATH", os.path.dirname(ext))
    monkeypatch.setenv("NODE_OPTIONS", "--require ./evil.js")
    captured = []

    def run(argv, **kwargs):
        captured.append(kwargs)
        class R:
            returncode = 0
            stdout = "ok\n"
            stderr = ""
        return R()

    gt.invoke(FAKE_COLLECTOR, [], repo, ["src"], run=run)
    kw = captured[0]
    assert os.path.realpath(kw["cwd"]) != os.path.realpath(repo)
    env = kw["env"]
    assert "NODE_OPTIONS" not in env
    for name in gt.COLLECTOR_ENV_CODE_LOADING:
        if name != gt.NODE_PATH_ENV:
            assert name not in env


def test_neutral_collector_cwd_raises_when_temp_base_inside_repo(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    fake_tmp = os.path.join(repo, "tmpdir")
    os.makedirs(fake_tmp)
    monkeypatch.setattr(gt.tempfile, "gettempdir", lambda: fake_tmp)
    gt._NEUTRAL_COLLECTOR_CWD = None
    with pytest.raises(RuntimeError, match="temp base"):
        gt.neutral_collector_cwd(repo)


# --- neutral_tool_config --------------------------------------------------------

def test_neutral_tool_config_returns_absolute_empty_file(tmp_path):
    repo = _init_repo(tmp_path)
    path = gt.neutral_tool_config(repo, "osv-scanner")
    assert os.path.isabs(path)
    assert os.path.isfile(path)
    assert os.path.getsize(path) == 0


def test_neutral_tool_config_caches_per_name(tmp_path):
    repo = _init_repo(tmp_path)
    a1 = gt.neutral_tool_config(repo, "osv-scanner")
    a2 = gt.neutral_tool_config(repo, "osv-scanner")
    assert a1 == a2
    other = gt.neutral_tool_config(repo, "other-tool")
    assert other != a1


def test_neutral_tool_config_recreates_deleted_file(tmp_path):
    repo = _init_repo(tmp_path)
    path = gt.neutral_tool_config(repo, "osv-scanner")
    os.remove(path)
    path2 = gt.neutral_tool_config(repo, "osv-scanner")
    assert path2 == path
    assert os.path.isfile(path2)
    assert os.path.getsize(path2) == 0


def test_neutral_tool_config_raises_when_temp_base_inside_repo(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    fake_tmp = os.path.join(repo, "tmpdir")
    os.makedirs(fake_tmp)
    monkeypatch.setattr(gt.tempfile, "gettempdir", lambda: fake_tmp)
    gt._NEUTRAL_TOOL_CONFIGS.clear()
    with pytest.raises(RuntimeError, match="temp base"):
        gt.neutral_tool_config(repo, "osv-scanner")


@pytest.mark.parametrize("evil_name", ["../../evil", "a/b", "..%2F"])
def test_neutral_tool_config_traversal_name_stays_under_temp(tmp_path, evil_name):
    repo = _init_repo(tmp_path)
    tmp_base = tempfile.gettempdir()
    path = gt.neutral_tool_config(repo, evil_name)
    assert gt._realpath_is_under(path, tmp_base)
    assert not gt._realpath_is_under(path, os.path.realpath(repo))


def test_invoke_subprocess_bounded_truncates_oversized_stdout(tmp_path, monkeypatch):
    monkeypatch.setattr(gt, "MAX_OUTPUT_BYTES", 64)
    res = gt._invoke(
        None, FAKE_COLLECTOR,
        [sys.executable, "-c", "print('x' * 128)"],
        str(tmp_path), 5, os.environ.copy(), None)
    assert res["outcome"] == "truncated-output"


def test_invoke_subprocess_bounded_capture_incomplete_when_reader_survives_join(
        tmp_path, monkeypatch):
    """Surviving reader threads must not yield empty-output from a partial drain."""
    repo = _init_repo(tmp_path)
    payload = "complete-payload-data"
    collector = _write_executable(
        tmp_path / "bin" / FAKE_COLLECTOR,
        _python_collector_shebang() +
        "import sys\nsys.stdout.write(%r)\nsys.stdout.flush()\n" % payload)
    monkeypatch.setenv("PATH", os.path.dirname(collector))

    stall = threading.Event()
    original_read = gt._read_pipe_bounded

    def _stall_stdout_read(pipe, max_bytes):
        if max_bytes == gt.MAX_OUTPUT_BYTES:
            stall.wait()
        return original_read(pipe, max_bytes)

    monkeypatch.setattr(gt, "_read_pipe_bounded", _stall_stdout_read)

    original_join = threading.Thread.join

    def _instant_join(self, timeout=None):
        return original_join(self, timeout=0)

    monkeypatch.setattr(threading.Thread, "join", _instant_join)

    out = gt.invoke(FAKE_COLLECTOR, [], repo, ["src"], run=None)
    assert out["outcome"] == "capture-incomplete", out
    assert out.get("reason")
    assert out["outcome"] != "empty-output"


def test_invoke_subprocess_bounded_ok_when_readers_drain_fully(tmp_path, monkeypatch):
    """Fully draining readers on the success path still yield ok with complete stdout."""
    repo = _init_repo(tmp_path)
    payload = "drained-output"
    collector = _write_executable(
        tmp_path / "bin" / FAKE_COLLECTOR,
        _python_collector_shebang() +
        "import sys\nsys.stdout.write(%r)\nsys.stdout.flush()\n" % payload)
    monkeypatch.setenv("PATH", os.path.dirname(collector))
    out = gt.invoke(FAKE_COLLECTOR, [], repo, ["src"], run=None)
    assert out["outcome"] == "ok", out
    assert out["stdout"] == payload


def test_invoke_subprocess_bounded_captures_complete_stdout_after_exit(
        tmp_path, monkeypatch):
    """Reader threads must join before stdout boxes are read on the success path."""
    repo = _init_repo(tmp_path)
    payload = "P" * 8192
    collector = _write_executable(
        tmp_path / "bin" / FAKE_COLLECTOR,
        _python_collector_shebang() +
        "import sys\n"
        "sys.stdout.write(%r)\n"
        "sys.stdout.flush()\n" % payload)
    monkeypatch.setenv("PATH", os.path.dirname(collector))
    original_read = gt._read_pipe_bounded

    def _slow_read(pipe, max_bytes):
        text, trunc = original_read(pipe, max_bytes)
        time.sleep(0.05)
        return text, trunc

    monkeypatch.setattr(gt, "_read_pipe_bounded", _slow_read)
    for _ in range(3):
        out = gt.invoke(FAKE_COLLECTOR, [], repo, ["src"], run=None)
        assert out["outcome"] == "ok", out
        assert out["stdout"] == payload


def test_kill_process_tree_child_pgid_none_uses_proc_kill_only(monkeypatch):
    killpg_calls = []

    def fake_killpg(pgid, sig):
        killpg_calls.append((pgid, sig))
        raise AssertionError("killpg must not run when child_pgid is None")

    monkeypatch.setattr(os, "killpg", fake_killpg)
    killed = []

    class FakeProc:
        pid = 12345

        def kill(self):
            killed.append(True)

    gt._kill_process_tree(FakeProc(), None)
    assert killed
    assert not killpg_calls


def test_kill_process_tree_child_pgid_uses_stored_killpg_not_getpgid(monkeypatch):
    killpg_calls = []

    def fake_killpg(pgid, sig):
        killpg_calls.append((pgid, sig))

    def fail_getpgid(pid):
        raise AssertionError("getpgid must not be called — use stored child_pgid")

    monkeypatch.setattr(os, "killpg", fake_killpg)
    monkeypatch.setattr(os, "getpgid", fail_getpgid)

    class FakeProc:
        pid = 12345

        def kill(self):
            raise AssertionError("proc.kill must not run when killpg succeeds")

    stored_pgid = 4242
    gt._kill_process_tree(FakeProc(), stored_pgid)
    assert killpg_calls == [(stored_pgid, signal.SIGKILL)]


def test_kill_process_tree_child_pgid_survives_reaped_leader(monkeypatch):
    """Stored pgid must be used even when getpgid(proc.pid) would fail."""
    killpg_calls = []

    def fake_killpg(pgid, sig):
        killpg_calls.append((pgid, sig))

    def reaped_getpgid(pid):
        raise ProcessLookupError(pid)

    monkeypatch.setattr(os, "killpg", fake_killpg)
    monkeypatch.setattr(os, "getpgid", reaped_getpgid)

    class FakeProc:
        pid = 12345

        def kill(self):
            raise AssertionError("proc.kill must not run when killpg succeeds")

    stored_pgid = 7777
    gt._kill_process_tree(FakeProc(), stored_pgid)
    assert killpg_calls == [(stored_pgid, signal.SIGKILL)]


def test_kill_process_tree_child_pgid_falls_back_to_proc_kill_on_killpg_error(monkeypatch):
    killed = []

    def fail_killpg(pgid, sig):
        raise OSError("killpg failed")

    monkeypatch.setattr(os, "killpg", fail_killpg)

    class FakeProc:
        pid = 12345

        def kill(self):
            killed.append(True)

    gt._kill_process_tree(FakeProc(), 5555)
    assert killed


def test_version_runs_from_neutral_cwd_with_sanitized_env(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    ext = _make_external_tool(tmp_path, "jscpd")
    monkeypatch.setenv("PATH", os.path.dirname(ext))
    monkeypatch.setenv("NODE_OPTIONS", "--require ./evil.js")
    run = _FakeRun(stdout="1.2.3\n")
    gt.version("jscpd", repo, run=run)
    _, kwargs = run.calls[0]
    assert os.path.realpath(kwargs["cwd"]) != os.path.realpath(repo)
    assert "NODE_OPTIONS" not in kwargs["env"]


def test_sanitized_env_drops_empty_relative_and_repo_path_never_absolutizes(tmp_path):
    repo = _init_repo(tmp_path)
    rel = "rel-bin"
    os.makedirs(os.path.join(repo, rel))
    repo_bin = os.path.join(repo, "bin")
    os.makedirs(repo_bin)
    old = os.getcwd()
    try:
        os.chdir(repo)
        env = gt.sanitized_env(
            base_env={"PATH": os.pathsep.join(["", rel, repo_bin, "/usr/bin", ""])},
            repo=repo)
    finally:
        os.chdir(old)
    parts = (env.get("PATH") or "").split(os.pathsep)
    assert "" not in parts
    assert rel not in parts
    assert os.path.realpath(os.path.join(repo, rel)) not in [
        os.path.realpath(p) for p in parts if p]
    assert os.path.realpath(repo_bin) not in [os.path.realpath(p) for p in parts if p]
    assert "/usr/bin" in parts


def test_sanitized_env_falls_back_to_safe_path_when_all_stripped(tmp_path):
    repo = _init_repo(tmp_path)
    rel = "rel-bin"
    os.makedirs(os.path.join(repo, rel))
    repo_bin = os.path.join(repo, "bin")
    os.makedirs(repo_bin)
    old = os.getcwd()
    try:
        os.chdir(repo)
        env = gt.sanitized_env(
            base_env={"PATH": os.pathsep.join(["", ".", rel, repo_bin, ""])},
            repo=repo)
    finally:
        os.chdir(old)
    path = env.get("PATH") or ""
    assert path != ""
    assert path == gt._default_safe_path()
    parts = path.split(os.pathsep)
    assert "" not in parts
    for part in gt._DEFAULT_SAFE_PATH_PARTS:
        if os.path.isdir(part):
            assert part in parts


def test_sanitized_env_keeps_nonexistent_outside_toolchain_node_path():
    env = gt.sanitized_env(
        base_env={gt.NODE_PATH_ENV: os.pathsep.join([
            "/abs/toolchain", "/other/outside"])} )
    assert env[gt.NODE_PATH_ENV] == "/abs/toolchain" + os.pathsep + "/other/outside"


def test_rce_regression_node_options_require_never_reaches_collector_child(
        tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    ext = _write_executable(
        tmp_path / "bin" / FAKE_COLLECTOR,
        "#!/bin/sh\necho ok\n")
    monkeypatch.setenv("PATH", os.path.dirname(ext))
    marker = os.path.join(repo, RCE_MARKER_NAME)
    with open(os.path.join(repo, "evil.js"), "w", encoding="utf-8") as fh:
        fh.write(
            "require('fs').writeFileSync(%r, 'node-options-executed\\n');\n"
            % RCE_MARKER_NAME)
    assert not os.path.exists(marker)
    monkeypatch.setenv("NODE_OPTIONS", "--require ./evil.js")
    captured = []

    def run(argv, **kwargs):
        captured.append(dict(kwargs))
        class R:
            returncode = 0
            stdout = "ok\n"
            stderr = ""
        return R()

    gt.invoke(FAKE_COLLECTOR, [], repo, ["src"], run=run)
    assert not os.path.exists(marker)
    assert captured
    repo_real = os.path.realpath(repo)
    for kw in captured:
        assert "NODE_OPTIONS" not in kw["env"]
        assert os.path.realpath(kw["cwd"]) != repo_real

    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed (positive control gated)")
    control_env = dict(os.environ)
    control_env["NODE_OPTIONS"] = "--require ./evil.js"
    subprocess.run(
        [node, "-e", "process.exit(0)"],
        cwd=repo, env=control_env, capture_output=True, text=True,
        timeout=30, check=False)
    assert os.path.isfile(marker)


def test_rce_regression_path_never_absolutized_to_select_repo_depcruise(tmp_path):
    repo = _init_repo(tmp_path)
    marker = os.path.join(repo, RCE_MARKER_NAME)
    bin_dir = os.path.join(repo, "bin")
    os.makedirs(bin_dir)
    fake = os.path.join(bin_dir, "depcruise")
    _write_executable(fake, "#!/usr/bin/env python3\nopen(%r, 'w').write('x')\n" % marker)
    old = os.getcwd()
    try:
        os.chdir(repo)
        built = gt.sanitized_env(
            base_env={"PATH": os.pathsep.join(["bin", "/usr/bin", "/bin"])},
            repo=repo)
    finally:
        os.chdir(old)
    parts = [p for p in (built.get("PATH") or "").split(os.pathsep) if p]
    assert "bin" not in parts
    assert os.path.realpath(bin_dir) not in [os.path.realpath(p) for p in parts]

    assert not os.path.exists(marker)
    control_env = {
        "PATH": os.pathsep.join([bin_dir, "/usr/bin", "/bin"]),
        "HOME": os.environ.get("HOME", "/tmp"),
    }
    subprocess.run(
        ["depcruise"], cwd=repo, env=control_env, capture_output=True, text=True,
        timeout=10, check=False)
    assert os.path.isfile(marker)


def test_rce_regression_node_path_inside_repo_never_loads_repo_packages(
        tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    ext = _write_executable(
        tmp_path / "bin" / FAKE_COLLECTOR,
        "#!/bin/sh\necho ok\n")
    monkeypatch.setenv("PATH", os.path.dirname(ext))
    marker = os.path.join(repo, RCE_MARKER_NAME)
    pkg_dir = os.path.join(repo, "node_modules", "guardian_rce_probe")
    os.makedirs(pkg_dir)
    with open(os.path.join(pkg_dir, "index.js"), "w", encoding="utf-8") as fh:
        fh.write(
            "require('fs').writeFileSync(%r, 'node-path-executed\\n');\n"
            % RCE_MARKER_NAME)
    nm = os.path.join(repo, "node_modules")
    monkeypatch.setenv(gt.NODE_PATH_ENV, nm)
    captured = []

    def run(argv, **kwargs):
        captured.append(dict(kwargs))
        class R:
            returncode = 0
            stdout = "ok\n"
            stderr = ""
        return R()

    gt.invoke(FAKE_COLLECTOR, [], repo, ["src"], run=run)
    assert not os.path.exists(marker)
    repo_real = os.path.realpath(repo)
    nm_real = os.path.realpath(nm)
    for kw in captured:
        child_np = kw["env"].get(gt.NODE_PATH_ENV)
        if child_np:
            for p in child_np.split(os.pathsep):
                if p:
                    assert os.path.realpath(p) != nm_real
                    assert not gt._realpath_is_under(p, repo_real)

    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed (positive control gated)")
    control_env = dict(os.environ)
    control_env[gt.NODE_PATH_ENV] = nm
    subprocess.run(
        [node, "-e", "require('guardian_rce_probe')"],
        cwd=repo, env=control_env, capture_output=True, text=True,
        timeout=30, check=False)
    assert os.path.isfile(marker)


def _config_dir_trap_fixture(tmp_path):
    repo = _init_repo(tmp_path)
    marker = os.path.join(repo, RCE_MARKER_NAME)
    os.makedirs(os.path.join(repo, "src"), exist_ok=True)
    with open(os.path.join(repo, "src", "a.js"), "w", encoding="utf-8") as fh:
        fh.write("export const a = 1;\n")
    os.makedirs(os.path.join(repo, "--config"), exist_ok=True)
    with open(os.path.join(repo, "--config", "x.js"), "w", encoding="utf-8") as fh:
        fh.write("export const x = 1;\n")
    trap_script = _write_executable(
        tmp_path / "bin" / FAKE_COLLECTOR,
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if sys.argv and sys.argv[-1] == '--config':\n"
        "    open(%r, 'w').write('trap\\n')\n"
        "print('ok')\n" % marker)
    return repo, marker, trap_script


def test_rce_regression_config_dir_trap_non_option_target_before_bare_config(
        tmp_path, monkeypatch):
    repo, marker, trap = _config_dir_trap_fixture(tmp_path)
    monkeypatch.setenv("PATH", os.path.dirname(trap))
    targets = ["src", "--config"]
    captured = []

    def run(argv, **kwargs):
        captured.append(list(argv))
        class R:
            returncode = 0
            stdout = "ok\n"
            stderr = ""
        return R()

    gt.invoke(FAKE_COLLECTOR, ["--json"], repo, targets, run=run)
    assert not os.path.exists(marker)
    for argv in captured:
        _assert_hardened_argv(argv, targets, repo=repo)

    subprocess.run(
        [sys.executable, trap, "--json", "src", "--config"],
        cwd=repo, capture_output=True, text=True, check=False)
    assert os.path.isfile(marker)


def test_rce_regression_config_dir_trap_bare_config_operand_before_target(
        tmp_path, monkeypatch):
    repo, marker, trap = _config_dir_trap_fixture(tmp_path)
    monkeypatch.setenv("PATH", os.path.dirname(trap))
    targets = ["--config", "src"]
    captured = []

    def run(argv, **kwargs):
        captured.append(list(argv))
        class R:
            returncode = 0
            stdout = "ok\n"
            stderr = ""
        return R()

    gt.invoke(FAKE_COLLECTOR, ["--json"], repo, targets, run=run)
    assert not os.path.exists(marker)
    for argv in captured:
        _assert_hardened_argv(argv, targets, repo=repo)

    subprocess.run(
        [sys.executable, trap, "--json", "src", "--config"],
        cwd=repo, capture_output=True, text=True, check=False)
    assert os.path.isfile(marker)


def test_rce_regression_depcruise_webpack_config_never_executes_during_lens_collect(
        tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    marker = os.path.join(repo, RCE_MARKER_NAME)
    with open(os.path.join(repo, ".dependency-cruiser.js"), "w", encoding="utf-8") as fh:
        fh.write(
            "require('fs').writeFileSync(%r, 'webpack-config-executed\\n');\n"
            "module.exports = {};\n" % RCE_MARKER_NAME)
    collector = _write_executable(
        tmp_path / "bin" / FAKE_COLLECTOR,
        _python_collector_shebang() +
        "import os\n"
        "cfg = '.dependency-cruiser.js'\n"
        "if os.path.isfile(cfg):\n"
        "    open(%r, 'w').write('webpack-config-executed\\n')\n"
        "print('ok')\n" % marker)
    monkeypatch.setenv("PATH", os.path.dirname(collector))
    assert not os.path.exists(marker)

    out = gt.invoke(FAKE_COLLECTOR, [], repo, ["src"], run=None)
    assert out["outcome"] == "ok", out
    assert not os.path.exists(marker)

    subprocess.run(
        [sys.executable, collector], cwd=repo, capture_output=True, text=True, check=False)
    assert os.path.isfile(marker)


def test_rce_regression_import_linter_contract_types_never_imports_repo_code(
        tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    marker = os.path.join(repo, RCE_MARKER_NAME)
    os.makedirs(os.path.join(repo, "app"), exist_ok=True)
    open(os.path.join(repo, "app", "__init__.py"), "w").close()
    with open(os.path.join(repo, "app", "payload.py"), "w", encoding="utf-8") as fh:
        fh.write(
            "open(%r, 'w').write('contract-types-executed\\n')\n"
            "class Attack:\n    pass\n" % RCE_MARKER_NAME)
    with open(os.path.join(repo, "setup.cfg"), "w", encoding="utf-8") as fh:
        fh.write(
            "[importlinter]\nroot_package = app\ncontract_types = pwn: app.payload.Attack\n")
    collector = _write_executable(
        tmp_path / "bin" / FAKE_COLLECTOR,
        _python_collector_shebang() +
        "import configparser, importlib, os, sys\n"
        "sys.path.insert(0, os.getcwd())\n"
        "cp = configparser.ConfigParser()\n"
        "cp.read('setup.cfg')\n"
        "spec = cp.get('importlinter', 'contract_types', fallback='').strip()\n"
        "if ':' in spec:\n"
        "    rhs = spec.split(':', 1)[1].strip()\n"
        "    mod_name, _, cls_name = rhs.rpartition('.')\n"
        "    getattr(importlib.import_module(mod_name.strip()), cls_name.strip())\n"
        "print('ok')\n")
    monkeypatch.setenv("PATH", os.path.dirname(collector))
    assert not os.path.exists(marker)

    out = gt.invoke(FAKE_COLLECTOR, [], repo, ["app"], run=None)
    assert out["outcome"] == "ok", out
    assert not os.path.exists(marker)

    subprocess.run(
        [sys.executable, collector], cwd=repo, capture_output=True, text=True, check=False)
    assert os.path.isfile(marker)

