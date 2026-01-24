"""
Maneuver Detection Module
Handles detection of orbital maneuvers using statistical analysis
"""

import numpy as np
import pandas as pd


def rolling_median_safe(s, window=3):
    """Compute rolling median with fallback for edge cases."""
    return s.astype(float).rolling(window=window, min_periods=1, center=True).median()


def mad_zscore(x, threshold=1e-9):
    """Robust z-score using Median Absolute Deviation (MAD)."""
    x = np.array(x, dtype=float)
    med = np.nanmedian(x)
    mad = np.nanmedian(np.abs(x - med))
    
    if mad < threshold or np.isnan(mad):
        mean = np.nanmean(x)
        std = np.nanstd(x)
        if std < threshold or np.isnan(std):
            return np.zeros_like(x)
        return (x - mean) / std
    
    return 0.6745 * (x - med) / mad


def detect_navik_maneuvers(df, sma_col='SEMIMAJOR_AXIS', inc_col='INCLINATION',
                           z_thresh=3.5, sma_abs_thresh_km=0.5, inc_abs_thresh_deg=0.01,
                           persist_window=2):
    """Detects orbital maneuvers for NavIC satellites."""
    df2 = df.copy().reset_index(drop=True)
    
    for c in [sma_col, inc_col]:
        if c in df2.columns:
            df2[c] = pd.to_numeric(df2[c], errors='coerce')
    
    if sma_col in df2.columns:
        df2[sma_col + '_smooth'] = rolling_median_safe(df2[sma_col], window=3)
    if inc_col in df2.columns:
        df2[inc_col + '_smooth'] = rolling_median_safe(df2[inc_col], window=3)
    
    df2['dSMA'] = df2[sma_col + '_smooth'].diff() if sma_col + '_smooth' in df2 else np.nan
    df2['dINC'] = df2[inc_col + '_smooth'].diff() if inc_col + '_smooth' in df2 else np.nan
    
    df2['z_dSMA'] = mad_zscore(df2['dSMA'].fillna(0))
    df2['z_dINC'] = mad_zscore(df2['dINC'].fillna(0))
    
    df2['SMA_candidate'] = False
    if 'dSMA' in df2.columns and 'z_dSMA' in df2.columns:
        df2.loc[
            (df2['dSMA'].abs() >= sma_abs_thresh_km) & (df2['z_dSMA'].abs() >= z_thresh),
            'SMA_candidate'
        ] = True
    
    # E-W maneuver detection based on SMA changes only
    df2['EW_candidate'] = df2['SMA_candidate'].copy()
    
    df2['INC_candidate'] = False
    if 'dINC' in df2.columns and 'z_dINC' in df2.columns:
        df2.loc[
            (df2['dINC'].abs() >= inc_abs_thresh_deg) & (df2['z_dINC'].abs() >= z_thresh),
            'INC_candidate'
        ] = True
    
    half = persist_window
    
    df2['pre_sma_med'] = df2[sma_col + '_smooth'].rolling(
        window=2*half+1, min_periods=1, center=False
    ).apply(
        lambda arr: np.median(arr[:-half]) if len(arr) > half else np.nan, raw=True
    )
    df2['post_sma_med'] = df2[sma_col + '_smooth'].shift(-half).rolling(
        window=2*half+1, min_periods=1, center=False
    ).apply(
        lambda arr: np.median(arr[half:]) if len(arr) > half else np.nan, raw=True
    )
    df2['sma_med_delta'] = (df2['post_sma_med'] - df2['pre_sma_med']).abs()
    
    df2['pre_inc_med'] = df2[inc_col + '_smooth'].rolling(
        window=2*half+1, min_periods=1, center=False
    ).apply(
        lambda arr: np.median(arr[:-half]) if len(arr) > half else np.nan, raw=True
    )
    df2['post_inc_med'] = df2[inc_col + '_smooth'].shift(-half).rolling(
        window=2*half+1, min_periods=1, center=False
    ).apply(
        lambda arr: np.median(arr[half:]) if len(arr) > half else np.nan, raw=True
    )
    df2['inc_med_delta'] = (df2['post_inc_med'] - df2['pre_inc_med']).abs()
    
    df2['EW_MANEUVER'] = False
    df2.loc[
        (df2['EW_candidate']) & (df2['sma_med_delta'] >= sma_abs_thresh_km),
        'EW_MANEUVER'
    ] = True
    
    df2['NS_MANEUVER'] = False
    df2.loc[
        (df2['INC_candidate']) & (df2['inc_med_delta'] >= inc_abs_thresh_deg),
        'NS_MANEUVER'
    ] = True
    
    df2['MANEUVER'] = df2['EW_MANEUVER'] | df2['NS_MANEUVER']
    
    return df2


def calculate_maneuver_uniformity(maneuver_dates):
    """Calculate coefficient of variation for maneuver spacing."""
    if len(maneuver_dates) < 2:
        return None
    
    maneuver_dates = sorted(maneuver_dates)
    intervals = [(maneuver_dates[i+1] - maneuver_dates[i]).days 
                 for i in range(len(maneuver_dates)-1)]
    
    if not intervals or np.mean(intervals) == 0:
        return None
    
    return np.std(intervals) / np.mean(intervals)
