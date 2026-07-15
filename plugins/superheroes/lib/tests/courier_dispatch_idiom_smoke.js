// plugins/superheroes/lib/tests/courier_dispatch_idiom_smoke.js
// #425: the courier dumb-pipe DISPATCH prompts must state byte-fidelity as *why-transparency*, not as
// concealment-shaped prohibition. The live 2026-07-14 0.13.0 run had 6 of 11 startup couriers blocked by
// the harness auto-mode safety classifier, which quoted the prompt's own "Do not echo, fence, summarize,
// or describe the command" clause as a concealment channel. The fidelity CONTRACT is unchanged (chatty
// couriers still corrupt byte-exact relays — #211/#218/#395); only the framing moves to transparency.
//
// This is the regression PIN. It guards two things:
//   (1) every dumb-pipe dispatch-prompt builder carries transparency framing (the reply is on the record,
//       nothing hidden) and NEVER the concealment idiom ("describe the command" / "Do not echo, fence,
//       summarize"). It checks both the built prompts AND the builder SOURCE, so a future edit that
//       reintroduces the prohibition idiom fails here rather than shipping.
//   (2) the #402 composed-exact invariants the reword must not break: the dumb-pipe LEAD prefixes
//       ('Run exactly this' / 'Execute this exact shell command') and the FIRST-blank-line command
//       boundary stay byte-compatible, so recordComposedFromPrompt still extracts the executed bytes off
//       the REAL reworked prompts.
// Run: node plugins/superheroes/lib/tests/courier_dispatch_idiom_smoke.js
'use strict'
const assert = require('assert')
const fs = require('fs')
const path = require('path')
const courier = require('../courier_exec.js')

const LIB = path.join(__dirname, '..')

// The concealment-shaped idiom the auto-mode classifier flagged (#425): the two literal clauses it
// quoted, plus one SHAPE alternative ("do not <hide-verb> … the command") so a synonym reword of the
// prohibition idiom fails too. The shape's verb list deliberately EXCLUDES verbs the sanctioned
// transparency phrasing uses in non-prohibition positions ("restating of the command corrupts the
// parse" carries no leading "do not", so `restate` is safe to include).
const CONCEALMENT_IDIOM = [
  /describe the command/i,
  /do not echo, fence, summariz/i,
  /do not (?:echo|repeat|reveal|restate|quote|mention|describe)\b[^.]*\bthe command/i,
]

function assertTransparent(name, prompt) {
  for (const re of CONCEALMENT_IDIOM) {
    assert.ok(!re.test(prompt), `${name} must NOT carry the concealment idiom ${re} (#425)`)
  }
  // Anchored to the clause's own framing — NOT bare /journal|record/, which the test command's own
  // bytes could satisfy (e.g. a journal_entry.py command riding after the blank line).
  assert.ok(/recorded in the (?:session transcript|run journal)|nothing here is hidden/i.test(prompt),
    `${name} must state the command/reply is on the record (transparency framing)`)
  assert.ok(/verbatim|byte-exact|byte-for-byte/i.test(prompt),
    `${name} must state the byte-fidelity reason (the caller parses it exactly)`)
}

// promptFor is module-private; capture the exact prompt the courier calls dispatch. runCourierText
// drives the non-strict lead; runCourierJson({strict:true}) drives the strict lead.
async function capture(fn) {
  let captured = null
  courier.setCourierAgent(async (prompt) => { captured = prompt; return [{ ok: true, stdout: '{}' }] })
  try { await fn() } finally { courier.setCourierAgent(null) }
  return captured
}

async function builtPromptsAreTransparent() {
  // A _SPINE_STATE_WRITE-shaped command (fence_cli arm) whose bytes carry NONE of the transparency-regex
  // words — so the positive framing assertions can only be satisfied by the clause under test, never by
  // the command payload itself (a journal_entry.py command would self-satisfy /journal/).
  const cmd = 'python3 lib/fence_cli.py renew --lease L7'

  const nonStrict = await capture(() => courier.runCourierText('idiom', cmd))
  const strict = await capture(() => courier.runCourierJson('idiom', cmd, { strict: true }))
  const marked = courier.markedPromptFor(cmd)

  assertTransparent('promptFor (non-strict)', nonStrict)
  assertTransparent('promptFor (strict)', strict)
  assertTransparent('markedPromptFor', marked)

  // #402 leads + first-blank-line boundary survive on the REAL reworked builders.
  for (const [name, p, lead] of [
    ['promptFor (non-strict)', nonStrict, 'Run exactly this'],
    ['promptFor (strict)', strict, 'Run exactly this'],
    ['markedPromptFor', marked, 'Execute this exact shell command'],
  ]) {
    assert.ok(p.startsWith(lead), `${name} keeps its dumb-pipe lead '${lead}' (#402 _DISPATCH_LEADS)`)
    assert.ok(p.endsWith('\n\n' + cmd), `${name} keeps the command after the FIRST blank line, unchanged`)
  }

  // The strict lead must keep its no-improvising clause (the misbehaving release courier depends on it).
  assert.ok(/do not run any other command/i.test(strict),
    'the strict promptFor keeps the no-improvising clause (release-courier fidelity)')

  // End-to-end: recordComposedFromPrompt, fed the REAL builders' prompts, still registers executed
  // bytes — including the STRICT lead, whose extra no-improvising text must not introduce a `\n\n`
  // ahead of the command boundary (the strict state-write class: lease release).
  const seen = []
  courier.setComposedRecorder((c) => seen.push(c))
  try {
    courier.recordComposedFromPrompt(nonStrict)
    courier.recordComposedFromPrompt(strict)
    courier.recordComposedFromPrompt(marked)
  } finally { courier.setComposedRecorder(null) }
  assert.deepStrictEqual(seen, [cmd, cmd, cmd],
    'recordComposedFromPrompt registers the executed bytes off ALL THREE reworked dumb-pipe builders (#402)')
}

// Static pin: grep EVERY lib source for the concealment idiom — a future prompt builder added in a
// sibling module (engine_dispatch, build_phase, …) must not reintroduce it either. The bundle is
// excluded here because test_bundle_drift.py pins committed-bundle == fresh-emit (clean sources ⇒
// clean bundle); tests live under lib/tests/ so the flat readdir never greps this file's own regexes.
function builderSourcesAreClean() {
  const sources = fs.readdirSync(LIB).filter((f) => f.endsWith('.js') && f !== 'showrunner.bundle.js')
  assert.ok(sources.includes('courier_exec.js') && sources.includes('review_panel_shell.js') &&
    sources.includes('showrunner.js'), 'the source sweep sees the three known dispatch-prompt builders')
  for (const f of sources) {
    const src = fs.readFileSync(path.join(LIB, f), 'utf8')
    for (const re of CONCEALMENT_IDIOM) {
      assert.ok(!re.test(src), `${f} must not contain the concealment idiom ${re} (#425)`)
    }
  }
  // review_panel_shell's verify prompt INLINES its transparency framing (a JSON-specific variant of
  // FIDELITY_IS_TRANSPARENT_CLAUSE, deliberately not the shared constant — its contract is "final stdout
  // JSON", not raw stdout). Pin the POSITIVE framing here too, so a future retune of the shared clause
  // that forgets this sibling fails visibly instead of silently reverting the verify courier to
  // classifier-blockable wording.
  const rps = fs.readFileSync(path.join(LIB, 'review_panel_shell.js'), 'utf8')
  assert.ok(/recorded in the run journal/.test(rps) && /byte-exactly/.test(rps),
    'review_panel_shell.js verify prompt carries the transparency framing (recorded + byte-exact) (#425)')
  const md = fs.readFileSync(path.join(LIB, '..', 'agents', 'courier.md'), 'utf8')
  assert.ok(/not concealment|nothing here is secret|nothing here is hidden/i.test(md),
    'agents/courier.md keeps its explicit not-concealment framing')
}

// #435: the WRITE-courier prompt is NARRATION-TOLERANT — a write's load-bearing output is a small receipt
// the caller extracts by pattern, so writeCourierPrompt drops the verbatim-relay demand that
// markedPromptFor carries (the EXACT sentence the auto-mode classifier quoted as concealment when it
// blocked 85/150 dispatches on the live 0.13.2 run). It must, however, keep: the _DISPATCH_LEADS lead + the
// first-blank-line command boundary (so composed-exact still registers the io writer's executed bytes), the
// payload-is-data clause (#403), transparency framing, and none of the concealment idiom.
function writeCourierPromptIsBenign() {
  const cmd = 'python3 -c \'import os,sys,hashlib\nsys.stdout.write("__SR_WROTE:x")\' /store/x.json payload hash'
  const p = courier.writeCourierPrompt(cmd)

  // (1) drops the verbatim-relay demand markedPromptFor carries — the flagged concealment-shaped sentence.
  assert.ok(!/entire reply must be the command's stdout, verbatim/i.test(p),
    'writeCourierPrompt must NOT demand the entire reply be verbatim stdout (#435 narration tolerance)')
  assert.ok(!/any narration[^.]*corrupts the parse/i.test(p),
    'writeCourierPrompt must NOT say narration corrupts the parse (#435)')
  // The shared FIDELITY_IS_TRANSPARENT_CLAUSE (markedPromptFor's) must not appear verbatim on the write prompt.
  assert.ok(p.indexOf(courier.FIDELITY_IS_TRANSPARENT_CLAUSE) < 0,
    'writeCourierPrompt must not carry the byte-exact FIDELITY_IS_TRANSPARENT_CLAUSE (that is for reads/exec)')

  // (2) never the concealment idiom.
  for (const re of CONCEALMENT_IDIOM) {
    assert.ok(!re.test(p), `writeCourierPrompt must NOT carry the concealment idiom ${re} (#435/#425)`)
  }

  // (3) keeps the payload-is-data clause + transparency framing.
  assert.ok(p.indexOf(courier.PAYLOAD_IS_DATA_CLAUSE) >= 0, 'writeCourierPrompt keeps the payload-is-data clause (#403)')
  assert.ok(/recorded in the (?:session transcript|run journal)|nothing here is hidden/i.test(p),
    'writeCourierPrompt keeps transparency framing (nothing hidden, on the record)')
  // It DOES ask the courier to copy the receipt LINE verbatim — a benign, targeted instruction, not a
  // whole-reply relay demand — so it names __SR_WROTE / __SR_EXIT and invites narration around it.
  assert.ok(/__SR_WROTE|__SR_EXIT/.test(p) && /report what happened|narration around it is fine/i.test(p),
    'writeCourierPrompt tells the courier to copy the receipt line but may narrate freely (#435)')

  // (4) #402: the lead + first-blank-line boundary survive, so recordComposedFromPrompt still extracts the bytes.
  assert.ok(p.startsWith('Execute this exact shell command'),
    'writeCourierPrompt keeps a _DISPATCH_LEADS lead (composed-exact registration)')
  assert.ok(p.endsWith('\n\n' + cmd), 'writeCourierPrompt keeps the command after the FIRST blank line, unchanged')
  const seen = []
  courier.setComposedRecorder((c) => seen.push(c))
  try { courier.recordComposedFromPrompt(p) } finally { courier.setComposedRecorder(null) }
  assert.deepStrictEqual(seen, [cmd],
    'recordComposedFromPrompt registers the io writer bytes off writeCourierPrompt (#402/#435)')
}

async function main() {
  await builtPromptsAreTransparent()
  writeCourierPromptIsBenign()
  builderSourcesAreClean()
  console.log('ok: courier dispatch prompts state fidelity as transparency; write prompt narration-tolerant; #402 leads + boundary intact (#425/#435)')
}

main().catch((e) => { console.error('FAIL:', e.message, e.stack); process.exit(1) })
