# ---------------------------------------------------------------------------
# API Gateway — validates Firebase JWTs at the edge and proxies to Cloud
# Functions. Required because the org policy denies unauthenticated CF invocations.
#
# Resources:
#   google_api_gateway_api          — logical API resource
#   google_api_gateway_api_config   — versioned OpenAPI 2.0 spec (immutable)
#   google_api_gateway_gateway      — deployed gateway instance with a public URL
# ---------------------------------------------------------------------------

resource "google_api_gateway_api" "daskalo" {
  provider     = google-beta
  project      = var.project_id
  api_id       = "daskalo-api"
  display_name = "Daskalo API"

  depends_on = [google_project_service.apis]
}

# API configs are immutable — a new one is created on every `terraform apply`
# when the spec changes (tracked by the md5 of the rendered template).
resource "google_api_gateway_api_config" "daskalo" {
  provider      = google-beta
  project       = var.project_id
  api           = google_api_gateway_api.daskalo.api_id
  api_config_id = "daskalo-config-${substr(md5(local.openapi_spec), 0, 8)}"
  display_name  = "Daskalo API config"

  openapi_documents {
    document {
      path     = "openapi.yaml"
      contents = base64encode(local.openapi_spec)
    }
  }

  gateway_config {
    backend_config {
      google_service_account = google_service_account.api_gateway_sa.email
    }
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    google_cloudfunctions2_function.evaluate_attempt,
    google_cloudfunctions2_function.complete_chapter,
    google_cloudfunctions2_function.add_own_word,
    google_cloudfunctions2_function.complete_practice,
  ]
}

resource "google_api_gateway_gateway" "daskalo" {
  provider     = google-beta
  project      = var.project_id
  region       = var.region
  api_config   = google_api_gateway_api_config.daskalo.id
  gateway_id   = "daskalo-gateway"
  display_name = "Daskalo API Gateway"

  depends_on = [google_api_gateway_api_config.daskalo]
}

# ---------------------------------------------------------------------------
# Local: render the OpenAPI template with actual Cloud Function URLs.
# ---------------------------------------------------------------------------

locals {
  openapi_spec = templatefile("${path.module}/openapi.yaml.tpl", {
    project_id            = var.project_id
    evaluate_attempt_url  = google_cloudfunctions2_function.evaluate_attempt.service_config[0].uri
    complete_chapter_url  = google_cloudfunctions2_function.complete_chapter.service_config[0].uri
    add_own_word_url      = google_cloudfunctions2_function.add_own_word.service_config[0].uri
    complete_practice_url = google_cloudfunctions2_function.complete_practice.service_config[0].uri
  })
}
