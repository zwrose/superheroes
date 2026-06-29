// plugins/superheroes/lib/tests/parity_runner.js
const fs = require('fs'); const path = require('path')
function canonicalJson(v) {
  if (v === null || typeof v !== 'object') return JSON.stringify(v)
  if (Array.isArray(v)) return '[' + v.map(canonicalJson).join(',') + ']'
  const keys = Object.keys(v).sort()
  return '{' + keys.map((k) => JSON.stringify(k) + ':' + canonicalJson(v[k])).join(',') + '}'
}
function deepEq(a, b) { return canonicalJson(a) === canonicalJson(b) }
const [twin, fn] = process.argv.slice(2)
const dir = path.join(__dirname, 'parity', twin, fn)
const mod = require(path.join(__dirname, '..', twin + '.js'))
let failed = 0
for (const name of fs.readdirSync(dir).filter((n) => n.endsWith('.json'))) {
  const { input, expected } = JSON.parse(fs.readFileSync(path.join(dir, name), 'utf8'))
  const got = mod[fn].apply(null, input)
  if (!deepEq(got, expected)) {
    failed += 1
    console.error(`MISMATCH ${twin}/${fn}/${name}\n  expected ${JSON.stringify(expected)}\n  got      ${JSON.stringify(got)}`)
  }
}
process.exit(failed ? 1 : 0)
