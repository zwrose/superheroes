// The superheroes mod (#1814 layer 1): steers every compaction with the
// session's charter directive plus its checkpoint notes, and saves the
// checkpoint block a reply ends with. Every hook here fails open — on any error
// the event goes on unchanged (`next(e)` once), no delivered-marker is written,
// and the PreCompact command hook steers in its place.

import type { EngineInterface, Register } from 'claude-code'

import { instructionsArgv, markArgv, parseVocabulary, saveArgv } from './argv'
import type { CliVocabulary } from './argv'
import { extractCheckpointBlock } from './checkpoint-block'

const CLI_TIMEOUT_MS = 15000

const transcriptPath = { plugin: 'superheroes', key: 'transcriptPath' } as const

const note = ($: EngineInterface, text: string): void => {
  try {
    $.ui.log(`superheroes mod: ${text}`, { to: 'debug' })
  } catch {
    // a log line is never worth failing a hook over
  }
}

// Runs one argv built by ./argv (the one home of the CLI's command lines); resolves
// its JSON object only for exit 0 with `ok: true`, otherwise rejects.
async function directive(
  $: EngineInterface,
  argv: readonly string[],
  stdin?: string,
): Promise<Record<string, unknown>> {
  const verb = argv[3] ?? '?'
  const { exitCode, stdout } = await $.process.run(
    argv,
    stdin === undefined ? { timeoutMs: CLI_TIMEOUT_MS } : { timeoutMs: CLI_TIMEOUT_MS, stdin },
  )

  if (exitCode !== 0) {
    throw new Error(`${verb} exited ${exitCode}: ${stdout.slice(0, 200)}`)
  }

  const res: unknown = JSON.parse(stdout)

  if (typeof res !== 'object' || res === null || (res as { ok?: unknown }).ok !== true) {
    throw new Error(`${verb} answered not ok: ${stdout.slice(0, 200)}`)
  }

  return res as Record<string, unknown>
}

// The CLI's vocabulary, read from the file the CLI's own parser is built from. Read per
// hook call; a missing or malformed file throws, which each caller fails open on.
const vocabulary = async ($: EngineInterface): Promise<CliVocabulary> =>
  parseVocabulary(await $.fs.read(`${$.plugin.root}/lib/compaction_cli.json`))

const text = (value: unknown): string | null =>
  typeof value === 'string' && value !== '' ? value : null

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    try {
      // The one definition of the mod-presence signal: the mod exports this variable
      // to the session's Bash children with the session's own id as its value. The
      // checkpoint skill reads it back: its own id means the mod runs in THIS
      // session and saves the reply's block; unset or another id means no mod here.
      // `$.env.set` needs a literal name, so this call is the one home; the skill cites it.
      await $.env.set('SUPERHEROES_COMPACT_MOD', await $.session.id())
    } catch (error) {
      note($, `session.start: ${String(error)}`)
    }

    return next(e)
  }).catch(($, e, next) => next(e))

  on('classic.SessionStart', async ($, e, next) => {
    try {
      await $.state.set(transcriptPath, text(e.transcript_path))
    } catch (error) {
      note($, `classic.SessionStart: ${String(error)}`)
    }

    return next(e)
  }).catch(($, e, next) => next(e))

  on('session.compact', async ($, e, next) => {
    let steered = e

    // A subagent's own compaction is not the session's: leave it untouched.
    if (!e.agentId) {
      try {
        const sessionId = await $.session.id()
        const { value: known } = await $.state.get(transcriptPath)
        const transcript = text(known)
        const owner = e.instructions?.trim() ? e.instructions : null

        const cli = await vocabulary($)
        const res = await directive(
          $,
          instructionsArgv(cli, $.plugin.root, sessionId, transcript, owner),
        )
        const instructions = text(res.instructions)
        const markerPath = text(res.markerPath)

        if (instructions === null || markerPath === null) {
          throw new Error('instructions answer lacks instructions or markerPath')
        }

        // Keep the instructions whatever the marker's acknowledgement does: a mark
        // that published the marker and then died before answering would leave
        // PreCompact deferring to a delivery that never reached the summarizer.
        steered = { ...e, instructions }

        // The CLI publishes the marker atomically (temp file + rename): a failed
        // write leaves no marker, so the PreCompact fallback steers as well.
        await directive($, markArgv(cli, $.plugin.root, sessionId))
      } catch (error) {
        note($, `session.compact: ${String(error)}`)
      }
    }

    return next(steered)
  }).catch(($, e, next) => next(e))

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)

    // A subagent's answer is not the session's: its checkpoint block must never
    // replace the parent's notes (`$.session.id()` is the parent's there too).
    if (!e.agentId) {
      try {
        const block = extractCheckpointBlock(e.answer)

        if (block !== null) {
          try {
            // The CLI replaces the notes atomically (temp file + rename): a failed
            // save leaves the last good notes in place.
            const cli = await vocabulary($)

            await directive($, saveArgv(cli, $.plugin.root, await $.session.id()), block)
            $.ui.toast('Checkpoint notes saved')
          } catch (error) {
            // The skill was told not to write the file (the presence signal is set),
            // so a failed save must reach the owner; the answer itself goes on unchanged.
            note($, `turn.complete: ${String(error)}`)
            $.ui.toast('Checkpoint notes NOT saved: the previous notes are still in place')
          }
        }
      } catch (error) {
        note($, `turn.complete: ${String(error)}`)
      }
    }

    return result
  }).catch(($, e, next) => next(e))
}
