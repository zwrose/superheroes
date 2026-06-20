#!/usr/bin/env python3
"""Dual-host (Claude + Codex) marketplace/manifest validator + neutral-language lint.

Checks (all stdlib): both marketplaces parse; every plugin has both manifests with
agreeing identity; Codex source paths resolve INSIDE plugins/<name>/ (containment);
required Codex manifest fields; the neutral-language lint over skills; and that each
plugin's hosts/<host>-tools.md is byte-identical to the repo-root canonical.
"""
import argparse, json, os, re, sys

# Ensure the scripts directory is in sys.path so validate_marketplace can be imported.
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from validate_marketplace import SEMVER

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PLUGINS = os.path.join(REPO, "plugins")
SEAM = '${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}'
POINTER_RE = re.compile(r"hosts/<your-host>-tools\.md|hosts/.*-tools\.md")
BANNED = ("subagent_type", "the Agent tool", "the Skill tool", "the Task tool")

def lint_skill(text):
    """Return a list of lint violations for one SKILL.md body."""
    errs = []
    if "hosts/" not in text or not POINTER_RE.search(text):
        errs.append("missing host-map pointer line")
    for tok in BANNED:
        if tok in text:
            errs.append(f"banned host-coupled token in prose: {tok!r}")
    # bare ${CLAUDE_PLUGIN_ROOT} that is NOT part of the portable seam
    for m in re.finditer(r"\$\{CLAUDE_PLUGIN_ROOT(:-\$\{PLUGIN_ROOT\})?\}", text):
        if m.group(1) is None:
            errs.append("bare ${CLAUDE_PLUGIN_ROOT} — use the portable seam " + SEAM)
    return errs

def _load(path, errors):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        errors.append(f"{path}: {e}")
        return None

def _plugins_from_claude(errors):
    mp = _load(os.path.join(REPO, ".claude-plugin", "marketplace.json"), errors) or {}
    out = {}
    for e in mp.get("plugins", []):
        name = e.get("name")
        man = _load(os.path.join(PLUGINS, name, ".claude-plugin", "plugin.json"), errors) if name else None
        if man:
            out[name] = man
    return mp.get("name"), out

def _validate_codex(claude_name, claude_plugins, errors):
    mp = _load(os.path.join(REPO, ".agents", "plugins", "marketplace.json"), errors)
    if not mp:
        return
    if mp.get("name") != claude_name:
        errors.append(f"codex marketplace name {mp.get('name')!r} != claude {claude_name!r}")
    if not isinstance(mp.get("plugins"), list) or not mp["plugins"]:
        errors.append("codex marketplace has no plugins[]")
        return
    seen = set()
    for e in mp["plugins"]:
        name = e.get("name")
        if not name:
            errors.append("codex marketplace entry missing name")
            continue
        seen.add(name)
        if "version" in e:
            errors.append(f"{name}: codex marketplace entry must not carry version")
        src = (e.get("source") or {}).get("path") or (e.get("source") or {}).get("url")
        resolved = os.path.abspath(os.path.join(REPO, src)) if src else ""
        want = os.path.join(PLUGINS, name)
        if not (resolved == want or resolved.startswith(want + os.sep)):
            errors.append(f"{name}: codex source {src!r} not contained in plugins/{name}/")
        man = _load(os.path.join(PLUGINS, name, ".codex-plugin", "plugin.json"), errors)
        if not man:
            continue
        for field in ("skills", "interface"):
            if field not in man:
                errors.append(f"{name}: .codex-plugin missing {field!r}")
        if not SEMVER.match(str(man.get("version", ""))):
            errors.append(f"{name}: codex version not SemVer")
        cl = claude_plugins.get(name, {})
        for field in ("name", "version", "author"):
            if man.get(field) != cl.get(field):
                errors.append(f"{name}: codex {field} drifts from claude")
        if not man.get("description"):
            errors.append(f"{name}: codex description empty")
        hooks_dir = os.path.join(PLUGINS, name, "hooks")
        if os.path.isdir(hooks_dir) and "hooks" not in man:
            errors.append(f"{name}: plugin hooks but .codex-plugin has no hooks pointer")
    for name in claude_plugins:
        if name not in seen:
            errors.append(f"{name}: present in claude marketplace, absent from codex")

def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()

def _read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()

def lint_reference_files(plugins_root, plugin_names):
    """Lint skill reference files for host coupling. The host-map pointer line is a
    SKILL.md-only requirement, so it is excluded for reference files."""
    out = []
    for name in plugin_names:
        for root, _, files in os.walk(os.path.join(plugins_root, name)):
            if "reference" not in root.split(os.sep):
                continue
            for f in files:
                if f.endswith(".md"):
                    fp = os.path.join(root, f)
                    for v in lint_skill(_read(fp)):
                        if "host-map pointer" not in v:
                            out.append(f"{fp}: {v}")
    return out

def _validate_maps_and_skills(plugins, errors):
    for host in ("claude", "codex"):
        canon = os.path.join(REPO, "hosts", f"{host}-tools.md")
        canon_bytes = _read_bytes(canon) if os.path.isfile(canon) else None
        if canon_bytes is None:
            errors.append(f"missing canonical hosts/{host}-tools.md")
        for name in plugins:
            p = os.path.join(PLUGINS, name, "hosts", f"{host}-tools.md")
            if not os.path.isfile(p):
                errors.append(f"{name}: missing hosts/{host}-tools.md"); continue
            if canon_bytes is not None and _read_bytes(p) != canon_bytes:
                errors.append(f"{name}: hosts/{host}-tools.md drifts from canonical")
    for name in plugins:
        for root, _, files in os.walk(os.path.join(PLUGINS, name, "skills")):
            for f in files:
                if f == "SKILL.md":
                    fp = os.path.join(root, f)
                    for v in lint_skill(_read(fp)):
                        errors.append(f"{fp}: {v}")
    errors.extend(lint_reference_files(PLUGINS, list(plugins)))

def main(argv=None):
    argparse.ArgumentParser(description="dual-host validator").parse_args(argv or [])
    errors = []
    cname, cplugins = _plugins_from_claude(errors)
    _validate_codex(cname, cplugins, errors)
    _validate_maps_and_skills(cplugins, errors)
    for e in errors:
        sys.stderr.write("error: " + e + "\n")
    if errors:
        return 1
    print("✓ dual-host manifests, tool maps, and skill language valid")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
