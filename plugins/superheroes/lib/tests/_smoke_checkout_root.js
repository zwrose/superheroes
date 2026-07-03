'use strict'
// Direct-node smokes run with cwd=repo-root; plant the acquire authority when reconcile has not.
const path = require('path')
if (!globalThis.__SR_ROOT) {
  globalThis.__SR_ROOT = path.resolve(__dirname, '../../../..')
}
