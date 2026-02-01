#!/usr/bin/env python3
"""
Update Bundled Data Script
Run this script locally to fetch fresh TLE and GP history data 
and save it to the data/ directory for bundled deployment.

Usage:
    python scripts/update_bundled_data.py --username YOUR_USERNAME --password YOUR_PASSWORD
    
Or set environment variables:
    SPACETRACK_USERNAME=your_username
    SPACETRACK_PASSWORD=your_password
    python scripts/update_bundled_data.py

Or the script will automatically read from .streamlit/secrets.toml if available.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import NAVIK_SATS, QZSS_SATS, BEIDOU3_SATS
from api.celestrak_api import fetch_tles_from_celestrak
from data.tle_cache import save_tles_to_bundle, save_gp_history_to_bundle


def load_credentials_from_secrets():
    """
    Load Space-Track credentials from .streamlit/secrets.toml file.
    
    Returns:
        tuple: (username, password) or (None, None) if not found
    """
    secrets_path = Path(__file__).parent.parent / ".streamlit" / "secrets.toml"
    
    if not secrets_path.exists():
        return None, None
    
    try:
        # Try using tomllib (Python 3.11+)
        try:
            import tomllib
            with open(secrets_path, 'rb') as f:
                secrets = tomllib.load(f)
        except ImportError:
            # Fallback to toml package
            try:
                import toml
                secrets = toml.load(secrets_path)
            except ImportError:
                # Simple manual parsing for nested TOML
                secrets = {}
                current_section = None
                with open(secrets_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('[') and line.endswith(']'):
                            current_section = line[1:-1]
                            secrets[current_section] = {}
                        elif '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            if current_section:
                                secrets[current_section][key] = value
                            else:
                                secrets[key] = value
        
        # Check for nested [spacetrack] section first
        if 'spacetrack' in secrets:
            username = secrets['spacetrack'].get('username')
            password = secrets['spacetrack'].get('password')
            if username and password:
                return username, password
        
        # Fall back to flat keys
        username = secrets.get('SPACETRACK_USERNAME') or secrets.get('spacetrack_username')
        password = secrets.get('SPACETRACK_PASSWORD') or secrets.get('spacetrack_password')
        
        return username, password
    except Exception as e:
        print(f"⚠️  Could not read secrets.toml: {e}")
        return None, None


def fetch_gp_history_for_satellite(norad_id: int, start_date: str, end_date: str,
                                    username: str, password: str) -> list:
    """
    Fetch GP history for a single satellite from Space-Track.
    
    Returns:
        List of GP records as dicts
    """
    import requests
    
    LOGIN_URL = "https://www.space-track.org/ajaxauth/login"
    
    session = requests.Session()
    resp = session.post(LOGIN_URL, data={'identity': username, 'password': password}, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"Space-Track login failed: HTTP {resp.status_code}")
    
    gp_url = (
        f"https://www.space-track.org/basicspacedata/query/class/gp_history/"
        f"EPOCH/{start_date}--{end_date}/NORAD_CAT_ID/{norad_id}/orderby/EPOCH asc/format/json"
    )
    
    resp = session.get(gp_url, timeout=120)
    if resp.status_code != 200:
        raise Exception(f"Failed to fetch GP data for {norad_id}: HTTP {resp.status_code}")
    
    return resp.json()


def update_constellation_tles(constellation_name: str, sat_dict: dict, verbose: bool = True):
    """
    Update bundled TLE data for a constellation using CelesTrak.
    
    Args:
        constellation_name: 'navic', 'qzss', or 'beidou3'
        sat_dict: Dictionary of satellite_name -> norad_id
        verbose: Print progress messages
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"Updating TLEs for {constellation_name.upper()}")
        print(f"{'='*60}")
    
    norad_ids = [nid for nid in sat_dict.values() if nid is not None]
    
    if verbose:
        print(f"Fetching TLEs for {len(norad_ids)} satellites from CelesTrak...")
    
    tle_data = fetch_tles_from_celestrak(norad_ids, timeout=30)
    
    if not tle_data:
        print(f"⚠️  Failed to fetch TLEs for {constellation_name}")
        return False
    
    success = save_tles_to_bundle(constellation_name, tle_data, sat_dict)
    
    if success and verbose:
        print(f"✅ Saved TLEs for {constellation_name} ({len(norad_ids)} satellites)")
    
    return success


def update_constellation_gp_history(constellation_name: str, sat_dict: dict,
                                     username: str, password: str,
                                     days: int = 90, verbose: bool = True):
    """
    Update bundled GP history data for a constellation using Space-Track.
    
    Args:
        constellation_name: 'navic', 'qzss', or 'beidou3'
        sat_dict: Dictionary of satellite_name -> norad_id
        username: Space-Track username
        password: Space-Track password
        days: Number of days of history to fetch
        verbose: Print progress messages
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"Updating GP History for {constellation_name.upper()}")
        print(f"{'='*60}")
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    if verbose:
        print(f"Date range: {start_str} to {end_str}")
    
    satellite_data = {}
    
    for sat_name, norad_id in sat_dict.items():
        if norad_id is None:
            if verbose:
                print(f"  ⏭️  Skipping {sat_name} (no NORAD ID)")
            continue
        
        if verbose:
            print(f"  📡 Fetching {sat_name} (NORAD {norad_id})...")
        
        try:
            records = fetch_gp_history_for_satellite(
                norad_id, start_str, end_str, username, password
            )
            satellite_data[sat_name] = records
            if verbose:
                print(f"     ✅ Got {len(records)} records")
        except Exception as e:
            print(f"     ⚠️  Error: {e}")
            satellite_data[sat_name] = []
    
    success = save_gp_history_to_bundle(
        constellation_name, satellite_data, start_str, end_str
    )
    
    if success and verbose:
        total_records = sum(len(r) for r in satellite_data.values())
        print(f"✅ Saved GP history for {constellation_name} ({total_records} total records)")
    
    return success


def main():
    parser = argparse.ArgumentParser(
        description="Update bundled TLE and GP history data for offline dashboard."
    )
    parser.add_argument('--username', '-u', 
                        default=os.environ.get('SPACETRACK_USERNAME'),
                        help='Space-Track username (or set SPACETRACK_USERNAME env var)')
    parser.add_argument('--password', '-p',
                        default=os.environ.get('SPACETRACK_PASSWORD'),
                        help='Space-Track password (or set SPACETRACK_PASSWORD env var)')
    parser.add_argument('--days', '-d', type=int, default=90,
                        help='Days of GP history to fetch (default: 90)')
    parser.add_argument('--constellation', '-c', 
                        choices=['navic', 'qzss', 'beidou3', 'all'],
                        default='all',
                        help='Constellation to update (default: all)')
    parser.add_argument('--tles-only', action='store_true',
                        help='Only update TLEs (skip GP history)')
    parser.add_argument('--history-only', action='store_true',
                        help='Only update GP history (skip TLEs)')
    
    args = parser.parse_args()
    
    # Try to get credentials from various sources
    username = args.username
    password = args.password
    
    # If not provided via CLI/env, try secrets.toml
    if not username or not password:
        secrets_username, secrets_password = load_credentials_from_secrets()
        if secrets_username and secrets_password:
            print("📂 Using credentials from .streamlit/secrets.toml")
            username = secrets_username
            password = secrets_password
    
    if not args.tles_only and (not username or not password):
        print("❌ Space-Track credentials required for GP history.")
        print("   Options:")
        print("   1. Use --username and --password arguments")
        print("   2. Set SPACETRACK_USERNAME/PASSWORD env vars")
        print("   3. Add credentials to .streamlit/secrets.toml")
        print("   4. Use --tles-only to only update TLEs (no credentials needed)")
        sys.exit(1)
    
    constellations = {
        'navic': NAVIK_SATS,
        'qzss': QZSS_SATS,
        'beidou3': BEIDOU3_SATS,
    }
    
    if args.constellation == 'all':
        targets = constellations
    else:
        targets = {args.constellation: constellations[args.constellation]}
    
    print(f"\n🛰️  GNSS Health Monitor - Data Update Script")
    print(f"   Timestamp: {datetime.now(timezone.utc).isoformat()}")
    
    # Update TLEs (uses CelesTrak, no auth needed)
    if not args.history_only:
        print("\n" + "="*60)
        print("UPDATING TLE DATA (CelesTrak)")
        print("="*60)
        
        for name, sat_dict in targets.items():
            update_constellation_tles(name, sat_dict)
    
    # Update GP History (uses Space-Track, auth required)
    if not args.tles_only:
        print("\n" + "="*60)
        print("UPDATING GP HISTORY DATA (Space-Track)")
        print("="*60)
        
        for name, sat_dict in targets.items():
            update_constellation_gp_history(
                name, sat_dict, username, password, args.days
            )
    
    print("\n" + "="*60)
    print("✅ DATA UPDATE COMPLETE")
    print("="*60)
    print("\nBundled data files updated in data/ directory.")
    print("Commit and push these changes to update Streamlit Cloud deployment.")


if __name__ == "__main__":
    main()
