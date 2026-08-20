"""
项目18：AI辅助山区泥石流"零死亡"综合方案 - 主程序（v2 含数据库数据+加密）
功能：AES解密 -> 数据加载 -> AHP易发性评估 -> 降雨监测 -> 分级预警 -> 转移规划 -> 救援调度 -> 可视化
"""
import rasterio
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm
from matplotlib.patches import FancyBboxPatch
import matplotlib.patches as mpatches
import os, sys, json
from collections import OrderedDict
from pathlib import Path
from key_manager import initialize as init_license

sys.stdout.reconfigure(encoding='utf-8')

# ===== 配置加载 =====
def load_config():
    """加载 config.json 配置文件"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(script_dir, 'config.json')
    if os.path.exists(cfg_path):
        with open(cfg_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    print("[警告] config.json 未找到，使用默认配置")
    return {}

def detect_project_root():
    """自动检测项目根目录：向上查找包含 1_数据包 和 2_源码 的目录"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 先检查脚本所在目录的上级目录
    for candidate in [script_dir] + list(Path(script_dir).parents):
        candidate = str(candidate)
        if os.path.isdir(os.path.join(candidate, '1_数据包')) and \
           os.path.isdir(os.path.join(candidate, '2_源码')):
            return candidate
    # 兜底：使用脚本所在目录的上级
    return os.path.dirname(script_dir)

CFG = load_config()

# 字体配置
_fonts = CFG.get('fonts', ['SimHei', 'Microsoft YaHei'])
plt.rcParams['font.sans-serif'] = _fonts
plt.rcParams['axes.unicode_minus'] = False

# 图表配置
_PLOT = CFG.get('plot', {})
_DPI = _PLOT.get('dpi', 150)

# 路径配置（优先使用 config.json 中的配置，否则自动检测）
_cfg_paths = CFG.get('paths', {})
BASE = _cfg_paths.get('base', '') or detect_project_root()
PROCESSED_DIR = _cfg_paths.get('raster_dir') or os.path.join(BASE, '1_数据包', 'processed_data')
DB_DATA_DIR = _cfg_paths.get('vector_dir') or os.path.join(BASE, '1_数据包', 'database_data')
OUTPUT_DIR = _cfg_paths.get('output_dir') or os.path.join(BASE, '2_源码', 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)
print(f"[配置] 项目根目录: {BASE}")

# ===== AES解密模块 =====
# 通过设备授权获取 AES 密钥（密钥不在源码中）
AES_KEY = init_license()

def aes_decrypt_file(filepath):
    """读取AES-256-CBC加密文件，返回解密后的JSON对象"""
    from Crypto.Cipher import AES
    with open(filepath, 'rb') as f:
        raw = f.read()
    iv = raw[:16]
    encrypted = raw[16:]
    cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(encrypted)
    pad_len = decrypted[-1]
    decrypted = decrypted[:-pad_len]
    return json.loads(decrypted.decode('utf-8'))

def load_db_data(name):
    """加载加密数据库文件"""
    path = os.path.join(DB_DATA_DIR, f'{name}.enc')
    if not os.path.exists(path):
        print(f"  [警告] {name}.enc 不存在")
        return []
    data = aes_decrypt_file(path)
    print(f"  [解密] {name}: {len(data)} 条记录")
    return data

# ===== GeoTIFF工具函数 =====
def read_tif(name):
    path = os.path.join(PROCESSED_DIR, f'{name}.tif')
    with rasterio.open(path) as src:
        return src.read(1).astype(float), src.transform, src.crs, src.bounds

def normalize(arr, vmin=None, vmax=None):
    a = arr.copy()
    if vmin is None: vmin = np.nanmin(a[np.isfinite(a)])
    if vmax is None: vmax = np.nanmax(a[np.isfinite(a)])
    a = np.clip(a, vmin, vmax)
    return np.where(np.isfinite(a), (a - vmin) / (vmax - vmin + 1e-10), 0)

def classify_risk(score):
    """风险分级（阈值从 config.json 读取）"""
    thresholds = CFG.get('risk_thresholds', [0.2, 0.4, 0.6, 0.8])
    levels = np.zeros_like(score, dtype=int)
    levels[score > 0] = 1
    for i, t in enumerate(thresholds):
        levels[score > t] = i + 2
    return levels

# ====================================================================
# 第一节：数据加载与解密
# ====================================================================
print("=" * 60)
print("第一节：数据加载与解密")
print("=" * 60)

# 加载GeoTIFF
print("\n[GeoTIFF] 加载12层空间数据 ...")
layers = {}
for name in ['dem', 'slope', 'aspect', 'landuse', 'soil_moisture', 'soil_sediment',
             'soil_type', 'lithology', 'ndvi', 'terrain_class', 'organic_carbon', 'ph']:
    data, transform, crs, bounds = read_tif(name)
    layers[name] = {'data': data, 'transform': transform, 'crs': crs, 'bounds': bounds}
    print(f"  {name}: {data.shape}, 有效像元 {np.count_nonzero(np.isfinite(data))}")

rows, cols = layers['dem']['data'].shape
bounds = layers['dem']['bounds']
# 统一尺寸（取最小公共形状，裁剪）
min_rows = min(l['data'].shape[0] for l in layers.values())
min_cols = min(l['data'].shape[1] for l in layers.values())
for name in layers:
    d = layers[name]['data']
    if d.shape[0] > min_rows or d.shape[1] > min_cols:
        layers[name]['data'] = d[:min_rows, :min_cols]
rows, cols = min_rows, min_cols
print(f"\n  统一尺寸: {rows}行 x {cols}列 = {rows*cols} 像元")
print(f"  空间范围: {bounds}")

# 加载加密数据库数据
print("\n[数据库] 解密加载 ...")
rainfall_all = load_db_data('rainfall_data')
rainfall_stations = load_db_data('rainfall_stations')
population = load_db_data('population')
shelters = load_db_data('shelters')
hidden_dangers = load_db_data('hidden_dangers')
dangerous_sources = load_db_data('dangerous_sources')
risk_spots = load_db_data('risk_spots')
roads = load_db_data('roads')

# ====================================================================
# 第二节：AHP层次分析法易发性评估
# ====================================================================
print("\n" + "=" * 60)
print("第二节：AHP层次分析法易发性评估")
print("=" * 60)

# AHP权重（10个因子，从 config.json 读取）
weights = OrderedDict(CFG.get('ahp_weights', {
    'slope': 0.25, 'lithology': 0.15, 'soil_moisture': 0.12,
    'dem': 0.10, 'landuse': 0.10, 'ndvi': 0.10,
    'soil_sediment': 0.08, 'terrain_class': 0.05,
    'organic_carbon': 0.03, 'ph': 0.02,
}))
print(f"\nAHP权重 (sum={sum(weights.values()):.2f}):")
for k, v in weights.items():
    print(f"  {k:18s}: {v:.2f}")

# 因子标准化（值越大=越危险，范围从 config.json 读取）
fr = CFG.get('factor_ranges', {})
print("\n因子标准化 ...")
factor_scores = {}
for name in weights:
    d = layers[name]['data']
    if name == 'slope':
        s = normalize(d, fr.get('slope', [0, 60])[0], fr.get('slope', [0, 60])[1])
    elif name == 'dem':
        s = 1.0 - normalize(d, fr.get('dem', [500, 2500])[0], fr.get('dem', [500, 2500])[1])
    elif name == 'ndvi':
        s = 1.0 - normalize(d, fr.get('ndvi', [-0.2, 0.8])[0], fr.get('ndvi', [-0.2, 0.8])[1])
    elif name == 'soil_moisture':
        s = normalize(d, fr.get('soil_moisture', [0, 1])[0], fr.get('soil_moisture', [0, 1])[1])
    elif name == 'soil_sediment':
        s = normalize(d, fr.get('soil_sediment', [0, 60])[0], fr.get('soil_sediment', [0, 60])[1])
    elif name == 'terrain_class':
        s = normalize(d, fr.get('terrain_class', [0, 400])[0], fr.get('terrain_class', [0, 400])[1])
    elif name == 'organic_carbon':
        s = 1.0 - normalize(d, fr.get('organic_carbon', [0, 50])[0], fr.get('organic_carbon', [0, 50])[1])
    elif name == 'ph':
        s = np.abs(normalize(d, fr.get('ph', [4, 9])[0], fr.get('ph', [4, 9])[1]) - 0.5) * 2
    elif name == 'landuse':
        s = np.where(d == 5, 1.0, np.where(d == 4, 0.6, np.where(d == 3, 0.4, np.where(d <= 2, 0.2, 0.3))))
    elif name == 'lithology':
        s = np.where(d == 4, 1.0, np.where(d == 2, 0.7, np.where(d == 6, 0.5, 0.3)))
    else:
        s = normalize(d)
    factor_scores[name] = s

# 加权叠加
print("加权叠加 ...")
susceptibility = np.zeros((rows, cols), dtype=float)
for name, w in weights.items():
    susceptibility += w * factor_scores[name]
susceptibility = np.clip(susceptibility, 0, 1)

# 风险分级
risk_level = classify_risk(susceptibility)
print(f"\n风险等级分布:")
for lv in range(1, 6):
    cnt = np.sum(risk_level == lv)
    pct = cnt / (rows * cols) * 100
    print(f"  {lv}级: {cnt:>8,} 像元 ({pct:.1f}%)")

# ====================================================================
# 第三节：降雨监测分析
# ====================================================================
print("\n" + "=" * 60)
print("第三节：降雨监测分析（数据库数据）")
print("=" * 60)

# 站点统计
print(f"\n降雨站点: {len(rainfall_stations)} 个")
if rainfall_stations:
    max_rain_stations = sorted(rainfall_stations, key=lambda x: x.get('max_rainfall_1h', 0), reverse=True)[:10]
    print("  降雨量TOP10站点:")
    for s in max_rain_stations:
        print(f"    {s['station_name']:15s}: 最大{s['max_rainfall_1h']:.1f}mm/h, 均值{s['avg_rainfall_1h']:.1f}mm/h")

# 降雨时间序列分析
print(f"\n降雨记录总数: {len(rainfall_all)}")
if rainfall_all:
    # 按小时统计
    hourly_rain = {}
    for r in rainfall_all:
        dt = r.get('datetime', '')
        if dt and len(dt) >= 13:
            hour_key = dt[:13]  # YYYYMMDDHHmm
            if hour_key not in hourly_rain:
                hourly_rain[hour_key] = []
            hourly_rain[hour_key].append(r['rainfall_1h'] or 0)
    print(f"  小时级时间步: {len(hourly_rain)} 个")

    # 找最大降雨事件
    max_hours = max(hourly_rain.keys(), key=lambda k: max(hourly_rain[k])) if hourly_rain else None
    if max_hours:
        vals = hourly_rain[max_hours]
        print(f"  最大降雨事件: {max_hours[:4]}-{max_hours[4:6]}-{max_hours[6:8]} {max_hours[8:10]}:{max_hours[10:12]}")
        print(f"    站点数: {len(vals)}, 最大: {max(vals):.1f}mm/h, 均值: {np.mean(vals):.1f}mm/h")

# ====================================================================
# 第四节：分级预警模拟
# ====================================================================
print("\n" + "=" * 60)
print("第四节：分级预警模拟（GB/T 28592-2012 / QX/T 487-2019）")
print("=" * 60)

# 国标预警阈值（从 config.json 读取）
warning_rules = CFG.get('warning_rules', {
    'blue': {'1h': 15, '24h': 50, 'level': 'IV', 'action': '加强监测'},
    'yellow': {'1h': 30, '24h': 100, 'level': 'III', 'action': '发布预警，准备转移'},
    'orange': {'1h': 50, '24h': 150, 'level': 'II', 'action': '紧急转移危险区群众'},
    'red': {'1h': 70, '24h': 200, 'level': 'I', 'action': '全面撤离，启动应急预案'},
})

# 基于历史降雨数据的预警频率统计
if rainfall_all:
    rain_values = [r['rainfall_1h'] for r in rainfall_all if r['rainfall_1h'] is not None]
    total = len(rain_values)
    warn_freq = {}
    for color, rule in warning_rules.items():
        cnt = sum(1 for v in rain_values if v >= rule['1h'])
        warn_freq[color] = cnt / total * 100 if total > 0 else 0
    print("\n预警触发频率（基于历史1h降雨量）:")
    for color, freq in warn_freq.items():
        print(f"  {color:8s}: {freq:.1f}%")
else:
    warn_freq = {'blue': 15, 'yellow': 12, 'orange': 4, 'red': 3}
    print("  使用默认频率")

# 预警区域叠加风险等级
warn_area = np.zeros((rows, cols), dtype=int)
if rainfall_all:
    max_1h = max((r['rainfall_1h'] or 0) for r in rainfall_all)
    # 模拟最大降雨事件的预警分布
    for color, rule in warning_rules.items():
        if max_1h >= rule['1h']:
            warn_area[susceptibility > 0.4] = list(warning_rules.keys()).index(color) + 1
print(f"\n最大1h降雨量: {max_1h:.1f}mm/h" if rainfall_all else "")

# ====================================================================
# 第五节：人口与避难所分析
# ====================================================================
print("\n" + "=" * 60)
print("第五节：人口分布与避难所分析（加密数据）")
print("=" * 60)

print(f"\n人口数据: {len(population)} 个区域")
if population:
    total_pop = sum(p.get('people_num', 0) or 0 for p in population)
    print(f"  研究区域总人口: {total_pop:,}")
    # 按区县统计
    county_pop = {}
    for p in population:
        c = p.get('county', '未知')
        county_pop[c] = county_pop.get(c, 0) + (p.get('people_num', 0) or 0)
    print("  区县人口分布:")
    for c, pop in sorted(county_pop.items(), key=lambda x: -x[1])[:8]:
        print(f"    {c}: {pop:,}")

print(f"\n避难场所: {len(shelters)} 个")
if shelters:
    total_cap = sum(s.get('capacity', 0) or 0 for s in shelters)
    print(f"  总容纳人数: {total_cap:,}")
    type_count = {}
    for s in shelters:
        t = s.get('type', '未知')
        type_count[t] = type_count.get(t, 0) + 1
    print("  类型分布:")
    for t, c in sorted(type_count.items(), key=lambda x: -x[1]):
        print(f"    {t}: {c}")

print(f"\n隐患点: {len(hidden_dangers)} 个")
print(f"危险源: {len(dangerous_sources)} 个")
print(f"风险点: {len(risk_spots)} 个")

# ====================================================================
# 第六节：转移路线规划
# ====================================================================
print("\n" + "=" * 60)
print("第六节：转移路线规划")
print("=" * 60)

# 识别高风险区聚落（基于人口数据+风险等级）
settlements = []
if population:
    for p in population:
        lon, lat = p.get('lon', 0), p.get('lat', 0)
        if lon and lat:
            # 转为栅格坐标
            col = int((lon - bounds.left) / (bounds.right - bounds.left) * cols)
            row_idx = int((bounds.top - lat) / (bounds.top - bounds.bottom) * rows)
            col = max(0, min(col, cols - 1))
            row_idx = max(0, min(row_idx, rows - 1))
            risk = risk_level[row_idx, col]
            if risk >= 3:
                settlements.append({
                    'name': f"{p.get('county','')}{p.get('country','')}",
                    'lon': lon, 'lat': lat,
                    'people': p.get('people_num', 0),
                    'risk': int(risk),
                })

print(f"高风险区聚落: {len(settlements)} 个")
settlements = sorted(settlements, key=lambda x: -x.get('people', 0))

# 选取代表性聚落（按风险降序取前N，N从 config.json 读取）
_top_n = CFG.get('evacuation', {}).get('top_n_settlements', 20)
top_settlements = settlements[:_top_n]
print(f"TOP{_top_n}聚落:")
for s in top_settlements[:10]:
    print(f"  {s['name']:20s}: {s['people']:>6,}人, 风险{s['risk']}级")

# 避险点选取（低风险区域）
safe_points = []
if shelters:
    for s in shelters:
        lon, lat = s.get('lon'), s.get('lat')
        if lon and lat:
            col = int((lon - bounds.left) / (bounds.right - bounds.left) * cols)
            row_idx = int((bounds.top - lat) / (bounds.top - bounds.bottom) * rows)
            col = max(0, min(col, cols - 1))
            row_idx = max(0, min(row_idx, rows - 1))
            if risk_level[row_idx, col] <= 2:
                safe_points.append(s)

print(f"低风险避难所: {len(safe_points)} 个")

# 疏散计划
evacuation_plans = []
for s in top_settlements:
    # 找最近的安全点
    best_shelter = None
    best_dist = float('inf')
    for sp in (safe_points if safe_points else shelters):
        dlon = (s['lon'] - sp.get('lon', 0)) ** 2
        dlat = (s['lat'] - sp.get('lat', 0)) ** 2
        dist = (dlon + dlat) ** 0.5 * 111
        if dist < best_dist:
            best_dist = dist
            best_shelter = sp
    if best_shelter:
        speed = CFG.get('evacuation', {}).get('walking_speed_km_per_min', 0.08)  # km/min
        time_min = best_dist / speed
        evacuation_plans.append({
            'settlement': s['name'], 'people': s['people'],
            'risk_level': s['risk'],
            'shelter': best_shelter.get('name', '避难所'),
            'distance_km': round(best_dist, 1),
            'time_min': round(time_min, 0),
        })

print(f"\n疏散计划: {len(evacuation_plans)} 条")
for e in evacuation_plans[:5]:
    print(f"  {e['settlement']:20s} -> {e['shelter']:20s}: {e['distance_km']}km, ~{e['time_min']}min")

# ====================================================================
# 第七节：救援力量调度
# ====================================================================
print("\n" + "=" * 60)
print("第七节：救援力量调度")
print("=" * 60)

rescue_forces = CFG.get('rescue_forces', [
    {'name': '专业救援队', 'units': 2, 'per_unit': 50, 'speed_kmh': 100, 'color': '#e74c3c'},
    {'name': '消防救援', 'units': 3, 'per_unit': 30, 'speed_kmh': 80, 'color': '#e67e22'},
    {'name': '武警部队', 'units': 2, 'per_unit': 100, 'speed_kmh': 60, 'color': '#f39c12'},
    {'name': '医疗救护', 'units': 4, 'per_unit': 20, 'speed_kmh': 70, 'color': '#27ae60'},
    {'name': '志愿者队伍', 'units': 5, 'per_unit': 15, 'speed_kmh': 40, 'color': '#2980b9'},
])
total_personnel = sum(f['units'] * f['per_unit'] for f in rescue_forces)
print(f"救援力量配置: {total_personnel} 人/批次")
for f in rescue_forces:
    print(f"  {f['name']:8s}: {f['units']}支 x {f['per_unit']}人 = {f['units']*f['per_unit']}人, 速度{f['speed_kmh']}km/h")

# ====================================================================
# 第八节：数据导出
# ====================================================================
print("\n" + "=" * 60)
print("第八节：数据导出")
print("=" * 60)

# 网格数据CSV
print("\n导出grid_data.csv ...")
grid_flat = []
for r in range(rows):
    for c in range(cols):
        lon = bounds.left + (c + 0.5) * (bounds.right - bounds.left) / cols
        lat = bounds.top - (r + 0.5) * (bounds.top - bounds.bottom) / rows
        row_data = {'lon': round(lon, 6), 'lat': round(lat, 6)}
        for name in weights:
            row_data[name] = round(float(factor_scores[name][r, c]), 4)
        row_data['susceptibility'] = round(float(susceptibility[r, c]), 4)
        row_data['risk_level'] = int(risk_level[r, c])
        grid_flat.append(row_data)

import csv
csv_path = os.path.join(OUTPUT_DIR, 'grid_data.csv')
if grid_flat:
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=grid_flat[0].keys())
        writer.writeheader()
        writer.writerows(grid_flat)
    print(f"  grid_data.csv: {len(grid_flat)} 行")

# JSON导出
json_data = {
    'monitoring_stations': rainfall_stations,
    'evacuation_plans': evacuation_plans,
    'warning_rules': warning_rules,
    'rescue_forces': rescue_forces,
    'settlements': settlements[:_top_n],
}
for key, data in json_data.items():
    path = os.path.join(OUTPUT_DIR, f'{key}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"  {key}.json: {len(data) if isinstance(data, list) else len(data.keys())} items")

# ====================================================================
# 第九节：可视化
# ====================================================================
print("\n" + "=" * 60)
print("第九节：可视化出图")
print("=" * 60)

risk_cmap = LinearSegmentedColormap.from_list('risk',
    ['#2ecc71', '#f1c40f', '#e67e22', '#e74c3c', '#8e44ad'], N=5)
risk_bounds = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
risk_norm = BoundaryNorm(risk_bounds, risk_cmap.N)

# --- 图1: 风险评估图 ---
fig, axes = plt.subplots(1, 2, figsize=(16, 7))
ax1 = axes[0]
im1 = ax1.imshow(susceptibility, cmap='YlOrRd', vmin=0, vmax=1)
ax1.set_title('泥石流易发性指数', fontsize=14, fontweight='bold')
plt.colorbar(im1, ax=ax1, shrink=0.8, label='易发性指数')
ax2 = axes[1]
im2 = ax2.imshow(risk_level, cmap=risk_cmap, norm=risk_norm)
ax2.set_title('风险等级分布', fontsize=14, fontweight='bold')
patches = [mpatches.Patch(color=risk_cmap(i), label=f'{i+1}级') for i in range(5)]
ax2.legend(handles=patches, loc='lower right')
plt.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, 'fig1_risk_assessment.png'), dpi=_DPI, bbox_inches='tight')
plt.close()
print("  fig1_risk_assessment.png")

# --- 图2: 因子得分图 ---
fig, axes = plt.subplots(2, 5, figsize=(20, 8))
factor_names = list(weights.keys())
for i, name in enumerate(factor_names):
    ax = axes[i // 5, i % 5]
    im = ax.imshow(factor_scores[name], cmap='YlOrRd', vmin=0, vmax=1)
    ax.set_title(f'{name}\n(w={weights[name]:.2f})', fontsize=10)
    ax.axis('off')
plt.suptitle('10因子标准化得分', fontsize=16, fontweight='bold')
plt.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, 'fig2_factor_scores.png'), dpi=_DPI, bbox_inches='tight')
plt.close()
print("  fig2_factor_scores.png")

# --- 图3: 监测站点分布 ---
fig, ax = plt.subplots(figsize=(12, 8))
ax.imshow(susceptibility, cmap='YlOrRd', alpha=0.6, extent=[bounds.left, bounds.right, bounds.bottom, bounds.top])
if rainfall_stations:
    lons = [s['lon'] for s in rainfall_stations]
    lats = [s['lat'] for s in rainfall_stations]
    max_rains = [s.get('max_rainfall_1h', 0) for s in rainfall_stations]
    sc = ax.scatter(lons, lats, c=max_rains, cmap='Blues', s=60, edgecolors='navy', linewidth=0.5, zorder=5)
    plt.colorbar(sc, ax=ax, shrink=0.7, label='最大1h降雨(mm)')
ax.set_title('雨量监测站点分布（南部山区）', fontsize=14, fontweight='bold')
ax.set_xlabel('经度'); ax.set_ylabel('纬度')
plt.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, 'fig3_monitoring_stations.png'), dpi=_DPI, bbox_inches='tight')
plt.close()
print("  fig3_monitoring_stations.png")

# --- 图4: 预警模拟图 ---
fig, ax = plt.subplots(figsize=(12, 8))
ax.imshow(susceptibility, cmap='Greys', alpha=0.3, extent=[bounds.left, bounds.right, bounds.bottom, bounds.top])
warn_cmap = LinearSegmentedColormap.from_list('warn',
    ['#3498db', '#f1c40f', '#e67e22', '#e74c3c'], N=4)
warn_norm = BoundaryNorm([0.5, 1.5, 2.5, 3.5, 4.5], warn_cmap.N)
if np.any(warn_area > 0):
    ax.imshow(warn_area, cmap=warn_cmap, norm=warn_norm, alpha=0.5,
              extent=[bounds.left, bounds.right, bounds.bottom, bounds.top])
patches = [mpatches.Patch(color=['#3498db', '#f1c40f', '#e67e22', '#e74c3c'][i],
    label=f"{list(warning_rules.keys())[i]}预警") for i in range(4)]
ax.legend(handles=patches, loc='upper right', fontsize=10)
ax.set_title('分级预警区域模拟', fontsize=14, fontweight='bold')
ax.set_xlabel('经度'); ax.set_ylabel('纬度')
plt.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, 'fig4_warning_simulation.png'), dpi=_DPI, bbox_inches='tight')
plt.close()
print("  fig4_warning_simulation.png")

# --- 图5: 转移路线图 ---
fig, ax = plt.subplots(figsize=(12, 8))
ax.imshow(risk_level, cmap=risk_cmap, norm=risk_norm, alpha=0.5,
          extent=[bounds.left, bounds.right, bounds.bottom, bounds.top])
# 聚落点
if top_settlements:
    ax.scatter([s['lon'] for s in top_settlements], [s['lat'] for s in top_settlements],
              c='red', s=40, marker='^', label='高风险聚落', zorder=5)
# 避难所
if safe_points:
    ax.scatter([s.get('lon',0) for s in safe_points[:20]], [s.get('lat',0) for s in safe_points[:20]],
              c='lime', s=60, marker='s', edgecolors='darkgreen', label='避难场所', zorder=5)
elif shelters:
    ax.scatter([s.get('lon',0) for s in shelters[:30]], [s.get('lat',0) for s in shelters[:30]],
              c='lime', s=60, marker='s', edgecolors='darkgreen', label='避难场所', zorder=5)
# 疏散路线（简化直线）
for e in evacuation_plans[:10]:
    for s in top_settlements:
        if s['name'] == e['settlement']:
            best = None
            for sp in (safe_points if safe_points else shelters):
                if sp.get('name') == e['shelter']:
                    best = sp; break
            if best:
                ax.plot([s['lon'], best.get('lon',0)], [s['lat'], best.get('lat',0)],
                       'g--', alpha=0.6, linewidth=1.5)
ax.legend(loc='upper left')
ax.set_title('群众转移路线与避险点规划', fontsize=14, fontweight='bold')
ax.set_xlabel('经度'); ax.set_ylabel('纬度')
plt.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, 'fig5_evacuation_routes.png'), dpi=_DPI, bbox_inches='tight')
plt.close()
print("  fig5_evacuation_routes.png")

# --- 图6: 高程+风险热力对比 ---
fig, axes = plt.subplots(1, 2, figsize=(16, 7))
ax1 = axes[0]
im1 = ax1.imshow(layers['dem']['data'], cmap='terrain',
                  extent=[bounds.left, bounds.right, bounds.bottom, bounds.top])
ax1.set_title('DEM高程', fontsize=14, fontweight='bold')
plt.colorbar(im1, ax=ax1, shrink=0.8, label='高程(m)')
ax2 = axes[1]
im2 = ax2.imshow(susceptibility, cmap='hot_r',
                  extent=[bounds.left, bounds.right, bounds.bottom, bounds.top])
ax2.set_title('易发性热力图', fontsize=14, fontweight='bold')
plt.colorbar(im2, ax=ax2, shrink=0.8, label='易发性指数')
plt.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, 'fig6_dem_risk_overlay.png'), dpi=_DPI, bbox_inches='tight')
plt.close()
print("  fig6_dem_risk_overlay.png")

# ===== 完成 =====
print("\n" + "=" * 60)
print("全部完成！")
print(f"输出目录: {OUTPUT_DIR}")
print(f"共生成: 6张图 + grid_data.csv + 4个JSON")
print("=" * 60)
