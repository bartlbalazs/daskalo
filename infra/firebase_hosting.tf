# ---------------------------------------------------------------------------
# Firebase Hosting site and Web App registration.
#
# Terraform creates the Firebase site resource so it exists before
# `deploy.sh --hosting` runs `firebase deploy --only hosting`.
# Actual content deployment is done by the CLI (not null_resource).
# ---------------------------------------------------------------------------

# Register the Firebase Web App (needed to retrieve SDK config values for environment.prod.ts).
resource "google_firebase_web_app" "daskalo" {
  provider     = google-beta
  project      = var.project_id
  display_name = var.firebase_app_display_name

  depends_on = [google_project_service.apis]
}

# Retrieve the Firebase SDK config (apiKey, messagingSenderId, appId, etc.)
data "google_firebase_web_app_config" "daskalo" {
  provider   = google-beta
  project    = var.project_id
  web_app_id = google_firebase_web_app.daskalo.app_id
}

# Create the Firebase Hosting site resource.
# The site ID is derived from the project ID to match the default Firebase site name.
resource "google_firebase_hosting_site" "daskalo" {
  provider = google-beta
  project  = var.project_id
  site_id  = var.project_id

  depends_on = [google_firebase_web_app.daskalo]
}
