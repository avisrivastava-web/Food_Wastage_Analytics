import pandas as pd
from analytics import dish_risk_analysis

menu = pd.DataFrame({
    "service_date": pd.to_datetime(["2026-01-01","2026-01-01","2026-01-02","2026-01-02","2026-01-03","2026-01-03","2026-01-04","2026-01-04"]),
    "meal": ["Lunch","Dinner"]*4,
    "dish": ["Risky","Rice","Safe","Rice","Risky","Rice","Safe","Rice"],
})
waste = pd.DataFrame({
    "service_date": pd.to_datetime(["2026-01-01","2026-01-02","2026-01-03","2026-01-04"]),
    "total_wastage_kg": [30,10,28,12],
    "covers_served": [100,100,100,100],
})
waste["kg_per_cover"] = waste["total_wastage_kg"] / waste["covers_served"]
risk, meta = dish_risk_analysis(menu, waste, 0.75, 2, 50)
assert risk.iloc[0]["dish"] == "Risky"
assert risk.iloc[0]["lift_vs_without"] > 0
print("Analytics self-test passed")
