@echo off
REM ==========================================================
REM 社交媒体求救信息自动提取与定位 - 一键运行全流程 (Windows)
REM 使用项目根目录的 .venv 虚拟环境
REM ==========================================================
chcp 65001 >nul
cd /d "%~dp0\.."

echo ==========================================================
echo  [1/6] 数据准备: 生成地名库 + 原始数据集 + BIO 标注
echo ==========================================================
".venv\Scripts\python.exe" -m src.geo.build_geo_dict
".venv\Scripts\python.exe" -m src.data.build_dataset
".venv\Scripts\python.exe" -m src.data.annotate

echo.
echo ==========================================================
echo  [2/7] 基线评估 (对照实验)
echo ==========================================================
".venv\Scripts\python.exe" -m src.baselines.rule_based
if exist ".env" (
    ".venv\Scripts\python.exe" -m src.baselines.llm_ner --evaluate --shots 3
) else (
    echo [跳过 LLM 基线] 未找到 .env, 请配置 DASHSCOPE_API_KEY
)

echo.
echo ==========================================================
echo  [3/7] 训练 BERT NER 模型 (GPU 优先, 约 5-10 分钟)
echo ==========================================================
".venv\Scripts\python.exe" -m src.train

echo.
echo ==========================================================
echo  [4/7] 评估 BERT 模型 + 生成对比报告
echo ==========================================================
".venv\Scripts\python.exe" -m src.evaluate

echo.
echo ==========================================================
echo  [5/7] 批量推理 + 结构化导出 (CSV)
echo ==========================================================
".venv\Scripts\python.exe" -m src.infer --batch

echo.
echo ==========================================================
echo  [6/7] 下载静态资源 + 生成求救点分布图 (离线 HTML 仪表盘)
echo ==========================================================
".venv\Scripts\python.exe" scripts\download_static.py
".venv\Scripts\python.exe" -m src.visualize

echo.
echo ==========================================================
echo  全流程完成! 产物:
echo    - 模型权重: outputs\checkpoints\bert_ner_best\
echo    - 评估报告: outputs\reports\metrics.json
echo    - LLM 报告: outputs\reports\llm_ner_raw_3shot.json
echo    - 结构化表: data\processed\structured_results.csv
echo    - 分布地图: outputs\maps\rescue_map.html
echo ==========================================================
pause
