// engine_pref.js — twin of engine_pref.resolve_engine / resolve_effort.
// Pure + deterministic engine-preference resolver. Fail-OPEN to 'claude'.

const ENGINES = ['claude', 'codex', 'cursor']
const DEFAULT_STALL_LIMIT_SECONDS = 300

const _ROLE_KEY = { review: 'reviewer', build: 'implementation', fix: 'implementation' }
const _CODEX_EFFORT = { review: 'high', build: 'high', fix: 'low' }
const _CURSOR_EFFORT = 'composer'

// Own-key membership (mirror model_tier.js): JS `in`/bracket walk the prototype chain,
// so a prototype-named engine/role ('constructor', 'toString') must not drift the result.
function hasOwn(o, k) {
  return Object.prototype.hasOwnProperty.call(o, k)
}

function resolveEngine(roleKind, prefs) {
  if (!hasOwn(_ROLE_KEY, roleKind)) return 'claude'
  const key = _ROLE_KEY[roleKind]
  if (!prefs || typeof prefs !== 'object' || Array.isArray(prefs)) return 'claude'
  if (!hasOwn(prefs, key)) return 'claude'
  const v = prefs[key]
  if (typeof v === 'string' && ENGINES.indexOf(v) !== -1) return v
  return 'claude'
}

function resolveEffort(engine, roleKind, overrides) {
  let def
  if (engine === 'codex') def = hasOwn(_CODEX_EFFORT, roleKind) ? _CODEX_EFFORT[roleKind] : 'high'
  else if (engine === 'cursor') def = _CURSOR_EFFORT
  else return null // claude or unknown engine
  if (overrides && typeof overrides === 'object' && !Array.isArray(overrides) && hasOwn(overrides, roleKind)) {
    const v = overrides[roleKind]
    if (typeof v === 'string' && v.trim()) return v.trim()
  }
  return def
}

// Twin of resolve_timeout: the finite UFR-5 stall limit. A valid positive int override wins; else the
// finite default. bool is excluded (JS has no int/bool subtype trap, but mirror the Python guard's intent:
// only a real positive integer number is honored). Always returns a finite positive int; never throws.
function resolveTimeout(overrides) {
  if (overrides && typeof overrides === 'object' && !Array.isArray(overrides) && hasOwn(overrides, 'timeout')) {
    const v = overrides.timeout
    if (typeof v === 'number' && Number.isInteger(v) && v > 0) return v
  }
  return DEFAULT_STALL_LIMIT_SECONDS
}

module.exports = { resolveEngine, resolveEffort, resolveTimeout, ENGINES, DEFAULT_STALL_LIMIT_SECONDS }
