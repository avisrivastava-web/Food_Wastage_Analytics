"""Regression test for the empty-database policy used by the Streamlit auto-demo bootstrap."""
from pathlib import Path
import tempfile

import pandas as pd
import database


def main():
    original_db_path = database.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as tmp:
            database.DB_PATH = Path(tmp) / "bootstrap_test.db"
            database.init_db()
            assert database.database_is_completely_empty(), "Fresh database should be completely empty"
            assert database.database_record_counts() == {"menu_rows": 0, "wastage_rows": 0}

            root = Path(__file__).resolve().parent
            menu = pd.read_csv(root / "data" / "test_menu_full_year_2025.csv")
            waste = pd.read_csv(root / "data" / "test_wastage_full_year_2025.csv")
            database.import_menu_df(menu, replace_existing=True)
            database.import_wastage_df(waste)

            counts = database.database_record_counts()
            assert counts["menu_rows"] == len(menu), counts
            assert counts["wastage_rows"] == len(waste), counts
            assert not database.database_is_completely_empty(), "Loaded demo database must not be considered empty"

            # A partial/user database must also be treated as non-empty so demo data is never auto-merged.
            database.clear_all()
            database.import_menu_df(menu.head(1), replace_existing=True)
            assert not database.database_is_completely_empty(), "Partial menu data must block automatic demo bootstrap"

            database.clear_all()
            database.import_wastage_df(waste.head(1))
            assert not database.database_is_completely_empty(), "Partial wastage data must block automatic demo bootstrap"

            database.clear_all()
            assert database.database_is_completely_empty(), "Explicit clear should return to an empty state"

        print("Automatic demo bootstrap policy tests passed.")
    finally:
        database.DB_PATH = original_db_path


if __name__ == "__main__":
    main()
