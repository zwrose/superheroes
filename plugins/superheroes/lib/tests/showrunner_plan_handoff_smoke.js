// Smoke: reviewDocPhase writes the plan review's non-blocking findings to plan-handoff.json
// at the plan-review terminal, with failure disclosure (UFR-1).
'use strict'
require('./_smoke_checkout_root.js')
if (globalThis.__SR_ROOT) process.chdir(globalThis.__SR_ROOT)
const assert = require('assert')
const fs = require('fs')
const sr = require('../showrunner.js')

globalThis.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
globalThis.log = () => {}

async function testPlanHandoffWriteSuccess() {
  const docsDir = fs.mkdtempSync('/tmp/sr-handoff-')
  try {
    // create the plan.md doc file that reviewDocPhase needs
    fs.writeFileSync(`${docsDir}/plan.md`, '# Test Plan\n## Review coverage decisions\n')
    globalThis.__SR_DOC_DIRS = { 'wi-handoff': docsDir }
    globalThis.agent = async (prompt, opts) => {
      const label = (opts && opts.label) || ''
      if (label === 'resume') return '1'
      if (label === 'save phase progress') return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (label === 'save round state') return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (opts && opts.courier) {
        if (prompt.includes('read-gate')) return [{ index: 0, ok: true, stdout: JSON.stringify({ review: 'pending' }) }]
        if (prompt.includes('review_handoff.py write')) {
          return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, path: `${docsDir}/plan-handoff.json`, counts: { distinct: 1 } }) }]
        }
        return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
      }
      if (label.endsWith('-reviewer')) {
        return {
          findings: [
            { file: 'plan.md', title: 'blocking', severity: 'Critical', docSection: 'Architecture' },
            { file: 'plan.md', title: 'nonblocking', severity: 'Minor', docSection: 'Goals' },
          ],
          confidence: 'high',
          verificationReceipt: { artifact: 'stub', chain: [], coverageDecisionIds: [] }
        }
      }
      if (label.startsWith('synthesis')) return { verdicts: [] }
      if (label === 'revise-doc') return { fixes: [], deferred: [] }
      return null
    }
    const r = await sr.reviewDocPhase('plan', 'wi-handoff', { runId: 'run-ho' })
    assert.strictEqual(r.gate, 'passed', 'clean review should pass')
    // assert plan-handoff.json was written with non-blocking finding
    const handoffPath = `${docsDir}/plan-handoff.json`
    assert.ok(fs.existsSync(handoffPath), `plan-handoff.json should exist at ${handoffPath}`)
    const handoff = JSON.parse(fs.readFileSync(handoffPath, 'utf8'))
    assert.strictEqual(handoff.schemaVersion, 1)
    assert.strictEqual(handoff.workItem, 'wi-handoff')
    // only the Minor finding should be in the handoff (not the Critical)
    assert.strictEqual(handoff.counts.distinct, 1, 'only non-blocking findings in handoff')
    delete globalThis.__SR_DOC_DIRS
  } finally {
    try { fs.rmSync(docsDir, { recursive: true, force: true }) } catch (_) {}
  }
}

async function testPlanHandoffWriteFailureDiscloses() {
  const docsDir = fs.mkdtempSync('/tmp/sr-handoff-fail-')
  try {
    fs.writeFileSync(`${docsDir}/plan.md`, '# Test Plan\n## Review coverage decisions\n')
    globalThis.__SR_DOC_DIRS = { 'wi-handoff-fail': docsDir }
    globalThis.agent = async (prompt, opts) => {
      const label = (opts && opts.label) || ''
      if (label === 'resume') return '1'
      if (label === 'save phase progress') return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (label === 'save round state') return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (opts && opts.courier) {
        if (prompt.includes('read-gate')) return [{ index: 0, ok: true, stdout: JSON.stringify({ review: 'pending' }) }]
        if (prompt.includes('review_handoff.py write')) {
          // simulate a write failure
          return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: false, reason: 'write-failed' }) }]
        }
        return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
      }
      if (label.endsWith('-reviewer')) {
        return {
          findings: [
            { file: 'plan.md', title: 'finding', severity: 'Minor', docSection: 'Goals' },
          ],
          confidence: 'high',
          verificationReceipt: { artifact: 'stub', chain: [], coverageDecisionIds: [] }
        }
      }
      if (label.startsWith('synthesis')) return { verdicts: [] }
      if (label === 'revise-doc') return { fixes: [], deferred: [] }
      return null
    }
    const r = await sr.reviewDocPhase('plan', 'wi-handoff-fail', { runId: 'run-hof' })
    assert.strictEqual(r.gate, 'passed', 'gate should still pass despite handoff write failure')
    // a disclosure should appear in phaseResult.assumptions
    assert.ok(r.phaseResult.assumptions && r.phaseResult.assumptions.length > 0, 'should have assumptions/disclosures')
    assert.ok(r.phaseResult.assumptions.some((a) => /plan-handoff\.json write may have failed/.test(a)), 'disclosure should mention handoff write failure')
    delete globalThis.__SR_DOC_DIRS
  } finally {
    try { fs.rmSync(docsDir, { recursive: true, force: true }) } catch (_) {}
  }
}

async function testPlanHandoffWriteDispatchRejectDiscloses() {
  const docsDir = fs.mkdtempSync('/tmp/sr-handoff-reject-')
  try {
    fs.writeFileSync(`${docsDir}/plan.md`, '# Test Plan\n## Review coverage decisions\n')
    globalThis.__SR_DOC_DIRS = { 'wi-handoff-reject': docsDir }
    globalThis.agent = async (prompt, opts) => {
      const label = (opts && opts.label) || ''
      if (label === 'resume') return '1'
      if (label === 'save phase progress') return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (label === 'save round state') return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (opts && opts.courier) {
        if (prompt.includes('read-gate')) return [{ index: 0, ok: true, stdout: JSON.stringify({ review: 'pending' }) }]
        if (prompt.includes('review_handoff.py write')) {
          // simulate a courier dispatch rejection (throw)
          throw new Error('courier transport failed')
        }
        return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
      }
      if (label.endsWith('-reviewer')) {
        return {
          findings: [
            { file: 'plan.md', title: 'finding', severity: 'Minor', docSection: 'Goals' },
          ],
          confidence: 'high',
          verificationReceipt: { artifact: 'stub', chain: [], coverageDecisionIds: [] }
        }
      }
      if (label.startsWith('synthesis')) return { verdicts: [] }
      if (label === 'revise-doc') return { fixes: [], deferred: [] }
      return null
    }
    const r = await sr.reviewDocPhase('plan', 'wi-handoff-reject', { runId: 'run-hor' })
    assert.strictEqual(r.gate, 'passed', 'gate should pass despite courier rejection')
    // disclosure on assumptions
    assert.ok(r.phaseResult.assumptions && r.phaseResult.assumptions.length > 0, 'should have disclosures')
    assert.ok(r.phaseResult.assumptions.some((a) => /plan-handoff\.json write may have failed/.test(a)), 'disclosure should mention handoff failure')
    delete globalThis.__SR_DOC_DIRS
  } finally {
    try { fs.rmSync(docsDir, { recursive: true, force: true }) } catch (_) {}
  }
}

require('node:test')
require('node:test').test('plan-handoff write success', testPlanHandoffWriteSuccess)
require('node:test').test('plan-handoff write failure discloses (UFR-1)', testPlanHandoffWriteFailureDiscloses)
require('node:test').test('plan-handoff dispatch reject discloses (UFR-1)', testPlanHandoffWriteDispatchRejectDiscloses)
