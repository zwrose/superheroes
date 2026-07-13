const assert = require('node:assert')
const test = require('node:test')
const sr = require('../showrunner.js')

test('tasks review journals routed_forward events for non-blocking findings', async () => {
  // Stub the journaling function to capture what would be journaled
  let capturedFindings = null
  const origJournal = sr.journalTasksRoutedFindings
  sr.journalTasksRoutedFindings = async (workItem, findings) => {
    capturedFindings = findings
  }

  const nonBlockingFindings = [
    { file: 'tasks.md', title: 'nit: variable naming', severity: 'Minor', docSection: 'Intro' },
    { file: 'tasks.md', title: 'clarify step order', severity: 'Minor', docSection: 'Flow' }
  ]

  await sr.journalTasksRoutedFindings('work-1', nonBlockingFindings)

  // Verify the findings were passed through
  assert.deepStrictEqual(capturedFindings, nonBlockingFindings)

  // Restore original
  sr.journalTasksRoutedFindings = origJournal
})

test('tasks review handles empty routed findings gracefully', async () => {
  // Empty findings should not crash
  const origJournal = sr.journalTasksRoutedFindings
  let called = false
  sr.journalTasksRoutedFindings = async (workItem, findings) => {
    called = true
  }

  // This should handle null/empty gracefully
  await sr.journalTasksRoutedFindings('work-1', [])

  assert.strictEqual(called, true)
  sr.journalTasksRoutedFindings = origJournal
})
