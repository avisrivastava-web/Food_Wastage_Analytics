import io
import pandas as pd

from excel_io import normalize_menu_excel, normalize_wastage_excel

menu_wide = pd.DataFrame({
    "Date": ["2026-10-01", "2026-10-02"],
    "Breakfast": ["Poha, Banana", "Idli, Sambar"],
    "Lunch": ["Rajma, Rice", "Chole, Rice"],
    "Snacks": ["Samosa", "Sandwich"],
    "Dinner": ["Dal, Roti", "Paneer, Roti"],
})
menu = normalize_menu_excel(menu_wide)
assert len(menu) == 14
assert set(menu.columns) == {"service_date", "meal", "dish"}

waste_raw = pd.DataFrame({
    "Date": ["2026-10-01", "2026-10-02"],
    "Total Wastage (kg)": [22.5, 15.0],
    "Covers Served": [220, 215],
    "Notes": ["", ""],
})
waste = normalize_wastage_excel(waste_raw)
assert len(waste) == 2
assert waste["total_wastage_kg"].sum() == 37.5
print("Excel import self-test passed")
