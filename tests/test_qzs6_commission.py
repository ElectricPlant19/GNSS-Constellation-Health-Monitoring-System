import pandas as pd
import health_assessment as ha

# Simulate sat_df spanning Jan to Oct 2025
dates = pd.to_datetime(['2025-01-05','2025-02-10','2025-03-15','2025-06-01','2025-09-01','2025-10-01'])
sat_df = pd.DataFrame({'EPOCH': dates, 'INCLINATION':[0.1,0.1,0.1,0.2,0.2,0.2]})
# Maneuvers: one in Jan (pre-commission), one in Mar (post-commission), one in Sep
man_dates = pd.to_datetime(['2025-01-20','2025-03-10','2025-09-05'])
maneuvers = pd.DataFrame({'EPOCH':man_dates,'EW_MANEUVER':[True,True,True],'NS_MANEUVER':[False,False,False]})
# Use pattern_maneuvers==maneuvers and pattern_df==sat_df
res = ha.assess_satellite_health_with_drift('QZS-6 (Michibiki-6)', sat_df, maneuvers, inc_tolerance=1.0, min_man_per_month=0.1, max_man_per_month=8, uniformity_threshold=0.8, pattern_maneuvers=maneuvers, pattern_df=sat_df)
print('Pattern Analysis Period:', res.get('Pattern Analysis Period'))
print('EW Expected Interval (days):', res.get('EW Expected Interval (days)'))
print('EW Days Since Last:', res.get('EW Days Since Last'))
print('Overall Score:', res.get('Overall Score'))
print('Remarks:', res.get('Remarks'))
