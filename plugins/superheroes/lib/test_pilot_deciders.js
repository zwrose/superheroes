// plugins/superheroes/lib/test_pilot_deciders.js
// Pure test-pilot decision helpers — no IO, no agent, no Python.
const { normalizeTitle } = require('./circuit_breaker.js')
const prCommentScrub = require('./pr_comment_scrub.js')

const WEB_KEYS = new Set([
  'user_facing', 'userFacing', 'browser', 'route', 'routes', 'page', 'pages', 'frontend',
  'baseUrl', 'base_url', 'dev-server', 'dev_server', 'devServer', 'runnable_web', 'runnableWeb', 'web',
])
const PROFILE_WEB_KEYS = new Set([...WEB_KEYS].filter((k) => k !== 'baseUrl' && k !== 'base_url'))
const NO_BROWSER_KEYS = {
  docs_only: 'docs-only',
  docsOnly: 'docs-only',
  cli_only: 'CLI-only',
  cliOnly: 'CLI-only',
  library_only: 'library-only',
  libraryOnly: 'library-only',
  internal_only: 'internal-only',
  internalOnly: 'internal-only',
}
const DOC_EXTS = new Set(['.md', '.mdx', '.rst', '.txt', '.adoc'])
const CLI_PATH_PARTS = ['/cli/', '/commands/', '/bin/']
const LIB_PATH_PARTS = ['/lib/', '/src/lib/', '/pkg/']
const INTERNAL_PATH_PARTS = ['/internal/', '/private/']
const WEB_EXTS = new Set(['.html', '.css', '.jsx', '.tsx', '.vue', '.svelte'])
const WEB_PATH_PARTS = ['/web/', '/frontend/', '/pages/', '/routes/', '/app/', '/public/']
const BROWSER_SOURCES = new Set(['browser', 'playwright', 'chrome-devtools', 'devtools'])
const DEFAULT_LIMITS = {
  planRecords: 20,
  browserSteps: 80,
  browserPasses: 4,
  browserFixBatches: 3,
  uniqueScenarios: 40,
  seedOperations: 120,
  elapsedSeconds: 3600,
  renderedBytes: 200000,
}
const MAX_BROWSER_FIX_BATCHES = 3
const PATHISH = /(?:\/private)?\/tmp\/\S+|\/[\w./-]+(?::\d+)?/g
const LINE = /:\d+\b/g

function verdict(v, reason) {
  return { verdict: v, reason }
}

function isObject(value) {
  return value === undefined || value === null || (typeof value === 'object' && !Array.isArray(value))
}

function* walk(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    for (const [key, nested] of Object.entries(value)) {
      yield [key, nested]
      yield* walk(nested)
    }
  } else if (Array.isArray(value)) {
    for (const nested of value) yield [null, nested]
  }
}

function truthySignal(obj, keys) {
  if (!obj || typeof obj !== 'object') return null
  for (const [key, value] of walk(obj)) {
    if (keys.has(key) && value !== false && value !== null && value !== '' && !(Array.isArray(value) && value.length === 0) && !(value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 0)) {
      return key
    }
  }
  return null
}

function files(diff) {
  if (!diff || typeof diff !== 'object') return []
  const list = diff.files || diff.paths || diff.changed_files
  return Array.isArray(list) && list.every((p) => typeof p === 'string') ? list : []
}

function ext(path) {
  const base = path.split('/').pop()
  if (!base.includes('.')) return ''
  return `.${base.split('.').pop().toLowerCase()}`
}

function docsOnly(list) {
  return list.length > 0 && list.every((path) => path.startsWith('docs/') || path.startsWith('documentation/') || DOC_EXTS.has(ext(path)))
}

function pathSignal(list, parts, exts) {
  const extensions = exts || new Set()
  return list.some((path) => {
    const normalized = `/${path.replace(/^\/+|\/+$/g, '')}`
    return parts.some((part) => normalized.includes(part)) || extensions.has(ext(path))
  })
}

function webPathSignal(list) {
  return list.some((path) => {
    const normalized = `/${path.replace(/^\/+|\/+$/g, '')}`
    if (WEB_PATH_PARTS.some((part) => normalized.includes(part))) return true
    return WEB_EXTS.has(ext(path)) && !pathSignal([path], [...CLI_PATH_PARTS, ...LIB_PATH_PARTS, ...INTERNAL_PATH_PARTS])
  })
}

function planFailed(planResult) {
  if (planResult == null) return null
  if (typeof planResult !== 'object') return 'malformed plan result'
  if (planResult.ok === false || planResult.status === 'failed' || planResult.status === 'error') {
    return String(planResult.reason || 'plan derivation failed')
  }
  return null
}

function planEmptyApplicable(planResult) {
  if (!planResult || typeof planResult !== 'object') return false
  const applicable = planResult.applicable === true || planResult.verdict === 'applicable'
  const steps = planResult.steps
  return applicable && Array.isArray(steps) && steps.length === 0
}

function missingRequiredSetup(detectors, profile) {
  let required = []
  if (detectors && typeof detectors === 'object') {
    required = detectors.requires_setup || detectors.required_setup || []
  }
  if (typeof required === 'string') required = [required]
  if (!Array.isArray(required)) return []
  profile = profile && typeof profile === 'object' ? profile : {}
  const missing = []
  for (const key of required) {
    if (typeof key !== 'string') continue
    const val = profile[key]
    if (val == null || val === '' || (Array.isArray(val) && val.length === 0) || (val && typeof val === 'object' && !Array.isArray(val) && Object.keys(val).length === 0)) {
      missing.push(key)
    }
  }
  return missing
}

function coerceJsonObject(value) {
  if (typeof value !== 'string') return value
  try {
    const parsed = JSON.parse(value)
    if (parsed === null || (parsed && typeof parsed === 'object' && !Array.isArray(parsed))) return parsed
  } catch (_e) { /* keep string */ }
  return value
}

function applicabilityDecision(diff, detectors, profile, planResult) {
  if (planResult === undefined) planResult = null
  diff = coerceJsonObject(diff)
  detectors = coerceJsonObject(detectors)
  profile = coerceJsonObject(profile)
  planResult = coerceJsonObject(planResult)
  if (![diff, detectors, profile, planResult].every(isObject)) {
    return verdict('park', 'malformed inputs')
  }
  diff = diff || {}
  detectors = detectors || {}
  profile = profile || {}
  const failed = planFailed(planResult)
  if (failed) return verdict('park', failed)
  if (planEmptyApplicable(planResult)) return verdict('park', 'empty applicable plan derivation')

  const changed = files(diff)
  let webSignal = truthySignal(detectors, WEB_KEYS) || truthySignal(profile, PROFILE_WEB_KEYS) || truthySignal(planResult, WEB_KEYS)
  if (!webSignal && webPathSignal(changed)) webSignal = 'frontend path'

  if (webSignal) {
    const missing = missingRequiredSetup(detectors, profile)
    if (missing.length) return verdict('park', `missing required setup: ${missing.join(', ')}`)
    return verdict('applicable', `browser/user-facing signal: ${webSignal}`)
  }

  for (const [key, label] of Object.entries(NO_BROWSER_KEYS)) {
    if (detectors[key] === true) return verdict('not_applicable', `${label} change with no browser signal`)
  }
  if (docsOnly(changed)) return verdict('not_applicable', 'docs-only change with no browser signal')
  if (pathSignal(changed, CLI_PATH_PARTS)) return verdict('not_applicable', 'CLI-only change with no browser signal')
  if (pathSignal(changed, LIB_PATH_PARTS)) return verdict('not_applicable', 'library-only change with no browser signal')
  if (pathSignal(changed, INTERNAL_PATH_PARTS)) return verdict('not_applicable', 'internal-only change with no browser signal')
  return verdict('park', 'uncertain applicability')
}

function parkAggregation(reason) {
  return { action: 'park', reason }
}

function browserSource(raw) {
  return raw.source || raw.evidenceSource || raw.evidence_source
}

function isBrowserSource(value) {
  if (typeof value !== 'string') return false
  const lower = value.toLowerCase()
  return BROWSER_SOURCES.has(lower) || lower.startsWith('browser:')
}

function limit(byteLimits, key, fallback) {
  if (!byteLimits || typeof byteLimits !== 'object') return fallback
  const aliases = {
    diagnostics: ['diagnostics', 'diagnosticBytes', 'diagnosticsBytes'],
    renderedBytes: ['renderedBytes', 'rendered', 'total'],
  }
  let value
  for (const candidate of aliases[key] || [key]) {
    if (Object.prototype.hasOwnProperty.call(byteLimits, candidate)) {
      value = byteLimits[candidate]
      break
    }
  }
  return typeof value === 'number' && value >= 0 ? value : fallback
}

function byteLength(text) {
  if (typeof Buffer !== 'undefined') return Buffer.byteLength(text, 'utf8')
  return new TextEncoder().encode(text).length
}

function scrubText(text, scrubber, maxBytes) {
  try {
    const out = scrubber(String(text || ''))
    if (byteLength(out) > maxBytes) return [null, 'diagnostics exceed byte limit']
    return [out, null]
  } catch (err) {
    return [null, `scrub failed: ${err && err.message ? err.message : err}`]
  }
}

function aggregateResults(rawResults, opts) {
  opts = opts || {}
  const scrubber = typeof opts.scrubber === 'function' ? opts.scrubber : prCommentScrub.scrub
  const byteLimits = opts.byteLimits || {}
  if (!rawResults || typeof rawResults !== 'object') return parkAggregation('browser results must be a JSON object')
  if (!isBrowserSource(browserSource(rawResults))) return parkAggregation('browser-derived evidence/source is required')

  const diagnosticLimit = limit(byteLimits, 'diagnostics', 20000)
  const records = []
  const steps = rawResults.steps || rawResults.records || []
  for (const step of steps) {
    if (!step || typeof step !== 'object') continue
    const [notes, noteProblem] = scrubText(step.notes || step.diagnostics || '', scrubber, diagnosticLimit)
    if (noteProblem) return parkAggregation(noteProblem)
    const stepId = step.id || step.stepId || step.step_id
    if (!stepId) return parkAggregation('browser result record is missing a step id')
    const record = {
      stepId: String(stepId),
      status: step.status || step.result || 'unknown',
      notes,
      browserExecuted: true,
    }
    const failureType = step.failureType || step.failure_type || step.kind
    if (failureType != null) record.failureType = String(failureType)
    for (const field of ['summary', 'message']) {
      if (step[field]) {
        const [text, problem] = scrubText(step[field], scrubber, diagnosticLimit)
        if (problem) return parkAggregation(problem)
        record[field] = text
      }
    }
    records.push(record)
  }

  const result = {
    action: 'aggregated',
    source: browserSource(rawResults),
    records,
    coverageRationale: rawResults.coverageRationale || rawResults.coverage_rationale,
  }
  const fixes = []
  for (const fix of rawResults.fixes || []) {
    if (fix && typeof fix === 'object') {
      fixes.push({ sha: fix.sha || fix.commit, summary: scrubber(String(fix.summary || '')) })
    }
  }
  if (fixes.length) result.fixes = fixes
  const renderedLimit = limit(byteLimits, 'renderedBytes', 200000)
  if (byteLength(JSON.stringify(result)) > renderedLimit) {
    return parkAggregation('rendered output exceeds byte limit')
  }
  return result
}

function withinBudget() {
  return { action: 'within_budget' }
}

function parkBudget(reason) {
  return { action: 'park_budget_exceeded', reason }
}

function validNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
}

function validateMapping(obj, label) {
  if (!obj || typeof obj !== 'object') return `${label} must be a JSON object`
  for (const [key, value] of Object.entries(obj)) {
    if (!validNumber(value)) return `malformed numeric value for ${label}.${key}`
  }
  return null
}

function budgetDecision(counts, limits) {
  const problem = validateMapping(counts, 'counts')
  if (problem) return parkBudget(problem)
  const merged = Object.assign({}, DEFAULT_LIMITS)
  if (limits != null) {
    const limitsProblem = validateMapping(limits, 'limits')
    if (limitsProblem) return parkBudget(limitsProblem)
    Object.assign(merged, limits)
  }
  for (const [key, max] of Object.entries(merged)) {
    const value = Object.prototype.hasOwnProperty.call(counts, key) ? counts[key] : 0
    if (value > max) return parkBudget(`${key} exceeded budget: ${value} > ${max}`)
  }
  return withinBudget()
}

function fixBatch(entry) {
  return entry && typeof entry === 'object' && (entry.type === 'browser_fix_batch' || entry.type === 'fix_batch')
}

function fixBatches(history) {
  return Array.isArray(history) ? history.filter(fixBatch) : []
}

function passSteps(passResult) {
  if (!passResult || typeof passResult !== 'object') return []
  if (Array.isArray(passResult.steps)) return passResult.steps
  if (Array.isArray(passResult.records)) return passResult.records
  return []
}

function stepId(step) {
  if (!step || typeof step !== 'object') return null
  const value = step.id || step.stepId || step.step_id
  return value != null && value !== '' ? String(value) : null
}

function failedSteps(passResult) {
  const failed = []
  for (const step of passSteps(passResult)) {
    if (!step || typeof step !== 'object') continue
    const status = step.status || step.result
    if ((status === 'failed' || status === 'fail') && stepId(step)) failed.push(step)
  }
  return failed
}

function appBug(step) {
  const kind = step.failureType || step.failure_type || step.kind
  return kind === undefined || kind === null || ['app_bug', 'app-bug', 'application'].includes(kind)
}

function failedStepIds(passResult) {
  return failedSteps(passResult).map(stepId).filter(Boolean)
}

function summaryForFailures(failed) {
  return `Fix browser app failures: ${failed.map(stepId).join(', ')}`
}

function scrubSummary(summary) {
  return normalizeTitle(String(summary || '').replace(PATHISH, ' ').replace(LINE, ' '))
}

function statusMap(value) {
  return value && typeof value === 'object' ? value : {}
}

function madeProgress(batch) {
  const before = statusMap(batch.before)
  const after = statusMap(batch.after)
  return Object.entries(before).some(([id, beforeStatus]) => (beforeStatus === 'failed' || beforeStatus === 'fail') && (after[id] === 'passed' || after[id] === 'pass'))
}

function lastTwoSameWithoutProgress(batches) {
  if (batches.length < 2) return null
  const prev = batches[batches.length - 2]
  const latest = batches[batches.length - 1]
  const prevSummary = scrubSummary(prev.summary)
  const latestSummary = scrubSummary(latest.summary)
  if (prevSummary && prevSummary === latestSummary && !madeProgress(prev) && !madeProgress(latest)) {
    return latestSummary
  }
  return null
}

function affectedStepIds(changedFiles, dependencyMap) {
  if (!dependencyMap || typeof dependencyMap !== 'object') return null
  const affected = new Set()
  for (const path of changedFiles || []) {
    const mapped = dependencyMap[path]
    if (!Array.isArray(mapped)) return null
    for (const id of mapped) {
      if (id != null && id !== '') affected.add(String(id))
    }
  }
  return [...affected].sort()
}

function rerunDecision(passResult, changedFiles, dependencyMap) {
  const failedIds = failedStepIds(passResult)
  const affectedIds = affectedStepIds(changedFiles, dependencyMap)
  if (affectedIds == null) return { action: 'rerun_all', failedStepIds: failedIds }
  return {
    action: 'rerun_subset',
    stepIds: [...new Set([...failedIds, ...affectedIds])].sort(),
    failedStepIds: failedIds,
    affectedStepIds: affectedIds,
  }
}

function retryDecisionFromFacts(passResult, history, changedFiles, dependencyMap) {
  const batches = fixBatches(history)
  const failed = failedSteps(passResult)

  if (changedFiles != null && batches.length) {
    return rerunDecision(passResult, changedFiles, dependencyMap)
  }

  if (failed.length && batches.length >= MAX_BROWSER_FIX_BATCHES) {
    return {
      action: 'park_cap_reached',
      reason: 'reached 3 browser fix batches with failed browser steps remaining',
    }
  }

  const noProgress = lastTwoSameWithoutProgress(batches)
  if (failed.length && noProgress) {
    return {
      action: 'park_no_progress',
      reason: `two consecutive browser fix batches made no progress: ${noProgress}`,
    }
  }

  const appFailures = failed.filter(appBug)
  if (appFailures.length) {
    return {
      action: 'fix_batch',
      failedStepIds: appFailures.map(stepId),
      summary: summaryForFailures(appFailures),
    }
  }

  if (failed.length) {
    return {
      action: 'park_unclassified_failure',
      reason: 'one or more browser failures are not app-bug failures',
    }
  }

  return { action: 'passed' }
}

module.exports = {
  applicabilityDecision,
  aggregateResults,
  budgetDecision,
  retryDecisionFromFacts,
}
