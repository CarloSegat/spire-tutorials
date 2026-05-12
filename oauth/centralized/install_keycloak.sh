#!/usr/bin/env bash
set -euo pipefail

VERSION="${KC_VERSION:-26.0.7}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEST="$PROJECT_ROOT/artefacts/keycloak"

mkdir -p "$PROJECT_ROOT/artefacts"

if [[ -x "$DEST/bin/kc.sh" ]]; then
  echo "keycloak already installed at $DEST"
  exit 0
fi

TARBALL="keycloak-$VERSION.tar.gz"
URL="https://github.com/keycloak/keycloak/releases/download/$VERSION/$TARBALL"
TMP="$(mktemp -d)"
trap "rm -rf $TMP" EXIT

echo "downloading $URL"
curl -L -o "$TMP/$TARBALL" "$URL"
tar -xzf "$TMP/$TARBALL" -C "$TMP"
rm -rf "$DEST"
mv "$TMP/keycloak-$VERSION" "$DEST"
echo "installed keycloak $VERSION at $DEST"
