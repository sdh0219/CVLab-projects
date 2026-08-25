# 基于 GAN 网络的图像去雾

本项目使用条件生成对抗网络（cGAN）完成图像去雾。U-Net式生成器输入有雾图、输出清晰图；PatchGAN判别器判断“有雾图+清晰结果”是真实配对还是生成配对。

## 损失函数

`Generator Loss = Adversarial BCE + 50 * L1 Reconstruction Loss`

对抗损失鼓励更真实的局部纹理，L1损失保持图像的整体结构和颜色。训练雾由大气散射简化公式在线随机合成。

## 主要文件

- `data/clear/`：20张清晰原图
- `dataset.py`：数据读取和合成雾
- `model.py`：生成器与PatchGAN判别器
- `train.py`：交替对抗训练、验证和画图
- `dehaze.py`：单图去雾
- `gan_dehaze_generator.pt`：最佳生成器模型

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
python make_demo.py
python dehaze.py examples\hazy_input.jpg --output examples\gan_dehazed.jpg
```

## 限制

本项目使用小数据集和合成雾，用于对抗训练教学。真实应用应使用大型真实成对去雾数据，并警惕GAN生成不存在的细节。
