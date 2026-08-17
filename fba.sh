#!/bin/bash
# ============================================
# FBA System - Management Script
# Easy commands to control the system
# ============================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="fba-system"

case "$1" in
    start)
        echo "Starting FBA System..."
        sudo systemctl start $SERVICE_NAME
        sleep 2
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    stop)
        echo "Stopping FBA System..."
        sudo systemctl stop $SERVICE_NAME
        echo "Stopped."
        ;;
    restart)
        echo "Restarting FBA System..."
        sudo systemctl restart $SERVICE_NAME
        sleep 2
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    status)
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    logs)
        sudo journalctl -u $SERVICE_NAME -f --no-pager
        ;;
    logs-today)
        sudo journalctl -u $SERVICE_NAME --since today --no-pager
        ;;
    update)
        echo "Updating FBA System..."
        cd "$SCRIPT_DIR"
        git pull 2>/dev/null || echo "Not a git repo, skipping pull"
        source .venv/bin/activate
        pip install -r requirements.txt -q
        sudo systemctl restart $SERVICE_NAME
        echo "Updated and restarted."
        ;;
    edit-env)
        nano "$SCRIPT_DIR/.env"
        echo "Remember to restart: $0 restart"
        ;;
    backup)
        BACKUP_DIR="$SCRIPT_DIR/backups"
        mkdir -p "$BACKUP_DIR"
        DATE=$(date +%Y%m%d_%H%M%S)
        cp "$SCRIPT_DIR/fba_system.db" "$BACKUP_DIR/fba_system_$DATE.db" 2>/dev/null
        cp "$SCRIPT_DIR/.env" "$BACKUP_DIR/env_$DATE.backup" 2>/dev/null
        echo "Backup saved to $BACKUP_DIR/"
        ;;
    docker-up)
        cd "$SCRIPT_DIR"
        docker-compose up -d --build
        echo "Docker container started."
        ;;
    docker-down)
        cd "$SCRIPT_DIR"
        docker-compose down
        echo "Docker container stopped."
        ;;
    docker-logs)
        docker logs fba-system -f
        ;;
    *)
        echo "FBA System Manager"
        echo "=================="
        echo ""
        echo "Usage: $0 {command}"
        echo ""
        echo "Commands:"
        echo "  start        - Start the system"
        echo "  stop         - Stop the system"
        echo "  restart      - Restart the system"
        echo "  status       - Check status"
        echo "  logs         - Follow live logs"
        echo "  logs-today   - View today's logs"
        echo "  update       - Pull updates and restart"
        echo "  edit-env     - Edit configuration"
        echo "  backup       - Backup database and config"
        echo ""
        echo "Docker commands:"
        echo "  docker-up    - Start with Docker"
        echo "  docker-down  - Stop Docker container"
        echo "  docker-logs  - View Docker logs"
        echo ""
        ;;
esac
