// plugins/superheroes/lib/tests/showrunner_strictify_smoke.js
// #307: engine_dispatch.strictify() — the OpenAI-strict `--output-schema` transformer applied at the
// codex staging seam. Two halves:
//   (a) UNIT: nested objects, arrays-of-objects (items), enum widening, no-mutation, idempotence.
//   (c) STAGING ROUND-TRIP: dispatchExternal on the codex REVIEW path actually WRITES the schema file
//       (the base64 stage command is executed for real against /tmp — the staging seam itself is NOT
//       stubbed), then the file is read back and asserted strict. A cursor dispatch stages the ORIGINAL
//       (unstrictified) schema. This is the coverage that was missing: every prior engine smoke stubbed
//       the CLI AND never validated the staged schema CONTENT, which is exactly how the day-one 400
//       survived 32/32 dispatches (see #307).
'use strict'
const assert = require('assert')
const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')
const { markedStdout } = require('./_marked_stdout.js')
const d = require('../engine_dispatch.js')
const guard = require('./structured_output_schema_guard.js')
const strictify = d.strictify

global.log = () => {}

// The REAL FINDINGS_SCHEMA literal, extracted from source (not hand-copied) so this smoke can never
// drift from the value the spine actually dispatches. The guard file owns the canonical strict-mode
// validation over all three literals; here we exercise the transformer + the staging seam.
const FINDINGS_SCHEMA = guard.extractConst(
  fs.readFileSync(path.join(__dirname, '..', 'showrunner.js'), 'utf8'), 'FINDINGS_SCHEMA')
assert.ok(FINDINGS_SCHEMA && FINDINGS_SCHEMA.properties, 'extracted the real FINDINGS_SCHEMA literal')

// Local re-encoding of the object-node strict rules for the unit assertions below.
function walkObjectNodes(node, visit, pathStr) {
  if (Array.isArray(node)) { node.forEach((n, i) => walkObjectNodes(n, visit, `${pathStr}[${i}]`)); return }
  if (!node || typeof node !== 'object') return
  const isObj = node.type === 'object' || (Array.isArray(node.type) && node.type.indexOf('object') >= 0)
  if (isObj) visit(node, pathStr)
  for (const k of Object.keys(node)) walkObjectNodes(node[k], visit, `${pathStr}.${k}`)
}
function assertStrict(schema, label) {
  walkObjectNodes(schema, (node, p) => {
    assert.strictEqual(node.additionalProperties, false, `${label}${p}: object node must set additionalProperties:false`)
    const propKeys = (node.properties && typeof node.properties === 'object') ? Object.keys(node.properties) : []
    assert.ok(Array.isArray(node.required), `${label}${p}: object node must carry a required array`)
    assert.deepStrictEqual([...node.required].sort(), [...propKeys].sort(),
      `${label}${p}: required must list EVERY property key`)
  }, '')
}

;(() => {
  // (a1) top-level + nested object nodes both get additionalProperties + a complete required.
  const s = strictify(FINDINGS_SCHEMA)
  assertStrict(s, 'FINDINGS_SCHEMA')
  assert.deepStrictEqual(s.required.sort(), ['confidence', 'findings', 'usage', 'verificationReceipt'].sort(),
    'previously-optional top-level keys (usage, verificationReceipt) are now required')

  // (a2) previously-optional props are widened to a nullable union (present-but-null stays legal).
  assert.deepStrictEqual(s.properties.verificationReceipt.type, ['object', 'null'],
    'optional object property is widened to a nullable object union')
  assert.deepStrictEqual(s.properties.usage.type, ['object', 'null'])
  // a REQUIRED property keeps its original (non-null) type.
  assert.strictEqual(s.properties.findings.type, 'array', 'a required property is not widened')

  // (a3) arrays-of-objects: the item object is strictified in place.
  const arrOfObj = {
    type: 'object', required: ['rows'],
    properties: {
      rows: { type: 'array', items: { type: 'object', required: ['id'], properties: { id: { type: 'string' }, note: { type: 'string' } } } },
    },
  }
  const sa = strictify(arrOfObj)
  assertStrict(sa, 'arrOfObj')
  assert.strictEqual(sa.properties.rows.items.additionalProperties, false, 'items object gets additionalProperties:false')
  assert.deepStrictEqual(sa.properties.rows.items.required.sort(), ['id', 'note'], 'items required lists every key')
  assert.deepStrictEqual(sa.properties.rows.items.properties.note.type, ['string', 'null'], 'optional item field widened')
  assert.strictEqual(sa.properties.rows.items.properties.id.type, 'string', 'required item field unchanged')

  // (a4) enum-only optional property (no `type`): null is added to the enum AND an inferred nullable
  // type union is synthesized (the FINAL_REVIEW_SCHEMA severity shape).
  const enumOpt = { type: 'object', properties: { severity: { enum: ['Critical', 'Minor'] } } }
  const se = strictify(enumOpt)
  assertStrict(se, 'enumOpt')
  assert.deepStrictEqual(se.properties.severity.enum, ['Critical', 'Minor', null], 'optional enum gains a null member')
  assert.deepStrictEqual(se.properties.severity.type, ['string', 'null'], 'optional enum gains an inferred nullable type')

  // (a5) NO MUTATION of the input (the literals are shared with the native agent() path).
  const before = JSON.stringify(FINDINGS_SCHEMA)
  strictify(FINDINGS_SCHEMA)
  assert.strictEqual(JSON.stringify(FINDINGS_SCHEMA), before, 'strictify must not mutate its input')

  // (a6) idempotent: an already-strict schema is a fixed point.
  const once = strictify(FINDINGS_SCHEMA)
  const twice = strictify(once)
  assert.strictEqual(JSON.stringify(once), JSON.stringify(twice), 'strictify is idempotent')

  // (a7) degenerate inputs never throw.
  assert.deepStrictEqual(strictify({}), {})
  assert.strictEqual(strictify(null), null)
  assert.deepStrictEqual(strictify({ type: 'string' }), { type: 'string' })

  // (a8) end-to-end: the REAL FINDINGS_SCHEMA is NOT strict-valid raw, and IS strict-valid (all three
  // OpenAI rules, incl. the array-items rule the live 400 surfaced) after strictify.
  assert.ok(guard.strictValid(FINDINGS_SCHEMA) !== null, 'the raw FINDINGS_SCHEMA is not OpenAI-strict-valid')
  assert.strictEqual(guard.strictValid(strictify(FINDINGS_SCHEMA)), null,
    'strictify makes the real FINDINGS_SCHEMA fully OpenAI-strict-valid (objects + arrays)')

  console.log('OK: strictify unit (nested, arrays-of-objects, enum, no-mutation, idempotent, real-literal e2e)')
})()

// ---------------------------------------------------------------------
// (c) STAGING ROUND-TRIP — the staging seam is executed for real (base64 stage runs against /tmp), and
// the on-disk schema file is read back. NO stubbing of the staging write itself.
// ---------------------------------------------------------------------
function makeStagingAgent(routes) {
  // Parse the numbered command list the exec dumb-pipe builds; RUN the base64 staging commands for
  // real (real file writes to /tmp), and route every other single command by substring like the
  // canonical engine smoke does.
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    const lines = prompt.split('\n').map((l) => l.match(/^\d+\.\s(.*)$/)).filter(Boolean).map((m) => m[1])
    if (lines.length && lines.every((c) => /base64 -d >/.test(c))) {
      return lines.map((c, i) => { execSync(c, { shell: '/bin/bash' }); return { index: i, ok: true, stdout: '' } })
    }
    for (const [needle, resp] of routes) {
      if (prompt.includes(needle)) return [{ index: 0, ok: true, stdout: typeof resp === 'function' ? resp(prompt) : resp }]
    }
    return [{ index: 0, ok: true, stdout: '{}' }]
  }
}

const reviewRoutes = [
  ['engine_adapter.py build-argv', JSON.stringify(['codex', 'exec', '--sandbox', 'read-only', '--output-schema', '/tmp/x', '-'])],
  ['engine_adapter.py parse-result', JSON.stringify({ ok: true, findings: [] })],
  ['journal_entry.py', JSON.stringify({ ok: true })],
  // #341: the codex CLI run rides the hardened marker courier — the run leaf must carry __SR_EXIT.
  ['--sandbox', markedStdout('{"findings":[]}')],
]

// A schema with an OPTIONAL object property + an OPTIONAL enum inside an array item — the shapes the
// day-one 400 rejected. Staged codex-side, it must land on disk fully strict.
const STAGE_SCHEMA = {
  type: 'object', required: ['findings'],
  properties: {
    findings: { type: 'array', items: { type: 'object', properties: { severity: { enum: ['Critical', 'Minor'] }, file: { type: 'string' } } } },
    usage: { type: 'object' },
  },
}

;(async () => {
  // pid-unique work-item so the staged /tmp paths (dispatchExternal derives them from the work-item)
  // never collide with a concurrent run of this smoke — the repo's shared-machine-global-state flake
  // convention (new smokes mint pid-unique /tmp names).
  const WI = `wi-strictify-${process.pid}`

  // codex read role: the staged schema file must be strictified.
  const codexSchemaPath = `/tmp/engine-codex-review-${WI}.schema.json`
  try { fs.unlinkSync(codexSchemaPath) } catch (_) {}
  global.agent = makeStagingAgent(reviewRoutes)
  const rCodex = await d.dispatchExternal({
    engine: 'codex', roleKind: 'review', effort: 'high', prompt: 'review please',
    cwd: '/tmp', schema: STAGE_SCHEMA, timeoutSeconds: 300, workItem: WI,
  })
  assert.ok(rCodex && Array.isArray(rCodex.findings), 'codex review dispatch completed: ' + JSON.stringify(rCodex))
  assert.ok(fs.existsSync(codexSchemaPath), 'the codex path must actually WRITE the schema file to disk')
  const staged = JSON.parse(fs.readFileSync(codexSchemaPath, 'utf8'))
  // The exact defect the API 400'd on: additionalProperties:false + a required listing every key,
  // on EVERY object node — asserted against the file that was really written, not an in-memory value.
  assertStrict(staged, 'staged-codex')
  assert.strictEqual(staged.properties.findings.items.additionalProperties, false,
    'the nested array-item object in the STAGED file is strict (day-one 400 site: missing "file" in required)')
  assert.deepStrictEqual(staged.properties.findings.items.required.sort(), ['file', 'severity'],
    'the staged item.required lists every property key')
  assert.deepStrictEqual(staged.properties.usage.type, ['object', 'null'], 'the staged optional object is nullable')
  // And it must differ from the raw literal — proving the transform actually ran end-to-end to disk.
  assert.notStrictEqual(JSON.stringify(staged), JSON.stringify(STAGE_SCHEMA),
    'the staged codex schema must be the STRICTIFIED form, not the raw literal')
  try { fs.unlinkSync(codexSchemaPath) } catch (_) {}
  console.log('OK: strictify staging round-trip — codex path writes the strictified schema to disk')

  // cursor read role: cursor ignores schemas, so the ORIGINAL (unstrictified) schema is staged.
  const cursorSchemaPath = `/tmp/engine-cursor-review-${WI}.schema.json`
  try { fs.unlinkSync(cursorSchemaPath) } catch (_) {}
  global.agent = makeStagingAgent([
    ['engine_adapter.py build-argv', JSON.stringify(['cursor-agent', '--model', 'x', '-p', '--trust', '--mode', 'plan', '--output-format', 'stream-json'])],
    ['engine_adapter.py parse-result', JSON.stringify({ ok: true, findings: [] })],
    ['journal_entry.py', JSON.stringify({ ok: true })],
    // #341: the cursor CLI run rides the hardened marker courier — the run leaf must carry __SR_EXIT.
    ['--output-format', markedStdout('{"findings":[]}')],
    ['--trust', markedStdout('{"findings":[]}')],
  ])
  await d.dispatchExternal({
    engine: 'cursor', roleKind: 'review', effort: 'high', prompt: 'review please',
    cwd: '/tmp', schema: STAGE_SCHEMA, timeoutSeconds: 300, workItem: WI,
  })
  assert.ok(fs.existsSync(cursorSchemaPath), 'the cursor path stages a schema file too')
  const cursorStaged = JSON.parse(fs.readFileSync(cursorSchemaPath, 'utf8'))
  assert.strictEqual(JSON.stringify(cursorStaged), JSON.stringify(STAGE_SCHEMA),
    'cursor must stage the ORIGINAL schema unchanged (strictify is codex-only)')
  try { fs.unlinkSync(cursorSchemaPath) } catch (_) {}
  console.log('OK: strictify is codex-only — cursor stages the original schema unchanged')
})()
