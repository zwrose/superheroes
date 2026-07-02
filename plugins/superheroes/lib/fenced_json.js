const { io } = require('./io_seam.js')

// writeTextVerified: put `text` on disk and PROVE it arrived intact. In the Workflow bundle the
// io seam is an LLM courier that can mangle a large body in transit (live 2026-07-02), so the
// write is followed by an on-disk hash read-back (a 64-char echo — too small to mangle) compared
// against the locally computed hash; one retry, then fail-closed. On node's disk io the verify
// is a cheap no-op check.
async function writeTextVerified(ioApi, path, text) {
  const want = ioApi.contentHash(text)
  // Ensure the parent dir exists — fenced_json.py's atomic replace used to makedirs for the
  // whole payload write; the staged file needs the same guarantee (a fresh /tmp run dir).
  const dir = String(path).slice(0, String(path).lastIndexOf('/'))
  if (dir) { try { await ioApi.mkdirp(dir) } catch (_) { /* the write below fails closed */ } }
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try { await ioApi.writeFile(path, text) } catch (_) { continue }
    const out = await ioApi.runHelper('python3', ['plugins/superheroes/lib/review_memory.py', 'hash', '--path', path])
    try {
      const parsed = JSON.parse((out && out.stdout) || '')
      if (parsed && parsed.ok && parsed.contentHash === want) return { ok: true, contentHash: want }
    } catch (_) { /* retry */ }
  }
  return { ok: false, reason: 'verified-write-failed' }
}

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
  // Stage the payload as a hash-verified FILE and hand the helper its path — an unbounded
  // payload must never ride the courier args inline (it gets mangled; live 2026-07-02).
  const stagedPath = path + '.payload'
  const staged = await writeTextVerified(ioApi, stagedPath, JSON.stringify(next))
  if (!staged.ok) return { ok: false, reason: 'payload-stage-failed' }
  const args = ['plugins/superheroes/lib/fenced_json.py', 'write', '--path', path, '--payload-path', stagedPath, '--expected-hash', opts.expectedHash, '--run-id', opts.runId]
  if (opts.lease) args.push('--lease', opts.lease)
  const out = await ioApi.runHelper('python3', args)
  try {
    return out.ok ? JSON.parse(out.stdout) : { ok: false, reason: 'write-failed' }
  } catch (_) {
    return { ok: false, reason: 'write-failed' }
  }
}

module.exports = { fencedJsonWrite, writeTextVerified }
