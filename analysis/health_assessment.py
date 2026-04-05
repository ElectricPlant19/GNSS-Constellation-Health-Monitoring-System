"""
Health Assessment Module
Comprehensive health assessment for NavIC satellites including drift analysis
"""

import numpy as np
import pandas as pd
from datetime import timedelta
from config.config import NAVIK_SERVICE_REQUIREMENTS, COMMISSION_DATES
from analysis.drift_analysis import assess_drift_health, calculate_drift_trend
from analysis.maneuver_detection import calculate_maneuver_uniformity


def analyze_maneuver_pattern(maneuver_events, observation_start, observation_end):
    """
    Dynamically analyze the maneuver pattern for a satellite.
    Analyzes E-W and N-S maneuvers separately as they serve different purposes.
    
    Args:
        maneuver_events: DataFrame of detected maneuvers with 'EPOCH', 'EW_MANEUVER', 'NS_MANEUVER' columns
        observation_start: Start date of observation period
        observation_end: End date of observation period
    
    Returns:
        dict: Pattern analysis including expected interval, last maneuver, and health metrics
    """
    if len(maneuver_events) == 0:
        return {
            'num_maneuvers': 0,
            'num_ew_maneuvers': 0,
            'num_ns_maneuvers': 0,
            'expected_interval_days': None,
            'ew_expected_interval_days': None,
            'ns_expected_interval_days': None,
            'median_interval_days': None,
            'last_maneuver_date': None,
            'last_ew_maneuver_date': None,
            'last_ns_maneuver_date': None,
            'days_since_last_maneuver': None,
            'days_since_last_ew': None,
            'days_since_last_ns': None,
            'is_overdue': False,
            'ew_is_overdue': False,
            'ns_is_overdue': False,
            'pattern_confidence': 'none',
            'maintenance_score': 0,
            'maintenance_status': 'No maneuvers detected'
        }
    
    # Separate E-W and N-S maneuvers
    ew_maneuvers = maneuver_events[maneuver_events.get('EW_MANEUVER', False) == True].copy() if 'EW_MANEUVER' in maneuver_events.columns else pd.DataFrame()
    ns_maneuvers = maneuver_events[maneuver_events.get('NS_MANEUVER', False) == True].copy() if 'NS_MANEUVER' in maneuver_events.columns else pd.DataFrame()
    
    num_ew = len(ew_maneuvers)
    num_ns = len(ns_maneuvers)
    
    # Helper function to analyze pattern for a specific maneuver type
    def analyze_type_pattern(maneuvers_df, maneuver_type_name):
        if len(maneuvers_df) == 0:
            return None, None, None, None, 'none'

        # Coerce epoch values to pandas datetime (ensure consistent types)
        dates_ts = pd.to_datetime(maneuvers_df['EPOCH']).sort_values()
        dates = list(dates_ts)
        intervals = []
        if len(dates) >= 2:
            for i in range(1, len(dates)):
                # Use pandas Timedelta `.days` safely by ensuring operands are Timestamps
                delta = pd.to_datetime(dates[i]) - pd.to_datetime(dates[i - 1])
                intervals.append(int(delta.days))

        if len(intervals) >= 2:
            median_int = float(np.median(intervals))
            mean_int = float(np.mean(intervals))
            std_int = float(np.std(intervals))
            expected_int = float(median_int)
            # Guard against divide-by-zero by checking mean_int
            if mean_int == 0:
                confidence = 'low'
            elif (std_int / mean_int) < 0.3:
                confidence = 'high'
            elif (std_int / mean_int) < 0.6:
                confidence = 'medium'
            else:
                confidence = 'low'
        elif len(intervals) == 1:
            expected_int = float(intervals[0])
            confidence = 'low'
        else:
            obs_days = int((pd.to_datetime(observation_end) - pd.to_datetime(observation_start)).days)
            expected_int = float(obs_days)
            confidence = 'very_low'

        last_date = pd.to_datetime(dates[-1])
        days_since = int((pd.to_datetime(observation_end) - last_date).days)
        # Avoid comparing timedelta-like types with floats
        is_overdue = False
        try:
            is_overdue = days_since > (expected_int * 1.5)
        except Exception:
            is_overdue = False

        return expected_int, last_date, days_since, is_overdue, confidence
    
    # Analyze E-W pattern
    ew_expected, ew_last_date, ew_days_since, ew_overdue, ew_confidence = analyze_type_pattern(ew_maneuvers, "E-W")
    
    # Analyze N-S pattern
    ns_expected, ns_last_date, ns_days_since, ns_overdue, ns_confidence = analyze_type_pattern(ns_maneuvers, "N-S")
    
    # Overall pattern analysis (all maneuvers)
    maneuver_dates = pd.to_datetime(maneuver_events['EPOCH']).sort_values().tolist()
    num_maneuvers = len(maneuver_dates)
    
    intervals_days = []
    if num_maneuvers >= 2:
        for i in range(1, num_maneuvers):
            intervals_days.append((maneuver_dates[i] - maneuver_dates[i-1]).days)
    
    if len(intervals_days) >= 2:
        median_interval = np.median(intervals_days)
        mean_interval = np.mean(intervals_days)
        std_interval = np.std(intervals_days)
        expected_interval_days = median_interval
        if std_interval / mean_interval < 0.3:
            pattern_confidence = 'high'
        elif std_interval / mean_interval < 0.6:
            pattern_confidence = 'medium'
        else:
            pattern_confidence = 'low'
    elif len(intervals_days) == 1:
        expected_interval_days = intervals_days[0]
        median_interval = intervals_days[0]
        pattern_confidence = 'low'
    else:
        observation_days = (observation_end - observation_start).days
        expected_interval_days = observation_days
        median_interval = observation_days
        pattern_confidence = 'very_low'
    
    last_maneuver_date = maneuver_dates[-1]
    days_since_last = (observation_end - last_maneuver_date).days
    is_overdue = days_since_last > (expected_interval_days * 1.5)
    
    # Calculate combined maintenance score
    ew_score = 100
    ns_score = 100
    
    # E-W score (60% weight - more critical for station-keeping)
    if ew_expected is not None and ew_days_since is not None:
        try:
            if ew_overdue:
                overdue_ratio = float(ew_days_since) / float(ew_expected)
                if overdue_ratio > 3.0:
                    ew_score = 0
                elif overdue_ratio > 2.0:
                    ew_score = 30
                else:
                    ew_score = 60
            else:
                recency_ratio = float(ew_days_since) / float(ew_expected)
                if recency_ratio < 0.5:
                    ew_score = 100
                elif recency_ratio < 1.0:
                    ew_score = 100
                else:
                    ew_score = 90

            # Adjust for confidence
            if ew_confidence == 'very_low':
                ew_score = max(50, ew_score * 0.7)
            elif ew_confidence == 'low':
                ew_score = max(60, ew_score * 0.85)
        except Exception:
            ew_score = 50
    else:
        ew_score = 50  # No E-W maneuvers detected or insufficient pattern info
    
    # N-S score (40% weight - less frequent but still important)
    if ns_expected is not None and ns_days_since is not None:
        try:
            if ns_overdue:
                overdue_ratio = float(ns_days_since) / float(ns_expected)
                if overdue_ratio > 3.0:
                    ns_score = 0
                elif overdue_ratio > 2.0:
                    ns_score = 30
                else:
                    ns_score = 60
            else:
                recency_ratio = float(ns_days_since) / float(ns_expected)
                if recency_ratio < 0.5:
                    ns_score = 100
                elif recency_ratio < 1.0:
                    ns_score = 100
                else:
                    ns_score = 90

            # Adjust for confidence
            if ns_confidence == 'very_low':
                ns_score = max(50, ns_score * 0.7)
            elif ns_confidence == 'low':
                ns_score = max(60, ns_score * 0.85)
        except Exception:
            ns_score = 70
    else:
        ns_score = 70  # No N-S maneuvers (less critical) or insufficient data
    
    # Combined maintenance score (weighted)
    maintenance_score = (ew_score * 0.6) + (ns_score * 0.4)
    
    # Build maintenance status message
    status_parts = []
    if ew_expected is not None:
        if ew_overdue:
            status_parts.append(f"E-W: OVERDUE ({ew_days_since} days, expected every {ew_expected:.0f} days)")
        else:
            status_parts.append(f"E-W: On schedule ({ew_days_since} days ago, every {ew_expected:.0f} days)")
    else:
        status_parts.append("E-W: No maneuvers detected")
    
    if ns_expected is not None:
        if ns_overdue:
            status_parts.append(f"N-S: OVERDUE ({ns_days_since} days, expected every {ns_expected:.0f} days)")
        else:
            status_parts.append(f"N-S: On schedule ({ns_days_since} days ago, every {ns_expected:.0f} days)")
    else:
        status_parts.append("N-S: No maneuvers detected")
    
    maintenance_status = " | ".join(status_parts)
    
    return {
        'num_maneuvers': num_maneuvers,
        'num_ew_maneuvers': num_ew,
        'num_ns_maneuvers': num_ns,
        'expected_interval_days': expected_interval_days,
        'ew_expected_interval_days': ew_expected,
        'ns_expected_interval_days': ns_expected,
        'median_interval_days': median_interval if len(intervals_days) > 0 else None,
        'last_maneuver_date': last_maneuver_date,
        'last_ew_maneuver_date': ew_last_date,
        'last_ns_maneuver_date': ns_last_date,
        'days_since_last_maneuver': days_since_last,
        'days_since_last_ew': ew_days_since,
        'days_since_last_ns': ns_days_since,
        'is_overdue': is_overdue,
        'ew_is_overdue': ew_overdue,
        'ns_is_overdue': ns_overdue,
        'pattern_confidence': pattern_confidence,
        'ew_confidence': ew_confidence,
        'ns_confidence': ns_confidence,
        'ew_score': ew_score,
        'ns_score': ns_score,
        'maintenance_score': maintenance_score,
        'maintenance_status': maintenance_status,
        'intervals': intervals_days if len(intervals_days) > 0 else None
    }


def assess_satellite_health_with_drift(sat_name, sat_df, maneuver_events, inc_tolerance, 
                                       min_man_per_month, max_man_per_month, uniformity_threshold,
                                       drift_tolerance_gso=0.05, service_requirements=None,
                                       pattern_maneuvers=None, pattern_df=None):
    """
    Comprehensive health assessment for a satellite including drift analysis.
    
    Uses instantaneous (latest) drift for health determination and always applies
    historical pattern analysis (last 365 days) for maneuver detection.
    
    Args:
        pattern_maneuvers: Maneuvers from last year's data for pattern analysis (optional)
        pattern_df: Last year's dataframe for pattern analysis (optional)
    """
    requirements_map = service_requirements if service_requirements is not None else NAVIK_SERVICE_REQUIREMENTS
    requirements = requirements_map.get(sat_name, {})
    
    # Handle different inclination formats (NavIC uses "inclination", QZSS uses different keys)
    target_inclination = None
    if "inclination" in requirements:
        target_inclination = requirements["inclination"]
    elif "inclination_target_deg" in requirements:
        target_inclination = requirements["inclination_target_deg"]
    elif "inclination_target_deg_range" in requirements:
        # For IGSO satellites with inclination range, use the midpoint
        inc_range = requirements["inclination_target_deg_range"]
        target_inclination = (inc_range[0] + inc_range[1]) / 2.0
    
    # Use instantaneous (latest) inclination for health assessment
    current_inclination = sat_df['INCLINATION'].iloc[-1]
    std_inclination = sat_df['INCLINATION'].std()
    
    # Determine satellite type
    if 0.0 < current_inclination < 10.0:
        sat_type = 'GEO'
    elif current_inclination >= 10.0:
        # Check if it's a QZSS satellite for specific QZO labeling
        is_qzss_system = service_requirements is not None and requirements.get('type') in ['IGSO', 'GEO']
        # If explicitly identified as QZSS or if we can infer it (though is_qzss flag is better)
        if is_qzss_system:
             sat_type = 'QZO'
        else:
             sat_type = 'IGSO'
    else:
        sat_type = 'Unclassified'
    
    observation_start = sat_df['EPOCH'].min()
    observation_end = sat_df['EPOCH'].max()
    observation_days = (observation_end - observation_start).days
    observation_months = observation_days / 30.0
    
    num_maneuvers = len(maneuver_events)
    maneuvers_per_month = num_maneuvers / observation_months if observation_months > 0 else 0
    
    # Detect if this is QZSS (service_requirements is not None and not NavIC)
    is_qzss = service_requirements is not None and requirements.get('type') in ['IGSO', 'GEO']
    
    # Inclination score with stability consideration
    if target_inclination is not None:
        inc_deviation = abs(current_inclination - target_inclination)
        
        # Penalize high standard deviation (unstable inclination)
        inc_stability_penalty = min(20, std_inclination * 10)
        
        inc_score = max(0, 100 - (inc_deviation / inc_tolerance) * 100 - inc_stability_penalty)
    else:
        inc_score = None
        inc_deviation = None
    
    # ========== DYNAMIC MANEUVER PATTERN ANALYSIS ==========
    # Use last year's data for pattern analysis if available, otherwise use selected range
    # Incorporate a launch-date estimate: use the satellite's first observation as a lower bound
    sat_first_obs = None
    try:
        sat_first_obs = pd.to_datetime(sat_df['EPOCH'].min())
    except Exception:
        sat_first_obs = None

    # Get commission/active date from config if available
    commission_date = None
    try:
        comm_raw = COMMISSION_DATES.get(sat_name)
        if comm_raw is not None:
            commission_date = pd.to_datetime(comm_raw)
    except Exception:
        commission_date = None

    # Effective active start is the later of first observation and commission date (if present)
    active_start = None
    if sat_first_obs is not None and commission_date is not None:
        active_start = max(sat_first_obs, commission_date)
    elif sat_first_obs is not None:
        active_start = sat_first_obs
    elif commission_date is not None:
        active_start = commission_date

    if pattern_maneuvers is not None and pattern_df is not None:
        pattern_obs_start = pd.to_datetime(pattern_df['EPOCH'].min())
        pattern_obs_end = pd.to_datetime(pattern_df['EPOCH'].max())
        # Do not analyze before the satellite's active start (commission/date or first obs)
        if active_start is not None and pattern_obs_start < active_start:
            effective_start = active_start
        else:
            effective_start = pattern_obs_start
        pattern_analysis = analyze_maneuver_pattern(pattern_maneuvers, effective_start, pattern_obs_end)
    else:
        # Fallback to selected range if pattern data not available; use satellite first obs as lower bound
        obs_start = pd.to_datetime(observation_start)
        obs_end = pd.to_datetime(observation_end)
        # Bound selected date range by active_start so pre-commission periods are excluded
        if active_start is not None and obs_start < active_start:
            obs_start = active_start
        pattern_analysis = analyze_maneuver_pattern(maneuver_events, obs_start, obs_end)
    
    # Use the dynamically determined maintenance score
    maintenance_score = pattern_analysis.get('maintenance_score', 50)
    maintenance_status = pattern_analysis.get('maintenance_status', 'Pattern analysis unavailable')
    expected_interval_days = pattern_analysis.get('expected_interval_days')
    days_since_last = pattern_analysis.get('days_since_last_maneuver')
    pattern_confidence = pattern_analysis.get('pattern_confidence', 'none')

    # Sanitize numeric pattern fields to avoid TypeError/ZeroDivisionError
    try:
        if expected_interval_days is not None:
            expected_interval_days = float(expected_interval_days)
            if expected_interval_days <= 0:
                expected_interval_days = None
    except Exception:
        expected_interval_days = None

    try:
        if days_since_last is not None:
            days_since_last = int(days_since_last)
    except Exception:
        days_since_last = None
    
    # Uniformity score with better weighting
    if num_maneuvers >= 2:
        maneuver_dates = pd.to_datetime(maneuver_events['EPOCH']).tolist()
        uniformity_cov = calculate_maneuver_uniformity(maneuver_dates)
        
        if uniformity_cov is not None and uniformity_cov <= uniformity_threshold:
            uniformity_score = 100
        elif uniformity_cov is not None:
            # Gradual degradation instead of abrupt
            excess = uniformity_cov - uniformity_threshold
            max_penalty = 50
            penalty = min(max_penalty, (excess / uniformity_threshold) * max_penalty)
            uniformity_score = 100 - penalty
        else:
            uniformity_score = 50
    else:
        uniformity_score = 50 if num_maneuvers == 1 else 0
        uniformity_cov = None
    
    # Enhanced DRIFT ANALYSIS
    if 'LonDrift_deg_per_day' in sat_df.columns:
        current_drift = sat_df['LonDrift_deg_per_day'].iloc[-1]  # Use instantaneous (latest) drift
        std_drift = sat_df['LonDrift_deg_per_day'].std()
        mean_drift = sat_df['LonDrift_deg_per_day'].mean()
        
        # Calculate drift trend
        drift_trend = calculate_drift_trend(sat_df)
        
        # Base drift assessment using instantaneous drift
        drift_assessment = assess_drift_health(current_drift, sat_type, drift_tolerance_gso)
        drift_score = drift_assessment['drift_score']
        drift_status = drift_assessment['drift_status']
        drift_color = drift_assessment['drift_color']
        
        # Stability penalty: penalize high standard deviation in drift (unstable station-keeping)
        if sat_type == 'GEO':
            drift_stability = std_drift / drift_tolerance_gso
            if drift_stability > 2:
                stability_penalty = min(30, (drift_stability - 2) * 10)
                drift_score = max(0, drift_score - stability_penalty)
        elif sat_type in ['IGSO', 'QZO']:
            drift_stability = std_drift / 2.0
            if drift_stability > 1:
                stability_penalty = min(20, (drift_stability - 1) * 10)
                drift_score = max(0, drift_score - stability_penalty)
        
        # Trend analysis bonus/penalty
        if drift_trend > 0.01:  # Drift magnitude increasing
            drift_score = max(0, drift_score - 10)
        elif drift_trend < -0.01:  # Drift magnitude decreasing (improving)
            drift_score = min(100, drift_score + 5)
        
    else:
        mean_drift = None
        std_drift = None
        current_drift = None
        drift_score = None
        drift_status = "N/A"
        drift_color = "⚪"
        drift_trend = None
    
    # ========== LONGITUDE SLOT DEVIATION ANALYSIS ==========
    longitude_deviation = None
    longitude_score = None
    designated_lon = None
    current_mean_lon = None
    
    # Get designated longitude from requirements
    if 'longitude' in requirements:
        designated_lon = requirements['longitude']
    elif 'central_longitude_deg' in requirements:
        designated_lon = requirements['central_longitude_deg']
    
    # Calculate current mean longitude - this requires satellite object for propagation
    # We'll mark it as unavailable here and calculate it separately if satellite object is provided
    # The longitude calculation will be done in the main app where we have access to satellite objects
    
    # For now, set score to None - it will be calculated elsewhere if satellite data is available
    longitude_score = None
    longitude_deviation = None
    current_mean_lon = None
    
    # Calculate overall score with updated weighting to include longitude deviation
    # Define base weights (updated to include longitude)
    weights = {
        'inc': 0.30,           # Reduced from 0.35
        'maintenance': 0.25,   # Same
        'uniformity': 0.10,    # Reduced from 0.15
        'drift': 0.20,         # Reduced from 0.25
        'longitude': 0.15      # New component
    }

    components = {}
    if inc_score is not None:
        components['inc'] = float(inc_score)
    if maintenance_score is not None:
        components['maintenance'] = float(maintenance_score)
    if uniformity_score is not None:
        components['uniformity'] = float(uniformity_score)
    if drift_score is not None:
        components['drift'] = float(drift_score)
    if longitude_score is not None:
        components['longitude'] = float(longitude_score)

    if len(components) == 0:
        overall_score = 50.0
    else:
        # Normalize weights for available components
        total_weight = sum(weights[k] for k in components.keys())
        weighted_sum = sum(components[k] * weights[k] for k in components.keys())
        overall_score = weighted_sum / total_weight
    
    if overall_score >= 85:
        health_status = "Excellent"
        status_color = "🟢"
    elif overall_score >= 70:
        health_status = "Good"
        status_color = "🟡"
    elif overall_score >= 50:
        health_status = "Fair"
        status_color = "🟠"
    else:
        health_status = "Needs Attention"
        status_color = "🔴"
    
    remarks = []
    
    # Inclination remarks
    if inc_score is not None and inc_deviation is not None:
        if inc_deviation <= inc_tolerance * 0.3:
            remarks.append(f"Excellent inclination control (±{inc_deviation:.2f}°)")
        elif inc_deviation <= inc_tolerance:
            remarks.append(f"Inclination within tolerance (±{inc_deviation:.2f}°)")
        else:
            remarks.append(f"⚠️ Inclination deviation exceeds tolerance ({inc_deviation:.2f}°)")
    
    # Enhanced drift remarks for both GEO (GSO) and IGSO/QZO
    if drift_score is not None:
        if sat_type == 'GEO':
            if drift_status == "Excellent":
                remarks.append(f"Excellent station-keeping ({drift_color} drift: {abs(current_drift):.3f}°/day)")
            elif drift_status == "Good":
                remarks.append(f"Good drift control ({drift_color} {abs(current_drift):.3f}°/day)")
            elif drift_status == "Fair":
                remarks.append(f"⚠️ Moderate drift detected ({drift_color} {abs(current_drift):.3f}°/day)")
            elif drift_status == "Poor":
                remarks.append(f"⚠️ High drift - requires correction ({drift_color} {abs(current_drift):.3f}°/day)")
            else:
                remarks.append(f"🔴 Critical drift - immediate attention needed ({abs(current_drift):.3f}°/day)")
            
            # Add drift direction
            if current_drift > 0:
                remarks.append(f"Drifting EASTWARD at {abs(current_drift):.3f}°/day")
            elif current_drift < 0:
                remarks.append(f"Drifting WESTWARD at {abs(current_drift):.3f}°/day")
        elif sat_type in ['IGSO', 'QZO']:
            if drift_status == "Normal":
                remarks.append(f"Normal {sat_type} drift ({drift_color} {abs(current_drift):.3f}°/day)")
            elif drift_status == "Elevated":
                remarks.append(f"⚠️ Elevated {sat_type} drift ({drift_color} {abs(current_drift):.3f}°/day)")
            else:
                remarks.append(f"⚠️ High {sat_type} drift ({drift_color} {abs(current_drift):.3f}°/day)")
        
        # Enhanced remarks about drift stability and trend
        if drift_trend is not None:
            if drift_trend > 0.01:
                remarks.append(f"📈 Drift magnitude increasing (trend: +{drift_trend:.3f}°/day)")
            elif drift_trend < -0.01:
                remarks.append(f"📉 Drift magnitude decreasing (trend: {drift_trend:.3f}°/day)")
        
        if sat_type == 'GEO' and std_drift is not None:
            if std_drift > drift_tolerance_gso:
                remarks.append(f"⚠️ Unstable drift (std dev: {std_drift:.3f}°/day)")
            elif std_drift > drift_tolerance_gso * 0.5:
                remarks.append(f"Moderate drift variability (std dev: {std_drift:.3f}°/day)")
    
    # Longitude slot deviation remarks
    if longitude_deviation is not None and designated_lon is not None:
        abs_dev = abs(longitude_deviation)
        if sat_type == 'GEO':
            if abs_dev <= 0.5:
                remarks.append(f"✅ Excellent longitude slot position ({longitude_deviation:+.2f}° from {designated_lon}°)")
            elif abs_dev <= 1.0:
                remarks.append(f"✓ Good longitude position ({longitude_deviation:+.2f}° from {designated_lon}°)")
            else:
                remarks.append(f"⚠️ Longitude deviation from designated slot ({longitude_deviation:+.2f}° from {designated_lon}°)")
        else:  # IGSO, QZO
            if abs_dev <= 5.0:
                remarks.append(f"✅ Within central longitude tolerance ({longitude_deviation:+.2f}° from {designated_lon}°)")
            else:
                remarks.append(f"⚠️ Central longitude deviation ({longitude_deviation:+.2f}° from {designated_lon}°)")
    
    # Dynamic maintenance remarks based on learned pattern (E-W and N-S separate)
    remarks.append(f"📊 {maintenance_status}")
    
    # E-W specific remarks
    ew_expected = pattern_analysis.get('ew_expected_interval_days')
    ew_days_since = pattern_analysis.get('days_since_last_ew')
    ew_confidence = pattern_analysis.get('ew_confidence')
    ew_overdue = pattern_analysis.get('ew_is_overdue')
    
    if ew_expected is not None:
        if ew_confidence == 'high':
            remarks.append(f"✅ E-W: Consistent pattern (every {ew_expected:.0f} days)")
        elif ew_confidence in ['medium', 'low']:
            remarks.append(f"ℹ️ E-W: Variable pattern (confidence: {ew_confidence})")
        
        if ew_overdue:
            remarks.append(f"🔴 E-W maneuver overdue by {ew_days_since - ew_expected:.0f} days")
        elif ew_days_since is not None:
            next_ew = ew_expected - ew_days_since
            if next_ew > 0:
                remarks.append(f"⏱️ Next E-W maneuver expected in ~{next_ew:.0f} days")
    
    # N-S specific remarks
    ns_expected = pattern_analysis.get('ns_expected_interval_days')
    ns_days_since = pattern_analysis.get('days_since_last_ns')
    ns_confidence = pattern_analysis.get('ns_confidence')
    ns_overdue = pattern_analysis.get('ns_is_overdue')
    
    if ns_expected is not None:
        if ns_confidence == 'high':
            remarks.append(f"✅ N-S: Consistent pattern (every {ns_expected:.0f} days)")
        elif ns_confidence in ['medium', 'low']:
            remarks.append(f"ℹ️ N-S: Variable pattern (confidence: {ns_confidence})")
        
        if ns_overdue:
            remarks.append(f"🔴 N-S maneuver overdue by {ns_days_since - ns_expected:.0f} days")
        elif ns_days_since is not None:
            next_ns = ns_expected - ns_days_since
            if next_ns > 0:
                remarks.append(f"⏱️ Next N-S maneuver expected in ~{next_ns:.0f} days")
    
    # Uniformity remarks
    if uniformity_cov is not None:
        if uniformity_cov <= uniformity_threshold:
            remarks.append("Regular maneuver pattern detected")
        else:
            remarks.append("Irregular maneuver spacing")
    
    if std_inclination < 0.1:
        remarks.append("Stable orbital parameters")
    
    # Get current altitude if available
    current_altitude = None
    if 'altitude_km' in sat_df.columns and not sat_df['altitude_km'].isna().all():
        current_altitude = sat_df['altitude_km'].iloc[-1]
    
    # Extract pattern details for display
    ew_expected = pattern_analysis.get('ew_expected_interval_days')
    ns_expected = pattern_analysis.get('ns_expected_interval_days')
    ew_days_since = pattern_analysis.get('days_since_last_ew')
    ns_days_since = pattern_analysis.get('days_since_last_ns')
    ew_confidence = pattern_analysis.get('ew_confidence', 'none')
    ns_confidence = pattern_analysis.get('ns_confidence', 'none')
    
    return {
        'Satellite': sat_name,
        'Type': sat_type,
        'Health Status': f"{status_color} {health_status}",
        'Overall Score': round(overall_score, 1),
        'Target Incl. (°)': target_inclination if target_inclination is not None else "N/A",
        'Incl. (°)': round(current_inclination, 3),
        'Incl. Dev. (°)': round(inc_deviation, 3) if inc_deviation is not None else "N/A",
        'Altitude (km)': round(current_altitude, 1) if current_altitude is not None else "N/A",
        'Mean Drift (°/day)': round(mean_drift, 4) if mean_drift is not None else "N/A",
        'Current Drift (°/day)': round(current_drift, 4) if current_drift is not None else "N/A",
        'Drift Status': f"{drift_color} {drift_status}",
        'Designated Lon (°)': round(designated_lon, 2) if designated_lon is not None else "N/A",
        'Current Mean Lon (°)': round(current_mean_lon, 2) if current_mean_lon is not None else "N/A",
        'Lon Slot Deviation (°)': round(longitude_deviation, 2) if longitude_deviation is not None else "N/A",
        'Lon Deviation Score': round(longitude_score, 1) if longitude_score is not None else "N/A",
        'Maneuvers/Month': round(maneuvers_per_month, 2),
        'Expected Interval (days)': round(expected_interval_days, 0) if expected_interval_days is not None else "N/A",
        'Days Since Last': days_since_last if days_since_last is not None else "N/A",
        'Pattern Confidence': pattern_confidence.replace('_', ' ').title(),
        'EW Maneuvers': int(maneuver_events['EW_MANEUVER'].sum()) if 'EW_MANEUVER' in maneuver_events.columns else 0,
        'NS Maneuvers': int(maneuver_events['NS_MANEUVER'].sum()) if 'NS_MANEUVER' in maneuver_events.columns else 0,
        'EW Expected Interval (days)': round(ew_expected, 0) if ew_expected is not None else "N/A",
        'NS Expected Interval (days)': round(ns_expected, 0) if ns_expected is not None else "N/A",
        'EW Days Since Last': ew_days_since if ew_days_since is not None else "N/A",
        'NS Days Since Last': ns_days_since if ns_days_since is not None else "N/A",
        'EW Pattern Confidence': ew_confidence.replace('_', ' ').title(),
        'NS Pattern Confidence': ns_confidence.replace('_', ' ').title(),
        'Uniformity (CoV)': round(uniformity_cov, 3) if uniformity_cov else "N/A",
        'Remarks': " | ".join(remarks),
        'Pattern Analysis Period': f"{pattern_obs_start.strftime('%Y-%m-%d')} to {pattern_obs_end.strftime('%Y-%m-%d')}" if pattern_maneuvers is not None else "Selected date range"

        #changes for longitudnal slot devialtion logical error fix 

        '_inc_score': round(inc_score, 1) if inc_score is not None else None,
        '_maintenance_score': round(maintenance_score, 1),
        '_uniformity_score': round(uniformity_score, 1),
        '_drift_score': round(drift_score, 1) if drift_score is not None else None,
    }
