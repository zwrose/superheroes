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
| Dispatch the `<name>` subagent/reviewer | `spawn_agent`, instructing it to load and apply `agents/<name>.md`'s methodology, then return findings; collect with `wait_agent`. |
| Multiple parallel dispatches | multiple `spawn_agent` calls in one turn |
| Track tasks ("todo", "mark done") | `update_plan` |
| Invoke another skill | skills load natively — follow their instructions |

## Dispatch surface (codex-cli 0.153.4)

Described against **codex-cli 0.153.4** — a statement of what that CLI offers, not a guarantee for later versions.

The `collaboration.*` verbs are `spawn_agent`, `send_message`, `followup_task`, `wait_agent`, `interrupt_agent`, and `list_agents`. There is **no `close_agent`**. There is **no `multi_agent` flag** in `~/.codex/config.toml`.

`spawn_agent` takes `task_name`, `message`, and optional `fork_turns`, `model`, and `reasoning_effort` — those optional parameters interact, so a caller supplying `model` or `reasoning_effort` should confirm the CLI's own fork-mode requirement before relying on the override, because a mismatched combination is rejected at dispatch rather than silently ignored. It takes **no tool-restriction and no sandbox argument** — a tool-restricted seat is **unenforced** on this host.

- **Instructions file:** `AGENTS.md` (Codex) — wherever a skill says "your instructions file".
- **Plugin root:** the portable seam `ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"` resolves to `${PLUGIN_ROOT}` on Codex. Use `$ROOT_DIR` for bundled-helper paths.
- **PreToolUse hooks:** Codex honors `permissionDecision: deny` (or exit code 2 + stderr). Plugin-bundled hooks run only after you review and trust them.
