// Unit smoke: confirmationFollowup docMode branch (FR-8) — mirrors Python doc_mode tests.
'use strict'
const assert = require('assert')
const { confirmationFollowup } = require('../review_round_policy.js')

function main() {
  const underCap = confirmationFollowup(['Important'], 1, false, undefined, true)
  assert.deepStrictEqual(underCap, {
    rearm: true, park: false, atCap: false,
    reason: 'open blocking finding in doc review — one more full confirmation panel required',
  })

  const atCap = confirmationFollowup(['Important'], 2, false, undefined, true)
  assert.strictEqual(atCap.rearm, false)
  assert.strictEqual(atCap.park, true)
  assert.strictEqual(atCap.atCap, true)

  const nothingOpen = confirmationFollowup([], 1, false, undefined, true)
  assert.deepStrictEqual(nothingOpen, {
    rearm: false, park: false, atCap: false,
    reason: 'no open blocking finding — doc review certifies',
  })

  const criticalAtCap = confirmationFollowup(['Critical'], 2, false, undefined, true)
  assert.strictEqual(criticalAtCap.park, true)
  assert.strictEqual(criticalAtCap.atCap, true)

  // regression: code review rule unchanged when docMode is false
  const codeMode = confirmationFollowup(['Important'], 2, false)
  assert.strictEqual(codeMode.park, false)
  assert.strictEqual(codeMode.rearm, false)
  assert.strictEqual(codeMode.atCap, true)

  console.log('ok: confirmationFollowup docMode branch')
}

main()
