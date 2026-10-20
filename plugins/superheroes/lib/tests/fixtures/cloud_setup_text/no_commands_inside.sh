#!/bin/bash
# Corner Shop · plugin @VERSION@ · calibration in the repository
# Setup text for a cloud environment: paste it over the whole setup-script field.
# It holds no reviewer pass and no other secret.
LOG="$HOME/superheroes-cloud-setup.log"
SRC="/opt/fixture/src"
LINK="/opt/fixture/plugin"
CLONE="corner-shop"

# Fetch the plugin at the commit the owner's machine runs.
(
  rm -rf "$SRC" && mkdir -p "$SRC" && cd "$SRC" && git init -q . \
    && git fetch -q --depth 1 "https://github.com/acme/superheroes.git" 0123456789abcdef0123456789abcdef01234567 \
    && git checkout -q --detach FETCH_HEAD && mkdir -p "/opt/fixture" \
    && ln -sfn "$SRC/plugins/superheroes" "$LINK" \
    && echo "plugin ok $(cat "$SRC/plugins/superheroes/version.txt")" || echo "plugin FAILED"
) >> "$LOG" 2>&1 &

# Install the reviewer tool and the duplication checker.
(
  npm install -g "@openai/codex" && echo "reviewer cli ok" || echo "reviewer cli FAILED"
  npm install -g "jscpd@5.0.12" && echo "duplication checker ok" || echo "duplication checker FAILED"
) >> "$LOG" 2>&1 &

# Install the two packages the write sandbox needs.
(
  apt-get install -y bubblewrap socat || { apt-get update && apt-get install -y bubblewrap socat; } \
    && echo "sandbox tools ok" || echo "sandbox tools FAILED"
) >> "$LOG" 2>&1 &

# Install the project's pinned Python, when it has a .python-version file: in the working
# directory, or in the clone beside it. uv reads the file itself, from that directory, with
# UV_PYTHON cleared so an inherited value cannot override it.
(
  DIR=""
  if [ -f "$PWD/.python-version" ]; then DIR="$PWD"
  elif [ -f "$PWD/$CLONE/.python-version" ]; then DIR="$PWD/$CLONE"
  fi
  if [ -z "$DIR" ]; then
    echo "pinned python: no .python-version in $PWD or $PWD/$CLONE"
  else
    if grep -qvE '^[[:space:]]*(#|$)' "$DIR/.python-version" && (cd "$DIR" && env -u UV_PYTHON uv python install); then echo "pinned python ok"
    else echo "pinned python FAILED"; fi
  fi
) >> "$LOG" 2>&1 &
wait

# The project's own tool steps, if any, go below this line.
echo "setup end" >> "$LOG"
exit 0
