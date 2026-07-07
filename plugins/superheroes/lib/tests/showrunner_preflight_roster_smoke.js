const assert = require('assert')
const { execFileSync } = require('child_process')
const path = require('path')
const showrunner = require('../showrunner.js')

function main() {
  const libDir = path.join(__dirname, '..')
  const out = execFileSync('python3', ['-c',
    'import sys; sys.path.insert(0, sys.argv[1]); import preflight_readout, json; ' +
    'print(json.dumps(list(preflight_readout.PHASES)))', libDir], { encoding: 'utf8' })
  const pyPhases = JSON.parse(out)
  assert.deepStrictEqual(pyPhases, showrunner.PHASES,
    'preflight_readout.PHASES must equal showrunner.js PHASES (roster-drift guard)')
  console.log('showrunner_preflight_roster_smoke ok')
}
main()
