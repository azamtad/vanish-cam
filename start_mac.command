#!/bin/bash
# VanishCam launcher for macOS. Double-click it in Finder, or run:
#   ./start_mac.command               (shows the effect menu)
#   ./start_mac.command --mode goku   (straight to Goku Instant Transmission)
#   ./start_mac.command --list-cameras
cd "$(dirname "$0")" || exit 1

VENV_DIR=".venv-mac"
VENV_PY="$VENV_DIR/bin/python"
ARCH="$(uname -m)"

fail() {
  echo
  echo "[VanishCam] $1"
  echo "Press Enter to close."
  read -r _
  exit 1
}

find_python() {
  local versions
  # MediaPipe 0.10.21 (the version that works on Macs) needs Python 3.9-3.12.
  versions="3.12 3.11 3.10 3.9"
  local dirs="/opt/homebrew/bin /usr/local/bin"
  for v in $versions; do
    for candidate in "python$v" $(for d in $dirs; do echo "$d/python$v"; done) \
                     "/Library/Frameworks/Python.framework/Versions/$v/bin/python3"; do
      if command -v "$candidate" >/dev/null 2>&1; then
        echo "$(command -v "$candidate")"; return 0
      fi
    done
  done
  # Last resort: whatever python3 is (Apple's /usr/bin/python3 is 3.9).
  if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(0 if (3, 9) <= sys.version_info[:2] <= (3, 12) else 1)' 2>/dev/null; then
    echo "$(command -v python3)"; return 0
  fi
  return 1
}

REQ_HASH="$(shasum requirements.txt | cut -d' ' -f1)"
# Rebuild the environment from scratch if requirements.txt changed or it was
# made with an unsupported Python (3.13+). Avoids half-upgraded packages.
if [ -d "$VENV_DIR" ]; then
  if [ "$(cat "$VENV_DIR/.requirements-hash" 2>/dev/null)" != "$REQ_HASH" ] || \
     ! "$VENV_PY" -c 'import sys; sys.exit(0 if (3, 9) <= sys.version_info[:2] <= (3, 12) else 1)' 2>/dev/null; then
    echo "[VanishCam] Rebuilding the Python environment (requirements changed)..."
    rm -rf "$VENV_DIR"
  fi
fi

if [ ! -x "$VENV_PY" ]; then
  PYTHON="$(find_python)" || fail "Python 3.9-3.12 was not found (3.13+ is not supported by MediaPipe on Mac). Install Python 3.12 from https://www.python.org/downloads/macos/ or with Homebrew: brew install python@3.12 - then double-click this file again."
  echo "[VanishCam] Creating a local Python environment with $PYTHON ($("$PYTHON" --version 2>&1))..."
  "$PYTHON" -m venv "$VENV_DIR" || fail "Could not create the Python environment."
fi

if [ "$(cat "$VENV_DIR/.requirements-hash" 2>/dev/null)" != "$REQ_HASH" ] || \
   ! "$VENV_PY" -c "import cv2, mediapipe, numpy" >/dev/null 2>&1; then
  echo "[VanishCam] Installing components (internet needed only this first time, ~1-2 min)..."
  "$VENV_PY" -m pip install --upgrade pip || fail "pip upgrade failed."
  "$VENV_PY" -m pip install -r requirements.txt certifi || fail "Installing the requirements failed (see messages above)."
  # Optional: virtual camera for Zoom/Meet/Discord via OBS. Not required.
  "$VENV_PY" -m pip install "pyvirtualcam>=0.15,<1" >/dev/null 2>&1 || \
    echo "[VanishCam] (Optional virtual-camera package not available - preview window still works.)"
  echo "$REQ_HASH" > "$VENV_DIR/.requirements-hash"
fi

echo "[VanishCam] Starting the webcam..."
echo "[VanishCam] (First time: macOS asks to allow camera access for Terminal - click OK.)"
"$VENV_PY" vanish_cam.py "$@"
STATUS=$?
if [ $STATUS -ne 0 ]; then
  fail "VanishCam stopped with an error (see above)."
fi
exit 0
