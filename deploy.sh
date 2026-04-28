#!/bin/bash
# =============================================================================
# Sponsorship Bridge — Deploy to Cloud Run
#
# Supports both stub and real calendar modes:
#   Stub mode (default):  ./deploy.sh
#   Real calendar mode:   USE_REAL_CALENDAR=true CALENDAR_TOKEN_JSON="$(cat token.json)" ./deploy.sh
#
# Prerequisites:
#   - gcloud CLI authenticated: gcloud auth login
#   - Project set: gcloud config set project YOUR_PROJECT_ID
#   - YouTube API key: export YOUTUBE_API_KEY="your-key"
#   - (Optional) token.json from auth_setup.py for real calendar
# =============================================================================

set -euo pipefail

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="europe-west1"
SERVICE_NAME="sponsorship-bridge"

if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo ""
echo "================================================="
echo "  Sponsorship Bridge — Deploying to Cloud Run"
echo "  Project: $PROJECT_ID"
echo "  Region:  $REGION"
echo "================================================="
echo ""

# ── Collect required config ─────────────────────────────────────────────────
if [ -z "${YOUTUBE_API_KEY:-}" ]; then
    read -rp "Enter your YouTube Data API key: " YOUTUBE_API_KEY
fi

# Calendar mode detection
CALENDAR_MODE="stub"
ENV_VARS="GOOGLE_CLOUD_PROJECT=$PROJECT_ID"
ENV_VARS="$ENV_VARS,GOOGLE_CLOUD_LOCATION=$REGION"
ENV_VARS="$ENV_VARS,GOOGLE_GENAI_USE_VERTEXAI=TRUE"
ENV_VARS="$ENV_VARS,YOUTUBE_API_KEY=$YOUTUBE_API_KEY"

if [ "${USE_REAL_CALENDAR:-false}" = "true" ]; then
    CALENDAR_MODE="real"
    if [ -z "${CALENDAR_TOKEN_JSON:-}" ]; then
        # Try to read from token.json in the current directory
        if [ -f "token.json" ]; then
            echo "  Found token.json — reading calendar credentials..."
            CALENDAR_TOKEN_JSON="$(cat token.json)"
        else
            echo "ERROR: USE_REAL_CALENDAR=true but CALENDAR_TOKEN_JSON is not set"
            echo "       and no token.json file found in the current directory."
            echo ""
            echo "  Run:  python3 auth_setup.py"
            echo "  Then: USE_REAL_CALENDAR=true CALENDAR_TOKEN_JSON=\"\$(cat token.json)\" ./deploy.sh"
            exit 1
        fi
    fi
    ENV_VARS="$ENV_VARS,USE_REAL_CALENDAR=true"
fi

echo "  Calendar mode: $CALENDAR_MODE"
echo ""

# ── Step 1: Enable APIs ─────────────────────────────────────────────────────
echo "[1/4] Enabling required APIs..."
APIS="run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com aiplatform.googleapis.com youtube.googleapis.com"
if [ "$CALENDAR_MODE" = "real" ]; then
    APIS="$APIS calendar-json.googleapis.com"
fi
# shellcheck disable=SC2086
gcloud services enable $APIS --project="$PROJECT_ID"

# ── Step 2: Deploy ──────────────────────────────────────────────────────────
echo "[2/4] Building and deploying to Cloud Run..."
DEPLOY_CMD=(
    gcloud run deploy "$SERVICE_NAME"
    --project="$PROJECT_ID"
    --source .
    --region="$REGION"
    --set-env-vars "$ENV_VARS"
    --allow-unauthenticated
    --memory 1Gi
    --timeout 300
)

# CALENDAR_TOKEN_JSON is passed separately via --update-env-vars because it
# contains JSON with commas, which --set-env-vars would misparse.
if [ "$CALENDAR_MODE" = "real" ]; then
    "${DEPLOY_CMD[@]}"
    echo ""
    echo "  Setting CALENDAR_TOKEN_JSON (separate step — contains JSON)..."
    gcloud run services update "$SERVICE_NAME" \
        --project="$PROJECT_ID" \
        --region="$REGION" \
        --update-env-vars "CALENDAR_TOKEN_JSON=$CALENDAR_TOKEN_JSON"
else
    ENV_VARS="$ENV_VARS,USE_REAL_CALENDAR=false"
    DEPLOY_CMD=(
        gcloud run deploy "$SERVICE_NAME"
        --project="$PROJECT_ID"
        --source .
        --region="$REGION"
        --set-env-vars "$ENV_VARS"
        --allow-unauthenticated
        --memory 1Gi
        --timeout 300
    )
    "${DEPLOY_CMD[@]}"
fi

# ── Step 3: Get URL ─────────────────────────────────────────────────────────
echo ""
echo "[3/4] Getting service URL..."
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" \
    --format="value(status.url)" \
    --project="$PROJECT_ID")

# ── Step 4: Smoke test ──────────────────────────────────────────────────────
echo "[4/4] Smoke test..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL/list-apps" 2>/dev/null || echo "000")

echo ""
echo "================================================="
echo "  Deployment complete!"
echo "================================================="
echo ""
echo "  Service URL:    $SERVICE_URL"
echo "  Calendar mode:  $CALENDAR_MODE"
echo "  Smoke test:     $HTTP_CODE (expect 200)"
echo ""
echo "  ── Quick verification ──────────────────────────"
echo ""
echo "  # List agents (should show sponsorship_bridge)"
echo "  curl $SERVICE_URL/list-apps"
echo ""
echo "  # Create a session"
echo "  curl -X POST $SERVICE_URL/apps/sponsorship_bridge/users/test_user/sessions \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"state\":{}}'"
echo ""
echo "  ── Demo prompts (test all 5) ──────────────────"
echo ""
echo "  1. Brand Mode (skincare):"
echo "     I'm an eco-friendly skincare brand targeting women 18-35 in the US."
echo "     Find me YouTube creators who make skincare, clean beauty, or sustainable lifestyle content."
echo ""
echo "  2. Brand Mode (fitness):"
echo "     I'm a fitness supplement brand targeting men 25-40."
echo "     Find me fitness creators in Southeast Asia."
echo ""
echo "  3. Creator Mode:"
echo "     I'm a creator. My channel covers sustainable living and zero-waste lifestyle."
echo "     What brands in your database would be a good match for me?"
echo ""
echo "  4. Match History:"
echo "     Show me the match history."
echo ""
echo "  5. Scheduling:"
echo "     Schedule an intro call between EcoGlow and the top creator for next Tuesday at 10am."
echo ""

if [ "$CALENDAR_MODE" = "real" ]; then
    echo "  ── Real Calendar verification ─────────────────"
    echo "  Prompt 5 should create a REAL Google Calendar event with a live Meet link."
    echo "  Check your Google Calendar to confirm the event was created."
    echo ""
fi
