#!/bin/bash
# ============================================
# Amazon FBA Wholesale System - Linux Setup
# Run this once on your server
# ============================================

set -e

echo "=========================================="
echo "  FBA Wholesale System - Linux Setup"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}Don't run this as root. Run as your regular user.${NC}"
    echo "The script will ask for sudo when needed."
    exit 1
fi

# Update system
echo -e "${YELLOW}[1/7] Updating system packages...${NC}"
sudo apt update -qq && sudo apt upgrade -y -qq

# Install Python 3.11+ if not present
echo -e "${YELLOW}[2/7] Checking Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo "Installing Python3..."
    sudo apt install -y python3 python3-pip python3-venv
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo -e "${GREEN}Found: $PYTHON_VERSION${NC}"

# Install pip and venv if missing
sudo apt install -y python3-pip python3-venv -qq 2>/dev/null || true

# Navigate to project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${YELLOW}[3/7] Creating virtual environment...${NC}"
python3 -m venv .venv
source .venv/bin/activate

echo -e "${YELLOW}[4/7] Installing dependencies...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo -e "${YELLOW}[5/7] Setting up configuration...${NC}"
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${GREEN}Created .env file. Edit it with your API keys:${NC}"
    echo "  nano .env"
else
    echo -e "${GREEN}.env already exists.${NC}"
fi

# Create uploads directory
mkdir -p uploads

echo -e "${YELLOW}[6/7] Setting up systemd service...${NC}"

# Get the current user and paths
CURRENT_USER=$(whoami)
PROJECT_PATH=$(pwd)
PYTHON_PATH="$PROJECT_PATH/.venv/bin/python"

# Create systemd service file
sudo tee /etc/systemd/system/fba-system.service > /dev/null <<EOF
[Unit]
Description=Amazon FBA Wholesale System
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_PATH
Environment=PATH=$PROJECT_PATH/.venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$PYTHON_PATH main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo -e "${YELLOW}[7/7] Enabling and starting service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable fba-system
sudo systemctl start fba-system

echo ""
echo -e "${GREEN}=========================================="
echo "  SETUP COMPLETE!"
echo "==========================================${NC}"
echo ""
echo "The FBA System is now running 24/7."
echo ""
echo "Useful commands:"
echo "  sudo systemctl status fba-system    # Check status"
echo "  sudo systemctl restart fba-system   # Restart"
echo "  sudo systemctl stop fba-system      # Stop"
echo "  sudo journalctl -u fba-system -f    # View logs"
echo ""
echo "Access the system at:"
echo "  http://$(hostname -I | awk '{print $1}'):8000"
echo "  or http://localhost:8000"
echo ""
echo -e "${YELLOW}Don't forget to edit .env with your API keys:${NC}"
echo "  nano $PROJECT_PATH/.env"
echo ""
