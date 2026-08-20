# 社交媒体求救信息自动提取与定位

> 面向"AI+防灾减灾"课程的大作业项目。利用 NLP/深度学习方法从微博、短视频评论、
> 新闻留言或模拟文本中**自动提取灾害求救信息**(地点、人员、灾情、需求),
> 并**解析地理位置生成求救点分布图**, 服务于应急救援决策。

---

## 项目亮点

- **完整深度学习流水线**: 数据构建 → 清洗标注 → BERT NER 训练 → 评估 → 地理编码 → 地图可视化
- **测试集 F1 = 0.9511**,相比规则基线 0.31 **提升 64 个百分点**,深度学习完胜
- **4 类实体抽取**: `LOC`(地点)、`PER`(人员)、`DIS`(灾情)、`NEED`(需求),BIO 标注体系
- **BERT + CRF** 序列标注模型,纯 PyTorch 实现 CRF(无外部依赖)
- **三方法对比体系**: 规则基线(0.31)→ LLM few-shot(0.65,通义千问零训练)→ BERT+CRF(0.95),覆盖"规则→提示工程→监督微调"完整谱系
- **本地+在线双地理编码**:内置 212 条中国灾区地名库,地理编码成功率 100%
- **🌐 求救点分布仪表盘** [`outputs/maps/rescue_map.html`](outputs/maps/rescue_map.html):**JS/CSS 全部本地化(0 CDN 引用)**,底图用高德中文街道瓦片(国内速度快),救援指挥中心风格:顶部统计徽章 + 左侧灾种柱状图 + 右侧地图 + 底部可搜索/筛选表格,288 个求救点按紧急程度着色 + 按灾种显示 emoji,浏览器打开即可

---

## 🎯 快速预览(一眼看懂项目做什么)

**输入一条求救微博:**
```
急!郑州京广路隧道被淹,水深2米,我们一辆车4个人出不来,求救船只,电话13900001111
```

**系统全自动输出:**

| 地点 | 人员 | 灾情 | 需求 | 紧急程度 | 经纬度 |
|------|------|------|------|----------|--------|
| 郑州京广路隧道 | 一辆车4个人 | 被淹 / 水深2米 | 船只 / 电话13900001111 | 🔴 紧急 | (113.64, 34.748) |

**并在地图上画一个 🔴 红点**,点击可看完整信息。

对 288 条求救文本批量处理后,**生成 [`outputs/maps/rescue_map.html`](outputs/maps/rescue_map.html)**——一份交互式仪表盘(JS/CSS 全部本地化,0 CDN;底图为高德中文街道瓦片,在线加载):
- **顶部**:标题栏 + 实时统计徽章(总求救/紧急数/已定位数)
- **左侧**:4 个统计卡片 + 灾种柱状图 + 紧急程度图例
- **右侧地图**:高德中文底图 + 288 个标记按紧急程度着色 + 按灾种显示 emoji,点击看富弹窗
- **底部表格**:可搜索/按紧急程度/按灾种筛选,点击行自动飞到地图该点
- 288 点全部成功定位(地理编码成功率 100%)
- 断网时:底图降级为纯色背景,**标记/弹窗/表格全部可用**

```bash
python scripts/download_static.py   # 首次: 下载静态资源到本地 (约 278 KB)
start outputs\maps\rescue_map.html   # Windows 直接打开
```

---

## 目录结构

以下为 **git 跟踪的真实文件树**(共 54 个文件)。`📁` 标注目录,`📦` 标注产物。

```
mediaSearch/
├── README.md                          # 本文件
├── requirements.txt                   # 依赖清单 (带版本号)
├── data/                              # 📁 数据包 (任务书要求)
│   ├── raw/
│   │   └── distress_messages_raw.jsonl        # 原始数据 (288 条, 68 种子 + 220 模板)
│   ├── processed/
│   │   ├── train.jsonl / dev.jsonl / test.jsonl  # BIO 标注 (201/28/59, 7:1:2)
│   │   └── structured_results.csv             # 📦 结构化结果表 (推理导出)
│   └── geo/
│       └── china_geo_dict.json                # 本地地名→经纬度字典 (212 条)
│
├── models/                            # 📁 BERT 权重 (1.6GB) → scripts/download_model.py 重下
│
├── src/                               # 📁 源码 (17 个 Python 模块)
│   ├── __init__.py
│   ├── config.py                      # 集中配置: 路径、标签、超参
│   ├── data/
│   │   ├── __init__.py
│   │   ├── build_dataset.py           # 生成原始数据集
│   │   ├── annotate.py                # 结构化标注 → BIO + 划分 train/dev/test
│   │   ├── preprocess.py              # 文本清洗 (URL/@/#/emoji/繁简)
│   │   └── dataset.py                 # PyTorch Dataset + Collate
│   ├── models/
│   │   ├── __init__.py
│   │   ├── bert_ner.py                # BERT + Linear (+ CRF) 模型
│   │   └── crf.py                     # 纯 PyTorch CRF + Viterbi 解码
│   ├── baselines/
│   │   ├── __init__.py
│   │   ├── rule_based.py              # 规则/词典基线 (对照实验)
│   │   └── llm_ner.py                 # LLM few-shot 基线 (通义千问, 需 API Key)
│   ├── geo/
│   │   ├── __init__.py
│   │   ├── build_geo_dict.py          # 生成地名库
│   │   ├── local_db.py                # 本地最长匹配
│   │   ├── online_api.py              # 高德/百度 API (带 AK 占位)
│   │   └── geocoder.py                # 统一接口: 本地优先 → 在线回退
│   ├── train.py                       # 训练 (含 TensorBoard + 日志 + 曲线图)
│   ├── evaluate.py                    # 评估 (P/R/F1 + bad case)
│   ├── infer.py                       # 推理 (文本→实体→地理编码→CSV)
│   └── visualize.py                   # 求救点分布仪表盘 (手写 HTML + 高德底图)
│
│
├── outputs/                           # 📁 运行产物
│   ├── checkpoints/                   # 训练模型权重
│   ├── maps/                          # 📁 求救点分布图
│   │   ├── rescue_map.html            # 📦 新版仪表盘 (136KB, 高德底图, 本地 JS/CSS)
│   │   ├── rescue_map_old.html        # 📦 旧版 folium (600KB, 含 CDN, 归档对比用)
│   │   └── static/                    # 离线静态资源 (278KB)
│   │       ├── jquery/jquery-3.7.1.min.js
│   │       ├── leaflet/{leaflet.js, leaflet.css}
│   │       └── markercluster/{*.js, *.css}
│   └── reports/                       # 📁 训练/评估报告
│       ├── train_log.txt              # 完整训练日志
│       ├── train_history.json         # 训练历史 (JSON, 画图用)
│       ├── training_curve.png         # 📦 静态训练曲线图 (放 PPT)
│       ├── metrics.json               # BERT vs 规则基线对比指标
│       └── badcase.txt                # 17 条预测错误样本
│
├── scripts/                           # 📁 辅助脚本
│   ├── download_model.py              # 一键下载 bert-base-chinese (ModelScope)
│   ├── download_static.py             # 下载地图静态资源到 outputs/maps/static/
│   ├── regen_old_map.py               # 还原旧版 folium 地图
│   ├── run_all.bat / run_all.sh       # 一键运行全流程 (Win/Linux)
│   └── start_tensorboard.bat / .sh    # 启动 TensorBoard (端口 6006)
│
└── (gitignore 排除, 不在仓库内但可重建)
    ├── .venv/                 # 虚拟环境 (3.6GB) → pip install -r requirements.txt 重建
    ├── models/                # BERT 权重 (1.6GB) → scripts/download_model.py 重下
    ├── outputs/checkpoints/   # 训练后权重 (400MB) → python -m src.train 重新训练
    └── outputs/reports/tensorboard/  # TB 日志 → 训练自动生成
```

**说明**:`📁` 目录、`📦` 产物(由代码生成但已纳入版本控制,方便直接查看)。仓库总大小约 **0.5 MB**,大文件全部由 `.gitignore` 排除,可通过上述命令重新构建。

---

## 环境配置

### 1. Python 环境

建议使用项目自带的虚拟环境 (`.venv`)。如需从零配置:

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. PyTorch (GPU 版,推荐)

PyTorch 需根据本机 CUDA 版本单独安装。访问 <https://pytorch.org/get-started/locally/>
选择对应版本,例如 (CUDA 12.1):

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

CPU 版可直接 `pip install torch`。

### 3. 验证环境

```bash
python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
python -c "from src.config import print_config; print_config()"
```

### 4. (可选) 高德地图 API Key

本项目默认使用本地地名库 (212 条中国灾区地名) 即可完成地理编码,
**无需 API Key 也能跑通全流程**。如需更全面的覆盖,可申请高德 Web 服务 Key:

1. 访问 <https://console.amap.com/dev/key/app> 注册并创建"Web 服务"类型 Key
2. 设置环境变量:
   ```bash
   # Windows
   set AMAP_KEY=你的key
   # Linux/macOS
   export AMAP_KEY=你的key
   ```

### 5. 首次运行会下载 BERT 模型

本项目预训练模型采用 `bert-base-chinese`(约 400MB)。**强烈推荐用 ModelScope
国内镜像离线下载**,避免训练时网络不稳定:

```bash
# 一键从 ModelScope 下载到 models/ 目录 (国内速度快, 无需科学上网)
.venv\Scripts\python.exe scripts\download_model.py
```

脚本会自动:
1. 安装 `modelscope`(如未装)
2. 下载 `bert-base-chinese` 全部文件到 `models/AI-ModelScope/bert-base-chinese/`
3. 配合 `src/config.py` 中已设好的本地路径,实现**完全离线训练**

> 也可以手动从 <https://modelscope.cn/models/AI-ModelScope/bert-base-chinese/files>
> 下载 5 个必需文件:`config.json / pytorch_model.bin / vocab.txt / tokenizer.json / tokenizer_config.json`,
> 放进 `models/bert-base-chinese/` 后修改 `src/config.py` 的 `BERT_MODEL_NAME`。

如果仍想用 HuggingFace 在线下载,设置国内镜像:
```bash
set HF_ENDPOINT=https://hf-mirror.com    # Windows
export HF_ENDPOINT=https://hf-mirror.com # Linux/macOS
```

---

## 快速开始

### 一键运行 (推荐)

```bash
# Windows
scripts\run_all.bat

# Linux/macOS (先 source .venv/bin/activate)
bash scripts/run_all.sh
```

该脚本会依次完成: 数据准备 → 规则基线 → BERT 训练 → 评估 → 推理 → 可视化。

### 分步运行

```bash
# 1. 数据准备
python -m src.geo.build_geo_dict      # 生成地名库
python -m src.data.build_dataset      # 生成原始数据
python -m src.data.annotate           # BIO 标注 + 划分

# 2. 基线评估 (对照实验, 不需要训练)
python -m src.baselines.rule_based                              # 规则基线
python -m src.baselines.llm_ner --evaluate --shots 3            # LLM 基线 (需配置 DASHSCOPE_API_KEY)

# 3. 训练 BERT NER 模型 (GPU 约 5-10 分钟, CPU 较慢)
python -m src.train
python -m src.train --epochs 5 --no_crf   # 自定义参数 / 不用 CRF

# 4. 评估
python -m src.evaluate

# 5. 批量推理 + 结构化导出
python -m src.infer --batch

# 6. 求救点分布图
python -m src.visualize
```

> **LLM 基线说明**:运行前需在项目根目录创建 `.env` 文件,写入 `DASHSCOPE_API_KEY=sk-你的key`
> (到 <https://bailian.console.aliyun.com/> 申请)。详见技术方案 4.5.2 节。

### 单条文本推理 (演示用)

```bash
python -m src.infer --text "求助! 汶川映秀镇3楼塌了,有3个人,急需水,电话13900001234"
```

---

## 训练监控 (TensorBoard)

训练过程会自动记录到 `outputs/reports/tensorboard/`,可用 TensorBoard 实时查看曲线:

```bash
# Windows
scripts\start_tensorboard.bat

# Linux/macOS
bash scripts/start_tensorboard.sh

# 或直接运行
tensorboard --logdir outputs/reports/tensorboard --port 6006
```

浏览器访问 **http://localhost:6006**,可以看到:

| 面板 | 内容 | 用途 |
|------|------|------|
| **SCALARS** | `train/loss_step` 每个 step 的 loss | 实时看训练是否在收敛 |
| **SCALARS** | `train/learning_rate` | 学习率 warmup 衰减曲线 |
| **SCALARS** | `dev/f1`、`dev/precision`、`dev/recall` | 每 epoch 的 dev 指标 |
| **SCALARS** | `dev_f1_by_type/{LOC,PER,DIS,NEED}` | 分类型 F1 曲线 |
| **HPARAMS** | 超参 + 最终 best_dev_f1 | 多次实验对比(如 CRF vs no-CRF) |
| **TEXT** | 训练配置、数据规模 | 实验记录 |

**多次实验对比**:每次训练(不同超参/不同种子)会生成独立的子目录(带时间戳),
TensorBoard 会把多条曲线叠加显示,方便对比。例如做 CRF 消融实验:

```bash
python -m src.train            # BERT+CRF
python -m src.train --no_crf   # BERT 不带 CRF
# 然后看 TensorBoard, 两条 F1 曲线会叠加, 直观对比 CRF 的提升
```

> 静态训练曲线图也同时生成在 `outputs/reports/training_curve.png`(可直接放 PPT)。

---

## 求救点分布图(核心可视化产物)

项目的**最终可视化产物**是 `outputs/maps/rescue_map.html`——一份**纯离线、富 UI 的
交互式 HTML 仪表盘**(救援指挥中心风格),把所有求救点按真实经纬度标在中国地图上,
**浏览器直接打开即可,无需服务器、无需联网**。

```bash
# Windows 直接打开
start outputs\maps\rescue_map.html

# 首次使用前, 下载静态资源到本地 (约 278 KB, 一次即可)
python scripts/download_static.py

# 基于 structured_results.csv 重新生成页面
python -m src.visualize
```

### 🌐 完全离线设计

页面 **JS/CSS 全部本地引用**(不依赖任何 CDN),从原来 folium 的 13 个 CDN 引用降到 **0 个**:

| 资源 | 来源 | 大小 |
|------|------|------|
| Leaflet 核心 JS/CSS | 本地 `outputs/maps/static/leaflet/` | 157.6 KB |
| MarkerCluster JS/CSS | 本地 `outputs/maps/static/markercluster/` | 35.0 KB |
| jQuery 3.7.1 | 本地 `outputs/maps/static/jquery/` | 85.5 KB |
| 求救点数据 | 内嵌 JSON(288 条) | — |

> **关于地图底图**:街道瓦片是百万张图片,无法打包。页面会**尝试**加载在线底图
> (**高德中文街道瓦片**,国内速度快、标注为中文),离线时自动降级为浅蓝背景——
> **但所有标记、弹窗、筛选、定位功能完全离线可用**。
>
> 准确表述:**JS/CSS 全部本地化(0 CDN),底图在线加载**。生产环境如需更稳定接入,
> 建议申请高德 AK 走官方 JS API(本项目用公开瓦片 URL,学习用途)。

### 🎨 仪表盘布局(告别单调地图)

```
┌─────────────────────────────────────────────────────────────┐
│ 🆘 灾害求救信息监控系统   [📍 总求救 288] [🔴 紧急 127] [✅ 已定位]│  ← 顶部标题栏
├──────────────┬──────────────────────────────────────────────┤
│ 📊 求救统计  │                                              │
│ ┌────┬────┐ │                                              │
│ │288 │127 │ │                                              │
│ │总数│紧急 │ │              交互式地图                      │
│ ├────┼────┤ │       (自定义图标 + 聚合 + 弹窗)              │
│ │115 │ 46 │ │                                              │
│ │高危│中等 │ │                                              │
│ └────┴────┘ │                                              │
│ 🌪️ 灾种分布 │                                              │
│ 地震 ▓▓▓▓▓ │                                              │
│ 洪水 ▓▓▓   │                                              │
│ 火灾 ▓▓    │                                              │
│ ...         │                                              │
├──────────────┴──────────────────────────────────────────────┤
│ 📋 求救信息列表  [🔍搜索] [全部][紧急][高][中] [灾种▼]      │  ← 底部表格
│ 🔴 地震 雅安芦山县  我们14人  食物/电话  原文...  [📍 定位]   │
│ 🟠 洪水 鹤壁浚县   有6个老人 急需药品   原文...  [📍 定位]   │
└─────────────────────────────────────────────────────────────┘
```

### 交互特性

| 特性 | 说明 |
|------|------|
| 📍 **288 个标记** | 全量数据,地理编码 |
| 🎨 **自定义图标** | 按紧急程度着色(🔴紧急/🟠高/🟡中)+ 按灾种显示 emoji(📈地震/🌊洪水/🌀台风/⛰️地质灾害/🔥火灾/❄️暴雪) |
| 🔍 **标记聚合** | MarkerCluster 自动聚合密集区域,缩放时展开 |
| 🪟 **富弹窗** | 点击标记显示灾种、紧急程度、地点、人员、灾情、需求、定位、原文 |
| 📊 **实时统计** | 左侧 4 个统计卡片 + 灾种柱状图 + 紧急程度图例 |
| 🔍 **表格搜索** | 按地点/人员/需求/原文关键词搜索 |
| 🎛️ **多维筛选** | 按紧急程度(全部/紧急/高/中)+ 按灾种下拉筛选 |
| 🎯 **点击定位** | 点击表格任意行 → 地图自动飞到该点并展开弹窗 |
| 📦 **单文件部署** | HTML + static/ 目录,可邮件发送,无需服务器 |

### 颜色与图标分布(288 个求救点)

| 维度 | 类别 | 数量 | 颜色/图标 |
|------|------|------|----------|
| 紧急程度 | 紧急 | 127 | 🔴 `#dc3545` |
| 紧急程度 | 高 | 115 | 🟠 `#fd7e14` |
| 紧急程度 | 中 | 46 | 🟡 `#ffc107` |
| 灾种 | 地震 | (动态统计) | 📈 |
| 灾种 | 洪水 | (动态统计) | 🌊 |
| 灾种 | 台风 | (动态统计) | 🌀 |
| 灾种 | 地质灾害 | (动态统计) | ⛰️ |
| 灾种 | 火灾 | (动态统计) | 🔥 |

### 演示建议

这是**汇报演示中最有视觉冲击力的环节**。推荐演示流程:

1. 浏览器打开 `rescue_map.html`,展示仪表盘全貌(统计 + 地图 + 表格);
2. 滚轮缩放到某灾区(如汶川/郑州),展开聚合标记;
3. 点击红色标记,展示富弹窗里的结构化信息;
4. 在搜索框输入"郑州"或"船",展示实时筛选;
5. 点击"紧急"按钮,只看紧急求救;
6. 点击表格某行,展示地图自动飞到该点;
7. 强调:"**全部 JS/CSS 离线,可部署到无网环境**"。

---

## 使用示例

输入:
```
求助! 郑州京广路隧道被淹,水深2米,我们一辆车4个人出不来,求救船只,电话13900001111
```

输出:
```
实体: [('LOC', '郑州京广路隧道'), ('DIS', '被淹'), ('DIS', '水深2米'),
       ('PER', '一辆车4个人'), ('NEED', '船只'), ('NEED', '电话13900001111')]
  地点 : 郑州京广路隧道
  人员 : 一辆车4个人
  灾情 : 被淹 / 水深2米
  需求 : 船只 / 电话13900001111
  定位 : (113.64, 34.748)  匹配=郑州京广路隧道  来源=local
```

---

## 数据来源(诚实说明)

在设计数据前,我们调研了中文 NER 公开数据集:

| 数据集 | 实体类型 | 能否复用 |
|--------|----------|----------|
| [CLUENER2020](https://github.com/CLUEbenchmark/CLUENER2020) | 地址/姓名/机构等 10 类 | LOC/PER 可复用,无 DIS/NEED |
| [Weibo NER](https://www.modelscope.cn/datasets/damo/weibo_ner) | GPE/LOC/ORG/PER | 文风接近,无 DIS/NEED |

**结论**:通用中文 NER 数据集存在且可用,但**专门标注"灾情 + 需求"的灾害求救 NER 数据集没有现成的**。因此本项目采用半合成策略(68 条人工种子 + 220 条模板扩增),保证 4 类实体覆盖、标注 100% 准确。详见 `docs/数据字段说明.md`。

### 数据规模

| 文件 | 说明 | 字段 |
|------|------|------|
| `distress_messages_raw.jsonl` | 原始数据(288 条) | `id, text, entities[{type,text}], urgency, source` |
| `train/dev/test.jsonl` | BIO 标注数据 | `id, text, tokens, tags, entities[{type,start,end,text}], urgency` |
| `china_geo_dict.json` | 地名库(212 条) | `{地名: {lng, lat, province, level}}` |
| `structured_results.csv` | 结构化结果表 | `id, 原文, 地点, 人员, 灾情, 需求, 紧急程度, 经度, 纬度, 匹配地名` |

---

## 技术方案与文档

- 📄 [`docs/技术方案.md`](docs/技术方案.md) — 2000-4000 字技术方案(背景、方法、结果、应用价值)
- 📄 [`docs/数据字段说明.md`](docs/数据字段说明.md) — 数据来源、字段定义、预处理流程
- 📄 [`docs/PPT大纲.md`](docs/PPT大纲.md) — 8-12 页汇报 PPT 大纲与配图建议

---

## 常见问题

**Q: 训练时报 `OSError: ... bert-base-chinese` 下载失败?**
A: 推荐用 ModelScope 一键下载(国内镜像):`.venv\Scripts\python.exe scripts\download_model.py`,
   下载到 `models/AI-ModelScope/bert-base-chinese/` 后自动离线训练。
   也可以设置 HF 镜像 `set HF_ENDPOINT=https://hf-mirror.com` 后重试。

**Q: 没有 GPU 能跑吗?**
A: 可以。CPU 上训练每个 epoch 约 5-10 分钟,建议先用 `--epochs 3` 测试。
   推理时 CPU 也能用,只是稍慢。

**Q: 地理编码定位不到?**
A: 本地库覆盖 212 条典型灾区地名,基本能匹配数据集。若用自定义文本,
   建议配置高德 API Key 以提升覆盖率。

**Q: 怎么录制演示视频?**
A: 打开 `notebooks/demo.ipynb`,从上到下依次运行单元格,配合讲解录制即可。

**Q: TensorBoard 提示 "TensorFlow installation not found"?**
A: 正常,不影响使用。这是告诉我们没装 TensorFlow(我们用 PyTorch),只是
   少了一些高级功能,SCALARS/HPARAMS/TEXT 这些我们用的面板都正常。

---

## 任务清单 (对照任务书)

- [x] 构建 ≥100 条灾害求救文本样例 (实际 288 条)
- [x] 提取地点、人员、灾情、需求等关键信息 (4 类实体, 测试集 F1=0.95)
- [x] 将文本信息结构化为表格 ([`structured_results.csv`](data/processed/structured_results.csv), 288 条)
- [x] 根据地点信息生成求救点分布图 ([`rescue_map.html`](outputs/maps/rescue_map.html), 288 点详见上文「求救点分布图」章节)
- [x] 分析该方法在应急救援中的应用价值 (见技术方案文档)
- [x] 数据包: 文本数据、标注样例、结构化结果表
- [x] 源码: 清洗、关键词/NER、地理编码、可视化
- [x] 技术方案
