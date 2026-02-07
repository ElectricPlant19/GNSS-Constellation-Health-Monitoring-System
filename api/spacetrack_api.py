"""
Space-Track API module for fetching satellite data
Handles authentication and data retrieval from space-track.org
"""

import requests
from requests.exceptions import Timeout, ConnectionError, RequestException
import streamlit as st
from config.config import LOGIN_URL


@st.cache_resource
def get_spacetrack_session(username: str, password: str):
    """Returns a logged-in requests.Session cached as a resource."""
    s = requests.Session()
    resp = s.post(LOGIN_URL, data={'identity': username, 'password': password}, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"Space-Track login failed: HTTP {resp.status_code}")
    return s


@st.cache_data(ttl=3600)
def fetch_tle_json_cached(norad_id: int, start_date: str, end_date: str, username: str, password: str):
    """Cached fetch of the GP history JSON."""
    session = get_spacetrack_session(username, password)
    gp_url = (
        f"https://www.space-track.org/basicspacedata/query/class/gp_history/"
        f"EPOCH/{start_date}--{end_date}/NORAD_CAT_ID/{norad_id}/orderby/EPOCH asc/format/json"
    )
    resp = session.get(gp_url, timeout=60)
    if resp.status_code != 200:
        raise Exception(f"Failed to fetch GP data for {norad_id}: HTTP {resp.status_code}")
    return resp.json()


@st.cache_data(ttl=3600)
def fetch_multiple_tles(norad_ids, username: str, password: str):
    """Fetch latest TLE data for multiple satellites."""
    session = get_spacetrack_session(username, password)
    ids_str = ','.join(map(str, norad_ids))
    # Use 'gp' class instead of 'tle_latest' to avoid 404 errors
    # Fetch data for last 30 days to ensure we get recent TLEs
    # We use format/tle (2-lines) and manually add the name line
    query_url = (
        f"https://www.space-track.org/basicspacedata/query/class/gp/"
        f"NORAD_CAT_ID/{ids_str}/EPOCH/>now-30/orderby/EPOCH desc/format/tle"
    )
    
    resp = session.get(query_url, timeout=60)
    if resp.status_code != 200:
        raise Exception(f"Failed to fetch TLE data: HTTP {resp.status_code}")
    
    # Process 2-line TLEs into 3-line format (Name, L1, L2) keeping only latest per satellite
    lines = resp.text.strip().split('\n')
    
    # Dictionary to store latest TLE per sat_id: {sat_id: [line1, line2]}
    # Since we ordered by EPOCH desc, the first occurrence we see is the latest
    latest_tles = {}
    
    i = 0
    while i < len(lines) - 1:
        line1 = lines[i].strip()
        line2 = lines[i+1].strip()
        
        if line1.startswith('1 ') and line2.startswith('2 '):
            try:
                # Extract NORAD ID from line 1 columns 2-7
                norad_id = int(line1[2:7])
                if norad_id not in latest_tles:
                    latest_tles[norad_id] = [line1, line2]
            except ValueError:
                pass
            i += 2
        else:
            i += 1
            
    # Reconstruct 3-line format for parser
    # Parser uses locally mapped name based on NORAD ID, so generic name in line 0 is fine
    output_lines = []
    for sat_id, tle_lines in latest_tles.items():
        output_lines.append(f"0 SATELLITE {sat_id}")
        output_lines.append(tle_lines[0])
        output_lines.append(tle_lines[1])
        
    return '\n'.join(output_lines)


def fetch_and_classify_satellite(norad_id: int, start_date: str, end_date: str,
                                 username: str, password: str, igso_min=10, deviation_tol=0.3):
    """Fetches and classifies satellite data."""
    import pandas as pd
    import numpy as np
    from config.config import R_EARTH
    
    try:
        data = fetch_tle_json_cached(int(norad_id), start_date, end_date, username, password)
    except Timeout:
        raise Exception(f"TIMEOUT: Space-Track API did not respond within 60 seconds for NORAD ID {norad_id}. The API may be overloaded. Please try again later or use a smaller date range.")
    except ConnectionError:
        raise Exception(f"CONNECTION ERROR: Unable to reach Space-Track API. Please check your internet connection.")
    except RequestException as e:
        raise Exception(f"REQUEST ERROR: {str(e)}")

    if not data:
        raise ValueError(f"No GP data found for NORAD ID {norad_id} in given range")

    df = pd.DataFrame(data)

    # Standardize column names
    if 'EPOCH' not in df.columns and 'epoch' in df.columns:
        df.rename(columns={'epoch': 'EPOCH'}, inplace=True)
    if 'INCLINATION' not in df.columns and 'inclination' in df.columns:
        df.rename(columns={'inclination': 'INCLINATION'}, inplace=True)
    if 'SEMIMAJOR_AXIS' not in df.columns and 'semimajor_axis' in df.columns:
        df.rename(columns={'semimajor_axis': 'SEMIMAJOR_AXIS'}, inplace=True)
    if 'MEAN_MOTION' not in df.columns and 'mean_motion' in df.columns:
        df.rename(columns={'mean_motion': 'MEAN_MOTION'}, inplace=True)

    if 'EPOCH' not in df.columns or 'INCLINATION' not in df.columns:
        raise ValueError("GP JSON missing required fields 'EPOCH' or 'INCLINATION'")

    required_cols = ['EPOCH', 'INCLINATION']
    if 'SEMIMAJOR_AXIS' in df.columns:
        required_cols.append('SEMIMAJOR_AXIS')
    if 'MEAN_MOTION' in df.columns:
        required_cols.append('MEAN_MOTION')
    # Preserve TLE lines for historical reconstruction
    if 'TLE_LINE1' in df.columns:
        required_cols.append('TLE_LINE1')
    if 'TLE_LINE2' in df.columns:
        required_cols.append('TLE_LINE2')
    if 'OBJECT_NAME' in df.columns:
        required_cols.append('OBJECT_NAME')
    # Preserve additional orbital elements for central longitude calculation
    if 'RA_OF_ASC_NODE' in df.columns:
        required_cols.append('RA_OF_ASC_NODE')
    if 'ARG_OF_PERICENTER' in df.columns:
        required_cols.append('ARG_OF_PERICENTER')
    if 'MEAN_ANOMALY' in df.columns:
        required_cols.append('MEAN_ANOMALY')
    if 'ECCENTRICITY' in df.columns:
        required_cols.append('ECCENTRICITY')
    
    df = df[required_cols].copy()
    df['EPOCH'] = pd.to_datetime(df['EPOCH'])
    df['INCLINATION'] = df['INCLINATION'].astype(float)
    
    # Calculate longitudinal drift
    if 'MEAN_MOTION' in df.columns:
        df['MEAN_MOTION'] = df['MEAN_MOTION'].astype(float)
        from analysis.drift_analysis import calculate_longitudinal_drift
        df['LonDrift_deg_per_day'] = calculate_longitudinal_drift(df['MEAN_MOTION'])

    # Classify satellite type
    df['type'] = df['INCLINATION'].apply(
        lambda x: 'GEO' if (x > 0.0 and x < 10.0) else ('IGSO' if x >= igso_min else 'Unclassified')
    )

    mean_incl = df['INCLINATION'].mean()
    df['mean_inclination'] = mean_incl
    df['maintained'] = df['INCLINATION'].apply(lambda x: abs(x - mean_incl) <= deviation_tol)

    df = df.sort_values('EPOCH').reset_index(drop=True)

    # Calculate altitude
    if 'SEMIMAJOR_AXIS' in df.columns:
        df['SEMIMAJOR_AXIS'] = df['SEMIMAJOR_AXIS'].astype(float)
        df['altitude_km'] = df['SEMIMAJOR_AXIS'] - R_EARTH
    else:
        df['SEMIMAJOR_AXIS'] = np.nan
        df['altitude_km'] = np.nan

    return df
