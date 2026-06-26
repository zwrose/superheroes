"""Project detectors for Workhorse — best-effort, graceful 'none found -> note
it'. No detector ever raises: a missing/garbled signal returns a structured
'none' result so the orchestrator can note it in the readout instead of crashing.
"""
import json
import os
import re

_DEV_SCRIPT_PREFERENCE = ("dev", "start", "serve", "develop")
_SAFE_NPM_SCRIPT = re.compile(r"^[A-Za-z0-9:_./-]+$")


def detect_dev_server(root, profile=None):
    """{'command': str|None, 'source': 'profile'|'package.json'|'none', 'note': str}.
    Profile override wins; else a package.json dev/start/serve script; else none."""
    if isinstance(profile, dict) and isinstance(profile.get("devCommand"), str) \
            and profile["devCommand"].strip():
        return {"command": profile["devCommand"].strip(), "source": "profile", "note": ""}
    pkg = os.path.join(root, "package.json")
    if os.path.isfile(pkg):
        try:
            with open(pkg, encoding="utf-8") as fh:
                data = json.load(fh)
        except (ValueError, OSError):
            data = None
        scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
        if not isinstance(scripts, dict):
            scripts = {}
        for name in _DEV_SCRIPT_PREFERENCE:
            if name in scripts:
                result = {"command": "npm run %s" % name, "source": "package.json",
                          "script": name, "note": ""}
                if _SAFE_NPM_SCRIPT.match(name):
                    result["argv"] = ["npm", "run", name]
                return result
    return {"command": None, "source": "none",
            "note": "no dev-server command detected — spot-check server skipped"}


def detect_ci(root):
    """{'provider': 'github-actions'|None, 'note': str}. A workflow file under
    .github/workflows is the signal; absence => 'CI not detected' (never a false ✓)."""
    wf = os.path.join(root, ".github", "workflows")
    try:
        if os.path.isdir(wf) and any(f.endswith((".yml", ".yaml")) for f in os.listdir(wf)):
            return {"provider": "github-actions", "note": ""}
    except OSError:
        pass
    return {"provider": None, "note": "CI not detected"}
