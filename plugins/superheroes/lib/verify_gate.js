// plugins/superheroes/lib/verify_gate.js
// JS twin of verify_gate.py's returncode->result classification (the subprocess RUN stays an
// executor; this is the pure mapping it feeds). 'none'/'' command -> skipped; timeout -> timeout;
// returncode 0 -> pass; else fail. Fail-closed: anything not unambiguously a pass is fail.
function classify(runResult) {
  const r = runResult || {}
  const cmd = r.command
  if (!cmd || String(cmd).trim().toLowerCase() === 'none') return 'skipped'
  if (r.timedOut) return 'timeout'
  return r.returncode === 0 ? 'pass' : 'fail'
}
module.exports = { classify }
