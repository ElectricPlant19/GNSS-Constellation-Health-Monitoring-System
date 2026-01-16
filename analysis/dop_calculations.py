"""
DOP (Dilution of Precision) Calculation Module
Handles DOP calculations and satellite position computations

This module calculates DOP values using standard GNSS methodology:
- Converts satellite positions to ECEF coordinates
- Computes line-of-sight unit vectors from observer to satellites
- Builds design matrix for position solution
- Calculates DOP metrics (GDOP, PDOP, HDOP, VDOP, TDOP)
"""

import numpy as np
import statistics
from datetime import datetime, timedelta
from datetime import timezone
from skyfield.api import load, EarthSatellite, wgs84
from config.config import NAVIK_SATS


def parse_tle_data(tle_text, sat_dict):
    """Parse TLE text and create satellite objects"""
    ts = load.timescale()
    satellites = {}
    
    lines = tle_text.strip().split('\n')
    
    for i in range(0, len(lines), 3):
        if i + 2 >= len(lines):
            break
        
        name = lines[i].strip()
        line1 = lines[i + 1].strip()
        line2 = lines[i + 2].strip()
        
        try:
            norad_id = int(line1[2:7])
            sat_name = None
            for s_name, s_id in sat_dict.items():
                if s_id == norad_id:
                    sat_name = s_name
                    break
            
            if sat_name:
                satellite = EarthSatellite(line1, line2, sat_name, ts)
                satellites[sat_name] = satellite
        except (ValueError, IndexError):
            continue
    
    return satellites


def calculate_satellite_position(satellite, time, observer_location):
    """Calculate satellite position relative to observer"""
    try:
        difference = satellite - observer_location
        topocentric = difference.at(time)
        alt, az, distance = topocentric.altaz()
        
        # Also get ECEF positions for accurate DOP calculation
        sat_geocentric = satellite.at(time)
        obs_geocentric = observer_location.at(time)
        
        return {
            'altitude': alt.degrees,
            'azimuth': az.degrees,
            'distance': distance.km,
            'elevation': alt.degrees,
            'sat_ecef': sat_geocentric.position.km,  # Satellite ECEF position
            'obs_ecef': obs_geocentric.position.km   # Observer ECEF position
        }
    except Exception:
        return None


# def geodetic_to_ecef(lat_deg, lon_deg, alt_m=0):
#     """
#     Convert geodetic coordinates (lat, lon, altitude) to ECEF coordinates.
    
#     Args:
#         lat_deg: Latitude in degrees
#         lon_deg: Longitude in degrees
#         alt_m: Altitude in meters above WGS84 ellipsoid
    
#     Returns:
#         numpy array [x, y, z] in meters
#     """
#     # WGS84 parameters
#     a = 6378137.0  # Semi-major axis (meters)
#     f = 1 / 298.257223563  # Flattening
#     e2 = 2 * f - f * f  # First eccentricity squared
    
#     lat_rad = np.radians(lat_deg)
#     lon_rad = np.radians(lon_deg)
    
#     # Radius of curvature in prime vertical
#     N = a / np.sqrt(1 - e2 * np.sin(lat_rad)**2)
    
#     x = (N + alt_m) * np.cos(lat_rad) * np.cos(lon_rad)
#     y = (N + alt_m) * np.cos(lat_rad) * np.sin(lon_rad)
#     z = (N * (1 - e2) + alt_m) * np.sin(lat_rad)
    
#     return np.array([x, y, z])


# def ecef_to_enu_matrix(lat_deg, lon_deg):
#     """
#     Create rotation matrix from ECEF to ENU (East-North-Up) frame.
    
#     Args:
#         lat_deg: Observer latitude in degrees
#         lon_deg: Observer longitude in degrees
    
#     Returns:
#         3x3 rotation matrix
#     """
#     lat_rad = np.radians(lat_deg)
#     lon_rad = np.radians(lon_deg)
    
#     sin_lat = np.sin(lat_rad)
#     cos_lat = np.cos(lat_rad)
#     sin_lon = np.sin(lon_rad)
#     cos_lon = np.cos(lon_rad)
    
#     # Rotation matrix from ECEF to ENU
#     R = np.array([
#         [-sin_lon,              cos_lon,             0      ],
#         [-sin_lat * cos_lon,   -sin_lat * sin_lon,   cos_lat],
#         [ cos_lat * cos_lon,    cos_lat * sin_lon,   sin_lat]
#     ])
    
#     return R


def calculate_design_matrix(satellite_positions, observer_lat, observer_lon, elevation_mask_deg=5):
    """
    Calculate the geometry matrix (design matrix) for DOP calculation.
    
    Uses direction cosines from azimuth and elevation angles:
    - sx = -sin(az) * cos(el)  (East component)
    - sy = cos(az) * cos(el)   (North component)
    - sz = sin(el)             (Up component)
    
    Where:
    - el = Local elevation angle
    - az = Local azimuth angle (from North)
    
    The design matrix A has one row per visible satellite:
    A = [sx₁  sy₁  sz₁  1]
        [sx₂  sy₂  sz₂  1]
        [...  ...  ...  1]
    
    Args:
        satellite_positions: List of satellite position dictionaries
        observer_lat: Observer latitude in degrees
        observer_lon: Observer longitude in degrees
        elevation_mask_deg: Minimum elevation angle in degrees (default 5°)
    
    Returns:
        numpy array: Design matrix A of shape (n_visible_sats, 4)
    """
    A = []
    
    sat_idx = 0
    for pos in satellite_positions:
        if pos is None:
            continue
            
        if pos['elevation'] > elevation_mask_deg:
            # Get azimuth and elevation in radians
            az = np.radians(pos['azimuth'])  # Azimuth from North
            el = np.radians(pos['elevation'])  # Elevation angle
            
            # Calculate direction cosines
            sx = -np.sin(az) * np.cos(el)  # East component (negative for East)
            sy = np.cos(az) * np.cos(el)   # North component
            sz = np.sin(el)                # Up component
            
            # Print Sx and Sy values (commented out)
            # print(f"Sx: {sx:+.6f}  Sy: {sy:+.6f}")
            
            # Design matrix row: [sx, sy, sz, 1]
            A.append([sx, sy, sz, 1])
            sat_idx += 1
    
    return np.array(A) if A else np.array([]).reshape(0, 4)


def calculate_dop_values(A):
    """
    Calculate various DOP values from the design matrix.
    
    Implementation follows the standard DOP calculation:
    1. Form the line-of-sight matrix A (already done)
    2. Compute A^T (transpose)
    3. Compute A^T * A
    4. Compute COV(x) = (A^T * A)^-1 (covariance matrix)
    5. Extract DOP values from diagonal elements:
       - GDOP = sqrt((sx)^2 + (sy)^2 + (sz)^2 + (st)^2)
       - PDOP = sqrt((sx)^2 + (sy)^2 + (sz)^2)
       - HDOP = sqrt((sx)^2 + (sy)^2)
       - VDOP = sqrt((sz)^2)
       - TDOP = sqrt((st)^2)
    
    Note: PDOP^2 = HDOP^2 + VDOP^2
          GDOP^2 = PDOP^2 + TDOP^2
    
    Args:
        A: Design matrix of shape (n_sats, 4) where each row is [sx, sy, sz, 1]
    
    Returns:
        dict: DOP values or None if calculation fails
    """
    if len(A) < 4:
        # print(f"ERROR: Cannot calculate DOP with only {len(A)} satellites (need at least 4)")
        return None
    
    try:
        # Step 1: Compute A^T (transpose)
        A_T = A.T
        
        # Step 2: Compute A^T * A
        ATA = np.dot(A_T, A)
        
        # Check condition number for numerical stability
        # A condition number > 1e8 indicates poor numerical stability
        cond = np.linalg.cond(ATA)
        if cond > 1e8:
            # print(f"WARNING: Ill-conditioned matrix (condition number: {cond:.2e})")
            return None
        
        # Check determinant (should be non-zero for invertibility)
        det = np.linalg.det(ATA)
        if abs(det) < 1e-10:
            # print(f"WARNING: Nearly singular matrix (determinant: {det:.2e})")
            return None
        
        # Step 3: Compute COV(x) = (A^T * A)^-1
        COV = np.linalg.inv(ATA)
        
        # Verify COV is positive definite (all diagonal elements should be positive)
        if not all(COV[i,i] > 0 for i in range(4)):
            # print("WARNING: Covariance matrix has non-positive diagonal elements")
            return None
        
        # Print diagonal values of covariance matrix (commented out)
        # print(f"\nDiagonal of COV(x) = (A^T * A)^-1:")
        # print(f"COV[0,0] (sx)^2: {COV[0,0]:.6f}")
        # print(f"COV[1,1] (sy)^2: {COV[1,1]:.6f}")
        # print(f"COV[2,2] (sz)^2: {COV[2,2]:.6f}")
        # print(f"COV[3,3] (st)^2: {COV[3,3]:.6f}")
        # print()
        
        # Step 4: Calculate DOP values from covariance matrix diagonal
        dop = {
            'GDOP': float(np.sqrt(COV[0,0] + COV[1,1] + COV[2,2] + COV[3,3])),  # sqrt((sx)^2 + (sy)^2 + (sz)^2 + (st)^2)
            'PDOP': float(np.sqrt(COV[0,0] + COV[1,1] + COV[2,2])),             # sqrt((sx)^2 + (sy)^2 + (sz)^2)
            'HDOP': float(np.sqrt(COV[0,0] + COV[1,1])),                        # sqrt((sx)^2 + (sy)^2)
            'VDOP': float(np.sqrt(COV[2,2])),                                   # sqrt((sz)^2)
            'TDOP': float(np.sqrt(COV[3,3])),                                   # sqrt((st)^2)
        }
        
        # Sanity checks with small tolerance for numerical errors
        eps = 0.001
        if dop['GDOP'] < dop['PDOP'] - eps:
            # print(f"WARNING: GDOP ({dop['GDOP']:.3f}) < PDOP ({dop['PDOP']:.3f})")
            return None
        
        if dop['PDOP'] < dop['HDOP'] - eps:
            # print(f"WARNING: PDOP ({dop['PDOP']:.3f}) < HDOP ({dop['HDOP']:.3f})")
            return None
            
        if dop['PDOP'] < dop['VDOP'] - eps:
            # print(f"WARNING: PDOP ({dop['PDOP']:.3f}) < VDOP ({dop['VDOP']:.3f})")
            return None
        
        # Reject unrealistic DOP values (indicating degenerate geometry or numerical issues)
        # For a 4-satellite constellation, GDOP > 100 is effectively unusable
        MAX_ACCEPTABLE_GDOP = 100.0
        if dop['GDOP'] > MAX_ACCEPTABLE_GDOP:
            # print(f"WARNING: GDOP ({dop['GDOP']:.3f}) exceeds maximum threshold ({MAX_ACCEPTABLE_GDOP})")
            return None
        
        # Quality assessment (kept for internal use, not printed)
        quality = "Excellent" if dop['GDOP'] < 2 else \
                  "Good" if dop['GDOP'] < 5 else \
                  "Moderate" if dop['GDOP'] < 10 else \
                  "Fair" if dop['GDOP'] < 20 else "Poor"
        
        # Print DOP calculation results (commented out)
        # print(f"DOP Calculation Results:")
        # print(f"  GDOP: {dop['GDOP']:.3f}  PDOP: {dop['PDOP']:.3f}  HDOP: {dop['HDOP']:.3f}")
        # print(f"  VDOP: {dop['VDOP']:.3f}  TDOP: {dop['TDOP']:.3f}")
        # print(f"  Geometry Quality: {quality}")
        # print()
        
        return dop
        
    except (np.linalg.LinAlgError, ValueError, FloatingPointError) as e:
        # print(f"ERROR: DOP calculation failed: {str(e)}")
        return None


def calculate_dop_for_location(satellites_dict, lat, lon, time, elevation_mask_deg=5):
    """
    Calculate DOP for a specific location and time.
    
    Args:
        satellites_dict: Dictionary of satellite name -> EarthSatellite object
        lat: Observer latitude in degrees
        lon: Observer longitude in degrees
        time: datetime object for calculation time
        elevation_mask_deg: Minimum elevation angle in degrees (default 5°)
    
    Returns:
        tuple: (dop_dict, visible_sat_names, all_sat_positions)
            - dop_dict: Dictionary of DOP values or None if insufficient satellites
            - visible_sat_names: List of satellite names above elevation mask
            - all_sat_positions: List of all satellite position dictionaries
    """
    ts = load.timescale()
    t = ts.utc(time.year, time.month, time.day, time.hour, time.minute, time.second)
    
    observer = wgs84.latlon(lat, lon)
    
    satellite_positions = []
    visible_sats = []
    
    for sat_name, sat_obj in satellites_dict.items():
        pos = calculate_satellite_position(sat_obj, t, observer)
        if pos:
            satellite_positions.append(pos)
            if pos['elevation'] > elevation_mask_deg:
                visible_sats.append(sat_name)
    
    H = calculate_design_matrix(satellite_positions, lat, lon, elevation_mask_deg)
    dop = calculate_dop_values(H)
    
    return dop, visible_sats, satellite_positions

def get_geo_box_vectorized(satellite, epoch, timestep_minutes, prop_duration_days):
    """Calculate geographic bounding box for satellite propagation."""
    if epoch.tzinfo is None:
        epoch = epoch.replace(tzinfo=timezone.utc)
    
    t1 = epoch
    t2 = t1 + timedelta(days=prop_duration_days)
    delta_t = (t2 - t1).seconds + 24*3600*(t2 - t1).days
    n_steps = int(delta_t / (timestep_minutes * 60)) + 1
    
    time_offsets = np.arange(1, n_steps-1) * (60 * timestep_minutes)
    time_offsets = time_offsets.tolist()
    epochs = [t1 + timedelta(seconds=t) for t in time_offsets]
    
    ts = load.timescale()
    ts_times = [ts.from_datetime(t) for t in epochs]
    
    positions = [satellite.at(t) for t in ts_times]
    
    lat_lon = [wgs84.latlon_of(pos) for pos in positions]
    latitudes = [ll[0].degrees for ll in lat_lon]
    longitudes = [ll[1].degrees for ll in lat_lon]
    
    return {
        'epochs': epochs,
        'latitudes': latitudes,
        'longitudes': longitudes,
        'min_lon': min(longitudes),
        'max_lon': max(longitudes),
        'mean_lon': statistics.mean(longitudes),
        'min_lat': min(latitudes),
        'max_lat': max(latitudes),
        'mean_lat': statistics.mean(latitudes)
    }



def calculate_bounding_boxes(satellites_dict, reference_time, timestep_minutes=15, prop_duration_days=1.5):
    """Calculate bounding boxes for all satellites."""
    import streamlit as st
    
    bounding_boxes = {}
    
    for sat_name, sat_obj in satellites_dict.items():
        try:
            box_data = get_geo_box_vectorized(sat_obj, reference_time, timestep_minutes, prop_duration_days)
            bounding_boxes[sat_name] = box_data
        except Exception as e:
            st.warning(f"Could not calculate bounding box for {sat_name}: {str(e)}")
            continue
    
    return bounding_boxes


def assess_dop_quality(dop_type, value):
    """
    Assess the quality of a DOP value based on the specified DOP type.
    
    Args:
        dop_type (str): Type of DOP ('GDOP', 'PDOP', 'HDOP', or 'VDOP')
        value (float): The DOP value to assess
        
    Returns:
        str: Quality assessment ('Ideal', 'Excellent', 'Good', 'Moderate', 'Fair', 'Poor')
    """
    from config.config import DOP_QUALITY_THRESHOLDS
    
    # Default to GDOP if invalid type is provided
    thresholds = DOP_QUALITY_THRESHOLDS.get(dop_type.upper(), DOP_QUALITY_THRESHOLDS['GDOP'])
    
    for quality, (min_val, max_val) in thresholds.items():
        if min_val <= value < max_val:
            return quality
    
    return 'Poor'


def get_dop_quality(gdop_value):
    """
    Get DOP quality assessment based on GDOP value.
    
    This is a convenience function that uses assess_dop_quality with GDOP type.
    
    Args:
        gdop_value (float): The GDOP value to assess
        
    Returns:
        str: Quality assessment ('Ideal', 'Excellent', 'Good', 'Moderate', 'Fair', 'Poor')
    """
    return assess_dop_quality('GDOP', gdop_value)