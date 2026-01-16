#!/usr/bin/env python3
"""
QZS-6 Satellite Parameter Sensitivity Analysis
==============================================

This script performs comprehensive parameter sensitivity analysis for the QZS-6 satellite
to determine if the critical health status is due to default threshold settings or
actual satellite issues.

Usage:
    python test_qzs6_analysis.py --username YOUR_USERNAME --password YOUR_PASSWORD

Requirements:
    - Space-Track.org credentials
    - Dependencies from requirements.txt
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
from pathlib import Path

# Import modules from the main application
from config import QZSS_SATS, QZSS_SERVICE_REQUIREMENTS, DEFAULT_PARAMS
from spacetrack_api import fetch_and_classify_satellite
from drift_analysis import assess_drift_health, get_drift_direction
from maneuver_detection import detect_navik_maneuvers
from health_assessment import assess_satellite_health_with_drift


def print_header(text, char='='):
    """Print a formatted header"""
    width = 80
    print(f"\n{char * width}")
    print(f"{text:^{width}}")
    print(f"{char * width}\n")


def print_section(text):
    """Print a section header"""
    print(f"\n{'─' * 80}")
    print(f"📊 {text}")
    print(f"{'─' * 80}\n")


def fetch_qzs6_data(username, password, start_date, end_date):
    """Fetch TLE data for QZS-6"""
    print_section("Fetching QZS-6 Satellite Data")
    
    # Use the correct satellite name as it appears in config
    qzs6_name = "QZS-6 (Michibiki-6)"
    qzs6_norad = QZSS_SATS.get(qzs6_name)
    if not qzs6_norad:
        print(f"❌ Error: {qzs6_name} NORAD ID not found in configuration")
        print(f"Available satellites: {list(QZSS_SATS.keys())}")
        sys.exit(1)
    
    print(f"🛰️  Satellite: {qzs6_name}")
    print(f"📡 NORAD ID: {qzs6_norad}")
    print(f"📅 Date Range: {start_date} to {end_date}")
    print(f"\n⏳ Fetching data from Space-Track.org...")
    
    try:
        df = fetch_and_classify_satellite(
            norad_id=int(qzs6_norad),
            start_date=start_date,
            end_date=end_date,
            username=username,
            password=password,
            igso_min=10,
            deviation_tol=0.3
        )
        
        df['EPOCH'] = pd.to_datetime(df['EPOCH'])
        df = df.sort_values('EPOCH').reset_index(drop=True)
        
        # Keep only one TLE per day
        df['date'] = df['EPOCH'].dt.date
        df = df.sort_values('EPOCH').groupby('date', as_index=False).first()
        df['EPOCH'] = pd.to_datetime(df['EPOCH'])
        
        df['satellite'] = qzs6_name
        
        if 'mean_inclination' not in df.columns:
            df['mean_inclination'] = df['INCLINATION'].mean()
        
        print(f"✅ Successfully fetched {len(df)} TLE entries")
        print(f"📊 Data spans {(df['EPOCH'].max() - df['EPOCH'].min()).days} days")
        
        return df
        
    except Exception as e:
        print(f"❌ Error fetching data: {str(e)}")
        sys.exit(1)



def test_maneuver_detection_sensitivity(df, test_name, params):
    """Test maneuver detection with different parameter sets"""
    print(f"\n  Testing: {test_name}")
    print(f"  Parameters: Z={params['z_threshold']:.1f}, "
          f"SMA={params['sma_threshold']:.2f}km, "
          f"Inc={params['inc_threshold']:.4f}°, "
          f"Window={params['persist_window']}")
    
    detected = detect_navik_maneuvers(
        df,
        sma_col='SEMIMAJOR_AXIS',
        inc_col='INCLINATION',
        z_thresh=params['z_threshold'],
        sma_abs_thresh_km=params['sma_threshold'],
        inc_abs_thresh_deg=params['inc_threshold'],
        persist_window=int(params['persist_window'])
    )
    
    ew_maneuvers = int(detected['EW_MANEUVER'].sum()) if 'EW_MANEUVER' in detected.columns else 0
    ns_maneuvers = int(detected['NS_MANEUVER'].sum()) if 'NS_MANEUVER' in detected.columns else 0
    total_maneuvers = ew_maneuvers + ns_maneuvers
    
    print(f"  Results: EW={ew_maneuvers}, NS={ns_maneuvers}, Total={total_maneuvers}")
    
    return {
        'test_name': test_name,
        'ew_maneuvers': ew_maneuvers,
        'ns_maneuvers': ns_maneuvers,
        'total_maneuvers': total_maneuvers,
        'detected_df': detected
    }


def test_health_assessment_sensitivity(df, detected_df, test_name, params):
    """Test health assessment with different parameter sets"""
    print(f"\n  Testing: {test_name}")
    print(f"  Parameters: Incl_Tol={params['inclination_tolerance']:.1f}°, "
          f"Drift_Tol={params['drift_tolerance_gso']:.3f}°/day, "
          f"Min_Man={params['min_maneuvers_per_month']}, "
          f"Max_Man={params['max_maneuvers_per_month']}, "
          f"Uniformity={params['maneuver_uniformity_threshold']:.2f}")
    
    sat_name = df['satellite'].iloc[0]  # Get actual satellite name from dataframe
    maneuver_events = detected_df[detected_df['MANEUVER']].copy()
    maneuver_events['satellite'] = sat_name
    
    health_data = assess_satellite_health_with_drift(
        sat_name,
        df,
        maneuver_events,
        params['inclination_tolerance'],
        params['min_maneuvers_per_month'],
        params['max_maneuvers_per_month'],
        params['maneuver_uniformity_threshold'],
        params['drift_tolerance_gso'],
        service_requirements=QZSS_SERVICE_REQUIREMENTS,
        pattern_maneuvers=maneuver_events,
        pattern_df=df
    )
    
    print(f"  Health Status: {health_data['Health Status']}")
    print(f"  Overall Score: {health_data['Overall Score']:.1f}/100")
    print(f"  Drift Status: {health_data['Drift Status']}")
    
    return {
        'test_name': test_name,
        'health_status': health_data['Health Status'],
        'overall_score': health_data['Overall Score'],
        'drift_status': health_data['Drift Status'],
        'full_health_data': health_data
    }


def test_drift_analysis_sensitivity(df, test_name, drift_tolerance):
    """Test drift analysis with different tolerance levels"""
    print(f"\n  Testing: {test_name}")
    print(f"  Drift Tolerance: ±{drift_tolerance:.3f}°/day")
    
    if 'LonDrift_deg_per_day' not in df.columns:
        print("  ⚠️  No drift data available")
        return None
    
    mean_drift = df['LonDrift_deg_per_day'].mean()
    current_drift = df['LonDrift_deg_per_day'].iloc[-1]
    std_drift = df['LonDrift_deg_per_day'].std()
    
    # Determine satellite type
    mean_incl = df['INCLINATION'].mean()
    sat_type = 'GSO' if 0.0 < mean_incl < 10.0 else 'IGSO'
    
    drift_assessment = assess_drift_health(mean_drift, sat_type, drift_tolerance)
    drift_direction = get_drift_direction(mean_drift)
    
    print(f"  Satellite Type: {sat_type}")
    print(f"  Mean Drift: {mean_drift:.4f}°/day ({drift_direction})")
    print(f"  Current Drift: {current_drift:.4f}°/day")
    print(f"  Std Dev: {std_drift:.4f}°/day")
    print(f"  Assessment: {drift_assessment['drift_status']}")
    print(f"  Drift Score: {drift_assessment['drift_score']:.1f}/100")
    
    return {
        'test_name': test_name,
        'drift_tolerance': drift_tolerance,
        'mean_drift': mean_drift,
        'current_drift': current_drift,
        'std_drift': std_drift,
        'drift_status': drift_assessment['drift_status'],
        'drift_score': drift_assessment['drift_score']
    }


def run_comprehensive_analysis(df, username, password):
    """Run comprehensive parameter sensitivity analysis"""
    
    print_header("QZS-6 PARAMETER SENSITIVITY ANALYSIS")
    
    # Test 1: Maneuver Detection Sensitivity
    print_section("Test 1: Maneuver Detection Parameter Sensitivity")
    
    maneuver_tests = [
        ("Default Parameters", DEFAULT_PARAMS),
        ("Relaxed Detection (Higher Thresholds)", {
            'z_threshold': 4.0,
            'sma_threshold': 2.0,
            'inc_threshold': 0.015,
            'persist_window': 2
        }),
        ("Strict Detection (Lower Thresholds)", {
            'z_threshold': 2.0,
            'sma_threshold': 0.3,
            'inc_threshold': 0.002,
            'persist_window': 1
        }),
        ("Very Relaxed (QZSS Optimized)", {
            'z_threshold': 5.0,
            'sma_threshold': 3.0,
            'inc_threshold': 0.020,
            'persist_window': 3
        })
    ]
    
    maneuver_results = []
    detected_dfs = {}
    
    for test_name, params in maneuver_tests:
        result = test_maneuver_detection_sensitivity(df, test_name, params)
        maneuver_results.append(result)
        detected_dfs[test_name] = result['detected_df']
    
    # Test 2: Health Assessment Sensitivity
    print_section("Test 2: Health Assessment Parameter Sensitivity")
    
    health_tests = [
        ("Default Parameters", DEFAULT_PARAMS),
        ("Relaxed Tolerances", {
            'inclination_tolerance': 2.0,
            'drift_tolerance_gso': 0.10,
            'min_maneuvers_per_month': 0,
            'max_maneuvers_per_month': 10,
            'maneuver_uniformity_threshold': 2.0
        }),
        ("Strict Tolerances", {
            'inclination_tolerance': 0.5,
            'drift_tolerance_gso': 0.02,
            'min_maneuvers_per_month': 1,
            'max_maneuvers_per_month': 6,
            'maneuver_uniformity_threshold': 0.5
        }),
        ("QZSS-Specific Tolerances", {
            'inclination_tolerance': 1.5,
            'drift_tolerance_gso': 0.15,
            'min_maneuvers_per_month': 0,
            'max_maneuvers_per_month': 8,
            'maneuver_uniformity_threshold': 1.5
        })
    ]
    
    health_results = []
    
    for test_name, params in health_tests:
        # Use default maneuver detection for health tests
        detected_df = detected_dfs["Default Parameters"]
        result = test_health_assessment_sensitivity(df, detected_df, test_name, params)
        health_results.append(result)
    
    # Test 3: Drift Analysis Sensitivity
    print_section("Test 3: Drift Tolerance Sensitivity")
    
    drift_tests = [
        ("Default GSO Tolerance", DEFAULT_PARAMS['drift_tolerance_gso']),
        ("Relaxed Tolerance", 0.10),
        ("Strict Tolerance", 0.02),
        ("Very Relaxed (QZSS)", 0.20),
        ("IGSO-like Tolerance", 2.0)
    ]
    
    drift_results = []
    
    for test_name, tolerance in drift_tests:
        result = test_drift_analysis_sensitivity(df, test_name, tolerance)
        if result:
            drift_results.append(result)
    
    # Summary Analysis
    print_section("Summary Analysis & Recommendations")
    
    print("📊 MANEUVER DETECTION SUMMARY:")
    print(f"{'Test Name':<40} {'EW':>6} {'NS':>6} {'Total':>8}")
    print("─" * 80)
    for result in maneuver_results:
        print(f"{result['test_name']:<40} {result['ew_maneuvers']:>6} "
              f"{result['ns_maneuvers']:>6} {result['total_maneuvers']:>8}")
    
    print("\n📊 HEALTH ASSESSMENT SUMMARY:")
    print(f"{'Test Name':<40} {'Score':>8} {'Status':<25}")
    print("─" * 80)
    for result in health_results:
        print(f"{result['test_name']:<40} {result['overall_score']:>8.1f} "
              f"{result['health_status']:<25}")
    
    print("\n📊 DRIFT ANALYSIS SUMMARY:")
    print(f"{'Test Name':<40} {'Tolerance':>12} {'Score':>8} {'Status':<20}")
    print("─" * 80)
    for result in drift_results:
        print(f"{result['test_name']:<40} ±{result['drift_tolerance']:>10.3f}°/d "
              f"{result['drift_score']:>8.1f} {result['drift_status']:<20}")
    
    # Detailed Analysis
    print("\n" + "=" * 80)
    print("🔍 DETAILED ANALYSIS")
    print("=" * 80)
    
    # Check if critical status persists across parameters
    critical_count = sum(1 for r in health_results if '🔴' in r['health_status'])
    
    print(f"\n1. Health Status Consistency:")
    print(f"   - Critical status in {critical_count}/{len(health_results)} parameter sets")
    
    if critical_count == len(health_results):
        print("   ⚠️  CRITICAL STATUS PERSISTS across all parameter variations")
        print("   → This suggests a genuine satellite issue, not threshold sensitivity")
    elif critical_count == 0:
        print("   ✅ No critical status with adjusted parameters")
        print("   → Default thresholds may be too strict for this satellite")
    else:
        print("   ⚡ Mixed results - status depends on thresholds")
        print("   → Satellite is borderline; consider threshold adjustment")
    
    # Maneuver pattern analysis
    default_maneuvers = next(r for r in maneuver_results if r['test_name'] == "Default Parameters")
    relaxed_maneuvers = next(r for r in maneuver_results if "Relaxed" in r['test_name'])
    
    print(f"\n2. Maneuver Detection Sensitivity:")
    maneuver_variance = max([r['total_maneuvers'] for r in maneuver_results]) - \
                       min([r['total_maneuvers'] for r in maneuver_results])
    print(f"   - Maneuver count variance: {maneuver_variance}")
    
    if maneuver_variance > 5:
        print("   ⚠️  High sensitivity to detection parameters")
        print("   → Consider reviewing threshold appropriateness")
    else:
        print("   ✅ Low sensitivity - consistent maneuver detection")
    
    # Drift analysis
    if drift_results:
        default_drift = next(r for r in drift_results if "Default" in r['test_name'])
        print(f"\n3. Drift Assessment:")
        print(f"   - Mean drift: {default_drift['mean_drift']:.4f}°/day")
        print(f"   - Current drift: {default_drift['current_drift']:.4f}°/day")
        print(f"   - Drift variability: {default_drift['std_drift']:.4f}°/day")
        
        if abs(default_drift['mean_drift']) > 0.05:
            print(f"   ⚠️  Significant drift detected")
        else:
            print(f"   ✅ Drift within normal range")
    
    # Final Recommendation
    print("\n" + "=" * 80)
    print("📋 FINAL RECOMMENDATION")
    print("=" * 80)
    
    if critical_count >= len(health_results) * 0.75:
        print("\n🔴 CONCLUSION: QZS-6 appears to have genuine operational issues")
        print("\nREASONS:")
        print("  - Critical status persists across multiple parameter configurations")
        print("  - Not significantly affected by threshold adjustments")
        print("\nRECOMMENDATION:")
        print("  - Further investigation required")
        print("  - Review satellite telemetry and operational logs")
        print("  - Contact satellite operators if applicable")
    else:
        print("\n🟡 CONCLUSION: QZS-6 status is threshold-sensitive")
        print("\nREASONS:")
        print("  - Health status varies significantly with parameter adjustments")
        print("  - Satellite may be operating within acceptable range for QZSS")
        print("\nRECOMMENDATION:")
        print("  - Consider adjusting default thresholds for QZSS satellites")
        print("  - Use QZSS-specific parameter set")
        print("  - Monitor trends over longer time periods")
    
    print("\n" + "=" * 80)


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='QZS-6 Parameter Sensitivity Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_qzs6_analysis.py --username myuser --password mypass
  python test_qzs6_analysis.py --username myuser --password mypass --days 180
        """
    )
    
    parser.add_argument('--username', required=True, help='Space-Track.org username')
    parser.add_argument('--password', required=True, help='Space-Track.org password')
    parser.add_argument('--days', type=int, default=365, 
                       help='Number of days of historical data to analyze (default: 365)')
    
    args = parser.parse_args()
    
    # Calculate date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=args.days)
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    # Fetch data
    df = fetch_qzs6_data(args.username, args.password, start_date_str, end_date_str)
    
    # Run analysis
    run_comprehensive_analysis(df, args.username, args.password)
    
    print(f"\n✅ Analysis complete at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
