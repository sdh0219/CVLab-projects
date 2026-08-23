# -*- coding: utf-8 -*-
"""
generate_data.py —— 合成贴近真实的雨量计多传感器数据集，并注入受控异常。

为什么自建数据集（而非直接下载）：
  1. 课程要求"原始数据 + 清洗后数据"对照，需要一份带【真值标签】的数据，
     才能在实验中【量化评估】异常检测的精确率/召回率与修正后的误差；真实公开
     数据没有逐点真值，无法严格评估清洗效果。
  2. 通过受控注入 7 类真实世界常见的雨量计故障，可系统覆盖各类清洗规则。
  3. 完全可复现（固定随机种子）。

降雨过程建模思路（贴近真实汛期）：
  - 大部分时间无雨（雨量为 0），符合降水的间歇性、稀疏性；
  - 降雨事件按泊松过程到达，每场雨有"历时 + 峰值雨强 + 钟形强度廓线"；
  - 雨量按翻斗分辨率 0.1mm 量化；
  - 同步生成【水位站】（对累计降雨的线性水库滞后响应）与【气象站】
    （温度、相对湿度，雨时湿度升高、温度略降），用于跨传感器一致性校验的背景。

注入的 7 类异常（覆盖项目"数据质量问题"要点）：
  1. 缺失值 missing        —— 通信中断/掉线（含随机点 + 连续整段）
  2. 负值 negative         —— 传输误码（降雨物理上不可能为负）
  3. 尖峰/超量程 spike     —— 电气干扰/哨兵值（如 999），物理不可能的极大值
  4. 传感器卡滞 stuck      —— 翻斗机械卡死，长时间读数恒定
  5. 虚假翻斗 spurious     —— 蛛网/振动/噪声导致干期出现微量假降雨
  6. 时间戳重复 duplicate  —— 数据采集器重发
  7. 时间戳乱序 disorder   —— 缓存回灌导致行顺序错乱

运行：python src/generate_data.py
"""
import json
import numpy as np
import pandas as pd

from config import (
    RANDOM_SEED, FREQ, SAMPLES_PER_HOUR, TIP_RESOLUTION,
    RAW_RAIN_CSV, RAW_MULTI_CSV, TRUTH_CSV, REPORT_DIR,
)

# 数据时间范围：2024 年汛期一个月（6 月），10 分钟分辨率
START = "2024-06-01 00:00:00"
DAYS = 30
N = DAYS * 24 * SAMPLES_PER_HOUR     # 总样本数 = 4320

STATION_ID = "RG-001"                # 雨量计站点编号


# ----------------------------------------------------------------------------
# 1. 生成"干净"的真实降雨过程
# ----------------------------------------------------------------------------
def generate_clean_rainfall(rng: np.random.Generator) -> np.ndarray:
    """生成无异常的真实 10min 雨量序列（单位 mm）。"""
    rain = np.zeros(N, dtype=float)

    # 泊松过程：平均每 ~2.5 天一场雨 -> 一个月约 12 场
    n_events = rng.poisson(DAYS / 2.5)
    n_events = max(n_events, 8)

    for _ in range(n_events):
        # 事件起始时刻
        start = rng.integers(0, N - 1)
        # 历时：1~10 小时（指数分布，封顶），换算为间隔数
        dur_hours = float(np.clip(rng.exponential(3.0) + 0.5, 0.5, 12.0))
        dur = max(int(dur_hours * SAMPLES_PER_HOUR), 3)
        end = min(start + dur, N)
        length = end - start
        if length < 3:
            continue

        # 峰值雨强（mm/10min）：gamma 分布，多数小雨、偶有暴雨
        peak = float(rng.gamma(shape=2.0, scale=2.2))     # 期望 ~4.4
        peak = float(np.clip(peak, 0.3, 18.0))

        # 强度廓线：beta 形钟形曲线（先增后减，峰值位置随机）
        t = np.linspace(0, 1, length)
        a, b = rng.uniform(1.5, 3.0), rng.uniform(1.5, 3.0)
        profile = (t ** (a - 1)) * ((1 - t) ** (b - 1))
        profile = profile / profile.max()
        # 叠加分钟级随机扰动，使曲线不光滑（更真实）
        noise = rng.normal(1.0, 0.18, size=length).clip(0.4, 1.6)
        rain[start:end] += peak * profile * noise

    # 轻微基底噪声（极小，模拟传感器本底，后续量化会归零）
    rain = np.clip(rain, 0, None)
    # 翻斗量化：四舍五入到 0.1mm
    rain = np.round(rain / TIP_RESOLUTION) * TIP_RESOLUTION
    return rain


def generate_companion_sensors(rain: np.ndarray, rng: np.random.Generator):
    """根据降雨生成同步的【水位站】与【气象站】序列，用作跨传感器背景。"""
    # 水位站：线性水库模型，水位对降雨有滞后累积响应 + 缓慢退水
    base_level = 1.20             # 基础水位 (m)
    level = np.full(N, base_level)
    storage = 0.0
    k_recession = 0.985           # 退水系数（每步衰减）
    gain = 0.015                  # 降雨->蓄量增益
    for i in range(N):
        storage = storage * k_recession + rain[i] * gain
        level[i] = base_level + storage + rng.normal(0, 0.003)
    level = np.round(level, 3)

    # 气象站：温度（日变化正弦 + 雨时降温）、相对湿度（雨时升高）
    hours = np.arange(N) / SAMPLES_PER_HOUR
    temp = 26 + 5 * np.sin(2 * np.pi * (hours - 8) / 24) + rng.normal(0, 0.4, N)
    humid = 65 + 8 * np.sin(2 * np.pi * (hours - 4) / 24) + rng.normal(0, 2.0, N)
    # 雨时：湿度抬升、温度回落（用滑动累计降雨调制）
    rain_recent = pd.Series(rain).rolling(6, min_periods=1).sum().to_numpy()
    humid = humid + 18 * np.tanh(rain_recent / 3.0)
    temp = temp - 2.5 * np.tanh(rain_recent / 3.0)
    humid = np.clip(humid, 20, 100).round(1)
    temp = temp.round(1)
    return level, temp, humid


# ----------------------------------------------------------------------------
# 2. 注入受控异常（同时记录逐点真值标签）
# ----------------------------------------------------------------------------
def inject_anomalies(rain_clean: np.ndarray, rng: np.random.Generator):
    """在干净序列上注入 7 类异常，返回 (含异常序列, 逐点异常类型标签数组)。

    标签取值：'' 表示正常，否则为异常类型字符串。
    时间戳类异常（重复/乱序）在 DataFrame 层处理，这里只处理数值类异常。
    """
    rain = rain_clean.copy()
    labels = np.array([""] * N, dtype=object)

    # 候选位置（避免重复占用）
    free = np.ones(N, dtype=bool)

    def take(positions):
        positions = [p for p in positions if 0 <= p < N and free[p]]
        for p in positions:
            free[p] = False
        return positions

    # --- (1) 负值 negative：约 0.5% ---
    neg_idx = take(rng.choice(N, size=int(N * 0.005), replace=False).tolist())
    for p in neg_idx:
        rain[p] = -round(float(rng.uniform(0.1, 5.0)), 1)
        labels[p] = "negative"

    # --- (2) 尖峰/超量程 spike：约 0.5%（含哨兵值 999 与物理不可能极大值）---
    spike_cand = [p for p in rng.choice(N, size=int(N * 0.006), replace=False).tolist() if free[p]]
    spike_idx = take(spike_cand)
    for p in spike_idx:
        if rng.random() < 0.4:
            rain[p] = 999.0                       # 哨兵/溢出值
        else:
            rain[p] = round(float(rng.uniform(60, 300)), 1)  # 物理不可能的极大值
        labels[p] = "spike"

    # --- (3) 传感器卡滞 stuck：3 段，每段连续 8~20 个间隔恒定非零 ---
    for _ in range(3):
        seg_len = int(rng.integers(8, 21))
        start = int(rng.integers(0, N - seg_len))
        seg = list(range(start, start + seg_len))
        if not all(free[p] for p in seg):
            continue
        stuck_val = round(float(rng.uniform(0.5, 3.0)), 1)  # 卡在某个非零读数
        for p in seg:
            rain[p] = stuck_val
            labels[p] = "stuck"
            free[p] = False

    # --- (4) 虚假翻斗 spurious：干期（真值为 0 处）注入微量假降雨，约 1% ---
    dry_positions = [p for p in range(N) if rain_clean[p] == 0 and free[p]]
    n_spur = int(N * 0.01)
    spur_idx = take(rng.choice(dry_positions, size=min(n_spur, len(dry_positions)), replace=False).tolist())
    for p in spur_idx:
        rain[p] = round(float(rng.choice([0.1, 0.1, 0.2, 0.3])), 1)
        labels[p] = "spurious"

    # --- (5) 缺失值 missing：随机点 ~3% + 2 段连续掉线 ---
    miss_random = take(rng.choice(N, size=int(N * 0.03), replace=False).tolist())
    for p in miss_random:
        rain[p] = np.nan
        labels[p] = "missing"
    # 连续掉线段（设备离线）
    for _ in range(2):
        seg_len = int(rng.integers(6, 19))   # 1~3 小时离线
        start = int(rng.integers(0, N - seg_len))
        for p in range(start, start + seg_len):
            if free[p]:
                rain[p] = np.nan
                labels[p] = "missing"
                free[p] = False

    return rain, labels


def to_dataframe(times, rain, level, temp, humid, station=STATION_ID) -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": times,
        "station_id": station,
        "rainfall_mm": rain,        # 雨量计：10min 雨量 (mm)
        "water_level_m": level,     # 水位站：水位 (m)
        "temperature_c": temp,      # 气象站：气温 (℃)
        "humidity_pct": humid,      # 气象站：相对湿度 (%)
    })


def inject_timestamp_anomalies(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """注入时间戳重复与乱序异常（行级），模拟采集器重发与缓存回灌。"""
    df = df.copy()
    # 重复：随机挑 5 行整行复制插入
    dup_rows = df.sample(n=5, random_state=int(rng.integers(0, 1e6)))
    df = pd.concat([df, dup_rows], ignore_index=True)
    # 乱序：对原顺序做局部打乱（整体仍接近时间顺序，但存在错位）
    idx = np.arange(len(df))
    swaps = rng.integers(0, len(df) - 1, size=20)
    for s in swaps:
        idx[s], idx[s + 1] = idx[s + 1], idx[s]
    df = df.iloc[idx].reset_index(drop=True)
    return df


def main():
    rng = np.random.default_rng(RANDOM_SEED)
    times = pd.date_range(START, periods=N, freq=FREQ)

    # 1) 干净真值
    rain_clean = generate_clean_rainfall(rng)
    level, temp, humid = generate_companion_sensors(rain_clean, rng)

    # 真值表（评估专用，含干净雨量）
    truth = to_dataframe(times, rain_clean, level, temp, humid)
    truth.to_csv(TRUTH_CSV, index=False, encoding="utf-8-sig")

    # 2) 注入数值类异常
    rain_dirty, labels = inject_anomalies(rain_clean, rng)

    # 原始多传感器表（仅雨量被污染；同步传感器保持真值，作为交叉校验背景）
    raw = to_dataframe(times, rain_dirty, level, temp, humid)
    raw["anomaly_truth"] = labels   # 逐点真值标签（评估用，真实场景中没有此列）

    # 3) 注入时间戳类异常 -> 这是"最原始"的入库数据
    raw = inject_timestamp_anomalies(raw, rng)

    # 保存：完整多传感器原始数据 + 单独的雨量计原始数据
    raw.to_csv(RAW_MULTI_CSV, index=False, encoding="utf-8-sig")
    raw[["timestamp", "station_id", "rainfall_mm", "anomaly_truth"]].to_csv(
        RAW_RAIN_CSV, index=False, encoding="utf-8-sig")

    # 4) 统计注入情况，便于核对
    counts = pd.Series(labels).value_counts().to_dict()
    counts = {("normal" if k == "" else k): int(v) for k, v in counts.items()}
    n_dup = 5
    summary = {
        "样本数(规则时间轴)": int(N),
        "时间范围": [str(times[0]), str(times[-1])],
        "采样分辨率": FREQ,
        "注入数值异常计数": {k: v for k, v in counts.items() if k != "normal"},
        "正常点数": counts.get("normal", 0),
        "注入重复行数": n_dup,
        "注入乱序交换次数": 20,
        "原始入库总行数(含重复)": int(len(raw)),
        "真实总降雨量_mm(真值)": round(float(rain_clean.sum()), 1),
    }
    (REPORT_DIR / "data_generation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 60)
    print("数据生成完成")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print(f"\n原始雨量计数据  -> {RAW_RAIN_CSV}")
    print(f"多传感器原始数据 -> {RAW_MULTI_CSV}")
    print(f"真值数据(评估用) -> {TRUTH_CSV}")


if __name__ == "__main__":
    main()
