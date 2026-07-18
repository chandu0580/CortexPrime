#!/usr/bin/env bash
# =============================================================================
# CortexPrime — Air-Gapped Bundle Generator
# =============================================================================
# Generates a portable tar.gz bundle of all Docker images for environments
# without internet access. Produces:
#   - images/cortexprime-airgap.tar.gz   — all images in a single archive
#   - images/*.tar.gz                    — individual image archives
#   - MANIFEST                           — SHA-256 checksums
#   - load-images.sh                     — one-command loader script
#   - README.txt                         — usage instructions
# =============================================================================

set -euo pipefail

BUNDLE_DIR="./cortexprime-airgap-bundle-$(date +%Y%m%d)"
IMAGES_DIR="$BUNDLE_DIR/images"

# ── Images from docker-compose.airgap.yml ──────────────────────────────────
IMAGES=(
  "cortexprime-backend:airgap"
  "cortexprime-frontend:airgap"
  "cortexprime-worker:airgap"
  "pgvector/pgvector:pg16"
  "redis:7.2-alpine"
  "rabbitmq:3.13-management-alpine"
  "neo4j:5.18-community"
  "ollama/ollama:latest"
  "minio/minio:RELEASE.2024-07-16T23-46-41Z"
)

# ── Step 1 — Create bundle directory structure ─────────────────────────────
mkdir -p "$IMAGES_DIR"

echo "========================================================================"
echo " CortexPrime — Air-Gapped Bundle Generator"
echo " Bundle  : $BUNDLE_DIR"
echo " Images  : ${#IMAGES[@]}"
echo "========================================================================"

# ── Step 2 — Pull all images ───────────────────────────────────────────────
echo ""
echo ">>> Pulling images..."
for img in "${IMAGES[@]}"; do
  echo "  Pulling  $img ..."
  docker pull "$img"
done

# ── Step 3 — Save as a combined archive ────────────────────────────────────
echo ""
echo ">>> Saving combined archive..."
COMBINED="$IMAGES_DIR/cortexprime-airgap.tar.gz"
docker save "${IMAGES[@]}" | gzip > "$COMBINED"
echo "  Created  $COMBINED  ($(du -sh "$COMBINED" | cut -f1))"

# ── Step 4 — Save individual images (for selective loading) ────────────────
echo ""
echo ">>> Saving individual archives..."
for img in "${IMAGES[@]}"; do
  safe_name=$(echo "$img" | tr '/:' '__')
  archive="$IMAGES_DIR/$safe_name.tar.gz"
  echo "  Saving   $img -> $(basename "$archive") ..."
  docker save "$img" | gzip > "$archive"
done

# ── Step 5 — Generate MANIFEST with checksums ──────────────────────────────
echo ""
echo ">>> Generating MANIFEST..."
{
  echo "# CortexPrime Air-Gap Bundle — SHA-256 Manifest"
  echo "# Generated: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "# Images: ${#IMAGES[@]}"
  echo ""
  echo "sha256sum:"
  sha256sum "$IMAGES_DIR/"*.tar.gz
} > "$BUNDLE_DIR/MANIFEST"
echo "  Created  $BUNDLE_DIR/MANIFEST"

# ── Step 6 — Generate load-images.sh loader script ─────────────────────────
echo ""
echo ">>> Generating load-images.sh..."
cat > "$BUNDLE_DIR/load-images.sh" << 'LOADEOF'
#!/usr/bin/env bash
# =============================================================================
# CortexPrime — Load Air-Gapped Images
# =============================================================================
# Loads all Docker images from the air-gap bundle.
# Usage: bash load-images.sh [--verbose]
# =============================================================================

set -euo pipefail

VERBOSE=false
if [[ "${1:-}" == "--verbose" ]]; then
  VERBOSE=true
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGES_DIR="$SCRIPT_DIR/images"

echo "========================================================================"
echo " CortexPrime — Loading Air-Gapped Images"
echo " Source : $IMAGES_DIR"
echo "========================================================================"

# Validate checksums first
if command -v sha256sum &> /dev/null; then
  echo ""
  echo ">>> Verifying checksums..."
  sha256sum -c "$SCRIPT_DIR/MANIFEST" 2>/dev/null || {
    echo "WARNING: Checksum verification failed. Aborting."
    exit 1
  }
  echo "  All checksums OK."
fi

# Load combined archive (fastest)
COMBINED="$IMAGES_DIR/cortexprime-airgap.tar.gz"
if [ -f "$COMBINED" ]; then
  echo ""
  echo ">>> Loading combined archive..."
  if [ "$VERBOSE" = true ]; then
    docker load < "$COMBINED"
  else
    echo -n "  Loading ... "
    LOAD_OUTPUT=$(docker load < "$COMBINED" 2>&1)
    LOADED_COUNT=$(echo "$LOAD_OUTPUT" | grep -c "^Loaded image")
    echo "done ($LOADED_COUNT images loaded)."
  fi
else
  # Fall back to individual archives
  echo ""
  echo ">>> Loading individual archives..."
  for archive in "$IMAGES_DIR"/*.tar.gz; do
    [ -f "$archive" ] || continue
    name=$(basename "$archive" .tar.gz)
    echo -n "  Loading $name ... "
    docker load < "$archive" > /dev/null 2>&1
    echo "done."
  done
fi

echo ""
echo "========================================================================"
echo " All images loaded successfully."
echo " You can now run:  docker compose -f docker-compose.airgap.yml up -d"
echo "========================================================================"
LOADEOF

chmod +x "$BUNDLE_DIR/load-images.sh"
echo "  Created  $BUNDLE_DIR/load-images.sh"

# ── Step 7 — Generate README.txt ───────────────────────────────────────────
echo ""
echo ">>> Generating README.txt..."
cat > "$BUNDLE_DIR/README.txt" << 'READMEEOF'
=============================================================================
 CortexPrime — Air-Gapped Deployment Bundle
=============================================================================

 This bundle contains all Docker images required to run CortexPrime in an
 environment with NO internet access.

-----------------------------------------------------------------------------
 Contents
-----------------------------------------------------------------------------

   images/
     cortexprime-airgap.tar.gz      Combined archive of all images
     <image_name>.tar.gz            Individual image archives

   MANIFEST                         SHA-256 checksums for all archives
   load-images.sh                   One-command loader script
   README.txt                       This file

-----------------------------------------------------------------------------
 Quick Start
-----------------------------------------------------------------------------

 1. Copy this bundle to the air-gapped machine:

       scp -r cortexprime-airgap-bundle-* user@airgap-host:/tmp/

 2. On the air-gapped machine, load all images:

       cd /tmp/cortexprime-airgap-bundle-*
       bash load-images.sh

 3. Verify images are loaded:

       docker images

 4. Start the stack:

       docker compose -f docker-compose.airgap.yml --env-file .env up -d

-----------------------------------------------------------------------------
 Included Images
-----------------------------------------------------------------------------

   cortexprime-backend:airgap
   cortexprime-frontend:airgap
   cortexprime-worker:airgap
   pgvector/pgvector:pg16
   redis:7.2-alpine
   rabbitmq:3.13-management-alpine
   neo4j:5.18-community
   ollama/ollama:latest
   minio/minio:RELEASE.2024-07-16T23-46-41Z

-----------------------------------------------------------------------------
 Selective Loading
-----------------------------------------------------------------------------

 To load only specific images, use docker load directly:

   docker load < images/redis_7.2-alpine.tar.gz
   docker load < images/pgvector_pgvector_pg16.tar.gz

-----------------------------------------------------------------------------
 Checksums
-----------------------------------------------------------------------------

 Verify integrity at any time:

   sha256sum -c MANIFEST

-----------------------------------------------------------------------------
 Requirements
-----------------------------------------------------------------------------

   - Docker >= 24.x
   - At least 20 GB free disk space for images
   - bash, sha256sum (coreutils)

=============================================================================
READMEEOF

echo ""
echo "========================================================================"
echo " Bundle created at: $BUNDLE_DIR"
echo " Size             : $(du -sh "$BUNDLE_DIR" | cut -f1)"
echo " To load images   : cd $BUNDLE_DIR && bash load-images.sh"
echo "========================================================================"
