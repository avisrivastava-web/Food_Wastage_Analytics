from __future__ import annotations

from datetime import date, timedelta
import pandas as pd


def daterange(start_date: date, end_date: date):
    d = start_date
    while d <= end_date:
        yield d
        d += timedelta(days=1)


def parse_dishes(text: str) -> list[str]:
    if not text:
        return []
    raw = text.replace("\n", ",").split(",")
    out = []
    seen = set()
    for item in raw:
        clean = " ".join(item.strip().split())
        key = clean.casefold()
        if clean and key not in seen:
            out.append(clean)
            seen.add(key)
    return out


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def quick_date_range(preset: str, available_start: date, available_end: date) -> tuple[date, date]:
    """Return an inclusive date range anchored to the latest date in the loaded data.

    Calendar-based presets intentionally use DateOffset so a range ending on
    31-Dec-2025 becomes 01-Dec-2025 for one month, 01-Oct-2025 for three
    months, 01-Jul-2025 for six months and 01-Jan-2025 for one year.
    """
    if available_end < available_start:
        available_start, available_end = available_end, available_start

    anchor = pd.Timestamp(available_end)
    presets = {
        "Recent 1 Week": anchor - pd.Timedelta(days=6),
        "Recent 1 Month": anchor - pd.DateOffset(months=1) + pd.Timedelta(days=1),
        "Recent 3 Months": anchor - pd.DateOffset(months=3) + pd.Timedelta(days=1),
        "Recent 6 Months": anchor - pd.DateOffset(months=6) + pd.Timedelta(days=1),
        "Recent 1 Year": anchor - pd.DateOffset(years=1) + pd.Timedelta(days=1),
        "All Available Data": pd.Timestamp(available_start),
    }
    if preset not in presets:
        raise ValueError(f"Unknown date preset: {preset}")
    start = max(pd.Timestamp(available_start), presets[preset]).date()
    return start, available_end
