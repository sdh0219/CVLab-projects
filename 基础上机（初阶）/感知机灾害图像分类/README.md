# 感知机的灾害图像分类

这是一个与课件示意图对应的教学项目：将图像转换为 3 个可解释特征，使用从零实现的感知机完成“火灾/ 非火灾”二分类。

## 目录

- `data/fire/`：火灾样本，y=1
- `data/normal/`：正常样本，y=0
- `features.py`：提取火焰色彩比例、烟雾纹理熵、边缘方向响应
- `perceptron.py`：感知机的训练、预测和模型保存
- `train.py`：训练并生成 `model.json` 和 `training_curve.png`
- `predict.py`：对单张图像进行判别
- `requirements.txt`：需要安装的 Python 库

## 环境要求

- Windows + **Python 3.10 ～ 3.12（64 位）**（代码使用了 `str | Path` 等较新语法，Python 3.9 及以下会报 TypeError，请全教室统一 3.10 以上版本）
- 联网仅用于 `pip install` 安装依赖；装好依赖后，本项目训练与预测**全程离线**可跑

## 一键运行（Windows）

双击 `install_and_train.bat`，脚本会创建独立虚拟环境、安装依赖并训练模型。

也可手动执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python train.py
python predict.py data\fire\fire_01.jpg
```

## 感知机公式

`z = w1*x1 + w2*x2 + w3*x3 + b`，当 `z >= 0` 时输出火灾 1，否则输出非火灾 0。对误分样本按以下规则更新：

`w <- w + eta*(y-y_hat)*x`

`b <- b + eta*(y-y_hat)`

由于少量真实图像未必完全线性可分，实现中加入了 Pocket 机制，最终保留训练过程中误分数最少的权重，但基本更新公式不变。

## 说明

该项目用于教学，数据量小，手工特征也可能受灯光、夕阳和红色物体干扰，不应直接用于真实火灾告警。
