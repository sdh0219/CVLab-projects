from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "outputs"

USGS_SITE = "05464500"
SITE_NAME = "Cedar River at Cedar Rapids, IA"
SITE_LATITUDE = 41.97194549
SITE_LONGITUDE = -91.6671239
START_DATE = "2008-01-01"
END_DATE = "2026-06-10"

RAW_DATA_PATH = DATA_DIR / f"usgs_{USGS_SITE}_instantaneous.json"
RAINFALL_RAW_DATA_PATH = DATA_DIR / "open_meteo_era5_hourly_precipitation.json"
CLEAN_DATA_PATH = DATA_DIR / "cedar_rapids_stage_hourly.csv"

MODEL_PATH = OUTPUT_DIR / "lstm_water_level_model.keras"
METRICS_PATH = OUTPUT_DIR / "evaluation_metrics.csv"
PREDICTION_PATH = OUTPUT_DIR / "prediction_result.csv"
FORECAST_PATH = OUTPUT_DIR / "future_forecast.csv"
PREDICTION_PLOT_PATH = OUTPUT_DIR / "prediction_plot.png"
RISK_PLOT_PATH = OUTPUT_DIR / "risk_plot.png"

WINDOW_SIZE = 72
FORECAST_HORIZON = 24
TEST_RATIO = 0.2
RANDOM_SEED = 42

RISK_THRESHOLDS_FT = {
    "action": 10.0,
    "minor": 12.0,
    "moderate": 14.0,
    "major": 16.0,
}
