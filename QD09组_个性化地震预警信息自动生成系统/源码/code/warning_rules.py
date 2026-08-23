import math


def get_demo_risk_info(magnitude, user_lat=None, user_lon=None, eq_lat=None, eq_lon=None):
    if magnitude is None:
        return ('未知', '无法判断', '请关注官方信息。')

    if magnitude < 3.0:
        base_level = '蓝色'
        base_desc = '普通提醒'
        base_action = '地震震级较小，一般不会造成破坏。请保持正常生活秩序，关注官方信息。'
    elif magnitude < 4.5:
        base_level = '黄色'
        base_desc = '注意防范'
        base_action = '地震有一定震感，请保持冷静，注意周围环境安全。'
    elif magnitude < 6.0:
        base_level = '橙色'
        base_desc = '准备避险'
        base_action = '地震震级较大，请做好避险准备，远离危险区域，关注后续信息。'
    else:
        base_level = '红色'
        base_desc = '立即避险或转移'
        base_action = '地震震级强烈，请立即采取避险措施，保护自身安全。'

    distance_info = ''
    if user_lat is not None and user_lon is not None and eq_lat is not None and eq_lon is not None:
        dist = haversine_km(user_lat, user_lon, eq_lat, eq_lon)
        if dist < 50:
            distance_info = f'您距离震中约 {dist:.0f} 公里，属于较近区域，请务必注意安全。'
        elif dist < 200:
            distance_info = f'您距离震中约 {dist:.0f} 公里，有一定影响，请保持关注。'
        else:
            distance_info = f'您距离震中约 {dist:.0f} 公里，影响较小，但仍需关注官方信息。'
    else:
        distance_info = '未获取用户坐标，当前等级仅按震级进行简化判断。'

    return (base_level, base_desc, base_action, distance_info)


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_earthquake_need_type(identity, age, mobility):
    if identity == '应急人员':
        return '应急响应与巡查排险'
    if age >= 60:
        if mobility in ('需协助', '较弱'):
            return '转移协助与居家避险'
        return '居家避险与社区关注'
    if age < 18:
        return '校园避险与有序撤离'
    if identity == '游客':
        return '景区疏散与安全指引'
    return '居家避险与风险关注'


def get_earthquake_action(identity, age, mobility, need_type):
    actions = ''

    if identity == '应急人员':
        actions = '请立即到岗到位，开展震后巡查排查，重点检查建筑物受损、火灾、燃气泄漏、滑坡等次生风险。协助重点人群转移，及时上报险情，配合统一指挥调度。'
        return actions

    if age < 18:
        actions = '请听从学校、老师或监护人安排，不拥挤奔跑，保护头部，有序撤离到安全区域。'
    elif age >= 60:
        actions = '请不要独自快速撤离，及时联系家属、社区或应急人员，优先获得协助，避免摔倒和拥挤。'
        if mobility in ('需协助', '较弱'):
            actions += ' 行动不便人员请提前联系救援人员协助，不要单独行动。'
    elif mobility in ('需协助', '较弱'):
        actions = '行动不便人员请提前联系救援人员协助，不要单独行动。'
    else:
        actions = '请保持冷静，就近躲避，远离玻璃、悬挂物和高大家具，不乘坐电梯，震动停止后按安全路线撤离。'

    if identity == '游客':
        actions += ' 请关注当地官方信息，远离山体、危墙、老旧建筑和玻璃幕墙，服从景区和当地管理部门疏散安排，不进入封闭区域。'
    elif identity == '普通居民' and age >= 18 and age < 60:
        if mobility not in ('需协助', '较弱'):
            actions += ' 请检查家中燃气、水电设施，确认安全后撤离到空旷区域。'

    need_actions = {
        '校园避险与有序撤离': ' 请服从学校统一指挥，有序疏散到安全区域，不要慌乱奔跑。',
        '转移协助与居家避险': ' 请按照指定路线转移到安全安置点，社区将安排专人协助。',
        '居家避险与社区关注': ' 请做好居家防范，社区工作人员将主动联系您，如有需要请及时求助。',
        '景区疏散与安全指引': ' 请服从景区管理部门疏散安排，注意沿途安全标识。',
        '应急响应与巡查排险': ' 请立即开展震后巡查，排查次生灾害隐患，协助群众转移。',
        '居家避险与风险关注': ' 请做好居家避险准备，备好应急物资，关注官方后续信息。',
    }
    actions += need_actions.get(need_type, ' 请关注官方后续信息。')

    return actions
