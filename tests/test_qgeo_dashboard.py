"""Verify QZS-7's displayed health includes all five existing components."""

from datetime import date

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


def test_dashboard_keeps_maneuvers_in_qgeo_weighted_health():
    app = AppTest.from_file('app.py', default_timeout=180).run()
    app.selectbox[0].set_value('QZSS').run()
    app.date_input[0].set_value(date(2026, 8, 22))
    app.date_input[1].set_value(date(2026, 11, 6))
    app.button[0].click().run()
    assert not app.exception, [e.message for e in app.exception]
    assert not app.error, [e.value for e in app.error]
    health = app.session_state['health_df']
    row = health.loc[health['Satellite'] == 'QZS-7 (Michibiki-7)'].iloc[0]
    weights = {
        '_inc_score': 0.30, '_maintenance_score': 0.25,
        '_drift_score': 0.20, 'Lon Deviation Score': 0.15,
        '_uniformity_score': 0.10,
    }
    assert all(pd.notna(row[key]) for key in weights)
    expected = sum(row[key] * weight for key, weight in weights.items())
    assert row['Overall Score'] == pytest.approx(expected, abs=0.051)
    assert row['Health Status'].split()[-1] in ('Healthy', 'Fair', 'Degraded', 'Critical')
    assert 'EW Maneuvers' in row and 'NS Maneuvers' in row
    assert any(m.label == 'Overall Health Score' for m in app.metric)
    assert not any(m.label == 'QGEO Range Compliance' for m in app.metric)
    references = [d.value for d in app.dataframe if 'Reference parameter' in d.value.columns]
    assert len(references) == 1
    assert references[0].loc[references[0]['Reference parameter'] == 'Eccentricity', 'Operational range'].iloc[0] == '0.007–0.009'
