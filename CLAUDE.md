# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the Streamlit app
streamlit run app.py

# Refresh bundled TLE + GP history data (requires Space-Track credentials)
python scripts/update_bundled_data.py --username USER --password PASS --days 365 --constellation all

# Update only TLEs (no credentials needed, uses CelesTrak)
python scripts/update_bundled_data.py --tles-only

# Run tests (from repo root)
python tests/test_health_run.py
python tests/test_qzs6_analysis.py
python tests/test_qzs6_commission.py

# Find BeiDou NORAD IDs (one-time utility)
python tests/find_beidou_norad_ids.py
```

Space-Track credentials can be provided via:
1. CLI args (`--username`/`--password`)
2. Env vars `SPACETRACK_USERNAME` / `SPACETRACK_PASSWORD`
3. `.streamlit/secrets.toml` under `[spacetrack]` section

## Architecture

This is a Streamlit dashboard for monitoring GEO/IGSO satellites across three GNSS constellations: NavIC (IRNSS), QZSS (Michibiki), and BeiDou-3.

### Data Flow

```
Space-Track.org ──► api/spacetrack_api.py ──► GP history (inclination, SMA, epoch)
CelesTrak       ──► api/celestrak_api.py  ──► Latest TLEs
                              │
                    data/tle_cache.py  ──► data/*.json (bundled offline snapshots)
                              │
                         app.py (orchestrator)
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
  analysis/              analysis/           analysis/
  health_assessment.py   drift_analysis.py   dop_calculations.py
  maneuver_detection.py
          │
          └──────────────────►  visualizations/visualization.py
```

### Key Design Decisions

- **Bundled data mode**: Pre-cached JSON files in `data/` allow the app to run without API credentials. The GitHub Actions workflow (`.github/workflows/update-tle-data.yml`) refreshes these weekly using `scripts/update_bundled_data.py`. When bundled mode is active, **all** analysis paths (GP history, pattern analysis for health scoring, TLEs for DOP and longitude deviation) use bundled data — no API calls are made. The only network call is Skyfield's one-time `load.timescale()` leap-second file download on first run.

- **Two data sources**: Space-Track provides full GP history (used for drift/maneuver analysis over time); CelesTrak provides current TLEs only (used for DOP calculations). The app prefers Space-Track but falls back where possible. In bundled mode, both are bypassed in favor of local JSON files.

- **Pattern analysis in bundled mode**: Health assessment requires a 365-day pattern window for maneuver detection. In bundled mode, pattern data is extracted from the already-loaded `df_all` (filtered to the pattern window) rather than calling `fetch_and_classify_satellite()`. If the bundled data doesn't cover the full 365-day window, all available bundled data for that satellite is used as a fallback.

- **Session state**: `app.py` stores fetched satellite data in `st.session_state` so re-renders don't re-fetch. DOP analysis results are also cached there.

- **Longitude deviation** is computed inside `app.py` using Skyfield propagation — not in the `analysis/` package — because it needs both the satellite objects (from DOP calculations) and the config data.

### Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `config/config.py` | NORAD IDs, designated slots/inclinations, tolerance thresholds, DOP quality levels |
| `api/spacetrack_api.py` | Auth + GP history fetch from Space-Track |
| `api/celestrak_api.py` | TLE fetch from CelesTrak (no auth) |
| `data/tle_cache.py` | Load/save bundled JSON snapshots |
| `analysis/health_assessment.py` | 5-component weighted health score (0–100) |
| `analysis/drift_analysis.py` | Mean motion → longitudinal drift (°/day) |
| `analysis/maneuver_detection.py` | MAD z-score detection of E-W/N-S maneuvers |
| `analysis/dop_calculations.py` | Skyfield-based GDOP/PDOP/HDOP/VDOP/TDOP |
| `visualizations/visualization.py` | All Plotly/Folium charts |
| `app.py` | UI, orchestration, session state, longitude deviation |

### Health Scoring Weights

| Component | Weight | Key threshold (GEO) |
|-----------|--------|----------------------|
| Inclination control | 30% | ±1.0° |
| Maintenance pattern | 25% | 1–8 maneuvers/month |
| Drift | 20% | <0.05°/day |
| Longitude deviation | 15% | <0.5° |
| Maneuver uniformity | 10% | CoV < 0.8 |

### Adding a New Constellation

1. Add NORAD IDs dict and service requirements dict to `config/config.py`
2. Add geographic reference points for DOP analysis to `config/config.py`
3. Wire up the new constellation in `app.py` (sidebar selector, data fetch, analysis calls)
4. Add bundled data files via `scripts/update_bundled_data.py`

### Satellite Status Notes

- `INACTIVE_SATELLITES` in `config/config.py` lists satellites excluded from DOP calculations (IRNSS-1C through 1G are messaging-only; navigation provided by NVS-01)
- `COMMISSION_DATES` tracks recently commissioned satellites that need analysis window constraints (e.g., QZS-6 commissioned 2025-02-01)
- Graveyard orbit detection threshold: SMA > 36,000 km
