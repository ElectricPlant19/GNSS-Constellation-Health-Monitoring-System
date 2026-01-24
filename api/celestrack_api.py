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
    
    # Headers to avoid being blocked by CelesTrak
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/plain,text/html,application/xhtml+xml',
    }
    
    for norad_id in norad_ids:
        url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=TLE"
        
        try:
            response = requests.get(url, timeout=60, headers=headers)
            response.raise_for_status()
            tle_text = response.text.strip()
            
            # Only add if we got valid TLE data (should have 3 lines)
            if tle_text and len(tle_text.split('\n')) >= 3:
                all_tles.append(tle_text)
        except requests.exceptions.Timeout:
            st.warning(f"Timeout fetching TLE for NORAD ID {norad_id}")
            continue
        except requests.exceptions.RequestException as e:
            st.warning(f"Error fetching TLE for NORAD ID {norad_id}: {str(e)[:50]}")
            continue
        except Exception as e:
            continue
    
    if not all_tles:
        st.error("⚠️ Could not fetch TLE data from CelesTrak. The service may be temporarily unavailable.")
    
    return '\n'.join(all_tles)
