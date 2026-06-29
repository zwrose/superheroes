// plugins/superheroes/lib/tests/showrunner_front_half_render_outcome_smoke.js
// TDD unit smoke for front_half.renderRunOutcome (#115 Task 18):
// Phase-records embed — calls injected renderReadout per phase record and assembles the envelope.
// This smoke purposely tests the ONLY path NOT covered by parity fixtures (which have no phase_records
// so loop_readout.render is never invoked in parity).  Here we inject a stub renderer that returns
// a sentinel per record and assert the ## headers + sentinel text appear in order.
'use strict'
const assert = require('assert')
const frontHalf = require('../front_half.js')

function main() {
  // Stub renderer: returns a known sentinel keyed by the record's phase field
  function stubRenderer(record) {
    return 'SENTINEL:' + (record && record.phase ? record.phase : 'unknown')
  }

  const outcome = {
    completed_phases: ['review-plan', 'review-tasks'],
    docs: { plan: 'docs/wi/plan.md', tasks: 'docs/wi/tasks.md' },
    notify: [],
    phase_records: [
      { phase: 'review-plan', record: { phase: 'review-plan', terminal: 'clean' } },
      { phase: 'review-tasks', record: { phase: 'review-tasks', terminal: 'clean-with-skips' } },
    ],
    readout_record_ok: true,
  }

  const text = frontHalf.renderRunOutcome(outcome, stubRenderer)

  // (1) envelope header present
  assert.ok(text.startsWith('# Front-half run outcome'), 'must start with envelope header')

  // (2) completed phases present
  assert.ok(text.includes('**Completed phases:** review-plan, review-tasks'), 'completed phases in envelope')

  // (3) each phase has a ## header
  assert.ok(text.includes('## review-plan — review loop readout'), 'review-plan readout header')
  assert.ok(text.includes('## review-tasks — review loop readout'), 'review-tasks readout header')

  // (4) sentinel for each record is embedded (stub was called with the right record)
  assert.ok(text.includes('SENTINEL:review-plan'), 'stub renderer called with review-plan record')
  assert.ok(text.includes('SENTINEL:review-tasks'), 'stub renderer called with review-tasks record')

  // (5) review-plan sentinel comes BEFORE review-tasks sentinel (order preserved)
  const idxPlan = text.indexOf('SENTINEL:review-plan')
  const idxTasks = text.indexOf('SENTINEL:review-tasks')
  assert.ok(idxPlan < idxTasks, 'phase_records embedded in order')

  // (6) non-dict phase_record is skipped (oracle parity, front_half.py:113-114)
  const outcomeWithBadRecord = {
    completed_phases: [],
    phase_records: [
      'not-a-dict',
      { phase: 'review-plan', record: { phase: 'review-plan', terminal: 'clean' } },
    ],
  }
  const text2 = frontHalf.renderRunOutcome(outcomeWithBadRecord, stubRenderer)
  // Only one ## header (the valid record); the string record is skipped
  const headers = (text2.match(/^## /mg) || []).length
  assert.strictEqual(headers, 1, 'non-dict phase_record is skipped, only 1 header')

  // (7) readout_record_ok: false — UFR-6 warning + phase_records still rendered
  const outcomeWithWarning = {
    completed_phases: ['review-plan'],
    phase_records: [
      { phase: 'review-plan', record: { phase: 'review-plan', terminal: 'clean' } },
    ],
    readout_record_ok: false,
  }
  const text3 = frontHalf.renderRunOutcome(outcomeWithWarning, stubRenderer)
  assert.ok(text3.includes('## review-plan — review loop readout'), 'readout header present with UFR-6')
  assert.ok(text3.includes('SENTINEL:review-plan'), 'sentinel embedded with UFR-6')
  assert.ok(text3.includes('⚠️ The durable readout record could not be written'), 'UFR-6 warning present')

  // (8) no renderReadout provided + empty phase_records -> no crash
  const textNoRenderer = frontHalf.renderRunOutcome({ completed_phases: [], phase_records: [] })
  assert.ok(textNoRenderer.startsWith('# Front-half run outcome'), 'no crash with empty phase_records + no renderer')

  console.log('ok: front_half.renderRunOutcome — phase_records embed, stub renderer, non-dict skip, UFR-6')
}

main()
