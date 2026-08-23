import os
import json
import hashlib
import time
import requests

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2


def get_session():
    sess = requests.Session()
    sess.headers.update({'User-Agent': USER_AGENT})
    return sess


def fetch_with_retry(url, params=None, timeout=REQUEST_TIMEOUT, max_retries=MAX_RETRIES):
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            sess = get_session()
            resp = sess.get(url, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp
            last_err = f'HTTP {resp.status_code}'
        except Exception as e:
            last_err = str(e)
        if attempt < max_retries:
            time.sleep(RETRY_DELAY)
    raise RuntimeError(f'Fetch failed after {max_retries} retries: {last_err}')


def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def save_snapshot(content, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if isinstance(content, (dict, list)):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
    else:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    return filepath


def write_crawl_log(log_path, entries):
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, 'a', encoding='utf-8') as f:
        for entry in entries:
            f.write(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {entry}\n')


def beijing_time_str(utc_time_str):
    try:
        from datetime import datetime, timezone, timedelta
        dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        bj = dt + timedelta(hours=8)
        return bj.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return utc_time_str


def haversine_km(lat1, lon1, lat2, lon2):
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
