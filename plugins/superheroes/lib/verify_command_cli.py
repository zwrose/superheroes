# plugins/superheroes/lib/verify_command_cli.py
"""Resolve the project verify command for the whole-branch final review's code-leg gate. Calls the
review_store CLI to resolve the profile (avoiding the positional resolve(cwd, kind, root) signature),
then parses the `command:` line under the profile's `## Verify` heading (the exact format
repo_doctor.py reads). Any failure fail-opens to "none" (verify_gate treats it as skipped;
the #89 panel re-runs verify)."""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    try:
        out = subprocess.run([sys.executable, os.path.join(HERE, "review_store.py"),
                              "resolve", "--kind", "profile"],
                             capture_output=True, text=True, cwd=os.getcwd(), timeout=30)
        obj = json.loads(out.stdout or "{}")
        return obj.get("path")
    except Exception:
        return None


def _command_from_profile(path):
    if not path or not os.path.isfile(path):
        return "none"
    in_verify = False
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if s.startswith("## "):
                in_verify = (s.lower() == "## verify")
                continue
            if in_verify and s.startswith("command:"):
                val = s.split(":", 1)[1].strip()
                return val or "none"
    return "none"


if __name__ == "__main__":
    print(json.dumps({"command": _command_from_profile(_profile_path())}))
