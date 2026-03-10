#!/bin/bash

# Dplight ERP Deployment Script
# Usage: ./deploy.sh

PROJECT_DIR="/opt/dplight"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo "🚀 Starting deployment..."

# 1. Pull latest code
cd $PROJECT_DIR
echo "📥 Pulling latest code..."
git pull origin main

# 2. Backend Deployment
echo "🐍 Deploying Backend..."
cd $BACKEND_DIR
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt

# 3. Frontend Deployment
echo "🎨 Deploying Frontend..."
cd $FRONTEND_DIR

# Install Node.js 20 (Required by Vite 6+)
if ! command -v node &> /dev/null || [[ $(node -v) =~ ^v1[0-9] ]]; then
    echo "❌ Node.js 20+ required. Installing..."
    curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -
    yum install -y nodejs
fi

# Explicitly add node to path for this session
export PATH=$PATH:/usr/bin:/usr/local/bin

npm install
npm run build

# 4. Restart Services
echo "🔄 Restarting Backend Service..."
# Copy service file if not exists or updated
if [ -f "$PROJECT_DIR/deploy/dplight-backend.service" ]; then
    cp "$PROJECT_DIR/deploy/dplight-backend.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable dplight-backend
fi
systemctl restart dplight-backend

echo "🔄 Reloading Nginx..."
# Copy nginx config if not exists or updated
if [ -f "$PROJECT_DIR/deploy/nginx.conf" ]; then
    cp "$PROJECT_DIR/deploy/nginx.conf" /etc/nginx/nginx.conf
fi
nginx -s reload

echo "✅ Deployment Completed Successfully!"
