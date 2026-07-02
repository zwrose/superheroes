let injectedAgent = null

class CourierTransportError extends Error {
  constructor(label, reason) {
    super(`courier transport failed after retry (${label}): ${reason}`)
    this.label = label
    this.reason = reason
  }
}

function setCourierAgent(fn) { injectedAgent = fn }

function currentAgent() {
  if (injectedAgent) return injectedAgent
  const root = typeof globalThis !== 'undefined' ? globalThis : undefined
  if (root && typeof root.agent === 'function') return root.agent
  throw new Error('courier agent unavailable')
}

// FR-5 cwd-rooting: mirror showrunner's selfContained() — when __SR_ROOT is set (throwaway/live-eval
// runs), root every courier command at the repo root so `python3 plugins/superheroes/lib/...` resolves.
// Already-rooted commands (a leading `cd `) are left untouched; without __SR_ROOT this is a no-op.
function rootedCommand(command) {
  const root = (typeof globalThis !== 'undefined' && globalThis.__SR_ROOT) ? String(globalThis.__SR_ROOT) : null
  if (!root) return command
  const trimmed = String(command).replace(/^\s+/, '')
  if (trimmed.startsWith('cd ')) return command
  return "cd '" + root.replace(/'/g, "'\\''") + "' && " + command
}

// promptFor: the courier command prompt. opts.strict adds an explicit no-improvising clause for
// state-changing single-command leaves (e.g. the lease release — live 2026-07-02 the park-path
// release courier freestyled unscripted Bash and manually released the lease). The lead ALWAYS
// begins 'Run exactly this command' (targetCommandPrompt keys off that prefix) and the command
// always follows the FIRST blank line unchanged, so the strict clause rides the prefix only.
function promptFor(command, opts) {
  const lead = (opts && opts.strict)
    ? 'Run exactly this command and return ONLY stdout, unchanged. Run ONLY this single command — ' +
      'do not run any other command, do not test, verify, explore, or re-run it, just execute the ' +
      'one command below and return its stdout verbatim:'
    : 'Run exactly this command and return ONLY stdout, unchanged:'
  return lead + '\n\n' + rootedCommand(command)
}

function firstResult(raw) {
  return Array.isArray(raw) ? raw[0] : raw
}

function stdoutOf(raw) {
  const row = firstResult(raw)
  if (row == null) return ''
  if (typeof row === 'string') return row
  if (typeof row.stdout === 'string') return row.stdout
  return ''
}

function commandOk(raw) {
  const row = firstResult(raw)
  return !(row && Object.prototype.hasOwnProperty.call(row, 'ok') && row.ok === false)
}

function missingRequired(value, required) {
  for (const key of required || []) {
    if (!Object.prototype.hasOwnProperty.call(value || {}, key)) return key
  }
  return null
}

// extractJson: fence-tolerant JSON extraction — the courier twin of the exec path's
// _parseExecResult (showrunner.js). A haiku courier sometimes wraps correct output in ```json
// fences or prose (observed live 2026-07-02 on 'read startup state'; both attempts failed the
// bare JSON.parse and the run parked 'unreadable'). Candidates, in order: (a) the FIRST fenced
// block anywhere (prose-prefixed fences included), (b) the whole trimmed string, (c) each
// individual line, LAST-to-first. Each candidate: direct JSON.parse, then a brace-slice from
// first '{' to last '}' (prose around a bare object). First candidate yielding an object/array
// wins; otherwise null (the caller retries fail-closed).
//
// The per-line pass (c) handles a `side-effect && save` chain whose answer is TWO top-level JSON
// objects on two lines — the set-gate line then the save line (live 2026-07-02, persistPhase
// parked review-plan on a healthy state). Neither the whole-string parse nor the first-{…-last-}
// slice can read two objects, so fall to the lines and take the LAST parseable one (the SAVE
// result — the caller's require() then validates THAT object). Ordered AFTER the whole-string
// candidates so a single (possibly pretty-printed) object/array is parsed whole and never
// mis-sliced into one of its own inner lines (e.g. a pretty-printed array's last element).
function extractJson(text) {
  const trimmed = String(text == null ? '' : text).trim()
  const candidates = []
  const fenceMatch = trimmed.match(/```(?:[a-zA-Z0-9]+)?\s*([\s\S]*?)```/)
  if (fenceMatch) candidates.push(fenceMatch[1].trim())
  candidates.push(trimmed)
  const lines = trimmed.split('\n')
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const line = lines[i].trim()
    if (line) candidates.push(line)
  }
  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(candidate)
      if (parsed !== null && typeof parsed === 'object') return parsed
    } catch (_e1) { /* try the brace-slice fallback */ }
    const first = candidate.indexOf('{')
    const last = candidate.lastIndexOf('}')
    if (first >= 0 && last > first) {
      try {
        const sliced = JSON.parse(candidate.slice(first, last + 1))
        if (sliced !== null && typeof sliced === 'object') return sliced
      } catch (_e2) { /* try the next candidate */ }
    }
  }
  return null
}

async function callOnce(label, command, promptOpts) {
  // `courier: true` marks this a dumb pipe for the bundle preamble's unconditional cheapest-model
  // pinning (same treatment as label 'exec'/'io'); the preamble strips it before the real agent().
  return currentAgent()(promptFor(command, promptOpts), { label, courier: true })
}

// runCourierText deliberately does NOT strip fences: its payload is arbitrary text whose
// legitimate content may itself contain ``` fences — unfencing here would corrupt it. JSON
// couriers get the fence-tolerant treatment in runCourierJson (extractJson) instead.
async function runCourierText(label, command) {
  let last = 'empty stdout'
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const raw = await callOnce(label, command)
    if (!commandOk(raw)) {
      return stdoutOf(raw)
    }
    const out = stdoutOf(raw)
    if (out.trim() !== '') return out
    last = 'empty stdout'
  }
  throw new CourierTransportError(label, last)
}

async function runCourierJson(label, command, opts) {
  const options = opts || {}
  const promptOpts = options.strict ? { strict: true } : undefined
  let last = 'empty stdout'
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const raw = await callOnce(label, command, promptOpts)
    const out = stdoutOf(raw)
    if (!commandOk(raw)) {
      return { ok: false, error: out.trim() || 'command failed' }
    }
    if (out.trim() === '') {
      last = 'empty stdout'
      continue
    }
    const parsed = extractJson(out)   // fence-tolerant (see extractJson) — bare parse alone parked live runs
    if (parsed == null) {
      last = 'unparseable JSON'
      continue
    }
    if (parsed && parsed.ok === false && options.retryRealFailure === false) return parsed
    const missing = missingRequired(parsed, options.require || [])
    if (missing) {
      last = `missing required field ${missing}`
      continue
    }
    return parsed
  }
  throw new CourierTransportError(label, last)
}

async function runCourierBatchJson(label, commands, opts) {
  const joined = commands.join('\n')
  const parsed = await runCourierJson(label, joined, opts)
  return parsed
}

module.exports = {
  CourierTransportError,
  extractJson,
  runCourierJson,
  runCourierText,
  runCourierBatchJson,
  setCourierAgent,
}
