#!/usr/bin/env bash
# ==============================================================
# CORTEXPRIME — TLS Certificate Generator
#
# Generates self-signed certificates for local / staging use.
# For production, replace with Let's Encrypt (see below).
#
# Usage:
#   bash scripts/generate-certs.sh [DOMAIN]
#
# DOMAIN defaults to "localhost".
#
# Output:
#   infra/nginx/certs/cert.pem
#   infra/nginx/certs/key.pem
#
# Let's Encrypt (production):
#   certbot certonly --webroot \
#     -w /var/www/certbot \
#     -d yourdomain.com \
#     --email admin@yourdomain.com \
#     --agree-tos --no-eff-email
#   # Then symlink or copy:
#   cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem infra/nginx/certs/cert.pem
#   cp /etc/letsencrypt/live/yourdomain.com/privkey.pem   infra/nginx/certs/key.pem
# ==============================================================

set -euo pipefail

DOMAIN="${1:-localhost}"
CERT_DIR="$(dirname "$0")/../infra/nginx/certs"

mkdir -p "$CERT_DIR"

echo "Generating self-signed TLS certificate for: $DOMAIN"
echo "Output directory: $CERT_DIR"

openssl req -x509 \
  -nodes \
  -newkey rsa:4096 \
  -keyout "$CERT_DIR/key.pem" \
  -out    "$CERT_DIR/cert.pem" \
  -days   365 \
  -subj   "/C=US/ST=State/L=City/O=CortexPrime/CN=$DOMAIN" \
  -addext "subjectAltName=DNS:$DOMAIN,DNS:www.$DOMAIN,IP:127.0.0.1"

chmod 600 "$CERT_DIR/key.pem"
chmod 644 "$CERT_DIR/cert.pem"

echo ""
echo "✅ Certificates written:"
echo "   cert: $CERT_DIR/cert.pem"
echo "   key:  $CERT_DIR/key.pem"
echo ""
echo "NOTE: These are self-signed. Browsers will show a warning."
echo "      Replace with Let's Encrypt certs for public deployments."
