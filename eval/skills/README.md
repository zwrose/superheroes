# On-Demand Skill Activation Runbook

This runbook describes the procedure for recording skill activation observations and
scoring them against the fixtures. The procedure is agent-driven and requires no paid
API calls beyond the normal Claude Code session.

## When to run

Run this procedure:
- Before recording a new baseline (Task 14)
- After any description change to a skill (UFR-4)
- After splitting a skill body into reference files (Tasks 15–17)
- At any time you want to verify activation health (UFR-5)

The recorded `activation-result.json` is a **required artifact of done** — a task that
changes a skill description or body is not complete until this file is regenerated and
every skill scores `pass`.

## Procedure

### 1. Load all 14 skill descriptions

Before judging any fixture phrase, read the `description:` frontmatter field of every
skill SKILL.md in `plugins/superheroes/skills/`:

```
plugins/superheroes/skills/audit-debt/SKILL.md
plugins/superheroes/skills/review-code/SKILL.md
plugins/superheroes/skills/review-init/SKILL.md
plugins/superheroes/skills/review-plan/SKILL.md
plugins/superheroes/skills/review-spec/SKILL.md
plugins/superheroes/skills/review-tasks/SKILL.md
plugins/superheroes/skills/test-pilot-execute/SKILL.md
plugins/superheroes/skills/test-pilot-init/SKILL.md
plugins/superheroes/skills/test-pilot-plan/SKILL.md
plugins/superheroes/skills/architect-discovery/SKILL.md
plugins/superheroes/skills/architect-plan/SKILL.md
plugins/superheroes/skills/architect-tasks/SKILL.md
plugins/superheroes/skills/architect-spec/SKILL.md
plugins/superheroes/skills/workhorse/SKILL.md
```

Judgment must be made in the context of ALL 14 descriptions simultaneously — not in
isolation — because activation is a selection among competing skills.

### 2. Load fixtures

For each skill, load `eval/skills/fixtures/<plugin>__<skill>.json`. Each fixture has:
- `should_fire`: phrases that SHOULD activate this skill (and not a sibling)
- `should_not_fire`: phrases that should activate a SIBLING skill, NOT this one

### 3. Judge each phrase 3 times

For every phrase in both directions, present it to yourself as a live model 3 times
(runs 0, 1, 2). Because the judgment is deterministic for clear phrases, the 3 runs
will typically produce identical results. If you genuinely waver, record the actual
judgment for each run independently.

Judgment rules:
- **`should_fire` phrase of skill S**: would skill S be the one that activates? YES → `activated=true`; NO → `activated=false`
- **`should_not_fire` phrase of skill S**: would skill S activate? If a sibling fires instead → `activated=false`; if S fires anyway → `activated=true`

Judge **honestly**. If a `should_fire` phrase is ambiguous and S would not clearly win,
record `activated=false` (a miss). Then sharpen the fixture phrase to be more
discriminating and re-judge — the baseline must be green, so any miss must be resolved
before committing.

### 4. Record observations

Write all observations to `eval/skills/activation-result.json`:

```json
{
  "recordedAt": "YYYY-MM-DD",
  "observations": [
    {"skill": "<plugin>/<skill>", "phrase": "<phrase text>", "direction": "should_fire", "run": 0, "activated": true},
    {"skill": "<plugin>/<skill>", "phrase": "<phrase text>", "direction": "should_fire", "run": 1, "activated": true},
    {"skill": "<plugin>/<skill>", "phrase": "<phrase text>", "direction": "should_fire", "run": 2, "activated": true},
    ...
  ]
}
```

The `skill` key uses a **slash** (`<plugin>/<skill>`), matching the registry and fixture
keys (the fixture filenames use `__` as a separator, but the observation key uses `/`).

One row per `(skill, phrase, direction, run)`.

### 5. Run the scorer

```bash
cd eval/lib && python3 -c "
import json, activation_score, skills, os, glob

obs = json.load(open('../skills/activation-result.json'))['observations']
fx = {
    os.path.splitext(os.path.basename(p))[0].replace('__', '/'):
    json.load(open(p))
    for p in glob.glob('../skills/fixtures/*.json')
}
result = activation_score.score(obs, fx, {}, {})
for skill, v in sorted(result.items()):
    print(f\"{v['verdict']:12s}  {skill}\")
"
```

### 6. Interpret results

| Verdict    | Meaning                                                                        |
|------------|--------------------------------------------------------------------------------|
| `pass`     | Every phrase in every direction passed across all runs.                        |
| `fail`     | At least one phrase consistently failed (0/N runs correct). Fix the phrase or the description. |
| `re-run`   | At least one phrase was intermittent. Re-judge more carefully; sharpen if ambiguous. |
| `carved-out` | An owner-approved pre-existing miss on an unchanged skill (see UFR-6).       |

Every skill must be `pass` (or `carved-out` with owner approval) before the baseline
is recorded as done.

### 7. Required artifact

`eval/skills/activation-result.json` is a **required artifact of done** (UFR-5). Its
`recordedAt` date must be on or after the date of the most recent skill change in the
commit being recorded. Commit it alongside any changes to skills or their descriptions.
