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

function main() {
  checkFile('showrunner.js', [
    'FINDINGS_SCHEMA',
    'SYNTH_VERDICTS_SCHEMA',
    'FIX_RESULT_SCHEMA',
  ])
  checkFile('build_phase.js', [])
  process.stdout.write('structured output schema guard: ok\n')
}

if (require.main === module) main()

module.exports = {
  assertNoTopLevelCombinators,
  braceSlice,
  checkFile,
  evalObjectLiteral,
  extractConst,
  extractInlineSchemas,
}
