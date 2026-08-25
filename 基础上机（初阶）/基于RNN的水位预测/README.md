# 基于 RNN 的水位预测

使用 NOAA CO-OPS The Battery 站 2024 年已核验逐小时水位，以过去 24 小时为一个时间窗口，训练基础 RNN 预测下一小时水位，并递归生成未来 24 小时预测。

## 流程

```text
过去24小时水位 -> RNN(32隐状态) -> 全连接层 -> 下一小时水位
```

- 只用训练集计算均值与标准差，避免数据泄漏。
- 按70%/15%/15%严格按时间先后划分训练、验证和测试集。
- 保存验证 MSE 最低的模型，报告测试 MAE 与 RMSE。
- `predict_future.py` 将每次预测送回时间窗口，生成多步递归预测。

## 主要文件

- `data/water_level_hourly_2024.csv`：原始逐小时水位
- `data/SOURCE.md`：站点、单位、基准面和 API 来源
- `model.py`：PyTorch RNN 模型
- `data_utils.py`：数据读取、连续性检查和滑动窗口
- `train.py`：训练、验证、测试和曲线绘制
- `predict_future.py`：未来 1–168 小时预测
- `rnn_model.pt`：训练完成后的最佳模型

## 环境要求

- Windows + **Python 3.10 ～ 3.12（64 位）**（代码使用了 `str | Path` 等较新语法，Python 3.9 及以下会报 TypeError，请全教室统一 3.10 以上版本）
- 联网仅用于 `pip install` 安装依赖；装好依赖后，本项目训练与预测**全程离线**可跑

## 运行

双击 `install_and_train.bat`，或手动执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python train.py
python predict_future.py --hours 24
```

输出包括 `rnn_model.pt`、`training_and_test.png`、`future_water_level.csv` 和 `future_forecast.png`。

## 限制

潮汐水位主要由天文潮、气压、风和径流等共同影响。本教学模型只使用单变量历史水位，多步递归时误差会累积，不应用于实际防汛或航海决策。
