# 基于 Autoencoder 的图像去雾

该教学项目使用卷积自编码器，将有雾图像映射为清晰图像。数据集保留20张清晰原图，训练时通过大气散射简化模型在线合成多种雾。

## 原理

```text
有雾图像 -> 卷积编码器 -> 压缩特征 -> 卷积解码器 -> 清晰图像
```

合成雾采用 `I(x) = J(x)t(x) + A(1-t(x))`，其中 `J`是清晰图、`t`是空间渐变透射率、`A`是大气光。模型以有雾图为输入、清晰图为目标，最小化像素 MSE。

## 文件

- `data/clear/`：20张清晰训练原图
- `data/*_sources.csv`：图像来源与许可证
- `dataset.py`：中文路径图像读取和随机雾合成
- `model.py`：卷积自编码器
- `train.py`：训练、验证、PSNR和对比图
- `make_demo_haze.py`：生成可复现的有雾测试图
- `dehaze.py`：对单张图像去雾

## 环境要求

- Windows + **Python 3.10 ～ 3.12（64 位）**（代码使用了 `str | Path` 等较新语法，Python 3.9 及以下会报 TypeError，请全教室统一 3.10 以上版本）
- 联网仅用于 `pip install` 安装依赖；装好依赖后，本项目训练与预测**全程离线**可跑

## 运行

双击 `install_and_train.bat`，或执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python train.py
python make_demo_haze.py
python dehaze.py examples\hazy_demo.jpg --output examples\dehazed_demo.jpg
```

## 限制

项目使用小数据集和合成雾，适合讲解自编码器与成对图像重建。真实雾的颜色、深度和光照更复杂，如需实用应换用大型真实成对去雾数据集。
