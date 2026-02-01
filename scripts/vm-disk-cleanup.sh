#!/usr/bin/env bash
# Run this ON THE GCP VM (e.g. via gcloud compute ssh) to free disk space.
# Cause: repeated HackersBot deploys leave old Docker image layers; they add up.

set -e

echo "=== Disk before ==="
df -h /

echo ""
echo "=== Docker usage ==="
sudo docker system df
sudo docker images -a

echo ""
echo "=== Pruning unused Docker images and build cache (keeps running container) ==="
sudo docker image prune -af
sudo docker builder prune -af 2>/dev/null || true

echo ""
echo "=== Optional: shrink journal logs to last 2 days ==="
sudo journalctl --vacuum-time=2d 2>/dev/null || true

echo ""
echo "=== Disk after ==="
df -h /
echo ""
echo "Done. Run 'sudo docker system df' to see remaining Docker usage."
