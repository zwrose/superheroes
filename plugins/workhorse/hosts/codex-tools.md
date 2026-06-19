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

- **Instructions file:** `AGENTS.md` (Codex) — wherever a skill says "your instructions file".
- **Plugin root:** the portable seam `ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"` resolves to `${PLUGIN_ROOT}` on Codex. Use `$ROOT_DIR` for bundled-helper paths.
- **PreToolUse hooks:** Codex honors `permissionDecision: deny` (or exit code 2 + stderr). Plugin-bundled hooks run only after you review and trust them.
- **The owner-approval gate (issue #14):** the enforcer GATES owner-authority actions
  (merge / release / deploy / force-push / push-to-default / `gh workflow run` /
  destructive) when running inside a superheroes repo. Codex honors only `deny`, so the
  gate is two-part: the hook DENIES the action and issues a one-time **nonce** (in the
  deny reason). Stop and ask the owner (escalation GATE). **With no approver (unattended /
  autonomous) → leave it denied; the loop parks here** — never self-approve. On the
  owner's explicit in-turn approval, mint a single-use 90s allowance:
  `python3 "$ROOT_DIR/lib/enforcer.py" approve --command-hash <H> --nonce <N>` (the deny
  reason carries both `<H>` and `<N>` — `approve` takes the hash, not the literal command,
  so the call doesn't itself re-trip the gate), then re-run the SAME command once. The
  next matching call consumes the allowance. Outside a superheroes repo the gate does not
  fire. The allowance is single-use, command-scoped, and wiped on compaction — a
  compacted/confused agent has no inherited approval and must re-ask.
