#!/usr/bin/env bash
# ==========================================================
# 社交媒体求救信息自动提取与定位 - 一键运行全流程 (Linux/Mac)
# 假设已激活虚拟环境 (source .venv/bin/activate)
# ==========================================================
set -e
cd "$(dirname "$0")/.."
PY="${PYTHON:-python}"

echo "=========================================================="
echo " [1/6] 数据准备: 生成地名库 + 原始数据集 + BIO 标注"
echo "=========================================================="
$PY -m src.geo.build_geo_dict
$PY -m src.data.build_dataset
$PY -m src.data.annotate

echo
echo "=========================================================="
echo " [2/7] 基线评估 (对照实验)"
echo "=========================================================="
$PY -m src.baselines.rule_based || true
if [ -f ".env" ]; then
    $PY -m src.baselines.llm_ner --evaluate --shots 3 || true
else
    echo "[跳过 LLM 基线] 未找到 .env, 请配置 DASHSCOPE_API_KEY"
fi

echo
echo "=========================================================="
echo " [3/7] 训练 BERT NER 模型"
echo "=========================================================="
$PY -m src.train

echo
echo "=========================================================="
echo " [4/7] 评估 BERT 模型 + 生成对比报告"
echo "=========================================================="
$PY -m src.evaluate

echo
echo "=========================================================="
echo " [5/7] 批量推理 + 结构化导出 (CSV)"
echo "=========================================================="
$PY -m src.infer --batch

echo
echo "=========================================================="
echo " [6/7] 下载静态资源 + 生成求救点分布图 (离线 HTML 仪表盘)"
echo "=========================================================="
$PY scripts/download_static.py
$PY -m src.visualize

echo
echo "=========================================================="
echo " 全流程完成! 产物:"
echo "   - 模型权重: outputs/checkpoints/bert_ner_best/"
echo "   - 评估报告: outputs/reports/metrics.json"
echo "   - LLM 报告: outputs/reports/llm_ner_raw_3shot.json"
echo "   - 结构化表: data/processed/structured_results.csv"
echo "   - 分布地图: outputs/maps/rescue_map.html"
echo "=========================================================="
