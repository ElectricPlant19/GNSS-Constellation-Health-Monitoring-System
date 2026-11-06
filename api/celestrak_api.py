"""
CelesTrak GP JSON API (legacy function names retained for compatibility)
With Space-Track fallback for cloud environments where CelesTrak may be blocked
"""

import requests
import json
from api.orbital_data import latest_gp_records

# Make streamlit optional so this module works in CI/scripts without streamlit
try:
    import streamlit as st
except ImportError:
    class _Stub:
        @staticmethod
        def cache_data(func=None, **kwargs):
            return func if func is not None else lambda f: f

        @staticmethod
        def warning(msg):
            print(f'WARNING: {msg}')
    st = _Stub()


@st.cache_data(ttl=7200, show_spinner=False)
def _fetch_gp(query, timeout):
    """Cache endpoints for two hours, including failures; never retry errors."""
    try:
        response = requests.get(
            f'https://celestrak.org/NORAD/elements/gp.php?{query}&FORMAT=JSON',
            timeout=timeout,
            headers={'User-Agent': 'GNSS-Health-Monitor/1.0 (Educational/Research)',
                     'Accept': 'application/json'},
        )
        response.raise_for_status()
        return latest_gp_records(response.json())
    except (requests.RequestException, ValueError):
        return None


@st.cache_data(ttl=7200, show_spinner=False)
def fetch_tles_from_celestrak(norad_ids, timeout=10):
    """Return OMM-compatible GP JSON (supports six-digit IDs), or empty text."""
    wanted = list(dict.fromkeys(int(n) for n in norad_ids))
    if not wanted:
        return ''
    batch = _fetch_gp('GROUP=gnss', timeout)
    if batch is None:
        return ''
    records = latest_gp_records(batch, wanted)
    found = {int(r['NORAD_CAT_ID']) for r in records}
    # Newly launched objects may not yet be listed in the GNSS group.
    for norad in wanted:
        if norad in found:
            continue
        individual = _fetch_gp(f'CATNR={norad}', timeout)
        if individual is None:
            break  # Stop on HTTP/network errors, per CelesTrak's usage policy.
        records.extend(latest_gp_records(individual, [norad]))
    return json.dumps(records) if records else ''


def fetch_tles_with_fallback(norad_ids, username=None, password=None, timeout=10):
    """Return (GP JSON, source), filling partial CelesTrak results if possible."""
    if not norad_ids:
        return '', 'none'
    payload = fetch_tles_from_celestrak(norad_ids, timeout=timeout)
    records = latest_gp_records(payload) if payload else []
    found = {int(r['NORAD_CAT_ID']) for r in records}
    missing = [int(n) for n in norad_ids if int(n) not in found]
    source = 'celestrak' if records else 'none'
    if missing and username and password:
        try:
            from api.spacetrack_api import fetch_multiple_tles
            fallback = fetch_multiple_tles(missing, username, password)
            extra = latest_gp_records(fallback, missing) if fallback else []
            if extra:
                source = 'celestrak + spacetrack' if records else 'spacetrack'
                records.extend(extra)
        except Exception as exc:
            st.warning(f'Space-Track fallback failed: {exc}')
    return (json.dumps(records), source) if records else ('', 'none')
