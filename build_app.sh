#!/bin/bash
# Assembles Penumbra.app (a double-clickable Dock app) around penumbra.py.
# No compiler needed. The app runs via PyObjC at runtime.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
# Install into a Launchpad-visible location so it behaves like a normal app.
if [ -w /Applications ]; then DEST=/Applications; else DEST="$HOME/Applications"; mkdir -p "$DEST"; fi
APP="$DEST/Penumbra.app"

echo "Building $APP ..."
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cp "$DIR/Info.plist"    "$APP/Contents/Info.plist"
cp "$DIR/penumbra.py"   "$APP/Contents/Resources/penumbra.py"
[ -f "$DIR/AppIcon.icns" ]     && cp "$DIR/AppIcon.icns"     "$APP/Contents/Resources/AppIcon.icns"
[ -f "$DIR/MenuTemplate.png" ] && cp "$DIR/MenuTemplate.png" "$APP/Contents/Resources/MenuTemplate.png"

# Launcher: find a Python that can import AppKit (PyObjC), then run the app.
cat > "$APP/Contents/MacOS/Penumbra" <<'LAUNCH'
#!/bin/bash
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$(cd "$HERE/.." && pwd)/Resources/penumbra.py"
# Use the first Python 3 that can import AppKit (i.e. has PyObjC installed).
for cand in "$(command -v python3 2>/dev/null)" \
            /opt/homebrew/bin/python3 \
            /usr/local/bin/python3 \
            /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
            /Applications/anaconda3/bin/python3 \
            /usr/bin/python3; do
    [ -n "${cand:-}" ] && [ -x "$cand" ] || continue
    if "$cand" -c 'import AppKit' >/dev/null 2>&1; then
        exec "$cand" "$SCRIPT"
    fi
done
osascript -e 'display alert "Penumbra needs PyObjC" message "No Python with PyObjC (AppKit) was found.\n\nInstall it with:\n    python3 -m pip install pyobjc-framework-Cocoa\n\nthen reopen Penumbra."'
LAUNCH
chmod +x "$APP/Contents/MacOS/Penumbra"

# Ad-hoc sign so it has a stable identity (fewer re-prompts / clean Gatekeeper).
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || echo "  (codesign skipped)"

# Register with LaunchServices so Launchpad and Spotlight pick it up immediately.
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP" 2>/dev/null || true

echo "Installed: $APP"
echo "Launch from Launchpad, Spotlight, or:  open \"$APP\""
