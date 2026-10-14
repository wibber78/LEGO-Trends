# Retired Sets Trends Radar v1.4

Release year is now mandatory. A search scans only the specified release year (up to three Brickset pages by default), rather than four years. Blank or invalid years are rejected in the UI and API.

All v1.3 features remain: official logo, colour-coded investment categories, individual score breakdowns, and up to 20 vertically stacked results. No API usage display or spreadsheet search.

## Deployment
Replace `app.py`, `logo.png` and `requirements.txt` in your Trends Radar GitHub repository. Keep Railway start command `uvicorn app:app --host 0.0.0.0 --port $PORT` and existing `BRICKSET_API_KEY`.

Searches are cached for six hours per running instance. A cold search may use up to three Brickset `getSets` calls depending on pagination.
