"""The mod's real argv (hooks/mod/argv.ts) through the real lib/compaction_directive.py CLI (#1814).

The mod tests (hooks/mod/register.test.ts) stub `process.run`; this is the seam they leave: the argv
the mod actually builds is compiled with `tsc`, printed by `node`, and executed against the real CLI
under an isolated config dir. An argv the CLI would reject (an extra flag, a renamed verb) fails here.
A missing `tsc` or `node` FAILS the test (never skips): CI installs both, and a skip would make this
receipt vacuous.
"""
import json
import os
import shutil
import subprocess
import sys

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ARGV_TS = os.path.join(_PLUGIN_ROOT, "hooks", "mod", "argv.ts")
_HOOK = os.path.join(_PLUGIN_ROOT, "hooks", "compaction_context.py")

SID = "sess-argv_1"
NOTES = "## Checkpoint notes\nMode: workhorse\nWO4 in flight\n"
OWNER = "keep the PR number"


def _tool(name):
    found = shutil.which(name)
    if found is None:
        raise AssertionError("%s is required to compile and run the mod's argv and is not on PATH" % name)
    return found


def _mod_argvs(tmp_path, transcript):
    tsc, node = _tool("tsc"), _tool("node")
    out = tmp_path / "js"
    built = subprocess.run(
        [tsc, "--outDir", str(out), "--module", "es2022", "--target", "es2022", "--strict", _ARGV_TS],
        capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    (out / "package.json").write_text('{"type": "module"}', encoding="utf-8")
    (out / "run.mjs").write_text(
        "import { instructionsArgv, markArgv, saveArgv } from './argv.js'\n"
        "const [root, sid, transcript, owner] = process.argv.slice(2)\n"
        "console.log(JSON.stringify({\n"
        "  instructions: instructionsArgv(root, sid, transcript, owner),\n"
        "  mark: markArgv(root, sid),\n"
        "  save: saveArgv(root, sid),\n"
        "}))\n", encoding="utf-8")
    r = subprocess.run([node, str(out / "run.mjs"), _PLUGIN_ROOT, SID, str(transcript), OWNER],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _exec(argv, env, cwd, stdin=None):
    # the mod's own argv, verbatim; only the interpreter name is pinned to the one running the suite
    r = subprocess.run([sys.executable] + argv[1:], env=env, input=stdin, capture_output=True,
                       text=True, timeout=30, cwd=cwd)
    return r.returncode, (json.loads(r.stdout) if r.stdout.strip() else None), r.stderr


def test_mod_argv_runs_through_the_real_cli_into_the_summarizer_text_and_the_marker_handoff(tmp_path):
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps({
        "type": "user", "isSidechain": False,
        "message": {"role": "user", "content": (
            "<command-message>superheroes:workhorse</command-message>\n"
            "<command-name>/superheroes:workhorse</command-name>")},
    }) + "\n", encoding="utf-8")
    argvs = _mod_argvs(tmp_path, transcript)
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path),
           "CLAUDE_CONFIG_DIR": str(tmp_path / "cfg")}
    cwd = str(tmp_path)

    code, saved, err = _exec(argvs["save"], env, cwd, stdin=NOTES)
    assert code == 0 and saved["ok"] is True, err

    code, out, err = _exec(argvs["instructions"], env, cwd)
    assert code == 0 and out["ok"] is True, err
    assert out["mode"] == "workhorse" and out["notesFound"] is True
    assert "WO4 in flight" in out["instructions"]
    assert OWNER in out["instructions"]
    assert "Issue number being built" in out["instructions"]  # the workhorse charter directive
    assert not os.path.exists(out["markerPath"])  # nothing is marked before `mark` runs

    code, marked, err = _exec(argvs["mark"], env, cwd)
    assert code == 0 and marked["path"] == out["markerPath"], err
    assert os.path.exists(out["markerPath"])

    # the PreCompact fallback consumes the marker the mod's `mark` published and prints nothing
    hook = subprocess.run([sys.executable, "-B", _HOOK], env=env, input=json.dumps({"session_id": SID}),
                          capture_output=True, text=True, timeout=30, cwd=cwd)
    assert hook.returncode == 0 and hook.stdout == ""
    assert not os.path.exists(out["markerPath"])
