"""
CelesTrak API module for fetching TLE data
"""

import requests
import streamlit as st
import time

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_tles_from_celestrack(norad_ids):
    """
    Fetch TLE data from CelesTrak for a list of NORAD IDs.
    Uses retry logic and alternative endpoints for cloud reliability.
    
    Args:
        norad_ids (list): List of NORAD IDs (integers or strings)
        
    Returns:
        str: Raw TLE text data (3 lines per satellite)
    """
    if not norad_ids:
        return ""
    
    all_tles = []
    
    # Headers to avoid being blocked
    headers = {
        'User-Agent': 'GNSS-Health-Monitor/1.0 (Educational/Research)',
        'Accept': 'text/plain',
    }
    
    # Try batch fetch first (faster and more reliable)
    try:
        # CelesTrak GP endpoint - try to fetch all at once using GROUP
        batch_url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=gnss&FORMAT=TLE"
        response = requests.get(batch_url, timeout=30, headers=headers)
        if response.status_code == 200:
            batch_text = response.text.strip()
            if batch_text and '1 ' in batch_text:
                # Parse batch response and filter for our satellites
                lines = batch_text.split('\n')
                for i in range(0, len(lines) - 2, 3):
                    if i + 2 < len(lines):
                        try:
                            line1 = lines[i + 1].strip()
                            # Extract NORAD ID from line 1 (columns 3-7)
                            if line1.startswith('1 '):
                                norad = int(line1[2:7])
                                if norad in [int(n) for n in norad_ids]:
                                    tle_block = '\n'.join([lines[i].strip(), line1, lines[i + 2].strip()])
                                    all_tles.append(tle_block)
                        except:
                            continue
    except Exception:
        pass  # Fall back to individual requests
    
    # If batch didn't work, try individual requests
    if not all_tles:
        for norad_id in norad_ids:
            # Try multiple retries
            for attempt in range(3):
                try:
                    url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=TLE"
                    response = requests.get(url, timeout=20, headers=headers)
                    
                    if response.status_code == 200:
                        tle_text = response.text.strip()
                        if tle_text and len(tle_text.split('\n')) >= 3 and '1 ' in tle_text:
                            all_tles.append(tle_text)
                            break
                    
                    time.sleep(0.5)  # Small delay between retries
                    
                except requests.exceptions.Timeout:
                    if attempt < 2:
                        time.sleep(1)
                        continue
                except Exception:
                    break
    
    if not all_tles:
        return ""
    
    return '\n'.join(all_tles)
