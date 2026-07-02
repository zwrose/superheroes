const assert = require('assert')
const { io } = require('../io_seam.js')
const { fencedJsonWrite } = require('../fenced_json.js')

async function main() {
  const dir = io().join(io().tmpdir(), `readout-fence-${Date.now()}`)
  await io().mkdirp(dir)
  for (const name of ['terminal-record.json', 'front-half-outcome.json', 'telemetry-mirror.json']) {
    const path = io().join(dir, name)
    await io().writeFile(path, JSON.stringify({ runId: 'newer', terminal: 'clean' }))
    const stale = await fencedJsonWrite(path, { runId: 'older', terminal: 'clean' }, { expectedHash: 'wrong', runId: 'older' })
    assert.strictEqual(stale.ok, false)
    const kept = JSON.parse(await io().readText(path))
    assert.strictEqual(kept.runId, 'newer')
  }

  // A THROWING stage+verify transport must fail CLOSED, never crash out of fencedJsonWrite. The
  // fold-1 (#141) rewrite calls io.stageAndRunHelper inside the retry loop; in the bundle that can
  // reject (a courier transport error after courier_exec's retries) and in defaultIo it can throw an
  // fs error (EACCES/ENOSPC). Pre-#143 the stage-write (io.writeFile) throw was caught and turned
  // into a retry -> {ok:false, reason:'payload-stage-failed'} park; the callers (e.g. showrunner.js
  // frontHalfBoundary / reviewDocPhase) branch on !recWrite.ok, so a raw throw would crash the run
  // instead of parking. Assert the graceful park is preserved (throw -> one retry -> fail-closed).
  {
    const realIo = global.io
    global.io = {
      contentHash: (t) => require('crypto').createHash('sha256').update(String(t || ''), 'utf8').digest('hex'),
      async stageAndRunHelper() { throw new Error('courier transport failed after retry (io): empty stdout') },
    }
    try {
      let rejected = false
      let res = null
      try {
        res = await fencedJsonWrite('/tmp/fence-throw/terminal-record.json', { terminal: 'clean' },
          { overwrite: true, runId: 'r-throw' })
      } catch (_) { rejected = true }
      assert.ok(!rejected, 'fencedJsonWrite must not propagate a stage+verify transport throw')
      assert.strictEqual(res && res.ok, false, 'a throwing transport fails closed to {ok:false}')
      assert.strictEqual(res.reason, 'payload-stage-failed',
        'the throw is reported as payload-stage-failed (pre-#143 fail-closed parity)')
    } finally {
      global.io = realIo
    }
  }
}

main().then(() => console.log('ok: readout fencing'))
