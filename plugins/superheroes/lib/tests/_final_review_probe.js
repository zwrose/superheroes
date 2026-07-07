'use strict'
// Shared harness for the smokes that drive build_phase.runFinalReview.
//
// (1) Collision-proof runDir. runFinalReview derives its durable panel-state dir
// INTERNALLY from the work-item name (`/tmp/workhorse-<workItem>-final-review`) — a
// fixed, machine-global path. Smokes that call it with a shared literal name ('wi')
// collide ACROSS PROCESSES: two pytest suites running concurrently on one machine
// (e.g. two live showrunner verify steps, seen 2026-07-06) reset and CAS-write the
// same directory mid-panel, flipping an expected 'clean' terminal to 'cannot-certify'
// (round-memory-unreadable / round-memory-write-failed / coverage-decision-write-failed).
// uniqueWorkItem() mints a pid-unique name so each smoke process's runDir is private.
//
// (2) Diagnosable terminals. runFinalReview returns {terminal} ONLY — the panel's
// reason never reaches the caller, so a flaked assertion used to read just
// "'cannot-certify' !== 'clean'". Requiring this module (BEFORE build_phase.js, which
// destructures reviewPanel at load) wraps review_panel_shell.reviewPanel to capture
// each verdict; assertTerminal() folds terminal+reason+round into the failure message.
const assert = require('assert')
const fs = require('fs')

const shell = require('../review_panel_shell.js')
const realReviewPanel = shell.reviewPanel
let lastVerdict = null
shell.reviewPanel = async (opts) => {
  lastVerdict = await realReviewPanel(opts)
  return lastVerdict
}

function uniqueWorkItem(prefix = 'wi') { return `${prefix}-pid${process.pid}` }

function runDirFor(workItem) { return `/tmp/workhorse-${workItem}-final-review` }

// Reset the durable panel accumulator (round-records.json / deferred-set.json / ...)
// so scenarios are hermetic and run-order independent (pid reuse across days included).
// pid-unique dirs would otherwise pile up in /tmp, so reap them on a PASSING exit —
// a failing run keeps its dir as post-mortem evidence next to the printed reason.
const madeRunDirs = new Set()
process.on('exit', (code) => {
  if (code !== 0) return
  for (const d of madeRunDirs) { try { fs.rmSync(d, { recursive: true, force: true }) } catch (_) {} }
})
function resetRunDir(workItem) {
  const d = runDirFor(workItem)
  fs.rmSync(d, { recursive: true, force: true })
  fs.mkdirSync(d, { recursive: true })
  madeRunDirs.add(d)
  return d
}

function assertTerminal(fr, expected, message) {
  const got = fr && fr.terminal
  if (got === expected) return
  const v = lastVerdict || {}
  assert.fail(`${message} — expected terminal '${expected}', got '${got}' `
    + `(panel verdict: terminal=${v.terminal} reason=${JSON.stringify(v.reason)} round=${v.round})`)
}

module.exports = { uniqueWorkItem, runDirFor, resetRunDir, assertTerminal }
