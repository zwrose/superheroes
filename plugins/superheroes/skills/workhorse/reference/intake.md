# Intake repairs: what an Anchor stop-report carries

This page is reference for the builder's Anchor stop at intake. The charter's §1 says when you stop.
The per-kind resolution tests and the Amendments-log rules live in
`skills/showrunner/reference/issue-contract.md` § Anchor resolution. This page says what repair the
stop-report carries, so the advisor gets the fix in the same round trip as the diagnosis.

Which repair you carry depends on which failure you hit. The two repairs below are not
interchangeable. Filling the derivable fields is not repairing the anchor. The citation and the
edit both stay the advisor's, and the build resumes only on the advisor's word.

## The missing-slot template

Carry this when the body has **no Anchor slot at all**: a pre-doctrine issue, filed before the
three-slot skeleton shipped. The advisor's retrofit recipe, with the template's layout, is in
`skills/showrunner/reference/issue-contract.md` § Pre-doctrine issues. Your report carries that
template pre-filled, with these fields:

| Field | What you put there |
|---|---|
| The Anchor header with its kind token | Blank. Choosing a citation would be repairing your own anchor. |
| The What slot | Filled, carried up from the issue's existing body. |
| The DoD slot | Filled from the existing body, one bullet per outcome a vet could grade from artifacts alone. Where the body yields none, say so and fill nothing. Never invent a requirement. |
| The dated separator line | The original filing's date only. The retrofit date is blank, because the advisor stamps it when the edit actually lands. |
| The original body | Preserved verbatim below the separator, byte-for-byte. |

## The existing-Anchor replacement

Carry this when the issue **already has an Anchor** that fails: a stale spec-section cursor, a dead
receipt link, a superseded ruling, or a malformed header. The repair is targeted and in place:

- One replacement `Anchor (<kind>):` header line, with its citation left blank for the advisor.
- Any non-Anchor slot the body is genuinely missing, filled the way the template fields above are
  filled.

An Anchor present is no proof the What and DoD slots are. A missing What or DoD is a vet finding,
not a filing-time block, and a board pass leaves an Anchor-only body with What and DoD deferred to
pickup. So a stale Anchor and an absent DoD often reach you together. Carrying only the Anchor line
would hand the advisor a body that is still incomplete.

Never add a second copy of a slot the body already carries: no nested skeleton, no dated separator,
and no second Anchor, What, or DoD. The reason is mechanical. The build-ready check has no
duplicate-slot refusal and keeps the **last** Anchor declaration it reads. A second set of slots
prepended above the preserved body leaves the stale Anchor last, so the check would read the stale
anchor and still report success.
