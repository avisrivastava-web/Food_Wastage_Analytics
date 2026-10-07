from __future__ import annotations

import numpy as np
import pandas as pd



def apply_dish_exclusions(menu: pd.DataFrame, excluded_dishes=None) -> pd.DataFrame:
    """Return menu rows with selected dishes removed from analytical calculations.

    This is intentionally non-destructive: callers receive a filtered copy and the
    underlying database/imported data is never changed. Matching is case-insensitive
    and ignores surrounding whitespace.
    """
    if menu is None or menu.empty or not excluded_dishes:
        return menu.copy() if isinstance(menu, pd.DataFrame) else pd.DataFrame()

    excluded = {str(x).strip().casefold() for x in excluded_dishes if str(x).strip()}
    if not excluded or "dish" not in menu.columns:
        return menu.copy()

    out = menu.copy()
    normalized = out["dish"].fillna("").astype(str).str.strip().str.casefold()
    return out.loc[~normalized.isin(excluded)].copy()

def build_daily_dataset(menu: pd.DataFrame, wastage: pd.DataFrame) -> pd.DataFrame:
    if wastage.empty:
        return pd.DataFrame()

    waste = wastage.copy()
    waste["service_date"] = pd.to_datetime(waste["service_date"])
    waste = waste.sort_values("service_date")
    waste["weekday"] = waste["service_date"].dt.day_name()
    waste["week_start"] = waste["service_date"] - pd.to_timedelta(waste["service_date"].dt.weekday, unit="D")
    waste["rolling_7d_kg"] = waste["total_wastage_kg"].rolling(7, min_periods=1).mean()
    waste["rolling_14d_kg"] = waste["total_wastage_kg"].rolling(14, min_periods=1).mean()

    if menu.empty:
        waste["dish_count"] = 0
        waste["meal_count"] = 0
        waste["menu_text"] = ""
        return waste

    m = menu.copy()
    m["service_date"] = pd.to_datetime(m["service_date"])
    grouped = (
        m.groupby("service_date")
        .agg(
            dish_count=("dish", "nunique"),
            meal_count=("meal", "nunique"),
            menu_text=("dish", lambda x: ", ".join(sorted(set(x)))),
        )
        .reset_index()
    )
    return waste.merge(grouped, on="service_date", how="left").fillna({"dish_count": 0, "meal_count": 0, "menu_text": ""})


def _safe_corr(a: pd.Series, b: pd.Series) -> float:
    if len(a) < 3 or a.nunique() < 2 or b.nunique() < 2:
        return 0.0
    c = a.astype(float).corr(b.astype(float))
    return 0.0 if pd.isna(c) else float(c)


def _rank_percentile(series: pd.Series) -> pd.Series:
    if series.empty:
        return series
    return series.rank(pct=True, method="average").fillna(0.0)


def dish_risk_analysis(
    menu: pd.DataFrame,
    wastage: pd.DataFrame,
    high_waste_quantile: float = 0.75,
    min_occurrences: int = 2,
    risk_cutoff: float = 65,
    use_normalized_if_available: bool = False,
) -> tuple[pd.DataFrame, dict]:
    if menu.empty or wastage.empty:
        return pd.DataFrame(), {}

    m = menu.copy()
    w = wastage.copy()
    m["service_date"] = pd.to_datetime(m["service_date"])
    w["service_date"] = pd.to_datetime(w["service_date"])

    metric = "total_wastage_kg"
    metric_label = "Total wastage (kg)"
    if use_normalized_if_available and "kg_per_cover" in w.columns and w["kg_per_cover"].notna().sum() >= max(3, int(len(w) * 0.5)):
        metric = "kg_per_cover"
        metric_label = "Wastage per cover (kg)"
        w = w[w[metric].notna()].copy()

    valid_dates = sorted(set(m["service_date"]) & set(w["service_date"]))
    if not valid_dates:
        return pd.DataFrame(), {}
    m = m[m["service_date"].isin(valid_dates)].copy()
    w = w[w["service_date"].isin(valid_dates)].copy()

    y = w.set_index("service_date")[metric].sort_index()
    overall_mean = float(y.mean())
    overall_median = float(y.median())
    overall_std = float(y.std(ddof=0)) if len(y) > 1 else 0.0
    high_threshold = float(y.quantile(high_waste_quantile))
    high_dates = set(y[y >= high_threshold].index)

    dishes_by_date = m.groupby("service_date")["dish"].apply(lambda s: sorted(set(s)))
    attributed = {}
    for dt, val in y.items():
        dishes = dishes_by_date.get(dt, [])
        excess = max(float(val) - overall_median, 0.0)
        if dishes and excess > 0:
            share = excess / len(dishes)
            for dish in dishes:
                attributed[dish] = attributed.get(dish, 0.0) + share

    rows = []
    date_index = y.index
    for dish in sorted(m["dish"].dropna().unique(), key=str.casefold):
        present_dates = set(m.loc[m["dish"] == dish, "service_date"])
        presence = pd.Series([1 if d in present_dates else 0 for d in date_index], index=date_index)
        with_vals = y[presence == 1]
        without_vals = y[presence == 0]
        occurrences = int(len(with_vals))
        mean_with = float(with_vals.mean()) if occurrences else 0.0
        mean_without = float(without_vals.mean()) if len(without_vals) else overall_mean
        lift = mean_with - mean_without
        effect_size = lift / overall_std if overall_std > 0 else 0.0
        corr = _safe_corr(presence, y)
        high_hits = len(present_dates & high_dates)
        high_hit_rate = high_hits / occurrences if occurrences else 0.0
        top_day_coverage = high_hits / len(high_dates) if high_dates else 0.0
        meals = sorted(set(m.loc[m["dish"] == dish, "meal"]))
        rows.append({
            "dish": dish,
            "meals": ", ".join(meals),
            "occurrences": occurrences,
            "mean_wastage_when_served": mean_with,
            "mean_wastage_when_not_served": mean_without,
            "lift_vs_without": lift,
            "effect_size": effect_size,
            "correlation": corr,
            "high_waste_hits": high_hits,
            "high_waste_hit_rate": high_hit_rate,
            "top_day_coverage": top_day_coverage,
            "attributed_excess_kg": float(attributed.get(dish, 0.0)),
        })

    result = pd.DataFrame(rows)
    if result.empty:
        return result, {}

    result["mean_rank"] = _rank_percentile(result["mean_wastage_when_served"])
    result["lift_rank"] = _rank_percentile(result["lift_vs_without"].clip(lower=0))
    result["attrib_rank"] = _rank_percentile(result["attributed_excess_kg"].clip(lower=0))
    result["corr_positive"] = result["correlation"].clip(lower=0, upper=1)
    frequency_confidence = np.minimum(result["occurrences"] / max(min_occurrences + 2, 4), 1.0)
    result["risk_score"] = (
        23 * result["mean_rank"]
        + 25 * result["lift_rank"]
        + 22 * result["top_day_coverage"].clip(0, 1)
        + 13 * result["corr_positive"]
        + 10 * result["attrib_rank"]
        + 7 * frequency_confidence
    ).round(1)
    result["confidence"] = result["occurrences"].apply(lambda n: "High" if n >= 6 else ("Medium" if n >= 3 else "Low"))
    result["flagged"] = (
        (result["risk_score"] >= risk_cutoff)
        & (result["occurrences"] >= min_occurrences)
        & (result["mean_wastage_when_served"] > overall_mean)
        & (result["lift_vs_without"] > 0)
    )
    result["priority"] = pd.cut(
        result["risk_score"], bins=[-1, 49.999, 64.999, 79.999, 1000], labels=["Low", "Watch", "High", "Critical"]
    ).astype(str)

    result = result.sort_values(["risk_score", "occurrences"], ascending=[False, False]).reset_index(drop=True)
    keep = [
        "dish", "meals", "occurrences", "risk_score", "priority", "confidence", "flagged",
        "mean_wastage_when_served", "mean_wastage_when_not_served", "lift_vs_without", "effect_size",
        "correlation", "high_waste_hits", "high_waste_hit_rate", "top_day_coverage", "attributed_excess_kg"
    ]
    result = result[keep]

    meta = {
        "metric": metric,
        "metric_label": metric_label,
        "overall_mean": overall_mean,
        "overall_median": overall_median,
        "high_threshold": high_threshold,
        "high_waste_days": len(high_dates),
        "analysis_days": len(valid_dates),
        "quantile": high_waste_quantile,
    }
    return result, meta


def dish_meal_risk(menu: pd.DataFrame, wastage: pd.DataFrame, high_waste_quantile: float = 0.75) -> pd.DataFrame:
    if menu.empty or wastage.empty:
        return pd.DataFrame()
    m = menu.copy(); w = wastage.copy()
    m["service_date"] = pd.to_datetime(m["service_date"]); w["service_date"] = pd.to_datetime(w["service_date"])
    y = w.set_index("service_date")["total_wastage_kg"]
    valid_dates = sorted(set(m["service_date"]) & set(y.index))
    if not valid_dates:
        return pd.DataFrame()
    y = y.loc[valid_dates]
    high_threshold = float(y.quantile(high_waste_quantile)); high_dates = set(y[y >= high_threshold].index)
    rows = []
    for (meal, dish), g in m.groupby(["meal", "dish"]):
        dates = set(g["service_date"]) & set(valid_dates)
        vals = y.loc[list(dates)] if dates else pd.Series(dtype=float)
        hits = len(dates & high_dates)
        rows.append({
            "meal": meal, "dish": dish, "occurrences": len(dates),
            "mean_wastage_kg": float(vals.mean()) if len(vals) else 0.0,
            "high_waste_hits": hits, "high_waste_rate": hits / len(dates) if dates else 0.0,
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out["context_score"] = (60 * _rank_percentile(out["mean_wastage_kg"]) + 40 * out["high_waste_rate"].clip(0, 1)).round(1)
        out = out.sort_values("context_score", ascending=False)
    return out


def pair_risk(menu: pd.DataFrame, wastage: pd.DataFrame, min_pair_occurrences: int = 2) -> pd.DataFrame:
    if menu.empty or wastage.empty:
        return pd.DataFrame()
    m = menu.copy(); w = wastage.copy()
    m["service_date"] = pd.to_datetime(m["service_date"]); w["service_date"] = pd.to_datetime(w["service_date"])
    y = w.set_index("service_date")["total_wastage_kg"]
    valid_dates = sorted(set(m["service_date"]) & set(y.index))
    if not valid_dates:
        return pd.DataFrame()
    by_date = m.groupby("service_date")["dish"].apply(lambda s: sorted(set(s)))
    stats = {}
    for dt in valid_dates:
        dishes = by_date.get(dt, []); val = float(y.loc[dt])
        for i in range(len(dishes)):
            for j in range(i + 1, len(dishes)):
                stats.setdefault((dishes[i], dishes[j]), []).append(val)
    rows = []
    for pair, vals in stats.items():
        if len(vals) >= min_pair_occurrences:
            rows.append({"dish_1": pair[0], "dish_2": pair[1], "occurrences": len(vals), "mean_wastage_kg": float(np.mean(vals)), "max_wastage_kg": float(np.max(vals))})
    out = pd.DataFrame(rows)
    if not out.empty:
        out["pair_score"] = (100 * _rank_percentile(out["mean_wastage_kg"])).round(1)
        out = out.sort_values(["pair_score", "occurrences"], ascending=[False, False])
    return out


def weekly_summary(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    d = daily.copy(); d["week_start"] = pd.to_datetime(d["week_start"])
    agg = {"total_wastage_kg": ["sum", "mean", "max"], "service_date": "count"}
    if "kg_per_cover" in d.columns:
        agg["kg_per_cover"] = "mean"
    out = d.groupby("week_start").agg(agg)
    out.columns = ["total_waste_kg", "avg_daily_waste_kg", "max_day_kg", "recorded_days"] + (["avg_kg_per_cover"] if "kg_per_cover" in d.columns else [])
    return out.reset_index()


def anomaly_days(daily: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    if daily.empty:
        return pd.DataFrame(), {}
    d = daily.copy().sort_values("service_date")
    y = d["total_wastage_kg"].astype(float)
    q1, q3 = float(y.quantile(.25)), float(y.quantile(.75)); iqr = q3 - q1
    upper = q3 + 1.5 * iqr if iqr > 0 else float(y.mean() + 2 * y.std(ddof=0))
    lower = max(0.0, q1 - 1.5 * iqr) if iqr > 0 else 0.0
    d["is_high_anomaly"] = d["total_wastage_kg"] > upper
    d["is_low_anomaly"] = d["total_wastage_kg"] < lower
    d["deviation_from_7d"] = d["total_wastage_kg"] - d["rolling_7d_kg"]
    return d[d["is_high_anomaly"] | d["is_low_anomaly"]].copy(), {"upper": upper, "lower": lower, "q1": q1, "q3": q3}


def trend_summary(daily: pd.DataFrame, window: int = 7) -> dict:
    if daily.empty:
        return {}
    y = daily.sort_values("service_date")["total_wastage_kg"].astype(float)
    n = len(y)
    recent = float(y.tail(min(window, n)).mean())
    prev = float(y.iloc[max(0, n - 2 * window):max(0, n - window)].mean()) if n > window else np.nan
    change_pct = ((recent - prev) / prev * 100.0) if pd.notna(prev) and prev != 0 else np.nan
    slope = float(np.polyfit(np.arange(n), y.values, 1)[0]) if n >= 3 else 0.0
    return {"recent_avg": recent, "previous_avg": prev, "change_pct": change_pct, "slope_per_day": slope}


def menu_complexity_analysis(menu: pd.DataFrame, wastage: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    if menu.empty or wastage.empty:
        return pd.DataFrame(), 0.0
    m = menu.copy(); w = wastage.copy()
    m["service_date"] = pd.to_datetime(m["service_date"]); w["service_date"] = pd.to_datetime(w["service_date"])
    c = m.groupby("service_date").agg(dish_count=("dish", "nunique"), meal_count=("meal", "nunique")).reset_index()
    out = w.merge(c, on="service_date", how="inner")
    corr = _safe_corr(out["dish_count"], out["total_wastage_kg"]) if len(out) else 0.0
    return out, corr


def weekday_summary(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    out = daily.groupby("weekday", as_index=False).agg(
        avg_wastage_kg=("total_wastage_kg", "mean"),
        total_wastage_kg=("total_wastage_kg", "sum"),
        days=("total_wastage_kg", "size"),
        max_wastage_kg=("total_wastage_kg", "max"),
    )
    out["weekday"] = pd.Categorical(out["weekday"], categories=order, ordered=True)
    return out.sort_values("weekday")


def high_waste_day_details(menu: pd.DataFrame, wastage: pd.DataFrame, quantile: float = .75) -> pd.DataFrame:
    if wastage.empty:
        return pd.DataFrame()
    w = wastage.copy(); w["service_date"] = pd.to_datetime(w["service_date"])
    threshold = float(w["total_wastage_kg"].quantile(quantile))
    top = w[w["total_wastage_kg"] >= threshold].copy()
    if menu.empty:
        top["menu"] = ""
        return top.sort_values("total_wastage_kg", ascending=False)
    m = menu.copy(); m["service_date"] = pd.to_datetime(m["service_date"])
    menu_text = m.groupby("service_date").apply(lambda g: " | ".join(f"{meal}: {', '.join(sorted(set(g.loc[g['meal']==meal, 'dish'])))}" for meal in ["Breakfast", "Lunch", "Snacks", "Dinner"] if (g["meal"] == meal).any()), include_groups=False)
    top["menu"] = top["service_date"].map(menu_text).fillna("")
    return top.sort_values("total_wastage_kg", ascending=False)


def quality_report(menu: pd.DataFrame, wastage: pd.DataFrame) -> dict:
    menu_dates = set(pd.to_datetime(menu["service_date"]).dt.date) if not menu.empty else set()
    waste_dates = set(pd.to_datetime(wastage["service_date"]).dt.date) if not wastage.empty else set()
    union = menu_dates | waste_dates
    matched = menu_dates & waste_dates
    return {
        "menu_days": len(menu_dates), "wastage_days": len(waste_dates), "matched_days": len(matched),
        "menu_without_wastage": sorted(menu_dates - waste_dates), "wastage_without_menu": sorted(waste_dates - menu_dates),
        "completeness_pct": (100.0 * len(matched) / len(union)) if union else 0.0,
    }


def executive_insights(daily: pd.DataFrame, risk: pd.DataFrame, menu: pd.DataFrame, waste: pd.DataFrame) -> list[str]:
    insights = []
    if daily.empty:
        return ["Add wastage records to generate automated insights."]
    t = trend_summary(daily)
    if pd.notna(t.get("change_pct", np.nan)):
        direction = "higher" if t["change_pct"] > 0 else "lower"
        insights.append(f"Recent average wastage is {abs(t['change_pct']):.1f}% {direction} than the preceding comparable period.")
    weekdays = weekday_summary(daily)
    if not weekdays.empty:
        worst = weekdays.loc[weekdays["avg_wastage_kg"].idxmax()]
        insights.append(f"{worst['weekday']} currently has the highest average recorded wastage at {worst['avg_wastage_kg']:.1f} kg.")
    complexity, corr = menu_complexity_analysis(menu, waste)
    if len(complexity) >= 5 and abs(corr) >= .25:
        relationship = "increases" if corr > 0 else "decreases"
        insights.append(f"Menu size shows a {abs(corr):.2f} correlation with waste; waste tends to {relationship} on days with more distinct dishes. Treat this as association, not causation.")
    if not risk.empty:
        flagged = risk[risk["flagged"]]
        if not flagged.empty:
            top = flagged.iloc[0]
            insights.append(f"{top['dish']} is the highest-priority dish signal (risk {top['risk_score']:.0f}/100, served {int(top['occurrences'])} times, lift {top['lift_vs_without']:+.1f} kg).")
        else:
            insights.append("No dish currently crosses the configured flag threshold; continue collecting repeated menu cycles before making strong dish-level conclusions.")
    return insights[:5]


def recommendations(dish_df: pd.DataFrame) -> list[str]:
    if dish_df.empty:
        return ["Collect menu and wastage data for several matched days before interpreting dish risk."]
    flagged = dish_df[dish_df["flagged"]].head(5)
    if flagged.empty:
        names = ", ".join(dish_df.head(3)["dish"].tolist())
        return [f"No dish crosses the current flag threshold. Keep collecting data; current highest-risk dishes are {names}.", "Use at least 3–5 appearances per dish before making major menu changes."]
    recs = []
    for r in flagged.itertuples(index=False):
        recs.append(f"{r.dish}: review batch size, portion size, acceptance and service timing. It appears {r.occurrences} time(s), risk {r.risk_score:.0f}/100, and is associated with {r.lift_vs_without:+.2f} kg versus days when absent.")
    return recs


def data_maturity_score(menu: pd.DataFrame, wastage: pd.DataFrame) -> dict:
    """Score how reliable the current dataset is for menu-driver analytics (0-100)."""
    q = quality_report(menu, wastage)
    matched = q["matched_days"]
    matched_points = min(matched / 56.0, 1.0) * 35
    completeness_points = min(q["completeness_pct"] / 100.0, 1.0) * 25

    cover_coverage = 0.0
    if not wastage.empty and "covers_served" in wastage.columns:
        cover_coverage = float(wastage["covers_served"].notna().mean())
    cover_points = cover_coverage * 20

    repeat_ratio = 0.0
    median_repeats = 0.0
    if not menu.empty:
        repeats = menu.groupby("dish")["service_date"].nunique()
        if len(repeats):
            repeat_ratio = float((repeats >= 3).mean())
            median_repeats = float(repeats.median())
    repeat_points = repeat_ratio * 20

    score = round(matched_points + completeness_points + cover_points + repeat_points, 1)
    if score >= 80:
        label = "Strong"
    elif score >= 60:
        label = "Good"
    elif score >= 40:
        label = "Developing"
    else:
        label = "Early"
    return {
        "score": score,
        "label": label,
        "matched_days": matched,
        "completeness_pct": q["completeness_pct"],
        "cover_coverage_pct": cover_coverage * 100,
        "repeat_ratio_pct": repeat_ratio * 100,
        "median_dish_repeats": median_repeats,
    }


def cover_relationship(wastage: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Measure how much total waste changes with covers served and flag excess vs attendance expectation."""
    if wastage.empty or "covers_served" not in wastage.columns:
        return pd.DataFrame(), {}
    d = wastage.copy()
    d["service_date"] = pd.to_datetime(d["service_date"])
    d = d[d["covers_served"].notna() & (pd.to_numeric(d["covers_served"], errors="coerce") > 0)].copy()
    if d.empty:
        return d, {}
    d["covers_served"] = pd.to_numeric(d["covers_served"], errors="coerce")
    d["total_wastage_kg"] = pd.to_numeric(d["total_wastage_kg"], errors="coerce")
    d["kg_per_cover"] = d["total_wastage_kg"] / d["covers_served"]

    corr = _safe_corr(d["covers_served"], d["total_wastage_kg"])
    slope = intercept = r2 = np.nan
    if len(d) >= 3 and d["covers_served"].nunique() >= 2:
        slope, intercept = np.polyfit(d["covers_served"], d["total_wastage_kg"], 1)
        d["attendance_expected_kg"] = intercept + slope * d["covers_served"]
        ss_res = float(((d["total_wastage_kg"] - d["attendance_expected_kg"]) ** 2).sum())
        ss_tot = float(((d["total_wastage_kg"] - d["total_wastage_kg"].mean()) ** 2).sum())
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    else:
        d["attendance_expected_kg"] = d["total_wastage_kg"].mean()
    d["excess_vs_attendance_kg"] = d["total_wastage_kg"] - d["attendance_expected_kg"]
    return d, {
        "days": len(d),
        "correlation": float(corr),
        "slope_kg_per_extra_cover": float(slope) if pd.notna(slope) else np.nan,
        "intercept": float(intercept) if pd.notna(intercept) else np.nan,
        "r2": float(r2) if pd.notna(r2) else np.nan,
        "avg_kg_per_cover": float(d["kg_per_cover"].mean()),
        "median_kg_per_cover": float(d["kg_per_cover"].median()),
    }


def weekday_benchmark(daily: pd.DataFrame) -> pd.DataFrame:
    """Expected waste benchmark for each date based on the average for its weekday."""
    if daily.empty:
        return pd.DataFrame()
    d = daily.copy()
    means = d.groupby("weekday")["total_wastage_kg"].mean().to_dict()
    d["weekday_expected_kg"] = d["weekday"].map(means).astype(float)
    d["vs_weekday_benchmark_kg"] = d["total_wastage_kg"] - d["weekday_expected_kg"]
    d["vs_weekday_benchmark_pct"] = np.where(
        d["weekday_expected_kg"] > 0,
        d["vs_weekday_benchmark_kg"] / d["weekday_expected_kg"] * 100,
        np.nan,
    )
    return d


def control_chart_data(daily: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Simple process-control view using mean +/- 2 and 3 standard deviations."""
    if daily.empty:
        return pd.DataFrame(), {}
    d = daily.copy().sort_values("service_date")
    y = d["total_wastage_kg"].astype(float)
    mean = float(y.mean())
    std = float(y.std(ddof=0)) if len(y) > 1 else 0.0
    d["process_mean"] = mean
    d["warning_upper"] = mean + 2 * std
    d["warning_lower"] = max(0.0, mean - 2 * std)
    d["control_upper"] = mean + 3 * std
    d["control_lower"] = max(0.0, mean - 3 * std)
    d["process_z"] = (y - mean) / std if std > 0 else 0.0
    d["outside_control"] = (d["total_wastage_kg"] > d["control_upper"]) | (d["total_wastage_kg"] < d["control_lower"])
    d["warning_signal"] = (d["process_z"].abs() >= 2) & (~d["outside_control"])
    return d, {
        "mean": mean,
        "std": std,
        "warning_upper": mean + 2 * std,
        "control_upper": mean + 3 * std,
        "outside_control_days": int(d["outside_control"].sum()),
        "warning_days": int(d["warning_signal"].sum()),
    }


def meal_complexity_summary(menu: pd.DataFrame, wastage: pd.DataFrame, high_quantile: float = 0.75) -> pd.DataFrame:
    """Relate number of distinct dishes in each meal to the day's total waste."""
    if menu.empty or wastage.empty:
        return pd.DataFrame()
    m = menu.copy(); w = wastage.copy()
    m["service_date"] = pd.to_datetime(m["service_date"]); w["service_date"] = pd.to_datetime(w["service_date"])
    counts = m.groupby(["service_date", "meal"])["dish"].nunique().unstack(fill_value=0)
    merged = w.set_index("service_date")[["total_wastage_kg"]].join(counts, how="inner")
    if merged.empty:
        return pd.DataFrame()
    threshold = float(merged["total_wastage_kg"].quantile(high_quantile))
    merged["is_high"] = merged["total_wastage_kg"] >= threshold
    rows = []
    for meal in ["Breakfast", "Lunch", "Snacks", "Dinner"]:
        if meal not in merged.columns:
            continue
        rows.append({
            "meal": meal,
            "avg_distinct_dishes": float(merged[meal].mean()),
            "correlation_with_daily_waste": _safe_corr(merged[meal], merged["total_wastage_kg"]),
            "avg_dishes_on_high_waste_days": float(merged.loc[merged["is_high"], meal].mean()) if merged["is_high"].any() else 0.0,
            "avg_dishes_on_other_days": float(merged.loc[~merged["is_high"], meal].mean()) if (~merged["is_high"]).any() else 0.0,
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out["complexity_lift_on_high_days"] = out["avg_dishes_on_high_waste_days"] - out["avg_dishes_on_other_days"]
        out = out.sort_values("correlation_with_daily_waste", ascending=False)
    return out


def menu_signature_analysis(menu: pd.DataFrame, wastage: pd.DataFrame, min_occurrences: int = 2) -> pd.DataFrame:
    """Find repeating meal-menu combinations and compare the total waste on days they are served."""
    if menu.empty or wastage.empty:
        return pd.DataFrame()
    m = menu.copy(); w = wastage.copy()
    m["service_date"] = pd.to_datetime(m["service_date"]); w["service_date"] = pd.to_datetime(w["service_date"])
    signatures = (
        m.groupby(["service_date", "meal"])["dish"]
        .apply(lambda s: " | ".join(sorted(set(map(str, s)))))
        .rename("menu_signature")
        .reset_index()
    )
    d = signatures.merge(w[["service_date", "total_wastage_kg"]], on="service_date", how="inner")
    if d.empty:
        return pd.DataFrame()
    out = d.groupby(["meal", "menu_signature"], as_index=False).agg(
        occurrences=("service_date", "size"),
        avg_wastage_kg=("total_wastage_kg", "mean"),
        min_wastage_kg=("total_wastage_kg", "min"),
        max_wastage_kg=("total_wastage_kg", "max"),
    )
    out = out[out["occurrences"] >= min_occurrences].copy()
    if not out.empty:
        # Rank within meal so breakfast combinations are compared with breakfast alternatives, etc.
        out["menu_score"] = out.groupby("meal")["avg_wastage_kg"].rank(pct=True, method="average").mul(100).round(1)
        out = out.sort_values(["menu_score", "occurrences"], ascending=[False, False])
    return out


def menu_novelty_analysis(menu: pd.DataFrame, wastage: pd.DataFrame, lookback_days: int = 14) -> tuple[pd.DataFrame, float]:
    """Compare waste with the share of dishes not seen in the prior lookback window."""
    if menu.empty or wastage.empty:
        return pd.DataFrame(), 0.0
    m = menu.copy(); w = wastage.copy()
    m["service_date"] = pd.to_datetime(m["service_date"]); w["service_date"] = pd.to_datetime(w["service_date"])
    by_date = m.groupby("service_date")["dish"].apply(lambda s: set(map(str, s))).sort_index()
    rows = []
    dates = list(by_date.index)
    for dt in dates:
        current = by_date.loc[dt]
        prior_sets = by_date.loc[(by_date.index < dt) & (by_date.index >= dt - pd.Timedelta(days=lookback_days))]
        previous = set().union(*prior_sets.tolist()) if len(prior_sets) else set()
        new_count = len(current - previous)
        total = len(current)
        rows.append({"service_date": dt, "dish_count": total, "new_dish_count": new_count, "novelty_rate": new_count / total if total else 0.0})
    out = pd.DataFrame(rows).merge(w[["service_date", "total_wastage_kg"]], on="service_date", how="inner")
    corr = _safe_corr(out["novelty_rate"], out["total_wastage_kg"]) if len(out) else 0.0
    return out, corr


def waste_stability_summary(daily: pd.DataFrame) -> dict:
    if daily.empty:
        return {}
    y = daily["total_wastage_kg"].astype(float)
    mean = float(y.mean())
    std = float(y.std(ddof=0)) if len(y) > 1 else 0.0
    cv = std / mean if mean > 0 else 0.0
    q25, q75 = float(y.quantile(.25)), float(y.quantile(.75))
    return {
        "mean": mean,
        "std": std,
        "cv": cv,
        "q25": q25,
        "q75": q75,
        "low_days": int((y <= q25).sum()),
        "typical_days": int(((y > q25) & (y < q75)).sum()),
        "high_days": int((y >= q75).sum()),
    }


def pareto_dish_excess(risk: pd.DataFrame) -> pd.DataFrame:
    """Rank dishes by estimated allocated excess waste and calculate cumulative share."""
    if risk.empty or "attributed_excess_kg" not in risk.columns:
        return pd.DataFrame()
    cols = ["dish", "occurrences", "risk_score", "priority", "attributed_excess_kg"]
    if "lift_vs_without" in risk.columns:
        cols.append("lift_vs_without")
    out = risk[cols].copy()
    # Exclude dishes whose average waste is not higher when present; this prevents ubiquitous
    # staples from dominating the Pareto simply because they appear on many days.
    if "lift_vs_without" in out.columns:
        out = out[out["lift_vs_without"] > 0]
    out = out[out["attributed_excess_kg"] > 0].sort_values("attributed_excess_kg", ascending=False)
    total = float(out["attributed_excess_kg"].sum())
    out["share_of_attributed_excess_pct"] = out["attributed_excess_kg"] / total * 100 if total > 0 else 0.0
    out["cumulative_share_pct"] = out["share_of_attributed_excess_pct"].cumsum()
    return out


def scenario_waste_estimate(selected_dishes: list[str], covers: int | None, risk: pd.DataFrame, wastage: pd.DataFrame) -> dict:
    """Association-based what-if estimate; designed for planning, not causal prediction."""
    if wastage.empty:
        return {}
    baseline = float(wastage["total_wastage_kg"].median())
    attendance_adjustment = 0.0
    cover_df, cover_meta = cover_relationship(wastage)
    if covers and cover_meta and pd.notna(cover_meta.get("slope_kg_per_extra_cover", np.nan)):
        typical_covers = float(cover_df["covers_served"].median())
        attendance_adjustment = (covers - typical_covers) * float(cover_meta["slope_kg_per_extra_cover"])
    dish_adjustments = []
    if not risk.empty:
        rmap = risk.set_index("dish")
        for dish in selected_dishes:
            if dish in rmap.index:
                row = rmap.loc[dish]
                lift = max(float(row["lift_vs_without"]), 0.0)
                confidence_weight = {"Low": 0.25, "Medium": 0.5, "High": 0.75}.get(str(row["confidence"]), 0.4)
                adj = lift * confidence_weight
                dish_adjustments.append((dish, adj))
    # Damp overlapping dish effects to avoid simply summing correlated signals.
    dish_total = sum(v for _, v in dish_adjustments) * (0.55 if len(dish_adjustments) > 1 else 0.7)
    estimate = max(0.0, baseline + attendance_adjustment + dish_total)
    variability = float(wastage["total_wastage_kg"].std(ddof=0)) if len(wastage) > 1 else baseline * 0.15
    return {
        "baseline_kg": baseline,
        "attendance_adjustment_kg": attendance_adjustment,
        "dish_adjustment_kg": dish_total,
        "estimated_waste_kg": estimate,
        "low_range_kg": max(0.0, estimate - variability),
        "high_range_kg": estimate + variability,
        "dish_adjustments": dish_adjustments,
    }
