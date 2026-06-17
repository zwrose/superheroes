#!/usr/bin/env bash
# dev-reinstall.sh — refresh the locally-installed superheroes plugins from this
# worktree, so a fresh Claude Code session picks up your latest committed changes.
#
# Why this exists: the `superheroes` marketplace is a local `directory` source that
# Claude Code COPIES into its plugin cache at install time. `claude plugin update`
# only re-copies when plugin.json's `version` changes — but we pin versions for
# releases, so between releases an `update` is a no-op. Uninstall + reinstall forces
# a fresh copy regardless of version. The marketplace registration itself is left
# untouched — you never repeat the one-time `claude plugin marketplace add`.
#
# Usage:
#   scripts/dev-reinstall.sh                      # refresh all band plugins
#   scripts/dev-reinstall.sh review-crew          # refresh just one (or several)
#
# After it finishes, START A FRESH `claude` SESSION in your target project — plugin
# changes apply on session start, not mid-session.

set -uo pipefail

MARKETPLACE="superheroes"
KNOWN="$HOME/.claude/plugins/known_marketplaces.json"

if [ "$#" -gt 0 ]; then
  PLUGINS=("$@")
else
  PLUGINS=(the-architect review-crew test-pilot)
fi

command -v claude >/dev/null 2>&1 || { echo "error: 'claude' CLI not on PATH" >&2; exit 1; }

# The marketplace must already be registered (the one-time setup). If it isn't,
# point the user at the add command rather than guessing a path.
if ! grep -q "\"$MARKETPLACE\"" "$KNOWN" 2>/dev/null; then
  here="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
  echo "error: marketplace '$MARKETPLACE' is not registered." >&2
  echo "  one-time setup:  claude plugin marketplace add \"$here\"" >&2
  exit 1
fi

echo "Refreshing from '$MARKETPLACE': ${PLUGINS[*]}"
for p in "${PLUGINS[@]}"; do
  echo "→ $p"
  # Uninstall may legitimately fail if the plugin isn't installed yet — keep going.
  claude plugin uninstall "$p@$MARKETPLACE" -y >/dev/null 2>&1 || true
  claude plugin install "$p@$MARKETPLACE"
done

echo
echo "✓ Done. Start a FRESH 'claude' session in your target project to load the new code"
echo "  (plugin changes apply on session start, not mid-session)."
