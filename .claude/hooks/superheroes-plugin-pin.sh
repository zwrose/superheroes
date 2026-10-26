#!/bin/bash
# Written by superheroes, which rewrites or removes it. Do not edit by hand.
# In a cloud session it installs the superheroes plugin at the commit named in the pin file
# when the installed plugin is at a different commit. It never fails the session.
LINK=/opt/superheroes/plugin
SRC_DIR=/opt/superheroes/plugin-src
PIN=.claude/superheroes-plugin-pin

if [ "${CLAUDE_CODE_REMOTE-}" != "true" ]; then
  exit 0
fi
export LC_ALL=C GIT_TERMINAL_PROMPT=0
cd "$(dirname "$0")/../.." 2>/dev/null || exit 0

# The log lives inside .git; command output goes there, never to the session.
LOG=$(git rev-parse --git-path superheroes-plugin-pin.log 2>/dev/null) && [ -n "$LOG" ] || LOG=/dev/null

INSTALLED=$(git -C "$LINK/" rev-parse HEAD 2>/dev/null) || INSTALLED=""
skip() {
  echo "superheroes: plugin pin not applied: $1; this session runs the plugin already installed (${INSTALLED:-none})."
  exit 0
}

# The pin is read with the same strict rules as the Python reader: every line is blank, a
# comment or key=value, and each of the four keys appears exactly once with a plain value.
SOURCE_RE='^https://[A-Za-z0-9][A-Za-z0-9._~:/-]*$'
PATH_RE='^[A-Za-z0-9._/-]+$'
COMMIT_RE='^[0-9a-f]{40}$'
VERSION_RE='^[0-9]+\.[0-9]+\.[0-9]+$'
[ -f "$PIN" ] || skip "the pin file is missing"
SEEN=' '
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in ''|'#'*) continue ;; esac
  [[ "$line" =~ ^([a-z]+)=(.*)$ ]] || skip "the pin file has a line that is not key=value"
  key=${BASH_REMATCH[1]}; value=${BASH_REMATCH[2]}
  case "$SEEN" in *" $key "*) skip "the pin file repeats $key" ;; esac
  SEEN="$SEEN$key "
  case "$key" in
    source) [[ "$value" =~ $SOURCE_RE ]] || skip "the pin source is not an https address"
      SOURCE=$value ;;
    commit) [[ "$value" =~ $COMMIT_RE ]] || skip "the pin commit is not a full lowercase sha"
      COMMIT=$value ;;
    subdir) [[ "$value" =~ $PATH_RE && "$value" != /* && "/$value/" != */../* ]] \
        || skip "the pin subdir is not a plain relative path"
      SUBDIR=$value ;;
    version) [[ "$value" =~ $VERSION_RE ]] || skip "the pin version is not x.y.z"
      VERSION=$value ;;
    *) skip "the pin file has an unknown key" ;;
  esac
done < "$PIN"
for key in source commit subdir version; do
  case "$SEEN" in *" $key "*) ;; *) skip "the pin file has no $key" ;; esac
done

# axis: a session already at the pinned commit fetches nothing
if [ "$INSTALLED" = "$COMMIT" ]; then
  exit 0
fi

# The pinned tree is fetched into its own directory, beside the setup text's, and only swapped
# in once its commit and version are the pin's.
DEST="$SRC_DIR-$COMMIT"
TIMEOUT=""
command -v timeout >/dev/null 2>&1 && TIMEOUT="timeout 120"
if [ ! -f "$DEST/$SUBDIR/version.txt" ]; then
  TMP="$DEST.tmp.$$"
  rm -rf "$TMP"
  if ! {
    mkdir -p "$TMP" && (cd "$TMP" && git init -q \
      && $TIMEOUT git fetch -q --depth 1 "$SOURCE" "$COMMIT" \
      && git checkout -q --detach FETCH_HEAD) \
      && rm -rf "$DEST" && mv "$TMP" "$DEST"
  } >>"$LOG" 2>&1; then
    rm -rf "$TMP"
    skip "the pinned commit could not be fetched"
  fi
fi

GOT=$(git -C "$DEST" rev-parse HEAD 2>/dev/null) || GOT=""
[ "$GOT" = "$COMMIT" ] || skip "the fetched plugin is not at the pinned commit"
GOT_VERSION=""
[ -f "$DEST/$SUBDIR/version.txt" ] && read -r GOT_VERSION < "$DEST/$SUBDIR/version.txt"
[ "$GOT_VERSION" = "$VERSION" ] || skip "the fetched plugin is version ${GOT_VERSION:-unknown}, not the pinned $VERSION"

# GNU mv -T replaces the link atomically; BSD mv has no -T, so there the link is replaced in
# place.
TMPLINK="$LINK.pin-tmp.$$"
swap() {
  mkdir -p "$(dirname "$LINK")" && ln -sfn "$DEST/$SUBDIR" "$TMPLINK" || return 1
  case "$(mv --version 2>/dev/null)" in
    *"GNU coreutils"*) mv -Tf "$TMPLINK" "$LINK" ;;
    *) rm -f "$TMPLINK" && ln -sfn "$DEST/$SUBDIR" "$LINK" ;;
  esac
}
swap >>"$LOG" 2>&1 || { rm -f "$TMPLINK"; skip "the plugin link could not be replaced"; }
echo "superheroes: plugin $VERSION installed at the pinned commit ${COMMIT:0:12}."
exit 0
