# Codex Tool Map

Skills in this plugin speak in host-neutral **actions**. On Codex they resolve to the tools below.

| Action the skill asks for | Codex tool |
|---|---|
| Read a file | `shell` (`cat`/`head`/`tail`) |
| Create / edit / delete a file | `apply_patch` |
| Run a shell command | `shell` |
| Search file contents / find files | `shell` (`rg`/`grep`/`find`) |
| Fetch a URL | `shell` (`curl`/`wget`) |
| Search the web | `web_search` |
| Dispatch the `<name>` subagent/reviewer | `spawn_agent`, instructing it to load and apply `agents/<name>.md`'s methodology, then return findings; collect with `wait_agent`, free with `close_agent`. Requires `multi_agent = true` in `~/.codex/config.toml`. |
| Multiple parallel dispatches | multiple `spawn_agent` calls in one turn |
| Track tasks ("todo", "mark done") | `update_plan` |
| Invoke another skill | skills load natively — follow their instructions |

## Dispatch Reliability

The `spawn_agent` path has not exhibited the Claude post-truncation dispatch derail. When a caller expects a file output, it may still verify existence and mtime before trusting the result, but do not apply the Claude fallback or reroute through `general-purpose` unless a Codex-specific failure class is observed.

- **Instructions file:** `AGENTS.md` (Codex) — wherever a skill says "your instructions file".
- **Plugin root:** the portable seam `ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"` resolves to `${PLUGIN_ROOT}` on Codex. Use `$ROOT_DIR` for bundled-helper paths.
- **PreToolUse hooks:** Codex honors `permissionDecision: deny` (or exit code 2 + stderr). Plugin-bundled hooks run only after you review and trust them.
