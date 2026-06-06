#!/bin/bash
#
# TeleExport Deployment Script
# Automated headless deployment for Ubuntu AWS servers
# Fully cleans old installation before fresh deploy
#
set -eo pipefail

# ─── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ─── Logging helpers ──────────────────────────────────────────────────────────
info()    { echo -e "${CYAN}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ─── Error trap ───────────────────────────────────────────────────────────────
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo ""
        error "Deployment failed (exit code ${exit_code}). Check the output above for details."
        error "You can re-run this script after fixing the issue."
    fi
}
trap cleanup EXIT
trap 'error "Failed at line $LINENO (command: $BASH_COMMAND)"' ERR

# ─── Banner ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║          TeleExport Server Deployment            ║${NC}"
echo -e "${CYAN}║      Automated Headless Setup for Ubuntu         ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ─── Check sudo ───────────────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    error "This script must be run with sudo."
    echo "  Usage: sudo bash deploy.sh"
    exit 1
fi

if [ -z "$SUDO_USER" ] || [ "$SUDO_USER" = "root" ]; then
    error "Please run with sudo as a regular user (not as root directly)."
    echo "  Usage: sudo bash deploy.sh"
    exit 1
fi

REAL_USER="$SUDO_USER"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)
info "Running as root, service will run as user: ${GREEN}${REAL_USER}${NC}"

# ─── Determine script directory ───────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
info "TeleExport directory: $SCRIPT_DIR"

# ─── Clean old installation ───────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║       Cleaning Previous Installation             ║${NC}"
echo -e "${YELLOW}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# Stop and remove old systemd service
if systemctl is-active --quiet teleexport.service 2>/dev/null; then
    info "Stopping running teleexport service..."
    systemctl stop teleexport.service
    success "Service stopped."
fi

if systemctl is-enabled --quiet teleexport.service 2>/dev/null; then
    info "Disabling old teleexport service..."
    systemctl disable teleexport.service > /dev/null 2>&1
    success "Service disabled."
fi

if [ -f /etc/systemd/system/teleexport.service ]; then
    info "Removing old systemd service file..."
    rm -f /etc/systemd/system/teleexport.service
    systemctl daemon-reload
    success "Old service file removed."
fi

# Remove old venv
VENV_DIR="${REAL_HOME}/.teleexport/venv"
if [ -d "$VENV_DIR" ]; then
    info "Removing old Python virtual environment..."
    rm -rf "$VENV_DIR"
    success "Old venv removed."
fi

# Remove old session files (they will be re-created during auth)
SESSION_DIR_PATH="${REAL_HOME}/.teleexport/sessions"
if [ -d "$SESSION_DIR_PATH" ]; then
    info "Removing old session files..."
    rm -rf "$SESSION_DIR_PATH"
    success "Old sessions removed."
fi

# Remove old config (will be re-created with new credentials)
CONFIG_DIR_PATH="${REAL_HOME}/.teleexport/config"
if [ -d "$CONFIG_DIR_PATH" ]; then
    info "Removing old config..."
    rm -rf "$CONFIG_DIR_PATH"
    success "Old config removed."
fi

# Remove stale Unix socket
SOCKET_PATH="${REAL_HOME}/.teleexport/teleexport.sock"
if [ -e "$SOCKET_PATH" ]; then
    info "Removing stale socket file..."
    rm -f "$SOCKET_PATH"
    success "Socket removed."
fi

# Remove old __pycache__ directories
find "$SCRIPT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

success "Old installation cleaned."

# ─── System checks ───────────────────────────────────────────────────────────
echo ""
info "Checking system requirements..."

# Check Ubuntu
if ! grep -qi "ubuntu" /etc/os-release 2>/dev/null; then
    warn "This script is designed for Ubuntu. Proceeding anyway..."
fi

# Check RAM (minimum 1GB)
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_RAM_MB=$((TOTAL_RAM_KB / 1024))
if [ "$TOTAL_RAM_MB" -lt 1024 ]; then
    warn "System has ${TOTAL_RAM_MB}MB RAM. Minimum recommended is 1024MB."
else
    success "RAM: ${TOTAL_RAM_MB}MB (OK)"
fi

# Check disk space (minimum 1GB free)
FREE_DISK_KB=$(df / | tail -1 | awk '{print $4}')
FREE_DISK_MB=$((FREE_DISK_KB / 1024))
if [ "$FREE_DISK_MB" -lt 1024 ]; then
    warn "Low disk space: ${FREE_DISK_MB}MB free. Minimum recommended is 1024MB."
else
    success "Disk: ${FREE_DISK_MB}MB free (OK)"
fi

# ─── Install system dependencies ──────────────────────────────────────────────
echo ""
info "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq software-properties-common build-essential curl > /dev/null 2>&1
success "System dependencies installed."

# ─── Install Python 3.11+ ─────────────────────────────────────────────────────
info "Checking Python 3.11..."
if command -v python3.11 &>/dev/null; then
    PYTHON_VERSION=$(python3.11 --version 2>&1)
    success "Python 3.11 already installed: $PYTHON_VERSION"
else
    info "Installing Python 3.11 via deadsnakes PPA..."
    add-apt-repository -y ppa:deadsnakes/ppa > /dev/null 2>&1
    apt-get update -qq
    apt-get install -y -qq python3.11 python3.11-venv python3.11-dev > /dev/null 2>&1
    success "Python 3.11 installed: $(python3.11 --version 2>&1)"
fi

# ─── Install pip for Python 3.11 ──────────────────────────────────────────────
info "Ensuring pip is available for Python 3.11..."
if ! python3.11 -m pip --version &>/dev/null; then
    apt-get install -y -qq python3-pip > /dev/null 2>&1 || true
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11 > /dev/null 2>&1
fi
success "pip ready: $(python3.11 -m pip --version 2>&1 | head -1)"

# ─── Create Python virtual environment ─────────────────────────────────────────
echo ""
info "Creating fresh Python virtual environment..."
sudo -u "$REAL_USER" python3.11 -m venv "$VENV_DIR"
success "Virtual environment created at ${VENV_DIR}"

# ─── Install Python dependencies ──────────────────────────────────────────────
info "Installing Python dependencies in venv..."
sudo -u "$REAL_USER" "${VENV_DIR}/bin/pip" install --upgrade pip > /dev/null 2>&1
sudo -u "$REAL_USER" "${VENV_DIR}/bin/pip" install \
    "telethon>=1.30" \
    "jinja2>=3.1" \
    "pillow>=11" \
    "orjson>=3.10" \
    "aiofiles>=24" \
    "tqdm>=4.66" \
    "emoji>=2.14" \
    "python-dateutil>=2.9" \
    "colorama>=0.4.6" \
    > /dev/null 2>&1
success "All Python dependencies installed in venv."

# ─── Prompt for Telegram API credentials ──────────────────────────────────────
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       Telegram API Credentials Setup             ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}You need API credentials from https://my.telegram.org${NC}"
echo -e "${YELLOW}Go to 'API development tools' and create an application.${NC}"
echo ""

# Prompt for api_id
while true; do
    read -rp "$(echo -e "${CYAN}Enter your api_id (numeric): ${NC}")" API_ID
    if [[ "$API_ID" =~ ^[0-9]+$ ]]; then
        success "api_id accepted: $API_ID"
        break
    else
        error "api_id must be a number. Please try again."
    fi
done

# Prompt for api_hash
while true; do
    read -rp "$(echo -e "${CYAN}Enter your api_hash (32 hex characters): ${NC}")" API_HASH
    if [[ "$API_HASH" =~ ^[a-fA-F0-9]{32}$ ]]; then
        success "api_hash accepted."
        break
    else
        error "api_hash must be exactly 32 hex characters (a-f and 0-9 only). Please try again."
    fi
done

# ─── Write config ─────────────────────────────────────────────────────────────
echo ""
info "Writing configuration..."
EXPORTS_DIR="${REAL_HOME}/TeleExport/exports"

mkdir -p "$CONFIG_DIR_PATH" "$SESSION_DIR_PATH" "$EXPORTS_DIR"

cat > "${CONFIG_DIR_PATH}/settings.json" <<EOF
{
    "api_id": ${API_ID},
    "api_hash": "${API_HASH}",
    "output_dir": "${EXPORTS_DIR}",
    "format": "html",
    "media_types": ["photo", "video", "audio", "document", "voice", "sticker"],
    "max_file_size_mb": 500,
    "batch_size": 100,
    "include_replies": true,
    "include_forwards": true,
    "theme": "dark",
    "language": "en"
}
EOF

# Fix ownership and permissions
chown -R "${REAL_USER}:${REAL_USER}" "${REAL_HOME}/.teleexport"
chown -R "${REAL_USER}:${REAL_USER}" "${REAL_HOME}/TeleExport"
chmod 600 "${CONFIG_DIR_PATH}/settings.json"
chmod 700 "${SESSION_DIR_PATH}"
success "Configuration saved to ${CONFIG_DIR_PATH}/settings.json"

# ─── Make run_server.py executable ────────────────────────────────────────────
chmod +x "${SCRIPT_DIR}/run_server.py"

# ─── Create systemd service ──────────────────────────────────────────────────
echo ""
info "Setting up systemd service..."

VENV_PYTHON="${VENV_DIR}/bin/python3"
RUN_SCRIPT="${SCRIPT_DIR}/run_server.py"

cat > /etc/systemd/system/teleexport.service <<EOF
[Unit]
Description=TeleExport Telegram Export Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${REAL_USER}
Group=${REAL_USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${VENV_PYTHON} ${RUN_SCRIPT}
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=HOME=${REAL_HOME}
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

success "Systemd service created at /etc/systemd/system/teleexport.service"

# ─── Enable service (but don't start - needs auth first) ─────────────────────
info "Enabling service..."
systemctl daemon-reload
systemctl enable teleexport.service > /dev/null 2>&1
success "Service enabled (will start on boot after authentication)."

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║            Authentication Required               ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
warn "You must authenticate before starting the service!"
echo ""
echo -e "${CYAN}Run this command to authenticate:${NC}"
echo ""
echo -e "  ${GREEN}${VENV_PYTHON} ${RUN_SCRIPT}${NC}"
echo ""
echo -e "${CYAN}What will happen:${NC}"
echo -e "  1. It will ask for your phone number (with country code like +998...)"
echo -e "  2. A verification code will be sent to your Telegram app"
echo -e "  3. If you don't receive it, press Enter to get an SMS"
echo -e "  4. Enter the code to complete authentication"
echo ""
echo -e "${CYAN}After authentication, start the service:${NC}"
echo ""
echo -e "  ${GREEN}sudo systemctl start teleexport${NC}"
echo -e "  ${GREEN}sudo systemctl status teleexport${NC}"
echo ""

# ─── Final status ─────────────────────────────────────────────────────────────
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║            Deployment Complete!                   ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
success "TeleExport has been deployed successfully."
echo ""
echo -e "${CYAN}Service commands:${NC}"
echo -e "  Start:   ${GREEN}sudo systemctl start teleexport${NC}"
echo -e "  Stop:    ${GREEN}sudo systemctl stop teleexport${NC}"
echo -e "  Status:  ${GREEN}sudo systemctl status teleexport${NC}"
echo -e "  Logs:    ${GREEN}sudo journalctl -u teleexport -f${NC}"
echo -e "  Restart: ${GREEN}sudo systemctl restart teleexport${NC}"
echo ""

# ─── my.telegram.org Instructions ─────────────────────────────────────────────
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     my.telegram.org Application Setup            ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}If you haven't created your Telegram API application yet:${NC}"
echo ""
echo -e "  1. Go to ${GREEN}https://my.telegram.org${NC}"
echo -e "  2. Log in with your phone number"
echo -e "  3. Click ${GREEN}'API development tools'${NC}"
echo -e "  4. Fill in the form with these values:"
echo ""
echo -e "     ${CYAN}App title:${NC}       TeleExport"
echo -e "     ${CYAN}Short name:${NC}      teleexport"
echo -e "     ${CYAN}URL:${NC}             (leave empty or enter any URL)"
echo -e "     ${CYAN}Platform:${NC}        Desktop"
echo -e "     ${CYAN}Description:${NC}     Telegram chat export tool"
echo ""
echo -e "  5. Click ${GREEN}'Create application'${NC}"
echo -e "  6. Copy the ${GREEN}api_id${NC} (number) and ${GREEN}api_hash${NC} (32 hex chars)"
echo ""
echo -e "${YELLOW}NOTE: my.telegram.org rate-limits login attempts. If you enter the wrong${NC}"
echo -e "${YELLOW}SMS code too many times, access may be blocked for up to 24 hours.${NC}"
echo ""
echo -e "${GREEN}Done! Your TeleExport server is ready.${NC}"
echo ""
