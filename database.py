import sqlite3
from contextlib import contextmanager
from datetime import date
from typing import Iterable

import pandas as pd

from config import DB_PATH, DATA_DIR, MEALS


DATA_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS menu_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_date TEXT NOT NULL,
                meal TEXT NOT NULL,
                dish TEXT NOT NULL,
                UNIQUE(service_date, meal, dish)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wastage (
                service_date TEXT PRIMARY KEY,
                total_wastage_kg REAL NOT NULL,
                covers_served INTEGER,
                notes TEXT DEFAULT ''
            )
            """
        )


def _clean_dish(dish: str) -> str:
    return " ".join(str(dish).strip().split())


def save_menu_for_date(service_date: date | str, meal_to_dishes: dict[str, Iterable[str]]):
    d = str(service_date)
    with get_conn() as conn:
        for meal in MEALS:
            conn.execute("DELETE FROM menu_entries WHERE service_date=? AND meal=?", (d, meal))
            dishes = meal_to_dishes.get(meal, [])
            seen = set()
            for dish in dishes:
                clean = _clean_dish(dish)
                key = clean.casefold()
                if clean and key not in seen:
                    conn.execute(
                        "INSERT OR IGNORE INTO menu_entries(service_date, meal, dish) VALUES(?,?,?)",
                        (d, meal, clean),
                    )
                    seen.add(key)


def upsert_wastage(service_date: date | str, total_wastage_kg: float, covers_served=None, notes: str = ""):
    d = str(service_date)
    covers = None if covers_served in (None, "", 0) else int(covers_served)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO wastage(service_date, total_wastage_kg, covers_served, notes)
            VALUES(?,?,?,?)
            ON CONFLICT(service_date) DO UPDATE SET
                total_wastage_kg=excluded.total_wastage_kg,
                covers_served=excluded.covers_served,
                notes=excluded.notes
            """,
            (d, float(total_wastage_kg), covers, notes or ""),
        )


def load_menu(start_date=None, end_date=None) -> pd.DataFrame:
    q = "SELECT service_date, meal, dish FROM menu_entries"
    params = []
    conditions = []
    if start_date is not None:
        conditions.append("service_date >= ?")
        params.append(str(start_date))
    if end_date is not None:
        conditions.append("service_date <= ?")
        params.append(str(end_date))
    if conditions:
        q += " WHERE " + " AND ".join(conditions)
    q += " ORDER BY service_date, CASE meal WHEN 'Breakfast' THEN 1 WHEN 'Lunch' THEN 2 WHEN 'Snacks' THEN 3 ELSE 4 END, dish"
    with get_conn() as conn:
        df = pd.read_sql_query(q, conn, params=params)
    if not df.empty:
        df["service_date"] = pd.to_datetime(df["service_date"])
    return df


def load_wastage(start_date=None, end_date=None) -> pd.DataFrame:
    q = "SELECT service_date, total_wastage_kg, covers_served, notes FROM wastage"
    params = []
    conditions = []
    if start_date is not None:
        conditions.append("service_date >= ?")
        params.append(str(start_date))
    if end_date is not None:
        conditions.append("service_date <= ?")
        params.append(str(end_date))
    if conditions:
        q += " WHERE " + " AND ".join(conditions)
    q += " ORDER BY service_date"
    with get_conn() as conn:
        df = pd.read_sql_query(q, conn, params=params)
    if not df.empty:
        df["service_date"] = pd.to_datetime(df["service_date"])
        df["kg_per_cover"] = df.apply(
            lambda r: r["total_wastage_kg"] / r["covers_served"] if pd.notna(r["covers_served"]) and r["covers_served"] > 0 else float("nan"),
            axis=1,
        )
    return df


def database_record_counts() -> dict[str, int]:
    """Return stored row counts without loading full tables into memory."""
    with get_conn() as conn:
        menu_rows = int(conn.execute("SELECT COUNT(*) FROM menu_entries").fetchone()[0])
        wastage_rows = int(conn.execute("SELECT COUNT(*) FROM wastage").fetchone()[0])
    return {"menu_rows": menu_rows, "wastage_rows": wastage_rows}


def database_is_completely_empty() -> bool:
    """True only when both core tables contain zero rows.

    This intentionally treats a partially populated database as non-empty so
    demo data is never mixed into user-entered/imported records automatically.
    """
    counts = database_record_counts()
    return counts["menu_rows"] == 0 and counts["wastage_rows"] == 0


def delete_date(service_date: date | str):
    d = str(service_date)
    with get_conn() as conn:
        conn.execute("DELETE FROM menu_entries WHERE service_date=?", (d,))
        conn.execute("DELETE FROM wastage WHERE service_date=?", (d,))


def clear_all():
    with get_conn() as conn:
        conn.execute("DELETE FROM menu_entries")
        conn.execute("DELETE FROM wastage")


def import_menu_df(df: pd.DataFrame, replace_existing: bool = False):
    required = {"service_date", "meal", "dish"}
    if not required.issubset(df.columns):
        raise ValueError(f"Menu CSV must contain columns: {', '.join(sorted(required))}")
    work = df.copy()
    work["service_date"] = pd.to_datetime(work["service_date"], errors="raise").dt.date.astype(str)
    work["meal"] = work["meal"].astype(str).str.strip().str.title()
    invalid = sorted(set(work["meal"]) - set(MEALS))
    if invalid:
        raise ValueError(f"Invalid meal values: {invalid}. Use only {MEALS}.")
    work["dish"] = work["dish"].astype(str).map(_clean_dish)
    work = work[work["dish"] != ""]
    with get_conn() as conn:
        if replace_existing:
            for service_date, meal in work[["service_date", "meal"]].drop_duplicates().itertuples(index=False):
                conn.execute("DELETE FROM menu_entries WHERE service_date=? AND meal=?", (service_date, meal))
        for row in work.itertuples(index=False):
            conn.execute(
                "INSERT OR IGNORE INTO menu_entries(service_date, meal, dish) VALUES(?,?,?)",
                (row.service_date, row.meal, row.dish),
            )


def import_wastage_df(df: pd.DataFrame):
    required = {"service_date", "total_wastage_kg"}
    if not required.issubset(df.columns):
        raise ValueError(f"Wastage CSV must contain columns: {', '.join(sorted(required))}")
    work = df.copy()
    work["service_date"] = pd.to_datetime(work["service_date"], errors="raise").dt.date.astype(str)
    work["total_wastage_kg"] = pd.to_numeric(work["total_wastage_kg"], errors="raise")
    if (work["total_wastage_kg"] < 0).any():
        raise ValueError("Wastage cannot be negative.")
    if "covers_served" not in work.columns:
        work["covers_served"] = None
    if "notes" not in work.columns:
        work["notes"] = ""
    for row in work.itertuples(index=False):
        covers = getattr(row, "covers_served", None)
        covers = None if pd.isna(covers) or covers in ("", 0) else int(float(covers))
        upsert_wastage(row.service_date, float(row.total_wastage_kg), covers, str(getattr(row, "notes", "") or ""))
