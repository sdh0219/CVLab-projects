import json
import os
import re
import time

from .crawler_utils import fetch_with_retry, save_snapshot

CEIC_URL = 'https://www.ceic.ac.cn/history'
CEIC_AJAX_URL = 'https://www.ceic.ac.cn/ajax/speedsearch'


def fetch_ceic_events(snapshot_dir=None):
    print('  Attempting CEIC (China Earthquake Networks Center)...')
    print(f'  URL: {CEIC_URL}')

    try:
        resp = fetch_with_retry(CEIC_URL, timeout=20)
        html = resp.text

        if snapshot_dir:
            ts = time.strftime('%Y%m%d_%H%M%S')
            save_snapshot(html, os.path.join(snapshot_dir, f'ceic_page_{ts}.html'))

        records = _parse_ceic_html(html)
        if records:
            print(f'  Parsed {len(records)} events from CEIC page')
            return records

        print('  No events found in CEIC page HTML')
        return []
    except Exception as e:
        print(f'  CEIC fetch failed: {e}')
        print('  CEIC may have anti-scraping protections or page structure changes')
        return []


def _parse_ceic_html(html):
    records = []

    table_patterns = [
        r'<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?</tr>',
    ]

    for pattern in table_patterns:
        matches = re.findall(pattern, html, re.DOTALL)
        for m in matches:
            cells = [re.sub(r'<[^>]+>', '', c).strip() for c in m]
            if len(cells) >= 6:
                try:
                    lat = float(_extract_num(cells[1]))
                    lon = float(_extract_num(cells[2]))
                    depth = float(_extract_num(cells[3]))
                    mag = float(_extract_num(cells[4]))
                except (ValueError, TypeError):
                    continue
                records.append({
                    'event_id': f'ceic_{len(records)}',
                    'event_time_beijing': cells[0],
                    'event_time_utc': '',
                    'latitude': lat,
                    'longitude': lon,
                    'depth_km': depth,
                    'magnitude': mag,
                    'magnitude_type': 'M',
                    'place': cells[5] if len(cells) > 5 else '',
                    'event_type': 'earthquake',
                    'source': 'CEIC',
                    'detail_url': CEIC_URL,
                    'status': 'manual',
                })

    if not records:
        json_patterns = re.findall(r'var\s+data\s*=\s*(\[.*?\])\s*;', html, re.DOTALL)
        for jp in json_patterns:
            try:
                items = json.loads(jp)
                for item in items:
                    records.append({
                        'event_id': f'ceic_{len(records)}',
                        'event_time_beijing': item.get('time', ''),
                        'event_time_utc': '',
                        'latitude': float(item.get('lat', 0)),
                        'longitude': float(item.get('lon', 0)),
                        'depth_km': float(item.get('depth', 0)),
                        'magnitude': float(item.get('mag', 0)),
                        'magnitude_type': 'M',
                        'place': item.get('location', ''),
                        'event_type': 'earthquake',
                        'source': 'CEIC',
                        'detail_url': CEIC_URL,
                        'status': 'manual',
                    })
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

    return records


def _extract_num(s):
    nums = re.findall(r'[-+]?\d*\.?\d+', s.replace('－', '-'))
    return nums[0] if nums else '0'
