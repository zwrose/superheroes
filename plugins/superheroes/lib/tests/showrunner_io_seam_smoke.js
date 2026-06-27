// plugins/superheroes/lib/tests/showrunner_io_seam_smoke.js
const assert = require('assert')
const os = require('os')
const fs = require('fs')
const { io, defaultIo, joinPath } = require('../io_seam.js')

// defaultIo round-trips on the real filesystem.
const dir = joinPath(os.tmpdir(), 'io-seam-smoke-' + process.pid)
defaultIo.mkdirp(dir)
const p = joinPath(dir, 'x.json')
defaultIo.writeFile(p, { a: 1 })
assert.deepStrictEqual(defaultIo.readJson(p, null), { a: 1 })
assert.strictEqual(defaultIo.readJson(joinPath(dir, 'missing.json'), 'DFLT'), 'DFLT')
defaultIo.writeFile(joinPath(dir, 't.txt'), 'hello')
assert.strictEqual(defaultIo.readText(joinPath(dir, 't.txt')), 'hello')

// io() honors an injected global.io (the bundle's leaf-bash impl), else defaultIo.
assert.strictEqual(io(), defaultIo)
const fake = { writeFile() {}, readText() { return '' }, readJson() { return 'INJ' }, mkdirp() {}, tmpdir() { return '/t' }, join: joinPath }
global.io = fake
assert.strictEqual(io(), fake)
assert.strictEqual(io().readJson('whatever', null), 'INJ')
delete global.io

// join normalizes duplicate separators.
assert.strictEqual(joinPath('/tmp/', '/a', 'b'), '/tmp/a/b')
fs.rmSync(dir, { recursive: true, force: true })
console.log('OK: io_seam defaultIo round-trips + global.io injection + join')
