import os
import json
import hashlib
import time
import pandas as pd
import shutil

from .crawler_utils import sha256_file, write_crawl_log
from .fetch_usgs import fetch_usgs_recent
from .fetch_ceic import fetch_ceic_events

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
RAW_DIR = os.path.join(DATA_DIR, 'raw')
PROCESSED_DIR = os.path.join(DATA_DIR, 'processed')
SNAPSHOT_DIR = os.path.join(RAW_DIR, 'source_snapshot')
LOG_PATH = os.path.join(DATA_DIR, 'crawl_log.txt')
METADATA_PATH = os.path.join(DATA_DIR, 'source_metadata.json')
PROCESSED_PATH = os.path.join(PROCESSED_DIR, 'earthquake_events_processed.csv')

DATA_PACK_ROOT = os.path.join(os.path.dirname(BASE_DIR), '1_\u6570\u636e\u5305')
DATA_PACK_RAW = os.path.join(DATA_PACK_ROOT, 'raw_data')
DATA_PACK_PROCESSED = os.path.join(DATA_PACK_ROOT, 'processed_data')


def _ensure_dirs():
    for d in [RAW_DIR, PROCESSED_DIR, SNAPSHOT_DIR]:
        os.makedirs(d, exist_ok=True)


def _save_raw_csv(records, source_name):
    ts = time.strftime('%Y%m%d_%H%M%S')
    path = os.path.join(RAW_DIR, 'earthquake_%s_raw_%s.csv' % (source_name, ts))
    df = pd.DataFrame(records)
    df.to_csv(path, index=False, encoding='utf-8-sig')
    return path


def _save_metadata(source_name, source_url, params, http_status, raw_file,
                    record_count, processed_count, data, cached=False,
                    cache_fetch_time=None, request_url=None, snapshot_file=None):
    times = [r.get('event_time_beijing') or r.get('event_time_utc', '') for r in data]
    valid_times = [t for t in times if t]
    raw_rel = None
    snap_rel = None
    if raw_file:
        raw_rel = os.path.relpath(raw_file, DATA_DIR)
    if snapshot_file:
        snap_rel = os.path.relpath(snapshot_file, DATA_DIR)

    meta = {
        'source_name': source_name,
        'source_url': source_url,
        'fetch_time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'query_parameters': params,
        'http_status': http_status,
        'request_url': request_url or source_url,
        'raw_file': raw_rel or '',
        'snapshot_file': snap_rel or '',
        'record_count': record_count,
        'processed_record_count': processed_count,
        'data_start_time': min(valid_times) if valid_times else '',
        'data_end_time': max(valid_times) if valid_times else '',
        'file_sha256': '',
        'cached': cached,
        'cache_fetch_time': cache_fetch_time,
    }
    if raw_file and os.path.exists(raw_file):
        meta['file_sha256'] = sha256_file(raw_file)
    return meta


def _deduplicate(records):
    seen = set()
    unique = []
    for r in records:
        key = (r.get('event_time_utc') or r.get('event_time_beijing', ''),
               r.get('latitude'), r.get('longitude'), r.get('magnitude'))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def _normalize_fields(records):
    for r in records:
        for field in ['magnitude', 'depth_km', 'latitude', 'longitude']:
            if r.get(field) is not None:
                try:
                    r[field] = float(r[field])
                except (ValueError, TypeError):
                    r[field] = None
    return records


def _load_metadata_from_cache(cache_dir):
    meta_path = os.path.join(cache_dir, 'source_metadata.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _fix_metadata_paths_for_data_pack(meta_path):
    """Rewrite raw_file/snapshot_file in 1_数据包/source_metadata.json
       to be relative to 1_数据包/ instead of 2_源码/data/."""
    if not os.path.exists(meta_path):
        return
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    changed = False
    raw = meta.get('raw_file', '')
    snap = meta.get('snapshot_file', '')
    # Paths from code are relative to DATA_DIR (2_源码/data/)
    # In 1_数据包/, files are in raw_data/
    if raw and raw.startswith('raw'):
        meta['raw_file'] = 'raw_data/' + os.path.basename(raw)
        changed = True
    if snap:
        meta['snapshot_file'] = 'raw_data/' + os.path.basename(snap)
        changed = True
    if changed:
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print('  Fixed metadata paths for 1_数据包/')


def update_earthquake_data(force_fetch=True):
    _ensure_dirs()
    log_entries = []
    all_records = []
    sources_used = []
    used_cache = False
    cache_fetch_time = None

    start_ts = time.strftime('%Y-%m-%d %H:%M:%S')
    log_entries.append('=== Start update: %s ===' % start_ts)

    # Step 1: Try CEIC
    print('\n[1] Trying CEIC (China Earthquake Networks Center)...')
    try:
        ceic_records = fetch_ceic_events(snapshot_dir=SNAPSHOT_DIR)
        if ceic_records:
            log_entries.append('CEIC: %d events fetched' % len(ceic_records))
            ceic_records = _normalize_fields(ceic_records)
            _save_raw_csv(ceic_records, 'ceic')
            all_records.extend(ceic_records)
            sources_used.append('CEIC')
        else:
            log_entries.append('CEIC: 0 events (page may be blocked or structure changed)')
    except Exception as e:
        log_entries.append('CEIC: Error - %s' % e)
        print('  CEIC error:', e)

    # Step 2: Try USGS - capture real http_status
    print('\n[2] Trying USGS Earthquake Catalog...')
    usgs_http_status = None
    usgs_request_url = None
    usgs_query_params = None
    usgs_snapshot_file = None
    try:
        result = fetch_usgs_recent(snapshot_dir=SNAPSHOT_DIR)
        usgs_records = result[0]
        usgs_http_status = result[1]
        usgs_request_url = result[2]
        usgs_query_params = result[3]

        if usgs_records:
            log_entries.append('USGS: %d events fetched, HTTP %d' % (len(usgs_records), usgs_http_status))
            usgs_records = _normalize_fields(usgs_records)
            raw_file = _save_raw_csv(usgs_records, 'usgs')
            all_records.extend(usgs_records)
            sources_used.append('USGS')

            if os.path.exists(SNAPSHOT_DIR):
                snapshots = sorted([f for f in os.listdir(SNAPSHOT_DIR) if f.startswith('usgs_raw_')])
                if snapshots:
                    usgs_snapshot_file = os.path.join(SNAPSHOT_DIR, snapshots[-1])
        else:
            log_entries.append('USGS: 0 events returned')
    except Exception as e:
        log_entries.append('USGS: Error - %s' % e)
        print('  USGS error:', e)

    # Step 3: Check if we have any data
    if not all_records:
        print('\n[3] No data from network. Checking cache...')
        log_entries.append('Network fetch returned 0 records total')
        cached_meta = _load_metadata_from_cache(DATA_DIR)
        if cached_meta:
            if cached_meta.get('cached') == False:
                cache_fetch_time = cached_meta.get('fetch_time')
            else:
                cache_fetch_time = cached_meta.get('cache_fetch_time') or cached_meta.get('fetch_time')

        if os.path.exists(PROCESSED_PATH):
            cache_time_str = cache_fetch_time or 'unknown'
            print('  Network fetch failed, using last successful real cache.')
            print('  Cache fetch time:', cache_time_str)
            print('  Cache file:', PROCESSED_PATH)
            log_entries.append('Network fetch failed, using cached data from %s' % cache_time_str)
            log_entries.append('Cache file: %s' % PROCESSED_PATH)
            used_cache = True
            df = pd.read_csv(PROCESSED_PATH, encoding='utf-8-sig')
            all_records = df.to_dict(orient='records')
            print('  Loaded %d records from cache' % len(all_records))
        else:
            log_entries.append('No cached data available - fetch failed completely')
            print('\n  ERROR: No network data and no cache available.')
            print('  Cannot generate fake data. Aborting.')
            write_crawl_log(LOG_PATH, log_entries)
            raise RuntimeError('No earthquake data available from network or cache')

    # Step 4: Deduplicate
    unique_records = _deduplicate(all_records)
    log_entries.append('Before dedup: %d, After dedup: %d' % (len(all_records), len(unique_records)))
    print('\n[4] Deduplication: %d -> %d unique records' % (len(all_records), len(unique_records)))

    # Step 5: Save processed data
    df = pd.DataFrame(unique_records)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    df.to_csv(PROCESSED_PATH, index=False, encoding='utf-8-sig')
    log_entries.append('Processed data saved: %s (%d records)' % (PROCESSED_PATH, len(df)))
    print('\n[5] Processed data saved:', PROCESSED_PATH)

    # Step 6: Save metadata
    if sources_used and not used_cache:
        raw_files_in_dir = [f for f in os.listdir(RAW_DIR) if f.endswith('.csv') and 'usgs' in f]
        raw_file_path = os.path.join(RAW_DIR, sorted(raw_files_in_dir)[-1]) if raw_files_in_dir else None
        meta = _save_metadata(
            source_name='USGS',
            source_url='https://earthquake.usgs.gov/fdsnws/event/1/query',
            params=usgs_query_params or {'format': 'geojson', 'minmagnitude': 2.5},
            http_status=usgs_http_status or 200,
            raw_file=raw_file_path,
            record_count=len(unique_records),
            processed_count=len(unique_records),
            data=unique_records,
            cached=False,
            cache_fetch_time=None,
            request_url=usgs_request_url,
            snapshot_file=usgs_snapshot_file,
        )
        with open(METADATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        log_entries.append('Metadata saved: %s' % METADATA_PATH)
    elif used_cache:
        cached_meta = _load_metadata_from_cache(DATA_DIR)
        meta = {
            'source_name': 'USGS (cache)',
            'source_url': 'https://earthquake.usgs.gov/fdsnws/event/1/query',
            'fetch_time': start_ts,
            'query_parameters': (cached_meta or {}).get('query_parameters', {}),
            'http_status': (cached_meta or {}).get('http_status', 200),
            'raw_file': (cached_meta or {}).get('raw_file', ''),
            'record_count': len(unique_records),
            'processed_record_count': len(unique_records),
            'data_start_time': (cached_meta or {}).get('data_start_time', ''),
            'data_end_time': (cached_meta or {}).get('data_end_time', ''),
            'file_sha256': '',
            'cached': True,
            'cache_fetch_time': cache_fetch_time,
        }
        with open(METADATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        log_entries.append('Metadata (cache mode) saved: %s' % METADATA_PATH)

    # Step 7: Write log (MUST happen before copy so 1_数据包 gets complete log)
    log_entries.append('Sources used: %s' % (', '.join(sources_used) if sources_used else 'cache'))
    log_entries.append('Total records: %d' % len(unique_records))
    log_entries.append('Used cache: %s' % used_cache)
    if used_cache and cache_fetch_time:
        log_entries.append('Original cache fetch time: %s' % cache_fetch_time)
    log_entries.append('=== End update: %s ===' % time.strftime('%Y-%m-%d %H:%M:%S'))
    write_crawl_log(LOG_PATH, log_entries)

    # Step 8: Copy to 1_数据包 (after log write so crawl_log.txt is complete)
    if os.path.exists(DATA_PACK_RAW):
        raw_files = [f for f in os.listdir(RAW_DIR) if f.endswith('.csv')]
        for rf in raw_files:
            shutil.copy2(os.path.join(RAW_DIR, rf), os.path.join(DATA_PACK_RAW, rf))
        if os.path.exists(SNAPSHOT_DIR):
            snaps = [f for f in os.listdir(SNAPSHOT_DIR) if f.endswith('.json')]
            for sf in snaps:
                shutil.copy2(os.path.join(SNAPSHOT_DIR, sf), os.path.join(DATA_PACK_RAW, sf))
    if os.path.exists(DATA_PACK_PROCESSED):
        shutil.copy2(PROCESSED_PATH, os.path.join(DATA_PACK_PROCESSED, 'earthquake_events_processed.csv'))
    if os.path.exists(METADATA_PATH):
        shutil.copy2(METADATA_PATH, os.path.join(DATA_PACK_ROOT, 'source_metadata.json'))
        # Fix metadata paths to be relative to 1_数据包/
        _fix_metadata_paths_for_data_pack(os.path.join(DATA_PACK_ROOT, 'source_metadata.json'))
    if os.path.exists(LOG_PATH):
        shutil.copy2(LOG_PATH, os.path.join(DATA_PACK_ROOT, 'crawl_log.txt'))
    print('  Data synced to 1_数据包/')

    return len(unique_records), sources_used, used_cache


if __name__ == '__main__':
    count, sources, cached = update_earthquake_data()
    print('\nDone. %d earthquake events, sources: %s, cached: %s' % (count, sources, cached))
