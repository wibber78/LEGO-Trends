# Retired Sets Trends Radar v1.6

Changes from v1.5: UK RRP availability no longer influences the opportunity score. Total is now out of 80 (retirement 40, Brickset rating 20, collector interest 20). Labels: Good Investment 58–80; Possible Investment 36–57; Not worth investing 0–35. UK RRP remains displayed as information.

## Deploy
Replace `app.py` in your existing Trends Radar GitHub repository and commit. Railway will redeploy. No changes to the API key, logo, dependencies or start command are required.

Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`

Scores are screening heuristics, not financial forecasts. Missing collector data contributes zero.
