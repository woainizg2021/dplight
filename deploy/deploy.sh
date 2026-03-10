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

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ npm not found. Installing Node.js..."
    # Install Node.js (assuming CentOS/RHEL/OpenCloudOS)
    curl -fsSL https://rpm.nodesource.com/setup_18.x | bash -
    yum install -y nodejs
fi

npm install
npm run build

# 4. Restart Services
echo "🔄 Restarting Backend Service..."
systemctl restart dplight-backend

echo "🔄 Reloading Nginx..."
nginx -s reload

echo "✅ Deployment Completed Successfully!"
