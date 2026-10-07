from datetime import date
from utils import quick_date_range


def main():
    start = date(2025, 1, 1)
    end = date(2025, 12, 31)
    expected = {
        "Recent 1 Week": date(2025, 12, 25),
        "Recent 1 Month": date(2025, 12, 1),
        "Recent 3 Months": date(2025, 10, 1),
        "Recent 6 Months": date(2025, 7, 1),
        "Recent 1 Year": date(2025, 1, 1),
        "All Available Data": date(2025, 1, 1),
    }
    for name, expected_start in expected.items():
        actual_start, actual_end = quick_date_range(name, start, end)
        assert actual_start == expected_start, (name, actual_start, expected_start)
        assert actual_end == end, (name, actual_end, end)

    # Range is clipped when less history exists than the requested preset.
    short_start = date(2025, 12, 10)
    actual_start, actual_end = quick_date_range("Recent 1 Month", short_start, end)
    assert actual_start == short_start
    assert actual_end == end
    print("Date preset tests passed.")


if __name__ == "__main__":
    main()
