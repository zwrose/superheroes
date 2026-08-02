# Contents

1. [Status and scope](#status-and-scope)
2. [The `pilot` block](#the-pilot-block)
3. [Field table](#field-table)
4. [Why two values are refused inline](#why-two-values-are-refused-inline)
5. [The probe vocabulary](#the-probe-vocabulary)
6. [Capture surfaces](#capture-surfaces)
7. [Declare and exercise](#declare-and-exercise)
8. [The target boundary](#the-target-boundary)
9. [Datastore identity](#datastore-identity)
10. [The policy document](#the-policy-document)
11. [Results travel, never policy](#results-travel-never-policy)
12. [Provisioning authorization](#provisioning-authorization)
13. [Seed and mint call shapes](#seed-and-mint-call-shapes)
14. [Slot reference format](#slot-reference-format)
15. [Slot lifecycle and generations](#slot-lifecycle-and-generations)
16. [The provisioning journal](#the-provisioning-journal)
17. [The partial-failure report](#the-partial-failure-report)
18. [Per-slot browser topology](#per-slot-browser-topology)
19. [Browser context creation and seed injection](#browser-context-creation-and-seed-injection)
20. [The provisioning gate](#the-provisioning-gate)

---

## Status and scope

This document is the normative contract home for the pilot framework (issue #822, epic #821).
It pins the schema, types, probe vocabulary, seed/mint call shapes, and refusal tokens that
downstream sub-issues build against.

**What this pins:** the optional nested `pilot` key inside `test-pilot-config`; the ten-token
probe vocabulary (`lib/pilot_probe.py`); slot reference format and account-set types
(`lib/pilot_slot.py`); seed/mint call shapes and artifact verification (`lib/pilot_seed.py`);
the contract validator (`lib/pilot_contract.py`, wired into `engine.load_profile_config`);
sub-issue **A3** — the per-slot target boundary (`lib/pilot_boundary.py`), the policy
document home (`lib/pilot_policy.py`), and the provisioning authorization layer
(`lib/pilot_provision.py`); and sub-issue **A2a** — the slot lifecycle and generation
allocation (`lib/pilot_lifecycle.py`) plus the provisioning journal and partial-failure
report (`lib/pilot_journal.py`).

**What this deliberately does not build** (successor sub-issues own these):

- Quarantine, sweep, the reassignment acceptance probe, deletion rules, and any recovery path out of
  `failed` (**A2b**).
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

## The target boundary

A **binding** is a validated per-slot target contract: a canonical slot reference, an exact
**origin** (`<scheme>://<host>:<port>`), a list of **permitted redirects** (each an exact
origin), and a non-empty **protected targets** list. Origins are never patterns — every
scheme/host/port triple is parsed and canonicalized; implicit ports, wildcards, userinfo,
path/query/fragment suffixes, and other non-canonical forms refuse.

`target_binding(slot_ref, *, origin, permitted_redirects, protected_targets)` builds the
binding dict. `check_target(binding, url)` and `check_redirect(binding, url)` evaluate
candidate URLs without raising on malformed input. Protected targets are checked **before**
the allowlist: a URL whose canonical origin appears in `protectedTargets` is refused with
`boundary-protected-target-refused` even when it equals the slot origin or a permitted
redirect. There is **no `--allow-protected` equivalent** on this path — unlike the engine's
`gate_violations`, which `--allow-protected` can bypass, protected-target refusal here is
unconditional.

Protected targets are a **two-class** list:

1. **URL-shaped entries** (contain `://`) — parsed and canonicalized to exact origins
   (`<scheme>://<host>:<port>`). Compared by `check_target` and `check_redirect` against
   candidate URL origins, and by `check_protected_identity` when the identity string equals the
   canonical origin.
2. **Opaque identity tokens** (no `://`) — stored verbatim. Compared only by
   `check_protected_identity` against datastore identity strings (for example a database name).
   A bare hostname such as `login.example.com` protects a **datastore identity** with that
   name, not a URL — an owner meaning to protect a URL must write the full origin including
   scheme and port (for example `https://login.example.com:443`).

URL-shaped entries that do not parse refuse at binding time. Opaque tokens are never
interpreted as hostnames for origin matching.

Public API in `lib/pilot_boundary.py`: `parse_origin`, `target_binding`, `check_target`,
`check_redirect`, `check_protected_identity`, `boundary_verdict`, `authorize_credentials`.

### Target boundary refusal tokens

| Token | When returned |
|---|---|
| `boundary-origin-invalid` | `parse_origin` receives a non-canonical origin; or `check_target` / `check_redirect` receives a URL that does not parse as an exact origin |
| `boundary-slot-ref-invalid` | `target_binding` receives a slot reference that does not parse |
| `boundary-redirects-invalid` | `permitted_redirects` is not a list, or any redirect does not parse as an exact origin |
| `boundary-protected-targets-invalid` | `protected_targets` is missing, empty, not a list, contains a non-string or empty entry, or contains a URL-shaped entry that does not parse |
| `boundary-target-off-allowlist` | `check_target`: parsed origin is not the binding origin and is not protected |
| `boundary-redirect-off-allowlist` | `check_redirect`: parsed origin is neither the binding origin nor a permitted redirect and is not protected |
| `boundary-protected-target-refused` | `check_target`, `check_redirect`, or `check_protected_identity`: parsed origin or identity names a protected target |
| `boundary-verdict-vacuous` | `boundary_verdict`: `checks` is empty, not a list, or missing mandatory check name `target-binding` or `datastore-identity` |
| `boundary-unverified` | `authorize_credentials`: verdict did not pass, schema version mismatch, slot reference mismatch, policy digest mismatch, or `checks` is empty, missing mandatory check names, or any check entry did not pass |

## Datastore identity

Datastore identity has two provenances:

- **`observed`** — the framework runs the policy-declared observer subprocess itself,
  delivering the policy's `connectionDetail` through the observer's `connectionEnvVar`.
  Recorded as **strong** (`strength: "strong"`, `weaker: false`).
- **`app-reported`** — the application reports its datastore identity when no observer is
  declared. Recorded as **weaker** (`strength: "weaker"`, `weaker: true`) rather than
  silently treated as equal to an observed identity.

When the policy declares an observer (`datastore.observer` is not `null`), the framework
runs `observe_datastore_identity` and **refuses** on observer failure — it does not fall back
to app-reported identity. A declared observer that exits non-zero, times out, emits empty or
multi-line stdout, or exceeds the output byte cap raises `boundary-datastore-observer-failed`.

Observer hardening (`observe_datastore_identity` validates before spawn):

- Executable must be an **absolute path** to a regular file **outside every reach root**.
- Executable owner UID must match the reading process; mode must not grant group- or
  world-write (`boundary-datastore-observer-invalid` otherwise).
- `reach_roots` must be a non-empty list of absolute paths (empty list refuses).
- `run_cwd` must be an existing directory **outside every reach root**.
- Any absolute command argument, and any relative argument resolved against `run_cwd`,
  must lie **outside every reach root** — whether or not the path exists at validation
  time.
- Child environment is **minimal**: only the declared `connectionEnvVar` is set to
  `connectionDetail` — no inherited `PATH` or other ambient variables.

`app_reported_identity(value)` records a weaker identity when no observer runs.
`check_datastore_identity(binding, observation, expected_identity)` compares the observation
against the policy's `expectedIdentity`.

### Datastore identity refusal tokens

| Token | When returned |
|---|---|
| `boundary-datastore-identity-unavailable` | `check_protected_identity`, `app_reported_identity`, or `check_datastore_identity`: identity is missing, empty, or not a string; or no observer is declared and no app-reported value is supplied |
| `boundary-datastore-identity-mismatch` | `check_datastore_identity`: observed identity does not equal `expectedIdentity` |
| `boundary-datastore-observer-invalid` | `observe_datastore_identity`: observer shape, connection detail, reach roots, run cwd, or confinement rules are violated |
| `boundary-datastore-observer-failed` | `observe_datastore_identity`: subprocess failure, non-zero exit, oversized output, invalid UTF-8, or stdout that is empty, multi-line, or contains control characters |

## The policy document

The policy document lives **outside every reach root**. Resolution is keyed by a
`policy_root` directory (absolute, existing) and a **declaration** identifier — an opaque
name, never a path fragment. The on-disk file is `<policy_root>/<declaration>.json`.

**Declaration grammar:** `^[A-Za-z0-9][A-Za-z0-9_-]*$` — no slashes, dots as path
components, or traversal sequences. The identifier selects a filename; it is not interpreted
as a relative path.

**File-integrity requirements** (enforced by `resolve_policy_document`):

- No symlink in the document path ancestry.
- Document must exist, be a regular file, and be readable.
- Owner UID must match the reading process (`policy-document-owner-mismatch` otherwise).
- Mode bits must not grant group- or world-write (`policy-document-mode-insecure` otherwise).
- Open uses `O_RDONLY | O_NOFOLLOW`; inode/device comparison closes symlink-rebind windows.

**JSON shape** (`schemaVersion` must be `1`):

```json
{
  "schemaVersion": 1,
  "declaration": "example-project-pilot-policy",
  "protectedTargets": ["https://app.example.com:443", "example_prod"],
  "datastore": {
    "expectedIdentity": "example_dev",
    "connectionDetail": "postgres://localhost:5432/example_dev",
    "observer": {
      "command": ["/opt/pilot/db-identity"],
      "connectionEnvVar": "PILOT_DB_URL"
    }
  },
  "slots": {
    "slot-a": {
      "origin": "http://127.0.0.1:5173",
      "permittedRedirects": ["http://127.0.0.1:9000"],
      "expectedIdentities": {"owner": "pilot-owner@example.test"},
      "mintableAccounts": ["pilot-owner"]
    }
  }
}
```

Top-level keys are exactly `schemaVersion`, `declaration`, `protectedTargets`, `datastore`,
and `slots`. Each slot requires `origin`, `permittedRedirects`, and `expectedIdentities`
(non-empty dict mapping account names to identity strings). `mintableAccounts` is optional.
`datastore.observer` may be `null` (app-reported path) or an object with `command` (non-empty
argv list) and `connectionEnvVar` (valid env-var name). The resolved document's
`declaration` field must match the identifier used to open it.

Public API in `lib/pilot_policy.py`: `resolve_policy_document`, `validate_policy`,
`policy_material`.

### Policy document refusal tokens

| Token | When returned |
|---|---|
| `policy-root-invalid` | `policy_root` is missing, not an absolute path, or not an existing directory |
| `policy-root-in-reach` | `policy_root` overlaps any reach root (raw or realpath) |
| `policy-declaration-invalid` | `declaration` does not match the declaration grammar |
| `policy-document-missing` | `<policy_root>/<declaration>.json` does not exist |
| `policy-document-symlink` | A symlink appears in the document path ancestry, or open-time inode/path checks detect a symlink rebind |
| `policy-document-not-regular-file` | Document path exists but is not a regular file |
| `policy-document-owner-mismatch` | Document owner UID does not match the reading process |
| `policy-document-mode-insecure` | Document mode grants group- or world-write |
| `policy-document-unreadable` | Document or an ancestor cannot be opened or read |
| `policy-document-invalid` | JSON parse failure, wrong top-level shape, declaration mismatch, or any structural validation failure in `validate_policy` |
| `policy-schema-version-unsupported` | `schemaVersion` is not integer `1` |

## Results travel, never policy

Boundary checks produce a **traveling verdict** — outcomes only, never policy material.
`boundary_verdict(binding, *, checks, policy_digest, datastore_identity=None, verified_at=None)`
assembles it:

```json
{
  "schemaVersion": 1,
  "slotRef": "slot-a@1",
  "result": "pass",
  "reason": null,
  "checks": [
    {"check": "target-binding", "result": "pass", "reason": null},
    {"check": "datastore-identity", "result": "pass", "reason": null}
  ],
  "datastoreIdentity": {
    "provenance": "observed",
    "strength": "strong",
    "match": true
  },
  "policyDigest": "a1b2c3d4e5f60718",
  "verifiedAt": "2026-08-02T04:00:00Z"
}
```

The verdict carries a `policyDigest` (the declaration digest) but **no policy field value** —
no origins, identities, connection strings, or mintable-account names appear in the serialized
verdict. `verify_boundary` in `lib/pilot_provision.py` calls `assert_results_only` on every
verdict before returning it.

`assert_results_only(result, material)` is the mechanical guard: it walks the result
structure (dicts, lists, string values, and dict keys) and refuses when any string from
`policy_material(policy)` appears as an exact match (`policy-material-in-result`).
`policy_material` extracts three classes:
`expected-identity`, `mintable-account`, and `connection-detail`.

`exercise_no_policy_material_in_reach(reach_roots, material)` walks reach roots and scans
regular file bytes for policy material needles. Receipt shape:

```json
{
  "kind": "policy-out-of-reach",
  "result": "pass",
  "reason": null,
  "evidence": "no policy material found in reach root",
  "scannedFiles": 2,
  "scannedBytes": 48,
  "findings": [],
  "coverageLimits": ["Compressed and archived content is scanned as raw bytes; material inside it is not detectable."],
  "symlinksSkipped": 0,
  "exercisedAt": "2026-08-02T04:00:00Z"
}
```

**Vacuity rules** (a vacuous scan is a failure, never a pass):

- Empty material (no non-empty string needles) → `policy-exercise-vacuous` (raises).
- Zero files scanned → `policy-exercise-vacuous` (receipt `result: "fail"`).
- Unreadable directory or file during walk → `policy-exercise-unreadable` (receipt
  `result: "fail"`).

Material found in reach produces `result: "fail"` with reason `policy-exercise-material-found`
and a `findings` list — the receipt itself does not echo the material string.

**Coverage limits:** compressed and archived content is scanned as raw bytes; material inside
compressed or archived containers is not reliably detectable. Symbolic links inside reach roots
are not followed; when any symlink is encountered during the walk, a second coverage-limit line
names the blind spot and states how many symlinks were skipped (`symlinksSkipped` on the
receipt).

### Results-travel refusal tokens

| Token | When returned |
|---|---|
| `policy-material-in-result` | `assert_results_only`: result structure contains a policy material string as a value or dict key |
| `policy-material-invalid` | `assert_results_only`: `material` is not a mapping or has no non-empty indexed needles |
| `policy-exercise-vacuous` | `exercise_no_policy_material_in_reach`: empty material, or walk completes with zero files scanned |
| `policy-exercise-unreadable` | `exercise_no_policy_material_in_reach`: directory listing or file read fails during walk |
| `policy-reach-root-invalid` | `exercise_no_policy_material_in_reach` or `resolve_policy_document`: reach root list is empty, invalid, or (exercise only) not an absolute path to an existing directory |
| `policy-exercise-material-found` | `exercise_no_policy_material_in_reach`: policy material byte-needle found in a reach-root file (receipt reason, not an exception) |

## Provisioning authorization

`authorize_credentials(verdict, slot_ref, policy_digest)` is the chokepoint every
credential-producing call passes through. It authorizes only when the verdict's `result` is
`pass`, `schemaVersion` matches, `slotRef` matches the caller's slot reference, and
`policyDigest` matches the caller's policy digest.

The `authorized_*` wrappers in `lib/pilot_provision.py` resolve sensitive allowlists from
the policy so the caller never holds them:

- `authorized_seed_request` — account must appear in the slot's `expectedIdentities`; calls
  `pilot_seed.seed_request` after authorization.
- `authorized_mint_request` — `mintableAccounts` is read from the policy and passed to
  `pilot_seed.mint_request`; the function signature has **no `allowlist` parameter**.
- `authorized_sentinel_probe_request` — slot's `mintableAccounts` is passed to
  `pilot_seed.sentinel_probe_request`.

`verify_boundary` runs target, redirect, and datastore-identity checks, assembles the
traveling verdict, and enforces `assert_results_only` before returning.

This is an **in-process chokepoint, not a sandbox**: the launcher, browser, and build session
share a UID by design (#660 §14). It prevents ordering mistakes (credentials before boundary
verification, or with a stale verdict), not a hostile process in another address space.

### Provisioning refusal tokens

| Token | When returned |
|---|---|
| `provision-slot-unknown` | `verify_boundary` or an `authorized_*` wrapper: slot reference does not parse, or slot id is absent from `policy.slots` |
| `provision-account-unknown` | `authorized_seed_request`: account is not in the slot's `expectedIdentities` |
| `provision-mint-unsupported` | `authorized_mint_request`: slot has no `mintableAccounts` or the list is empty |

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

## Slot lifecycle and generations

Slot lifecycle state, generation allocation, and serialized persistence live in
`lib/pilot_lifecycle.py`. The module owns the per-slot record and its transitions; it does
not write journal records, enforce fencing, or expose recovery entry points from `failed`.

### Slot states

| State | Meaning |
|---|---|
| `provisioning` | A provisioning attempt is in progress for this generation |
| `provisioned` | Provisioning finished; the slot is ready for session handoff |
| `occupied` | A pilot session holds the slot |
| `released` | The session released the slot; ready for the next provisioning attempt |
| `failed` | Provisioning or occupancy failed; partial effects may exist |
| `retired` | The slot is permanently withdrawn from service |

### Legal transitions

One row per source state; targets are every state the code allows from that source.

| From state | Legal targets |
|---|---|
| `provisioning` | `provisioned`, `failed` |
| `provisioned` | `occupied`, `failed`, `retired` |
| `occupied` | `released`, `failed`, `retired` |
| `released` | `provisioning`, `retired` |
| `failed` | `retired` |
| `retired` | *(none)* |

`failed` is terminal within this module apart from `retired`: a partial provisioning failure
must reach the owner before anything relaunches. Sub-issue **A2b** adds the named recovery
entry point; this module deliberately does not.

### Generation allocation

The generation is allocated at the **start of a provisioning attempt**, not at session
handoff, so every journal record and every fencing confirmation can be keyed to a
`<slot>@<generation>` reference. `begin_generation` is legal only from `released`.

### Serialized allocation

`slots_dir(cwd, root=None)` resolves the on-disk slot-store directory from a working
directory; it returns `{"ok", "reason", "path"}` and never raises. Every public entry
point in `pilot_lifecycle.py` and `pilot_journal.py` refuses rather than raising a builtin
exception; `slots_dir` was the last lifecycle entry point that could leak an `OSError`
from the store's repo-root walk.

**Every** allocation, including the first, happens under the per-slot advisory `flock`.
`create_slot(slots_dir_path, slot, accounts, *, now, timeout=...)` creates a slot's **first**
record **under the per-slot lock**, refusing if one already exists (`slot-record-exists`).
It exists because `mutate()` refuses when no record is present — without it, the very first
record (and therefore generation 1) would be allocated through the lock-free `write_record()`,
and two launchers first-provisioning the same slot would both persist `slot@1`.

`mutate()` holds the same lock across load → validate → callback → durable save, because
atomic replacement alone gives no read-modify-write exclusion; without it two launchers both
allocate the same generation. `begin_generation()` is the serialized path into
`provisioning` from `released`. The record write fsyncs the **parent directory**, so a crash
cannot recover a pre-allocation record after the new generation was handed out.

`mutate()` refuses when the loaded record's `slot` differs from the slot whose lock it holds
(`slot-record-slot-mismatch`), **and** when the callback *return* record's `slot` differs,
before writing either end.

### Record validation

`_validate_record()` enforces a bounded consistency check, not a full history replay: the
**last** history entry's `to` must equal the record's `state` and its `generation` must equal
the record's `generation`. A record violating that is `slot-record-invalid`.

The slot directory must be a real directory and the lock file a regular file — a symlink at
the slot-directory component or at the lock/record file itself is refused (`slot-dir-unsafe`).
This is **not** a full path-ancestry walk.

**Check/use limit:** the slot-directory symlink refusal is a check-then-use test by pathname —
it refuses a symlink or non-directory **at the moment of the check** and does **not** close a
race against an actor able to replace the directory between check and use. Under this project's
single-user local threat model the guard targets accidents and stale state, not a hostile local
actor; a full fix needs directory-descriptor-relative operations and is deliberately not built.

**Special-file safety:** the slot-record reader opens with `O_NOFOLLOW | O_NONBLOCK` and refuses
a non-regular file — a symlink or FIFO at the record path is refused rather than followed or
blocked on.

**Type-safety of validation:** every enum/membership check tests that the value is a string
first, so a parseable record carrying an unhashable value (`"kind": []`, `"state": []`) produces
the documented refusal rather than raising. Public entry points never raise on malformed *data* —
they refuse.

A non-serialisable history `detail` is refused at `transition()` and at record validation, so
it can never reach the writer's `json.dumps`.

### Generation check (three-valued)

`generation_check(carried, current)` returns one of three answers:

| Answer | When |
|---|---|
| `ok` | `carried` equals `current` |
| `slot-generation-stale` | `carried` is less than `current` |
| `slot-generation-ahead` | `carried` is greater than `current` |

The module deliberately exports **no boolean staleness helper**, because a two-valued answer
falls open on the `carried > current` case. Numbering lives here; broker-side enforcement is
sub-issue **C7's** (design seam S1).

### Lifecycle refusal tokens

| Token | When returned |
|---|---|
| `slot-state-invalid` | target state is not in `SLOT_STATES`, or `provisioning_outcome` is called with an unknown state |
| `slot-transition-illegal` | `transition` or `begin_generation` requests a move not in `TRANSITIONS` |
| `slot-occupied` | `transition` targets `occupied` while already `occupied` |
| `slot-retired` | mutation is attempted on a `retired` record |
| `slot-record-invalid` | record shape, history, accounts, timestamps, caller `now`, last-history consistency, or non-serialisable history `detail` fail validation |
| `slot-record-absent` | `read_record` returns this, and **only** this, when the record file genuinely does not exist (`ENOENT`); every other read failure stays `slot-record-unreadable`. `create_slot()` writes **only** on a genuinely absent record, so an unreadable-but-present record (bad mode, dangling symlink, transient I/O error) must never be mistaken for absence and silently replaced — that would reset a slot's durable history and generation to 1 while a broker may still be fencing against it |
| `slot-record-unreadable` | the on-disk record cannot be read (any failure other than genuine absence) |
| `slot-record-write-failed` | durable write or parent-directory fsync failed |
| `slot-generation-stale` | `generation_check`: carried generation is behind current |
| `slot-generation-ahead` | `generation_check`: carried generation is ahead of current |
| `slot-lock-unavailable` | per-slot advisory `flock` could not be acquired within timeout |
| `slot-mutation-failed` | the mutation callback raised an unexpected exception |
| `slot-generation-allocation-required` | `transition()` refuses the `released → provisioning` edge; only `begin_generation()` may enter `provisioning` from `released`, because each provisioning attempt must allocate its own generation or it would reuse the previous attempt's `<slot>@<generation>` identity and collide with that generation's journal and fencing records. The edge remains a legal lifecycle edge in `TRANSITIONS` — the refusal is in the generic mover, not in the table |
| `slot-record-slot-mismatch` | `mutate()` refuses when the loaded record's `slot` differs from the locked slot **or** the callback return's `slot` differs, before writing |
| `slot-dir-unsafe` | the slot directory is a symlink or not a directory, or the lock file is not a regular file; refuses a symlink at the slot-directory component and at the lock/record file itself — **not** a full path-ancestry walk |
| `slot-record-exists` | `create_slot()` refuses because a record already exists |
| `slot-root-unresolved` | `slots_dir()` could not resolve the slot-store root from the supplied `cwd` — a non-string, over-long, missing, or otherwise unresolvable working directory — returned rather than raised |

## The provisioning journal

The durable provisioning journal lives in `lib/pilot_journal.py`. Each shared or slot-scoped
effect is recorded **before and after** the operation: a crash between acting and recording
must replay as *possibly applied*, which is the honest state; a journal written only on
success reports a shared effect as never having happened.

### Effect kinds and scope

| Kind | Scope |
|---|---|
| `worktree-created` | `slot` |
| `app-started` | `slot` |
| `credential-minted` | `shared` |
| `credential-seeded` | `shared` |
| `namespace-touched` | `shared` |
| `project-declared` | `shared` |
| `browser-server-provisioned` | `slot` |
| `browser-server-torn-down` | `slot` |

`project-declared` is the **one** project hook ("what did setup touch") and is `shared`
because the framework cannot classify what the project names — fail closed.

### End outcomes (three-valued)

| Outcome | Meaning |
|---|---|
| `applied` | the caller proved the effect completed |
| `not-applied` | the caller proved the effect did not run |
| `indeterminate` | transport, process, timeout, or partial-operation error |

Only a caller that can *prove* non-application may record `not-applied`; every transport,
process, timeout, or partial-operation error records `indeterminate`. A two-valued outcome
would report a credential that really was minted as never minted.

### Replay states

| Replay state | Source |
|---|---|
| `applied` | paired `end` with outcome `applied` |
| `not-applied` | paired `end` with outcome `not-applied` |
| `possibly-applied` | paired `end` with outcome `indeterminate`, or `begin` with no `end`, or any anomaly |

### On-disk record shapes

Begin phase (`_build_begin_record`):

```json
{
  "schemaVersion": 1,
  "phase": "begin",
  "effectId": "<id>",
  "slotRef": "<slot>@<generation>",
  "kind": "<effect-kind>",
  "at": "<ISO-8601-UTC-Z>"
}
```

Optional `detail` object when the caller supplies one.

End phase (`_build_end_record`):

```json
{
  "schemaVersion": 1,
  "phase": "end",
  "effectId": "<id>",
  "slotRef": "<slot>@<generation>",
  "outcome": "applied | not-applied | indeterminate",
  "at": "<ISO-8601-UTC-Z>"
}
```

Optional `reason` string — `end_effect()` accepts a `reason` with **any** outcome including
`applied`, not only `not-applied` or `indeterminate`.

### Durable append

Journal records are appended with durability and safety: opened `O_NOFOLLOW | O_NONBLOCK` with a
regular-file check, written in a loop until the whole line lands, `fsync`ed, and the **parent
directory** `fsync`ed. A symlink or FIFO at the journal path is refused (`journal-write-failed`)
rather than followed or blocked on. Invalid UTF-8 in a journal is `journal-unreadable`, never an
exception and never silently replaced.

**Special-file safety:** the journal reader also opens with `O_NOFOLLOW | O_NONBLOCK` and refuses
a non-regular file at the journal path.

**Type-safety of validation:** every enum/membership check tests that the value is a string
first, so malformed data produces the documented refusal rather than raising. Public entry points
never raise on malformed *data* — they refuse. A non-serialisable `detail` is refused at record
validation so it can never reach `json.dumps`.

### Fail-closed reader rules

- A missing or unreadable journal is a refusal and never "no effects".
- A torn trailing line (file does not end with newline) sets `torn`.
- A parseable-but-non-conforming record becomes an anomaly **and** an `unknown` /
  `possibly-applied` entry rather than being skipped.
- Orphan `end`, duplicate `effectId`, out-of-order pairs, and `slotRef` disagreement never
  pair opportunistically.
- **Filtering by `slotRef` never hides evidence:** invalid records are retained regardless of
  their `slotRef`, and pairing anomalies are detected globally before filtering.

### `effect()` context manager

A clean exit from the `effect()` block **is** the caller's assertion that the effect completed;
a caller that swallows its own errors must call `mark_not_applied` or let the exception
propagate, because the context manager cannot tell a swallowed failure from success.

On a clean body a failed `end` write raises `PilotJournalError`; when the body itself raised,
the body's exception wins and the missing `end` record replays as `possibly-applied`. The
asymmetry is deliberate.

### Journal refusal tokens

| Token | When returned |
|---|---|
| `journal-unreadable` | journal file cannot be read during replay |
| `journal-write-failed` | append or fsync failed |
| `journal-record-invalid` | record shape, timestamp, or serialisable `detail` fails validation |
| `journal-effect-kind-unknown` | `kind` is not in `EFFECT_KINDS` |
| `journal-outcome-invalid` | `outcome` is not in `END_OUTCOMES` |
| `journal-slot-ref-invalid` | `slotRef` does not parse |
| `journal-effect-id-invalid` | `effectId` is missing or does not match the allowed pattern |

## The partial-failure report

`partial_failure_report` answers whether healthy slots may launch after one or more slots
failed provisioning. A failed slot may already have started an app, created a credential, or
touched shared fixtures, so the healthy slots are **not safe by assumption**. The report
enumerates what the failed slots touched and confirms they are fenced before recommending the
rest launch.

### Input shape per slot

`fencing` is a **caller-supplied verification result** — this module never performs or infers
fencing.

```json
{
  "slot": "<slot-id>",
  "slotRef": "<slot>@<generation>",
  "outcome": "provisioned | failed",
  "replay": {
    "ok": true,
    "effects": [],
    "torn": false,
    "anomalies": []
  },
  "fencing": {
    "fenced": true,
    "slotRef": "<slot>@<generation>"
  }
}
```

**Entry identity is bound:** the slot id parsed out of `slotRef` must equal the entry's
`slot`; a mismatch is `report-slot-entry-invalid`. Otherwise one slot could borrow another
slot's fencing confirmation.

`replay` is **optional** for a `provisioned` entry and **required** for a `failed` one.
`fencing` is meaningful only for failed slots and is ignored for provisioned entries.

When a healthy slot's `replay` **is** supplied, its journal is enumerated: every
`possibly-applied` effect becomes a warning, and a **shared**-scoped `possibly-applied` effect
on a *healthy* slot raises `failed-slot-shared-effect-possibly-applied` just as it does on a
failed slot. An unsettled shared effect — a credential mint that crashed mid-flight — is
unsettled whichever slot produced it, and fencing a slot does not un-touch shared state. This
is a **deliberate widening** beyond the enumerate-failed-slots wording, taken fail-closed.

### Blocker tokens

| Token | When raised |
|---|---|
| `report-slots-invalid` | `slots` argument is not a list or tuple; returns fail-closed report with `recommendLaunch: false` rather than raising |
| `report-slot-entry-invalid` | entry is not a mapping, required fields are missing or malformed, or the slot id parsed from `slotRef` does not equal the entry's `slot` |
| `report-slot-outcome-invalid` | `outcome` is not `provisioned` or `failed` |
| `report-slot-duplicate` | the same `slot` id (or the same `slotRef`) appears in more than one entry |
| `failed-slot-fence-missing` | `fencing` is absent on a failed slot |
| `failed-slot-fence-invalid` | `fencing` is not a mapping, or `fenced` is not a boolean |
| `failed-slot-not-fenced` | `fenced` is `false` |
| `failed-slot-fence-ref-mismatch` | `fencing.slotRef` does not equal the entry's `slotRef` |
| `failed-slot-journal-unreadable` | `replay.ok` is not `true` |
| `failed-slot-journal-torn` | `replay.torn` is `true` |
| `failed-slot-journal-anomaly` | `replay.anomalies` is non-empty |
| `failed-slot-replay-shape-invalid` | the `replay` result is not a complete, well-formed replay: it must be a dict with `ok is True`, `torn` exactly `true`/`false`, `anomalies` a list, and `effects` a list whose every entry is a dict with a known `state` and a scope that agrees with `EFFECT_SCOPE[kind]` when `kind` is a known effect kind (unknown or absent `kind` must carry `shared`). A scope disagreement blocks — otherwise a caller could label a `credential-minted` possibly-applied effect as slot-scoped and downgrade a blocker to a warning. Anything else blocks — without this, a failed but correctly fenced slot carrying `replay: {"ok": true}` and nothing else produced `recommendLaunch: true` with no journal evidence at all |
| `slot-replay-slot-mismatch` | the `replay` result supplied for an entry is not stamped with that entry's `slotRef`. `replay()` stamps its result with the `journalPath` it read and the `slotRef` filter it was given, and the report checks that stamp. **This is provenance, not authentication** — a caller that hand-builds a dict can still forge the stamp; what it removes is the accidental cross-wiring of one slot's replay into another slot's entry |
| `failed-slot-shared-effect-possibly-applied` | a replayed effect has `scope: "shared"` and state `possibly-applied` (on failed or healthy slots when `replay` is supplied) |
| `no-healthy-slots` | no slot reported `outcome: "provisioned"` |

### Launch recommendation rule

`recommendLaunch` is true only when there are no blockers and at least one healthy slot.
Every unknown — missing fencing, a non-boolean `fenced`, a mismatched `slotRef`, an
unreadable or torn journal, an anomaly — is a blocker, never a pass. `fenced` is compared
with `is True` / `is False` so a truthy string like `"true"` cannot confirm.

A **shared**-scoped possibly-applied effect blocks even on a fenced slot: fencing a slot does
not un-touch a shared datastore or un-mint a credential on a shared service.

Sub-issue **C8** renders this report to the owner.

## Per-slot browser topology

Each slot gets its own browser and its own automation server, never shared between slots.
Within a slot, one browser context per account. The server and its socket directory are created
fresh per generation and the previous ones torn down. **The browser is the server's child**,
so tearing down the server takes the browser with it.

Two ruled-out arrangements are refused in code:

- **Tabs sharing one context** — `plan_topology` refuses when the same account appears more
  than once in the account list (`browser-shared-context-refused`); `context_set` refuses when
  two accounts would share the same context identity.
- **One browser or server spanning more than one slot** — `admit_server_registry` refuses when
  a server PID or browser PID is registered under more than one slot, or when more than one
  server record exists for the same slot.

### The Playwright pin

The framework **never installs** an automation runtime — `verify_pin` observes and compares
only. The pin shape is `schemaVersion` (integer `1`), `version` (non-empty string without
control characters), and `integrityDigest` (64-character lowercase hex). Before spawn,
`verify_pin` validates the observer the way `pilot_boundary` hardens datastore observers:
the executable must be an **absolute path** to a regular file **owned by the reading process**
with mode that grants neither group- nor world-write; `run_cwd` must be an existing directory.
A violation refuses (`browser-pin-observer-unsafe`) rather than spawning. The child receives
a **minimal environment** — only `PATH` is carried from the ambient environment, nothing else.
The observer contract requires one clean line of stdout in the form `<version> <digest>`, from
a bounded subprocess with stderr discarded; a subprocess that cannot spawn, or anything else
(non-zero exit, timeout, oversized output, invalid UTF-8, multi-line stdout, control characters,
or wrong token count), refuses (`browser-pin-observer-failed`) rather than raising.

### The socket directory

A unix socket path is capped by `sun_path` — 104 bytes on Darwin, 108 on Linux (the values in
`SUN_PATH_MAX`). The framework **measures the worst-case full path and refuses before launch**
(`socket_dir_plan`), and an unrecognised platform uses the **smallest** cap. The base directory
defaults to the system temp dir and is never inside the worktree (`browser-socket-base-in-worktree`
when `worktree_root` overlaps the base). When the caller omits `worktree_root`, `socket_dir_plan`
resolves the repository root from `os.getcwd()` itself (`browser-worktree-root-unresolved` when
that resolution fails). Field evidence this closes: deep worktree paths break automation socket
tooling.

`remove_socket_dir` refuses **before deleting anything** when the path's basename does not carry
the framework's socket-directory prefix (`pb-`; `browser-socket-dir-unrecognized`). Removal is
still guarded by "is a directory, not a symlink" on an already-planned path.

### Teardown requires an observed terminal state

`teardown_server` never infers process exit from the socket file's absence — that is a second
read of the same liveness marker the design refuses for terminal states. The caller supplies an
`observe_exit` callback; teardown proceeds only when it reports `exited: true` for **both** the
server PID and the browser PID. The browser is the server's child by design, but a reparented or
surviving browser would otherwise hold a live authenticated session while teardown reported
success — so both exit statuses are observed and carried on the teardown receipt
(`observedServerExitStatus`, `observedBrowserExitStatus`).

When socket-directory removal fails after having already removed entries, teardown records the
journal effect as **possibly-applied** (`indeterminate`), not `not-applied`, because the
journal's `not-applied` means *proved* not applied — partial cleanup is not proof of
non-application.

### Broker admission

Every browser instruction travels through the per-generation server, which is why admission is
where a stale generation dies. `admit` is the fencing chokepoint: it requires `slots_dir` and
reads the slot's on-disk lifecycle record for the authoritative generation — it does not trust
the caller's server record for "current". A server record whose `generation` disagrees with the
slot store refuses (`browser-server-record-stale`) before comparing the operation's generation.
Generation comparison then delegates to `pilot_lifecycle.generation_check`, propagating its
tokens (`slot-generation-stale`, `slot-generation-ahead`) rather than re-deriving them. When
`slots_dir` is not supplied, admission refuses (`browser-fencing-slots-dir-required`). Cross-
reference the declared seam **S1** (generation numbering defined in A2a / #823, enforced here).

### Provisioning journal shape

The primary provisioning shape journals **before** processes exist: `begin_provision_server`
writes the journal `begin` record and returns an `effectId`; the caller spawns the server and
browser, then `provision_server` closes that effect with `outcome: applied` via the supplied
`effect_id`. A crash between spawning and recording must replay as *possibly-applied*, never as
never-happened (#660 §7). The legacy `effect()` wrapper inside `provision_server` (when
`effect_id` is omitted) remains for callers that journal and spawn in one step.

Public API in `lib/pilot_browser.py`: `validate_pin`, `verify_pin`, `socket_dir_plan`,
`create_socket_dir`, `remove_socket_dir`, `assert_browser_is_server_child`,
`begin_provision_server`, `provision_server`, `teardown_server`, `plan_topology`,
`admit_server_registry`, `admit`.

### Browser topology refusal tokens

| Token | When returned |
|---|---|
| `browser-pin-invalid` | `validate_pin`: pin is not a dict with exactly `schemaVersion`, `version`, and `integrityDigest`; `schemaVersion` is not `1`; `version` is empty or contains whitespace/control characters; `integrityDigest` is not a 64-character lowercase hex string |
| `browser-pin-observer-invalid` | `_validate_observer` or `verify_pin`: observer is not a dict with exactly a non-empty `command` list of non-empty strings; `run_cwd` is not a string path; `timeout_seconds` or `max_output_bytes` has wrong type |
| `browser-pin-observer-unsafe` | `_validate_observer_safety` or `verify_pin`: `run_cwd` is not an existing directory; observer executable is not an absolute path, cannot be stat'd, is not a regular file, owner UID does not match the reading process, or mode grants group- or world-write |
| `browser-pin-observer-failed` | `verify_pin`: subprocess spawn failure, timeout, oversized output, non-zero exit, invalid UTF-8, empty/multi-line/control-character stdout, or stdout not exactly two space-separated tokens |
| `browser-pin-version-mismatch` | `verify_pin`: observed version does not match the pin's `version` |
| `browser-pin-integrity-mismatch` | `verify_pin`: observed digest does not match the pin's `integrityDigest` |
| `browser-socket-path-too-long` | `socket_dir_plan`: worst-case socket path exceeds the platform `SUN_PATH_MAX` cap, or `launch_token` is present but not a non-empty string |
| `browser-socket-base-in-worktree` | `socket_dir_plan`: `worktree_root` is not a string, or the resolved base directory overlaps the worktree |
| `browser-worktree-root-unresolved` | `socket_dir_plan`: `worktree_root` is supplied but not a valid path string, or defaults to `store_core.repo_root(os.getcwd())` and repository root resolution fails |
| `browser-socket-dir-exists` | `create_socket_dir`: the planned path already exists |
| `browser-socket-dir-unsafe` | `create_socket_dir`: plan is invalid, path is a symlink, created path is not a directory, mode is wrong, or `os.makedirs`/`stat` fails; `remove_socket_dir`: path is a symlink |
| `browser-socket-dir-not-directory` | `remove_socket_dir`: path is not a string or not a directory |
| `browser-socket-dir-unrecognized` | `remove_socket_dir`: path basename does not start with the framework socket-directory prefix (`pb-`), checked before any entries are removed |
| `browser-socket-dir-unremovable` | `remove_socket_dir`: directory contents cannot be enumerated; an entry cannot be classified or removed safely (including a non-empty subdirectory); or removing the now-empty directory fails |
| `browser-server-record-invalid` | `provision_server`, `teardown_server`, `admit_server_registry`, or `admit`: server record shape, slot reference, generation, PIDs, pin, or timestamps fail validation; journal write fails |
| `browser-not-server-child` | `assert_browser_is_server_child`: browser PID's parent is not the server PID |
| `browser-pid-unreadable` | `assert_browser_is_server_child`: parent PID cannot be read from the process table |
| `browser-terminal-state-unobserved` | `teardown_server`: `observe_exit` does not return a dict with `exited: true` for the server PID or for the browser PID |
| `browser-shared-context-refused` | `plan_topology`: duplicate account in the account list; `context_set`: two accounts would share the same context identity |
| `browser-server-shared-across-slots-refused` | `admit_server_registry`: the same server PID appears under more than one slot |
| `browser-shared-across-slots-refused` | `admit_server_registry`: the same browser PID appears under more than one slot |
| `browser-multiple-servers-for-slot` | `admit_server_registry`: more than one server record exists for the same slot |
| `browser-fencing-slots-dir-required` | `admit`: `slots_dir` is not supplied |
| `browser-server-record-stale` | `admit`: on-disk slot lifecycle record cannot be read, or the live server record's `generation` disagrees with the slot store's authoritative generation |
| `browser-operation-slot-ref-invalid` | `socket_dir_plan`, `provision_server`, `plan_topology`, or `admit`: operation slot reference does not parse |
| `browser-operation-slot-mismatch` | `admit`: operation slot id does not match the live record's slot |

## Browser context creation and seed injection

This is the declared seam **S3**'s context-side half: the interface and artifact-integrity
contract are A1's (#822), the artifacts come from B4 (capture) and B6 (mint client), and
**context-side injection is C7's** because C7 owns context creation and the capture options.

**No credential is seeded before provisioning gates have run.** `context_spec` refuses to build
a context spec without a valid `gate_provisioning` receipt whose `slotRef` matches the caller's
slot reference — boundary authorization, declare-and-exercise, and datastore-identity gates must
have completed first. This is the ordering guarantee the design rests on; the receipt is checked
before `seed_request` runs.

A project declares which surface holds its login session, and **the framework requires the
matching capture options** — `indexedDB: true` for an IndexedDB-held session, `credentials: true`
for WebAuthn. A capture missing the options its declared surfaces require **refuses here**. The
match must be **exact in both directions**: an option set that the declared surfaces do not
require also refuses, because an unrequired `credentials: true` installs a virtual authenticator
that displaces real ones.

**Verify-at-seed happens at context creation**, not earlier and not in the caller — the
artifact's integrity is checked as the context is built, and the spec carries the artifact's
verified path and hash, never its contents.

One context per account; `sessionStorage` never reaches a context spec (D7).

Public API in `lib/pilot_context.py`: `context_set`, `context_spec`.

### Context refusal tokens

| Token | When returned |
|---|---|
| `context-provisioning-receipt-missing` | `context_spec`: `provisioning_receipt` is `None` |
| `context-provisioning-receipt-invalid` | `context_spec`: receipt is not a dict, is missing a required key (`slotRef`, `policyDigest`, `datastoreIdentity`, `declarations`), or any required value is `None` or wrong type |
| `context-provisioning-receipt-slot-mismatch` | `context_spec`: receipt `slotRef` does not equal the canonical slot reference for the caller's `slot_ref` |
| `context-options-mismatch` | `context_spec`: `requested_options` is supplied and does not exactly equal `required_context_options(capture_surfaces)` |
| `context-artifact-missing` | `context_set`: `artifacts` is not a dict, or a required account has no artifact entry |
| `context-artifact-unknown-account` | `context_set`: `artifacts` contains an account not in the slot's account set |
| `context-shared-context-refused` | `context_set`: two accounts would share the same context identity |

**Propagated verbatim from `pilot_seed`:** this module does not re-wrap `seed-*` or `artifact-*`
tokens — `context_spec` propagates them from `required_context_options` and `seed_request`
unchanged (`seed-capture-surfaces-invalid`, `seed-capture-surfaces-empty`,
`seed-capture-surface-duplicate`, `seed-capture-surface-session-storage-refused`,
`seed-capture-surface-unknown`, `seed-slot-ref-invalid`, `seed-account-invalid`,
`seed-context-options-invalid`, `seed-verify-argument-invalid`, `artifact-path-traversal`,
`artifact-symlink-in-path`, `artifact-missing`, `artifact-not-regular-file`,
`artifact-owner-mismatch`, `artifact-mode-mismatch`, `artifact-hash-mismatch`,
`artifact-unreadable`). Propagation is deliberate so a caller can distinguish "your declared
surfaces are wrong" from "your options do not match your surfaces."

## The provisioning gate

### Declare and exercise, live

A1 shipped the registry's shape and predicates without a live enforcement point on purpose —
wiring it into the in-repo path would put policy back inside the builder's reach. The live gate
is here. A declaration that has never been exercised is **absent**, and absent **refuses**.

| kind | declaration source | applicable when |
|---|---|---|
| `identity-probe` | `pilot.identityProbe` | always |
| `capture-reduction` | `pilot.captureSurface` + `pilot.captureOptions` | always |
| `cleanup-containment` | `pilot.cleanup` | always |
| `effects-escape` | `pilot.effectsEscape` | always |
| `operating-ceiling` | `pilot.administrativeMax` | always |
| `mint-gate-off` | `pilot.mint.envelope` | slot policy grants `mintableAccounts`, or `pilot.mint` is present |
| `mint-account-allowlist` | policy slot's `mintableAccounts` | slot policy grants `mintableAccounts`, or `pilot.mint` is present |

Two load-bearing facts: **mint applicability is policy-side** — a slot whose policy grants
`mintableAccounts` makes both mint kinds applicable regardless of whether the branch-mutable
`pilot.mint` block declares mint; a policy grant with no block declaration to exercise now
refuses (`provision-mint-declaration-missing`) rather than skipping. A captured-sign-in project
with no policy mint grant legitimately has no mint declaration, and its mint kinds are recorded
`not-applicable`, not failed — and **`mint-account-allowlist` is sourced from the policy, never
the block**, because an inline allowlist is refused precisely to keep it outside branch-mutable
reach. Letting the block alone decide applicability would let a builder skip the mint gates by
deleting a config key.

Mapping **completeness is enforced**: a `DECLARATION_KINDS` member with no
`DECLARATION_SOURCES` entry refuses (`provision-declaration-kinds-uncovered`), so a new
declaration kind cannot silently miss the gate.

### The datastore-identity strength gate

A3 records `strength` explicitly rather than refusing, because the design supports
app-reported identity where the datastore is not directly reachable — it just requires the
weaker guarantee to be carried explicitly rather than silently. The `strong` / `weaker`
vocabulary is not single-homed: `pilot_boundary` emits the literals on observations and
verdicts; `pilot_provision` carries matching `STRENGTH_*` constants for the gate, and a drift
test guards the pair. So C7 **refuses `weaker` by default** and proceeds only on an explicit
**acceptance record** (`acceptedBy`, `acceptedAt`, `reason`) supplied at the provisioning call,
which runs in the advisor and never reaches the builder. It is deliberately a record, not a
boolean, so it cannot be dropped silently and the advisor's launch ledger (sub-issue C8 / #830)
can surface it to the owner.

A passing boundary verdict **may still carry a null `datastoreIdentity`** — the mandatory-check
set constrains check *names* only — which is why absent identity is a real refusal here rather
than a formality.

This is an **in-process chokepoint, not a sandbox**: the launcher, browser, and build session
share a UID by design (#660 §14). It prevents ordering mistakes, not a hostile process in
another address space.

Public API in `lib/pilot_provision.py`: `declaration_for`, `require_declarations_exercised`,
`gate_datastore_identity`, `gate_provisioning`.

### Provisioning gate refusal tokens

| Token | When returned |
|---|---|
| `provision-declaration-kinds-uncovered` | `declaration_for` or `require_declarations_exercised`: `kind` is not in `DECLARATION_SOURCES`, or `DECLARATION_SOURCES` does not cover every `DECLARATION_KINDS` member |
| `provision-declaration-source-missing` | `declaration_for`: applicable kind's extractor raises `KeyError`, `TypeError`, or `PilotSlotError` |
| `provision-datastore-identity-absent` | `gate_datastore_identity`: verdict has no `datastoreIdentity` dict, or provenance/strength is missing or empty, or `match` is not a boolean |
| `provision-datastore-identity-unmatched` | `gate_datastore_identity`: `match` is not `true` |
| `provision-datastore-identity-weaker-unaccepted` | `gate_datastore_identity`: strength is `weaker` and no `weaker_acceptance` record is supplied |
| `provision-weaker-acceptance-invalid` | `gate_datastore_identity`: `weaker_acceptance` is not a dict with exactly `acceptedBy`, `acceptedAt`, and `reason` as non-empty strings, with `acceptedAt` in ISO-8601 UTC `Z` form |
| `provision-datastore-identity-strength-unknown` | `gate_datastore_identity`: strength is neither `strong` nor `weaker` |
| `provision-mint-declaration-missing` | `declaration_for` for a mint kind: slot policy grants `mintableAccounts` but `pilot.mint` is absent from the block |
