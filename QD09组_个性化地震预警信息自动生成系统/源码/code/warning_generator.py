from code.user_profile import get_profile_label
from code.warning_rules import get_demo_risk_info, get_earthquake_need_type, get_earthquake_action


def _try_parse_coords(location_str):
    import re
    if not location_str:
        return None, None
    nums = re.findall(r'[-+]?\d+\.?\d*', location_str)
    if len(nums) >= 2:
        try:
            return float(nums[0]), float(nums[1])
        except (ValueError, IndexError):
            pass
    return None, None


def generate_earthquake_warning(event, identity, age, location, mobility, user_lat=None, user_lon=None):
    mag = event.get('magnitude', 0)
    depth = event.get('depth_km', 0)
    place = event.get('place', '未知位置')
    time_bj = event.get('event_time_beijing') or event.get('event_time_utc', '')
    source = event.get('source', 'USGS')
    detail_url = event.get('detail_url', '')
    eq_lat = event.get('latitude')
    eq_lon = event.get('longitude')

    if user_lat is None:
        user_lat, user_lon = _try_parse_coords(location)

    need_type = get_earthquake_need_type(identity, age, mobility)
    profile_label = get_profile_label(identity, age, mobility)
    risk_label, risk_desc, base_action, distance_info = get_demo_risk_info(
        mag, user_lat=user_lat, user_lon=user_lon, eq_lat=eq_lat, eq_lon=eq_lon
    )
    action_suggestion = get_earthquake_action(identity, age, mobility, need_type)

    mag_str = f'M{mag:.1f}' if mag is not None else '未知震级'
    depth_str = f'{depth:.0f} 公里' if depth is not None else '未知深度'

    text = f'【地震提醒】公开地震目录显示，{time_bj} 在 {place} 发生 {mag_str} 地震，震源深度 {depth_str}。'
    text += f' 您属于{profile_label}。{distance_info}'
    text += f' 系统识别的重点需求：{need_type}。'
    text += f' 行动建议：{action_suggestion}'
    text += f' 数据来源：{source}。'

    return text, need_type, profile_label, risk_desc, action_suggestion, distance_info
