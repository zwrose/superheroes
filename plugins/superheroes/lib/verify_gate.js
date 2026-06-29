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
  // Tolerate a stringified returncode: pass iff an unambiguous integer 0 (numeric 0 or the string
  // '0'). Fail-CLOSED on anything that is not a plain integer string — crucially the empty string,
  // because Number('')===0 (and Number('  ')===0, Number(null)===0). An empty/whitespace/dropped
  // returncode is a plausible courier garble — exactly the corruption this layer exists to catch —
  // and must NEVER read as a pass. Match an integer string first; everything else (''/NaN/null/
  // undefined/missing) -> fail.
  const rcStr = String(r.returncode).trim()
  if (!/^-?\d+$/.test(rcStr)) return 'fail'
  return Number(rcStr) === 0 ? 'pass' : 'fail'
}
module.exports = { classify }
