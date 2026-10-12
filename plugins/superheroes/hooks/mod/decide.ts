// The decision logic of the automatic checkpoint (#1814 layer 2): pure, no engine
// imports, and the one home of every threshold rule. register.ts reads the engine
// and acts on what this answers.

export type Mode = 'auto' | 'click-only' | 'off'

export type Settings = { thresholdTokens: number; allowanceTokens: number; mode: Mode }

export const DEFAULT_SETTINGS: Settings = {
  thresholdTokens: 500000,
  allowanceTokens: 120000,
  mode: 'auto',
}

// How far below the trigger the heads-up band appears, and how far past the
// current fill a Snooze pushes the next automatic run.
export const HEADS_UP_TOKENS = 50000
export const SNOOZE_STEP_TOKENS = 100000

// The lowest trigger there is, whatever the settings or the window say: a tiny
// window must not fire a checkpoint on every turn.
export const MIN_TRIGGER_TOKENS = 50000

// The ranges the manifest's `userConfig` declares; a value outside one counts as unset.
const THRESHOLD_RANGE = [50000, 2000000] as const
const ALLOWANCE_RANGE = [0, 1000000] as const

const MODES: readonly Mode[] = ['auto', 'click-only', 'off']

const inRange = (value: unknown, [min, max]: readonly [number, number]): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max

// Coerces the plugin's options to settings: anything missing, malformed or out of
// range takes its default; the allowance is clamped into [0, threshold).
export const settingsFrom = (options: unknown): Settings => {
  const raw: Record<string, unknown> =
    typeof options === 'object' && options !== null ? { ...options } : {}
  const thresholdTokens = inRange(raw.autoCheckpointTokens, THRESHOLD_RANGE)
    ? raw.autoCheckpointTokens
    : DEFAULT_SETTINGS.thresholdTokens
  const allowance = inRange(raw.autoCheckpointAllowance, ALLOWANCE_RANGE)
    ? raw.autoCheckpointAllowance
    : DEFAULT_SETTINGS.allowanceTokens
  const mode = MODES.find(m => m === raw.autoCheckpointMode) ?? DEFAULT_SETTINGS.mode

  return { thresholdTokens, allowanceTokens: Math.min(allowance, thresholdTokens - 1), mode }
}

// The fill at which the checkpoint runs. With the harness's own auto-compaction on
// and its threshold known, the checkpoint must land an allowance before it:
// min(threshold, autoCompactThreshold - allowance). Floored at MIN_TRIGGER_TOKENS.
export const effectiveTrigger = (
  settings: Settings,
  autoCompactThreshold: number | undefined,
  isAutoCompactEnabled: boolean,
): number => {
  const window =
    isAutoCompactEnabled && autoCompactThreshold !== undefined && Number.isFinite(autoCompactThreshold)
      ? autoCompactThreshold - settings.allowanceTokens
      : Infinity

  return Math.max(MIN_TRIGGER_TOKENS, Math.min(settings.thresholdTokens, window))
}

export type DecideInput = {
  tokens: number
  trigger: number
  mode: Mode
  isIdle: boolean
  isInteractive: boolean
  isRunning: boolean
  snoozeUntilTokens: number | null
}

export type Decision = { showBand: boolean; fire: boolean; reason: string }

// `reason` names the gate that decided: off, running, below-heads-up, click-only,
// headless, busy, below-trigger, snoozed, or fire.
export const decide = (input: DecideInput): Decision => {
  const { tokens, trigger, mode, isIdle, isInteractive, isRunning, snoozeUntilTokens } = input

  if (mode === 'off') {
    return { showBand: false, fire: false, reason: 'off' }
  }
  if (isRunning) {
    return { showBand: false, fire: false, reason: 'running' }
  }
  if (tokens < trigger - HEADS_UP_TOKENS) {
    return { showBand: false, fire: false, reason: 'below-heads-up' }
  }

  const band = (fire: boolean, reason: string): Decision => ({ showBand: true, fire, reason })

  if (mode !== 'auto') {
    return band(false, 'click-only')
  }
  if (!isInteractive) {
    return band(false, 'headless')
  }
  if (!isIdle) {
    return band(false, 'busy')
  }
  if (tokens < trigger) {
    return band(false, 'below-trigger')
  }
  if (tokens < (snoozeUntilTokens ?? 0)) {
    return band(false, 'snoozed')
  }

  return band(true, 'fire')
}

export const snooze = (tokens: number): number => tokens + SNOOZE_STEP_TOKENS

// The changed-file gate: a checkpoint counts only when the notes file now holds
// text that differs from what it held before.
export const notesChanged = (before: string | null, after: string | null): boolean =>
  typeof after === 'string' && after !== '' && after !== before
