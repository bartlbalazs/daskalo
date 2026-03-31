#!/usr/bin/env bash
# deploy.sh — Orchestrates infrastructure and frontend deployments.
#
# Flags:
#   --infra     Build backend source zip + run terraform apply
#   --hosting   Generate environment.prod.ts + ng build + firebase deploy
#   (no flags)  Both --infra and --hosting in sequence
#
# Prerequisites:
#   - gcloud CLI authenticated
#   - terraform CLI installed
#   - firebase CLI installed (`npm install -g firebase-tools`)
#   - node / npm installed (for Angular build)
#   - infra/terraform.tfvars filled in (copy from infra/terraform.tfvars.example)
#
# Usage:
#   ./deploy.sh                 # full deploy (infra + hosting)
#   ./deploy.sh --infra         # infrastructure only
#   ./deploy.sh --hosting       # frontend/hosting only (requires prior --infra run)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
INFRA_DIR="${REPO_ROOT}/infra"
BUILD_DIR="${INFRA_DIR}/.build"
BACKEND_DIR="${REPO_ROOT}/backend"
FRONTEND_DIR="${REPO_ROOT}/frontend"
ENV_PROD_TS="${FRONTEND_DIR}/src/environments/environment.prod.ts"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { echo "[deploy] $*"; }
die()  { echo "[deploy] ERROR: $*" >&2; exit 1; }
step() { echo ""; echo "[deploy] ======================================================"; echo "[deploy] $*"; echo "[deploy] ======================================================"; }

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
DO_INFRA=false
DO_HOSTING=false

if [[ $# -eq 0 ]]; then
  DO_INFRA=true
  DO_HOSTING=true
fi

for arg in "$@"; do
  case "$arg" in
    --infra)    DO_INFRA=true ;;
    --hosting)  DO_HOSTING=true ;;
    *)          die "Unknown flag: $arg. Valid flags: --infra, --hosting" ;;
  esac
done

# ---------------------------------------------------------------------------
# terraform.tfvars must exist
# ---------------------------------------------------------------------------
if [[ ! -f "${INFRA_DIR}/terraform.tfvars" ]]; then
  die "infra/terraform.tfvars not found. Copy infra/terraform.tfvars.example and fill in values."
fi

# ---------------------------------------------------------------------------
# STEP 1: Infrastructure (--infra)
# ---------------------------------------------------------------------------
if [[ "$DO_INFRA" == true ]]; then
  step "INFRA: Building backend source zip"

  mkdir -p "${BUILD_DIR}"
  BACKEND_ZIP="${BUILD_DIR}/backend.zip"

  # Build zip from the backend directory, excluding dev-only files.
  # The zip contains all Python source files needed by Cloud Functions.
  (
    cd "${BACKEND_DIR}"
    zip -r "${BACKEND_ZIP}" . \
      --exclude "*.pyc" \
      --exclude "*/__pycache__/*" \
      --exclude ".venv/*" \
      --exclude "tests/*" \
      --exclude ".python-version" \
      --exclude "*.egg-info/*" \
      --exclude ".ruff_cache/*" \
      --exclude "main.py" \
      --exclude ".env*" \
      > /dev/null
  )
  log "  Backend zip: ${BACKEND_ZIP} ($(du -sh "${BACKEND_ZIP}" | cut -f1))"

  step "INFRA: Running terraform plan"
  terraform -chdir="${INFRA_DIR}" plan -out="${BUILD_DIR}/tfplan"

  echo ""
  read -r -p "[deploy] Apply the plan above? [y/N] " CONFIRM
  if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    log "Aborted by user."
    exit 0
  fi

  step "INFRA: Running terraform apply"
  terraform -chdir="${INFRA_DIR}" apply "${BUILD_DIR}/tfplan"

  log "Terraform apply complete."
fi

# ---------------------------------------------------------------------------
# STEP 2: Hosting (--hosting)
# ---------------------------------------------------------------------------
if [[ "$DO_HOSTING" == true ]]; then
  step "HOSTING: Reading Terraform outputs"

  # Read outputs — these were set by the last terraform apply.
  API_GATEWAY_URL=$(terraform -chdir="${INFRA_DIR}" output -raw api_gateway_url)
  FIREBASE_API_KEY=$(terraform -chdir="${INFRA_DIR}" output -raw firebase_api_key)
  FIREBASE_MESSAGING_SENDER_ID=$(terraform -chdir="${INFRA_DIR}" output -raw firebase_messaging_sender_id)
  FIREBASE_WEB_APP_ID=$(terraform -chdir="${INFRA_DIR}" output -raw firebase_web_app_id)
  PUBLIC_ASSETS_BUCKET=$(terraform -chdir="${INFRA_DIR}" output -raw public_assets_bucket_name)

  # Derive project_id and other Firebase config fields from tfvars.
  PROJECT_ID=$(terraform -chdir="${INFRA_DIR}" output -json 2>/dev/null | python3 -c "
import sys, json
# fallback: read project_id from terraform.tfvars
" 2>/dev/null || true)

  # Simpler: read project_id directly from terraform.tfvars.
  PROJECT_ID=$(grep -E '^project_id\s*=' "${INFRA_DIR}/terraform.tfvars" | sed 's/.*=\s*"\(.*\)"/\1/')

  if [[ -z "$PROJECT_ID" ]]; then
    die "Could not determine project_id from infra/terraform.tfvars."
  fi

  # Read Firestore database name from terraform.tfvars (defaults to "(default)" if absent).
  DB_NAME=$(grep -E '^db_name\s*=' "${INFRA_DIR}/terraform.tfvars" | sed 's/.*=\s*"\(.*\)"/\1/' || true)
  DB_NAME="${DB_NAME:-(default)}"

  log "  API Gateway URL:  ${API_GATEWAY_URL}"
  log "  Project ID:       ${PROJECT_ID}"
  log "  Firestore DB:     ${DB_NAME}"

  step "HOSTING: Generating environment.prod.ts"
  cat > "${ENV_PROD_TS}" <<EOF
// src/environments/environment.prod.ts — PRODUCTION
// Auto-generated by deploy.sh — do not edit manually.
// Re-run: ./deploy.sh --hosting

export const environment = {
  production: true,
  useEmulators: false,
  // API Gateway URL — all Cloud Function calls go through here.
  evaluateAttemptUrl: '${API_GATEWAY_URL}/evaluate',
  completeChapterUrl: '${API_GATEWAY_URL}/complete-chapter',
  completePracticeUrl: '${API_GATEWAY_URL}/complete-practice',
  addOwnWordUrl: '${API_GATEWAY_URL}/add-own-word',
  firestoreDb: '${DB_NAME}',
  firebase: {
    apiKey: '${FIREBASE_API_KEY}',
    authDomain: '${PROJECT_ID}.firebaseapp.com',
    projectId: '${PROJECT_ID}',
    storageBucket: '${PUBLIC_ASSETS_BUCKET}',
    messagingSenderId: '${FIREBASE_MESSAGING_SENDER_ID}',
    appId: '${FIREBASE_WEB_APP_ID}',
  },
};
EOF
  log "  Written: ${ENV_PROD_TS}"

  step "HOSTING: Building Angular app (production)"
  (
    cd "${FRONTEND_DIR}"
    npm run build -- --configuration production
  )

  step "HOSTING: Deploying to Firebase Hosting + Firestore rules + Storage rules"

  # Generate a temporary firebase.json with the storage bucket injected.
  # The committed firebase.json has no bucket (used by the local emulator).
  # The Firebase CLI requires an explicit bucket when no project-level default
  # bucket exists, so we provide one here at deploy time.
  FIREBASE_DEPLOY_JSON="${FRONTEND_DIR}/firebase.deploy.json"
  python3 - <<PYEOF
import json
with open("${FRONTEND_DIR}/firebase.json") as f:
    cfg = json.load(f)
cfg["storage"] = [{"bucket": "${PUBLIC_ASSETS_BUCKET}", "rules": cfg["storage"]["rules"]}]
cfg["firestore"]["database"] = "${DB_NAME}"
with open("${FIREBASE_DEPLOY_JSON}", "w") as f:
    json.dump(cfg, f, indent=2)
PYEOF

  (
    cd "${FRONTEND_DIR}"
    firebase deploy \
      --only hosting,firestore,storage \
      --config firebase.deploy.json \
      --project "${PROJECT_ID}"
  )

  rm -f "${FIREBASE_DEPLOY_JSON}"

  HOSTING_URL=$(terraform -chdir="${INFRA_DIR}" output -raw hosting_default_url 2>/dev/null || echo "https://${PROJECT_ID}.web.app")
  log ""
  log "Deployment complete."
  log "  Hosting URL:     ${HOSTING_URL}"
  log "  API Gateway URL: ${API_GATEWAY_URL}"
fi

log ""
log "Done."
