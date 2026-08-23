import json
import os
import time

from .crawler_utils import fetch_with_retry, save_snapshot, beijing_time_str

USGS_BASE = 'https://earthquake.usgs.gov/fdsnws/event/1/query'
USGS_DEFAULT_PARAMS = {
    'format': 'geojson',
    'starttime': None,
    'endtime': None,
    'minmagnitude': 2.5,
    'maxradiuskm': 2000,
    'latitude': 35,
    'longitude': 105,
    'orderby': 'time',
    'limit': 200,
}


def build_query_params(starttime=None, endtime=None, minmag=2.5, limit=200):
    from datetime import datetime, timezone, timedelta
    if starttime is None:
        starttime = (datetime.now(timezone.utc) - timedelta(days=180)).strftime('%Y-%m-%d')
    if endtime is None:
        endtime = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    params = dict(USGS_DEFAULT_PARAMS)
    params['starttime'] = starttime
    params['endtime'] = endtime
    params['minmagnitude'] = minmag
    params['limit'] = limit
    return params


def fetch_usgs_events(params=None, snapshot_dir=None):
    if params is None:
        params = build_query_params()
    url = USGS_BASE
    print(f'  Fetching USGS: {url}')
    print(f'  Params: {json.dumps(params, ensure_ascii=False)}')

    resp = fetch_with_retry(url, params=params)
    http_status = resp.status_code

    data = resp.json()
    features = data.get('features', [])
    if not features:
        raise RuntimeError(f'USGS returned 0 events for the given params')

    if snapshot_dir:
        ts = time.strftime('%Y%m%d_%H%M%S')
        snap_path = os.path.join(snapshot_dir, f'usgs_raw_{ts}.json')
        save_snapshot(data, snap_path)
        print(f'  Snapshot saved: {snap_path}')

    records = []
    for f in features:
        props = f.get('properties', {})
        coords = f.get('geometry', {}).get('coordinates', [])
        lon, lat, depth = coords[0], coords[1], coords[2] if len(coords) >= 3 else None
        utc_time = props.get('time')
        from datetime import datetime, timezone
        if utc_time:
            utc_dt = datetime.fromtimestamp(utc_time / 1000, tz=timezone.utc)
            time_utc = utc_dt.strftime('%Y-%m-%d %H:%M:%S')
            time_bj = beijing_time_str(utc_dt.isoformat())
        else:
            time_utc = ''
            time_bj = ''

        records.append({
            'event_id': props.get('id') or f.get('id', ''),
            'event_time_utc': time_utc,
            'event_time_beijing': time_bj,
            'latitude': lat,
            'longitude': lon,
            'depth_km': depth,
            'magnitude': props.get('mag'),
            'magnitude_type': props.get('magType', ''),
            'place': props.get('place', ''),
            'event_type': props.get('type', 'earthquake'),
            'source': 'USGS',
            'detail_url': props.get('url', ''),
            'status': props.get('status', ''),
        })

    print(f'  Parsed {len(records)} USGS events')
    return records, http_status, resp.url, params


def fetch_usgs_recent(snapshot_dir=None):
    params = build_query_params(limit=200, minmag=2.5)
    result = fetch_usgs_events(params=params, snapshot_dir=snapshot_dir)
    # Unpack: records, http_status, request_url, query_params
    return result if isinstance(result, tuple) else (result, 200, USGS_BASE, params)
