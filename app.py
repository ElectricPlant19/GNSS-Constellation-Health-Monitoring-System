"""
Main NavIC Comprehensive Monitoring Application
Streamlit-based interface for satellite monitoring and analysis
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta, timezone
from skyfield.api import load

# Import our modular components
from config.config import (
    NAVIK_SATS, INDIA_EXTREME_POINTS, JAPAN_KEY_POINTS, CHINA_KEY_POINTS, INACTIVE_SATELLITES, DEFAULT_PARAMS,
    QZSS_SATS, QZSS_SERVICE_REQUIREMENTS,
    BEIDOU3_SATS, BEIDOU3_SERVICE_REQUIREMENTS,
    GRAVEYARD_ORBIT_MIN, GEO_NOMINAL_ALTITUDE, GEO_ALTITUDE_TOLERANCE
)
from api.spacetrack_api import fetch_and_classify_satellite, fetch_multiple_tles
from api.celestrak_api import fetch_tles_from_celestrak
from analysis.drift_analysis import assess_drift_health, get_drift_direction
from analysis.maneuver_detection import detect_navik_maneuvers
from analysis.health_assessment import assess_satellite_health_with_drift
from analysis.dop_calculations import parse_tle_data, calculate_dop_for_location, get_dop_quality
from visualizations.visualization import (
    plot_individual_satellites, plot_combined_drift, plot_bounding_boxes,
    plot_sky_plot, plot_animated_sky_plot, plot_dop_over_time, plot_combined_inclination,
    plot_combined_altitude, plot_drift_distribution, plot_drift_vs_altitude,
    plot_constellation_coverage, plot_mean_longitude_map, plot_historical_central_longitude
)

# Initialize timescale globally
ts = load.timescale()


def get_graveyard_satellites(df_all):
    """
    Identify satellites that are in graveyard orbit.
    
    Args:
        df_all: DataFrame containing satellite orbital data
        
    Returns:
        set: Set of satellite names that are in graveyard orbit
    """
    
    graveyard_sats = set()
    
    for sat_name in df_all['satellite'].unique():
        sat_df = df_all[df_all['satellite'] == sat_name]
        
        # Check if satellite has altitude data
        if 'altitude_km' not in sat_df.columns or sat_df['altitude_km'].isna().all():
            continue
            
        # Get current altitude (most recent data point)
        current_altitude = sat_df['altitude_km'].iloc[-1]
        
        # Check for graveyard orbit
        if current_altitude >= GRAVEYARD_ORBIT_MIN:
            graveyard_sats.add(sat_name)
    
    return graveyard_sats


def check_graveyard_orbit_satellites(df_all):
    """
    Check for satellites that may have been moved to graveyard orbit.
    Prints warnings to terminal for all satellites with abnormally high altitudes.
    
    Args:
        df_all: DataFrame containing satellite orbital data
    """
    
    print("\n" + "="*80)
    print("🛰️  GRAVEYARD ORBIT DETECTION - SATELLITE STATUS CHECK")
    print("="*80)
    
    for sat_name in sorted(df_all['satellite'].unique()):
        sat_df = df_all[df_all['satellite'] == sat_name].copy()
        
        # Check if satellite has altitude data
        if 'altitude_km' not in sat_df.columns or sat_df['altitude_km'].isna().all():
            print(f"\n📡 {sat_name}")
            print(f"   ⚠️  No altitude data available")
            continue
        
        # Get mean inclination to determine satellite type
        mean_incl = sat_df['INCLINATION'].mean()
        
        # Determine satellite type
        if mean_incl < 10.0:
            sat_type = "GSO"
        else:
            sat_type = "IGSO"
        
        # Get recent altitude (last 10% of data points)
        recent_data = sat_df.tail(max(1, len(sat_df) // 10))
        recent_altitude = recent_data['altitude_km'].mean()
        max_altitude = sat_df['altitude_km'].max()
        min_altitude = sat_df['altitude_km'].min()
        current_altitude = sat_df['altitude_km'].iloc[-1]
        
        # Calculate deviation from nominal GEO altitude
        altitude_deviation = current_altitude - GEO_NOMINAL_ALTITUDE
        
        # Determine status
        status = "✅ OPERATIONAL"
        details = []
        
        # Check for graveyard orbit (applies to both GSO and IGSO)
        if current_altitude >= GRAVEYARD_ORBIT_MIN:
            status = "💀 GRAVEYARD ORBIT (DEAD)"
            details.append(f"Current altitude ({current_altitude:.1f} km) is in graveyard orbit zone (>{GRAVEYARD_ORBIT_MIN:.1f} km)")
            details.append(f"Satellite has been raised {altitude_deviation:.1f} km above nominal GEO altitude")
        elif sat_type == "GSO" and abs(altitude_deviation) > GEO_ALTITUDE_TOLERANCE:
            # For GSO satellites, check if they're within operational tolerance
            if altitude_deviation > 0:
                status = "⚠️  ELEVATED ORBIT (POSSIBLY DECOMMISSIONED)"
                details.append(f"Altitude {altitude_deviation:.1f} km above nominal GEO ({GEO_NOMINAL_ALTITUDE:.1f} km)")
            else:
                status = "⚠️  LOW ORBIT (ANOMALOUS)"
                details.append(f"Altitude {abs(altitude_deviation):.1f} km below nominal GEO ({GEO_NOMINAL_ALTITUDE:.1f} km)")
        elif sat_type == "IGSO":
            # For IGSO satellites, just note their altitude (they have elliptical orbits)
            details.append(f"IGSO satellite with elliptical orbit (altitude varies)")
        
        # Print satellite status
        print(f"\n📡 {sat_name}")
        print(f"   Status: {status}")
        print(f"   Type: {sat_type} (Inclination: {mean_incl:.2f}°)")
        print(f"   Current Altitude: {current_altitude:.2f} km")
        print(f"   Recent Avg Altitude: {recent_altitude:.2f} km")
        print(f"   Altitude Range: {min_altitude:.2f} - {max_altitude:.2f} km")
        print(f"   Deviation from GEO: {altitude_deviation:+.2f} km")
        
        if details:
            print(f"   ℹ️  NOTES:")
            for detail in details:
                print(f"      - {detail}")
    
    print("\n" + "="*80)
    print("📊 GRAVEYARD ORBIT CHECK COMPLETE")
    print("="*80 + "\n")


# Streamlit Configuration
st.set_page_config(
    page_title="GNSS Health Monitor",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "# GNSS Health Monitor\nComprehensive satellite constellation monitoring and analysis system."
    }
)

# Custom CSS for modern, professional UI
st.markdown("""
<style>
    /* Main color scheme - using relative colors that work in both themes */
    :root {
        --primary-color: #1e3a8a;
        --secondary-color: #3b82f6;
        --success-color: #10b981;
        --warning-color: #f59e0b;
        --danger-color: #ef4444;
        --info-color: #06b6d4;
    }
    
    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .main-header h1 {
        color: white;
        margin: 0;
        font-size: 2.5rem;
        font-weight: 700;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    .main-header p {
        color: rgba(255, 255, 255, 0.9);
        margin: 0.5rem 0 0 0;
        font-size: 1.1rem;
    }
    
    /* Metric cards - theme aware */
    .metric-card {
        background: color-mix(in srgb, var(--secondary-color) 10%, transparent);
        border-radius: 8px;
        padding: 1.5rem;
        border-left: 4px solid var(--secondary-color);
        margin-bottom: 1rem;
    }
    
    .metric-card h3 {
        opacity: 0.7;
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin: 0 0 0.5rem 0;
    }
    
    .metric-card .value {
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
    }
    
    /* Status badges - semi-transparent for theme compatibility */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.875rem;
        font-weight: 600;
        text-align: center;
    }
    
    .status-healthy {
        background-color: rgba(16, 185, 129, 0.2);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    
    .status-fair {
        background-color: rgba(245, 158, 11, 0.2);
        color: #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    
    .status-degraded {
        background-color: rgba(251, 146, 60, 0.2);
        color: #fb923c;
        border: 1px solid rgba(251, 146, 60, 0.3);
    }
    
    .status-critical {
        background-color: rgba(239, 68, 68, 0.2);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    
    /* Sidebar improvements */
    section[data-testid="stSidebar"] > div {
        padding-top: 2rem;
    }
    
    /* Better section headers */
    .section-header {
        color: var(--primary-color);
        font-size: 1.5rem;
        font-weight: 700;
        margin: 2rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 3px solid var(--secondary-color);
    }
    
    /* Info cards - semi-transparent backgrounds for theme compatibility */
    .info-card {
        background: color-mix(in srgb, var(--info-color) 15%, transparent);
        border-left: 4px solid var(--info-color);
        border-radius: 8px;
        padding: 1rem 1.5rem;
        margin: 1rem 0;
    }
    
    .success-card {
        background: color-mix(in srgb, var(--success-color) 15%, transparent);
        border-left: 4px solid var(--success-color);
        border-radius: 8px;
        padding: 1rem 1.5rem;
        margin: 1rem 0;
    }
    
    .warning-card {
        background: color-mix(in srgb, var(--warning-color) 15%, transparent);
        border-left: 4px solid var(--warning-color);
        border-radius: 8px;
        padding: 1rem 1.5rem;
        margin: 1rem 0;
    }
    
    /* Button improvements */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        padding: 0.625rem 1.25rem;
        transition: all 0.2s;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    }
    
    /* Expander styling - let Streamlit handle colors */
    .streamlit-expanderHeader {
        border-radius: 8px;
        font-weight: 600;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 12px 24px;
        font-weight: 600;
    }
    
    /* Remove extra padding */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Improved spacing */
    h1, h2, h3 {
        margin-top: 1.5rem;
    }
    
    /* Loading state */
    .stSpinner > div {
        border-top-color: var(--secondary-color);
    }
</style>
""", unsafe_allow_html=True)

# Modern header
st.markdown("""
<div class="main-header">
    <h1>🛰️ GNSS Health Monitor</h1>
    <p>Comprehensive satellite constellation monitoring and analysis</p>
</div>
""", unsafe_allow_html=True)

# ==================== SIDEBAR CONFIGURATION ====================

st.sidebar.markdown("### ⚙️ Configuration")
st.sidebar.markdown("---")

# Credentials - Always visible
st.sidebar.markdown("#### 🔐 Space-Track Credentials")
username = st.sidebar.text_input("Username", value="", type="default", help="Your Space-Track.org username")
password = st.sidebar.text_input("Password", value="", type="password", help="Your Space-Track.org password")

st.sidebar.markdown("---")

# Constellation Selection - Always visible
st.sidebar.markdown("#### �️ Constellation")
constellation = st.sidebar.selectbox(
    "Select constellation", 
    ["NavIC", "QZSS", "BeiDou-3"], 
    index=0,
    help="Choose which satellite constellation to analyze"
)

# Per-constellation configuration and info
if constellation == "NavIC":
    SAT_DICT = NAVIK_SATS
    SERVICE_REQS = None
    system_label = "NavIC"
    LOCATION_POINTS = INDIA_EXTREME_POINTS
    st.sidebar.info("🇮🇳 **NavIC (IRNSS)**: 7 satellites providing regional navigation coverage for India")
    include_inactive_sats = st.sidebar.checkbox(
        "Include inactive satellites in DOP", value=False,
        help="IRNSS-1C, 1D, 1E are currently inactive"
    )
elif constellation == "QZSS":
    SAT_DICT = QZSS_SATS
    SERVICE_REQS = QZSS_SERVICE_REQUIREMENTS
    system_label = "QZSS"
    LOCATION_POINTS = JAPAN_KEY_POINTS
    include_inactive_sats = False
    st.sidebar.info("🇯🇵 **QZSS (Michibiki)**: 5 satellites with orbit corrections ~every 6 months")
else:  # BeiDou-3
    SAT_DICT = BEIDOU3_SATS
    SERVICE_REQS = BEIDOU3_SERVICE_REQUIREMENTS
    system_label = "BeiDou-3"
    LOCATION_POINTS = CHINA_KEY_POINTS
    include_inactive_sats = False
    st.sidebar.info("🇨🇳 **BeiDou-3**: IGSO & GEO satellites for Asia-Pacific coverage")

st.sidebar.markdown("---")

# Date Range - Always visible
st.sidebar.markdown("#### 📅 Analysis Period")
col1, col2 = st.sidebar.columns(2)

# Calculate default date range: last 90 days
from datetime import date as date_class, timedelta as timedelta_class
default_end = date_class.today()
default_start = default_end - timedelta_class(days=90)

with col1:
    start_date = st.date_input("Start date", value=default_start)
with col2:
    end_date = st.date_input("End date", value=default_end)

start_date_str = start_date.strftime("%Y-%m-%d")
end_date_str = end_date.strftime("%Y-%m-%d")
daily_only = st.sidebar.checkbox("One TLE per day", value=True, help="Keep only first TLE entry per day to reduce data volume")
use_historical_pattern = True  # Always use historical pattern for maneuver detection

st.sidebar.markdown("---")

# DOP Settings - Simplified
st.sidebar.markdown("#### 📡 DOP Location")
use_custom_location = st.sidebar.checkbox("Custom location", value=False)
custom_lat = 28.7
custom_lon = 77.1
if use_custom_location:
    custom_lat = st.sidebar.number_input("Latitude (°)", min_value=-90.0, max_value=90.0, 
                                         value=28.7, step=0.1, format="%.3f")
    custom_lon = st.sidebar.number_input("Longitude (°)", min_value=-180.0, max_value=180.0, 
                                         value=77.1, step=0.1, format="%.3f")

elevation_mask_deg = st.sidebar.slider("Elevation Mask (°)", min_value=0, max_value=30, 
                                       value=DEFAULT_PARAMS["elevation_mask_deg"], step=1,
                                       help="Minimum elevation angle for satellite visibility")

st.sidebar.markdown("---")

# Advanced Settings - Collapsed by default
with st.sidebar.expander("⚙️ Advanced Settings", expanded=False):
    st.markdown("##### Maneuver Detection")
    z_threshold = st.number_input("Z-Score Threshold", min_value=1.0, max_value=10.0, 
                                  value=DEFAULT_PARAMS["z_threshold"], step=0.5,
                                  help="Statistical threshold for detecting orbital changes")
    sma_threshold = st.number_input("SMA Change (km)", min_value=0.1, 
                                    max_value=5.0, value=DEFAULT_PARAMS["sma_threshold"], step=0.1,
                                    help="Semi-major axis change threshold")
    inc_threshold = st.number_input("Inclination Change (°)", 
                                    min_value=0.001, max_value=0.1, value=DEFAULT_PARAMS["inc_threshold"], 
                                    step=0.001, format="%.3f",
                                    help="Inclination change threshold")
    persist_window = st.number_input("Persistence Window", min_value=1, max_value=10, 
                                     value=DEFAULT_PARAMS["persist_window"], step=1,
                                     help="Number of consecutive TLEs to confirm maneuver")
    
    st.markdown("---")
    st.markdown("##### Health Assessment")
    inclination_tolerance = st.number_input("Inclination Tolerance (°)", 
                                           min_value=0.1, max_value=5.0, 
                                           value=4.0 if constellation == "QZSS" else DEFAULT_PARAMS["inclination_tolerance"], step=0.1,
                                           help="QZSS IGSO satellites have ±4° tolerance (inclination target 43°)")
    drift_tolerance_gso = st.number_input("GSO Drift Tolerance (°/day)", 
                                          min_value=0.01, max_value=0.5, 
                                          value=DEFAULT_PARAMS["drift_tolerance_gso"], 
                                          step=0.01, format="%.2f")
    min_maneuvers_per_month = st.number_input("Min Maneuvers/Month", min_value=0, 
                                              max_value=10, value=DEFAULT_PARAMS["min_maneuvers_per_month"], step=1)
    max_maneuvers_per_month = st.number_input("Max Maneuvers/Month", min_value=1, 
                                              max_value=20, value=DEFAULT_PARAMS["max_maneuvers_per_month"], step=1)
    maneuver_uniformity_threshold = st.number_input("Maneuver Uniformity CoV", 
                                                   min_value=0.1, max_value=2.0, 
                                                   value=DEFAULT_PARAMS["maneuver_uniformity_threshold"], step=0.1)

st.sidebar.markdown("---")


# ==================== MAIN ANALYSIS ====================

# Main Analysis Button - Prominent placement
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    run_analysis = st.button("🚀 Fetch Data & Run Analysis", type="primary", use_container_width=True)

if run_analysis:
    if not username or not password:
        st.error("❌ Please enter Space-Track credentials in the sidebar")
    else:
        # Validate date range
        if start_date > end_date:
            st.error("❌ Start date must be before end date")
        elif end_date > date_class.today():
            st.error(f"❌ End date cannot be in the future. Today is {date_class.today().strftime('%Y-%m-%d')}")
        else:
            with st.spinner(f"🔄 Fetching {system_label} satellite data..."):
                all_dfs = []
                errors = {}
                
                total_sats = len(SAT_DICT)
                progress_placeholder = st.empty()
                
                for idx, (sat_name, norad) in enumerate(SAT_DICT.items(), 1):
                    try:
                        progress_placeholder.info(f"📡 Fetching {sat_name} ({idx}/{total_sats})... NORAD ID: {norad}")
                        
                        if norad is None:
                            raise ValueError(f"NORAD ID not set for {sat_name}. Please update configuration.")
                        df = fetch_and_classify_satellite(
                            norad_id=int(norad),
                            start_date=start_date_str,
                            end_date=end_date_str,
                            username=username,
                            password=password,
                            igso_min=10,
                            deviation_tol=0.3
                        )

                        df['EPOCH'] = pd.to_datetime(df['EPOCH'])
                        df = df.sort_values('EPOCH').reset_index(drop=True)

                        if daily_only:
                            df['date'] = df['EPOCH'].dt.date
                            df = df.sort_values('EPOCH').groupby('date', as_index=False).first()
                            df['EPOCH'] = pd.to_datetime(df['EPOCH'])

                        df['satellite'] = sat_name

                        if 'mean_inclination' not in df.columns:
                            df['mean_inclination'] = df['INCLINATION'].mean()

                        all_dfs.append(df)
                        progress_placeholder.success(f"✅ {sat_name} fetched successfully ({len(df)} records)")

                    except Exception as e:
                        error_msg = str(e)
                        if "timeout" in error_msg.lower():
                            error_msg = f"Request timeout - Space-Track API is slow or unresponsive. Try a smaller date range."
                        elif "No GP data found" in error_msg:
                            error_msg = f"No data available for the selected date range ({start_date_str} to {end_date_str})"
                        errors[sat_name] = error_msg
                        progress_placeholder.warning(f"⚠️ {sat_name} failed: {error_msg}")
                
                progress_placeholder.empty()

            if errors:
                st.warning("⚠️ Some satellites failed to fetch:")
                for s, msg in errors.items():
                    st.write(f"- **{s}**: {msg}")

            if not all_dfs:
                st.error("❌ No data fetched for any satellite")
            else:
                df_all = pd.concat(all_dfs, ignore_index=True, sort=False)
                
                # Identify and remove graveyard satellites from analysis
                graveyard_sats = get_graveyard_satellites(df_all)
                if graveyard_sats:
                    st.warning(f"⚠️ Excluding {len(graveyard_sats)} satellite(s) in graveyard orbit: {', '.join(sorted(graveyard_sats))}")
                    df_all = df_all[~df_all['satellite'].isin(graveyard_sats)]
                
                # Store in session state
                st.session_state['df_all'] = df_all
                st.session_state['analysis_complete'] = True
                st.session_state['errors'] = errors
                st.session_state['graveyard_sats'] = graveyard_sats
                st.session_state['system_label'] = system_label
                
                # Check for graveyard orbit satellites (for logging)
                check_graveyard_orbit_satellites(df_all)
                
                st.markdown('<div class="success-card"><strong>✅ Data fetched successfully!</strong> Explore the results below.</div>', unsafe_allow_html=True)


# ==================== RESULTS DISPLAY ====================

# Display results if analysis is complete
if st.session_state.get('analysis_complete', False):
    df_all = st.session_state['df_all']
    system_label = st.session_state.get('system_label', constellation)
    
    st.markdown("---")
    
    # Summary metrics at top
    col1, col2, col3, col4 = st.columns(4)
    
    total_sats = len(df_all['satellite'].unique())
    graveyard_sats = st.session_state.get('graveyard_sats', set())
    active_sats = total_sats - len(graveyard_sats)
    date_range_days = (df_all['EPOCH'].max() - df_all['EPOCH'].min()).days
    
    with col1:
        st.metric("Constellation", system_label, f"{active_sats} active")
    with col2:
        st.metric("Total Satellites", total_sats, f"{len(graveyard_sats)} inactive" if graveyard_sats else "All active")
    with col3:
        st.metric("Analysis Period", f"{date_range_days} days", f"{start_date_str} to {end_date_str}")
    with col4:
        st.metric("Data Points", len(df_all), f"Across {total_sats} satellites")
    
    st.markdown("---")
    
    # Tab-based navigation for main content
    tab1, tab2, tab3, tab4 = st.tabs(["🏥 Health Overview", "📊 Drift & Maneuvers", "📡 DOP Analysis", "📈 Visualizations"])
    
    # ==================== TAB 1: HEALTH OVERVIEW ====================
    with tab1:
        st.markdown(f"## Satellite Health Assessment")
        
        maneuver_summary = []
        all_maneuvers_df = pd.DataFrame()
        health_assessments = []
        
        # Fetch last year's data for pattern analysis
        from datetime import datetime, timezone
        # Determine pattern analysis window: either last 365 days or user-selected range
        if use_historical_pattern:
            pattern_end_date = datetime.now(timezone.utc)
            pattern_start_date = pattern_end_date - timedelta(days=365)
        else:
            # Use selected analysis period for pattern analysis
            pattern_start_date = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            pattern_end_date = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

        pattern_start_str = pattern_start_date.strftime("%Y-%m-%d")
        pattern_end_str = pattern_end_date.strftime("%Y-%m-%d")
        
        with st.spinner("Analyzing satellite health and maneuver patterns..."):
            # Fetch pattern data for all satellites
            pattern_data = {}
            for sat_name, norad in SAT_DICT.items():
                try:
                    if norad is None:
                        continue
                    pattern_df = fetch_and_classify_satellite(
                        norad_id=int(norad),
                        start_date=pattern_start_str,
                        end_date=pattern_end_str,
                        username=username,
                        password=password,
                        igso_min=10,
                        deviation_tol=0.3
                    )
                    pattern_df['EPOCH'] = pd.to_datetime(pattern_df['EPOCH'])
                    pattern_df = pattern_df.sort_values('EPOCH').reset_index(drop=True)
                    
                    # Detect maneuvers in pattern data
                    pattern_detected = detect_navik_maneuvers(
                        pattern_df,
                        sma_col='SEMIMAJOR_AXIS',
                        inc_col='INCLINATION',
                        z_thresh=z_threshold,
                        sma_abs_thresh_km=sma_threshold,
                        inc_abs_thresh_deg=inc_threshold,
                        persist_window=int(persist_window)
                    )
                    pattern_maneuvers = pattern_detected[pattern_detected['MANEUVER']].copy()
                    pattern_data[sat_name] = {
                        'df': pattern_df,
                        'maneuvers': pattern_maneuvers
                    }
                except Exception as e:
                    pattern_data[sat_name] = None
            # Determine days where the constellation appears fully deployed
            # Count how many satellites have observations on each UTC date
            from collections import Counter
            date_counter = Counter()
            for sat_name, pdata in pattern_data.items():
                if pdata is None:
                    continue
                try:
                    dates = pd.to_datetime(pdata['df']['EPOCH']).dt.date.unique().tolist()
                    for d in dates:
                        date_counter[d] += 1
                except Exception:
                    continue

            expected_constellation_size = len(SAT_DICT)
            # require at least 75% of expected satellites present to consider the day 'deployed'
            min_required = max(1, int(0.75 * expected_constellation_size))
            deployed_dates = {d for d, cnt in date_counter.items() if cnt >= min_required}
            # If we found no deployed dates (small sample), fall back to allowing all dates
            if not deployed_dates:
                deployed_dates = None

            for sat_name in sorted(df_all['satellite'].unique()):
                sat_df = df_all[df_all['satellite'] == sat_name].copy()
                
                sat_detected = detect_navik_maneuvers(
                    sat_df,
                    sma_col='SEMIMAJOR_AXIS',
                    inc_col='INCLINATION',
                    z_thresh=z_threshold,
                    sma_abs_thresh_km=sma_threshold,
                    inc_abs_thresh_deg=inc_threshold,
                    persist_window=int(persist_window)
                )
                
                ew_maneuvers = int(sat_detected['EW_MANEUVER'].sum()) if 'EW_MANEUVER' in sat_detected.columns else 0
                ns_maneuvers = int(sat_detected['NS_MANEUVER'].sum()) if 'NS_MANEUVER' in sat_detected.columns else 0
                
                maneuver_events = sat_detected[sat_detected['MANEUVER']].copy()
                maneuver_events['satellite'] = sat_name
                all_maneuvers_df = pd.concat([all_maneuvers_df, maneuver_events], ignore_index=True)
                
                maneuver_summary.append({
                    'Satellite': sat_name,
                    'E-W Maneuvers': ew_maneuvers,
                    'N-S Maneuvers': ns_maneuvers,
                    'Total Maneuvers': ew_maneuvers + ns_maneuvers,
                    'Observation Period (days)': (sat_df['EPOCH'].max() - sat_df['EPOCH'].min()).days
                })
                
                # Use last year's data for health assessment if available
                if pattern_data.get(sat_name) is not None:
                    health_sat_df = pattern_data[sat_name]['df'].copy()
                    health_maneuvers = pattern_data[sat_name]['maneuvers'].copy()
                else:
                    health_sat_df = sat_df.copy()
                    health_maneuvers = maneuver_events.copy()

                # If we computed deployed_dates, filter out days where constellation
                # wasn't fully deployed (helps QZSS during ramp-up periods)
                if deployed_dates is not None and not health_sat_df.empty:
                    try:
                        health_sat_df['EPOCH_date'] = pd.to_datetime(health_sat_df['EPOCH']).dt.date
                        filtered_df = health_sat_df[health_sat_df['EPOCH_date'].isin(deployed_dates)].drop(columns=['EPOCH_date'])
                        if not filtered_df.empty:
                            health_sat_df = filtered_df.reset_index(drop=True)
                        # Filter maneuvers by deployed dates as well
                        if not health_maneuvers.empty:
                            health_maneuvers['EPOCH_date'] = pd.to_datetime(health_maneuvers['EPOCH']).dt.date
                            fm = health_maneuvers[health_maneuvers['EPOCH_date'].isin(deployed_dates)].drop(columns=['EPOCH_date'])
                            if not fm.empty:
                                health_maneuvers = fm.reset_index(drop=True)
                    except Exception:
                        # If anything goes wrong during filtering, fall back to unfiltered data
                        pass
                
                health_data = assess_satellite_health_with_drift(
                    sat_name, health_sat_df, health_maneuvers,
                    inclination_tolerance, min_maneuvers_per_month,
                    max_maneuvers_per_month, maneuver_uniformity_threshold,
                    drift_tolerance_gso, service_requirements=SERVICE_REQS,
                    pattern_maneuvers=health_maneuvers,
                    pattern_df=health_sat_df
                )
                health_assessments.append(health_data)
        
        health_df = pd.DataFrame(health_assessments)
        
        # Calculate longitude deviations using satellite objects if available
        if 'satellites_dop' in st.session_state and 'current_time' in st.session_state:
            try:
                from skyfield.api import load, wgs84
                import numpy as np
                from datetime import timedelta
                
                satellites_dop = st.session_state['satellites_dop']
                current_time = st.session_state['current_time']
                ts = load.timescale()
                
                # Calculate mean longitude for each satellite over last 24 hours
                for idx, row in health_df.iterrows():
                    sat_name = row['Satellite']
                    designated_lon = row['Designated Lon (°)']
                    
                    if sat_name in satellites_dop and designated_lon != "N/A":
                        try:
                            sat_obj = satellites_dop[sat_name]
                            
                            # Generate time steps over 24 hours
                            num_steps = 96  # 15-minute intervals
                            longitudes = []
                            
                            for i in range(num_steps):
                                dt = current_time - timedelta(hours=24) + timedelta(minutes=i * 15)
                                t = ts.from_datetime(dt)
                                geocentric = sat_obj.at(t)
                                subpoint = wgs84.subpoint(geocentric)
                                longitudes.append(subpoint.longitude.degrees)
                            
                            # Compute circular mean longitude
                            lons_rad = np.deg2rad(longitudes)
                            x = np.cos(lons_rad)
                            y = np.sin(lons_rad)
                            mean_x = np.mean(x)
                            mean_y = np.mean(y)
                            mean_lon_rad = np.arctan2(mean_y, mean_x)
                            current_mean_lon = np.rad2deg(mean_lon_rad)
                            
                            # Calculate deviation from designated longitude
                            diff = current_mean_lon - float(designated_lon)
                            while diff > 180:
                                diff -= 360
                            while diff < -180:
                                diff += 360
                            longitude_deviation = diff
                            
                            # Update health_df with calculated values
                            health_df.at[idx, 'Current Mean Lon (°)'] = round(current_mean_lon, 2)
                            health_df.at[idx, 'Lon Slot Deviation (°)'] = round(longitude_deviation, 2)
                            
                            # Calculate longitude score
                            abs_dev = abs(longitude_deviation)
                            sat_type = row['Type']
                            
                            if sat_type == 'GSO':
                                if abs_dev <= 0.5:
                                    lon_score = 100
                                elif abs_dev <= 1.0:
                                    lon_score = 90 - ((abs_dev - 0.5) / 0.5) * 20
                                elif abs_dev <= 2.0:
                                    lon_score = 70 - ((abs_dev - 1.0) / 1.0) * 30
                                else:
                                    lon_score = max(0, 40 - ((abs_dev - 2.0) / 2.0) * 40)
                            else:  # IGSO
                                if abs_dev <= 5.0:
                                    lon_score = 100
                                elif abs_dev <= 10.0:
                                    lon_score = 90 - ((abs_dev - 5.0) / 5.0) * 30
                                else:
                                    lon_score = max(0, 60 - ((abs_dev - 10.0) / 10.0) * 60)
                            
                            health_df.at[idx, 'Lon Deviation Score'] = round(lon_score, 1)
                            
                            # Recalculate overall score with longitude component
                            weights = {
                                'inc': 0.30,
                                'maintenance': 0.25,
                                'drift': 0.20,
                                'longitude': 0.15,
                                'uniformity': 0.10
                            }
                            
                            # Get existing component scores (normalized to handle "N/A")
                            components = {}
                            # Note: We'd need to extract individual component scores from the health assessment
                            # For now, just update the longitude-related fields
                            
                        except Exception as e:
                            # If calculation fails for this satellite, leave as N/A
                            pass
            except Exception as e:
                # If overall calculation fails, proceed without longitude data
                pass
        
        # Health summary metrics
        st.markdown("### 📊 Overall Health Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        healthy_count = len(health_df[health_df['Overall Score'] >= 80])
        fair_count = len(health_df[(health_df['Overall Score'] >= 60) & (health_df['Overall Score'] < 80)])
        degraded_count = len(health_df[(health_df['Overall Score'] >= 40) & (health_df['Overall Score'] < 60)])
        critical_count = len(health_df[health_df['Overall Score'] < 40])
        
        with col1:
            st.metric("🟢 Healthy", healthy_count, help="Score ≥ 80")
        with col2:
            st.metric("🟡 Fair", fair_count, help="Score 60-79")
        with col3:
            st.metric("🟠 Degraded", degraded_count, help="Score 40-59")
        with col4:
            st.metric("🔴 Critical", critical_count, help="Score < 40")
        
        st.markdown("---")
        
        # Main health table
        st.markdown("### 📋 Detailed Health Assessment")
        st.dataframe(
            health_df[[
                'Satellite', 'Type', 'Health Status', 'Overall Score', 
                'Target Incl. (°)', 'Mean Incl. (°)', 'Incl. Dev. (°)',
                'Altitude (km)', 'Current Drift (°/day)', 
                'Designated Lon (°)', 'Lon Slot Deviation (°)'
            ]],
            hide_index=True,
            use_container_width=True,
            column_config={
                "Health Status": st.column_config.TextColumn(
                    "Health Status",
                    help="🟢 Healthy (≥80) | 🟡 Fair (60-79) | 🟠 Degraded (40-59) | 🔴 Critical (<40)",
                    width="medium"
                ),
                "Overall Score": st.column_config.NumberColumn(
                    "Overall Score",
                    help="Weighted score: Inclination (30%) + Maintenance (25%) + Drift (20%) + Longitude (15%) + Uniformity (10%)",
                    format="%.1f"
                ),
                "Altitude (km)": st.column_config.NumberColumn(
                    "Altitude (km)",
                    help="Current orbital altitude. GEO nominal: 35,786 km. Graveyard: >35,986 km",
                    format="%.1f"
                ),
                "Designated Lon (°)": st.column_config.NumberColumn(
                    "Designated Lon (°)",
                    help="Designated longitude slot from constellation requirements",
                    format="%.2f"
                ),
                "Lon Slot Deviation (°)": st.column_config.NumberColumn(
                    "Lon Slot Deviation (°)",
                    help="Deviation from designated slot. GSO: <0.5° ideal | IGSO: <5° ideal",
                    format="%.2f"
                )
            }
        )
        
        # Health scoring explanation
        with st.expander("ℹ️ Health Scoring Methodology", expanded=False):
            st.markdown("""
            ### 🏥 Health Status Determination
            
            The **Overall Score** (0-100) uses weighted components:
            
            #### 📊 Score Components:
            - **Inclination Score (30%)**: Deviation from target inclination with stability assessment
            - **Maintenance Score (25%)**: Dynamic pattern-based maneuver schedule analysis
            - **Drift Score (20%)**: Longitudinal drift analysis (GSO: <0.05°/day, IGSO: <2°/day)
            - **Longitude Deviation Score (15%)**: Slot position accuracy (GSO: <0.5° ideal, IGSO: <5° ideal)
            - **Uniformity Score (10%)**: Maneuver spacing regularity
            
            #### 🎯 Status Thresholds:
            - **🟢 Healthy**: Score ≥ 80
            - **🟡 Fair**: Score 60-79
            - **🟠 Degraded**: Score 40-59
            - **🔴 Critical**: Score < 40
            
            #### 🔍 Pattern Analysis:
            Each satellite's maneuver pattern is learned from historical data (last 365 days).
            The system detects expected intervals and flags overdue corrections automatically.
            """)
        
        # Detailed remarks
        with st.expander("📋 Detailed Health Remarks & Pattern Analysis", expanded=False):
            for idx, row in health_df.iterrows():
                # Create a visually distinct container for each satellite
                with st.container():
                    # Satellite header with status color coding
                    status = row['Health Status']
                    if '🟢' in status:
                        status_color = '#10b981'
                        status_emoji = '🟢'
                    elif '🟡' in status:
                        status_color = '#f59e0b'
                        status_emoji = '🟡'
                    elif '🟠' in status:
                        status_color = '#fb923c'
                        status_emoji = '🟠'
                    else:
                        status_color = '#ef4444'
                        status_emoji = '🔴'
                    
                    st.markdown(f"""
                    <div style="background: linear-gradient(90deg, {status_color}15 0%, transparent 100%); 
                                border-left: 4px solid {status_color}; 
                                padding: 1.5rem; 
                                border-radius: 8px; 
                                margin-bottom: 1.5rem;">
                        <h3 style="margin: 0 0 0.5rem 0; color: {status_color};">
                            {status_emoji} {row['Satellite']} ({row['Type']})
                        </h3>
                        <p style="margin: 0; opacity: 0.8;">Status: {status}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Overall Score with visual indicator
                    score = row['Overall Score']
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col2:
                        st.metric(
                            "Overall Health Score", 
                            f"{score:.1f}/100",
                            delta=None,
                            help="Composite score based on inclination, maintenance, drift, and uniformity"
                        )
                        # Progress bar
                        st.progress(score / 100)
                    
                    st.markdown("---")
                    
                    # Maneuver Pattern Analysis in organized cards
                    st.markdown("#### 📊 Maneuver Pattern Analysis")
                    st.caption(f"**Analysis Period:** {row.get('Pattern Analysis Period', 'N/A')}")
                    
                    st.markdown("")  # Spacing
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("""
                        <div style="background: rgba(59, 130, 246, 0.1); 
                                    border-left: 3px solid #3b82f6; 
                                    padding: 1rem; 
                                    border-radius: 6px;">
                            <h5 style="margin: 0 0 0.5rem 0; color: #3b82f6;">⬅️➡️ E-W Maneuvers (Drift Correction)</h5>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        ew_total = row['EW Maneuvers']
                        ew_interval = row.get('EW Expected Interval (days)', 'N/A')
                        ew_since_last = row.get('EW Days Since Last', 'N/A')
                        ew_confidence = row.get('EW Pattern Confidence', 'N/A')
                        
                        st.markdown(f"""
                        - **Total Maneuvers:** `{ew_total}`
                        - **Expected Interval:** `{ew_interval}` days
                        - **Days Since Last:** `{ew_since_last}`
                        - **Pattern Confidence:** `{ew_confidence}`
                        """)
                    
                    with col2:
                        st.markdown("""
                        <div style="background: rgba(16, 185, 129, 0.1); 
                                    border-left: 3px solid #10b981; 
                                    padding: 1rem; 
                                    border-radius: 6px;">
                            <h5 style="margin: 0 0 0.5rem 0; color: #10b981;">⬆️⬇️ N-S Maneuvers (Inclination Correction)</h5>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        ns_total = row['NS Maneuvers']
                        ns_interval = row.get('NS Expected Interval (days)', 'N/A')
                        ns_since_last = row.get('NS Days Since Last', 'N/A')
                        ns_confidence = row.get('NS Pattern Confidence', 'N/A')
                        
                        st.markdown(f"""
                        - **Total Maneuvers:** `{ns_total}`
                        - **Expected Interval:** `{ns_interval}` days
                        - **Days Since Last:** `{ns_since_last}`
                        - **Pattern Confidence:** `{ns_confidence}`
                        """)
                    
                    st.markdown("")  # Spacing
                    st.markdown("---")
                    
                    # Health Remarks in a styled box
                    st.markdown("#### 💬 Health Assessment Details")
                    remarks_list = row['Remarks'].split(' | ')
                    
                    for remark in remarks_list:
                        # Color code remarks based on keywords
                        if any(word in remark.lower() for word in ['healthy', 'good', 'normal', 'on schedule']):
                            icon = '✅'
                            color = '#10b981'
                        elif any(word in remark.lower() for word in ['warning', 'caution', 'due soon', 'approaching']):
                            icon = '⚠️'
                            color = '#f59e0b'
                        elif any(word in remark.lower() for word in ['critical', 'overdue', 'high', 'severe']):
                            icon = '🔴'
                            color = '#ef4444'
                        else:
                            icon = 'ℹ️'
                            color = '#3b82f6'
                        
                        st.markdown(f"""
                        <div style="background: {color}10; 
                                    border-left: 3px solid {color}; 
                                    padding: 0.75rem 1rem; 
                                    border-radius: 6px; 
                                    margin-bottom: 0.5rem;">
                            <span style="color: {color}; font-weight: 600;">{icon}</span> {remark}
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.markdown("<br>", unsafe_allow_html=True)  # Extra spacing between satellites

        
        # Store for other tabs
        st.session_state['health_df'] = health_df
        st.session_state['maneuver_summary'] = maneuver_summary
    
    # ==================== TAB 2: DRIFT & MANEUVERS ====================
    with tab2:
        st.markdown("## Drift & Maneuver Analysis")
        
        # Get data from session
        health_df = st.session_state.get('health_df', pd.DataFrame())
        maneuver_summary = st.session_state.get('maneuver_summary', [])
        
        # Create sub-tabs for better organization
        subtab1, subtab2, subtab3 = st.tabs(["🌍 Drift Analysis", "🛠️ Maneuver Detection", "🔍 Satellite Classification"])
        
        with subtab1:
            st.markdown("### Longitudinal Drift Analysis")
            drift_summary = []
            for sat_name in sorted(df_all['satellite'].unique()):
                sat_df = df_all[df_all['satellite'] == sat_name].copy()
                
                if 'LonDrift_deg_per_day' in sat_df.columns:
                    current_drift = sat_df['LonDrift_deg_per_day'].iloc[-1]  # Use instantaneous drift
                    std_drift = sat_df['LonDrift_deg_per_day'].std()
                    
                    # Determine satellite type
                    mean_incl = sat_df['INCLINATION'].mean()
                    if 0.0 < mean_incl < 10.0:
                        sat_type = 'GSO'
                    else:
                        sat_type = 'IGSO'
                    
                    drift_assessment = assess_drift_health(current_drift, sat_type, drift_tolerance_gso)  # Use current_drift
                    drift_direction = get_drift_direction(current_drift)
                    
                    drift_summary.append({
                        'Satellite': sat_name,
                        'Type': sat_type,
                        'Current Drift (°/day)': round(current_drift, 4),
                        'Std Dev (°/day)': round(std_drift, 4),
                        'Direction': drift_direction,
                        'Drift Status': f"{drift_assessment['drift_color']} {drift_assessment['drift_status']}",
                        'Drift Score': round(drift_assessment['drift_score'], 1)
                    })
            
            drift_summary_df = pd.DataFrame(drift_summary)
            st.dataframe(drift_summary_df, hide_index=True, use_container_width=True)
            st.caption(f"**GSO Drift Tolerance:** ±{drift_tolerance_gso}°/day | Positive = Eastward, Negative = Westward")
        
        with subtab2:
            st.markdown("### Maneuver Detection Summary")
            if maneuver_summary:
                maneuver_summary_df = pd.DataFrame(maneuver_summary)
                st.caption(f"**Detection Parameters:** Z-score ≥ {z_threshold}, SMA ≥ {sma_threshold} km, Inclination ≥ {inc_threshold}°, Window = {int(persist_window)}")
                st.dataframe(maneuver_summary_df, hide_index=True, use_container_width=True)
                
                if not health_df.empty:
                    st.markdown("---")
                    st.markdown("#### 📊 Maneuver Pattern Analysis (Last 365 Days)")
                    pattern_summary = []
                    for _, row in health_df.iterrows():
                        pattern_summary.append({
                            'Satellite': row['Satellite'],
                            'E-W Expected Interval (days)': str(row.get('EW Expected Interval (days)', 'N/A')),
                            'E-W Days Since Last': str(row.get('EW Days Since Last', 'N/A')),
                            'E-W Confidence': str(row.get('EW Pattern Confidence', 'N/A')),
                            'N-S Expected Interval (days)': str(row.get('NS Expected Interval (days)', 'N/A')),
                            'N-S Days Since Last': str(row.get('NS Days Since Last', 'N/A')),
                            'N-S Confidence': str(row.get('NS Pattern Confidence', 'N/A')),
                            'Analysis Period': str(row.get('Pattern Analysis Period', 'N/A'))
                        })
                    
                    pattern_summary_df = pd.DataFrame(pattern_summary)
                    st.dataframe(pattern_summary_df, hide_index=True, use_container_width=True)
                    st.caption("💡 **Pattern Analysis**: E-W maneuvers correct longitudinal drift, N-S maneuvers correct inclination.")
            else:
                st.info("No maneuver data available")
        
        with subtab3:
            st.markdown("### Satellite Classification Summary")
            sat_summary = []
            for sat_name in sorted(df_all['satellite'].unique()):
                sub = df_all[df_all['satellite'] == sat_name]
                mean_incl = sub['INCLINATION'].mean() if not sub.empty else float('nan')
                mean_alt = sub['altitude_km'].mean() if not sub.empty and 'altitude_km' in sub.columns else float('nan')
                current_drift = sub['LonDrift_deg_per_day'].iloc[-1] if 'LonDrift_deg_per_day' in sub.columns and len(sub) > 0 else float('nan')  # Use instantaneous drift
                
                if 0.0 < mean_incl < 10.0:
                    sat_type = 'GSO'
                elif mean_incl >= 10.0:
                    sat_type = 'IGSO'
                else:
                    sat_type = 'Unclassified'
                
                sat_summary.append({
                    'Satellite': sat_name,
                    'Mean Inclination (°)': round(mean_incl, 3) if not sub.empty else None,
                    'Mean Altitude (km)': round(mean_alt, 2) if not pd.isna(mean_alt) else None,
                    'Current Drift (°/day)': round(current_drift, 4) if not pd.isna(current_drift) else None,
                    'Classified Type': sat_type
                })
            sat_summary_df = pd.DataFrame(sat_summary)
            st.dataframe(sat_summary_df, hide_index=True, use_container_width=True)
    
    
    # ==================== TAB 3: DOP ANALYSIS ====================
    with tab3:
        st.markdown("## Dilution of Precision (DOP) Analysis")
        try:
            norad_ids = [nid for nid in SAT_DICT.values() if nid is not None]
            # Use CelesTrak API for DOP TLE data (no authentication required)
            tle_data = fetch_tles_from_celestrak(norad_ids)
            
            if not tle_data:
                st.error("❌ Failed to fetch TLE data for DOP calculations")
            else:
                satellites = parse_tle_data(tle_data, SAT_DICT)
                
                if len(satellites) == 0:
                    st.error("❌ No satellites parsed from TLE data")
                else:
                    # Filter out inactive satellites if toggle is off
                    original_count = len(satellites)
                    if system_label == "NavIC" and not include_inactive_sats:
                        satellites = {name: sat for name, sat in satellites.items() if name not in INACTIVE_SATELLITES}
                        inactive_count = original_count - len(satellites)
                        if inactive_count > 0:
                            st.info(f"📋 Excluding {inactive_count} inactive satellites (IRNSS-1C, 1D, 1E) from DOP calculations")
                    
                    st.success(f"✅ Successfully loaded {len(satellites)} satellites for DOP calculations")
                    
                    current_time = datetime.now(timezone.utc)
                    st.caption(f"Calculation Time (UTC): {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    dop_results = []
                    last_sat_positions = None
                    last_location_meta = None
                    
                    if use_custom_location:
                        lat, lon = float(custom_lat), float(custom_lon)
                        location_name = f"Custom ({lat:.3f}, {lon:.3f})"
                        dop, visible_sats, sat_positions = calculate_dop_for_location(
                            satellites, lat, lon, current_time, elevation_mask_deg=elevation_mask_deg
                        )
                        last_sat_positions = sat_positions
                        last_location_meta = {'name': location_name, 'lat': lat, 'lon': lon}
                        
                        if dop:
                            quality = get_dop_quality(dop['GDOP'])
                            
                            dop_results.append({
                                'Location': location_name,
                                'Latitude': lat,
                                'Longitude': lon,
                                'Visible Sats': len(visible_sats),
                                'GDOP': round(dop['GDOP'], 2),
                                'PDOP': round(dop['PDOP'], 2),
                                'HDOP': round(dop['HDOP'], 2),
                                'VDOP': round(dop['VDOP'], 2),
                                'TDOP': round(dop['TDOP'], 2),
                                'Quality': quality
                            })
                        else:
                            dop_results.append({
                                'Location': location_name,
                                'Latitude': lat,
                                'Longitude': lon,
                                'Visible Sats': len(visible_sats),
                                'GDOP': None,
                                'PDOP': None,
                                'HDOP': None,
                                'VDOP': None,
                                'TDOP': None,
                                'Quality': 'N/A'
                            })
                    else:
                        for location_name, (lat, lon) in LOCATION_POINTS.items():
                            dop, visible_sats, sat_positions = calculate_dop_for_location(
                                satellites, lat, lon, current_time, elevation_mask_deg=elevation_mask_deg
                            )
                            
                            if dop:
                                quality = get_dop_quality(dop['GDOP'])
                                
                                dop_results.append({
                                    'Location': location_name,
                                    'Latitude': lat,
                                    'Longitude': lon,
                                    'Visible Sats': len(visible_sats),
                                    'GDOP': round(dop['GDOP'], 2),
                                    'PDOP': round(dop['PDOP'], 2),
                                    'HDOP': round(dop['HDOP'], 2),
                                    'VDOP': round(dop['VDOP'], 2),
                                    'TDOP': round(dop['TDOP'], 2),
                                    'Quality': quality
                                })
                            else:
                                dop_results.append({
                                    'Location': location_name,
                                    'Latitude': lat,
                                    'Longitude': lon,
                                    'Visible Sats': len(visible_sats),
                                    'GDOP': None,
                                    'PDOP': None,
                                    'HDOP': None,
                                    'VDOP': None,
                                    'TDOP': None,
                                    'Quality': 'N/A'
                                })
                    
                    dop_df = pd.DataFrame(dop_results)
                    st.dataframe(dop_df, hide_index=True, width='stretch')
                    
                    # DOP Quality Guide with reference
                    with st.expander("ℹ️ DOP Quality Reference", expanded=False):
                        st.markdown("""
                        ### DOP Quality Assessment
                        
                        | DOP Type | Ideal | Excellent | Good | Moderate | Fair | Poor |
                        |----------|-------|-----------|------|----------|------|------|
                        | **GDOP** | <1 | 1-2 | 2-5 | 5-10 | 10-20 | >20 |
                        | **PDOP** | <1 | 1-2 | 2-5 | 5-10 | 10-20 | >20 |
                        | **HDOP** | <1 | 1-2 | 2-5 | 5-10 | 10-20 | >20 |
                        | **VDOP** | <2 | 2-3 | 3-5 | 5-10 | 10-15 | >15 |
                        
                        **Source:** 
                        Isik, O. K., Hong, J., Petrunin, I., & Tsourdos, A. (2020). 
                        "Integrity Analysis for GPS-Based Navigation of UAVs in Urban Environment". 
                        *Robotics*, 9(3), 66. https://doi.org/10.3390/robotics9030066
                        """)
                    
                    st.caption(f"*Elevation mask: {elevation_mask_deg}°")
                    
                    # Store for plotting
                    st.session_state['satellites_dop'] = satellites
                    st.session_state['dop_results'] = dop_results
                    st.session_state['current_time'] = current_time
                    st.session_state['elevation_mask_deg'] = elevation_mask_deg
                    if last_sat_positions is not None and last_location_meta is not None:
                        st.session_state['last_sat_positions'] = last_sat_positions
                        st.session_state['last_location_meta'] = last_location_meta
                    
                    
        except Exception as e:
            st.error(f"❌ Error during DOP analysis: {str(e)}")
    
    # ==================== TAB 4: VISUALIZATIONS ====================
    with tab4:
        st.markdown("## Visualizations & Plots")
        
        show_plots = st.button("🎨 Generate All Visualizations", type="primary", use_container_width=True)
        
        if show_plots or st.session_state.get('show_plots', False):
            st.session_state['show_plots'] = True
            
            # Create visualization sub-tabs
            viz_tab1, viz_tab2, viz_tab3, viz_tab4 = st.tabs(["📈 Orbital Trends", "🌌 Sky Plots", "📡 DOP Trends", "🗺️ Ground Trace"])
            
            with viz_tab1:
                st.markdown("### Orbital Parameter Trends")
                
                # Individual satellite plots
                plot_individual_satellites(df_all)
                
                # Combined plots
                plot_combined_drift(df_all, system_label=system_label)
                plot_combined_inclination(df_all, system_label=system_label)
                plot_combined_altitude(df_all, system_label=system_label)
                plot_drift_distribution(df_all)
                plot_drift_vs_altitude(df_all)
                
                # Mean longitude map view with deviation analysis
                if st.session_state.get('satellites_dop') and st.session_state.get('current_time'):
                    satellites = st.session_state['satellites_dop']
                    current_time = st.session_state['current_time']
                    plot_mean_longitude_map(satellites, current_time, system_label=system_label)
                else:
                    st.info("💡 Run DOP analysis to view mean longitude map")
                
                # Historical central longitude tracking
                st.markdown("---")
                plot_historical_central_longitude(df_all, system_label=system_label)
            
            with viz_tab2:
                st.markdown("### Sky Plots & Satellite Visibility")
                
                # Azimuth-Elevation Sky Plot
                if st.session_state.get('satellites_dop') and st.session_state.get('current_time'):
                    satellites = st.session_state['satellites_dop']
                    current_time = st.session_state['current_time']
                    elevation_mask = st.session_state.get('elevation_mask_deg', elevation_mask_deg)
                    
                    # Let user select location for sky plot
                    if use_custom_location:
                        sky_plot_lat = custom_lat
                        sky_plot_lon = custom_lon
                        sky_plot_name = f"Custom ({sky_plot_lat:.3f}, {sky_plot_lon:.3f})"
                    else:
                        sky_plot_location = st.selectbox("Select Location for Sky Plot", list(LOCATION_POINTS.keys()))
                        sky_plot_lat, sky_plot_lon = LOCATION_POINTS[sky_plot_location]
                        sky_plot_name = sky_plot_location
                    
                    # Calculate satellite positions for selected location
                    with st.spinner(f"Calculating satellite positions for {sky_plot_name}..."):
                        dop, visible_sats, sat_positions = calculate_dop_for_location(
                            satellites, sky_plot_lat, sky_plot_lon, current_time, 
                            elevation_mask_deg=elevation_mask
                        )
                        loc_meta = {'name': sky_plot_name, 'lat': sky_plot_lat, 'lon': sky_plot_lon}
                        
                        # Add toggle for animated vs static sky plot
                        plot_type = st.radio(
                            "Sky Plot Type",
                            ["Static (Current Time)", "Animated (24 Hours)"],
                            horizontal=True,
                            help="Choose between a static snapshot or an animated view showing satellite movement over 24 hours"
                        )
                        
                        if plot_type == "Static (Current Time)":
                            plot_sky_plot(satellites, sat_positions, loc_meta, elevation_mask)
                        else:
                            # Animated sky plot
                            plot_animated_sky_plot(
                                satellites, 
                                loc_meta, 
                                current_time, 
                                elevation_mask_deg=elevation_mask,
                                duration_hours=24,
                                time_step_minutes=15
                            )
                else:
                    st.info("💡 Run DOP analysis to generate sky plots")
            
            with viz_tab3:
                st.markdown("### DOP Time Series")
                
                # DOP Over Last 30 Days Plot
                if st.session_state.get('satellites_dop') and st.session_state.get('dop_results'):
                    satellites = st.session_state['satellites_dop']
                    
                    if use_custom_location:
                        selected_location = None
                    else:
                        location_options = list(LOCATION_POINTS.keys())
                        selected_location = st.selectbox("Select Location for DOP Time Series", location_options)
                    
                    if use_custom_location or selected_location:
                        plot_dop_over_time(satellites, use_custom_location, custom_lat, custom_lon, 
                                          elevation_mask_deg, selected_location, LOCATION_POINTS)
                else:
                    st.info("💡 Run DOP analysis to generate DOP time series")
            
            with viz_tab4:
                st.markdown("### 🗺️ Ground Traces")
                
                # Satellite bounding box plots
                if st.session_state.get('satellites_dop') and st.session_state.get('current_time'):
                    satellites = st.session_state['satellites_dop']
                    reference_time = st.session_state['current_time']
                    
                    plot_bounding_boxes(satellites, reference_time, location_points=LOCATION_POINTS)
                else:
                    st.info("💡 Run DOP analysis to generate 3D coverage plots")
        else:
            st.info("👆 Click the button above to generate visualizations")


else:
    # Welcome message when no analysis has been run
    st.markdown("""
    <div class="info-card">
        <h3>👋 Welcome to GNSS Constellation Monitoring</h3>
        <p>Select a constellation and configure your analysis parameters in the sidebar, then click the button above to begin.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 🛰️ Supported Systems")
        st.markdown("""
        - **NavIC (IRNSS)**: 7 satellites, India coverage
        - **QZSS (Michibiki)**: 5 satellites, Japan coverage  
        - **BeiDou-3**: IGSO & GEO, Asia-Pacific coverage
        """)
    
    with col2:
        st.markdown("### 📊 Key Features")
        st.markdown("""
        - **Health Assessment**: Dynamic pattern-based scoring
        - **Drift Analysis**: Longitudinal drift tracking
        - **Maneuver Detection**: E-W & N-S corrections
        """)
    
    with col3:
        st.markdown("### 🎯 Analysis Tools")
        st.markdown("""
        - **DOP Calculations**: Precision metrics
        - **Visualizations**: Interactive plots & charts
        - **Classification**: GSO/IGSO identification
        """)
    
    st.markdown("---")
    
    st.markdown("""
    <div class="info-card">
        <h4>🚀 Getting Started</h4>
        <ol>
            <li>Enter your <strong>Space-Track credentials</strong> in the sidebar</li>
            <li>Select a <strong>constellation</strong> (NavIC, QZSS, or BeiDou-3)</li>
            <li>Choose your <strong>analysis period</strong></li>
            <li>Optionally adjust advanced settings</li>
            <li>Click <strong>"Fetch Data & Run Analysis"</strong></li>
        </ol>
    </div>
    """, unsafe_allow_html=True)

