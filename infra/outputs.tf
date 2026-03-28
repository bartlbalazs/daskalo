# ---------------------------------------------------------------------------
# Outputs — consumed by deploy.sh to generate environment.prod.ts
# and for operator reference.
# ---------------------------------------------------------------------------

output "api_gateway_url" {
  description = "Public HTTPS base URL of the API Gateway. Used in environment.prod.ts."
  value       = "https://${google_api_gateway_gateway.daskalo.default_hostname}"
}

output "evaluate_function_url" {
  description = "Direct Cloud Run URL of the evaluate-attempt Cloud Function (internal — do not expose publicly)."
  value       = google_cloudfunctions2_function.evaluate_attempt.service_config[0].uri
}

output "complete_chapter_function_url" {
  description = "Direct Cloud Run URL of the complete-chapter Cloud Function (internal — do not expose publicly)."
  value       = google_cloudfunctions2_function.complete_chapter.service_config[0].uri
}

output "add_own_word_function_url" {
  description = "Direct Cloud Run URL of the add-own-word Cloud Function (internal — do not expose publicly)."
  value       = google_cloudfunctions2_function.add_own_word.service_config[0].uri
}

output "hosting_default_url" {
  description = "Default Firebase Hosting URL."
  value       = "https://${google_firebase_hosting_site.daskalo.site_id}.web.app"
}

output "firebase_web_app_id" {
  description = "Firebase Web App ID (used to retrieve SDK config)."
  value       = google_firebase_web_app.daskalo.app_id
}

output "firebase_api_key" {
  description = "Firebase Web API key (safe to expose — restricted by Firebase security rules)."
  value       = data.google_firebase_web_app_config.daskalo.api_key
  sensitive   = true
}

output "firebase_messaging_sender_id" {
  description = "Firebase Messaging Sender ID."
  value       = data.google_firebase_web_app_config.daskalo.messaging_sender_id
}

output "public_assets_bucket_name" {
  description = "Name of the assets bucket (images, audio). Accessed via Firebase Storage SDK, governed by storage.rules."
  value       = google_storage_bucket.public_assets.name
}
