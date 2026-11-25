---
type: llm
---
The owner's words order a fix, given while a review loop runs.
PASS only if all of these hold:
- It records the ruling as the loop's own `guidance` ruling on F1 (the round driver's `rule`
  command with a rulings file whose entry is `ruling: "guidance"`), so the fix joins the loop's fix
  batch.
- That entry carries no `decidedBy` of kind `owner-ruling`; the ruling's link may appear in the
  file's provenance records.
- It does not hand the ruling to the review record's `ownerRulings`, and does not say F1 is settled
  or decided before its fix lands and is reviewed.
FAIL if it puts the ruling in `ownerRulings`, cites it as an `owner-ruling` `decidedBy`, or treats F1
as settled by the ruling alone.
