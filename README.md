# Retired Sets Trends Radar v1.2

A standalone FastAPI app for screening LEGO sets approaching retirement.

## Deploy to Railway

1. Upload `app.py` and `requirements.txt` to the separate Trends Radar GitHub repository.
2. Configure `BRICKSET_API_KEY` in Railway Variables (same key as Price Checker).
3. Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`.
4. Generate a Railway domain pointed to the listening port.

## Version 1.2

- Removed Brickset API usage display and endpoint.
- Added labelled screening bands: **Good Investment** (65–90), **Possible Investment** (40–64), **Not worth investing** (0–39).
- Returns the top 20 retirement candidates in descending score order, displayed in a single vertical list.
- No spreadsheet analysis or stock valuation.
- Results are cached for 6 hours per running application instance.

**Caution:** The categories are heuristic labels requested for convenience, not validated investment recommendations. The app does not measure current resale market prices or predict profits. Always verify purchase cost and recent sold prices before buying.
