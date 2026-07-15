import os, re
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def _read(p):
    return open(os.path.join(ROOT, p), encoding="utf-8").read()


def test_interactive_doc_legs_cap_at_three():
    for skill in ("plugins/superheroes/skills/review-plan/SKILL.md",
                  "plugins/superheroes/skills/review-tasks/SKILL.md"):
        text = _read(skill)
        assert "--max-rounds 3" in text, f"{skill} must cap the doc loop at 3"
        assert "--max-rounds 7" not in text, f"{skill} must not keep the old 7-round cap"


def test_native_doc_panel_caps_at_three():
    text = _read("plugins/superheroes/lib/showrunner.js")
    # showrunner.js has TWO `reviewPanel({ ... })` call sites: `runReviewCodePanel`'s (earlier
    # in the file, no `docMode` key at all — every doc_mode/docMode gate defaults false) and
    # `runReviewDocPanel`'s (the one this test pins). An un-scoped `re.search` starts at the
    # FIRST occurrence (the code leg's) and, since `.*?` is dot-all (re.S) and there is no
    # `docMode: true` before it closes, the lazy scan crosses straight through that call's own
    # closing `})` looking for the next "docMode: true" — landing on the doc leg's, many lines
    # later, and matching the entire wrongly-scoped span between the two calls (the assertion
    # below would then pass even if the CODE leg's `maxRounds` were wrong, since `maxRounds: 3`
    # only needs to appear somewhere in that oversized span). Anchor the search to
    # `runReviewDocPanel`'s own body first so the regex can only match ITS `reviewPanel` call.
    fn_start = text.index("async function runReviewDocPanel")
    body = text[fn_start:]
    # `docMode: true` sits INSIDE the nested `legKind: { ... }` object literal, one brace level
    # below `reviewPanel({ ... })` itself (see Task 9's edit) — a `[^}]*?` scanner can never
    # cross that inner closing `}` to reach the call's own closing `})`, so it must be `.*?`
    # (dot-all via re.S, already passed) rather than a `}`-excluding class.
    m = re.search(r"reviewPanel\(\{.*?docMode:\s*true.*?\}\s*\)", body, re.S)
    # the docMode reviewPanel call carries maxRounds: 3
    assert m and "maxRounds: 3" in m.group(0)
