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

module.exports = { gateForTerminal, isUsableDraft }
