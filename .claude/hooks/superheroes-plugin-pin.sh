#!/bin/bash
# Written by superheroes, which rewrites or removes it. Do not edit by hand.
# In a cloud session it installs the superheroes plugin at the commit named in the pin file
# when the installed plugin is not at that commit and version. Every failure it handles ends in
# exit 0 with a one-line notice; a hook that cannot start, or that the session's hook timeout
# cancels, is reported by the session itself.
set +e +u
LINK=/opt/superheroes/plugin
SRC_DIR=/opt/superheroes/plugin-src
PIN=.claude/superheroes-plugin-pin

if [ "${CLAUDE_CODE_REMOTE-}" != "true" ]; then
  exit 0
fi
export LC_ALL=C GIT_TERMINAL_PROMPT=0
cd "$(dirname "$0")/../.." 2>/dev/null || exit 0

# The log lives inside .git. Command output goes there; the session sees only this script's
# one-line notices.
LOG=$(git rev-parse --git-path superheroes-plugin-pin.log 2>/dev/null) && [ -n "$LOG" ] || LOG=/dev/null

INSTALLED=$(git -C "$LINK/" rev-parse HEAD 2>/dev/null) || INSTALLED=""
skip() {
  echo "superheroes: plugin pin not applied: $1; this session runs the plugin already installed (${INSTALLED:-none})."
  exit 0
}
# The first line of a file, also when it has no final newline; empty when it cannot be read.
first_line() {
  local v=""
  { IFS= read -r v < "$1"; } 2>/dev/null
  printf '%s' "$v"
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
done < "$PIN" 2>/dev/null
for key in source commit subdir version; do
  case "$SEEN" in *" $key "*) ;; *) skip "the pin file has no $key" ;; esac
done

# axis: a session already at the pinned commit and version fetches nothing
if [ "$INSTALLED" = "$COMMIT" ] && [ "$(first_line "$LINK/version.txt")" = "$VERSION" ]; then
  exit 0
fi

# The pinned tree is fetched into a new directory of its own, beside the setup text's, so two
# sessions fetching at once never share or delete a tree; it is linked only once its commit and
# version are the pin's. The fetch and the checkout are each bounded where timeout exists.
TIMEOUT=""
command -v timeout >/dev/null 2>&1 && TIMEOUT="timeout 120"
DEST=""
drop() {
  [ -n "$DEST" ] && rm -rf "$DEST" >>"$LOG" 2>&1
  skip "$1"
}
if ! {
  mkdir -p "$(dirname "$SRC_DIR")" && DEST=$(mktemp -d "$SRC_DIR-$COMMIT.XXXXXX") \
    && (cd "$DEST" && git init -q \
      && $TIMEOUT git fetch -q --depth 1 "$SOURCE" "$COMMIT" \
      && $TIMEOUT git checkout -q --detach FETCH_HEAD)
} >>"$LOG" 2>&1; then
  drop "the pinned commit could not be fetched"
fi

GOT=$(git -C "$DEST" rev-parse HEAD 2>/dev/null) || GOT=""
[ "$GOT" = "$COMMIT" ] || drop "the fetched plugin is not at the pinned commit"
GOT_VERSION=$(first_line "$DEST/$SUBDIR/version.txt")
[ "$GOT_VERSION" = "$VERSION" ] || drop "the fetched plugin is version ${GOT_VERSION:-unknown}, not the pinned $VERSION"

# The link is replaced only by renaming a new link over it, so it is never absent: mv -T (GNU and
# GNU-compatible mv) and mv -h (BSD mv) each rename onto the link itself rather than into the
# folder it points to. Each form is tried by what this mv accepts, never by its name; a mv that
# takes neither leaves the old link in place.
TMPLINK="$LINK.pin-tmp.$$"
swap() {
  mkdir -p "$(dirname "$LINK")" && ln -sfn "$DEST/$SUBDIR" "$TMPLINK" || return 1
  mv -Tf "$TMPLINK" "$LINK" || mv -fh "$TMPLINK" "$LINK"
}
swap >>"$LOG" 2>&1 || { rm -f "$TMPLINK" >>"$LOG" 2>&1; drop "the plugin link could not be replaced"; }
echo "superheroes: plugin $VERSION installed at the pinned commit ${COMMIT:0:12}."
exit 0
