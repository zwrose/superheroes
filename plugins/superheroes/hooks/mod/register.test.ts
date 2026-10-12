import type { On, SessionCompactInput } from 'claude-code'
import { expect, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'

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
const pathAnswer = ok({ path: NOTES, markerPath: MARKER })

type Rig = {
  argv: string[][]
  writes: { path: string; text: string }[]
  seen: SessionCompactInput[]
  envs: [string, string | undefined][]
  states: unknown[]
  toasts: string[]
  order: string[]
}

// Registers the world beneath the mod: the CLI stub on `process.run`, the file
// system on `fs.write`, the session id, and the engine's own compaction/turn
// bottoms, each recording what reached it.
function rig(
  on: On,
  cli: (argv: readonly string[]) => Cli,
  options: { isIdBroken?: boolean; isWriteBroken?: boolean; isEnvBroken?: boolean; isStateBroken?: boolean } = {},
): Rig {
  const r: Rig = { argv: [], writes: [], seen: [], envs: [], states: [], toasts: [], order: [] }

  on('session.id', () =>
    options.isIdBroken ? { deny: 'no session id' } : { value: SESSION },
  )
  on('process.run', (_$, e) => {
    r.argv.push([...e.argv])
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
  on('fs.write', (_$, e) => {
    if (options.isWriteBroken) {
      return { deny: 'disk full' }
    }
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

    return { messages: SUMMARY }
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

const block = (body: string) => `Here you go.\n\n\`\`\`superheroes-checkpoint\n${body}\n\`\`\`\n`

for (const trigger of ['manual', 'auto'] as const) {
  test(`session.compact (${trigger}): the CLI's instructions reach the summarizer, the marker lands first`, async ($, on) => {
    const r = rig(on, () => steer)

    const res = await compact($, { trigger })

    expect(res).toEqual({ messages: SUMMARY })
    expect(r.seen).toHaveLength(1)
    expect(nth(r.seen, 0).instructions).toBe(DIRECTIVE)
    expect(nth(r.seen, 0).trigger).toBe(trigger)
    expect(r.argv).toHaveLength(1)
    expect(nth(r.argv, 0)[0]).toBe('python3')
    expect(nth(r.argv, 0)[1]).toBe('-B')
    expect(nth(r.argv, 0)[2]?.endsWith('/lib/compaction_directive.py')).toBe(true)
    expect(nth(r.argv, 0)[3]).toBe('instructions')
    expect(flag(nth(r.argv, 0), '--session-id')).toBe(SESSION)
    expect(nth(r.argv, 0)).not.toContain('--user-instructions')
    expect(r.writes).toHaveLength(1)
    expect(nth(r.writes, 0).path).toBe(MARKER)
    expect(/^\d+$/.test(nth(r.writes, 0).text)).toBe(true)
    expect(r.order).toEqual([`write:${MARKER}`, 'compact'])
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
  ['the marker write throws', steer, { isWriteBroken: true }],
]

for (const [name, cli, options] of failures) {
  test(`session.compact fails open: ${name}`, async ($, on) => {
    const r = rig(on, () => cli, options)

    const res = await compact($, { instructions: 'keep this' })

    expect(res).toEqual({ messages: SUMMARY })
    expect(r.seen).toHaveLength(1)
    expect(nth(r.seen, 0).instructions).toBe('keep this')
    expect(r.writes).toHaveLength(0)
  })
}

test('session.compact fails open with no owner text: instructions stay absent', async ($, on) => {
  const r = rig(on, () => ({ exitCode: 1, stdout: '' }))

  await compact($)

  expect(nth(r.seen, 0).instructions).toBeUndefined()
  expect(r.writes).toHaveLength(0)
})

test('session.start sets SUPERHEROES_COMPACT_MOD for Bash children', async ($, on) => {
  const r = rig(on, () => steer)

  const res = await $.session.start({ cwd: '/w', surface: null, isInteractive: false })

  expect(res).toEqual({ cwd: '/w' })
  expect(r.envs).toEqual([['SUPERHEROES_COMPACT_MOD', '1']])
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

const complete = ($: Engine, answer: string) =>
  $.turn.complete({
    answer,
    durationMs: 10,
    isAborted: false,
    turnId: 't1',
    reason: 'answer',
  })

test('turn.complete saves the checkpoint block to the CLI path, then toasts, and never alters the answer', async ($, on) => {
  const r = rig(on, () => pathAnswer)
  const answer = block('## Notes\n- one\n- two')

  const res = await complete($, answer)

  expect(res).toEqual({ text: answer })
  expect(r.argv).toHaveLength(1)
  expect(nth(r.argv, 0)[3]).toBe('path')
  expect(flag(nth(r.argv, 0), '--session-id')).toBe(SESSION)
  expect(r.writes).toEqual([{ path: NOTES, text: '## Notes\n- one\n- two' }])
  expect(r.toasts).toEqual(['Checkpoint notes saved'])
})

for (const [name, answer] of [
  ['no block', 'Just an answer.'],
  ['an unclosed block', '```superheroes-checkpoint\nnotes with no end\n'],
  ['an empty block', '```superheroes-checkpoint\n\n```\n'],
] as const) {
  test(`turn.complete with ${name}: no CLI call, no write, no toast`, async ($, on) => {
    const r = rig(on, () => pathAnswer)

    const res = await complete($, answer)

    expect(res).toEqual({ text: answer })
    expect(r.argv).toHaveLength(0)
    expect(r.writes).toHaveLength(0)
    expect(r.toasts).toHaveLength(0)
  })
}

for (const [name, cli, options] of [
  ['the CLI exits 1', { exitCode: 1, stdout: '{"ok": false, "reason": "x"}' }, {}],
  ['stdout is not JSON', { exitCode: 0, stdout: 'oops' }, {}],
  ['the CLI cannot run', null, {}],
  ['the session id throws', pathAnswer, { isIdBroken: true }],
  ['the notes write fails', pathAnswer, { isWriteBroken: true }],
] as [string, Cli, Options][]) {
  test(`turn.complete fails open: ${name} — no toast, answer unchanged`, async ($, on) => {
    const r = rig(on, () => cli, options)
    const answer = block('notes')

    const res = await complete($, answer)

    expect(res).toEqual({ text: answer })
    expect(r.writes).toHaveLength(0)
    expect(r.toasts).toHaveLength(0)
  })
}
