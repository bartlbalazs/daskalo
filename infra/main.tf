terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
  }

  # Remote state stored in GCS — bucket created by bootstrap.sh
  backend "gcs" {
    # The bucket name is injected at `terraform init` time via -backend-config
    # or the auto-detected bucket: {project_id}-terraform-state
    # bootstrap.sh passes: -backend-config="bucket=${PROJECT_ID}-terraform-state"
    prefix = "daskalo/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
