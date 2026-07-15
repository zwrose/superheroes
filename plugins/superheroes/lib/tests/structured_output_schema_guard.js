// plugins/superheroes/lib/tests/structured_output_schema_guard.js
// Anthropic structured-output tool input_schema rejects top-level allOf/oneOf/anyOf.
// Smokes stub agent() and never hit the API subset rule — this guard walks every schema
// literal passed to agent({schema}) / structured-output tools in the showrunner spine.
'use strict'
const fs = require('fs')
const path = require('path')
const vm = require('vm')

const FORBIDDEN = ['allOf', 'oneOf', 'anyOf']

function braceSlice(text, openIdx) {
  if (text[openIdx] !== '{') throw new Error(`expected { at ${openIdx}`)
  let depth = 0
  for (let i = openIdx; i < text.length; i++) {
    const ch = text[i]
    if (ch === '{') depth++
    else if (ch === '}') {
      depth--
      if (depth === 0) return text.slice(openIdx, i + 1)
    }
  }
  throw new Error(`unclosed brace at ${openIdx}`)
}

function evalObjectLiteral(literal) {
  return vm.runInNewContext('(' + literal + ')', {}, { timeout: 1000 })
}

function extractConst(source, name) {
  const marker = `const ${name} = `
  const start = source.indexOf(marker)
  if (start < 0) return null
  const open = start + marker.length
  const trimmed = source.slice(open).trimStart()
  const actualOpen = open + (source.slice(open).length - trimmed.length)
  if (trimmed[0] !== '{') return null
  const literal = braceSlice(source, actualOpen)
  return evalObjectLiteral(literal)
}

function extractInlineSchemas(source) {
  const schemas = []
  const needle = 'schema: '
  let idx = 0
  while ((idx = source.indexOf(needle, idx)) >= 0) {
    let p = idx + needle.length
    while (p < source.length && /\s/.test(source[p])) p++
    if (source[p] !== '{') {
      idx = p + 1
      continue
    }
    const literal = braceSlice(source, p)
    try {
      schemas.push({ at: idx, schema: evalObjectLiteral(literal) })
    } catch (e) {
      throw new Error(`inline schema at ${idx}: ${e.message}`)
    }
    idx = p + literal.length
  }
  return schemas
}

function assertNoTopLevelCombinators(schema, label) {
  if (!schema || typeof schema !== 'object' || Array.isArray(schema)) return
  for (const key of FORBIDDEN) {
    if (Object.prototype.hasOwnProperty.call(schema, key)) {
      throw new Error(`${label}: top-level ${key} is rejected by Anthropic tool input_schema`)
    }
  }
}

function checkFile(relPath, constNames) {
  const file = path.join(__dirname, '..', relPath)
  const source = fs.readFileSync(file, 'utf8')
  for (const name of constNames) {
    const schema = extractConst(source, name)
    if (schema) assertNoTopLevelCombinators(schema, `${relPath}:${name}`)
  }
  for (const { at, schema } of extractInlineSchemas(source)) {
    assertNoTopLevelCombinators(schema, `${relPath}:inline@${at}`)
  }
}

// #307: codex's `--output-schema` rides OpenAI STRICT structured outputs. Encode its THREE hard rules,
// surfaced one at a time by the API's incremental validation (a green validator alone is NOT proof —
// each rule below was a distinct live 400): (1) every OBJECT node MUST set `additionalProperties:false`;
// (2) its `required` MUST list EVERY key in `properties`; (3) every ARRAY node MUST declare typed
// `items` (an `items:{}` with no `type` is also rejected). Asserted over the schemas dispatched to codex
// AFTER the engine_dispatch.strictify() staging transform. `strictValid` returns the first violation (a
// string) or null. Distinct from assertNoTopLevelCombinators, which encodes the Anthropic-subset rule
// for the NATIVE (un-strictified) path; a schema is dispatched to ONE or the OTHER, never both.
function _schemaNodes(node, pathStr, out) {
  if (Array.isArray(node)) { node.forEach((n, i) => _schemaNodes(n, `${pathStr}[${i}]`, out)); return out }
  if (!node || typeof node !== 'object') return out
  const types = Array.isArray(node.type) ? node.type : (node.type != null ? [node.type] : [])
  if (types.indexOf('object') >= 0) out.push({ kind: 'object', node, path: pathStr })
  if (types.indexOf('array') >= 0) out.push({ kind: 'array', node, path: pathStr })
  for (const k of Object.keys(node)) _schemaNodes(node[k], `${pathStr}.${k}`, out)
  return out
}

function _hasType(schema) {
  if (!schema || typeof schema !== 'object' || Array.isArray(schema)) return false
  return schema.type !== undefined || Array.isArray(schema.enum)
}

function strictValid(schema) {
  for (const { kind, node, path: p } of _schemaNodes(schema, '', [])) {
    const where = p || '<root>'
    if (kind === 'object') {
      if (node.additionalProperties !== false) {
        return `object node at ${where}: OpenAI strict requires additionalProperties:false`
      }
      const propKeys = (node.properties && typeof node.properties === 'object' && !Array.isArray(node.properties))
        ? Object.keys(node.properties) : []
      if (!Array.isArray(node.required)) {
        return `object node at ${where}: OpenAI strict requires a "required" array`
      }
      const req = [...node.required].sort()
      const keys = [...propKeys].sort()
      if (req.length !== keys.length || req.some((k, i) => k !== keys[i])) {
        return `object node at ${where}: OpenAI strict requires "required" to list every property key ` +
          `(properties=[${keys}], required=[${req}])`
      }
    } else { // array
      if (!_hasType(node.items)) {
        return `array node at ${where}: OpenAI strict requires typed "items" (an items schema with a type/enum)`
      }
    }
  }
  return null
}

function assertStrictModeValid(schema, label) {
  const err = strictValid(schema)
  if (err) throw new Error(`${label}: ${err}`)
}

// The three literals dispatched to codex via `--output-schema` (issue #307): FINDINGS_SCHEMA
// (review-code panel — the acceptance-harness dispatch), REVIEW_TASK_SCHEMA + FINAL_REVIEW_SCHEMA
// (the workhorse per-task + whole-branch reviewers). Each is extracted from source, run through the
// SAME strictify() the dispatch staging seam applies, and strict-validated. The raw literals are
// ALSO asserted to FAIL strict validation — proving the transform is load-bearing (not that the
// literals happened to be strict already), so this gate would go red if strictify were bypassed.
function checkStrictModeSchemas() {
  const { strictify } = require('../engine_dispatch.js')
  const targets = [
    ['showrunner.js', 'FINDINGS_SCHEMA'],
    ['build_phase.js', 'REVIEW_TASK_SCHEMA'],
    ['build_phase.js', 'FINAL_REVIEW_SCHEMA'],
  ]
  for (const [relPath, name] of targets) {
    const source = fs.readFileSync(path.join(__dirname, '..', relPath), 'utf8')
    const raw = extractConst(source, name)
    if (!raw) throw new Error(`${relPath}:${name}: could not extract the schema literal`)
    if (strictValid(raw) === null) {
      throw new Error(`${relPath}:${name}: raw literal is already strict-valid — the strictify guard is not load-bearing ` +
        `(update this expectation only if the literal was intentionally authored strict)`)
    }
    assertStrictModeValid(strictify(raw), `${relPath}:${name} (post-strictify)`)
  }
}

// #418: FINDINGS_SCHEMA_RECEIPT_REQUIRED is derived via Object.assign (not a `{` literal), so the
// source-parse extractConst above cannot reach it. Require the module and assert the runtime object
// directly: no top-level combinator, and verificationReceipt promoted into `required` (the whole point
// of the variant). It is a native-path-only retry schema — never dispatched to codex — so no
// strict-mode check applies.
function checkDerivedSchemas() {
  const sr = require('../showrunner.js')
  const variant = sr.FINDINGS_SCHEMA_RECEIPT_REQUIRED
  if (!variant) throw new Error('showrunner.js: FINDINGS_SCHEMA_RECEIPT_REQUIRED is not exported (#418)')
  assertNoTopLevelCombinators(variant, 'showrunner.js:FINDINGS_SCHEMA_RECEIPT_REQUIRED')
  if (!Array.isArray(variant.required) || !variant.required.includes('verificationReceipt')) {
    throw new Error('showrunner.js:FINDINGS_SCHEMA_RECEIPT_REQUIRED must list verificationReceipt in required (#418)')
  }
}

function main() {
  checkFile('showrunner.js', [
    'FINDINGS_SCHEMA',
    'SYNTH_VERDICTS_SCHEMA',
    'FIX_RESULT_SCHEMA',
  ])
  checkFile('build_phase.js', [])
  checkStrictModeSchemas()
  checkDerivedSchemas()
  process.stdout.write('structured output schema guard: ok\n')
}

if (require.main === module) main()

module.exports = {
  assertNoTopLevelCombinators,
  assertStrictModeValid,
  strictValid,
  checkStrictModeSchemas,
  braceSlice,
  checkFile,
  evalObjectLiteral,
  extractConst,
  extractInlineSchemas,
}
