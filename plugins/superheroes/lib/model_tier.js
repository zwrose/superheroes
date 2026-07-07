// model_tier.js — twin of model_tier.resolve_model
// Pure + deterministic model-tier resolver: role -> model name or null.

const DEFAULT_TIERS = {
  orchestrator: null,
  reviewer: 'sonnet',
  'reviewer-deep': 'opus',
  mechanical: 'haiku',
  synthesis: 'opus',
  fixer: 'sonnet',
  author: 'opus',
  builder: 'opus',               // native build-phase implementer (a smart leaf; owner policy defaults to opus)
}

// The accepted-model set — twin of model_tier_overrides.KNOWN_MODELS (the Python validator's domain).
// This is NOT DEFAULT_TIERS' value set (which omits 'fable', a valid but non-default model). The
// freeze-consume merge boundary validates a snapshot's pinned model against this before pinning it,
// mirroring the producer's refusal posture. Drift-guarded against the Python home by test_ssot_drift.py.
const KNOWN_MODELS = ['haiku', 'sonnet', 'opus', 'fable']

const _FIXER_BY_CONTEXT = { code: 'sonnet', doc: 'opus' }

// Split roles (mirror model_tier.py._ROLE_FALLBACK): own override wins, else resolve as the base
// role. `author-plan` lets plan authoring alone move (e.g. to fable) without moving tasks authoring.
const _ROLE_FALLBACK = { 'author-plan': 'author' }

// Python `k in dict` / `dict.get(k, default)` test OWN keys only; JS `in`/bracket walk the prototype
// chain (so `'constructor' in {}` is true). Use own-key membership everywhere a twin mirrors Python
// dict membership, so a prototype-named role/identity ('constructor', 'toString', '…::hasOwnProperty')
// cannot drift the result.
function hasOwn(o, k) {
  return Object.prototype.hasOwnProperty.call(o, k)
}

function resolveModel(role, overrides, context) {
  if (hasOwn(_ROLE_FALLBACK, role)) {
    if (overrides && typeof overrides === 'object' && !Array.isArray(overrides) && hasOwn(overrides, role)) {
      const v = overrides[role]
      if (v === null) return null
      if (typeof v === 'string' && v.trim()) return v.trim()
      // malformed own-override -> resolve as the base role (fail-open)
    }
    return resolveModel(_ROLE_FALLBACK[role], overrides, context)
  }
  if (!hasOwn(DEFAULT_TIERS, role)) role = 'reviewer'   // safe capable default for an unknown role
  let def = DEFAULT_TIERS[role]
  if (role === 'fixer' && hasOwn(_FIXER_BY_CONTEXT, context)) def = _FIXER_BY_CONTEXT[context]
  if (!overrides || typeof overrides !== 'object' || Array.isArray(overrides)) return def
  if (!hasOwn(overrides, role)) return def
  const v = overrides[role]
  if (v === null) return null
  if (typeof v === 'string' && v.trim()) return v.trim()
  return def   // malformed (non-str / empty) -> default
}

module.exports = { resolveModel, DEFAULT_TIERS, KNOWN_MODELS }
