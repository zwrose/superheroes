// plugins/superheroes/lib/build_progress.js
function reconcile(taskList, committedTaskIds, unmappedCommits, reviewRecords, worktreeDirty, finalReview, provenance) {
  const committed = new Set(committedTaskIds || [])
  const reviews = reviewRecords || {}
  if (unmappedCommits && unmappedCommits > 0) {
    return { action: 'park', reason: `${unmappedCommits} commit(s) above the branch base carry no/unknown Task-Id — fail closed (UFR-7)` }
  }
  if (provenance === 'garbled') {
    return { action: 'park', reason: 'build provenance is unreadable (garbled) — fail closed (UFR-6)' }
  }
  let resume = null
  for (const t of taskList || []) {
    if (!(committed.has(t.id) && reviews[t.id] === 'passed')) { resume = t; break }
  }
  if (worktreeDirty) {
    return { action: 'reset_uncommitted', resume_at: resume, reason: 'uncommitted leftover changes — reset only those, then re-dispatch (UFR-12)' }
  }
  if (resume !== null) {
    if (committed.has(resume.id)) {
      return { action: 'review_task', resume_at: resume, reason: 'task implemented but not reviewed — keep the commit, take it up at review (UFR-7)' }
    }
    return { action: 'build_task', resume_at: resume, reason: 'first task not yet implemented — build it' }
  }
  if (finalReview === null || finalReview === undefined || !finalReview.clean) {
    return { action: 'final_review', reason: 'all tasks complete — run/resume the whole-branch final review to a clean result (FR-8/UFR-7)' }
  }
  if (provenance === 'absent') {
    return { action: 'write_provenance', reason: 'final review clean, provenance absent — (re)write provenance idempotently, do not re-review (FR-9)' }
  }
  return { action: 'complete', reason: 'build complete — provenance present over the handed-off commit' }
}
module.exports = { reconcile }
