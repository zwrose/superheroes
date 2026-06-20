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
python3 -m pip install --upgrade pytest   # the only test dependency
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
python3 .github/scripts/validate_marketplace.py
python3 -m pytest plugins/superheroes/eval/tests/ -q
# and, if you touched the shared lib/ helpers:
python3 -m pytest plugins/superheroes/lib/tests/ -q
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
  > by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md`
  > (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude
  > Code, `codex-tools.md` on Codex.
- **Use the portable root seam.** Assign it once per bash block:
  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  ```
  Then use `$ROOT_DIR` for all bundled-helper paths. Never write a bare
  `${CLAUDE_PLUGIN_ROOT}` — it breaks on Codex. The validator fails on bare usage.
- **Both `hosts/` maps must stay byte-identical to the repo-root canonical** —
  see RELEASING.md for the release checklist.

## Be decent

Be respectful and assume good faith. That's the whole code of conduct.
