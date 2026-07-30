"""Structural drift guards for the never-mutate / never-claim-a-run guarantee (#719).

Two field occurrences drove the guarantee this file guards: a shell-less review seat
asked to prove a claim empirically could only trace it, and a seat handed a shell
proved the same class of claim by running it. The fix is **structural** — a tool grant
plus a rule — so per CONVENTIONS §12.1 it ships the detector that would have caught the
original escape. The guarantee has two independent failure axes, and a guard that reads
only one does not bite when the other breaks:

- **the tool grant** — a seat's declared `tools:` grant, on the host where that grant is
  a real constraint. Guarded by deriving the observe-only set from the contents of
  `agents/`, so a NEW seat added with `Bash` or `Edit` fails unless its author consciously
  adds it to `EXECUTION_SEATS`. These tests pin the **declared** grant shape — worth
  pinning because it keeps the intended shape legible and makes an unintended widening
  visible, not because a grant, by itself, enforces the rule below.
- **the rule** — a review seat is **obliged** never to change the repository and never to
  claim a run it did not make; whether an empirical statement is a receipt follows from
  whether the seat actually ran it, never from the seat's kind. Guarded by pinning the
  rule inside its one home (`rubric/review-base.md`'s `## Verification rules` section)
  and asserting every pointer still resolves to it. The rule's own enforcement is the
  obligation itself plus the orchestrator's before/after probe, with bounds recorded in
  `LEDGERS.md` §3.

Every assertion **fails closed**: a renamed or deleted file, an empty or unparseable
frontmatter block, an absent `tools:` key, or a glob that matched nothing is a failure,
never a vacuous pass. An absent `tools:` key is the sharpest of those — a seat with no
`tools:` line inherits *every* tool, so "no Bash found, pass" would be exactly backwards.
"""
import os
import re

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))
REPO = os.path.abspath(os.path.join(PLUGIN, "..", ".."))

# The complete, explicit allowlist of seats that legitimately hold execution or write
# capability. Everything else found under `agents/` is, BY DERIVATION, an observe-only
# seat — so adding a new agent that holds `Bash`/`Edit` fails the guard below until its
# author consciously lands it here. Deriving the observe-only set (rather than
# hand-typing today's roster) is the whole point: a hand-typed list of today's seats
# would not bite on tomorrow's seat.
EXECUTION_SEATS = {
    # Writes the tree under a work order. Execution and write capability ARE its job:
    # it holds `Edit`, `Write` and `Bash` by definition.
    "implementer",
    # The interactive build pilot — deliberately unconstrained: it carries no `tools:`
    # key at all and so inherits every tool the host offers.
    "pilot",
    # Runs the enumerated command list the orchestrator authored. `Bash` is granted so
    # that "this needs to be run" has an honest answer; `Edit`/`Write` are withheld so
    # the seat has no ergonomic path to a code edit (not the shell one — `Bash` can
    # still redirect or run a mutating command). test_check_runner_* pins this
    # declared shape; the orchestrator's before/after tree probe (`LEDGERS.md` §3) is
    # what actually detects a mutation.
    "check-runner",
}

# The enumerated sites that point at the home rule. Deliberately a list, not a glob: each
# is a known copy-holder, and a NEW pointer must be added here (CONVENTIONS §11.2).
POINTER_FILES = [
    os.path.join("skills", "review-code", "reference", "auto-fix-loop.md"),
    os.path.join("skills", "review-code", "reference", "verification-pass.md"),
    os.path.join("skills", "workhorse", "SKILL.md"),
    os.path.join("agents", "check-runner.md"),
]

# Both byte-identical copies of the Claude host map. `validate_hosts.py` already owns
# byte-equality between them; this file asserts PRESENCE of the carve-out, which
# byte-equality alone would NOT catch if both copies lost the sentence together.
HOST_MAP_COPIES = [
    os.path.join(REPO, "hosts", "claude-tools.md"),
    os.path.join(PLUGIN, "hosts", "claude-tools.md"),
]

_TOOLS_LINE_RE = re.compile(r"^tools:\s*(.*)$", re.M)
_DISALLOWED_TOOLS_RE = re.compile(r"^disallowedTools\s*:", re.M)
# A grammatical bare tool token — no inline comment, no quoting, no YAML flow-sequence
# bracket, no other decoration. `Bash # temporary` is exactly the shape this refuses
# (item 8, #719 round 2): it is not equal to `"Bash"`, so a naive `==`/`in` check on the
# raw split token would silently pass a seat that really does hold a shell.
_TOOL_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _norm(text):
    """Collapse every whitespace run to one space.

    The strings asserted below are prose that wraps across source lines at different
    points in different files, so every containment check runs over normalized text.
    """
    return re.sub(r"\s+", " ", text)


def _read_required(path, why):
    """Read a file this guard depends on, failing loudly if it moved (edge 3).

    Never `if os.path.exists(...): ...` — a file this guard reads that has been renamed
    or deleted must FAIL here. Silently skipping is how a drift test stops guarding
    anything while still reporting green.
    """
    assert os.path.isfile(path), (
        "%s is missing or was renamed (expected: %s). This drift guard reads it at "
        "runtime; a vanished file must fail here, never silently pass." % (path, why))
    with open(path) as f:
        return f.read()


def _parse_tools(text, label):
    """Fail-closed read of a seat's `tools:` frontmatter grant.

    Returns the granted tool names as a list. Raises `AssertionError` on every shape
    that is not exactly one readable `tools:` line inside a well-formed frontmatter
    block — specifically:

    - **an absent `tools:` key** (edge 2): a seat with no `tools:` line inherits EVERY
      tool, so an absent grant is the MOST PERMISSIVE grant. Returning an empty list
      here would make the downstream `"Bash" not in tools` assertion pass vacuously on
      the single most permissive seat there is.
    - **an empty or unparseable frontmatter block** (edge 4): no opening delimiter, no
      closing delimiter, an empty block, or a `tools:` line that names nothing.
    - **a duplicated `tools:` key**: ambiguous, so refuse rather than pick one.
    - **a `disallowedTools` key present at all** (item 8, #719 round 2): that key changes
      the effective grant, and this guard models `tools:` alone — it refuses to read a
      grant it cannot fully account for rather than guessing.
    - **any parsed token that is not a bare grammatical name** (item 8, #719 round 2):
      `Bash # temporary` splits into a token that is not equal to `"Bash"`, so a
      `"Bash" not in tools` check downstream would pass while the seat really holds a
      shell — the worst shape a fail-closed guard can take. Every token must match
      `^[A-Za-z][A-Za-z0-9_]*$` or the grant is refused as unparseable.
    """
    lines = text.split("\n")
    assert lines and lines[0].strip() == "---", (
        "%s: frontmatter does not open with a `---` delimiter — an unparseable "
        "frontmatter block must fail, never pass." % label)
    block = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        block.append(line)
    else:
        raise AssertionError(
            "%s: frontmatter block is never closed by a `---` delimiter — an "
            "unparseable frontmatter block must fail, never pass." % label)
    assert [ln for ln in block if ln.strip()], (
        "%s: frontmatter block is empty — an empty frontmatter block grants nothing "
        "explicitly and so inherits everything; it must fail, never pass." % label)
    block_text = "\n".join(block)
    assert not _DISALLOWED_TOOLS_RE.search(block_text), (
        "%s: frontmatter contains a `disallowedTools` key. The effective grant is then "
        "not the `tools:` line alone, and this guard refuses to interpret a shape it "
        "does not model rather than reading a grant that may be wrong." % label)
    matches = _TOOLS_LINE_RE.findall(block_text)
    assert len(matches) == 1, (
        "%s: expected exactly one `tools:` line in the frontmatter, found %d. An "
        "ABSENT `tools:` key is the MOST PERMISSIVE grant there is — the seat inherits "
        "every tool the host offers, including `Bash` and `Edit` — so it must fail here "
        "rather than read as \"no Bash found, pass\". Give the seat an explicit `tools:` "
        "grant, or add its slug to EXECUTION_SEATS if it is deliberately unconstrained."
        % (label, len(matches)))
    tools = [t.strip() for t in matches[0].split(",") if t.strip()]
    assert tools, (
        "%s: `tools:` is present but grants nothing parseable (%r) — an unparseable "
        "grant must fail, never pass." % (label, matches[0]))
    for t in tools:
        assert _TOOL_TOKEN_RE.match(t), (
            "%s: `tools:` grant contains an ungrammatical token %r (from %r). A token "
            "carrying an inline comment, quoting, a YAML flow-sequence bracket, or any "
            "other decoration is unparseable and is refused rather than guessed — "
            "declare the tool bare (e.g. `Bash`, not `Bash # temporary`)."
            % (label, t, matches[0]))
    return tools


def _agent_slugs():
    """Every bundled seat, derived from the contents of `agents/` (edge 1)."""
    adir = os.path.join(PLUGIN, "agents")
    assert os.path.isdir(adir), (
        "%s is missing or was renamed — this guard derives the observe-only seat set "
        "from its contents and cannot pass without it." % adir)
    slugs = {fn[:-3] for fn in os.listdir(adir) if fn.endswith(".md")}
    assert slugs, (
        "%s matched no `*.md` agent files — a derivation that found nothing must not "
        "pass vacuously." % adir)
    return slugs


def _verification_rules_section():
    """The `## Verification rules` section of the rubric — the home of the never-mutate /
    never-claim-a-run rule.

    Returns the text from that heading up to the next `## ` heading, so a rule that
    drifted OUT of the section (into, say, the findings-format section) fails rather
    than passing on a file-wide substring match.
    """
    text = _read_required(
        os.path.join(PLUGIN, "rubric", "review-base.md"),
        "the single home of the never-mutate / never-claim-a-run verification rule")
    headings = [m.start() for m in re.finditer(r"^##\s+", text, re.M)]
    start = None
    for pos in headings:
        line = text[pos:text.index("\n", pos)]
        if line.startswith("## Verification rules"):
            start = pos
            break
    assert start is not None, (
        "review-base.md: no `## Verification rules` heading found. That section is the "
        "home of the never-mutate / never-claim-a-run rule; without it this guard cannot "
        "check placement.")
    later = [pos for pos in headings if pos > start]
    section = text[start:later[0] if later else len(text)]
    assert section.strip(), "review-base.md: the `## Verification rules` section is empty."
    return section


def _no_mutation_no_claim_rule():
    """Derive the never-mutate / never-claim-a-run rule's title and body from the home at
    runtime (edge 5).

    The title is NEVER retyped in this module. A contract test that restates the
    constant it guards proves nothing (CONVENTIONS §11.3): if the title were a literal
    here, renaming it in the home would leave this test green while every pointer in
    the repo dangled. So the pointer test below reads the title from here.

    Keyed on the rule's NUMBER (7), which restates none of the title. A renumber or a
    deletion therefore fails loudly — the correct fail-closed direction.
    """
    section = _verification_rules_section()
    m = re.search(r"^7\.\s+\*\*(.+?)\*\*", section, re.M)
    assert m, (
        "review-base.md: verification rule 7's bolded title line was not found inside "
        "the `## Verification rules` section. That rule is the never-mutate / "
        "never-claim-a-run rule's single home and every pointer in the repo resolves to "
        "it; if it was deleted, renumbered, or moved out of the section, this guard must "
        "fail, not pass.")
    title = m.group(1).strip()
    assert title, "review-base.md: verification rule 7 has an empty bolded title."
    rest = section[m.end():]
    nxt = re.search(r"^\d+\.\s", rest, re.M)
    return title, rest[:nxt.start()] if nxt else rest


# The observe-only ALLOWLIST (item 8, #719 round 4). A seat's granted tools must be a
# SUBSET of this small permitted set — never a two-name DENYLIST of ("Bash", "Edit"),
# which passes on everything else: `MultiEdit`/`NotebookEdit` edit files without being
# named `Edit`; an `mcp__*` shell tool is neither literal name; and sharpest of all,
# `Task` — a seat holding `Task` can dispatch a `general-purpose` child that holds
# `Bash` + `Edit` + `Write`, exactly the capability-restoration path
# `hosts/claude-tools.md`'s derail-fallback carve-out exists to close. A denylist has
# to predict every tool name that will ever exist; an allowlist only has to state the
# ones this seat needs, so a brand-new mutation- or dispatch-capable tool fails by
# default instead of passing by omission.
OBSERVE_ONLY_ALLOWED_TOOLS = {"Read", "Grep", "Glob", "Write"}


def test_observe_only_seats_grant_is_a_subset_of_the_allowlist():
    """Axis 1 — the tool grant. Every seat that is not on the small execution allowlist
    must hold ONLY tools drawn from `OBSERVE_ONLY_ALLOWED_TOOLS` (`Read`, `Grep`, `Glob`,
    `Write`) — an ALLOWLIST, not the prior two-name denylist of `("Bash", "Edit")`. That
    denylist verifiably would NOT have bitten on `MultiEdit`, `NotebookEdit`, an
    `mcp__*` shell tool, or `Task` (which can dispatch an unconstrained
    `general-purpose` child holding `Bash`+`Edit`+`Write` — exactly the
    capability-restoration path this same branch closes at `hosts/claude-tools.md`).
    The allowlist form fails a NEW mutation- or dispatch-capable tool by default instead
    of passing it by omission.

    The observe-only set is DERIVED from `agents/` (edge 1), so a future seat added with
    a disallowed tool fails here until someone consciously puts it on `EXECUTION_SEATS`.
    This test pins the **declared** grant for the seats this host constrains — it does
    not, by itself, prove a seat cannot mutate (`Bash` on an execution seat can still
    redirect or run a mutating command); the never-change-the-repository half of rule 7
    (review-base.md) is an obligation on the seat, not something this grant enforces.
    """
    slugs = _agent_slugs()
    missing = EXECUTION_SEATS - slugs
    assert not missing, (
        "EXECUTION_SEATS names seats with no file under agents/: %s. A renamed or "
        "deleted execution seat must fail here rather than silently shrink the "
        "allowlist." % sorted(missing))
    observe_only = sorted(slugs - EXECUTION_SEATS)
    assert observe_only, (
        "the derived observe-only seat set is EMPTY — every seat under agents/ is on the "
        "execution allowlist, so this guard would assert nothing. A derivation that "
        "matched nothing must not pass vacuously.")
    for slug in observe_only:
        tools = _parse_tools(
            _read_required(os.path.join(PLUGIN, "agents", slug + ".md"),
                           "an observe-only review seat"),
            slug)
        extra = sorted(set(tools) - OBSERVE_ONLY_ALLOWED_TOOLS)
        assert not extra, (
            "agents/%s.md grants %s (tools: %s) outside the observe-only ALLOWLIST %s. "
            "%s is a **bundled** review seat: a two-name denylist of (\"Bash\", "
            "\"Edit\") would miss this — `MultiEdit`/`NotebookEdit` edit files without "
            "being named `Edit`, and `Task` can dispatch an unconstrained "
            "`general-purpose` child holding `Bash`+`Edit`+`Write`. If this seat is "
            "meant to hold that capability, that is a deliberate change to the "
            "guarantee in review-base.md's verification rule 7 — add it to "
            "EXECUTION_SEATS with its reason." % (slug, extra, tools,
                                                   sorted(OBSERVE_ONLY_ALLOWED_TOOLS),
                                                   slug))


@pytest.mark.parametrize("text, match", [
    # no `tools:` key at all — the most permissive grant, must NOT read as "no Bash, pass"
    ("---\nname: x\ndescription: y\n---\nbody\n", "MOST PERMISSIVE"),
    # `tools:` declared twice — ambiguous, refuse
    ("---\nname: x\ntools: Read\ntools: Bash\n---\n", "found 2"),
    # `tools:` present but names nothing
    ("---\nname: x\ntools:   \n---\n", "grants nothing parseable"),
    # frontmatter never closed
    ("---\nname: x\ntools: Read\n", "never closed"),
    # no opening delimiter
    ("name: x\ntools: Read\n", "does not open"),
    # empty frontmatter block
    ("---\n\n---\nbody\n", "block is empty"),
    # inline comment decorates a token — `"Bash # temporary" != "Bash"`, so a naive
    # `"Bash" not in tools` check would pass while the seat really holds a shell (item 8)
    ("---\nname: x\ntools: Read, Bash # temporary\n---\n", "ungrammatical"),
    # `disallowedTools` present — the effective grant is no longer `tools:` alone (item 8)
    ("---\nname: x\ntools: Read\ndisallowedTools: Bash\n---\n", "disallowedTools"),
])
def test_tools_parser_fails_closed(text, match):
    """The frontmatter reader must RAISE on every shape that is not exactly one readable
    `tools:` grant (edges 2 and 4), including a decorated token or a `disallowedTools`
    key that changes the effective grant (item 8, #719 round 2) — otherwise the
    `not in tools` assertions above pass vacuously on precisely the seats that are least
    constrained.
    """
    with pytest.raises(AssertionError, match=match):
        _parse_tools(text, "<test>")


def test_check_runner_grant_is_the_constrained_shape():
    """`check-runner` is the seat that exists so "this needs to be run" has an honest
    answer, so it holds `Bash`; `Edit` and `Write` are withheld. That withheld grant
    removes only the **ergonomic** path to a code edit — `Bash` can still redirect or
    run a mutating command, so this does not itself prevent mutation. This test pins
    the seat's **declared** shape; the orchestrator's before/after tree probe
    (`LEDGERS.md` §3) is the actual detection. Asserted on the PARSED grant, not a
    substring of the file: the prose body mentions all three tool names.
    """
    tools = _parse_tools(
        _read_required(os.path.join(PLUGIN, "agents", "check-runner.md"),
                       "the check-runner execution seat"),
        "check-runner")
    assert "Bash" in tools, (
        "agents/check-runner.md no longer grants `Bash` (tools: %s). The seat exists to "
        "RUN the orchestrator's enumerated command list; without a shell it cannot, and "
        "the honest answer to \"this needs to be run\" is gone." % tools)
    for withheld in ("Edit", "Write"):
        assert withheld not in tools, (
            "agents/check-runner.md grants `%s` (tools: %s). It is withheld on purpose: "
            "it removes the ergonomic path to a code edit (not the shell one — `Bash` "
            "can still redirect or run a mutating command), and the withheld grant is "
            "what makes the declared constraint legible in the seat's own frontmatter; "
            "the orchestrator's before/after tree probe (`LEDGERS.md` §3) is what "
            "actually detects a mutation."
            % (withheld, tools))


# `check-runner`'s own ALLOWLIST (item 5, #719 round 5) — the same allowlist-not-denylist
# reasoning as `OBSERVE_ONLY_ALLOWED_TOOLS` above: a two-name denylist of ("Edit", "Write")
# would pass `Task` (a route to an unconstrained `general-purpose` child — this module
# names it above as the sharpest omission), `MultiEdit`, or `NotebookEdit` in silence,
# because none of those tokens equals `"Edit"` or `"Write"`. `check-runner` is exempt from
# `OBSERVE_ONLY_ALLOWED_TOOLS` (it is on `EXECUTION_SEATS`), so without its own allowlist
# nothing bounds what else its grant could hold.
CHECK_RUNNER_ALLOWED_TOOLS = {"Read", "Grep", "Glob", "Bash"}


def test_check_runner_grant_is_a_subset_of_its_own_allowlist():
    """`check-runner`'s granted tools must be a SUBSET of `CHECK_RUNNER_ALLOWED_TOOLS`
    (`Read`, `Grep`, `Glob`, `Bash`) — an ALLOWLIST, not a denylist of `("Edit", "Write")`.
    That denylist would not bite on `Task`, `MultiEdit`, or `NotebookEdit`: none of those
    tokens equals `"Edit"` or `"Write"`, so a seat holding any of them would pass a denylist
    check while gaining exactly the capability-restoration or edit path the withheld grant
    exists to keep out. The allowlist form fails a new token by name instead of passing it
    by omission.
    """
    tools = _parse_tools(
        _read_required(os.path.join(PLUGIN, "agents", "check-runner.md"),
                       "the check-runner execution seat"),
        "check-runner")
    assert "Bash" in tools, (
        "agents/check-runner.md no longer grants `Bash` (tools: %s). The seat exists to "
        "RUN the orchestrator's enumerated command list; without a shell it cannot." % tools)
    extra = sorted(set(tools) - CHECK_RUNNER_ALLOWED_TOOLS)
    assert not extra, (
        "agents/check-runner.md grants %s (tools: %s) outside its own ALLOWLIST %s. A "
        "denylist of (\"Edit\", \"Write\") would miss this — `Task` can dispatch an "
        "unconstrained `general-purpose` child holding `Bash`+`Edit`+`Write`, and "
        "`MultiEdit`/`NotebookEdit` edit files without being named `Edit`. If this seat is "
        "meant to hold that capability, that is a deliberate change to its declared shape "
        "— widen CHECK_RUNNER_ALLOWED_TOOLS with the reason." % (
            extra, tools, sorted(CHECK_RUNNER_ALLOWED_TOOLS)))


# The receipt envelope's magic string. Both homes must agree on the literal token that
# ties an output file to a command; this is a CONVENTIONS §11.2 copy-plus-drift TOKEN
# pin, not a prose-semantics pin — it does not assert the two homes describe the
# envelope identically (they may word it differently), only that the literal marker
# both sides key on is present in both places.
RAN_MARKER_TOKEN = "# ran: "


def test_ran_marker_token_present_in_both_homes():
    """The `# ran: ` receipt-envelope token is defined in TWO places — the producer
    (`agents/check-runner.md`, which prefixes each stdout capture's first line with it)
    and the consumer (`skills/workhorse/SKILL.md` §8 item 3, which reads that first
    line back) — with no drift test before this one, so the two could disagree on the
    literal marker while CI stayed green.

    This is a TOKEN pin (CONVENTIONS §11.2's copy-plus-drift pattern), not a pin on the
    surrounding protocol prose: it asserts only that the exact string `'# ran: '`
    occurs in both files, which is the magic string both sides must agree on to tie an
    output file to a command. It does not assert anything about how each file
    describes the envelope around that token.
    """
    for rel in (os.path.join("agents", "check-runner.md"),
                os.path.join("skills", "workhorse", "SKILL.md")):
        text = _read_required(os.path.join(PLUGIN, rel),
                              "one of the two `# ran: ` receipt-envelope token homes")
        assert RAN_MARKER_TOKEN in text, (
            "%s no longer contains the literal receipt-envelope token %r. The producer "
            "(check-runner.md) and consumer (workhorse SKILL.md §8 item 3) must agree "
            "on this exact marker or an output file can no longer be tied to a command."
            % (rel, RAN_MARKER_TOKEN))


# How close the literal token and its positional anchor must sit to count as the SAME
# clause (item 6, #719 round 5), measured on today's text: the two are ~70-90 normalized
# characters apart in both homes. 250 is generous enough to survive a modest rewording of
# the sentence between them, while still being far narrower than "anywhere in the file" —
# a stray, unrelated occurrence of either string elsewhere in a multi-thousand-character
# file will not fall inside it by coincidence.
RAN_MARKER_ANCHOR_WINDOW = 250


def test_ran_marker_token_is_paired_with_its_first_line_anchor():
    """Strengthens `test_ran_marker_token_present_in_both_homes` (item 6, #719 round 5).

    That test's plain substring check would still pass a mutant that renamed the
    producer's OPERATIVE prefix (say, to `# executed: `) while the literal string
    `'# ran: '` kept sitting somewhere in unrelated explanatory prose, and the consumer
    kept expecting `'# ran: '` — producer and consumer would disagree on the marker that
    actually ties an output file to a command, yet the file-wide presence check would
    stay green.

    Checked before writing this: in BOTH homes today, the literal token and the phrase
    "first line" sit inside the SAME sentence describing the marker's placement
    (check-runner.md: "The first line of each stdout capture is the command you
    actually ran... prefixed `# ran: `"; SKILL.md: "Each stdout capture opens with a
    `# ran: <command>` line... read the first line of the capture"). That is a genuine,
    non-vacuous pairing to require — not a coincidence of an unrelated "first line"
    landing near an unrelated "# ran: " by chance in a much larger file.
    """
    for rel in (os.path.join("agents", "check-runner.md"),
                os.path.join("skills", "workhorse", "SKILL.md")):
        text = _norm(_read_required(
            os.path.join(PLUGIN, rel),
            "one of the two `# ran: ` receipt-envelope token homes"))
        occurrences = [m.start() for m in re.finditer(re.escape(RAN_MARKER_TOKEN), text)]
        assert occurrences, (
            "%s: the literal token %r is gone (test_ran_marker_token_present_in_both_homes "
            "already asserts this; this test cannot pair what is not there)."
            % (rel, RAN_MARKER_TOKEN))
        paired = any(
            "first line" in text[max(0, i - RAN_MARKER_ANCHOR_WINDOW):
                                   i + RAN_MARKER_ANCHOR_WINDOW]
            for i in occurrences
        )
        assert paired, (
            "%s: no occurrence of the literal token %r sits within %d characters of the "
            "phrase 'first line'. Both homes state that phrase as the positional anchor "
            "for the SAME receipt clause the token belongs to; a token that drifted into "
            "unrelated prose (while the producer's real operative prefix silently "
            "changed) would pass the plain presence check but not this pairing."
            % (rel, RAN_MARKER_TOKEN, RAN_MARKER_ANCHOR_WINDOW))


def test_no_mutation_no_claim_rule_lives_in_review_base_verification_rules():
    """Axis 2 — the rule. The never-mutate / never-claim-a-run rule has ONE home:
    verification rule 7 of `rubric/review-base.md`, inside its `## Verification rules`
    section. Assert it sits there and that its two load-bearing clauses survive, so a
    rewrite that keeps the title but drops the substance fails.
    """
    title, body = _no_mutation_no_claim_rule()
    nbody = _norm(body)
    # Clause 1: a review seat's execution-flavoured statements are analysis, not receipts.
    assert "is **analysis, not a receipt**" in nbody, (
        "review-base.md rule 7 (%r) no longer says a review seat's mutation/test/parity "
        "statement is **analysis, not a receipt**. That clause is the rule's whole "
        "point: without it the rule reads as a capability note rather than a ban on "
        "answering in the register of a receipt." % title)
    # Clause 2: a finding whose proof needs a run is STILL emitted, with the check named.
    assert ("**still emit the finding**: name the **check** — the exact command, "
            "mutation, or input that would settle it") in nbody, (
        "review-base.md rule 7 (%r) no longer says a finding whose proof requires "
        "execution is STILL emitted with the check named. Dropping that clause turns "
        "the rule into a reason to stay silent, which the rule itself calls worse than "
        "either failure it forbids." % title)


@pytest.mark.parametrize("rel", POINTER_FILES)
def test_pointer_resolves_to_the_home_rule(rel):
    """Every pointer at the never-mutate / never-claim-a-run rule must resolve to the
    home, keyed on the title DERIVED from `review-base.md` at runtime (edge 5) — never
    on a literal retyped here, which would let a title change pass green while the
    pointers dangled.

    This is the CONVENTIONS §11.2 copy-plus-drift-test pattern: each pointer keeps its
    own restatement (not a bare cross-reference) because a dispatched seat's prompt
    must be self-contained — the seat never reads `review-base.md` at dispatch time —
    and this test is the drift guard that reads the home at runtime and fails the four
    copies out of sync with it, per §11.3.

    What this guards: the rule's **title**, derived from the home at runtime, must
    appear in all four pointers — so a rename in the home reddens every stale pointer.

    What this does NOT guard (disclosed, not silently dropped — WO7, #719): each
    pointer also carries its own **restatement** of the rule's substance (the
    never-mutate half), and nothing here checks those restatements against the home. A
    pointer could drop its never-mutate clause while keeping the title and CI would
    stay green. A prior round (WO6) added a windowed `mutat`-stem assertion meant to
    pin exactly that gap; it was inert, because the home's own title reads "A review
    seat never mutates, and never claims a run it did not make" — the title itself
    contains `mutates`, so any assertion anchored on the title's own occurrence is
    pre-satisfied by the anchor before it ever reaches the pointer's real restatement.
    Anchor and payload were not disjoint. The durable fix is a **design** change — one
    shared fragment every dispatcher inlines, so there is literally one copy to drift —
    rather than a stronger substring; that is handed to the advisor as a follow-up, not
    attempted here.

    The same gap applies on the **home** side, not just the pointers (WO8, #719): a
    second `mutat`-stem assertion against the home body (removed here) was equally
    inert, because every `mutat` occurrence in the home is either inside the title
    (already covered above) or inside the already-asserted still-emit clause, so it
    could never fail on its own. Nothing in this file pins the home's never-mutate
    prohibition independently of those two already-genuine clauses; that gap ships
    disclosed, not silently dropped, alongside the pointer gap above.
    """
    title, _ = _no_mutation_no_claim_rule()
    ntitle = _norm(title)
    text = _norm(_read_required(os.path.join(PLUGIN, rel),
                                "a pointer at the never-mutate / never-claim-a-run "
                                "verification rule"))
    assert "base rubric" in text.lower(), (
        "%s no longer names the **base rubric** as the authoritative home of the "
        "never-mutate / never-claim-a-run rule. A pointer that does not name its home "
        "is a second copy." % rel)
    assert ntitle in text, (
        "%s no longer quotes the home rule's title %r (read from review-base.md at "
        "runtime). This pointer cites the rule by name, so a rename in the home "
        "leaves it dangling." % (rel, title))


@pytest.mark.parametrize("path", HOST_MAP_COPIES)
def test_host_map_carries_the_capability_constrained_carve_out(path):
    """The derail fallback re-dispatches a seat as `general-purpose` with its frontmatter
    STRIPPED — which restores every tool and would silently void a withheld `Edit`/`Write`.
    Both copies of the Claude host map must carry the carve-out that forbids it.

    Byte-equality between the two copies is `validate_hosts.py`'s job and is not
    duplicated here. This asserts PRESENCE, which byte-equality alone would not catch if
    both copies lost the sentence together.
    """
    text = _norm(_read_required(path, "a copy of the Claude host tool map"))
    assert ("**Never apply this fallback to a capability-constrained seat** — one whose "
            "`tools:` frontmatter deliberately withholds a capability (for example a "
            "seat granted `Bash` but not `Edit`/`Write`).") in text, (
        "%s no longer carries the capability-constrained carve-out on the derail "
        "fallback. Without it, the fallback's frontmatter-stripping re-dispatch hands a "
        "deliberately shell-only or write-less seat every tool back." % path)
    assert ("Stripping the frontmatter restores every tool and silently voids the "
            "constraint the seat exists to carry.") in text, (
        "%s no longer states WHY the carve-out exists (frontmatter-stripping restores "
        "every tool). The mechanism is the load-bearing half — without it the carve-out "
        "reads as an arbitrary prohibition." % path)


def test_workhorse_charter_names_check_runner_in_both_enumerations():
    """`check-runner` is a dispatch kind, so the Workhorse charter must name it in BOTH
    enumerations that must cover every dispatch: the gated model-check list (a dispatch
    kind absent there dispatches with no validated model) and the dispatch-provenance
    list (a dispatch kind absent there ships with no provenance row the advisor can vet).

    Each assertion is scoped to the enumeration itself, not to the file: a file-wide
    substring search would pass on any of the charter's other mentions of the seat.
    """
    text = _norm(_read_required(
        os.path.join(PLUGIN, "skills", "workhorse", "SKILL.md"),
        "the Workhorse charter"))

    gate = re.findall(
        r"dispatch kinds this charter sanctions(.*?)you \*\*run the model gate\*\*", text)
    assert len(gate) == 1, (
        "workhorse/SKILL.md: expected exactly one gated-model-check dispatch-kind "
        "enumeration ('… dispatch kinds this charter sanctions … you **run the model "
        "gate**'), found %d. A reworded or duplicated enumeration must fail here, not "
        "pass unread." % len(gate))
    assert "`check-runner` dispatch" in gate[0], (
        "workhorse/SKILL.md: the gated model-check dispatch-kind enumeration does not "
        "name a `check-runner` dispatch: %r. A dispatch kind missing from that list "
        "dispatches without its model validated against the registry allowlist."
        % gate[0])

    prov = re.findall(r"each dispatch \((.*?)\)", text)
    assert len(prov) == 1, (
        "workhorse/SKILL.md: expected exactly one dispatch-provenance enumeration "
        "('each dispatch (…)'), found %d. A reworded or duplicated enumeration must "
        "fail here, not pass unread." % len(prov))
    assert "`check-runner`" in prov[0], (
        "workhorse/SKILL.md: the dispatch-provenance enumeration does not name "
        "`check-runner`: %r. A dispatch kind missing from that list ships with no "
        "provenance row recording the engine + model it ran on." % prov[0])


def _tree_probe_paragraph():
    """The Workhorse charter's before/after tree-probe paragraph (item 10, #719 round 2).

    `check-runner` deliberately holds `Bash`, so this paragraph — the orchestrator's
    committed-baseline `git rev-parse HEAD` / `git status --porcelain` / reflog-count
    capture, before and after every `check-runner` dispatch — is the control that
    detects a shell-based mutation. No test read it before this one. Located by a
    stable anchor (the paragraph's opening bold clause) up to the next `## ` heading, so
    the assertions below are scoped to the paragraph itself, not a file-wide substring
    search that would pass on unrelated text elsewhere in the charter.
    """
    text = _read_required(
        os.path.join(PLUGIN, "skills", "workhorse", "SKILL.md"),
        "the Workhorse charter, home of the before/after tree-probe paragraph")
    anchor = "**Probe the tree before and after every `check-runner` dispatch"
    start = text.find(anchor)
    assert start != -1, (
        "workhorse/SKILL.md: the before/after tree-probe paragraph's opening anchor "
        "(%r) was not found. `check-runner` deliberately holds `Bash`, and this "
        "paragraph is the control that detects a shell-based mutation; a guard that "
        "cannot locate it protects nothing." % anchor)
    heading = re.search(r"\n##\s+", text[start:])
    assert heading is not None, (
        "workhorse/SKILL.md: no `## ` heading found after the tree-probe paragraph's "
        "anchor — cannot bound the paragraph's end.")
    return text[start:start + heading.start()]


def test_workhorse_tree_probe_paragraph_carries_its_load_bearing_elements():
    """`check-runner` deliberately holds `Bash`, so the Workhorse charter's before/after
    repository probe is the control that detects a shell-based mutation. No test read it
    before this one (item 10, #719 round 2): deleting that paragraph, changing
    `--porcelain` to `-uno`, or dropping the INDETERMINATE rule would leave every other
    test in this file green while materially weakening the guarantee this branch ships.
    Scoped to the paragraph itself via `_tree_probe_paragraph` (a stable anchor to the
    next `## ` heading), not the whole charter — a file-wide substring search would pass
    on unrelated text.
    """
    raw = _tree_probe_paragraph()
    para = _norm(raw)

    assert "Commit the landed work first so the baseline is clean" in para, (
        "the tree-probe paragraph no longer states the committed-baseline requirement "
        "— the probe must be taken over a COMMITTED tree, never a dirty one, or a prior "
        "order's uncommitted work is exactly what the probe would misattribute.")

    for cmd in ("git rev-parse HEAD", "git status --porcelain",
                "git reflog --date=iso HEAD | wc -l"):
        assert cmd in para, (
            "the tree-probe paragraph no longer names `%s` as one of the three "
            "before/after signals it captures." % cmd)

    # The paragraph's own prose correctly NAMES `-uno` to reject it — "(**not** `-uno`:
    # a run's untracked output is exactly what you want to see)" — so a blanket ban on
    # the substring "-uno" anywhere in the paragraph would redden against that correct,
    # intentional explanation. The actual weakening the Test seat named is the git-status
    # INVOCATION itself switching to `-uno`, so that is what this asserts against,
    # scoped to the invocation rather than the whole paragraph's prose.
    assert "git status --porcelain" in para
    assert "git status -uno" not in para and "git status --porcelain -uno" not in para, (
        "the tree-probe paragraph's git-status INVOCATION now uses `-uno` — the "
        "specific weakening the Test seat named: `-uno` hides untracked output, which "
        "is exactly what a shell-based mutation (a planted file, a probe left behind) "
        "would produce.")
    assert ("git status --untracked-files=no" not in para
            and "git status --porcelain --untracked-files=no" not in para), (
        "the tree-probe paragraph's git-status INVOCATION now uses the long form "
        "`--untracked-files=no` — the same weakening as `-uno` (edge 6, #719 round 4): "
        "it hides untracked output, which is exactly what a shell-based mutation (a "
        "planted file, a probe left behind) would produce. (The paragraph's own "
        "explanatory aside naming `--untracked-files=no` as the excluded long form is "
        "fine — this check only rejects the INVOCATION, mirroring the `-uno` check "
        "above.)")

    assert "failed verification" in para, (
        "the tree-probe paragraph no longer says a delta is a FAILED VERIFICATION — "
        "without it a detected mutation could be read as a mere warning rather than a "
        "failure.")

    assert "INDETERMINATE" in para, (
        "the tree-probe paragraph no longer says a timed-out or unjoined dispatch is "
        "INDETERMINATE — without it such a dispatch could be misread as clean.")
