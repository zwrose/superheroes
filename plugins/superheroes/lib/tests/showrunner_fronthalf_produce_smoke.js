// Smoke: producePhase resumes a usable draft (no authoring), re-produces when not usable, and parks
// (low confidence) when the produce leaf fails or yields no usable draft. Stubs the leaves.
// usableDraft verdict is computed Python-side at the IO boundary (front_half_usable.py
// --emit-signals calls front_half.is_usable_draft and returns a small {usable, recorded, expected}
// signal). The spine reads signals.usable directly — no JS twin call on the live doc text.
// The agent stub must:
//   - intercept exec (label='exec') for: front_half_usable --emit-signals, appendNotify (append-notify).
//   - intercept author-* label for authoring.
//   - NOT intercept model_tier_resolve, front_half_usable --write-marker, or append-notify via 'lib'.
const assert = require('assert')
const sr = require('../showrunner.js')
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

// Small boundary signals: verdict computed Python-side. No large doc text in the pipe.
const USABLE_SIGNAL = JSON.stringify({ usable: true, recorded: 'abc123', expected: 'abc123' })
const NOT_USABLE_SIGNAL = JSON.stringify({ usable: false, recorded: '', expected: '' })

function agentWith({ usableSeq, authored, notifyOk = true }) {
  const seq = usableSeq.slice()
  let produceCalls = 0
  const fn = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (opts && opts.courier) {
      if (prompt.includes('emit-signals')) return [{ index: 0, ok: true, stdout: seq.shift() ? USABLE_SIGNAL : NOT_USABLE_SIGNAL }]
      if (prompt.includes('append-notify')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: notifyOk }) }]
      // Any other exec (e.g. persist, journal, checkpoint) — return ok
      return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
    }
    if (label === 'lib') {
      // model_tier_resolve and front_half_usable --write-marker must NOT appear via 'lib' after Task 12.
      if (prompt.includes('model_tier_resolve')) throw new Error('model_tier_resolve dispatched as cmdRunner — must be in-process JS twin')
      if (prompt.includes('front_half_usable') && prompt.includes('--write-marker')) throw new Error('write-marker dispatched as cmdRunner — must be folded into author agent')
      return { ok: true }
    }
    if (label.startsWith('author-')) { produceCalls += 1; return authored }
    return null
  }
  fn.produceCalls = () => produceCalls
  return fn
}

// ---------------------------------------------------------------------------
// Layer 2b: repair-loop adversarial smokes
//
// GAP_SIGNAL: simulates --emit-signals returning not-usable with specific gap fields.
// The repair loop should re-dispatch the author with a hint naming the gaps and retry
// up to N=2 times (3 total author attempts). A mutant that skips the retry must fail.
// ---------------------------------------------------------------------------

const GAP_SIGNAL = JSON.stringify({
  usable: false,
  recorded: '',
  expected: '',
  missing_sections: ['Architecture', 'Tech Stack'],
  placeholder: false,
})

// Helper: builds an agent stub for repair-loop scenarios.
// emitSeq: array of JSON strings for successive --emit-signals calls.
// authorResults: array of return values for successive author-* calls.
// capturedPrompts: array that receives captured author-* prompts.
function repairAgent({ emitSeq, authorResults, capturedPrompts = [], notifyOk = true }) {
  const eSeq = emitSeq.slice()
  const aSeq = authorResults.slice()
  return async function(prompt, opts) {
    const label = (opts && opts.label) || ''
    if (opts && opts.courier) {
      if (prompt.includes('emit-signals')) {
        const sig = eSeq.shift()
        return [{ index: 0, ok: true, stdout: sig !== undefined ? sig : NOT_USABLE_SIGNAL }]
      }
      if (prompt.includes('append-notify')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: notifyOk }) }]
      return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
    }
    if (label === 'lib') return { ok: true }
    if (label.startsWith('author-')) {
      capturedPrompts.push(prompt)
      const r = aSeq.shift()
      return r !== undefined ? r : null
    }
    return null
  }
}

async function repairLoopSmokes() {
  // (h) fail-then-pass: 1st author fails check, 2nd author passes -> high, total 2 author calls.
  // emitSeq: pre-check=false(gap), post-1st-attempt=false(gap), post-2nd-attempt=true
  const prompts_h = []
  global.agent = repairAgent({
    emitSeq: [GAP_SIGNAL, GAP_SIGNAL, USABLE_SIGNAL],
    authorResults: [{ status: 'ok' }, { status: 'ok' }],
    capturedPrompts: prompts_h,
  })
  let r = await sr.producePhase('tasks', 'wi')
  assert.strictEqual(r.confidence, 'high', '(h) fail-then-pass -> high')
  assert.strictEqual(prompts_h.length, 2, '(h) exactly 2 author calls for fail-then-pass')
  // 2nd author prompt must contain a gap hint naming the missing sections.
  const hint_h = prompts_h[1]
  assert.ok(hint_h.includes('Architecture') || hint_h.includes('Tech Stack'),
    '(h) re-prompt hint names the missing sections from the gap signal')
  assert.ok(hint_h.includes('##') || hint_h.toLowerCase().includes('heading'),
    '(h) re-prompt hint references ## headings or heading format')

  // (i) persistent failure: all 3 author attempts produce not-usable -> low (park after N=2 retries).
  // emitSeq: pre-check=false, after-1st=false, after-2nd=false, after-3rd=false (total 4 emits)
  const prompts_i = []
  global.agent = repairAgent({
    emitSeq: [GAP_SIGNAL, GAP_SIGNAL, GAP_SIGNAL, GAP_SIGNAL],
    authorResults: [{ status: 'ok' }, { status: 'ok' }, { status: 'ok' }],
    capturedPrompts: prompts_i,
  })
  r = await sr.producePhase('tasks', 'wi')
  assert.strictEqual(r.confidence, 'low', '(i) persistent failure after N=2 retries -> low (park)')
  assert.strictEqual(prompts_i.length, 3, '(i) exactly 3 author calls (initial + N=2 retries)')

  // (j) first-try pass: usable immediately after first author -> no retry, 1 author call.
  const prompts_j = []
  global.agent = repairAgent({
    emitSeq: [NOT_USABLE_SIGNAL, USABLE_SIGNAL],
    authorResults: [{ status: 'ok' }],
    capturedPrompts: prompts_j,
  })
  r = await sr.producePhase('tasks', 'wi')
  assert.strictEqual(r.confidence, 'high', '(j) first-try pass -> high')
  assert.strictEqual(prompts_j.length, 1, '(j) first-try pass: exactly 1 author call (no retry)')

  // (k) adversarial mutant check: a 0-retry impl would NOT call the author a 2nd time on
  // fail-then-pass. We verify that removing the retry loop would fail test (h): re-verify that
  // prompts_h.length === 2 (not 1). If the loop is absent, it would be 1.
  assert.ok(prompts_h.length > 1,
    '(k) adversarial: a 0-retry impl produces only 1 author call -> test (h) would catch it')

  // (l) NOTIFY defaults across repair attempts are accumulated (not lost on retry).
  // 1st attempt fails check and returns a NOTIFY; 2nd attempt passes. The NOTIFY from the 1st
  // (failing) attempt must be durably recorded, not dropped.
  // emit-signal sequence: pre-check=gap, post-1st-author=gap, post-2nd-author=usable (3 calls)
  const notifyLedger = []
  const prompts_l = []
  const lEmitSeq = [GAP_SIGNAL, GAP_SIGNAL, USABLE_SIGNAL]
  global.agent = async function(prompt, opts) {
    const label = (opts && opts.label) || ''
    if (opts && opts.courier) {
      if (prompt.includes('emit-signals')) {
        const sig = lEmitSeq.shift()
        return [{ index: 0, ok: true, stdout: sig !== undefined ? sig : USABLE_SIGNAL }]
      }
      if (prompt.includes('append-notify')) {
        // parse entries from the prompt to accumulate in the test ledger
        const m = prompt.match(/--entries\s+'([^']+)'/)
        if (m) { try { notifyLedger.push(...JSON.parse(m[1])) } catch (_) {} }
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      }
      return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
    }
    if (label === 'lib') return { ok: true }
    if (label.startsWith('author-')) {
      prompts_l.push(prompt)
      // 1st attempt: returns a NOTIFY; 2nd attempt: clean
      return prompts_l.length === 1
        ? { status: 'ok', notify: [{ identity: 'n-retry', message: 'chose default on retry' }] }
        : { status: 'ok' }
    }
    return null
  }
  r = await sr.producePhase('tasks', 'wi')
  assert.strictEqual(r.confidence, 'high', '(l) NOTIFY on retry + final usable -> high')
  // The NOTIFY from the 1st attempt must have been durably recorded (not silently dropped).
  assert.ok(notifyLedger.some((n) => n.message === 'chose default on retry'),
    '(l) NOTIFY from 1st (failing) attempt must be durably recorded, not dropped on retry')

  console.log('ok: Layer 2b repair-loop — fail-then-pass, persistent-park, first-try-no-retry, notify-accumulate, adversarial-mutant')
}

async function main() {
  // (a) already-usable draft -> resume, never author (FR-8).
  let ag = agentWith({ usableSeq: [true], authored: { status: 'ok' } })
  global.agent = ag
  let r = await sr.producePhase('plan', 'wi')
  assert.strictEqual(r.confidence, 'high', 'usable draft -> high')
  assert.strictEqual(ag.produceCalls(), 0, 'a usable draft is NOT re-authored')

  // (b) not usable -> author -> (marker written by author internally) -> re-check usable -> high.
  ag = agentWith({ usableSeq: [false, true], authored: { status: 'ok' } })
  global.agent = ag
  r = await sr.producePhase('plan', 'wi')
  assert.strictEqual(r.confidence, 'high', 'authored + usable -> high')
  assert.strictEqual(ag.produceCalls(), 1, 'the produce leaf authored once')

  // (c) produce leaf fails (null) -> low confidence (parks, UFR-4).
  ag = agentWith({ usableSeq: [false], authored: null })
  global.agent = ag
  r = await sr.producePhase('plan', 'wi')
  assert.strictEqual(r.confidence, 'low', 'failed produce -> low (park)')

  // (d) authored but still not usable -> repair loop kicks in; park after N=2 retries.
  // With repair loop: need enough not-usable signals for 3 total author attempts.
  ag = agentWith({ usableSeq: [false, false, false, false], authored: { status: 'ok' } })
  global.agent = ag
  r = await sr.producePhase('plan', 'wi')
  assert.strictEqual(r.confidence, 'low', '(d) authored-but-always-not-usable -> low (park after retries)')

  // (e) produce returns a NOTIFY default + ledger write ok -> high (NOTIFY durably recorded).
  ag = agentWith({ usableSeq: [false, true], authored: { status: 'ok', notify: [{ identity: 'n1', message: 'went with X' }] } })
  global.agent = ag
  r = await sr.producePhase('plan', 'wi')
  assert.strictEqual(r.confidence, 'high', 'authored + notify recorded + usable -> high')

  // (f) NOTIFY default but the durable ledger write fails -> low (UFR-2: not silently lost).
  ag = agentWith({ usableSeq: [false], authored: { status: 'ok', notify: [{ identity: 'n1', message: 'went with X' }] }, notifyOk: false })
  global.agent = ag
  r = await sr.producePhase('plan', 'wi')
  assert.strictEqual(r.confidence, 'low', 'failed NOTIFY durable write -> low (park, UFR-2)')
  // (g) FR-5: producePhase embeds selfContained() write-marker command in the author agent prompt
  // when __SR_ROOT is set. The embedded command must be cd-prefixed so the haiku leaf uses the correct repo.
  const savedRoot = globalThis.__SR_ROOT
  try {
    globalThis.__SR_ROOT = '/test-repo'
    let capturedPrompt = null
    const agG = async (prompt, opts) => {
      const label = (opts && opts.label) || ''
      if (opts && opts.courier) {
        if (prompt.includes('emit-signals')) return [{ index: 0, ok: true, stdout: NOT_USABLE_SIGNAL }]
        if (prompt.includes('append-notify')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
      }
      if (label === 'exec2') return [{ index: 0, ok: true, stdout: USABLE_SIGNAL }]
      if (label.startsWith('author-')) {
        capturedPrompt = prompt
        return { status: 'ok' }
      }
      return null
    }
    // Override exec emit-signals to return not-usable first, then usable on second call.
    let emitCount = 0
    global.agent = async (prompt, opts) => {
      const label = (opts && opts.label) || ''
      if (opts && opts.courier) {
        if (prompt.includes('emit-signals')) {
          emitCount += 1
          return [{ index: 0, ok: true, stdout: emitCount === 1 ? NOT_USABLE_SIGNAL : USABLE_SIGNAL }]
        }
        if (prompt.includes('append-notify')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
      }
      if (label.startsWith('author-')) { capturedPrompt = prompt; return { status: 'ok' } }
      return null
    }
    emitCount = 0
    await sr.producePhase('plan', 'wi-fr5')
    assert.ok(capturedPrompt !== null, 'produce leaf was called')
    assert.ok(capturedPrompt.includes("cd '/test-repo' && python3 plugins/superheroes/lib/front_half_usable.py"),
      'producePhase embeds selfContained write-marker command when __SR_ROOT is set')
    // FIX 6 (#115 final review, test-003): the author prompt carries the --write-marker flag (UFR-4)
    // so the author stamps the completion marker itself (the FR-4 fold). A regression that dropped
    // the flag from the embedded command would leave the doc unmarked — catch it here.
    assert.ok(capturedPrompt.includes('--write-marker'), 'author prompt carries --write-marker (UFR-4)')
  } finally {
    globalThis.__SR_ROOT = savedRoot
  }

  console.log('ok: producePhase resume / re-produce / park / notify (exec+twin, no cmdRunner) + FR-5 cd-prefix in embedded write-marker')

  await repairLoopSmokes()
}
main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
