"""
TLE Cache Module - Bundled data loading and refresh logic for Streamlit Cloud deployment.
Provides offline-first data loading with optional API refresh support.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# Directory containing bundled data files
DATA_DIR = Path(__file__).parent


def get_data_file_path(constellation: str, data_type: str) -> Path:
    """
    Get the path to a bundled data file.
    
    Args:
        constellation: 'navic', 'qzss', or 'beidou3'
        data_type: 'tles' or 'gp_history'
    
    Returns:
        Path to the JSON data file
    """
    filename = f"{constellation.lower()}_{data_type}.json"
    return DATA_DIR / filename


def load_bundled_tles(constellation: str) -> dict:
    """
    Load bundled TLE data from JSON file.
    
    Args:
        constellation: 'navic', 'qzss', or 'beidou3'
    
    Returns:
        dict with keys: 'tle_data' (raw TLE string), 'timestamp', 'satellites'
        Returns empty dict if file not found
    """
    filepath = get_data_file_path(constellation, "tles")
    
    if not filepath.exists():
        return {}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"Error loading bundled TLEs for {constellation}: {e}")
        return {}


def load_bundled_gp_history(constellation: str) -> dict:
    """
    Load bundled GP history data from JSON file.
    
    Args:
        constellation: 'navic', 'qzss', or 'beidou3'
    
    Returns:
        dict with keys: 'satellites' (dict of sat_name -> list of GP records), 
                       'timestamp', 'start_date', 'end_date'
        Returns empty dict if file not found
    """
    filepath = get_data_file_path(constellation, "gp_history")
    
    if not filepath.exists():
        return {}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"Error loading bundled GP history for {constellation}: {e}")
        return {}


def get_tle_metadata(constellation: str) -> dict:
    """
    Get metadata about bundled TLE data (timestamp, satellite count).
    
    Args:
        constellation: 'navic', 'qzss', or 'beidou3'
    
    Returns:
        dict with 'timestamp', 'satellite_count', 'available'
    """
    data = load_bundled_tles(constellation)
    
    if not data:
        return {
            'available': False,
            'timestamp': None,
            'satellite_count': 0
        }
    
    return {
        'available': True,
        'timestamp': data.get('timestamp', 'Unknown'),
        'satellite_count': len(data.get('satellites', {}))
    }


def get_gp_history_metadata(constellation: str) -> dict:
    """
    Get metadata about bundled GP history data.
    
    Args:
        constellation: 'navic', 'qzss', or 'beidou3'
    
    Returns:
        dict with 'timestamp', 'start_date', 'end_date', 'satellite_count', 'available'
    """
    data = load_bundled_gp_history(constellation)
    
    if not data:
        return {
            'available': False,
            'timestamp': None,
            'start_date': None,
            'end_date': None,
            'satellite_count': 0
        }
    
    return {
        'available': True,
        'timestamp': data.get('timestamp', 'Unknown'),
        'start_date': data.get('start_date'),
        'end_date': data.get('end_date'),
        'satellite_count': len(data.get('satellites', {}))
    }


def save_tles_to_bundle(constellation: str, tle_text: str, satellites: dict) -> bool:
    """
    Save TLE data to bundled JSON file.
    
    Args:
        constellation: 'navic', 'qzss', or 'beidou3'
        tle_text: Raw TLE string (3-line format)
        satellites: Dict mapping sat_name -> norad_id
    
    Returns:
        True if successful, False otherwise
    """
    filepath = get_data_file_path(constellation, "tles")
    
    try:
        data = {
            'constellation': constellation,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'tle_data': tle_text,
            'satellites': satellites
        }
        
        # Ensure directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        return True
    except Exception as e:
        print(f"Error saving TLEs for {constellation}: {e}")
        return False


def save_gp_history_to_bundle(constellation: str, satellite_data: dict, 
                              start_date: str, end_date: str) -> bool:
    """
    Save GP history data to bundled JSON file.
    
    Args:
        constellation: 'navic', 'qzss', or 'beidou3'
        satellite_data: Dict mapping sat_name -> list of GP records (as dicts)
        start_date: Analysis start date (YYYY-MM-DD)
        end_date: Analysis end date (YYYY-MM-DD)
    
    Returns:
        True if successful, False otherwise
    """
    filepath = get_data_file_path(constellation, "gp_history")
    
    try:
        data = {
            'constellation': constellation,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'start_date': start_date,
            'end_date': end_date,
            'satellites': satellite_data
        }
        
        # Ensure directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        return True
    except Exception as e:
        print(f"Error saving GP history for {constellation}: {e}")
        return False


def format_timestamp_for_display(iso_timestamp: str) -> str:
    """
    Format an ISO timestamp for user-friendly display.
    
    Args:
        iso_timestamp: ISO format timestamp string
    
    Returns:
        Human-readable date string (e.g., "Jan 30, 2025")
    """
    if not iso_timestamp:
        return "Unknown"
    
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        return dt.strftime("%b %d, %Y")
    except Exception:
        return iso_timestamp[:10] if len(iso_timestamp) >= 10 else "Unknown"
