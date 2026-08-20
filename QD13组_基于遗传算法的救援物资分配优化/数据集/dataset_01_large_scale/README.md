# 数据集 01：大规模洪涝应急调度

## 场景说明

本数据集模拟**大规模洪涝灾害**下的应急物资调运场景，重点体现**数据规模大、计算维度高**的特点，适用于验证遗传算法在大规模问题上的可扩展性。

## 数据规模

| 项目 | 数值 |
|------|------|
| 受灾点 | 80 个 |
| 储备仓库 | 12 个 |
| 物资类型 | 3 种（饮用水, 方便面, 帐篷） |
| 受灾人口 | 5,169,540 人 |
| 总需求量 | 17,078,456 单位 |
| 总库存量 | 11,675,647 单位 |
| 最大运输能力 | 92,240 单位 |

## 文件说明

```
dataset_01_large_scale/
├── README.md
├── metadata.json
└── processed_data/
    └── processed_data.py    # 模型可直接加载
```

## 使用方式

在 `源码/code/config.json` 中配置：

```json
{
  "data": {
    "disaster_points_file": "../../数据包/dataset_01_large_scale/processed_data/processed_data.py",
    "use_simulation": false
  }
}
```

然后运行：

```bash
cd 源码/code
python main_universal.py
```
