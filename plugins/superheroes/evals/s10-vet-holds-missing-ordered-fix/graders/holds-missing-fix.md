---
type: llm
---
PASS only if all of these hold:
- The verdict in `owner-half.md` is NOT-READY.
- `receipt.md` names the leftover row (the row that checks no leftover skipped the owner's review)
  as the row that held the PR, and says why: the owner's ruling on F1 ordered a retry cap of three,
  which holds at the record's final commit A but not at head B, where uploads retry five times.
- Nothing in either file treats F1 as settled because its ruling link resolves or because head
  coverage answered `proven`.
FAIL if the verdict is READY or PARKED, if the receipt holds the PR on some other row without naming
the leftover row and the missing cap at B, or if F1 is passed because the cap holds at A.
