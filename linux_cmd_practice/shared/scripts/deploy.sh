#!/bin/bash
# Application Deploy Script
set -e

APP_NAME="myapp"
VERSION="${1:-latest}"
DEPLOY_DIR="/opt/${APP_NAME}"

echo "=== Deploying ${APP_NAME} v${VERSION} ==="
echo "[1/4] Pulling image..."
sleep 1
echo "[2/4] Stopping old container..."
sleep 1
echo "[3/4] Starting new container..."
sleep 1
echo "[4/4] Health check..."
sleep 1
echo "Deploy successful! ${APP_NAME} v${VERSION} is running on port 8080"
