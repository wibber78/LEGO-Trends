# Retired Sets Trends Radar v1.8

## Changes
- Theme field now has searchable autocomplete suggestions from Brickset `getThemes`.
- New optional keyword search uses Brickset `getSets` `query` parameter, which searches set number, name, theme and subtheme. Useful for Formula 1 sets across themes.
- Theme list is cached in memory for 24 hours, separately from the six-hour `getSets` cache. Brickset states its initial 100/day limit is for `getSets`.
- Mandatory release year, retirement filters, top 20, collector demand scoring and logo remain unchanged.

## Install
Replace `app.py` in your existing GitHub Trends Radar repo and commit. No new packages or Railway variables required. Keep `logo.png` in the repository.

## Example
Year 2025; Theme blank; Keyword Formula 1; Retirement window next 24 months. If no results appear, widen the window or try another year. Brickset's `query` searches name/theme/subtheme; it is not a universal semantic search.

## Notes
`getThemes` requires a Brickset API key. If it fails, manual theme entry and keyword search remain available. No live API-key test was performed.
