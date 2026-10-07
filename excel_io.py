from __future__ import annotations

import io
import re
from typing import Iterable

import pandas as pd

from config import MEALS
from utils import parse_dishes


def _canon(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _rename_by_aliases(df: pd.DataFrame, aliases: dict[str, Iterable[str]]) -> pd.DataFrame:
    work = df.copy()
    lookup = {_canon(c): c for c in work.columns}
    rename = {}
    for target, names in aliases.items():
        for name in names:
            source = lookup.get(_canon(name))
            if source is not None:
                rename[source] = target
                break
    return work.rename(columns=rename)


def normalize_menu_excel(df: pd.DataFrame) -> pd.DataFrame:
    """Accept either long format or a friendly one-row-per-date wide format."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["service_date", "meal", "dish"])

    aliases = {
        "service_date": ["service_date", "date", "menu_date", "day", "service date"],
        "meal": ["meal", "meal_type", "meal type"],
        "dish": ["dish", "dish_name", "dish name", "item", "menu_item", "menu item"],
        "Breakfast": ["breakfast", "break fast"],
        "Lunch": ["lunch"],
        "Snacks": ["snacks", "snack", "evening snacks", "evening snack"],
        "Dinner": ["dinner"],
    }
    work = _rename_by_aliases(df, aliases)

    # Long format: one dish per row.
    if {"service_date", "meal", "dish"}.issubset(work.columns):
        out = work[["service_date", "meal", "dish"]].copy()
        out = out.dropna(subset=["service_date", "meal", "dish"])
        out["service_date"] = pd.to_datetime(out["service_date"], errors="raise").dt.date.astype(str)
        out["meal"] = out["meal"].astype(str).str.strip().str.title()
        invalid = sorted(set(out["meal"]) - set(MEALS))
        if invalid:
            raise ValueError(f"Invalid meal values: {invalid}. Use only {MEALS}.")
        out["dish"] = out["dish"].astype(str).str.strip()
        out = out[out["dish"] != ""]
        return out.drop_duplicates().reset_index(drop=True)

    # Wide format: one row per date, one cell per meal with comma/newline separated dishes.
    if "service_date" not in work.columns:
        raise ValueError("Menu Excel needs a Date/Service Date column.")
    present_meals = [m for m in MEALS if m in work.columns]
    if not present_meals:
        raise ValueError("Menu Excel needs Breakfast, Lunch, Snacks and/or Dinner columns, or long-format Meal and Dish columns.")

    rows = []
    for row in work.itertuples(index=False):
        raw_date = getattr(row, "service_date")
        if pd.isna(raw_date):
            continue
        service_date = pd.to_datetime(raw_date, errors="raise").date().isoformat()
        row_dict = row._asdict()
        for meal in present_meals:
            cell = row_dict.get(meal)
            if pd.isna(cell) if not isinstance(cell, str) else False:
                continue
            for dish in parse_dishes("" if cell is None else str(cell).replace(";", ",")):
                rows.append({"service_date": service_date, "meal": meal, "dish": dish})
    return pd.DataFrame(rows, columns=["service_date", "meal", "dish"]).drop_duplicates().reset_index(drop=True)


def normalize_wastage_excel(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["service_date", "total_wastage_kg", "covers_served", "notes"])

    aliases = {
        "service_date": ["service_date", "date", "wastage_date", "day", "service date"],
        "total_wastage_kg": [
            "total_wastage_kg", "wastage_kg", "waste_kg", "total waste kg", "total wastage kg",
            "wastage (kg)", "waste (kg)", "total waste", "total wastage",
        ],
        "covers_served": ["covers_served", "covers", "people_served", "people served", "persons_served", "headcount"],
        "notes": ["notes", "note", "remarks", "remark", "comments", "comment"],
    }
    work = _rename_by_aliases(df, aliases)
    required = {"service_date", "total_wastage_kg"}
    if not required.issubset(work.columns):
        raise ValueError("Wastage Excel needs Date and Total Wastage (kg) columns.")

    keep = [c for c in ["service_date", "total_wastage_kg", "covers_served", "notes"] if c in work.columns]
    out = work[keep].copy().dropna(subset=["service_date", "total_wastage_kg"])
    out["service_date"] = pd.to_datetime(out["service_date"], errors="raise").dt.date.astype(str)
    out["total_wastage_kg"] = pd.to_numeric(out["total_wastage_kg"], errors="raise")
    if (out["total_wastage_kg"] < 0).any():
        raise ValueError("Wastage cannot be negative.")

    if "covers_served" not in out.columns:
        out["covers_served"] = None
    else:
        out["covers_served"] = pd.to_numeric(out["covers_served"], errors="coerce")
        if (out["covers_served"].dropna() < 0).any():
            raise ValueError("Covers served cannot be negative.")
    if "notes" not in out.columns:
        out["notes"] = ""
    out["notes"] = out["notes"].fillna("").astype(str)
    return out[["service_date", "total_wastage_kg", "covers_served", "notes"]].reset_index(drop=True)


def workbook_sheet_names(uploaded_file) -> list[str]:
    uploaded_file.seek(0)
    names = pd.ExcelFile(uploaded_file, engine="openpyxl").sheet_names
    uploaded_file.seek(0)
    return names


def read_excel_sheet(uploaded_file, sheet_name=0) -> pd.DataFrame:
    uploaded_file.seek(0)
    df = pd.read_excel(uploaded_file, sheet_name=sheet_name, engine="openpyxl")
    uploaded_file.seek(0)
    return df


def read_combined_workbook(uploaded_file) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Auto-detect likely menu and wastage sheets, then normalize both."""
    uploaded_file.seek(0)
    xls = pd.ExcelFile(uploaded_file, engine="openpyxl")
    names = xls.sheet_names
    canon_names = {_canon(n): n for n in names}

    def pick(candidates: list[str]):
        for candidate in candidates:
            if _canon(candidate) in canon_names:
                return canon_names[_canon(candidate)]
        return None

    menu_sheet = pick(["Menu", "Weekly Menu", "Menu Entry", "Food Menu"])
    waste_sheet = pick(["Wastage", "Waste", "Wastage Entry", "Food Wastage"])

    # Fallback: inspect headers if names differ.
    if menu_sheet is None or waste_sheet is None:
        for name in names:
            sample = pd.read_excel(xls, sheet_name=name, nrows=5)
            cols = {_canon(c) for c in sample.columns}
            if menu_sheet is None and ("meal" in cols or "breakfast" in cols or "lunch" in cols):
                menu_sheet = name
            if waste_sheet is None and any(k in cols for k in ["total_wastage_kg", "wastage_kg", "waste_kg", "total_wastage"]):
                waste_sheet = name

    if menu_sheet is None and waste_sheet is None:
        raise ValueError("Could not identify Menu or Wastage sheets. Use the downloadable template for the easiest import.")

    menu = normalize_menu_excel(pd.read_excel(xls, sheet_name=menu_sheet)) if menu_sheet else pd.DataFrame(columns=["service_date", "meal", "dish"])
    waste = normalize_wastage_excel(pd.read_excel(xls, sheet_name=waste_sheet)) if waste_sheet else pd.DataFrame(columns=["service_date", "total_wastage_kg", "covers_served", "notes"])
    uploaded_file.seek(0)
    return menu, waste, {"menu_sheet": menu_sheet, "wastage_sheet": waste_sheet, "all_sheets": names}
