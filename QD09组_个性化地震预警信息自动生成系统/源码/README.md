# 地震预警信息自动生成系统

## 使用说明

### 首次运行
```bash
双击 一键部署环境.bat
```
自动完成：Python检测/安装、虚拟环境创建、依赖安装、数据生成、系统自检。

### 后续启动
```bash
双击 start_project.bat
```
自动检查环境、启动Web服务、打开浏览器。

## 环境要求
- 操作系统：Windows 10/11 64位
- 磁盘空间：约 500 MB（含Python运行时和依赖包）
- 无需预先安装Python（项目自带Python 3.11安装程序）

## 项目结构
```
2_源码/
├── 一键部署环境.bat    # 一键部署（首次运行）
├── start_project.bat   # 一键启动（后续使用）
├── app.py              # Flask Web应用
├── main.py             # 数据处理脚本
├── code/               # 核心业务逻辑
├── crawler/            # 数据采集模块
├── data/               # 地震数据目录
├── templates/          # HTML模板
├── static/             # 静态资源（样式、图表、图片）
├── runtime/            # 项目自带Python安装程序
├── wheelhouse/         # 离线依赖包
├── logs/               # 运行日志
└── requirements.txt    # Python依赖清单
```

## 数据来源
- USGS（美国地质调查局）实时地震数据
- 包含 200+ 条最新真实地震记录

## 功能特性
- 四类人群个性化预警（普通居民/游客/应急人员）
- 200+ 真实地震事件选择
- 地震统计仪表盘（4张图表）
- 实时数据更新

## 技术栈
- Python 3.10-3.12
- Flask（Web框架）
- pandas（数据处理）
- matplotlib（数据可视化）
- requests（数据采集）
