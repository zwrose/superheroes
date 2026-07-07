// plugins/superheroes/lib/tests/showrunner_startup_parrot_smoke.js
// #281: the startup gather (readStartupState) was answered WITHOUT executing in a live run (park
// wf_ac2f134f: 4 transcript events, ZERO tool calls). A courier mentally simulated the embedded
// Python and fabricated a well-formed payload — a poisoned spec_gate:'unreadable' AND a rewritten
// engine_prefs claude/claude when the store's real pref was implementation:cursor. The fix routes the
// gather through runCourierMarkedJson (the #218/#232 __SR_EXIT proof-of-execution marker), which
// certifies the WHOLE payload (every field, incl. engine_prefs — which has no impossible-combination
// signature a semantic tripwire could catch), plus a cheap semantic tripwire on the exact
// spec_present && spec_gate=='unreadable' fabrication tell. This smoke drives readStartupState directly.
const assert = require('assert')
const { markedStdout } = require('./_marked_stdout.js')
const sr = require('../showrunner.js')

global.log = () => {}

// The exact live-park fabrication: well-formed payload, poisoned gate + rewritten prefs, but (as a
// did-not-run answer) NO __SR_EXIT execution marker.
const PARROT = {
  ok: true, spec_gate: 'unreadable', model_overrides: {},
  doc_dir: '/Users/zwrose/weekly-eats/docs/superheroes/wi',   // the MAIN checkout, not the leaf worktree
  engine_prefs: { reviewer: 'claude', implementation: 'claude', effort: {} },
  spec_present: true, tasks_present: false, tasks_gate: null,
}
// A genuine execution's answer for this work item: real gate + the owner's real store pref (cursor).
const REAL = {
  ok: true, spec_gate: 'passed', model_overrides: {}, doc_dir: '/wt/docs/superheroes/wi',
  engine_prefs: { reviewer: 'codex', implementation: 'cursor', effort: {} },
  spec_present: true, tasks_present: false, tasks_gate: null,
}

;(async () => {
  // (A) A did-not-run parrot (well-formed payload, NO marker) must fail CLOSED — the fabricated
  //     engine_prefs (claude/claude) and doc_dir (main checkout) must NEVER survive. It is retried the
  //     full 2×3 marker chain before falling back to the degenerate (null prefs / empty doc_dir).
  {
    let calls = 0
    global.agent = async (_p, opts) => {
      if (opts && opts.label === 'read startup state') { calls += 1; return JSON.stringify(PARROT) }  // no __SR_EXIT
      return [{ ok: true, stdout: '{}' }]
    }
    const facts = await sr.readStartupState('wi')
    assert.strictEqual(facts.engine_prefs, null,
      '#281 (A): a did-not-run parrot must NOT plant fabricated engine_prefs — fail closed to null (not claude/claude)')
    assert.strictEqual(facts.doc_dir, '', '#281 (A): the parrot doc_dir (main checkout) must not survive')
    assert.strictEqual(facts.spec_gate, 'unreadable', '#281 (A): the degenerate fallback gate')
    assert.strictEqual(calls, 6, '#281 (A): a marker-less answer is retried the full 2×3 marker chain before failing closed')
    console.log('OK (A): a did-not-run parrot fails closed — no fabricated engine_prefs/doc_dir survives')
  }

  // (B) A STOCHASTIC parrot (the observed class): the first dispatch parrots without a marker, a retry
  //     produces the REAL marked answer -> the gather recovers the owner's real store pref (cursor),
  //     NOT the fabricated claude. This is the proof-of-execution marker doing its job on engine_prefs.
  {
    let n = 0
    global.agent = async (_p, opts) => {
      if (opts && opts.label === 'read startup state') {
        n += 1
        return n === 1 ? JSON.stringify(PARROT) : markedStdout(REAL)   // 1st: no marker; 2nd: real, marked
      }
      return [{ ok: true, stdout: '{}' }]
    }
    const facts = await sr.readStartupState('wi')
    assert.strictEqual(facts.engine_prefs.implementation, 'cursor',
      '#281 (B): the marker retry recovers the REAL store pref (cursor), not the parroted claude')
    assert.strictEqual(facts.spec_gate, 'passed', '#281 (B): the real gate comes through on the marked retry')
    assert.strictEqual(n, 2, '#281 (B): the marker-less parrot was retried until a real marked answer arrived')
    console.log('OK (B): a stochastic parrot is retried and the REAL engine_prefs (cursor) round-trips')
  }

  // (C) Semantic tripwire: a MARKED answer with spec_present && spec_gate=='unreadable' (the exact live
  //     fabrication tell) is retried ONCE; a stochastic parrot self-corrects to the real gate.
  {
    let n = 0
    global.agent = async (_p, opts) => {
      if (opts && opts.label === 'read startup state') {
        n += 1
        return markedStdout(n === 1 ? PARROT : REAL)   // both MARKED; 1st carries the suspect combo
      }
      return [{ ok: true, stdout: '{}' }]
    }
    const facts = await sr.readStartupState('wi')
    assert.strictEqual(facts.spec_gate, 'passed',
      '#281 (C): the semantic tripwire retried the marked spec_present+unreadable answer and got the real gate')
    assert.strictEqual(facts.engine_prefs.implementation, 'cursor', '#281 (C): the retry also recovered the real prefs')
    assert.strictEqual(n, 2, '#281 (C): exactly ONE semantic retry (the marker is present, so no marker-level retry)')
    console.log('OK (C): the semantic tripwire retries a marked spec_present+unreadable answer once')
  }

  // (D) Semantic tripwire is BOUNDED: a GENUINE read exception reproduces the suspect combo on retry, so
  //     it is accepted after exactly one retry (the twin then parks honestly on 'unreadable') — never an
  //     infinite retry loop.
  {
    let n = 0
    global.agent = async (_p, opts) => {
      if (opts && opts.label === 'read startup state') { n += 1; return markedStdout(PARROT) }  // always suspect+marked
      return [{ ok: true, stdout: '{}' }]
    }
    const facts = await sr.readStartupState('wi')
    assert.strictEqual(facts.spec_gate, 'unreadable',
      '#281 (D): a reproduced (genuine) read exception is accepted after one retry -> honest park input')
    assert.strictEqual(n, 2, '#281 (D): the semantic tripwire retries exactly once, then accepts (no infinite loop)')
    console.log('OK (D): the semantic tripwire is bounded to one retry, then accepts a reproduced suspect answer')
  }

  // (E) the tripwire fires ONLY on spec_present===true: a LEGITIMATE resolver failure yields
  //     spec_present:false + spec_gate:'unreadable' (the script's init defaults when the outer try
  //     raised before spec_present was set) — that must NOT trip a retry. Pins the spec_present
  //     sub-clause (a mutant dropping it would retry this state).
  {
    let n = 0
    global.agent = async (_p, opts) => {
      if (opts && opts.label === 'read startup state') {
        n += 1
        return markedStdout({ ok: true, spec_present: false, spec_gate: 'unreadable', model_overrides: {},
          doc_dir: '', engine_prefs: { reviewer: 'claude', implementation: 'claude', effort: {} },
          tasks_present: false, tasks_gate: null })
      }
      return [{ ok: true, stdout: '{}' }]
    }
    const facts = await sr.readStartupState('wi')
    assert.strictEqual(facts.spec_gate, 'unreadable', '#281 (E): a legitimate resolver-failure unreadable state is accepted')
    assert.strictEqual(n, 1, '#281 (E): spec_present:false + unreadable must NOT trip the semantic retry (only spec_present===true is suspect)')
    console.log('OK (E): a legitimate spec_present:false + unreadable state does not trip the tripwire')
  }

  // (F) fail-direction: a GENUINE present-but-unparseable spec carries spec_present+unreadable WITH a
  //     real doc_dir/engine_prefs. The tripwire retries; if the RETRY transport-fails, the
  //     already-certified FIRST answer must be KEPT — never discarded for the degenerate fallback
  //     (which would null engine_prefs -> all-claude and empty doc_dir -> mis-routed docs). (#281 review.)
  {
    let n = 0
    const REAL_SUSPECT = { ok: true, spec_present: true, spec_gate: 'unreadable', model_overrides: {},
      doc_dir: '/wt/docs/superheroes/wi', engine_prefs: { reviewer: 'codex', implementation: 'cursor', effort: {} },
      tasks_present: false, tasks_gate: null }
    global.agent = async (_p, opts) => {
      if (opts && opts.label === 'read startup state') {
        n += 1
        return n === 1 ? markedStdout(REAL_SUSPECT) : JSON.stringify(REAL_SUSPECT)   // retry: no marker -> transport-fails
      }
      return [{ ok: true, stdout: '{}' }]
    }
    const facts = await sr.readStartupState('wi')
    assert.strictEqual(facts.spec_gate, 'unreadable', '#281 (F): the genuine unreadable gate is kept (the twin parks honestly)')
    assert.strictEqual(facts.engine_prefs.implementation, 'cursor',
      '#281 (F): a retry-transport failure keeps the certified first answer engine_prefs (cursor), not the degenerate null')
    assert.strictEqual(facts.doc_dir, '/wt/docs/superheroes/wi',
      '#281 (F): the certified first answer doc_dir is kept, not the degenerate empty string')
    assert.strictEqual(n, 7, '#281 (F): first marked dispatch (1) + the retry chain transport-failing over 2×3 (6) = 7, then the first answer is kept')
    console.log('OK (F): a retry-transport failure keeps the certified first answer (no degenerate reset)')
  }

  console.log('OK: #281 startup-gather proof-of-execution marker + semantic tripwire')
})().catch((e) => { console.error('FAIL:', (e && e.message) || e); process.exit(1) })
