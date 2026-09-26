---
type: llm
---
PASS only if the reply explains that `git rebase --onto` replays a range of commits onto a new base
(the new base, the old upstream, the branch) and gives a concrete example command.
FAIL if it gives no explanation of what moves where, or no example.
