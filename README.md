# WasteLens — Food Wastage Analytics

A complete Streamlit analytics application for entering menus and daily food wastage, tracking trends, detecting unusual waste, and identifying dishes repeatedly associated with high-wastage days.

## Main features

- Flexible date ranges; seven days is only the default.
- Quick viewing periods: Recent 1 Week, 1 Month, 3 Months, 6 Months, 1 Year, All Available Data and Custom Dates.
- Four meals per day: Breakfast, Lunch, Snacks and Dinner.
- Multiple dishes in each meal.
- Daily total wastage in kilograms.
- Optional covers served for kg-per-cover analysis.
- Persistent SQLite database.
- Polished Streamlit dashboard with responsive KPI cards and charts.
- Daily, 7-day and 14-day wastage trends.
- Week-over-week summaries.
- Weekday pattern analysis.
- IQR-based unusual/outlier day detection.
- High-wastage-day menu review.
- Weekday-specific expected-waste benchmarking.
- Attendance-adjusted waste and kg-per-cover efficiency.
- Covers-vs-waste correlation and attendance residual analysis.
- Process-control chart with ±2σ warning and ±3σ control limits.
- Menu complexity vs wastage correlation.
- Meal-specific menu-complexity analysis.
- 14-day menu novelty analysis.
- Dish risk ranking with repetition/confidence logic.
- Non-destructive dish exclusion filter: ignore any selected dish(es) in analytics without deleting stored/raw data.
- Dish × meal context analysis.
- Pareto analysis of positive excess-waste association.
- Repeating high-waste dish-pair analysis.
- Repeating meal-menu combination analysis.
- Association-based what-if scenario planner.
- Data maturity/reliability score.
- Optional blended ₹/kg financial-impact and target-savings estimate.
- Automated management insights and action suggestions.
- Data completeness checks.
- CSV import/export.
- Excel import using combined or separate workbooks.
- Included Excel templates for easy data entry.
- Automatic cloud/demo bootstrap: if both SQLite tables are empty, the bundled full-year 2025 test dataset is restored automatically on startup.

## Excel import options

Open **Excel Import** in the website. You can use any of these:

1. **Combined workbook** — Menu and Wastage sheets in one `.xlsx` file.
2. **Menu Excel only** — upload just a menu workbook.
3. **Wastage Excel only** — upload just the wastage workbook.

Three ready-made templates are included in `templates/` and are also downloadable from inside the website.

### Friendly menu Excel format

One row per date:

| Date | Breakfast | Lunch | Snacks | Dinner |
|---|---|---|---|---|
| 2026-10-07 | Poha, Banana | Rajma, Rice, Salad | Samosa | Dal, Roti |

Put multiple dishes in a cell separated by commas. The importer also accepts long format with `service_date, meal, dish`.

### Wastage Excel format

| Date | Total Wastage (kg) | Covers Served | Notes |
|---|---:|---:|---|
| 2026-10-07 | 18.5 | 240 | Event day |

Only Date and Total Wastage are required. Covers and Notes are optional.

## Windows: easiest way to run

1. Install Python 3.11 or newer from python.org and tick **Add Python to PATH**.
2. Extract this project folder.
3. Double-click `setup_and_run_windows.bat` the first time.
4. The script installs requirements and opens Streamlit.
5. For later runs, double-click `run_windows.bat`.

Normally the app opens at `http://localhost:8501`.

## Command-line start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud demo behavior

This build is ready for a free Streamlit Community Cloud demo with the full 2025 test year bundled in the repository. On startup, WasteLens checks the SQLite database. If **both** the menu table and wastage table are completely empty, it automatically imports `data/test_menu_full_year_2025.csv` and `data/test_wastage_full_year_2025.csv` before the dashboard is shown. This is useful after a fresh cloud deployment or a cloud restart where local SQLite storage has been recreated.

The safeguard is conservative: if either table already contains any records, automatic demo loading is skipped so synthetic records are never silently mixed into user data. An intentional **Reset database** also pauses automatic reload for the rest of that browser session, allowing you to start entering real data immediately. On a later cold restart with an empty database, the bundled demo year can restore itself again.

To disable this behavior permanently, set `AUTO_LOAD_TEST_DATA_IF_EMPTY = False` in `config.py`.

## Recommended workflow

1. Add menu and wastage through **Data Entry** or **Excel Import**.
2. Use **Overview** for management KPIs, trends and automatic insights.
3. Use the quick period selector on **Overview** or **Analytics Lab** to switch instantly between the most recent 1 week, 1 month, 3 months, 6 months, 1 year, all available data or a custom range. Recent periods end on the latest date in the loaded dataset.
4. Optionally use **Dish exclusions** in the sidebar to ignore one or more dishes for the current analysis without deleting them.
5. Use **Analytics Lab** for dish drivers, weekday benchmarks, attendance-adjusted efficiency, process control, menu structure, dish pairs and scenario planning.
6. Use **Data Reliability** inside Analytics Lab before making strong operational decisions.
7. Use **Data Manager** for data quality, filtered raw-data views, exports, deletion and reset.
8. Read `ANALYTICS_GUIDE.md` for a plain-English definition of every major metric.

## Dish exclusion filter

Use **🚫 Dish exclusions** in the sidebar when you want one or more dishes to be ignored in analytical calculations. This is useful for compulsory staples, known data-quality issues, test items, or when you want to see how rankings change without a particular dish.

Exclusion is **non-destructive**: the dish stays in the SQLite database, raw-data views and exports. It is removed from dish risk, dish×meal context, Pareto attribution, menu complexity, novelty, pairs, repeating meal menus and Scenario Planner dish choices. Daily total wastage is not reduced, because WasteLens stores one total wastage value per day rather than dish-level wastage kilograms. Clear the selection to restore the complete analysis.

## Interpretation of dish risk

The application receives one total waste number per day, so it cannot prove which exact dish was physically discarded. Instead, it ranks dishes that repeatedly coincide with high-waste days.

A dish's score considers:

- average waste when the dish is served,
- lift versus dates when it is absent,
- positive correlation with daily wastage,
- how many high-waste dates contain the dish,
- estimated share of excess waste above a median baseline,
- and the number of times the dish has appeared.

The result is an **association / prioritization signal, not causal proof**.

## Best data quality

For meaningful dish-level conclusions, aim for at least 4–8 weeks of repeated menu cycles. Enter covers served where possible so the system can separate high waste caused by higher attendance from menu-related effects.

## Project files

- `app.py` — complete Streamlit website.
- `analytics.py` — analytical calculations and scoring.
- `excel_io.py` — Excel normalization and import logic.
- `database.py` — SQLite persistence and imports.
- `utils.py` — helper functions.
- `config.py` — app constants and paths.
- `.streamlit/config.toml` — visual theme.
- `templates/` — Excel import templates.
- `data/sample_menu.csv` / `data/sample_wastage.csv` — sample data.
- `test_analytics.py` — analytics self-test.
- `test_excel_import.py` — Excel import self-test.
- `test_auto_demo_bootstrap.py` — verifies empty/partial database detection for automatic cloud demo restore.
- `ANALYTICS_GUIDE.md` — plain-English analytics definitions and recommended operating workflow.

## Included full-year 2025 analytics test dataset

The project includes a synthetic **365-day / full-calendar-year test dataset** covering 01-Jan-2025 through 31-Dec-2025, with all four meals every day. It is designed to exercise long-range analytics, seasonality, attendance adjustment, anomaly detection, process-control views and dish-risk analysis rather than merely populate the database.

Files in `test_dataset/`:

- `Food_Wastage_Test_Dataset_Full_Year_2025.xlsx` — combined workbook with Test Guide, Menu and Wastage sheets.
- `Menu_Test_Dataset_Full_Year_2025.xlsx` — menu-only test workbook.
- `Wastage_Test_Dataset_Full_Year_2025.xlsx` — wastage-only test workbook.

The same records are available as `data/test_menu_full_year_2025.csv` and `data/test_wastage_full_year_2025.csv`. The dataset is integrated directly into the software: use the **Built-in test dataset** shortcut in the sidebar or click **Load full-year 2025 analytics test dataset** in **Data Manager**. No file upload is needed. Data Manager also offers a clean-load option that clears existing records first.

After loading the test year, the quick period selector gives predictable ranges anchored to 31-Dec-2025: **Recent 1 Week = 25–31 Dec**, **Recent 1 Month = 01–31 Dec**, **Recent 3 Months = 01 Oct–31 Dec**, **Recent 6 Months = 01 Jul–31 Dec**, and **Recent 1 Year = 01 Jan–31 Dec 2025**.

The full-year dataset deliberately includes repeated positive waste associations for **Lauki Kofta, Soya Chunk Curry, Bread Pakora and Aloo Paratha**, lower-waste control patterns, monthly/seasonal shifts, attendance changes, festival/event days and operational anomalies. Because only total daily waste is recorded, companion side dishes may also inherit statistical association; this is intentional so the software demonstrates the difference between association and causal proof.

