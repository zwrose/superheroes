// plugins/superheroes/lib/review_memory.js
const BLOCKING = new Set(['Critical', 'Important'])

function _norm(value) {
  return String(value || '').trim().toLowerCase().replace(/\s+/g, ' ')
}

const _MAX_TITLE = 160
const _TITLE_ELLIPSIS = '...'
function clampTitle(title) {
  if (typeof title !== 'string') return title
  if (title.length <= _MAX_TITLE) return title
  const limit = _MAX_TITLE - _TITLE_ELLIPSIS.length
  let prefix = title.slice(0, limit).replace(/[ \t\n\r\f\v]+$/, '')
  let boundary = -1
  for (const ch of [' ', '\t', '\n', '\r', '\f', '\v']) boundary = Math.max(boundary, prefix.lastIndexOf(ch))
  if (boundary > 0) prefix = prefix.slice(0, boundary).replace(/[ \t\n\r\f\v]+$/, '')
  if (!prefix) prefix = title.slice(0, limit).replace(/[ \t\n\r\f\v]+$/, '')
  return prefix + _TITLE_ELLIPSIS
}

function _titleText(finding) {
  if (!finding || typeof finding !== 'object') return ''
  return finding.title || finding.summary || ''
}

function classKey(finding) {
  finding = finding || {}
  return `${finding.dimension || ''}::${finding.taxonomy || ''}::${_norm(clampTitle(_titleText(finding)))}`
}

function canonicalClassKey(finding) {
  if (!finding || typeof finding !== 'object') return classKey({})
  if (finding.title || finding.summary || finding.dimension || finding.taxonomy) return classKey(finding)
  return finding.classKey || classKey(finding)
}

function classKeyAliases(finding) {
  const aliases = new Set([canonicalClassKey(finding)])
  if (finding && typeof finding === 'object' && finding.classKey) aliases.add(finding.classKey)
  return aliases
}


function recurrentClasses(records, coverageDecisions) {
  const covered = new Set((coverageDecisions || []).map((d) => d && d.classKey).filter(Boolean))
  const seen = Object.create(null)
  for (const rec of records || []) {
    for (const finding of (rec && rec.findings) || []) {
      if (finding.carried) continue
      if (!BLOCKING.has(finding.severity)) continue
      const key = canonicalClassKey(finding)
      let isCovered = false
      for (const alias of classKeyAliases(finding)) if (covered.has(alias)) isCovered = true
      if (isCovered) continue
      if (!seen[key]) seen[key] = new Set()
      seen[key].add(rec.round)
    }
  }
  return Object.keys(seen).sort()
    .filter((k) => seen[k].size >= 2)
    .map((k) => ({ classKey: k, rounds: Array.from(seen[k]).sort((a, b) => a - b) }))
}

function promoteRecord(record, dimensions) {
  record = record || {}
  if (record.schemaVersion === 2) return record
  const dims = {}
  for (const d of dimensions || []) dims[d] = { dimension: d, status: 'unknown' }
  return {
    schemaVersion: 2,
    round: record.round,
    kind: 'unknown',
    dimensions: dims,
    findings: Array.isArray(record.findings) ? record.findings : [],
    changedSubjects: null,
    coverageDecisions: [],
    tokenUsage: { available: false, reason: 'promoted from schema v1' },
    confirmationPending: false,
  }
}

function recordFromDimensionResults(roundNo, kind, dimensions, changedSubjects, coverageDecisions, tokenUsage, confirmationPending) {
  const findings = []
  const carriedFindings = []
  const dimensionRecords = {}
  const subjectFallback = { test: 'Test', security: 'Security', code: 'Code', architecture: 'Architecture', failure: 'Failure-Mode' }
  for (const [name, result] of Object.entries(dimensions || {})) {
    const out = Object.assign({ dimension: name, round: roundNo }, result || {})
    const current = []
    const carried = []
    const isCarried = out.status === 'skipped' || out.carriedFromRound !== undefined
    for (const raw of Array.isArray(out.findings) ? out.findings : []) {
      const item = Object.assign({ dimension: out.dimension || name }, raw)
      if (isCarried) {
        item.carried = true
        item.sourceRound = out.carriedFromRound || item.sourceRound || roundNo
        carried.push(item)
      } else {
        current.push(item)
      }
    }
    const subjects = new Set([...current, ...carried].map((f) => f.dimension).filter(Boolean))
    const fallback = subjectFallback[String(name || '').split('-')[0].toLowerCase()]
    if (fallback) subjects.add(fallback)
    out.findings = current.concat(carried)
    out.currentFindings = current
    out.carriedFindings = carried
    out.hasFindings = current.length + carried.length > 0
    out.subjects = Array.from(subjects).sort()
    dimensionRecords[name] = out
    findings.push(...current)
    carriedFindings.push(...carried)
  }
  return {
    schemaVersion: 2,
    round: roundNo,
    kind,
    dimensions: dimensionRecords,
    findings,
    carriedFindings,
    changedSubjects,
    coverageDecisions: coverageDecisions || [],
    tokenUsage: tokenUsage || { available: false, reason: 'missing' },
    confirmationPending: !!confirmationPending,
  }
}

// skeletonRecord: the JS twin of review_memory.py summarize_record — the bounded durable form
// of a round record (D3). Findings keep only identity/class/severity (title<=160); dimension
// records keep their scheduling scalars + skeleton findings. This is what persist-skeleton
// ships inline (Python re-applies summarize_record on arrival, so a drift here can widen the
// leaf payload but can never widen the on-disk contract).
const _SKELETON_FIELDS = ['file', 'line', 'title', 'severity', 'taxonomy', 'dimension',
                          'classKey', 'carried', 'sourceRound', 'synthesisUnverified']
function _skeletonFinding(finding) {
  if (!finding || typeof finding !== 'object') return {}
  const out = {}
  for (const k of _SKELETON_FIELDS) if (k in finding) out[k] = finding[k]
  if (typeof out.title === 'string') out.title = clampTitle(out.title)
  // A stored classKey is preserved verbatim (legacy unclamped-title keys must survive
  // skeletonization for classKeyAliases to match legacy coverage decisions); only a
  // key-less finding gets the canonical stamp.
  if (!('classKey' in out) && (finding.dimension || finding.taxonomy)) out.classKey = canonicalClassKey(finding)
  return out
}

function _summarizeDimension(dim) {
  if (!dim || typeof dim !== 'object') return {}
  const findings = Array.isArray(dim.findings) ? dim.findings : []
  const out = {}
  // `usage` is a small scalar object ({total,input,output}); the skeleton keeps it so a carried
  // (skipped) dimension carries its prior round's usage forward and the telemetry stays complete
  // (#211: the loop reads the carried dim from the durable skeleton, not an in-memory copy).
  for (const k of ['dimension', 'status', 'confidence', 'round', 'subjects',
                   'carriedFromRound', 'escalated', 'tier', 'usage']) if (k in dim) out[k] = dim[k]
  out.findings = findings.map(_skeletonFinding)
  out.hasFindings = findings.length > 0 || !!dim.hasFindings
  out.blockingCount = findings.filter((f) => f && typeof f === 'object' && BLOCKING.has(f.severity)).length
  return out
}

// skeletonDeferred: the JS twin of _skeleton_deferred — deferred entries ride the update-round
// delta as identity/severity/reason (+ skeleton finding); the full bodies' durable home is the
// best-effort round-bodies dump.
const _MAX_DEFER_REASON = 500
const _MAX_COVERAGE_TEXT = 500
const _COVERAGE_FIELDS = ['id', 'classKey', 'kind', 'sourceRound', 'challengedBy', 'text', 'source']

function skeletonDeferred(items) {
  const out = []
  for (const item of Array.isArray(items) ? items : []) {
    if (!item || typeof item !== 'object') { out.push(item); continue }
    const slim = {}
    for (const k of ['identity', 'id', 'severity', 'reason']) if (k in item) slim[k] = item[k]
    if (typeof slim.reason === 'string' && slim.reason.length > _MAX_DEFER_REASON) slim.reason = slim.reason.slice(0, _MAX_DEFER_REASON)
    if (item.finding && typeof item.finding === 'object' && !Array.isArray(item.finding)) slim.finding = _skeletonFinding(item.finding)
    out.push(slim)
  }
  return out
}

// skeletonCoverageDecisions: the JS twin of _skeleton_coverage_decisions — coverage decision
// text is unbounded in the fix loop but must not ride the courier-staged update-round delta
// whole. Identity/class/source fields pass through; text is bounded at persist time. The in-memory
// record keeps the full text for the current session's fix context.
function skeletonCoverageDecisions(items) {
  const out = []
  for (const item of Array.isArray(items) ? items : []) {
    if (!item || typeof item !== 'object') { out.push(item); continue }
    const slim = {}
    for (const k of _COVERAGE_FIELDS) if (k in item) slim[k] = item[k]
    if (typeof slim.text === 'string' && slim.text.length > _MAX_COVERAGE_TEXT) slim.text = slim.text.slice(0, _MAX_COVERAGE_TEXT)
    out.push(slim)
  }
  return out
}

function skeletonRecord(record) {
  const rec = (record && typeof record === 'object') ? record : {}
  const findings = Array.isArray(rec.findings) ? rec.findings : []
  const carried = Array.isArray(rec.carriedFindings) ? rec.carriedFindings : []
  const dims = {}
  for (const [name, d] of Object.entries(rec.dimensions || {})) dims[name] = _summarizeDimension(d)
  return {
    schemaVersion: rec.schemaVersion === undefined ? null : rec.schemaVersion,
    round: rec.round === undefined ? null : rec.round,
    kind: rec.kind === undefined ? null : rec.kind,
    confirmationPending: !!rec.confirmationPending,
    changedSubjects: rec.changedSubjects === undefined ? null : rec.changedSubjects,
    coverageDecisions: skeletonCoverageDecisions(rec.coverageDecisions || []),
    tokenUsage: rec.tokenUsage === undefined ? null : rec.tokenUsage,
    findings: findings.map(_skeletonFinding),
    carriedFindings: carried.map(_skeletonFinding),
    dimensions: dims,
  }
}

module.exports = { clampTitle, classKey, canonicalClassKey, classKeyAliases, recurrentClasses, promoteRecord, recordFromDimensionResults, skeletonRecord, skeletonDeferred, skeletonCoverageDecisions }
