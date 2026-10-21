#!/bin/bash
# Updates ONLY the backend + frontend containers from the two tar files in this
# folder. Does NOT touch the database, run migrations/seed, or reset the
# dashboard login (unlike deploy-app.sh). Keeps :previous images for rollback.
#
#   ./deploy-update.sh            deploy
#   ./deploy-update.sh rollback   go back to the previous images
set -e
cd "$(dirname "$0")"

NETWORK="self-branding-net"
BACKEND="self-branding-backend"
FRONTEND="self-branding-frontend"
PORT=8084

run_backend() {
  docker rm -f "$BACKEND" >/dev/null 2>&1 || true
  docker run -d --name "$BACKEND" --network "$NETWORK" \
    --env-file self-branding-backend.env --restart unless-stopped "$BACKEND:latest" >/dev/null
}
run_frontend() {
  docker rm -f "$FRONTEND" >/dev/null 2>&1 || true
  docker run -d --name "$FRONTEND" --network "$NETWORK" -p ${PORT}:3000 \
    --env-file self-branding-frontend.env --restart unless-stopped "$FRONTEND:latest" >/dev/null
}

if [ "$1" = "rollback" ]; then
  echo "==> Rolling back to :previous images..."
  docker tag "$BACKEND:previous" "$BACKEND:latest"
  docker tag "$FRONTEND:previous" "$FRONTEND:latest"
  run_backend; sleep 6; run_frontend; sleep 5
else
  [ -f self-branding-backend.tar ] && [ -f self-branding-frontend.tar ] || { echo "tar files missing in $(pwd)"; exit 1; }
  echo "==> Saving current images as :previous (rollback)..."
  docker tag "$BACKEND:latest" "$BACKEND:previous" 2>/dev/null || true
  docker tag "$FRONTEND:latest" "$FRONTEND:previous" 2>/dev/null || true
  echo "==> Loading new images..."
  docker load -i self-branding-backend.tar
  docker load -i self-branding-frontend.tar
  echo "==> Restarting backend, then frontend..."
  run_backend; sleep 6; run_frontend; sleep 5
fi

echo "==> Smoke tests..."
docker exec "$BACKEND" python -c "import requests;print('  backend /health ->', requests.get('http://localhost:8000/health').text)"
curl -s -o /dev/null -w "  frontend /login -> HTTP %{http_code}\n" "http://localhost:${PORT}/login"
curl -s -o /dev/null -w "  public https://self-branding.bassir.net/login -> HTTP %{http_code}\n" https://self-branding.bassir.net/login || true
docker ps --filter "name=self-branding-"
