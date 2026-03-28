variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Functions, API Gateway, and GCS buckets."
  type        = string
  default     = "europe-west1"
}

variable "db_name" {
  description = "Firestore database name. Use '(default)' for the default database."
  type        = string
  default     = "(default)"
}

variable "public_assets_bucket_name" {
  description = "Globally unique name for the public assets GCS bucket (images, audio)."
  type        = string
}

variable "firebase_app_display_name" {
  description = "Display name for the Firebase web app resource."
  type        = string
  default     = "Daskalo"
}

variable "evaluate_function_memory" {
  description = "Memory for the evaluate-attempt Cloud Function."
  type        = string
  default     = "512M"
}

variable "evaluate_function_cpu" {
  description = "vCPU allocation for the evaluate-attempt Cloud Function. Set to '1' when memory > 512Mi."
  type        = string
  default     = "0.333"
}

variable "evaluate_function_timeout" {
  description = "Timeout (seconds) for the evaluate-attempt Cloud Function."
  type        = number
  default     = 120
}

variable "complete_chapter_function_memory" {
  description = "Memory for the complete-chapter Cloud Function."
  type        = string
  default     = "512M"
}

variable "complete_chapter_function_cpu" {
  description = "vCPU allocation for the complete-chapter Cloud Function. Set to '1' when memory > 512Mi."
  type        = string
  default     = "0.333"
}

variable "complete_chapter_function_timeout" {
  description = "Timeout (seconds) for the complete-chapter Cloud Function."
  type        = number
  default     = 180
}

variable "add_own_word_function_memory" {
  description = "Memory for the add-own-word Cloud Function."
  type        = string
  default     = "512M"
}

variable "add_own_word_function_cpu" {
  description = "vCPU allocation for the add-own-word Cloud Function. Set to '1' when memory > 512Mi."
  type        = string
  default     = "0.333"
}

variable "add_own_word_function_timeout" {
  description = "Timeout (seconds) for the add-own-word Cloud Function."
  type        = number
  default     = 60
}
