# ---------------------------------------------------------------------------
# Cloud Functions (2nd gen) — evaluate-attempt and complete-chapter.
#
# Source zip is built by deploy.sh (--infra) and placed at:
#   infra/.build/backend.zip
#
# The zip is uploaded to a private GCS bucket and referenced by both functions.
# Both functions are deployed with --no-allow-unauthenticated (org policy).
# The API Gateway service account (api-gateway-sa) holds roles/run.invoker and
# is the only identity permitted to invoke them.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Private GCS bucket for Cloud Function source archives.
# ---------------------------------------------------------------------------

resource "google_storage_bucket" "cf_source" {
  name          = "${var.project_id}-cf-source"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Upload the backend source zip (built by deploy.sh before terraform apply).
# The object is replaced on every deploy because the source_hash triggers
# a new Cloud Function revision only when the zip content actually changes.
# ---------------------------------------------------------------------------

resource "google_storage_bucket_object" "backend_zip" {
  name   = "backend-${filemd5("${path.module}/.build/backend.zip")}.zip"
  bucket = google_storage_bucket.cf_source.name
  source = "${path.module}/.build/backend.zip"
}

# ---------------------------------------------------------------------------
# evaluate-attempt Cloud Function
# ---------------------------------------------------------------------------

resource "google_cloudfunctions2_function" "evaluate_attempt" {
  project     = var.project_id
  location    = var.region
  name        = "evaluate-attempt"
  description = "Evaluates an AI-graded exercise attempt using Gemini."

  build_config {
    runtime     = "python311"
    entry_point = "evaluate_attempt_fn"

    environment_variables = {
      GOOGLE_FUNCTION_SOURCE = "fn_evaluate.py"
    }

    source {
      storage_source {
        bucket = google_storage_bucket.cf_source.name
        object = google_storage_bucket_object.backend_zip.name
      }
    }
  }

  service_config {
    available_memory               = var.evaluate_function_memory
    available_cpu                  = var.evaluate_function_cpu
    timeout_seconds                = var.evaluate_function_timeout
    max_instance_count             = 2
    min_instance_count             = 0
    all_traffic_on_latest_revision = true

    service_account_email = google_service_account.cf_runtime_sa.email

    environment_variables = {
      GOOGLE_CLOUD_PROJECT = var.project_id
      FIRESTORE_DB         = var.db_name
    }
  }

  depends_on = [
    google_project_service.apis,
    google_storage_bucket_object.backend_zip,
  ]
}

# Deny unauthenticated invocations explicitly (defence-in-depth; org policy also enforces this).
resource "google_cloud_run_service_iam_member" "evaluate_attempt_no_public" {
  project  = var.project_id
  location = var.region
  service  = google_cloudfunctions2_function.evaluate_attempt.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.api_gateway_sa.email}"
}

# ---------------------------------------------------------------------------
# complete-chapter Cloud Function
# ---------------------------------------------------------------------------

resource "google_cloudfunctions2_function" "complete_chapter" {
  project     = var.project_id
  location    = var.region
  name        = "complete-chapter"
  description = "Generates a progress summary and updates user progress in Firestore."

  build_config {
    runtime     = "python311"
    entry_point = "complete_chapter_fn"

    environment_variables = {
      GOOGLE_FUNCTION_SOURCE = "fn_complete_chapter.py"
    }

    source {
      storage_source {
        bucket = google_storage_bucket.cf_source.name
        object = google_storage_bucket_object.backend_zip.name
      }
    }
  }

  service_config {
    available_memory               = var.complete_chapter_function_memory
    available_cpu                  = var.complete_chapter_function_cpu
    timeout_seconds                = var.complete_chapter_function_timeout
    max_instance_count             = 2
    min_instance_count             = 0
    all_traffic_on_latest_revision = true

    service_account_email = google_service_account.cf_runtime_sa.email

    environment_variables = {
      GOOGLE_CLOUD_PROJECT = var.project_id
      FIRESTORE_DB         = var.db_name
    }
  }

  depends_on = [
    google_project_service.apis,
    google_storage_bucket_object.backend_zip,
  ]
}

# Allow API Gateway SA to invoke complete-chapter.
resource "google_cloud_run_service_iam_member" "complete_chapter_invoker" {
  project  = var.project_id
  location = var.region
  service  = google_cloudfunctions2_function.complete_chapter.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.api_gateway_sa.email}"
}

# ---------------------------------------------------------------------------
# add-own-word Cloud Function
# ---------------------------------------------------------------------------

resource "google_cloudfunctions2_function" "add_own_word" {
  project     = var.project_id
  location    = var.region
  name        = "add-own-word"
  description = "Normalises a student's Greek input via Gemini, generates TTS audio, and saves the word card."

  build_config {
    runtime     = "python311"
    entry_point = "add_own_word_fn"

    environment_variables = {
      GOOGLE_FUNCTION_SOURCE = "fn_own_word.py"
    }

    source {
      storage_source {
        bucket = google_storage_bucket.cf_source.name
        object = google_storage_bucket_object.backend_zip.name
      }
    }
  }

  service_config {
    available_memory               = var.add_own_word_function_memory
    available_cpu                  = var.add_own_word_function_cpu
    timeout_seconds                = var.add_own_word_function_timeout
    max_instance_count             = 2
    min_instance_count             = 0
    all_traffic_on_latest_revision = true

    service_account_email = google_service_account.cf_runtime_sa.email

    environment_variables = {
      GOOGLE_CLOUD_PROJECT = var.project_id
      FIRESTORE_DB         = var.db_name
      PUBLIC_ASSETS_BUCKET = var.public_assets_bucket_name
    }
  }

  depends_on = [
    google_project_service.apis,
    google_storage_bucket_object.backend_zip,
  ]
}

# Allow API Gateway SA to invoke add-own-word.
resource "google_cloud_run_service_iam_member" "add_own_word_invoker" {
  project  = var.project_id
  location = var.region
  service  = google_cloudfunctions2_function.add_own_word.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.api_gateway_sa.email}"
}
