// The one parser of the checkpoint block a session ends its reply with
// (`skills/checkpoint/SKILL.md` step 4). Pure: no `claude-code` import.

/** The one definition of the checkpoint fence's info string; tests import it, and the skill cites this file. */
export const CHECKPOINT_INFO = 'superheroes-checkpoint'

/**
 * The one definition of the mod-presence signal: the mod exports this variable
 * to the session's Bash children with the session's own id as its value. A
 * checkpoint skill that reads back its own session id knows the mod runs in
 * THIS session and will save the reply's block; anything else (unset, or an id
 * inherited from another session's child, e.g. a dispatched Codex child) means
 * no mod here. The mod's `$.env.set` needs a literal name, so register.ts spells it and
 * register.test.ts pins that literal to this constant; the skill cites this file.
 */
export const COMPACT_MOD_ENV = 'SUPERHEROES_COMPACT_MOD'
// CommonMark: a fence is three or more backticks (info string without a backtick)
// or three or more tildes; it closes only on the same character, at least as long.
const OPEN = /^ {0,3}(?:(`{3,})([^`]*)|(~{3,})(.*))$/
const CLOSE_TICKS = /^ {0,3}(`{3,})[ \t]*$/
const CLOSE_TILDES = /^ {0,3}(~{3,})[ \t]*$/

/**
 * The body of the last fenced block whose info string is exactly
 * `superheroes-checkpoint`, without its fences and without the one trailing
 * newline; null when there is none, the last one is never closed, or its body
 * is empty. The checkpoint fence is three or more backticks and closes on a
 * line of at least as many; any other fence (backtick or tilde) is walked past
 * whole, so a checkpoint fence quoted inside it is not a block.
 */
export function extractCheckpointBlock(text: string): string | null {
  const lines = text.split(/\r?\n/)
  let last: { body: string[]; isClosed: boolean } | null = null

  for (let i = 0; i < lines.length; i += 1) {
    const open = OPEN.exec(lines[i] ?? '')
    if (open === null) {
      continue
    }

    const isTilde = open[3] !== undefined
    const width = (open[1] ?? open[3] ?? '').length
    const info = (isTilde ? open[4] : open[2]) ?? ''
    const closer = isTilde ? CLOSE_TILDES : CLOSE_TICKS
    const body: string[] = []
    let isClosed = false

    for (i += 1; i < lines.length; i += 1) {
      const line = lines[i] ?? ''
      const close = closer.exec(line)
      if (close !== null && (close[1] ?? '').length >= width) {
        isClosed = true
        break
      }
      body.push(line)
    }

    if (!isTilde && info.trim() === CHECKPOINT_INFO) {
      last = { body, isClosed }
    }
  }

  if (last === null || !last.isClosed) {
    return null
  }

  const body = last.body.join('\n')

  return body.trim() === '' ? null : body
}
