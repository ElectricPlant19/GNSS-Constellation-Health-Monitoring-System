"""
RAAN Spacing Analysis for co-located IGSO / QZO satellites.

When multiple IGSO satellites share the same ground-track central longitude,
they are designed to sit on equally spaced RAAN values (3 sats -> 120 deg,
2 sats -> 180 deg apart). Deviation from equal RAAN spacing degrades geometric
diversity and causes worse DOP at users on the ground.

The ground-track central longitude is derived from the TLE itself by taking
the circular mean of the sub-satellite longitude over one sidereal day. For a
GEO satellite this is essentially its station-keeping longitude; for an IGSO
it is the centre of the figure-8 ground track. Using the TLE-derived value
rather than a static configured slot lets the grouping logic cope with:

    * config files that list slightly different target longitudes for
      satellites that are in fact flying through the same ground track
      (e.g. QZS-1R listed as 148 deg but actually parked at ~136 deg,
      next to QZS-2 and QZS-4);
    * chains of satellites where consecutive configured values differ by
      more than ``longitude_match_tol_deg`` (e.g. 117, 118, 119 deg) but
      which are obviously co-located.

Clustering is single-linkage on the circular longitude axis: two satellites
end up in the same cluster whenever consecutive sorted longitudes differ by
at most ``longitude_match_tol_deg``, with chaining and 0 deg/360 deg wrap
handled correctly.

IGSO classification is driven by TLE inclination (>= ``inclination_threshold``
deg) rather than a config ``type`` field, so the analysis does not silently
skip satellites whose config lacks a type annotation.
"""

import math
from datetime import datetime, timedelta, timezone

import numpy as np
from skyfield.api import load

IGSO_INCLINATION_THRESHOLD_DEG = 20.0
SIDEREAL_DAY_HOURS = 23.9344696
DEFAULT_LONGITUDE_TOL_DEG = 5.0

_TS = None


def _get_timescale():
    """Return a cached Skyfield timescale (leap-second file loaded once)."""
    global _TS
    if _TS is None:
        _TS = load.timescale()
    return _TS


def _inclination_deg(sat_obj):
    try:
        return math.degrees(sat_obj.model.inclo)
    except Exception:
        return None


def get_raan_deg(sat_obj):
    """RAAN (degrees, 0-360) from a Skyfield EarthSatellite."""
    try:
        return math.degrees(sat_obj.model.nodeo) % 360.0
    except Exception:
        return None


def _circular_mean_deg(lons_deg):
    """Circular mean of longitudes (deg) in [0, 360)."""
    rad = np.deg2rad(np.asarray(lons_deg) % 360.0)
    mean = math.atan2(float(np.mean(np.sin(rad))), float(np.mean(np.cos(rad))))
    return math.degrees(mean) % 360.0


def get_ground_track_central_longitude_deg(sat_obj, ts=None,
                                           duration_hours=SIDEREAL_DAY_HOURS,
                                           samples=96):
    """
    Circular mean of sub-satellite longitude over one sidereal day.

    For a GEO satellite this effectively returns the station-keeping
    longitude; for an IGSO it returns the centre of the figure-8 ground
    track. Returns degrees in [0, 360) or None on error.
    """
    try:
        ts = ts or _get_timescale()
        t0 = datetime.now(timezone.utc)
        times = [t0 + timedelta(hours=duration_hours * i / samples)
                 for i in range(samples)]
        t_sf = ts.utc(
            [t.year for t in times],
            [t.month for t in times],
            [t.day for t in times],
            [t.hour for t in times],
            [t.minute for t in times],
            [t.second + t.microsecond * 1e-6 for t in times],
        )
        lons = np.asarray(sat_obj.at(t_sf).subpoint().longitude.degrees)
        return _circular_mean_deg(lons)
    except Exception:
        return None


def _cluster_by_longitude(items, tol_deg):
    """
    Single-linkage clustering on the circular longitude axis.

    Two items join the same cluster whenever the gap between consecutive
    sorted longitudes is at most ``tol_deg``. Wrap-around across 0 deg/360
    deg is handled by checking whether the first and last clusters can be
    merged via the shortest arc.
    """
    if not items:
        return []

    sorted_items = sorted(items, key=lambda x: x["central_lon"])
    clusters = [[sorted_items[0]]]
    for it in sorted_items[1:]:
        if it["central_lon"] - clusters[-1][-1]["central_lon"] <= tol_deg:
            clusters[-1].append(it)
        else:
            clusters.append([it])

    if len(clusters) >= 2:
        wrap_gap = (sorted_items[0]["central_lon"] + 360.0
                    - clusters[-1][-1]["central_lon"])
        if wrap_gap <= tol_deg:
            clusters[0] = clusters[-1] + clusters[0]
            clusters.pop()

    return clusters


def _classify_status(max_dev_deg, ideal_spacing_deg):
    if ideal_spacing_deg <= 0:
        return "N/A"
    pct = abs(max_dev_deg) / ideal_spacing_deg * 100.0
    if pct < 5:
        return "Ideal"
    if pct < 15:
        return "Good"
    if pct < 30:
        return "Moderate"
    return "Poor"


def analyze_raan_spacing(satellites_dict, service_requirements=None,
                         longitude_match_tol_deg=DEFAULT_LONGITUDE_TOL_DEG,
                         inclination_threshold_deg=IGSO_INCLINATION_THRESHOLD_DEG,
                         ts=None):
    """
    Group IGSO satellites by TLE-derived ground-track central longitude and
    analyze RAAN spacing for every group of two or more.

    Args:
        satellites_dict: dict mapping satellite name -> Skyfield
            EarthSatellite (as produced by
            ``analysis.dop_calculations.parse_tle_data``).
        service_requirements: optional dict mapping satellite name -> config
            requirements. Kept for API compatibility; not required for the
            calculation (IGSO membership and central longitude both come
            from the TLE).
        longitude_match_tol_deg: maximum gap (deg) between consecutive
            sorted central longitudes for two satellites to land in the
            same cluster. Applied transitively (single-linkage) so a chain
            like 117, 118, 119 groups into one cluster when the tolerance
            is 1 deg or more.
        inclination_threshold_deg: TLE inclination above which a satellite
            is treated as IGSO. Below this threshold it is considered GEO
            and excluded from the spacing analysis.
        ts: optional Skyfield timescale (primarily for tests).

    Returns:
        List of group dicts with keys:
            central_longitude_deg, satellite_count, ideal_spacing_deg,
            max_deviation_deg, rms_deviation_deg, status,
            satellites: [{name, raan_deg, central_longitude_deg,
                          next_neighbor, gap_to_next_deg,
                          deviation_from_ideal_deg}]
        Groups with fewer than two satellites are dropped. Results are
        sorted ascending by cluster central longitude.
    """
    if not satellites_dict:
        return []

    ts = ts or _get_timescale()

    items = []
    for name, sat_obj in satellites_dict.items():
        inc = _inclination_deg(sat_obj)
        if inc is None or inc < inclination_threshold_deg:
            continue
        raan = get_raan_deg(sat_obj)
        lon = get_ground_track_central_longitude_deg(sat_obj, ts=ts)
        if raan is None or lon is None:
            continue
        items.append({
            "name": name,
            "central_lon": lon,
            "raan": raan,
            "inclination": inc,
        })

    clusters = _cluster_by_longitude(items, longitude_match_tol_deg)

    results = []
    for cluster in clusters:
        n = len(cluster)
        if n < 2:
            continue

        ideal = 360.0 / n
        sorted_cluster = sorted(cluster, key=lambda x: x["raan"])
        raans = [c["raan"] for c in sorted_cluster]

        gaps = []
        for k in range(n):
            nxt = raans[(k + 1) % n]
            gap = (nxt - raans[k]) % 360.0
            if gap == 0.0:
                gap = 360.0
            gaps.append(gap)

        sats_out = []
        for k, c in enumerate(sorted_cluster):
            gap_to_next = gaps[k]
            dev = gap_to_next - ideal
            next_name = sorted_cluster[(k + 1) % n]["name"]
            sats_out.append({
                "name": c["name"],
                "raan_deg": round(c["raan"], 2),
                "central_longitude_deg": round(c["central_lon"], 2),
                "next_neighbor": next_name,
                "gap_to_next_deg": round(gap_to_next, 2),
                "deviation_from_ideal_deg": round(dev, 2),
            })

        devs = np.asarray([g - ideal for g in gaps])
        max_dev = float(np.max(np.abs(devs)))
        rms_dev = float(np.sqrt(np.mean(devs ** 2)))

        cluster_lon = _circular_mean_deg([c["central_lon"] for c in cluster])

        results.append({
            "central_longitude_deg": round(cluster_lon, 2),
            "satellite_count": n,
            "ideal_spacing_deg": round(ideal, 2),
            "satellites": sats_out,
            "max_deviation_deg": round(max_dev, 2),
            "rms_deviation_deg": round(rms_dev, 2),
            "status": _classify_status(max_dev, ideal),
        })

    results.sort(key=lambda g: g["central_longitude_deg"])
    return results
