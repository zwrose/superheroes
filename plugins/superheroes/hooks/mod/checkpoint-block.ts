// The one parser of the checkpoint block a session ends its reply with
// (`skills/checkpoint/SKILL.md` step 4). Pure: no `claude-code` import.

const INFO = 'superheroes-checkpoint'
const OPEN = /^ {0,3}(`{3,})([^`]*)$/
const CLOSE = /^ {0,3}(`{3,})[ \t]*$/

/**
 * The body of the last fenced block whose info string is exactly
 * `superheroes-checkpoint`, without its fences and without the one trailing
 * newline; null when there is none, the last one is never closed, or its body
 * is empty. The fence is three or more backticks and closes on a line of at
 * least as many; any other fence is walked past whole, so a checkpoint fence
 * quoted inside it is not a block.
 */
export function extractCheckpointBlock(text: string): string | null {
  const lines = text.split(/\r?\n/)
  let last: { body: string[]; isClosed: boolean } | null = null

  for (let i = 0; i < lines.length; i += 1) {
    const open = OPEN.exec(lines[i])
    if (open === null) {
      continue
    }

    const width = open[1].length
    const body: string[] = []
    let isClosed = false

    for (i += 1; i < lines.length; i += 1) {
      const close = CLOSE.exec(lines[i])
      if (close !== null && close[1].length >= width) {
        isClosed = true
        break
      }
      body.push(lines[i])
    }

    if (open[2].trim() === INFO) {
      last = { body, isClosed }
    }
  }

  if (last === null || !last.isClosed) {
    return null
  }

  const body = last.body.join('\n')

  return body.trim() === '' ? null : body
}
