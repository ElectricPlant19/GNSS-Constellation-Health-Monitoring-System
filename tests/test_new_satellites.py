"""Offline regressions for six-digit GP IDs and the new NavIC/QZSS members."""

import json
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
import requests
from skyfield.api import load
from sgp4.exporter import export_omm

from api import celestrak_api, spacetrack_api
from api.orbital_data import latest_gp_records, satellite_from_record
from analysis.dop_calculations import parse_tle_data
from analysis.health_assessment import assess_satellite_health_with_drift, longitude_deviation_score
from config.config import NAVIK_SATS, QZSS_SATS, QZSS_SERVICE_REQUIREMENTS, BEIDOU3_SATS
from data import tle_cache

ROOT = Path(__file__).resolve().parents[1]
QZS7 = 'QZS-7 (Michibiki-7)'


def bundle(system):
    return json.loads((ROOT / 'data' / f'{system}_tles.json').read_text(encoding='utf-8'))


def gp_record(system, norad):
    return latest_gp_records(bundle(system)['tle_data'], [norad])[0]


@pytest.fixture(autouse=True)
def clear_api_caches():
    for func in (celestrak_api._fetch_gp, celestrak_api.fetch_tles_from_celestrak,
                 spacetrack_api.fetch_multiple_tles):
        func.clear()
    yield
    for func in (celestrak_api._fetch_gp, celestrak_api.fetch_tles_from_celestrak,
                 spacetrack_api.fetch_multiple_tles):
        func.clear()


@pytest.mark.parametrize('system,sats,name,norad', [
    ('navic', NAVIK_SATS, 'NVS-03', 101228),
    ('qzss', QZSS_SATS, QZS7, 100270),
])
def test_bundled_gp_propagates_six_digit_satellites(system, sats, name, norad):
    satellites = parse_tle_data(bundle(system)['tle_data'], sats)
    sat = satellites[name]
    assert sat.model.satnum == norad
    position = sat.at(sat.epoch).position.km
    assert np.isfinite(position).all()
    assert 40000 < np.linalg.norm(position) < 45000


def test_legacy_bundle_and_equivalent_omm_propagate_identically():
    satellites = parse_tle_data(bundle('beidou3')['tle_data'], BEIDOU3_SATS)
    assert len(satellites) == 7
    old = next(iter(satellites.values()))
    fields = export_omm(old.model, old.name)
    new = satellite_from_record(fields, old.name, load.timescale())
    np.testing.assert_allclose(new.at(old.epoch).position.km,
                               old.at(old.epoch).position.km, atol=0.01)


def test_latest_records_filter_and_keep_newest_epoch():
    newer = gp_record('qzss', 100270)
    older = deepcopy(newer)
    older['EPOCH'] = '2026-08-22T00:00:00.000000'
    assert latest_gp_records([newer, older, {'error': 'missing'}], [100270]) == [newer]


def test_celestrak_queries_missing_id_in_partial_group(monkeypatch):
    existing = gp_record('qzss', 62876)
    new = gp_record('qzss', 100270)
    group, single = Mock(), Mock()
    group.json.return_value, single.json.return_value = [existing], [new]
    get = Mock(side_effect=[group, single])
    monkeypatch.setattr(celestrak_api.requests, 'get', get)
    result = latest_gp_records(celestrak_api.fetch_tles_from_celestrak([62876, 100270]))
    assert {int(r['NORAD_CAT_ID']) for r in result} == {62876, 100270}
    urls = [c.args[0] for c in get.call_args_list]
    assert 'GROUP=gnss&FORMAT=JSON' in urls[0]
    assert 'CATNR=100270&FORMAT=JSON' in urls[1]
    celestrak_api.fetch_tles_from_celestrak([100270])
    assert get.call_count == 2  # Endpoint cache shared between constellation requests.


def test_celestrak_stops_after_http_error(monkeypatch):
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError('403')
    get = Mock(return_value=response)
    monkeypatch.setattr(celestrak_api.requests, 'get', get)
    assert celestrak_api.fetch_tles_from_celestrak([101228, 100270]) == ''
    assert get.call_count == 1


def test_partial_provider_fallback_preserves_successful_records(monkeypatch):
    nvs, qzs = gp_record('navic', 101228), gp_record('qzss', 100270)
    monkeypatch.setattr(celestrak_api, 'fetch_tles_from_celestrak', Mock(return_value=json.dumps([nvs])))
    fallback = Mock(return_value=json.dumps([qzs]))
    monkeypatch.setattr(spacetrack_api, 'fetch_multiple_tles', fallback)
    payload, source = celestrak_api.fetch_tles_with_fallback([101228, 100270], 'test', 'test')
    assert len(latest_gp_records(payload)) == 2
    assert source == 'celestrak + spacetrack'
    fallback.assert_called_once_with([100270], 'test', 'test')


def test_spacetrack_fetches_json_with_full_ids(monkeypatch):
    response, session = Mock(), Mock()
    response.json.return_value = [gp_record('qzss', 100270)]
    session.get.return_value = response
    monkeypatch.setattr(spacetrack_api, 'get_spacetrack_session', Mock(return_value=session))
    result = spacetrack_api.fetch_multiple_tles([100270], 'test', 'test')
    assert latest_gp_records(result)[0]['NORAD_CAT_ID'] == 100270
    url = session.get.call_args.args[0]
    assert 'NORAD_CAT_ID/100270/' in url and url.endswith('/format/json')


def test_bundle_metadata_only_counts_received_objects(tmp_path, monkeypatch):
    monkeypatch.setattr(tle_cache, 'DATA_DIR', tmp_path)
    payload = json.dumps([gp_record('qzss', 100270)])
    assert tle_cache.save_tles_to_bundle('qzss', payload, QZSS_SATS)
    saved = tle_cache.load_bundled_tles('qzss')
    assert saved['format'] == 'GP_JSON'
    assert saved['satellites'] == {QZS7: 100270}


def test_qgeo_classification_inclination_and_dateline_slot_scoring():
    df = pd.DataFrame({'EPOCH': pd.to_datetime(['2026-11-04', '2026-11-05']),
                       'INCLINATION': [2.86, 2.86]})
    maneuvers = pd.DataFrame(columns=['EPOCH', 'EW_MANEUVER', 'NS_MANEUVER'])
    result = assess_satellite_health_with_drift(
        QZS7, df, maneuvers, 1.0, 1, 8, 0.8,
        service_requirements=QZSS_SERVICE_REQUIREMENTS, constellation_name='QZSS')
    assert result['Type'] == 'QGEO'
    assert result['_inc_score'] == 100
    assert result['Target Incl. (°)'] == 5.0
    assert result['Designated Lon (°)'] == -175.5
    req = QZSS_SERVICE_REQUIREMENTS[QZS7]
    assert longitude_deviation_score(184.5 - (-175.5), 'QGEO', req) == 100
    assert longitude_deviation_score(177.5 - (-175.5), 'QGEO', req) == 100
    assert longitude_deviation_score(190.5 - (-175.5), 'QGEO', req) == 100
    assert longitude_deviation_score(6.0, 'QGEO', req) == 100
    assert longitude_deviation_score(6.1, 'QGEO', req) < 100
    assert longitude_deviation_score(-7.1, 'QGEO', req) < 100


def test_historical_longitude_works_without_tle_lines(monkeypatch):
    from visualizations import visualization as vis
    record = gp_record('qzss', 100270)
    record['satellite'] = QZS7
    df = pd.DataFrame([record])
    df['EPOCH'] = pd.to_datetime(df['EPOCH'])
    render = Mock()
    for method in ('markdown', 'caption', 'dataframe'):
        monkeypatch.setattr(vis.st, method, Mock())
    monkeypatch.setattr(vis.st, 'spinner', lambda *a, **kw: nullcontext())
    monkeypatch.setattr(vis.st, 'expander', lambda *a, **kw: nullcontext())
    monkeypatch.setattr(vis.st, 'plotly_chart', render)
    vis.plot_historical_central_longitude(df, 'QZSS')
    assert render.call_count == 1
    traces = render.call_args.args[0].data
    assert traces[0].name == QZS7
    assert np.isfinite(traces[0].y[0])
