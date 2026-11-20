"""The census of what the plugin's SessionStart hook reads (issue 2568).

`cloud_setup_text.START_HOOK_READS` lists the plugin files the real `hooks/session_start.py` reads,
and the setup stamp counts exactly those (plus the SessionStart registrations). The list is measured:
the real hook runs in a fresh process under an audit hook that records every file it opens inside
the plugin, in every configuration that changes what it reads, and the union must equal the list in
both directions. A second test is a static belt over the imports, and a third proves the comparison
reports a difference either way.
"""
import ast
import base64
import json
import os
import subprocess
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PLUGIN = os.path.dirname(_LIB)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_pass  # noqa: E402
import cloud_setup_text  # noqa: E402

HOOK = os.path.join(_PLUGIN, "hooks", "session_start.py")
LISTED = set(cloud_setup_text.START_HOOK_READS)
SOURCES = ("startup", "resume", "clear", "compact")

# The runner installs an audit hook for `open` events, runs the real hook as `__main__`, and writes
# the plugin-relative path of every file opened under the plugin root (bytecode left out) to a log.
RUNNER = '''\
import json
import os
import runpy
import sys

plugin_root = os.path.realpath(sys.argv[1])
hook, log = sys.argv[2], sys.argv[3]
seen = set()


def audit(event, args):
    if event != "open" or not args:
        return
    target = args[0]
    if not isinstance(target, (str, bytes, os.PathLike)):
        return
    try:
        real = os.path.realpath(os.fsdecode(target))
    except Exception:
        return
    if not real.startswith(plugin_root + os.sep):
        return
    if "__pycache__" in real.split(os.sep) or real.endswith(".pyc"):
        return
    # a directory opened (a marker sweep's O_DIRECTORY open) is no file the hook reads
    if os.path.isdir(real):
        return
    seen.add(os.path.relpath(real, plugin_root).replace(os.sep, "/"))


sys.addaudithook(audit)
sys.argv = [hook]
code = 0
try:
    runpy.run_path(hook, run_name="__main__")
except SystemExit as exc:
    code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
sys.stdout.flush()
with open(log, "w", encoding="utf-8") as fh:
    json.dump(sorted(seen), fh)
sys.exit(code)
'''


def _env(home, remote, extra=None):
    env = {"HOME": str(home), "PATH": os.environ.get("PATH", ""),
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
           "PYTHONDONTWRITEBYTECODE": "1"}
    if remote:
        env["CLAUDE_CODE_REMOTE"] = "true"
    env.update(extra or {})
    return env


def _fresh_repo(base, calibrated):
    repo = base / "repo"
    repo.mkdir(parents=True)
    env = {"PATH": os.environ.get("PATH", ""), "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(base / "home")}
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True, env=env)
    if calibrated:
        # an in-repo review-crew calibration file is the evidence `session_context.covenant`
        # reads (`mode_registry.hero_evidence`) to treat the project as calibrated
        layer = repo / ".claude" / "superheroes"
        layer.mkdir(parents=True)
        (layer / "review-crew.md").write_text("# Crew\n")
    return repo


def _placeable_pass():
    """A pass `cloud_pass.place` accepts, built at run time from obviously fake pieces: an access
    token whose middle part carries a far-future expiry, a fake id token and an empty renewal key."""
    claims = base64.urlsafe_b64encode(
        json.dumps({"exp": 4000000000}).encode("ascii")).rstrip(b"=").decode("ascii")
    tokens = {"access" + "_token": ".".join(("fake-head", claims, "fake-sig")),
              "id" + "_token": "fake-id-" + "q" * 20,
              "refresh" + "_token": ""}
    return base64.b64encode(json.dumps({"tokens": tokens}).encode("ascii")).decode("ascii")


def _run(tmp_path_factory, runner, name, source, remote, calibrated, with_pass=None):
    base = tmp_path_factory.mktemp(name)
    (base / "home").mkdir()
    repo = _fresh_repo(base, calibrated)
    log = base / "opened.json"
    extra = {}
    if with_pass:
        # built at run time from pieces: a junk value that is no real pass, or a fake one that places
        extra[cloud_pass.PASS_ENV] = (_placeable_pass() if with_pass == "placeable"
                                      else "junk-" + "x" * 24 + "-" + "y" * 24)
        env_file = base / "claude-env"
        env_file.write_text("")
        extra["CLAUDE_ENV_FILE"] = str(env_file)
    payload = {"source": source, "cwd": str(repo), "session_id": "census-" + name,
               "transcript_path": str(base / "transcript.jsonl")}
    # A fresh, empty bytecode prefix: with a compiled file already beside a module, Python loads
    # that and never opens the source, so the audit would miss a file the hook really needs.
    # Pinned condition: no bytecode is read; a cloud session's first start has none either, and the
    # set of files it reads does not depend on whether bytecode exists.
    prefix = base / "pycache"
    done = subprocess.run(
        [sys.executable, "-B", "-X", "pycache_prefix=" + str(prefix), str(runner), _PLUGIN, HOOK,
         str(log)], input=json.dumps(payload),
        cwd=str(repo), env=_env(base / "home", remote, extra), capture_output=True, text=True,
        timeout=120)
    opened = set(json.loads(log.read_text())) if log.exists() else None
    return {"name": name, "code": done.returncode, "stdout": done.stdout, "stderr": done.stderr,
            "opened": opened, "calibrated": calibrated, "home": base / "home",
            "pass": with_pass}


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    runner = tmp_path_factory.mktemp("runner") / "audit_runner.py"
    runner.write_text(RUNNER)
    out = []
    for source in SOURCES:
        for remote in (False, True):
            for calibrated in (False, True):
                name = "%s-%s-%s" % (source, "remote" if remote else "local",
                                     "calibrated" if calibrated else "bare")
                out.append(_run(tmp_path_factory, runner, name, source, remote, calibrated))
    out.append(_run(tmp_path_factory, runner, "remote-pass-env-file", "startup", True, False,
                    with_pass="junk"))
    # the success path: a pass the hook places, so a file read only after a successful placement
    # is in the union the list is compared against
    out.append(_run(tmp_path_factory, runner, "remote-pass-placed", "startup", True, True,
                    with_pass="placeable"))
    return out


def _differences(observed, listed):
    """(read but not listed, listed but not read), each sorted."""
    return sorted(set(observed) - set(listed)), sorted(set(listed) - set(observed))


def test_every_configuration_runs_the_real_hook_to_a_bootstrap(runs):
    assert len(runs) == 18
    for run in runs:
        assert run["code"] == 0, run
        assert run["opened"] is not None, run
        out = json.loads(run["stdout"])
        assert "hookSpecificOutput" in out, run
        context = out["hookSpecificOutput"]["additionalContext"]
        # the fixture provably creates the condition the covenant read discriminates on
        assert ("### Covenant" in context) == run["calibrated"], run["name"]
        assert "hooks/session_start.py" in run["opened"], run["name"]


def test_the_success_configuration_really_places_the_pass(runs):
    # axis: the fixture provably reaches the success path, so its reads are in the census union
    placed = [run for run in runs if run["pass"] == "placeable"]
    assert len(placed) == 1
    run = placed[0]
    context = json.loads(run["stdout"])["hookSpecificOutput"]["additionalContext"]
    assert "The reviewer pass is in place" in context, run["name"]
    assert (run["home"] / ".codex" / "auth.json").is_file(), run["name"]
    # the fake pass never reaches the bootstrap text
    assert _placeable_pass() not in run["stdout"] + run["stderr"]


def test_the_listed_read_set_is_what_the_real_hook_reads(runs):
    observed = set().union(*(run["opened"] for run in runs))
    unlisted, unread = _differences(observed, LISTED)
    assert not unlisted and not unread, (
        "read by the hook but not in START_HOOK_READS: %s\nin START_HOOK_READS but never read: %s"
        % (unlisted, unread))


def test_the_comparison_reports_a_difference_in_either_direction(runs):
    observed = set().union(*(run["opened"] for run in runs))
    assert _differences(observed, LISTED) == ([], [])
    # axis: a list with one stale extra entry reports it as listed but never read
    assert _differences(observed, LISTED | {"lib/cloud_check.py"}) == ([], ["lib/cloud_check.py"])
    # axis: a list missing one entry reports it as read but not listed
    dropped = sorted(LISTED)[0]
    assert _differences(observed, LISTED - {dropped}) == ([dropped], [])
    assert _differences(observed - {dropped}, LISTED) == ([], [dropped])
    assert _differences(observed | {"lib/extra.py"}, LISTED) == (["lib/extra.py"], [])


def _lib_modules():
    return {name[:-3] for name in os.listdir(_LIB)
            if name.endswith(".py") and os.path.isfile(os.path.join(_LIB, name))}


def _imported(nodes):
    names = set()
    for node in nodes:
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _top_level_import_nodes(body):
    for node in body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node
        elif isinstance(node, ast.Try):
            yield from _top_level_import_nodes(node.body)


def _parse(path):
    with open(path, encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=path)


def test_the_listed_read_set_covers_the_static_imports():
    lib = _lib_modules()
    hook_imports = _imported(ast.walk(_parse(HOOK))) & lib
    missing = sorted("lib/%s.py" % name for name in hook_imports if "lib/%s.py" % name not in LISTED)
    assert not missing, "session_start.py imports lib modules not in START_HOOK_READS: %s" % missing
    for rel in sorted(r for r in LISTED if r.startswith("lib/")):
        top = _imported(_top_level_import_nodes(_parse(os.path.join(_PLUGIN, *rel.split("/"))).body))
        absent = sorted("lib/%s.py" % name for name in top & lib if "lib/%s.py" % name not in LISTED)
        assert not absent, "%s imports at module top level, outside START_HOOK_READS: %s" % (rel, absent)
