// engine_pref.js — twin of engine_pref.resolve_engine / resolve_effort.
// Pure + deterministic engine-preference resolver. Fail-OPEN to 'claude'.

const ENGINES = ['claude', 'codex', 'cursor']
const DEFAULT_STALL_LIMIT_SECONDS = 300

// #309 role-appropriate dispatch ceilings (owner policy: HIGH ceilings + monitors, never borderline
// limits). Before this, EVERY external dispatch inherited the bare 300s DEFAULT as a pure wall-clock
// kill, SIGALRMing legitimately-working builds at 5 minutes (a test-first build cannot reliably
// finish that fast). WRITE roles (build/fix/author-plan) get a high ceiling; READ roles (review) a
// moderate one. These are CEILINGS, not expected durations — the honest fall-open still fires the
// instant the CLI dies. The high ceiling is PAIRED with a byte-activity stall monitor (resolveIdle
// below + engine_dispatch's shell watchdog): the ceiling bounds worst case, the monitor kills a
// genuinely-wedged (no-output) CLI far sooner. Both limits are ALWAYS armed; monitor ≤ ceiling.
const WRITE_TIMEOUT_SECONDS = 2400   // build/fix/author-plan: a full test-first build (write→run→impl→run→commit)
const READ_TIMEOUT_SECONDS = 900     // review/review-deep: a read-only review pass
const _ROLE_TIMEOUT = { build: WRITE_TIMEOUT_SECONDS, fix: WRITE_TIMEOUT_SECONDS,
  'author-plan': WRITE_TIMEOUT_SECONDS, review: READ_TIMEOUT_SECONDS, 'review-deep': READ_TIMEOUT_SECONDS }

// #309 byte-activity stall thresholds — the monitor half of the ceiling+monitor pair. A dispatch that
// emits NO output bytes (stdout+stderr) for this many seconds is a wedged CLI, not a slow one, and is
// killed well before the ceiling. Set FAR above the observed inter-chunk gaps of a working engine
// (2026-07-09 receipts: codex ≤ ~8s between chunks, cursor ≤ ~4s), so a legitimately-working CLI is
// never false-killed. WRITE roles get the longer idle window (a builder can think between file
// writes); READ roles the shorter one (a reviewer streams findings steadily). Both are well under
// their role ceiling (600 < 2400, 300 < 900), so the monitor always fires first on a true stall.
const WRITE_IDLE_SECONDS = 600   // build/fix/author-plan: no-output-bytes stall kill
const READ_IDLE_SECONDS = 300    // review/review-deep: no-output-bytes stall kill
const DEFAULT_IDLE_SECONDS = 300 // no-role fallback (conservative read-level idle)
const _ROLE_IDLE = { build: WRITE_IDLE_SECONDS, fix: WRITE_IDLE_SECONDS,
  'author-plan': WRITE_IDLE_SECONDS, review: READ_IDLE_SECONDS, 'review-deep': READ_IDLE_SECONDS }

// `author-plan` (the front-half plan-author leaf) reads its OWN key — plan authoring routes
// independently of review/build; tasks authoring has no key on purpose and always runs native.
const _ROLE_KEY = { review: 'reviewer', build: 'implementation', fix: 'implementation',
  'author-plan': 'planAuthor' }
// Depth-aware review: deep reviewers (security/architecture — reviewer-deep tier) -> 'review-deep'
// (xhigh); regular review -> 'review' (high). Mirrors engine_pref.py._CODEX_EFFORT.
const _CODEX_EFFORT = { review: 'high', 'review-deep': 'xhigh', build: 'high', fix: 'low',
  'author-plan': 'xhigh' }
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

// Twin of resolve_timeout: the finite UFR-5 stall limit in seconds. Resolution order (#309): a valid
// positive int owner override (`overrides.timeout`) wins over everything; else the role-appropriate
// ceiling for `roleKind` (WRITE_TIMEOUT_SECONDS / READ_TIMEOUT_SECONDS); else the legacy
// DEFAULT_STALL_LIMIT_SECONDS when no role is supplied (back-compat — engine_authz's throwaway probe
// and any pre-#309 caller keep the 300s default). bool is excluded (mirror the Python guard's intent:
// only a real positive integer number is honored). Always returns a finite positive int; never throws.
function resolveTimeout(overrides, roleKind) {
  if (overrides && typeof overrides === 'object' && !Array.isArray(overrides) && hasOwn(overrides, 'timeout')) {
    const v = overrides.timeout
    if (typeof v === 'number' && Number.isInteger(v) && v > 0) return v
  }
  if (roleKind != null && hasOwn(_ROLE_TIMEOUT, roleKind)) return _ROLE_TIMEOUT[roleKind]
  return DEFAULT_STALL_LIMIT_SECONDS
}

// Twin of resolve_idle: the #309 byte-activity stall threshold in seconds — the monitor paired with
// resolveTimeout's ceiling. Resolution mirrors resolveTimeout: a valid positive-int owner override
// (`overrides.idleTimeout`) wins; else the role-appropriate idle window (WRITE_IDLE / READ_IDLE); else
// DEFAULT_IDLE_SECONDS for an unknown/absent role. bool is excluded (an int subclass, same guard as
// resolveTimeout). Always returns a finite positive int; never throws. The dispatch clamps this to the
// ceiling (monitor ≤ ceiling) and an override never disables the ceiling — both limits stay armed.
function resolveIdle(overrides, roleKind) {
  if (overrides && typeof overrides === 'object' && !Array.isArray(overrides) && hasOwn(overrides, 'idleTimeout')) {
    const v = overrides.idleTimeout
    if (typeof v === 'number' && Number.isInteger(v) && v > 0) return v
  }
  if (roleKind != null && hasOwn(_ROLE_IDLE, roleKind)) return _ROLE_IDLE[roleKind]
  return DEFAULT_IDLE_SECONDS
}

module.exports = { resolveEngine, resolveEffort, resolveTimeout, resolveIdle, ENGINES,
  DEFAULT_STALL_LIMIT_SECONDS, WRITE_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS,
  WRITE_IDLE_SECONDS, READ_IDLE_SECONDS, DEFAULT_IDLE_SECONDS }
