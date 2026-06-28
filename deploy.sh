#!/usr/bin/env bash
#
# One-shot deploy for the World Cup Detector backend on a VPS.
#
# Brings up the FastAPI backend behind Caddy (automatic HTTPS via Let's Encrypt)
# using Docker Compose. Safe to re-run — it pulls the latest code and restarts.
#
# Usage (on the VPS):
#   curl -fsSL https://raw.githubusercontent.com/Naofumi-dev/world-cup-detector/main/deploy.sh | sudo bash
#
# Override defaults with env vars, e.g.:
#   curl -fsSL .../deploy.sh | sudo WCD_DOMAIN=api.example.com bash
#
set -euo pipefail

REPO="https://github.com/Naofumi-dev/world-cup-detector.git"
BRANCH="${WCD_BRANCH:-main}"
DIR="${WCD_DIR:-/opt/world-cup-detector}"
DOMAIN="${WCD_DOMAIN:-wcd-api.armageddonvivas.cloud}"
CORS="${WCD_CORS_ORIGINS:-https://armageddonvivas.cloud,https://www.armageddonvivas.cloud}"

echo "==> World Cup Detector deploy"
echo "    domain : $DOMAIN"
echo "    cors   : $CORS"
echo "    dir    : $DIR"
echo

# 1. Ensure Docker is installed.
if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker..."
  curl -fsSL https://get.docker.com | sh
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: Docker Compose v2 plugin not found. Install it and re-run." >&2
  exit 1
fi

# 2. Clone or update the repo.
if [ -d "$DIR/.git" ]; then
  echo "==> Updating existing checkout..."
  git -C "$DIR" fetch origin "$BRANCH"
  git -C "$DIR" checkout -B "$BRANCH" "origin/$BRANCH"
else
  echo "==> Cloning repo..."
  git clone -b "$BRANCH" "$REPO" "$DIR"
fi

# 3. Write the runtime env consumed by docker-compose.yml.
cat > "$DIR/deploy/.env" <<EOF
WCD_DOMAIN=$DOMAIN
WCD_CORS_ORIGINS=$CORS
EOF

# 4. Build and start.
echo "==> Building and starting containers..."
cd "$DIR/deploy"
docker compose up -d --build

echo
echo "==> Containers:"
docker compose ps
echo
echo "Done. Caddy will fetch a TLS cert on first request (~30s)."
echo "Verify from anywhere:"
echo "    curl -s https://$DOMAIN/api/health    # expect {\"status\":\"ok\"}"
echo
echo "If the cert never appears, make sure the Cloudflare record for"
echo "'$DOMAIN' is set to DNS only (grey cloud) and ports 80/443 are open."
