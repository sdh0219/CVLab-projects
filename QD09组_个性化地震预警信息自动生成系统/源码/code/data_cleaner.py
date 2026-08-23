import pandas as pd


def clean_earthquake_data(df):
    if df.empty:
        return df
    df = df.copy()
    df.columns = df.columns.str.strip()

    numeric_cols = ['magnitude', 'depth_km', 'latitude', 'longitude']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    if 'event_time_utc' in df.columns:
        df['event_time_utc'] = pd.to_datetime(df['event_time_utc'], errors='coerce')
    if 'event_time_beijing' in df.columns:
        df['event_time_beijing'] = pd.to_datetime(df['event_time_beijing'], errors='coerce')

    df = df.dropna(subset=['magnitude', 'latitude', 'longitude'])
    df = df[df['magnitude'] >= 0]

    df = df.drop_duplicates(subset=['event_time_utc', 'latitude', 'longitude', 'magnitude'])

    for col in ['place', 'source', 'event_id']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df.reset_index(drop=True)
