# 基于扩散模型的图像去雨

该教学项目使用条件DDPM恢复有雨图像。训练时向清晰图随机加入高斯噪声，去噪网络在“有雨条件图”引导下预测噪声；推理时从有雨图的低强度扩散状态开始，经10步反向扩散生成去雨图，以保留原场景结构。

## 流程

```text
清晰图 x0 -> 随机时间步加噪 -> xt
xt + 有雨条件图 + 时间编码 -> U-Net去噪器 -> 预测噪声
推理：有雨图的低强度加噪状态 -> 10步反向扩散 -> 去雨图
```

## 文件

- `data/clear/`：20张清晰原图和来源信息
- `dataset.py`：随机雨线和雨幕合成
- `model.py`：带时间编码的条件U-Net去噪器
- `diffusion.py`：前向加噪和DDPM反向采样
- `train.py`：噪声预测训练和去雨比较
- `derain.py`：单图去雨
- `diffusion_derain.pt`：已训练模型

## 环境要求

- Windows + **Python 3.10 ～ 3.12（64 位）**（代码使用了 `str | Path` 等较新语法，Python 3.9 及以下会报 TypeError，请全教室统一 3.10 以上版本）
- 联网仅用于 `pip install` 安装依赖；装好依赖后，本项目训练与预测**全程离线**可跑

## 运行

双击 `install_and_train.bat`，或执行：

```powershell
python train.py
python make_demo.py
python derain.py examples\rainy_input.jpg --output examples\derained_output.jpg
```

## 限制

为便于CPU教学，图像缩放为64×64，反向扩散只用40步，数据也是合成雨。该项目用于演示条件扩散原理，实用去雨需要更大的真实数据、更高分辨率和更长训练。
