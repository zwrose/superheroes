# Contents

1. [Decision points — skill-surface contract](#decision-points--skill-surface-contract-1144)
2. [Known limitation](#known-limitation)
3. [1a — Decision block grammar](#1a--decision-block-grammar)
4. [1b — Forbidden primitives and waiting tokens](#1b--forbidden-primitives-and-waiting-tokens)
5. [1c — Carrier registry](#1c--carrier-registry)
6. [1d — Structural exemptions](#1d--structural-exemptions--and-nothing-else)

# Decision points — skill-surface contract (#1144)

Every skill-surface site that takes a default or would otherwise wait for an owner answer must
be wrapped in a declared **decision block**. Owner-decision primitives are **forbidden outside**
such a block. This contract implements `rubric/escalation-base.md` (`escalation-version: 3`) at
each site: NOTIFY **discloses without waiting**; GATE — stop, write the decision down, and hand
back — **never wait for an answer**.

The mechanical census lives in `lib/tests/test_decision_point_census.py`. Read this file before
converting a skill surface.

## Known limitation

A decision point phrased entirely outside the forbidden-primitive vocabulary below is **not**
detected. There is no runtime chokepoint for skill prose; this closed-world prohibition list is
the strongest available construction, and the limitation is disclosed rather than hidden. Carrier
delivery is not checked at all — by owner ruling 2026-08-25 (`a`-and-stop).

## 1a — Decision block grammar

A decision block is a bounded pair of HTML comments:

```html
<!-- decision-point: id=<kebab-case-id> mode=<proceed|notify|gate> kind=<storage-location|ask-user-question|interview-step|owner-gate> default="<what is taken when nobody answers>" carrier=<carrier-key> -->
   … the site's prose …
<!-- /decision-point: id=<same-id> -->
```

The census enforces:

- **`id`** is unique across the whole `skills/` tree. Duplicates are an error.
- Every open has a matching close with the **identical** `id`; an orphan close or unmatched open
  is an error. Blocks **do not nest**.
- **`mode`** is exactly one of `proceed`, `notify`, or `gate` (the three rubric modes).
- **`kind`** is exactly one of `storage-location`, `ask-user-question`, `interview-step`,
  `owner-gate`.
- **`default`** is a non-empty quoted string in the open tag.
- **`carrier`** is a key from the carrier registry in §1c — never free prose. It names the
  intended durable home of the disclosure (a declaration, not a verified delivery guarantee — see
  §1c).
- The prose inside the block must name **`/superheroes:configure`** as the follow-up.

**Mode-specific structure** (enforced inside the block prose, every mode):

| mode | required prose |
| --- | --- |
| `gate` | states that the decision is **written down** and the run **hands back**; must not contain a waiting token (§1b) |
| `notify` | names the **action taken** and states that the **run continues**; must not contain a waiting token |
| `proceed` | records the default taken and continues; must not contain a waiting token |

**No block of any mode may contain a waiting token** (§1b).

## 1b — Forbidden primitives and waiting tokens

Two fixed sets — the census reads these literally (after `*` emphasis is normalized away
before matching; backticks and underscores are not, because a backtick distinguishes a mention from
an invocation; underscore-emphasis is a stated limitation — see the census module docstring) and
cross-line joining for multi-word literals).

**Forbidden outside a decision block** (unless byte-pinned or rubric-excluded per §1d):

- `AskUserQuestion`
- `decide-location)` (the CLI invocation substring)
- `present-judgment`
- `present-stall-menu`
- `one question at a time`
- `one-question-at-a-time`
- `Ask, one at a time`
- `only on the owner's explicit confirm`
- `only what they approve`
- `Only if they decline`
- `STOP and guide`
- `ask the user to start`

**Waiting tokens** (forbidden **inside** any block, every mode):

- `wait for`
- `waits for`
- `until they answer`
- `until the owner answers`
- `and wait`

## 1c — Carrier registry

Each `carrier=` value must resolve to a registry key. The census checks the name; an unknown
carrier is an error from the block parser.

The `carrier` names the **intended durable home** of the disclosure. It is a **declaration, not a
verified guarantee**: no test asserts that a disclosure reaches its writer. Owner ruling 2026-08-25
(`a`-and-stop) declined the mechanical-carrier redesign with a registry trigger — a field case where
a silently-taken provisional default actually costs the owner something reopens it.

| key | artifact | writer | census assertion |
| --- | --- | --- | --- |
| `review-crew-layer` | `## Setup disclosures` in the review-crew layer | `core_md.py write-layer --hero review-crew` | registry key only; no delivery assertion |
| `test-pilot-layer` | `## Setup disclosures` in the test-pilot layer | `core_md.py write-layer --hero test-pilot` | registry key only; no delivery assertion |
| `review-spec-receipt` | `$SESSION_DIR/receipt.md` | review-spec's own assembly step | registry key only; no delivery assertion |
| `audit-report` | `$SESSION_DIR/report.md` | audit-debt's report write | registry key only; no delivery assertion |
| `review-code-meta` | `$SESSION_DIR/meta.json` | review-code setup's meta encode | for `kind=storage-location` blocks only: `test_storage_decision_blocks_capture_source` in `lib/tests/test_decision_point_census.py` requires the block's own fenced bash to assign `SOURCE` from `decide-location`'s `.source` and to cover `$SOURCE` in its usable-value guard — shell text inside the block, not delivery to `meta.json` |
| `doc-policy-disclosures` | the `disclosures` field of `doc-policy.json` | `architect_config.write_policy` | registry key only; no delivery assertion |
| `run-output` | the run's own report to the owner | the run itself | registry key only; no file writer — use where a decision is reported to the owner in the session, in particular where a **gate hands back before any writer executes** |

**Carrier note:**

- **`review-spec-receipt`** — lives in a `mktemp` `$SESSION_DIR` and is persisted only by an issue
  post conditional on a linked issue and a working `gh`; that is a known property of this carrier,
  not a census gap awaiting another work order.

## 1d — Structural exemptions — and nothing else

No rationale is ever accepted. A forbidden primitive outside a block is permitted only if:

**Byte-pinned line** — the exact stripped line text appears in the census pin table
(`test_decision_point_census.py`). A pin is a *literal*, never a reason; when the line changes the
pin stops matching and the site must be re-adjudicated. Use for prohibition text ("Never open
AskUserQuestion"), historical notes, and reference docs that *name* a phase rather than instruct
a wait.

**Rubric-excluded surface** — `rubric/escalation-base.md` § Scope says the rubric "does **not**
govern **discovery**: discovery is *elicitation*, not escalation … its one-question-at-a-time
dialogue is not an escalation to be minimized." Exempt exactly the surfaces the rubric excludes:
`skills/architect-discovery/**`. The exclusion is the rubric's, not the detector's.
