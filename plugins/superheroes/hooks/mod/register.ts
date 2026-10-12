// The superheroes mod (#1814 layer 1): steers every compaction with the
// session's charter directive plus its checkpoint notes, and saves the
// checkpoint block a reply ends with. Every hook here fails open — on any error
// the event goes on unchanged (`next(e)` once), no delivered-marker is written,
// and the PreCompact command hook steers in its place.

import type { EngineInterface, Register } from 'claude-code'

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

// Runs one verb of lib/compaction_directive.py; resolves its JSON object only
// for exit 0 with `ok: true`, otherwise rejects.
async function directive(
  $: EngineInterface,
  verb: string,
  args: readonly string[],
): Promise<Record<string, unknown>> {
  const argv = ['python3', '-B', `${$.plugin.root}/lib/compaction_directive.py`, verb, ...args]
  const { exitCode, stdout } = await $.process.run(argv, { timeoutMs: CLI_TIMEOUT_MS })

  if (exitCode !== 0) {
    throw new Error(`${verb} exited ${exitCode}: ${stdout.slice(0, 200)}`)
  }

  const res: unknown = JSON.parse(stdout)

  if (typeof res !== 'object' || res === null || (res as { ok?: unknown }).ok !== true) {
    throw new Error(`${verb} answered not ok: ${stdout.slice(0, 200)}`)
  }

  return res as Record<string, unknown>
}

const text = (value: unknown): string | null =>
  typeof value === 'string' && value !== '' ? value : null

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    try {
      await $.env.set('SUPERHEROES_COMPACT_MOD', '1')
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
        const args = ['--session-id', await $.session.id()]
        const { value: known } = await $.state.get(transcriptPath)
        const transcript = text(known)
        const owner = e.instructions?.trim() ? e.instructions : null

        if (transcript !== null) {
          args.push('--transcript', transcript)
        }
        if (owner !== null) {
          args.push('--user-instructions', owner)
        }

        const res = await directive($, 'instructions', args)
        const instructions = text(res.instructions)
        const markerPath = text(res.markerPath)

        if (instructions === null || markerPath === null) {
          throw new Error('instructions answer lacks instructions or markerPath')
        }

        await $.fs.write(markerPath, String(Date.now()))
        steered = { ...e, instructions }
      } catch (error) {
        note($, `session.compact: ${String(error)}`)
      }
    }

    return next(steered)
  }).catch(($, e, next) => next(e))

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)

    try {
      const block = extractCheckpointBlock(e.answer)

      if (block !== null) {
        const res = await directive($, 'path', ['--session-id', await $.session.id()])
        const path = text(res.path)

        if (path === null) {
          throw new Error('path answer lacks path')
        }

        await $.fs.write(path, block)
        $.ui.toast('Checkpoint notes saved')
      }
    } catch (error) {
      note($, `turn.complete: ${String(error)}`)
    }

    return result
  }).catch(($, e, next) => next(e))
}
