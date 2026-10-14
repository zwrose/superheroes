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
import { decide, effectiveTrigger, notesChanged, rearmAt, settingsFrom, snooze } from './decide'
import type { Settings } from './decide'

const MANIFEST = '.claude-plugin/plugin.json'

const CLI_TIMEOUT_MS = 15000

const CHECKPOINT_COMMAND = 'superheroes:checkpoint'

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
const rearmAfterCompact = { plugin: 'superheroes', key: 'rearmAfterCompact' } as const

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

// The settings: the options coerced against the manifest's `userConfig`, read per call
// like the vocabulary. Null (fail safe: no band, no automatic run) when the manifest
// cannot answer.
async function loadSettings($: EngineInterface, options: unknown): Promise<Settings | null> {
  try {
    const manifest: { userConfig?: unknown } = JSON.parse(await $.fs.read(`${$.plugin.root}/${MANIFEST}`))

    return settingsFrom(options, manifest.userConfig)
  } catch (error) {
    note($, `settings: ${String(error)}`)

    return null
  }
}

// The session's checkpoint notes as they stand: null when there is no file, undefined when
// the path could not be resolved or the file exists but could not be read.
async function readNotes($: EngineInterface): Promise<string | null | undefined> {
  let path: string | null

  try {
    const cli = await vocabulary($)

    path = text((await directive($, pathArgv(cli, $.plugin.root, await $.session.id()))).path)
  } catch {
    return undefined
  }
  if (path === null) {
    return null
  }
  try {
    return (await $.fs.exists(path)) ? await $.fs.read(path) : null
  } catch {
    return undefined
  }
}

// The checkpoint now running, or null (none, or one so old its turn is long lost).
async function runningCheckpoint($: EngineInterface) {
  const { value } = await $.state.get(checkpoint)

  if (!value) {
    return null
  }
  if ((await $.clock.now()) - value.startedAt < STALE_CHECKPOINT_MS) {
    return value
  }
  // a lost checkpoint turn must not leave the session busy for good
  if (value.turnId !== undefined && (await $.state.get(isTurnActive)).value === value.turnId) {
    await $.state.set(isTurnActive, null)
  }

  return null
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

// Runs /superheroes:checkpoint (automatic, or the band's Now). Never starts a second one,
// and Now waits out a running turn.
async function startCheckpoint($: EngineInterface, isNow = false): Promise<void> {
  if (isStarting) {
    return
  }
  isStarting = true

  try {
    if ((await runningCheckpoint($)) !== null) {
      return
    }
    const notesBefore = await readNotes($)
    // the fill it started at: the fallback re-arm when the ending fill cannot be read
    let fill: number | undefined

    try {
      fill = (await $.session.usage()).context.tokens
    } catch {
      // an unread fill only means no fallback snooze when this checkpoint is skipped
    }

    // a turn may have begun while the notes and fill were read: write nothing then
    if (typeof (await $.state.get(isTurnActive)).value === 'string') {
      if (isNow) {
        $.ui.toast('Auto-checkpoint: wait for the current turn to finish')
      }

      return
    }

    await $.state.set(checkpoint, { startedAt: await $.clock.now(), fill, ...(notesBefore === undefined ? {} : { notesBefore }) })
    await $.state.set(band, false)
    // not awaited: the call settles with the checkpoint turn, which must not hold a hook
    $.command.run({ command: CHECKPOINT_COMMAND, args: 'auto' }).catch(error =>
      abandonCheckpoint($, error),
    )
  } catch (error) {
    await abandonCheckpoint($, error)
  } finally {
    isStarting = false
  }
}

// Where an automatic re-arm waits: nowhere (null) while the fill is below the trigger, which
// alone governs then; otherwise `rearmAt`.
const rearmTo = (
  tokens: number,
  trigger: number,
  breakdown: { isAutoCompactEnabled?: boolean; autoCompactThreshold?: number } | undefined,
): number | null =>
  tokens < trigger ? null : rearmAt(tokens, breakdown?.isAutoCompactEnabled ? breakdown.autoCompactThreshold : undefined)

// Reads the fill, decides, and draws the band from state; starts a checkpoint on `fire`.
// A failed usage read changes nothing.
async function evaluate($: EngineInterface, options: unknown): Promise<void> {
  const settings = await loadSettings($, options)

  if (settings === null) {
    await $.state.set(band, false)

    return
  }

  const { context } = await $.session.usage({ breakdown: 'summary' })

  if (context.tokens === undefined) {
    return
  }

  const trigger = effectiveTrigger(
    settings,
    context.breakdown?.autoCompactThreshold,
    context.breakdown?.isAutoCompactEnabled ?? false,
  )
  // the first measurement after a successful compaction: context must grow from here
  // before an automatic run repeats, within the harness's own compaction window
  if ((await $.state.get(rearmAfterCompact)).value === true) {
    await $.state.set(snoozeUntilTokens, rearmTo(context.tokens, trigger, context.breakdown))
    await $.state.set(rearmAfterCompact, false)
  }
  // read before the idle gate: a stale checkpoint's expiry frees a lost turn's busy mark
  const isRunning = (await runningCheckpoint($)) !== null

  const snoozed = (await $.state.get(snoozeUntilTokens)).value
  const decision = decide({
    tokens: context.tokens,
    trigger,
    mode: settings.mode,
    isIdle: typeof (await $.state.get(isTurnActive)).value !== 'string',
    isInteractive: (await $.state.get(isInteractive)).value === true,
    isRunning,
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
// turn runs, so it waits (a busy turn counts as no attempt, until the checkpoint is stale),
// and a rejection is tried once more before the owner is told.
// No instructions here: the `session.compact` hook steers this compaction too. The
// checkpoint stays set (`compacting`) until this resolves, so a measurement taken at the
// still-high fill starts no second one; the toast waits for the compaction itself.
function compactSoon($: EngineInterface, options: unknown, startedAt: number, isRetry = false): void {
  $.clock.after(COMPACT_DELAY_MS, async () => {
    let didFail = false
    let skipReason = ''
    let isLast = isRetry

    try {
      const pending = (await $.state.get(checkpoint)).value

      // another compaction already satisfied (or a new checkpoint replaced) this one
      if (!pending?.compacting || pending.startedAt !== startedAt) {
        return
      }
      if (typeof (await $.state.get(isTurnActive)).value === 'string') {
        if ((await runningCheckpoint($)) !== null) {
          compactSoon($, options, startedAt, isRetry)

          return
        }
        isLast = true
        throw new Error('a turn is still running')
      }

      const res = await $.session.compact()

      // a vetoed compaction resolves with a skip: the context did not shrink
      if (typeof res?.skip === 'string') {
        skipReason = ` (${res.skip})`
        throw new Error(res.skip)
      }
    } catch (error) {
      if (!isLast) {
        compactSoon($, options, startedAt, true)

        return
      }
      note($, `compact: ${String(error)}`)
      $.ui.toast(`Auto-checkpoint saved the notes but could not compact${skipReason}`)
      didFail = true
    }
    try {
      // the compaction resolved or gave up: bookkeeping failures here never schedule another one
      const { value } = await $.state.get(checkpoint)

      await $.state.set(checkpoint, null)
      if (didFail) {
        // the next automatic run waits for the fill to grow, as a skipped checkpoint does
        await rearmFromEnd($, options, value?.fill)
      } else {
        $.ui.toast('Checkpointed and compacted')
      }
    } catch (error) {
      note($, `compact state: ${String(error)}`)
    }
  })
}

// Ends the checkpoint the finished main-loop turn belonged to: compacts once the notes
// file changed, otherwise says why not. A failed save or an unreadable baseline never compacts.
async function finishCheckpoint($: EngineInterface, options: unknown, saveFailed: boolean, isAborted: boolean, turnId: string): Promise<void> {
  const { value } = await $.state.get(checkpoint)

  // only the checkpoint command's own turn ends it: a user turn queued ahead of it does not
  if (!value || value.compacting || value.turnId !== turnId) {
    return
  }

  // an interrupted checkpoint turn is cancelled, whatever its reply saved
  if (isAborted) {
    await endWithoutCompacting($, options, value.fill, 'Auto-checkpoint cancelled: the turn was interrupted')

    return
  }

  const notesAfter = saveFailed ? null : await readNotes($)
  const why = saveFailed
    ? 'the notes could not be saved'
    : value.notesBefore === undefined
      ? 'the notes could not be read before the checkpoint'
      : notesChanged(value.notesBefore, notesAfter ?? null)
        ? null
        : 'the notes file did not change'

  if (why === null) {
    await $.state.set(checkpoint, { ...value, compacting: true })
    compactSoon($, options, value.startedAt)
  } else {
    await endWithoutCompacting($, options, value.fill, `Auto-checkpoint skipped: ${why}; next try after more context`)
  }
}

// Snoozes past the fill as it stands now, the checkpoint's own turn included (or this would
// start again at once), unless it is below the trigger; an unreadable fill falls back to a
// step past the start fill.
async function rearmFromEnd($: EngineInterface, options: unknown, startFill: number | undefined): Promise<void> {
  let until: number | null | undefined = typeof startFill === 'number' ? snooze(startFill) : undefined

  try {
    const { context } = await $.session.usage({ breakdown: 'summary' })

    if (context.tokens !== undefined) {
      const settings = await loadSettings($, options)
      const { isAutoCompactEnabled, autoCompactThreshold } = context.breakdown ?? {}
      const trigger = settings === null ? 0 : effectiveTrigger(settings, autoCompactThreshold, isAutoCompactEnabled ?? false)

      until = rearmTo(context.tokens, trigger, context.breakdown)
    }
  } catch {
    // keep the fallback
  }
  if (until !== undefined) {
    await $.state.set(snoozeUntilTokens, until)
  }
}

// Ends a checkpoint that will not compact: cleared, re-armed, and the owner told.
async function endWithoutCompacting($: EngineInterface, options: unknown, startFill: number | undefined, message: string): Promise<void> {
  await $.state.set(checkpoint, null)
  await rearmFromEnd($, options, startFill)
  $.ui.toast(message)
}

export const register: Register = (on, options) => {
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

    const result = await next(steered)

    // published once the compaction is done: a measurement during it sees the old fill;
    // a skipped one keeps the Snooze and band
    if (!('skip' in result)) {
      await forgetFill($)
      try {
        await $.state.set(rearmAfterCompact, true)
        // a pending automatic compaction is satisfied by this one
        if ((await $.state.get(checkpoint)).value?.compacting) {
          await $.state.set(checkpoint, null)
        }
      } catch (error) {
        note($, `session.compact state: ${String(error)}`)
      }
    }

    return result
  }).catch(($, e, next) => next(e))

  on('session.measure', async ($, e, next) => {
    try {
      await evaluate($, options)
    } catch (error) {
      note($, `session.measure: ${String(error)}`)
    }

    return next(e)
  }).catch(($, e, next) => next(e))

  on('turn.start', async ($, e, next) => {
    try {
      await $.state.set(isTurnActive, e.turnId)

      const running = await runningCheckpoint($)

      // measured on harness 2.1.296: a command's turn.start text carries its <command-name> tag
      if (
        running !== null &&
        running.turnId === undefined &&
        e.text.includes(`<command-name>/${CHECKPOINT_COMMAND}</command-name>`)
      ) {
        await $.state.set(checkpoint, { ...running, turnId: e.turnId })
      }
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
          (await loadSettings($, options))?.mode === 'click-only'
            ? 'Context is near the checkpoint threshold'
            : 'Auto-checkpoint soon'

        drawn = Box({
          children: [
            Text({ dimColor: true, children: `${headsUp} ` }),
            Button({ key: 'now', label: 'Now', onPress: () => startCheckpoint($, true) }),
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
        await $.state.set(isTurnActive, null)
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
        await finishCheckpoint($, options, warning !== null, e.isAborted, e.turnId)
      } catch (error) {
        await abandonCheckpoint($, error)
      }
    }

    return warning === null ? result : { ...result, text: `${result.text}\n\n${warning}` }
  }).catch(($, e, next) => next(e))
}
