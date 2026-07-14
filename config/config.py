"""
Configuration file for NavIC Comprehensive Monitoring System
Contains all constants, satellite data, and configuration parameters
"""

# Constants
MU = 398600.4418  # km^3/s^2
R_EARTH = 6371.0  # km
GEOSYNC_MEAN_MOTION = 1.00273790935  # revolutions/day for perfect geostationary orbit (= 86400 / 86164.09053)

# Orbital altitude thresholds (km)
GEO_NOMINAL_ALTITUDE = 35786.0  # Nominal GEO altitude (km)
GEO_ALTITUDE_TOLERANCE = 100.0  # Normal operational tolerance (±100 km)
GRAVEYARD_ORBIT_THRESHOLD = 36000.0  # Altitude above which satellite is likely in graveyard orbit
GRAVEYARD_ORBIT_MIN = 35986.0  # Minimum graveyard orbit altitude (GEO + 200 km)

# NavIC Satellite NORAD IDs
NAVIK_SATS = {
    "IRNSS-1B": 39635,
    "IRNSS-1C": 40269,
    "IRNSS-1D": 40547,
    "IRNSS-1E": 41241,
    "IRNSS-1F": 41384,
    "IRNSS-1G": 41469,
    "IRNSS-1I": 43286,
    "NVS-01": 56759
}

# India's extreme geographical points for DOP analysis
INDIA_EXTREME_POINTS = {
    "Northernmost (Siachen Glacier)": (35.5, 77.0),
    "Southernmost (Indira Point)": (6.75, 93.85),
    "Easternmost (Kibithu)": (28.0, 97.0),
    "Westernmost (Guhar Moti)": (23.7, 68.1),
    "Capital (Delhi)": (28.7, 77.1)
}

# Japan's key geographical points for QZSS DOP analysis
JAPAN_KEY_POINTS = {
    "Northernmost (Hokkaido - Wakkanai)": (45.4, 141.7),
    "Southernmost (Okinawa - Ishigaki)": (24.3, 124.2),
    "Easternmost (Tokyo)": (35.7, 139.7),
    "Westernmost (Kyushu - Nagasaki)": (32.8, 129.9),
    "Capital (Tokyo)": (35.7, 139.7)
}

# China's key geographical points for BeiDou-3 DOP analysis
CHINA_KEY_POINTS = {
    "Northernmost (Mohe, Heilongjiang)": (53.5, 122.5),
    "Southernmost (Sansha, Hainan)": (16.8, 112.3),
    "Easternmost (Fuyuan, Heilongjiang)": (48.4, 134.7),
    "Westernmost (Wuqia, Xinjiang)": (39.7, 75.3),
    "Capital (Beijing)": (39.9, 116.4),
    "Shanghai": (31.2, 121.5),
    "Guangzhou": (23.1, 113.3),
    "Chengdu": (30.7, 104.1),
    "Urumqi (Xinjiang)": (43.8, 87.6),
    "Lhasa (Tibet)": (29.7, 91.1)
}

# NavIC service requirements (target longitudes and inclinations)
# GEO satellites (inclination ~5°): 32.5°E, 83°E, 131.5°E
# GEO satellites (inclination ~29-30°): 55°E (2 sats), 111.75°E (2 sats)
NAVIK_SERVICE_REQUIREMENTS = {
    "IRNSS-1B": {"longitude": 55.0, "inclination": 29.0},      # GEO
    "IRNSS-1C": {"longitude": 83.0, "inclination": 5.0},       # GEO
    "IRNSS-1D": {"longitude": 111.75, "inclination": 30.0},    # GEO
    "IRNSS-1E": {"longitude": 111.75, "inclination": 29.0},    # GEO
    "IRNSS-1F": {"longitude": 32.5, "inclination": 5.0},       # GEO
    "IRNSS-1G": {"longitude": 129.5, "inclination": 5.1},      # GEO (messaging-only; navigation services via NVS-1)
    "IRNSS-1I": {"longitude": 55.0, "inclination": 29.0},      # GEO
    "NVS-01": {"longitude": 131.5, "inclination": 5.0}         # GEO
}

# QZSS Satellite NORAD IDs (fill correct NORAD_CAT_ID values)
QZSS_SATS = {
    "QZS-1R (Michibiki-1R)": 49336,
    "QZS-2 (Michibiki-2)": 42738,    
    "QZS-3 (Michibiki-3)": 42917,     
    "QZS-4 (Michibiki-4)": 42965,   
    "QZS-6 (Michibiki-6)": 62876      
}

# QZSS service/target requirements (per provided specifications)
# Semi-major axis 42164 km ±10 km, eccentricity < 0.099, period ≈ 23h56m
# IGSO trio: inclination 39–41°, argument of perigee 270° ±1°, central track 139°E ±5°
# GEO members: inclination 0°, QZS-3 at 127°E, QZS-6 at 90.5°E
QZSS_SERVICE_REQUIREMENTS = {
    "QZS-1R (Michibiki-1R)": {
        "type": "IGSO",
        "central_longitude_deg": 148.0, "longitude_tol_deg": 5.0,
        "inclination_target_deg_range": (39.0, 47.0),
        "arg_perigee_deg": 270.0, "arg_perigee_tol_deg": 1.0,
        "sma_km": 42164.0, "sma_tol_km": 10.0,
        "ecc_max": 0.099
    },
    "QZS-2 (Michibiki-2)": {
        "type": "IGSO",
        "central_longitude_deg": 139.0, "longitude_tol_deg": 5.0,
        "inclination_target_deg_range": (39.0, 47.0),
        "arg_perigee_deg": 270.0, "arg_perigee_tol_deg": 1.0,
        "sma_km": 42164.0, "sma_tol_km": 10.0,
        "ecc_max": 0.099
    },
    "QZS-4 (Michibiki-4)": {
        "type": "IGSO",
        "central_longitude_deg": 139.0, "longitude_tol_deg": 5.0,
        "inclination_target_deg_range": (39.0, 47.0),
        "arg_perigee_deg": 270.0, "arg_perigee_tol_deg": 1.0,
        "sma_km": 42164.0, "sma_tol_km": 10.0,
        "ecc_max": 0.099
    },
    "QZS-3 (Michibiki-3)": {
        "type": "GEO",
        "central_longitude_deg": 127.0, "longitude_tol_deg": 0.5,
        "inclination_target_deg": 0.0, "inclination_tol_deg": 0.5,
        "sma_km": 42164.0, "sma_tol_km": 10.0,
        "ecc_max": 0.099
    },
    "QZS-6 (Michibiki-6)": {
        "type": "GEO",
        "central_longitude_deg": 90.5, "longitude_tol_deg": 0.5,
        "inclination_target_deg": 0.0, "inclination_tol_deg": 0.5,
        "sma_km": 42164.0, "sma_tol_km": 10.0,
        "ecc_max": 0.099
    }
}

# Typical maintenance cadence for QZSS (about once every six months)
QZSS_MAINTENANCE_NOTE = "Orbit correction maneuvers occur roughly once every six months."

# BeiDou-3 Satellite NORAD IDs (IGSO and GEO satellites only)
# Note: NORAD IDs need to be filled in with actual values from Space-Track
# BEIDOU3_SATS = {
#     # Only include BeiDou-3 (BDS-3) satellites — remove BeiDou-1/2 (Compass) entries
#     # GEO Satellites (BeiDou-3)
#     "BeiDou-3 G1": 43683,      # BEIDOU-3 G1 (GEO)
#     "BeiDou-3 G2": 45344,      # BEIDOU-3 G2 (GEO)
#     "BeiDou-3 G3": 45807,      # BEIDOU-3 G3 (GEO)
#     "BeiDou-3 G4": 56564,      # BEIDOU-3 G4 (GEO; launched 2023)

#     # IGSO Satellites (BeiDou-3)
#     "BeiDou-3 I1": 44204,      # BEIDOU-3 IGSO-1
#     "BeiDou-3 I2": 44337,      # BEIDOU-3 IGSO-2
#     "BeiDou-3 I3": 44709,      # BEIDOU-3 IGSO-3
# }


# BEIDOU3_SERVICE_REQUIREMENTS = {
#     # Service requirements for BeiDou-3 satellites only
#     "BeiDou-3 I1": {
#         "type": "IGSO",
#         "central_longitude_deg": 120.0, "longitude_tol_deg": 5.0,
#         "inclination_target_deg": 55.0, "inclination_tol_deg": 1.0,
#         "sma_km": 42164.0, "sma_tol_km": 10.0,
#         "ecc_max": 0.05
#     },
#     "BeiDou-3 I2": {
#         "type": "IGSO",
#         "central_longitude_deg": 120.0, "longitude_tol_deg": 5.0,
#         "inclination_target_deg": 55.0, "inclination_tol_deg": 1.0,
#         "sma_km": 42164.0, "sma_tol_km": 10.0,
#         "ecc_max": 0.05
#     },
#     "BeiDou-3 I3": {
#         "type": "IGSO",
#         "central_longitude_deg": 120.0, "longitude_tol_deg": 5.0,
#         "inclination_target_deg": 55.0, "inclination_tol_deg": 1.0,
#         "sma_km": 42164.0, "sma_tol_km": 10.0,
#         "ecc_max": 0.05
#     },
#     # GEO satellites
#     "BeiDou-3 G1": {
#         "type": "GEO",
#         "central_longitude_deg": 140.0, "longitude_tol_deg": 0.5,
#         "inclination_target_deg": 0.0, "inclination_tol_deg": 0.5,
#         "sma_km": 42164.0, "sma_tol_km": 10.0,
#         "ecc_max": 0.05
#     },
#     "BeiDou-3 G2": {
#         "type": "GEO",
#         "central_longitude_deg": 80.0, "longitude_tol_deg": 0.5,
#         "inclination_target_deg": 0.0, "inclination_tol_deg": 0.5,
#         "sma_km": 42164.0, "sma_tol_km": 10.0,
#         "ecc_max": 0.05
#     },
#     "BeiDou-3 G3": {
#         "type": "GEO",
#         "central_longitude_deg": 110.5, "longitude_tol_deg": 0.5,
#         "inclination_target_deg": 0.0, "inclination_tol_deg": 0.5,
#         "sma_km": 42164.0, "sma_tol_km": 10.0,
#         "ecc_max": 0.05
#     },
#     "BeiDou-3 G4": {
#         "type": "GEO",
#         "central_longitude_deg": 160.0, "longitude_tol_deg": 0.5,
#         "inclination_target_deg": 0.0, "inclination_tol_deg": 0.5,
#         "sma_km": 42164.0, "sma_tol_km": 10.0,
#         "ecc_max": 0.05
#     }  # G4 launched to 160°E (backup); swapped to 140°E Apr 2026
# }


BEIDOU3_SATS = {
    "BeiDou-3 G1": 43683,
    "BeiDou-3 G2": 45344,
    "BeiDou-3 G3": 45807,
    "BeiDou-3 G4": 56564,
    "BeiDou-3 I1": 44204,
    "BeiDou-3 I2": 44337,
    "BeiDou-3 I3": 44709,
}

BEIDOU3_SERVICE_REQUIREMENTS = {
    "BeiDou-3 I1": {
        "type": "IGSO",
        "central_longitude_deg": 118.0,
        "longitude_tol_deg": 5.0,
        "inclination_target_deg": 55.0,
        "inclination_target_deg_range": (52.0, 58.0),
        "inclination_tol_deg": 3.0,
        "sma_km": 42164.0,
        "sma_tol_km": 10.0,
        "ecc_max": 0.05
    },
    "BeiDou-3 I2": {
        "type": "IGSO",
        "central_longitude_deg": 118.0,
        "longitude_tol_deg": 5.0,
        "inclination_target_deg": 55.0,
        "inclination_target_deg_range": (52.0, 58.0),
        "inclination_tol_deg": 3.0,
        "sma_km": 42164.0,
        "sma_tol_km": 10.0,
        "ecc_max": 0.05
    },
    "BeiDou-3 I3": {
        "type": "IGSO",
        "central_longitude_deg": 118.0,
        "longitude_tol_deg": 5.0,
        "inclination_target_deg": 55.0,
        "inclination_target_deg_range": (52.0, 58.0),
        "inclination_tol_deg": 3.0,
        "sma_km": 42164.0,
        "sma_tol_km": 10.0,
        "ecc_max": 0.05
    },
    "BeiDou-3 G1": {
        "type": "GEO",
        # G1 (PRN 4) was originally stationed at 140°E. As part of a
        # coordinated slot swap with G4 (announced Apr 2026 by CSNO),
        # G1 now occupies the 160°E position — the constellation's
        # designated spare slot.
        "central_longitude_deg": 160.0,
        "longitude_tol_deg": 0.5,
        "inclination_target_deg": 0.0,
        "inclination_target_deg_range": (-3.0, 3.0),
        "inclination_tol_deg": 3.0,
        "sma_km": 42164.0,
        "sma_tol_km": 10.0,
        "ecc_max": 0.05
    },
    "BeiDou-3 G2": {
        "type": "GEO",
        "central_longitude_deg": 80.0,
        "longitude_tol_deg": 0.5,
        "inclination_target_deg": 0.0,
        "inclination_target_deg_range": (-3.0, 3.0),
        "inclination_tol_deg": 3.0,
        "sma_km": 42164.0,
        "sma_tol_km": 10.0,
        "ecc_max": 0.05
    },
    "BeiDou-3 G3": {
        "type": "GEO",
        "central_longitude_deg": 110.5,
        "longitude_tol_deg": 0.5,
        "inclination_target_deg": 0.0,
        "inclination_target_deg_range": (-3.0, 3.0),
        "inclination_tol_deg": 3.0,
        "sma_km": 42164.0,
        "sma_tol_km": 10.0,
        "ecc_max": 0.05
    },
    "BeiDou-3 G4": {
        # G4 was launched to 160°E as BeiDou-3's first backup (May 2023).
        # Per CSNO's Apr 2026 re-designation, G4 now occupies 140°E and
        # carries PRN 1, while 160°E is the constellation's spare slot.
        "type": "GEO",
        "central_longitude_deg": 140.0,
        "longitude_tol_deg": 0.5,
        "inclination_target_deg": 0.0,
        "inclination_target_deg_range": (-3.0, 3.0),
        "inclination_tol_deg": 3.0,
        "sma_km": 42164.0,
        "sma_tol_km": 10.0,
        "ecc_max": 0.05
    },
}

# BeiDou-3 maintenance note
BEIDOU3_MAINTENANCE_NOTE = "BeiDou-3 IGSO and GEO satellites provide regional coverage over Asia-Pacific."

# BeiDou-3 GEO slot swap notification
# CSNO announced (Apr 2026) that G4 (PRN 1) now occupies 140°E and
# G1 (PRN 4) occupies 160°E. The 160°E position is the spare slot.
BEIDOU3_SLOT_SWAP_NOTE = (
    "**BeiDou-3 GEO Slot Swap**\n\n"
    "G1 and G4 have exchanged positions per the China Satellite Navigation "
    "Office's (CSNO) April 2026 re-designation:\n\n"
    "• **G4** (PRN 1) now occupies **140°E** (prime slot)\n"
    "• **G1** (PRN 4) now occupies **160°E** (constellation spare slot)\n\n"
    "This was a coordinated swap — G4 departed 160°E first, maintaining "
    "continuous occupancy at 140°E, followed by G1's repositioning to "
    "160°E. The dashboard's longitude deviation scores reflect these "
    "new designations."
)

# Commissioning / active dates for satellites (use for analysis windows)
# Dates should be YYYY-MM-DD. Add entries for recently commissioned satellites.
COMMISSION_DATES = {
    "QZS-6 (Michibiki-6)": "2025-02-01",
    "NVS-01": "2023-12-18",
    "IRNSS-1I": "2021-01-29",
}

# Space-Track API configuration
LOGIN_URL = "https://www.space-track.org/ajaxauth/login"

# Inactive satellites (for DOP calculations)
# IRNSS-1B is operational, but IRNSS-1C, 1D, 1E, 1F, and 1G are messaging-only (no navigation services)
# (Navigation services for the 1G slot are now provided by NVS-1)
INACTIVE_SATELLITES = ["IRNSS-1C", "IRNSS-1D", "IRNSS-1E", "IRNSS-1F", "IRNSS-1G"]

# Default analysis parameters
DEFAULT_PARAMS = {
    "z_threshold": 3.5,
    "sma_threshold": 1.5,  # SMA Change (km) - updated for NavIC
    "inc_threshold": 0.1,  # Inclination Change (°) - updated for NavIC
    "persist_window": 2,
    "inclination_tolerance": 1.0,
    "drift_tolerance_gso": 0.05,
    "min_maneuvers_per_month": 1,
    "max_maneuvers_per_month": 8,
    "maneuver_uniformity_threshold": 0.8,
    "elevation_mask_deg": 5,
    "timestep_minutes": 15,
    "prop_duration_days": 1.5
}

# DOP quality thresholds based on Isik et al. (2020)
# Source: Isik, Oguz Kagan; Hong, Juhyeon; Petrunin, Ivan; Tsourdos, Antonios (25 August 2020).
# "Integrity Analysis for GPS-Based Navigation of UAVs in Urban Environment". 
# Robotics. 9 (3): 66. doi:10.3390/robotics9030066.

# DOP quality assessment thresholds
DOP_QUALITY_THRESHOLDS = {
    'GDOP': {
        'Ideal': (0, 1),
        'Excellent': (1, 2),
        'Good': (2, 5),
        'Moderate': (5, 10),
        'Fair': (10, 20),
        'Poor': (20, float('inf'))
    },
    'PDOP': {
        'Ideal': (0, 1),
        'Excellent': (1, 2),
        'Good': (2, 5),
        'Moderate': (5, 10),
        'Fair': (10, 20),
        'Poor': (20, float('inf'))
    },
    'HDOP': {
        'Ideal': (0, 1),
        'Excellent': (1, 2),
        'Good': (2, 5),
        'Moderate': (5, 10),
        'Fair': (10, 20),
        'Poor': (20, float('inf'))
    },
    'VDOP': {
        'Ideal': (0, 2),
        'Excellent': (2, 3),
        'Good': (3, 5),
        'Moderate': (5, 10),
        'Fair': (10, 15),
        'Poor': (15, float('inf'))
    }
}

# For backward compatibility with existing code
DOP_QUALITY_LEVELS = {
    'Ideal': 1,
    'Excellent': 2,
    'Good': 4,
    'Moderate': 6,
    'Fair': 8,
    'Poor': float('inf')
}
