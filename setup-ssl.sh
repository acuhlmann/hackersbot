#!/usr/bin/env bash
# Issue or renew Let's Encrypt TLS for hackernews.photogroup.network on hn-vm.
#
# Prerequisites:
#   - DNS A record hackernews.photogroup.network → VM public IP (DNS-only / grey cloud on Cloudflare)
#   - nginx serving the hostname on :80
#   - Ports 80 and 443 open
#
# Usage:
#   ./setup-ssl.sh

set -euo pipefail

PROJECT="${PROJECT:-photogroup-215600}"
ZONE="${ZONE:-us-central1-a}"
INSTANCE="${INSTANCE:-hn-vm}"
DOMAIN="${DOMAIN:-hackernews.photogroup.network}"

echo "Issuing/renewing TLS for $DOMAIN on $INSTANCE ($ZONE)..."

gcloud compute ssh "$INSTANCE" --project "$PROJECT" --zone "$ZONE" --command "
  set -euo pipefail
  sudo certbot --nginx -d '$DOMAIN' --non-interactive --agree-tos --register-unsafely-without-email --redirect
  sudo systemctl enable --now certbot.timer
  sudo certbot certificates
  echo '--- listeners ---'
  sudo ss -tlnp | grep -E ':80|:443' || true
"

echo ""
echo "Verify: curl -sSI https://$DOMAIN/"
