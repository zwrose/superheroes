# test-pilot profile — {{project-name}}

<!-- provenance: plugin-version={{plugin-version}} profile-version=1
     status={{status}} created={{date}} updated={{date}} -->

This profile is a CLAUDE.md-aware ADDER: it carries only what the project's
CLAUDE.md does not already state. Conventions live in CLAUDE.md.

## App launch

- Dev command: `{{dev-command}}`
- Base URL: {{base-url}}
- Readiness probe: GET {{readiness-url}} → expect HTTP {{readiness-status}}
- May test-pilot start/stop the server: {{yes/no}}

> Per-worktree PORT: if the launch worktree carries a `.env.local` with a
> `PORT=<N>` line, test-pilot honors it automatically — the resolved port,
> base URL, and readiness probe follow that value (what the dev server will
> actually bind) instead of the base URL above, and the resolved port is
> disclosed in the phase record. No per-worktree edit to this profile needed.

## Auth strategy

{{One of: test-user credentials (env var NAMES only, never secrets) /
auth bypass mechanism / "requires the user's real browser session"
(forces Claude in Chrome). Describe exactly how execute gets a signed-in
session.}}

## Seed surfaces

Blocks may touch ONLY these surfaces:

- DB: connection from env var `{{DB_ENV_VAR}}` (name only — never the value)
- HTTP API: {{api-base}}
- Project CLI: {{seed-related npm/make scripts, if any}}

Protected targets (the engine's enforced gate REFUSES writes matching these
patterns — see the config block below): {{describe what is protected and why}}

## Browser tool order

{{e.g. chrome-devtools, claude-in-chrome — first available wins}}

## Machine-readable config

The engine parses ONLY this block; keep it in sync with the prose above.

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
  "mayManageServer": true
}
```

## Pilot framework (optional)

The `pilot` key is optional. Add it to the live `test-pilot-config` block above only once
the owner has answered every field — `effectsEscape`, the mint envelope, and expected pilot
identities have no defaults; an unanswered declaration is absent and absent refuses.

`mint` is required when `signInPath` is `"minted"` and may also be declared on the `"attended"`
path (the example below shows both); it is optional on the attended path.

Copy the example below **only** once every field is owner-answered. Field definitions,
refusal tokens, and the probe vocabulary live in
[`reference/pilot-contract.md`](../reference/pilot-contract.md).

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
