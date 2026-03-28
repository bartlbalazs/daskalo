# ---------------------------------------------------------------------------
# Service Accounts and IAM bindings.
#
# Two dedicated service accounts:
#   api-gateway-sa  — used by API Gateway to invoke Cloud Functions via Cloud Run
#   cf-runtime-sa   — attached to both Cloud Functions at runtime
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 1. API Gateway service account
# ---------------------------------------------------------------------------

resource "google_service_account" "api_gateway_sa" {
  project      = var.project_id
  account_id   = "api-gateway-sa"
  display_name = "API Gateway → Cloud Functions invoker"

  depends_on = [google_project_service.apis]
}

# Allow API Gateway SA to invoke Cloud Run services (CF2 runs on Cloud Run).
resource "google_project_iam_member" "api_gateway_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.api_gateway_sa.email}"
}

# ---------------------------------------------------------------------------
# 2. Cloud Function runtime service account
# ---------------------------------------------------------------------------

resource "google_service_account" "cf_runtime_sa" {
  project      = var.project_id
  account_id   = "cf-runtime-sa"
  display_name = "Cloud Function runtime SA (Vertex AI, Firestore, Speech)"

  depends_on = [google_project_service.apis]
}

# Vertex AI — needed to call Gemini models.
resource "google_project_iam_member" "cf_runtime_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.cf_runtime_sa.email}"
}

# Firestore — read/write exercise attempts, chapters, users.
resource "google_project_iam_member" "cf_runtime_datastore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.cf_runtime_sa.email}"
}

# Cloud Speech-to-Text — used by pronunciation evaluation.
resource "google_project_iam_member" "cf_runtime_speech_client" {
  project = var.project_id
  role    = "roles/speech.client"
  member  = "serviceAccount:${google_service_account.cf_runtime_sa.email}"
}

# Firebase Auth Admin — needed to verify Firebase ID tokens via Admin SDK.
resource "google_project_iam_member" "cf_runtime_firebase_sdk_admin" {
  project = var.project_id
  role    = "roles/firebase.sdkAdminServiceAgent"
  member  = "serviceAccount:${google_service_account.cf_runtime_sa.email}"
}

# Read objects from the Cloud Functions source bucket.
resource "google_project_iam_member" "cf_runtime_storage_object_viewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.cf_runtime_sa.email}"
}

# Write own-word audio files to the public assets bucket (add-own-word function).
resource "google_project_iam_member" "cf_runtime_storage_object_creator" {
  project = var.project_id
  role    = "roles/storage.objectCreator"
  member  = "serviceAccount:${google_service_account.cf_runtime_sa.email}"
}
