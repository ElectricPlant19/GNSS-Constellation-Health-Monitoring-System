# QZS-6 Parameter Sensitivity Analysis

## Overview

This test script performs comprehensive parameter sensitivity analysis for the QZS-6 satellite to determine if its critical health status is due to default threshold settings or actual satellite issues.

## Features

✅ **Maneuver Detection Testing**
- Tests 4 different parameter configurations (Default, Relaxed, Strict, QZSS-Optimized)
- Varies Z-score threshold, SMA threshold, inclination threshold, and persistence window
- Compares maneuver counts across configurations

✅ **Health Assessment Testing**
- Tests 4 different tolerance sets
- Varies inclination tolerance, drift tolerance, maneuver frequency limits
- Tracks health status changes across parameter variations

✅ **Drift Analysis Testing**
- Tests 5 different drift tolerance levels
- Evaluates drift assessment sensitivity
- Compares GSO vs IGSO tolerance approaches

✅ **Comprehensive Reporting**
- Terminal-only output (no frontend impact)
- Summary tables for all test categories
- Detailed analysis with recommendations
- Final conclusion on satellite condition

## Installation

No additional dependencies required beyond the main application requirements.

## Usage

### Basic Usage

```bash
python test_qzs6_analysis.py --username YOUR_USERNAME --password YOUR_PASSWORD
```

### Specify Custom Date Range

```bash
# Analyze last 180 days instead of default 365
python test_qzs6_analysis.py --username YOUR_USERNAME --password YOUR_PASSWORD --days 180
```

### Command Line Options

- `--username` (required): Your Space-Track.org username
- `--password` (required): Your Space-Track.org password
- `--days` (optional): Number of days of historical data to analyze (default: 365)

## Output Format

The script outputs to terminal in the following sections:

1. **Data Fetching**: Progress and data statistics
2. **Maneuver Detection Tests**: Results for each parameter set
3. **Health Assessment Tests**: Health scores and status for each configuration
4. **Drift Analysis Tests**: Drift assessments under different tolerances
5. **Summary Tables**: Comparative overview of all test results
6. **Detailed Analysis**: Consistency checks and sensitivity analysis
7. **Final Recommendation**: Conclusion and actionable recommendations

## Interpretation Guide

### Critical Status Consistency

- **Persists across all tests** → Genuine satellite issue
- **Appears in some tests** → Threshold-sensitive, borderline condition
- **Does not appear in adjusted tests** → Default thresholds may be too strict

### Maneuver Variance

- **High variance (>5 maneuvers)** → Detection parameters need review
- **Low variance (<5 maneuvers)** → Consistent detection, reliable results

### Recommended Actions

Based on the final conclusion:

**If genuine issue:**
- Further investigation required
- Review satellite telemetry
- Contact operators if applicable

**If threshold-sensitive:**
- Consider QZSS-specific parameters
- Adjust default thresholds
- Monitor trends over longer periods

## Example Output

```
================================================================================
              QZS-6 PARAMETER SENSITIVITY ANALYSIS
================================================================================

────────────────────────────────────────────────────────────────────────────────
📊 Fetching QZS-6 Satellite Data
────────────────────────────────────────────────────────────────────────────────

🛰️  Satellite: QZS-6
📡 NORAD ID: 43195
📅 Date Range: 2024-12-07 to 2025-12-07

⏳ Fetching data from Space-Track.org...
✅ Successfully fetched 365 TLE entries
📊 Data spans 365 days

...
```

## Notes

- **Non-Invasive**: This script does not modify any application files or configurations
- **Terminal Output Only**: All output goes to stdout/stderr, no frontend impact
- **Independent Execution**: Can be run while the Streamlit app is running
- **Comprehensive Testing**: Tests ~12 different parameter combinations total

## Troubleshooting

**Error: "QZS-6 NORAD ID not found"**
- Check that `config.py` has QZS-6 defined in QZSS_SATS

**Error: "Failed to fetch data"**
- Verify Space-Track credentials
- Check internet connection
- Ensure NORAD ID is correct

**No drift data available**
- This is normal if the satellite doesn't have orbit propagation data
- Drift tests will be skipped automatically

## Technical Details

The script tests the following parameter ranges:

**Maneuver Detection:**
- Z-score: 2.0 - 5.0
- SMA threshold: 0.3 - 3.0 km
- Inclination threshold: 0.002 - 0.020 degrees
- Persistence window: 1 - 3 TLEs

**Health Assessment:**
- Inclination tolerance: 0.5 - 2.0 degrees
- Drift tolerance: 0.02 - 0.20 degrees/day
- Min maneuvers/month: 0 - 1
- Max maneuvers/month: 6 - 10
- Uniformity threshold: 0.5 - 2.0

**Drift Analysis:**
- Tolerance range: 0.02 - 2.0 degrees/day

## Integration

This script uses the same modules as the main application:
- `config.py`: Satellite definitions and default parameters
- `spacetrack_api.py`: TLE data fetching
- `drift_analysis.py`: Drift calculations
- `maneuver_detection.py`: Maneuver identification
- `health_assessment.py`: Health scoring

Results from this analysis can inform parameter adjustments in the main application's sidebar settings.
