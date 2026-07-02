// plugins/superheroes/lib/tests/showrunner_io_seam_smoke.js
const assert = require('assert')
const os = require('os')
const fs = require('fs')
const { io, defaultIo, joinPath } = require('../io_seam.js')

// The io seam is uniformly async (defaultIo's four IO methods return Promises so they share one
// contract with the bundle's leaf-bash io) — so the round-trip body must await each call.
;(async () => {
  // defaultIo round-trips on the real filesystem.
  const dir = joinPath(os.tmpdir(), 'io-seam-smoke-' + process.pid)
  await defaultIo.mkdirp(dir)
  const p = joinPath(dir, 'x.json')
  await defaultIo.writeFile(p, { a: 1 })
  assert.deepStrictEqual(await defaultIo.readJson(p, null), { a: 1 })
  assert.strictEqual(await defaultIo.readJson(joinPath(dir, 'missing.json'), 'DFLT'), 'DFLT')
  await defaultIo.writeFile(joinPath(dir, 't.txt'), 'hello')
  assert.strictEqual(await defaultIo.readText(joinPath(dir, 't.txt')), 'hello')

  // io() honors an injected global.io (the bundle's leaf-bash impl), else defaultIo. These are sync
  // structural assertions on the selector + joinPath (no IO), so they stay un-awaited.
  assert.strictEqual(io(), defaultIo)
  const fake = { writeFile() {}, readText() { return '' }, readJson() { return 'INJ' }, mkdirp() {}, tmpdir() { return '/t' }, join: joinPath }
  global.io = fake
  assert.strictEqual(io(), fake)
  assert.strictEqual(io().readJson('whatever', null), 'INJ')
  delete global.io

  // join normalizes duplicate separators.
  assert.strictEqual(joinPath('/tmp/', '/a', 'b'), '/tmp/a/b')

  // stageAndRunHelper: ONE call that (1) ensures the staged path's parent dir, (2) writes the
  // payload verbatim, (3) runs the helper — the single-leaf twin of writeFile+runHelper (fold 1,
  // #141). Result shape matches runHelper ({ ok, status, stdout }). Staging into a not-yet-created
  // subdir must still succeed (the parent-dir create is folded into the same op).
  const nested = joinPath(dir, 'sub', 'staged.txt')
  const res = await defaultIo.stageAndRunHelper(nested, 'payload-bytes\n', 'cat', [nested])
  assert.strictEqual(res.ok, true, 'stageAndRunHelper reports ok on a clean helper exit')
  assert.strictEqual(res.stdout, 'payload-bytes\n', 'the helper sees the exact staged bytes')
  assert.strictEqual(fs.readFileSync(nested, 'utf8'), 'payload-bytes\n', 'the payload lands on disk')
  // a non-zero helper is reported ok:false (fail-closed), stage still happened.
  const bad = await defaultIo.stageAndRunHelper(joinPath(dir, 's2.txt'), 'x', 'false', [])
  assert.strictEqual(bad.ok, false, 'a non-zero helper exit is ok:false')

  fs.rmSync(dir, { recursive: true, force: true })
  console.log('OK: io_seam defaultIo round-trips + global.io injection + join + stageAndRunHelper')
})().catch((e) => { console.error(e); process.exit(1) })
