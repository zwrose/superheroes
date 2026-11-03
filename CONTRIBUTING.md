# Contributing

Thanks for your interest in **superheroes**. This is a personal marketplace I
maintain, but it's public and contributions are genuinely welcome — bug reports,
fixes, docs, eval fixtures, and new ideas all help.

How it works: fork the repo and open a pull request whenever you'd like. As the
maintainer I'll review it, talk through any feedback, and merge it once it's ready.
`main` is protected so every change lands through a PR with passing CI — that's what
keeps the published plugins stable for everyone installing them.

## Ways to contribute

- **Report a bug or request a feature** — open an issue. Include the command you ran,
  what you expected, and what actually happened.
- **Fix or improve something** — open a PR (see below).
- **Improve a reviewer** — if you change agent methodology or the rubric, the eval
  gate has to stay green. Start with [`plugins/superheroes/eval/README.md`](plugins/superheroes/eval/README.md).

## Development setup

```bash
git clone https://github.com/<your-fork>/superheroes
cd superheroes
uv python install              # provisions the pinned Python from .python-version (needs uv)
# scripts/pinned-python runs Python under that pin with requirements-dev.txt
```

To try a plugin from your working copy, add the local checkout as a marketplace:

```
/plugin marketplace add /absolute/path/to/superheroes
/plugin install superheroes@superheroes
```

Restart Claude Code after installing, and re-install after changes.

## Before you open a PR

Run the same checks CI runs — all must pass:

```bash
scripts/pinned-python .github/scripts/validate_marketplace.py
scripts/pinned-python -m pytest plugins/superheroes/eval/tests/ -q
# and, if you touched the shared lib/ helpers:
scripts/pinned-python -m pytest plugins/superheroes/lib/tests/ -q
```

Then:

- **Use [Conventional Commits](https://www.conventionalcommits.org/)**, scoped to
  `superheroes` — e.g. `fix(superheroes): …`, `feat(superheroes): …`, `docs: …`. See
  [CLAUDE.md](CLAUDE.md) for the convention.
- **Don't bump plugin versions.** Versioning, tags, and releases are
  maintainer-owned (see [RELEASING.md](RELEASING.md)). If your change is
  user-facing, add a bullet under `## [Unreleased]` in the relevant plugin's
  `CHANGELOG.md` and I'll cut the release.
- **Keep PRs focused.** One logical change per PR is easiest to review and merge.

## PR process

1. Fork → branch → commit → push to your fork.
2. Open a PR against `main`. CI runs automatically.
   - First-time contributors: a maintainer approves the workflow run before CI
     executes (a GitHub default for public repos).
3. I'll review and work through any feedback with you. Once CI is green and we're
   happy with it, I'll merge it (squash; the branch is deleted on merge).

## Plugin structure rules

If you're adding or restructuring a plugin, a few hard rules (CI enforces the
manifest ones):

- `.claude-plugin/` contains **only** manifests — `plugin.json`, and
  `marketplace.json` at the repo root. Components live at the plugin root:
  `agents/`, `skills/`, `rubric/`, `eval/`.
- Each plugin's `plugin.json` carries its own SemVer `version`. Do **not** also set
  `version` in the marketplace entry — `plugin.json` wins silently and the
  duplicate masks it.
- A new plugin must be listed in `.claude-plugin/marketplace.json` with a `source`
  path that exists.

## Multi-host rules

Skills must work on both Claude Code and Codex. A few hard rules:

- **Speak in actions, not tool names.** A skill says "read the file" or "run the
  verify command" — not `Read` (Claude Code) or `shell` (Codex). Tool names belong in
  the per-host tool-map (`hosts/<host>-tools.md`), nowhere else. The validate_hosts.py
  neutral-language check bans four host-coupled tokens — dispatch/invocation phrasings
  that name one runtime's API rather than the action — anywhere in a `SKILL.md`:
  `subagent_type`, `the Agent tool`, `the Skill tool`, and `the Task tool`.
- **Every `SKILL.md` carries the host-map pointer line.** The boilerplate reads:
  > This skill speaks in host-neutral actions. Resolve them to your runtime's tools
  > by reading the host tool map at `${CLAUDE_PLUGIN_ROOT}/hosts/<your-host>-tools.md`
  > (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude
  > Code, `codex-tools.md` on Codex.
- **Name the plugin root with `${CLAUDE_PLUGIN_ROOT}`.** Assign it once per bash block:
  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  ```
  Then use `${ROOT_DIR}` for all bundled-helper paths. Both hosts set the variable for plugin
  hooks (Codex as a compatibility alias of `PLUGIN_ROOT`); in skill text the model resolves it
  (CONVENTIONS §7.4), and in Bash commands it does not expand — that layer is tracked in
  [#93](https://github.com/zwrose/superheroes/issues/93).
- **Both `hosts/` maps must stay byte-identical to the repo-root canonical** —
  see RELEASING.md for the release checklist.

## Writing skill text

- **Brace every shell variable.** Write `${VAR}`, never `$VAR`. zsh reads a modifier such
  as `:h` or `:r` right after an unbraced name (`$VAR:h`) and silently changes the value.
- **Plain step numbers.** The rule lives in [CONVENTIONS.md](CONVENTIONS.md), in its intro
  ("Number steps with plain digits").
- **Markdown that renders.** Put no bare `<word>` outside backticks: the renderer swallows
  it as an HTML tag, so write `` `<word>` ``. Put no paragraph inside a nested list item: it
  renders as a code block or breaks the list, so use a sub-bullet or close the list.
- **Adding a skill: the gate checklist.** CI checks these on a skill
  (`.github/scripts/validate_skills.py` and `.github/scripts/validate_hosts.py`):
  1. The frontmatter is strict YAML.
  2. A skill listed in `eval/skills/registry.json` `bodyCeilings` stays under its body line
     ceiling, and its description carries the phrases listed in its `requiredPhrases`.
  3. Every `${CLAUDE_PLUGIN_ROOT}/<path>` citation resolves, and a cited file cites no
     further file (one hop).
  4. Every `CONVENTIONS §N` citation names a real section.
  5. A `reference/*.md` file over 100 lines opens with a Contents heading.
  6. The combined description size stays below the recorded baseline,
     `combinedDescriptionChars` in `eval/skills/baseline.json`. That file also carries the
     known-red set.
  7. The host-map pointer line is present, and the neutral-language ban from
     [Multi-host rules](#multi-host-rules) holds (`validate_hosts.py`).
- **What gates an edit to an existing skill.** A body-only edit is gated by exactly those
  structural checks, plus any prose-pin test under `plugins/superheroes/lib/tests/` that
  reads the file. A description or fixture change also owes the activation re-record; see
  `eval/skills/README.md` § When to run.

## Be decent

Be respectful and assume good faith. That's the whole code of conduct.
