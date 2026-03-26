# ---------------------------------------------------------------------------
# Firestore database — NATIVE mode (required for real-time listeners).
# Only one (default) database is provisioned. The name is configurable via
# var.db_name (defaults to "(default)").
# ---------------------------------------------------------------------------

resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = var.db_name
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  # Prevent accidental data loss on `terraform destroy`.
  deletion_policy = "DELETE"

  depends_on = [google_project_service.apis]
}
