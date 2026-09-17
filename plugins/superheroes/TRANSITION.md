# Transition notes

This file records **consumer-visible shape changes** across plugin releases, newest release first.
Add an entry here whenever a release changes a contract that callers, orchestrators, or downstream
tools read — return shapes, artifact filenames, dispatch channels, or validation rules. Internal
refactors that leave every consumer-facing field unchanged do not belong here.

## Unreleased

### Certification receipt artifact

At a terminal, the driver now writes a **certification artifact** beside `round-receipt.json`:

- **Success** — `certification-receipt.json`: carries `terminalState`, `terminalCause`, per-seat
  provenance in `seats`, the `disclosures` block (`importantOutOfScope`), and each finding's
  disposition plus its disposition proof (`dispositionReceipt` where applicable).
- **Refusal** — `certification-refusal.json`: names one of the four escape classes
  (`unrun-review`, `same-family-seat`, `unfetched-findings`, `disposition-without-receipt`) and the
  artifact that failed.

`round-receipt.json` and `validate_receipt` are **unchanged** — same required keys, same validator,
same handback gate vocabulary. The certification artifact is separate machinery produced by
`round_certification.certify`.

**`certificationShape` rule (writer receipt only).** Any hand-landed seat forces
`audited-chain`, never `full-panel-confirmed` (and any `full-panel*` shape in loop state is
downgraded the same way). The driver's `round-receipt.json` still records the loop's own shape;
only the certification receipt applies this override.

### `run_loop` return contract

`round_driver.run_loop` now returns the certification writer's **receipt or refusal** directly.
There is no fallback to a legacy `build_receipt`-only dict.

| Outcome | What you get | How to read it |
| --- | --- | --- |
| Certified | Receipt dict with `verdict`, `terminalState`, `terminalCause`, `seats`, `disclosures`, … | Same field names as `certification-receipt.json`; `terminalState` is `certified` on success. |
| Escape-class refusal | Refusal dict with `class` (one of the four escape classes), `artifact`, `detail`, optional `bindingFailure` | No `verdict` key — discriminate on `class`, not `receipt["verdict"]`. |
| Writer fault | Refusal dict with `class: "writer-fault"` | Internal writer crash or empty return; not one of the four escape classes. |
| Any refusal from `run_loop` | Above plus `loopTerminal`, `loopCertificationShape`, `loopRounds` | `loopTerminal` is what the loop reached; it asserts nothing about certification. |

**Migration.** Callers that tested `receipt["verdict"]` on the `run_loop` return must branch:

```python
result = run_loop(seams, config)
if "class" in result:
    # refusal — inspect result["class"]; use result.get("loopTerminal") for loop observability
    ...
elif result.get("terminalState") == "certified":
    # certification receipt
    ...
```

A refusal carries the loop's own terminal in `loopTerminal` alongside its refusal class.

### Codex dispatch channel

Codex review and write dispatches now run with **`--json`** and **`--output-last-message`**. Engagement
is read from codex's own JSONL event stream (`engagement.source` is `codex-events` when tool-call
telemetry parses). The review findings payload is read from the **last-message file**
(`codex_review_payload_text`); the event stream's last `agent_message` item is the fallback when the
file is absent.

Consumers that parsed review output from codex stdout must read the last-message file (or the
structured event stream) instead of treating raw stdout as the findings payload.
