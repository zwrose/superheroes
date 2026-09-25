# WO-C (#1425) bite-proof — the retargeted detectors, C15 layer 3

Declared guarded-element set (exactly five, per the order): **E1**
`.github/scripts/validate_hosts.py` `POINTER_RE`, axis: every `SKILL.md` carries the rooted
pointer `${CLAUDE_PLUGIN_ROOT}/hosts/<your-host>-tools.md`. **E2** same `POINTER_RE`, axis: the
retired fallback form no longer satisfies the check. **E3** `.github/scripts/validate_skills.py`
`_REF` in `check_links`, axis: a rooted citation in a skill doc must resolve. **E4** same `_REF`
in `check_depth`, axis: a reference doc cited from a skill must not itself cite another file.
**E5** `plugins/superheroes/lib/tests/skill_surface.py` `_REF`, axis: reference files a SKILL.md
links are included in the surface the consuming tests read.

**Probes ran at `29a621e4`** (C15 layer 3's last commit at order time), in a **detached** worktree
at `.../scratchpad/probe-bp` created with `git worktree add --detach ... 29a621e4`. Every
mutation, red run, restore, and green run below happened only in that probe tree; the BUILD
worktree received only the two deliverables (this record and the three axis-line comments) —
no probe mutation landed there.

**Redaction and elision:** nothing needed redaction — no capture carries secrets, tokens, or
private URLs. One elision, applied throughout: the probe tree's absolute path is shortened to
`.../scratchpad/probe-bp` or `/private/tmp/.../probe-bp` (the elided part is the fixed session
scratchpad prefix under `/private/tmp/claude-501/`, about 150 characters, identical in every
occurrence), and in the E5 list output the repeated `.../reference/` directory prefix is shortened
the same way. Every other character of each command and capture is as run.

**Command form** (`/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-bp <cmd>`,
run from the probe-bp root) is referred to below as *the command*.

---

## E1 — `POINTER_RE`, axis: a SKILL.md carries the rooted host-map pointer

**guarded element:** `.github/scripts/validate_hosts.py:25` (`POINTER_RE`)

**neutralization** (`plugins/superheroes/skills/checkpoint/SKILL.md`, probe tree):
```
This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.
```
→
```
This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `hosts/tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.
```

**command:** the command `.github/scripts/validate_hosts.py`.

**raw red:**
```
error: /private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-1425-e1490399b9821494/ac70d891-8ab8-498a-8fe7-19eb9f64bdfd/scratchpad/probe-bp/plugins/superheroes/skills/checkpoint/SKILL.md: missing host-map pointer line
EXIT:1
```
Decisive line contains exactly `checkpoint/SKILL.md: missing host-map pointer line` — matches
the order's named red token.

**restore:** inverse Edit, putting the original pointer sentence back verbatim.

**restore receipt** (`git status --porcelain`, probe-bp): empty (clean).

**raw green:**
```
✓ dual-host manifests, tool maps, and skill language valid
EXIT:0
```

---

## E2 — `POINTER_RE`, axis: the retired fallback form no longer satisfies the check

**guarded element:** `.github/scripts/validate_hosts.py:25` (`POINTER_RE`)

**neutralization** (same file, probe tree):
```
...reading the host tool map at `${CLAUDE_PLUGIN_ROOT}/hosts/<your-host>-tools.md` (the leading variable...
```
→
```
...reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable...
```

**command:** the command `.github/scripts/validate_hosts.py`.

**raw red:**
```
error: /private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-1425-e1490399b9821494/ac70d891-8ab8-498a-8fe7-19eb9f64bdfd/scratchpad/probe-bp/plugins/superheroes/skills/checkpoint/SKILL.md: missing host-map pointer line
EXIT:1
```
Same token as E1 — the retired fallback form does not satisfy `POINTER_RE` either.

**restore:** inverse Edit, putting `${CLAUDE_PLUGIN_ROOT}/hosts/<your-host>-tools.md` back.

**restore receipt** (`git status --porcelain`, probe-bp): empty (clean).

**raw green:**
```
✓ dual-host manifests, tool maps, and skill language valid
EXIT:0
```

---

## E3 — `_REF` in `check_links`, axis: a rooted citation must resolve

**guarded element:** `.github/scripts/validate_skills.py:33` (`_REF`, consumed by `check_links` at line 42)

**neutralization** (`plugins/superheroes/skills/checkpoint/SKILL.md`, probe tree) — appended line:
```
See `${CLAUDE_PLUGIN_ROOT}/rubric/bite-proof-gone.md`.
```
(inserted after the "Common mistakes" table's last row, `rubric/bite-proof-gone.md` does not exist)

**command:** the command `.github/scripts/validate_skills.py`.

**raw red:**
```
✗ 1 skill problem(s):
  - reference-link: superheroes/checkpoint: unresolved reference rubric/bite-proof-gone.md
EXIT:1
```
Output contains exactly `unresolved reference rubric/bite-proof-gone.md` — matches the order's
named red token.

**restore:** inverse Edit, deleting the appended line.

**restore receipt** (`git status --porcelain`, probe-bp): empty (clean).

**raw green:**
```
✓ skills meet token-shape rules
EXIT:0
```

---

## E4 — `_REF` in `check_depth`, axis: a cited reference doc must not itself cite another file

**guarded element:** `.github/scripts/validate_skills.py:33` (`_REF`, consumed by `check_depth` at line 245)

**selection grep** (probe-bp, confirming the chosen reference file is cited via the rooted form
and currently cites no `${CLAUDE_PLUGIN_ROOT}/` path itself):
```
$ grep -n 'reference/spec-content.md' plugins/superheroes/skills/architect-spec/SKILL.md
20:`${CLAUDE_PLUGIN_ROOT}/skills/architect-spec/reference/spec-content.md`.

$ grep -q '\${CLAUDE_PLUGIN_ROOT}/' plugins/superheroes/skills/architect-spec/reference/spec-content.md ; echo $?
1
```
(exit `1` = no match — `spec-content.md` cites no `${CLAUDE_PLUGIN_ROOT}/` path before neutralization)

**neutralization** (`plugins/superheroes/skills/architect-spec/reference/spec-content.md`, probe tree) — appended after the file's last line:
```
elsewhere. For the log's entry format, see the `## Amendments` section of the spec template
(`templates/spec.md`) — and stop there.
```
→
```
elsewhere. For the log's entry format, see the `## Amendments` section of the spec template
(`templates/spec.md`) — and stop there.

See `${CLAUDE_PLUGIN_ROOT}/rubric/review-base.md`.
```

**command:** the command `.github/scripts/validate_skills.py`.

**raw red:**
```
✗ 2 skill problem(s):
  - reference-depth: superheroes/architect-spec: skills/architect-spec/reference/spec-content.md itself references another file (chain deeper than one hop)
  - reference-depth: superheroes/showrunner: skills/architect-spec/reference/spec-content.md itself references another file (chain deeper than one hop)
EXIT:1
```
Output contains `reference-depth:` naming `skills/architect-spec/reference/spec-content.md` —
matches the order's named condition. (`spec-content.md` is linked by both `architect-spec` and
`showrunner`, so `check_depth` flags the chain-deeper-than-one-hop violation once per consuming
skill — both entries name the same file.)

**restore:** inverse Edit, deleting the appended `See ...` line.

**restore receipt** (`git status --porcelain`, probe-bp): empty (clean).

**raw green:**
```
✓ skills meet token-shape rules
EXIT:0
```

---

## E5 — `skill_surface.py` `_REF`, axis: a linked reference file is included in the consumer surface

**guarded element:** `plugins/superheroes/lib/tests/skill_surface.py:8` (`_REF`)

**`linked_reference_files('review-code')` at head** (probe-bp, unmutated):
```
$ /usr/bin/python3 -B -c "
import sys
sys.path.insert(0, 'plugins/superheroes/lib/tests')
from skill_surface import linked_reference_files
print(linked_reference_files('review-code'))
"
['/private/tmp/.../probe-bp/plugins/superheroes/skills/review-code/reference/auto-fix-loop.md', '.../headless-presentation.md', '.../round-driver.md', '.../setup.md', '.../verification-pass.md']
```
Non-empty — includes `reference/setup.md`.

**chosen test:** `plugins/superheroes/lib/tests/test_verification_pass_wired.py::test_skill_resolves_the_verifier_tier_not_the_session_model`
— its assertion (`re.search(r"^[ \t]*VERIFIER_MODEL=[^\n]*--role[ \t]+verifier", text, re.MULTILINE)`)
needs the `VERIFIER_MODEL=$(python3 -B "$MT" --role verifier ...)` assignment line, which lives
only in `reference/setup.md` (confirmed: `grep -n "VERIFIER_MODEL=" plugins/superheroes/skills/review-code/SKILL.md plugins/superheroes/skills/review-code/reference/*.md` shows the assignment only in `reference/setup.md:86`, never in `SKILL.md` itself).

**neutralization** (`plugins/superheroes/skills/review-code/SKILL.md`, probe tree) — both
occurrences of the citation (line 45 and line 55) changed identically, `replace_all`:
```
`${CLAUDE_PLUGIN_ROOT}/skills/review-code/reference/setup.md`
```
→
```
`$ROOT_DIR/skills/review-code/reference/setup.md`
```

**command:** `cd probe-bp && /usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-bp -m pytest plugins/superheroes/lib/tests/test_verification_pass_wired.py::test_skill_resolves_the_verifier_tier_not_the_session_model -q` (selected by full node id, never `-k`).

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_skill_resolves_the_verifier_tier_not_the_session_model __________

    def test_skill_resolves_the_verifier_tier_not_the_session_model():
        text = surface_text("review-code")
        # Model resolved via the verifier tier (--role verifier), not the session model.
>       assert re.search(
            r"^[ \t]*VERIFIER_MODEL=[^\n]*--role[ \t]+verifier",
            text,
            re.MULTILINE,
        ), (
            "surface must assign VERIFIER_MODEL via --role verifier"
        )
E       AssertionError: surface must assign VERIFIER_MODEL via --role verifier
E       assert None
E        +  where None = <function search at 0x100af7e50>('^[ \\t]*VERIFIER_MODEL=[^\\n]*--role[ \\t]+verifier', '---\nname: review-code\ndescription: Use when reviewing code changes on a local branch or an open pull request before...n fallback is recorded in the\n  seat-map receipt, so a downgraded composition is visible at vet time, never silent.\n', re.MULTILINE)
E        +    where <function search at 0x100af7e50> = re.search
E        +    and   re.MULTILINE = re.MULTILINE

/private/tmp/.../probe-bp/plugins/superheroes/lib/tests/test_verification_pass_wired.py:47: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_verification_pass_wired.py::test_skill_resolves_the_verifier_tier_not_the_session_model
1 failed in 0.76s
```
Fails with the assertion naming the missing text (`VERIFIER_MODEL` assigned via `--role verifier`)
— the surface's rendered text (visible in the traceback) carries only `SKILL.md`'s own body, not
`reference/setup.md`'s content.

**restore:** inverse Edit (`replace_all`), putting `${CLAUDE_PLUGIN_ROOT}/skills/review-code/reference/setup.md` back at both sites.

**restore receipt** (`git status --porcelain`, probe-bp): empty (clean).

**raw green:**
```
.                                                                        [100%]
1 passed in 0.54s
```

---

## Restore receipt (whole run)

Every element's individual restore receipt above (`git status --porcelain` immediately after
the inverse Edit, before the green run) was empty — the probe tree was clean before every green
run, with no residue at any point across all five elements.

## Axis lines shipped (build worktree)

- `.github/scripts/validate_hosts.py`, immediately above `POINTER_RE`:
  `# Bites on: a SKILL.md whose rooted host-map pointer is absent or in the retired fallback form.`
- `.github/scripts/validate_skills.py`, immediately above `_REF = re.compile(`:
  `# Bites on: a ${CLAUDE_PLUGIN_ROOT}/<path> citation that does not resolve, or a cited reference that cites another file.`
- `plugins/superheroes/lib/tests/skill_surface.py`, immediately above `_REF = re.compile(`:
  `# Bites on: a SKILL.md reference link in the ${CLAUDE_PLUGIN_ROOT}/skills/<s>/reference/<f>.md form (other forms are not collected).`
