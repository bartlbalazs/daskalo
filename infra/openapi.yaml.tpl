swagger: "2.0"
info:
  title: "Daskalo API"
  description: "API Gateway for Daskalo Cloud Functions. Validates Firebase JWTs at the edge."
  version: "1.0.0"
host: "PLACEHOLDER"  # replaced by API Gateway at deploy time
schemes:
  - "https"
produces:
  - "application/json"

# ---------------------------------------------------------------------------
# Per-user rate limiting via API Gateway quota
# ---------------------------------------------------------------------------
x-google-management:
  metrics:
    - name: "evaluate-attempt-requests"
      displayName: "Evaluate Attempt Requests"
      valueType: INT64
      metricKind: DELTA
    - name: "complete-chapter-requests"
      displayName: "Complete Chapter Requests"
      valueType: INT64
      metricKind: DELTA
    - name: "add-own-word-requests"
      displayName: "Add Own Word Requests"
      valueType: INT64
      metricKind: DELTA
  quota:
    limits:
      - name: "evaluate-attempt-limit"
        metric: "evaluate-attempt-requests"
        unit: "1/min/{project}"
        values:
          STANDARD: 5
      - name: "complete-chapter-limit"
        metric: "complete-chapter-requests"
        unit: "1/min/{project}"
        values:
          STANDARD: 3
      - name: "add-own-word-limit"
        metric: "add-own-word-requests"
        unit: "1/min/{project}"
        values:
          STANDARD: 5

# ---------------------------------------------------------------------------
# Firebase JWT security definition
# ---------------------------------------------------------------------------
securityDefinitions:
  firebase:
    authorizationUrl: ""
    flow: "implicit"
    type: "oauth2"
    x-google-issuer: "https://securetoken.google.com/${project_id}"
    x-google-jwks_uri: "https://www.googleapis.com/service_accounts/v1/metadata/x509/securetoken@system.gserviceaccount.com"
    x-google-audiences: "${project_id}"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
paths:

  # -------------------------------------------------------------------------
  # /evaluate — POST (evaluate-attempt function)
  # -------------------------------------------------------------------------
  /evaluate:
    post:
      operationId: "evaluateAttempt"
      summary: "Evaluate an exercise attempt"
      security:
        - firebase: []
      x-google-quota:
        metricCosts:
          "evaluate-attempt-requests": 1
      x-google-backend:
        address: "${evaluate_attempt_url}"
        jwt_audience: "${evaluate_attempt_url}"
        deadline: 120.0
        protocol: h2
      parameters:
        - in: body
          name: body
          required: true
          schema:
            type: object
      responses:
        "200":
          description: "Evaluation result"
        "400":
          description: "Invalid argument"
        "401":
          description: "Unauthenticated"
        "403":
          description: "Permission denied"
        "404":
          description: "Not found"
        "409":
          description: "Already evaluated"
        "500":
          description: "Internal error"
    options:
      operationId: "evaluateAttemptCors"
      summary: "CORS preflight for /evaluate"
      x-google-backend:
        address: "${evaluate_attempt_url}"
        deadline: 20.0
      parameters:
        - in: header
          name: Origin
          type: string
        - in: header
          name: Access-Control-Request-Method
          type: string
        - in: header
          name: Access-Control-Request-Headers
          type: string
      responses:
        "200":
          description: "CORS preflight response"
          headers:
            Access-Control-Allow-Origin:
              type: string
            Access-Control-Allow-Methods:
              type: string
            Access-Control-Allow-Headers:
              type: string
            Access-Control-Max-Age:
              type: string

  # -------------------------------------------------------------------------
  # /complete-chapter — POST (complete-chapter function)
  # -------------------------------------------------------------------------
  /complete-chapter:
    post:
      operationId: "completeChapter"
      summary: "Complete a chapter and generate progress summary"
      security:
        - firebase: []
      x-google-quota:
        metricCosts:
          "complete-chapter-requests": 1
      x-google-backend:
        address: "${complete_chapter_url}"
        jwt_audience: "${complete_chapter_url}"
        deadline: 180.0
        protocol: h2
      parameters:
        - in: body
          name: body
          required: true
          schema:
            type: object
      responses:
        "200":
          description: "Progress result"
        "400":
          description: "Invalid argument"
        "401":
          description: "Unauthenticated"
        "403":
          description: "Permission denied"
        "404":
          description: "Chapter not found"
        "500":
          description: "Internal error"
    options:
      operationId: "completeChapterCors"
      summary: "CORS preflight for /complete-chapter"
      x-google-backend:
        address: "${complete_chapter_url}"
        deadline: 20.0
      parameters:
        - in: header
          name: Origin
          type: string
        - in: header
          name: Access-Control-Request-Method
          type: string
        - in: header
          name: Access-Control-Request-Headers
          type: string
      responses:
        "200":
          description: "CORS preflight response"
          headers:
            Access-Control-Allow-Origin:
              type: string
            Access-Control-Allow-Methods:
              type: string
            Access-Control-Allow-Headers:
              type: string
            Access-Control-Max-Age:
              type: string

  # -------------------------------------------------------------------------
  # /add-own-word — POST (add-own-word function)
  # -------------------------------------------------------------------------
  /add-own-word:
    post:
      operationId: "addOwnWord"
      summary: "Add a custom vocabulary word for the current user"
      security:
        - firebase: []
      x-google-quota:
        metricCosts:
          "add-own-word-requests": 1
      x-google-backend:
        address: "${add_own_word_url}"
        jwt_audience: "${add_own_word_url}"
        deadline: 60.0
        protocol: h2
      parameters:
        - in: body
          name: body
          required: true
          schema:
            type: object
      responses:
        "200":
          description: "Own word added or already exists"
        "400":
          description: "Invalid argument"
        "401":
          description: "Unauthenticated"
        "403":
          description: "Permission denied"
        "429":
          description: "Rate limit exceeded"
        "500":
          description: "Internal error"
    options:
      operationId: "addOwnWordCors"
      summary: "CORS preflight for /add-own-word"
      x-google-backend:
        address: "${add_own_word_url}"
        deadline: 20.0
      parameters:
        - in: header
          name: Origin
          type: string
        - in: header
          name: Access-Control-Request-Method
          type: string
        - in: header
          name: Access-Control-Request-Headers
          type: string
      responses:
        "200":
          description: "CORS preflight response"
          headers:
            Access-Control-Allow-Origin:
              type: string
            Access-Control-Allow-Methods:
              type: string
            Access-Control-Allow-Headers:
              type: string
            Access-Control-Max-Age:
              type: string
