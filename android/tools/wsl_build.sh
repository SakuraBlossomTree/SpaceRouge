#!/usr/bin/env bash
# Builds the SpaceRouge APK inside WSL (Ubuntu). Called by build_apk.bat.
#   $1 = this android/ folder, as a WSL path (e.g. /mnt/c/Users/.../android)
#
# The project is copied to ~/spacerouge-android and built there: building
# directly on the Windows drive (/mnt/c) is very slow and can fail.
set -euo pipefail

SRC="${1:?usage: wsl_build.sh /mnt/c/path/to/android}"
WORK="$HOME/spacerouge-android"
VENV="$HOME/buildozer-env"

echo "=== SpaceRouge Android build ==="

# --- keep Windows programs out of the build ----------------------------------------
# WSL adds every Windows folder (/mnt/c/...) to PATH; the Android build must not
# pick up Windows cmake / perl / python / java / git by mistake.
PATH="$(printf '%s' "$PATH" | tr ':' '\n' | grep -v '^/mnt/' | paste -sd: -)"
export PATH

# --- which Linux is this? ----------------------------------------------------------
if ! command -v apt-get >/dev/null 2>&1; then
    echo "ERROR: this WSL Linux has no apt-get, so it isn't Ubuntu/Debian."
    echo "Install Ubuntu (PowerShell as Administrator):  wsl --install -d Ubuntu"
    exit 1
fi
if [ "$(id -u)" -eq 0 ]; then
    SUDO=""                      # already root (no sudo needed)
elif command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
else
    echo "ERROR: not root and sudo is missing. In PowerShell run:"
    echo "    wsl -d <distro> -u root apt-get install -y sudo"
    exit 1
fi

# --- one-time setup ------------------------------------------------------------
if [ ! -x "$VENV/bin/buildozer" ]; then
    echo "--- First run: installing build tools (asks for your WSL password) ---"
    $SUDO apt-get update
    $SUDO apt-get install -y git zip unzip rsync openjdk-17-jdk python3-pip python3-venv \
        autoconf automake libtool pkg-config zlib1g-dev libncurses-dev cmake \
        libffi-dev libssl-dev build-essential ccache
    $SUDO apt-get install -y libtinfo5 2>/dev/null || $SUDO apt-get install -y libtinfo6 || true
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --upgrade pip setuptools wheel
    "$VENV/bin/pip" install --upgrade buildozer "cython<3.0"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

# --- copy the project into the Linux filesystem ------------------------------------
mkdir -p "$WORK"
rsync -a --delete \
    --exclude .buildozer --exclude bin --exclude __pycache__ \
    --exclude settings.json --exclude save.json --exclude .venv --exclude venv \
    "$SRC/" "$WORK/"

# --- build -----------------------------------------------------------------------------
cd "$WORK"

# If the Python version pin changed since last time, clear the old compiled
# libraries (keeps the downloaded SDK/NDK). Adding a requirement or editing a
# recipe doesn't need this - p4a reuses what's built and builds the rest.
SPEC_HASH="$(grep -oE 'python3==[0-9.]+' buildozer.spec | sort | sha256sum | cut -d' ' -f1)"
if [ -f .last_python ] && [ "$(cat .last_python)" != "$SPEC_HASH" ]; then
    echo "--- Python version changed: cleaning previous build ---"
    buildozer android clean || true
fi
echo "--- Building (the first build downloads the Android SDK/NDK: 30-60 min) ---"
LOG="$SRC/build.log"
echo "--- Full output is also saved to android/build.log ---"
buildozer android debug 2>&1 | tee "$LOG"

echo "$SPEC_HASH" > .last_python

# --- copy the APK back to Windows --------------------------------------------------------
mkdir -p "$SRC/bin"
cp -f bin/*.apk "$SRC/bin/"
echo
echo "=== Done! APK copied to: $SRC/bin ==="
ls -1 "$SRC/bin"/*.apk
