# plugins/superheroes/lib/build_progress.py
"""Per-task resume reconciler — the recover.reconcile analog at task granularity (FR-11, UFR-7,
UFR-12, FR-9). Reality (commits + records) wins; any ambiguity parks fail-closed. All git/store
reads are gathered by build_phase.js; commit inputs are scoped to commits ABOVE the branch
merge-base (base history is never read as trailer-less)."""


def reconcile(task_list, committed_task_ids, unmapped_commits, review_records,
              worktree_dirty, final_review, provenance):
    committed = set(committed_task_ids or [])
    reviews = review_records or {}

    if unmapped_commits and unmapped_commits > 0:
        return {"action": "park",
                "reason": "%d commit(s) above the branch base carry no/unknown Task-Id — fail "
                          "closed (UFR-7)" % unmapped_commits}
    if provenance == "garbled":
        return {"action": "park",
                "reason": "build provenance is unreadable (garbled) — fail closed (UFR-6)"}

    resume = None
    for t in task_list or []:
        if not (t["id"] in committed and reviews.get(t["id"]) == "passed"):
            resume = t
            break

    if worktree_dirty:
        return {"action": "reset_uncommitted", "resume_at": resume,
                "reason": "uncommitted leftover changes — reset only those, then re-dispatch (UFR-12)"}

    if resume is not None:
        if resume["id"] in committed:
            return {"action": "review_task", "resume_at": resume,
                    "reason": "task implemented but not reviewed — keep the commit, take it up at "
                              "review (UFR-7)"}
        return {"action": "build_task", "resume_at": resume,
                "reason": "first task not yet implemented — build it"}

    if final_review is None or not final_review.get("clean"):
        return {"action": "final_review",
                "reason": "all tasks complete — run/resume the whole-branch final review to a "
                          "clean result (FR-8/UFR-7)"}
    if provenance == "absent":
        return {"action": "write_provenance",
                "reason": "final review clean, provenance absent — (re)write provenance "
                          "idempotently, do not re-review (FR-9)"}
    return {"action": "complete",
            "reason": "build complete — provenance present over the handed-off commit"}
