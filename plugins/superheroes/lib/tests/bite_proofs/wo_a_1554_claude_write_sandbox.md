# WO-A #1554 bite-proofs: the claude write channel's sandboxed shell

Each row: guarded element, the neutralization (one targeted edit, reverted by the inverse edit),
the detector run alone (`-p no:xdist`, single node), its red result, and the restore. All eight
restores were verified by the post-restore green run of the new file and the touched suites (1686
passed; the one failure, `test_native_write_timeout_with_blank_report_forfeits_with_admission_detail`,
is a codex timeout test that passed alone twice on the same head).

| # | Guarded element | Neutralization | Detector (red) | Red result |
|---|---|---|---|---|
| 1 | `--restricted` in the claude write argv | `engine_adapter.py` write branch: `"--permission-mode", "acceptEdits", "--restricted",` became `"--permission-mode", "acceptEdits",` | `test_claude_write_exact_argv` | `At index 11 diff: '--tools' != '--restricted'` |
| 2 | `"allowUnsandboxedCommands": False` | set to `True` | `test_settings_json_keys` | `'allowUnsandboxedCommands': True ... != ... 'allowUnsandboxedCommands': False` |
| 3 | `"failIfUnavailable": True` | key line deleted | `test_settings_json_keys` | sandbox dict lacks `failIfUnavailable` (assert dict mismatch) |
| 4 | `network.allowedDomains == []` plus `strictAllowlist` | `"strictAllowlist": True` became `False` | `test_settings_json_keys` | sandbox dict mismatch (network differs) |
| 5 | `denyWrite` of the common hooks | resolver: dropped `os.path.join(git_common_dir, "hooks"),` | `test_resolver_linked_worktree_roots_and_denies` | `At index 0 diff: '.../main/.git/config' != '.../main/.git/hooks'` |
| 6 | `sandbox-process-listing-unavailable` refusal | adapter: `if opts.get("requiresProcessListing") is True:` became `if False and opts.get(...) is True:` (disables the check; same effect as deleting it) | `test_requires_process_listing_refuses_claude_write_only` | `assert None == 'sandbox-process-listing-unavailable'` (reason `None`) |
| 7 | `sandbox-roots-missing` | adapter: on a missing dict, fall back to `{"writeRoots":[cwd or "/"],"denyWrite":[],"uvCacheDir":None}` before the validity check | `test_claude_write_without_sandbox_refuses_roots_missing` | `assert None == 'sandbox-roots-missing'` for opts `{}` |
| 8 | Continuation uses the journaled sandbox | dispatcher: on `opened is not None`, re-resolve with `_resolve_claude_write_sandbox` instead of `opened.get("claudeWriteSandbox")` | `test_continuation_uses_journaled_sandbox_not_environment` | `a continuation re-resolved the sandbox` / `assert 2 == 1` |

Restored lines (inverse edits, quoted from the final files):

- 1: `engine_adapter.py:619  "--permission-mode", "acceptEdits", "--restricted",`
- 2/3/4: `engine_adapter.py:262-265  "failIfUnavailable": True, ... "allowUnsandboxedCommands": False, "network": {"allowedDomains": [], "strictAllowlist": True},`
- 5: `engine_dispatch.py:1693  os.path.join(git_common_dir, "hooks"),`
- 6: `engine_adapter.py:578  if opts.get("requiresProcessListing") is True:`
- 7: `engine_adapter.py:584  if not claude_write_sandbox_valid(opts.get("claudeWriteSandbox")):` (preceded by the process-listing check only)
- 8: `engine_dispatch.py:6274  claude_write_sandbox = opened.get("claudeWriteSandbox")`
