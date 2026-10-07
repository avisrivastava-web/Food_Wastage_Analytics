import pandas as pd
from analytics import (
    build_daily_dataset, dish_risk_analysis, data_maturity_score,
    cover_relationship, weekday_benchmark, control_chart_data,
    meal_complexity_summary, menu_signature_analysis, menu_novelty_analysis,
    waste_stability_summary, pareto_dish_excess, scenario_waste_estimate,
)

menu = pd.read_csv('data/test_menu_full_year_2025.csv')
waste = pd.read_csv('data/test_wastage_full_year_2025.csv')
waste['service_date'] = pd.to_datetime(waste['service_date'])
waste['kg_per_cover'] = waste['total_wastage_kg'] / waste['covers_served']

daily = build_daily_dataset(menu, waste)
risk, meta = dish_risk_analysis(menu, waste)

assert len(daily) == 365
assert not risk.empty
assert data_maturity_score(menu, waste)['score'] >= 80
cover_df, cover_meta = cover_relationship(waste)
assert len(cover_df) == 365 and 'excess_vs_attendance_kg' in cover_df.columns
assert len(weekday_benchmark(daily)) == 365
control_df, control_meta = control_chart_data(daily)
assert len(control_df) == 365 and 'control_upper' in control_df.columns
assert len(meal_complexity_summary(menu, waste)) == 4
assert not menu_signature_analysis(menu, waste, 2).empty
novelty, novelty_corr = menu_novelty_analysis(menu, waste)
assert len(novelty) == 365
assert waste_stability_summary(daily)['mean'] > 0
assert not pareto_dish_excess(risk).empty
scenario = scenario_waste_estimate(['Lauki Kofta', 'Soya Chunk Curry'], 250, risk, waste)
assert scenario['estimated_waste_kg'] > scenario['baseline_kg']
print('Advanced analytics self-test passed')
