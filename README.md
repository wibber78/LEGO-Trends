# Retired Sets Trends Radar v1.5

- Centres the Retired Sets logo and header text.
- Collector interest is calculated as min(20, round(100 × wantedBy / (ownedBy + 1))) when Brickset provides both counts.
- If collector counts are missing, displays **Data unavailable**, rather than misleading **0/20**. Missing data contributes zero points to the existing 90-point screening heuristic; categories and thresholds are unchanged.
- Shows wanted/owned counts when present.

## Deploy
Replace `app.py` in your Trends Radar GitHub repository and commit. Existing `logo.png`, `requirements.txt`, `BRICKSET_API_KEY` and Railway start command remain unchanged.

**Note:** Brickset may not supply wanted/owned counts in its `getSets` response. This release makes the absence transparent; it does not invent collector-interest values.
