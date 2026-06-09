#!/bin/bash
#
# Anti-Stalker Intelligence System Deployment Script
# Automated headless deployment for Ubuntu servers
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
echo -e "${CYAN}║     Anti-Stalker Intelligence System             ║${NC}"
echo -e "${CYAN}║      Automated Deployment for Ubuntu             ║${NC}"
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
info "Anti-Stalker directory: $SCRIPT_DIR"

# ─── Clean old installation ───────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║       Cleaning Previous Installation             ║${NC}"
echo -e "${YELLOW}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# Stop and remove old systemd service
if systemctl is-active --quiet anti_stalker.service 2>/dev/null; then
    info "Stopping running anti_stalker service..."
    systemctl stop anti_stalker.service
    success "Service stopped."
fi

if systemctl is-enabled --quiet anti_stalker.service 2>/dev/null; then
    info "Disabling old anti_stalker service..."
    systemctl disable anti_stalker.service > /dev/null 2>&1
    success "Service disabled."
fi

if [ -f /etc/systemd/system/anti_stalker.service ]; then
    info "Removing old systemd service file..."
    rm -f /etc/systemd/system/anti_stalker.service
    systemctl daemon-reload
    success "Old service file removed."
fi

# Remove old venv
VENV_DIR="${REAL_HOME}/.anti_stalker/venv"
if [ -d "$VENV_DIR" ]; then
    info "Removing old Python virtual environment..."
    rm -rf "$VENV_DIR"
    success "Old venv removed."
fi

# Remove old config
CONFIG_DIR="${REAL_HOME}/.anti_stalker/config"
if [ -d "$CONFIG_DIR" ]; then
    info "Removing old config..."
    rm -rf "$CONFIG_DIR"
    success "Old config removed."
fi

# Remove old session files (they will be re-created during auth)
SESSION_DIR="${REAL_HOME}/.anti_stalker/data/sessions"
if [ -d "$SESSION_DIR" ]; then
    info "Removing old session files..."
    rm -rf "$SESSION_DIR"
    success "Old sessions removed."
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

# Check disk space (minimum 2GB free)
FREE_DISK_KB=$(df / | tail -1 | awk '{print $4}')
FREE_DISK_MB=$((FREE_DISK_KB / 1024))
if [ "$FREE_DISK_MB" -lt 2048 ]; then
    warn "Low disk space: ${FREE_DISK_MB}MB free. Minimum recommended is 2048MB."
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
sudo -u "$REAL_USER" "${VENV_DIR}/bin/pip" install -r "${SCRIPT_DIR}/requirements.txt" > /dev/null 2>&1
success "All Python dependencies installed in venv."

# ─── Prompt for credentials ───────────────────────────────────────────────────
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         Credentials & Configuration              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}You need API credentials from https://my.telegram.org${NC}"
echo -e "${YELLOW}Go to 'API development tools' and create an application.${NC}"
echo ""

# Prompt for TELEGRAM_API_ID
while true; do
    read -rp "$(echo -e "${CYAN}Enter your TELEGRAM_API_ID (numeric): ${NC}")" TELEGRAM_API_ID
    if [[ "$TELEGRAM_API_ID" =~ ^[0-9]+$ ]]; then
        success "TELEGRAM_API_ID accepted: $TELEGRAM_API_ID"
        break
    else
        error "TELEGRAM_API_ID must be a number. Please try again."
    fi
done

# Prompt for TELEGRAM_API_HASH
while true; do
    read -rp "$(echo -e "${CYAN}Enter your TELEGRAM_API_HASH (32 hex characters): ${NC}")" TELEGRAM_API_HASH
    if [[ "$TELEGRAM_API_HASH" =~ ^[a-fA-F0-9]{32}$ ]]; then
        success "TELEGRAM_API_HASH accepted."
        break
    else
        error "TELEGRAM_API_HASH must be exactly 32 hex characters (a-f and 0-9 only). Please try again."
    fi
done

# Prompt for TELEGRAM_PHONE
while true; do
    read -rp "$(echo -e "${CYAN}Enter your TELEGRAM_PHONE (e.g. +1234567890): ${NC}")" TELEGRAM_PHONE
    if [[ "$TELEGRAM_PHONE" =~ ^\+[0-9]{10,15}$ ]]; then
        success "TELEGRAM_PHONE accepted: $TELEGRAM_PHONE"
        break
    else
        error "TELEGRAM_PHONE must start with + followed by 10-15 digits. Please try again."
    fi
done

# Prompt for BOT_TOKEN
while true; do
    read -rp "$(echo -e "${CYAN}Enter your BOT_TOKEN (format NUMBER:HASH): ${NC}")" BOT_TOKEN
    if [[ "$BOT_TOKEN" =~ ^[0-9]+:.+$ ]]; then
        success "BOT_TOKEN accepted."
        break
    else
        error "BOT_TOKEN must be in format NUMBER:HASH (e.g. 123456:ABCdef...). Please try again."
    fi
done

# Prompt for MY_TELEGRAM_ID
while true; do
    read -rp "$(echo -e "${CYAN}Enter your MY_TELEGRAM_ID (numeric): ${NC}")" MY_TELEGRAM_ID
    if [[ "$MY_TELEGRAM_ID" =~ ^[0-9]+$ ]]; then
        success "MY_TELEGRAM_ID accepted: $MY_TELEGRAM_ID"
        break
    else
        error "MY_TELEGRAM_ID must be a number. Please try again."
    fi
done

# Prompt for DASHBOARD_SECRET_KEY
while true; do
    read -rp "$(echo -e "${CYAN}Enter DASHBOARD_SECRET_KEY (min 16 chars, or press Enter to auto-generate): ${NC}")" DASHBOARD_SECRET_KEY
    if [ -z "$DASHBOARD_SECRET_KEY" ]; then
        DASHBOARD_SECRET_KEY=$(python3.11 -c "import secrets; print(secrets.token_hex(32))")
        success "DASHBOARD_SECRET_KEY auto-generated."
        break
    elif [ ${#DASHBOARD_SECRET_KEY} -ge 16 ]; then
        success "DASHBOARD_SECRET_KEY accepted."
        break
    else
        error "DASHBOARD_SECRET_KEY must be at least 16 characters. Please try again."
    fi
done

# Prompt for TRACKING_REDIRECT_URL
while true; do
    read -rp "$(echo -e "${CYAN}Enter TRACKING_REDIRECT_URL (starts with http): ${NC}")" TRACKING_REDIRECT_URL
    if [[ "$TRACKING_REDIRECT_URL" =~ ^https?://.+$ ]]; then
        success "TRACKING_REDIRECT_URL accepted: $TRACKING_REDIRECT_URL"
        break
    else
        error "TRACKING_REDIRECT_URL must start with http:// or https://. Please try again."
    fi
done

# ─── Write config ─────────────────────────────────────────────────────────────
echo ""
info "Writing configuration..."

DATA_DIR="${REAL_HOME}/.anti_stalker/data"
mkdir -p "$CONFIG_DIR" "$DATA_DIR/logs" "$DATA_DIR/backups" "$DATA_DIR/reports" "$DATA_DIR/sessions"

cat > "${CONFIG_DIR}/.env" <<EOF
# Anti-Stalker Intelligence System Configuration
# Generated by deploy.sh on $(date)

# Telegram API Credentials
TELEGRAM_API_ID=${TELEGRAM_API_ID}
TELEGRAM_API_HASH=${TELEGRAM_API_HASH}
TELEGRAM_PHONE=${TELEGRAM_PHONE}

# Bot Configuration
BOT_TOKEN=${BOT_TOKEN}
MY_TELEGRAM_ID=${MY_TELEGRAM_ID}

# Dashboard Configuration
DASHBOARD_SECRET_KEY=${DASHBOARD_SECRET_KEY}
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8080

# Trap Server Configuration
TRACKING_REDIRECT_URL=${TRACKING_REDIRECT_URL}
TRAP_SERVER_HOST=0.0.0.0
TRAP_SERVER_PORT=5000

# Monitoring Intervals (seconds)
ONLINE_CHECK_INTERVAL=30
DEEP_ANALYSIS_INTERVAL=3600
REPORT_GENERATION_INTERVAL=86400

# Detection Thresholds
STALKER_SCORE_THRESHOLD=70
CORRELATION_MIN_EVENTS=5
ANOMALY_SENSITIVITY=0.8

# Storage
DATABASE_URL=sqlite+aiosqlite:///${DATA_DIR}/anti_stalker.db
LOG_DIR=${DATA_DIR}/logs
BACKUP_DIR=${DATA_DIR}/backups
REPORT_DIR=${DATA_DIR}/reports
SESSION_DIR=${DATA_DIR}/sessions
EOF

# Fix ownership and permissions
chown -R "${REAL_USER}:${REAL_USER}" "${REAL_HOME}/.anti_stalker"
chmod 600 "${CONFIG_DIR}/.env"
chmod 700 "${DATA_DIR}/sessions"
success "Configuration saved to ${CONFIG_DIR}/.env"

# Create symlink in project directory so Pydantic BaseSettings can find .env
# regardless of which directory the process is started from
ln -sf "${CONFIG_DIR}/.env" "${SCRIPT_DIR}/.env"
chown -h "${REAL_USER}:${REAL_USER}" "${SCRIPT_DIR}/.env"
success "Created .env symlink in project directory"

# ─── Create systemd service ──────────────────────────────────────────────────
echo ""
info "Setting up systemd service..."

VENV_PYTHON="${VENV_DIR}/bin/python3"

cat > /etc/systemd/system/anti_stalker.service <<EOF
[Unit]
Description=Anti-Stalker Intelligence System
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${REAL_USER}
Group=${REAL_USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${VENV_PYTHON} main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=HOME=${REAL_HOME}
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=${CONFIG_DIR}/.env

[Install]
WantedBy=multi-user.target
EOF

success "Systemd service created at /etc/systemd/system/anti_stalker.service"

# ─── Enable service (but don't start - needs auth first) ─────────────────────
info "Enabling service..."
systemctl daemon-reload
systemctl enable anti_stalker.service > /dev/null 2>&1
success "Service enabled (will start on boot after authentication)."

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║            Authentication Required               ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
warn "You must authenticate Telethon before starting the service!"
echo ""
echo -e "${CYAN}Run this command to authenticate:${NC}"
echo ""
echo -e "  ${GREEN}sudo -u ${REAL_USER} ${VENV_PYTHON} ${SCRIPT_DIR}/main.py${NC}"
echo ""
echo -e "${CYAN}What will happen:${NC}"
echo -e "  1. The system will send a verification code to your Telegram app"
echo -e "  2. Enter the code when prompted"
echo -e "  3. If 2FA is enabled, enter your 2FA password"
echo -e "  4. A session file will be saved for future headless use"
echo ""
echo -e "${CYAN}After authentication, start the service:${NC}"
echo ""
echo -e "  ${GREEN}sudo systemctl start anti_stalker${NC}"
echo -e "  ${GREEN}sudo systemctl status anti_stalker${NC}"
echo ""

# ─── Final status ─────────────────────────────────────────────────────────────
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║            Deployment Complete!                   ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
success "Anti-Stalker Intelligence System has been deployed successfully."
echo ""
echo -e "${CYAN}Service commands:${NC}"
echo -e "  Start:   ${GREEN}sudo systemctl start anti_stalker${NC}"
echo -e "  Stop:    ${GREEN}sudo systemctl stop anti_stalker${NC}"
echo -e "  Status:  ${GREEN}sudo systemctl status anti_stalker${NC}"
echo -e "  Logs:    ${GREEN}sudo journalctl -u anti_stalker -f${NC}"
echo -e "  Restart: ${GREEN}sudo systemctl restart anti_stalker${NC}"
echo ""
echo -e "${CYAN}Dashboard:${NC}"
echo -e "  URL:     ${GREEN}http://your-server-ip:8080${NC}"
echo ""
echo -e "${GREEN}Done! Your Anti-Stalker Intelligence System is ready.${NC}"
echo ""
