"""Structural drift guards for the no-shell-verification guarantee (#719).

Two field occurrences drove the guarantee this file guards: a shell-less review seat
asked to prove a claim empirically could only trace it, and a seat handed a shell
proved the same class of claim by running it. The fix is **structural** — a tool grant
plus a rule — so per CONVENTIONS §12.1 it ships the detector that would have caught the
original escape. The guarantee has two independent failure axes, and a guard that reads
only one does not bite when the other breaks:

- **the tool grant** — a review seat that acquires `Bash` (or `Edit`) silently becomes
  able to do the thing the rule forbids. Guarded by deriving the observe-only set from
  the contents of `agents/`, so a NEW seat added with a shell fails unless its author
  consciously adds it to `EXECUTION_SEATS`.
- **the rule** — the prose that tells a seat its statements are analysis, not receipts.
  Guarded by pinning the rule inside its one home (`rubric/review-base.md`'s
  `## Verification rules` section) and asserting every pointer still resolves to it.

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
    # the seat cannot mutate the tree it runs over (test_check_runner_* pins that shape).
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
    matches = _TOOLS_LINE_RE.findall("\n".join(block))
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
    """The `## Verification rules` section of the rubric — the home of the no-shell rule.

    Returns the text from that heading up to the next `## ` heading, so a rule that
    drifted OUT of the section (into, say, the findings-format section) fails rather
    than passing on a file-wide substring match.
    """
    text = _read_required(
        os.path.join(PLUGIN, "rubric", "review-base.md"),
        "the single home of the no-shell verification rule")
    headings = [m.start() for m in re.finditer(r"^##\s+", text, re.M)]
    start = None
    for pos in headings:
        line = text[pos:text.index("\n", pos)]
        if line.startswith("## Verification rules"):
            start = pos
            break
    assert start is not None, (
        "review-base.md: no `## Verification rules` heading found. That section is the "
        "home of the no-shell rule; without it this guard cannot check placement.")
    later = [pos for pos in headings if pos > start]
    section = text[start:later[0] if later else len(text)]
    assert section.strip(), "review-base.md: the `## Verification rules` section is empty."
    return section


def _no_shell_rule():
    """Derive the no-shell rule's title and body from the home at runtime (edge 5).

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
        "the `## Verification rules` section. That rule is the no-shell rule's single "
        "home and every pointer in the repo resolves to it; if it was deleted, "
        "renumbered, or moved out of the section, this guard must fail, not pass.")
    title = m.group(1).strip()
    assert title, "review-base.md: verification rule 7 has an empty bolded title."
    rest = section[m.end():]
    nxt = re.search(r"^\d+\.\s", rest, re.M)
    return title, rest[:nxt.start()] if nxt else rest


def test_observe_only_seats_hold_no_shell_and_cannot_edit():
    """Axis 1 — the tool grant. Every seat that is not on the small execution allowlist
    must explicitly grant neither `Bash` nor `Edit`.

    The observe-only set is DERIVED from `agents/` (edge 1), so a future seat added with
    a shell fails here until someone consciously puts it on the allowlist. `Write` is
    deliberately NOT forbidden: the review seats write their findings JSON.
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
        for forbidden in ("Bash", "Edit"):
            assert forbidden not in tools, (
                "agents/%s.md grants `%s` (tools: %s). %s is an observe-only seat: its "
                "mutation, test and parity statements are analysis, not receipts, which "
                "only holds while it cannot run or edit anything. If this seat is meant "
                "to hold execution capability, that is a deliberate change to the "
                "guarantee in review-base.md's verification rule 7 — add it to "
                "EXECUTION_SEATS with its reason." % (slug, forbidden, tools, slug))


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
])
def test_tools_parser_fails_closed(text, match):
    """The frontmatter reader must RAISE on every shape that is not exactly one readable
    `tools:` grant (edges 2 and 4) — otherwise the `not in tools` assertions above pass
    vacuously on precisely the seats that are least constrained.
    """
    with pytest.raises(AssertionError, match=match):
        _parse_tools(text, "<test>")


def test_check_runner_grant_is_the_constrained_shape():
    """`check-runner` is the seat that exists so "this needs to be run" has an honest
    answer, so it holds `Bash` — but it must not be able to mutate the tree it runs
    over, so `Edit` and `Write` are both withheld. Asserted on the PARSED grant, not a
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
            "the seat runs commands over a tree it must not mutate, and the withheld "
            "grant is what makes that constraint legible in the seat's own frontmatter."
            % (withheld, tools))


def test_no_shell_rule_lives_in_review_base_verification_rules():
    """Axis 2 — the rule. The no-shell rule has ONE home: verification rule 7 of
    `rubric/review-base.md`, inside its `## Verification rules` section. Assert it sits
    there and that its two load-bearing clauses survive, so a rewrite that keeps the
    title but drops the substance fails.
    """
    title, body = _no_shell_rule()
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
    """Every pointer at the no-shell rule must resolve to the home, keyed on the title
    DERIVED from `review-base.md` at runtime (edge 5) — never on a literal retyped here,
    which would let a title change pass green while the pointers dangled.

    One uniform tier, applied to all four pointers: each names the base rubric as the
    authoritative home (the floor assertion) AND quotes the home's title verbatim
    (whitespace-normalized). The title is read from `review-base.md` at runtime, so a
    rename in the home fails every pointer here rather than passing green.
    """
    title, _ = _no_shell_rule()
    ntitle = _norm(title)
    text = _norm(_read_required(os.path.join(PLUGIN, rel),
                                "a pointer at the no-shell verification rule"))
    assert "base rubric" in text.lower(), (
        "%s no longer names the **base rubric** as the authoritative home of the "
        "no-shell rule. A pointer that does not name its home is a second copy." % rel)
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
