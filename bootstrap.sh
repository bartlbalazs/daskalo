#!/usr/bin/env bash
# bootstrap.sh — One-time setup for Terraform remote state and Firebase Storage.
#
# Run this ONCE before the first `terraform apply` to:
#   1. Enable the minimal GCP APIs needed for Terraform itself.
#   2. Create the GCS bucket that stores Terraform state.
#   3. Run `terraform init` pointing at that bucket.
#   4. Initialize Firebase Storage at the project level (creates the default bucket
#      so that `firebase deploy --only storage` works in subsequent deploys).
#
# Usage:
#   ./bootstrap.sh
#
# Prerequisites:
#   - gcloud CLI installed and authenticated (`gcloud auth login`)
#   - PROJECT_ID set in this script or as an environment variable
#   - Sufficient permissions: storage.buckets.create, serviceusage.services.enable

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — edit these or override via environment variables.
# ---------------------------------------------------------------------------
PROJECT_ID="${PROJECT_ID:-}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "ERROR: PROJECT_ID is not set."
  echo "  Set it in the environment:  export PROJECT_ID=my-gcp-project-id"
  echo "  Or edit bootstrap.sh directly."
  exit 1
fi

REGION="${REGION:-europe-west1}"
STATE_BUCKET="${PROJECT_ID}-daskalo-terraform-state"
INFRA_DIR="$(cd "$(dirname "$0")/infra" && pwd)"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() { echo "[bootstrap] $*"; }
die() { echo "[bootstrap] ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Set the active project
# ---------------------------------------------------------------------------
log "Setting active GCP project to: ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}"

# ---------------------------------------------------------------------------
# 2. Enable bootstrap APIs (just enough for Terraform to function)
# ---------------------------------------------------------------------------
BOOTSTRAP_APIS=(
  "cloudresourcemanager.googleapis.com"
  "iam.googleapis.com"
  "storage.googleapis.com"
  "serviceusage.googleapis.com"
)

log "Enabling bootstrap APIs..."
for api in "${BOOTSTRAP_APIS[@]}"; do
  log "  Enabling: ${api}"
  gcloud services enable "${api}" --project="${PROJECT_ID}" --quiet
done

# ---------------------------------------------------------------------------
# 3. Create the Terraform state GCS bucket (idempotent)
# ---------------------------------------------------------------------------
log "Checking for Terraform state bucket: gs://${STATE_BUCKET}"
if gsutil ls -b "gs://${STATE_BUCKET}" &>/dev/null; then
  log "  Bucket already exists — skipping creation."
else
  log "  Creating bucket gs://${STATE_BUCKET} in ${REGION}..."
  gsutil mb -p "${PROJECT_ID}" -l "${REGION}" -b on "gs://${STATE_BUCKET}"
  log "  Enabling versioning on state bucket..."
  gsutil versioning set on "gs://${STATE_BUCKET}"
  log "  Bucket created."
fi

# ---------------------------------------------------------------------------
# 4. terraform init with backend config pointing at the state bucket
# ---------------------------------------------------------------------------
log "Running terraform init in ${INFRA_DIR}..."
terraform -chdir="${INFRA_DIR}" init \
  -backend-config="bucket=${STATE_BUCKET}" \
  -reconfigure

# ---------------------------------------------------------------------------
# 5. Initialize Firebase Storage at the project level (idempotent)
# ---------------------------------------------------------------------------
# The Firebase CLI (`firebase deploy --only storage`) requires a project-level
# "default" Firebase Storage bucket to exist. This is normally created by
# clicking "Get Started" in the Firebase Console. We do it here via the REST
# API so it is part of the reproducible setup.
#
# This creates an empty default bucket named ${PROJECT_ID}.firebasestorage.app
# and marks Firebase Storage as "set up" on the project. The actual app assets
# live in the custom bucket created by Terraform (public_assets_bucket_name).
#
# The call is idempotent — re-running when the bucket already exists returns a
# 409 Conflict which we treat as success.
log "Ensuring Firebase Storage default bucket is initialized..."
HTTP_STATUS=$(curl -s -o /tmp/firebase_storage_init.json -w "%{http_code}" \
  -X POST \
  "https://firebasestorage.googleapis.com/v1alpha/projects/${PROJECT_ID}/defaultBucket" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d "{\"location\": \"${REGION}\"}")

if [[ "$HTTP_STATUS" == "200" ]]; then
  log "  Firebase Storage default bucket created successfully."
elif [[ "$HTTP_STATUS" == "409" ]]; then
  log "  Firebase Storage default bucket already exists — skipping."
else
  log "  WARNING: Unexpected response (HTTP ${HTTP_STATUS}):"
  cat /tmp/firebase_storage_init.json
  log "  You may need to initialize Firebase Storage manually via the Firebase Console."
fi

log ""
log "Bootstrap complete."
log "Next steps:"
log "  1. Copy infra/terraform.tfvars.example → infra/terraform.tfvars and fill in values."
log "  2. Run:  ./deploy.sh --infra"
