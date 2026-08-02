# Contents

1. [Status and scope](#status-and-scope)
2. [The `pilot` block](#the-pilot-block)
3. [Field table](#field-table)
4. [Why two values are refused inline](#why-two-values-are-refused-inline)
5. [The probe vocabulary](#the-probe-vocabulary)
6. [Capture surfaces](#capture-surfaces)
7. [Declare and exercise](#declare-and-exercise)
8. [Seed and mint call shapes](#seed-and-mint-call-shapes)
9. [Slot reference format](#slot-reference-format)

---

## Status and scope

This document is the normative contract home for the pilot framework (issue #822, epic #821).
It pins the schema, types, probe vocabulary, seed/mint call shapes, and refusal tokens that
downstream sub-issues build against.

**What this pins:** the optional nested `pilot` key inside `test-pilot-config`; the ten-token
probe vocabulary (`lib/pilot_probe.py`); slot reference format and account-set types
(`lib/pilot_slot.py`); seed/mint call shapes and artifact verification (`lib/pilot_seed.py`);
and the contract validator (`lib/pilot_contract.py`, wired into `engine.load_profile_config`).

**What this deliberately does not build** (successor sub-issues own these):

- Generation allocation, incrementing, or staleness comparison (**A2a**).
- Where the policy document lives or how it is read (**A3**).
- Browser context creation, credential injection, or broker-side stale-generation enforcement (**C7**).
- Running a live cleanup and capturing its effect receipt (**C9**).
- The measured operating ceiling and its degradation receipts (**D11b**).
- App stand-up, teardown, or wave-deadline runtime (**B5**).

This wave ships types, vocabulary, schema, and call shapes only.

## The `pilot` block

The `pilot` key is **optional**. When absent, the engine behaves exactly as it does today.
When present, it nests inside the shipped `test-pilot-config` block:

```json test-pilot-config
{
  "schemaVersion": 1,
  "baseUrl": "{{base-url}}",
  "allowedOrigins": [],
  "dbEnvVar": "{{DB_ENV_VAR}}",
  "apiBase": "{{api-base}}",
  "protectedTargets": ["{{main-db-name}}", "{{main-db-uri-glob}}"],
  "browserTools": ["{{tool-1}}", "{{tool-2}}"],
  "devCommand": ["{{cmd}}", "{{arg}}"],
  "readinessUrl": "{{readiness-url}}",
  "mayManageServer": true,
  "pilot": {
    "schemaVersion": 1,
    "signInPath": "captured",
    "credentialSet": [
      {"account": "owner", "role": "resource-owner"},
      {"account": "guest", "role": "share-recipient"}
    ],
    "captureSurface": ["cookies", "localStorage"],
    "captureOptions": {"indexedDB": false, "credentials": false},
    "validityProvenance": "server-probe",
    "identityProbe": {"path": "/api/me", "unseededExpectation": "no-session"},
    "cleanup": {"command": ["npm", "run", "fixtures:clean", "--", "--namespace", "{namespace}"]},
    "administrativeMax": 4,
    "effectsEscape": {"canEscape": false, "evidence": "dev mail capture + sandboxed outbound calls"},
    "policyRef": {"declaration": "example-project-pilot-policy"},
    "mint": {
      "envelope": {
        "enablingFlagEnvVar": "ALLOW_TEST_MINT",
        "enabledScopes": ["development"],
        "forbiddenScopes": ["production", "staging"],
        "gateOffTestCommand": ["npm", "run", "test:mint-gate-off"]
      },
      "sentinelIdentifier": "pilot-sentinel-no-such-account"
    }
  }
}
```

The normative `pilot` object shape (shown above under `"pilot":`) is:

```json
{
  "schemaVersion": 1,
  "signInPath": "captured",
  "credentialSet": [
    {"account": "owner", "role": "resource-owner"},
    {"account": "guest", "role": "share-recipient"}
  ],
  "captureSurface": ["cookies", "localStorage"],
  "captureOptions": {"indexedDB": false, "credentials": false},
  "validityProvenance": "server-probe",
  "identityProbe": {"path": "/api/me", "unseededExpectation": "no-session"},
  "cleanup": {"command": ["npm", "run", "fixtures:clean", "--", "--namespace", "{namespace}"]},
  "administrativeMax": 4,
  "effectsEscape": {"canEscape": false, "evidence": "dev mail capture + sandboxed outbound calls"},
  "policyRef": {"declaration": "example-project-pilot-policy"},
  "mint": {
    "envelope": {
      "enablingFlagEnvVar": "ALLOW_TEST_MINT",
      "enabledScopes": ["development"],
      "forbiddenScopes": ["production", "staging"],
      "gateOffTestCommand": ["npm", "run", "test:mint-gate-off"]
    },
    "sentinelIdentifier": "pilot-sentinel-no-such-account"
  }
}
```

## Field table

| Field | Type | Required | Closed enum / condition | Refusal token |
|---|---|---|---|---|
| `schemaVersion` | integer | required | must be `1` | `pilot-schema-version-unsupported` |
| `signInPath` | string | required | `captured` or `minted` | `pilot-sign-in-path-invalid` |
| `credentialSet` | array of objects | required | non-empty | `pilot-credential-set-empty` |
| `credentialSet[]` entry | object | per entry | must have `account` (non-empty string) and `role` (non-empty string); no duplicate `account` keys | `pilot-credential-set-invalid` (malformed entry); `pilot-account-key-duplicate` (duplicate `account`); `pilot-account-key-invalid` (`account` empty or non-string); `pilot-account-role-missing` (`role` absent or empty) |
| `credentialSet[].expectedIdentity` | — | **refused** | must not appear inline | `pilot-expected-identity-inline-refused` |
| `captureSurface` | array of strings | required | non-empty; members must be known surfaces (see [Capture surfaces](#capture-surfaces)) | `pilot-capture-surface-invalid` (absent, empty, or unknown member); `pilot-capture-surface-session-storage-refused` (`sessionStorage` present) |
| `captureOptions` | object | required | keys `indexedDB` and `credentials`, each boolean; must agree with `captureSurface` (two-way) | `pilot-capture-options-invalid` (malformed); `pilot-capture-options-mismatch` (disagrees with `captureSurface`) |
| `validityProvenance` | string | required | `cookie-expiry`, `token-claim`, `server-probe`, `unknown` | `pilot-validity-provenance-invalid` |
| `identityProbe` | object | required | must have `path` (non-empty string) and `unseededExpectation` (probe token) | `pilot-identity-probe-invalid` (malformed); `pilot-identity-probe-expectation-unknown` (`unseededExpectation` not a probe token) |
| `cleanup` | object | required | must have `command` | see `cleanup.command` |
| `cleanup.command` | array of strings | required | non-empty strings; must contain `{namespace}`; `{namespace}` must not appear at `argv[0]` | `pilot-cleanup-command-invalid` (absent or not a list of non-empty strings); `pilot-cleanup-unparameterized` (no `{namespace}`); `pilot-cleanup-placeholder-in-argv0` (`{namespace}` at `argv[0]`) |
| `administrativeMax` | integer | required | `>= 1` | `pilot-administrative-max-invalid` |
| `effectsEscape` | object | required | must be present (no default) | `pilot-effects-escape-absent` |
| `effectsEscape.canEscape` | boolean | required | — | `pilot-effects-escape-invalid` |
| `effectsEscape.evidence` | string | required | non-empty | `pilot-effects-escape-evidence-missing` |
| `policyRef` | object | required | must have `declaration` | `pilot-policy-ref-missing` (`declaration` absent or empty) |
| `mint` | object | conditional | required when `signInPath` is `"minted"`; optional otherwise | `pilot-mint-declaration-missing` |
| `mint.mintableAccounts` | — | **refused** | must not appear inline | `pilot-mintable-allowlist-inline-refused` |
| `mint.envelope` | object | required when `mint` present | must include `enablingFlagEnvVar`, `enabledScopes`, `forbiddenScopes`, `gateOffTestCommand`; `enabledScopes` and `forbiddenScopes` must not overlap | `pilot-mint-envelope-incomplete`; `pilot-mint-envelope-scope-conflict` |
| `mint.envelope.gateOffTestCommand` | array of strings | required | non-empty command argv | `pilot-mint-gate-off-test-missing` |
| `mint.sentinelIdentifier` | string | required when `mint` present | non-empty | `pilot-mint-sentinel-missing` |
| *(any unrecognised key)* | — | — | — | `pilot-unknown-field` |

## Why two values are refused inline

Two fields are deliberately **not** carried in the `pilot` block and are refused by name when
present:

- **`expectedIdentity`** on each credential-set entry (`pilot-expected-identity-inline-refused`).
- **`mint.mintableAccounts`** (`pilot-mintable-allowlist-inline-refused`).

This block can live in-repo at `.claude/superheroes/test-pilot.md`, where a branch could edit
the very allowlist or identity expectations the engine checks against. The expected pilot
identity for each account and the mintable-account allowlist are **policy** — they are resolved
from a policy document that sub-issue **A3** places outside builder reach. The block carries
only `policyRef.declaration`, a name that resolves against that external policy document.

## The probe vocabulary

The probe vocabulary has exactly ten tokens, defined in `lib/pilot_probe.py`. Every token
must appear in this document so drift tests can catch vocabulary additions without a
corresponding doc update.

**All ten tokens:**

- `transport-error`
- `unexpected-status`
- `invalid-body`
- `no-session`
- `wrong-identity`
- `disabled-account`
- `unauthorized`
- `forbidden`
- `rate-limited`
- `infrastructure-unavailable`

**Three disjoint classes** (union is the whole set):

| Class | Tokens | Routing rule |
|---|---|---|
| **lapse** | `no-session` | The **only** token that routes to the mid-wave lapse path |
| **infrastructure** | `transport-error`, `unexpected-status`, `invalid-body`, `rate-limited`, `infrastructure-unavailable` | Never routes to lapse |
| **identity** | `wrong-identity`, `disabled-account`, `unauthorized`, `forbidden` | A real answer from the application about the session's identity or authority; never routes to lapse |

Only `no-session` routes to the mid-wave lapse path. Infrastructure classifications never do.

Public API in `pilot_probe.py`: `REASON_<UPPER_SNAKE>` constants, `LAPSE_REASONS`,
`INFRASTRUCTURE_REASONS`, `IDENTITY_REASONS`, `ALL_PROBE_REASONS` (derived as the union of
the three classes), `EXPECTED_TOKEN_COUNT = 10`, `routes_to_lapse(reason)`,
`is_infrastructure(reason)`, `classify(reason)` (returns `"lapse"` / `"infrastructure"` /
`"identity"`; raises `ValueError` on an unknown token).

## Capture surfaces

| Declared surface | Required capture option |
|---|---|
| `cookies` | none (carried by default) |
| `localStorage` | none (carried by default) |
| `indexedDB` | `captureOptions.indexedDB` must be `true` |
| `webauthn` | `captureOptions.credentials` must be `true` |
| `sessionStorage` | **never carried — refused by name** (design decision D7) |

The check is **two-way**: a declared surface's option must be `true`, and an option must be
`false` when its surface is not declared (no over-broad capture). The mapping lives in one
place: `pilot_seed.required_context_options(capture_surfaces)` returning
`{"indexedDB": <bool>, "credentials": <bool>}`.

`sessionStorage` is refused by name (`pilot-capture-surface-session-storage-refused`), not
treated as an unknown surface value.

## Declare and exercise

Every pilot declaration must be **exercised** before the engine treats it as present. The
registry document shape:

```json
{
  "schemaVersion": 1,
  "records": [
    {
      "kind": "identity-probe",
      "declarationDigest": "a1b2c3d4e5f60718",
      "exercisedAt": "2026-08-02T04:00:00Z",
      "receipt": {"result": "pass", "evidence": "seeded returned the recorded identity; unseeded returned no-session"}
    }
  ]
}
```

**Declaration kinds:** `identity-probe`, `capture-reduction`, `cleanup-containment`,
`mint-gate-off`, `mint-account-allowlist`, `effects-escape`, `operating-ceiling`.

**Two load-bearing rules:**

1. **A declaration that has never been exercised is treated as absent, and absent refuses.**
2. **Every record is bound to a digest of the exact declaration it exercised**, so changing
   the probe, the cleanup command, the account set, or the mint envelope invalidates the old
   receipt rather than inheriting it.

A record whose digest does not match the current declaration, whose receipt is empty, or whose
receipt does not carry `result: "pass"` counts as **absent**.

### Registry refusal tokens

| Token | When returned |
|---|---|
| `pilot-declaration-unexercised` | `require_exercised` is called for a declaration that has no matching exercised record |
| `pilot-declaration-kind-unknown` | `is_exercised` or `require_exercised` is called with a `kind` not in the declaration-kind set |

## Seed and mint call shapes

Call shapes live in `lib/pilot_seed.py`. Refusal tokens use the `seed-*`, `artifact-*`, and
`mint-*` prefixes (§S4).

### `required_context_options(capture_surfaces)`

Returns `{"indexedDB": <bool>, "credentials": <bool>}` for the declared capture surfaces.
See [Capture surfaces](#capture-surfaces) for the two-way mapping rules.

| Token | When returned |
|---|---|
| `seed-capture-surfaces-invalid` | `capture_surfaces` is not a JSON array (a Python `list`) of strings |
| `seed-capture-surfaces-empty` | `capture_surfaces` is an empty JSON array (a Python `list`) |
| `seed-capture-surface-duplicate` | the same surface appears more than once |
| `seed-capture-surface-session-storage-refused` | `sessionStorage` is declared |
| `seed-capture-surface-unknown` | a surface is not in the known set (including an empty string) |

### `verify_artifact(path, *, expected_uid, expected_mode, recorded_sha256)`

Verify-at-seed artifact integrity. Returns an `ok`/`reason` dict (never raises on artifact
failure). Checks run in this order:

1. Path has a traversal component (`..` or absolute escape) → `artifact-path-traversal`
2. No symlink in the path ancestry → `artifact-symlink-in-path`
3. File exists → `artifact-missing`
4. File is a regular file → `artifact-not-regular-file`
5. Owner UID matches `expected_uid` → `artifact-owner-mismatch`
6. Mode bits match `expected_mode` → `artifact-mode-mismatch`
7. SHA-256 digest matches `recorded_sha256` → `artifact-hash-mismatch`
8. File is readable (including hash read), or any other `OSError` during checks → `artifact-unreadable`

Invalid caller arguments (`expected_uid`, `expected_mode`, `recorded_sha256`) raise
`PilotSeedError` with `seed-verify-argument-invalid` before any filesystem check runs.

### `seed_request(slot_ref, account, artifact, context_options)`

Builds a seed request descriptor after local validation and artifact verification.

- `slot_ref` — slot reference string (`<slot>@<generation>`).
- `account` — account name from the credential set.
- `artifact` — mapping with `path`, `expectedUid`, `expectedMode`, `sha256`.
- `context_options` — `{"indexedDB": bool, "credentials": bool}` from
  `required_context_options`.

Calls `verify_artifact` and refuses with the artifact token on failure. Returns a descriptor
with `slotRef`, `account`, `artifact` (path + verified sha256), and `contextOptions`.

| Token | When returned |
|---|---|
| `seed-slot-ref-invalid` | `slot_ref` does not parse as a valid slot reference |
| `seed-account-invalid` | `account` is missing, empty, or not a string |
| `seed-context-options-invalid` | `context_options` is not exactly `{"indexedDB": bool, "credentials": bool}` |
| `seed-verify-argument-invalid` | the `artifact` mapping is malformed or has invalid verify arguments |

### `mint_request(account, *, allowlist, envelope)`

Builds a mint-client request descriptor.

- `account` — account to mint.
- `allowlist` — **required caller-supplied argument**; the module never reads an inline
  allowlist from config. Policy resolution is A3's job.
- `envelope` — mint envelope from the `pilot` block.

The mint allowlist is policy and must be supplied by the caller at mint time, not embedded in
the branch-mutable `pilot` block.

| Token | When returned |
|---|---|
| `mint-allowlist-empty` | `allowlist` is missing, empty, or not a JSON array (a Python `list`) of non-empty strings |
| `mint-account-invalid` | `account` is missing, empty, or not a string |
| `mint-account-not-in-allowlist` | `account` is not in the caller-supplied allowlist |
| `mint-envelope-incomplete` | `envelope` is missing `enablingFlagEnvVar` |

### `sentinel_probe_request(sentinel, *, allowlist, envelope)`

Builds a sentinel probe request for the mint gate-off exercise.

- `sentinel` — identifier that must correspond to **no real account**.
- `allowlist` — caller-supplied mintable-account allowlist.
- `envelope` — mint envelope.

**The sentinel must not be a mintable account.** If the sentinel appears in the allowlist, the
live probe would succeed (mint would return a session) instead of exercising the gate-off
refusal — the probe would not detect a disabled mint gate.

| Token | When returned |
|---|---|
| `mint-allowlist-empty` | `allowlist` is missing, empty, or not a JSON array (a Python `list`) of non-empty strings |
| `mint-account-invalid` | `sentinel` is missing, empty, or not a string |
| `mint-sentinel-in-allowlist` | `sentinel` appears in the caller-supplied allowlist |

## Slot reference format

Slot references use the format `<slot>@<generation>` (§S5).

- `<slot>` matches `store.SLOT_RE` (`^[A-Za-z0-9][A-Za-z0-9_-]*$` — import from `store`,
  never re-type the pattern). The alphabet excludes `@`, which makes the format injective.
- `<generation>` is a decimal integer ≥ 1 with no leading zeros and no sign.

**Round-trip guarantee:** `parse_slot_ref(format_slot_ref(slot, generation)) == (slot,
generation)` for every valid `(slot, generation)` pair.

Types and validation live in `lib/pilot_slot.py`.

| Token | When returned |
|---|---|
| `slot-id-invalid` | slot id is not a string matching `SLOT_RE` |
| `slot-generation-invalid` | generation is not an integer ≥ 1 (bools excluded) |
| `slot-ref-malformed` | slot reference string is not `<slot>@<generation>` |
| `slot-account-set-empty` | account set is empty or not a sequence |
| `slot-account-duplicate` | the same `account` appears more than once |
| `slot-account-role-missing` | an entry has no non-empty `role` |
| `slot-account-entry-invalid` | an entry is not a mapping with a non-empty `account` string |
