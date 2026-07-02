#!/usr/bin/env bash
#
# One-shot deploy for the World Cup Detector backend on a VPS that already runs
# Traefik as its reverse proxy. Auto-detects Traefik's Docker network, removes
# any leftover Caddy container, and (re)creates the backend wired into Traefik
# with automatic HTTPS and the correct CORS origins.
#
# Usage (on the VPS):
#   curl -fsSL https://raw.githubusercontent.com/Naofumi-dev/world-cup-detector/main/deploy.sh | bash
#
# Override any default with an env var, e.g.:
#   curl -fsSL .../deploy.sh | TRAEFIK_NETWORK=proxy WCD_CERTRESOLVER=le bash
#
set -euo pipefail

REPO="https://github.com/Naofumi-dev/world-cup-detector.git"
BRANCH="${WCD_BRANCH:-main}"
DIR="${WCD_DIR:-/opt/world-cup-detector}"
DOMAIN="${WCD_DOMAIN:-wcd-api.armageddonvivas.cloud}"
CORS="${WCD_CORS_ORIGINS:-https://world-cup-detector.vercel.app,https://armageddonvivas.cloud,https://www.armageddonvivas.cloud}"
CORS_REGEX="${WCD_CORS_ORIGIN_REGEX:-https://.*\.vercel\.app}"
CERTRESOLVER="${WCD_CERTRESOLVER:-letsencrypt}"
FOOTBALL_TOKEN="${WCD_FOOTBALL_API_TOKEN:-}"

echo "==> World Cup Detector deploy (Traefik mode)"

command -v docker >/dev/null 2>&1 || { echo "==> Installing Docker..."; curl -fsSL https://get.docker.com | sh; }
docker compose version >/dev/null 2>&1 || { echo "ERROR: Docker Compose v2 plugin required." >&2; exit 1; }

# --- Detect the Docker network that Traefik is on (so the backend can share it).
NET="${TRAEFIK_NETWORK:-}"
if [ -z "$NET" ]; then
  TRAEFIK_CT=$(docker ps --format '{{.Names}}' | grep -i traefik | head -1 || true)
  if [ -n "$TRAEFIK_CT" ]; then
    NET=$(docker inspect "$TRAEFIK_CT" -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}' \
          | grep -vE '^(bridge|host|none|)$' | head -1 || true)
  fi
fi
if [ -z "$NET" ]; then
  echo "ERROR: Could not auto-detect Traefik's network. Re-run with TRAEFIK_NETWORK=<name>." >&2
  echo "       (find it with: docker network ls)" >&2
  exit 1
fi
echo "==> Traefik network: $NET"
echo "==> Domain: $DOMAIN   CORS: $CORS"

# --- Clone or hard-update the repo checkout.
if [ -d "$DIR/.git" ]; then
  echo "==> Updating checkout..."
  git -C "$DIR" fetch origin "$BRANCH"
  git -C "$DIR" reset --hard "origin/$BRANCH"
else
  echo "==> Cloning repo..."
  git clone -b "$BRANCH" "$REPO" "$DIR"
fi

# --- Write the runtime env consumed by docker-compose.yml.
# Preserve a previously-configured football-data token when not supplied.
if [ -z "$FOOTBALL_TOKEN" ] && [ -f "$DIR/deploy/.env" ]; then
  FOOTBALL_TOKEN=$(grep -E '^WCD_FOOTBALL_API_TOKEN=' "$DIR/deploy/.env" | head -1 | cut -d= -f2- || true)
fi
cat > "$DIR/deploy/.env" <<EOF
WCD_DOMAIN=$DOMAIN
WCD_CORS_ORIGINS=$CORS
WCD_CORS_ORIGIN_REGEX=$CORS_REGEX
WCD_CERTRESOLVER=$CERTRESOLVER
TRAEFIK_NETWORK=$NET
WCD_FOOTBALL_API_TOKEN=$FOOTBALL_TOKEN
EOF

# --- Recreate the stack (removes the orphaned Caddy container).
cd "$DIR/deploy"
echo "==> Recreating backend..."
docker compose up -d --build --force-recreate --remove-orphans

echo
docker compose ps
echo
echo "Done. Give Traefik ~30s for the cert, then verify (should print the header):"
echo "  curl -si -H \"Origin: https://world-cup-detector.vercel.app\" https://$DOMAIN/api/health | grep -i access-control"
