# Health Scoring Logic and Data Flow: A Comprehensive Deep-Dive

This document provides an exhaustive explanation of how the GNSS Constellation Health Monitoring System computes satellite health scores, traces every byte of data from ingestion to final display, describes edge-case handling at every stage, evaluates the physical significance and resilience of the scoring model, and proposes targeted improvements.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Data Ingestion and Preprocessing](#2-data-ingestion-and-preprocessing)
3. [Maneuver Detection Pipeline](#3-maneuver-detection-pipeline)
4. [Maneuver Pattern Analysis](#4-maneuver-pattern-analysis)
5. [Drift Analysis](#5-drift-analysis)
6. [Inclination Scoring](#6-inclination-scoring)
7. [Maintenance Scoring](#7-maintenance-scoring)
8. [Uniformity Scoring](#8-uniformity-scoring)
9. [Longitude Deviation Scoring](#9-longitude-deviation-scoring)
10. [Overall Score Composition](#10-overall-score-composition)
11. [Health Status Classification](#11-health-status-classification)
12. [Sample Calculations](#12-sample-calculations)
13. [Edge Case Handling Across the Data Flow](#13-edge-case-handling-across-the-data-flow)
14. [Resilience Analysis](#14-resilience-analysis)
15. [Physical Significance Commentary](#15-physical-significance-commentary)
16. [Suggested Improvements](#16-suggested-improvements)

---

## 1. System Overview

The system monitors GEO (Geostationary) and IGSO (Inclined Geosynchronous Orbit) satellites across three constellations -- NavIC (IRNSS), QZSS (Michibiki), and BeiDou-3 -- and produces a composite health score in the range [0, 100] for each satellite. The score aggregates five independent sub-scores:

| Component             | Weight | Source Module                     |
|-----------------------|--------|-----------------------------------|
| Inclination Control   | 30%    | `analysis/health_assessment.py`   |
| Maintenance Pattern   | 25%    | `analysis/health_assessment.py`   |
| Drift                 | 20%    | `analysis/drift_analysis.py`      |
| Longitude Deviation   | 15%    | `app.py` (Skyfield propagation)   |
| Maneuver Uniformity   | 10%    | `analysis/maneuver_detection.py`  |

The overall score is a **weight-normalized** weighted average of whichever components are available. If a component cannot be computed (e.g., no TLE data for longitude), its weight is excluded and the remaining weights are re-normalized.

---

## 2. Data Ingestion and Preprocessing

### 2.1 Data Sources

Two independent data sources feed the system:

| Source         | Module                    | Data Provided                                   | Auth Required |
|----------------|---------------------------|-------------------------------------------------|---------------|
| Space-Track.org| `api/spacetrack_api.py`   | GP history: epoch, inclination, SMA, mean motion, RAAN, eccentricity, etc. | Yes (username/password) |
| CelesTrak      | `api/celestrak_api.py`    | Latest TLEs (two-line element sets)             | No            |

**Fallback strategy**: Bundled JSON files in `data/` allow the app to run without any API credentials. A GitHub Actions workflow refreshes these weekly via `scripts/update_bundled_data.py`.

### 2.2 GP History Fetch (`fetch_and_classify_satellite`)

**Location**: `api/spacetrack_api.py:88`

This is the primary data-fetch function. For a given NORAD catalog ID and date range, it:

1. **Fetches JSON** from Space-Track's `gp_history` endpoint, cached for 1 hour via `@st.cache_data(ttl=3600)`.
2. **Standardizes column names** -- the GP JSON may use lowercase (`epoch`, `inclination`, `semimajor_axis`, `mean_motion`) or uppercase field names depending on the API version. The function normalizes to uppercase.
3. **Validates required columns** -- `EPOCH` and `INCLINATION` are mandatory; if absent, a `ValueError` is raised. `SEMIMAJOR_AXIS`, `MEAN_MOTION`, TLE lines, RAAN, argument of perigee, mean anomaly, and eccentricity are included when available.
4. **Computes derived quantities**:
   - `LonDrift_deg_per_day` = `(MEAN_MOTION - 1.00273790935) * 360` (see Section 5)
   - `altitude_km` = `SEMIMAJOR_AXIS - 6371.0` (Earth radius subtracted)
   - `type` = `'GEO'` if 0 < inclination < 10, `'IGSO'` if inclination >= 10, else `'Unclassified'`
   - `mean_inclination` = mean of all INCLINATION values
   - `maintained` = boolean flag for whether each epoch's inclination is within `deviation_tol` (default 0.3 deg) of the mean

**Edge cases handled at ingestion**:
- **Timeout** on Space-Track: caught as `requests.exceptions.Timeout`, re-raised with a descriptive error suggesting smaller date range or retry.
- **Connection error**: caught and re-raised with network check suggestion.
- **Empty response**: if `data` is empty, a `ValueError` is raised.
- **Missing SMA**: if `SEMIMAJOR_AXIS` is not in the GP JSON, both `SEMIMAJOR_AXIS` and `altitude_km` are set to `NaN`.
- **Missing MEAN_MOTION**: longitudinal drift cannot be computed; column is simply absent.

### 2.3 Session-Level Caching

`app.py` uses Streamlit's `st.session_state` to store fetched data, so re-renders of the UI don't trigger re-fetching. The health assessment results themselves are also cached under a cache key, invalidated when the user changes analysis parameters.

### 2.4 Pattern Data Window

For health assessment, the system fetches a separate "pattern analysis" window:
- **Default**: last 365 days from now (if `use_historical_pattern` is True).
- **Fallback**: the user-selected date range.

This pattern data is used exclusively for maneuver detection and maintenance scoring, giving the algorithm a longer historical baseline than the selected analysis window.

### 2.5 Deployed-Date Filtering

Before health assessment, the system counts how many satellites have GP observations on each UTC date. A date is considered "deployed" only if at least 75% of the expected constellation size has observations on that date. Any dates that fail this threshold are excluded from both the satellite DataFrame and the maneuver list. This prevents distorted scores during constellation ramp-up periods (e.g., QZSS adding QZS-6).

**Edge cases**:
- If zero dates pass the threshold, `deployed_dates` is set to `None`, and no filtering is applied.
- If filtering produces an empty DataFrame for a satellite, the unfiltered data is retained.
- Any exceptions during filtering are silently caught, falling back to unfiltered data.

---

## 3. Maneuver Detection Pipeline

### 3.1 Core Algorithm (`detect_navik_maneuvers`)

**Location**: `analysis/maneuver_detection.py:31`

Station-keeping maneuvers are detected using a two-stage statistical approach on the smoothed time series of SMA and inclination.

**Step 1: Smoothing**

A rolling median with window=3 and `min_periods=1` (centered) is applied to both the SMA and inclination columns. The rolling median is robust to single-point outliers and doesn't require the series to be uniformly sampled.

**Step 2: First-differences**

```
dSMA[i] = SMA_smooth[i] - SMA_smooth[i-1]
dINC[i] = INC_smooth[i] - INC_smooth[i-1]
```

The first data point gets `NaN` (filled with 0 for z-score computation).

**Step 3: Robust z-scores (MAD z-score)**

```python
def mad_zscore(x, threshold=1e-9):
    med = nanmedian(x)
    mad = nanmedian(|x - med|)
    if mad < 1e-9:
        # Fallback to standard z-score
        return (x - mean) / std   # if std < 1e-9, return all zeros
    return 0.6745 * (x - med) / mad
```

The MAD z-score uses the Median Absolute Deviation instead of the standard deviation. The factor 0.6745 normalizes MAD to be comparable to standard deviation for normal distributions. This is critical because maneuver-induced jumps would inflate the standard deviation, masking the very outliers we want to detect.

**Edge case -- constant series**: If MAD < 1e-9 (i.e., all differences are essentially identical), it falls back to standard z-score. If the standard deviation is also < 1e-9, all z-scores are set to zero (no maneuvers detected). This prevents division by zero.

**Step 4: Candidate identification**

A data point is an E-W (East-West) maneuver candidate if:
```
|dSMA| >= sma_abs_thresh_km (default 1.5 km)  AND  |z_dSMA| >= z_thresh (default 3.5)
```

A data point is an N-S (North-South) maneuver candidate if:
```
|dINC| >= inc_abs_thresh_deg (default 0.1 deg)  AND  |z_dINC| >= z_thresh (default 3.5)
```

Both a statistical threshold (z-score) AND a physical threshold (absolute change) must be exceeded. This dual-gate prevents false positives from both noise (small but statistically unusual) and genuine large variations in quiet periods (large but statistically expected).

**Step 5: Persistence confirmation**

Candidates are confirmed only if the **pre-to-post median shift** exceeds the physical threshold. This uses a rolling window of `persist_window` (default 2) on each side:

```
pre_sma_med  = median of SMA_smooth values in a window before the candidate
post_sma_med = median of SMA_smooth values in a window after the candidate
sma_med_delta = |post_sma_med - pre_sma_med|
```

An E-W maneuver is confirmed if: `EW_candidate AND sma_med_delta >= sma_abs_thresh_km`
An N-S maneuver is confirmed if: `INC_candidate AND inc_med_delta >= inc_abs_thresh_deg`

This persistence check eliminates transient spikes that revert immediately (e.g., a GP solution artifact).

**Step 6: Combined flag**

`MANEUVER = EW_MANEUVER | NS_MANEUVER`

A single epoch can be both an E-W and N-S maneuver (a combined station-keeping burn).

### 3.2 Physical Basis

- **E-W maneuvers** correct longitudinal drift by adjusting the semi-major axis (and thus the orbital period). A higher SMA means a longer period and westward drift relative to the rotating Earth; a lower SMA causes eastward drift.
- **N-S maneuvers** correct inclination. The orbital plane precesses due to Earth's oblateness (J2 perturbation), and periodic burns are needed to maintain the target inclination.

### 3.3 Maneuver Uniformity (`calculate_maneuver_uniformity`)

**Location**: `analysis/maneuver_detection.py:112`

Computes the Coefficient of Variation (CoV) of the intervals between consecutive maneuvers:

```
intervals = [date[i+1] - date[i] for i in range(n-1)]    # in days
CoV = std(intervals) / mean(intervals)
```

**Edge cases**:
- Fewer than 2 maneuvers: returns `None` (uniformity is undefined).
- Mean interval = 0 (all maneuvers on the same day): returns `None`.

**Physical meaning**: A low CoV (< 0.8) indicates regular, predictable station-keeping. High CoV suggests erratic maintenance or anomaly-driven corrections.

---

## 4. Maneuver Pattern Analysis

### 4.1 Overview (`analyze_maneuver_pattern`)

**Location**: `analysis/health_assessment.py:14`

This function separately analyzes E-W and N-S maneuver patterns to determine:
- Expected maneuver interval (median of inter-maneuver gaps)
- Whether the satellite is overdue for a maneuver
- Pattern confidence level
- Per-type and combined maintenance scores

### 4.2 Per-Type Analysis (`analyze_type_pattern`)

For each maneuver type (E-W or N-S):

1. **Sort maneuver epochs** chronologically.
2. **Compute inter-maneuver intervals** in days.
3. **Derive expected interval**:
   - >= 2 intervals: use the **median** interval (robust to outliers)
   - exactly 1 interval: use that single interval (confidence = `low`)
   - 0 intervals (single maneuver): expected interval = observation span (confidence = `very_low`)
4. **Assess confidence** via CoV of intervals:
   - CoV < 0.3: `high` confidence (very regular pattern)
   - CoV < 0.6: `medium` confidence
   - CoV >= 0.6 or mean = 0: `low` confidence
5. **Overdue detection**: `days_since_last > expected_interval * 1.5`

**Edge cases**:
- Zero maneuvers of a given type: all fields are `None` with confidence `none`.
- Comparison between timedelta-like types and floats is wrapped in a `try/except` to handle potential type mismatches (the code coerces epochs to `pd.to_datetime` but defensive handling remains).

### 4.3 Commission Date Handling

The function respects the satellite's commission (active) date from `config.config.COMMISSION_DATES`. If the satellite was commissioned after the start of the analysis window, the `effective_start` is clamped to `max(observation_start, commission_date)`. This prevents pre-operational epochs from polluting the pattern analysis.

**Edge cases**:
- Commission date may have timezone info; the code strips it via `tz_localize(None)` to avoid comparison errors with timezone-naive GP epochs.
- If both `commission_date` and `sat_first_obs` are `None`, `active_start` is `None` and no clamping occurs.

### 4.4 Combined Maintenance Score

The E-W and N-S scores are combined with a 60:40 weighting:

```
maintenance_score = ew_score * 0.6 + ns_score * 0.4
```

**E-W score computation** (60% weight -- more critical for GEO station-keeping):

| Condition                        | E-W Score |
|----------------------------------|-----------|
| Not overdue, recency_ratio < 1.0 | 100       |
| Not overdue, recency_ratio >= 1.0| 90        |
| Overdue, ratio > 3.0x           | 0         |
| Overdue, ratio > 2.0x           | 30        |
| Overdue, ratio <= 2.0x          | 60        |
| No E-W maneuvers detected       | 50        |

Confidence adjustments:
- `very_low` confidence: `ew_score = max(50, ew_score * 0.7)`
- `low` confidence: `ew_score = max(60, ew_score * 0.85)`

**N-S score computation** (40% weight):
Same logic as E-W, except:
- Default when no N-S maneuvers: 70 (less critical than E-W)
- Exception fallback on error: 70 (vs 50 for E-W)

### 4.5 Recency Ratio vs Overdue Ratio

An important distinction:
- **Recency ratio** = `days_since_last / expected_interval` (used when NOT overdue, i.e., days_since <= 1.5x expected)
- **Overdue ratio** = `days_since_last / expected_interval` (used when overdue, i.e., days_since > 1.5x expected)

The scoring is step-wise (not continuous), which creates discrete jumps at the thresholds.

---

## 5. Drift Analysis

### 5.1 Longitudinal Drift Calculation

**Location**: `analysis/drift_analysis.py:10`

```python
drift_deg_per_day = (mean_motion - GEOSYNC_MEAN_MOTION) * 360
```

Where:
- `GEOSYNC_MEAN_MOTION = 1.00273790935` rev/day (= 86400 / 86164.09053 seconds, the sidereal day)
- `mean_motion` is from the GP data in revolutions/day

**Physical significance**: A satellite with mean motion exactly equal to the geosynchronous value orbits in sync with Earth's rotation and experiences zero longitudinal drift. Any deviation causes the sub-satellite point to drift eastward (higher mean motion = shorter period = satellite "outruns" Earth) or westward (lower mean motion = longer period = satellite "falls behind").

For a GEO satellite, even a tiny drift of 0.05 deg/day means the satellite moves 18 deg in longitude per year if uncorrected.

### 5.2 Drift Health Assessment (`assess_drift_health`)

**Location**: `analysis/drift_analysis.py:27`

Uses different thresholds for GEO vs IGSO/QZO:

**GEO satellites** (tolerance default = 0.05 deg/day):

| Condition                | Score | Status    | Color |
|--------------------------|-------|-----------|-------|
| |drift| <= 0.015 (0.3x)  | 100   | Excellent | Green |
| |drift| <= 0.05 (1.0x)   | 80    | Good      | Green |
| |drift| <= 0.10 (2.0x)   | 60    | Fair      | Yellow|
| |drift| <= 0.25 (5.0x)   | 40    | Poor      | Orange|
| |drift| > 0.25           | 0     | Critical  | Red   |

**IGSO/QZO satellites** (tolerance default = 2.0 deg/day):

| Condition                | Score | Status   | Color |
|--------------------------|-------|----------|-------|
| |drift| <= 2.0           | 100   | Normal   | Green |
| |drift| <= 4.0           | 70    | Elevated | Yellow|
| |drift| > 4.0            | 40    | High     | Orange|

The wider IGSO tolerances reflect the fact that IGSO satellites inherently have larger apparent longitudinal excursions due to their inclined orbits.

### 5.3 Drift Stability Penalty

**Location**: `analysis/health_assessment.py:444`

After computing the base drift score, the system applies a **stability penalty** based on the standard deviation of drift over the observation window:

For GEO:
```
drift_stability = std_drift / drift_tolerance_gso
if drift_stability > 2:
    penalty = min(30, (drift_stability - 2) * 10)
    drift_score -= penalty
```

For IGSO/QZO:
```
drift_stability = std_drift / drift_tolerance_igso
if drift_stability > 1:
    penalty = min(20, (drift_stability - 1) * 10)
    drift_score -= penalty
```

**Physical rationale**: A satellite whose drift oscillates wildly even if its mean drift is low is experiencing unstable station-keeping, which is a sign of control system issues or environmental perturbations not being adequately managed.

### 5.4 Drift Trend Analysis

**Location**: `analysis/drift_analysis.py:93`

```python
def calculate_drift_trend(sat_df, recent_window=7):
    recent_drift = mean(last 7 points of |drift|)
    early_drift  = mean(first 7 points of |drift|)
    return |recent_drift| - |early_drift|
```

- Positive trend (> 0.01): drift magnitude increasing --> -10 penalty on drift score
- Negative trend (< -0.01): drift magnitude decreasing (improving) --> +5 bonus on drift score

**Edge case**: If DataFrame has fewer than 2 rows, trend = 0 (no penalty/bonus).
If fewer than `recent_window` rows, uses first/last individual values instead of windowed means.

---

## 6. Inclination Scoring

**Location**: `analysis/health_assessment.py:327`

### 6.1 Target Inclination Resolution

The system supports multiple configuration formats for target inclination:

1. `"inclination"` key (NavIC format): direct float value
2. `"inclination_target_deg"` key (QZSS GEO format): direct float value
3. `"inclination_target_deg_range"` key (QZSS IGSO format): tuple `(min, max)`, uses midpoint

If none of these keys exist, `target_inclination = None` and the inclination score is excluded from the overall score entirely.

### 6.2 Score Formula

```python
inc_deviation = |current_inclination - target_inclination|
inc_stability_penalty = min(20, std_inclination * 10)
inc_score = max(0, 100 - (inc_deviation / inc_tolerance) * 100 - inc_stability_penalty)
```

Where:
- `current_inclination` = the **latest** (most recent epoch) inclination value (instantaneous, not averaged)
- `inc_tolerance` = default 1.0 deg (configurable in sidebar)
- `std_inclination` = standard deviation of all inclination values in the window

### 6.3 Behavior Profile

With `inc_tolerance = 1.0` deg and zero stability penalty:

| Deviation | Score |
|-----------|-------|
| 0.0 deg   | 100   |
| 0.3 deg   | 70    |
| 0.5 deg   | 50    |
| 1.0 deg   | 0     |

The stability penalty can subtract up to 20 additional points. For example, if `std_inclination = 0.5`:
```
penalty = min(20, 0.5 * 10) = 5
```
A satellite with 0.3 deg deviation and 0.5 deg std would score `70 - 5 = 65`.

### 6.4 Edge Cases

- If `target_inclination` is `None`, `inc_score` is `None` and excluded from the weighted average.
- `std_inclination` is always computed on the full DataFrame, even if it has only 1 row (in which case std = 0, no penalty).

---

## 7. Maintenance Scoring

The maintenance score is the output of the pattern analysis system described in Section 4.4. It reflects whether the satellite is receiving timely station-keeping maneuvers.

### 7.1 Key Properties

- Range: [0, 100]
- 60% weight to E-W (longitude control), 40% to N-S (inclination control)
- Scores are clamped: E-W minimum is 50 (or 60 with `low` confidence), N-S minimum is 70 when no data
- The 1.5x overdue threshold is the critical boundary

### 7.2 Interaction with Confidence

Low-confidence patterns are penalized but bounded:
- A `very_low` confidence E-W score of 100 becomes `max(50, 100 * 0.7) = 70`
- A `low` confidence E-W score of 100 becomes `max(60, 100 * 0.85) = 85`

This prevents the system from giving full marks when the underlying data is too sparse to be trusted.

---

## 8. Uniformity Scoring

**Location**: `analysis/health_assessment.py:410`

### 8.1 Score Formula

```python
if num_maneuvers >= 2:
    uniformity_cov = calculate_maneuver_uniformity(maneuver_dates)
    if CoV <= threshold (default 0.8):
        uniformity_score = 100
    else:
        excess = CoV - threshold
        penalty = min(50, (excess / threshold) * 50)
        uniformity_score = 100 - penalty
elif num_maneuvers == 1:
    uniformity_score = 50
else:  # 0 maneuvers
    uniformity_score = 0
```

### 8.2 Behavior Profile

With threshold = 0.8:

| CoV   | Score |
|-------|-------|
| 0.0   | 100   |
| 0.4   | 100   |
| 0.8   | 100   |
| 1.0   | 87.5  |
| 1.2   | 75    |
| 1.6   | 50    |
| 2.4+  | 50    |

The penalty is capped at 50, so the minimum uniformity score (with 2+ maneuvers) is 50.

### 8.3 Edge Cases

- `uniformity_cov = None` (from `calculate_maneuver_uniformity`): uniformity_score = 50.
- 0 maneuvers: score = 0 (harshest possible -- the satellite is receiving no maintenance at all).

---

## 9. Longitude Deviation Scoring

### 9.1 Architecture Note

Unlike all other components, longitude deviation is computed in `app.py` (lines 1003-1188), not in the `analysis/` package. This is because it requires:
1. **Skyfield satellite objects** (parsed from TLEs)
2. **Skyfield propagation** to compute sub-satellite longitude over a 24-hour window
3. **Configuration data** for designated longitude slots

### 9.2 Mean Longitude Computation

```python
num_steps = 96  # 15-minute intervals over 24 hours
longitudes = []
for each 15-min step over the last 24 hours:
    geocentric = sat_obj.at(t)
    subpoint = wgs84.subpoint(geocentric)
    longitudes.append(subpoint.longitude.degrees)

# Circular mean (handles 360/0 wraparound correctly)
lons_rad = np.deg2rad(longitudes)
mean_lon = np.rad2deg(arctan2(mean(sin(lons_rad)), mean(cos(lons_rad))))
```

The circular mean is essential because naive arithmetic averaging fails near the 180/-180 degree boundary. For example, longitudes [179, -179] should average to 180, not 0.

### 9.3 Deviation Calculation

```python
diff = current_mean_lon - designated_lon
# Normalize to [-180, +180]
while diff > 180:  diff -= 360
while diff < -180: diff += 360
longitude_deviation = diff
```

### 9.4 Score Formula

**GEO satellites**:

| |deviation| | Score |
|-------------|-------|
| <= 0.5 deg  | 100   |
| 0.5-1.0 deg | 90 to 70 (linear) |
| 1.0-2.0 deg | 70 to 40 (linear) |
| > 2.0 deg   | 40 to 0 (linear, clamped at 0) |

Expressed as formulas:
```
if abs_dev <= 0.5: lon_score = 100
elif abs_dev <= 1.0: lon_score = 90 - ((abs_dev - 0.5) / 0.5) * 20
elif abs_dev <= 2.0: lon_score = 70 - ((abs_dev - 1.0) / 1.0) * 30
else: lon_score = max(0, 40 - ((abs_dev - 2.0) / 2.0) * 40)
```

**IGSO/QZO satellites**:

| |deviation| | Score |
|-------------|-------|
| <= 5.0 deg  | 100   |
| 5-10 deg    | 90 to 60 (linear) |
| > 10 deg    | 60 to 0 (linear, clamped at 0) |

### 9.5 Overall Score Recalculation

After the longitude score is computed, `app.py` **recalculates** the overall score by reading back the stored per-component scores (`_inc_score`, `_maintenance_score`, `_uniformity_score`, `_drift_score`) and adding the longitude component:

```python
_weights = {'inc': 0.30, 'maintenance': 0.25, 'uniformity': 0.10, 'drift': 0.20, 'longitude': 0.15}
_components = {k: score for k, score in available_component_scores}
_components['longitude'] = lon_score
new_score = sum(w[k] * _components[k] for k in _components) / sum(w[k] for k in _components)
```

**Fallback**: If no component scores can be read from the health_df row, the system blends the original 4-component score (which was normalized over 0.85 total weight) with longitude:
```
new_score = original_score * 0.85 + lon_score * 0.15
```

### 9.6 Edge Cases

- **No TLE data available**: longitude calculation is skipped entirely; the health score uses only the 4 other components normalized over 0.85 total weight.
- **Designated longitude is "N/A"**: satellite is skipped for longitude scoring.
- **Satellite not in `satellites_dop`**: Skyfield propagation is skipped.
- **Propagation exception**: silently caught (`pass`), satellite retains "N/A" for longitude fields.
- **TLE source priority**: session-state cached satellites_dop > bundled TLEs > CelesTrak API > Space-Track API.

---

## 10. Overall Score Composition

### 10.1 Formula

```python
weights = {'inc': 0.30, 'maintenance': 0.25, 'uniformity': 0.10, 'drift': 0.20, 'longitude': 0.15}

# Collect available components
components = {}
if inc_score is not None:          components['inc'] = inc_score
if maintenance_score is not None:  components['maintenance'] = maintenance_score
if uniformity_score is not None:   components['uniformity'] = uniformity_score
if drift_score is not None:        components['drift'] = drift_score
if longitude_score is not None:    components['longitude'] = longitude_score

# Normalize
total_weight = sum(weights[k] for k in components)
overall_score = sum(components[k] * weights[k] for k in components) / total_weight
```

### 10.2 Weight Normalization Example

If longitude is unavailable:
- Active weights: inc=0.30, maint=0.25, unif=0.10, drift=0.20 (sum = 0.85)
- Normalization: each component's effective weight = declared_weight / 0.85
  - inc: 0.30/0.85 = 35.3%
  - maint: 0.25/0.85 = 29.4%
  - unif: 0.10/0.85 = 11.8%
  - drift: 0.20/0.85 = 23.5%

### 10.3 Degenerate Case

If all component scores are `None`, `overall_score = 50.0` (neutral default).

---

## 11. Health Status Classification

| Score Range | Status          | Emoji |
|-------------|-----------------|-------|
| >= 85       | Excellent       | Green |
| 70 - 84     | Good            | Yellow|
| 50 - 69     | Fair            | Orange|
| < 50        | Needs Attention | Red   |

Note: The dashboard summary metrics use slightly different breakpoints:
- Healthy: >= 80
- Fair: 60-79
- Degraded: 40-59
- Critical: < 40

This is a minor inconsistency between the per-satellite label and the summary buckets.

---

## 12. Sample Calculations

### 12.1 Healthy GEO Satellite (e.g., NVS-01)

**Given**:
- Current inclination: 4.98 deg, target: 5.0 deg, std: 0.05 deg
- E-W maneuvers: 12 in 365 days, median interval 28 days, last maneuver 15 days ago
- N-S maneuvers: 4 in 365 days, median interval 85 days, last maneuver 40 days ago
- E-W/N-S confidence: high
- Current drift: 0.008 deg/day, std: 0.012 deg/day, trend: -0.002
- Longitude deviation: +0.3 deg from 131.5 deg
- Maneuver uniformity CoV: 0.45

**Component scores**:

1. **Inclination**: deviation = |4.98 - 5.0| = 0.02 deg
   - stability_penalty = min(20, 0.05 * 10) = 0.5
   - inc_score = max(0, 100 - (0.02/1.0)*100 - 0.5) = max(0, 100 - 2 - 0.5) = **97.5**

2. **Maintenance**:
   - E-W: not overdue (15 < 28*1.5=42), recency_ratio = 15/28 = 0.54 < 1.0 --> score = 100, high confidence --> no adjustment --> **100**
   - N-S: not overdue (40 < 85*1.5=127.5), recency_ratio = 40/85 = 0.47 < 0.5 --> score = 100, high confidence --> **100**
   - maintenance_score = 100 * 0.6 + 100 * 0.4 = **100**

3. **Drift**: |0.008| = 0.008 < 0.015 (0.3 * 0.05) --> base score = **100**, status = Excellent
   - stability: std/tol = 0.012/0.05 = 0.24 (< 2, no penalty)
   - trend: -0.002 (|trend| < 0.01, no bonus/penalty)
   - drift_score = **100**

4. **Longitude**: |0.3| <= 0.5 --> lon_score = **100**

5. **Uniformity**: CoV = 0.45 < 0.8 --> uniformity_score = **100**

**Overall Score**:
```
= (97.5*0.30 + 100*0.25 + 100*0.10 + 100*0.20 + 100*0.15) / (0.30+0.25+0.10+0.20+0.15)
= (29.25 + 25 + 10 + 20 + 15) / 1.0
= 99.25 / 1.0
= 99.3 --> "Excellent"
```

### 12.2 Degraded GEO Satellite (e.g., IRNSS-1C with drift issues)

**Given**:
- Current inclination: 6.5 deg, target: 5.0 deg, std: 0.8 deg
- E-W maneuvers: 2 in 365 days, median interval 180 days, last maneuver 300 days ago
- N-S maneuvers: 0 in 365 days
- E-W confidence: low
- Current drift: 0.12 deg/day, std: 0.08 deg/day, trend: +0.03
- Longitude deviation: +2.5 deg from 83.0 deg
- Maneuver uniformity CoV: 1.2

**Component scores**:

1. **Inclination**: deviation = |6.5 - 5.0| = 1.5 deg
   - stability_penalty = min(20, 0.8 * 10) = 8
   - inc_score = max(0, 100 - (1.5/1.0)*100 - 8) = max(0, 100 - 150 - 8) = **0**

2. **Maintenance**:
   - E-W: overdue (300 > 180*1.5=270), overdue_ratio = 300/180 = 1.67 < 2.0 --> score = 60
     - low confidence: max(60, 60 * 0.85) = max(60, 51) = **60**
   - N-S: no maneuvers --> ns_score = **70**
   - maintenance_score = 60 * 0.6 + 70 * 0.4 = 36 + 28 = **64**

3. **Drift**: |0.12| = 0.12, tolerance = 0.05
   - 0.05 < 0.12 <= 0.10? No. 0.10 < 0.12 <= 0.25? Yes. --> base score = 40, status = Poor
   - stability: 0.08/0.05 = 1.6 (< 2, no penalty)
   - trend: +0.03 > 0.01 --> -10 penalty
   - drift_score = max(0, 40 - 10) = **30**

4. **Longitude**: |2.5| > 2.0 --> lon_score = max(0, 40 - ((2.5 - 2.0)/2.0)*40) = max(0, 40 - 10) = **30**

5. **Uniformity**: CoV = 1.2, excess = 1.2 - 0.8 = 0.4
   - penalty = min(50, (0.4/0.8)*50) = min(50, 25) = 25
   - uniformity_score = 100 - 25 = **75**

**Overall Score**:
```
= (0*0.30 + 64*0.25 + 75*0.10 + 30*0.20 + 30*0.15) / 1.0
= (0 + 16 + 7.5 + 6 + 4.5) / 1.0
= 34.0 --> "Needs Attention"
```

### 12.3 IGSO Satellite with Missing Longitude Data

**Given**:
- Current inclination: 40.2 deg, target: 43.0 deg (midpoint of [39, 47] range), std: 0.3 deg
- E-W maneuvers: 3, median interval 120 days, last maneuver 50 days ago
- N-S maneuvers: 2, median interval 180 days, last maneuver 100 days ago
- Confidence: medium for both
- Current drift: 0.5 deg/day, std: 0.3 deg/day, trend: 0.0
- Longitude data: **unavailable** (TLE fetch failed)
- Maneuver uniformity CoV: 0.6

**Component scores**:

1. **Inclination**: deviation = |40.2 - 43.0| = 2.8 deg
   - stability_penalty = min(20, 0.3 * 10) = 3
   - inc_score = max(0, 100 - (2.8/1.0)*100 - 3) = max(0, 100 - 280 - 3) = **0**

   (Note: with default tolerance of 1.0 deg, even 1+ deg deviation zeroes the inclination score. For IGSO satellites with natural inclination ranges, this seems harsh -- see Improvements section.)

2. **Maintenance**:
   - E-W: not overdue (50 < 120*1.5=180), recency_ratio = 50/120 = 0.42 < 0.5 --> score = 100
     - medium confidence: no adjustment (only `low` and `very_low` are penalized) --> **100**
   - N-S: not overdue (100 < 180*1.5=270), recency_ratio = 100/180 = 0.56 < 1.0 --> score = 100
     - medium confidence --> **100**
   - maintenance_score = 100 * 0.6 + 100 * 0.4 = **100**

3. **Drift**: |0.5| <= 2.0 (IGSO tolerance) --> base score = **100**, status = Normal
   - stability: 0.3/2.0 = 0.15 (< 1, no penalty)
   - trend: 0.0 (no bonus/penalty)
   - drift_score = **100**

4. **Longitude**: **Not available** (excluded from weighted average)

5. **Uniformity**: CoV = 0.6 < 0.8 --> uniformity_score = **100**

**Overall Score** (4 components, total_weight = 0.85):
```
= (0*0.30 + 100*0.25 + 100*0.10 + 100*0.20) / 0.85
= (0 + 25 + 10 + 20) / 0.85
= 55 / 0.85
= 64.7 --> "Fair"
```

This illustrates how a single zeroed component (inclination at 30% weight) can drag the entire score down even when all other metrics are perfect. The weight re-normalization amplifies inclination's impact when longitude is absent (effective weight = 35.3%).

---

## 13. Edge Case Handling Across the Data Flow

### 13.1 Empty/No Data

| Stage | Condition | Handling |
|-------|-----------|----------|
| API fetch | Empty JSON response | `ValueError` raised with descriptive message |
| `assess_satellite_health_with_drift` | `sat_df is None or sat_df.empty` | Returns `{'Health Status': 'No Data', 'Overall Score': 0.0}` |
| `analyze_maneuver_pattern` | Zero maneuver events | Returns all `None` values, `maintenance_score = 0`, status = "No maneuvers detected" |
| Longitude calculation | No TLE data available | Warning displayed, longitude scoring skipped |
| Overall score | All component scores `None` | `overall_score = 50.0` (neutral fallback) |

### 13.2 Single Data Point

| Stage | Condition | Handling |
|-------|-----------|----------|
| Drift trend | `len(sat_df) < 2` | Returns 0 (no trend) |
| Maneuver uniformity | 1 maneuver | Returns `None`, uniformity_score = 50 |
| Pattern analysis | 1 interval | Uses that interval, confidence = `low` |
| Inclination std | 1 row | std = 0, no stability penalty |

### 13.3 Numerical Edge Cases

| Stage | Condition | Handling |
|-------|-----------|----------|
| MAD z-score | MAD = 0 (constant diffs) | Falls back to standard z-score; if std = 0 too, returns zeros |
| Pattern interval | `expected_interval <= 0` | Sanitized to `None` to avoid division by zero |
| Maneuver uniformity | `mean(intervals) = 0` | Returns `None` |
| DOP calculation | `len(A) < 4` (fewer than 4 visible satellites) | Returns `None` |
| DOP calculation | Ill-conditioned matrix (cond > 1e8) | Returns `None` |
| DOP calculation | Singular matrix (det < 1e-10) | Returns `None` |
| DOP calculation | Negative diagonal in covariance | Returns `None` |
| DOP calculation | GDOP > 100 | Returns `None` (unrealistic geometry) |
| DOP calculation | GDOP < PDOP or PDOP < HDOP | Returns `None` (sanity check violated) |

### 13.4 Type/Format Edge Cases

| Stage | Condition | Handling |
|-------|-----------|----------|
| GP column names | Lowercase from newer API version | Renamed to uppercase at ingestion |
| Commission date | Timezone-aware datetime | Stripped to timezone-naive via `tz_localize(None)` |
| Pattern dates | Mixed types (Timestamp vs datetime) | Coerced via `pd.to_datetime()` throughout |
| Overdue comparison | Timedelta vs float comparison | Wrapped in `try/except`, defaults to `is_overdue = False` |
| NaN in component scores | `float('nan')` in stored score | Checked with `isinstance(_v, float) and np.isnan(_v)` before use |

### 13.5 Constellation Ramp-Up

The deployed-date filtering mechanism (requiring >= 75% of expected satellites to have observations on a date) handles the period when a new satellite is being commissioned (e.g., QZS-6 from Feb 2025). Dates before the constellation was fully deployed are excluded so that sparse early data doesn't distort the health assessment.

---

## 14. Resilience Analysis

### 14.1 Strengths

1. **Robust statistics**: MAD z-scores for maneuver detection are resistant to outliers and non-Gaussian noise.
2. **Dual-gate maneuver detection**: Requiring both statistical significance AND physical magnitude prevents both noise-triggered and baseline-shift false positives.
3. **Persistence confirmation**: The pre/post median shift check eliminates transient spikes.
4. **Weight re-normalization**: Gracefully handles missing components without biasing the score.
5. **Circular mean longitude**: Correctly handles the 180/-180 deg wraparound.
6. **Commission date awareness**: Prevents pre-operational data from polluting scores.
7. **Multiple fallback paths**: API > bundled data > cached session state.

### 14.2 Weaknesses

1. **Step-wise maintenance scoring**: The overdue ratio creates discrete jumps (e.g., score drops from 90 to 60 at the 1.5x threshold). A continuous function would be smoother.
2. **Fixed inclination tolerance**: A single `inc_tolerance = 1.0 deg` is applied to all satellites regardless of type (GEO vs IGSO). IGSO satellites with natural 39-47 deg inclination ranges are unfairly penalized.
3. **Uniform confidence penalty**: The confidence adjustment uses `max()` clamping that can neutralize the penalty (e.g., if score is 60 and multiplier gives 60 * 0.85 = 51, `max(60, 51) = 60` -- no actual penalty applied).
4. **Asymmetric default scores**: No E-W maneuvers = 50, no N-S maneuvers = 70. While physically justified (E-W is more critical for GEO), the difference is somewhat arbitrary.
5. **Longitude computed outside analysis package**: Architectural inconsistency; the longitude score is interleaved with UI code in `app.py`, making it harder to test and maintain.
6. **Trend bonus/penalty asymmetry**: Improving drift gets +5, worsening drift gets -10. The worsening penalty is larger, which is conservative and arguably correct, but the +5 bonus has negligible impact.
7. **Silent exception swallowing**: Several `except Exception: pass` blocks in `app.py` and `health_assessment.py` hide errors that could indicate data quality issues.

---

## 15. Physical Significance Commentary

### 15.1 Inclination Control (30% weight)

**Significance**: For GEO satellites, inclination directly determines the north-south excursion of the sub-satellite point. A 1-degree inclination creates approximately +/-1 degree latitude oscillation (about 111 km north-south movement). For navigation satellites, this oscillation affects the satellite's visibility geometry and DOP values for users at high/low latitudes.

**Assessment**: The 30% weight is appropriate for GEO satellites. However, the absolute tolerance of 1.0 deg is too tight for IGSO satellites where inclination is a design parameter (e.g., QZSS IGSO satellites are designed for 39-47 deg inclination, and BeiDou IGSO for ~55 deg).

### 15.2 Maintenance Pattern (25% weight)

**Significance**: Regular station-keeping maneuvers are the primary indicator that a satellite is being actively controlled. A satellite that stops receiving maneuvers will drift uncontrolled within months (GEO drift budget is typically +/-0.05 deg/day). The 60/40 E-W/N-S split correctly reflects that E-W maneuvers are more frequent and more critical for GEO operational services.

**Assessment**: The weight is appropriate. The 1.5x overdue threshold is reasonable -- it allows some schedule flexibility (maneuver timing depends on ground station availability, delta-V budget, etc.) while still flagging missed windows.

### 15.3 Drift (20% weight)

**Significance**: Longitudinal drift is the most immediate indicator of station-keeping quality. Even small drift rates compound: 0.05 deg/day = 18.25 deg/year. For GEO communication/navigation satellites, the ITU coordination agreements specify +/-0.1 deg station-keeping boxes, so drift > 0.05 deg/day means the satellite will leave its box within a day.

**Assessment**: The default tolerance of 0.05 deg/day for GEO aligns with standard industry practice. The IGSO tolerance of 2.0 deg/day is generous, reflecting the natural longitudinal excursion of inclined orbits. The stability penalty and trend analysis add meaningful nuance beyond the instantaneous value.

### 15.4 Longitude Deviation (15% weight)

**Significance**: This directly measures whether the satellite is in its assigned orbital slot. For GEO satellites, the ITU-regulated station-keeping box is typically +/-0.1 deg, though operational practice often allows up to +/-0.5 deg. A satellite outside its box risks radio frequency interference with neighboring satellites and violates coordination agreements.

**Assessment**: The 15% weight is appropriate as a confirmation metric -- if drift is well-controlled, longitude deviation should also be small. The GEO thresholds (100 at <= 0.5 deg) are physically reasonable. The IGSO thresholds (100 at <= 5 deg) correctly account for the larger ground-track footprint.

### 15.5 Maneuver Uniformity (10% weight)

**Significance**: Uniform maneuver spacing indicates predictable, planned station-keeping. Irregular spacing may indicate reactive corrections (responding to anomalies) rather than proactive maintenance, or it may indicate that the satellite's delta-V budget is constrained and maneuvers are being rationed.

**Assessment**: The 10% weight is appropriately low -- uniformity is a secondary quality indicator, not a primary health metric. A satellite with irregular but effective maneuvers (low drift, correct inclination) is healthy; the uniformity score reflects operational quality rather than orbital health.

---

## 16. Suggested Improvements

### 16.1 Per-Constellation Inclination Tolerance (High Impact)

**Problem**: A single `inc_tolerance = 1.0 deg` is too tight for IGSO satellites (QZSS: 39-47 deg range, BeiDou: 55 +/- 1 deg). An IGSO satellite at 40.0 deg with a target midpoint of 43.0 deg scores 0 on inclination.

**Suggestion**: Use the inclination range or per-satellite tolerance from the config:

```python
# For satellites with inclination_target_deg_range:
inc_range = requirements.get("inclination_target_deg_range")
if inc_range:
    target_min, target_max = inc_range
    if target_min <= current_inclination <= target_max:
        inc_deviation = 0  # within range
    else:
        inc_deviation = min(abs(current_inclination - target_min), 
                           abs(current_inclination - target_max))
    effective_tolerance = (target_max - target_min) / 2  # half-width of range
```

**Physical justification**: IGSO satellites are designed to operate within a range of inclinations; any value within that range is equally healthy. The health score should only penalize deviations outside the range.

### 16.2 Continuous Maintenance Scoring (Medium Impact)

**Problem**: The step-wise overdue scoring creates abrupt jumps (100 -> 90 -> 60 -> 30 -> 0) that don't reflect the gradual degradation of station-keeping confidence.

**Suggestion**: Use a smooth decay function:

```python
# Continuous maintenance score
if expected_interval > 0:
    ratio = days_since_last / expected_interval
    if ratio <= 1.0:
        score = 100
    elif ratio <= 1.5:
        score = 100 - (ratio - 1.0) * 60  # linear 100 -> 70
    else:
        score = max(0, 70 * exp(-0.5 * (ratio - 1.5)))  # exponential decay
```

**Physical justification**: The urgency of a missed maneuver increases gradually, not in discrete steps. A satellite 1.6x overdue is only marginally worse than one at 1.4x overdue.

### 16.3 Eccentricity as a Health Component (Medium Impact)

**Problem**: Eccentricity is available in the GP data but not used in health scoring. For GEO satellites, eccentricity should be near-zero; elevated eccentricity indicates orbit anomalies or uncontrolled perturbations.

**Suggestion**: Add an eccentricity score with ~5% weight (reduce uniformity to 5%):

```python
if sat_type == 'GEO':
    if eccentricity <= 0.001:
        ecc_score = 100
    elif eccentricity <= 0.005:
        ecc_score = 80
    elif eccentricity <= 0.01:
        ecc_score = 50
    else:
        ecc_score = max(0, 50 - (eccentricity - 0.01) * 5000)
```

**Physical justification**: Eccentricity causes altitude oscillations (perigee/apogee difference). For GEO satellites, high eccentricity degrades pointing accuracy and link budgets, and is a direct indicator of orbit control quality.

### 16.4 Age-Weighted Drift Score (Low-Medium Impact)

**Problem**: The drift score uses only the latest (instantaneous) drift value. A satellite that was recently corrected (low current drift) but had high drift historically may appear healthier than warranted.

**Suggestion**: Blend instantaneous and recent-average drift:

```python
weighted_drift = 0.7 * current_drift + 0.3 * mean_drift_last_30_days
```

**Physical justification**: Post-maneuver drift is often artificially low and ramps up as perturbations accumulate. Using a blend gives a more realistic picture of the satellite's station-keeping quality over a full maneuver cycle.

### 16.5 Altitude/SMA Health Component (Medium Impact)

**Problem**: Altitude is displayed in the UI but not included in the health score. A satellite drifting toward graveyard orbit (SMA > 36,000 km above Earth center, or altitude > 35,986 km) should be flagged before it crosses the threshold.

**Suggestion**: Add an altitude anomaly check (not a weighted score component, but a binary override):

```python
nominal_altitude = 35786.0  # km
altitude_deviation = abs(current_altitude - nominal_altitude)
if altitude_deviation > 200:  # Approaching graveyard orbit
    overall_score = min(overall_score, 20)
    health_status = "Needs Attention"
    remarks.append("CRITICAL: Altitude anomaly detected -- possible graveyard orbit")
```

**Physical justification**: A satellite in graveyard orbit is permanently decommissioned. The altitude check serves as a safety net that overrides all other scores when the satellite is no longer in its operational orbit.

### 16.6 Move Longitude Scoring to the Analysis Package (Architectural)

**Problem**: Longitude deviation scoring is implemented inline in `app.py` (200+ lines interleaved with UI code), making it untestable, undocumented in the analysis package, and fragile to UI refactoring.

**Suggestion**: Create `analysis/longitude_analysis.py` with:
- `calculate_mean_longitude(sat_obj, ts, duration_hours=24, steps=96) -> float`
- `calculate_longitude_deviation(mean_lon, designated_lon) -> float`
- `score_longitude_deviation(deviation, sat_type) -> float`

Then call these from `app.py` with the Skyfield objects as parameters.

### 16.7 Configurable Health Thresholds per Constellation (Low Impact)

**Problem**: The health status boundaries (85/70/50) are hardcoded and applied uniformly to all constellations, regardless of their operational maturity or design differences.

**Suggestion**: Allow per-constellation threshold overrides in `config.py`:

```python
HEALTH_THRESHOLDS = {
    "default": {"excellent": 85, "good": 70, "fair": 50},
    "QZSS":    {"excellent": 80, "good": 65, "fair": 45},  # newer constellation, looser standards during ramp-up
}
```

### 16.8 Time-Decayed Confidence in Pattern Analysis (Low Impact)

**Problem**: Pattern confidence is based solely on the CoV of all intervals, treating a 1-year-old interval and a 1-week-old interval equally.

**Suggestion**: Apply exponential time-decay weights to intervals:

```python
now = observation_end
weights = [exp(-lambda * (now - date[i]).days) for i in range(len(intervals))]
weighted_std = sqrt(sum(w * (x - weighted_mean)^2) / sum(w))
```

**Physical justification**: Recent maneuver patterns are more predictive of current satellite operations than historical ones. A satellite that recently changed operators or underwent orbit modification should have its older patterns downweighted.

### 16.9 DOP-Informed Health Score (Aspirational)

**Problem**: DOP (Dilution of Precision) is computed in a separate tab and not fed back into the per-satellite health score. Yet the ultimate purpose of a navigation satellite is to contribute to good positioning accuracy.

**Suggestion**: For each satellite, compute its marginal DOP contribution (DOP with vs without the satellite) and incorporate it as a low-weight (5%) component. This directly measures the satellite's value to the constellation.

**Physical justification**: A satellite in the wrong position that nonetheless improves constellation geometry is still useful; conversely, a satellite in perfect position that adds nothing to DOP (e.g., colocated with another satellite) provides redundancy but not geometry improvement.

---

## Appendix A: Constants

| Constant | Value | Source |
|----------|-------|--------|
| `GEOSYNC_MEAN_MOTION` | 1.00273790935 rev/day | 86400 / 86164.09053 (sidereal day) |
| `R_EARTH` | 6371.0 km | Standard spherical approximation |
| `GEO_NOMINAL_ALTITUDE` | 35786.0 km | Standard GEO altitude |
| `GRAVEYARD_ORBIT_THRESHOLD` | 36000.0 km | ITU convention |
| Default `z_threshold` | 3.5 | MAD z-score threshold for maneuver detection |
| Default `sma_threshold` | 1.5 km | Minimum SMA change for E-W maneuver |
| Default `inc_threshold` | 0.1 deg | Minimum inclination change for N-S maneuver |
| Default `drift_tolerance_gso` | 0.05 deg/day | GEO drift tolerance |
| Default `drift_tolerance_igso` | 2.0 deg/day | IGSO drift tolerance |
| Default `uniformity_threshold` | 0.8 | CoV threshold for uniform spacing |

## Appendix B: Complete Data Flow Diagram

```
                    ┌─────────────────────┐
                    │   Space-Track.org    │
                    │   (GP History API)   │
                    └─────────┬───────────┘
                              │
                    fetch_tle_json_cached()
                    [Cached TTL=1hr]
                              │
                              ▼
                ┌─────────────────────────────┐
                │  fetch_and_classify_satellite │
                │  (api/spacetrack_api.py)      │
                ├─────────────────────────────┤
                │ 1. Standardize column names  │
                │ 2. Validate EPOCH, INCLINATION│
                │ 3. Compute LonDrift_deg/day  │
                │ 4. Compute altitude_km       │
                │ 5. Classify GEO/IGSO         │
                └─────────────┬───────────────┘
                              │
                     sat_df (DataFrame)
                              │
              ┌───────────────┼────────────────┐
              │               │                │
              ▼               ▼                ▼
    ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐
    │ Deployed-   │  │ detect_navik │  │ Pattern-period   │
    │ date filter │  │ _maneuvers() │  │ data fetch       │
    │ (75% rule)  │  │ (selected    │  │ (last 365 days)  │
    └──────┬──────┘  │  range)      │  └────────┬─────────┘
           │         └──────┬───────┘           │
           │                │                   │
           ▼                ▼                   ▼
    ┌──────────────────────────────────────────────────┐
    │        assess_satellite_health_with_drift()       │
    │        (analysis/health_assessment.py)             │
    ├──────────────────────────────────────────────────┤
    │                                                    │
    │  ┌──────────────────────────────────────────────┐ │
    │  │ 1. Resolve target inclination from config    │ │
    │  │ 2. Determine satellite type (GEO/IGSO/QZO)  │ │
    │  │ 3. Clamp observation window by commission    │ │
    │  │    date if applicable                        │ │
    │  └──────────────────────────────────────────────┘ │
    │                                                    │
    │  ┌──────────────┐  ┌────────────────────────────┐ │
    │  │ Inclination  │  │ analyze_maneuver_pattern() │ │
    │  │ Score        │  │ ┌─E-W pattern───────────┐  │ │
    │  │ deviation +  │  │ │ median interval       │  │ │
    │  │ stability    │  │ │ overdue check (1.5x)  │  │ │
    │  │ penalty      │  │ │ confidence (CoV)      │  │ │
    │  └──────────────┘  │ └───────────────────────┘  │ │
    │                     │ ┌─N-S pattern───────────┐  │ │
    │  ┌──────────────┐  │ │ median interval       │  │ │
    │  │ Drift Score  │  │ │ overdue check (1.5x)  │  │ │
    │  │ base +       │  │ │ confidence (CoV)      │  │ │
    │  │ stability +  │  │ └───────────────────────┘  │ │
    │  │ trend adj    │  │                             │ │
    │  └──────────────┘  │ Combined: 0.6*EW + 0.4*NS  │ │
    │                     └────────────────────────────┘ │
    │  ┌──────────────┐                                  │
    │  │ Uniformity   │                                  │
    │  │ Score (CoV)  │                                  │
    │  └──────────────┘                                  │
    │                                                    │
    │  ┌──────────────────────────────────────────────┐ │
    │  │ OVERALL SCORE (weight-normalized average)    │ │
    │  │ inc*0.30 + maint*0.25 + unif*0.10 + drift*0.20│ │
    │  │ / sum(active_weights)                        │ │
    │  │ (longitude NOT included yet -- computed below)│ │
    │  └──────────────────────────────────────────────┘ │
    └──────────────────────┬───────────────────────────┘
                           │
                   health_df (DataFrame)
                           │
                           ▼
    ┌──────────────────────────────────────────────────┐
    │         Longitude Deviation (app.py)              │
    ├──────────────────────────────────────────────────┤
    │ 1. Load TLEs: session_state > bundled > API      │
    │ 2. Parse TLEs into Skyfield EarthSatellite objs  │
    │ 3. For each satellite:                           │
    │    a. Propagate over 96 steps (24h, 15min each)  │
    │    b. Compute sub-satellite longitude at each    │
    │    c. Circular mean longitude                    │
    │    d. Deviation = mean_lon - designated_lon      │
    │    e. Normalize to [-180, +180]                  │
    │    f. Score using GEO/IGSO piecewise-linear fn   │
    │ 4. Recalculate overall score with 5 components   │
    │ 5. Update health status label                    │
    │ 6. Append longitude remarks                      │
    └──────────────────────┬───────────────────────────┘
                           │
                    Final health_df
                           │
                           ▼
    ┌──────────────────────────────────────────────────┐
    │              Streamlit Display                    │
    │  - Summary metrics (Healthy/Fair/Degraded/Crit)  │
    │  - Detailed health table                         │
    │  - Per-satellite expandable remarks              │
    │  - Cached in st.session_state                    │
    └──────────────────────────────────────────────────┘
```

## Appendix C: File Reference

| File | Key Functions | Role |
|------|---------------|------|
| `config/config.py` | N/A (constants only) | NORAD IDs, service requirements, thresholds, DOP quality levels |
| `api/spacetrack_api.py` | `fetch_and_classify_satellite()`, `fetch_tle_json_cached()` | GP history fetch and preprocessing |
| `api/celestrak_api.py` | `fetch_tles_with_fallback()` | Latest TLE fetch (no auth) |
| `data/tle_cache.py` | `load_bundled_tles()` | Load pre-cached JSON data |
| `analysis/maneuver_detection.py` | `detect_navik_maneuvers()`, `mad_zscore()`, `calculate_maneuver_uniformity()` | Statistical maneuver detection |
| `analysis/drift_analysis.py` | `calculate_longitudinal_drift()`, `assess_drift_health()`, `calculate_drift_trend()` | Drift computation and scoring |
| `analysis/health_assessment.py` | `assess_satellite_health_with_drift()`, `analyze_maneuver_pattern()` | 5-component health scoring |
| `analysis/dop_calculations.py` | `calculate_dop_values()`, `calculate_dop_for_location()` | DOP computation (separate from health score) |
| `app.py` | Lines 840-1190 | Orchestration, longitude scoring, UI |
