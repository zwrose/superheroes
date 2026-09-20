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

# Fields exempt from scrubbing at the readout egress. Every other interpolated value
# passes through `_readout_egress` and is scrubbed by default.
_READOUT_SCRUB_EXEMPT = frozenset({
    "courierRetries.retried",  # Python int rendered with %d; cannot carry a string.
})


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


def _readout_egress(field, value, root=None):
    """axis: scrub-by-default — an unlisted field is scrubbed, so a new field cannot leak by omission."""
    if field in _READOUT_SCRUB_EXEMPT:
        return value
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    if not text:
        return ""
    return scrub(text, root=root)[0]


def build_readout(ctx):
    """Assemble the plain-language 'your turn' readout from a context dict:
    pr_url, dev_url, ci_status, built_vs_acceptance, test_results, smoke (list),
    raw_ci_excerpt, root. Every value interpolated into a line passes through
    `_readout_egress` and is scrubbed by default. The only exempt field is
    `courierRetries.retried` (an integer count rendered with %d). Merge is always
    the owner's."""
    ctx = ctx or {}
    root = ctx.get("root")

    def _egress(field, value):
        return _readout_egress(field, value, root=root)

    lines = ["## Workhorse — your turn", ""]
    if ctx.get("pr_url"):
        lines.append("- **PR (yours to merge):** %s" % _egress("pr_url", ctx["pr_url"]))
    if ctx.get("dev_url"):
        lines.append("- **Live dev server:** %s" % _egress("dev_url", ctx["dev_url"]))
    lines.append("- **CI:** %s" % _egress("ci_status", ctx.get("ci_status", "CI not detected")))
    retries = ctx.get("courierRetries")
    if isinstance(retries, dict) and isinstance(retries.get("retried"), int) and retries["retried"] > 0:
        lines.append("- **Couriers:** %d retried (dispatches that needed more than one attempt)"
                     % _egress("courierRetries.retried", retries["retried"]))
    if ctx.get("built_vs_acceptance"):
        lines += ["", "### Built vs. acceptance", _egress("built_vs_acceptance", ctx["built_vs_acceptance"])]
    if ctx.get("test_results"):
        lines += ["", "### test-pilot", _egress("test_results", ctx["test_results"])]
    smoke = ctx.get("smoke") or []
    if smoke:
        lines += ["", "### Spot-check"] + ["- [ ] %s" % _egress("smoke[]", s) for s in smoke]
    denials = ctx.get("permissionDenials") or []
    if denials:
        lines += ["", "### Permission denials (15-min timeout)"]
        for d in denials:
            if not isinstance(d, dict):
                continue
            step = _egress("permissionDenials[].step", d.get("step") or "unknown step")
            detail = d.get("detail")
            detail_text = _egress("permissionDenials[].detail",
                                  detail if isinstance(detail, str) else (str(detail) if detail else ""))
            lines.append("- **%s**%s" % (step, (": " + detail_text) if detail_text else ""))
    if ctx.get("raw_ci_excerpt"):
        lines += ["", "<details><summary>CI excerpt</summary>", "",
                  _egress("raw_ci_excerpt", ctx["raw_ci_excerpt"]), "</details>"]
    lines += ["", "_Merge is yours — Workhorse never merges._"]
    return "\n".join(lines)
