import type { On, SessionCompactInput, SessionUsage } from 'claude-code'
import { expect, mock, test } from 'claude-code/testing'
import type { Engine, MockClock } from 'claude-code/testing'

import { CHECKPOINT_INFO } from './checkpoint-block'
import { USER_CONFIG } from './user-config.fixture'

// What the stubbed lib/compaction_directive.py answers: a process result, or
// `null` for a CLI that cannot run at all (missing, timed out).
type Cli = { exitCode: number; stdout: string } | null

const SESSION = 'sess-1'
const HISTORY = [{ role: 'user' as const, text: 'hello', toolUses: [] }]
const SUMMARY = [{ role: 'user' as const, text: 'summary', toolUses: [] }]
const MARKER = '/notes/sess-1.delivered'
const NOTES = '/notes/sess-1.md'
const DIRECTIVE = 'You are the showrunner. Keep the notes.'

const ok = (body: Record<string, unknown>): Cli => ({
  exitCode: 0,
  stdout: JSON.stringify({ ok: true, ...body }),
})
const steer = ok({
  mode: 'showrunner',
  instructions: DIRECTIVE,
  notesPath: NOTES,
  notesFound: true,
  markerPath: MARKER,
})
const saveAnswer = ok({ path: NOTES })

// What the stubbed lib/compaction_cli.json reads as. The mod takes its vocabulary from that
// file; the real file's agreement with the real CLI is lib/tests/test_compaction_mod_argv_1814.py.
const VOCABULARY = JSON.stringify({
  verbs: {
    path: { sessionId: '--session-id' },
    instructions: { sessionId: '--session-id', transcriptPath: '--transcript', userInstructions: '--user-instructions' },
    mark: { sessionId: '--session-id' },
    save: { sessionId: '--session-id' },
  },
})

// What `session.usage` answers at a fill, on a 1M window whose auto-compaction runs at 967000.
const usageAt = (tokens: number): SessionUsage => ({
  startedAt: 0,
  rateLimits: [],
  context: {
    tokens,
    window: 1000000,
    breakdown: {
      categories: [],
      totalTokens: tokens,
      maxTokens: 1000000,
      rawMaxTokens: 1000000,
      autocompactSource: 'auto',
      percentage: 0,
      gridRows: [],
      model: 'm',
      memoryFiles: [],
      mcpTools: [],
      agents: [],
      apiUsage: null,
      autoCompactThreshold: 967000,
      isAutoCompactEnabled: true,
    },
  },
})

type Rig = {
  argv: string[][]
  stdins: (string | undefined)[]
  writes: { path: string; text: string }[]
  reads: string[]
  seen: SessionCompactInput[]
  envs: [string, string | undefined][]
  states: unknown[]
  toasts: string[]
  order: string[]
  clock: MockClock
  // the slash commands the mod ran, `name args`
  commands: string[]
  // every `$.state.set` as [key, value]
  sets: [string, unknown][]
  // what `session.usage` answers (null: it fails) and what the notes file holds (null: missing)
  usage: SessionUsage | null
  notes: string | null
  compactAttempts: number
}

// Registers the world beneath the mod: the CLI stub on `process.run`, the file
// system on `fs.write`, the session id, and the engine's own compaction/turn
// bottoms, each recording what reached it.
function rig(
  on: On,
  cli: (argv: readonly string[]) => Cli,
  options: {
    isIdBroken?: boolean
    isEnvBroken?: boolean
    isStateBroken?: boolean
    vocabulary?: string | null
    isCommandBroken?: boolean
    manifest?: string | null
    compactFailures?: number
  } = {},
): Rig {
  const r: Rig = {
    argv: [],
    stdins: [],
    writes: [],
    reads: [],
    seen: [],
    envs: [],
    states: [],
    toasts: [],
    order: [],
    clock: mock.clock(on),
    commands: [],
    sets: [],
    usage: usageAt(0),
    notes: 'old notes',
    compactAttempts: 0,
  }

  on('session.id', () =>
    options.isIdBroken ? { deny: 'no session id' } : { value: SESSION },
  )
  on('process.run', (_$, e) => {
    r.argv.push([...e.argv])
    r.order.push(`cli:${e.argv[3]}`)
    r.stdins.push(e.init?.stdin)
    const out = cli(e.argv)

    return out === null
      ? { deny: 'cannot start' }
      : {
          value: {
            exitCode: out.exitCode,
            stdout: out.stdout,
            stderr: '',
            isStdoutTruncated: false,
            isStderrTruncated: false,
          },
        }
  })
  on('fs.read', (_$, e) => {
    r.reads.push(e.path)

    if (e.path === NOTES) {
      return r.notes === null ? { deny: 'no such file' } : { value: r.notes }
    }

    if (e.path.endsWith('/.claude-plugin/plugin.json')) {
      return options.manifest === null
        ? { deny: 'no such file' }
        : { value: options.manifest ?? JSON.stringify({ userConfig: USER_CONFIG }) }
    }

    return options.vocabulary === null
      ? { deny: 'no such file' }
      : { value: options.vocabulary ?? VOCABULARY }
  })
  on('fs.write', (_$, e) => {
    r.writes.push({ path: e.path, text: e.text })
    r.order.push(`write:${e.path}`)

    return { value: undefined }
  })
  on('env.set', (_$, e) => {
    if (options.isEnvBroken) {
      return { deny: 'env locked' }
    }
    r.envs.push([e.name, e.value])

    return { value: undefined }
  })
  on('state.set', (_$, e, next) => {
    if (options.isStateBroken) {
      return { deny: 'state locked' }
    }
    r.states.push(e.value)
    r.sets.push([e.key, e.value])

    return next(e)
  })
  on('ui.toast', (_$, e) => {
    r.toasts.push(e.text)

    return { value: undefined }
  })
  on('ui.log', () => ({ value: undefined }))
  on('session.compact', (_$, e) => {
    r.seen.push(e)
    r.order.push('compact')
    r.compactAttempts += 1
    if (r.compactAttempts <= (options.compactFailures ?? 0)) {
      throw new Error('a turn is running')
    }

    return { messages: SUMMARY }
  })
  // the engine's own band, which the mod's draws in place of only while it has something to say
  on('ui.render', ($, e) => $.ui.resolve(e).Text({ children: 'engine band' }))
  on('session.usage', () => (r.usage === null ? { deny: 'no usage' } : { value: r.usage }))
  on('session.measure', (_$, e) => ({ changed: e.changed }))
  on('turn.start', (_$, e) => ({ turnId: e.turnId }))
  on('command.run', (_$, e) => {
    r.commands.push(`${e.command} ${e.args}`.trim())

    if (options.isCommandBroken) {
      throw new Error('unknown command')
    }

    return { text: '' }
  })
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('turn.complete', (_$, e) => ({ text: e.answer }))
  on('classic.SessionStart', () => ({}))

  return r
}

const compact = ($: Engine, e: Partial<SessionCompactInput> = {}) =>
  $.session.compact({ trigger: 'manual', messages: HISTORY, ...e })

const flag = (argv: readonly string[], name: string) => {
  const at = argv.indexOf(name)

  return at === -1 ? undefined : argv[at + 1]
}

// The i-th recorded item, narrowed: a missing one fails the test where it is read.
const nth = <T>(items: readonly T[], i: number): T => {
  const item = items[i]
  expect(item).toBeDefined()
  if (item === undefined) {
    throw new Error(`no recorded item at ${i}`)
  }

  return item
}

const block = (body: string) => `Here you go.\n\n\`\`\`${CHECKPOINT_INFO}\n${body}\n\`\`\`\n`

for (const trigger of ['manual', 'auto'] as const) {
  test(`session.compact (${trigger}): the CLI's instructions reach the summarizer, the marker lands first`, async ($, on) => {
    const r = rig(on, () => steer)

    const res = await compact($, { trigger })

    expect(res).toEqual({ messages: SUMMARY })
    expect(r.seen).toHaveLength(1)
    expect(nth(r.seen, 0).instructions).toBe(DIRECTIVE)
    expect(nth(r.seen, 0).trigger).toBe(trigger)
    expect(r.argv).toHaveLength(2)
    expect(nth(r.reads, 0).endsWith('/lib/compaction_cli.json')).toBe(true)
    expect(nth(r.argv, 0)[0]).toBe('python3')
    expect(nth(r.argv, 0)[1]).toBe('-B')
    expect(nth(r.argv, 0)[2]?.endsWith('/lib/compaction_directive.py')).toBe(true)
    expect(nth(r.argv, 0)[3]).toBe('instructions')
    expect(flag(nth(r.argv, 0), '--session-id')).toBe(SESSION)
    expect(nth(r.argv, 0)).not.toContain('--user-instructions')
    // the CLI publishes the marker atomically; the mod writes no file itself
    expect(nth(r.argv, 1)[3]).toBe('mark')
    expect(flag(nth(r.argv, 1), '--session-id')).toBe(SESSION)
    expect(r.writes).toHaveLength(0)
    expect(r.order).toEqual(['cli:instructions', 'cli:mark', 'compact'])
  })
}

test("session.compact: the owner's /compact text is forwarded as --user-instructions", async ($, on) => {
  const r = rig(on, () => steer)

  await compact($, { instructions: 'keep the PR number' })

  expect(flag(nth(r.argv, 0), '--user-instructions')).toBe('keep the PR number')
  expect(nth(r.seen, 0).instructions).toBe(DIRECTIVE)
})

test('session.compact: blank owner text is not forwarded', async ($, on) => {
  const r = rig(on, () => steer)

  await compact($, { instructions: '  \n ' })

  expect(nth(r.argv, 0)).not.toContain('--user-instructions')
})

test('session.compact: the transcript the session started with is forwarded', async ($, on) => {
  const r = rig(on, () => steer)

  await $.classic.SessionStart({ source: 'startup', transcript_path: '/t/s.jsonl' })
  await compact($)

  expect(flag(nth(r.argv, 0), '--transcript')).toBe('/t/s.jsonl')
})

test('session.compact: no --transcript while the transcript is unknown', async ($, on) => {
  const r = rig(on, () => steer)

  await $.classic.SessionStart({ source: 'startup', transcript_path: '' })
  await compact($)

  expect(nth(r.argv, 0)).not.toContain('--transcript')
  expect(nth(r.seen, 0).instructions).toBe(DIRECTIVE)
})

test("session.compact: a subagent's own compaction is untouched", async ($, on) => {
  const r = rig(on, () => steer)

  await compact($, { agentId: 'agent-7', instructions: 'subagent text' })

  expect(r.argv).toHaveLength(0)
  expect(r.writes).toHaveLength(0)
  expect(r.seen).toHaveLength(1)
  expect(nth(r.seen, 0).instructions).toBe('subagent text')
  expect(nth(r.seen, 0).agentId).toBe('agent-7')
})

type Options = NonNullable<Parameters<typeof rig>[2]>

const failures: [string, Cli, Options][] = [
  ['CLI exits non-zero', { exitCode: 1, stdout: '{"ok": false, "reason": "no-notes"}' }, {}],
  ['CLI exits 2 with no output', { exitCode: 2, stdout: '' }, {}],
  ['stdout is not JSON', { exitCode: 0, stdout: 'Traceback (most recent call last)' }, {}],
  ['stdout is JSON but not an object', { exitCode: 0, stdout: '"fine"' }, {}],
  ['ok is false on exit 0', { exitCode: 0, stdout: '{"ok": false, "reason": "x"}' }, {}],
  // the exit code and the ok flag each refuse on their own, whatever else the body carries
  [
    'CLI exits 1 though its body says ok',
    { exitCode: 1, stdout: steer?.stdout ?? '' },
    {},
  ],
  [
    'ok is false though the body carries instructions',
    {
      exitCode: 0,
      stdout: JSON.stringify({ ok: false, reason: 'x', instructions: DIRECTIVE, markerPath: MARKER }),
    },
    {},
  ],
  ['instructions are empty', ok({ instructions: '', markerPath: MARKER }), {}],
  ['markerPath is missing', ok({ instructions: DIRECTIVE }), {}],
  ['the CLI cannot run (missing or timed out)', null, {}],
  ['the session id throws', steer, { isIdBroken: true }],
  ['the vocabulary file cannot be read', steer, { vocabulary: null }],
  ['the vocabulary file is not JSON', steer, { vocabulary: '{ not json' }],
  ['the vocabulary file lacks a verb', steer, { vocabulary: JSON.stringify({ verbs: { mark: { sessionId: '--session-id' } } }) }],
]

for (const [name, cli, options] of failures) {
  test(`session.compact fails open: ${name}`, async ($, on) => {
    // the failure is the instructions verb's; `mark` would succeed if anything issued it
    const r = rig(on, argv => (argv[3] === 'mark' ? ok({ path: MARKER }) : cli), options)

    const res = await compact($, { instructions: 'keep this' })

    expect(res).toEqual({ messages: SUMMARY })
    expect(r.seen).toHaveLength(1)
    expect(nth(r.seen, 0).instructions).toBe('keep this')
    expect(r.writes).toHaveLength(0)
    // no marker is published, or the PreCompact fallback would be suppressed with nothing steering
    expect(r.argv.filter(argv => argv[3] === 'mark')).toHaveLength(0)
  })
}

test('session.compact keeps the retrieved instructions when the marker is not acknowledged', async ($, on) => {
  const r = rig(on, argv =>
    argv[3] === 'mark' ? { exitCode: 1, stdout: '{"ok": false, "reason": "x"}' } : steer,
  )

  const res = await compact($, { instructions: 'keep this' })

  expect(res).toEqual({ messages: SUMMARY })
  // a mark that published and then died unacknowledged must not drop the steering
  expect(nth(r.seen, 0).instructions).toBe(DIRECTIVE)
  expect(r.order).toEqual(['cli:instructions', 'cli:mark', 'compact'])
  // the mod never writes a marker file itself
  expect(r.writes).toHaveLength(0)
})

test('session.compact fails open with no owner text: instructions stay absent', async ($, on) => {
  const r = rig(on, () => ({ exitCode: 1, stdout: '' }))

  await compact($)

  expect(nth(r.seen, 0).instructions).toBeUndefined()
  expect(r.writes).toHaveLength(0)
})

test('session.start sets the mod-presence variable to this session id for Bash children', async ($, on) => {
  const r = rig(on, () => steer)

  const res = await $.session.start({ cwd: '/w', surface: null, isInteractive: false })

  expect(res).toEqual({ cwd: '/w' })
  expect(r.envs).toHaveLength(1)
  expect(nth(r.envs, 0)[1]).toBe(SESSION)
})

test('session.start still completes when the env write throws', async ($, on) => {
  rig(on, () => steer, { isEnvBroken: true })

  const res = await $.session.start({ cwd: '/w', surface: null, isInteractive: false })

  expect(res).toEqual({ cwd: '/w' })
})

test('classic.SessionStart stores the transcript path under the plugin state', async ($, on) => {
  const r = rig(on, () => steer)

  await $.classic.SessionStart({ source: 'startup', transcript_path: '/t/s.jsonl' })
  await $.classic.SessionStart({ source: 'clear', transcript_path: '' })

  expect(r.states).toEqual(['/t/s.jsonl', null])
})

test('classic.SessionStart still completes when the state write throws', async ($, on) => {
  rig(on, () => steer, { isStateBroken: true })

  const res = await $.classic.SessionStart({ source: 'startup', transcript_path: '/t/s.jsonl' })

  expect(res).toEqual({})
})

const complete = ($: Engine, answer: string, e: { agentId?: string } = {}) =>
  $.turn.complete({
    answer,
    durationMs: 10,
    isAborted: false,
    turnId: 't1',
    reason: 'answer',
    ...e,
  })

test('turn.complete hands the checkpoint block to the CLI save verb on stdin, then toasts, and never alters the answer', async ($, on) => {
  const r = rig(on, () => saveAnswer)
  const answer = block('## Notes\n- one\n- two')

  const res = await complete($, answer)

  expect(res).toEqual({ text: answer })
  expect(r.argv).toHaveLength(1)
  expect(nth(r.argv, 0)[3]).toBe('save')
  expect(flag(nth(r.argv, 0), '--session-id')).toBe(SESSION)
  expect(r.stdins).toEqual(['## Notes\n- one\n- two'])
  // the CLI owns the (atomic) file write; the mod writes nothing itself
  expect(r.writes).toHaveLength(0)
  expect(r.toasts).toEqual(['Checkpoint notes saved'])
})

test("turn.complete: a subagent's checkpoint block never reaches the parent's notes", async ($, on) => {
  const r = rig(on, () => saveAnswer)
  const answer = block('subagent state')

  const res = await complete($, answer, { agentId: 'agent-7' })

  expect(res).toEqual({ text: answer })
  expect(r.argv).toHaveLength(0)
  expect(r.writes).toHaveLength(0)
  expect(r.toasts).toHaveLength(0)
})

for (const [name, answer] of [
  ['no block', 'Just an answer.'],
  ['a checkpoint example quoted in a tilde fence', `~~~markdown\n\`\`\`${CHECKPOINT_INFO}\nquoted\n\`\`\`\n~~~\n`],
  ['a checkpoint example inside an unclosed tilde fence', `~~~markdown\n\`\`\`${CHECKPOINT_INFO}\nquoted\n\`\`\`\n`],
  ['a checkpoint example inside an unclosed four-tilde fence', `~~~~markdown\n\`\`\`${CHECKPOINT_INFO}\nquoted\n\`\`\`\n`],
  ['a checkpoint example quoted in a backtick fence', `\`\`\`\`markdown\n\`\`\`${CHECKPOINT_INFO}\nquoted\n\`\`\`\n\`\`\`\`\n`],
  ['an unclosed block', `\`\`\`${CHECKPOINT_INFO}\nnotes with no end\n`],
  ['a closed block followed by prose', `${block('example notes')}This is only an example.\n`],
  ['an empty block', `\`\`\`${CHECKPOINT_INFO}\n\n\`\`\`\n`],
] as const) {
  test(`turn.complete with ${name}: no CLI call, no write, no toast`, async ($, on) => {
    const r = rig(on, () => saveAnswer)

    const res = await complete($, answer)

    expect(res).toEqual({ text: answer })
    expect(r.argv).toHaveLength(0)
    expect(r.writes).toHaveLength(0)
    expect(r.toasts).toHaveLength(0)
  })
}

for (const [name, cli, options] of [
  ['the CLI exits 1 (save refused)', { exitCode: 1, stdout: '{"ok": false, "reason": "empty-notes"}' }, {}],
  ['stdout is not JSON', { exitCode: 0, stdout: 'oops' }, {}],
  ['the CLI cannot run', null, {}],
  ['the session id throws', saveAnswer, { isIdBroken: true }],
  ['the vocabulary file is malformed', saveAnswer, { vocabulary: '{ not json' }],
] as [string, Cli, Options][]) {
  test(`turn.complete fails open: ${name} — failure toast and a warning line beneath the answer`, async ($, on) => {
    const r = rig(on, () => cli, options)
    const answer = block('notes')

    const res = await complete($, answer)
    const warning = 'Checkpoint notes NOT saved: the previous notes are still in place'

    expect(res).toEqual({ text: `${answer}\n\n${warning}` })
    expect(r.writes).toHaveLength(0)
    expect(r.toasts).toEqual([warning])
  })
}

// ---- the automatic checkpoint (#1814 layer 2) --------------------------------------

const COMMAND = 'superheroes:checkpoint auto'
const SUCCESS = 'Checkpointed and compacted'
const SKIPPED = 'Auto-checkpoint skipped: the notes file did not change'
const COMPACT_FAILED = 'Auto-checkpoint saved the notes but could not compact'
const COMMAND_FAILED = 'Auto-checkpoint failed'

// Above the 500000 default trigger / inside its 50000 heads-up band / below the band.
const PAST = 520000
const NEAR = 470000
const FAR_BELOW = 100000

const start = ($: Engine, isInteractive = true) =>
  $.session.start({ cwd: '/w', surface: 'terminal', isInteractive })

// The engine measures the session at `tokens`.
async function measure($: Engine, r: Rig, tokens: number) {
  r.usage = usageAt(tokens)

  return $.session.measure({
    context: { tokens, window: 1000000 },
    rateLimits: [],
    changed: ['context'],
  })
}

const BAND = {
  hasSurvey: false,
  isWorking: false,
  maxRows: 10,
  bodyColumns: 80,
  scroll: { offset: 0, bodyRows: 10 },
  view: {},
}

const mountBand = ($: Engine, surface: 'terminal' | 'desktop') =>
  $.ui.mount({ plugin: 'superheroes', surface, component: 'AbovePrompt', props: BAND })

test('measure at the trigger runs /superheroes:checkpoint auto once, and never again while it runs', async ($, on) => {
  const r = rig(on, () => saveAnswer)

  await start($)
  await measure($, r, PAST)
  await r.clock.settle()

  expect(r.commands).toEqual([COMMAND])

  await measure($, r, PAST + 1000)
  await measure($, r, PAST + 2000)
  await r.clock.settle()

  expect(r.commands).toEqual([COMMAND])
})

test('measure below the trigger runs nothing', async ($, on) => {
  const r = rig(on, () => saveAnswer)

  await start($)
  await measure($, r, NEAR)
  await r.clock.settle()

  expect(r.commands).toEqual([])
})

test('headless (not interactive): nothing runs automatically', async ($, on) => {
  const r = rig(on, () => saveAnswer)

  await start($, false)
  await measure($, r, PAST)
  await r.clock.settle()

  expect(r.commands).toEqual([])
})

test('a turn in progress holds the automatic run until the turn completes', async ($, on) => {
  const r = rig(on, () => saveAnswer)

  await start($)
  await $.turn.start({ text: 'work', turnId: 't1' })
  await measure($, r, PAST)
  await r.clock.settle()

  expect(r.commands).toEqual([])

  await complete($, 'done')
  await r.clock.settle()

  // no timer measures again: the engine's own measurement after the turn finds it idle
  expect(r.commands).toEqual([])

  await measure($, r, PAST)
  await r.clock.settle()

  expect(r.commands).toEqual([COMMAND])
})

test('usage cannot be read: no band change and nothing runs', async ($, on) => {
  const r = rig(on, () => saveAnswer)

  await start($)
  r.usage = null
  await $.session.measure({ context: { tokens: PAST, window: 1000000 }, rateLimits: [], changed: ['context'] })
  await r.clock.settle()

  expect(r.commands).toEqual([])
  expect(r.sets.filter(([key]) => key === 'band')).toEqual([])
})

test('a checkpoint that changed the notes compacts after the turn and toasts', async ($, on) => {
  const r = rig(on, () => saveAnswer)

  await start($)
  await measure($, r, PAST)
  await r.clock.settle()
  r.notes = 'fresh notes'

  await complete($, 'Done.')

  // not inside the turn that ended: only once the clock has moved on, and the toast
  // only once the compaction resolved
  expect(r.toasts).toEqual([])
  expect(r.seen).toHaveLength(0)

  await r.clock.advance(1000)

  expect(r.toasts).toEqual([SUCCESS])
  expect(r.seen).toHaveLength(1)
  // The mod passes no instructions: the real engine runs the mod's own `session.compact` hook
  // for the compaction it starts, and that hook steers it (measured on #1814, comment
  // 6134267207). The kit's `session.compact` bottom need not emulate that.
  expect(nth(r.seen, 0).instructions).toBeUndefined()
  // and the mod itself composed nothing and marked nothing
  expect(r.argv.filter(argv => argv[3] === 'instructions' || argv[3] === 'mark')).toEqual([])
})

test('a measurement after the turn, before the compaction runs, starts no second checkpoint', async ($, on) => {
  const r = rig(on, () => saveAnswer)

  await start($)
  await measure($, r, PAST)
  await r.clock.settle()
  r.notes = 'fresh notes'

  await complete($, 'Done.')
  // the engine measures ~4 ms after the turn, at the same high fill, before the timer
  await measure($, r, PAST)
  await r.clock.advance(1000)

  expect(r.commands).toEqual([COMMAND])
  expect(r.seen).toHaveLength(1)

  // a late second turn.complete does not finish the held checkpoint again
  await complete($, 'Done.')
  await r.clock.advance(5000)

  expect(r.seen).toHaveLength(1)
  expect(r.toasts).toEqual([SUCCESS])

  // resolved: the checkpoint is cleared and a later one may run
  await measure($, r, PAST)
  await r.clock.settle()

  expect(r.commands).toEqual([COMMAND, COMMAND])
})

test('a failed save never compacts, even when the notes file changed', async ($, on) => {
  const r = rig(on, argv => (argv[3] === 'save' ? { exitCode: 1, stdout: 'no' } : saveAnswer))

  await start($)
  await measure($, r, PAST)
  await r.clock.settle()
  r.notes = 'fresh notes'

  await complete($, block('notes'))
  await r.clock.advance(5000)

  expect(r.toasts).toContain('Auto-checkpoint skipped: the notes could not be saved')
  expect(r.seen).toHaveLength(0)
})

test('an unreadable baseline never compacts and says why', async ($, on) => {
  const r = rig(on, argv => (argv[3] === 'path' ? { exitCode: 1, stdout: 'no' } : saveAnswer))

  await start($)
  await measure($, r, PAST)
  await r.clock.settle()
  r.notes = 'fresh notes'

  await complete($, 'Done.')
  await r.clock.advance(5000)

  expect(r.toasts).toEqual(['Auto-checkpoint skipped: the notes could not be read before the checkpoint'])
  expect(r.seen).toHaveLength(0)
})

test('a missing or malformed manifest schema runs nothing and draws no band', async ($, on) => {
  const r = rig(on, () => saveAnswer, { manifest: '{"userConfig": 3}' })

  await start($)
  await measure($, r, PAST)
  await r.clock.settle()

  expect(r.commands).toEqual([])
  expect(r.sets.filter(([key]) => key === 'band').every(([, value]) => value === false)).toBe(true)
})

test('a checkpoint that left the notes unchanged does not compact, and a later one may run', async ($, on) => {
  const r = rig(on, () => saveAnswer)

  await start($)
  await measure($, r, PAST)
  await r.clock.settle()

  await complete($, 'Done.')
  await r.clock.advance(1000)

  expect(r.toasts).toEqual([SKIPPED])
  expect(r.seen).toHaveLength(0)

  await measure($, r, PAST)
  await r.clock.settle()

  expect(r.commands).toEqual([COMMAND, COMMAND])
})

test('a checkpoint whose notes were deleted does not compact', async ($, on) => {
  const r = rig(on, () => saveAnswer)

  await start($)
  await measure($, r, PAST)
  await r.clock.settle()
  r.notes = null

  await complete($, 'Done.')
  await r.clock.advance(1000)

  expect(r.toasts).toEqual([SKIPPED])
  expect(r.seen).toHaveLength(0)
})

test("a subagent's turn never finishes the checkpoint", async ($, on) => {
  const r = rig(on, () => saveAnswer)

  await start($)
  await measure($, r, PAST)
  await r.clock.settle()
  r.notes = 'fresh notes'

  await complete($, 'Done.', { agentId: 'agent-7' })
  await r.clock.advance(5000)

  expect(r.toasts).toEqual([])
  expect(r.seen).toHaveLength(0)

  await complete($, 'Done.')
  await r.clock.advance(1000)

  expect(r.toasts).toEqual([SUCCESS])
  expect(r.seen).toHaveLength(1)
})

test('a checkpoint whose turn never completed stops blocking after a while', async ($, on) => {
  const r = rig(on, () => saveAnswer)

  await start($)
  await measure($, r, PAST)
  await r.clock.settle()
  await r.clock.advance(31 * 60 * 1000)
  await measure($, r, PAST)
  await r.clock.settle()

  expect(r.commands).toEqual([COMMAND, COMMAND])
})

test('the checkpoint command fails to run: the checkpoint is cleared and the owner is told', async ($, on) => {
  const r = rig(on, () => saveAnswer, { isCommandBroken: true })

  await start($)
  await measure($, r, PAST)
  await r.clock.settle()

  expect(r.toasts).toEqual([COMMAND_FAILED])

  // cleared: the next measurement may try again
  await measure($, r, PAST)
  await r.clock.settle()

  expect(r.commands).toEqual([COMMAND, COMMAND])
})

test('compaction that rejects is retried once, then the owner is told, with no loop', async ($, on) => {
  const r = rig(on, () => saveAnswer, { compactFailures: 2 })

  await start($)
  await measure($, r, PAST)
  await r.clock.settle()
  r.notes = 'fresh notes'
  await complete($, 'Done.')

  await r.clock.advance(1000)
  expect(r.compactAttempts).toBe(1)
  expect(r.toasts).toEqual([])

  await r.clock.advance(1000)
  expect(r.compactAttempts).toBe(2)
  expect(r.toasts).toEqual([COMPACT_FAILED])

  await r.clock.advance(60000)
  expect(r.compactAttempts).toBe(2)
})

test('compaction that rejects once is retried and lands', async ($, on) => {
  const r = rig(on, () => saveAnswer, { compactFailures: 1 })

  await start($)
  await measure($, r, PAST)
  await r.clock.settle()
  r.notes = 'fresh notes'
  await complete($, 'Done.')
  await r.clock.advance(2000)

  expect(r.compactAttempts).toBe(2)
  expect(r.toasts).toEqual([SUCCESS])
})

test('Snooze defers the automatic run to the fill it names, and compaction clears it', async ($, on) => {
  const r = rig(on, () => saveAnswer)

  await start($)
  await measure($, r, NEAR)
  const ui = await mountBand($, 'terminal')

  await ui.press({ key: 'snooze' })

  expect(r.sets.filter(([key]) => key === 'snoozeUntilTokens')).toEqual([['snoozeUntilTokens', NEAR + 100000]])

  await measure($, r, PAST)
  await measure($, r, NEAR + 100000 - 1)
  await r.clock.settle()
  expect(r.commands).toEqual([])

  await measure($, r, NEAR + 100000)
  await r.clock.settle()
  expect(r.commands).toEqual([COMMAND])

  r.notes = 'fresh notes'
  await complete($, 'Done.')
  await r.clock.advance(1000)

  // the mod's own compaction resets nothing itself: its `session.compact` hook does (see above)
  expect(r.seen).toHaveLength(1)
  expect(r.sets.filter(([key]) => key === 'snoozeUntilTokens').at(-1)).toEqual(['snoozeUntilTokens', NEAR + 100000])

  await compact($)

  expect(r.sets.filter(([key]) => key === 'snoozeUntilTokens').at(-1)).toEqual(['snoozeUntilTokens', null])
})

test('click-only: the band shows, nothing runs on its own, and Now runs the checkpoint', { options: { autoCheckpointMode: 'click-only' } }, async ($, on) => {
  const r = rig(on, () => saveAnswer)

  await start($)
  await measure($, r, PAST)
  await r.clock.settle()

  expect(r.commands).toEqual([])

  const ui = await mountBand($, 'terminal')

  expect(await ui.find({ type: 'Text', text: 'Context is near the checkpoint threshold' })).toBeDefined()

  await ui.press({ key: 'now' })
  await r.clock.settle()

  expect(r.commands).toEqual([COMMAND])
})

test('Now runs the checkpoint in auto mode too, below the trigger', async ($, on) => {
  const r = rig(on, () => saveAnswer)

  await start($)
  await measure($, r, NEAR)
  const ui = await mountBand($, 'terminal')

  await ui.press({ key: 'now' })
  await r.clock.settle()

  expect(r.commands).toEqual([COMMAND])

  // and not a second one while it runs
  await measure($, r, PAST)
  await r.clock.settle()
  expect(r.commands).toEqual([COMMAND])
})

test('off: no band and no run', { options: { autoCheckpointMode: 'off' } }, async ($, on) => {
  const r = rig(on, () => saveAnswer)

  await start($)
  await measure($, r, PAST)
  await r.clock.settle()

  expect(r.commands).toEqual([])
  expect(r.sets.filter(([key]) => key === 'band').every(([, value]) => value === false)).toBe(true)
})

for (const surface of ['terminal', 'desktop'] as const) {
  test(`the band draws "Auto-checkpoint soon" with Now and Snooze on ${surface}`, async ($, on) => {
    const r = rig(on, () => saveAnswer)

    await start($)
    await measure($, r, NEAR)
    const ui = await mountBand($, surface)

    expect(await ui.find({ type: 'Text', text: 'Auto-checkpoint soon' })).toBeDefined()
    expect(await ui.find({ type: 'Button', key: 'now' })).toBeDefined()
    expect(await ui.find({ type: 'Button', key: 'snooze' })).toBeDefined()
  })

  test(`the band is absent on ${surface} while the fill is far below the trigger`, async ($, on) => {
    const r = rig(on, () => saveAnswer)

    await start($)
    await measure($, r, FAR_BELOW)
    const ui = await mountBand($, surface)

    expect(await ui.find({ type: 'Text', text: 'engine band' })).toBeDefined()
    expect(await ui.find({ type: 'Button', key: 'now' })).toBeUndefined()
    expect(await ui.find({ type: 'Button', key: 'snooze' })).toBeUndefined()
  })
}

test('the band is absent while a checkpoint runs', async ($, on) => {
  const r = rig(on, () => saveAnswer)

  await start($)
  await measure($, r, PAST)
  await r.clock.settle()
  const ui = await mountBand($, 'terminal')

  expect(await ui.find({ type: 'Text', text: 'engine band' })).toBeDefined()
  expect(await ui.find({ type: 'Button', key: 'now' })).toBeUndefined()
})
