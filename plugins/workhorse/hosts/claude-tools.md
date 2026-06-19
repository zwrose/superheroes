# Claude Code Tool Map

Skills in this plugin speak in host-neutral **actions**. On Claude Code they resolve to the tools below.

| Action the skill asks for | Claude Code tool |
|---|---|
| Read a file | `Read` |
| Create / edit / delete a file | `Write` / `Edit` |
| Run a shell command | `Bash` |
| Search file contents / find files | `Grep` / `Glob` |
| Fetch a URL | `WebFetch` |
| Search the web | `WebSearch` |
| Dispatch the `<name>` subagent/reviewer | the `Agent` tool with `subagent_type: <plugin>:<name>` (the bundled agent in `agents/<name>.md`) |
| Multiple parallel dispatches | multiple `Agent` calls in one message |
| Track tasks ("todo", "mark done") | `TodoWrite` |
| Invoke another skill | the `Skill` tool |

- **Instructions file:** `CLAUDE.md` (Claude Code).
- **Plugin root:** the portable seam `ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"` resolves to `${CLAUDE_PLUGIN_ROOT}` on Claude. Use `$ROOT_DIR` for bundled-helper paths.
- **PreToolUse hooks:** declared in `hooks/hooks.json`; deny via `hookSpecificOutput.permissionDecision: deny`.
- **The owner-approval gate (issue #14):** the enforcer GATES owner-authority actions
  (merge / release / deploy / force-push / push-to-default / `gh workflow run` /
  destructive) when running inside a superheroes repo. On Claude Code the hook emits
  `permissionDecision: ask` — a native live prompt the owner answers (the agent cannot
  answer it itself). On the owner's in-turn approval the action proceeds; with no owner
  (unattended) the prompt is denied and the loop parks. Outside a superheroes repo the
  gate does not fire. No allowance/`approve` dance is needed here — `ask` is the gate.
