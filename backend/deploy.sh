#!/bin/bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Daskalo — Cloud Functions deployment script
#
# Deploys two 2nd-gen Cloud Functions:
#   1. evaluate-attempt  — AI exercise evaluation (fn_evaluate.py)
#   2. complete-chapter  — Chapter completion / grammar book (fn_complete_chapter.py)
#
# Both functions use HTTP triggers with --allow-unauthenticated.
# Auth is enforced in code via Firebase ID token verification.
#
# Prerequisites:
#   - backend/.env.deploy exists (copy from .env.deploy.example and fill in)
#   - gcloud CLI authenticated with sufficient permissions
#
# Usage:
#   ./deploy.sh           # deploy both functions
#   ./deploy.sh --infra   # provision GCP APIs + GCS bucket first, then deploy
#   ./deploy.sh --help
# ---------------------------------------------------------------------------

# --- Load Configuration ---
ENV_FILE=".env.deploy"
if [[ -f "$ENV_FILE" ]]; then
  export $(grep -v '^#' "$ENV_FILE" | xargs)
else
  echo "Error: $ENV_FILE not found."
  echo "Please copy .env.deploy.example to $ENV_FILE and fill in your details."
  exit 1
fi

# Ensure required variables are set
: "${PROJECT_ID:?Variable PROJECT_ID is not set in $ENV_FILE}"
: "${REGION:?Variable REGION is not set in $ENV_FILE}"
: "${PUBLIC_ASSETS_BUCKET:?Variable PUBLIC_ASSETS_BUCKET is not set in $ENV_FILE}"
: "${DB_NAME:?Variable DB_NAME is not set in $ENV_FILE}"

# --- Usage ---
usage() {
  cat <<EOF
Usage: ./deploy.sh [OPTIONS]

Deploy Daskalo Cloud Functions to GCP.

Options:
  --infra             Provision GCP infrastructure (APIs, GCS bucket) before deploying
  --help              Show this help message and exit

GCP resources:
  Project:              $PROJECT_ID
  Region:               $REGION
  Public Assets Bucket: $PUBLIC_ASSETS_BUCKET
  Functions:            evaluate-attempt, complete-chapter
EOF
}

INFRA=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --infra) INFRA=true; shift ;;
    --help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

echo "=== Deploying Daskalo Cloud Functions to project: $PROJECT_ID ==="

# ---------------------------------------------------------------------------
# Infrastructure provisioning (one-time setup)
# ---------------------------------------------------------------------------

if [[ "$INFRA" == true ]]; then
  echo "--- Enabling required GCP APIs ---"
  gcloud services enable \
    firestore.googleapis.com \
    cloudfunctions.googleapis.com \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    storage-component.googleapis.com \
    aiplatform.googleapis.com \
    --project="$PROJECT_ID"

  echo "--- Checking Public Assets GCS bucket ---"
  if ! gsutil ls -b "gs://$PUBLIC_ASSETS_BUCKET" &>/dev/null; then
    echo "Creating GCS bucket '$PUBLIC_ASSETS_BUCKET'..."
    gsutil mb -l "$REGION" -p "$PROJECT_ID" "gs://$PUBLIC_ASSETS_BUCKET"
  fi
  gsutil iam ch allUsers:objectViewer "gs://$PUBLIC_ASSETS_BUCKET"
fi

# ---------------------------------------------------------------------------
# Shared deploy flags
# ---------------------------------------------------------------------------

COMMON_FLAGS=(
  --gen2
  --runtime=python311
  --region="$REGION"
  --trigger-http
  --allow-unauthenticated
  --timeout=120s
  --memory=512Mi
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,FIRESTORE_DATABASE=$DB_NAME,PUBLIC_ASSETS_BUCKET=$PUBLIC_ASSETS_BUCKET"
  --project="$PROJECT_ID"
  --quiet
)

# ---------------------------------------------------------------------------
# 1. evaluate-attempt
# ---------------------------------------------------------------------------

echo "--- Deploying evaluate-attempt ---"
gcloud functions deploy evaluate-attempt \
  "${COMMON_FLAGS[@]}" \
  --entry-point=evaluate_attempt_fn \
  --source=.

echo "--- evaluate-attempt deployed ---"
gcloud functions describe evaluate-attempt \
  --gen2 \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(serviceConfig.uri)'

# ---------------------------------------------------------------------------
# 2. complete-chapter
# ---------------------------------------------------------------------------

echo "--- Deploying complete-chapter ---"
gcloud functions deploy complete-chapter \
  "${COMMON_FLAGS[@]}" \
  --timeout=180s \
  --memory=512Mi \
  --entry-point=complete_chapter_fn \
  --source=.

echo "--- complete-chapter deployed ---"
gcloud functions describe complete-chapter \
  --gen2 \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(serviceConfig.uri)'

echo ""
echo "=== Deployment complete ==="
echo "Update frontend/src/environments/environment.prod.ts with the URLs printed above."
