---
type: llm
---
PASS only if all of these hold:
- The verdict in `owner-half.md` is NOT-READY or PARKED, never READY.
- The receipt or the owner half says the owner's ruling on F1 ordered a fix (a retry cap of three)
  that the reviewed head does not hold (it still allows five retries).
- It does not treat F1 as settled merely because the review record files it as an owner ruling.
FAIL if the verdict is READY, or if F1 is passed because its ruling link resolves without the
ordered fix being checked.
