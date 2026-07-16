# plugins/superheroes/lib/manual_completion.py
"""#450 manual-completion receipt — the pure core.

When a session takes over a PARKED showrunner run and completes it BY HAND (native gate, docs
commits, PR, full review-code panel, ready-flip) outside the spine, the run record otherwise goes
permanently dark: the journal's last entry is the park, the checkpoint freezes at the parked phase
with `pr: null`, and the shipped reality (a reviewed, ready PR) is reconcilable ONLY from the
driving session's transcript. Every record-reading consumer — run_watch, token_trend, the readout,
run-quality diagnosis (#293) — then reconstructs a lie-by-omission: "parked, never resumed" when
the truth is "manually completed to PR #N".

The receipt is two durable facts: a TERMINAL journal event (`manual_completion`, payload
`{pr, headSha?, note?}`) and the checkpoint's coarse `phase` advanced to the terminal marker
(`checkpoint.SHIPPED_MANUAL`). This module is the pure transform half — no IO — so the terminal
shapes are unit-pinnable; the IO leaf that writes both is manual_completion_entry.py.

Fail-soft by design (epic #327): a missing receipt changes nothing about today's behavior; its
presence is what makes the record truthful. The resume cursor (lastGoodStep/lastGoodPhase) is left
UNTOUCHED — it is a faithful record of where the automated spine actually reached before the
hand-off, and checkpoint validation couples the pair (clearing one without the other fails closed).
"""
import re

import checkpoint as ckpt_lib

TERMINAL_PHASE = ckpt_lib.SHIPPED_MANUAL
EVENT_TYPE = "manual_completion"

# A PR number inside a github .../pull/<n> (or .../pulls/<n>) URL — matched FIRST so a trailing
# query string or fragment (?w=1, #issuecomment-9) can't shadow the real number.
_PR_PATH_RE = re.compile(r"/pulls?/(\d+)")


def build_payload(pr, head_sha=None, note=None):
    """The `manual_completion` journal payload: {pr, headSha?, note?}. `pr` is stored as-passed
    (a PR number or URL string — truthful to what the finisher recorded). Empty optionals are
    omitted rather than written as null-valued keys. NOTE: `note` is free text and MUST be
    scrubbed by the caller before it reaches this payload (the journal writes `payload` as-is)."""
    payload = {"pr": pr}
    if head_sha:
        payload["headSha"] = head_sha
    if note:
        payload["note"] = note
    return payload


def _as_number(pr):
    """The integer PR number embedded in `pr` (a bare int, a "#420", or a .../pull/420 URL),
    or None when none is derivable. Never raises. A github `/pull/<n>` path wins so a trailing
    query string or fragment (`?w=1`, `#issuecomment-9`) can't shadow the real number; a bare
    `#420` PR ref still resolves via the trailing-digit scan."""
    if isinstance(pr, bool):
        return None
    if isinstance(pr, int):
        return pr
    if not isinstance(pr, str):
        return None
    s = pr.strip()
    m = _PR_PATH_RE.search(s)
    if m:
        return int(m.group(1))
    s = s.split("?", 1)[0]                 # drop a query string (a bare "#420" ref is kept)
    digits = ""
    for ch in reversed(s.rstrip("/")):
        if ch.isdigit():
            digits = ch + digits
        elif digits:
            break
    return int(digits) if digits else None


def pr_record(pr, url=None):
    """Shape `checkpoint.pr` as the {number?, url?, isDraft} dict the record readers expect
    (run_watch._read_checkpoint reads pr.url; journal.render_brief reads pr.isDraft). A
    hand-shipped PR is ready → isDraft False. A URL passed as `pr` is adopted as the url."""
    rec = {"isDraft": False}
    number = _as_number(pr)
    if number is not None:
        rec["number"] = number
    if url:
        rec["url"] = url
    elif isinstance(pr, str) and pr.startswith("http"):
        rec["url"] = pr
    return rec


def advance_checkpoint(ckpt, pr, url=None):
    """Return a COPY of `ckpt` advanced to the terminal manual-shipped state: the coarse `phase`
    set to TERMINAL_PHASE and the shipped PR recorded. Pure — the input is not mutated. The resume
    cursor is intentionally preserved (see module docstring)."""
    out = dict(ckpt or {})
    out["phase"] = TERMINAL_PHASE
    out["pr"] = pr_record(pr, url)
    return out


def is_manually_completed(ckpt):
    """True when `ckpt` already carries the terminal manual-completion marker (idempotency key —
    a second receipt on an already-terminal checkpoint is a no-op)."""
    return isinstance(ckpt, dict) and ckpt.get("phase") == TERMINAL_PHASE
