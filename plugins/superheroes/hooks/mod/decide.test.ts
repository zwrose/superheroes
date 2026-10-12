import { expect, test } from 'claude-code/testing'

import {
  DEFAULT_SETTINGS,
  HEADS_UP_TOKENS,
  MIN_TRIGGER_TOKENS,
  SNOOZE_STEP_TOKENS,
  decide,
  effectiveTrigger,
  notesChanged,
  settingsFrom,
  snooze,
} from './decide'
import type { DecideInput } from './decide'

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
  const settings = { ...DEFAULT_SETTINGS, thresholdTokens: 900000 }

  // 967000 - 120000 = 847000, earlier than the owner's 900000
  expect(effectiveTrigger(settings, AUTO_COMPACT, true)).toBe(847000)
})

test('window clamp: a threshold earlier than the window keeps the threshold', () => {
  expect(effectiveTrigger(DEFAULT_SETTINGS, AUTO_COMPACT, true)).toBe(500000)
})

test('window clamp: auto-compact off, or its threshold unknown, leaves the threshold alone', () => {
  const settings = { ...DEFAULT_SETTINGS, thresholdTokens: 900000 }

  expect(effectiveTrigger(settings, AUTO_COMPACT, false)).toBe(900000)
  expect(effectiveTrigger(settings, undefined, true)).toBe(900000)
  expect(effectiveTrigger(settings, undefined, false)).toBe(900000)
})

test('window clamp: a bigger allowance fires earlier', () => {
  const settings = { ...DEFAULT_SETTINGS, thresholdTokens: 900000, allowanceTokens: 300000 }

  expect(effectiveTrigger(settings, AUTO_COMPACT, true)).toBe(667000)
})

test('window clamp: the trigger never falls below the floor, so a tiny window cannot fire every turn', () => {
  expect(MIN_TRIGGER_TOKENS).toBe(50000)
  expect(effectiveTrigger(DEFAULT_SETTINGS, 100000, true)).toBe(MIN_TRIGGER_TOKENS)
  expect(effectiveTrigger(DEFAULT_SETTINGS, 10000, true)).toBe(MIN_TRIGGER_TOKENS)
})

test('settingsFrom: a missing or empty options object is the defaults', () => {
  expect(settingsFrom({})).toEqual(DEFAULT_SETTINGS)
  expect(settingsFrom(undefined)).toEqual(DEFAULT_SETTINGS)
  expect(settingsFrom(null)).toEqual(DEFAULT_SETTINGS)
  expect(settingsFrom('auto')).toEqual(DEFAULT_SETTINGS)
})

test('settingsFrom: valid values are kept', () => {
  expect(
    settingsFrom({ autoCheckpointTokens: 300000, autoCheckpointAllowance: 50000, autoCheckpointMode: 'click-only' }),
  ).toEqual({ thresholdTokens: 300000, allowanceTokens: 50000, mode: 'click-only' })
  expect(settingsFrom({ autoCheckpointMode: 'off' }).mode).toBe('off')
})

test('settingsFrom: malformed or out-of-range values take their defaults', () => {
  expect(settingsFrom({ autoCheckpointTokens: 49999 }).thresholdTokens).toBe(500000)
  expect(settingsFrom({ autoCheckpointTokens: 2000001 }).thresholdTokens).toBe(500000)
  expect(settingsFrom({ autoCheckpointTokens: '300000' }).thresholdTokens).toBe(500000)
  expect(settingsFrom({ autoCheckpointTokens: Number.NaN }).thresholdTokens).toBe(500000)
  expect(settingsFrom({ autoCheckpointAllowance: -1 }).allowanceTokens).toBe(120000)
  expect(settingsFrom({ autoCheckpointAllowance: 1000001 }).allowanceTokens).toBe(120000)
  expect(settingsFrom({ autoCheckpointMode: 'sometimes' }).mode).toBe('auto')
  expect(settingsFrom({ autoCheckpointMode: 3 }).mode).toBe('auto')
})

test('settingsFrom: the allowance is clamped below the threshold', () => {
  const settings = settingsFrom({ autoCheckpointTokens: 100000, autoCheckpointAllowance: 900000 })

  expect(settings.allowanceTokens).toBe(99999)
  expect(settings.allowanceTokens).toBeLessThan(settings.thresholdTokens)
  expect(settingsFrom({ autoCheckpointAllowance: 0 }).allowanceTokens).toBe(0)
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
