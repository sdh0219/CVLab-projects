# 基于 CNN 的灾害图像分类

该教学项目直接从 RGB 图像像素学习“火灾/非火灾”特征，不使用人工设计的火焰色彩比例、纹理熵等特征。

## CNN 结构

```text
128x128 RGB图像
 -> Conv(3→16) + BatchNorm + ReLU + MaxPool
 -> Conv(16→32) + BatchNorm + ReLU + MaxPool
 -> Conv(32→64) + BatchNorm + ReLU
 -> Global Average Pooling
 -> Dropout + Linear(64→1)
 -> Sigmoid火灾概率
```

训练使用 Adam、`BCEWithLogitsLoss`、水平翻转及亮度/对比度增强。数据按类别分层拆分为 16 张训练图和 4 张验证图，保存验证损失最低的模型。

## 目录内容

- `data/fire/`、`data/normal/`：图像和来源清单
- `model.py`：CNN 网络结构
- `dataset.py`：图像读取、增强和数据划分
- `train.py`：训练、验证、最佳模型保存和曲线绘制
- `predict.py`：单图火灾概率预测
- `requirements.txt`：所需 Python 库
- `cnn_model.pt`：训练后生成的最佳模型

## 环境要求

- Windows + **Python 3.10 ～ 3.12（64 位）**（代码使用了 `str | Path` 等较新语法，Python 3.9 及以下会报 TypeError，请全教室统一 3.10 以上版本）
- 联网仅用于 `pip install` 安装依赖；装好依赖后，本项目训练与预测**全程离线**可跑

## 运行

双击 `install_and_train.bat`，或者在项目目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python train.py
python predict.py data\fire\fire_01.jpg
```

## 限制

当前只有 20 张教学样本，验证集仅 4 张，准确率波动会很大。本项目适合讲解 CNN 工作流程，不能直接用于真实火灾告警。
