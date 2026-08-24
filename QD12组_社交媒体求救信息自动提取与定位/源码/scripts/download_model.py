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

    # modelscope 的缓存布局是 models/AI-ModelScope--bert-base-chinese/snapshots/<版本>/,
    # 而代码期望的加载路径是平铺的 models/AI-ModelScope/bert-base-chinese/。
    # 这里把快照内容复制/同步到目标目录, 让 src/config.py 的本地探测直接命中。
    import shutil
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    copied = skipped = 0
    for f in sorted(Path(path).iterdir()):
        dest = TARGET_DIR / f.name
        if f.name.startswith("."):
            continue
        if dest.exists() and dest.stat().st_size == f.stat().st_size:
            skipped += 1
            continue
        shutil.copy2(f, dest)
        copied += 1
    print(f"[OK] 已同步到 {TARGET_DIR} (复制 {copied} 个文件, 跳过已存在 {skipped} 个)")

    # 列出文件 + 校验大小
    print("\n文件清单:")
    total = 0
    for f in sorted(TARGET_DIR.iterdir()):
        size = f.stat().st_size
        total += size
        if size > 1024 * 1024:
            print(f"  {f.name:30s}  {size/1024/1024:.1f} MB")
        else:
            print(f"  {f.name:30s}  {size/1024:.1f} KB")
    print(f"  {'合计':30s}  {total/1024/1024:.1f} MB")

    print("\n" + "=" * 60)
    print("下载成功! 无需修改任何配置:")
    print(f"  src/config.py 会自动检测到本地模型目录")
    print(f"  {TARGET_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
