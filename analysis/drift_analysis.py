"""
Drift Analysis Module
Handles longitudinal drift calculations and drift health assessment
"""

import numpy as np
from config.config import GEOSYNC_MEAN_MOTION


def calculate_longitudinal_drift(mean_motion):
    """
    Calculate longitudinal drift in degrees per day.
    
    Parameters:
    -----------
    mean_motion : float
        Mean motion in revolutions/day from TLE
    
    Returns:
    --------
    float : Longitudinal drift in degrees/day
            Positive = Eastward drift, Negative = Westward drift
    """
    return (mean_motion - GEOSYNC_MEAN_MOTION) * 360


def assess_drift_health(drift_deg_per_day, sat_type, drift_tolerance_gso=0.05, drift_tolerance_igso=2.0):
    """
    Assess drift health based on satellite type.
    
    Parameters:
    -----------
    drift_deg_per_day : float
        Longitudinal drift in degrees/day
    sat_type : str
        'GSO' or 'IGSO'
    drift_tolerance_gso : float
        Acceptable drift for GSO satellites (degrees/day)
    drift_tolerance_igso : float
        Acceptable drift for IGSO satellites (degrees/day)
    
    Returns:
    --------
    dict : Drift assessment with score and status
    """
    abs_drift = abs(drift_deg_per_day)
    
    if sat_type == 'GSO':
        tolerance = drift_tolerance_gso
        if abs_drift <= tolerance * 0.3:
            drift_score = 100
            drift_status = "Excellent"
            drift_color = "🟢"
        elif abs_drift <= tolerance:
            drift_score = 80
            drift_status = "Good"
            drift_color = "🟢"
        elif abs_drift <= tolerance * 2:
            drift_score = 60
            drift_status = "Fair"
            drift_color = "🟡"
        elif abs_drift <= tolerance * 5:
            drift_score = 40
            drift_status = "Poor"
            drift_color = "🟠"
        else:
            drift_score = 0
            drift_status = "Critical"
            drift_color = "🔴"
    else:  # IGSO
        tolerance = drift_tolerance_igso
        if abs_drift <= tolerance:
            drift_score = 100
            drift_status = "Normal"
            drift_color = "🟢"
        elif abs_drift <= tolerance * 2:
            drift_score = 70
            drift_status = "Elevated"
            drift_color = "🟡"
        else:
            drift_score = 40
            drift_status = "High"
            drift_color = "🟠"
    
    return {
        'drift_score': drift_score,
        'drift_status': drift_status,
        'drift_color': drift_color,
        'abs_drift': abs_drift
    }


def calculate_drift_trend(sat_df, recent_window=7):
    """
    Calculate drift trend over time.
    
    Parameters:
    -----------
    sat_df : pandas.DataFrame
        Satellite data with 'LonDrift_deg_per_day' column
    recent_window : int
        Number of recent data points to consider
    
    Returns:
    --------
    float : Drift trend (positive = increasing drift magnitude)
    """
    if len(sat_df) < 2:
        return 0
    
    if len(sat_df) >= recent_window:
        recent_drift = sat_df['LonDrift_deg_per_day'].iloc[-recent_window:].mean()
        early_drift = sat_df['LonDrift_deg_per_day'].iloc[:recent_window].mean()
    else:
        recent_drift = sat_df['LonDrift_deg_per_day'].iloc[-1]
        early_drift = sat_df['LonDrift_deg_per_day'].iloc[0]
    
    return abs(recent_drift) - abs(early_drift)


def get_drift_direction(drift_value):
    """
    Get drift direction string.
    
    Parameters:
    -----------
    drift_value : float
        Drift value in degrees/day
    
    Returns:
    --------
    str : Direction string with emoji
    """
    if drift_value > 0:
        return "Eastward ➡️"
    elif drift_value < 0:
        return "Westward ⬅️"
    else:
        return "Stable ⏸️"
