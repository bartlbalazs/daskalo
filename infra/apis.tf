# ---------------------------------------------------------------------------
# Enable all required GCP APIs.
# disable_on_destroy = false prevents accidental API disabling on `terraform destroy`.
# ---------------------------------------------------------------------------

locals {
  required_apis = [
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "firestore.googleapis.com",
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "storage.googleapis.com",
    "aiplatform.googleapis.com",
    "speech.googleapis.com",
    "texttospeech.googleapis.com",
    "apigateway.googleapis.com",
    "servicecontrol.googleapis.com",
    "servicemanagement.googleapis.com",
    "firebase.googleapis.com",
    "firebasestorage.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.required_apis)

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}
