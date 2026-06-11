#!/bin/bash

set -e

echo "--- WZML-X Automated Deployment Script ---"

# 1. Update System
echo "Updating system..."
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install Dependencies
echo "Installing dependencies..."
sudo apt-get install -y python3 python3-pip python3-venv git ffmpeg aria2 curl unzip p7zip-full p7zip-rar build-essential libmagic1 qbittorrent-nox

# 3. Create Virtual Environment
echo "Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

# 4. Install Requirements
echo "Installing Python requirements..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Check/Generate .env
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "Please edit the .env file with your credentials and run the script again."
    exit 0
fi

# 6. Create Systemd Service
echo "Creating systemd service..."
REPO_PATH=$(pwd)
USER_NAME=$(whoami)

SERVICE_FILE="/etc/systemd/system/wzmlx.service"

sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=WZML-X Telegram Bot
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$REPO_PATH
ExecStart=$REPO_PATH/venv/bin/python3 -m bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 7. Enable and Start Service
echo "Starting WZML-X service..."
sudo systemctl daemon-reload
sudo systemctl enable wzmlx
sudo systemctl restart wzmlx

echo "Deployment Successful!"
echo "You can check the status with: sudo systemctl status wzmlx"
echo "You can check the logs with: journalctl -u wzmlx -f"
