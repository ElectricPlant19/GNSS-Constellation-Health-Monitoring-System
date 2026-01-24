# 🛰️ GNSS Constellation Health Monitoring System

A comprehensive real-time monitoring and analysis system for multiple Global Navigation Satellite System (GNSS) constellations including **NavIC (IRNSS)**, **QZSS (Michibiki)**, and **BeiDou-3**. This application provides satellite health assessment, orbital drift analysis, maneuver detection, longitude slot deviation tracking, and Dilution of Precision (DOP) calculations through an interactive Streamlit web interface.

### 🚀 **Live Demo**: [https://gnss-constellation-health-monitoring-system.streamlit.app/](https://gnss-constellation-health-monitoring-system.streamlit.app/)

## 📑 Table of Contents

- [Key Features](#-key-features)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [What the Application Does](#-what-the-application-does)
- [Health Scoring System](#-health-scoring-system)
- [Understanding the Output](#-understanding-the-output)
- [Configuration & Customization](#-configuration--customization)
- [Troubleshooting](#-troubleshooting)
- [Technical Background](#-technical-background)

## 🌟 Key Features

- **Multi-Constellation Support**: Monitor NavIC, QZSS, and BeiDou-3 satellites
- **Advanced Health Assessment**: 5-component weighted health scoring (Inclination, Maintenance, Drift, Longitude Deviation, Uniformity)
- **Longitudinal Drift Analysis**: Track east-west drift for station-keeping assessment
- **Longitude Slot Deviation**: Monitor deviation from designated orbital slots
- **Maneuver Detection**: Automated detection of E-W and N-S orbital correction maneuvers
- **DOP Calculations**: Dilution of Precision analysis for regional locations
- **Interactive Visualizations**: Rich time-series plots, sky plots, and geographic maps
- **Modular Architecture**: Clean, maintainable codebase with separated concerns

## ⚡ Quick Start

**Try it online:** [Live Demo](https://gnss-constellation-health-monitoring-system.streamlit.app/)

**Or run locally:**

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the application
streamlit run app.py

# 3. Open browser at http://localhost:8501

# 4. Enter Space-Track credentials and start analyzing!
```

**First time user?** Register for free at [Space-Track.org](https://www.space-track.org/auth/createAccount)

## 📁 Project Structure

```
final__dash/
├── app.py                          # Main Streamlit application (entry point)
├── requirements.txt                # Python dependencies
├── README.md                       # This documentation
│
├── config/
│   └── config.py                   # Configuration constants and satellite data
│
├── api/
│   ├── spacetrack_api.py          # Space-Track.org API client
│   └── celestrak_api.py           # CelesTrak API client
│
├── analysis/
│   ├── __init__.py                # Package exports
│   ├── health_assessment.py       # Satellite health scoring
│   ├── drift_analysis.py          # Longitudinal drift calculations
│   ├── maneuver_detection.py      # Orbital maneuver detection
│   └── dop_calculations.py        # DOP calculations
│
├── visualizations/
│   ├── __init__.py                # Package exports
│   └── visualization.py           # All plotting and visualization functions
│
└── tests/
    ├── test_health_run.py
    ├── test_qzs6_analysis.py
    ├── test_qzs6_commission.py
    ├── find_beidou_norad_ids.py
    ├── run_qzs6_test.sh
    └── TEST_QZS6_README.md
```

## 🔧 Module Descriptions

### `config/config.py`
- Centralized configuration and constants
- Satellite NORAD IDs for NavIC, QZSS, BeiDou-3
- Geographic points for DOP analysis (India, Japan, China)
- Service requirements and tolerances
- Default analysis parameters
- DOP quality thresholds

### `api/`
**spacetrack_api.py**: Space-Track.org API integration
- `get_spacetrack_session()`: Authentication
- `fetch_tle_json_cached()`: Cached GP history data
- `fetch_multiple_tles()`: Latest TLE data
- `fetch_and_classify_satellite()`: Complete satellite data processing

**celestrak_api.py**: CelesTrak API integration for backup TLE data

### `analysis/`
**health_assessment.py**: Comprehensive satellite health scoring
- `assess_satellite_health_with_drift()`: Complete health assessment
- `analyze_maneuver_pattern()`: Dynamic pattern-based maneuver analysis
- Integrates inclination, maintenance, drift, longitude deviation, and uniformity

**drift_analysis.py**: Longitudinal drift calculations
- `calculate_longitudinal_drift()`: Mean motion to drift conversion
- `assess_drift_health()`: Drift-based health assessment
- `calculate_drift_trend()`: Drift trend analysis over time
- `get_drift_direction()`: Drift direction with emojis

**maneuver_detection.py**: Statistical orbital maneuver detection
- `detect_navik_maneuvers()`: Main detection algorithm
- `calculate_maneuver_uniformity()`: Spacing analysis
- MAD (Median Absolute Deviation) z-score method

**dop_calculations.py**: DOP calculations and satellite positioning
- `parse_tle_data()`: Parse TLE into satellite objects
- `calculate_satellite_position()`: Position calculations
- `calculate_dop_for_location()`: Location-specific DOP
- `calculate_bounding_boxes()`: Ground track bounding boxes
- `get_dop_quality()`: DOP quality assessment

### `visualizations/`
**visualization.py**: All plotting and visualization functions
- `plot_individual_satellites()`: Individual satellite plots
- `plot_combined_drift()`: Combined drift comparison
- `plot_bounding_boxes()`: Ground track visualizations
- `plot_sky_plot()`: Azimuth-elevation sky plots
- `plot_dop_over_time()`: DOP time series
- `plot_mean_longitude_map()`: Geographic longitude deviation map
- `plot_drift_distribution()`: Drift distribution analysis
- And more specialized plotting functions

### `app.py`
Main Streamlit application providing:
- User interface and sidebar configuration
- Data fetching and processing orchestration
- Results display and visualization coordination
- Session state management
- Longitude deviation calculation using satellite propagation

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Space-Track.org account (free registration)

### Installation

1. **Clone or download the repository**
   ```bash
   cd final__dash
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # Linux/Mac
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Running the Application

1. **Start the Streamlit server**
   ```bash
   streamlit run app.py
   ```

2. **Access the application**
   - Opens automatically at http://localhost:8501
   - Enter Space-Track credentials in sidebar
   - Select constellation and date range
   - Click "Fetch Data & Run Analysis"

### Example Workflow

```
1. Launch Application
   └─> streamlit run app.py

2. Configure Settings (Sidebar)
   ├─> Enter Space-Track credentials
   ├─> Select constellation: NavIC
   ├─> Set date range: 2025-01-01 to 2025-10-01
   └─> Adjust parameters (optional)

3. Run Analysis
   └─> Click "Fetch Data & Run Analysis"

4. View Results
   ├─> Health Overview Tab
   ├─> Drift & Maneuvers Tab
   ├─> DOP Analysis Tab
   └─> Visualizations Tab

5. Generate Additional Analysis
   └─> Run DOP Analysis for specific locations
```

## 📊 What the Application Does

### Health Assessment
- **5-Component Scoring System**: Comprehensive 0-100 health score
  - Inclination Control (30%): Target deviation monitoring
  - Maintenance Pattern (25%): E-W and N-S maneuver analysis
  - Drift Analysis (20%): Longitudinal drift assessment
  - Longitude Deviation (15%): Slot position accuracy
  - Uniformity (10%): Maneuver spacing regularity

### Orbital Analysis
- **Longitudinal Drift**: Degrees per day calculation
- **Drift Direction**: Eastward/Westward identification
- **Altitude Monitoring**: Semi-major axis tracking
- **Inclination Trends**: Change detection over time
- **Graveyard Orbit Detection**: Decommissioned satellite identification

### Longitude Slot Deviation
**NEW FEATURE**: Monitors satellite position relative to designated orbital slots
- Uses Skyfield propagation for accurate position calculation
- Computes circular mean longitude over 24 hours
- Calculates angular deviation with wrap-around handling
- Color-coded deviation table:
  - 🟢 Green: ≤ 0.5° (Good)
  - 🟡 Yellow: 0.5° - 1.0° (Acceptable)
  - 🔴 Red: > 1.0° (Needs Attention)

### DOP Analysis
- **GDOP**: Geometric Dilution of Precision
- **PDOP**: Position Dilution of Precision
- **HDOP**: Horizontal Dilution of Precision
- **VDOP**: Vertical Dilution of Precision
- **TDOP**: Time Dilution of Precision
- **Regional Coverage**: Location-specific calculations

### Visualizations
- Individual satellite time-series plots
- Combined constellation comparison
- Sky plots (azimuth-elevation diagrams)
- Geographic longitude deviation map with designated slots
- Ground track bounding boxes
- DOP time-series (30 days)
- Drift distribution analysis

## 🎯 Health Scoring System

### Component Weights

| Component | Weight | GSO Tolerance | IGSO Tolerance |
|-----------|--------|---------------|----------------|
| **Inclination** | 30% | ± 1.0° | ± 4.0° |
| **Maintenance** | 25% | Pattern-based | Pattern-based |
| **Drift** | 20% | < 0.05°/day | < 2.0°/day |
| **Longitude Deviation** | 15% | < 0.5° | < 5.0° |
| **Uniformity** | 10% | CoV < 0.8 | CoV < 0.8 |

### Health Status Indicators

| Status | Score Range | Color | Meaning |
|--------|-------------|-------|---------|
| 🟢 Excellent | 85-100 | Green | All parameters within ideal range |
| 🟡 Good | 70-84 | Yellow | Within operational tolerance |
| 🟠 Fair | 50-69 | Orange | Some parameters degraded, monitoring needed |
| 🔴 Needs Attention | 0-49 | Red | Significant deviations, corrective action required |

## 📈 Understanding the Output

### Key Metrics Explained

**Inclination Deviation**:
- **Excellent**: < 0.3 × tolerance
- **Good**: < tolerance
- **Poor**: > tolerance

**Longitudinal Drift** (GSO):
- **Excellent**: < 0.015°/day
- **Good**: < 0.05°/day
- **Fair**: 0.05° - 0.10°/day
- **Poor**: > 0.10°/day

**Longitude Slot Deviation** (GSO):
- **Excellent**: ≤ 0.5°
- **Good**: 0.5° - 1.0°
- **Needs Attention**: > 1.0°

**Maneuvers per Month**:
- **Typical**: 1-8 maneuvers
- **Insufficient**: < 1
- **Excessive**: > 8

**DOP Values**:
- **Ideal**: < 1
- **Excellent**: 1-2
- **Good**: 2-5
- **Moderate**: 5-10
- **Fair**: 10-20
- **Poor**: > 20

## 🔧 Configuration & Customization

### Supported Constellations

| Constellation | Satellites | Coverage | Status |
|---------------|------------|----------|--------|
| **NavIC (IRNSS)** | 7 (3 GEO, 4 IGSO) | India & surrounding | ✅ Fully configured |
| **QZSS (Michibiki)** | 5 (3 IGSO, 2 GEO) | Japan & Asia-Pacific | ✅ Fully configured |
| **BeiDou-3** | 7 (3 IGSO, 4 GEO) | Asia-Pacific | ✅ Fully configured |

### NavIC Orbital Slots
- **GEO**: 32.5°E, 83°E, 131.5°E (inclination ~5°)
- **GSO**: 55°E (2 sats), 111.75°E (2 sats) (inclination ~29-30°)

### Analysis Parameters

Customizable through sidebar:

**Maneuver Detection:**
- Z-Score Threshold (default: 3.5)
- SMA Change (km): 0.5
- Inclination Change (°): 0.01
- Persistence Window: 2

**Health Assessment:**
- Inclination Tolerance (°): 1.0 (NavIC), 4.0 (QZSS IGSO)
- GSO Drift Tolerance (°/day): 0.05
- Min/Max Maneuvers/Month: 1-8
- Uniformity Threshold: 0.8

**DOP Settings:**
- Elevation Mask: 0-30° (default: 5°)
- Custom location option
- Timestep: 15 minutes

## 🐛 Troubleshooting

### Common Issues

**"Failed to fetch TLE data"**
- Verify Space-Track credentials
- Check internet connection
- Ensure NORAD IDs are valid in `config/config.py`

**"No satellites parsed"**
- Check NORAD IDs are set (not `None`)
- For BeiDou-3, run `tests/find_beidou_norad_ids.py` first

**"Module not found" errors**
- Ensure all files are in correct directory structure
- Verify dependencies: `pip list`
- Check import paths use new structure

**Slow performance**
- Reduce date range
- Enable "One TLE per day" option
- Close other Streamlit instances

**Longitude deviation shows "N/A"**
- Run DOP Analysis first to create satellite objects
- Ensure constellation is selected correctly
- Check designated longitude values in config

## 🎓 Technical Background

### Algorithms

**Drift Calculation**: Based on mean motion deviation from geosynchronous rate (1.00273790935 rev/day)

**Longitude Deviation**: 
- Uses Skyfield satellite propagation
- Calculates circular mean over 24 hours
- Accounts for ±180° wrap-around
- Compares to designated slot from config

**Maneuver Detection**: MAD z-score method with persistence filtering

**Health Scoring**: Multi-factor weighted system with dynamic pattern recognition

**DOP Calculation**: Standard geometric dilution using satellite-observer geometry

### Data Sources
- **Primary**: Space-Track.org (GP history, TLE data)
- **Backup**: CelesTrak (public TLE data)
- **Calculations**: Skyfield library for precise positioning

### Performance
- Analysis time: 30-60 seconds for 9 months
- Memory usage: ~500MB for full constellation
- Supports concurrent satellite analysis

## 📋 Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `streamlit` | ≥1.28.0 | Web framework |
| `numpy` | ≥1.24.0 | Numerical computations |
| `pandas` | ≥2.0.0 | Data manipulation |
| `plotly` | ≥5.17.0 | Interactive plots |
| `folium` | ≥0.14.0 | Geographic maps |
| `streamlit-folium` | ≥0.13.0 | Folium integration |
| `requests` | ≥2.31.0 | HTTP requests |
| `skyfield` | ≥1.46 | Satellite positioning |

## 🚀 Future Enhancements

- [ ] GPS, GLONASS, Galileo support
- [ ] PDF report export
- [ ] Real-time alerting system
- [ ] Historical trend comparison
- [ ] Machine learning anomaly detection
- [ ] API endpoint
- [ ] Multi-user configurations

## 📝 License & Credits

This project uses data from Space-Track.org (free registration required). Built with open-source libraries following modular design principles.

**Made with ❤️ for GNSS monitoring and analysis**

---

For detailed technical documentation, see individual module docstrings and comments in the source code.
