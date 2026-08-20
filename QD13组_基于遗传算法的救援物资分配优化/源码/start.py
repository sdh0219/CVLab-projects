#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键启动脚本（跨平台）
用法:
  python start.py          # 完整启动：检查依赖 → 导出数据 → 启动前端
  python start.py --skip-export   # 跳过数据导出，直接启动前端
  python start.py --export-only   # 仅导出数据，不启动前端
"""

import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.join(ROOT, 'code')
FRONTEND_DIR = os.path.join(ROOT, 'frontend')
REQUIREMENTS = os.path.join(ROOT, 'requirements.txt')
OUTPUT_RESULTS = os.path.join(ROOT, 'output', 'results.json')
API_PORT = os.environ.get('API_PORT', '5181')


def log(msg, level='info'):
    icons = {'info': '→', 'ok': '✓', 'warn': '⚠', 'err': '✗', 'step': '●'}
    print(f"  {icons.get(level, '→')} {msg}")


def header(title):
    print()
    print('=' * 60)
    print(f'  {title}')
    print('=' * 60)


def run(cmd, cwd=None, check=True):
    """执行命令"""
    result = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str))
    if check and result.returncode != 0:
        sys.exit(result.returncode)
    return result.returncode


def find_python():
    for name in ('python3', 'python'):
        path = shutil.which(name)
        if path:
            return path
    return None


def find_npm():
    return shutil.which('npm')


def check_python_deps(py):
    """检查并安装 Python 依赖"""
    header('步骤 1/4 · 检查 Python 环境')
    log(f'Python: {py}')

    try:
        subprocess.run([py, '-c', 'import numpy, matplotlib, flask'], check=True, capture_output=True)
        log('Python 依赖已就绪', 'ok')
    except subprocess.CalledProcessError:
        log('正在安装 Python 依赖...', 'warn')
        run([py, '-m', 'pip', 'install', '-r', REQUIREMENTS, '-q'])
        log('Python 依赖安装完成', 'ok')


def sync_cached_data(py):
    """将 output 缓存同步到前端静态目录"""
    sync_script = (
        'from export_for_frontend import sync_to_frontend; '
        'sync_to_frontend()'
    )
    subprocess.run([py, '-c', sync_script], cwd=CODE_DIR, check=False)


def export_data(py, force=False):
    """导出优化结果供前端使用；已有缓存时默认跳过"""
    header('步骤 2/4 · 加载/导出优化数据')

    if not force and os.path.isfile(OUTPUT_RESULTS):
        log(f'已存在缓存: output/results.json', 'ok')
        log('跳过模型运行，直接加载已保存数据', 'ok')
        log('如需重新运行请使用 --force-export 或在前端点击「运行算法」', 'warn')
        sync_cached_data(py)
        return

    export_script = os.path.join(CODE_DIR, 'export_for_frontend.py')
    if not os.path.exists(export_script):
        log(f'未找到 {export_script}', 'err')
        sys.exit(1)
    run([py, export_script], cwd=CODE_DIR)
    log('数据导出完成', 'ok')


def start_api_server(py):
    """后台启动 Flask API 服务"""
    header('步骤 3/4 · 启动后端 API')
    api_script = os.path.join(CODE_DIR, 'api_server.py')
    if not os.path.exists(api_script):
        log(f'未找到 {api_script}', 'err')
        sys.exit(1)

    env = os.environ.copy()
    env['API_PORT'] = API_PORT
    subprocess.Popen(
        [py, api_script],
        cwd=CODE_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    log(f'API 服务已启动: http://127.0.0.1:{API_PORT}', 'ok')


def check_node_deps():
    """检查并安装 Node 依赖"""
    header('步骤 4/4 · 启动 Vue 前端')
    npm = find_npm()
    if not npm:
        log('未找到 npm，请先安装 Node.js: https://nodejs.org/', 'err')
        sys.exit(1)
    log(f'npm: {npm}')

    node_modules = os.path.join(FRONTEND_DIR, 'node_modules')
    if not os.path.isdir(node_modules):
        log('正在安装前端依赖（首次运行需等待）...', 'warn')
        run([npm, 'install'], cwd=FRONTEND_DIR)
        log('前端依赖安装完成', 'ok')
    else:
        log('前端依赖已就绪', 'ok')

    return npm


def start_frontend(npm):
    """启动 Vite 开发服务器"""
    print()
    log('正在启动可视化前端...', 'step')
    log('访问地址: http://127.0.0.1:5180', 'ok')
    log('按 Ctrl+C 停止服务', 'warn')
    print()
    run([npm, 'run', 'dev'], cwd=FRONTEND_DIR, check=False)


def main():
    parser = argparse.ArgumentParser(description='救援物资分配优化 - 一键启动')
    parser.add_argument('--skip-export', action='store_true', help='跳过数据导出/同步')
    parser.add_argument('--export-only', action='store_true', help='仅导出数据')
    parser.add_argument('--force-export', action='store_true', help='强制重新运行模型并导出')
    args = parser.parse_args()

    print()
    print('  🚨 救援物资分配优化系统 - 一键启动')
    print('  基于遗传算法 · Vue 可视化前端')

    py = find_python()
    if not py:
        log('未找到 Python，请先安装 Python 3.8+', 'err')
        sys.exit(1)

    check_python_deps(py)

    if not args.skip_export:
        export_data(py, force=args.force_export)
    else:
        log('已跳过数据导出', 'warn')

    if args.export_only:
        print()
        log('数据导出完成，未启动前端', 'ok')
        return

    start_api_server(py)
    npm = check_node_deps()
    start_frontend(npm)


if __name__ == '__main__':
    main()
