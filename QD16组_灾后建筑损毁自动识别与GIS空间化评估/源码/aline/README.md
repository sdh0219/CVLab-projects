# A 线：建筑物灾后损毁自动识别

项目16「灾后损失自动评估与三维建模」A 线实现：基于灾前/灾后配对影像，用**孪生变化检测网络**逐栋识别建筑损毁等级（xBD 官方 4 级标度），并统计损毁数量与面积、生成损毁分布图与统计柱状图。

## 整条流水线

```
灾前/灾后影像 + WKT标注
        │
        ▼
 [data] 标注栅格化 ──► 定位掩膜(建筑/背景) + 损毁掩膜(0~4级)
        │
        ▼
 [model] 孪生U-Net：共享编码器分别编码前/后影像
        │           ├─ 定位头(灾前特征)      → 建筑分割
        │           └─ 损毁头(前后特征逐层差) → 5类损毁分级
        ▼
 [train] 联合损失(定位CE + 损毁加权CE)
        ▼
 [inference] 逐张预测 → 损毁掩膜.npy + 彩色图 + 叠加图
        ▼
 [stats] 连通域→逐栋众数等级 → 数量/面积统计 → CSV + 柱状图
```

## 目录结构

```
aline/
├── config.py                 # 所有参数（路径/类别/超参/物理参数）集中于此
├── requirements.txt
├── data/
│   ├── make_dummy_data.py     # 生成 xBD 格式合成数据（仅离线调试用）
│   ├── mask_from_json.py      # WKT 多边形 → 定位/损毁掩膜
│   └── dataset.py             # PyTorch Dataset（自动配对、在线栅格化、增强）
├── models/
│   └── siamese_unet.py        # 孪生 U-Net（ResNet 编码器 + 双解码头）
├── train.py                   # 训练（联合损失 + 损毁宏F1 评估 + 存最优权重）
├── inference.py               # 推理 → 掩膜/彩色图/叠加图
├── stats.py                   # 逐栋统计 + CSV + 柱状图
└── outputs/                   # 权重/预测/统计产物
```

## 快速开始（合成数据，验证流程）

```bash
pip install -r requirements.txt
python data/make_dummy_data.py     # 生成合成数据
python train.py --epochs 10        # 训练
python inference.py                # 推理
python stats.py                    # 统计出图
```

## 换成真实 xBD（正式跑）

1. 到 https://xview2.org/dataset 注册下载 xBD，解压后结构为：
   ```
   xBD/{train,test,hold}/images/*_pre_disaster.png  *_post_disaster.png
                        /labels/*_pre_disaster.json *_post_disaster.json
   ```
2. 改 `config.py`：
   - `DATA_ROOT` 指向 xBD 根目录
   - `IMG_SIZE = 1024`（显存不足则保持下采样，或自行切片为 512/512）
   - `PRETRAINED = True`（用 ImageNet 预训练编码器，真实数据必开）
   - `GSD_M` 按影像实际地面分辨率设置（xBD Maxar 约 0.5m）
3. `python train.py --epochs 50 --pretrained`
4. 删掉 `make_dummy_data.py` 即可，其余代码无需改动。

## 关键设计说明

- **孪生 + 特征差分**：编码器权重共享，损毁头吃灾前/灾后特征的逐层绝对差，本质是变化检测，对"建筑还在但塌了"的场景更敏感。
- **类别不平衡**：背景像素占绝大多数，损毁损失用类别权重 `[0.05,1,2,2,2]` 压低背景、强化重等级。
- **像素→建筑**：统计阶段先连通域分割出单栋，再取栋内损毁等级众数，避免边缘碎像素污染计数。
- **面积换算**：`面积(m²) = 像素数 × GSD²`。

## 评测指标

训练时打印各损毁等级 F1 与忽略背景的宏平均 F1（xView2 官方损毁评测口径）。

## 下一步（与项目其他部分衔接）

- 损毁分布图叠到 Cesium + PostGIS（你现成的 GIS 系统）
- 可选：把每栋损毁结果喂给 Qwen-VL 生成自然语言损毁描述，呼应多模态主线
- B 线（倾斜摄影三维重建 + 体积估算）单独实现
