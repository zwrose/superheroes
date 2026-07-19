"""SSOT drift guard for the implementer contract (CONVENTIONS §11 Pattern 2).

`agents/implementer-contract.md` is the authoritative home of the implementer contract. Two
consumers carry it: `agents/implementer.md` embeds a verbatim copy under `## Your contract` so a
dispatched Claude subagent holds the contract without a runtime read (the host dispatches an agent
template as-is), and the workhorse charter inlines the same home for external-engine dispatch. This
test parses the home and the embedded section, **fails closed** if either cannot be bounded, and
asserts **byte-equality** of the two bodies — so editing, truncating, or padding either one breaks CI
unless the copy is re-synced. Byte-equality (not containment) catches an *extra* rule slipped into
the copy, which a substring check would miss.
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENTS = os.path.normpath(os.path.join(_HERE, "..", "..", "agents"))
_HOME = os.path.join(_AGENTS, "implementer-contract.md")
_TEMPLATE = os.path.join(_AGENTS, "implementer.md")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _home_body(text):
    """Everything after the leading '# ' H1 of the home, stripped. Fail-closed."""
    lines = text.split("\n")
    if not lines or not lines[0].startswith("# "):
        raise RuntimeError("implementer-contract.md: expected a leading '# ' heading")
    body = "\n".join(lines[1:]).strip()
    if not body:
        raise RuntimeError("implementer-contract.md: contract body is empty")
    return body


def _section(text, heading):
    """The body of the `## <heading>` section (up to the next '## '), stripped. Fail-closed."""
    marker = f"## {heading}"
    if marker not in text:
        raise RuntimeError(f"implementer.md: section {marker!r} not found")
    after = text.split(marker, 1)[1]
    body = after.split("\n## ", 1)[0].strip()
    if not body:
        raise RuntimeError(f"implementer.md: section {marker!r} is empty")
    return body


def test_template_embeds_the_contract_home_byte_for_byte():
    home = _home_body(_read(_HOME))
    embedded = _section(_read(_TEMPLATE), "Your contract")
    assert embedded == home, (
        "agents/implementer.md's `## Your contract` section is not byte-identical to "
        "implementer-contract.md — re-sync the embedded copy with the home."
    )
