// Shared route matching for build_phase task-scoped leaf labels (#150).
function routeMatches(label, needle) {
  if (label === needle) return true
  if (needle === 'implement-task' && /^implement task .+ of \d+$/.test(label)) return true
  if (needle === 'fix-task' && /^fix task /.test(label)) return true
  if (typeof needle === 'string' && needle.startsWith('task-reviewer:r')) {
    return /^review task .+:r\d+$/.test(label)
  }
  return false
}

module.exports = { routeMatches }
