"""Shared GP/OMM handling, including catalog numbers beyond the TLE limit."""

import json
from datetime import datetime, timezone

ORBIT_FIELDS = (
    'EPOCH', 'MEAN_MOTION', 'ECCENTRICITY', 'INCLINATION',
    'RA_OF_ASC_NODE', 'ARG_OF_PERICENTER', 'MEAN_ANOMALY',
)


def latest_gp_records(payload, norad_ids=None):
    """Filter and deduplicate GP JSON, retaining the newest epoch for each ID."""
    records = json.loads(payload) if isinstance(payload, str) else payload
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        raise ValueError('Expected a GP JSON array or record')
    wanted = None if norad_ids is None else {int(n) for n in norad_ids}
    latest = {}
    for record in records:
        try:
            norad = int(record['NORAD_CAT_ID'])
            if wanted is not None and norad not in wanted:
                continue
            if any(record.get(field) in (None, '') for field in ORBIT_FIELDS):
                continue
            epoch = datetime.fromisoformat(record['EPOCH'].replace('Z', '+00:00'))
            epoch = epoch.replace(tzinfo=timezone.utc) if epoch.tzinfo is None else epoch
            if norad not in latest or epoch > latest[norad][0]:
                latest[norad] = (epoch, dict(record))
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    return [record for _, record in latest.values()]


def satellite_from_record(record, name, ts):
    """Build a Skyfield satellite from a GP record or legacy history TLE lines."""
    from skyfield.api import EarthSatellite

    line1, line2 = record.get('TLE_LINE1'), record.get('TLE_LINE2')
    if isinstance(line1, str) and line1.startswith('1 ') and isinstance(line2, str) and line2.startswith('2 '):
        return EarthSatellite(line1, line2, name, ts)

    # Fail on absent orbital elements instead of manufacturing a trajectory.
    for field in (*ORBIT_FIELDS, 'NORAD_CAT_ID'):
        value = record.get(field)
        if value is None or value == '' or value != value:
            raise ValueError(f'Missing GP field: {field}')
    fields = dict(record)
    epoch = datetime.fromisoformat(str(fields['EPOCH']).replace('Z', '+00:00'))
    if epoch.tzinfo is not None:
        epoch = epoch.astimezone(timezone.utc).replace(tzinfo=None)
    fields['EPOCH'] = epoch.isoformat(timespec='microseconds')
    fields['OBJECT_NAME'] = name
    defaults = {
        'OBJECT_ID': '', 'CLASSIFICATION_TYPE': 'U', 'EPHEMERIS_TYPE': 0,
        'ELEMENT_SET_NO': 0, 'REV_AT_EPOCH': 0, 'BSTAR': 0.0,
        'MEAN_MOTION_DOT': 0.0, 'MEAN_MOTION_DDOT': 0.0,
    }
    for key, default in defaults.items():
        value = fields.get(key)
        if value is None or value == '' or value != value:
            fields[key] = default
    return EarthSatellite.from_omm(ts, fields)
