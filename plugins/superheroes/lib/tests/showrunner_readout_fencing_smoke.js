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
}

main().then(() => console.log('ok: readout fencing'))
