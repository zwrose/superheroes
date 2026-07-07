// E (SSOT drift guard): showrunner.js's _TIER_ROLE (cfg.tiers-key -> {role, context}) is an unguarded
// copy of the review-code tier vocabulary that also lives in two Python homes:
//   - review_code_config._TIER_ROLE (the resolve_tiers mapping — same key->role,context shape), and
//   - preflight_readout._PHASE_ROLES (the tier_role column of every dispatching role).
// A rename on EITHER side must fail CI, not silently mis-route a frozen pin. This smoke reads both
// homes via `python3 -c` (the roster-parity exec pattern) and asserts they agree with the JS export.
const assert = require('assert')
const { execFileSync } = require('child_process')
const path = require('path')
const showrunner = require('../showrunner.js')

function main() {
  const libDir = path.join(__dirname, '..')
  const out = execFileSync('python3', ['-c',
    'import sys; sys.path.insert(0, sys.argv[1]); import json; ' +
    'import review_code_config as rc, preflight_readout as pr; ' +
    // review_code_config._TIER_ROLE: {cfgKey: [role, context]}
    'cfg = {k: [role, ctx] for k, (role, ctx) in rc._TIER_ROLE.items()}; ' +
    // preflight_readout._PHASE_ROLES tier_role column, flattened to the set of all dispatching tier_roles
    'roles = sorted({tr for rows in pr._PHASE_ROLES.values() for (_l, tr, _k, _kt) in rows if tr}); ' +
    'print(json.dumps({"cfg": cfg, "phaseRoles": roles}))', libDir], { encoding: 'utf8' })
  const py = JSON.parse(out)

  // 1) JS _TIER_ROLE must equal review_code_config._TIER_ROLE, key-for-key, role AND context.
  const js = showrunner._TIER_ROLE
  assert.ok(js && typeof js === 'object', 'showrunner.js must export _TIER_ROLE')
  const jsFlat = {}
  for (const k of Object.keys(js)) jsFlat[k] = [js[k].role, js[k].context]
  assert.deepStrictEqual(jsFlat, py.cfg,
    'showrunner.js _TIER_ROLE must match review_code_config._TIER_ROLE (cfg-key -> role, context) — a rename on either side must fail CI')

  // 2) Every review-code tier role the JS map pins must be a real dispatching tier_role in the readout
  //    roster (preflight_readout._PHASE_ROLES) — so the model_tier vocabulary can never diverge from the
  //    roster that actually dispatches those roles.
  for (const k of Object.keys(js)) {
    assert.ok(py.phaseRoles.indexOf(js[k].role) !== -1,
      `_TIER_ROLE.${k} role '${js[k].role}' must appear as a dispatching tier_role in preflight_readout._PHASE_ROLES`)
  }

  console.log('showrunner_reviewcode_tier_role_drift_smoke ok')
}
main()
