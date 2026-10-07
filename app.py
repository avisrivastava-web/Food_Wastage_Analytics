from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import (
    APP_NAME, MEALS, DATA_DIR, TEMPLATE_DIR, TEST_DATA_DIR,
    DEFAULT_HIGH_WASTE_QUANTILE, DEFAULT_MIN_OCCURRENCES, DEFAULT_RISK_CUTOFF,
    AUTO_LOAD_TEST_DATA_IF_EMPTY,
)
from database import (
    init_db, save_menu_for_date, upsert_wastage, load_menu, load_wastage,
    delete_date, clear_all, import_menu_df, import_wastage_df,
    database_is_completely_empty,
)
from analytics import (
    build_daily_dataset, dish_risk_analysis, dish_meal_risk, pair_risk,
    quality_report, recommendations, weekly_summary, anomaly_days, trend_summary,
    menu_complexity_analysis, weekday_summary, high_waste_day_details, executive_insights,
    data_maturity_score, cover_relationship, weekday_benchmark, control_chart_data,
    meal_complexity_summary, menu_signature_analysis, menu_novelty_analysis,
    waste_stability_summary, pareto_dish_excess, scenario_waste_estimate,
    apply_dish_exclusions,
)
from excel_io import (
    normalize_menu_excel, normalize_wastage_excel, read_combined_workbook,
    workbook_sheet_names, read_excel_sheet,
)
from utils import daterange, parse_dishes, df_to_csv_bytes, quick_date_range


st.set_page_config(page_title=APP_NAME, page_icon="♻️", layout="wide", initial_sidebar_state="expanded")
init_db()
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.0rem; padding-bottom: 2.5rem; max-width: 1500px;}
    [data-testid="stSidebar"] {border-right: 1px solid #dfe9e6;}
    h1, h2, h3 {letter-spacing: -0.02em;}
    .hero {
      background: linear-gradient(135deg, #0d574b 0%, #168d78 56%, #2aa78f 100%);
      padding: 24px 28px; border-radius: 18px; color: white; margin-bottom: 18px;
      box-shadow: 0 10px 30px rgba(18, 96, 82, .16);
    }
    .hero h1 {margin: 0 0 6px 0; color: white; font-size: 2.05rem;}
    .hero p {margin: 0; color: rgba(255,255,255,.88); font-size: .98rem;}
    .section-card {
      background: #fff; border: 1px solid #e3ece9; border-radius: 16px; padding: 18px 20px;
      box-shadow: 0 4px 18px rgba(23, 52, 46, .05); margin-bottom: 10px;
    }
    div[data-testid="stMetric"] {
      background: white; border: 1px solid #e1ebe8; padding: 14px 16px; border-radius: 15px;
      box-shadow: 0 4px 16px rgba(23,52,46,.045);
    }
    div[data-testid="stMetric"] label {color: #58716a;}
    .insight {
      background: #eef9f6; border-left: 4px solid #16a085; padding: 11px 14px;
      border-radius: 8px; margin: 7px 0; color: #20423a;
    }
    .warning-card {background:#fff7e8; border:1px solid #f5dfad; border-radius:12px; padding:13px 15px;}
    .muted {color:#6d837d; font-size:.90rem;}
    .pill {display:inline-block; padding:4px 9px; border-radius:999px; background:#eaf7f3; margin-right:5px; font-size:.82rem;}
    .stButton > button, .stDownloadButton > button {border-radius: 10px;}
    .explain {background:#f7fbfa; border:1px solid #dceae6; border-radius:12px; padding:11px 14px; margin:6px 0 14px 0; color:#425f58; font-size:.91rem;}
    .definition {background:#f4f7ff; border-left:4px solid #6574cd; border-radius:8px; padding:10px 13px; margin:7px 0 12px 0; color:#39445d;}
    .action-card {background:#fff8ea; border-left:4px solid #d99c24; border-radius:8px; padding:10px 13px; margin:7px 0; color:#5f4a1d;}
    </style>
    """,
    unsafe_allow_html=True,
)


def hero(title: str, subtitle: str):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def explain(text: str):
    st.markdown(f'<div class="explain">{text}</div>', unsafe_allow_html=True)


def definition(text: str):
    st.markdown(f'<div class="definition">{text}</div>', unsafe_allow_html=True)


def action_note(text: str):
    st.markdown(f'<div class="action-card"><b>Operational use:</b> {text}</div>', unsafe_allow_html=True)


def exclusion_status(excluded_dishes):
    if excluded_dishes:
        preview = ", ".join(excluded_dishes[:6])
        extra = f" +{len(excluded_dishes)-6} more" if len(excluded_dishes) > 6 else ""
        st.info(
            f"Dish-exclusion filter active: **{len(excluded_dishes)} dish(es)** ignored in menu-based analytics — "
            f"{preview}{extra}. Stored/raw data is unchanged, and total daily wastage remains unchanged."
        )


def load_all():
    return load_menu(), load_wastage()


def data_date_bounds(menu, wastage):
    dates = []
    if not menu.empty:
        dates.extend(pd.to_datetime(menu["service_date"]).dt.date.tolist())
    if not wastage.empty:
        dates.extend(pd.to_datetime(wastage["service_date"]).dt.date.tolist())
    if not dates:
        return date.today() - timedelta(days=30), date.today()
    return min(dates), max(dates)


def file_bytes(path: Path):
    return path.read_bytes() if path.exists() else None


def load_builtin_full_year_test_dataset(reset_first: bool = False):
    """Load the bundled 365-day synthetic test dataset into SQLite."""
    menu_path = DATA_DIR / "test_menu_full_year_2025.csv"
    waste_path = DATA_DIR / "test_wastage_full_year_2025.csv"
    if not menu_path.exists() or not waste_path.exists():
        raise FileNotFoundError("Bundled full-year test dataset files are missing from the project.")
    if reset_first:
        clear_all()
    menu_df = pd.read_csv(menu_path)
    waste_df = pd.read_csv(waste_path)
    import_menu_df(menu_df, replace_existing=True)
    import_wastage_df(waste_df)
    return len(menu_df), len(waste_df)


def date_filters(key: str, default_start, default_end):
    """Quick analysis-period presets plus the original custom date controls.

    "Most recent" is anchored to the latest date available in the loaded data,
    rather than today's date. This keeps historical test datasets immediately
    useful even when the application is run later.
    """
    presets = [
        "All Available Data",
        "Recent 1 Week",
        "Recent 1 Month",
        "Recent 3 Months",
        "Recent 6 Months",
        "Recent 1 Year",
        "Custom Dates",
    ]
    st.markdown("#### Analysis period")
    preset = st.radio(
        "Quick date range",
        presets,
        horizontal=True,
        key=f"{key}_preset",
        help=(
            "Recent periods end on the latest date present in the loaded data. "
            "Choose Custom Dates to enter any start and end dates manually."
        ),
    )

    start_key, end_key = f"{key}_start", f"{key}_end"
    if preset == "Custom Dates":
        if start_key not in st.session_state:
            st.session_state[start_key] = default_start
        if end_key not in st.session_state:
            st.session_state[end_key] = default_end
        disabled = False
    else:
        start_calc, end_calc = quick_date_range(preset, default_start, default_end)
        st.session_state[start_key] = start_calc
        st.session_state[end_key] = end_calc
        disabled = True

    a, b = st.columns(2)
    start = a.date_input("From", key=start_key, disabled=disabled)
    end = b.date_input("To", key=end_key, disabled=disabled)
    if end < start:
        st.error("End date must be on or after start date.")
        st.stop()

    days = (end - start).days + 1
    if preset == "Custom Dates":
        period_label = f"Custom: {start:%d %b %Y} to {end:%d %b %Y}"
    else:
        period_label = f"{preset}: {start:%d %b %Y} to {end:%d %b %Y}"
    st.caption(f"Showing **{days:,} calendar day{'s' if days != 1 else ''}** — {period_label}. Latest loaded-data date: **{default_end:%d %b %Y}**.")
    return start, end, period_label


# Cloud/demo bootstrap: Community Cloud local storage can be recreated after
# restarts. When both core tables are truly empty, restore the bundled full-year
# synthetic dataset automatically. A session flag prevents an intentional reset
# from immediately repopulating the database during the same user session.
auto_loaded_test_dataset = False
auto_load_error = None
_auto_load_blocked = bool(st.session_state.get("disable_auto_test_bootstrap", False))
if AUTO_LOAD_TEST_DATA_IF_EMPTY and not _auto_load_blocked and database_is_completely_empty():
    try:
        _auto_menu_rows, _auto_waste_rows = load_builtin_full_year_test_dataset(reset_first=False)
        auto_loaded_test_dataset = True
        st.session_state["auto_test_bootstrap_notice"] = (
            f"Full-year 2025 demo data was restored automatically "
            f"({_auto_waste_rows} days, {_auto_menu_rows:,} menu-dish rows)."
        )
    except Exception as exc:
        auto_load_error = str(exc)

menu_all, waste_all = load_all()
min_d, max_d = data_date_bounds(menu_all, waste_all)

st.sidebar.markdown("## ♻️ WasteLens")
st.sidebar.caption("Food Wastage Analytics")
if auto_load_error:
    st.sidebar.warning(f"Automatic demo-data restore failed: {auto_load_error}")
elif st.session_state.get("auto_test_bootstrap_notice"):
    st.sidebar.success(st.session_state.pop("auto_test_bootstrap_notice"))
page = st.sidebar.radio(
    "Navigation",
    ["Overview", "Data Entry", "Analytics Lab", "Excel Import", "Data Manager", "Methodology"],
    label_visibility="collapsed",
)
st.sidebar.divider()
with st.sidebar.expander("Analysis controls", expanded=False):
    high_q = st.slider("High-wastage cutoff percentile", 0.50, 0.95, DEFAULT_HIGH_WASTE_QUANTILE, 0.05, help="Days at or above this percentile are treated as high-wastage days for association analysis.")
    min_occ = st.number_input("Minimum dish appearances for flagging", 1, 30, DEFAULT_MIN_OCCURRENCES, help="A dish must appear at least this many times before it can be flagged.")
    risk_cutoff = st.slider("Dish association-risk threshold", 40, 90, DEFAULT_RISK_CUTOFF, 5, help="Higher values make dish flagging more conservative.")
    normalize = st.checkbox("Analyze kg per cover when enough attendance data exists", value=False, help="Useful when daily attendance varies substantially.")
all_dish_options = (
    sorted(menu_all["dish"].dropna().astype(str).unique().tolist(), key=str.casefold)
    if not menu_all.empty and "dish" in menu_all.columns else []
)
if "excluded_dishes" in st.session_state:
    st.session_state["excluded_dishes"] = [d for d in st.session_state["excluded_dishes"] if d in all_dish_options]
with st.sidebar.expander("🚫 Dish exclusions", expanded=False):
    st.caption(
        "Select dishes to ignore in menu-based analytics without deleting them. "
        "Raw data and recorded daily wastage remain untouched."
    )
    excluded_dishes = st.multiselect(
        "Exclude dishes from analysis",
        all_dish_options,
        key="excluded_dishes",
        placeholder="Choose one or more dishes",
        help=(
            "Excluded dishes are removed from dish rankings, correlations, Pareto, menu complexity, "
            "novelty, pairs, repeating meal menus and the scenario planner. This does not subtract "
            "kilograms from daily total waste because dish-level waste is not recorded."
        ),
    )
    st.caption(f"Currently excluded: **{len(excluded_dishes)}**")
    if st.button("Clear dish exclusions", key="clear_dish_exclusions", use_container_width=True, disabled=not excluded_dishes):
        st.session_state["excluded_dishes"] = []
        st.rerun()


with st.sidebar.expander("Optional planning assumptions", expanded=False):
    cost_per_kg = st.number_input("Blended food cost per kg (₹)", min_value=0.0, value=0.0, step=10.0, help="Optional blended estimate. Set to 0 to hide cost analytics.")
    target_reduction_pct = st.slider("Waste-reduction target", 0, 50, 15, 5, help="Used only for indicative savings calculations.")

quality_all = quality_report(menu_all, waste_all)
st.sidebar.metric("Matched data days", quality_all["matched_days"])
st.sidebar.caption(f"Completeness: {quality_all['completeness_pct']:.0f}%")
with st.sidebar.expander("🧪 Built-in test dataset", expanded=False):
    st.caption("365-day synthetic dataset • 01 Jan–31 Dec 2025 • four meals/day • covers, notes, seasonality and designed anomalies.")
    if st.button("Load / restore full-year test data", key="sidebar_load_test", use_container_width=True):
        try:
            st.session_state["disable_auto_test_bootstrap"] = False
            m_rows, w_rows = load_builtin_full_year_test_dataset(reset_first=False)
            st.success(f"Loaded {w_rows} test days and {m_rows:,} menu-dish rows.")
            st.rerun()
        except Exception as e:
            st.error(str(e))


if page == "Overview":
    hero(
        "Food Wastage Command Center",
        "A management view of how much food is being wasted, whether performance is improving, which menu items are repeatedly associated with high-waste days, and where to investigate first.",
    )
    start, end, period_label = date_filters("overview", min_d, max_d)
    menu_raw = load_menu(start, end); waste = load_wastage(start, end)
    menu = apply_dish_exclusions(menu_raw, excluded_dishes)
    daily = build_daily_dataset(menu, waste)
    risk, meta = dish_risk_analysis(menu, waste, high_q, int(min_occ), float(risk_cutoff), normalize)
    quality = quality_report(menu_raw, waste)
    maturity = data_maturity_score(menu, waste)

    if daily.empty:
        st.info("No wastage data exists in this date range. Add records through Data Entry or Excel Import, or load the included full-year 2025 test dataset from Data Manager.")
        st.stop()

    st.markdown(f'<span class="pill">Active period: {period_label}</span>', unsafe_allow_html=True)
    exclusion_status(excluded_dishes)
    total = float(daily["total_wastage_kg"].sum())
    avg = float(daily["total_wastage_kg"].mean())
    median = float(daily["total_wastage_kg"].median())
    worst = daily.loc[daily["total_wastage_kg"].idxmax()]
    t = trend_summary(daily)
    stability = waste_stability_summary(daily)
    change = t.get("change_pct")
    delta = None if pd.isna(change) else f"{change:+.1f}% vs previous comparable period"
    covers_available = daily.get("kg_per_cover", pd.Series(dtype=float)).notna().sum() if "kg_per_cover" in daily.columns else 0
    avg_per_cover = float(daily.loc[daily["kg_per_cover"].notna(), "kg_per_cover"].mean()) if covers_available else None

    st.markdown("### 1. Executive KPI summary")
    explain("These are the headline numbers for the selected period. Lower total waste, lower daily average and lower kg per cover are generally better. The data maturity score tells you how much confidence to place in dish-level conclusions.")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total food waste", f"{total:,.1f} kg", help="Sum of all recorded daily food wastage in the selected period.")
    c2.metric("Average waste / day", f"{avg:,.2f} kg", delta, help="Mean recorded waste per day. The delta compares the latest period with the preceding comparable period.")
    c3.metric("Median waste / day", f"{median:,.2f} kg", help="The middle daily value. Median is less distorted by one-off extreme days than the average.")
    c4.metric("Highest-waste day", f"{worst['total_wastage_kg']:.1f} kg", worst["service_date"].strftime("%d %b"), help="The single highest recorded wastage day in the selected range.")
    c5.metric("Flagged dishes", int(risk["flagged"].sum()) if not risk.empty else 0, help="Dishes that cross the configured association-risk threshold and minimum repetition rules.")
    c6.metric("Data maturity", f"{maturity['score']:.0f}/100", maturity["label"], help="A reliability/readiness score based on matched days, completeness, cover data and dish repetition.")

    if covers_available >= 3:
        c7, c8, c9, c10 = st.columns(4)
        c7.metric("Average waste / cover", f"{avg_per_cover:.3f} kg", help="Waste divided by people/covers served. Useful when attendance changes from day to day.")
        c8.metric("Matched menu + waste days", quality["matched_days"], f"{quality['completeness_pct']:.0f}% complete")
        c9.metric("Daily variability", f"{stability['cv']*100:.1f}% CV", help="Coefficient of variation: standard deviation divided by average. Higher values mean waste is less predictable.")
        c10.metric("High-waste quartile days", stability["high_days"], help="Number of days at or above the 75th percentile of waste in this selected range.")

    if cost_per_kg > 0:
        st.markdown("#### Indicative financial impact")
        explain("This uses the optional blended ₹/kg assumption from the sidebar. It is a planning estimate, not an accounting valuation, because different foods have different ingredient costs.")
        estimated_cost = total * cost_per_kg
        target_kg = total * target_reduction_pct / 100.0
        target_savings = target_kg * cost_per_kg
        f1,f2,f3 = st.columns(3)
        f1.metric("Estimated cost of recorded waste", f"₹{estimated_cost:,.0f}")
        f2.metric(f"Target reduction ({target_reduction_pct}%)", f"{target_kg:,.1f} kg")
        f3.metric("Indicative savings at target", f"₹{target_savings:,.0f}")

    st.markdown("### 2. Automated management interpretation")
    explain("These statements translate the statistical outputs into plain English. They are designed to tell a kitchen or operations manager what deserves attention first.")
    insights = executive_insights(daily, risk, menu, waste)
    for item in insights:
        st.markdown(f'<div class="insight">{item}</div>', unsafe_allow_html=True)
    if maturity["score"] < 60:
        action_note("Treat dish rankings as provisional. Collect more repeated menu cycles and cover counts before making major menu removals or purchasing changes.")

    st.markdown("### 3. Waste trend and weekday pattern")
    explain("The daily line shows actual recorded waste. The 7-day and 14-day averages smooth day-to-day noise. The weekday chart shows whether certain days of the week repeatedly run higher than others.")
    left, right = st.columns([1.65, 1])
    with left:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=daily["service_date"], y=daily["total_wastage_kg"], mode="lines+markers", name="Daily waste (kg)"))
        fig.add_trace(go.Scatter(x=daily["service_date"], y=daily["rolling_7d_kg"], mode="lines", name="7-day moving average"))
        if len(daily) >= 14:
            fig.add_trace(go.Scatter(x=daily["service_date"], y=daily["rolling_14d_kg"], mode="lines", name="14-day moving average", line={"dash": "dot"}))
        fig.update_layout(title="Daily food wastage trend", xaxis_title="Service date", yaxis_title="Food wastage (kg)", hovermode="x unified", height=420, margin=dict(l=10,r=10,t=55,b=10))
        st.plotly_chart(fig, use_container_width=True)
        action_note("A sustained fall in the moving-average lines suggests genuine improvement. A single low day is not enough to conclude that the process has improved.")
    with right:
        wkday = weekday_summary(daily)
        fig2 = px.bar(wkday, x="weekday", y="avg_wastage_kg", title="Average waste by weekday", labels={"avg_wastage_kg":"Average waste (kg)", "weekday":"Weekday"}, hover_data=["days","max_wastage_kg"])
        fig2.update_layout(height=420, margin=dict(l=10,r=10,t=55,b=10))
        st.plotly_chart(fig2, use_container_width=True)
        action_note("If one weekday is consistently high, check attendance forecasting, production habits, recurring menu design and delivery/service timing specific to that day.")

    st.markdown("### 4. Day-by-day benchmark variance")
    explain("Each day is compared with the historical average for the same weekday inside the selected period. Positive values mean the day wasted more than its normal weekday benchmark; negative values mean it performed better.")
    benchmark = weekday_benchmark(daily)
    if not benchmark.empty:
        f = px.bar(
            benchmark,
            x="service_date", y="vs_weekday_benchmark_kg",
            hover_data=["total_wastage_kg", "weekday_expected_kg", "weekday"],
            labels={"service_date":"Service date", "vs_weekday_benchmark_kg":"Variance vs weekday benchmark (kg)"},
            title="Variance from weekday-specific expected waste",
        )
        f.add_hline(y=0, line_dash="dash")
        f.update_layout(height=360, margin=dict(l=10,r=10,t=55,b=10))
        st.plotly_chart(f, use_container_width=True)

    st.markdown("### 5. Highest-priority menu signals")
    explain("Dish scores are association signals, not proof that the dish itself was thrown away. A dish ranks higher when it repeatedly appears on high-waste days, has higher average waste when present, covers many high-waste days and has enough repetition for confidence.")
    a, b = st.columns([1, 1])
    with a:
        st.markdown("#### Dish association-risk ranking")
        if risk.empty:
            st.caption("Add matched menu and wastage data to calculate dish signals.")
        else:
            top = risk.head(10).sort_values("risk_score")
            f = px.bar(top, x="risk_score", y="dish", orientation="h", hover_data=["occurrences", "lift_vs_without", "confidence", "priority"], labels={"risk_score":"Association-risk score (0–100)", "dish":"Dish"})
            f.add_vline(x=risk_cutoff, line_dash="dash", annotation_text="flag threshold")
            f.update_layout(height=390, margin=dict(l=10,r=10,t=30,b=10))
            st.plotly_chart(f, use_container_width=True)
    with b:
        st.markdown("#### Estimated excess-waste concentration")
        pareto = pareto_dish_excess(risk)
        if pareto.empty:
            st.caption("Not enough positive excess-waste attribution to display a Pareto view.")
        else:
            p = pareto.head(10).copy()
            f = go.Figure()
            f.add_trace(go.Bar(x=p["dish"], y=p["attributed_excess_kg"], name="Allocated excess kg"))
            f.add_trace(go.Scatter(x=p["dish"], y=p["cumulative_share_pct"], name="Cumulative share %", yaxis="y2", mode="lines+markers"))
            f.update_layout(
                height=390, title="Pareto view of estimated excess-waste association",
                xaxis_title="Dish", yaxis_title="Allocated excess waste (kg)",
                yaxis2=dict(title="Cumulative share (%)", overlaying="y", side="right", range=[0, 105]),
                margin=dict(l=10,r=10,t=55,b=10), legend=dict(orientation="h")
            )
            st.plotly_chart(f, use_container_width=True)
        action_note("Focus trials on a small number of repeatedly high-ranked dishes first—e.g., adjust batch size or portioning—then observe whether waste falls on future comparable days.")

    st.markdown("### 6. Exceptions that need investigation")
    explain("Two different exception methods are shown: IQR outliers detect values far from the overall distribution, while process-control limits look for statistically unusual movement around the process average.")
    anomalies, limits = anomaly_days(daily)
    control, control_meta = control_chart_data(daily)
    x1, x2 = st.columns([1.05, 1.35])
    with x1:
        st.markdown("#### IQR outlier days")
        if anomalies.empty:
            st.success("No strong IQR-based outliers were found in the selected range.")
        else:
            show = anomalies[["service_date", "total_wastage_kg", "deviation_from_7d", "menu_text"]].copy()
            show["service_date"] = show["service_date"].dt.date
            show = show.rename(columns={"service_date":"Date", "total_wastage_kg":"Waste (kg)", "deviation_from_7d":"Difference vs 7-day avg (kg)", "menu_text":"Menu served"})
            st.dataframe(show, use_container_width=True, hide_index=True)
        if limits:
            st.caption(f"Current IQR high-outlier reference: above {limits['upper']:.1f} kg.")
    with x2:
        st.markdown("#### Process-control view")
        if not control.empty:
            f = go.Figure()
            f.add_trace(go.Scatter(x=control["service_date"], y=control["total_wastage_kg"], mode="lines+markers", name="Actual waste"))
            f.add_trace(go.Scatter(x=control["service_date"], y=control["process_mean"], mode="lines", name="Process mean"))
            f.add_trace(go.Scatter(x=control["service_date"], y=control["warning_upper"], mode="lines", name="+2σ warning", line={"dash":"dot"}))
            f.add_trace(go.Scatter(x=control["service_date"], y=control["control_upper"], mode="lines", name="+3σ control limit", line={"dash":"dash"}))
            f.update_layout(height=340, xaxis_title="Service date", yaxis_title="Waste (kg)", margin=dict(l=10,r=10,t=15,b=10), legend=dict(orientation="h"))
            st.plotly_chart(f, use_container_width=True)
            st.caption(f"Warning-zone days: {control_meta.get('warning_days',0)} | Outside control limits: {control_meta.get('outside_control_days',0)}")

    if covers_available >= 3:
        st.markdown("### 7. Attendance-normalized efficiency")
        explain("Total kilograms can rise simply because more people were served. Kg per cover divides waste by attendance and is therefore a fairer efficiency metric when footfall varies.")
        per_cover = daily[daily["kg_per_cover"].notna()].copy()
        p1, p2 = st.columns([1.55, 1])
        with p1:
            f = px.line(per_cover, x="service_date", y="kg_per_cover", markers=True, labels={"kg_per_cover":"Food waste per cover (kg/person)", "service_date":"Service date"}, title="Waste per cover over time")
            st.plotly_chart(f, use_container_width=True)
        with p2:
            st.metric("Average kg / cover", f"{per_cover['kg_per_cover'].mean():.3f}")
            st.metric("Best recorded kg / cover", f"{per_cover['kg_per_cover'].min():.3f}")
            st.metric("Worst recorded kg / cover", f"{per_cover['kg_per_cover'].max():.3f}")
            action_note("Use kg per cover to judge preparation/portioning efficiency. Use total kg to understand absolute cost and disposal impact.")

    st.markdown("### 8. Data confidence at a glance")
    explain("Analytics become more trustworthy when menu and wastage dates match, dishes repeat enough times for comparison, and attendance/covers are recorded consistently.")
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Matched analysis days", maturity["matched_days"])
    q2.metric("Data completeness", f"{maturity['completeness_pct']:.0f}%")
    q3.metric("Cover-data availability", f"{maturity['cover_coverage_pct']:.0f}%")
    q4.metric("Dishes with ≥3 repeats", f"{maturity['repeat_ratio_pct']:.0f}%")


elif page == "Data Entry":
    hero("Data Entry", "Enter menus and wastage manually. Date ranges are flexible; seven days is simply the default.")
    menu_tab, waste_tab = st.tabs(["🍽️ Menu", "⚖️ Wastage"])

    with menu_tab:
        st.subheader("Menu entry — what was planned/served")
        explain("Enter every dish served in each of the four meals. Separate multiple dishes with commas. Consistent dish naming matters: 'Rajma' and 'Rajma Curry' will be treated as different dishes unless you use the same name consistently.")
        c1, c2 = st.columns(2)
        start = c1.date_input("Start date", value=date.today(), key="menu_start")
        end = c2.date_input("End date", value=date.today() + timedelta(days=6), key="menu_end")
        if end < start:
            st.error("End date must be on or after start date."); st.stop()
        if (end - start).days > 30:
            st.warning("Manual entry is limited to 31 days per editing session. Excel Import is better for larger ranges.")
            end = start + timedelta(days=30)

        existing = load_menu(start, end)
        existing_map = {}
        if not existing.empty:
            for (d, meal), g in existing.groupby([existing["service_date"].dt.date, "meal"]):
                existing_map[(d, meal)] = ", ".join(g["dish"].tolist())

        with st.form("menu_form"):
            entries = {}
            for d in daterange(start, end):
                with st.expander(d.strftime("%A, %d %b %Y"), expanded=(d == start)):
                    cols = st.columns(4)
                    for idx, meal in enumerate(MEALS):
                        with cols[idx]:
                            entries[(d, meal)] = st.text_area(
                                meal, value=existing_map.get((d, meal), ""), height=110,
                                key=f"menu_{d}_{meal}", placeholder="Dish 1, Dish 2",
                            )
            submitted = st.form_submit_button("Save menu", type="primary", use_container_width=True)
        if submitted:
            for d in daterange(start, end):
                save_menu_for_date(d, {meal: parse_dishes(entries[(d, meal)]) for meal in MEALS})
            st.success(f"Menu saved for {start} to {end}."); st.rerun()

    with waste_tab:
        st.subheader("Daily wastage entry — what was discarded")
        explain("Waste kg is the total food wastage for the whole day. Covers served is optional but strongly recommended because it allows the system to calculate waste per person and separate attendance effects from menu effects. Use Notes for events, quality problems, unexpected attendance or service disruptions.")
        c1, c2 = st.columns(2)
        start = c1.date_input("Start date", value=date.today(), key="waste_start")
        end = c2.date_input("End date", value=date.today() + timedelta(days=6), key="waste_end")
        if end < start:
            st.error("End date must be on or after start date."); st.stop()
        existing = load_wastage(start, end)
        existing_map = {r.service_date.date(): r for r in existing.itertuples(index=False)} if not existing.empty else {}
        with st.form("waste_form"):
            rows = {}
            for d in daterange(start, end):
                r = existing_map.get(d)
                st.markdown(f"**{d.strftime('%A, %d %b %Y')}**")
                a, b, c = st.columns([1, 1, 2])
                kg = a.number_input("Waste kg", min_value=0.0, value=float(getattr(r, "total_wastage_kg", 0.0)), step=0.1, key=f"kg_{d}")
                cv = b.number_input("Covers served", min_value=0, value=int(getattr(r, "covers_served", 0) or 0), step=1, key=f"cv_{d}")
                nt = c.text_input("Notes", value=str(getattr(r, "notes", "") or ""), key=f"nt_{d}")
                rows[d] = (kg, cv, nt)
            submitted = st.form_submit_button("Save wastage", type="primary", use_container_width=True)
        if submitted:
            for d, (kg, cv, nt) in rows.items():
                upsert_wastage(d, kg, cv if cv > 0 else None, nt)
            st.success("Wastage saved."); st.rerun()


elif page == "Analytics Lab":
    hero(
        "Analytics Lab",
        "Detailed diagnostic analysis for menu drivers, attendance effects, process stability, menu design, repeating combinations and planning scenarios.",
    )
    start, end, period_label = date_filters("lab", min_d, max_d)
    menu_raw = load_menu(start, end); waste = load_wastage(start, end)
    menu = apply_dish_exclusions(menu_raw, excluded_dishes)
    daily = build_daily_dataset(menu, waste)
    risk, meta = dish_risk_analysis(menu, waste, high_q, int(min_occ), float(risk_cutoff), normalize)
    maturity = data_maturity_score(menu, waste)
    if daily.empty:
        st.info("No data is available for this date range."); st.stop()

    st.markdown(f'<span class="pill">Active period: {period_label}</span>', unsafe_allow_html=True)
    exclusion_status(excluded_dishes)
    definition(
        "How to use this page: start with Dish Drivers to identify recurring menu associations, then use Attendance & Efficiency and Process Control to rule out non-menu causes. Menu Structure and Repeating Menus help identify design-level effects. The Scenario Planner is a planning aid only—it is not a causal forecast."
    )

    tabs = st.tabs([
        "Dish Drivers",
        "Trends & Benchmarks",
        "Attendance & Efficiency",
        "High-Waste & Control",
        "Menu Structure",
        "Pairs & Meal Menus",
        "Scenario Planner",
        "Data Reliability",
    ])

    with tabs[0]:
        st.markdown("### Dish-level association analysis")
        explain("This analysis asks: when a dish appears, is the whole day's recorded waste repeatedly higher? It does not claim that the dish itself was discarded, because the input is one total wastage number for the day.")
        if risk.empty:
            st.info("Matched menu and wastage data is required for dish analysis.")
        else:
            k1,k2,k3,k4,k5 = st.columns(5)
            k1.metric("Matched analysis days", meta["analysis_days"], help="Days that have both menu and wastage records.")
            unit = "kg" if meta["metric"] == "total_wastage_kg" else "kg/cover"
            k2.metric("High-waste cutoff", f"{meta['high_threshold']:.2f} {unit}", help="Days at or above this value are classified as high-waste days according to the selected percentile.")
            k3.metric("Flagged dish signals", int(risk["flagged"].sum()))
            k4.metric("Unique dishes assessed", len(risk))
            k5.metric("Overall daily mean", f"{meta['overall_mean']:.2f} {unit}")

            definition("Risk score (0–100) combines repeated exposure to high-waste days, average waste when served, lift versus days when absent, positive correlation, allocated excess waste and repetition confidence. Higher = stronger investigation priority, not proof of causation.")
            display = risk.copy()
            display.insert(0, "Flag", display["flagged"].map({True:"⚠️ Review", False:""}))
            display = display.rename(columns={
                "dish":"Dish",
                "meals":"Meal(s) served",
                "occurrences":"Times served",
                "risk_score":"Association risk score",
                "priority":"Priority band",
                "confidence":"Repetition confidence",
                "mean_wastage_when_served":"Avg waste when served",
                "mean_wastage_when_not_served":"Avg waste when absent",
                "lift_vs_without":"Waste lift vs absent",
                "correlation":"Presence/waste correlation",
                "high_waste_hits":"High-waste appearances",
                "top_day_coverage":"Share of high-waste days covered",
                "attributed_excess_kg":"Allocated excess association (kg)",
            })
            cols = ["Flag","Dish","Meal(s) served","Times served","Association risk score","Priority band","Repetition confidence","Waste lift vs absent","Presence/waste correlation","High-waste appearances","Share of high-waste days covered","Allocated excess association (kg)"]
            st.dataframe(
                display[cols], use_container_width=True, hide_index=True,
                column_config={
                    "Association risk score": st.column_config.ProgressColumn("Association risk score", min_value=0, max_value=100, format="%.0f"),
                    "Share of high-waste days covered": st.column_config.NumberColumn(format="%.1%"),
                    "Presence/waste correlation": st.column_config.NumberColumn(format="%.2f"),
                    "Waste lift vs absent": st.column_config.NumberColumn(format="%.2f"),
                    "Allocated excess association (kg)": st.column_config.NumberColumn(format="%.2f"),
                },
            )
            st.download_button("Download full dish-driver analysis (CSV)", df_to_csv_bytes(risk), "dish_driver_analysis.csv", "text/csv")

            c1,c2 = st.columns(2)
            with c1:
                f = px.scatter(
                    risk, x="occurrences", y="risk_score", size="mean_wastage_when_served", hover_name="dish",
                    hover_data=["lift_vs_without","correlation","priority","confidence"],
                    labels={"occurrences":"Times dish was served", "risk_score":"Association risk score (0–100)"},
                    title="Risk score versus number of observations",
                )
                f.add_hline(y=risk_cutoff, line_dash="dash", annotation_text="flag threshold")
                st.plotly_chart(f, use_container_width=True)
                action_note("Prefer dishes in the upper-right: high association score plus enough repetitions. A high score from only one or two appearances should be treated cautiously.")
            with c2:
                context = dish_meal_risk(menu, waste, high_q).head(20)
                if not context.empty:
                    context = context.assign(label=context["dish"] + " — " + context["meal"])
                    f = px.bar(
                        context.sort_values("context_score"), x="context_score", y="label", orientation="h",
                        hover_data=["occurrences","mean_wastage_kg","high_waste_rate"],
                        labels={"context_score":"Dish × meal context score", "label":"Dish and meal"},
                        title="Where the same dish is most concerning by meal",
                    )
                    st.plotly_chart(f, use_container_width=True)
                action_note("If a dish is high-risk only in one meal, investigate that meal's batch size, portioning and service timing before changing the dish everywhere.")

            st.markdown("#### Pareto: where the estimated excess association is concentrated")
            pareto = pareto_dish_excess(risk)
            if pareto.empty:
                st.caption("No positive allocated excess-waste association is available.")
            else:
                p = pareto.head(15)
                f = go.Figure()
                f.add_trace(go.Bar(x=p["dish"], y=p["attributed_excess_kg"], name="Allocated excess kg"))
                f.add_trace(go.Scatter(x=p["dish"], y=p["cumulative_share_pct"], yaxis="y2", mode="lines+markers", name="Cumulative share %"))
                f.update_layout(
                    height=420, yaxis_title="Allocated excess association (kg)",
                    yaxis2=dict(title="Cumulative share (%)", overlaying="y", side="right", range=[0,105]),
                    xaxis_title="Dish", legend=dict(orientation="h"),
                )
                st.plotly_chart(f, use_container_width=True)
            st.markdown("#### Recommended investigation actions")
            for rec in recommendations(risk):
                st.markdown(f'<div class="insight">{rec}</div>', unsafe_allow_html=True)

    with tabs[1]:
        st.markdown("### Trend, weekly performance and weekday benchmark")
        explain("Use this tab to decide whether waste is improving over time and whether high values are explained by recurring weekday patterns rather than isolated menu effects.")
        weekly = weekly_summary(daily)
        benchmark = weekday_benchmark(daily)
        c1,c2 = st.columns([1.4,1])
        with c1:
            f = px.bar(weekly, x="week_start", y="total_waste_kg", hover_data=["avg_daily_waste_kg","recorded_days","max_day_kg"], title="Weekly total food wastage", labels={"week_start":"Week starting", "total_waste_kg":"Total waste (kg)"})
            st.plotly_chart(f, use_container_width=True)
        with c2:
            wk = weekday_summary(daily)
            f = px.bar(wk, x="weekday", y="avg_wastage_kg", title="Average daily waste by weekday", labels={"weekday":"Weekday", "avg_wastage_kg":"Average waste (kg)"})
            st.plotly_chart(f, use_container_width=True)
        st.markdown("#### Weekly summary table")
        explain("Recorded days is important: avoid comparing a full 7-day week with a partial week without considering this column.")
        show = weekly.rename(columns={"week_start":"Week starting", "total_waste_kg":"Total waste (kg)", "avg_daily_waste_kg":"Avg daily waste (kg)", "max_day_kg":"Highest day (kg)", "recorded_days":"Recorded days", "avg_kg_per_cover":"Avg kg/cover"})
        st.dataframe(show, use_container_width=True, hide_index=True)

        st.markdown("#### Daily variance from same-weekday benchmark")
        if not benchmark.empty:
            f = px.bar(
                benchmark, x="service_date", y="vs_weekday_benchmark_kg",
                hover_data=["weekday","total_wastage_kg","weekday_expected_kg","vs_weekday_benchmark_pct"],
                labels={"service_date":"Service date", "vs_weekday_benchmark_kg":"Variance (kg)"},
                title="Actual waste minus normal waste for that weekday",
            )
            f.add_hline(y=0, line_dash="dash")
            st.plotly_chart(f, use_container_width=True)
            action_note("Investigate large positive bars. These are days that performed worse than their own weekday norm, making them useful candidates for menu and operations review.")

    with tabs[2]:
        st.markdown("### Attendance and waste efficiency")
        explain("This analysis separates 'we wasted more because we served more people' from 'we wasted more than attendance would normally explain'. Covers served should represent the number of meals/people actually served consistently each day.")
        cover_df, cover_meta = cover_relationship(waste)
        if len(cover_df) < 3:
            st.info("At least 3 days with covers served are needed. Add Covers Served in Data Entry or the wastage Excel file.")
        else:
            m1,m2,m3,m4 = st.columns(4)
            m1.metric("Days with cover data", cover_meta["days"])
            m2.metric("Covers ↔ total waste correlation", f"{cover_meta['correlation']:.2f}", help="Positive means higher attendance tends to coincide with higher total waste.")
            m3.metric("Average waste / cover", f"{cover_meta['avg_kg_per_cover']:.3f} kg")
            r2 = cover_meta.get("r2")
            m4.metric("Attendance model R²", "—" if pd.isna(r2) else f"{r2:.2f}", help="Approximate share of total-waste variation explained by covers alone in a simple linear relationship.")

            c1,c2 = st.columns(2)
            with c1:
                f = px.scatter(
                    cover_df, x="covers_served", y="total_wastage_kg", hover_data=["service_date","kg_per_cover","excess_vs_attendance_kg"],
                    labels={"covers_served":"Covers / people served", "total_wastage_kg":"Total waste (kg)"},
                    title="Does higher attendance explain higher total waste?",
                )
                if "attendance_expected_kg" in cover_df:
                    line = cover_df.sort_values("covers_served")
                    f.add_trace(go.Scatter(x=line["covers_served"], y=line["attendance_expected_kg"], mode="lines", name="Attendance-based expected waste"))
                st.plotly_chart(f, use_container_width=True)
            with c2:
                f = px.line(cover_df.sort_values("service_date"), x="service_date", y="kg_per_cover", markers=True, title="Waste efficiency per cover", labels={"service_date":"Service date", "kg_per_cover":"Waste per cover (kg/person)"})
                st.plotly_chart(f, use_container_width=True)

            st.markdown("#### Days with more waste than attendance alone would suggest")
            excess = cover_df.sort_values("excess_vs_attendance_kg", ascending=False).head(12).copy()
            excess["service_date"] = excess["service_date"].dt.date
            excess = excess.rename(columns={"service_date":"Date", "covers_served":"Covers served", "total_wastage_kg":"Actual waste (kg)", "attendance_expected_kg":"Attendance-expected waste (kg)", "excess_vs_attendance_kg":"Excess vs attendance expectation (kg)", "kg_per_cover":"Kg per cover"})
            st.dataframe(excess[["Date","Covers served","Actual waste (kg)","Attendance-expected waste (kg)","Excess vs attendance expectation (kg)","Kg per cover"]], use_container_width=True, hide_index=True)
            action_note("Large positive attendance-adjusted residuals deserve menu/operations investigation. They are harder to explain merely by serving more people.")

    with tabs[3]:
        st.markdown("### High-waste days, statistical outliers and process control")
        explain("High-waste percentile days are relative to your chosen cutoff. IQR outliers are distribution-based extremes. Process-control limits identify days unusually far from the process mean. These methods answer slightly different questions, so use them together.")
        top_days = high_waste_day_details(menu, waste, high_q)
        st.markdown(f"#### Days at or above the selected {int(high_q*100)}th percentile")
        if top_days.empty:
            st.info("No high-waste days found.")
        else:
            d = top_days.copy(); d["service_date"] = d["service_date"].dt.date
            d = d.rename(columns={"service_date":"Date", "total_wastage_kg":"Waste (kg)", "covers_served":"Covers served", "menu":"Full menu", "notes":"Operational notes"})
            st.dataframe(d[["Date","Waste (kg)","Covers served","Full menu","Operational notes"]], use_container_width=True, hide_index=True)

        c1,c2 = st.columns(2)
        with c1:
            anomalies, limits = anomaly_days(daily)
            st.markdown("#### IQR statistical outliers")
            if anomalies.empty:
                st.success("No strong IQR outliers in this range.")
            else:
                a = anomalies[["service_date","total_wastage_kg","rolling_7d_kg","deviation_from_7d","menu_text"]].copy()
                a["service_date"] = a["service_date"].dt.date
                st.dataframe(a, use_container_width=True, hide_index=True)
            if limits:
                st.caption(f"IQR high-outlier threshold: {limits['upper']:.2f} kg.")
        with c2:
            control, cm = control_chart_data(daily)
            st.markdown("#### Process-control signals")
            if not control.empty:
                f = go.Figure()
                f.add_trace(go.Scatter(x=control["service_date"], y=control["total_wastage_kg"], mode="lines+markers", name="Actual waste"))
                f.add_trace(go.Scatter(x=control["service_date"], y=control["process_mean"], mode="lines", name="Mean"))
                f.add_trace(go.Scatter(x=control["service_date"], y=control["warning_upper"], mode="lines", name="+2σ warning", line={"dash":"dot"}))
                f.add_trace(go.Scatter(x=control["service_date"], y=control["control_upper"], mode="lines", name="+3σ control", line={"dash":"dash"}))
                f.update_layout(yaxis_title="Waste (kg)", xaxis_title="Service date", legend=dict(orientation="h"))
                st.plotly_chart(f, use_container_width=True)
                st.caption(f"Warning-zone days: {cm['warning_days']} | Outside-control days: {cm['outside_control_days']}")
        action_note("For each extreme day, read the operational notes first. Events, quality issues, unexpected attendance, service delays or production errors can be stronger explanations than the menu.")

    with tabs[4]:
        st.markdown("### Menu structure and design effects")
        explain("This section tests whether complexity, meal-level dish counts, or menu novelty are associated with higher daily waste. These are design-level signals rather than individual-dish signals.")
        complexity, corr = menu_complexity_analysis(menu, waste)
        meal_comp = meal_complexity_summary(menu, waste, high_q)
        novelty, novelty_corr = menu_novelty_analysis(menu, waste)

        a,b,c = st.columns(3)
        a.metric("Menu size ↔ waste correlation", f"{corr:.2f}", help="Correlation between number of distinct dishes that day and total daily waste.")
        b.metric("Menu novelty ↔ waste correlation", f"{novelty_corr:.2f}", help="Correlation between share of dishes not seen in the prior 14 days and total daily waste.")
        avg_dishes = float(complexity["dish_count"].mean()) if not complexity.empty else 0.0
        c.metric("Average distinct dishes / day", f"{avg_dishes:.1f}")

        c1,c2 = st.columns(2)
        with c1:
            if not complexity.empty:
                f = px.scatter(complexity, x="dish_count", y="total_wastage_kg", hover_data=["service_date"], labels={"dish_count":"Distinct dishes served that day", "total_wastage_kg":"Total waste (kg)"}, title="Does a larger menu coincide with more waste?")
                st.plotly_chart(f, use_container_width=True)
        with c2:
            if not novelty.empty:
                f = px.scatter(novelty, x="novelty_rate", y="total_wastage_kg", hover_data=["service_date","new_dish_count","dish_count"], labels={"novelty_rate":"Share of dishes new vs prior 14 days", "total_wastage_kg":"Total waste (kg)"}, title="Does menu novelty coincide with more waste?")
                st.plotly_chart(f, use_container_width=True)

        st.markdown("#### Which meal's complexity is most associated with daily waste?")
        if meal_comp.empty:
            st.info("Menu data is required for meal-complexity analysis.")
        else:
            mshow = meal_comp.rename(columns={
                "meal":"Meal",
                "avg_distinct_dishes":"Avg distinct dishes",
                "correlation_with_daily_waste":"Correlation with total daily waste",
                "avg_dishes_on_high_waste_days":"Avg dishes on high-waste days",
                "avg_dishes_on_other_days":"Avg dishes on other days",
                "complexity_lift_on_high_days":"Dish-count lift on high-waste days",
            })
            st.dataframe(mshow, use_container_width=True, hide_index=True, column_config={"Correlation with total daily waste": st.column_config.NumberColumn(format="%.2f")})
            f = px.bar(meal_comp, x="meal", y="correlation_with_daily_waste", labels={"meal":"Meal", "correlation_with_daily_waste":"Correlation with daily waste"}, title="Meal-specific menu complexity signal")
            f.add_hline(y=0, line_dash="dash")
            st.plotly_chart(f, use_container_width=True)
        action_note("A strong positive complexity signal suggests testing a simpler offering or smaller batch breadth for that meal, rather than immediately blaming one dish.")

    with tabs[5]:
        st.markdown("### Dish pairs and repeating meal-menu combinations")
        explain("Pair analysis looks for two dishes that repeatedly coexist on higher-waste days. Repeating meal-menu analysis compares recurring combinations within Breakfast, Lunch, Snacks or Dinner. Both can reveal interaction effects that single-dish analysis misses.")
        pairs = pair_risk(menu, waste, min_pair_occurrences=max(2, int(min_occ)))
        signatures = menu_signature_analysis(menu, waste, min_occurrences=max(2, int(min_occ)))
        c1,c2 = st.columns(2)
        with c1:
            st.markdown("#### Repeating dish pairs")
            if pairs.empty:
                st.info("No dish pair repeats enough times for the current minimum-occurrence setting.")
            else:
                pshow = pairs.head(50).rename(columns={"dish_1":"Dish 1", "dish_2":"Dish 2", "occurrences":"Times together", "mean_wastage_kg":"Avg waste when together (kg)", "max_wastage_kg":"Max waste when together (kg)", "pair_score":"Pair association score"})
                st.dataframe(pshow, use_container_width=True, hide_index=True, column_config={"Pair association score": st.column_config.ProgressColumn(min_value=0,max_value=100,format="%.0f")})
        with c2:
            st.markdown("#### Repeating meal menus")
            if signatures.empty:
                st.info("No meal-menu combination repeats enough times for direct comparison.")
            else:
                sshow = signatures.head(40).copy()
                sshow["menu_signature"] = sshow["menu_signature"].str.slice(0, 180)
                sshow = sshow.rename(columns={"meal":"Meal", "menu_signature":"Meal-menu combination", "occurrences":"Times repeated", "avg_wastage_kg":"Avg total-day waste when served (kg)", "min_wastage_kg":"Min total-day waste (kg)", "max_wastage_kg":"Max total-day waste (kg)", "menu_score":"Within-meal association score"})
                st.dataframe(sshow, use_container_width=True, hide_index=True, column_config={"Within-meal association score": st.column_config.ProgressColumn(min_value=0,max_value=100,format="%.0f")})
        action_note("If the same meal-menu combination repeatedly coincides with high total-day waste, compare it with alternative combinations in the same meal and run a controlled production-volume trial while keeping attendance and other conditions comparable.")

    with tabs[6]:
        st.markdown("### Association-based what-if planner")
        explain("This tool creates a rough planning estimate from the historical median, attendance relationship and positive dish associations. It deliberately dampens dish effects because dishes can be correlated with one another. Do not treat this as a guaranteed forecast or causal model.")
        dish_options = sorted(risk["dish"].tolist(), key=str.casefold) if not risk.empty else sorted(menu["dish"].unique().tolist(), key=str.casefold)
        selected = st.multiselect("Dishes you are considering for a future menu", dish_options, help="Select dishes to see how their historical associations change the planning estimate.")
        covers_default = int(waste["covers_served"].dropna().median()) if "covers_served" in waste.columns and waste["covers_served"].notna().any() else 0
        covers_input = st.number_input("Expected covers / people served (optional)", min_value=0, value=covers_default, step=1)
        est = scenario_waste_estimate(selected, covers_input if covers_input > 0 else None, risk, waste)
        if est:
            e1,e2,e3,e4 = st.columns(4)
            e1.metric("Historical median baseline", f"{est['baseline_kg']:.1f} kg")
            e2.metric("Attendance adjustment", f"{est['attendance_adjustment_kg']:+.1f} kg")
            e3.metric("Selected-dish association adjustment", f"{est['dish_adjustment_kg']:+.1f} kg")
            e4.metric("Planning estimate", f"{est['estimated_waste_kg']:.1f} kg")
            st.info(f"Indicative variability range: approximately {est['low_range_kg']:.1f}–{est['high_range_kg']:.1f} kg based on historical variability.")
            if est["dish_adjustments"]:
                adf = pd.DataFrame(est["dish_adjustments"], columns=["Dish","Weighted positive association adjustment (kg)"])
                st.dataframe(adf, use_container_width=True, hide_index=True)
            action_note("Use this for menu-planning discussion and trial design. After the actual service day, compare actual waste with the estimate and record operational notes to improve future interpretation.")

    with tabs[7]:
        st.markdown("### Data reliability and analysis readiness")
        explain("A sophisticated chart is not useful if the underlying data is incomplete. This score summarizes whether you have enough matched dates, repeated dishes and attendance information for stronger conclusions.")
        q = quality_report(menu_raw, waste)
        m1,m2,m3,m4,m5 = st.columns(5)
        m1.metric("Maturity score", f"{maturity['score']:.0f}/100", maturity["label"])
        m2.metric("Matched menu + waste days", maturity["matched_days"])
        m3.metric("Completeness", f"{maturity['completeness_pct']:.0f}%")
        m4.metric("Cover-data coverage", f"{maturity['cover_coverage_pct']:.0f}%")
        m5.metric("Dishes repeated ≥3 times", f"{maturity['repeat_ratio_pct']:.0f}%")

        st.markdown("#### Reliability interpretation")
        if maturity["score"] >= 80:
            st.success("Strong dataset: suitable for repeated-pattern analysis, while still remembering that daily total waste cannot prove dish-level disposal.")
        elif maturity["score"] >= 60:
            st.info("Good dataset: useful operational signals are available, but continue collecting cover counts and repeated menu cycles.")
        elif maturity["score"] >= 40:
            st.warning("Developing dataset: use rankings mainly to decide what to investigate, not what to remove from the menu.")
        else:
            st.warning("Early dataset: conclusions are highly provisional. Prioritize consistent daily recording before acting on rankings.")

        c1,c2 = st.columns(2)
        with c1:
            st.markdown("#### Menu dates missing wastage")
            if q["menu_without_wastage"]:
                st.write(", ".join(map(str, q["menu_without_wastage"][:50])))
            else:
                st.success("None")
        with c2:
            st.markdown("#### Wastage dates missing menu")
            if q["wastage_without_menu"]:
                st.write(", ".join(map(str, q["wastage_without_menu"][:50])))
            else:
                st.success("None")
        action_note("For the strongest analysis, target at least 4–8 weeks of matched data, record covers served daily, and ensure important dishes appear multiple times across different weekdays and attendance levels.")


elif page == "Excel Import":
    hero("Excel Import Center", "Upload a combined workbook or separate menu/wastage Excel files. Download the ready-made templates below.")

    st.markdown("### Download Excel templates")
    t1,t2,t3 = st.columns(3)
    combined_path = TEMPLATE_DIR / "Food_Wastage_Import_Template.xlsx"
    menu_path = TEMPLATE_DIR / "Menu_Import_Template.xlsx"
    waste_path = TEMPLATE_DIR / "Wastage_Import_Template.xlsx"
    t1.download_button("Combined template", file_bytes(combined_path), combined_path.name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", disabled=not combined_path.exists(), use_container_width=True)
    t2.download_button("Menu-only template", file_bytes(menu_path), menu_path.name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", disabled=not menu_path.exists(), use_container_width=True)
    t3.download_button("Wastage-only template", file_bytes(waste_path), waste_path.name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", disabled=not waste_path.exists(), use_container_width=True)
    st.caption("Menu template format: Date + Breakfast + Lunch + Snacks + Dinner. Put multiple dishes in a meal cell separated by commas.")
    with st.expander("How to prepare Excel data correctly", expanded=False):
        st.markdown("""
**Menu workbook rules**
- One row per service date in the simple template.
- Use the four columns **Breakfast, Lunch, Snacks, Dinner**.
- Separate multiple dishes with commas.
- Keep dish names consistent across weeks.

**Wastage workbook rules**
- **Date** and **Total Wastage (kg)** are required.
- **Covers Served** is optional but recommended.
- **Notes** should capture unusual conditions such as events, low attendance, quality issues or late service.

**Why this matters:** menu names drive dish matching, while covers and notes help distinguish menu effects from operational causes.
        """)

    st.markdown("### Test dataset")
    st.caption("Use the ready-made full-year 2025 synthetic dataset to test imports, seasonality, trends, anomaly detection and dish-risk analytics before entering real data.")
    d1,d2,d3 = st.columns(3)
    test_combined = TEST_DATA_DIR / "Food_Wastage_Test_Dataset_Full_Year_2025.xlsx"
    test_menu = TEST_DATA_DIR / "Menu_Test_Dataset_Full_Year_2025.xlsx"
    test_waste = TEST_DATA_DIR / "Wastage_Test_Dataset_Full_Year_2025.xlsx"
    d1.download_button("Download combined test data", file_bytes(test_combined), test_combined.name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", disabled=not test_combined.exists(), use_container_width=True)
    d2.download_button("Download test menu", file_bytes(test_menu), test_menu.name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", disabled=not test_menu.exists(), use_container_width=True)
    d3.download_button("Download test wastage", file_bytes(test_waste), test_waste.name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", disabled=not test_waste.exists(), use_container_width=True)

    combined_tab, menu_tab, waste_tab = st.tabs(["Combined workbook", "Menu Excel", "Wastage Excel"])

    with combined_tab:
        up = st.file_uploader("Upload combined Excel workbook", type=["xlsx"], key="combined_xlsx")
        if up is not None:
            try:
                menu_df, waste_df, info = read_combined_workbook(up)
                st.success(f"Detected menu sheet: {info['menu_sheet'] or '—'} | wastage sheet: {info['wastage_sheet'] or '—'}")
                p1,p2 = st.columns(2)
                with p1:
                    st.markdown("**Normalized menu preview**"); st.dataframe(menu_df.head(30), use_container_width=True, hide_index=True)
                with p2:
                    st.markdown("**Normalized wastage preview**"); st.dataframe(waste_df.head(30), use_container_width=True, hide_index=True)
                replace = st.checkbox("Replace existing menu entries for the dates/meals present in this workbook", value=True, key="combined_replace")
                if st.button("Import combined workbook", type="primary", use_container_width=True):
                    if not menu_df.empty: import_menu_df(menu_df, replace_existing=replace)
                    if not waste_df.empty: import_wastage_df(waste_df)
                    st.success(f"Imported {len(menu_df)} menu rows and {len(waste_df)} wastage rows."); st.rerun()
            except Exception as e:
                st.error(f"Excel import error: {e}")

    with menu_tab:
        up = st.file_uploader("Upload menu Excel", type=["xlsx"], key="menu_xlsx")
        if up is not None:
            try:
                names = workbook_sheet_names(up)
                sheet = st.selectbox("Sheet", names, key="menu_sheet")
                raw = read_excel_sheet(up, sheet)
                normalized = normalize_menu_excel(raw)
                st.dataframe(normalized.head(50), use_container_width=True, hide_index=True)
                replace = st.checkbox("Replace existing entries for imported date/meal combinations", value=True, key="menu_replace")
                if st.button("Import menu Excel", type="primary"):
                    import_menu_df(normalized, replace_existing=replace)
                    st.success(f"Imported {len(normalized)} menu rows."); st.rerun()
            except Exception as e:
                st.error(f"Menu Excel error: {e}")

    with waste_tab:
        up = st.file_uploader("Upload wastage Excel", type=["xlsx"], key="waste_xlsx")
        if up is not None:
            try:
                names = workbook_sheet_names(up)
                sheet = st.selectbox("Sheet", names, key="waste_sheet")
                raw = read_excel_sheet(up, sheet)
                normalized = normalize_wastage_excel(raw)
                st.dataframe(normalized.head(50), use_container_width=True, hide_index=True)
                st.caption("Existing wastage dates are updated automatically when re-imported.")
                if st.button("Import wastage Excel", type="primary"):
                    import_wastage_df(normalized)
                    st.success(f"Imported {len(normalized)} wastage rows."); st.rerun()
            except Exception as e:
                st.error(f"Wastage Excel error: {e}")


elif page == "Data Manager":
    hero("Data Manager", "Review, export, validate or remove stored records.")
    tab1, tab2, tab3 = st.tabs(["View & Export", "CSV Import", "Delete / Reset"])
    with tab1:
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Load 7-day sample data", use_container_width=True):
                try:
                    import_menu_df(pd.read_csv(DATA_DIR / "sample_menu.csv"), replace_existing=True)
                    import_wastage_df(pd.read_csv(DATA_DIR / "sample_wastage.csv"))
                    st.success("7-day sample data loaded."); st.rerun()
                except Exception as e: st.error(str(e))
        with b2:
            replace_db_with_test = st.checkbox(
                "Clear current database before loading test data",
                value=False,
                help="Turn this on for a clean demonstration containing only the bundled 2025 test year. Leave it off to merge/restore the test dates without deleting other dates.",
                key="reset_before_test_load",
            )
            if st.button("Load full-year 2025 analytics test dataset", type="primary", use_container_width=True):
                try:
                    st.session_state["disable_auto_test_bootstrap"] = False
                    m_rows, w_rows = load_builtin_full_year_test_dataset(reset_first=replace_db_with_test)
                    st.success(f"Built-in test dataset loaded: {w_rows} days and {m_rows:,} menu-dish rows. Open Overview or Analytics Lab and use the quick-period buttons to compare 1 week through 1 year.")
                    st.rerun()
                except Exception as e: st.error(str(e))
        st.caption("The full-year 2025 dataset is bundled inside the software, not fetched from the internet. It is synthetic and intentionally contains seasonality, menu-related patterns, attendance variation and operational anomalies for testing.")
        st.markdown("#### Raw-data viewing period")
        dm_start, dm_end, dm_period_label = date_filters("manager", min_d, max_d)
        menu = load_menu(dm_start, dm_end); waste = load_wastage(dm_start, dm_end); q = quality_report(menu, waste)
        st.markdown(f'<span class="pill">Raw data: {dm_period_label}</span>', unsafe_allow_html=True)
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Menu days", q["menu_days"]); m2.metric("Waste days", q["wastage_days"]); m3.metric("Matched days", q["matched_days"]); m4.metric("Completeness", f"{q['completeness_pct']:.0f}%")
        if q["menu_without_wastage"]: st.warning("Menu without wastage: " + ", ".join(map(str, q["menu_without_wastage"][:15])))
        if q["wastage_without_menu"]: st.warning("Wastage without menu: " + ", ".join(map(str, q["wastage_without_menu"][:15])))
        st.markdown("#### Menu data"); st.dataframe(menu, use_container_width=True, hide_index=True)
        st.download_button("Export menu CSV", df_to_csv_bytes(menu), f"menu_export_{dm_start}_to_{dm_end}.csv", "text/csv", disabled=menu.empty)
        st.markdown("#### Wastage data"); st.dataframe(waste, use_container_width=True, hide_index=True)
        st.download_button("Export wastage CSV", df_to_csv_bytes(waste), f"wastage_export_{dm_start}_to_{dm_end}.csv", "text/csv", disabled=waste.empty)

    with tab2:
        c1,c2 = st.columns(2)
        with c1:
            st.markdown("**Menu CSV** — `service_date, meal, dish`")
            up = st.file_uploader("Menu CSV", type=["csv"], key="menu_csv")
            if up is not None:
                try:
                    preview = pd.read_csv(up); st.dataframe(preview.head(20), use_container_width=True)
                    if st.button("Import menu CSV"):
                        import_menu_df(preview); st.success("Imported."); st.rerun()
                except Exception as e: st.error(str(e))
        with c2:
            st.markdown("**Wastage CSV** — `service_date, total_wastage_kg` + optional covers/notes")
            up = st.file_uploader("Wastage CSV", type=["csv"], key="waste_csv")
            if up is not None:
                try:
                    preview = pd.read_csv(up); st.dataframe(preview.head(20), use_container_width=True)
                    if st.button("Import wastage CSV"):
                        import_wastage_df(preview); st.success("Imported."); st.rerun()
                except Exception as e: st.error(str(e))

    with tab3:
        st.subheader("Delete one date")
        d = st.date_input("Date", value=date.today(), key="delete_date")
        confirm = st.checkbox("I understand this deletes both menu and wastage for the selected date.")
        if st.button("Delete selected date", disabled=not confirm):
            st.session_state["disable_auto_test_bootstrap"] = True
            delete_date(d); st.success(f"Deleted {d}."); st.rerun()
        st.divider(); st.subheader("Reset all data")
        phrase = st.text_input("Type RESET ALL DATA to enable")
        if st.button("Reset database", disabled=phrase != "RESET ALL DATA"):
            # Keep the database empty after an intentional reset in this session.
            # On a future cold cloud restart, the demo bootstrap can run again.
            st.session_state["disable_auto_test_bootstrap"] = True
            clear_all(); st.success("All data cleared. Automatic demo reload is paused for this session."); st.rerun()


elif page == "Methodology":
    hero("Methodology, Definitions & Interpretation", "A plain-English guide to every major metric, score and limitation used in WasteLens.")

    st.markdown("### 1. What data the system uses")
    explain("Each service date can contain four meals—Breakfast, Lunch, Snacks and Dinner—with any number of dishes. The wastage table stores one total food-waste value for the whole day, plus optional covers served and operational notes.")
    st.markdown("""
**Core fields**
- **Service date:** the date food was served.
- **Meal:** Breakfast, Lunch, Snacks or Dinner.
- **Dish:** one menu item. Keep names consistent across weeks.
- **Total wastage (kg):** total food discarded across the whole day.
- **Covers served:** number of people/meals served that day. Recommended.
- **Notes:** operational context such as events, quality issues, unexpected attendance or service delays.
    """)

    st.markdown("### 2. Dish association-risk model")
    definition("The score is designed to prioritize investigation. It is not a measurement of how many kilograms of that specific dish were discarded.")
    st.markdown("""
A dish receives a stronger signal when several conditions occur together:
- it appears repeatedly rather than only once,
- daily waste is higher on days when it is served than on days when it is absent,
- it appears on many of the selected high-waste days,
- its presence has a positive statistical correlation with daily waste,
- it receives a larger share of the estimated excess waste above the median baseline,
- and it has enough observations to produce medium or high repetition confidence.

**Priority bands**
- **Low:** weak current association.
- **Watch:** worth observing as more data arrives.
- **High:** strong enough for operational review/trial.
- **Critical:** strongest current investigation priority.
    """)

    st.markdown("### 3. Dish exclusion filter")
    explain("Use the Dish exclusions control in the sidebar when a dish should be ignored for a particular investigation—for example, a compulsory staple, a known data-quality problem, or an item you do not want influencing menu-driver rankings. Exclusion is non-destructive and session-based: it does not delete the dish from stored data.")
    st.markdown("""
- Excluded dishes are removed from dish risk rankings and dish × meal analysis.
- They are also removed from menu complexity, novelty, pair analysis, repeating meal-menu analysis, Pareto attribution and scenario-planner dish choices.
- Raw-data views and exports still contain the dishes.
- **Daily total wastage does not decrease when a dish is excluded**, because the input contains one total wastage figure for the day rather than kilograms wasted for each dish.
- Clear the exclusion list at any time to restore the full analysis.
    """)

    st.markdown("### 4. High-waste days and percentile cutoff")
    explain("The high-waste percentile is configurable in the sidebar. At 75%, the highest quarter of days are treated as high-waste days. Raising the percentile makes the definition stricter; lowering it includes more days.")

    st.markdown("### 5. Trend metrics")
    st.markdown("""
- **Daily waste:** actual kilograms recorded that day.
- **7-day moving average:** average of the latest seven observations, used to smooth daily noise.
- **14-day moving average:** slower trend line useful for confirming sustained improvement or deterioration.
- **Week-over-week summary:** total, average and maximum waste grouped by week.
- **Weekday benchmark variance:** actual waste minus the average for the same weekday. Positive = worse than that weekday's norm; negative = better.
    """)

    st.markdown("### 6. Attendance and efficiency metrics")
    st.markdown("""
- **Kg per cover:** total waste divided by covers served. Lower is generally better.
- **Covers ↔ waste correlation:** whether busier days tend to have more total waste.
- **Attendance-expected waste:** a simple historical linear benchmark based on covers served.
- **Excess vs attendance expectation:** actual waste minus that attendance-based benchmark. Large positive values suggest attendance alone does not explain the high waste.
- **R²:** approximate proportion of waste variation explained by covers in the simple attendance model. It is descriptive, not causal.
    """)

    st.markdown("### 7. Outliers and process control")
    st.markdown("""
- **IQR outlier:** a day far outside the middle spread of the observed data. Useful for spotting extreme days.
- **+2σ warning line:** roughly two standard deviations above the process average; worth reviewing.
- **+3σ control line:** a stronger statistical exception signal. A day beyond this line may represent a special operational cause.

Always check Notes before blaming the menu. Events, spoilage, attendance errors and service disruptions can create extreme waste.
    """)

    st.markdown("### 8. Menu structure analytics")
    st.markdown("""
- **Menu complexity correlation:** relationship between number of distinct dishes and total waste.
- **Meal-specific complexity:** checks whether extra variety in Breakfast, Lunch, Snacks or Dinner is more associated with high total waste.
- **Menu novelty rate:** share of dishes not seen in the previous 14 days. This helps test whether unfamiliar/new menus coincide with more waste.
- **Dish pair analysis:** identifies two dishes that repeatedly appear together on higher-waste days.
- **Repeating meal-menu analysis:** compares recurring combinations within each meal and the total-day waste observed on those dates.
    """)

    st.markdown("### 9. Pareto excess-waste view")
    explain("The system allocates each day's positive excess above the overall median across the dishes served that day. The Pareto chart then shows where this estimated association is concentrated. This is a prioritization device, not direct dish-level weighing.")

    st.markdown("### 10. Scenario Planner")
    explain("The what-if planner combines the historical median, attendance relationship and positive dish associations. Dish effects are deliberately dampened because menu items often appear together. Use the result to plan trials—not as a guaranteed forecast.")

    st.markdown("### 11. Data maturity score")
    st.markdown("""
The 0–100 maturity score rewards:
- more matched menu + wastage days,
- high date completeness,
- consistent cover-count availability,
- and repeated appearances of dishes across the dataset.

**Interpretation:** Early < 40, Developing 40–59, Good 60–79, Strong ≥ 80.
    """)

    st.markdown("### 12. Critical limitation")
    st.warning("Because the input contains one total wastage value for the whole day, WasteLens cannot prove that a particular dish was physically discarded. Dish, pair and menu results are association/prioritization signals. Direct attribution would require meal-level or dish-level discarded kilograms.")

    st.markdown("### 13. Recommended operating workflow")
    st.markdown("""
1. Record menu, total wastage, covers served and notes every day.
2. Review Overview weekly for trend and exceptions.
3. Use Attendance & Efficiency to check whether high totals are simply attendance-driven.
4. Review high-waste/outlier days and operational notes.
5. Shortlist only repeated high-confidence dish/menu signals.
6. Run a controlled production or portion-size trial on a small number of items.
7. Continue collecting data and compare post-change waste with comparable historical days.
    """)

    st.markdown("### 14. Recommended data volume")
    st.info("The app works immediately, but stronger conclusions generally need at least 4–8 weeks of matched data. Record covers served whenever possible and aim for important dishes to appear at least 3–6 times across varying weekdays and attendance levels.")

