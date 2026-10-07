# V3.4 — Automatic Cloud Demo Bootstrap

- On application startup, if **both** SQLite core tables are completely empty, the bundled 365-day 2025 test dataset is automatically restored before analytics are rendered.
- Designed for Streamlit Community Cloud/free-demo restarts where local SQLite storage may be recreated.
- Partial databases are treated as non-empty, preventing synthetic test records from being silently merged into user data.
- Intentional delete/reset operations set a session guard so a deliberate empty database is not immediately repopulated during the same browser session.
- Manual built-in test-data loading clears the session guard.
- Added `AUTO_LOAD_TEST_DATA_IF_EMPTY` in `config.py` for a one-line permanent on/off switch.
- Added `database_record_counts()` and `database_is_completely_empty()` helpers plus `test_auto_demo_bootstrap.py`.

---

# V3.3 — Dish Exclusion Filter

- Added a global **Dish exclusions** sidebar control.
- Supports excluding one or many dishes without deleting or editing stored data.
- Exclusions propagate through all menu-based analytics: dish risk, dish×meal context, Pareto, complexity, novelty, pairs, repeating meal menus, menu text and scenario planning.
- Daily total-waste KPIs remain unchanged because wastage is recorded at daily level, not per dish.
- Added an on-page banner when exclusions are active, a one-click clear button, methodology documentation and `test_dish_exclusions.py`.

---

# WasteLens V3 Upgrade

## Dashboard clarity
- Added plain-English explanations before every major analytics section.
- Added operational-use notes after important charts.
- Expanded metric labels and help text so units and interpretations are explicit.
- Added a complete in-project `ANALYTICS_GUIDE.md`.

## New analytics
- Data maturity/readiness score (0–100).
- Weekday-specific expected-waste benchmark and variance.
- Covers-served vs total-waste relationship.
- Kg-per-cover efficiency analysis.
- Attendance-based expected waste and excess residuals.
- Process-control chart with +2σ warning and +3σ control limits.
- Daily variability / coefficient of variation.
- Meal-specific menu-complexity analysis.
- 14-day menu novelty analysis.
- Pareto concentration of positive excess-waste association.
- Repeating meal-menu combination analysis.
- Association-based what-if scenario planner.
- Optional blended ₹/kg waste-cost and reduction-target savings estimates.

## Interpretation safeguards
- Stronger distinction between association and causation.
- Attendance and operational exceptions are reviewed before menu conclusions.
- Pareto logic excludes dishes with non-positive waste lift so ubiquitous staples do not dominate simply through frequency.

## Test dataset
- Replaced the earlier 56-day test set with a full **365-day calendar-year 2025 dataset**.
- Added monthly/seasonal variation, attendance shifts, event dates and operational anomalies across the year.
- Test Guide expanded to explain how to validate the new V3 analytics over a long date range.
- Advanced analytics self-test added.

## V3.2 — Built-in full-year test dataset + quick period filters

- Integrated the synthetic 01-Jan-2025 to 31-Dec-2025 dataset as a one-click built-in software test dataset.
- Added a sidebar shortcut to load/restore the bundled full-year test data.
- Added an optional clean-load switch in Data Manager to clear the current database before loading the test dataset.
- Added quick analysis periods to Overview, Analytics Lab and Data Manager raw-data views:
  - Recent 1 Week
  - Recent 1 Month
  - Recent 3 Months
  - Recent 6 Months
  - Recent 1 Year
  - All Available Data
  - Custom Dates
- Recent periods are anchored to the latest date present in the loaded database, not the computer's current date. This makes historical datasets work correctly at any future date.
- Data Manager CSV exports now include the selected date range in the filename.
- Added `test_date_presets.py` to validate all quick-period calculations.
