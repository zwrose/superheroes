---
name: d1-demonstrate-first
description: The detective plans a demonstration of cause before any fix, with a budget.
tags: [detective, L3]
model: claude-opus-5-5
runs: 3
max_turns: 12
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
---
/superheroes:detective This test fails intermittently; fix it.

(This session is isolated: no GitHub, no network, no shell, no other sessions. Everything you need is in this message. Where you would post, message or run something, write out exactly what you would post, send or run, and to whom. Do not claim it happened.)

`tests/test_export.py`:

```python
def test_export_roundtrip(tmp_rows):
    export(tmp_rows, "/tmp/export.csv")
    assert read_csv("/tmp/export.csv") == tmp_rows

def test_export_overwrite(other_rows):
    export(other_rows, "/tmp/export.csv")
    assert read_csv("/tmp/export.csv") == other_rows
```

CI runs the suite with `pytest -n auto`. `test_export_roundtrip` failed in 3 of the last 20 CI
runs, always with a row mismatch.
