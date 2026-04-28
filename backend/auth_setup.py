"""
auth_setup.py
─────────────
Run this ONCE locally (not on Cloud Run) to generate a token.json file
for the Google Calendar API.

Usage:
    python auth_setup.py

Then copy the contents of token.json and store them as the Cloud Run
environment variable CALENDAR_TOKEN_JSON.

Prerequisites:
  1. Enable Google Calendar API in your GCP project
  2. Create OAuth 2.0 credentials (Desktop app type) in GCP Console
  3. Download the credentials JSON and save it as credentials.json
     in the same directory as this script
  4. Add your Google account as a Test User in the OAuth consent screen
"""

import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os

SCOPES = [
    "https://www.googleapis.com/auth/calendar",          # create/edit events
    "https://www.googleapis.com/auth/calendar.readonly", # list events
]

CREDENTIALS_FILE = "credentials.json"  # Downloaded from GCP Console
TOKEN_FILE = "token.json"


def main():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"ERROR: {CREDENTIALS_FILE} not found.")
        print("Download it from GCP Console → APIs & Services → Credentials")
        print("Create an OAuth 2.0 Client ID (Desktop app type)")
        return

    creds = None

    # Load existing token if available
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            token_data = json.load(f)
        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes"),
        )

    # Refresh or run the OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8085, open_browser=True)

    # Save token.json
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes),
    }

    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

    print(f"✅ token.json generated successfully!")
    print()
    print("Next steps:")
    print("  1. Copy the contents of token.json")
    print("  2. Set it as the env var CALENDAR_TOKEN_JSON in Cloud Run:")
    print()
    print("  gcloud run services update sponsorship-bridge \\")
    print("    --region=europe-west1 \\")
    print(f"    --set-env-vars 'CALENDAR_TOKEN_JSON=$(cat {TOKEN_FILE})'")
    print()
    print("  3. Set USE_REAL_CALENDAR=true in Cloud Run env vars")
    print("  4. DO NOT commit token.json or credentials.json to git")


if __name__ == "__main__":
    main()
