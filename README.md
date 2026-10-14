# Retired Sets Trends Radar v1.7

## Changes
- Retirement proximity removed from the score (still a search filter and shown per result).
- UK RRP still informational only.
- Collector Demand Score: Brickset rating (40), wanted-by count relative to this search (30), wanted/owned ratio relative to this search (20), and rating confidence based on number of ratings (10).
- Correctly reads `collections.ownedBy` and `collections.wantedBy`, with fallback for older payloads.
- Colour categories: Strong Collector Demand (70+), Moderate Collector Demand (40–69), Limited Collector Demand (<40), or Insufficient data if less than 70% of underlying scoring data is present.
- Score breakdown, actual collector counts, rating count, data coverage and explanatory notes.
- Required release year, optional theme, retirement window, top 20, centred logo, six-hour cache retained.

## Deploy
Replace `app.py` in your Trends Radar GitHub repository and commit. Other files are included for completeness but need not be replaced if already present.

Railway start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`

`BRICKSET_API_KEY` must already be set in Railway.

## Important limitations
Scoring is a relative popularity screen among sets matching the current scan; it is **not** a prediction of profit, future value, or scarcity. The Brickset API may not return all rating or collection fields. Missing fields show as unavailable and are not silently treated as zero. Rating count field names may vary by API response; no additional API calls are made.
