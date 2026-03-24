# Security & Infrastructure Guidelines

This document outlines the security rules and infrastructure requirements for the Greek Language Learning Application.

## 1. Firebase Configuration

### 1.1 Authentication
- **Provider**: Google Sign-In via Firebase Auth.
- **Enablement**: New users signing up via the Angular frontend will be created with `status: "pending"`.
- **Admin Action**: An administrator (via the Firebase Console or an admin script) must manually change the user's status to `active` before they can access content or write exercise attempts.

### 1.2 Firestore Security Rules
Strict security rules are required to ensure data integrity and prevent unauthorized access. The rules must enforce the "active" status check.

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Helper function to check if the user is logged in
    function isAuthenticated() {
      return request.auth != null;
    }

    // Helper function to check if the current user is "active"
    // This is the core enablement check.
    function isActiveUser() {
      return isAuthenticated() && get(/databases/$(database)/documents/users/$(request.auth.uid)).data.status == "active";
    }

    // Users can read/write their own document
    match /users/{userId} {
      allow read, write: if request.auth.uid == userId;
      // Note: We'll need a way for the backend to set/update 'status'.
      // The backend uses the Admin SDK, which bypasses these rules.
    }

    // Phases and Chapters are strictly read-only for active users
    match /phases/{phaseId} {
      allow read: if isActiveUser();
      allow write: if false; // Only written by the Backend Ingestion Service
    }

    match /chapters/{chapterId} {
      allow read: if isActiveUser();
      allow write: if false; // Only written by the Backend Ingestion Service
    }

    // Exercise Attempts
    // Active users can read their own attempts
    // Active users can create new attempts, but cannot fake evaluations
    match /exercise_attempts/{attemptId} {
      allow read: if isActiveUser() && resource.data.userId == request.auth.uid;
      allow create: if isActiveUser() && request.resource.data.userId == request.auth.uid && request.resource.data.evaluation == null;
      allow update, delete: if false; // Only the Backend can update (add evaluation)
    }
  }
}
```

## 2. Google Cloud Infrastructure

### 2.1 Project Setup
1. Create a Google Cloud Project (e.g., `greek-learning-app-prod`).
2. Enable necessary APIs:
   - Compute Engine API
   - Cloud Run Admin API
   - Eventarc API
   - Cloud Storage API
   - Vertex AI API (for Content Generation CLI)
   - Firestore API

### 2.2 Cloud Storage Buckets
Two distinct buckets are required:
1.  **Ingestion Bucket (Private)**: The CLI uploads `.zip` files here. This bucket triggers Eventarc. Only the backend and specific service accounts should have access.
2.  **Public Assets Bucket (Public Read)**: The backend moves audio (`.mp3`) and images (`.jpg`) here during ingestion. The Angular app loads media directly from this bucket.

### 2.3 Cloud Run & Eventarc
- The FastAPI application must be deployed to Cloud Run.
- **Security**: The Cloud Run service should *not* allow unauthenticated invocation (`--no-allow-unauthenticated`).
- **Ingress**: Configure ingress to "Internal and Cloud Load Balancing" or rely solely on Eventarc invocations using a specific service account.
- **Service Account**: Create a dedicated service account for Eventarc (e.g., `eventarc-trigger-sa@...`). Grant it `roles/run.invoker` on the Cloud Run service.

## 3. Cost Control & Billing Alerts
Given the use of Vertex AI and LLMs, proactive cost management is crucial.

1.  **Set up a Billing Budget**: Go to Billing -> Budgets & alerts in the GCP console.
2.  **Alert Thresholds**: Configure alerts at 50%, 90%, and 100% of your expected monthly spend (e.g., a $10/month budget).
3.  **Action on 100%**: Consider configuring automated actions (like disabling billing or shutting down services) if the budget is reached, though simple email alerts are often sufficient for early stages.