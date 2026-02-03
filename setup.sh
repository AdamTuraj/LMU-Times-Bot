#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------
# Project setup script
#
# Generates:
#   ./Backend/.env
#   ./Discord Bot/.env
#   ./Recorder/.env
#
# Builds Recorder (PyInstaller) and moves exe to ./out
# ------------------------------------------------------------

# ---------- Helpers ----------
prompt() {
  # usage: prompt "Label" "default" -> echoes result
  local label="$1"
  local def="${2:-}"
  local val=""
  if [[ -n "$def" ]]; then
    read -r -p "${label} [${def}]: " val
    val="${val:-$def}"
  else
    read -r -p "${label}: " val
    while [[ -z "$val" ]]; do
      read -r -p "${label} (required): " val
    done
  fi
  echo "$val"
}

require_dir() {
  local d="$1"
  if [[ ! -d "$d" ]]; then
    echo "ERROR: Expected directory not found: $d"
    echo "Run this script from the project root (the folder containing Backend / Discord Bot / Recorder)."
    exit 1
  fi
}

pick_python() {
  # Prefer python3, fallback to python
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
  elif command -v python >/dev/null 2>&1; then
    echo "python"
  else
    echo "ERROR: Python not found (python3/python). Install Python first." >&2
    exit 1
  fi
}

install_venv_support_if_needed() {
  # On Debian/Ubuntu minimal installs, python -m venv can fail with:
  # "ensurepip is not available" -> needs python3-venv (or pythonX.Y-venv).
  #
  # We'll detect by trying to import ensurepip, and if missing, try apt install.
  local py="$1"

  if "$py" -c "import ensurepip" >/dev/null 2>&1; then
    return 0
  fi

  echo "Venv/ensurepip appears to be missing. Attempting to install venv support (Debian/Ubuntu)..."

  if ! command -v apt-get >/dev/null 2>&1; then
    echo "ERROR: apt-get not found, so I can't auto-install python venv support."
    echo "Install your Python venv package manually (e.g., python3-venv or python3.X-venv) and re-run."
    exit 1
  fi

  # Try to figure out python version like 3.12 -> python3.12-venv
  local ver=""
  ver="$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")"

  # Try a few common package names.
  # We do NOT prompt; we just attempt. If it fails, we show what to run.
  set +e
  sudo apt-get update
  sudo apt-get install -y "python${ver}-venv"
  local rc=$?
  if [[ $rc -ne 0 ]]; then
    echo "Could not install python${ver}-venv; trying python3-venv..."
    sudo apt-get install -y python3-venv
    rc=$?
  fi
  set -e

  if [[ $rc -ne 0 ]]; then
    echo "ERROR: Automatic install failed."
    echo "Try manually:"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install -y python${ver}-venv"
    echo "or:"
    echo "  sudo apt-get install -y python3-venv"
    exit 1
  fi

  echo "Installed venv support successfully."
}

activate_venv() {
  # shellcheck disable=SC1091
  if [[ -f ".venv/bin/activate" ]]; then
    source ".venv/bin/activate"
  else
    source ".venv/Scripts/activate"
  fi
}

venv_install_requirements() {
  local folder="$1"
  local py="$2"

  echo "---- [${folder}] Creating virtualenv + installing requirements ----"
  ( cd "$folder"
    "$py" -m venv .venv
    activate_venv

    python -m pip install --upgrade pip

    if [[ -f "requirements.txt" ]]; then
      pip install -r "requirements.txt"
    else
      echo "WARNING: No requirements.txt found in ${folder}. Skipping pip install."
    fi
  )
}

# ---------- Writers (DO NOT CHANGE VARIABLE NAMES) ----------
write_env_backend() {
  local outpath="$1"
  cat > "$outpath" <<EOF
# Server Configuration
DEBUG=${DEBUG}
PORT=${PORT}
HOST=${HOST}

# Discord OAuth2 Configuration
DISCORD_CLIENT_ID=${DISCORD_CLIENT_ID}
DISCORD_CLIENT_SECRET=${DISCORD_CLIENT_SECRET}
DISCORD_CALLBACK_URL=${DISCORD_CALLBACK_URL}
HOME_GUILD_ID=${HOME_GUILD_ID}

# Callback URL
APPLICATION_CALLBACK=${APPLICATION_CALLBACK}

# Database Path
DATABASE_PATH="${DATABASE_PATH}"
EOF
}

write_env_discord_bot() {
  local outpath="$1"
  cat > "$outpath" <<EOF
# Discord Bot Token
TOKEN="${TOKEN}"

# Server to enable slash commands in
GUILD_ID=${GUILD_ID}

# Owner ID
OWNER_ID=${OWNER_ID}

# Database URL
DATABASE_URL="${DATABASE_URL}"
EOF
}

write_env_recorder() {
  local outpath="$1"
  cat > "$outpath" <<EOF
# Application name
APP_NAME=${APP_NAME}

# Backend API URL
BACKEND_URL=${BACKEND_URL}

# LMU local API URL
LMU_URL=${LMU_URL}
EOF
}

# ---------- Start ----------
require_dir "./Backend"
require_dir "./Discord Bot"
require_dir "./Recorder"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$(pick_python)"
install_venv_support_if_needed "$PYTHON_BIN"

echo
echo "=== Setup ==="
echo
echo "Discord credentials help:"
echo "  • Bot Token (TOKEN): Discord Developer Portal -> Your App -> Bot -> Token (Reset/Copy)"
echo "  • OAuth Client ID (DISCORD_CLIENT_ID): Developer Portal -> Your App -> OAuth2 -> Client ID"
echo "  • OAuth Client Secret (DISCORD_CLIENT_SECRET): Developer Portal -> Your App -> OAuth2 -> Client Secret (Reset/Copy)"
echo "Guild ID help (HOME_GUILD_ID):"
echo "  • Discord -> Settings -> Advanced -> Developer Mode ON"
echo "  • Right-click server -> Copy Server ID"
echo "  • HOME_GUILD_ID is enforced on the backend to restrict Recorder login to members of that server."
echo

# -----------------------------
# Group 1: URLs first (requested)
# -----------------------------
echo "=== URLs ==="
BACKEND_URL="$(prompt "Backend API URL" "http://localhost:8000")"
LMU_URL="$(prompt "LMU local API URL" "http://localhost:6397")"
echo

# -----------------------------
# Group 2: Backend server config
# -----------------------------
echo "=== Backend: Server Configuration ==="
DEBUG="$(prompt "Debug mode (DEBUG)" "false")"
HOST="$(prompt "Host (HOST)" "localhost")"
PORT="$(prompt "Port (PORT)" "8000")"
echo

# -----------------------------
# Group 3: Backend Discord OAuth2
# -----------------------------
echo "=== Backend: Discord OAuth2 Configuration ==="
DISCORD_CLIENT_ID="$(prompt "Discord OAuth Client ID (DISCORD_CLIENT_ID)" "")"
DISCORD_CLIENT_SECRET="$(prompt "Discord OAuth Client Secret (DISCORD_CLIENT_SECRET)" "")"

DEFAULT_CALLBACK="${BACKEND_URL%/}/discord/callback"
DISCORD_CALLBACK_URL="$(prompt "Discord callback URL (DISCORD_CALLBACK_URL)" "$DEFAULT_CALLBACK")"

HOME_GUILD_ID="$(prompt "Home Server ID (HOME_GUILD_ID) - used to restrict login" "")"
echo

# -----------------------------
# Group 4: Backend misc
# -----------------------------
echo "=== Backend: Callback + Database ==="
APPLICATION_CALLBACK="$(prompt "Application callback URL (APPLICATION_CALLBACK)" "http://localhost:54783/callback")"
DATABASE_PATH="$(prompt "Database path (DATABASE_PATH)" "../database.db")"
echo

# -----------------------------
# Group 5: Discord Bot (no duplicate guild/db asks)
# -----------------------------
echo "=== Discord Bot ==="
TOKEN="$(prompt "Discord Bot Token (TOKEN)" "")"
GUILD_ID="$HOME_GUILD_ID"   # Do not ask twice
OWNER_ID="$(prompt "Owner ID (OWNER_ID)" "")"
DATABASE_URL="$DATABASE_PATH"  # Do not ask twice
echo

# -----------------------------
# Group 6: Recorder
# -----------------------------
echo "=== Recorder ==="
APP_NAME="$(prompt "App name (APP_NAME)" "LMU Times Recorder")"
echo

echo "=== Writing .env files ==="
write_env_backend "./Backend/.env"
write_env_discord_bot "./Discord Bot/.env"
write_env_recorder "./Recorder/.env"

echo "Wrote:"
echo "  ./Backend/.env"
echo "  ./Discord Bot/.env"
echo "  ./Recorder/.env"
echo

echo "=== Creating venvs + installing requirements ==="
venv_install_requirements "./Backend" "$PYTHON_BIN"
venv_install_requirements "./Discord Bot" "$PYTHON_BIN"
venv_install_requirements "./Recorder" "$PYTHON_BIN"

echo
echo "=== PyInstaller build (Recorder) ==="
echo "Put an icon named 'icon.ico' in THIS script folder:"
echo "  $SCRIPT_DIR"
echo

ICON_PATH="${SCRIPT_DIR}/icon.ico"
while [[ ! -f "$ICON_PATH" ]]; do
  read -r -p "icon.ico not found yet. Put it in the script folder and press Enter to re-check (or Ctrl+C to abort)..." _
done

echo "Found icon: $ICON_PATH"
echo "Copying icon into ./Recorder ..."
cp -f "$ICON_PATH" "./Recorder/icon.ico"

echo "Building Recorder with PyInstaller..."
(
  cd "./Recorder"
  activate_venv

  # Ensure PyInstaller exists in this venv
  if ! python -c "import PyInstaller" >/dev/null 2>&1; then
    echo "PyInstaller not found in Recorder venv. Installing it now..."
    pip install pyinstaller
  fi

  python -m PyInstaller --onefile --windowed --icon=icon.ico --name "$APP_NAME" main.py
)

mkdir -p "./out"

DIST_DIR="./Recorder/dist"
if [[ -d "$DIST_DIR" ]]; then
  if [[ -f "${DIST_DIR}/${APP_NAME}.exe" ]]; then
    mv -f "${DIST_DIR}/${APP_NAME}.exe" "./out/"
    echo "Moved: ./out/${APP_NAME}.exe"
  elif [[ -f "${DIST_DIR}/${APP_NAME}" ]]; then
    mv -f "${DIST_DIR}/${APP_NAME}" "./out/"
    echo "Moved: ./out/${APP_NAME}"
  else
    echo "WARNING: Could not find expected output in ${DIST_DIR}."
    echo "Contents:"
    ls -la "$DIST_DIR" || true
  fi
else
  echo "WARNING: Dist folder not found: ${DIST_DIR}"
fi

echo
echo "✅ Done."
echo "Output folder: ./out"
