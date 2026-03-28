#!/bin/bash
# HackersBot VM Startup Script - runs on every boot
# Ensures disk is expanded, Docker is cleaned up, and the app is running

set -e
LOG="/var/log/hackersbot-startup.log"
exec >> "$LOG" 2>&1
echo "=== Startup script running at $(date) ==="

# 1. Expand the filesystem to use all available disk space
echo "Expanding filesystem..."
if command -v growpart &>/dev/null; then
  growpart /dev/sda 1 2>/dev/null || true
  resize2fs /dev/sda1 2>/dev/null || true
fi
echo "Disk space after expansion:"
df -h /

# 2. Clean up Docker to free space
echo "Cleaning up Docker..."
if command -v docker &>/dev/null; then
  # Remove all stopped containers
  docker container prune -f 2>/dev/null || true
  # Remove dangling images (old layers from previous deploys)
  docker image prune -f 2>/dev/null || true
  # Remove unused volumes
  docker volume prune -f 2>/dev/null || true
  # Remove build cache
  docker builder prune -f 2>/dev/null || true
  echo "Docker disk usage after cleanup:"
  docker system df 2>/dev/null || true
fi

# 3. Clean system caches
echo "Cleaning system caches..."
apt-get clean 2>/dev/null || true
journalctl --vacuum-size=50M 2>/dev/null || true

# 4. Ensure hackersbot container is running
echo "Checking hackersbot container..."
if docker ps -a --format '{{.Names}}' | grep -q hackersbot-app; then
  if ! docker ps --format '{{.Names}}' | grep -q hackersbot-app; then
    echo "Container exists but not running. Starting..."
    docker start hackersbot-app
  else
    echo "Container is already running."
  fi
else
  echo "No hackersbot-app container found. Will be created on next deploy."
fi

# 5. Ensure nginx is running (if installed)
if command -v nginx &>/dev/null; then
  systemctl start nginx 2>/dev/null || true
fi

echo "Disk space at end of startup:"
df -h /
echo "=== Startup script completed at $(date) ==="
