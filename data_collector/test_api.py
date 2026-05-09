"""
Verify Python can call the flight pricing API.
Throwaway test script. Saves the latest response to data/sample_response.json
for inspection. Each run overwrites the previous sample.
"""
import os
import json
from pathlib import Path

import requests
from dotenv import load_dotenv


# Block A: Load the .env file sitting next to this script, then read API config
load_dotenv(Path(__file__).parent / ".env")
token = os.environ["API_TOKEN"]


# Block B: Get the endpoint URL and define query parameters
URL = os.environ["API_URL"]
params = {
    "origin": "JFK",
    "destination": "LHR",
    "departure_at": "2026-08",
    "currency": "usd",
    "market": "us",
    "one_way": "true",
    "limit": 5,
    "token": token,
}


# Block C: Send the GET request — requests builds the query string from `params`
response = requests.get(URL, params=params)


# Block D: Save the response to data/sample_response.json (overwritten each run)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
out_path = PROJECT_ROOT / "data" / "sample_response.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(response.json(), indent=2))


# Confirm
offers_count = len(response.json().get("data", []))
print(f"Status: {response.status_code}")
print(f"Saved {offers_count} offers to {out_path}")