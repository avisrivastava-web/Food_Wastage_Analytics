from pathlib import Path

APP_NAME = "Food Wastage Analytics"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TEMPLATE_DIR = BASE_DIR / "templates"
TEST_DATA_DIR = BASE_DIR / "test_dataset"
DB_PATH = DATA_DIR / "food_wastage.db"
MEALS = ["Breakfast", "Lunch", "Snacks", "Dinner"]
DEFAULT_HIGH_WASTE_QUANTILE = 0.75
DEFAULT_RISK_CUTOFF = 65
DEFAULT_MIN_OCCURRENCES = 2
AUTO_LOAD_TEST_DATA_IF_EMPTY = True
