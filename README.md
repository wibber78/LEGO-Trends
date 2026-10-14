# Retired Sets Trends Radar — v1.1

A separate FastAPI dashboard for LEGO retirement and buying-opportunity screening using Brickset.

## Deploy to Railway

1. Add `app.py` and `requirements.txt` to the Trends Radar GitHub repository.
2. In the Trends Radar Railway service, set `BRICKSET_API_KEY` to your existing Brickset key.
3. Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. Deploy and open the Railway public URL.

## Changes in v1.1

- Removed CSV inventory upload, comparison, and export functionality, including the backend endpoint.
- Added an API usage panel with Refresh button, querying Brickset `getKeyUsageStats`.
- Usage is reported by Brickset for the shared API key, so calls from the Price Checker are included.
- Retirement scans still use a six-hour in-memory cache per Railway instance.
- Scores are heuristic screening indicators, not verified resale forecasts.

## Note

The usage endpoint has not been live-tested with your private Brickset key. It displays returned usage fields without assuming a fixed response schema. If Brickset rejects the call, the dashboard shows an error but retirement searches continue to work.
