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
14. [Attended seeding](#attended-seeding)
15. [Slot reference format](#slot-reference-format)
16. [Slot lifecycle and generations](#slot-lifecycle-and-generations)
17. [The provisioning journal](#the-provisioning-journal)
18. [The partial-failure report](#the-partial-failure-report)
19. [The launch ledger's slot grammar](#the-launch-ledgers-slot-grammar)
20. [The identity-probe exercise](#the-identity-probe-exercise)
21. [Mid-wave lapse](#mid-wave-lapse)
22. [Credential validity margin](#credential-validity-margin)
23. [Minted sign-in exercises](#minted-sign-in-exercises)
24. [The app-lifecycle exercise](#the-app-lifecycle-exercise)
25. [Reclaim safety](#reclaim-safety)
26. [Cleanup containment and resurrection](#cleanup-containment-and-resurrection)
27. [Per-slot browser topology](#per-slot-browser-topology)
28. [Browser context creation and seed injection](#browser-context-creation-and-seed-injection)
29. [The provisioning gate](#the-provisioning-gate)
30. [Per-slot app lifecycle](#per-slot-app-lifecycle)
31. [Wave runtime — deadline and teardown](#wave-runtime--deadline-and-teardown)

---

## Status and scope

This document is the normative contract home for the pilot framework (issue #822, epic #821).
It pins the schema, types, probe vocabulary, seed/mint call shapes, and refusal tokens that
downstream sub-issues build against.

**What this pins:** the optional nested `pilot` key inside `test-pilot-config`; the ten-token
probe vocabulary (`lib/pilot_probe.py`); slot reference format and account-set types
(`lib/pilot_slot.py`); seed/mint call shapes and artifact verification (`lib/pilot_seed.py` —
the artifact half is the latent S3 restore seam with no producer in this repository);
the contract validator (`lib/pilot_contract.py`, wired into `engine.load_profile_config`);
sub-issue **A3** — the per-slot target boundary (`lib/pilot_boundary.py`), the policy
document home (`lib/pilot_policy.py`), and the provisioning authorization layer
(`lib/pilot_provision.py`); sub-issue **A2a** — the slot lifecycle and generation
allocation (`lib/pilot_lifecycle.py`) plus the provisioning journal and partial-failure
report (`lib/pilot_journal.py`); sub-issue **B6** — the identity-probe exercise and
mid-wave lapse episode (`lib/pilot_identity.py`), the launch-time credential validity
margin (`lib/pilot_horizon.py`), and minted sign-in exercises (`lib/pilot_mint.py`);
sub-issue **B4** — attended seeding (`lib/pilot_attended.py`) and the app-lifecycle exercise
(`lib/pilot_lifecycle_exercise.py`); sub-issue **C9** — the cleanup effect receipt, containment
resolution, and resurrection
planner (`lib/pilot_cleanup.py`, plus the policy's `datastore.containment` declaration);
and sub-issue **B5** — per-slot app instance control (`lib/pilot_appctl.py`), the wave
deadline runtime and two-phase teardown (`lib/pilot_wave.py`), and the substrate
amendments in `pilot_contract.py` (`app-lifecycle` declaration kind), `pilot_provision.py`
(`authorized_app_launch` chokepoint), and `pilot_journal.py` (journal-level append lock
and `DETAIL_MAX_BYTES` bound).

**What this deliberately does not build** (successor sub-issues own these):

- Quarantine, sweep, the reassignment acceptance probe, deletion rules, and any recovery path out of
  `failed` (**A2b**).
- Browser context creation, credential injection, or broker-side stale-generation enforcement (**C7**).
- The measured operating ceiling and its degradation receipts (**D11b**).

The `"app-lifecycle"` declaration kind's **exercise producer** is sub-issue **B4** (#826) and
has landed in `lib/pilot_lifecycle_exercise.py`; a project with no receipt still refuses, which
is the correct fail-closed state, not a gap.

This document pins schema, vocabulary, validation, and the mechanisms through A3, A2a, and C9;
browser, broker, and teardown execution remain successor-owned.

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
    "signInPath": "attended",
    "attended": {"vehicle": "automation"},
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
  "signInPath": "attended",
  "attended": {"vehicle": "automation"},
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
| `signInPath` | string | required | `attended` or `minted` | `pilot-sign-in-path-invalid`; `pilot-sign-in-path-retired-captured` (retired literal `captured`); `pilot-sign-in-path-unhandled` (a `SIGN_IN_PATHS` member has no entry in the sign-in-path required-block mapping — completeness guard; fail-closed instead of falling through) |
| `attended` | object | conditional | required when `signInPath` is `"attended"`; optional otherwise | `pilot-attended-declaration-missing`; `pilot-attended-declaration-invalid` |
| `attended.vehicle` | string | required when `attended` present | `automation` or `real-chrome` | `pilot-attended-vehicle-invalid` |
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

**Declaration kinds:** `identity-probe`, `session-surface`, `cleanup-containment`,
`mint-gate-off`, `mint-account-allowlist`, `effects-escape`, `operating-ceiling`,
`app-lifecycle`. The `app-lifecycle` exercise producer has landed in
`lib/pilot_lifecycle_exercise.py`; a project with no matching exercised record still refuses
stand-up.

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
    },
    "containment": {
      "permissions": {
        "cannotReachForeignNamespaces": true,
        "evidence": "separate database per slot; role grants scoped to slot namespace"
      },
      "sentinel": {
        "plantCommand": ["/opt/pilot/sentinel-plant", "--namespace", "{namespace}", "--id", "{sentinel}"],
        "probeCommand": ["/opt/pilot/sentinel-probe", "--namespace", "{namespace}", "--id", "{sentinel}"],
        "connectionEnvVar": "PILOT_DB_URL"
      }
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
argv list) and `connectionEnvVar` (valid env-var name). `datastore.containment` is **optional**;
when present its keys are exactly `permissions` and `sentinel`, and each may be `null`.
`permissions` requires a real-boolean `cannotReachForeignNamespaces` and non-empty `evidence`.
`sentinel` requires `plantCommand`, `probeCommand`, and `connectionEnvVar`; each command is a
non-empty argv of non-empty strings with an **absolute** `argv[0]` that carries neither
`{namespace}` nor `{sentinel}`, both `{namespace}` and `{sentinel}` appearing in
`command[1:]`, and no unrecognised `{...}` placeholder anywhere. The resolved document's
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
structure (dicts, lists, and string values) and refuses when any string from
`policy_material(policy)` appears as an exact match (`policy-material-in-result`).
`policy_material` extracts three classes:
`expected-identity`, `mintable-account`, and `connection-detail`.

**Values always; keys for everything except a field-name-shaped account name.** A dict value is
data; a dict key is the result's *shape* — a field name the producer wrote. The guard cannot tell
the two apart when they spell the same word, and account names are exactly the short bare words
that field names use. So a **`mintable-account`** needle matching `^[A-Za-z_][A-Za-z0-9_-]*\Z` is
matched against **values only**. Every other needle — both other classes, and any account name that
could not be a field name — is matched **in key position as well**. The anchor is `\Z`, matching
the whole string with no exception: Python's `$` would also accept one trailing newline, so an
account name spelled `owner\n` would read as field-name-shaped and lose its key-position match. It
does not — it is matched in key position, like any other name that could not be a field name. Before this rule, a project
with an account named `owner`, `note`, or `op` hit a refusal the moment a result used that word as
a field name, with nothing in the refusal to say the account *name* rather than a leak was the
cause — account naming was a landmine (#861; PR #857 worked around it by renaming a plan-step key
to `responsibleParty`, and #866 renamed that key back to `owner` once this rule made the workaround
unnecessary).

The carve-out is deliberately keyed on the material **class** and not on spelling alone. The schema
permits any non-empty string for `expectedIdentity` and `connectionDetail`, and bare ones are
ordinary — the example policy above uses `example_dev` as its datastore identity. Exempting
material by shape alone would have dropped key-position detection for those too, silently, since
they are under no naming pressure toward field names. Account names are the only class the project
chooses in the same vocabulary as its result fields.

**Coverage limit:** a `mintable-account` name that is field-name-shaped is **not** detected in
**key** position. A producer that keys a result dict *by account name* leaks that name past this
guard. Producers assemble results under fixed field names and put data in values; keying by
material is the shape to avoid.

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
| `policy-material-in-result` | `assert_results_only`: result structure contains a policy material string as a value — or, for everything except a field-name-shaped `mintable-account` name, as a dict key |
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
| `provision-launch-invalid` | `authorized_app_launch`: `launch` is not a mapping, or `baseUrl` / `readinessUrl` is absent, non-string, or empty |

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

## Attended seeding

Attended seeding lives in `lib/pilot_attended.py`. The model is per-slot **per-account** owner
sign-in into the live browser context: nothing is captured, stored, or transferred, and the
session dies with teardown.

`seeding_vehicle(attended_declaration, *, idp_rejects_automation, human_driven_rejected=False)`
returns a uniform `ok`-keyed dict on both paths. On success: `{"ok": true, "reason": null,
"vehicle": "<automation|real-chrome>"}`. On refusal: `{"ok": false, "reason": "<token>"}`. Default
vehicle is `automation`; when the declaration's `vehicle` is `real-chrome`, or when the identity
provider rejects automation (`idp_rejects_automation`), the vehicle escalates to `real-chrome`.
When even a human-driven provisioned browser is refused (`human_driven_rejected`), the project
declares pilot auth unsupported for that mechanism via `attended-vehicle-unsupported-mechanism`;
**minted sign-in remains available**.

`attended_seeding_plan(slot, generation, accounts, *, sign_in_path, attended_declaration,
capture_surfaces, expected_identities, ...)` builds one step per `(slotRef, account)` pair. Each
step carries its own policy-resolved expected identity and the owner prompt. The plan refuses a
non-attended `sign_in_path`.

`prompt_copy(slot_ref, account, expected_identity, vehicle)` returns deliberately jargon-free
owner-facing text for one sign-in step.

`verify_at_seed(answer, *, expected_identity)` is the **identity** half of verify-at-seed on the
attended path (there is no artifact). The signed-in identity must equal the recorded expected
identity; **any other account, including the owner's own personal account, refuses**. Comparison
uses `hmac.compare_digest` on UTF-8 bytes. The artifact half (`pilot_seed.verify_artifact`) is not
on this path because there is no artifact.

`seed_outcome(steps, results)` requires every account to present the **exact** `verify_at_seed`
success shape: `ok` a real `bool` and `true`, `outcome == "verified"`, `reason` is `null`, and
`identity` equal to that account's `expectedIdentity` from its step (compared with
`hmac.compare_digest` on UTF-8 bytes). Anything malformed — a truthy `ok` that is not a real
`verify_at_seed` success, a missing account, or a mismatched step/result set — refuses with
`attended-seed-incomplete`, because a slot may not be certified seeded on a result that never
came from a real verify-at-seed. A well-formed per-account refusal (`ok` is `false` with a
bool) still refuses the whole slot with that account's `reason`.

`lapse_disposition(answer, *, reprobe_count)` delegates to `pilot_identity.lapse_step` with
`sign_in_path="attended"` so attended lapse and identity lapse can never disagree.

### Attended seeding refusal tokens

| Token | When returned |
|---|---|
| `attended-sign-in-path-not-attended` | `attended_seeding_plan`: `sign_in_path` is not `"attended"` |
| `attended-vehicle-invalid` | `seeding_vehicle` or plan: vehicle declaration malformed, or bool flags invalid |
| `attended-vehicle-unsupported-mechanism` | `seeding_vehicle`: human-driven provisioned browser refused — declare pilot auth unsupported for that mechanism |
| `attended-account-set-empty` | `attended_seeding_plan`: slot account set empty (propagated from slot validation) |
| `attended-account-set-mismatch` | `attended_seeding_plan`: `expected_identities` keys do not match slot accounts exactly |
| `attended-expected-identity-missing` | `attended_seeding_plan`: an account's expected identity is `None` |
| `attended-expected-identity-invalid` | `attended_seeding_plan` or `verify_at_seed`: expected identity missing or not a non-empty string |
| `attended-identity-mismatch` | `verify_at_seed`: signed-in identity does not equal expected identity |
| `attended-identity-absent` | `verify_at_seed`: probe returned no identity |
| `attended-answer-invalid` | `verify_at_seed`: probe answer shape invalid |
| `attended-slot-ref-invalid` | `attended_seeding_plan`: slot reference or generation invalid |
| `attended-account-invalid` | `attended_seeding_plan`: account entry malformed |
| `attended-context-reused` | `attended_seeding_plan`: duplicate `(slotRef, account)` pair |
| `attended-seed-incomplete` | `seed_outcome`: steps or results incomplete, mismatched, or any account result is not the exact `verify_at_seed` success shape |

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

### `end_effect()` origin verification

`end_effect(journal_path, *, slot_ref, effect_id, kind, outcome, at, reason=None)` requires
`kind` — the same effect kind the caller opened with `begin_effect`. The `kind` argument is used
only for verification; it is **not** written into the end record. On-disk end record shapes and
`schemaVersion` are unchanged.

Argument validation order: `journal_path` → `slot_ref` → `effect_id` → `kind` → `outcome` →
`at` → `reason`; first failure wins, all before any file access.

Before appending, the writer scans the journal (under the write lock, in the same lock hold as
the append) for every parsed record whose `effectId` equals `effect_id`. Write-path preconditions
run inside the append path before the verify hook: an unwritable parent directory (symlinked
parent, parent exists but is not a directory, or failed `makedirs`) or a lock that cannot be
acquired within the timeout refuses `journal-write-failed` before origin verification runs at all.
Precedence (first match wins):

| Condition | Refusal |
|---|---|
| journal cannot be read (non-regular file, I/O error, invalid UTF-8) | `journal-unreadable` |
| journal file missing | `journal-effect-origin-missing` |
| journal torn (last record incomplete, file does not end with newline) | `journal-torn` |
| zero records with `phase == "begin"` and this `effectId` | `journal-effect-origin-missing` |
| more than one such begin-phase record | `journal-effect-origin-ambiguous` |
| exactly one, but it fails begin-record validation | `journal-effect-origin-invalid` |
| exactly one valid begin, but its `kind` != the `kind` argument | `journal-effect-origin-kind-mismatch` |
| exactly one valid begin, but its `slotRef` != the `slot_ref` argument | `journal-effect-origin-slot-mismatch` |
| any record with `phase == "end"` and this `effectId` already exists | `journal-effect-already-closed` |
| otherwise | proceed with the append |

A parseable record counts by its `phase` and `effectId` whether or not it is a valid record. An
unparseable line cannot match. For `replay()`, a torn trailing line (file does not end with
newline) is dropped before the record loop — pairing proceeds on the truncated text. On
`end_effect` close, the torn check returns **before** the record scan: nothing is appended, the
partial tail stays on disk, and no scan runs. The `journal-torn` refusal fires only while the
journal still ends mid-record; `begin_effect` does not verify origin, so once any record is
appended after a tear the file no longer reads as torn and a subsequent close surfaces
`journal-effect-origin-missing` instead of `journal-torn` — the glued bytes remain on disk but are
no longer recoverable as a record and no longer detectable as torn. `replay()` torn handling is
unchanged: it still returns `ok: true` with `torn: true` and pairs what it can. A missing journal
file is treated as `journal-effect-origin-missing` during close; replay still treats a missing
journal as `journal-unreadable`.

On any refusal, **nothing is appended** — the open `begin` stays open and replays as
`possibly-applied`.

### Durable append

Journal records are appended with durability and safety: opened `O_NOFOLLOW | O_NONBLOCK` with a
regular-file check, written in a loop until the whole line lands, `fsync`ed, and the **parent
directory** `fsync`ed. `begin_effect` still refuses a symlink, FIFO, or directory sitting **at** the
journal path with `journal-write-failed` (its write path is unchanged). `end_effect` reaches the
special file first through close-time origin verification and refuses `journal-unreadable` before
the write-side `open`/`fstat` that would have produced `journal-write-failed`. Invalid UTF-8 in a
journal is `journal-unreadable`, never an exception and never silently replaced.

**Special-file safety:** the journal reader also opens with `O_NOFOLLOW | O_NONBLOCK` and refuses
a non-regular file at the journal path (`replay`, `end_effect` origin verification).

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

`mark_indeterminate` records `indeterminate` with an explicit end timestamp and optional
`reason` when transport, process, timeout, or partial-operation error prevents the caller
from proving applied or not-applied.

### Journal refusal tokens

| Token | When returned |
|---|---|
| `journal-unreadable` | journal file cannot be read during replay **or during `end_effect` close-time origin verification** (`replay`, `end_effect`) |
| `journal-torn` | `end_effect`: journal torn (last record incomplete) — close refused, nothing appended |
| `journal-write-failed` | parent-directory setup failure (symlinked parent, parent exists but is not a directory, `makedirs` failure), lock acquisition failure, append or fsync failure, or a symlink, FIFO, or directory at the journal path (`begin_effect`, `end_effect` write path) |
| `journal-record-invalid` | record shape, timestamp, or serialisable `detail` fails validation |
| `journal-effect-kind-unknown` | `kind` is not in `EFFECT_KINDS` |
| `journal-outcome-invalid` | `outcome` is not in `END_OUTCOMES` |
| `journal-slot-ref-invalid` | `slotRef` does not parse |
| `journal-effect-id-invalid` | `effectId` is missing or does not match the allowed pattern |
| `journal-effect-origin-missing` | `end_effect`: no begin-phase record carries this `effectId` (including missing journal) |
| `journal-effect-origin-ambiguous` | `end_effect`: more than one begin-phase record carries this `effectId` |
| `journal-effect-origin-invalid` | `end_effect`: the single begin-phase record fails validation |
| `journal-effect-origin-kind-mismatch` | `end_effect`: begin `kind` does not match the `kind` argument |
| `journal-effect-origin-slot-mismatch` | `end_effect`: begin `slotRef` does not match the `slot_ref` argument |
| `journal-effect-already-closed` | `end_effect`: an end-phase record for this `effectId` already exists |

### Segment-aware aggregate replay

`replay_sources(paths, *, slot_ref=None, journal_path=None)` in `lib/pilot_journal.py` folds an
**ordered sequence of journal sources** into one replay result. `replay(journal_path, *,
slot_ref=None)` is now its single-path case — it delegates to `replay_sources([journal_path], …)`
with unchanged behaviour.

The fold is over **records**, not over per-file replay results: an effect whose `begin` lands in one
segment and whose `end` lands in another resolves only when every source's records are concatenated
and paired together. Folding per-file replay outputs would leave cross-segment effects stuck in
`possibly-applied` even when the union is complete.

`aggregate_replay(slots_dir_path, slot, journal_path, *, slot_ref)` in `lib/pilot_reclaim.py` lists
retained segments in numeric sequence order via `journal_segments`, then appends the live journal
when it is present and readable. `slot_ref` is **required and keyword-only**: a replay result stamped
`None` is refused downstream by the partial-failure report's provenance check, so the signature makes
it impossible to forget.

**Fail-closed across sources:** any unreadable source refuses the whole aggregate; any torn source
makes the aggregate torn; every source's anomalies accumulate; a later good source never repairs an
earlier bad one. An empty `paths` list refuses (`journal-unreadable`).

**Segment contiguity.** Segment sequence numbers must be contiguous from 1. A gap yields
`segment-sequence-gap`; a first sequence above 1 yields `segment-sequence-not-one`. Both are
**anomalies on the aggregate**, which reach the partial-failure report as
`failed-slot-journal-anomaly`. Without this check, lost segment files disappear from an aggregate
with no file torn and no refusal.

**The absent live journal has two meanings.** Rotation renames the live journal and deliberately
does not recreate it, so *segments present and live journal absent* is **normal** after rotation.
*No segments and no live journal* is **unreadable evidence** and refuses. A path that exists but is a
symlink, a non-regular file, or unreadable is a **refusal**, never a skip.

**Refusals pass through.** `aggregate_replay` propagates `journal_segments`' own reason —
`reclaim-journal-outside-slot` stays that, and is not flattened into `journal-unreadable`.

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

## The launch ledger's slot grammar

The launch ledger (`lib/launch_ledger.py`) can now stamp wave attribution on a `reserved` event.
Three optional fields — `slot`, `generation`, and `boundary` — travel on that record. `SCHEMA` stays
`1`; a record written without any of them folds exactly as before. That back-compatibility guarantee
is the point: older ledgers and launches that never carried slot metadata remain valid.

**All-or-nothing pairing.** `slot` and `generation` are refused unless both are present;
`boundary` is refused unless both are present. A lone `slot`, a lone `generation`, or a `boundary`
without its slot pair all refuse at fold time.

**The `boundary` block** is a closed key allowlist matched **exactly** — an unknown key refuses:

| Field | Type | Nullable |
|---|---|---|
| `slotRef` | string | no |
| `result` | string | no |
| `provenance` | string | no |
| `strength` | `"strong"` or `"weaker"` | no |
| `match` | boolean | no |
| `policyDigest` | string | no |
| `verifiedAt` | string (ISO-8601 UTC with `Z`) | no |
| `weakerAccepted` | boolean | no |
| `acceptedBy` | string | yes |
| `acceptedAt` | string (ISO-8601 UTC with `Z`) | yes |
| `acceptanceReason` | string | yes |

```json
{
  "slot": "a",
  "generation": 1,
  "boundary": {
    "slotRef": "a@1",
    "result": "pass",
    "provenance": "observed",
    "strength": "strong",
    "match": true,
    "policyDigest": "a1b2c3d4e5f60718",
    "verifiedAt": "2026-08-02T04:00:00Z",
    "weakerAccepted": false,
    "acceptedBy": null,
    "acceptedAt": null,
    "acceptanceReason": null
  }
}
```

`boundary_record(verdict, *, weaker_acceptance=None)` projects a traveling boundary verdict into
this flat block. Cross-field invariants: the verdict's `schemaVersion` must match; `datastoreIdentity`
must be a dict (a passing verdict may carry `null` there, and this refuses it); `weaker` **requires**
a validated acceptance record (`acceptedBy`, `acceptedAt`, `reason`); `strong` **refuses** one; an
unknown `strength` refuses; the acceptance `reason` is capped at 500 characters and a longer one
refuses rather than being truncated.

Weaker acceptance is a **record**, not a boolean, so it cannot be dropped silently and the
owner-facing batch report can name who accepted a weaker guarantee and when.

**The `slots` block on `count`.** `COUNT_RESULT_BLOCKS` names `slots` alongside `counts`,
`amendments`, `lanes`, `attempts`, and `laneDetail`. For every launch in the batch that carried a
`slot`, `count` emits one entry with `launchId`, `issue`, `slot`, `generation`, `slotRef`,
`strength`, `weakerAccepted`, `acceptedBy`, `acceptedAt`, and `acceptanceReason`. A slot recorded
without a `boundary` block appears with `strength: null` and null acceptance fields rather than
being omitted — an absent boundary is itself worth seeing in the batch accounting.

**The launcher is the caller.** `launch_build` in `lib/launcher.py` accepts `slot`, `generation`,
and `boundary` keyword arguments and passes them through on the refusal path via
`_try_reserve_for_refusal`, so a wave slot whose launch is refused at preflight, premise, or compose
is still attributable to its slot. The `launch` CLI exposes the same three fields (`--slot`,
`--generation`, `--boundary`). The launcher also **refuses** a parallel launch on a slot-calibrated
project (a `pilot` block with a non-empty `credentialSet`, plus a batch declared with
`expectedLaunches > 1` or a batch that already has a live lane) that carries no slot reservation,
with refusal token `preflight-slot-reservation-required`. The refusal payload carries `missing` (the
lanes lacking a reservation, with the literal `this-launch` standing for the launch being attempted)
and `remedy` (the command shape). Single-lane launches and projects with no `pilot` block are
untouched. Enforcement is a preflight check plus a post-reserve re-check, not a predicate inside
`launch_ledger.reserve`'s lock, so two launches racing on an *undeclared* batch can both pass
preflight — the post-reserve re-check then refuses at least one of them before any spawn.
A reserved-but-never-started lane has no CLI transition today — it is resolved when that
launch itself reaches a terminal outcome; `record-outcome` cannot clear it
(`outcome-without-started`).

**Results-only scan at the durable write boundary.** `boundary_record` accepts an optional
`material` argument; when the caller passes it, the composer scans the record it is about to return
with `assert_results_only` against that policy material and refuses with
`ledger-boundary-material-in-record` if policy material appears in the composed block. Production
callers on the `--boundary` CLI route and the `reserve`/`fold` path do not pass `material` by design
— S2's rule is that policy never travels to where the builder or ledger writer can hold it. The
advisor holds the policy and **must** pass `material` when it wants that scan. When `material` is not
passed, `acceptanceReason` is unscanned caller-supplied prose in a durable file; that residual is
stated here rather than implied clean.

### Slot-grammar refusal tokens

| Token | When returned |
|---|---|
| `fold-bad-field:reserved:slot` | `slot` present but fails slot-id validation |
| `fold-bad-field:reserved:generation` | `generation` present but not a valid integer generation |
| `fold-bad-field:reserved:slot-generation` | only one of `slot` or `generation` is present |
| `fold-bad-field:reserved:boundary` | `boundary` present without both `slot` and `generation` |
| `fold-bad-field:reserved:boundary-shape` | `boundary` is not a mapping |
| `fold-bad-field:reserved:boundary-keys` | `boundary` key set does not match the closed allowlist exactly |
| `fold-bad-field:reserved:boundary-slotRef` | `slotRef` missing, empty, or does not match `format_slot_ref(slot, generation)` |
| `fold-bad-field:reserved:boundary-result` | `result` missing or empty |
| `fold-bad-field:reserved:boundary-provenance` | `provenance` missing or empty |
| `fold-bad-field:reserved:boundary-strength` | `strength` is not `strong` or `weaker` |
| `fold-bad-field:reserved:boundary-match` | `match` is not a boolean |
| `fold-bad-field:reserved:boundary-policyDigest` | `policyDigest` missing or empty |
| `fold-bad-field:reserved:boundary-verifiedAt` | `verifiedAt` missing, empty, or not ISO-8601 UTC with `Z` |
| `fold-bad-field:reserved:boundary-weakerAccepted` | `weakerAccepted` is not a boolean |
| `fold-bad-field:reserved:boundary-weakerAccepted-strength` | `weakerAccepted` disagrees with `strength` |
| `fold-bad-field:reserved:boundary-acceptance-required` | `weakerAccepted: true` but an acceptance field is missing or empty |
| `fold-bad-field:reserved:boundary-acceptance-forbidden` | `weakerAccepted: false` but an acceptance field is present |
| `fold-bad-field:reserved:boundary-acceptance-reason-too-long` | `acceptanceReason` exceeds 500 characters |
| `fold-bad-field:reserved:boundary-acceptedAt` | `acceptedAt` is not ISO-8601 UTC with `Z` |
| `fold-bad-field:reserved:boundary-nullable` | a nullable acceptance field is present but not a non-empty string |
| `ledger-boundary-verdict-invalid` | `boundary_record`: verdict is not a mapping or required verdict fields are absent |
| `ledger-boundary-schema-version` | `boundary_record`: verdict `schemaVersion` does not match |
| `ledger-boundary-datastore-identity-absent` | `boundary_record`: `datastoreIdentity` is not a dict or required identity fields are absent |
| `ledger-boundary-strength-unknown` | `boundary_record`: identity `strength` is not `strong` or `weaker` |
| `ledger-boundary-weaker-unaccepted` | `boundary_record`: weaker verdict with no `weaker_acceptance` |
| `ledger-boundary-weaker-acceptance-invalid` | `boundary_record`: `weaker_acceptance` fails validation |
| `ledger-boundary-strong-with-acceptance` | `boundary_record`: strong verdict with a `weaker_acceptance` supplied |
| `ledger-boundary-acceptance-reason-too-long` | `boundary_record`: acceptance `reason` exceeds 500 characters |
| `ledger-boundary-material-in-record` | `boundary_record`: composed record carries policy material when `material` is supplied |
| `preflight-slot-reservation-required` | a parallel launch on a slot-calibrated project carries no slot reservation for one or more lanes |
| `preflight-slot-calibration-unreadable` | a parallel launch on a project whose calibration profile cannot be read or parsed |
| `post-reserve-ledger-unreadable` | the post-reserve re-check could not read the launch ledger |

## The identity-probe exercise

The identity-probe exercise (design decision D3) proves that the configured probe
discriminates between seeded and unseeded contexts. Public API lives in
`lib/pilot_identity.py`.

### Answer shape

Each probe answer carries **exactly one** of:

- `identity` — a non-empty string naming the session's identity, or
- `reason` — one of the ten probe tokens from [The probe vocabulary](#the-probe-vocabulary).

Both fields present, neither present, or an empty identity refuses
(`identity-answer-invalid`). An unknown `reason` token refuses
(`identity-answer-reason-unknown`).

`probe_answer(*, identity=None, reason=None)` normalizes and validates one answer.
`evaluate_pair` and `run_pair_exercise` accept answer dicts with the same shape.

### Authoritative exercise vs helper

`run_pair_exercise` is the **authoritative** single-account exercise: it invokes two
**distinct** probe callables exactly once each and grades the results through
`evaluate_pair`. Distinct callables are verified here; whether they ran in different
browser contexts is C7's responsibility.

`evaluate_pair(seeded, unseeded, *, expected_identity)` is a **helper** only — grading
two fabricated answers does not establish that they came from two contexts. Preflight
must call `run_pair_exercise` (or the slot-level harness below), not `evaluate_pair`
alone.

### Ordered checks in `evaluate_pair`

Checks run in this order:

1. **Normalize both answers** — malformed shape returns the answer-validation refusal.
2. **Expected identity** — `expected_identity` must be a non-empty string
   (`identity-expected-missing` otherwise). This runs before grading because an absent
   expectation cannot discriminate seeded from unseeded answers.
3. **Identical answers** — if the normalized seeded and unseeded answers are equal,
   refuse with `identity-probe-answers-identical`. This runs **before** seeded/unseeded
   discrimination because identical answers prove the probe cannot distinguish contexts,
   regardless of whether each answer individually looks valid.
4. **Seeded leg** — seeded answer must carry `identity` matching `expected_identity`;
   a seeded `reason` refuses (`identity-probe-seeded-refused`).
5. **Unseeded leg** — unseeded answer must carry `reason: no-session`
   (`identity-probe-unseeded-not-no-session` otherwise).

### Per-account harness

`evaluate_slot(slot_accounts, expected_identities, answers)` runs the pair grading across
a slot's whole account set. The authoritative account list comes from
`pilot_slot.account_keys(slot_accounts)`; the `expected_identities` and `answers` key sets
must match that list exactly (`identity-account-set-mismatch`). An empty account set
refuses (`identity-account-set-empty`).

### Valid-but-wrong-account leg

`evaluate_wrong_account_leg(answer, *, expected_identity, other_identity)` grades the
free leg under minting: the probe must discriminate when a valid-but-wrong account is
presented. When `other_identity` equals `expected_identity`, the check is vacuous and
refuses (`identity-wrong-account-vacuous`). Pass requires `wrong-identity` or an identity
matching `other_identity`; infrastructure and lapse tokens are inconclusive
(`identity-wrong-account-inconclusive`).

### Declaration and registry binding

`identity_probe_declaration` binds a receipt to slot reference, generation, policy digest,
sorted account keys, and a **digest** of the expected identities — never the identity
strings themselves (they are policy material).

`identity_probe_receipt` assembles the `identity-probe` registry record.
`require_identity_probe_exercised` calls `require_exercised` for that kind.

A registry record is the durable receipt of an exercise that happened; it is **never**
a substitute for running the live probe in the current preflight. `is_exercised` carries
no freshness or launched-instance binding — the declaration binds slot, generation, and
policy digest.

### Identity-probe refusal tokens

| Token | When returned |
|---|---|
| `identity-answer-invalid` | `probe_answer` or answer normalization: both fields set, neither set, empty identity, or malformed dict |
| `identity-answer-reason-unknown` | `reason` is not one of the ten probe tokens |
| `identity-expected-missing` | `evaluate_pair`: `expected_identity` missing or empty |
| `identity-probe-answers-identical` | `evaluate_pair`: normalized seeded and unseeded answers are equal |
| `identity-probe-seeded-refused` | `evaluate_pair`: seeded answer carries a `reason` instead of identity |
| `identity-probe-seeded-identity-mismatch` | `evaluate_pair`: seeded identity does not match `expected_identity` |
| `identity-probe-unseeded-not-no-session` | `evaluate_pair`: unseeded answer is not `no-session` |
| `identity-probe-not-callable` | `run_pair_exercise`: a probe argument is not callable |
| `identity-probe-legs-not-distinct` | `run_pair_exercise`: seeded and unseeded callables are the same object |
| `identity-probe-leg-failed` | `run_pair_exercise` or `lapse_episode`: probe callable raised |
| `identity-account-set-empty` | `evaluate_slot`: account list from `account_keys` is empty |
| `identity-account-set-mismatch` | `evaluate_slot`: `expected_identities` or `answers` keys do not match the slot account set |
| `identity-wrong-account-vacuous` | `evaluate_wrong_account_leg`: `other_identity` equals `expected_identity` |
| `identity-wrong-account-not-discriminated` | `evaluate_wrong_account_leg`: answer identity equals `expected_identity` |
| `identity-wrong-account-unexpected-identity` | `evaluate_wrong_account_leg`: answer identity matches neither expected nor other |
| `identity-wrong-account-inconclusive` | `evaluate_wrong_account_leg`: infrastructure/lapse token or malformed answer |
| `identity-declaration-slot-invalid` | `identity_probe_declaration`: slot reference does not parse |
| `identity-declaration-invalid` | `identity_probe_declaration`: policy digest or expected-identities shape invalid |
| `identity-receipt-argument-invalid` | `identity_probe_receipt`: malformed result, timestamp, or declaration kind absent |

## Mid-wave lapse

When a mid-wave probe returns `no-session`, the framework routes to the lapse path.
Public API: `lapse_step`, `lapse_episode` in `lib/pilot_identity.py`.

Infrastructure classifications **never** route to lapse — only `no-session` does
(see [The probe vocabulary](#the-probe-vocabulary)). `lapse_step` classifies via
`pilot_probe.classify`; infrastructure tokens defer, identity-class tokens refuse.

### Action set

| Action | Meaning |
|---|---|
| `continue` | Session is valid; wave proceeds |
| `reprobe` | First `no-session` within budget — exactly one re-probe allowed |
| `park` | Confirmed lapse on `attended` sign-in path — slot parks (durable transition is A2a/B5); attended cannot self-heal because no credential is stored |
| `remint` | Confirmed lapse on `minted` sign-in path — caller must re-mint before continuing |
| `defer` | Infrastructure classification or probe transport failure — not a lapse |
| `refuse` | Identity-class probe token — not a lapse |

### Re-probe budget

`lapse_episode` **owns** the re-probe budget. A caller-supplied `reprobe_count` on
`lapse_step` can grade individual steps but cannot confirm a lapse — only
`lapse_episode` performs the second probe. The budget is exactly one re-probe: first
`no-session` → `reprobe`; second confirmed `no-session` → `park` (attended) or
`remint` (minted).

### Attended ⇒ park / minted ⇒ re-mint

After the single re-probe confirms `no-session`:

- **`signInPath: attended`** → `park` with lapse evidence. Attended cannot self-heal on lapse
  because nothing was captured, stored, or transferred — the owner must sign in again.
- **`signInPath: minted`** → `remint` action; `continue` is returned **only after** a
  supplied `remint` callable actually succeeds. If `remint` is absent, not callable,
  raises, or returns falsy, the episode **parks** (`lapse-remint-unavailable` or
  `lapse-remint-failed`).

Probe callable failures during the episode defer rather than lapse.

### `lapse_episode` return shape

Every return carries the same keys: `action`, `class`, `reason`, `firstReason`,
`secondReason`, `probeCalls`, `reminted` (`null` where not applicable).

### Lapse refusal tokens

| Token | When returned |
|---|---|
| `lapse-sign-in-path-invalid` | `lapse_step`: `sign_in_path` not in `attended` / `minted` |
| `lapse-reprobe-budget-invalid` | `lapse_step`: `reprobe_count` not `0` or `1` (bools excluded) |
| `lapse-probe-not-callable` | `lapse_episode`: probe argument is not callable |
| `lapse-remint-unavailable` | `lapse_episode`: minted path confirmed lapse but `remint` absent or not callable — episode parks |
| `lapse-remint-failed` | `lapse_episode`: `remint` raised or returned falsy |

## Credential validity margin

Launch-time comparison: for each account, `deadline + margin ≤ horizon` must hold before
the wave launches. Public API lives in `lib/pilot_horizon.py`.

**Runtime terminus enforcement is B5's (#827); only the launch-time comparison lives
here.**

The margin math never takes a bare integer horizon — every comparison uses a
**provenance-bound observation** constructed by one of:

- `cookie_expiry_observation(storage_state, *, cookie_name)`
- `token_claim_observation(token, *, claim="exp")`
- `server_probe_observation(*, expires_at, observed_at)`
- `unknown_observation()`

`validate_observation` refuses shapes the constructors would not emit.

### The comparison

`account_margin(observation, *, deadline_at, margin_seconds, sign_in_path, attended, ...)`
computes `required_until = deadline_at + margin_seconds` and requires
`required_until ≤ expiresAt` for a covered launch.

There is **no minted-path exemption** from `deadline + margin ≤ horizon`. Re-minting is
recovery after a confirmed mid-wave lapse (see [Mid-wave lapse](#mid-wave-lapse)), not a
launch gate — a short horizon cannot be waived because the sign-in path is `minted`.

### Decision order

1. **Validate observation shape** — refuse malformed observations before margin math.
2. **Unknown provenance, unattended** — when `validityProvenance` is `unknown` and
   `attended` is `false`, refuse (`horizon-unknown-provenance-unattended`). Unknown
   cannot claim an unattended horizon. When `attended` is `true`, disposition is
   `attended` (pass).
3. **Server-probe staleness** — when `server_probe_max_age` is set, refuse if
   `now - observedAt > server_probe_max_age` (`horizon-server-probe-stale`).
4. **Server-probe without expiry** — when `expiresAt` is `null`, disposition is
   `server-probe-recheck` with `requiresMidWaveRecheck: true` (pass at launch; B5
   re-checks mid-wave).
5. **Margin comparison** — `required_until ≤ expiresAt` → disposition `covered`; else
   `horizon-margin-exceeded` with `shortfallSeconds`.

`wave_margin(slot_accounts, accounts, ...)` evaluates every account in the authoritative
account set from `pilot_slot.account_keys(slot_accounts)`. The `accounts` observation
mapping must match that set exactly (`horizon-account-set-mismatch`). The wave result
includes `requiresMidWaveRecheck: true` when **any** account's margin result requires it.

### Epoch seconds

All instants in the margin path are **UTC epoch seconds** (integer). Instants in wire
format (`YYYY-MM-DDTHH:MM:SSZ`) parse through `parse_instant`, which uses
`time.strptime` — not `datetime.fromisoformat`, which does not accept a trailing `Z`
before Python 3.11.

### Horizon refusal tokens

| Token | When returned |
|---|---|
| `horizon-instant-invalid` | `parse_instant`: value is not `YYYY-MM-DDTHH:MM:SSZ` |
| `horizon-storage-state-invalid` | `cookie_expiry_observation`: malformed storage state or cookie entry |
| `horizon-cookie-name-invalid` | `cookie_name` missing or empty |
| `horizon-cookie-not-found` | named cookie absent from storage state |
| `horizon-cookie-ambiguous` | more than one cookie with the same name |
| `horizon-cookie-session-only` | cookie has no expiry or session-only expiry (`-1`, `0`) |
| `horizon-token-malformed` | JWT-shaped token cannot be decoded |
| `horizon-token-claim-missing` | claim (default `exp`) absent from payload |
| `horizon-token-claim-invalid` | claim value not a finite number with `int(value) >= 1` |
| `horizon-observation-invalid` | `validate_observation` or constructor input shape invalid |
| `horizon-sign-in-path-invalid` | `sign_in_path` not in `attended` / `minted` |
| `horizon-deadline-invalid` | `deadline_at` not a positive integer (bools excluded) |
| `horizon-margin-invalid` | `margin_seconds` not a strictly positive integer |
| `horizon-flag-invalid` | `attended` is not a bool |
| `horizon-now-invalid` | `now` invalid, or required but absent for staleness / past-deadline checks |
| `horizon-max-age-invalid` | `server_probe_max_age` invalid when provided |
| `horizon-deadline-in-past` | `deadline_at <= now` when `now` is supplied |
| `horizon-unknown-provenance-unattended` | `unknown` provenance with `attended: false` |
| `horizon-server-probe-stale` | server-probe observation older than `server_probe_max_age` |
| `horizon-margin-exceeded` | `deadline_at + margin_seconds > expiresAt` |
| `horizon-account-set-empty` | `wave_margin`: accounts mapping empty or absent |
| `horizon-account-set-mismatch` | `wave_margin`: observation keys do not match the slot account set, or slot account entry missing or empty |

## Minted sign-in exercises

Minted sign-in exercises live in `lib/pilot_mint.py`. Every public path that mints goes
through A3's `authorized_*` wrappers; this module performs no network I/O — the caller
injects a transport callable.

A registry record is the durable receipt of an exercise that happened; it is **never**
a substitute for the live sentinel exercise in the current preflight (see
[Declare and exercise](#declare-and-exercise) — `is_exercised` carries no freshness or
launched-instance binding).

### Flag-scope rule

`flag_scope_check(envelope, *, observed_scopes)` returns whether the enabling flag was
observed only in declared `enabledScopes`. A flag set in any scope **outside**
`enabledScopes` is disqualifying (`mint-flag-set-outside-declared-scope`). Vacuous or
malformed `observed_scopes` refuses (`mint-observed-scopes-invalid`).

### Gate-off receipt

`run_gate_off_test` executes `gateOffTestCommand` with the enabling environment variable
**removed** from the supplied environment. Timeout, oversize output, and spawn failure
refuse rather than pass.

`gate_off_receipt` binds the registry record to the exact envelope via
`declaration_digest`. `require_gate_off` calls `require_exercised` for kind
`mint-gate-off`.

### Live sentinel exercise

`sentinel_exercise` runs a two-leg preflight:

1. **Positive control** — an authorized mint of an allowlisted `control_account` must
   succeed first. If the control mint fails, the exercise is `inconclusive`
   (`mint-control-did-not-mint`) — a refusal only discriminates when minting
   demonstrably works.
2. **Sentinel probe** — `authorized_sentinel_probe_request` probes the sentinel
   identifier, which must be absent from the mintable allowlist.

**Unverifiable half:** the framework cannot verify that the sentinel corresponds to no
real account — only that it is absent from the allowlist
(`sentinel_probe_request` enforces allowlist absence, not global non-existence).

### Sentinel status table

| HTTP status | Outcome | Notes |
|---|---|---|
| 400, 403, 409, 422 | `refused` (pass) | Gate refused as expected |
| 401 | `inconclusive` | Request was not authenticated — the allowlist may never have been consulted; treating "could not tell" as "refused" fails open (`unauthorized`) |
| 2xx | `minted` (fail) | `mint-sentinel-minted` — gate did not refuse |
| 404 | `inconclusive` | Endpoint absent — allowlist was never consulted; treating "could not tell" as "refused" fails open (`mint-sentinel-endpoint-absent`) |
| 429 | `inconclusive` | `rate-limited` |
| ≥ 500 | `inconclusive` | `infrastructure-unavailable` |
| other | `inconclusive` | `mint-sentinel-unexpected-status` |
| transport error | `inconclusive` | `transport-error` |

### Mint exercise refusal tokens

| Token | When returned |
|---|---|
| `mint-envelope-incomplete` | envelope missing required keys, malformed scope fields, or missing/malformed `gateOffTestCommand` |
| `mint-observed-scopes-invalid` | `flag_scope_check`: `observed_scopes` empty or malformed |
| `mint-flag-set-outside-declared-scope` | enabling flag observed in a scope outside `enabledScopes` |
| `mint-gate-off-argument-invalid` | `timeout_seconds` or `max_output_bytes` not a positive integer |
| `mint-gate-off-cwd-invalid` | `run_cwd` missing or not an existing directory |
| `mint-gate-off-environment-invalid` | environment not a string-to-string mapping |
| `mint-gate-off-timeout` | gate-off subprocess exceeded timeout |
| `mint-gate-off-output-oversize` | gate-off stdout exceeded byte cap |
| `mint-gate-off-spawn-failed` | gate-off subprocess could not start or stdout read failed |
| `mint-gate-off-test-failed` | gate-off subprocess exited non-zero |
| `mint-receipt-argument-invalid` | `gate_off_receipt`: malformed run result or timestamp |
| `mint-transport-invalid` | `authorized_mint` or `sentinel_exercise`: transport not callable |
| `mint-control-did-not-mint` | sentinel exercise: control mint leg failed — exercise inconclusive |
| `mint-sentinel-setup-failed` | sentinel exercise: post-control setup failed — exercise inconclusive but control result preserved |
| `mint-sentinel-minted` | sentinel leg returned 2xx — gate did not refuse |
| `mint-sentinel-endpoint-absent` | sentinel leg returned 404 — inconclusive, not refusal |
| `mint-sentinel-unexpected-status` | sentinel leg returned an unclassified status |

## The app-lifecycle exercise

The app-lifecycle exercise lives in `lib/pilot_lifecycle_exercise.py`. It grades an observed
navigation trace against a slot's declared origin and `permittedRedirects` allowlist so an
`app-lifecycle` declaration can be exercised before stand-up.

Attended sign-in is the first thing that legitimately leaves the app's own origin — the owner
signs in through a real identity provider — so the declared `permittedRedirects` allowance
becomes load-bearing on that path.

`normalize_origin(value)` canonicalizes to `scheme://host[:port]` for http(s) URLs. Malformed URL
authorities — including `urlsplit` failures and invalid port values such as non-numeric ports
or out-of-range port numbers — refuse with `lifecycle-exercise-origin-invalid` instead of letting
a bare `ValueError` escape. Origins are compared exactly, never by string prefix.

`evaluate_trace(trace, *, origin, permitted_redirects)` grades a navigation trace: every visited
origin must be the declared origin or a permitted redirect; the trace must start and end at the
declared origin. For grading only, permitted redirects are normalized (canonicalized,
de-duplicated, and sorted) before comparison — that normalization never reaches the declaration
digest. A malformed trace entry refuses `lifecycle-exercise-trace-invalid`; a malformed permitted-
redirect list refuses `lifecycle-exercise-redirect-invalid`.

`app_lifecycle_declaration(*, slot_ref, policy_digest, origin, permitted_redirects)` returns the
digested `declaration` plus `slot`, `generation`, and `policyDigest` as metadata **outside** the
digest. The `declaration` member is the **raw policy shape** —
`{"origin": <origin>, "permittedRedirects": <permitted_redirects>}` — byte-for-byte what
`pilot_provision.declaration_for("app-lifecycle", …)` returns. **Only** that `declaration` member
is digested; the gate has no normalizer, so the producer must digest exactly what the gate
digests. Redirect **order is significant** to the digest — the gate does not sort or de-duplicate
`permittedRedirects`, so the producer must not either; keeping redirect order stable is the policy
document's concern.

`app_lifecycle_receipt(declaration, result, *, exercised_at)` builds the registry record. The
result must bind to its declaration; a forged result refuses. On pass, evidence carries origins
only — never a path, query, or fragment, because a sign-in URL can carry tokens. On fail,
evidence is pinned to the module's own `REFUSAL_*` tokens only; any other reason is recorded as
`lifecycle-exercise-refused` so caller-controlled free text never reaches the persisted record.

`require_app_lifecycle_exercised(registry, declaration)` requires a matching exercised record in
the registry.

### App-lifecycle exercise refusal tokens

| Token | When returned |
|---|---|
| `lifecycle-exercise-declaration-slot-invalid` | `app_lifecycle_declaration`: `slot_ref` does not parse |
| `lifecycle-exercise-declaration-invalid` | `app_lifecycle_declaration`: policy digest missing or empty |
| `lifecycle-exercise-origin-invalid` | `normalize_origin` or declaration: origin malformed or not http(s) |
| `lifecycle-exercise-redirect-invalid` | declaration or trace: permitted redirect list malformed |
| `lifecycle-exercise-trace-invalid` | `evaluate_trace`: trace or URL entry malformed |
| `lifecycle-exercise-trace-empty` | `evaluate_trace`: trace is empty |
| `lifecycle-exercise-navigation-escaped` | `evaluate_trace`: visited origin not in allowlist |
| `lifecycle-exercise-trace-did-not-return` | `evaluate_trace`: trace did not start and end at declared origin |
| `lifecycle-exercise-receipt-argument-invalid` | `app_lifecycle_receipt`: declaration, result, or timestamp malformed or not bound |

## Reclaim safety

Quarantine-never-delete reclaim, sweep, deletion authorization, journal rotation, and the
reassignment acceptance probe live in `lib/pilot_reclaim.py` and `lib/pilot_fence.py`.

### On-disk layout

```
<slots_dir>/
  <slot>/
    journal.ndjson
    journal.<NNNN>.ndjson
    slot.json
    .slot.lock
  .pilot-quarantine/
    <entryName>/
      …payload…
    <entryName>.quarantine.json
```

The quarantine directory name `.pilot-quarantine` cannot collide with a slot id: `store.SLOT_RE`
requires a leading `[A-Za-z0-9]`, so no valid slot id begins with `.`.

### Quarantine, never delete

When a stale occupant is reclaimed, its payload directory is **renamed aside** into
`.pilot-quarantine`, never deleted. A cross-device rename **refuses** (`reclaim-cross-device`)
rather than degrading to a copy. The sidecar is written **before** the rename: a crash must
leave an unexplained sidecar rather than an unexplained entry — the same before-and-after
discipline the provisioning journal uses.

If the rename never happened (cross-device or other `OSError` refusal), the payload remains
**untouched at `originalPath`** and the pending sidecar is stale. Recovery: the operator
removes the stale sidecar by hand — the framework will not, by design. The sidecar is loud
so the operator can distinguish "payload safe at original path, sidecar stale" from a
completed move.

### The sidecar

```json
{
  "schemaVersion": 1,
  "entryName": "<slot>-gen<generation>-<compact-timestamp>",
  "originalPath": "/absolute/path/to/payload",
  "slot": "<slot-id>",
  "slotRef": "<slot>@<generation>",
  "generation": 1,
  "reason": "<reclaim-reason>",
  "quarantinedAt": "<ISO-8601-UTC-Z>",
  "expiresAt": "<ISO-8601-UTC-Z>",
  "move": "pending | moved",
  "status": "quarantined | deletion-authorized | deleted",
  "occupant": {
    "pid": 12345,
    "processInstance": "inst-abc",
    "livenessSource": "heartbeat-record | mtime | process-table | lock-probe",
    "observedAt": "<ISO-8601-UTC-Z>"
  }
}
```

After authorization or deletion, optional fields `terminalReceipt`, `deletionAuthorizedAt`, and
`deletedAt` may appear.

| Field | Type | Meaning |
|---|---|---|
| `schemaVersion` | integer | must be `1` |
| `entryName` | string | quarantine entry directory name |
| `originalPath` | string | realpath of the payload before rename |
| `slot` | string | slot id |
| `slotRef` | string | `<slot>@<generation>` |
| `generation` | integer | generation at quarantine time |
| `reason` | string | caller-supplied reclaim reason (≤ 500 chars) |
| `quarantinedAt` | string | ISO-8601 UTC timestamp with `Z` suffix |
| `expiresAt` | string | informational only — **no predicate ever reads it**; grace is always recomputed from `quarantinedAt` |
| `move` | string | `pending` before rename completes; `moved` after |
| `status` | string | `quarantined`, `deletion-authorized`, or `deleted` |
| `occupant` | object | the stale occupant's liveness binding |
| `terminalReceipt` | object | present after deletion is authorized |
| `deletionAuthorizedAt` | string | present after deletion is authorized |
| `deletedAt` | string | present on the tombstone |

### Deletion authorization

`authorize_deletion(sidecar, receipt, *, now)` is a pure check — it touches no filesystem.
`GRACE_HOURS` is a fixed constant (`72`) with no parameter. The occupant's `livenessSource`
may be `heartbeat-record`, `mtime`, `process-table`, or `lock-probe`; `mtime` and
`process-table` are **liveness** sources that can never be terminal.

Authorization requires **all** of the following, checked in this order:

1. Sidecar passes structural validation (`reclaim-sidecar-invalid` otherwise).
2. `now` is a valid ISO-8601 UTC timestamp (`reclaim-now-invalid` otherwise).
3. `move` is `moved` (`reclaim-entry-not-moved` otherwise).
4. `status` is not `deleted` (`reclaim-status-not-deletable` otherwise).
5. At least `GRACE_HOURS` (72) have elapsed since `quarantinedAt` (`reclaim-grace-not-elapsed`
   otherwise).
6. Receipt passes structural validation (`reclaim-receipt-invalid` otherwise).
7. Receipt `source` is in `TERMINAL_SOURCES` — currently only `process-exit-status`
   (`reclaim-receipt-source-not-terminal` otherwise).
8. Receipt `source` differs from the occupant's `livenessSource`
   (`reclaim-receipt-not-independent` otherwise).
9. Occupant `pid` and `processInstance` are both non-null (`reclaim-occupant-unbound`
   otherwise).
10. Receipt `pid`, `processInstance`, `entryName`, and `slotRef` match the sidecar
    (`reclaim-receipt-binding-mismatch` otherwise).
11. Receipt `observedAt` is not before the occupant's `observedAt`
    (`reclaim-receipt-predates-liveness` otherwise).

Two properties make this fail-closed: an occupant with a null `pid` or `processInstance` can
**never** be authorized, and there is **no disk-pressure input, no force flag, and no
free-space read anywhere in the module** — an emergency cleanup path is how a recovery
mechanism becomes a data-loss mechanism.

### The terminal receipt

```json
{
  "schemaVersion": 1,
  "source": "process-exit-status",
  "pid": 12345,
  "processInstance": "inst-abc",
  "waitStatus": 0,
  "entryName": "<entryName>",
  "slotRef": "<slot>@<generation>",
  "observedAt": "<ISO-8601-UTC-Z>"
}
```

The caller mints this **at its real wait/reap seam, immediately after `os.waitpid`/
`Popen.wait()` returns, and nowhere else**.

The receipt is a **caller attestation minted at the reap seam** — the framework cannot verify
that the caller actually reaped the process. Its trustworthiness is the caller's responsibility.
Specifically, a non-blocking `waitpid(..., WNOHANG)` that returns `(0, 0)` means the process
has **not** exited and must never be turned into a receipt.

### The sweep

`sweep(slots_dir_path, *, now, receipts=None)` runs **on the next acting run, never on a
timer**. `receipts` is a mapping keyed by `entryName` to terminal receipts.

Each entry in `warned`, `retained`, and `deleted` carries a `kind` discriminator:

- `"entry"` — per-quarantine-entry shapes (`entryName`, `sidecarPath`, `entryPath`, `reason`).
- `"journal-segments"` — segment-pressure shapes (`slot`, `segmentCount`, `reason`).

Per-entry classification:

- Payload directory without a matching sidecar → warn `reclaim-sidecar-absent`, retain.
- Unreadable or invalid sidecar → warn with the load reason, retain.
- Sidecar `entryName` disagrees with its filename → warn `reclaim-sidecar-entry-name-mismatch`, retain.
- `move` is `pending` and the payload exists → repair sidecar to `moved`, warn, retain.
- `move` is `pending`, payload absent, but `originalPath` still exists → warn
  `reclaim-pending-move-not-applied` (payload safe at original path; sidecar stale), retain.
- `move` is `pending` and the payload is absent with no `originalPath` → warn
  `reclaim-entry-not-moved`, retain.
- `status` is `deleted` → retain (tombstone, no warn).
- `status` is `deletion-authorized` → re-run `authorize_deletion` with the stored receipt;
  on success resume delete if payload exists, otherwise write tombstone; on refusal retain and warn.
- Receipt supplied for entry → `authorize_deletion`; on success delete; on refusal retain
  (warn if grace has elapsed).
- No receipt → retain; warn `reclaim-grace-not-elapsed` if grace has elapsed.

Symlinked `.pilot-quarantine` refuses in both `quarantine_entry` and `sweep`
(`reclaim-quarantine-dir-unsafe`). Containment checks and sweep listing are check-then-use guards
under this project's single-user threat model — they aim at accidents and stale state, not a
hostile local actor.

Deletion order (three steps):

1. Write durable `deletion-authorized` sidecar with embedded `terminalReceipt`.
2. Remove the payload directory (`shutil.rmtree`).
3. Write `deleted` tombstone sidecar.

**The tombstone is retained forever.** An interrupted delete resumes on the next sweep when
the sidecar is already `deletion-authorized`.

### Journal rotation and retention

`rotate_journal(slots_dir_path, slot, journal_path, *, now, timeout=30.0)` rotates a live
journal into a retained segment.

**State gate:** rotation is permitted only when the slot record's state is `released` or
`retired`. `failed` refuses (`reclaim-rotate-slot-failed`) because its journal is what the
partial-failure report reads. Active states (`provisioning`, `provisioned`, `occupied`) refuse
(`reclaim-rotate-slot-active`).

**Quiescence:** an unfiltered replay must succeed with no torn tail, no anomalies, and every
effect in `applied` or `not-applied` state (`reclaim-rotate-not-quiescent` otherwise).

**Threshold:** at least `ROTATE_MIN_RECORDS` (200) non-empty lines in the live journal
(`reclaim-rotate-below-threshold` when below).

**Segment naming:** `<stem>.<NNNN>.ndjson` where `<stem>` is the live journal basename without
extension and `<NNNN>` is a zero-padded four-digit (or longer) sequence (`journal.0001.ndjson`,
`journal.0002.ndjson`, …). **Segments are never deleted.**

Segment-pressure warnings in `sweep` count retained segments for every `*.ndjson` live journal
found in a slot directory (default `journal.ndjson` and any non-segment sibling such as
`events.ndjson`), using the same stem-based derivation as `rotate_journal`.

`pilot_journal`'s writers do not hold the slot lock, so the exclusion rotation relies on is
**contract-level, not lock-level** — no provisioning attempt is live in `released` or
`retired`. The lock does not exclude writers.

Rotation **does not create a new live journal** — `pilot_journal`'s writer opens with `O_CREAT`
and recreates the live journal on the next append. For replay across retained segments plus the
live journal, see [Segment-aware aggregate replay](#segment-aware-aggregate-replay) under
[The provisioning journal](#the-provisioning-journal).

### Reclaim refusal tokens

| Token | When returned |
|---|---|
| `reclaim-slots-dir-invalid` | `slots_dir_path` is missing, empty, or not a string |
| `reclaim-source-invalid` | source path is not an absolute existing directory (symlinks and files refuse) |
| `reclaim-source-inside-slot-store` | source path is inside, equal to, or an ancestor of the slot store or quarantine |
| `reclaim-slot-ref-invalid` | `slot_ref` does not parse |
| `reclaim-reason-invalid` | `reason` is missing, empty, not a string, or exceeds 500 characters |
| `reclaim-occupant-invalid` | occupant block shape or field values fail validation |
| `reclaim-now-invalid` | `now` is not a valid ISO-8601 UTC timestamp |
| `reclaim-entry-exists` | quarantine entry or sidecar path already exists |
| `reclaim-cross-device` | `os.rename` fails with `EXDEV` |
| `reclaim-rename-failed` | `os.rename` fails for any other reason |
| `reclaim-sidecar-write-failed` | sidecar atomic write or parent-directory fsync fails — before any rename (nothing moved); after rename but before `move: moved` update (payload moved, sidecar stale); or during tombstone write after deletion (payload gone, tombstone missing) |
| `reclaim-sidecar-absent` | sidecar file does not exist |
| `reclaim-sidecar-unreadable` | sidecar cannot be opened or read as a regular file |
| `reclaim-sidecar-invalid` | sidecar JSON or structural validation fails |
| `reclaim-sidecar-status-unbacked` | `status` is `deletion-authorized` or `deleted` but `terminalReceipt` is absent |
| `reclaim-sidecar-entry-name-mismatch` | sidecar `entryName` disagrees with its filename |
| `reclaim-quarantine-dir-unsafe` | `.pilot-quarantine` is a symlink or non-directory |
| `reclaim-pending-move-not-applied` | `move` is `pending`, payload absent from quarantine, but `originalPath` still exists |
| `reclaim-grace-not-elapsed` | fewer than 72 hours since `quarantinedAt` |
| `reclaim-receipt-invalid` | receipt shape fails validation, or `receipts` argument to `sweep` is not a mapping |
| `reclaim-receipt-source-not-terminal` | receipt `source` is not in `TERMINAL_SOURCES` |
| `reclaim-receipt-not-independent` | receipt `source` equals the occupant's `livenessSource` |
| `reclaim-occupant-unbound` | occupant `pid` or `processInstance` is null |
| `reclaim-receipt-binding-mismatch` | receipt `pid`, `processInstance`, `entryName`, or `slotRef` does not match the sidecar |
| `reclaim-receipt-predates-liveness` | receipt `observedAt` is before the occupant's `observedAt` |
| `reclaim-entry-not-moved` | sidecar `move` is not `moved` |
| `reclaim-status-not-deletable` | sidecar `status` is already `deleted` |
| `reclaim-delete-failed` | `shutil.rmtree` on the payload fails during sweep |
| `reclaim-quarantine-dir-unreadable` | quarantine directory cannot be listed |
| `reclaim-journal-segments-high` | a slot has at least `SEGMENT_WARN_COUNT` (20) retained journal segments |
| `reclaim-slot-invalid` | slot id fails validation |
| `reclaim-journal-path-invalid` | journal path is missing, not absolute, or is a symlink |
| `reclaim-journal-outside-slot` | journal path is not contained in the slot directory |
| `reclaim-journal-absent` | live journal does not exist at rotation time |
| `reclaim-rotate-slot-unreadable` | slot record cannot be read during rotation |
| `reclaim-rotate-slot-active` | slot state is `provisioning`, `provisioned`, or `occupied` |
| `reclaim-rotate-slot-failed` | slot state is `failed` |
| `reclaim-rotate-not-quiescent` | journal replay is torn, anomalous, or has unsettled effects |
| `reclaim-rotate-below-threshold` | live journal has fewer than 200 non-empty lines (ok result, `rotated: false`) |
| `reclaim-rotate-segment-exists` | target segment path already exists |
| `reclaim-rotate-failed` | `os.rename` of live journal to segment fails |
| `reclaim-segments-unreadable` | slot directory cannot be listed for segment enumeration |
| `reclaim-aggregate-lock-unavailable` | `aggregate_replay`: `slot_lock` times out while listing retained journal segments and reading live-journal status |

### The reassignment acceptance probe

`reassignment_probe_result(slot_ref, checks)` grades four reach-check answers:

| Check | Required answer for `trusted` |
|---|---|
| `browser` | `unreachable` |
| `port` | `unreachable` |
| `worktree` | `unreachable` |
| `datastore` | `unreachable` |

Three answers: `unreachable`, `reachable`, `indeterminate`. Two verdicts: `trusted` and
`retire`. **An ungradeable probe is never `trusted`** — any missing check, unknown check name,
or invalid answer returns `retire`.

The verdict is **generation-bound**: `apply_probe_verdict` compares the carried generation
against the record's current one inside the mutation via `generation_check`. A `trusted`
verdict mutates nothing.

**Scope:** this module grades the probe and applies the fail-closed retirement; `failed →
retired` is an edge that **already exists** in the lifecycle transition table, so this is the
*reason* to take it, not a new transition — and making a failed slot reusable again is
deliberately **not built here**.

### Fence refusal tokens

| Token | When returned |
|---|---|
| `fence-slot-ref-invalid` | `slot_ref` does not parse |
| `fence-checks-invalid` | `checks` is not a mapping |
| `fence-check-unknown` | a check key is not one of the four required checks |
| `fence-check-missing` | a required check is absent |
| `fence-answer-invalid` | an answer is not one of the three allowed values |
| `fence-check-failed` | one or more checks are not `unreachable` (ok result with `verdict: retire`) |
| `fence-result-invalid` | probe result shape or verdict is invalid |
| `fence-result-slot-mismatch` | result `slotRef` does not equal the caller's `slot_ref` |
| `fence-now-invalid` | `now` is not a valid ISO-8601 UTC timestamp |
| `fence-slots-dir-invalid` | `slots_dir_path` is missing or empty |
| `fence-verdict-not-applicable` | verdict is `trusted` — no mutation applies |

## Cleanup containment and resurrection

Cleanup containment lives in `lib/pilot_cleanup.py`. It answers whether a project's declared
cleanup command is safe to run during resurrection — whether it confines its destructive effect
to the slot's own namespace — and plans the resurrection sequence without executing it.

### Why a receipt at all

A `{namespace}` argument on the cleanup command proves **command shape**, not **effect**. A
stale, buggy, or branch-modified cleanup can ignore its argument, connect to the wrong datastore,
or delete by a prefix that reaches sibling namespaces. The containment exercise runs the real
cleanup against planted sentinels and records what actually happened.

### The exercise lifecycle

The harness mints fresh sentinel ids, probes **absent** everywhere, plants in the slot's
namespace **and in every other declared slot namespace**, probes **present** everywhere, runs
the parameterized cleanup, then requires the own sentinel **gone** and every foreign sentinel
**surviving**. Both directions are checked: an inert cleanup that leaves the own sentinel
standing fails as loudly as an overreaching one that destroys a foreign sentinel.

**Every** sibling namespace is used, not one arbitrary foreign namespace. With slots `a`, `ab`,
and `b`, a prefix cleanup of `a*` destroys `ab` while leaving `b` intact — testing against a
single foreign namespace would pass.

### What the receipt is bound to

A passing receipt binds to:

- the declared cleanup argv (HMAC digest keyed on the policy document),
- the resolved configuration (sentinel commands, namespace, foreign namespaces, observed
  datastore identity with provenance and strength, run cwd),
- **and the cleanup's source state** — the repository HEAD oid plus a content digest of every
  dirty or untracked path in the cleanup repository (regular files by content, symlinks by link
  target string, directories and other non-regular entries by path only), plus content digests of
  the cleanup argv's executable (`argv0Digest`) and of every argv-tail element that exists as a
  regular file or as a symlink to a regular file (`argvDigests` — every tail element is probed as
  a path with no leading-dash exemption; relative tail paths are resolved against `runCwd`, the
  same cwd the cleanup command runs under). An element that names nothing on disk contributes
  nothing. The receipt refuses with `cleanup-source-argv-unbindable` when a tail element is not a
  string, when `lstat` leaves existence undetermined (for example `EACCES`, `ELOOP`, or `EIO`), or
  when an element exists but yields no content digest (a symlink to a non-regular target, a
  dangling or looping symlink, a directory or other non-regular entry, or an unreadable file) — the
  receipt is withheld rather than recording an unbound entry, so `argvDigests` never carries a null
  digest. `argv0_content_digest` digests a regular
  file only and returns `null` for a symlinked `argv[0]`, so a symlinked cleanup executable is not
  content-bound today — a known limitation, deliberately not closed here because refusing on it
  would break the ordinary "interpreter plus script" shape (`/usr/bin/python3` is commonly a
  symlink). An edit to bound files — committed or not — invalidates the receipt at the same argv.
  A cleanup that reads a file not named in its argv (a sourced helper, an imported module, a config
  file) is still not covered by this binding; that limitation is known.

  The source binding is a **snapshot taken before the exercise runs**, not an execution-time
  guarantee: a tail path can be created after it was classified absent, or a digested file replaced
  after it was hashed, between the snapshot and the cleanup's own execution. Closing that window
  would require an execution-time identity strategy, which this binding does not attempt.

  Because every relative argv-tail element is resolved against `runCwd`, an ordinary lexical argv
  token that happens to name an existing non-digestible entry there — most commonly a directory —
  refuses the whole receipt with `cleanup-source-argv-unbindable`. This is deliberate: the harness
  cannot tell a lexical token from a path the cleanup reads, and a receipt it cannot bind is one it
  must not issue. Authors can rename or relocate the colliding entry, or declare the cleanup with a
  `runCwd` that does not contain it.

Both digests are **HMAC-SHA256 keyed on a digest of the whole policy document**. An unkeyed
truncated digest of a low-entropy identity such as a database name would be a dictionary oracle
recovering the very material the policy keeps out of results.

### What the receipt does not prove

> This receipt is evidence about one execution of one cleanup command. It shows that a stale, buggy, or edited cleanup did not reach a foreign namespace on this run.
>
> It is NOT a defense against hostile cleanup code. A cleanup with datastore access can preserve or recreate a sentinel while destroying other foreign data, so a passing receipt does not establish containment against an adversary. Datastore permissions that cannot reach foreign namespaces are the stronger assurance, which is why resolve_containment prefers them.

The receipt is evidence against stale, buggy, and edited cleanup, **not** against hostile
cleanup code — which is why datastore permissions rank above it.

### The containment resolution ladder

`resolve_containment` returns one of four modes:

| Mode | Requires | Meaning | Refusal remedy |
|---|---|---|---|
| `permissions` | `containment.permissions` with `cannotReachForeignNamespaces: true` and non-empty `evidence` | Datastore permissions cannot reach foreign namespaces; no receipt exercise needed | — |
| `single-slot` | Policy declares exactly one slot | No sibling namespace exists to destroy | — |
| `receipt` | A passing, fresh `cleanup-containment` receipt for the current policy, block, and source tree | Containment was exercised and passed on this run | — |
| `refused` | None of the above | Containment cannot be assured | `isolated datastores, or one slot` |

### The trust asymmetry

The cleanup command lives in the branch-mutable `pilot` block and is deliberately **unconfined**
— it is the thing under test. The sentinel instruments live in the out-of-reach policy and are
**confined**: owner-owned executable, not group/world-writable, absolute `argv[0]` outside every
reach root, run cwd outside every reach root. An instrument a branch can edit can forge its own
verdict.

### Journaling

Both shared effects — the plant and the cleanup — are wrapped in `pilot_journal`
`namespace-touched` begin/end pairs, so a crash mid-exercise leaves `possibly-applied` rather
than a silent gap.

### Bounded runner output modes

`pilot_bounded_run.run_bounded` is the shared bounded child-process runner; `pilot_cleanup.run_bounded`
is a thin adapter over it with `retain_output=False`. The `retain_output` parameter selects how
stdout is handled:

- `retain_output=True` (default, unchanged): stdout is retained up to `max_output_bytes`; output
  beyond the cap classifies as `oversize`.
- `retain_output=False`: stdout is counted but never accumulated; `stdoutBytes` and
  `stdoutTruncated` are reported on every outcome; **truncation is reportable on a `completed`
  outcome, not a refusal**.

The two modes exist because the callers' semantics differ — `pilot_mint` needs the bytes back;
`pilot_cleanup` only needs exit classification and byte counts. Collapsing the modes would erase
one of those contracts. Both modes return `stdoutBytes` and `stdoutTruncated`, so the result shape
is uniform.

Under `retain_output=False`, a **mid-stream read error refuses** as `spawn-failed`, which
`pilot_cleanup` turns into `cleanup-sentinel-probe-indeterminate` — this is a behaviour change from
the pre-fold `pilot_cleanup` copy, which could have reported zero bytes on a read failure. Process-group
containment on every termination path is unconditional in both modes.

### Resurrection

`resurrection_plan` orders: parameterized cleanup → reseed through A1's interface via A3's
authorization chokepoint → a new generation (**enforced at the broker, C7 — this planner does
not perform it**) → resume. The `artifact` keyword is not part of the signature.

Sign-in-path dispatch is exhaustive: `"attended"` maps to **`park`** and `"minted"` maps to
**`resurrect`** with mint reseed steps. An unknown `signInPath` or dispatch kind **raises** rather
than falling through to mint.

On the **`attended`** sign-in path, `resurrection_plan` returns **`park`** with
`cleanup-attended-reseed-requires-owner` and carries **no steps** — nothing is cleaned up and
nothing is reseeded, because the work must be preserved for the owner. Attended cannot
self-resurrect because no credential was stored. The **`minted`** path is unchanged: containment
resolved and verdict present → `resurrect` with mint reseed steps.

**Effects-escape rule:** the declaration has no default; an absent or unexercised declaration
refuses. Where effects **can** escape the datastore (`effectsEscape.canEscape` is `true`), a
crashed slot **parks for owner inspection instead of resurrecting** — reseeding cannot un-send
mail or un-fire a webhook, and replay would duplicate it.

Resurrection actions: `park` (effects can escape), `resurrect` (containment resolved and verdict
present), `refuse` (declaration unexercised, containment unresolved, or verdict missing).

### Residual sentinels

The harness plants foreign sentinels it cannot remove — there is no remove command, and running
the project cleanup against a sibling namespace to tidy up would be the exact destruction the
exercise prevents — so the receipt records them under `residualSentinels` for the advisor. On a
successful exercise, residual entries name the **foreign** namespaces whose sentinels were
planted and not removed. On a **plant failure**, an entry may also name the **own** namespace,
marked `possibly-planted`, meaning the plant may or may not have written before failing. Each
entry carries the `namespace`, the planted `sentinelId`, and a `state` of `planted` when the plant
command completed successfully or `possibly-planted` when the plant may or may not have written (a
mid-command failure or timeout leaves the honest `possibly-planted` state) so the advisor can
locate and remove residue without guessing which unpredictable id was minted for that namespace.

### Declare-and-exercise binding

`cleanup_containment_exercise_declaration(cleanup, slot)` is the declaration shape for
`cleanup-containment` registry records and `require_exercised` checks: the cleanup declaration
plus the slot id, so a receipt exercised for one slot cannot satisfy resurrection for a sibling.

The containment exercise is **not** safe to run concurrently against one datastore for two
sibling slots: concurrent exercises can interfere through shared sentinel state and degrade to a
false `cleanup-foreign-sentinel-destroyed` containment failure rather than a false pass.

### Cleanup containment refusal tokens

| Token | When returned |
|---|---|
| `cleanup-namespace-invalid` | `namespace_for_slot`, `resolve_cleanup_command`, or `substitute_sentinel_command`: slot id does not validate |
| `cleanup-command-invalid` | `resolve_cleanup_command` or `substitute_sentinel_command`: command is missing, empty, or contains a non-string or empty argv element |
| `cleanup-command-unparameterized` | `resolve_cleanup_command` or `substitute_sentinel_command`: `{namespace}` or `{sentinel}` is absent from `command[1:]`, or substitution leaves no namespace/sentinel in the resolved argv |
| `cleanup-command-argv0-placeholder` | `resolve_cleanup_command` or `substitute_sentinel_command`: `{namespace}` or `{sentinel}` appears in `argv[0]` |
| `cleanup-command-placeholder-unknown` | `resolve_cleanup_command` or `substitute_sentinel_command`: an unrecognised `{...}` placeholder appears in the command |
| `cleanup-substitution-empty` | `resolve_cleanup_command` or `substitute_sentinel_command`: placeholder substitution produces an empty argv element |
| `cleanup-sentinel-undeclared` | `_sentinel_from_policy`: `datastore.containment` is absent or `sentinel` is `null` |
| `cleanup-sentinel-declaration-invalid` | `_validate_sentinel_declaration`: sentinel shape, env var, or command argv is malformed |
| `cleanup-sentinel-confinement` | `_validate_sentinel_declaration`: reach roots or run cwd invalid; executable not owner-owned, not mode-safe, not outside reach roots, or run cwd inside reach |
| `cleanup-sentinel-id-invalid` | `substitute_sentinel_command`: sentinel id does not match the allowed pattern |
| `cleanup-sentinel-plant-failed` | `plant_sentinel`: plant command exited non-zero or timed out |
| `cleanup-sentinel-probe-indeterminate` | `probe_sentinel` or `run_bounded`: probe exited with a code other than 0/1, timed out, or subprocess could not be started |
| `cleanup-source-root-invalid` | `source_identity`: `cleanup_root` is missing or not an existing directory |
| `cleanup-source-unreadable` | `source_identity`: `git status --porcelain -z` could not be read, or a dirty worktree file could not be hashed |
| `cleanup-source-argv-unbindable` | `_argv_tail_digests`: an argv-tail element exists but yields no content digest (a symlink to a non-regular target, a dangling or looping symlink, a directory or other non-regular entry, an unreadable file, or an indeterminate `lstat`), or a tail element is not a string |
| `cleanup-policy-invalid` | `foreign_namespaces`: policy shape or slot membership is invalid |
| `cleanup-argv0-not-absolute` | `cleanup_effect_receipt`: resolved cleanup `argv[0]` is not an absolute path |
| `cleanup-receipt-vacuous` | `cleanup_effect_receipt`: sentinel already present before plant, or absent after plant |
| `cleanup-own-sentinel-survived` | `cleanup_effect_receipt`: own sentinel still present after cleanup |
| `cleanup-foreign-sentinel-destroyed` | `cleanup_effect_receipt`: a foreign sentinel was destroyed by cleanup |
| `cleanup-command-failed` | `cleanup_effect_receipt`: cleanup command exited non-zero or timed out |
| `cleanup-no-foreign-namespace` | `cleanup_effect_receipt`: policy has no sibling slot to contain against |
| `receipt-schema-invalid` | `receipt_valid_for` or `registry_record`: receipt shape is invalid; or `resolve_containment`: receipt validation prerequisites are missing |
| `receipt-result-not-pass` | `receipt_valid_for` or `registry_record`: receipt `result` is not `pass` |
| `receipt-slot-mismatch` | `receipt_valid_for`: receipt `slotRef` does not match |
| `receipt-stale-command` | `receipt_valid_for`: declared cleanup command changed since the receipt was taken |
| `receipt-stale-config` | `receipt_valid_for`: resolved configuration or source state changed since the receipt was taken |
| `containment-undeclared` | `resolve_containment`: no permissions, no single-slot escape, and no receipt supplied |
| `resurrection-effects-escape-park` | `resurrection_plan`: `effectsEscape.canEscape` is `true` — slot parks for owner inspection |
| `resurrection-effects-escape-unexercised` | `resurrection_plan`: `effects-escape` declaration has not been exercised |
| `resurrection-containment-unresolved` | `resurrection_plan`: containment mode is not `permissions`, `receipt`, or `single-slot` |
| `resurrection-cleanup-containment-unexercised` | `resurrection_plan`: containment mode is `receipt` but `cleanup-containment` declaration is unexercised |
| `resurrection-verdict-missing` | `resurrection_plan`: no boundary verdict supplied |
| `cleanup-attended-reseed-requires-owner` | `resurrection_plan`: `signInPath` is `"attended"` — slot parks; no cleanup or reseed steps are planned because the work must be preserved for the owner |

Public API in `lib/pilot_cleanup.py`: `namespace_for_slot`, `foreign_namespaces`,
`resolve_cleanup_command`, `substitute_sentinel_command`, `mint_sentinel_id`, `plant_sentinel`,
`probe_sentinel`, `cleanup_effect_receipt`, `receipt_valid_for`, `registry_record`,
`cleanup_containment_exercise_declaration`, `resolve_containment`, `resurrection_plan`.

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
with mode that grants neither group- nor world-write, resolved **outside every reach root**;
`run_cwd` must be an existing directory outside every reach root; and every absolute command
argument, and every relative argument resolved against `run_cwd`, must lie outside every reach
root. `reach_roots` is a required argument — omitting it or supplying an empty or invalid list
refuses (`browser-pin-observer-unsafe`) rather than spawning. Branch-controlled code must not
be able to supply the executable that vouches for the pin. The child receives
a **minimal environment** — only `PATH` is carried from the ambient environment, nothing else.
The observer contract requires one clean line of stdout in the form `<version> <digest>`, from
a bounded subprocess with stderr discarded; a subprocess that cannot spawn, or anything else
(non-zero exit, timeout, oversized output, invalid UTF-8, multi-line stdout, control characters,
or wrong token count), refuses (`browser-pin-observer-failed`) rather than raising.

### The socket directory

A unix socket path is capped by `sun_path` — 104 bytes on Darwin, 108 on Linux (the values in
`SUN_PATH_MAX`). The framework **measures the worst-case full path and refuses before launch**
(`socket_dir_plan`), and an unrecognised platform uses the **smallest** cap. The base directory
defaults to a short path under the system temp directory — never derived from the checkout —
and is never inside the worktree (`browser-socket-base-in-worktree` when `worktree_root` overlaps
the base). Checkout-independent base selection keeps the measured worst-case path independent of
where the repository lives. When the caller omits `worktree_root`, `socket_dir_plan` resolves the
calling process's repository root from `os.getcwd()` itself (`browser-worktree-root-unresolved`
when that resolution fails). Field evidence this closes: deep worktree paths break automation
socket tooling.

`remove_socket_dir` refuses **before deleting anything** when the path's basename does not carry
the framework's socket-directory prefix (`pb-`; `browser-socket-dir-unrecognized`). Removal is
still guarded by "is a directory, not a symlink" on an already-planned path.

### Teardown requires an observed terminal state

`teardown_server` never infers process exit from the socket file's absence — that is a second
read of the same liveness marker the design refuses for terminal states. The caller supplies an
`observe_exit` callback; teardown proceeds only when it reports `exited: true` for **both** the
server PID and the browser PID. A genuinely unobserved exit refuses (`browser-terminal-state-unobserved`);
an observer that reports a process exited but cannot supply an exit status is **accepted** — the
receipt records the status as absent. This matters because the browser is the server's child by
design, so a launcher legitimately has no exit status for it. A reparented or surviving browser
would otherwise hold a live authenticated session while teardown reported success — so both
processes must be observed exited. The teardown receipt carries both exit statuses
(`observedServerExitStatus`, `observedBrowserExitStatus`); either may be absent.

When socket-directory removal fails after having already removed entries, teardown records the
journal effect as **possibly-applied** (`indeterminate`), not `not-applied`, because the
journal's `not-applied` means *proved* not applied — partial cleanup is not proof of
non-application.

### Broker admission

The broker-admission guarantee does not hold in general: several public entry points in
`pilot_browser.py` can leak a **builtin** exception once an input gets past outer shape
validation.
The raise sites below are **the ones found so far**; two successive hostile-input sweeps have
each discovered sites the previous sweep missed, so this list is a **floor**, not an inventory —
it is explicitly **not** established as complete.

- **`validate_pin` raises `PilotBrowserError` by design** — it is exception-only, not a
  refusal-returning function; callers are expected to catch the domain exception (e.g.
  `validate_pin(None)` raises `PilotBrowserError: browser-pin-invalid`).
- **`verify_pin` is a hybrid** — it raises `PilotBrowserError` during its structural-validation
  phase, then returns `ok`/`reason` dicts for observer failure, version mismatch, and integrity
  mismatch (seven dict-returning exits in total — six `_fail`, one `_ok`). *This hybrid
  characterization is from reading those return sites in code, not from an execution receipt — the
  hostile-input sweep could not drive `verify_pin` past `_validate_observer_safety` in the
  measurement environment.* `verify_pin` can also raise builtin `ValueError` when a NUL byte
  appears in the observer executable path (e.g. `command=["/us\x00r/bin/false"]`):
  `_validate_observer_safety` does `os.stat(executable)` inside a `try/except OSError`, and a NUL
  in the path raises `ValueError`, which that handler does not catch.
- **`socket_dir_plan` can raise builtin `TypeError`** when `platform` is unhashable (e.g.
  `platform=[]` or `platform={}`) — a recognised validation input, not a call-shape error.
- **`socket_dir_plan` can also raise builtin `UnicodeEncodeError`** when `launch_token` contains a
  surrogate (e.g. `launch_token="\udc80"`) while measuring the socket path — the same category as
  its `TypeError` entry above.
- **`create_socket_dir` can raise builtin `ValueError`** on a NUL-containing path (e.g.
  `path="a\x00b"`): the `islink`/`lexists` pre-checks return `False` for a NUL path rather than
  raising, so the path reaches the guarded block, and `os.makedirs` then raises `ValueError` inside
  a `try/except OSError` that does not catch it.
- **`plan_topology` can raise builtin `TypeError`** when `accounts` is not iterable despite a valid
  `slot_ref` (e.g. `plan_topology("slot-a@1", None)` or `plan_topology("slot-a@1", 0)`): `for
  entry in accounts` executes directly with no iterability check.
- **`begin_provision_server` and `provision_server` can raise builtin `ValueError`** on a
  NUL-containing journal path (e.g. `journal_path="a\x00b"`); the failure comes from `os.open` on
  the lock file inside `pilot_journal._acquire_journal_lock`, reached because `_is_str_path`
  accepts any `str` and a NUL byte only fails at the syscall — not from opening the journal itself.
- **`teardown_server` can raise builtin `ValueError`** on a NUL-containing journal path when exit
  observation reports both processes exited (e.g. `teardown_server("a\x00b", ...,
  observe_exit=both-exited)`): it is masked **only while exit observation refuses** — the default
  observer reports not-exited and refuses early with `browser-terminal-state-unobserved`, but with
  an observer reporting both processes exited it proceeds to journalling and hits the same lock-file
  `ValueError`; its `except` clauses do not handle it.

A **common cause** runs through most of these: a `try/except OSError` around a path syscall does
not catch the `ValueError` a NUL byte produces, and `_is_str_path` accepts any `str`.

Several entry points raise builtin `TypeError` on **call-shape errors** — supplying a non-callable
where a callable is required, or omitting a required argument — rather than refusing. These are
the same class of mistake as calling the API wrong, not a recognised validation failure that leaks
through shape checks: **`assert_browser_is_server_child`** when `ppid_of` is not callable (e.g.
`ppid_of=0`), **`provision_server`** when `ppid_of` is not callable, **`teardown_server`** when
`observe_exit` is not callable (e.g. `observe_exit=0`), and **`provision_server`** when
`effect_id` is **omitted** at the call, as any Python call missing an argument does. An
`effect_id` that is *supplied* but unusable still refuses (`browser-server-record-invalid`).

Every browser instruction travels through the per-generation server, which is why admission is
where a stale generation dies. `admit` is the fencing chokepoint: it requires `slots_dir` and
reads the slot's on-disk lifecycle record for the authoritative generation — it does not trust
the caller's server record for "current". An unusable `slots_dir` — omitted, not a non-empty
string, or not an existing directory — refuses (`browser-fencing-slots-dir-required`) rather than
raising. A server record whose `generation` disagrees with the slot store refuses
(`browser-server-record-stale`) before comparing the operation's generation. Fencing also reads
the slot's on-disk lifecycle **state**: only `provisioned` and `occupied` may serve browser
operations; `provisioning`, `released`, `failed`, and `retired` refuse
(`browser-slot-state-not-live`). The state check matters because `released`, `failed`, and
`retired` slots keep the **same** generation number — a generation-only fence would still admit a
slot that is no longer live. Generation comparison then delegates to
`pilot_lifecycle.generation_check`, propagating its tokens (`slot-generation-stale`,
`slot-generation-ahead`) rather than re-deriving them. Cross-reference the declared seam **S1**
(generation numbering defined in A2a / #823, enforced here).

### Provisioning journal shape

The primary provisioning shape journals **before** processes exist: `begin_provision_server`
writes the journal `begin` record and returns an `effectId`; the caller spawns the server and
browser, then `provision_server` closes that effect with `outcome: applied` via the supplied
`effect_id`. A crash between spawning and recording must replay as *possibly-applied*, never as
never-happened (#660 §7). This is the **only** provisioning shape: `effect_id` is a required
argument, so omitting it is a `TypeError` at call time, and an explicitly supplied non-string or
empty `effect_id` refuses (`browser-server-record-invalid`). There is no journal-after-the-fact
fallback — the legacy `effect()` wrapper was removed in #863 with zero live callers, because a
crash on that path left no journal trace at all.

Public API in `lib/pilot_browser.py`: `validate_pin`, `verify_pin`, `socket_dir_plan`,
`create_socket_dir`, `remove_socket_dir`, `assert_browser_is_server_child`,
`begin_provision_server`, `provision_server`, `teardown_server`, `plan_topology`,
`admit_server_registry`, `admit`.

### Known limitations

These are recorded contract facts, not oversights pending silent fix:

- **Socket-base worktree containment resolves the calling process's repository, not the slot's
  worktree.** Per-slot worktrees are a framework concept C7 does not own; binding the
  containment check to the slot's tree belongs with the sub-issues that own slot worktrees
  (B5/C8). As shipped, the check confines the base relative to the running process's repo.

### Browser topology refusal tokens

| Token | When returned |
|---|---|
| `browser-pin-invalid` | `validate_pin`: pin is not a dict with exactly `schemaVersion`, `version`, and `integrityDigest`; `schemaVersion` is not `1`; `version` is empty or contains whitespace/control characters; `integrityDigest` is not a 64-character lowercase hex string |
| `browser-pin-observer-invalid` | `_validate_observer` or `verify_pin`: observer is not a dict with exactly a non-empty `command` list of non-empty strings; `run_cwd` is not a string path; `timeout_seconds` or `max_output_bytes` has wrong type |
| `browser-pin-observer-unsafe` | `_validate_observer_safety` or `verify_pin`: `reach_roots` is omitted, empty, or invalid; `run_cwd` is not an existing directory or overlaps a reach root; observer executable is not an absolute path, cannot be stat'd, is not a regular file, owner UID does not match the reading process, mode grants group- or world-write, or overlaps a reach root; or any command argument resolves inside a reach root |
| `browser-pin-observer-failed` | `verify_pin`: subprocess spawn failure, timeout, oversized output, non-zero exit, invalid UTF-8, empty/multi-line/control-character stdout, or stdout not exactly two space-separated tokens |
| `browser-pin-version-mismatch` | `verify_pin`: observed version does not match the pin's `version` |
| `browser-pin-integrity-mismatch` | `verify_pin`: observed digest does not match the pin's `integrityDigest` |
| `browser-socket-path-too-long` | `socket_dir_plan`: worst-case socket path exceeds the platform `SUN_PATH_MAX` cap, or `launch_token` is present but not a non-empty string |
| `browser-socket-base-in-worktree` | `socket_dir_plan`: `worktree_root` is not a string, or the resolved base directory overlaps the worktree |
| `browser-worktree-root-unresolved` | `socket_dir_plan`: `worktree_root` is supplied but not a valid path string, or omitted and `store_core.repo_root(os.getcwd())` for the calling process fails |
| `browser-socket-dir-exists` | `create_socket_dir`: the planned path already exists |
| `browser-socket-dir-unsafe` | `create_socket_dir`: plan is invalid, path is a symlink, created path is not a directory, mode is wrong, or `os.makedirs`/`stat` fails; `remove_socket_dir`: path is a symlink |
| `browser-socket-dir-not-directory` | `remove_socket_dir`: path is not a string or not a directory |
| `browser-socket-dir-unrecognized` | `remove_socket_dir`: path basename does not start with the framework socket-directory prefix (`pb-`), checked before any entries are removed |
| `browser-socket-dir-unremovable` | `remove_socket_dir`: directory contents cannot be enumerated; an entry cannot be classified or removed safely (including a non-empty subdirectory); or removing the now-empty directory fails |
| `browser-server-record-invalid` | `provision_server`, `teardown_server`, `admit_server_registry`, or `admit`: server record shape, slot reference, generation, PIDs, pin, or timestamps fail validation; `provision_server`'s required `effect_id` is supplied but is not a non-empty string; journal write fails |
| `browser-not-server-child` | `assert_browser_is_server_child`: browser PID's parent is not the server PID |
| `browser-pid-unreadable` | `assert_browser_is_server_child`: parent PID cannot be read from the process table |
| `browser-terminal-state-unobserved` | `teardown_server`: `observe_exit` does not return a dict with `exited: true` for the server PID or for the browser PID (a dict with `exited: true` and absent `status` is accepted) |
| `browser-shared-context-refused` | `plan_topology`: duplicate account in the account list; `context_set`: two accounts would share the same context identity |
| `browser-server-shared-across-slots-refused` | `admit_server_registry`: the same server PID appears under more than one slot |
| `browser-shared-across-slots-refused` | `admit_server_registry`: the same browser PID appears under more than one slot |
| `browser-multiple-servers-for-slot` | `admit_server_registry`: more than one server record exists for the same slot |
| `browser-fencing-slots-dir-required` | `admit`: `slots_dir` is omitted, not a non-empty string, or not an existing directory |
| `browser-server-record-stale` | `admit`: on-disk slot lifecycle record cannot be read, or the live server record's `generation` disagrees with the slot store's authoritative generation |
| `browser-slot-state-not-live` | `admit`: on-disk slot lifecycle state is not `provisioned` or `occupied` |
| `browser-operation-slot-ref-invalid` | `socket_dir_plan`, `provision_server`, `plan_topology`, or `admit`: operation slot reference does not parse |
| `browser-operation-slot-mismatch` | `admit`: operation slot id does not match the live record's slot |

## Browser context creation and seed injection

This is the declared seam **S3**'s context-side half: A1 (#822) owns the interface and
artifact-integrity contract; the artifact-restore entry point (`context_spec_from_artifact`) is
**latent, with no producer** in this repository, kept as the declared S3 seam. Live seeding is
**attended** (B4, `lib/pilot_attended.py`) or **minted** (B6); **context-side injection is C7's**
because C7 owns context creation and the capture options.

**No credential is seeded before provisioning gates have run.** `context_spec` refuses to build
a context spec without a valid `gate_provisioning` receipt whose `slotRef` matches the caller's
slot reference — boundary authorization, declare-and-exercise, and datastore-identity gates must
have completed first. The receipt check is not shape-only: it requires a non-empty `declarations`
list whose entries carry `kind` and `status`, a `datastoreIdentity` carrying `provenance`,
`strength`, and `match` with `match` true, a non-empty `policyDigest`, and it refuses an
unparseable caller `slot_ref` rather than allowing it. The receipt is the evidence that the
boundary, declare-and-exercise, and datastore-identity gates ran — a gate that accepted a
hand-made dict would not be checking anything. This is the ordering guarantee the design rests
on; the receipt is checked before live seeding runs.

Both `context_set` and `context_spec` take a required keyword-only `sign_in_path` argument.
Live-seeding paths (`attended` and `minted`) take **no** artifact; a supplied artifact refuses
with `context-artifact-refused-on-live-seeding`. A non-string `sign_in_path` (for example a list
or dict) refuses `context-sign-in-path-invalid` via an `isinstance` check before membership
testing — it does not raise `TypeError`. Any other invalid `sign_in_path` also refuses
`context-sign-in-path-invalid`. The returned spec carries `"artifact": None`.

`context_spec_from_artifact(slot_ref, account, artifact, *, capture_surfaces,
provisioning_receipt)` is the **latent** S3 restore entry point: it builds one context spec from
a stored artifact via verify-at-seed. **No caller in this repository** reaches it — live seeding
must pass `sign_in_path` on `context_spec` instead.

A project declares which surface holds its login session, and **the framework requires the
matching capture options** — `indexedDB: true` for an IndexedDB-held session, `credentials: true`
for WebAuthn. A capture missing the options its declared surfaces require **refuses here**. The
match must be **exact in both directions**: an option set that the declared surfaces do not
require also refuses, because an unrequired `credentials: true` installs a virtual authenticator
that displaces real ones.

**Verify-at-seed on the latent artifact path** happens at context creation — the artifact's
integrity is checked as the context is built, and the spec carries the artifact's verified path
and hash, never its contents. On attended and minted live-seeding paths there is no artifact.

One context per account; `sessionStorage` never reaches a context spec (D7).

Public API in `lib/pilot_context.py`: `context_set`, `context_spec`, `context_spec_from_artifact`.

### Context refusal tokens

| Token | When returned |
|---|---|
| `context-provisioning-receipt-missing` | `context_spec`: `provisioning_receipt` is `None` |
| `context-provisioning-receipt-invalid` | `context_spec`: receipt is not a dict, is missing a required key (`slotRef`, `policyDigest`, `datastoreIdentity`, `declarations`), any required value is `None` or wrong type, `declarations` is empty or an entry lacks `kind` or `status`, `datastoreIdentity` lacks non-empty `provenance`/`strength` or `match` is not `true`, or `policyDigest` is empty |
| `context-provisioning-receipt-slot-mismatch` | `context_spec`: receipt `slotRef` does not equal the canonical slot reference for the caller's `slot_ref` |
| `context-options-mismatch` | `context_spec`: `requested_options` is supplied and does not exactly equal `required_context_options(capture_surfaces)` |
| `context-sign-in-path-invalid` | `context_set` or `context_spec`: `sign_in_path` is not a string, or is not in `attended` / `minted` |
| `context-artifact-refused-on-live-seeding` | `context_set` or `context_spec`: artifact supplied on attended or minted live-seeding path |
| `context-artifact-missing` | `context_spec_from_artifact`: artifact is `None` |
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
| `session-surface` | `pilot.captureSurface` + `pilot.captureOptions` | always |
| `cleanup-containment` | `pilot.cleanup` | always |
| `effects-escape` | `pilot.effectsEscape` | always |
| `operating-ceiling` | `pilot.administrativeMax` | always |
| `mint-gate-off` | `pilot.mint.envelope` | slot policy grants `mintableAccounts`, or `pilot.mint` is present |
| `mint-account-allowlist` | policy slot's `mintableAccounts` | slot policy grants `mintableAccounts`, or `pilot.mint` is present |

Two load-bearing facts: **mint applicability is policy-side** — a slot whose policy grants
`mintableAccounts` makes both mint kinds applicable regardless of whether the branch-mutable
`pilot.mint` block declares mint; a policy grant with no block declaration to exercise now
refuses (`provision-mint-declaration-missing`) rather than skipping. An attended-sign-in project
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

## Per-slot app lifecycle

Per-slot app instance control lives in `lib/pilot_appctl.py`. It owns one slot's app
process: resolve the project's `devCommand` and `readinessUrl` with per-slot parameters,
fence endpoints wave-wide before any spawn, write the durable instance record **before**
spawn, poll readiness with attribution, and stop with two independent observations.

**Declaration digest limit:** the `app-lifecycle` declaration digest binds the policy-side
`origin` and `permittedRedirects` for the slot — the same facts `authorized_app_launch` checks
`baseUrl` and `readinessUrl` against. It does **not** bind the project's branch-mutable
`devCommand` or outer `readinessUrl` (those live in the outer `test-pilot-config`, outside the
extractor's reach). A `devCommand` change therefore does not invalidate an existing
app-lifecycle exercise receipt. Closing that gap would need the outer config in the extractor's
reach — a successor change, deliberately not made here.

**What it deliberately does not own:** it allocates no port, picks no port, performs no
fencing at a broker, and never restarts or reseeds a slot. Port assignment and broker-side
enforcement are upstream; this module consumes an allocation and proves the endpoint is free
before bind.

### Parameterization (`resolve_invocation`)

The project's `devCommand` and `readinessUrl` carry `{name}` placeholders substituted from
a per-slot `params` map. Substitution is a **single left-to-right pass** per string: each
`{name}` is replaced once and the scan does not re-examine substituted text. A re-scanning
implementation would let a project's parameter value become a template — a value containing
`{other}` could expand into a second substitution the author did not intend.

`{name}` must not appear at `argv[0]` — the same rule as
`pilot-cleanup-placeholder-in-argv0` for cleanup commands. A placeholder in the executable
position would let project data choose which binary runs.

### Endpoint fencing

`check_endpoint_free` probes whether `(host, port)` accepts a new bind. A per-slot occupancy
probe is **not** the port fence: two slots handed the same free port both observe it free
before either binds. `assert_unique_endpoints` refuses duplicate `(host, port)` pairs
across the wave **before** any spawn — wave-wide endpoint uniqueness is the fence.
A malformed host or port is an allocation error (`app-allocation-invalid`), never a bind
conflict — `app-bind-conflict` means evidence that something is already listening on a
well-formed endpoint.

### Bind conflict

A bind conflict is **terminal, never retried**. `RETRYABLE_REASONS` is an **allowlist** —
only `app-readiness-timeout` and `app-readiness-transport-error` are retryable today, so a
future refusal token cannot silently become retryable without an explicit code change.
`app-bind-conflict` is deliberately absent from the allowlist.

### Readiness ladder

`stand_up` evaluates readiness in this order on each poll:

1. **Process exited** — if the child has exited, inspect stderr for bind-conflict patterns;
   bind conflict wins over generic process exit.
2. **Transport error** — probe carries a transport `error`; retry until the monotonic
   deadline, then `app-readiness-transport-error`.
3. **Redirect** — HTTP 3xx is refused (`app-readiness-redirect-refused`), not followed. A
   redirect means the readiness target is not the one the boundary authorized.
4. **Success band** — HTTP 2xx:
   - `readinessAttribution: "nonce"` — the launch nonce must appear in the response body;
     deadline expiry without it is `app-readiness-unattributed`.
   - `readinessAttribution: "unattributed"` — accepted but recorded as a **degradation**
     (`readiness-unattributed` kind).
5. **Unexpected status** — any other non-empty HTTP status at deadline is
   `app-readiness-unexpected-status`.
6. **No answer** — deadline reached with no transport error and no HTTP status is
   `app-readiness-timeout`.

`readinessAttribution` has no default — it must be exactly `nonce` or `unattributed`.

### Instance record states

| State | Meaning |
|---|---|
| `starting` | record written before spawn; process may not yet be ready |
| `ready` | readiness probe succeeded and generation still matches |
| `stopped` | stop observed both process-group gone and endpoint free |
| `indeterminate` | readiness failed, stop could not observe both conditions, or generation moved mid-flight |

**Record-before-spawn:** the instance record is written in `starting` state with `pid: 0`
before `Popen`. A crash between the record and the spawn leaves `starting`, which is the
honest state, rather than an invisible live app.

**On-disk instance record (`app.json`):** durable fields include `stdoutPath` and
`stderrPath` — absolute paths beside the slot directory where the default spawn redirects
child stdout/stderr so long-running chatty processes cannot block on pipe buffers.

### Stop observations

Stop requires **two independent observations**: the process group is gone **and** the
endpoint is free. Identity is corroborated **before** any signal (`ps` matching the
executable token — the first whitespace-separated field of the `ps` command line, or its
basename — not a substring of the whole line). A double stop is idempotent — an
already-`stopped` record with a valid `stopReceipt` returns that receipt; a `stopped`
record without one is not evidence and falls through to the two-observation path. A
`stopReceipt` whose `slotRef` does not exactly match the instance record's `slotRef` is
invalid — the same provenance rule as `slot-replay-slot-mismatch`: **provenance, not
authentication**; a caller that hand-builds the dict can still forge it; what it removes is
the accidental cross-wiring of one slot's stop evidence into another slot's record.

`check_endpoint_free` may return `observable: false` on `socket.timeout` (unknown occupancy).
That carve-out applies to the pre-spawn probe only. `stop()` treats a non-observable
endpoint probe as **not** endpoint-free.

**Accepted residual:** a reused pid whose process runs the same `argv[0]` would corroborate
via `ps`. Under this project's single-user local threat model the guard targets accidents
and stale state, not a hostile local actor — the same posture section 15 uses for its
check/use limit.

### App lifecycle refusal tokens

| Token | When returned |
|---|---|
| `app-command-invalid` | `devCommand` is absent, not a non-empty list of non-empty strings |
| `app-params-invalid` | `params` is not a mapping, a key is empty or contains `{`/`}`, or a value is not a string |
| `app-placeholder-unresolved` | a `{name}` placeholder remains after single-pass substitution |
| `app-placeholder-in-argv0` | `argv[0]` contains a `{name}` placeholder |
| `app-env-invalid` | optional `env` is not a mapping of valid string keys and values |
| `app-allocation-invalid` | allocation list entry is malformed, has duplicate `slotRef`, or port out of range; or `check_endpoint_free` received a malformed host, port, timeout, or non-callable `connect` |
| `app-launch-invalid` | `stand_up` launch dict shape, slot/slotRef mismatch, or `readinessAttribution` not in the allowed set |
| `app-cwd-invalid` | `cwd` is not an absolute existing directory, or the path is a symlink or non-directory |
| `app-readiness-url-invalid` | readiness URL is absent or not `http`/`https` after substitution |
| `app-bind-conflict` | endpoint probe on a well-formed `(host, port)` finds something listening, spawn stderr shows bind conflict, or probe raises an `OSError` other than connection refused / timeout |
| `app-endpoint-duplicate` | `assert_unique_endpoints` finds the same `(host, port)` on two slots |
| `app-spawn-failed` | `Popen` raised `OSError` |
| `app-readiness-timeout` | *(retryable)* readiness polling exhausted the monotonic deadline with no transport error and no HTTP status |
| `app-readiness-transport-error` | *(retryable)* readiness probe still carries a transport `error` when the monotonic deadline is reached |
| `app-readiness-unexpected-status` | readiness probe returned a non-2xx/non-3xx HTTP status when the monotonic deadline is reached |
| `app-readiness-redirect-refused` | readiness probe returned HTTP 3xx |
| `app-readiness-unattributed` | `nonce` attribution required but body did not contain the launch nonce at deadline |
| `app-process-exited` | child exited before readiness succeeded (and stderr was not a bind conflict) |
| `app-generation-moved` | slot generation changed during stand-up |
| `app-slot-state-not-launchable` | slot lifecycle record is absent or not in `provisioning`/`provisioned` |
| `app-instance-record-invalid` | instance record shape fails validation, including a `stopReceipt` whose `slotRef` does not match the record's `slotRef` |
| `app-instance-record-absent` | `read_instance` — file genuinely does not exist |
| `app-instance-record-unreadable` | instance record cannot be read |
| `app-instance-record-write-failed` | durable instance write or parent fsync failed |
| `app-instance-record-exists` | an active instance record (`starting`/`ready`/`indeterminate`) already exists |
| `app-instance-pid-mismatch` | `stop` corroboration failed — pid does not match recorded `argv[0]` |
| `app-stop-indeterminate` | stop could not observe both process-group gone and endpoint free |
| `app-declaration-unexercised` | `app-lifecycle` declaration has no exercised registry record |
| `app-journal-write-failed` | journal `begin_effect` or `end_effect` failed during stand-up |

## Wave runtime — deadline and teardown

The wave deadline runtime and wave-end teardown live in `lib/pilot_wave.py`. It owns a
launch-anchored monotonic deadline, the durable park latch, per-slot two-phase teardown
(sequential across slots — not a wave-level fence sweep), and the wave report.

**Non-goals:** app-instance control (`pilot_appctl`), automation-server fencing (**C7**, issue #829),
cleanup (**C9**, issue #831), and reclaim (**A2b**, issue #824) — those arrive as injected
handlers.

### Launch-anchored monotonic deadline

`wave_anchor` records `launchedAt` (wall clock, for humans) and `launchedAtMono` (monotonic,
for enforcement). `wave_phase` computes elapsed time from the monotonic anchor only. A
wall-clock deadline is not enough: an NTP correction or manual clock change would move the
terminus of an unattended promise without the framework noticing.

### Wave phases

| Phase | Boundary | Admission |
|---|---|---|
| `wave-running` | `elapsed < deadlineSeconds` | `admit_work` returns `ok: true` |
| `wave-winding-down` | `deadlineSeconds ≤ elapsed < deadlineSeconds + marginSeconds` | new work refused (`ok: false`, `reason: null`) |
| `wave-expired` | `elapsed ≥ deadlineSeconds + marginSeconds` | parked — destructive teardown may proceed behind confirmed fences |

### Durable park latch

`latch_park` writes `park.json` under the per-slot lock **before** any destructive step.
Destructive steps re-read the latch under that same lock immediately before running. The
latch is idempotent — a valid existing latch is returned unchanged.

**Fail-closed unreadable latch:** a latch file that is present but unreadable reads as
**latched**, because a destructive step must never run because it could not read the latch
that would have stopped it.

### Two-phase teardown

**Fence phase** (`app-instance`, `automation-server`): non-destructive; both steps are
attempted regardless of each other's outcome.

**Destructive phase** (`cleanup`, `reclaim`): runs only behind confirmed fences, only on a
`complete` intent, and only with the latch unset. `reclaim` requires `cleanup` confirmed.

The phases are split because halting the whole chain on a failed fence would leave an
authenticated browser driving — the exact harm the fence phase exists to prevent.

`run_teardown` invokes `teardown_slot` **sequentially** — each slot's full fence-then-
destructive chain completes before the next slot starts. On the deadline path this means
earlier slots may be torn down while a later slot's browser is still driving; there is no
wave-level fence pass that halts every slot's browser before any destructive step begins.

### Handler contract

Each step handler returns a three-valued journal outcome:

| Outcome | Step status |
|---|---|
| `applied` | `confirmed` — requires a valid receipt (`step`, `slotRef`, `observedAt`, `evidence`) |
| `not-applied` | `failed` |
| `indeterminate` | `indeterminate` |

A raising handler is **indeterminate**, not failed. An **absent** handler is `unavailable`
(`wave-step-unavailable`), never a skipped step.

Unbuilt handler owners: **C7** (issue #829, `automation-server`), **C9** (issue #831,
`cleanup`), **A2b** (issue #824, `reclaim`).

### Bounded-handler limit

B5 measures a handler's elapsed time on the injected monotonic clock and refuses a late
answer with `wave-step-overran`. It **cannot interrupt** a hung in-process handler, and it
ships no watchdog daemon.

### Teardown steps

| Step | Phase |
|---|---|
| `app-instance` | fence |
| `automation-server` | fence |
| `cleanup` | destructive |
| `reclaim` | destructive |

`STEP_ORDER` equals `FENCE_STEPS + DESTRUCTIVE_STEPS`; the two tuples are disjoint.

### Step statuses

| Status | Meaning |
|---|---|
| `confirmed` | handler returned `applied` with a valid receipt |
| `failed` | handler returned `not-applied` |
| `indeterminate` | handler raised, returned indeterminate, overran, or returned an invalid shape |
| `unavailable` | no handler registered for the step |
| `refused-park` | destructive step refused because intent is `park` or latch is set |
| `not-reached` | destructive step skipped because a fence was not confirmed |

### Teardown intents

| Intent | Meaning |
|---|---|
| `complete` | full teardown — fences then destructive steps when allowed |
| `park` | fence only — destructive steps return `refused-park` |

### Slot dispositions

| Disposition | When |
|---|---|
| `torn-down` | `complete` intent and every step in `STEP_ORDER` is `confirmed` |
| `parked` | `park` intent, both fence steps `confirmed`, both destructive steps `refused-park` |
| `incomplete` | any other outcome |

### Wave report `complete` rule

`wave_report` sets `complete: true` only when every slot disposition is `torn-down` or
`parked` **and** there are no blockers. Any `incomplete` disposition, blocker, or empty
slot list makes `complete` false.

### Wave refusal tokens

| Token | When returned |
|---|---|
| `wave-deadline-invalid` | `deadlineSeconds` is not a non-negative real number |
| `wave-margin-invalid` | `marginSeconds` is not a non-negative real number |
| `wave-clock-invalid` | monotonic clock returned non-finite value, anchor is invalid, or `now_mono < launchedAtMono` |
| `wave-anchor-invalid` | `launchedAt` is not valid ISO-8601 UTC-Z, or anchor construction failed |
| `wave-slot-entry-invalid` | teardown entry is not a mapping, slot/slotRef/intent invalid, slot ≠ parsed slotRef, or `stepTimeoutSeconds` is present but not a non-negative real number |
| `wave-slots-invalid` | `run_teardown` or `wave_report` received a non-mapping or slots list is invalid |
| `wave-step-unavailable` | no handler registered for the step |
| `wave-step-failed` | handler returned `not-applied` |
| `wave-step-indeterminate` | handler raised, returned indeterminate, or cleanup journal begin failed |
| `wave-step-result-invalid` | handler result is not a mapping or outcome is not a known journal outcome |
| `wave-step-receipt-missing` | handler returned `applied` without a valid receipt |
| `wave-step-overran` | handler elapsed time exceeded `stepTimeoutSeconds` |
| `wave-park-destructive-refused` | destructive step refused because intent is `park` or latch is set |
| `wave-park-latch-write-failed` | park latch could not be written or slot lock failed |
| `wave-park-latch-unreadable` | park latch file is present but cannot be read — reads as latched |
| `wave-fence-unconfirmed` | destructive step reached before all fence steps are `confirmed` |
