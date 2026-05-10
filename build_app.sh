#!/usr/bin/env bash
# Builds EbookReader.app and packages it as EbookReader.zip
# Run once on a Mac with Python 3.9+ available.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="EbookReader"
APP_DIR="$SCRIPT_DIR/$APP_NAME.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

echo "Building $APP_NAME.app …"

# ── Clean previous build ───────────────────────────────────────────────────────
rm -rf "$APP_DIR"

# ── Create bundle skeleton ─────────────────────────────────────────────────────
mkdir -p "$MACOS" "$RESOURCES"

# ── Copy app source files ──────────────────────────────────────────────────────
cp "$SCRIPT_DIR/ebook_reader.py"  "$RESOURCES/"
cp "$SCRIPT_DIR/requirements.txt" "$RESOURCES/"

# ── Write the launcher executable ─────────────────────────────────────────────
cat > "$MACOS/$APP_NAME" <<'LAUNCHER'
#!/usr/bin/env bash
# This script runs inside the .app bundle.
BUNDLE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESOURCES="$BUNDLE/Resources"
VENV="$RESOURCES/.venv"

find_python() {
    for c in python3 python3.12 python3.11 python3.10 python3.9; do
        if command -v "$c" &>/dev/null; then
            if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' 2>/dev/null; then
                echo "$c"; return 0
            fi
        fi
    done
    return 1
}

PYTHON="$(find_python)" || {
    osascript -e 'display dialog "Ebook Reader requires Python 3.9 or later.\n\nInstall from python.org or run:\n  brew install python3" buttons {"OK"} default button "OK" with icon stop' 2>/dev/null || true
    exit 1
}

if [ ! -d "$VENV" ]; then
    "$PYTHON" -m venv "$VENV"
    "$VENV/bin/pip" install --quiet --upgrade pip
    "$VENV/bin/pip" install --quiet -r "$RESOURCES/requirements.txt"
fi

exec "$VENV/bin/python" "$RESOURCES/ebook_reader.py" "$@"
LAUNCHER

chmod +x "$MACOS/$APP_NAME"

# ── Write Info.plist ───────────────────────────────────────────────────────────
cat > "$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>EbookReader</string>
    <key>CFBundleDisplayName</key>
    <string>Ebook Reader</string>
    <key>CFBundleIdentifier</key>
    <string>com.ebookreader.app</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>EbookReader</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeName</key>
            <string>EPUB Ebook</string>
            <key>CFBundleTypeExtensions</key>
            <array><string>epub</string></array>
            <key>CFBundleTypeRole</key>
            <string>Viewer</string>
        </dict>
        <dict>
            <key>CFBundleTypeName</key>
            <string>PDF Document</string>
            <key>CFBundleTypeExtensions</key>
            <array><string>pdf</string></array>
            <key>CFBundleTypeRole</key>
            <string>Viewer</string>
        </dict>
    </array>
</dict>
</plist>
PLIST

echo "App bundle created: $APP_DIR"

# ── Package as zip ─────────────────────────────────────────────────────────────
ZIP="$SCRIPT_DIR/$APP_NAME.zip"
rm -f "$ZIP"
cd "$SCRIPT_DIR"
zip -r "$ZIP" "$APP_NAME.app" --exclude "*.DS_Store" --exclude "*/__pycache__/*"

echo ""
echo "✅  Done!  Output: $ZIP"
echo ""
echo "To install:"
echo "  1. Unzip $APP_NAME.zip"
echo "  2. Move EbookReader.app to your Applications folder"
echo "  3. Right-click → Open (first launch only, to bypass Gatekeeper)"
echo ""
echo "On first launch the app will install Python libraries automatically."
