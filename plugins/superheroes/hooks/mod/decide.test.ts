import { expect, test } from 'claude-code/testing'

import {
  HEADS_UP_TOKENS,
  MIN_TRIGGER_TOKENS,
  SNOOZE_STEP_TOKENS,
  decide,
  effectiveTrigger,
  notesChanged,
  rearmAt,
  settingsFrom,
  snooze,
} from './decide'
import type { DecideInput, Settings } from './decide'

type Spec = { default: number; min: number; max: number }

// A test-local schema in the manifest's shape, its values deliberately not the manifest's:
// these tests cover the coercion logic. (The manifest itself: lib/tests/test_user_config_1814.py.)
const schemaOf = (): Record<string, any> => ({
  autoCheckpointTokens: { default: 400000, min: 20000, max: 1500000 },
  autoCheckpointAllowance: { default: 90000, min: 0, max: 950000 },
  autoCheckpointMode: { default: 'auto', options: ['auto', 'click-only', 'off'] },
})
const settingsOf = (schema: unknown, options: unknown): Settings => settingsFrom(options, schema)!
const TRIGGER = 500000

// Every gate open: at the trigger, auto, idle, interactive, nothing running, no snooze.
const open: DecideInput = {
  tokens: TRIGGER,
  trigger: TRIGGER,
  mode: 'auto',
  isIdle: true,
  isInteractive: true,
  isRunning: false,
  snoozeUntilTokens: null,
}

const run = (change: Partial<DecideInput>) => decide({ ...open, ...change })

test('decide fires with every gate open', () => {
  expect(run({})).toEqual({ showBand: true, fire: true, reason: 'fire' })
})

test('threshold: one token below the trigger shows the band and does not fire', () => {
  expect(run({ tokens: TRIGGER - 1 })).toEqual({ showBand: true, fire: false, reason: 'below-trigger' })
  expect(run({ tokens: TRIGGER + 1 }).fire).toBe(true)
})

test('threshold: no band until the heads-up distance below the trigger', () => {
  expect(run({ tokens: TRIGGER - HEADS_UP_TOKENS })).toMatchObject({ showBand: true, fire: false })
  expect(run({ tokens: TRIGGER - HEADS_UP_TOKENS - 1 })).toEqual({
    showBand: false,
    fire: false,
    reason: 'below-heads-up',
  })
})

test('idle gate: a running turn keeps the band and holds the fire', () => {
  expect(run({ isIdle: false })).toEqual({ showBand: true, fire: false, reason: 'busy' })
})

test('interactive gate: headless draws nothing automatic', () => {
  expect(run({ isInteractive: false })).toMatchObject({ fire: false, reason: 'headless' })
})

test('running gate: a checkpoint in progress hides the band and holds the fire', () => {
  expect(run({ isRunning: true })).toEqual({ showBand: false, fire: false, reason: 'running' })
})

test('click-only: the band shows and nothing fires, however far past the trigger', () => {
  expect(run({ mode: 'click-only' })).toEqual({ showBand: true, fire: false, reason: 'click-only' })
  expect(run({ mode: 'click-only', tokens: TRIGGER * 2 }).fire).toBe(false)
})

test('off: no band and no fire', () => {
  expect(run({ mode: 'off' })).toEqual({ showBand: false, fire: false, reason: 'off' })
  expect(run({ mode: 'off', tokens: TRIGGER * 2 }).showBand).toBe(false)
})

test('snooze: holds the fire below the snooze fill and releases it at or past it', () => {
  const until = snooze(TRIGGER)

  expect(until).toBe(TRIGGER + SNOOZE_STEP_TOKENS)
  expect(run({ snoozeUntilTokens: until })).toEqual({ showBand: true, fire: false, reason: 'snoozed' })
  expect(run({ snoozeUntilTokens: until, tokens: until - 1 }).fire).toBe(false)
  expect(run({ snoozeUntilTokens: until, tokens: until }).fire).toBe(true)
})

test('snooze: one below the trigger is not rescued by an old snooze below it', () => {
  expect(run({ tokens: TRIGGER - 1, snoozeUntilTokens: 1 }).fire).toBe(false)
})

const AUTO_COMPACT = 967000

test('window clamp: auto-compact on pulls the trigger to threshold minus the allowance', () => {
  const DEFAULT_SETTINGS = settingsOf(schemaOf(), {})

  const settings = { ...DEFAULT_SETTINGS, thresholdTokens: 900000 }

  // 967000 - 90000 = 877000, earlier than the owner's 900000
  expect(effectiveTrigger(settings, AUTO_COMPACT, true)).toBe(877000)
})

test('window clamp: a threshold earlier than the window keeps the threshold', () => {
  const DEFAULT_SETTINGS = settingsOf(schemaOf(), {})

  expect(effectiveTrigger(DEFAULT_SETTINGS, AUTO_COMPACT, true)).toBe(400000)
})

test('window clamp: auto-compact off, or its threshold unknown, leaves the threshold alone', () => {
  const DEFAULT_SETTINGS = settingsOf(schemaOf(), {})

  const settings = { ...DEFAULT_SETTINGS, thresholdTokens: 900000 }

  expect(effectiveTrigger(settings, AUTO_COMPACT, false)).toBe(900000)
  expect(effectiveTrigger(settings, undefined, true)).toBe(900000)
  expect(effectiveTrigger(settings, undefined, false)).toBe(900000)
})

test('window clamp: a bigger allowance fires earlier', () => {
  const DEFAULT_SETTINGS = settingsOf(schemaOf(), {})

  const settings = { ...DEFAULT_SETTINGS, thresholdTokens: 900000, allowanceTokens: 300000 }

  expect(effectiveTrigger(settings, AUTO_COMPACT, true)).toBe(667000)
})

test('window clamp: the trigger never falls below the floor, so a tiny window cannot fire every turn', () => {
  const DEFAULT_SETTINGS = settingsOf(schemaOf(), {})

  expect(effectiveTrigger(DEFAULT_SETTINGS, 100000, true)).toBe(MIN_TRIGGER_TOKENS)
  expect(effectiveTrigger(DEFAULT_SETTINGS, 10000, true)).toBe(MIN_TRIGGER_TOKENS)
})

test('settingsFrom: a missing or empty options object is the manifest defaults', () => {
  const schema = schemaOf()
  const defaults = {
    thresholdTokens: schema.autoCheckpointTokens.default,
    allowanceTokens: schema.autoCheckpointAllowance.default,
    mode: schema.autoCheckpointMode.default,
  }

  for (const options of [{}, undefined, null, 'auto']) {
    expect(settingsFrom(options, schema)).toEqual(defaults)
  }
})

test('settingsFrom: valid values are kept', () => {
  const schema = schemaOf()

  expect(
    settingsOf(schema, { autoCheckpointTokens: 300000, autoCheckpointAllowance: 50000, autoCheckpointMode: 'click-only' }),
  ).toEqual({ thresholdTokens: 300000, allowanceTokens: 50000, mode: 'click-only' })
  expect(settingsOf(schema, { autoCheckpointMode: 'off' }).mode).toBe('off')
})

test('settingsFrom: malformed or out-of-range values take their defaults', () => {
  const schema = schemaOf()
  const tokens: Spec = schema.autoCheckpointTokens
  const allowance: Spec = schema.autoCheckpointAllowance
  const defaults = settingsOf(schema, {})

  for (const bad of [tokens.min - 1, tokens.max + 1, '300000', Number.NaN]) {
    expect(settingsOf(schema, { autoCheckpointTokens: bad }).thresholdTokens).toBe(tokens.default)
  }
  for (const bad of [allowance.min - 1, allowance.max + 1]) {
    expect(settingsOf(schema, { autoCheckpointAllowance: bad }).allowanceTokens).toBe(allowance.default)
  }
  expect(settingsOf(schema, { autoCheckpointMode: 'sometimes' }).mode).toBe(defaults.mode)
  expect(settingsOf(schema, { autoCheckpointMode: 3 }).mode).toBe(defaults.mode)
})

test('settingsFrom: the allowance is independent of the threshold', () => {
  const schema = schemaOf()
  const settings = settingsOf(schema, { autoCheckpointTokens: 500000, autoCheckpointAllowance: 700000 })

  expect(settings.allowanceTokens).toBe(700000)
  expect(effectiveTrigger(settings, AUTO_COMPACT, true)).toBe(267000)
  expect(settingsOf(schema, { autoCheckpointAllowance: 0 }).allowanceTokens).toBe(0)
})

test('settingsFrom: a missing or malformed schema answers null', () => {
  const schema = schemaOf()

  expect(settingsFrom({}, undefined)).toBeNull()
  expect(settingsFrom({}, 3)).toBeNull()
  expect(settingsFrom({}, {})).toBeNull()
  expect(settingsFrom({}, { ...schema, autoCheckpointMode: { default: 'auto' } })).toBeNull()
  expect(settingsFrom({}, { ...schema, autoCheckpointTokens: { default: 'x', min: 1, max: 2 } })).toBeNull()
})

test('notesChanged: true only for non-empty text that differs from before', () => {
  expect(notesChanged('old', 'new')).toBe(true)
  expect(notesChanged(null, 'first notes')).toBe(true)
})

test('notesChanged: unchanged, empty or missing notes do not count', () => {
  expect(notesChanged('same', 'same')).toBe(false)
  expect(notesChanged('old', '')).toBe(false)
  expect(notesChanged('old', null)).toBe(false)
  expect(notesChanged(null, null)).toBe(false)
  expect(notesChanged(null, '')).toBe(false)
})

test('rearmAt: a step past the fill, within half the headroom before the harness compacts', () => {
  expect(rearmAt(80000, 967000)).toBe(80000 + SNOOZE_STEP_TOKENS)
  expect(rearmAt(80000, 167000)).toBe(80000 + 43500)
  expect(rearmAt(166999, 167000)).toBe(166999)
  expect(rearmAt(167000, 167000)).toBe(167000 + SNOOZE_STEP_TOKENS)
  expect(rearmAt(180000, 167000)).toBe(180000 + SNOOZE_STEP_TOKENS)
  expect(rearmAt(80000, undefined)).toBe(snooze(80000))
})
