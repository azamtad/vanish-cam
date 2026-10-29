#!/bin/bash
# Builds VanishCam.app and installs it in your Applications folder.
# Double-click this file once. Afterwards open VanishCam like any other app
# (Launchpad, Spotlight, Dock). Run it again after updating the code.
cd "$(dirname "$0")" || exit 1
SRC="$(pwd)"
SUPPORT="$HOME/Library/Application Support/VanishCam"
VENV="$SUPPORT/venv"
PY="$VENV/bin/python"
export PYTHONDONTWRITEBYTECODE=1

fail() {
  echo
  echo "[Install] $1"
  echo "Press Enter to close."
  read -r _
  exit 1
}

find_python() {
  # MediaPipe 0.10.21 (the version that works on Macs) needs Python 3.9-3.12.
  local v candidate
  for v in 3.12 3.11 3.10 3.9; do
    for candidate in "python$v" "/opt/homebrew/bin/python$v" "/usr/local/bin/python$v" \
                     "/Library/Frameworks/Python.framework/Versions/$v/bin/python3"; do
      if command -v "$candidate" >/dev/null 2>&1; then
        command -v "$candidate"; return 0
      fi
    done
  done
  if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(0 if (3, 9) <= sys.version_info[:2] <= (3, 12) else 1)' 2>/dev/null; then
    command -v python3; return 0
  fi
  return 1
}

echo "=== Installing VanishCam ==="
mkdir -p "$SUPPORT" || fail "Could not create $SUPPORT"

# 1) Python environment (lives in ~/Library/Application Support/VanishCam)
if [ -x "$PY" ] && ! "$PY" -c 'import sys; sys.exit(0 if (3, 9) <= sys.version_info[:2] <= (3, 12) else 1)' 2>/dev/null; then
  rm -rf "$VENV"
fi
if [ ! -x "$PY" ]; then
  PYTHON="$(find_python)" || fail "Python 3.9-3.12 was not found. Install Python 3.12 from https://www.python.org/downloads/macos/ and run this again."
  echo "[1/5] Creating the Python environment with $("$PYTHON" --version 2>&1)..."
  "$PYTHON" -m venv "$VENV" || fail "Could not create the Python environment."
else
  echo "[1/5] Python environment found."
fi
echo "[2/5] Installing components (first time ~1-2 min)..."
"$PY" -m pip install --quiet --upgrade pip || fail "pip upgrade failed."
"$PY" -m pip install --quiet -r requirements.txt certifi || fail "Installing the requirements failed (see above)."
# Optional extras: Dock icon / window focus (PyObjC) and the OBS virtual camera.
"$PY" -m pip install --quiet pyobjc-framework-Cocoa pyobjc-framework-AVFoundation || echo "      (PyObjC could not be installed - the camera permission pop-up may need a second start.)"
"$PY" -m pip install --quiet "pyvirtualcam>=0.15,<1" >/dev/null 2>&1 || true

# 2) Build the app bundle in a temporary folder
echo "[3/5] Building VanishCam.app..."
BUILD_DIR="$(mktemp -d)"
APP="$BUILD_DIR/VanishCam.app"
RES="$APP/Contents/Resources"
mkdir -p "$APP/Contents/MacOS" "$RES/app/assets" || fail "Could not create the app bundle."
for f in vanish_cam.py goku_effect.py naruto_effect.py vanish_sound.py hud.py macos_app.py \
         hand_landmarker.task face_landmarker.task requirements.txt; do
  cp "$f" "$RES/app/" || fail "Missing file: $f"
done
for f in substitution_log.png vanish.MP3 teleport.wav AppIcon.png; do
  cp "assets/$f" "$RES/app/assets/" || fail "Missing file: assets/$f"
done
cp assets/AppIcon.icns "$RES/AppIcon.icns" || fail "Missing file: assets/AppIcon.icns"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>VanishCam</string>
  <key>CFBundleDisplayName</key><string>VanishCam</string>
  <key>CFBundleIdentifier</key><string>io.github.azamtad.vanishcam</string>
  <key>CFBundleExecutable</key><string>VanishCam</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSCameraUsageDescription</key>
  <string>VanishCam uses the camera to make you vanish. Video stays on your Mac and is never recorded or uploaded.</string>
</dict>
</plist>
PLIST

cat > "$RES/launch.sh" <<'LAUNCHER'
#!/bin/bash
# Started by Contents/MacOS/VanishCam: runs the Python app, shows a dialog if it fails.
APP_DIR="$(cd "$(dirname "$0")/app" && pwd)"
SUPPORT="$HOME/Library/Application Support/VanishCam"
PY="$SUPPORT/venv/bin/python"
LOG="$HOME/Library/Logs/VanishCam.log"
mkdir -p "$HOME/Library/Logs"
export VANISHCAM_DATA="$SUPPORT" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

alert() {
  /usr/bin/osascript -e 'on run argv' \
    -e 'set r to display dialog (item 1 of argv) buttons {"Show Log", "OK"} default button "OK" with title "VanishCam" with icon caution' \
    -e 'return button returned of r' -e 'end run' "$1" 2>/dev/null
}

if [ ! -x "$PY" ]; then
  alert "VanishCam is not set up on this Mac yet. Open the VanishCam project folder and double-click \"Install VanishCam.command\"." >/dev/null
  exit 1
fi

cd "$APP_DIR" || exit 1
"$PY" "$APP_DIR/vanish_cam.py" "$@" > "$LOG" 2>&1
STATUS=$?
if [ $STATUS -ne 0 ]; then
  MSG="$(grep -E '\[VanishCam\] ERROR:' "$LOG" | tail -1 | sed 's/.*ERROR: //')"
  [ -z "$MSG" ] && MSG="VanishCam quit unexpectedly (code $STATUS). The log has the details."
  if [ "$(alert "$MSG")" = "Show Log" ]; then
    open -e "$LOG"
  fi
fi
exit 0
LAUNCHER
chmod 755 "$RES/launch.sh"

# The app's main program must be a compiled binary, otherwise macOS never shows
# the camera permission pop-up for it (see launcher.c).
if xcode-select -p >/dev/null 2>&1 && cc -O2 -o "$APP/Contents/MacOS/VanishCam" launcher.c 2>/dev/null; then
  :
else
  echo
  echo "[Install] The Apple developer tools are needed once to build the app."
  echo "          A window will ask to install them - click Install, wait until it's done,"
  echo "          then double-click Install VanishCam.command again."
  xcode-select --install >/dev/null 2>&1
  fail "Developer tools missing."
fi

# 3) Download models + teleport sound now, so the app starts instantly
echo "[4/5] Preparing models and sounds..."
mkdir -p "$SUPPORT/models" "$SUPPORT/assets"
[ -d models ] && cp -n models/* "$SUPPORT/models/" 2>/dev/null
[ -f assets/teleport.mp3 ] && cp -n assets/teleport.mp3 "$SUPPORT/assets/" 2>/dev/null
( cd "$RES/app" && VANISHCAM_DATA="$SUPPORT" "$PY" -c "
import vanish_cam as v
v.download_models()
v.ensure_teleport_sound()
" ) 2>&1 | grep -E "VanishCam|%" || true
ls "$SUPPORT/models/"*.tflite >/dev/null 2>&1 || fail "Could not download the MediaPipe models (check your internet) and run this again."

# Ad-hoc code signature: lets macOS remember the camera permission for the app.
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || echo "      (Could not sign the app - it should still work.)"

# 4) Install
if [ -w /Applications ]; then DEST="/Applications"; else DEST="$HOME/Applications"; mkdir -p "$DEST"; fi
echo "[5/5] Installing to $DEST..."
pkill -f "Resources/app/vanish_cam.py" 2>/dev/null
rm -rf "$DEST/VanishCam.app"
ditto "$APP" "$DEST/VanishCam.app" || fail "Could not copy the app to $DEST."
rm -rf "$BUILD_DIR"
# Refresh the icon cache entry for the new app.
touch "$DEST/VanishCam.app"

echo
echo "=== Done! VanishCam is in $DEST ==="
echo "Open it from Launchpad or Spotlight (Cmd+Space, type VanishCam)."
echo "Tip: drag VanishCam from your Applications folder into the Dock."
echo "macOS will ask once to allow camera access for VanishCam - click OK."
echo
open "$DEST/VanishCam.app"
echo "You can close this window."
