# 基于 Transformer 的应急事件自动研判

一个可离线训练和演示的教学系统。它用字符级 Transformer Encoder 区分火灾、洪涝、地震、危化品泄漏、山体滑坡和其他事件，再提取事件要素并生成教学性处置提示。

## 系统流程

```text
报警文本 -> 字符分词 -> Transformer Encoder -> 灾种分类
                                   +-> 时间/地点/人员/风向提取
                                   +-> 风险级别与处置提示
```

## 环境要求

- Windows + **Python 3.10 ～ 3.12（64 位）**（代码使用了 `str | Path` 等较新语法，Python 3.9 及以下会报 TypeError，请全教室统一 3.10 以上版本）
- 联网仅用于 `pip install` 安装依赖；装好依赖后，本项目训练与预测**全程离线**可跑

## 运行

1. 双击 `install_train_demo.bat` 安装依赖、生成教学数据、训练模型并运行命令行演示。
2. 双击 `start_web_demo.bat`，浏览器访问 `http://127.0.0.1:5000`。

手动命令：

```powershell
python make_dataset.py
python train.py
python demo.py
python app.py
```

## 文件

- `data/events.jsonl`：六类合成教学文本
- `model.py`：Transformer Encoder
- `train.py`：训练与验证
- `analyzer.py`：模型推理、要素提取和规则研判
- `demo.py`：命令行演示
- `app.py`：Python标准库HTTP服务器网页演示，无需额外Web框架
- `event_transformer.pt`：已训练模型

## 安全边界

本项目的数据是为课堂生成的合成样本，不是经过行业验收的事故数据。风险等级和处置建议仅供教演示，不得用于自动启动响应、人员疏散或救援调度。实际应用必须接入经审核的预案和真实业务数据，并由有权人员审核。
