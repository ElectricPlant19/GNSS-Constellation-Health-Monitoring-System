"""
Helper script to find BeiDou-3 NORAD IDs from Space-Track.org
This script searches for BeiDou/Compass satellites and helps identify NORAD IDs
"""

import requests
import pandas as pd
from datetime import datetime

def login_spacetrack(username, password):
    """Login to Space-Track and return session"""
    session = requests.Session()
    login_url = "https://www.space-track.org/ajaxauth/login"
    
    response = session.post(login_url, data={
        'identity': username,
        'password': password
    })
    
    if response.status_code == 200:
        print("✅ Successfully logged in to Space-Track")
        return session
    else:
        print(f"❌ Login failed: {response.status_code}")
        return None

def search_beidou_satellites(session):
    """Search for BeiDou/Compass satellites"""
    
    # Search for satellites with BeiDou or Compass in name
    query_url = (
        "https://www.space-track.org/basicspacedata/query/class/satcat/"
        "OBJECT_NAME/~~BeiDou,Compass/"
        "orderby/LAUNCH_DATE desc/"
        "format/json"
    )
    
    response = session.get(query_url)
    
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data)
        
        # Filter for relevant columns
        if not df.empty:
            df = df[['OBJECT_NAME', 'NORAD_CAT_ID', 'LAUNCH_DATE', 'DECAY_DATE', 'OBJECT_TYPE']]
            df = df[df['DECAY_DATE'].isna()]  # Only active satellites
            
        return df
    else:
        print(f"❌ Search failed: {response.status_code}")
        return None

def get_latest_tle(session, norad_id):
    """Get latest TLE for a satellite"""
    query_url = (
        f"https://www.space-track.org/basicspacedata/query/class/gp/"
        f"NORAD_CAT_ID/{norad_id}/"
        f"orderby/EPOCH desc/limit/1/"
        f"format/json"
    )
    
    response = session.get(query_url)
    
    if response.status_code == 200:
        data = response.json()
        if data:
            return data[0]
    return None

def classify_beidou_satellite(tle_data):
    """Classify BeiDou satellite based on orbital parameters"""
    if not tle_data:
        return "Unknown"
    
    inclination = float(tle_data.get('INCLINATION', 0))
    period = float(tle_data.get('PERIOD', 0))
    
    # Geosynchronous orbit: period ~1436 minutes (23h 56m)
    is_geosync = 1430 < period < 1445
    
    if is_geosync:
        if inclination < 10:
            return "GEO"
        elif 50 < inclination < 60:
            return "IGSO"
        else:
            return "Other Geosync"
    elif 700 < period < 800:
        return "MEO"
    else:
        return "Other"

def analyze_beidou_constellation(username, password):
    """Main function to analyze BeiDou constellation"""
    
    print("=" * 80)
    print("BeiDou-3 NORAD ID Finder")
    print("=" * 80)
    print()
    
    # Login
    session = login_spacetrack(username, password)
    if not session:
        return
    
    print("\n🔍 Searching for BeiDou/Compass satellites...")
    df = search_beidou_satellites(session)
    
    if df is None or df.empty:
        print("❌ No satellites found")
        return
    
    print(f"✅ Found {len(df)} active BeiDou/Compass satellites\n")
    
    # Get TLE data for each satellite
    results = []
    
    for idx, row in df.iterrows():
        norad_id = row['NORAD_CAT_ID']
        name = row['OBJECT_NAME']
        
        print(f"Analyzing {name} (NORAD {norad_id})...", end=" ")
        
        tle = get_latest_tle(session, norad_id)
        sat_type = classify_beidou_satellite(tle)
        
        if tle:
            results.append({
                'Name': name,
                'NORAD_ID': norad_id,
                'Type': sat_type,
                'Inclination': float(tle.get('INCLINATION', 0)),
                'Period_min': float(tle.get('PERIOD', 0)),
                'Eccentricity': float(tle.get('ECCENTRICITY', 0)),
                'Mean_Motion': float(tle.get('MEAN_MOTION', 0)),
                'Launch_Date': row['LAUNCH_DATE']
            })
            print(f"✅ {sat_type}")
        else:
            print("❌ No TLE data")
    
    # Create results DataFrame
    results_df = pd.DataFrame(results)
    
    # Filter for IGSO and GEO only
    igso_geo_df = results_df[results_df['Type'].isin(['IGSO', 'GEO'])].copy()
    
    print("\n" + "=" * 80)
    print("BeiDou-3 IGSO and GEO Satellites")
    print("=" * 80)
    print()
    
    # Sort by type and inclination
    igso_geo_df = igso_geo_df.sort_values(['Type', 'Inclination'], ascending=[False, True])
    
    print(igso_geo_df.to_string(index=False))
    
    # Save to CSV
    output_file = 'beidou3_norad_ids.csv'
    igso_geo_df.to_csv(output_file, index=False)
    print(f"\n✅ Results saved to {output_file}")
    
    # Generate config.py code
    print("\n" + "=" * 80)
    print("Code for config.py (BEIDOU3_SATS dictionary)")
    print("=" * 80)
    print("\nBEIDOU3_SATS = {")
    
    for _, row in igso_geo_df.iterrows():
        name = row['Name']
        norad_id = row['NORAD_ID']
        sat_type = row['Type']
        incl = row['Inclination']
        
        # Try to create a clean name
        if 'IGSO' in name.upper():
            clean_name = name
        elif 'COMPASS' in name.upper():
            clean_name = name
        else:
            clean_name = name
            
        print(f'    "{clean_name}": {norad_id},  # {sat_type} - Incl: {incl:.1f}°')
    
    print("}")
    
    print("\n" + "=" * 80)
    print("Analysis Complete!")
    print("=" * 80)

if __name__ == "__main__":
    print("BeiDou-3 NORAD ID Finder")
    print("-" * 80)
    
    username = input("Enter Space-Track username: ").strip()
    password = input("Enter Space-Track password: ").strip()
    
    if username and password:
        analyze_beidou_constellation(username, password)
    else:
        print("❌ Username and password are required")
