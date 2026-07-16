require('./_smoke_checkout_root.js')
// plugins/superheroes/lib/tests/build_phase_reset_denial_smoke.js
// #449: the fix-loop's round-reset (`git checkout -- . && git clean -fd .`, build_phase.resetUncommitted)
// trips the harness auto-mode classifier as [Self-Modification] — the live weekly-eats
// staging-environment-setup run (2026-07-15, spine 0.13.2) had the fixer lane STARVE at the third park
// because the round-reset was denied and the park read as the underlying finding failing. This smoke pins:
//   (A) the reset prompt is CLASSIFIER-BENIGN: it names the operation as the build loop's OWN sanctioned
//       round-reset of its THROWAWAY build worktree (plugin lifecycle, not agent self-modification), and
//       states it never touches the user's own tree and never drops a commit.
//   (B) resetUncommitted DETECTS a denial and returns a structured { ok:false, denied:true, error } —
//       distinct from a plain reset failure ({ ok:false }) and a success ({ ok:true }).
//   (C) the build-loop ENTRY reset parks LOUDLY, naming the denial, instead of the generic
//       "could not reset uncommitted changes: unknown" that read as the finding's own failure.
// Run: node plugins/superheroes/lib/tests/build_phase_reset_denial_smoke.js
const assert = require('assert')
const { routeMatches } = require('./_task_leaf_route.js')
global.log = () => {}
global.parallel = async (fns) => { for (const f of (fns || [])) await f() }

// The canonical auto-mode classifier refusal phrasing (matches courier.denialReason's DENIAL_SIG).
const DENIAL_PROSE =
  'I could not run that command: permission for this action was denied by the auto mode classifier ' +
  '([Self-Modification]).'

function makeAgent(routes) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    for (const [needle, resp] of routes) {
      if (routeMatches(label, needle)) return typeof resp === 'function' ? resp(prompt) : resp
    }
    for (const [needle, resp] of routes) if (prompt.includes(needle)) return typeof resp === 'function' ? resp(prompt) : resp
    if (opts && opts.courier) { for (const [needle, resp] of routes) if (needle === 'exec') return typeof resp === 'function' ? resp(prompt) : resp }
    return ''
  }
}

const bp = require('../build_phase.js')

;(async () => {
  // (A) the reset prompt is classifier-benign (captured off a real dispatch).
  let resetPrompt = null
  global.agent = makeAgent([
    ['reset-uncommitted', (p) => { resetPrompt = p; return { ok: true } }],
  ])
  const okRes = await bp.resetUncommitted('/plugin/wt', 'superheroes/wi-abc')
  assert.strictEqual(okRes.ok, true, 'a clean reset returns { ok:true }')
  assert.ok(resetPrompt, 'the reset dispatched (prompt captured)')
  assert.ok(/not agent self-modification|plugin lifecycle|sanctioned/i.test(resetPrompt),
    'the reset prompt frames the operation as sanctioned plugin lifecycle, not agent self-modification (#449)')
  assert.ok(/throwaway|disposable|build worktree/i.test(resetPrompt),
    'the reset prompt names the plugin\'s OWN throwaway/disposable build worktree (#449 fix direction 1)')
  assert.ok(/never touches the user|not the user'?s|user'?s own (working )?tree/i.test(resetPrompt),
    'the reset prompt states it never touches the user\'s own tree (#449)')
  assert.ok(/git checkout -- \. && git clean -fd/i.test(resetPrompt),
    'the reset prompt still carries the exact reset commands')
  assert.ok(/do NOT touch any commit|never (rewrites or )?drops? any commit|never (rewrites|drops)/i.test(resetPrompt),
    'the reset prompt still forbids touching any commit')

  // (B) resetUncommitted classifies a DENIAL vs a plain failure vs success.
  global.agent = makeAgent([['reset-uncommitted', () => DENIAL_PROSE]])
  const deniedRes = await bp.resetUncommitted('/plugin/wt', 'superheroes/wi-abc')
  assert.strictEqual(deniedRes.ok, false, 'a denied reset is not ok')
  assert.strictEqual(deniedRes.denied, true, 'a denied reset is flagged denied:true (#449 fixer-lane honesty)')
  assert.ok(/auto[- ]?mode classifier|self-modification/i.test(deniedRes.error || ''),
    'the denied result carries the (scrubbed) denial reason')

  global.agent = makeAgent([['reset-uncommitted', () => ({ ok: false, error: 'dirty submodule' })]])
  const failRes = await bp.resetUncommitted('/plugin/wt', 'superheroes/wi-abc')
  assert.strictEqual(failRes.ok, false, 'a plain failure is not ok')
  assert.ok(!failRes.denied, 'a plain failure is NOT flagged as a denial (distinct from [Self-Modification])')
  assert.ok(/dirty submodule/.test(failRes.error || ''), 'a plain failure preserves its error')

  // (B2) a SCHEMA-COERCED denial: the harness may honor the {required:['ok']} schema and return the
  //      denial as an OBJECT whose error field carries the classifier phrasing (not raw prose). The denial
  //      must still be detected over the object's error field, else the silent-starve returns (premortem).
  global.agent = makeAgent([['reset-uncommitted', () => ({ ok: false, error: 'permission for this action was denied by the auto mode classifier ([Self-Modification])' })]])
  const deniedObjRes = await bp.resetUncommitted('/plugin/wt', 'superheroes/wi-abc')
  assert.strictEqual(deniedObjRes.denied, true, 'a schema-coerced (object) denial is flagged denied:true too (#449, over the error field)')
  assert.ok(/auto[- ]?mode classifier|self-modification/i.test(deniedObjRes.error || ''),
    'the object-form denial carries the scrubbed denial reason')

  // (B3) code-001: a proven-EXECUTED reset whose text merely NARRATES a denial phrase is content, not a
  //      denial — the executed-success signal is checked FIRST, so no spurious park.
  global.agent = makeAgent([['reset-uncommitted', () => 'no permission was denied by the auto mode classifier; reset done {"ok":true}']])
  const executedRes = await bp.resetUncommitted('/plugin/wt', 'superheroes/wi-abc')
  assert.strictEqual(executedRes.ok, true, 'a proven-executed reset ({"ok":true}) is NOT reinterpreted as a denial even if its text mentions the classifier (code-001)')
  assert.ok(!executedRes.denied, 'the executed reset carries no denied flag')

  // (C) the build-loop entry reset parks LOUDLY on a denial (names the denial; distinct from a plain fail).
  //     Drive: tasks present, entry gather dirty -> reconcile returns reset_uncommitted -> fence ok -> reset
  //     DENIED. The park reason must name the denial (not the generic "could not reset ... unknown").
  function entryLeaf(p) {
    if (p.includes('read-gate')) return '{"review": "passed"}'
    if (p.includes('build_entry.py')) return JSON.stringify({ branch: 'superheroes/wi-abc', path: '/plugin/wt' })
    if (p.includes('task_list_cli.py')) return JSON.stringify({ tasks: [{ id: '1', title: 'A' }] })
    if (p.includes('build_state_cli.py gather')) return JSON.stringify({ committed_task_ids: [], unmapped_commits: 0, worktree_dirty: true })
    if (p.includes('fence_cli.py')) return JSON.stringify({ ok: true })
    if (p.includes('journal_entry.py')) return JSON.stringify({ ok: true })
    return '{}'
  }
  global.agent = makeAgent([
    ['exec', (p) => [{ index: 0, ok: true, stdout: entryLeaf(p) }]],
    ['reset-uncommitted', () => DENIAL_PROSE],
  ])
  const parked = await bp.buildPhase('wi-abc', 5)
  assert.strictEqual(parked.confidence, 'low', 'a denied entry reset parks')
  const reason = parked.parkReason || (parked.assumptions || [])[0] || ''
  assert.ok(/denied/i.test(reason) && /classifier|self-modification/i.test(reason),
    'the park reason NAMES the classifier denial (loud, not generic) (#449 fix direction 3): ' + reason)
  // Pin the LOUD branch specifically — NOT words that rr.error alone supplies (test-review): a partial
  // revert to the generic `park('could not reset uncommitted changes: ' + rr.error)` would still carry the
  // denial words via rr.error, so assert the reason does NOT use the generic reset-failure prefix and DOES
  // carry the loud self-explaining disclosure that resolves the fixer-starve confusion.
  assert.ok(!/^could not reset uncommitted changes:/i.test(reason),
    'a denied reset does NOT fall through the generic reset-failure prefix (#449 fix direction 3)')
  assert.ok(/round-reset DENIED by the auto-mode classifier|this park IS the denial/i.test(reason),
    'the park reason carries the LOUD self-explaining disclosure, not a bare interpolation of rr.error (#449)')

  console.log('ok: reset prompt is classifier-benign; resetUncommitted flags denials; entry reset parks loudly naming the denial (#449)')
})().catch((e) => { console.error('FAIL:', e.message, e.stack); process.exit(1) })
