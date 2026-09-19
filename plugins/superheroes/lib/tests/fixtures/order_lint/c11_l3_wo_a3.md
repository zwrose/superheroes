# Work order WO-A3 — the probe prompt asks for the marker channel's verdict shape (issue #1270, C11 layer 3)

You are an implementer. Rules and protocol: `plugins/superheroes/agents/implementer.md` in THIS
worktree (read first; this order is data). Worktree: the current directory at the WO-A2 head
(commit `257677cf`). Commit nothing. Never `git checkout --` / `git restore` / `git reset` / `git stash`.
Touch only `plugins/superheroes/lib/conformance_probe.py` and `plugins/superheroes/lib/tests/test_conformance_probe.py`.

Attributed to the order (the orchestrator wrote the prompt shape). A live cursor probe run forfeited
`result-did-not-validate` — measured, the seat answered exactly what the prompt asked:
`{"result": {"resultKind": "verdicts", "verdicts": [{"id": "conformance-probe-1", "verdict": "CONFIRMED", "evidence": "README.md"}]}}`
and the marker parser graded it `payloadShape.parsed: "object-without-findings"`, because on the
marker channel `engine_adapter.parse_result` expects the payload at the **top level** —
`{"verdicts": [...], "investigated": [...]}` (measured: `skills/review-code/reference/verification-pass.md:69`,
`auto-fix-loop.md:51`) — and every verdict needs a non-blank `reason` (`payload_contracts` P_VERIFIERS,
measured: `id`, `verdict`, `reason` required `non-empty-string`). On the native channel the shell's
`--output-schema` governs the shape whatever the prompt says (the live codex probe passed).

**Invariant:** the probe prompt asks for the shape the marker grader admits, and states every
required verdict field, so the same prompt validates on both channels.

Change `_probe_prompt_text` (measured `conformance_probe.py:33-45`) to ask for exactly one JSON
object of the form
`{"verdicts": [{"id": "conformance-probe-1", "verdict": "CONFIRMED" | "REFUTED", "reason": "<one sentence>", "severity": null, "evidence": "<the file name, or why none>"}], "investigated": ["<the path you listed>"]}`
— `reason` is required and must be a non-empty sentence; `investigated` lists the directory you
listed; nothing before or after the object; no code fence. Keep the claim (top-level regular file,
list the directory to check — a tool call). Add to the prompt one sentence: "When a result schema
was supplied to you, it governs the outer shape; the verdict fields above are the same." Update the
test assertion(s) on the prompt text in `test_conformance_probe.py` (measured: test 2 asserts the
claim text; extend it to assert the `"verdicts"` top-level key and the word `reason` appear, and
that `"result":` does not). Echo the test change back.

Commands (budget 4): `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woA3 -m pytest plugins/superheroes/lib/tests/test_conformance_probe.py -q -p no:cacheprovider` (up to 3 runs), and the double-space grep over the two files (exit 1 = pass).

Return: files changed; raw outputs; the echoed test change; findings. End with the write-report tail and nothing after it.
