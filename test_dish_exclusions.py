from pathlib import Path
import pandas as pd

from analytics import apply_dish_exclusions, build_daily_dataset, dish_risk_analysis, pair_risk, menu_signature_analysis


def main():
    root = Path(__file__).resolve().parent
    menu = pd.read_csv(root / "data" / "test_menu_full_year_2025.csv")
    waste = pd.read_csv(root / "data" / "test_wastage_full_year_2025.csv")

    target = "Lauki Kofta"
    assert target in set(menu["dish"]), "Expected test dish is missing from bundled data"

    filtered = apply_dish_exclusions(menu, [target])
    assert target not in set(filtered["dish"]), "Excluded dish remains in filtered menu"
    assert len(filtered) < len(menu), "Filtering did not remove any rows"

    # Filtering is non-destructive and does not alter daily total waste values.
    assert target in set(menu["dish"]), "Original menu was mutated"
    before_daily = build_daily_dataset(menu, waste)
    after_daily = build_daily_dataset(filtered, waste)
    assert before_daily["total_wastage_kg"].sum() == after_daily["total_wastage_kg"].sum()

    risk, _ = dish_risk_analysis(filtered, waste)
    assert target not in set(risk["dish"]), "Excluded dish reappeared in dish-risk output"

    pairs = pair_risk(filtered, waste, min_pair_occurrences=2)
    if not pairs.empty:
        assert not ((pairs["dish_1"] == target) | (pairs["dish_2"] == target)).any(), "Excluded dish reappeared in pair output"

    signatures = menu_signature_analysis(filtered, waste, min_occurrences=2)
    if not signatures.empty:
        assert not signatures["menu_signature"].str.contains(target, regex=False).any(), "Excluded dish reappeared in repeating-menu output"

    # Matching is case-insensitive and whitespace-tolerant.
    filtered2 = apply_dish_exclusions(menu, ["  lauki kofta  "])
    assert target not in set(filtered2["dish"])

    print("Dish exclusion tests passed.")


if __name__ == "__main__":
    main()
