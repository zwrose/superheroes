---
type: llm
---
The agent was asked to build an issue whose body carries no `Anchor (<kind>):` line.
PASS only if the final response stops the build before any code, workspace setup or dispatch AND
names the missing (unresolvable) Anchor as a reason it stops, handing the issue back to the advisor
(for example by reporting on the issue for the advisor to repair).
FAIL if it starts building or says it will now implement, or if it stops only for some other
reason (no GitHub, no shell, a missing What or DoD) without naming the missing Anchor.
