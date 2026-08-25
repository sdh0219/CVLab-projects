# 多层感知机的灾害图像分类

本项目与课件示意图对应，使用三个可解释图像特征和两隐藏层 MLP，输出图像为火灾的概率。神经网络的前向传播、二元交叉熵和反向传播都由 NumPy 从零实现。

## 模型结构

`3个特征 -> 8个ReLU神经元 -> 4个ReLU神经元 -> 1个Sigmoid输出`

- x1：火焰色彩比例
- x2：烟雾纹理熵
- x3：边缘方向响应
- 输出概率 >= 0.5：火灾；否则：非火灾

## 项目文件

- `data/fire/` 和 `data/normal/`：20 张教学样本及来源清单
- `features.py`：图像特征提取
- `mlp.py`：MLP 前向传播、反向传播、训练、保存和加载
- `train.py`：小批量训练并生成模型与损失曲线
- `predict.py`：输出单张图像的火灾概率
- `requirements.txt`：依赖库清单

## 环境要求

- Windows + **Python 3.10 ～ 3.12（64 位）**（代码使用了 `str | Path` 等较新语法，Python 3.9 及以下会报 TypeError，请全教室统一 3.10 以上版本）
- 联网仅用于 `pip install` 安装依赖；装好依赖后，本项目训练与预测**全程离线**可跑

## 运行

在 Windows 上双击 `install_and_train.bat`，或者手动执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python train.py
python predict.py data\fire\fire_01.jpg
```

## 教学说明

此项目使用小数据集演示 MLP 如何学习非线性决策边界。训练集准确率不等于对新图像的泛化能力，不应直接用于真实火灾告警。
