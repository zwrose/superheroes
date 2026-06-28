// plugins/superheroes/lib/front_half.js
// Pure-decider JS twin of front_half.py: gate_for_terminal + is_usable_draft.
// render_run_outcome is deferred to Task 18. IO helpers (merge_findings /
// record_deferred / append_notify) stay Python executors (Task 11).

function gateForTerminal(terminal) {
  return (terminal === 'clean' || terminal === 'clean-with-skips') ? 'passed' : 'changes-requested'
}

// Faithful port of front_half.py _PLACEHOLDER (same four alternatives, same IGNORECASE flag).
// NOTE: Python _PLACEHOLDER is compiled with re.IGNORECASE only (NOT re.ASCII), so Python's
// \w/\s/\b are UNICODE-aware there. JS \w/\s/\b (no `u` flag) are ASCII-aware. The twin
// intentionally uses JS-default classes — NOT explicit ASCII classes as in circuit_breaker.js.
// This is an accepted ASCII-in-practice approximation: the divergence only bites on a unicode
// word/space char immediately adjacent to a placeholder token or heading, which never occurs in
// ASCII definition-docs. Do NOT "fix" this to explicit ASCII classes; the asymmetry is deliberate.
const _PLACEHOLDER = /\{\{|<!--\s*AUTHOR GUIDANCE|\bTBD\b|similar to Task\s+\w/i

function _escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') }

function isUsableDraft(docText, completionSignal, expectedSignal, requiredSections = []) {
  if (!completionSignal || !expectedSignal || completionSignal !== expectedSignal) return false
  if (!docText || !docText.trim() || !docText.startsWith('---\n')) return false
  const end = docText.indexOf('\n---', 4)
  if (end === -1) return false
  const body = docText.slice(end + 4)
  if (!body.trim()) return false
  if (_PLACEHOLDER.test(docText)) return false
  for (const sec of requiredSections) {
    const m = new RegExp('^#{1,6}\\s+' + _escapeRe(sec) + '\\s*$', 'm').exec(body)
    if (!m) return false
    const rest = body.slice(m.index + m[0].length)
    const nxt = /^#{1,6}\s+/m.exec(rest)
    const segment = nxt ? rest.slice(0, nxt.index) : rest
    if (!segment.trim()) return false
  }
  return true
}

// ---------------------------------------------------------------------------
// renderRunOutcome — faithful JS twin of front_half.py:render_run_outcome (FR-7).
// Composes the front-half run-outcome envelope in-process (pure; never throws).
// For phase_records, calls the optional renderReadout(record) injected by the spine
// (exec-backed in the real run; a stub in unit tests).  Parity fixtures NEVER have
// phase_records, so renderReadout is undefined for all parity cases — the loop body
// is simply never reached.
//
// Return value: when all renderReadout calls return plain strings (or renderReadout is
// absent), the function returns a string synchronously.  When renderReadout is async
// (exec-backed in the spine), it returns a Promise<string>.  The spine always awaits it.
// FR-8 sandbox: no fs/child_process/time-funcs/rand-funcs/process/bare-global (use globalThis).
// ---------------------------------------------------------------------------

function renderRunOutcome(outcome, renderReadout) {
  const o = (outcome !== null && typeof outcome === 'object' && !Array.isArray(outcome)) ? outcome : {}
  const lines = ['# Front-half run outcome', '']
  const completed = (o.completed_phases && Array.isArray(o.completed_phases)) ? o.completed_phases : []
  lines.push('**Completed phases:** ' + (completed.length ? completed.join(', ') : '(none)'))
  lines.push('')

  const docs = (o.docs && typeof o.docs === 'object' && !Array.isArray(o.docs)) ? o.docs : {}
  if (Object.keys(docs).length > 0) {
    lines.push('**Docs:**')
    for (const k of Object.keys(docs)) {
      lines.push('- ' + k + ' → ' + docs[k])
    }
    lines.push('')
  }

  if (o.parked_phase) {
    lines.push('**Parked at:** ' + o.parked_phase + ' — ' + (o.park_reason || ''))
    lines.push('')
  }

  // Deduplicated NOTIFY defaults: key is (phase, identity || message) — distinct un-identified
  // NOTIFYs (no identity) fall back to message so they don't collapse on (phase, undefined).
  const notify = Array.isArray(o.notify) ? o.notify : []
  const deduped = []
  const seen = new Set()
  for (const n of notify) {
    if (!n || typeof n !== 'object') continue
    const key = JSON.stringify([n.phase, n.identity !== undefined ? n.identity : n.message])
    if (seen.has(key)) continue
    seen.add(key)
    deduped.push(n)
  }
  lines.push('**NOTIFY defaults (named — owner may veto):**')
  if (deduped.length) {
    for (const n of deduped) {
      lines.push('- [' + (n.phase !== undefined ? n.phase : '?') + '] ' + (n.message !== undefined ? n.message : ''))
    }
  } else {
    lines.push('- (none)')
  }
  lines.push('')

  // Collect phase_records to embed (skip non-dict entries per oracle parity).
  const phaseRecords = Array.isArray(o.phase_records) ? o.phase_records : []
  const validRecords = phaseRecords.filter(function(pr) {
    return pr && typeof pr === 'object' && !Array.isArray(pr)
  })

  const ufr6 = o.readout_record_ok === false

  // Internal finalizer: receives per-record rendered texts (string[]) and assembles the full output.
  function _finish(renderedTexts) {
    const out = lines.slice()
    for (let i = 0; i < validRecords.length; i++) {
      const pr = validRecords[i]
      const phase = pr.phase !== undefined ? pr.phase : '?'
      out.push('## ' + phase + ' — review loop readout')
      out.push('')
      out.push(renderedTexts[i])
      out.push('')
    }
    if (ufr6) {
      out.push('> ⚠️ The durable readout record could not be written — this outcome is ' +
        'reported to the invoking session only; treat the durable copy as missing (UFR-6).')
      out.push('')
    }
    return out.join('\n').replace(/\s+$/, '') + '\n'
  }

  // If there are no phase_records or no renderReadout, compose synchronously.
  if (validRecords.length === 0 || typeof renderReadout !== 'function') {
    return _finish([])
  }

  // Call renderReadout for each valid record. If any call returns a Promise, collect all as promises.
  const results = validRecords.map(function(pr) {
    try {
      return renderReadout(pr.record !== undefined ? pr.record : null)
    } catch (_) {
      return ''
    }
  })

  // Check if any result is a thenable (async renderReadout).
  const hasPromise = results.some(function(r) {
    return r && typeof r === 'object' && typeof r.then === 'function'
  })
  if (!hasPromise) {
    // All synchronous — return string directly (parity path + sync stub tests).
    return _finish(results.map(function(r) { return typeof r === 'string' ? r : '' }))
  }

  // At least one async — return a Promise that resolves to the assembled string.
  return Promise.all(results.map(function(r) {
    if (r && typeof r === 'object' && typeof r.then === 'function') return r
    return Promise.resolve(typeof r === 'string' ? r : '')
  })).then(_finish, function() { return _finish(results.map(function() { return '' })) })
}

module.exports = { gateForTerminal, isUsableDraft, renderRunOutcome }
