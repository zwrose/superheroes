// A test fixture, not shipped logic: the manifest's `userConfig` (plugin.json is the one
// home of the settings' defaults and bounds). A test body cannot read files, so the tests
// take the schema from here; lib/tests/test_user_config_fixture_1814.py fails when it drifts.
export const USER_CONFIG = {
  "autoCheckpointTokens": {
    "type": "number",
    "title": "Auto-checkpoint threshold (tokens)",
    "description": "Context size at which the session saves its checkpoint notes and compacts itself.",
    "default": 500000,
    "min": 50000,
    "max": 2000000
  },
  "autoCheckpointAllowance": {
    "type": "number",
    "title": "Auto-checkpoint allowance (tokens)",
    "description": "How many tokens before the harness's own auto-compaction the checkpoint must land.",
    "default": 120000,
    "min": 0,
    "max": 1000000
  },
  "autoCheckpointMode": {
    "type": "string",
    "title": "Auto-checkpoint mode",
    "description": "auto: checkpoint and compact on its own; click-only: only when you press Now on the band; off: never.",
    "default": "auto",
    "options": [
      "auto",
      "click-only",
      "off"
    ]
  }
}
