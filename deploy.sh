#!/usr/bin/env bash
# Brings up the KPI dashboard alongside the existing PDF merger.
# Run with:  sudo bash /home/mdziamara/brocarga_kpis/deploy.sh
set -euo pipefail

KPIS=/home/mdziamara/brocarga_kpis
SCRIPTS=/home/mdziamara/Brocarga-scripts

step() { printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }

step "1/6  shared network"
# Both compose projects declare this as external, so it has to exist first.
docker network inspect brocarga-edge >/dev/null 2>&1 \
  && echo "brocarga-edge already exists" \
  || docker network create brocarga-edge

step "2/6  build the dashboard image (npm ci + webpack, this is the slow one)"
docker compose -f "$KPIS/docker-compose.yaml" --project-directory "$KPIS" build

step "3/6  start the dashboard"
docker compose -f "$KPIS/docker-compose.yaml" --project-directory "$KPIS" up -d

step "4/6  recreate the proxy so it joins brocarga-edge and picks up the new routing"
docker compose -f "$SCRIPTS/docker-compose.yaml" --project-directory "$SCRIPTS" up -d

step "5/6  containers"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

step "6/6  checks"
echo "-- nginx config --"
docker exec pdf-merger-proxy nginx -t 2>&1 || true

echo "-- dashboard direct (expect 200) --"
# Same X-Forwarded-Proto trick as the compose healthcheck: this bypasses nginx,
# and without the header SECURE_SSL_REDIRECT sends the probe to https on a
# plaintext port, where it hangs on a TLS handshake that never completes.
docker exec brocarga-kpis-web python -c "
import urllib.request as u
r = u.urlopen(u.Request('http://127.0.0.1:8000/api/health/',
                        headers={'X-Forwarded-Proto': 'https'}), timeout=10)
print(r.status, r.read(300).decode())
" 2>&1 || true

echo "-- through the proxy, the paths the tunnel will hit --"
for path in / /api/health/ /merge; do
  code=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 15 "https://127.0.0.1:8090$path" || echo "curl-failed")
  printf '  %-16s %s\n' "$path" "$code"
done

echo
echo "Expected: /  -> 200 (SPA shell), /api/health/ -> 200, /merge -> 405"
echo "(/merge answers POST only, so 405 from a GET means it is still routed correctly.)"
