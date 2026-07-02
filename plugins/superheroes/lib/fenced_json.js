const { io } = require('./io_seam.js')

// fencedJsonWrite: put a JSON artifact on disk through the courier in TWO leaves — one
// unverified stage-write of the payload file, then one fenced_json.py write that verifies the
// staged text's sha256 ITSELF before applying (--payload-hash). A courier that mangles the
// staged body in transit (live 2026-07-02) fails the Python-side hash check as payload-corrupt
// and the stage is retried once, then fail-closed — never silently altered content. This folds
// the old 6-leaf ceremony (pre-read + current-read + mkdir + stage + hash read-back + write)
// into stage + verify-write.
//
// opts: { runId, lease?, expectedHash?, overwrite? } — exactly one of expectedHash (CAS fence
// against the hash the caller last observed) or overwrite:true (single-writer, lease-guarded
// run artifacts like terminal-record.json, where the runtime unconditionally replaces and the
// old read-then-CAS pair protected nothing the lease doesn't already).
async function fencedJsonWrite(path, payload, opts) {
  const ioApi = io()
  if (!opts || !opts.runId) return { ok: false, reason: 'missing-run-id' }
  if (!opts.expectedHash && !opts.overwrite) return { ok: false, reason: 'missing-expected-hash' }
  const next = Object.assign({}, payload || {}, { runId: opts.runId, lease: opts.lease })
  const text = JSON.stringify(next)
  const want = ioApi.contentHash(text)
  const stagedPath = path + '.payload'
  const args = ['plugins/superheroes/lib/fenced_json.py', 'write', '--path', path,
    '--payload-path', stagedPath, '--payload-hash', want, '--run-id', opts.runId]
  if (opts.overwrite) args.push('--allow-overwrite')
  else args.push('--expected-hash', opts.expectedHash)
  if (opts.lease) args.push('--lease', opts.lease)
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try { await ioApi.writeFile(stagedPath, text) } catch (_) { continue }
    const out = await ioApi.runHelper('python3', args)
    let parsed = null
    try { parsed = JSON.parse((out && out.stdout) || '') } catch (_) { parsed = null }
    if (parsed && parsed.ok) return parsed
    // a real refusal (stale, missing-run-id, replace-failed) is final; only a transport-corrupt
    // stage (or an unparseable answer) earns the one retry.
    if (parsed && parsed.reason && parsed.reason !== 'payload-corrupt' && parsed.reason !== 'payload-unreadable') {
      return { ok: false, reason: parsed.reason }
    }
  }
  return { ok: false, reason: 'payload-stage-failed' }
}

module.exports = { fencedJsonWrite }
