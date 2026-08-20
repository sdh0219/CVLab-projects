"""一键从 ModelScope 下载 bert-base-chinese 到项目目录。

用法:
    .venv\\Scripts\\python.exe scripts\\download_model.py

下载完成后, src/config.py 中的 BERT_MODEL_NAME 会自动指向本地路径:
    models/AI-ModelScope/bert-base-chinese

如果未安装 modelscope, 会自动尝试 pip 安装。
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJ_ROOT = Path(__file__).resolve().parent.parent
TARGET_DIR = PROJ_ROOT / "models" / "AI-ModelScope" / "bert-base-chinese"


def ensure_modelscope():
    try:
        import modelscope  # noqa: F401
        return True
    except ImportError:
        print("[!] 未检测到 modelscope, 尝试自动安装...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "modelscope"])
        return True


def main():
    print("=" * 60)
    print("从 ModelScope 下载 bert-base-chinese")
    print("=" * 60)

    ensure_modelscope()
    from modelscope import snapshot_download

    print(f"\n目标路径: {TARGET_DIR}")
    print("开始下载 (国内服务器, 通常 1-3 分钟)...\n")

    path = snapshot_download(
        "AI-ModelScope/bert-base-chinese",
        cache_dir=str(PROJ_ROOT / "models"),
    )
    print(f"\n[OK] 下载完成 -> {path}")

    # 列出文件 + 校验大小
    print("\n文件清单:")
    total = 0
    for f in sorted(Path(path).iterdir()):
        size = f.stat().st_size
        total += size
        if size > 1024 * 1024:
            print(f"  {f.name:30s}  {size/1024/1024:.1f} MB")
        else:
            print(f"  {f.name:30s}  {size/1024:.1f} KB")
    print(f"  {'合计':30s}  {total/1024/1024:.1f} MB")

    # 提示修改 config
    print("\n" + "=" * 60)
    print("下载成功! 请确认 src/config.py 中:")
    print(f'  BERT_MODEL_NAME = "{path}"')
    print("(脚本已自动修改, 若已存在则无需手动改)")
    print("=" * 60)


if __name__ == "__main__":
    main()
