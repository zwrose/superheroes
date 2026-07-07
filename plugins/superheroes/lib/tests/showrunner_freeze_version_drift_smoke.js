// B (version-channel drift guard): the JS consumer's READOUT_VERSION is a COPY of the Python writer's
// preflight_readout.READOUT_VERSION (the ONLY writer of frozenSnapshots). If a Python-side bump isn't
// mirrored in showrunner.js, the migration gate would compare against a stale expected version and
// silently mis-handle records. This smoke dumps the Python constant via `python3 -c` (the roster-parity
// exec pattern) and asserts the JS copy equals it — a rename/bump on either side fails CI.
const assert = require('assert')
const { execFileSync } = require('child_process')
const path = require('path')
const showrunner = require('../showrunner.js')

function main() {
  const libDir = path.join(__dirname, '..')
  const out = execFileSync('python3', ['-c',
    'import sys; sys.path.insert(0, sys.argv[1]); import preflight_readout, json; ' +
    'print(json.dumps(preflight_readout.READOUT_VERSION))', libDir], { encoding: 'utf8' })
  const pyVersion = JSON.parse(out)
  assert.strictEqual(typeof showrunner.READOUT_VERSION, 'number',
    'showrunner.js must export a numeric READOUT_VERSION (the freeze-consume version gate)')
  assert.strictEqual(showrunner.READOUT_VERSION, pyVersion,
    `showrunner.js READOUT_VERSION (${showrunner.READOUT_VERSION}) must equal ` +
    `preflight_readout.READOUT_VERSION (${pyVersion}) — a Python-side bump must be mirrored in the JS consumer`)
  console.log('showrunner_freeze_version_drift_smoke ok')
}
main()
