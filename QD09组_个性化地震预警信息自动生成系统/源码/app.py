import os
import re
import pandas as pd
from flask import Flask, render_template, request, jsonify

from code.data_loader import load_earthquake_events, load_latest_events
from code.warning_generator import generate_earthquake_warning
from code.visualization import generate_earthquake_charts
from code.warning_rules import get_demo_risk_info

app = Flask(__name__)


def _load_or_create_events():
    path = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'earthquake_events_processed.csv')
    if os.path.exists(path):
        return load_earthquake_events(path)
    return None


@app.route('/')
def index():
    df = load_latest_events(50)
    events = []
    if df is not None and not df.empty:
        for _, r in df.iterrows():
            events.append({
                'event_time_beijing': str(r.get('event_time_beijing', '')),
                'event_time_utc': str(r.get('event_time_utc', '')),
                'magnitude': r.get('magnitude', ''),
                'place': r.get('place', ''),
                'event_id': r.get('event_id', ''),
                'source': r.get('source', ''),
            })
    return render_template('index.html', events=events)


@app.route('/get_event_detail')
def get_event_detail():
    event_id = request.args.get('event_id', '')
    df = load_earthquake_events()
    if df.empty:
        return jsonify({'success': False, 'error': 'No data'})
    if 'event_id' in df.columns and event_id:
        row = df[df['event_id'] == event_id]
        if row.empty:
            return jsonify({'success': False, 'error': 'Event not found'})
    else:
        row = df.iloc[[0]]

    r = row.iloc[0]
    return jsonify({
        'success': True,
        'event': {
            'event_id': r.get('event_id', ''),
            'event_time_beijing': str(r.get('event_time_beijing', '')),
            'magnitude': float(r.get('magnitude', 0)) if pd.notna(r.get('magnitude')) else 0,
            'depth_km': float(r.get('depth_km', 0)) if pd.notna(r.get('depth_km')) else 0,
            'latitude': float(r.get('latitude', 0)) if pd.notna(r.get('latitude')) else 0,
            'longitude': float(r.get('longitude', 0)) if pd.notna(r.get('longitude')) else 0,
            'place': r.get('place', ''),
            'source': r.get('source', ''),
            'detail_url': r.get('detail_url', ''),
        }
    })


@app.route('/generate', methods=['POST'])
def generate():
    identity = request.form.get('identity', '普通居民')
    age = int(request.form.get('age', 0))
    location = request.form.get('location', '')
    mobility = request.form.get('mobility', '')
    event_id = request.form.get('event_id', '')

    df = load_earthquake_events()
    if df.empty:
        return jsonify({'success': False, 'error': '暂无地震事件数据，请先更新数据'})

    selected_event = None
    if event_id and 'event_id' in df.columns:
        matches = df[df['event_id'] == event_id]
        if not matches.empty:
            selected_event = matches.iloc[0].to_dict()

    if selected_event is None:
        selected_event = df.iloc[0].to_dict()

    user_lat, user_lon = None, None
    nums = re.findall(r'[-+]?\d+\.?\d*', location)
    if len(nums) >= 2:
        try:
            user_lat, user_lon = float(nums[0]), float(nums[1])
        except (ValueError, IndexError):
            pass

    text, need_type, profile_label, risk_desc, action_suggestion, distance_info = generate_earthquake_warning(
        event=selected_event,
        identity=identity,
        age=age,
        location=location,
        mobility=mobility,
        user_lat=user_lat,
        user_lon=user_lon,
    )

    risk_label, _, _, _ = get_demo_risk_info(selected_event.get('magnitude', 0),
                                                 user_lat=user_lat, user_lon=user_lon,
                                                 eq_lat=selected_event.get('latitude'),
                                                 eq_lon=selected_event.get('longitude'))

    return jsonify({
        'success': True,
        'warning_text': text,
        'need_type': need_type,
        'profile_label': profile_label,
        'risk_desc': f'{selected_event.get("magnitude", "?")} 级地震',
        'risk_label': risk_label,
        'action_suggestion': action_suggestion,
        'distance_info': distance_info,
        'event_info': {
            'time': str(selected_event.get('event_time_beijing', '')),
            'magnitude': float(selected_event.get('magnitude', 0)) if pd.notna(selected_event.get('magnitude')) else 0,
            'depth_km': float(selected_event.get('depth_km', 0)) if pd.notna(selected_event.get('depth_km')) else 0,
            'place': selected_event.get('place', ''),
            'source': selected_event.get('source', ''),
            'detail_url': selected_event.get('detail_url', ''),
            'latitude': float(selected_event.get('latitude', 0)) if pd.notna(selected_event.get('latitude')) else 0,
            'longitude': float(selected_event.get('longitude', 0)) if pd.notna(selected_event.get('longitude')) else 0,
        }
    })


@app.route('/dashboard')
def dashboard():
    df = _load_or_create_events()
    if df is None or df.empty:
        return render_template('dashboard.html', charts={}, events=[], stats={})

    charts = generate_earthquake_charts(df)

    stats = {
        'total': len(df),
        'max_magnitude': float(df['magnitude'].max()) if 'magnitude' in df.columns else 0,
        'avg_depth': float(df['depth_km'].mean()) if 'depth_km' in df.columns else 0,
        'latest_time': str(df['event_time_utc'].max()) if 'event_time_utc' in df.columns else '',
        'source': df['source'].iloc[0] if 'source' in df.columns and not df.empty else '',
    }

    events = df.head(20).to_dict(orient='records')

    return render_template('dashboard.html', charts=charts, events=events, stats=stats)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='127.0.0.1', port=port)
