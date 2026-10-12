// The superheroes mod (#1814): steers every compaction with the session's charter
// directive plus its checkpoint notes, saves the checkpoint block a reply ends with
// (layer 1), and runs the automatic checkpoint: at the trigger it runs
// /superheroes:checkpoint, and once the notes file changed it compacts (layer 2;
// the decisions are ./decide). Every hook here fails open — on any error the event
// goes on unchanged (`next(e)` once), no delivered-marker is written, and the
// PreCompact command hook steers in its place.
//
// Two engine facts, measured on harness 2.1.296 (#1814, comment 6134267207).
// First: the mod's own `session.compact` hook runs for a compaction the mod starts with
// `$.session.compact()` (`e.trigger === 'plugin'`). That hook is the only place
// instructions are composed and the marker is marked, so the mod's own compaction
// passes no instructions and resets no fill itself.
// Second: `session.measure` fires after the main `turn.complete` (and once at session
// start), so the idle gate needs no timer to measure again after a turn.

import type { EngineInterface, Register, RenderElement } from 'claude-code'

import { instructionsArgv, markArgv, parseVocabulary, pathArgv, saveArgv } from './argv'
import type { CliVocabulary } from './argv'
import { extractCheckpointBlock } from './checkpoint-block'
import { decide, effectiveTrigger, notesChanged, settingsFrom, snooze } from './decide'
import type { Settings } from './decide'

const CLI_TIMEOUT_MS = 15000

// The compaction waits until the turn has ended.
const COMPACT_DELAY_MS = 1000

// A checkpoint that never saw its turn complete stops blocking the next one after this.
const STALE_CHECKPOINT_MS = 30 * 60 * 1000

const transcriptPath = { plugin: 'superheroes', key: 'transcriptPath' } as const
const isInteractive = { plugin: 'superheroes', key: 'isInteractive' } as const
const isTurnActive = { plugin: 'superheroes', key: 'isTurnActive' } as const
const checkpoint = { plugin: 'superheroes', key: 'checkpoint' } as const
const snoozeUntilTokens = { plugin: 'superheroes', key: 'snoozeUntilTokens' } as const
const band = { plugin: 'superheroes', key: 'band' } as const

// True while a checkpoint is being started: two measurements must not both start one.
let isStarting = false

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

// The session's checkpoint notes as they stand, or null: a missing file, an unresolvable
// path and a failed read all read as no notes.
async function readNotes($: EngineInterface): Promise<string | null> {
  try {
    const cli = await vocabulary($)
    const res = await directive($, pathArgv(cli, $.plugin.root, await $.session.id()))
    const path = text(res.path)

    return path === null ? null : await $.fs.read(path)
  } catch {
    return null
  }
}

// The checkpoint now running, or null (none, or one so old its turn is long lost).
async function runningCheckpoint($: EngineInterface) {
  const { value } = await $.state.get(checkpoint)

  return value && (await $.clock.now()) - value.startedAt < STALE_CHECKPOINT_MS ? value : null
}

// A checkpoint that could not start or finish: clear it, tell the owner, block nothing.
async function abandonCheckpoint($: EngineInterface, error: unknown): Promise<void> {
  note($, `checkpoint: ${String(error)}`)
  try {
    await $.state.set(checkpoint, null)
    $.ui.toast('Auto-checkpoint failed')
  } catch (cleanup) {
    note($, `checkpoint cleanup: ${String(cleanup)}`)
  }
}

// Runs /superheroes:checkpoint (automatic, or the band's Now). Never starts a second one.
async function startCheckpoint($: EngineInterface): Promise<void> {
  if (isStarting) {
    return
  }
  isStarting = true

  try {
    if ((await runningCheckpoint($)) !== null) {
      return
    }

    const notesBefore = await readNotes($)

    await $.state.set(checkpoint, { startedAt: await $.clock.now(), notesBefore })
    await $.state.set(band, false)
    // not awaited: the call settles with the checkpoint turn, which must not hold a hook
    $.command.run({ command: 'superheroes:checkpoint', args: 'auto' }).catch(error =>
      abandonCheckpoint($, error),
    )
  } catch (error) {
    await abandonCheckpoint($, error)
  } finally {
    isStarting = false
  }
}

// Reads the fill, decides, and draws the band from state; starts a checkpoint on `fire`.
// A failed usage read changes nothing.
async function evaluate($: EngineInterface, settings: Settings): Promise<void> {
  const { context } = await $.session.usage({ breakdown: 'summary' })

  if (context.tokens === undefined) {
    return
  }

  const trigger = effectiveTrigger(
    settings,
    context.breakdown?.autoCompactThreshold,
    context.breakdown?.isAutoCompactEnabled ?? false,
  )
  const snoozed = (await $.state.get(snoozeUntilTokens)).value
  const decision = decide({
    tokens: context.tokens,
    trigger,
    mode: settings.mode,
    isIdle: (await $.state.get(isTurnActive)).value !== true,
    isInteractive: (await $.state.get(isInteractive)).value === true,
    isRunning: (await runningCheckpoint($)) !== null,
    snoozeUntilTokens: typeof snoozed === 'number' ? snoozed : null,
  })

  await $.state.set(band, decision.showBand)
  if (decision.fire) {
    await startCheckpoint($)
  }
}

// The compaction input with the session's directive and notes as its instructions (the
// owner's own text rides along inside them). Fails open: on any error the input comes
// back as it was. The `session.compact` hook is the one caller: every main-loop
// compaction, the mod's own included, is steered there and nowhere else.
async function steer<T extends { instructions?: string }>($: EngineInterface, e: T): Promise<T> {
  let steered = e

  try {
    const sessionId = await $.session.id()
    const { value: known } = await $.state.get(transcriptPath)
    const transcript = text(known)
    const owner = e.instructions?.trim() ? e.instructions : null

    const cli = await vocabulary($)
    const res = await directive($, instructionsArgv(cli, $.plugin.root, sessionId, transcript, owner))
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

  return steered
}

// The fill is about to drop: a Snooze and the band belong to the old fill.
async function forgetFill($: EngineInterface): Promise<void> {
  try {
    await $.state.set(snoozeUntilTokens, null)
    await $.state.set(band, false)
  } catch (error) {
    note($, `session.compact state: ${String(error)}`)
  }
}

// Compacts after the turn that ended the checkpoint; `$.session.compact` rejects while a
// turn runs, so it waits, and a rejection is tried once more before the owner is told.
// No instructions here: the `session.compact` hook steers this compaction too.
function compactSoon($: EngineInterface, isRetry = false): void {
  $.clock.after(COMPACT_DELAY_MS, async () => {
    try {
      await $.session.compact()
    } catch (error) {
      if (!isRetry) {
        compactSoon($, true)

        return
      }
      note($, `compact: ${String(error)}`)
      $.ui.toast('Auto-checkpoint saved the notes but could not compact')
    }
  })
}

// Ends the checkpoint the finished main-loop turn belonged to: compacts once the notes
// file changed, otherwise says why not.
async function finishCheckpoint($: EngineInterface, saveFailed: boolean): Promise<void> {
  const { value } = await $.state.get(checkpoint)

  if (!value) {
    return
  }

  const notesAfter = await readNotes($)

  await $.state.set(checkpoint, null)
  if (notesChanged(value.notesBefore, notesAfter)) {
    compactSoon($)
    $.ui.toast('Checkpointed and compacted')
  } else {
    $.ui.toast(
      `Auto-checkpoint skipped: ${saveFailed ? 'the notes could not be saved' : 'the notes file did not change'}`,
    )
  }
}

export const register: Register = (on, options) => {
  const settings = settingsFrom(options)

  on('session.start', async ($, e, next) => {
    try {
      await $.state.set(isInteractive, e.isInteractive)
    } catch (error) {
      note($, `session.start state: ${String(error)}`)
    }

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
    // A subagent's own compaction is not the session's: leave it untouched.
    if (e.agentId) {
      return next(e)
    }

    const steered = await steer($, e)

    await forgetFill($)

    return next(steered)
  }).catch(($, e, next) => next(e))

  on('session.measure', async ($, e, next) => {
    try {
      await evaluate($, settings)
    } catch (error) {
      note($, `session.measure: ${String(error)}`)
    }

    return next(e)
  }).catch(($, e, next) => next(e))

  on('turn.start', async ($, e, next) => {
    try {
      await $.state.set(isTurnActive, true)
    } catch (error) {
      note($, `turn.start: ${String(error)}`)
    }

    return next(e)
  }).catch(($, e, next) => next(e))

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    let drawn: RenderElement | null = null

    try {
      if (!e.props.hasSurvey && (await $.state.get(band)).value === true) {
        const { Box, Button, Text } = $.ui.resolve(e)
        const headsUp =
          settings.mode === 'click-only'
            ? 'Context is near the checkpoint threshold'
            : 'Auto-checkpoint soon'

        drawn = Box({
          children: [
            Text({ dimColor: true, children: `${headsUp} ` }),
            Button({ key: 'now', label: 'Now', onPress: () => startCheckpoint($) }),
            Button({
              key: 'snooze',
              label: 'Snooze',
              onPress: async () => {
                try {
                  const tokens = (await $.session.usage()).context.tokens ?? 0

                  await $.state.set(snoozeUntilTokens, snooze(tokens))
                  await $.state.set(band, false)
                } catch (error) {
                  note($, `snooze: ${String(error)}`)
                }
              },
            }),
          ],
        })
      }
    } catch (error) {
      note($, `ui.render: ${String(error)}`)
    }

    return drawn ?? next(e)
  }).catch(($, e, next) => next(e))

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)

    // A subagent's answer is not the session's: its checkpoint block must never
    // replace the parent's notes (`$.session.id()` is the parent's there too).
    let warning: string | null = null

    if (!e.agentId) {
      try {
        await $.state.set(isTurnActive, false)
      } catch (error) {
        note($, `turn.complete state: ${String(error)}`)
      }

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
            // so a failed save must reach the owner: by toast, and by a line shown beneath the
            // answer (headless output emits no toast).
            note($, `turn.complete: ${String(error)}`)
            warning = 'Checkpoint notes NOT saved: the previous notes are still in place'
            $.ui.toast(warning)
          }
        }
      } catch (error) {
        note($, `turn.complete: ${String(error)}`)
      }

      try {
        await finishCheckpoint($, warning !== null)
      } catch (error) {
        await abandonCheckpoint($, error)
      }
    }

    return warning === null ? result : { ...result, text: `${result.text}\n\n${warning}` }
  }).catch(($, e, next) => next(e))
}
