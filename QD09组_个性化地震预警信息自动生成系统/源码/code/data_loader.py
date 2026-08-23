import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')
PROCESSED_PATH = os.path.join(PROCESSED_DIR, 'earthquake_events_processed.csv')
RAW_DIR = os.path.join(BASE_DIR, 'data', 'raw')


def load_earthquake_events(path=None):
    if path is None:
        path = PROCESSED_PATH
    if not os.path.exists(path):
        raw_files = [f for f in os.listdir(RAW_DIR) if f.endswith('.csv') and 'usgs' in f]
        if raw_files:
            latest = sorted(raw_files)[-1]
            path = os.path.join(RAW_DIR, latest)
        else:
            return pd.DataFrame()
    return pd.read_csv(path, encoding='utf-8-sig')


def load_latest_events(limit=200):
    df = load_earthquake_events()
    if df.empty:
        return df
    if 'event_time_utc' in df.columns:
        df = df.sort_values('event_time_utc', ascending=False)
    return df.head(limit).reset_index(drop=True)


def save_processed_data(df, path=None):
    if path is None:
        path = PROCESSED_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, encoding='utf-8-sig')
    return path
