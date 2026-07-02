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

function promptFor(command) {
  return 'Run exactly this command and return ONLY stdout, unchanged:\n\n' + rootedCommand(command)
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

async function callOnce(label, command) {
  // `courier: true` marks this a dumb pipe for the bundle preamble's unconditional cheapest-model
  // pinning (same treatment as label 'exec'/'io'); the preamble strips it before the real agent().
  return currentAgent()(promptFor(command), { label, courier: true })
}

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
  let last = 'empty stdout'
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const raw = await callOnce(label, command)
    const out = stdoutOf(raw)
    if (!commandOk(raw)) {
      return { ok: false, error: out.trim() || 'command failed' }
    }
    if (out.trim() === '') {
      last = 'empty stdout'
      continue
    }
    let parsed
    try {
      parsed = JSON.parse(out)
    } catch (e) {
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
  runCourierJson,
  runCourierText,
  runCourierBatchJson,
  setCourierAgent,
}
