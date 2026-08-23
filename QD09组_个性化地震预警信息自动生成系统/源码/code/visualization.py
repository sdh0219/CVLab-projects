import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import os
import pandas as pd

CHART_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'charts')


def _get_font():
    font_paths = [
        'C:/Windows/Fonts/simhei.ttf',
        'C:/Windows/Fonts/msyh.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/System/Library/Fonts/PingFang.ttc',
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            return FontProperties(fname=fp)
    return None


def _init_chart_dir():
    os.makedirs(CHART_DIR, exist_ok=True)


def plot_magnitude_distribution(df):
    _init_chart_dir()
    font = _get_font()
    bins = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    labels = ['M<1', 'M1-2', 'M2-3', 'M3-4', 'M4-5', 'M5-6', 'M6-7', 'M7-8', 'M8-9', 'M>=9']
    df['mag_bin'] = pd.cut(df['magnitude'], bins=bins, labels=labels, right=False)
    counts = df['mag_bin'].value_counts().sort_index()
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = ['#4CAF50', '#8BC34A', '#CDDC39', '#FFEB3B', '#FFC107', '#FF9800', '#FF5722', '#F44336', '#B71C1C']
    bars = ax.bar(counts.index, counts.values, color=colors[:len(counts)])
    ax.set_title('地震震级分布', fontproperties=font, fontsize=14, fontweight='bold')
    ax.set_xlabel('震级范围', fontproperties=font, fontsize=11)
    ax.set_ylabel('事件数量', fontproperties=font, fontsize=11)
    for bar, val in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5, str(val),
                ha='center', va='bottom', fontproperties=font)
    ax.set_xticks(range(len(counts.index)))
    ax.set_xticklabels(counts.index, fontproperties=font, rotation=30)
    path = os.path.join(CHART_DIR, 'magnitude_distribution.png')
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    return 'charts/magnitude_distribution.png'


def plot_depth_distribution(df):
    _init_chart_dir()
    font = _get_font()
    bins = [0, 10, 30, 50, 70, 100, 200, 500, 1000]
    labels = ['0-10km', '10-30km', '30-50km', '50-70km', '70-100km', '100-200km', '200-500km', '500km+']
    df['depth_bin'] = pd.cut(df['depth_km'], bins=bins, labels=labels, right=False)
    counts = df['depth_bin'].value_counts().sort_index()
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(counts.index, counts.values, color=['#1565C0', '#1976D2', '#2196F3', '#42A5F5', '#64B5F6', '#90CAF9', '#BBDEFB', '#E3F2FD'])
    ax.set_title('震源深度分布', fontproperties=font, fontsize=14, fontweight='bold')
    ax.set_xlabel('深度范围', fontproperties=font, fontsize=11)
    ax.set_ylabel('事件数量', fontproperties=font, fontsize=11)
    for bar, val in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5, str(val),
                ha='center', va='bottom', fontproperties=font)
    ax.set_xticks(range(len(counts.index)))
    ax.set_xticklabels(counts.index, fontproperties=font, rotation=30)
    path = os.path.join(CHART_DIR, 'depth_distribution.png')
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    return 'charts/depth_distribution.png'


def plot_time_trend(df):
    _init_chart_dir()
    font = _get_font()
    df['event_time_utc'] = pd.to_datetime(df['event_time_utc'], errors='coerce')
    df['date'] = df['event_time_utc'].dt.date
    daily = df.groupby('date').size().reset_index(name='count')
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(range(len(daily)), daily['count'].values, color='#F44336', marker='o', linestyle='-', linewidth=1.2, markersize=3)
    ax.set_title('地震事件时间趋势', fontproperties=font, fontsize=14, fontweight='bold')
    ax.set_xlabel('日期', fontproperties=font, fontsize=11)
    ax.set_ylabel('每日事件数', fontproperties=font, fontsize=11)
    step = max(1, len(daily) // 10)
    tick_indices = range(0, len(daily), step)
    tick_labels = [str(daily.iloc[i]['date']) for i in tick_indices]
    ax.set_xticks(list(tick_indices))
    ax.set_xticklabels(tick_labels, fontproperties=font, rotation=30, fontsize=8)
    path = os.path.join(CHART_DIR, 'time_trend.png')
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    return 'charts/time_trend.png'


def plot_location_scatter(df):
    _init_chart_dir()
    font = _get_font()
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(9, 6))
    sc = ax.scatter(df['longitude'], df['latitude'], c=df['magnitude'], cmap='YlOrRd',
                    s=df['magnitude'] * 8, alpha=0.6, edgecolors='gray', linewidth=0.3)
    ax.set_title('地震事件地理分布（经纬度散点图）', fontproperties=font, fontsize=14, fontweight='bold')
    ax.set_xlabel('经度', fontproperties=font, fontsize=11)
    ax.set_ylabel('纬度', fontproperties=font, fontsize=11)
    cbar = plt.colorbar(sc)
    cbar.set_label('震级', fontproperties=font)
    path = os.path.join(CHART_DIR, 'location_scatter.png')
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    return 'charts/location_scatter.png'


def generate_earthquake_charts(df):
    return {
        'magnitude_distribution': plot_magnitude_distribution(df),
        'depth_distribution': plot_depth_distribution(df),
        'time_trend': plot_time_trend(df),
        'location_scatter': plot_location_scatter(df),
    }
