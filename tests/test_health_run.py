import pandas as pd
import health_assessment as ha

# create sat_df with EPOCH and INCLINATION
dates = [pd.Timestamp('2025-11-01'), pd.Timestamp('2025-12-01')]
sat_df = pd.DataFrame({'EPOCH': pd.to_datetime(dates),'INCLINATION':[0.0,0.1]})
# maneuvers events
man_dates = [pd.Timestamp('2025-11-10'), pd.Timestamp('2025-12-10')]
maneuvers = pd.DataFrame({'EPOCH':pd.to_datetime(man_dates),'EW_MANEUVER':[True,True],'NS_MANEUVER':[False,False]})
pattern = maneuvers.copy()
pattern_df = sat_df.copy()
res = ha.assess_satellite_health_with_drift('QZS-6', sat_df, maneuvers, inc_tolerance=1.0, min_man_per_month=1, max_man_per_month=8, uniformity_threshold=0.8, pattern_maneuvers=pattern, pattern_df=pattern_df)
print('OK', res.get('Overall Score'))
print('Remarks:', res.get('Remarks'))
