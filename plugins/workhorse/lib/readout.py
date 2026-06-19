"""⑨ Handoff readout builder + the secret-scrub seam. Any CI-log / env-derived
content Workhorse emits passes through test-pilot's pr_comment.py `scrub` (the
band's single scrub source). If test-pilot is unresolvable, unscrubbable content
is DROPPED (fail-closed: never leak), and the readout notes the omission. Merge is
always the owner's — the readout says so.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import band_lib  # noqa: E402

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRUB = ("test-pilot", "lib", "pr_comment.py")


def scrub(text, root=None):
    """Scrub via test-pilot's pr_comment.py. Returns (scrubbed, ok). On any
    failure ok=False and the text is REPLACED with a redaction note (never raw)."""
    if not text:
        return ("", True)
    lib = band_lib.resolve_target(_SCRUB, root=root, plugin_root=_PLUGIN_ROOT)
    if lib is None:
        return ("[omitted — scrubber unavailable]", False)
    try:
        p = subprocess.run([sys.executable, lib, "scrub"], input=text,
                           capture_output=True, text=True, timeout=15)
        if p.returncode != 0:
            return ("[omitted — scrub failed]", False)
        return (p.stdout, True)
    except Exception:
        return ("[omitted — scrub error]", False)


def build_readout(ctx):
    """Assemble the plain-language 'your turn' readout from a context dict:
    pr_url, dev_url, ci_status, built_vs_acceptance, test_results, smoke (list),
    raw_ci_excerpt, root. EVERY free-text field that could carry a secret
    (built_vs_acceptance, test_results, raw_ci_excerpt — anything Workhorse
    interpolates from CI logs / env / subagent output) passes through `scrub`
    (design §3⑨: ALL PR-bound output through the secret-scrub seam, not just the
    CI excerpt). Structured fields (URLs, the CI status word, the static smoke
    list) are Workhorse-authored and not scrubbed. Merge is always the owner's."""
    ctx = ctx or {}
    root = ctx.get("root")

    def _safe(text):
        return scrub(text, root=root)[0] if text else ""

    lines = ["## Workhorse — your turn", ""]
    if ctx.get("pr_url"):
        lines.append("- **PR (yours to merge):** %s" % ctx["pr_url"])
    if ctx.get("dev_url"):
        lines.append("- **Live dev server:** %s" % ctx["dev_url"])
    lines.append("- **CI:** %s" % ctx.get("ci_status", "CI not detected"))
    if ctx.get("built_vs_acceptance"):
        lines += ["", "### Built vs. acceptance", _safe(ctx["built_vs_acceptance"])]
    if ctx.get("test_results"):
        lines += ["", "### test-pilot", _safe(ctx["test_results"])]
    smoke = ctx.get("smoke") or []
    if smoke:
        lines += ["", "### Spot-check"] + ["- [ ] %s" % s for s in smoke]
    if ctx.get("raw_ci_excerpt"):
        lines += ["", "<details><summary>CI excerpt</summary>", "",
                  _safe(ctx["raw_ci_excerpt"]), "</details>"]
    lines += ["", "_Merge is yours — Workhorse never merges._"]
    return "\n".join(lines)
