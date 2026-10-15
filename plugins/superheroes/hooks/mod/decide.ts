// The decision logic of the automatic checkpoint (#1814 layer 2): pure, no engine
// imports, and the one home of every threshold rule. register.ts reads the engine
// and acts on what this answers.

// The manifest's `userConfig.autoCheckpointMode.options` is the roster of modes; the code
// names only the two whose behavior it implements, and any other valid mode is band-only.
// These spellings are owners' saved setting values, fixed outside the repository: the
// CONVENTIONS §11.3 exception.
export const AUTO_MODE = 'auto'
export const OFF_MODE = 'off'

export type Settings = { thresholdTokens: number; allowanceTokens: number; mode: string }

// How far below the trigger the heads-up band appears, and how far past the
// current fill a Snooze pushes the next automatic run.
export const HEADS_UP_TOKENS = 50000
export const SNOOZE_STEP_TOKENS = 100000

// The lowest trigger there is, whatever the settings or the window say: a tiny
// window must not fire a checkpoint on every turn.
export const MIN_TRIGGER_TOKENS = 50000

type Spec = { default?: unknown; min?: unknown; max?: unknown; options?: unknown }

const asRecord = (value: unknown): Record<string, unknown> =>
  typeof value === 'object' && value !== null ? { ...value } : {}

const specOf = (schema: unknown, key: string): Spec => asRecord(asRecord(schema)[key])

// The setting's number: the raw value when it lies in the spec's [min, max], else the
// spec's default; null when the spec itself is no usable number setting.
const numberSetting = (raw: unknown, { default: dflt, min, max }: Spec): number | null => {
  const fits = (v: unknown): v is number =>
    typeof v === 'number' && typeof min === 'number' && typeof max === 'number' && v >= min && v <= max

  return fits(raw) ? raw : fits(dflt) ? dflt : null
}

// Coerces the plugin's options to settings. The manifest's `userConfig` (the parsed
// object, passed as `schema`) is the one home of defaults, bounds and modes: anything
// missing, malformed or out of range takes its default; the allowance is kept as is
// (headroom before the harness compacts, not a share of the threshold). Null when the schema cannot answer: the caller then runs nothing.
export const settingsFrom = (options: unknown, schema: unknown): Settings | null => {
  const raw = asRecord(options)
  const thresholdTokens = numberSetting(raw.autoCheckpointTokens, specOf(schema, 'autoCheckpointTokens'))
  const allowance = numberSetting(raw.autoCheckpointAllowance, specOf(schema, 'autoCheckpointAllowance'))
  const { default: dflt, options: modes } = specOf(schema, 'autoCheckpointMode')
  const known = Array.isArray(modes) ? (modes as unknown[]) : []
  const mode = known.includes(raw.autoCheckpointMode) ? raw.autoCheckpointMode : dflt

  if (thresholdTokens === null || allowance === null || !known.includes(mode)) {
    return null
  }

  return { thresholdTokens, allowanceTokens: allowance, mode: mode as string }
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

// The surface of the desktop app, whose Code tab hosts the session as an SDK host (so
// `session.start` reports it not interactive): its presence on the roster is attendance.
export const DESKTOP_SURFACE = 'desktop'

// bite-proof axis: a non-interactive session counts as attended only with 'desktop' on the roster
export const isAttended = (isInteractive: boolean, surfaces: readonly unknown[] | null): boolean =>
  isInteractive === true || (Array.isArray(surfaces) && surfaces.includes(DESKTOP_SURFACE))

export type DecideInput = {
  tokens: number
  trigger: number
  mode: string
  isIdle: boolean
  isAttended: boolean
  isRunning: boolean
  snoozeUntilTokens: number | null
}

export type Decision = { showBand: boolean; fire: boolean; reason: string }

// `reason` names the gate that decided: off, headless (no person attached: no band and no
// run, in every mode), running, below-heads-up, click-only, busy, below-trigger, snoozed,
// or fire.
export const decide = (input: DecideInput): Decision => {
  const { tokens, trigger, mode, isIdle, isRunning, snoozeUntilTokens } = input

  if (mode === OFF_MODE) {
    return { showBand: false, fire: false, reason: 'off' }
  }
  if (!input.isAttended) {
    return { showBand: false, fire: false, reason: 'headless' }
  }
  if (isRunning) {
    return { showBand: false, fire: false, reason: 'running' }
  }
  if (tokens < trigger - HEADS_UP_TOKENS) {
    return { showBand: false, fire: false, reason: 'below-heads-up' }
  }

  const band = (fire: boolean, reason: string): Decision => ({ showBand: true, fire, reason })

  if (mode !== AUTO_MODE) {
    return tokens < (snoozeUntilTokens ?? 0)
      ? { showBand: false, fire: false, reason: 'snoozed' }
      : band(false, 'click-only')
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

// Where an automatic re-arm waits for: a step past the fill, but never beyond the middle of
// the headroom left before the harness compacts (`autoCompactThreshold`: known only while its
// auto-compact is on), so a checkpoint still runs first. The owner's Snooze keeps `snooze`.
export const rearmAt = (fill: number, autoCompactThreshold: number | undefined): number =>
  autoCompactThreshold !== undefined && autoCompactThreshold > fill
    ? Math.min(snooze(fill), fill + Math.max(1, Math.floor((autoCompactThreshold - fill) / 2)))
    : snooze(fill)

// The changed-file gate: a checkpoint counts only when the notes file now holds
// text that differs from what it held before.
export const notesChanged = (before: string | null, after: string | null): boolean =>
  typeof after === 'string' && after !== '' && after !== before
