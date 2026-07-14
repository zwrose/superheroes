// Task 4 (#397 FR-1): native doc reviewer + synthesis leaves steer to the document-severity bar.
const assert = require('node:assert')
const test = require('node:test')
const sr = require('../showrunner.js')

test('doc reviewer + synthesis prompts carry the document-severity bar', async () => {
  const prompts = []
  globalThis.agent = async (prompt, opts) => {
    prompts.push(prompt)
    return opts && opts.label && opts.label.startsWith('synthesis')
      ? { verdicts: [] } : { findings: [] }
  }
  globalThis.__SR_OVERRIDES = null
  await sr.docReviewerAgent('architecture-reviewer',
    { docType: 'plan', docPath: 'plan.md' }, 'review-base', '/tmp/x', 1, {})
  await sr.docSynthesisLeaf([], { docType: 'plan', docPath: 'plan.md' }, 'review-base', '/tmp/x', 1)
  assert.ok(prompts.every((p) => /document-review severity|blocking bar|follow(ing)? the document/i.test(p)),
    'both doc leaves must steer to the document-severity rule')
  assert.ok(prompts.every((p) => /incident-anchored|unauthenticated access/i.test(p)),
    'both doc leaves must carry the incident-anchored always-blocking carve-out')
})
