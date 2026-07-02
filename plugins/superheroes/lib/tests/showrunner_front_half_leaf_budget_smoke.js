const assert = require('assert')
const sr = require('../showrunner.js')

;(async () => {
  const labels = []
  global.log = () => {}
  global.agent = async (_prompt, opts) => {
    labels.push(opts.label)
    return [{ ok: true, stdout: JSON.stringify({ ok: true, path: '/tmp/doc.md', docType: opts.label === 'read plan draft' ? 'plan' : 'tasks', gate: 'pending', exists: true }) }]
  }

  const plan = await sr.readDefinitionDraft('wi', 'plan')
  const tasks = await sr.readDefinitionDraft('wi', 'tasks')
  assert.strictEqual(plan.docType, 'plan')
  assert.strictEqual(tasks.docType, 'tasks')
  assert.deepStrictEqual(labels, ['read plan draft', 'read tasks draft'])
  console.log('ok: front-half draft reads folded')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
