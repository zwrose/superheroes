const { io } = require('./io_seam.js')

async function fencedJsonWrite(path, payload, opts) {
  const ioApi = io()
  if (!opts || !opts.expectedHash) return { ok: false, reason: 'missing-expected-hash' }
  let current = ''
  try { current = await ioApi.readText(path) } catch (err) {
    if (!(err && err.code === 'ENOENT')) return { ok: false, reason: 'unreadable' }
  }
  if (ioApi.contentHash(current) !== opts.expectedHash) return { ok: false, reason: 'stale' }
  if (!opts.runId) return { ok: false, reason: 'missing-run-id' }
  const next = Object.assign({}, payload || {}, { runId: opts.runId, lease: opts.lease })
  const args = ['plugins/superheroes/lib/fenced_json.py', 'write', '--path', path, '--payload-json', JSON.stringify(next), '--expected-hash', opts.expectedHash, '--run-id', opts.runId]
  if (opts.lease) args.push('--lease', opts.lease)
  const out = await ioApi.runHelper('python3', args)
  return out.ok ? JSON.parse(out.stdout) : { ok: false, reason: 'write-failed' }
}

module.exports = { fencedJsonWrite }
