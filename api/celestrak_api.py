"""
CelesTrak API module for fetching TLE data
With Space-Track fallback for cloud environments where CelesTrak may be blocked
"""

import requests
import time

# Make streamlit optional so this module works in CI/scripts without streamlit
try:
    import streamlit as st
except ImportError:
    # Create a minimal stub so @st.cache_data and st.warning work outside Streamlit
    class _Stub:
        @staticmethod
        def cache_data(func=None, *, ttl=None, show_spinner=True):
            """No-op decorator when streamlit is not installed."""
            if func is not None:
                return func
            def decorator(f):
                return f
            return decorator
        @staticmethod
        def warning(msg):
            print(f"WARNING: {msg}")
    st = _Stub()

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_tles_from_celestrak(norad_ids, timeout=10):
    """
    Fetch TLE data from CelesTrak for a list of NORAD IDs.
    Uses retry logic and alternative endpoints for cloud reliability.
    
    Args:
        norad_ids (list): List of NORAD IDs (integers or strings)
        timeout (int): Request timeout in seconds (default 10 for cloud)
        
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
    
    # Quick connectivity check - if this fails, skip CelesTrak entirely
    try:
        test_url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_ids[0]}&FORMAT=TLE"
        test_response = requests.get(test_url, timeout=5, headers=headers)
        if test_response.status_code != 200:
            return ""  # CelesTrak not responding, fail fast
    except Exception:
        return ""  # Network issue, fail fast
    
    # Try batch fetch first (faster and more reliable)
    try:
        # CelesTrak GP endpoint - try GNSS group first
        batch_url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=gnss&FORMAT=TLE"
        response = requests.get(batch_url, timeout=timeout, headers=headers)
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
                        except Exception:
                            continue
    except Exception:
        pass  # Fall back to individual requests
    
    # If batch didn't work, try individual requests (with reduced retries for speed)
    if not all_tles:
        for norad_id in norad_ids:
            # Reduced to 2 attempts for faster failure
            for attempt in range(2):
                try:
                    url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=TLE"
                    response = requests.get(url, timeout=timeout, headers=headers)
                    
                    if response.status_code == 200:
                        tle_text = response.text.strip()
                        if tle_text and len(tle_text.split('\n')) >= 3 and '1 ' in tle_text:
                            all_tles.append(tle_text)
                            break
                    
                    time.sleep(0.3)  # Shorter delay between retries
                    
                except requests.exceptions.Timeout:
                    if attempt < 1:
                        time.sleep(0.5)
                        continue
                except Exception:
                    break
    
    if not all_tles:
        return ""
    
    return '\n'.join(all_tles)


def fetch_tles_with_fallback(norad_ids, username=None, password=None, timeout=10):
    """
    Fetch TLE data with CelesTrak as primary source and Space-Track as fallback.
    This is useful for cloud environments where CelesTrak may be blocked.
    
    Args:
        norad_ids (list): List of NORAD IDs
        username (str): Space-Track username (for fallback)
        password (str): Space-Track password (for fallback)
        timeout (int): Request timeout in seconds
        
    Returns:
        tuple: (tle_data: str, source: str) - TLE data and the source used
    """
    if not norad_ids:
        return "", "none"
    
    # Try CelesTrak first (no auth required)
    tle_data = fetch_tles_from_celestrak(norad_ids, timeout=timeout)
    if tle_data:
        return tle_data, "celestrak"
    
    # Fall back to Space-Track if credentials provided
    if username and password:
        try:
            from api.spacetrack_api import fetch_multiple_tles
            tle_data = fetch_multiple_tles(norad_ids, username, password)
            if tle_data:
                return tle_data, "spacetrack"
            else:
                st.warning("⚠️ Space-Track fallback returned no data.")
        except Exception as e:
            # Space-Track also failed - log the error for debugging
            st.warning(f"⚠️ Space-Track fallback failed: {str(e)}")
            pass
    
    return "", "none"
