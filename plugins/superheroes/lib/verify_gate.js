// plugins/superheroes/lib/verify_gate.js
// JS twin of verify_gate.py's returncode->result classification (the subprocess RUN stays an
// executor; this is the pure mapping it feeds). 'none'/'' command -> skipped; timeout -> timeout;
// returncode 0 -> pass; else fail. Fail-closed: anything not unambiguously a pass is fail.
// Defense-in-depth: tolerates courier-stringified fields (returncode:'0', timedOut:'false').
function classify(runResult) {
  const r = runResult || {}
  const cmd = r.command
  if (!cmd || String(cmd).trim().toLowerCase() === 'none') return 'skipped'
  // Tolerate stringified timedOut: truthy iff boolean true or string 'true' (case-insensitive).
  // A stringified 'false' is NOT timed out (the original bug: any non-empty string was truthy).
  const timedOut = r.timedOut === true || String(r.timedOut).toLowerCase() === 'true'
  if (timedOut) return 'timeout'
  // Tolerate stringified returncode: pass iff numeric 0 OR coercible string '0'.
  // Fail-closed: NaN / undefined / null / missing -> fail. Explicit null guard: Number(null)===0
  // but a null returncode signals no exit code (timeout or error), which is never a pass.
  const rc = r.returncode
  if (rc === null || rc === undefined) return 'fail'
  return Number(rc) === 0 ? 'pass' : 'fail'
}
module.exports = { classify }
