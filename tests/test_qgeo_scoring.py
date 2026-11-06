"""QGEO design references must preserve the existing weighted health model."""

import pandas as pd
import pytest

from analysis.health_assessment import assess_satellite_health_with_drift, longitude_deviation_score
from config.config import QZSS_SERVICE_REQUIREMENTS

NAME = 'QZS-7 (Michibiki-7)'
REQ = QZSS_SERVICE_REQUIREMENTS[NAME]


def history(inclination=2.86, drift=0.0):
    return pd.DataFrame({
        'EPOCH': pd.to_datetime(['2026-10-01', '2026-11-01']),
        'INCLINATION': inclination, 'LonDrift_deg_per_day': drift,
        'ECCENTRICITY': 0.008, 'SEMIMAJOR_AXIS': 42165.0,
        'ARG_OF_PERICENTER': 0.0, 'RA_OF_ASC_NODE': 50.0,
    })


def maneuvers():
    return pd.DataFrame({
        'EPOCH': pd.date_range('2026-10-01', periods=5, freq='7D'),
        'EW_MANEUVER': True, 'NS_MANEUVER': True,
    })


def assess(df, events=None, **kwargs):
    if events is None:
        events = maneuvers().iloc[:0]
    return assess_satellite_health_with_drift(
        NAME, df, events, 1.0, 1, 8, 0.8,
        service_requirements=QZSS_SERVICE_REQUIREMENTS,
        constellation_name='QZSS', **kwargs)


@pytest.mark.parametrize('inclination,score', [
    (1.0, 100), (2.86, 100), (5.0, 100), (8.0, 100),
    (0.75, 50), (8.25, 50),
])
def test_inclination_uses_operational_range_and_existing_penalty(inclination, score):
    result = assess(history(inclination))
    assert result['Type'] == 'QGEO'
    assert result['Target Incl. (°)'] == 5.0
    assert result['_inc_score'] == score


def test_existing_inclination_stability_penalty_is_retained():
    assert assess(history([1.0, 8.0]))['_inc_score'] == 80


@pytest.mark.parametrize('longitude,score', [
    (177.5, 100), (184.5, 100), (190.5, 100), (-175.5, 100),
    (-182.5, 100), (544.5, 100),
    (174.25, 50), (193.75, 50), (171.0, 0), (197.0, 0),
])
def test_longitude_retains_gradual_scoring_around_qgeo_range(longitude, score):
    assert longitude_deviation_score(longitude - REQ['central_longitude_deg'], 'QGEO', REQ) == pytest.approx(score)


def test_maneuver_maintenance_still_changes_score_with_original_weight():
    df, events = history(), maneuvers()
    # Keep inclination, drift, longitude availability, and uniformity identical.
    # Only the historical maintenance pattern differs.
    maintained = assess(df, events, pattern_maneuvers=events, pattern_df=df)
    no_pattern = assess(df, events, pattern_maneuvers=events.iloc[:0], pattern_df=df)
    assert maintained['_maintenance_score'] == 100
    assert no_pattern['_maintenance_score'] == 0
    for key in ('_inc_score', '_uniformity_score', '_drift_score'):
        assert maintained[key] == no_pattern[key] == 100
    # The analysis module normalizes over 0.85 until the app adds longitude.
    assert maintained['_score_total_weight'] == no_pattern['_score_total_weight'] == 0.85
    assert maintained['Overall Score'] == 100
    assert no_pattern['Overall Score'] == round((30 + 10 + 20) / 0.85, 1)


def test_no_maneuvers_still_reduces_maintenance_and_uniformity_scores():
    result = assess(history())
    assert result['_maintenance_score'] == result['_uniformity_score'] == 0
    assert result['Overall Score'] == round((30 + 20) / 0.85, 1)
    assert 'Degraded' in result['Health Status']


@pytest.mark.parametrize('drift,score', [(0, 100), (3, 70), (5, 40)])
def test_drift_remains_a_scored_component(drift, score):
    assert assess(history(drift=drift))['_drift_score'] == score


def test_reference_only_parameters_do_not_add_new_score_components():
    original = assess(history(), maneuvers())
    changed = assess(history().assign(
        ECCENTRICITY=0.006, SEMIMAJOR_AXIS=42500,
        ARG_OF_PERICENTER=90, RA_OF_ASC_NODE=300), maneuvers())
    assert changed['Overall Score'] == original['Overall Score']
    assert REQ['ecc_nominal'] == 0.008
    assert (REQ['ecc_min'], REQ['ecc_max']) == (0.007, 0.009)
    assert REQ['sma_km'] == 42165
    assert REQ['arg_perigee_deg'] == 0
    assert REQ['raan_reference_deg'] == 50
    assert REQ['raan_reference_epoch'] == '2031-10'


def test_other_satellites_keep_the_existing_weighted_health_model():
    result = assess_satellite_health_with_drift(
        'QZS-6 (Michibiki-6)', history(0.1), maneuvers().iloc[:0], 1.0, 1, 8, 0.8,
        service_requirements=QZSS_SERVICE_REQUIREMENTS, constellation_name='QZSS')
    assert result['Type'] == 'GEO'
    assert result['Overall Score'] == 55.3
