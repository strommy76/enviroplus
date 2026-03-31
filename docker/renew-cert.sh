#!/usr/bin/env bash
# Renews the Tailscale TLS cert for Grafana and restarts the container.
# Run via cron: 0 3 1 * * /home/pistrommy/projects/enviroplus/docker/renew-cert.sh

set -euo pipefail

HOSTNAME="bspilhx.tail32dc7b.ts.net"
TLS_DIR="$(dirname "$0")/tls"
COMPOSE_DIR="$(dirname "$0")"

tailscale cert \
  --cert-file "${TLS_DIR}/${HOSTNAME}.crt" \
  --key-file  "${TLS_DIR}/${HOSTNAME}.key" \
  "${HOSTNAME}"

docker compose -f "${COMPOSE_DIR}/docker-compose.yml" \
  --env-file "${COMPOSE_DIR}/../.env" \
  restart grafana
