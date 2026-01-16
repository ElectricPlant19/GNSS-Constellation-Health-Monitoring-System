"""
CelesTrak API module for fetching satellite TLE data
Handles TLE retrieval from celestrak.org (no authentication required)
"""

import requests
import streamlit as st


@st.cache_data(ttl=3600)
def fetch_tles_from_celestrak(norad_ids):
    """
    Fetch latest TLE data for multiple satellites from CelesTrak.
    
    CelesTrak returns 3LE format (three-line element sets):
    - Line 0: Satellite name
    - Line 1: TLE line 1
    - Line 2: TLE line 2
    
    Note: CelesTrak's API only supports fetching one satellite at a time via CATNR,
    so we make individual requests and combine the results.
    
    Args:
        norad_ids: List of NORAD catalog IDs
        
    Returns:
        str: TLE data in 3LE format (name + TLE1 + TLE2 for each satellite)
        
    Raises:
        Exception: If the API request fails
    """
    if not norad_ids:
        raise ValueError("No NORAD IDs provided")
    
    all_tle_data = []
    failed_ids = []
    
    for norad_id in norad_ids:
        try:
            # CelesTrak GP endpoint - CATNR accepts only one satellite at a time
            url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=TLE"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                failed_ids.append(norad_id)
                continue
            
            tle_text = response.text.strip()
            
            if not tle_text or "No GP data found" in tle_text:
                failed_ids.append(norad_id)
                continue
            
            all_tle_data.append(tle_text)
            
        except requests.exceptions.RequestException:
            failed_ids.append(norad_id)
            continue
    
    if not all_tle_data:
        raise Exception(
            f"CelesTrak failed to fetch TLE data for all satellites.\n"
            f"Failed NORAD IDs: {failed_ids}"
        )
    
    # Combine all TLE data with newlines
    combined_tle = "\n".join(all_tle_data)
    
    return combined_tle
