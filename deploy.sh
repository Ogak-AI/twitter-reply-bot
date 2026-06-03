#!/bin/bash
# deploy.sh — One-command production deployment for World Cup 2026 Bot
# Supports both Docker and bare-metal (systemd) deployments
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh docker      → Deploy with Docker Compose
#   ./deploy.sh server      → Deploy directly on server (systemd)
#   ./deploy.sh update      → Pull latest code and restart
#   ./deploy.sh status      → Check running status
#   ./deploy.sh logs        → Tail live logs
#   ./deploy.sh stop        → Stop the bot

set -e

APP_DIR="/opt/worldcup-buffer-bot"
SERVICE_NAME="worldcup-bot"
REPO_URL="https://github.com/YOUR_USERNAME/worldcup-buffer-bot.git"   # Set your repo URL
PYTHON="python3"

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"

info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }


# ─── DOCKER DEPLOY ────────────────────────────────────────────────
deploy_docker() {
    info "Deploying with Docker Compose..."

    # Check Docker is installed
    command -v docker >/dev/null 2>&1 || error "Docker not installed. Run: curl -fsSL https://get.docker.com | sh"
    command -v docker-compose >/dev/null 2>&1 || \
        docker compose version >/dev/null 2>&1 || \
        error "Docker Compose not found."

    # Check .env exists
    [ -f ".env" ] || error ".env file not found. Copy .env.example to .env and fill in your values."

    info "Pulling latest images..."
    docker compose build --no-cache bot

    info "Starting services..."
    docker compose up -d

    info "Bot is running!"
    docker compose logs --tail=20 bot
}


# ─── BARE METAL / SYSTEMD DEPLOY ─────────────────────────────────
deploy_server() {
    info "Deploying to server with systemd..."

    # Must be root or sudo
    [ "$EUID" -eq 0 ] || error "Run with sudo: sudo ./deploy.sh server"

    # Install system deps
    info "Installing system dependencies..."
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip python3-venv git curl

    # No local AI model installation is required for Groq.

    # Create app user
    id -u botuser &>/dev/null || useradd -m -s /bin/bash botuser
    info "App user: botuser"

    # Clone or update repo
    if [ -d "$APP_DIR" ]; then
        info "Updating existing installation..."
        cd "$APP_DIR"
        git pull
    else
        info "Cloning repository..."
        git clone "$REPO_URL" "$APP_DIR"
        cd "$APP_DIR"
    fi

    # Check .env
    [ -f "$APP_DIR/.env" ] || {
        warn ".env not found. Copying .env.example..."
        cp "$APP_DIR/.env.example" "$APP_DIR/.env"
        error "Fill in $APP_DIR/.env then re-run deploy.sh server"
    }

    # Create virtualenv and install deps
    info "Setting up Python virtualenv..."
    $PYTHON -m venv "$APP_DIR/venv"
    "$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
    "$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

    # Create data/logs dirs
    mkdir -p "$APP_DIR/data" "$APP_DIR/logs"
    chown -R botuser:botuser "$APP_DIR"

    # Install systemd service
    info "Installing systemd service..."
    sed "s|/opt/worldcup-buffer-bot|$APP_DIR|g" "$APP_DIR/worldcup-bot.service" \
        > /etc/systemd/system/worldcup-bot.service

    systemctl daemon-reload
    systemctl enable worldcup-bot
    systemctl restart worldcup-bot

    sleep 2
    systemctl status worldcup-bot --no-pager
    info "Deployment complete! World Cup 2026 bot is running as a system service."
}


# ─── UPDATE ──────────────────────────────────────────────────────
cmd_update() {
    info "Updating bot..."
    if [ -f "docker-compose.yml" ] && command -v docker &>/dev/null; then
        git pull
        docker compose build --no-cache bot
        docker compose up -d
        info "Docker containers updated and restarted."
    else
        cd "$APP_DIR"
        git pull
        "$APP_DIR/venv/bin/pip" install --quiet -r requirements.txt
        sudo systemctl restart worldcup-bot
        info "Bot updated and restarted."
    fi
}


# ─── STATUS ──────────────────────────────────────────────────────
cmd_status() {
    if [ -f "docker-compose.yml" ] && command -v docker &>/dev/null; then
        docker compose ps
    elif systemctl is-active --quiet worldcup-bot; then
        echo ""
        systemctl status worldcup-bot --no-pager
    else
        warn "Bot does not appear to be running."
    fi
}


# ─── LOGS ────────────────────────────────────────────────────────
cmd_logs() {
    if [ -f "docker-compose.yml" ] && command -v docker &>/dev/null; then
        docker compose logs -f bot
    else
        journalctl -u worldcup-bot -f
    fi
}


# ─── STOP ────────────────────────────────────────────────────────
cmd_stop() {
    if [ -f "docker-compose.yml" ] && command -v docker &>/dev/null; then
        docker compose down
        info "Docker containers stopped."
    else
        sudo systemctl stop worldcup-bot
        info "Bot service stopped."
    fi
}


# ─── ENTRYPOINT ──────────────────────────────────────────────────
case "${1:-}" in
    docker)  deploy_docker ;;
    server)  deploy_server ;;
    update)  cmd_update ;;
    status)  cmd_status ;;
    logs)    cmd_logs ;;
    stop)    cmd_stop ;;
    *)
        echo ""
        echo "Usage: ./deploy.sh <command>"
        echo ""
        echo "Commands:"
        echo "  docker   — Deploy with Docker Compose (recommended)"
        echo "  server   — Deploy directly on server with systemd"
        echo "  update   — Pull latest code and restart"
        echo "  status   — Check if bot is running"
        echo "  logs     — Tail live logs"
        echo "  stop     — Stop the bot"
        echo ""
        ;;
esac
