#!/bin/bash
# Builds Penumbra.app from Sources/main.swift, no Xcode project needed.
set -euo pipefail

APP="Penumbra"
DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="$DIR/build/$APP.app"
CONTENTS="$OUT/Contents"

# Guard: CLT 16.4 ships a stale duplicate modulemap that breaks EVERY Swift+Cocoa
# compile ("redefinition of module 'SwiftBridging'"). Detect it and print the fix.
STALE="/Library/Developer/CommandLineTools/usr/include/swift/module.modulemap"
BRIDGE="/Library/Developer/CommandLineTools/usr/include/swift/bridging.modulemap"
if [ -f "$STALE" ] && [ -f "$BRIDGE" ]; then
    echo "!! Command Line Tools bug detected: a stale duplicate modulemap makes every"
    echo "   Swift+Cocoa build fail (redefinition of module 'SwiftBridging')."
    echo "   The file below is an orphaned 2023 duplicate of bridging.modulemap."
    echo ""
    echo "   One-time fix (safe + reversible):"
    echo "       sudo mv \"$STALE\" \"$STALE.disabled\""
    echo ""
    echo "   Then re-run ./build.sh.  (No compiler needed for the app itself,"
    echo "   ./build_app.sh builds the ready-to-run Python version.)"
    exit 1
fi

echo "Cleaning..."
rm -rf "$DIR/build"
mkdir -p "$CONTENTS/MacOS" "$CONTENTS/Resources"

echo "Compiling..."
swiftc -O -swift-version 5 \
    -o "$CONTENTS/MacOS/$APP" \
    "$DIR/Sources/main.swift" \
    -framework Cocoa -framework ServiceManagement

cp "$DIR/Info.plist" "$CONTENTS/Info.plist"

echo "Ad-hoc code-signing (stable identity for Launch-at-Login)..."
codesign --force --sign - --identifier com.molanocortes.penumbra "$OUT" >/dev/null 2>&1 || \
    echo "  (codesign skipped, app still runs)"

echo ""
echo "Built: $OUT"
echo "Run it:  open \"$OUT\""
