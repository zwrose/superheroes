"""step 9 Handoff readout builder + the secret-scrub seam. Any CI-log / env-derived
content Workhorse emits passes through pr_comment.py's `scrub` (the band's single
scrub source). In the consolidated one-plugin tree pr_comment is a same-tree sibling,
so this imports it directly (no resolver, no subprocess). If scrubbing fails for ANY
reason, unscrubbable content is DROPPED (fail-closed: never leak), and the readout notes
the omission. Merge is always the owner's — the readout says so.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pr_comment  # noqa: E402  (same-tree sibling; the band's single scrub source)
import cost_report  # noqa: E402  (#130: the run-cost line renderer)


def scrub(text, root=None):
    """Scrub via pr_comment.scrub. Returns (scrubbed, ok). On any failure ok=False and the
    text is REPLACED with a redaction note (never raw). `root` is accepted for call-site
    compatibility; the in-tree scrubber needs no resolution."""
    if not text:
        return ("", True)
    try:
        return (pr_comment.scrub(text), True)
    except Exception:
        return ("[omitted — scrub error]", False)


def build_readout(ctx):
    """Assemble the plain-language 'your turn' readout from a context dict:
    pr_url, dev_url, ci_status, built_vs_acceptance, test_results, smoke (list),
    raw_ci_excerpt, root. EVERY free-text field that could carry a secret
    (built_vs_acceptance, test_results, raw_ci_excerpt — anything Workhorse
    interpolates from CI logs / env / subagent output) passes through `scrub`
    (design §3.9: ALL PR-bound output through the secret-scrub seam, not just the
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
    # #130: the run-cost footer — Workhorse-authored structured counts (not CI/env free-text), so it
    # bypasses the scrub seam. Omitted entirely when there is no cost data.
    cost_lines = cost_report.render_cost_line(ctx.get("cost"))
    if cost_lines:
        lines += [""] + cost_lines
    lines += ["", "_Merge is yours — Workhorse never merges._"]
    return "\n".join(lines)
