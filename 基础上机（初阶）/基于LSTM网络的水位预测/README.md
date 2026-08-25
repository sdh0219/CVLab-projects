# 基于 LSTM 网络的水位预测

使用 NOAA CO-OPS The Battery 站 2024 年 8,784 条已核验逐小时水位。模型以过去 24 小时水位预测下一小时，并递归生成未来 24 小时预测。

## 网络结构

```text
过去24小时水位 -> LSTM(32个隐藏单元) -> Linear(32→1) -> 下一小时水位
```

LSTM 通过输入门、遗忘门和输出门控制记忆单元，比基础 RNN 更适合学习较长时间依赖。

## 数据与评估

- 数据单位：米，MLLW 基准面，GMT 时间。
- 按时间顺序划分 70% 训练、15% 验证、15% 测试。
- 均值和标准差仅使用训练段计算，避免数据泄漏。
- 保存验证 MSE 最低的模型，测试集报告 MAE 和 RMSE。

## 文件

- `data/water_level_hourly_2024.csv`：原始水位数据
- `data/SOURCE.md`：数据来源和 API 说明
- `model.py`：LSTM 模型
- `data_utils.py`：数据读取、连续性检查和滑动窗口
- `train.py`：训练、验证和测试
- `predict_future.py`：未来1–168小时递归预测
- `requirements.txt`：依赖库

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

生成 `lstm_model.pt`、`training_and_test.png`、`future_water_level.csv` 和 `future_forecast.png`。

## 限制

本教学模型只使用历史水位，未加入风、气压、降雨或天文潮预报；多步递归误差会累积，不应用于真实防汛或航海决策。
