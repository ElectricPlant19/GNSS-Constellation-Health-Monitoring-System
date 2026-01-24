"""
CelesTrak API module for fetching TLE data
"""

import requests
import streamlit as st

@st.cache_data(ttl=3600)
def fetch_tles_from_celestrak(norad_ids):
    """
    Fetch TLE data from CelesTrak for a list of NORAD IDs.
    
    Args:
        norad_ids (list): List of NORAD IDs (integers or strings)
        
    Returns:
        str: Raw TLE text data (3 lines per satellite)
    """
    if not norad_ids:
        return ""
    
    all_tles = []
    
    for norad_id in norad_ids:
        url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=TLE"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            tle_text = response.text.strip()
            
            # Only add if we got valid TLE data (should have 3 lines)
            if tle_text and len(tle_text.split('\n')) >= 3:
                all_tles.append(tle_text)
        except Exception as e:
            print(f"Error fetching TLE for NORAD ID {norad_id} from CelesTrak: {e}")
            continue
    
    return '\n'.join(all_tles)
